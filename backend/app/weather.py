"""Experimental weather-price comparison; the coastal points are proxies, not national generation."""
import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import numpy as np

LOCAL_TIME = ZoneInfo("Europe/Bucharest")
LOCATIONS = {"bucharest": (44.4268, 26.1025), "constanta": (44.1598, 28.6348), "tulcea": (45.1787, 28.8050),
             "arad": (46.1866, 21.3123), "craiova": (44.3302, 23.7949), "giurgiu": (43.9037, 25.9699)}


def wind_proxy(speed):
    # ponytail: generic turbine curve; replace with fleet-weighted curves and measured generation.
    return 0. if speed < 3 or speed >= 25 else min(1., (speed ** 3 - 3 ** 3) / (12 ** 3 - 3 ** 3))


def weather_features(row):
    temperature = row["bucharest_temperature_c"]
    return [row["bucharest_ghi_w_m2"] / 1000, max(0., 18 - temperature), max(0., temperature - 22),
            (row["constanta_ghi_w_m2"] + row["tulcea_ghi_w_m2"]) / 2000,
            (wind_proxy(row["constanta_wind_100m_m_s"]) + wind_proxy(row["tulcea_wind_100m_m_s"])) / 2]


def calendar_features(row):
    stamp = datetime.fromisoformat(row["bucharest_time"])
    hour = stamp.hour
    return [float(hour == h) for h in range(24)] + [float(stamp.weekday() >= 5),
            math.sin(2 * math.pi * stamp.timetuple().tm_yday / 365.25),
            math.cos(2 * math.pi * stamp.timetuple().tm_yday / 365.25)]


def predict_prices(training, targets, with_weather, regional=True):
    def features(row):
        return calendar_features(row) + (weather_features(row)[:5 if regional else 3] if with_weather else [])
    x = np.array([features(r) for r in training])
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale < 1e-8] = 1
    x = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    y = np.array([r["price_lei_kwh"] for r in training])
    penalty = np.eye(x.shape[1]) * 10
    penalty[0, 0] = 0
    coefficients = np.linalg.solve(x.T @ x + penalty, x.T @ y)
    future = np.array([features(r) for r in targets])
    predictions = np.column_stack([np.ones(len(future)), (future - mean) / scale]) @ coefficients
    # Guard extrapolation outside this very small seasonal dataset; these are estimates, not quotes.
    return np.clip(predictions, -2., 5.).tolist()


def historical_estimates(day, intervals):
    from .battery import history
    cutoff = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    available = sorted({r["bucharest_time"][:10] for r in history() if r["bucharest_time"][:10] < cutoff})[-28:]
    training = [r for r in history() if r["bucharest_time"][:10] in available]
    result = {"available": len(available) >= 7, "training_days": len(available),
              "training_end": available[-1] if available else None,
              "note": "Exploratory held-out day: training ends before the preceding day. Target-day weather is ERA5 reanalysis, not an archived issued forecast. This tests weather information under optimistic availability, not live forecast performance."}
    if not result["available"]:
        result["note"] = "At least seven earlier data days are required for the price-estimate comparison."
        return result
    for name, with_weather, regional in (("calendar", False, False), ("local", True, False), ("weather", True, True)):
        prices = predict_prices(training, intervals, with_weather, regional)
        result[f"{name}_prices"] = prices
        result[f"{name}_mae_ron_kwh"] = sum(abs(p - r["price_lei_kwh"]) for p, r in zip(prices, intervals)) / len(intervals)
    return result


def opportunity_signals(intervals, config):
    result = []
    for row in intervals:
        coast_solar, coast_wind = weather_features(row)[3:]
        local = row["bucharest_ghi_w_m2"] / 1000
        surplus = max(0., row.get("pv_kwh", 0.) - row.get("load_kwh", 0.))
        # Thresholds are illustrative and visible in the documentation, not learned shortage probabilities.
        signal = "Local surplus / weak coastal renewables" if surplus > 0 and coast_wind < .2 and coast_solar < local * .7 else \
                 "Broad renewable availability" if coast_wind > .5 or coast_solar > .5 else "No strong weather mismatch"
        result.append({"bucharest_time": row["bucharest_time"], "local_surplus_kwh": surplus,
                       "coastal_solar_proxy": coast_solar, "coastal_wind_proxy": coast_wind, "signal": signal})
    return result


