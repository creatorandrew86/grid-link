"""Download public OPCOM prices and ERA5 weather for the Romanian research note.

Run with the project's Python environment. Existing downloads are reused.
This is research tooling; it does not change GridLink's pricing or dispatch.
"""
import calendar
import concurrent.futures
import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
MONTHS = [(2026, 1, 31), (2026, 4, 30), (2026, 7, 31), (2026, 9, 28)]
BUCHAREST = ZoneInfo("Europe/Bucharest")
MARKET_TIME = ZoneInfo("Europe/Brussels")
OPCOM = "https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv"


def download(url, path, params=None):
    if path.exists():
        return path.read_text(encoding="utf-8")
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
    path.write_text(response.text, encoding="utf-8")
    return response.text


def price_day(day):
    url = f"{OPCOM}/{day:%d/%m/%Y}/ro?resolution=15"
    body = download(url, RAW / f"opcom-{day}.csv")
    rows = [r for r in csv.reader(io.StringIO(body)) if r and r[0] == "Romania"]
    start = datetime.combine(day, datetime.min.time(), MARKET_TIME).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), MARKET_TIME).astimezone(timezone.utc)
    assert len(rows) == int((end - start).total_seconds() / 900), (day, len(rows))
    result = []
    for index, row in enumerate(rows):
        assert int(row[1]) == index + 1 and row[6] == "PT15M", (day, row)
        timestamp = start + timedelta(minutes=15 * index)
        local = timestamp.astimezone(BUCHAREST)
        result.append({"utc": timestamp.isoformat(), "local": local.isoformat(),
                       "market_delivery_date": day.isoformat(), "market_interval": index + 1,
                       "price_lei_mwh": float(row[2]), "source_url": url})
    return result


def weather_place(place, lat, lon):
    params = {"latitude": lat, "longitude": lon, "start_date": "2025-12-31",
              "end_date": "2026-09-29", "models": "era5", "timezone": "UTC",
              "timeformat": "unixtime", "wind_speed_unit": "ms",
              "hourly": "temperature_2m,shortwave_radiation,cloud_cover,wind_speed_100m,precipitation"}
    body = download("https://archive-api.open-meteo.com/v1/archive", RAW / f"era5-{place}.json", params)
    data = json.loads(body)
    series = data["hourly"]
    assert all(len(v) == len(series["time"]) for v in series.values())
    # Radiation and precipitation are averages/sums for the preceding hour.
    # The record at t+1 describes the price interval starting at t.
    result = {}
    for i, epoch in enumerate(series["time"][:-1]):
        result[epoch] = {
            "temperature_c": series["temperature_2m"][i],
            "ghi_w_m2": series["shortwave_radiation"][i + 1],
            "cloud_cover_pct": series["cloud_cover"][i],
            "wind_100m_m_s": series["wind_speed_100m"][i],
            "precipitation_mm": series["precipitation"][i + 1],
        }
    return place, result


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    RAW.mkdir(exist_ok=True, parents=True)
    days = set()
    selected_days = set()
    for year, month, last in MONTHS:
        assert last <= calendar.monthrange(year, month)[1]
        first = date(year, month, 1)
        days.add(first - timedelta(days=1))  # Bucharest midnight is the preceding market day's last hour.
        for offset in range(last):
            day = first + timedelta(days=offset)
            days.add(day)
            selected_days.add(day.isoformat())
    intervals = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for index, rows in enumerate(pool.map(price_day, sorted(days)), 1):
            intervals.extend(r for r in rows if r["local"][:10] in selected_days)
            if index % 20 == 0:
                print(f"Downloaded {index}/{len(days)} OPCOM days", flush=True)
    intervals.sort(key=lambda r: r["utc"])
    assert len(intervals) == len(selected_days) * 96 == 11520
    assert len({r["utc"] for r in intervals}) == len(intervals)
    write_csv(HERE / "prices-15min.csv", intervals)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        weather = dict(pool.map(lambda args: weather_place(*args), [
            ("bucharest", 44.4268, 26.1025), ("constanta", 44.1598, 28.6348),
            ("tulcea", 45.1787, 28.8050)]))
    hourly = []
    for index in range(0, len(intervals), 4):
        group = intervals[index:index + 4]
        timestamp = datetime.fromisoformat(group[0]["utc"])
        assert timestamp.minute == 0
        assert all(datetime.fromisoformat(r["utc"]) == timestamp + timedelta(minutes=15 * j)
                   for j, r in enumerate(group))
        epoch = int(timestamp.timestamp())
        row = {"utc": group[0]["utc"], "bucharest_time": group[0]["local"],
               "price_lei_kwh": round(sum(r["price_lei_mwh"] for r in group) / 4000, 8)}
        for place, data in weather.items():
            assert epoch in data and all(value is not None for value in data[epoch].values()), (place, timestamp)
            row.update({f"{place}_{key}": value for key, value in data[epoch].items()})
        hourly.append(row)
    write_csv(HERE / "hourly-prices-weather.csv", hourly)
    metadata = {"retrieved_on": "2026-10-04", "price_source": OPCOM,
                "weather_source": "https://archive-api.open-meteo.com/v1/archive",
                "weather_model": "ERA5; gridded reanalysis, not rooftop measurements",
                "selection": MONTHS, "local_days": len(selected_days),
                "price_intervals": len(intervals), "paired_hours": len(hourly),
                "clock": "OPCOM Europe/Brussels converted via UTC to Europe/Bucharest",
                "radiation_alignment": "ERA5 preceding-hour mean at t+1 paired with price starting at t"}
    (HERE / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
