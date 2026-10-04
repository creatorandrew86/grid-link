"""Measured-demand transfer test against Romanian prices, with explicit ROI assumptions.

Run: python research/romania/backtest_consumers.py
Public raw downloads are cached in ignored raw/. No app settings or meter data are changed.
"""
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.battery import BatteryScenario, describe_schedule, history, optimise
from app.weather import historical_estimates

HERE = Path(__file__).resolve().parent
SOURCE = "https://data.open-power-system-data.org/household_data/2020-04-15"
HOUSE_FEEDS = {2: ("grid_import",), 3: ("grid_import", "pv", "grid_export"),
               4: ("grid_import", "pv", "grid_export"), 5: ("grid_import",),
               6: ("grid_import", "pv", "grid_export")}
UNIT_COST_RON = 4750.21  # PowerSense published SE-G5.1 Pro-B module, VAT included, no installation.
INSTALL_RON = 1500.     # Assumption for an existing compatible inverter, not an installer quote.
OPEX_RON_YEAR = 100.    # Assumption, per system.


def download():
    raw = HERE / "raw"
    raw.mkdir(exist_ok=True)
    paths = {}
    for name, filename in (("data", "household_data_60min_singleindex.csv"), ("metadata", "datapackage.json")):
        path = raw / ("opsd-household-60min.csv" if name == "data" else "opsd-household-metadata.json")
        if not path.exists():
            response = httpx.get(f"{SOURCE}/{filename}", follow_redirects=True, timeout=120)
            response.raise_for_status()
            path.write_bytes(response.content)
        paths[name] = path
    return paths


def measured_days(path):
    """CSV values are cumulative, last reading in each hour; differences belong to the current hour."""
    groups, rejected = defaultdict(list), Counter()
    with path.open(encoding="utf-8") as file:
        rows = csv.DictReader(file)
        previous = next(rows)
        for row in rows:
            stamp = datetime.fromisoformat(row["utc_timestamp"])
            if stamp - datetime.fromisoformat(previous["utc_timestamp"]) != timedelta(hours=1):
                rejected["nonconsecutive_rows"] += 1
                previous = row
                continue
            local = datetime.fromisoformat(row["cet_cest_timestamp"])
            for house, feeds in HOUSE_FEEDS.items():
                columns = [f"DE_KN_residential{house}_{feed}" for feed in feeds]
                if not all(row[c] and previous[c] for c in columns):
                    rejected["missing_reading_hours"] += 1
                    continue
                if any(c in row["interpolated"] or c in previous["interpolated"] for c in columns):
                    rejected["flagged_interpolation_hours"] += 1
                    continue
                deltas = {feed: float(row[c]) - float(previous[c]) for feed, c in zip(feeds, columns)}
                load = deltas["grid_import"] + deltas.get("pv", 0.) - deltas.get("grid_export", 0.)
                if not all(math.isfinite(v) and v >= -1e-6 for v in deltas.values()) or load < -.003:
                    rejected["negative_meter_or_reconstructed_load_hours"] += 1
                    continue
                if load < 0:
                    rejected["rounding_clipped_hours"] += 1
                groups[(house, local.date())].append({"hour": local.hour, "load_kwh": max(0., load), "source_utc": row["utc_timestamp"]})
            previous = row
    complete = {key: sorted(values, key=lambda r: r["hour"]) for key, values in groups.items()
                if len(values) == 24 and {r["hour"] for r in values} == set(range(24))}
    rejected["incomplete_or_dst_days"] = len(groups) - len(complete)
    return complete, dict(rejected)


def transfer_profiles(complete):
    """Use unique measured days; preserve month and prefer the same weekday, without scaling energy."""
    targets = sorted({date.fromisoformat(r["bucharest_time"][:10]) for r in history()})
    selected, used = [], set()
    for house in HOUSE_FEEDS:
        for target in targets:
            candidates = [source_day for h, source_day in complete
                          if h == house and source_day.month == target.month and (h, source_day) not in used]
            if not candidates:
                continue
            donor = min(candidates, key=lambda d: (d.weekday() != target.weekday(), abs(d.day - target.day), abs(d.year - 2016), d))
            used.add((house, donor))
            selected.append({"house": str(house), "target_day": target.isoformat(), "source_day": donor.isoformat(),
                             "weekday_matched": donor.weekday() == target.weekday(), "profile": complete[(house, donor)]})
    return selected