def live_outlook():
    """Fetch a current forecast. Keep predictions advisory and separate from historical dispatch."""
    from .battery import history
    retrieved = datetime.now(timezone.utc)
    response = httpx.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": ",".join(str(v[0]) for v in LOCATIONS.values()),
        "longitude": ",".join(str(v[1]) for v in LOCATIONS.values()),
        "hourly": "temperature_2m,shortwave_radiation,wind_speed_100m",
        "models": "ecmwf_ifs", "wind_speed_unit": "ms", "timezone": "UTC", "forecast_days": 4,
    }, timeout=20)
    response.raise_for_status()
    forecasts = response.json()
    if not isinstance(forecasts, list) or len(forecasts) != len(LOCATIONS):
        raise ValueError("The weather provider returned incomplete location forecasts.")
    by_location = {}
    for name, forecast in zip(LOCATIONS, forecasts):
        hourly = forecast["hourly"]
        by_location[name] = {stamp: {key: hourly[key][i] for key in
                             ("temperature_2m", "shortwave_radiation", "wind_speed_100m")}
                             for i, stamp in enumerate(hourly["time"])}
    rows = []
    for stamp, local in by_location["bucharest"].items():
        utc = datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
        if utc < retrieved or utc >= retrieved + timedelta(hours=48):
            continue
        row = {"utc": utc.isoformat(), "bucharest_time": utc.astimezone(LOCAL_TIME).isoformat()}
        next_stamp = (utc + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        for name in LOCATIONS:
            start = by_location[name].get(stamp)
            end = by_location[name].get(next_stamp)
            if start is None or end is None or any(v is None or not math.isfinite(v) for v in (*start.values(), *end.values())):
                raise ValueError("The weather provider returned missing forecast values.")
            # Radiation at t+1 is the preceding hour's mean; wind/temperature are instantaneous at t.
            row.update({f"{name}_temperature_c": start["temperature_2m"],
                        f"{name}_ghi_w_m2": end["shortwave_radiation"],
                        f"{name}_wind_100m_m_s": start["wind_speed_100m"]})
        rows.append(row)
    if not rows:
        raise ValueError("The weather provider returned no upcoming forecast hours.")
    # Fit only completed research days available before retrieval, even if the system clock changes.
    complete_days = sorted({r["bucharest_time"][:10] for r in history()
                            if datetime.fromisoformat(r["utc"]) < retrieved - timedelta(days=1)})[-28:]
    if len(complete_days) < 7:
        raise ValueError("Not enough completed research days are available to estimate prices.")
    training = [r for r in history() if r["bucharest_time"][:10] in complete_days]
    calendar, weather = predict_prices(training, rows, False), predict_prices(training, rows, True)
    for row, base, estimate in zip(rows, calendar, weather):
        row.update({"calendar_price_estimate": base, "weather_price_estimate": estimate,
                    "weather_adjustment": estimate - base,
                    "coastal_wind_proxy": weather_features(row)[4]})
    regions = [{"name": name.title(), "irradiation_kwh_m2": sum(r[f"{name}_ghi_w_m2"] for r in rows) / 1000,
                "mean_wind_100m_m_s": sum(r[f"{name}_wind_100m_m_s"] for r in rows) / len(rows)} for name in LOCATIONS]
    return {"retrieved_at": retrieved.isoformat(), "training_end": complete_days[-1], "regions": regions,
            "locations": LOCATIONS, "rows": rows,
            "note": "Current ECMWF IFS forecast via Open-Meteo. Retrieval time is recorded; model issuance time is not supplied by this endpoint. Prices are unvalidated estimates, not OPCOM quotes. The price model uses Bucharest and Constanta/Tulcea; Arad, Craiova and Giurgiu add regional context only. These points are not a capacity-weighted national generation forecast; imports, outages and hydro are absent. Published prices should take priority."}
