"""Run with: python -m unittest discover -s backend -v"""
import random
import unittest

from app.engine import clear_market
from app.models import MarketSettings, Participant


def member(id, load, solar=0):
    return Participant(id=id, name=id * 2, type="prosumer" if solar else "consumer", load_kw=load, solar_kwp=solar)


class PrototypeChecks(unittest.TestCase):
    def test_example_prices_and_transport_accounting(self):
        result = clear_market([member("s", 1, 5), member("b", 2)], MarketSettings(solar_yield_factor=1))
        self.assertAlmostEqual(result["rates"]["clearing_price"], .212)
        self.assertAlmostEqual(result["rates"]["seller_rate"], .2045)
        self.assertAlmostEqual(result["rates"]["buyer_rate"], .2195)
        self.assertAlmostEqual(result["totals"]["local_traded_kwh"], .5)
        self.assertAlmostEqual(result["totals"]["benefit"], .1025)
        self.assertAlmostEqual(result["totals"]["transport_collected"], .0075)
        for share in (0, .5, 1):
            rates = clear_market([], MarketSettings(buyer_transport_share=share))["rates"]
            self.assertAlmostEqual(rates["buyer_rate"] - rates["seller_rate"], .015)

    def test_conservation_and_no_member_loses_money(self):
        rng = random.Random(7)
        for _ in range(60):
            participants = [member(str(index), rng.uniform(0, 10), rng.uniform(0, 15) if index % 2 else 0) for index in range(8)]
            result = clear_market(participants, MarketSettings(price_weight=rng.random(), buyer_transport_share=rng.random()))
            totals, rows = result["totals"], result["participants"]
            self.assertAlmostEqual(sum(r["local_bought_kwh"] for r in rows), totals["local_traded_kwh"], places=7)
            self.assertAlmostEqual(sum(r["local_sold_kwh"] for r in rows), totals["local_traded_kwh"], places=7)
            self.assertAlmostEqual(totals["generation_kwh"] + totals["grid_import_kwh"], totals["load_kwh"] + totals["grid_export_kwh"], places=7)
            self.assertAlmostEqual(sum(r["transport_paid"] for r in rows), totals["transport_collected"], places=7)
            self.assertAlmostEqual(totals["benchmark_bill"] - totals["optimized_bill"], totals["benefit"], places=7)
            self.assertTrue(all(r["benefit"] >= -1e-8 for r in rows))

    def test_empty_night_and_uncompetitive_market(self):
        self.assertEqual(clear_market([], MarketSettings())["totals"]["benefit"], 0)
        participants = [member("s", 1, 5), member("b", 2)]
        night = clear_market(participants, MarketSettings(solar_yield_factor=0))
        self.assertEqual(night["totals"]["local_traded_kwh"], 0)
        self.assertEqual(night["totals"]["grid_import_kwh"], .75)
        paused = clear_market(participants, MarketSettings(transport_fee=1))
        self.assertFalse(paused["trade_enabled"])
        self.assertEqual(paused["totals"]["benefit"], 0)
        with self.assertRaises(ValueError):
            clear_market([], MarketSettings(), interval_hours=0)


if __name__ == "__main__":
    unittest.main()