def intervals_for(profile, solar_kwp):
    weather = [r for r in history() if r["bucharest_time"][:10] == profile["target_day"]]
    loads = {r["hour"]: r["load_kwh"] for r in profile["profile"]}
    return [{**r, "hours": 1., "load_kwh": loads[datetime.fromisoformat(r["bucharest_time"]).hour],
             "pv_kwh": min(solar_kwp, max(0., solar_kwp * r["bucharest_ghi_w_m2"] / 1000 * .8))} for r in weather]


def validate(schedule, config):
    eta = math.sqrt(config.round_trip_efficiency)
    previous = config.capacity_kwh * config.initial_soc_fraction
    for r in schedule["rows"]:
        assert abs(r["pv_kwh"] + r["grid_import_kwh"] + r["discharge_kwh"] - r["load_kwh"] - r["charge_kwh"] - r["grid_export_kwh"] - r["curtailed_kwh"]) < 1e-5
        assert abs(r["soc_kwh"] - previous - r["charge_kwh"] * eta + r["discharge_kwh"] / eta) < 1e-5
        assert config.capacity_kwh * config.reserve_fraction - 1e-5 <= r["soc_kwh"] <= config.capacity_kwh * config.max_soc_fraction + 1e-5
        assert r["charge_kwh"] <= config.charge_kw * r["hours"] + 1e-5
        assert r["discharge_kwh"] <= config.discharge_kw * r["hours"] + 1e-5
        assert r["grid_import_kwh"] <= config.grid_import_kw * r["hours"] + 1e-5
        assert r["grid_export_kwh"] <= config.grid_export_kw * r["hours"] + 1e-5
        assert r["curtailed_kwh"] <= r["pv_kwh"] + 1e-5
        assert r["charge_kwh"] * r["discharge_kwh"] < 1e-5
        assert r["grid_import_kwh"] * r["grid_export_kwh"] < 1e-5
        previous = r["soc_kwh"]
    assert abs(previous - config.capacity_kwh * config.initial_soc_fraction) < 1e-5


def case_result(profile, modules, solar_kwp, forecast=None, wear=.15):
    config = BatteryScenario(day=profile["target_day"], solar_kwp=solar_kwp, capacity_kwh=5.12 * modules,
                             charge_kw=min(2.5 * modules, 5.), discharge_kw=min(2.5 * modules, 5.),
                             max_soc_fraction=1., wear_ron_per_kwh=wear)
    intervals = intervals_for(profile, solar_kwp)
    zero = np.zeros(len(intervals))
    base = describe_schedule(intervals, config, zero, zero, np.full(len(intervals), config.capacity_kwh * .1), "No battery")
    plan = optimise(intervals, config, planning_prices=forecast)
    validate(plan, config)
    saving = base["total_cost_ron"] - plan["total_cost_ron"]
    if forecast is None:
        assert saving >= -1e-5  # Idle is feasible; exact-price optimisation must not cost more.
    import_cost = sum(r["grid_import_kwh"] * r["import_price"] for r in base["rows"])
    result = {"house": profile["house"], "target_day": profile["target_day"], "source_day": profile["source_day"],
            "modules": modules, "capacity_kwh": config.capacity_kwh, "solar_kwp": solar_kwp,
            "wear_rate": wear, "load_kwh": sum(r["load_kwh"] for r in intervals),
            "baseline_bill_ron": base["total_cost_ron"], "baseline_import_spend_ron": import_cost,
            "optimised_bill_after_wear_ron": plan["total_cost_ron"], "savings_after_wear_ron": saving,
            "cash_savings_ron": base["energy_cost_ron"] - plan["energy_cost_ron"], "wear_ron": plan["wear_cost_ron"],
            "discharge_ac_kwh": plan["discharge_kwh"], "equivalent_cycles": plan["equivalent_cycles"],
            "day_bill_reduction_pct": 100 * saving / base["total_cost_ron"] if base["total_cost_ron"] > .01 else None,
            "validated": True}
    return {key: value.item() if isinstance(value, np.generic) else value for key, value in result.items()}


