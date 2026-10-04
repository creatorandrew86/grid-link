"""Reproduce price summaries and an explicitly assumed battery benchmark.

Inputs are public market prices and ERA5 weather, not GridLink meter readings.
The benchmark compares the same assumed 25 kWh evening deficit in every policy.
"""
import csv
import json
import os
import statistics as stats
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(HERE.parent.parent / ".tools" / "research-mpl"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

FEE = 0.5879032  # Current published Hidro Dinamic C, Bucharest, excluding VAT and PZU.
VAT = 1.21
EFFICIENCY = 0.90
WEAR = 0.15  # Assumption, lei per AC kWh delivered; not a supplier/manufacturer quote.
OUTPUT_KWH = 20.0
POWER_KW = 5.0
LABELS = {"01": "January", "04": "April", "07": "July", "09": "September 1-28"}


def rate(p):
    return VAT * (p + FEE)


def fill_cost(rows, energy, reverse=False):
    remaining = energy
    cost = 0.0
    selected = []
    for row in sorted(rows, key=lambda r: r["price_lei_kwh"], reverse=reverse):
        quantity = min(POWER_KW, remaining)
        if quantity <= 1e-10:
            break
        cost += quantity * rate(row["price_lei_kwh"])
        selected.append((row["hour"], quantity))
        remaining -= quantity
    assert remaining < 1e-8
    return cost, selected


def main():
    with (HERE / "hourly-prices-weather.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in list(row):
            if key not in {"utc", "bucharest_time"}:
                row[key] = float(row[key])
        row["hour"] = int(row["bucharest_time"][11:13])
        row["day"] = row["bucharest_time"][:10]
        row["month"] = row["day"][5:7]
    days = defaultdict(list)
    months = defaultdict(list)
    for row in rows:
        days[row["day"]].append(row)
        months[row["month"]].append(row)
    hourly_means = []
    for hour in range(24):
        hourly_means.append({"bucharest_hour_start": hour, **{
            m: stats.mean(r["price_lei_kwh"] for r in months[m] if r["hour"] == hour)
            for m in LABELS}})
    daily = []
    for day, group in sorted(days.items()):
        assert len(group) == 24
        night = [r for r in group if r["hour"] < 6]
        midday = [r for r in group if 10 <= r["hour"] < 17]
        evening = [r for r in group if 18 <= r["hour"] < 23]
        before_evening = [r for r in group if r["hour"] < 18]
        night_price = stats.mean(r["price_lei_kwh"] for r in night)
        evening_price = stats.mean(r["price_lei_kwh"] for r in evening)
        best_night_cost, _ = fill_cost(night, OUTPUT_KWH / EFFICIENCY)
        best_day_cost, selected = fill_cost(before_evening, OUTPUT_KWH / EFFICIENCY)
        avoided_cost, _ = fill_cost(evening, OUTPUT_KWH, reverse=True)
        fixed_margin = OUTPUT_KWH * (rate(evening_price) - rate(night_price) / EFFICIENCY - WEAR)
        night_margin = avoided_cost - best_night_cost - OUTPUT_KWH * WEAR
        day_margin = avoided_cost - best_day_cost - OUTPUT_KWH * WEAR
        assert day_margin + 1e-8 >= night_margin
        minimum = min(group, key=lambda r: r["price_lei_kwh"])
        daily.append({"date": day,
                      "night_00_06_lei_kwh": night_price,
                      "midday_10_17_lei_kwh": stats.mean(r["price_lei_kwh"] for r in midday),
                      "evening_18_23_lei_kwh": evening_price,
                      "daily_min_lei_kwh": minimum["price_lei_kwh"], "daily_min_hour": minimum["hour"],
                      "daily_max_lei_kwh": max(r["price_lei_kwh"] for r in group),
                      "ghi_kwh_m2": sum(r["bucharest_ghi_w_m2"] for r in group) / 1000,
                      "temperature_max_c": max(r["bucharest_temperature_c"] for r in group),
                      "temperature_min_c": min(r["bucharest_temperature_c"] for r in group),
                      "dobrogea_wind_100m_m_s": stats.mean((r["constanta_wind_100m_m_s"] + r["tulcea_wind_100m_m_s"]) / 2 for r in group),
                      "precipitation_mm": sum(r["bucharest_precipitation_mm"] for r in group),
                      "fixed_night_margin_lei": fixed_margin,
                      "price_aware_night_margin_lei": night_margin,
                      "price_aware_day_margin_lei": day_margin,
                      "day_charge_hours": ";".join(f"{h:02d}:00={q:.3f}kWh" for h, q in sorted(selected))})
    summary = {}
    for m, group in months.items():
        period = [d for d in daily if d["date"][5:7] == m]
        summary[m] = {"days": len(period), "wholesale_mean": stats.mean(r["price_lei_kwh"] for r in group),
                      "night": stats.mean(d["night_00_06_lei_kwh"] for d in period),
                      "midday": stats.mean(d["midday_10_17_lei_kwh"] for d in period),
                      "evening": stats.mean(d["evening_18_23_lei_kwh"] for d in period),
                      "negative_hourly_means": sum(r["price_lei_kwh"] < 0 for r in group),
                      "min_hourly": min(r["price_lei_kwh"] for r in group),
                      "max_hourly": max(r["price_lei_kwh"] for r in group),
                      "mean_daily_ghi": stats.mean(d["ghi_kwh_m2"] for d in period),
                      "midday_cheaper_days": sum(d["midday_10_17_lei_kwh"] < d["night_00_06_lei_kwh"] for d in period),
                      "cheapest_hour_midday_days": sum(10 <= d["daily_min_hour"] < 17 for d in period)}
        for policy in ["fixed_night", "price_aware_night", "price_aware_day"]:
            values = [d[f"{policy}_margin_lei"] for d in period]
            summary[m][policy] = {"raw_mean_lei_day": stats.mean(values),
                                  "mean_with_unprofitable_cycles_skipped": stats.mean(max(0, x) for x in values),
                                  "unprofitable_full_cycles": sum(x < 0 for x in values),
                                  "period_savings_with_skips": sum(max(0, x) for x in values)}
    for name, data in [("hourly-means.csv", hourly_means), ("daily-benchmark.csv", daily)]:
        with (HERE / name).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    (HERE / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), gridspec_kw={"height_ratios": [2, 1]})
    colors = ["#4063b0", "#238b45", "#d87819", "#8e4585"]
    for m, color in zip(LABELS, colors):
        axes[0].plot(range(24), [h[m] for h in hourly_means], color=color, linewidth=2.5, label=LABELS[m])
    axes[0].axhline(0, color="#888888", linewidth=0.8)
    axes[0].set(xlim=(0, 23), xticks=range(0, 24, 2), ylabel="Wholesale price (lei/kWh)",
                xlabel="Hour starting, Bucharest time", title="Romanian day-ahead prices: cheap hours shift with the season")
    axes[0].legend(ncol=2, frameon=False)
    axes[0].grid(axis="y", alpha=0.2)
    for index, m in enumerate(LABELS):
        x = [index - .24, index, index + .24]
        policies = ["fixed_night", "price_aware_night", "price_aware_day"]
        axes[1].bar(x, [summary[m][p]["mean_with_unprofitable_cycles_skipped"] for p in policies],
                    width=.22, color=["#969696", "#4063b0", "#238b45"])
    axes[1].set(xticks=range(4), xticklabels=list(LABELS.values()), ylabel="Illustrative saving (lei/day)")
    axes[1].legend(handles=[Patch(color=color, label=label) for color, label in zip(
        ["#969696", "#4063b0", "#238b45"],
        ["Fixed night, skip losses", "Best night hours", "Best hours before evening"])],
        ncol=3, frameon=False, fontsize=10)
    axes[1].grid(axis="y", alpha=.2)
    fig.text(.07, .012, "OPCOM data, 120 local days in 2026. Benchmark: 20 kWh delivered/day, 5 kW, 90% efficiency, "
             "0.15 lei/kWh wear;\ncurrent Hidro Dinamic C Bucharest fees applied retrospectively. "
             "Assumed evening deficit; no measured community load or PV.", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, .065, 1, 1))
    fig.savefig(HERE / "price-patterns-and-battery.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True)
    for col, day in enumerate(["2026-04-02", "2026-04-26"]):
        group = days[day]
        axes[0, col].plot(range(24), [r["price_lei_kwh"] for r in group], color="#4063b0", linewidth=2)
        axes[0, col].axhline(0, color="#888888", linewidth=.8)
        axes[0, col].set(title=f"{day}: {'rainy Thursday' if col == 0 else 'sunny Sunday'}",
                         ylim=(-.55, 1.0), ylabel="Wholesale price (lei/kWh)")
        axes[1, col].fill_between(range(24), [r["bucharest_ghi_w_m2"] for r in group], color="#e3b42f", alpha=.65)
        axes[1, col].set(ylim=(0, 1000), ylabel="Solar radiation (W/m²)",
                         xlabel="Hour starting, Bucharest", xticks=range(0, 24, 3))
        for ax in axes[:, col]:
            ax.grid(axis="y", alpha=.2)
    fig.suptitle("Matched Romanian prices and Bucharest ERA5 weather")
    fig.text(.065, .02, "OPCOM hourly means and ERA5 gridded reanalysis. "
             "These days also differ in demand, wind and other conditions; this comparison does not isolate weather causally.",
             fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, .055, 1, .96))
    fig.savefig(HERE / "weather-and-prices.png", dpi=160)
    plt.close(fig)
    print(json.dumps(summary, indent=2))
    print("WEATHER / PRICE CASES")
    for day in ["2026-01-20", "2026-01-27", "2026-04-02", "2026-04-26", "2026-07-22", "2026-07-30", "2026-09-13"]:
        print(next(d for d in daily if d["date"] == day))
    print("HIGHEST PRICE", max(daily, key=lambda d: d["daily_max_lei_kwh"]))


if __name__ == "__main__":
    main()
