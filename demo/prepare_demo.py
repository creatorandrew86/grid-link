"""Build reproducible, clearly labelled pitch fixtures; --seed writes only our demo UUIDs.

Run: .tools/venv/Scripts/python.exe demo/prepare_demo.py --seed
Rerun --seed before rehearsals to reset our demo memberships/preferences (no deletes).
"""
import argparse
import csv
import json
import os
import runpy
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.database import Database
from app.sign_up import hash_password
from app.models import Participant
from app.community_battery import ComparisonInput, compare_batteries, measured_days
from app.battery import BatteryScenario, describe_schedule, optimise

OUT = ROOT / "demo"
PUBLIC = ROOT / "public" / "demo"
EMAIL = "pitch@gridlink.demo"
PASSWORD = "GridLinkPitch26!"
SOURCES = {
    "load": "https://data.open-power-system-data.org/household_data/2020-04-15/",
    "price": "https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv",
    "weather": "https://open-meteo.com/en/docs/historical-weather-api",
    "equipment": "https://powersense.ro/baterie-deye-se-g5-1-pro-b/",
    "specification": "https://deye.com/wp-content/uploads/2026/01/deye-se-g5.1-pro-b-series_brochure-20260115auv1.0.pdf",
}


def uid(name):
    return str(uuid5(NAMESPACE_URL, "gridlink-hackathon-2026/" + name))


def catalogue():
    return {"comparison": {"source": "measured", "funding_rule": "equal_share", "horizon_years": 10,
        "discount_rate": .06, "connection_import_kw": 20, "connection_export_kw": 20,
        "dispatch_wear_ron_per_kwh": .15,
        "designs": [{"chemistry": "LFP", "capacity_kwh": 5.12 * n, "power_kw": min(2.56 * n, 5),
                     "installed_cost_ron": round(4750.21 * n + 1500, 2), "efficiency": .9,
                     "usable_fraction": .9, "service_years": 10, "annual_fade": .02,
                     "annual_maintenance_ron": 100} for n in (1, 2, 3, 4, 6, 8, 12, 16, 20)]},
        "quote_source": "PowerSense published Deye SE-G5.1 Pro-B module: 4,750.21 RON incl. VAT, excluding installation; not an accepted installation quote",
        "quote_date": "2026-10-05", "data_mode": "demo_replay",
        "dataset_source": "OPSD/CoSSMic measured German household donor days mapped to July 2026 Romanian OPCOM prices; Bucharest ERA5 solar proxy. Fictional communities.",
        "assumptions_source": "Demo assumes existing compatible 5 kW inverter/shared meter, 1,500 RON installation, 20 kW grid limits, 90% system round-trip efficiency, 2% annual fade, 100 RON/year maintenance and 6% discount rate. Manufacturer capacity/power; other values are explicit scenario assumptions. Export credit is zero; dynamic import = 1.21*(PZU + 0.5879032), a tariff scenario rather than an actual bill."}


