"""Pure interval clearing. Future measured/forecast loads can use the same engine."""
from decimal import Decimal

from .models import MarketSettings, Participant


def clear_market(participants: list[Participant], settings: MarketSettings, interval_hours=0.25):
    d = lambda value: Decimal(str(value))
    hours = d(interval_hours)
    if not hours.is_finite() or hours <= 0:
        raise ValueError("Interval duration must be positive and finite.")
    buy, sell = d(settings.grid_buy), d(settings.grid_sell)
    fee, share = d(settings.transport_fee), d(settings.buyer_transport_share)
    price = sell + d(settings.price_weight) * (buy - sell)
    buyer_fee, seller_fee = fee * share, fee * (1 - share)
    buyer_rate, seller_rate = price + buyer_fee, price - seller_fee
    competitive = buyer_rate <= buy and seller_rate >= sell
    rows = []
    for member in participants:
        load = d(member.load_kw) * hours
        generation = d(member.solar_kwp) * d(settings.solar_yield_factor) * hours
        self_use = min(load, generation)
        rows.append({"member": member, "load": load, "generation": generation,
                     "self_use": self_use, "deficit": load - self_use, "surplus": generation - self_use})
    demand = sum((r["deficit"] for r in rows), Decimal(0))
    supply = sum((r["surplus"] for r in rows), Decimal(0))
    matched = min(demand, supply) if competitive else Decimal(0)
    ledger = []
    # ponytail: proportional allocation of one interval; add scheduling only with forecast/meter inputs.
    for row in rows:
        local_buy = matched * row["deficit"] / demand if demand else Decimal(0)
        local_sell = matched * row["surplus"] / supply if supply else Decimal(0)
        grid_import, grid_export = row["deficit"] - local_buy, row["surplus"] - local_sell
        benchmark = row["deficit"] * buy - row["surplus"] * sell
        optimized = grid_import * buy + local_buy * buyer_rate - grid_export * sell - local_sell * seller_rate
        ledger.append({**row["member"].model_dump(), "load_kwh": row["load"],
                       "generation_kwh": row["generation"], "self_consumed_kwh": row["self_use"],
                       "local_bought_kwh": local_buy, "local_sold_kwh": local_sell,
                       "grid_import_kwh": grid_import, "grid_export_kwh": grid_export,
                       "benchmark_bill": benchmark, "optimized_bill": optimized,
                       "benefit": benchmark - optimized,
                       "transport_paid": local_buy * buyer_fee + local_sell * seller_fee})
    total = lambda key: sum((row[key] for row in ledger), Decimal(0))
    result = {"settings": settings.model_dump(), "interval_minutes": float(hours * 60),
              "rates": {"clearing_price": price, "buyer_rate": buyer_rate, "seller_rate": seller_rate,
                        "buyer_transport_fee": buyer_fee, "seller_transport_fee": seller_fee},
              "trade_enabled": competitive,
              "trade_note": None if competitive else "Local trading is paused because these rates are worse than the grid for a buyer or seller.",
              "totals": {"load_kwh": total("load_kwh"), "generation_kwh": total("generation_kwh"),
                         "self_consumed_kwh": total("self_consumed_kwh"), "local_traded_kwh": matched,
                         "grid_import_kwh": demand - matched, "grid_export_kwh": supply - matched,
                         "benchmark_bill": total("benchmark_bill"), "optimized_bill": total("optimized_bill"),
                         "benefit": total("benefit"), "transport_collected": matched * fee,
                         "local_coverage": matched / demand if demand else Decimal(0)},
              "participants": ledger}

    def serialize(value):
        if isinstance(value, Decimal):
            return float(value.quantize(Decimal("0.000000001")))
        if isinstance(value, dict):
            return {key: serialize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [serialize(item) for item in value]
        return value

    return serialize(result)
