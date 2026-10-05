"""Individual-prosumer battery economics. Reuses the production solver and measured loads.

Run: python research/romania/backtest_prosumers.py
Public weather downloads use the existing collector/cache. Financial results are conditional
extrapolations of four sampled seasons, not a Romanian population estimate or a live trial.
"""
import csv
import gzip
import hashlib
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.romania.backtest_consumers import (
    BatteryScenario, HERE, INSTALL_RON, OPEX_RON_YEAR, UNIT_COST_RON,
    describe_schedule, history, optimise, validate,
)
from research.romania.collect_data import weather_place, write_csv

REGIONS = {
    "bucharest": (44.4268, 26.1025, .31739, "Rețele Electrice / Muntenia"),
    "timisoara": (45.7489, 21.2087, .31739, "Rețele Electrice / Banat"),
    "constanta": (44.1598, 28.6348, .31739, "Rețele Electrice / Dobrogea"),
    "ploiesti": (44.9367, 26.0129, .35534, "DEER / Muntenia Nord"),
    "brasov": (45.6579, 25.6012, .35534, "DEER / Transilvania Sud"),
    "cluj": (46.7712, 23.6236, .35534, "DEER / Transilvania Nord"),
    "iasi": (47.1585, 27.6014, .38791, "Delgaz Grid"),
    "craiova": (44.3302, 23.7949, .33325, "Distribuție Oltenia"),
}
# Published OPCOM PZU volume-weighted monthly means, not hourly arithmetic means.
MONTHLY_PZU = {"2026-01": .79041, "2026-04": .51465, "2026-07": .63646, "2026-09": .91736}
FIXED_ACTIVE = .515     # VIITOR HIDRO October 2026, explicit prosumer clause, excludes TG.
AUXILIARY_KW = .020     # Assumed incremental battery-system consumption, not a measured spec.
WEAR_RON_KWH = .30      # Conservative dispatch penalty; never also deducted from investment cash flows.
CONTRACTS = ("fixed_quantitative", "fixed_post2030", "capped_dynamic")
WEATHER_PATH = HERE / "prosumer-weather.csv"


def contract_prices(price, region, contract, month):
    distribution = REGIONS[region][2]
    # Charges transcribed from the current supplier annexes; prices include VAT on imports.
    common = .03645 + .0740192 + .000144 + .01450 + .00768 + distribution
    if contract.startswith("fixed"):
        buy = (FIXED_ACTIVE + .00363 + .01272 + common) * 1.21
        sell = FIXED_ACTIVE if contract == "fixed_quantitative" else MONTHLY_PZU[month]
    else:
        # YellowGrid/GAN offer: supply commission is already part of Pe, not an extra 0.05.
        # Its published annex uses TSS 0.01470, versus Hidroelectrica's 0.01272.
        buy = (min(.55, .1375 + .75 * price) + .01470 + common) * 1.21
        sell = max(.50, .125 + .75 * price)
    return buy, sell


def inputs():
    profiles = defaultdict(list)
    with (HERE / "measured-demand-profiles.csv").open(encoding="utf-8") as file:
        for row in csv.DictReader(file):
            profiles[(row["house"], row["target_day"])].append(
                {**row, "hour": int(row["hour"]), "load_kwh": float(row["load_kwh"])})
    price_days = defaultdict(list)
    for row in history():
        price_days[row["bucharest_time"][:10]].append(row)
    if not WEATHER_PATH.exists():
        rows = []
        for region, (lat, lon, _, _) in REGIONS.items():
            _, weather = weather_place(region, lat, lon)
            for price in history():
                epoch = int(datetime.fromisoformat(price["utc"]).timestamp())
                rows.append({"region": region, "utc": price["utc"], **weather[epoch]})
        write_csv(WEATHER_PATH, rows)
    weather = {}
    with WEATHER_PATH.open(encoding="utf-8") as file:
        for row in csv.DictReader(file):
            weather[(row["region"], row["utc"])] = float(row["ghi_w_m2"])
    assert len(weather) == len(REGIONS) * len(history())
    for values in profiles.values():
        assert len(values) == 24 and {r["hour"] for r in values} == set(range(24))
    return profiles, price_days, weather


def make_intervals(region, profile, solar, contract, price_rows, weather):
    loads = {r["hour"]: r["load_kwh"] for r in profile}
    intervals = []
    for price in price_rows:
        hour = datetime.fromisoformat(price["bucharest_time"]).hour
        buy, sell = contract_prices(price["price_lei_kwh"], region, contract, price["bucharest_time"][:7])
        intervals.append({**price, "hours": 1, "load_kwh": loads[hour],
                          "pv_kwh": min(solar, max(0, solar * weather[(region, price["utc"])] / 1000 * .8)),
                          "import_price": buy, "export_price": sell})
    return intervals


