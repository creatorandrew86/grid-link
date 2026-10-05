"""Test whether the conservative dispatch wear penalty changes the investment conclusion.

Run after backtest_prosumers.py. Zero wear is an optimistic dispatch ceiling, not zero ageing.
"""
import gzip
import csv
import json
from concurrent.futures import ProcessPoolExecutor
from itertools import product

from backtest_prosumers import HERE, REGIONS, finances, inputs, replay, summarise


def replay_wear(task):
    rows = replay(task[:-1], wear=task[-1])
    return [{**row, "wear_rate": task[-1]} for row in rows]


def main():
    profiles, days, weather = inputs()
    settings = [(c, 5, m) for c, m in product(("capped_export",), (1, 2))]
    settings += [("capped_dynamic", 10, 1), ("fixed_quantitative", 5, 1), ("fixed_post2030", 5, 1)]
    tasks = [(region, house, solar, modules, contract, profiles, days, weather, wear)
             for region, house, (contract, solar, modules), wear in
             product(REGIONS, ("2", "3", "4", "5", "6"), settings, (.15, 0))]
    summaries, count = [], 0
    with gzip.open(HERE / "prosumer-wear-days.csv.gz", "wt", newline="", encoding="utf-8") as file, ProcessPoolExecutor(max_workers=4) as pool:
        writer = None
        for i, rows in enumerate(pool.map(replay_wear, tasks), 1):
            if writer is None:
                writer = csv.DictWriter(file, fieldnames=list(rows[0]))
                writer.writeheader()
            writer.writerows(rows)
            summary = summarise(rows)
            summary["wear_rate"] = rows[0]["wear_rate"]
            summaries.append(summary)
            count += len(rows)
            if i % 50 == 0:
                print(f"Wear sensitivity: {i}/{len(tasks)} designs; {count:,} physical checks passed", flush=True)
    lookup = {(d["region"], d["house"], d["solar_kwp"], d["modules"], d["contract"], d["wear_rate"]): d for d in summaries}
    designs = []
    for d in summaries:
        if d["contract"] == "fixed_post2030":
            continue
        future = d["annual_cash_savings_ron"]
        if d["contract"] == "fixed_quantitative":
            future = lookup[(d["region"], d["house"], d["solar_kwp"], d["modules"], "fixed_post2030", d["wear_rate"])]["annual_cash_savings_ron"]
        d["finance"] = finances(d["annual_cash_savings_ron"], future, d["modules"])
        d["finance_savings_minus25pct"] = finances(d["annual_cash_savings_ron"], future, d["modules"], savings_factor=.75)
        designs.append(d)
    (HERE / "prosumer-wear.json").write_text(json.dumps({"daily_replays": count, "technical_checks_passed": count,
        "selection": "Eight regions and five homes; fixed 5kWp/5.12kWh, capped self-use 10kWp/5.12kWh, capped export 5kWp/5.12 or 10.24kWh",
        "designs": designs}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Completed {count:,} sensitivity replays; {len(designs)} investment designs", flush=True)


if __name__ == "__main__":
    main()