def summarise(rows):
    savings = sum(r["savings_after_wear_ron"] for r in rows)
    spend = sum(r["baseline_import_spend_ron"] for r in rows)
    positive_baseline = [r for r in rows if r["baseline_bill_ron"] > .01]
    baseline_bill = sum(r["baseline_bill_ron"] for r in rows)
    by_house_month = defaultdict(list)
    for row in rows:
        by_house_month[(row["house"], row["target_day"][:7])].append(row)
    # Equal weight for homes and sampled seasons, despite differing numbers of clean meter days.
    # This remains an extrapolation, not a full-year price backtest.
    def annualised(field):
        by_house = defaultdict(list)
        for (house, month), group in by_house_month.items():
            by_house[house].append(statistics.mean(r[field] for r in group))
        return 365 * statistics.mean(statistics.mean(values) for values in by_house.values())
    annual_cash = annualised("cash_savings_ron")
    annual_delivered = annualised("discharge_ac_kwh")
    modules = rows[0]["modules"]
    capex = modules * UNIT_COST_RON + INSTALL_RON
    first_net = annual_cash - OPEX_RON_YEAR
    yearly = [annual_cash * .98 ** year - OPEX_RON_YEAR for year in range(10)]
    cumulative, degraded_payback = 0., None
    for year, cash in enumerate(yearly, 1):
        if cumulative + cash >= capex and cash > 0 and degraded_payback is None:
            degraded_payback = year - 1 + (capex - cumulative) / cash
        cumulative += cash
    return {"cases": len(rows), "households": len({r["house"] for r in rows}),
            "mean_load_kwh_day": statistics.mean(r["load_kwh"] for r in rows),
            "baseline_bill_ron": baseline_bill, "savings_after_wear_ron": savings,
            "pooled_net_bill_reduction_pct": 100 * savings / baseline_bill if len(positive_baseline) == len(rows) else None,
            "mean_day_bill_reduction_pct_positive_bills": statistics.mean(r["day_bill_reduction_pct"] for r in positive_baseline) if positive_baseline else None,
            "savings_as_pct_of_baseline_import_spend": 100 * savings / spend if spend > 0 else None,
            "days_better": sum(r["savings_after_wear_ron"] > .01 for r in rows),
            "days_equal": sum(abs(r["savings_after_wear_ron"]) <= .01 for r in rows),
            "days_worse": sum(r["savings_after_wear_ron"] < -.01 for r in rows),
            "profitable_days_pct": 100 * sum(r["savings_after_wear_ron"] > .01 for r in rows) / len(rows),
            "physical_checks_passed_pct": 100 * sum(r["validated"] for r in rows) / len(rows),
            "positive_baseline_cases": len(positive_baseline), "mean_cash_savings_ron_day": statistics.mean(r["cash_savings_ron"] for r in rows),
            "mean_cycles_day": statistics.mean(r["equivalent_cycles"] for r in rows),
            "roi_projection": {"sample_season_extrapolated_annual_cash_savings_ron": annual_cash,
                "annual_discharge_ac_kwh": annual_delivered, "capex_ron_existing_inverter": capex,
                "first_year_cash_return_pct": 100 * first_net / capex,
                "simple_payback_years": capex / first_net if first_net > 0 else None,
                "degraded_payback_within_10_years": degraded_payback,
                "ten_year_cash_roi_pct": 100 * (sum(yearly) - capex) / capex,
                "ten_year_npv_ron_discount_6pct": sum(cash / 1.06 ** year for year, cash in enumerate(yearly, 1)) - capex,
                "throughput_warranty_reference_years": 16000 * modules * math.sqrt(.9) / annual_delivered if annual_delivered > 0 else None,
                "simple_payback_with_6000_ron_inverter_retrofit": (capex + 6000) / first_net if first_net > 0 else None}}