def build():
    definitions = [
        ("origin", "DEMO - Linden Court", "declined", False),
        ("solar", "DEMO - Solar Commons", "approved", True),
        ("flat", "DEMO - Fixed Tariff Homes", "interested", True),
        ("sparse", "DEMO - Incomplete History", "undecided", False),
    ]
    communities = [{"id": uid(slug), "slug": "hackathon-demo-" + slug, "name": name, "currency": "RON",
        "timezone": "Europe/Bucharest", "battery_policy": policy, "battery_accepting_members": accepting,
        "battery_meter_boundary": "shared_meter", "network_zone": "HACKATHON-DEMO-ONLY",
        "description": json.dumps({"gridlink_demo": True, "battery_analysis_config": catalogue()})}
        for slug, name, policy, accepting in definitions]
    specs = [("pitch", "origin", 2, 0), ("neighbour", "origin", 5, 0),
             ("solar-one", "solar", 3, 10), ("solar-two", "solar", 4, 10),
             ("flat-one", "flat", 5, 0), ("sparse-one", "sparse", 2, 0)]
    loads = {}
    donors = {}
    with (ROOT / "research/romania/measured-demand-profiles.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if "2026-07-01" <= r["target_day"] <= "2026-07-30":
                key = (int(r["house"]), r["target_day"], int(r["hour"]))
                loads[key] = float(r["load_kwh"])
                donors[key] = r["source_utc"]
    with (ROOT / "research/romania/hourly-prices-weather.csv").open(encoding="utf-8") as f:
        weather = [r for r in csv.DictReader(f) if "2026-07-01" <= r["bucharest_time"][:10] <= "2026-07-30"]
    assert len(weather) == 720
    participants = []
    password_hash = hash_password(PASSWORD)
    for slug, community, house, solar in specs:
        mean = statistics.mean(loads[(house, r["bucharest_time"][:10], datetime.fromisoformat(r["bucharest_time"]).hour)] for r in weather)
        participants.append({"id": uid(slug), "community_id": uid(community), "name": "Demo " + slug.replace('-', ' ').title(),
            "email": EMAIL if slug == "pitch" else slug + "@gridlink.demo", "password_hash": password_hash,
            "pod": "GLDEMO2026" + slug.replace('-', '').upper(), "type": "prosumer" if solar else "consumer",
            "load_kw": round(mean, 4), "solar_kwp": solar})
    events = defaultdict(list)
    for community in communities:
        for r in weather:
            day, hour = r["bucharest_time"][:10], datetime.fromisoformat(r["bucharest_time"]).hour
            if community["id"] == uid("sparse") and day > "2026-07-05":
                continue
            profiles = {uid(slug): {"load_kwh": loads[(house, day, hour)],
                "generation_kwh": max(0., solar * float(r["bucharest_ghi_w_m2"]) / 1000 * .8),
                "source_utc": donors[(house, day, hour)]} for slug, _, house, solar in specs}
            rows = [profiles[p["id"]] for p in participants if p["community_id"] == community["id"]]
            summary = {"mode": "demo_battery", "currency": "RON", "meter_boundary": "shared_meter",
                       "battery_free_baseline": True, "interval_minutes": 60, "demo_member_profiles": profiles,
                       "measurement": {"load_kwh": sum(v["load_kwh"] for v in rows),
                           "generation_kwh": sum(v["generation_kwh"] for v in rows),
                           "import_price_ron": 1.2 if community["id"] == uid("flat") else 1.21 * (float(r["price_lei_kwh"]) + .5879032),
                           "export_price_ron": 0.,
                           "member_loads_kwh": {p["id"]: profiles[p["id"]]["load_kwh"] for p in participants if p["community_id"] == community["id"]},
                           "member_generation_kwh": {p["id"]: profiles[p["id"]]["generation_kwh"] for p in participants if p["community_id"] == community["id"]}}}
            events[community["id"]].append({"community_id": community["id"], "interval_start": r["utc"], "summary": summary})
    pods = [{"id": uid("pod-" + p["email"]), "community_id": p["community_id"], "pod": p["pod"], "is_active": True,
             "battery_eligible_communities": [uid("solar"), uid("flat")] if p["id"] == uid("pitch") else []} for p in participants]
    interests = [{"participant_id": p["id"], "community_id": p["community_id"],
                  "interested": p["community_id"] == uid("solar")} for p in participants]
    return communities, participants, events, pods, interests


def seed(data):
    db = Database()
    communities, participants, events, pods, interests = data
    groups = [("communities", communities, "id"), ("approved_pods", pods, "id"),
              ("participants", participants, "id"), ("community_battery_interest", interests, "participant_id")]
    for table, rows, key in groups:
        for row in rows:
            existing = db.remote("GET", table, query=f"?{key}=eq.{row[key]}&limit=1")
            db.remote("PATCH" if existing else "POST", table, row, query=f"?{key}=eq.{row[key]}" if existing else "")
        print("Seeded/reset", table, len(rows), flush=True)
    for cid, rows in events.items():
        existing = db.remote("GET", "clearing_events", query=f"?community_id=eq.{cid}&select=interval_start&limit=1000")
        seen = {datetime.fromisoformat(r["interval_start"]) for r in existing}
        fresh = [r for r in rows if datetime.fromisoformat(r["interval_start"]) not in seen]
        for i in range(0, len(fresh), 200):
            db.remote("POST", "clearing_events", fresh[i:i+200])
        print("Demo archive", cid, len(rows), "intervals; added", len(fresh), flush=True)
    print("Demo account:", EMAIL, "/", PASSWORD, flush=True)


def analyse(data):
    communities, participants, events, _, _ = data
    request = ComparisonInput.model_validate(catalogue()["comparison"])
    member = Participant.model_validate(participants[0])
    results = {}
    for community in communities:
        cid = community["id"]
        roster = [Participant.model_validate(p) for p in participants if p["community_id"] == cid]
        incoming = cid in (uid("solar"), uid("flat"))
        result = compare_batteries(request, roster, events[cid], community["timezone"], "shared_meter",
            roster[0].id if cid == uid("sparse") else member.id,
            joining_member=member if incoming else None, joining_events=events[uid("origin")] if incoming else None,
            joining_timezone="Europe/Bucharest", demo_mode=True)
        result["community"] = {"id": cid, "name": community["name"]}
        results[community["slug"]] = result
        best = result.get("best_design_index")
        print(community["name"], result["status"],
              result["designs"][best]["design"]["capacity_kwh"] if best is not None else "no annual ROI", flush=True)
    assert results["hackathon-demo-flat"]["purchase_recommended"] is False
    assert results["hackathon-demo-sparse"]["status"] == "limited_history"
    assert results["hackathon-demo-solar"]["member_count"] == 3
    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "results.json").write_text(json.dumps({"sources": SOURCES, "results": results}, indent=2), encoding="utf-8")
    return results


