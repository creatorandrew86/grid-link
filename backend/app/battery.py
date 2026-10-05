"""Single-meter, hourly battery replay using the collected Romanian data."""
import csv
import math
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy.optimize import Bounds, LinearConstraint, milp

DATA = Path(__file__).resolve().parents[2] / "research/romania/hourly-prices-weather.csv"


class BatteryScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    day: date = date(2026, 7, 30)
    daily_load_kwh: float = Field(default=50, ge=0, le=1000)
    load_profile: Literal["evening", "flat", "daytime"] = "evening"
    solar_kwp: float = Field(default=20, ge=0, le=1000)
    pv_performance_ratio: float = Field(default=.8, gt=0, le=1)
    capacity_kwh: float = Field(default=20, ge=0, le=1000)
    charge_kw: float = Field(default=5, ge=0, le=1000)
    discharge_kw: float = Field(default=5, ge=0, le=1000)
    round_trip_efficiency: float = Field(default=.9, gt=0, le=1)
    reserve_fraction: float = Field(default=.1, ge=0, le=1)
    initial_soc_fraction: float = Field(default=.1, ge=0, le=1)
    max_soc_fraction: float = Field(default=.9, ge=0, le=1)
    wear_ron_per_kwh: float = Field(default=.15, ge=0, le=10)
    import_fee_ron_per_kwh: float = Field(default=.5879032, ge=0, le=10)
    vat_fraction: float = Field(default=.21, ge=0, le=1)
    export_price_factor: float = Field(default=1, ge=0, le=1)
    export_fee_ron_per_kwh: float = Field(default=.05, ge=0, le=10)
    grid_import_kw: float = Field(default=100, gt=0, le=2000)
    grid_export_kw: float = Field(default=100, ge=0, le=2000)
    allow_battery_export: bool = False

    @model_validator(mode="after")
    def check_soc(self):
        if not self.reserve_fraction <= self.initial_soc_fraction <= self.max_soc_fraction:
            raise ValueError("Starting battery charge must lie between the reserve and maximum charge.")
        return self


@lru_cache(maxsize=1)
def history():
    with DATA.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        for key in row:
            if key not in {"utc", "bucharest_time"}:
                row[key] = float(row[key])
    if len({r["utc"] for r in rows}) != len(rows):
        raise ValueError("The research dataset contains duplicate timestamps.")
    return rows


def dataset_info():
    days = sorted({r["bucharest_time"][:10] for r in history()})
    return {"days": days, "hours": len(history()), "location": "Bucharest",
            "resolution": "hourly", "weather": "ERA5 historical reanalysis",
            "boundary": "One shared billing meter; demand and PV are scenarios."}


def make_intervals(config):
    rows = [r for r in history() if r["bucharest_time"][:10] == config.day.isoformat()]
    if not rows:
        raise ValueError("Choose one of the dates included in the research dataset.")
    weights = []
    for row in rows:
        hour = datetime.fromisoformat(row["bucharest_time"]).hour
        weights.append(3 if config.load_profile == "evening" and 18 <= hour < 23 else
                       2 if config.load_profile == "daytime" and 8 <= hour < 18 else 1)
    intervals = []
    for row, weight in zip(rows, weights):
        # ponytail: horizontal GHI proxy; use calibrated tilted-plane PV when meter/site data exists.
        pv = min(config.solar_kwp, config.solar_kwp * row["bucharest_ghi_w_m2"] / 1000 * config.pv_performance_ratio)
        intervals.append({**row, "hours": 1., "load_kwh": config.daily_load_kwh * weight / sum(weights),
                          "pv_kwh": max(0., pv)})
    return intervals


def tariffs(price, config):
    return ((price + config.import_fee_ron_per_kwh) * (1 + config.vat_fraction),
            price * config.export_price_factor - config.export_fee_ron_per_kwh)


