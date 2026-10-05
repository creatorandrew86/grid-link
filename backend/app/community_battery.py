"""Shared-meter battery comparisons; measured inputs never fall back to scenarios."""
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .battery import BatteryScenario, describe_schedule, history, make_intervals, optimise


class BatteryDesign(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    chemistry: Literal["LFP", "NMC", "Lead-acid"]
    capacity_kwh: float = Field(gt=0, le=1000)
    power_kw: float = Field(gt=0, le=1000)
    installed_cost_ron: float = Field(gt=0, le=10000000)
    efficiency: float = Field(gt=0, le=1)
    usable_fraction: float = Field(gt=0, le=1)
    service_years: int = Field(ge=1, le=30)
    annual_fade: float = Field(default=.02, ge=0, le=.2)
    annual_maintenance_ron: float = Field(default=100, ge=0, le=100000)


class ComparisonInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    source: Literal["measured", "planning"] = "measured"
    shared_meter_confirmed: bool = False
    funding_rule: Literal["equal_share", "consumption_share"] = "equal_share"
    designs: list[BatteryDesign] = Field(min_length=1, max_length=9)
    horizon_years: int = Field(default=10, ge=1, le=30)
    discount_rate: float = Field(default=.06, ge=0, le=.5)
    connection_import_kw: float = Field(default=100, gt=0, le=2000)
    connection_export_kw: float = Field(default=100, ge=0, le=2000)
    dispatch_wear_ron_per_kwh: float = Field(default=.15, ge=0, le=10)


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    interval_start: datetime
    interval_minutes: Literal[15, 60] = 15
    load_kwh: float = Field(ge=0, le=100000)
    generation_kwh: float = Field(ge=0, le=100000)
    import_price_ron: float = Field(ge=-100, le=100)
    export_price_ron: float = Field(ge=-100, le=100)
    member_loads_kwh: dict[UUID, float] | None = None

    @model_validator(mode="after")
    def check_time(self):
        t = self.interval_start
        if t.utcoffset() is None or t > datetime.now(timezone.utc):
            raise ValueError("Readings need a timezone and cannot be in the future.")
        if t.second or t.microsecond or int(t.timestamp()) % (self.interval_minutes * 60):
            raise ValueError("Align readings to the stated interval boundary.")
        if self.member_loads_kwh is not None:
            values = self.member_loads_kwh.values()
            if any(not math.isfinite(v) or v < 0 for v in values):
                raise ValueError("Member consumption must be finite and nonnegative.")
            if abs(sum(values) - self.load_kwh) > max(1e-4, self.load_kwh * 1e-6):
                raise ValueError("Member consumption must add up to the community's gross demand.")
        return self


class MeasurementBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    community_id: UUID
    # Gross demand and generation at the same shared meter, before a battery is installed.
    shared_meter_confirmed: Literal[True]
    battery_free_baseline_confirmed: Literal[True]
    readings: list[Measurement] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_times(self):
        if len({r.interval_start for r in self.readings}) != len(self.readings):
            raise ValueError("Duplicate interval timestamps are not allowed.")
        return self


class BatteryInterest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interested: bool


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_community_id: UUID


def financial_projection(annual_cash_saving, design, request, factor=1.):
    years = min(design.service_years, request.horizon_years)
    cashflows = [annual_cash_saving * factor * (1 - design.annual_fade) ** year
                 - design.annual_maintenance_ron for year in range(years)]
    cumulative, payback = 0., None
    timeline = [{"year": 0, "net_cash_ron": -design.installed_cost_ron,
                 "cumulative_ron": -design.installed_cost_ron}]
    for year, cash in enumerate(cashflows, 1):
        if payback is None and cash > 0 and cumulative + cash >= design.installed_cost_ron:
            payback = year - 1 + (design.installed_cost_ron - cumulative) / cash
        cumulative += cash
        timeline.append({"year": year, "net_cash_ron": cash,
                         "cumulative_ron": cumulative - design.installed_cost_ron})
    return {"years": years, "first_year_net_saving_ron": cashflows[0], "payback_years": payback,
            "roi_pct": 100 * (sum(cashflows) - design.installed_cost_ron) / design.installed_cost_ron,
            "npv_ron": sum(cash / (1 + request.discount_rate) ** year
                           for year, cash in enumerate(cashflows, 1)) - design.installed_cost_ron,
            "timeline": timeline}


def measured_days(events, community_timezone):
    zone = ZoneInfo(community_timezone)
    grouped = defaultdict(list)
    excluded = 0
    for event in events:
        s = event.get("summary", {})
        if (s.get("mode") != "measured" or s.get("currency") != "RON"
                or s.get("meter_boundary") != "shared_meter"
                or s.get("battery_free_baseline") is not True):
            excluded += 1
            continue
        try:
            reading = Measurement(interval_start=event["interval_start"],
                                  interval_minutes=s["interval_minutes"], **s["measurement"])
            grouped[reading.interval_start.astimezone(zone).date()].append(reading)
        except (KeyError, TypeError, ValueError):
            excluded += 1
    complete, incomplete = [], 0
    for day, readings in sorted(grouped.items()):
        readings.sort(key=lambda r: r.interval_start)
        start = datetime.combine(day, datetime.min.time(), zone).astimezone(timezone.utc)
        end = datetime.combine(day + timedelta(days=1), datetime.min.time(), zone).astimezone(timezone.utc)
        step = timedelta(minutes=readings[0].interval_minutes)
        expected = int((end - start) / step)
        if (len(readings) != expected or any(r.interval_minutes != readings[0].interval_minutes
                or r.interval_start != start + i * step for i, r in enumerate(readings))):
            incomplete += 1
            continue
        complete.append([{"utc": r.interval_start.isoformat(),
                          "bucharest_time": r.interval_start.astimezone(zone).isoformat(),
                          "hours": r.interval_minutes / 60, "load_kwh": r.load_kwh,
                          "pv_kwh": r.generation_kwh, "import_price": r.import_price_ron,
                          "export_price": r.export_price_ron,
                          "member_loads_kwh": {str(k): v for k, v in r.member_loads_kwh.items()}
                              if r.member_loads_kwh is not None else None} for r in readings])
    return complete, {"complete_days": len(complete), "incomplete_days": incomplete,
                      "excluded_intervals": excluded, "valid_intervals": sum(map(len, complete))}


def planning_days(participants):
    # ponytail: flat entered demand and historic weather; replace with metered profiles when available.
    load = sum(p.load_kw for p in participants) * 24
    solar = sum(p.solar_kwp for p in participants)
    config = BatteryScenario(daily_load_kwh=0, solar_kwp=0)
    result = []
    for day in sorted({r["bucharest_time"][:10] for r in history()})[-30:]:
        rows = make_intervals(config.model_copy(update={"day": datetime.fromisoformat(day).date(),
                                                        "daily_load_kwh": load, "solar_kwp": solar,
                                                        "load_profile": "flat"}))
        result.append(rows)
    return result


def compare_batteries(request, participants, events, community_timezone, meter_boundary, member_id=None):
    if not participants:
        raise ValueError("The community needs at least one member.")
    if request.source == "planning":
        if not request.shared_meter_confirmed:
            raise ValueError("Confirm the shared billing meter assumption for this planning preview.")
        days = planning_days(participants)
        coverage = {"complete_days": len(days), "incomplete_days": 0, "excluded_intervals": 0,
                    "valid_intervals": sum(map(len, days))}
    else:
        days, coverage = measured_days(events, community_timezone)
        if meter_boundary != "shared_meter":
            return {"status": "meter_boundary_unconfirmed", "coverage": coverage, "designs": [],
                    "message": "A shared billing meter must be verified before estimating community battery returns."}
    sampled = days[-30:]
    if not sampled:
        return {"status": "no_measured_history", "coverage": coverage, "designs": [],
                "message": "No complete measured days yet. Simulated settlements are excluded from measured ROI."}
    if request.source == "planning":
        loads = {p.id: p.load_kw for p in participants}
    else:
        loads = {p.id: 0. for p in participants}
        for interval in (r for day in sampled for r in day):
            measured = interval.get("member_loads_kwh")
            if measured is None or set(measured) != set(loads):
                loads = {}
                break
            for key in loads:
                loads[key] += measured[key]
    total_load = sum(loads.values())
    allocations = {"equal_share": 1 / len(participants),
                   "consumption_share": loads.get(member_id, 0.) / total_load
                       if total_load > 0 and member_id in loads else None}
    results = []
    for design in request.designs:
        config = BatteryScenario(capacity_kwh=design.capacity_kwh, charge_kw=design.power_kw,
                                 discharge_kw=design.power_kw, round_trip_efficiency=design.efficiency,
                                 reserve_fraction=1 - design.usable_fraction,
                                 initial_soc_fraction=1 - design.usable_fraction, max_soc_fraction=1,
                                 wear_ron_per_kwh=request.dispatch_wear_ron_per_kwh,
                                 grid_import_kw=request.connection_import_kw,
                                 grid_export_kw=request.connection_export_kw)
        cash, wear, base_bill = 0., 0., 0.
        try:
            for intervals in sampled:
                n = len(intervals)
                baseline = describe_schedule(intervals, config, np.zeros(n), np.zeros(n),
                                             np.full(n, config.capacity_kwh * config.initial_soc_fraction), "No battery")
                dispatch = optimise(intervals, config)
                cash += baseline["energy_cost_ron"] - dispatch["energy_cost_ron"]
                wear += dispatch["wear_cost_ron"]
                base_bill += baseline["energy_cost_ron"]
        except ValueError as error:
            results.append({"design": design.model_dump(), "error": str(error)})
            continue
        annual_cash = cash / len(sampled) * 365
        # Dispatch wear guides cycling; capex is counted once in cash projections.
        projections = {name: financial_projection(annual_cash, design, request, factor)
                       for name, factor in (("lower", .7), ("base", 1.), ("higher", 1.3))} if len(sampled) >= 30 else None
        results.append({"design": design.model_dump(), "sample_cash_saving_ron": cash,
                        "sample_saving_after_wear_ron": cash - wear, "sample_baseline_bill_ron": base_bill,
                        "annual_cash_saving_ron": annual_cash if projections else None,
                        "member_allocations": {rule: {"share": share,
                            "contribution_ron": design.installed_cost_ron * share if share is not None else None,
                            "first_year_saving_ron": projections["base"]["first_year_net_saving_ron"] * share
                                if projections and share is not None else None}
                            for rule, share in allocations.items()}, "projections": projections})
    return {"status": "ready" if len(sampled) >= 30 else "limited_history", "source": request.source,
            "currency": "RON", "coverage": {**coverage, "replayed_days": len(sampled),
                "from": sampled[0][0]["utc"], "to": sampled[-1][-1]["utc"]},
            "member_count": len(participants), "funding_rule": request.funding_rule, "designs": results,
            "notes": ["Historical optimal dispatch is an upper-bound reference, not a live forecast.",
                      "Annual savings extend the recent daily average to 365 days; seasonal coverage may be limited.",
                      "Lower/base/higher use 70%, 100%, and 130% of savings; these are sensitivity scenarios, not confidence intervals.",
                      "Cash ROI counts installed cost once; dispatch wear is excluded from financial cashflows.",
                      "Projection stops at the shorter of service life and analysis horizon. No replacements, subsidies, financing or resale value are assumed.",
                      "Equal shares divide costs and savings evenly. Consumption shares use complete per-member gross-demand readings; planning previews use entered demand.",
                      "Personal savings are an agreed allocation scenario, not a measured attribution of battery benefits. Interest is not a payment commitment."]}