def charts(data, results):
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".tools/matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False})
    _, participants, events, _, _ = data
    solar = results["hackathon-demo-solar"]
    best = solar["designs"][solar["best_design_index"]]
    days, _ = measured_days(events[uid("solar")], "Europe/Bucharest", demo_mode=True)
    day = days[14]
    # The invitation includes the pitch member in all hourly rows.
    from app.community_battery import include_joining_member
    day = include_joining_member([day], events[uid("origin")], "Europe/Bucharest", Participant.model_validate(participants[0]), demo_mode=True)[0]
    d = best["design"]
    config = BatteryScenario(capacity_kwh=d["capacity_kwh"], charge_kw=d["power_kw"], discharge_kw=d["power_kw"],
        round_trip_efficiency=d["efficiency"], reserve_fraction=.1, initial_soc_fraction=.1, grid_import_kw=20, grid_export_kw=20, wear_ron_per_kwh=.15)
    plan = optimise(day, config)
    baseline = describe_schedule(day, config, np.zeros(24), np.zeros(24), np.full(24, d["capacity_kwh"]*.1), "No battery")
    for row in plan["rows"]:
        assert abs(row["pv_kwh"] + row["grid_import_kwh"] + row["discharge_kwh"] - row["load_kwh"] - row["charge_kwh"] - row["grid_export_kwh"] - row["curtailed_kwh"]) < 1e-5
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    h = np.arange(24)
    axes[0].plot(h, [r["import_price"] for r in day], color="#755d00", label="Dynamic import price")
    axes[0].set_ylabel("RON/kWh"); axes[0].legend(loc="upper left")
    axes[1].plot(h, [r["load_kwh"] for r in day], label="Demand")
    axes[1].plot(h, [r["pv_kwh"] for r in day], label="Modelled PV")
    axes[1].bar(h, [r["charge_kwh"] for r in plan["rows"]], alpha=.6, label="Charge")
    axes[1].bar(h, [-r["discharge_kwh"] for r in plan["rows"]], alpha=.6, label="Discharge (negative)")
    axes[1].set_ylabel("kWh per hour"); axes[1].legend(ncol=2)
    axes[2].plot(h, [r["soc_kwh"] for r in plan["rows"]], label="Stored energy")
    axes[2].plot(h, [r["grid_import_kwh"] for r in baseline["rows"]], '--', label="Import without battery")
    axes[2].plot(h, [r["grid_import_kwh"] for r in plan["rows"]], label="Import with battery")
    axes[2].set_ylabel("kWh"); axes[2].set_xlabel("Bucharest hour, 15 July 2026"); axes[2].legend(ncol=2)
    fig.suptitle("Solar Commons + joining member: historical replay\nMeasured donor demand / modelled PV / known prices / no battery export")
    fig.tight_layout(); fig.savefig(PUBLIC / "dispatch.png"); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    sizes = [r["design"]["capacity_kwh"] for r in solar["designs"]]
    axes[0].plot(sizes, [r["projections"]["base"]["npv_ron"] for r in solar["designs"]], 'o-')
    axes[0].axhline(0, color="black", lw=1); axes[0].set_ylabel("10-year NPV, RON"); axes[0].set_xlabel("Nominal capacity, kWh")
    axes[0].set_title("Bigger is not always better")
    axes[1].plot(sizes, [r["annual_cash_saving_ron"] for r in solar["designs"]], 'o-', color="#755d00")
    axes[1].set_ylabel("Annualised cash savings, RON"); axes[1].set_xlabel("Nominal capacity, kWh"); axes[1].set_title("Savings saturate as size increases")
    fig.suptitle("Conditional annualisation of 30 July replay days; explicit cost assumptions")
    fig.tight_layout(); fig.savefig(PUBLIC / "sizing.png"); plt.close(fig)
    (PUBLIC / "dispatch.json").write_text(json.dumps({"baseline": baseline, "optimised": plan}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    args = parser.parse_args()
    data = build()
    if args.seed:
        seed(data)
    results = analyse(data)
    charts(data, results)
    runpy.run_path(str(OUT / "make_pitch_page.py"))
    print("Offline pitch results and charts: public/demo/", flush=True)
