"""Reproduce the exploratory price/schedule comparison; target weather is reanalysis.

Run from the repository root: python research/romania/check_weather_strategy.py
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.battery import BatteryScenario, dataset_info, simulate


def main():
    records = []
    for day in dataset_info()["days"]:
        for exports in (False, True):
            result = simulate(BatteryScenario(day=day, allow_battery_export=exports))
            experiment = result["weather_experiment"]
            if not experiment["available"]:
                continue
            records.append({"day": day, "battery_exports": exports,
                            **{k: experiment[k] for k in ("calendar_mae_ron_kwh", "local_mae_ron_kwh",
                                  "weather_mae_ron_kwh", "weather_advantage_ron", "regional_advantage_ron")},
                            "optimised_savings_ron": result["strategies"]["optimised"]["savings_ron"]})
    groups = defaultdict(list)
    for row in records:
        groups[(row["day"][:7], row["battery_exports"])].append(row)
    summary = [{"month": month, "battery_exports": exports, "evaluated_days": len(rows),
                **{key: statistics.mean(r[key] for r in rows) for key in records[0]
                   if key not in {"day", "battery_exports"}},
                "days_regional_weather_helped": sum(r["regional_advantage_ron"] > 1e-5 for r in rows)}
               for (month, exports), rows in sorted(groups.items())]
    output = {"method": "28 earlier available data days, excluding the preceding day; ridge regression. Target-day weather is ERA5 reanalysis, not an issued forecast. Demand/PV and export contract are assumptions. Separate local and coastal features; no national generation model.",
              "default_config": BatteryScenario().model_dump(mode="json"), "summary": summary, "days": records}
    path = Path(__file__).with_name("weather-experiment.json")
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
