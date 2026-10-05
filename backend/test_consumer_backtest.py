"""Regression checks for measured-meter conversion and investment accounting."""
import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.romania.backtest_consumers import (
    HOUSE_FEEDS, INSTALL_RON, UNIT_COST_RON, measured_days, summarise,
)
from research.romania.backtest_prosumers import finances


class ConsumerBacktestTests(unittest.TestCase):
    def test_prosumer_projection_stops_quantitative_compensation_in_2030(self):
        result = finances(1000, 0, 1)
        self.assertAlmostEqual(result["yearly_net_cashflows_ron"][0], 900)
        self.assertAlmostEqual(result["yearly_net_cashflows_ron"][4], 130.59204)
        self.assertEqual(result["yearly_net_cashflows_ron"][5], -100)
        self.assertIsNone(result["projected_payback_within_10_years"])
        self.assertLess(result["ten_year_npv_ron_at_6pct"], 0)
        zero = finances(0, 0, 1)
        self.assertAlmostEqual(zero["ten_year_cash_roi_pct"],
                               -100 * (UNIT_COST_RON + INSTALL_RON + 1000) / (UNIT_COST_RON + INSTALL_RON))

    def meter_fixture(self, flagged=False):
        fields = ["utc_timestamp", "cet_cest_timestamp", "interpolated"]
        fields += [f"DE_KN_residential{house}_{feed}"
                   for house, feeds in HOUSE_FEEDS.items() for feed in feeds]
        rows = []
        local = datetime(2016, 1, 1, 23, tzinfo=timezone(timedelta(hours=1)))
        import2, import3, pv3, export3 = 100., 100., 100., 100.
        for step in range(25):
            if step:
                import2 += step
                import3 += 1
                pv3 += 2
                export3 += .5
            stamp = local + timedelta(hours=step)
            row = dict.fromkeys(fields, "")
            row.update(utc_timestamp=stamp.astimezone(timezone.utc).isoformat(),
                       cet_cest_timestamp=stamp.isoformat(),
                       DE_KN_residential2_grid_import=import2,
                       DE_KN_residential3_grid_import=import3,
                       DE_KN_residential3_pv=pv3,
                       DE_KN_residential3_grid_export=export3)
            if flagged and step == 13:
                row["interpolated"] = "DE_KN_residential2_grid_import;"
            rows.append(row)
        return fields, rows

    def read_fixture(self, flagged=False):
        fields, rows = self.meter_fixture(flagged)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meters.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            return measured_days(path)

    def test_cumulative_hour_end_alignment_and_gross_pv_demand(self):
        complete, _ = self.read_fixture()
        house2 = next(rows for (house, _), rows in complete.items() if house == 2)
        house3 = next(rows for (house, _), rows in complete.items() if house == 3)
        self.assertEqual(house2[0]["hour"], 0)
        self.assertEqual(house2[0]["load_kwh"], 1.)
        self.assertEqual(house2[-1]["load_kwh"], 24.)
        self.assertEqual(sum(r["load_kwh"] for r in house2), 300.)
        self.assertEqual(sum(r["load_kwh"] for r in house3), 60.)

    def test_flagged_feed_excludes_day_without_excluding_other_house(self):
        complete, rejected = self.read_fixture(flagged=True)
        self.assertEqual({house for house, _ in complete}, {3})
        self.assertEqual(rejected["flagged_interpolation_hours"], 2)

    def test_cash_roi_does_not_charge_capital_wear_twice(self):
        rows = [{"house": "2", "target_day": f"2026-{month:02d}-01", "modules": 1,
                 "load_kwh": 10., "baseline_bill_ron": 100.,
                 "baseline_import_spend_ron": 100., "savings_after_wear_ron": 8.,
                 "cash_savings_ron": 10., "discharge_ac_kwh": 4.,
                 "equivalent_cycles": 1., "day_bill_reduction_pct": 8., "validated": True}
                for month in (1, 4, 7, 9)]
        result = summarise(rows)
        self.assertEqual(result["pooled_net_bill_reduction_pct"], 8.)
        roi = result["roi_projection"]
        self.assertEqual(roi["sample_season_extrapolated_annual_cash_savings_ron"], 3650.)
        self.assertAlmostEqual(roi["simple_payback_years"], (UNIT_COST_RON + INSTALL_RON) / 3550.)
        uneven_sample = rows + [dict(rows[0])] * 5
        uneven_sample += [{**row, "house": "3", "cash_savings_ron": 20.} for row in rows]
        self.assertEqual(summarise(uneven_sample)["roi_projection"]["sample_season_extrapolated_annual_cash_savings_ron"], 5475.)
        rows[0]["baseline_bill_ron"] = -1.
        self.assertIsNone(summarise(rows)["pooled_net_bill_reduction_pct"])


if __name__ == "__main__":
    unittest.main()