def interval_tariffs(interval, config, planning_price=None):
    """Research replays may supply final contract prices, including caps and export credits."""
    explicit = "import_price" in interval or "export_price" in interval
    if explicit:
        if planning_price is not None:
            raise ValueError("Explicit contract tariffs cannot be combined with raw planning prices.")
        if not all(key in interval and math.isfinite(interval[key]) for key in ("import_price", "export_price")):
            raise ValueError("Supply both finite import and export contract prices.")
        return interval["import_price"], interval["export_price"]
    return tariffs(interval["price_lei_kwh"] if planning_price is None else planning_price, config)


def describe_schedule(intervals, config, charges, discharges, states, label, flows=None):
    rows = []
    for i, interval in enumerate(intervals):
        buy, sell = interval_tariffs(interval, config)
        net = interval["load_kwh"] + charges[i] - interval["pv_kwh"] - discharges[i]
        imported = max(0., net)
        exported = min(max(0., -net), config.grid_export_kw * interval["hours"]) if sell > 0 else 0.
        curtailed = max(0., -net) - exported
        if flows is not None:
            imported, exported, curtailed = (max(0., float(block[i])) for block in flows)
        if imported > config.grid_import_kw * interval["hours"] + 1e-5:
            raise ValueError("The connection import limit cannot cover this demand scenario.")
        rows.append({**interval, "import_price": buy, "export_price": sell,
                     "charge_kwh": float(charges[i]), "discharge_kwh": float(discharges[i]),
                     "soc_kwh": float(states[i]), "grid_import_kwh": imported,
                     "grid_export_kwh": exported, "curtailed_kwh": curtailed,
                     "energy_cost_ron": imported * buy - exported * sell,
                     "wear_cost_ron": float(discharges[i]) * config.wear_ron_per_kwh})
    energy = sum(r["energy_cost_ron"] for r in rows)
    wear = sum(r["wear_cost_ron"] for r in rows)
    return {"label": label, "rows": rows, "energy_cost_ron": energy, "wear_cost_ron": wear,
            "total_cost_ron": energy + wear,
            **{key: sum(r[key] for r in rows) for key in
               ("grid_import_kwh", "grid_export_kwh", "curtailed_kwh", "charge_kwh", "discharge_kwh")},
            "equivalent_cycles": sum(discharges) / math.sqrt(config.round_trip_efficiency) / config.capacity_kwh if config.capacity_kwh else 0.}


