"""
Generates realistic order history data for BigQuery table: order_history
Tracks orders, fulfillment, lead times, and monthly stockout incidents for:
Kanpur, Unnao, Agra, Noida across shoes, belts, bags, jackets.
"""

import os
import csv
import random
from datetime import datetime, timedelta

random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DISTRICTS = ["Kanpur", "Unnao", "Agra", "Noida"]
PRODUCTS = ["shoes", "belts", "bags", "jackets"]

base_date = datetime(2026, 7, 1)
orders = []

for i in range(1, 151):
    order_id = f"ORD-2026-{i:04d}"
    order_date = base_date + timedelta(days=random.randint(0, 95))
    district = random.choice(DISTRICTS)
    product = random.choice(PRODUCTS)

    req_qty = random.randint(200, 1500)
    month = order_date.month

    # Intentional realistic stockout patterns:
    # Agra has frequent belt stockouts in August and September
    if district == "Agra" and product == "belts" and month in (8, 9, 10):
        is_stockout = True
        fulfilled_qty = int(req_qty * random.uniform(0.1, 0.45))
        severity = "CRITICAL" if fulfilled_qty < (req_qty * 0.3) else "HIGH"
        lead_time_days = random.randint(8, 16)
    # Noida has jacket shortages during pre-export rush in September
    elif district == "Noida" and product == "jackets" and month in (8, 9):
        is_stockout = random.random() < 0.6
        fulfilled_qty = int(req_qty * 0.6) if is_stockout else req_qty
        severity = "MEDIUM" if is_stockout else "NONE"
        lead_time_days = random.randint(6, 12) if is_stockout else random.randint(3, 5)
    else:
        # Standard fulfillment
        is_stockout = random.random() < 0.12  # baseline 12% stockout rate
        fulfilled_qty = int(req_qty * 0.75) if is_stockout else req_qty
        severity = "LOW" if is_stockout else "NONE"
        lead_time_days = random.randint(4, 7) if is_stockout else random.randint(2, 4)

    unit_price = {"shoes": 850, "belts": 340, "bags": 1600, "jackets": 3800}[product]
    order_value = req_qty * unit_price

    orders.append({
        "order_id": order_id,
        "date": order_date.strftime("%Y-%m-%d"),
        "district": district,
        "product": product,
        "requested_quantity": req_qty,
        "fulfilled_quantity": fulfilled_qty,
        "is_stockout": "TRUE" if is_stockout else "FALSE",
        "stockout_severity": severity,
        "lead_time_days": lead_time_days,
        "order_value_inr": order_value
    })

orders.sort(key=lambda x: x["date"])

output_file = os.path.join(DATA_DIR, "order_history.csv")
with open(output_file, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(orders[0].keys()))
    writer.writeheader()
    writer.writerows(orders)

print(f"[OK] Generated {len(orders)} order history records -> {output_file}")