def replay(task, *, wear=WEAR_RON_KWH):
    region, house, solar, modules, contract, profiles, price_days, weather = task
    config = BatteryScenario(solar_kwp=solar, capacity_kwh=5.12 * modules,
                             charge_kw=min(2.5 * modules, 5), discharge_kw=min(2.5 * modules, 5),
                             max_soc_fraction=1, wear_ron_per_kwh=wear,
                             grid_import_kw=15, grid_export_kw=10,
                             allow_battery_export=contract == "capped_export")
    result = []
    for (h, day), profile in sorted(profiles.items()):
        if h != house:
            continue
        intervals = make_intervals(region, profile, solar, contract, price_days[day], weather)
        zeros = np.zeros(24)
        states = np.full(24, config.capacity_kwh * .1)
        baseline = describe_schedule(intervals, config, zeros, zeros, states, "No battery")
        # Extra standby/auxiliary consumption is part of the physical energy balance.
        battery_intervals = [{**r, "load_kwh": r["load_kwh"] + AUXILIARY_KW} for r in intervals]
        idle = describe_schedule(battery_intervals, config, zeros, zeros, states, "Battery idle")
        plan = optimise(battery_intervals, config)
        validate(plan, config)
        assert plan["total_cost_ron"] <= idle["total_cost_ron"] + 1e-5
        result.append({"region": region, "house": house, "target_day": day,
                       "source_day": profile[0]["source_day"], "solar_kwp": solar,
                       "modules": modules, "capacity_kwh": config.capacity_kwh, "contract": contract,
                       "load_kwh": sum(r["load_kwh"] for r in intervals),
                       "pv_kwh": sum(r["pv_kwh"] for r in intervals),
                       "baseline_bill_ron": baseline["energy_cost_ron"],
                       "baseline_import_spend_ron": sum(r["grid_import_kwh"] * r["import_price"] for r in baseline["rows"]),
                       "baseline_import_kwh": baseline["grid_import_kwh"],
                       "baseline_export_kwh": baseline["grid_export_kwh"],
                       "battery_import_kwh": plan["grid_import_kwh"],
                       "battery_export_kwh": plan["grid_export_kwh"],
                       "battery_bill_after_wear_ron": plan["total_cost_ron"],
                       "cash_savings_ron": baseline["energy_cost_ron"] - plan["energy_cost_ron"],
                       "savings_after_wear_ron": baseline["energy_cost_ron"] - plan["total_cost_ron"],
                       "discharge_ac_kwh": plan["discharge_kwh"],
                       "equivalent_cycles": plan["equivalent_cycles"], "validated": True})
    return result


def annualise(rows, field):
    months = defaultdict(list)
    for row in rows:
        months[row["target_day"][:7]].append(row[field])
    assert len(months) == 4, "Every design must cover all four sampled seasons."
    return 365 * statistics.mean(statistics.mean(values) for values in months.values())


def finances(current, future, modules, *, savings_factor=1, extra_capex=0, replacement_year=None):
    capex = UNIT_COST_RON * modules + INSTALL_RON + extra_capex
    # Start 1 October 2026: 4.25 years to the statutory end of quantitative compensation.
    weights = [1, 1, 1, 1, .25, 0, 0, 0, 0, 0]
    cashflows = [(current * w + future * (1 - w)) * savings_factor * .98 ** i - OPEX_RON_YEAR
                 for i, w in enumerate(weights)]
    if replacement_year:
        cashflows[replacement_year - 1] -= UNIT_COST_RON * modules
    pv_cash = sum(cash / 1.06 ** year for year, cash in enumerate(cashflows, 1))
    cumulative, discounted, payback, discounted_payback = 0., 0., None, None
    for year, cash in enumerate(cashflows, 1):
        present = cash / 1.06 ** year
        if payback is None and cash > 0 and cumulative + cash >= capex:
            payback = year - 1 + (capex - cumulative) / cash
        if discounted_payback is None and present > 0 and discounted + present >= capex:
            discounted_payback = year - 1 + (capex - discounted) / present
        cumulative += cash
        discounted += present
    first_net = cashflows[0]
    return {"capex_ron": capex, "first_year_net_saving_ron": first_net,
            "first_year_cash_return_pct": 100 * first_net / capex,
            "constant_first_year_simple_payback_years": capex / first_net if first_net > 0 else None,
            "projected_payback_within_10_years": payback,
            "discounted_payback_within_10_years": discounted_payback,
            "ten_year_cash_roi_pct": 100 * (sum(cashflows) - capex) / capex,
            "ten_year_npv_ron_at_6pct": pv_cash - capex,
            "maximum_total_capex_for_npv_zero_ron": pv_cash,
            "yearly_net_cashflows_ron": cashflows}