def optimise(intervals, config, *, night_only=False, planning_prices=None, label="Optimised"):
    """Solve energy flows in kWh; settle returned schedules using actual prices."""
    n = len(intervals)
    if not n or n > 168:
        raise ValueError("Provide between one and 168 consecutive hourly intervals.")
    times = [datetime.fromisoformat(r["utc"]) for r in intervals]
    if any(abs((b - a).total_seconds() / 3600 - r["hours"]) > 1e-8
           for a, b, r in zip(times, times[1:], intervals)):
        raise ValueError("Intervals must be consecutive; reset the battery across dataset gaps.")
    eta = math.sqrt(config.round_trip_efficiency)
    start = config.capacity_kwh * config.initial_soc_fraction
    # Variable blocks: charge, discharge, import, export, curtailment, end SOC, battery mode, grid mode.
    lower, upper, objective = np.zeros(8 * n), np.zeros(8 * n), np.zeros(8 * n)
    integral = np.zeros(8 * n)
    constraints, lows, highs = [], [], []

    def constraint(values, low, high):
        row = np.zeros(8 * n)
        for index, value in values.items():
            row[index] = value
        constraints.append(row); lows.append(low); highs.append(high)

    for t, interval in enumerate(intervals):
        c, d, imp, exp, spill, soc, mode, grid = [block * n + t for block in range(8)]
        hours = interval["hours"]
        charge_max, discharge_max = config.charge_kw * hours, config.discharge_kw * hours
        import_max, export_max = config.grid_import_kw * hours, config.grid_export_kw * hours
        hour = datetime.fromisoformat(interval["bucharest_time"]).hour
        if night_only:
            charge_max *= hour < 6
            discharge_max *= 18 <= hour < 23
        if not config.allow_battery_export:
            discharge_max = min(discharge_max, max(0., interval["load_kwh"] - interval["pv_kwh"]))
        upper[[c, d, imp, exp, spill, soc, mode, grid]] = [charge_max, discharge_max, import_max,
            export_max, interval["pv_kwh"], config.capacity_kwh * config.max_soc_fraction, 1, 1]
        lower[soc] = config.capacity_kwh * config.reserve_fraction
        integral[[mode, grid]] = 1
        buy, sell = interval_tariffs(interval, config, planning_prices[t] if planning_prices is not None else None)
        objective[imp], objective[exp], objective[d] = buy, -sell, config.wear_ron_per_kwh
        constraint({imp: 1, d: 1, c: -1, exp: -1, spill: -1},
                   interval["load_kwh"] - interval["pv_kwh"], interval["load_kwh"] - interval["pv_kwh"])
        balance = {soc: 1, c: -eta, d: 1 / eta}
        if t:
            balance[soc - 1] = -1
        constraint(balance, start if t == 0 else 0, start if t == 0 else 0)
        constraint({c: 1, mode: -charge_max}, -np.inf, 0)
        constraint({d: 1, mode: discharge_max}, -np.inf, discharge_max)
        constraint({imp: 1, grid: -import_max}, -np.inf, 0)
        constraint({exp: 1, grid: export_max}, -np.inf, export_max)
    lower[6 * n - 1] = upper[6 * n - 1] = start
    solution = milp(objective, integrality=integral, bounds=Bounds(lower, upper),
                    constraints=LinearConstraint(np.array(constraints), lows, highs),
                    options={"time_limit": 15., "mip_rel_gap": 1e-7})
    if not solution.success:
        raise ValueError("No optimal schedule was found within the limits. Check the connection and battery settings.")
    values = solution.x
    result = describe_schedule(intervals, config, np.maximum(0., values[:n]),
                               np.maximum(0., values[n:2*n]), values[5*n:6*n], label,
                               flows=(values[2*n:3*n], values[3*n:4*n], values[4*n:5*n]))
    result["solver"] = "SciPy / HiGHS mixed-integer optimisation"
    return result


def simulate(config):
    from .weather import historical_estimates, opportunity_signals
    intervals = make_intervals(config)
    zeros = np.zeros(len(intervals))
    start = config.capacity_kwh * config.initial_soc_fraction
    baseline = describe_schedule(intervals, config, zeros, zeros, np.full(len(intervals), start), "No battery")
    strategies = {"baseline": baseline,
                  "night": optimise(intervals, config, night_only=True, label="Night-only"),
                  "optimised": optimise(intervals, config)}
    experiment = historical_estimates(config.day.isoformat(), intervals)
    if experiment["available"]:
        for key, title in (("calendar", "Calendar price estimate"), ("local", "Local weather estimate"), ("weather", "Local + coastal weather estimate")):
            strategies[key] = optimise(intervals, config, planning_prices=experiment[f"{key}_prices"], label=title)
        experiment["weather_advantage_ron"] = strategies["calendar"]["total_cost_ron"] - strategies["weather"]["total_cost_ron"]
        experiment["regional_advantage_ron"] = strategies["local"]["total_cost_ron"] - strategies["weather"]["total_cost_ron"]
    for strategy in strategies.values():
        strategy["savings_ron"] = baseline["total_cost_ron"] - strategy["total_cost_ron"]
    return {"config": config.model_dump(mode="json"), "strategies": strategies,
            "weather_experiment": experiment, "opportunities": opportunity_signals(intervals, config),
            "notes": ["Historical replay: actual prices and ERA5 weather, with assumed demand and horizontal-plane PV.",
                      "One shared billing meter. Results are in RON; community settlement settings remain separate.",
                      "Import fees/VAT use the research reference; exports use an illustrative wholesale-linked contract.",
                      "Every schedule ends at its starting battery charge. Wear is an assumption; equipment cost is excluded.",
                      "Night-only is the best feasible 00:00–06:00 charging / 18:00–23:00 discharge schedule; it can skip cycles."]}