def main():
    paths = download()
    complete, rejected = measured_days(paths["data"])
    profiles = transfer_profiles(complete)
    derived = [{"house": p["house"], "target_day": p["target_day"], "source_day": p["source_day"],
                "weekday_matched": p["weekday_matched"], **hour} for p in profiles for hour in p["profile"]]
    with (HERE / "measured-demand-profiles.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(derived[0]))
        writer.writeheader(); writer.writerows(derived)
    cases, estimates = [], []
    grouped = defaultdict(list)
    for i, profile in enumerate(profiles):
        for solar in (0, 5):
            for modules in (1, 2, 4):
                row = case_result(profile, modules, solar)
                cases.append(row); grouped[("household", solar, modules)].append(row)
        # Price-estimate variants are evaluated at the smallest battery, against real target consumption.
        intervals = intervals_for(profile, 0)
        experiment = historical_estimates(profile["target_day"], intervals)
        if experiment["available"]:
            for name in ("calendar", "local", "weather"):
                row = case_result(profile, 1, 0, forecast=experiment[f"{name}_prices"])
                row["strategy"] = name
                estimates.append(row)
        # A more conservative wear sensitivity for the existing 5.12-kWh algorithm.
        row = case_result(profile, 1, 0, wear=.30)
        cases.append(row)
        grouped[("wear_sensitivity", 0, 1)].append(row)
        if (i + 1) % 100 == 0:
            print(f"Validated {i + 1}/{len(profiles)} measured household-days", flush=True)
    # A synthetic five-home community: only dates with all five matched measured profiles.
    by_target = defaultdict(list)
    for profile in profiles:
        by_target[profile["target_day"]].append(profile)
    for target, members in sorted(by_target.items()):
        if len(members) != 5:
            continue
        community = {"house": "community", "target_day": target, "source_day": "multiple",
                     "profile": [{"hour": h, "load_kwh": sum(p["profile"][h]["load_kwh"] for p in members)} for h in range(24)]}
        for solar in (0, 20):
            for modules in (1, 2, 4):
                row = case_result(community, modules, solar)
                cases.append(row); grouped[("community", solar, modules)].append(row)
    # Four homes have complete coverage of all 120 Romanian price days, avoiding the fifth home's sparse seasons.
    for target, members in sorted(by_target.items()):
        members = [p for p in members if p["house"] in {"2", "3", "4", "5"}]
        if len(members) != 4:
            continue
        community = {"house": "community4", "target_day": target, "source_day": "multiple",
                     "profile": [{"hour": h, "load_kwh": sum(p["profile"][h]["load_kwh"] for p in members)} for h in range(24)]}
        for solar in (0, 20):
            for modules in (1, 2, 4):
                row = case_result(community, modules, solar)
                cases.append(row); grouped[("community4", solar, modules)].append(row)
    summaries = [{"scope": scope, "solar_kwp": solar, "capacity_kwh": 5.12 * modules, **summarise(rows)}
                 for (scope, solar, modules), rows in sorted(grouped.items())]
    estimate_summary = {name: summarise([r for r in estimates if r["strategy"] == name]) for name in ("calendar", "local", "weather")}
    metadata = {"source": SOURCE, "source_sha256": hashlib.sha256(paths["data"].read_bytes()).hexdigest(),
                "license": "CC-BY-4.0", "attribution": "Open Power System Data. 2020. Data Package Household Data. Version 2020-04-15. Primary data: CoSSMic / ISC Konstanz.",
                "measured_households": list(HOUSE_FEEDS), "derived_household_days": len(profiles),
                "community_cohorts": {"community": {"houses": [2, 3, 4, 5, 6], "days": 68},
                                      "community4": {"houses": [2, 3, 4, 5], "days": 120}},
                "source_day_reuse": False, "weekday_matched_pct": 100 * sum(p["weekday_matched"] for p in profiles) / len(profiles),
                "quality_rejections": rejected, "complete_available_days_by_house": dict(Counter(h for h, day in complete)),
                "notes": ["German measured profiles relocated by local clock, month and preferred weekday to 2026 Romanian prices; energy is not scaled.",
                          "Five selected households are not a representative Romanian population sample. Community profiles sum matched, non-contemporaneous source days under a hypothetical shared meter.",
                          "Hourly cumulative last readings are differenced against the previous row and assigned to the current labelled hour; readings approximate hour-end by the final minute.",
                          "Exclude missing, flagged-interpolated, nonconsecutive, incomplete/DST and invalid-negative readings. Reconstruct gross demand as import + PV - export where all feeds exist.",
                          "Actual target demand is known to the optimiser: perfect-demand reference, not a live demand-forecast backtest. PV is modelled from Bucharest ERA5, not measured Romanian PV.",
                          "Price-estimate comparisons use historical actual target weather; they do not validate issued forecasts.",
                          "Profitable means more than 0.01 RON/day saved after dispatch wear. Pooled percentage uses summed costs, not average percentages.",
                          "ROI extrapolates seasonal mean savings to 365 days, weighting each home and each of its four sampled seasons equally. This is not a measured annual return.",
                          "Financial cash flows omit noncash wear to avoid counting battery cost twice; dispatch still uses its wear penalty. Cash projection: 100 RON/year operating cost, 2% annual savings fade, 10 years, 6% discount, no replacement, subsidy, finance, residual value or price escalation.",
                          "Module price 4750.21 RON incl. VAT plus assumed 1500 RON installation; existing compatible inverter. A separate 6000 RON inverter retrofit sensitivity is an assumption.",
                          "16 MWh/module manufacturer throughput is a warranty reference, not a claim that failure or replacement occurs at that point."]}
    output = {"metadata": metadata, "summaries": summaries, "price_estimate_summaries": estimate_summary,
              "cases": cases, "price_estimate_cases": estimates}
    (HERE / "consumer-backtest.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    with (HERE / "consumer-backtest.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(cases[0]))
        writer.writeheader(); writer.writerows(cases)
    print(json.dumps({"metadata": metadata, "summaries": summaries, "price_estimate_summaries": estimate_summary}, indent=2), flush=True)


if __name__ == "__main__":
    main()