def summarise(rows):
    reference = rows[0]
    annual = annualise(rows, "cash_savings_ron")
    import_spend = sum(r["baseline_import_spend_ron"] for r in rows)
    baseline = sum(r["baseline_bill_ron"] for r in rows)
    saving = sum(r["cash_savings_ron"] for r in rows)
    discharge = annualise(rows, "discharge_ac_kwh")
    return {**{key: reference[key] for key in ("region", "house", "solar_kwp", "modules", "capacity_kwh", "contract")},
            "cases": len(rows), "mean_load_kwh_day": statistics.mean(r["load_kwh"] for r in rows),
            "annual_load_kwh": annualise(rows, "load_kwh"),
            "annual_pv_proxy_kwh": annualise(rows, "pv_kwh"),
            "annual_cash_savings_ron": annual,
            "annual_baseline_net_bill_ron": annualise(rows, "baseline_bill_ron"),
            "annual_baseline_import_spend_ron": annualise(rows, "baseline_import_spend_ron"),
            "cash_saving_pct_of_import_spend": 100 * saving / import_spend if import_spend > 0 else None,
            "net_bill_reduction_pct": 100 * saving / baseline if all(r["baseline_bill_ron"] > .01 for r in rows) else None,
            "days_better_cash_pct": 100 * sum(r["cash_savings_ron"] > .01 for r in rows) / len(rows),
            "days_worse_cash_pct": 100 * sum(r["cash_savings_ron"] < -.01 for r in rows) / len(rows),
            "days_better_after_wear_pct": 100 * sum(r["savings_after_wear_ron"] > .01 for r in rows) / len(rows),
            "annual_discharge_ac_kwh": discharge,
            "throughput_reference_years": 16000 * reference["modules"] * math.sqrt(.9) / discharge if discharge > 0 else None,
            "physical_checks_passed_pct": 100 * sum(r["validated"] for r in rows) / len(rows)}


