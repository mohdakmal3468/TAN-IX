"""
tools/inventory_model.py
------------------------
Predicts safety stock, reorder point and stock status from raw inputs, so
they no longer have to be typed into inventory records.

Inputs that stay in an inventory record:
    district, product, quantity, daily_burn_rate_pct (% of the warehouse capacity used per day)
Everything else is computed here from data/order_history.csv.
"""
import csv
import math
import os
import statistics
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER_HISTORY = os.path.join(ROOT, "data", "order_history.csv")

Z_SCORE = float(os.getenv("SERVICE_LEVEL_Z", "1.65"))   # 1.28=90%, 1.65=95%, 2.33=99%
SURPLUS_MULTIPLIER = 3.0                                # surplus if stock >= 3x reorder point
CRITICAL_DAYS_LEFT = 2.0

# Full warehouse capacity per product (same numbers as scripts/generate_sample_data.py).
# The burn-rate percentage is measured against this fixed number, so it stays
# correct after stock is transferred in or out.
PRODUCT_CAPACITY = {"shoes": 10000, "belts": 8000, "bags": 5000, "jackets": 3500}


@lru_cache(maxsize=1)
def demand_stats() -> dict:
    """Average and spread of daily demand + average lead time per (district, product)."""
    with open(ORDER_HISTORY, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("order_history.csv is empty, cannot predict safety stock")
    first = date.fromisoformat(min(r["date"] for r in rows))
    last = date.fromisoformat(max(r["date"] for r in rows))
    span = (last - first).days + 1

    groups = defaultdict(list)
    for r in rows:
        groups[(r["district"], r["product"])].append(r)

    stats = {}
    for key, items in groups.items():
        per_day = defaultdict(float)
        for r in items:
            per_day[r["date"]] += float(r["requested_quantity"])
        series = [per_day.get((first + timedelta(days=i)).isoformat(), 0.0) for i in range(span)]
        stats[key] = {
            "avg_daily": statistics.mean(series),
            "std_daily": statistics.pstdev(series),
            "lead_time_days": statistics.mean(float(r["lead_time_days"]) for r in items),
        }
    return stats


def _stats(district: str, product: str) -> dict:
    key = (district.capitalize().strip(), product.lower().strip())
    if key not in demand_stats():
        raise KeyError(f"No order history for {key}; cannot predict safety stock")
    return demand_stats()[key]


def predict_safety_stock(district: str, product: str) -> float:
    """Safety stock = Z x (std of daily demand) x sqrt(lead time in days)."""
    s = _stats(district, product)
    return round(Z_SCORE * s["std_daily"] * math.sqrt(s["lead_time_days"]), 0)


def predict_reorder_point(district: str, product: str) -> float:
    """Reorder point = demand during lead time + safety stock."""
    s = _stats(district, product)
    return round(s["avg_daily"] * s["lead_time_days"] + predict_safety_stock(district, product), 0)


def burn_units_per_day(product: str, burn_rate_pct: float) -> float:
    """Converts '% of capacity used per day' into units per day."""
    return PRODUCT_CAPACITY[product.lower().strip()] * float(burn_rate_pct) / 100.0


def days_left(product: str, quantity: float, burn_rate_pct: float) -> float:
    units = burn_units_per_day(product, burn_rate_pct)
    return round(float(quantity) / units, 1) if units > 0 else 999.0


def classify_status(district: str, product: str, quantity: float, burn_rate_pct: float) -> str:
    """CRITICAL_DEFICIT / LOW_STOCK / NORMAL / SURPLUS, predicted from the inputs only."""
    safety = predict_safety_stock(district, product)
    reorder = predict_reorder_point(district, product)
    runway = days_left(product, quantity, burn_rate_pct)
    if quantity <= safety or runway <= CRITICAL_DAYS_LEFT:
        return "CRITICAL_DEFICIT"
    if quantity <= reorder:
        return "LOW_STOCK"
    if quantity >= SURPLUS_MULTIPLIER * reorder:
        return "SURPLUS"
    return "NORMAL"


def enrich_record(rec: dict) -> dict:
    """Takes a raw record (district, product, quantity, daily_burn_rate_pct) and adds predictions."""
    d, p, q = rec["district"], rec["product"], float(rec["quantity"])
    if "daily_burn_rate_pct" in rec:
        pct = float(rec["daily_burn_rate_pct"])
    elif "daily_burn_rate" in rec:
        cap = PRODUCT_CAPACITY.get(p.lower().strip(), 10000)
        pct = (float(rec["daily_burn_rate"]) / cap) * 100.0
    else:
        pct = 1.0
    return {
        **rec,
        "daily_burn_rate_pct": round(pct, 2),
        "daily_burn_units": round(burn_units_per_day(p, pct), 1),
        "safety_stock": predict_safety_stock(d, p),
        "reorder_point": predict_reorder_point(d, p),
        "days_left": days_left(p, q, pct),
        "status": classify_status(d, p, q, pct),
    }


if __name__ == "__main__":
    import json
    inv = json.load(open(os.path.join(ROOT, "data", "inventory.json"), encoding="utf-8"))
    print(f"{'district':8} {'product':8} {'qty':>6} {'burn%':>6} {'safety':>7} {'reorder':>8} {'days':>6}  status")
    for r in inv:
        pct = r["daily_burn_rate"] / PRODUCT_CAPACITY[r["product"]] * 100   # one-time conversion of old data
        e = enrich_record({"district": r["district"], "product": r["product"],
                           "quantity": r["quantity"], "daily_burn_rate_pct": pct})
        print(f"{e['district']:8} {e['product']:8} {e['quantity']:6.0f} {pct:6.2f} "
              f"{e['safety_stock']:7.0f} {e['reorder_point']:8.0f} {e['days_left']:6.1f}  {e['status']}")