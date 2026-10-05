"""Optimistic seven-day replay: energy carries overnight; future prices/load/PV are known.

Run after backtest_prosumers.py. This is a financial opportunity ceiling, not a live forecast.
The selected cases match the wear sensitivity; resets occur only at week/dataset boundaries.
"""
import csv
import gzip
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
from itertools import product

import numpy as np

from backtest_prosumers import (
    AUXILIARY_KW, BatteryScenario, HERE, REGIONS, describe_schedule, finances,
    inputs, make_intervals, optimise, summarise, validate,
)


def replay_week(task):
    region, house, solar, modules, contract, profiles, price_days, weather = task
    config = BatteryScenario(solar_kwp=solar, capacity_kwh=5.12 * modules,
                             charge_kw=min(2.5 * modules, 5), discharge_kw=min(2.5 * modules, 5),
                             max_soc_fraction=1, wear_ron_per_kwh=0, grid_import_kw=15,
                             grid_export_kw=10, allow_battery_export=contract == "capped_export")
    blocks, previous = [], None
    for day in sorted(day for h, day in profiles if h == house):
        stamp = date.fromisoformat(day)
        if previous is None or stamp - previous != timedelta(days=1) or len(blocks[-1]) == 7:
            blocks.append([])
        blocks[-1].append(day)
        previous = stamp
    results = []
    for block in blocks:
        intervals = [row for day in block for row in
                     make_intervals(region, profiles[(house, day)], solar, contract, price_days[day], weather)]
        zero = np.zeros(len(intervals))
        states = np.full(len(intervals), config.capacity_kwh * .1)
        base = describe_schedule(intervals, config, zero, zero, states, "No battery")
        battery_intervals = [{**r, "load_kwh": r["load_kwh"] + AUXILIARY_KW} for r in intervals]
        plan = optimise(battery_intervals, config)
        validate(plan, config)
        assert plan["energy_cost_ron"] <= describe_schedule(battery_intervals, config, zero, zero, states, "Idle")["energy_cost_ron"] + 1e-5
        for i, day in enumerate(block):
            b, p = base["rows"][24*i:24*(i+1)], plan["rows"][24*i:24*(i+1)]
            cash = sum(r["energy_cost_ron"] for r in b) - sum(r["energy_cost_ron"] for r in p)
            results.append({"region": region, "house": house, "solar_kwp": solar, "modules": modules,
                            "capacity_kwh": config.capacity_kwh, "contract": contract, "target_day": day,
                            "source_day": profiles[(house, day)][0]["source_day"],
                            "load_kwh": sum(r["load_kwh"] for r in b), "pv_kwh": sum(r["pv_kwh"] for r in b),
                            "baseline_bill_ron": sum(r["energy_cost_ron"] for r in b),
                            "baseline_import_spend_ron": sum(r["grid_import_kwh"] * r["import_price"] for r in b),
                            "cash_savings_ron": cash, "savings_after_wear_ron": cash,
                            "discharge_ac_kwh": sum(r["discharge_kwh"] for r in p),
                            "equivalent_cycles": sum(r["discharge_kwh"] for r in p) / np.sqrt(.9) / config.capacity_kwh,
                            "end_soc_kwh": p[-1]["soc_kwh"], "block_start": block[0], "block_end": block[-1],
                            "validated": True})
    return results, len(blocks)


def main():
    profiles, days, weather = inputs()
    settings = [("fixed_quantitative", 5, 1), ("fixed_post2030", 5, 1),
                ("capped_dynamic", 10, 1), ("capped_export", 5, 1), ("capped_export", 5, 2)]
    tasks = [(region, house, solar, modules, contract, profiles, days, weather)
             for region, house, (contract, solar, modules) in product(REGIONS, ("2", "3", "4", "5", "6"), settings)]
    summaries, count, blocks = [], 0, 0
    with gzip.open(HERE / "prosumer-horizon-days.csv.gz", "wt", newline="", encoding="utf-8") as file, ProcessPoolExecutor(max_workers=4) as pool:
        writer = None
        for i, (rows, checked_blocks) in enumerate(pool.map(replay_week, tasks), 1):
            if writer is None:
                writer = csv.DictWriter(file, fieldnames=list(rows[0]))
                writer.writeheader()
            writer.writerows(rows)
            summaries.append(summarise(rows))
            count += len(rows)
            blocks += checked_blocks
            if i % 25 == 0:
                print(f"Seven-day ceiling: {i}/{len(tasks)} designs; {blocks:,} blocks / {count:,} meter-days checked", flush=True)
    lookup = {(d["region"], d["house"], d["solar_kwp"], d["modules"], d["contract"]): d for d in summaries}
    designs = []
    for d in summaries:
        if d["contract"] == "fixed_post2030":
            continue
        future = d["annual_cash_savings_ron"]
        if d["contract"] == "fixed_quantitative":
            future = lookup[(d["region"], d["house"], d["solar_kwp"], d["modules"], "fixed_post2030")]["annual_cash_savings_ron"]
        d["finance"] = finances(d["annual_cash_savings_ron"], future, d["modules"])
        d["finance_savings_minus25pct"] = finances(d["annual_cash_savings_ron"], future, d["modules"], savings_factor=.75)
        designs.append(d)
    (HERE / "prosumer-horizon.json").write_text(json.dumps({"daily_meter_replays": count, "technical_blocks_passed": blocks,
        "selection": settings, "assumptions": "Perfect seven-day future information, zero dispatch wear; 20W auxiliary, 90% efficiency, equal starting/ending SOC per block",
        "designs": designs}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Completed {blocks:,} blocks / {count:,} meter-day replays; {len(designs)} investment designs", flush=True)


if __name__ == "__main__":
    main()