def plot(designs):
    os.environ.setdefault("MPLCONFIGDIR", str(HERE.parents[1] / ".tools" / "matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = {"fixed_quantitative": "Fixed price + credit\n2031 settlement transition",
              "capped_dynamic": "Capped dynamic\nself-consumption",
              "capped_export": "Capped dynamic\nexport enabled (conditional)"}
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    for modules, colour in ((1, "#087f8c"), (2, "#cb7b2e"), (4, "#824a9e")):
        values = [[d["finance"]["ten_year_cash_roi_pct"] for d in designs
                   if d["modules"] == modules and d["contract"] == contract] for contract in labels]
        positions = np.arange(3) + (math.log2(modules) - 1) * .23
        boxes = axes[0].boxplot(values, positions=positions, widths=.20, patch_artist=True,
                              showfliers=False, manage_ticks=False)
        for box in boxes["boxes"]:
            box.set_facecolor(colour)
            box.set_alpha(.65)
        axes[0].plot([], [], color=colour, linewidth=8, label=f"{5.12 * modules:g} kWh")
    axes[0].axhline(0, color="#555555", linewidth=1)
    axes[0].set_xticks(range(3), labels.values(), fontsize=9)
    axes[0].set_ylabel("Conditional 10-year cash ROI (%)")
    axes[0].legend(frameon=False)
    axes[0].set_title("Many designs do not recover their cost")
    for contract, colour in zip(labels, ("#087f8c", "#cb7b2e", "#824a9e")):
        values = sorted(d["finance"]["maximum_total_capex_for_npv_zero_ron"] for d in designs
                        if d["contract"] == contract and d["modules"] == 1)
        axes[1].plot(values, np.linspace(0, 100, len(values)), label=labels[contract].replace("\n", " "), color=colour)
    axes[1].axvline(6250.21, color="#555555", linestyle="--", label="Base installed 5.12 kWh cost")
    axes[1].set_xlabel("Maximum total installed cost for 6% return (RON)")
    axes[1].set_ylabel("Cumulative share of tested designs (%)")
    axes[1].set_title("Use the customer's break-even cost")
    axes[1].legend(fontsize=8, frameon=False)
    fig.suptitle("Individual prosumers: conservative daily policy, existing PV/inverter\n0.30 RON/kWh dispatch wear; 20 W auxiliary load; 2026 seasonal replay; assumptions in PROSUMER_BATTERY_ROI.md", fontsize=11)
    fig.savefig(HERE / "prosumer-battery-roi.png", dpi=160)
    plt.close(fig)


def main():
    profiles, price_days, weather = inputs()
    tasks = [(region, house, solar, modules, contract, profiles, price_days, weather)
             for region, house, solar, modules, contract in
             product(REGIONS, ("2", "3", "4", "5", "6"), (3, 5, 10), (1, 2, 4), CONTRACTS)]
    # Conditional export-enabled experiment at 5 kWp; not assumed permitted for every contract.
    tasks += [(region, house, 5, modules, "capped_export", profiles, price_days, weather)
              for region, house, modules in product(REGIONS, ("2", "3", "4", "5", "6"), (1, 2, 4))]
    summary, checks, count = [], 0, 0
    path = HERE / "prosumer-backtest-days.csv.gz"
    with gzip.open(path, "wt", newline="", encoding="utf-8") as file, ProcessPoolExecutor(max_workers=4) as pool:
        writer = None
        for i, rows in enumerate(pool.map(replay, tasks), 1):
            if writer is None:
                writer = csv.DictWriter(file, fieldnames=list(rows[0]))
                writer.writeheader()
            writer.writerows(rows)
            count += len(rows)
            checks += sum(r["validated"] for r in rows)
            summary.append(summarise(rows))
            if i % 30 == 0:
                print(f"{i}/{len(tasks)} designs; {count:,} validated daily replays", flush=True)
    lookup = {(d["region"], d["house"], d["solar_kwp"], d["modules"], d["contract"]): d for d in summary}
    designs = []
    for item in summary:
        if item["contract"] == "fixed_post2030":
            continue
        future = item["annual_cash_savings_ron"]
        if item["contract"] == "fixed_quantitative":
            future = lookup[(item["region"], item["house"], item["solar_kwp"], item["modules"], "fixed_post2030")]["annual_cash_savings_ron"]
        arguments = item["annual_cash_savings_ron"], future, item["modules"]
        item["annual_cash_savings_post2030_proxy_ron"] = future
        item["finance"] = finances(*arguments)
        item["finance_savings_minus25pct"] = finances(*arguments, savings_factor=.75)
        item["finance_inverter_retrofit"] = finances(*arguments, extra_capex=6000)
        item["finance_replacement_year8"] = finances(*arguments, replacement_year=8)
        designs.append(item)
    sources = {"price_csv": HERE / "hourly-prices-weather.csv", "demand_csv": HERE / "measured-demand-profiles.csv",
               "weather_csv": WEATHER_PATH}
    sources.update({path.name: path for path in (HERE / "raw").glob("*.pdf") if path.name in
                    {"hidrofix-october-2026.pdf", "viitor-hidro-october-2026.pdf",
                     "yellowgrid-september-2026.pdf", "deye-se-g5.1-pro-b.pdf"}})
    output = {"computed_on": "2026-10-05", "daily_replays": count, "technical_checks_passed": checks,
              "dispatch_designs": len(summary), "investment_designs": len(designs),
              "regions": REGIONS, "monthly_pzu_ron_per_kwh": MONTHLY_PZU,
              "assumptions": {"fixed_active": FIXED_ACTIVE, "auxiliary_kw": AUXILIARY_KW,
                  "wear_ron_ac_kwh": WEAR_RON_KWH, "round_trip_efficiency": .9,
                  "unit_cost_ron": UNIT_COST_RON, "installation_ron": INSTALL_RON,
                  "annual_operating_cost_ron": OPEX_RON_YEAR, "discount_rate": .06,
                  "annual_savings_fade": .02, "pv_performance_ratio": .8,
                  "fixed_quantitative_year_weights": [1, 1, 1, 1, .25, 0, 0, 0, 0, 0],
                  "boundary": "One prosumer and one meter. Perfect hourly prices, load and PV; seasonal extrapolation."},
              "input_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sources.items()},
              "designs": designs, "post2030_dispatch_designs": [d for d in summary if d["contract"] == "fixed_post2030"]}
    (HERE / "prosumer-backtest.json").write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    flat = [{**{key: value for key, value in d.items() if not key.startswith("finance")},
             **{key: value for key, value in d["finance"].items() if key != "yearly_net_cashflows_ron"}}
            for d in designs]
    write_csv(HERE / "prosumer-designs.csv", flat)
    plot(designs)
    print(f"Completed {count:,} daily replays, {checks:,} physical checks passed; {len(designs)} investment designs.", flush=True)


if __name__ == "__main__":
    main()
