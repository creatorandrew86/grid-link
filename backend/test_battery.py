"""Run with the existing unittest command; no network is required."""
import math
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.battery import BatteryScenario, history, make_intervals, optimise, simulate
from app.main import create_app
from app.weather import historical_estimates, wind_proxy


class BatteryChecks(unittest.TestCase):
    def check_physics(self, strategy, config):
        previous = config.capacity_kwh * config.initial_soc_fraction
        eta = math.sqrt(config.round_trip_efficiency)
        for row in strategy["rows"]:
            self.assertAlmostEqual(row["pv_kwh"] + row["grid_import_kwh"] + row["discharge_kwh"],
                                   row["load_kwh"] + row["charge_kwh"] + row["grid_export_kwh"] + row["curtailed_kwh"], places=5)
            self.assertAlmostEqual(row["soc_kwh"], previous + row["charge_kwh"] * eta - row["discharge_kwh"] / eta, places=5)
            self.assertLessEqual(row["charge_kwh"], config.charge_kw * row["hours"] + 1e-5)
            self.assertLessEqual(row["discharge_kwh"], config.discharge_kw * row["hours"] + 1e-5)
            self.assertGreaterEqual(row["soc_kwh"] + 1e-5, config.capacity_kwh * config.reserve_fraction)
            self.assertLessEqual(row["soc_kwh"], config.capacity_kwh * config.max_soc_fraction + 1e-5)
            self.assertLessEqual(row["curtailed_kwh"], row["pv_kwh"] + 1e-5)
            self.assertLess(row["charge_kwh"] * row["discharge_kwh"], 1e-5)
            self.assertLess(row["grid_import_kwh"] * row["grid_export_kwh"], 1e-5)
            previous = row["soc_kwh"]
        self.assertAlmostEqual(previous, config.capacity_kwh * config.initial_soc_fraction, places=5)
        self.assertAlmostEqual(strategy["total_cost_ron"], sum(r["energy_cost_ron"] + r["wear_cost_ron"] for r in strategy["rows"]), places=5)

    def test_real_days_physics_and_baselines(self):
        for settings in ({"day": "2026-01-20", "solar_kwp": 0},
                         {"day": "2026-04-26", "allow_battery_export": True, "grid_export_kw": 3},
                         {"day": "2026-07-30"}, {"day": "2026-09-13", "capacity_kwh": 0}):
            config = BatteryScenario(**settings)
            result = simulate(config)
            for strategy in result["strategies"].values():
                self.check_physics(strategy, config)
            best, baseline, night = [result["strategies"][k]["total_cost_ron"] for k in ("optimised", "baseline", "night")]
            self.assertLessEqual(best, baseline + 1e-5)
            self.assertLessEqual(best, night + 1e-5)
            if config.capacity_kwh == 0:
                self.assertAlmostEqual(best, baseline, places=5)
            if result["weather_experiment"]["available"]:
                self.assertLess(result["weather_experiment"]["training_end"], config.day.isoformat())

    def test_hand_calculated_arbitrage_and_negative_prices(self):
        config = BatteryScenario(daily_load_kwh=0, solar_kwp=0, capacity_kwh=5, charge_kw=5, discharge_kw=5,
                                 reserve_fraction=0, initial_soc_fraction=0, max_soc_fraction=1,
                                 round_trip_efficiency=1, wear_ron_per_kwh=0,
                                 import_fee_ron_per_kwh=0, vat_fraction=0, export_fee_ron_per_kwh=0)
        stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        intervals = [{"utc": (stamp + timedelta(hours=i)).isoformat(),
                      "bucharest_time": (stamp + timedelta(hours=i)).isoformat(), "hours": 1,
                      "price_lei_kwh": price, "pv_kwh": 0, "load_kwh": load}
                     for i, (price, load) in enumerate(((1, 0), (3, 5)))]
        result = optimise(intervals, config)
        self.check_physics(result, config)
        self.assertAlmostEqual(result["total_cost_ron"], 5, places=5)
        intervals[0]["price_lei_kwh"] = -1
        result = optimise(intervals, config)
        self.check_physics(result, config)
        self.assertAlmostEqual(result["total_cost_ron"], -5, places=5)
        # A flat positive price and losses cannot justify cycling.
        config = config.model_copy(update={"round_trip_efficiency": .9, "wear_ron_per_kwh": .1})
        intervals[0]["price_lei_kwh"] = intervals[1]["price_lei_kwh"] = 1
        self.assertAlmostEqual(optimise(intervals, config)["charge_kwh"], 0, places=5)
        intervals[1]["utc"] = (stamp + timedelta(days=5)).isoformat()
        with self.assertRaises(ValueError):
            optimise(intervals, config)
        self.assertEqual(wind_proxy(2), 0)
        self.assertEqual(wind_proxy(26), 0)

    def test_api_validation_serialisation_and_provider_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "GRIDLINK_DB_PATH": str(Path(directory) / "test.db"), "GRIDLINK_SEED_DEMO": "0",
            "SUPABASE_URL": "", "SUPABASE_SECRET_KEY": "", "SUPABASE_SERVICE_ROLE_KEY": "",
        }):
            with TestClient(create_app()) as client:
                self.assertEqual(len(client.get("/api/battery/dataset").json()["days"]), 120)
                response = client.post("/api/battery/simulate", json={})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn("optimised", response.json()["strategies"])
                for bad in ({"day": "2026-03-01"}, {"round_trip_efficiency": 0},
                            {"initial_soc_fraction": 0}, {"unknown": 1}):
                    self.assertEqual(client.post("/api/battery/simulate", json=bad).status_code, 422)
                with self.assertRaises(ValueError):
                    BatteryScenario(capacity_kwh=float("inf"))
                self.assertFalse(historical_estimates("2026-01-01", make_intervals(BatteryScenario(day="2026-01-01")))["available"])
                with patch("app.main.live_outlook", side_effect=ValueError("missing forecast")):
                    self.assertEqual(client.get("/api/battery/weather-outlook").status_code, 503)

    def test_estimate_training_excludes_future_prices_and_weather(self):
        config = BatteryScenario()
        intervals = make_intervals(config)
        original = historical_estimates(config.day.isoformat(), intervals)
        changed = [{**r, "price_lei_kwh": r["price_lei_kwh"] + 100,
                    "constanta_ghi_w_m2": 10000} if r["bucharest_time"][:10] >= "2026-07-29" else r
                   for r in history()]
        with patch("app.battery.history", return_value=changed):
            result = historical_estimates(config.day.isoformat(), intervals)
        for key in ("calendar_prices", "local_prices", "weather_prices"):
            self.assertEqual(original[key], result[key])


if __name__ == "__main__":
    unittest.main()
