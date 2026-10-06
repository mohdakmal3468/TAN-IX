"""
scripts/generate_sample_data.py
-------------------------------
Generates realistic domain-specific sample data for TAN-IX:
1. 4 UP Districts: Kanpur, Unnao, Agra, Noida
2. 4 Leather Products per District: shoes, belts, bags, jackets
   - Deliberate imbalance: Agra has CRITICAL DEFICIT of belts; Kanpur has SURPLUS of belts!
3. 4 Carriers: with varying cost, speed, and reliability profiles
4. 12 Directed Route Lanes: connecting all 4 districts across UP expressways
5. 12 Regional Disruption Events: environmental, flood, and expressway incidents
6. 200 Historical Transit Logs: saved as both JSON and CSV for BigQuery simulation
"""

import os
import json
import csv
import random
from datetime import datetime, timedelta, timezone

# Set fixed seed for consistent reproducibility
random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# 1. DISTRICTS & INVENTORY DATA
# ------------------------------------------------------------------------------
DISTRICTS = ["Kanpur", "Unnao", "Agra", "Noida"]
PRODUCTS = ["shoes", "belts", "bags", "jackets"]

PRODUCT_METRICS = {
    "shoes": {"unit": "pairs", "unit_cost_inr": 850, "burn_rate_base": 120, "reorder_base": 1500, "capacity": 10000},
    "belts": {"unit": "units", "unit_cost_inr": 340, "burn_rate_base": 140, "reorder_base": 1200, "capacity": 8000},
    "bags": {"unit": "units", "unit_cost_inr": 1600, "burn_rate_base": 75, "reorder_base": 800, "capacity": 5000},
    "jackets": {"unit": "garments", "unit_cost_inr": 3800, "burn_rate_base": 40, "reorder_base": 500, "capacity": 3500}
}

# ------------------------------------------------------------------------------
# 2. CARRIERS (4 Profiles with distinct trade-offs)
# ------------------------------------------------------------------------------
CARRIERS = [
    {
        "carrier_id": "CAR-01",
        "name": "Yamuna Fast Haulers",
        "speed_kmh": 70,
        "base_rate_per_km_inr": 54.0,
        "reliability_pct": 96.0,
        "fleet_type": "Express Container Fleet",
        "primary_corridor": "Yamuna Expressway",
        "tier": "Premium Fast"
    },
    {
        "carrier_id": "CAR-02",
        "name": "UP State Freight Express",
        "speed_kmh": 55,
        "base_rate_per_km_inr": 42.0,
        "reliability_pct": 92.5,
        "fleet_type": "Eicher Pro (9 Ton)",
        "primary_corridor": "Agra-Lucknow Expressway & NH-19",
        "tier": "Standard Reliable"
    },
    {
        "carrier_id": "CAR-03",
        "name": "Awadh Inter-District Fleet",
        "speed_kmh": 46,
        "base_rate_per_km_inr": 34.0,
        "reliability_pct": 84.0,
        "fleet_type": "Tata 407 (3.5 Ton)",
        "primary_corridor": "NH-27 & Regional Highways",
        "tier": "Economy"
    },
    {
        "carrier_id": "CAR-04",
        "name": "Ganga Basin Cargo Logistics",
        "speed_kmh": 40,
        "base_rate_per_km_inr": 28.0,
        "reliability_pct": 77.0,
        "fleet_type": "Multi-Axle Heavy Haulers",
        "primary_corridor": "Old GT Road / NH-19",
        "tier": "Budget Bulk"
    }
]

# ------------------------------------------------------------------------------
# 3. 12 DIRECTED ROUTE LANES (4 x 3 = 12 Lanes)
# ------------------------------------------------------------------------------
ROUTE_MATRIX = {
    ("Kanpur", "Unnao"): {"distance_km": 25, "transit_hours": 0.8, "route_name": "NH-27 / Ganga Bridge Corridor", "toll_inr": 80},
    ("Unnao", "Kanpur"): {"distance_km": 25, "transit_hours": 0.8, "route_name": "NH-27 / Ganga Bridge Corridor", "toll_inr": 80},
    ("Kanpur", "Agra"): {"distance_km": 285, "transit_hours": 4.5, "route_name": "Agra-Lucknow Expressway & NH-19", "toll_inr": 780},
    ("Agra", "Kanpur"): {"distance_km": 285, "transit_hours": 4.5, "route_name": "Agra-Lucknow Expressway & NH-19", "toll_inr": 780},
    ("Kanpur", "Noida"): {"distance_km": 465, "transit_hours": 6.8, "route_name": "Agra-Lucknow Expway + Yamuna Expway", "toll_inr": 1350},
    ("Noida", "Kanpur"): {"distance_km": 465, "transit_hours": 6.8, "route_name": "Yamuna Expway + Agra-Lucknow Expway", "toll_inr": 1350},
    ("Unnao", "Agra"): {"distance_km": 290, "transit_hours": 4.6, "route_name": "Agra-Lucknow Expressway", "toll_inr": 810},
    ("Agra", "Unnao"): {"distance_km": 290, "transit_hours": 4.6, "route_name": "Agra-Lucknow Expressway", "toll_inr": 810},
    ("Unnao", "Noida"): {"distance_km": 475, "transit_hours": 7.0, "route_name": "Agra-Lucknow Expway + Yamuna Expway", "toll_inr": 1390},
    ("Noida", "Unnao"): {"distance_km": 475, "transit_hours": 7.0, "route_name": "Yamuna Expway + Agra-Lucknow Expway", "toll_inr": 1390},
    ("Agra", "Noida"): {"distance_km": 195, "transit_hours": 2.5, "route_name": "Yamuna Expressway", "toll_inr": 590},
    ("Noida", "Agra"): {"distance_km": 195, "transit_hours": 2.5, "route_name": "Yamuna Expressway", "toll_inr": 590}
}

# ------------------------------------------------------------------------------
# 4. 12 DISRUPTION EVENTS (Realistic Regional Hazards)
# ------------------------------------------------------------------------------
DISRUPTIONS = [
    # Kanpur
    {
        "event_id": "EVT-KNP-01",
        "location": "Kanpur (Jajmau)",
        "type": "REGULATORY_NGT",
        "severity": "HIGH",
        "timestamp": "2026-10-06T09:30:00Z",
        "title": "UPPCB & NGT Effluent Inspection Shutdown Notice",
        "description": "Statutory inspection ordered for 14 tanning units along Jajmau PETP; 48-hour output reduction enforced.",
        "impacted_clusters": ["Kanpur", "Agra"],
        "status": "ACTIVE"
    },
    {
        "event_id": "EVT-KNP-02",
        "location": "Kanpur (Shuklaganj)",
        "type": "WEATHER_FLOOD",
        "severity": "HIGH",
        "timestamp": "2026-10-05T14:15:00Z",
        "title": "Ganges River Basin High Water Discharge Warning",
        "description": "Narora Barrage discharge causing localized waterlogging on access ramps to Jajmau Ganga Bridge.",
        "impacted_clusters": ["Kanpur", "Unnao"],
        "status": "MONITORING"
    },
    {
        "event_id": "EVT-KNP-03",
        "location": "Kanpur (Chakeri)",
        "type": "RAW_MATERIAL_SPIKE",
        "severity": "MEDIUM",
        "timestamp": "2026-10-04T11:00:00Z",
        "title": "Chrome Tanning Chemical Shortage",
        "description": "Import consignments delayed at Nhava Sheva port, driving local chrome tanning salts up by 18%.",
        "impacted_clusters": ["Kanpur"],
        "status": "ACTIVE"
    },
    # Unnao
    {
        "event_id": "EVT-UNO-01",
        "location": "Unnao (Banthar)",
        "type": "REGULATORY_NGT",
        "severity": "MEDIUM",
        "timestamp": "2026-10-03T16:20:00Z",
        "title": "UPSIDC CETP Bio-Filter Maintenance",
        "description": "Planned maintenance of primary biological treatment line limiting wet-blue tanning capacity.",
        "impacted_clusters": ["Unnao"],
        "status": "MONITORING"
    },
    {
        "event_id": "EVT-UNO-02",
        "location": "Unnao (NH-27 Junction)",
        "type": "LABOR_STRIKE",
        "severity": "HIGH",
        "timestamp": "2026-10-02T08:00:00Z",
        "title": "Local Commercial Transporters Union Strike",
        "description": "Toll protest near Banthar toll plaza temporarily halting outward short-haul truck dispatches.",
        "impacted_clusters": ["Unnao", "Kanpur"],
        "status": "RESOLVED"
    },
    {
        "event_id": "EVT-UNO-03",
        "location": "Unnao (Industrial Area)",
        "type": "WEATHER_FLOOD",
        "severity": "MEDIUM",
        "timestamp": "2026-10-01T12:00:00Z",
        "title": "Monsoon Inundation in Lowland Tanneries",
        "description": "Drainage overflow after 78mm torrential downpour delayed raw buffalo hide drying processes.",
        "impacted_clusters": ["Unnao"],
        "status": "RESOLVED"
    },
    # Agra
    {
        "event_id": "EVT-AGR-01",
        "location": "Agra (Yamuna Expressway Entry)",
        "type": "EXPRESSWAY_FOG",
        "severity": "HIGH",
        "timestamp": "2026-10-06T04:00:00Z",
        "title": "Dense Winter Fog Night Speed Restrictions",
        "description": "Visibility below 40m between Agra Mile 20 and Jewar; commercial freight transit capped at 50 km/h.",
        "impacted_clusters": ["Agra", "Noida"],
        "status": "ACTIVE"
    },
    {
        "event_id": "EVT-AGR-02",
        "location": "Agra (Sikandra)",
        "type": "RAW_MATERIAL_SPIKE",
        "severity": "HIGH",
        "timestamp": "2026-10-05T10:30:00Z",
        "title": "Footwear Belt & Upper Raw Component Shortage",
        "description": "Severe deficit of finished belt leather stock in Sikandra manufacturing clusters halting finishing lines.",
        "impacted_clusters": ["Agra"],
        "status": "ACTIVE"
    },
    {
        "event_id": "EVT-AGR-03",
        "location": "Agra (Hing Ki Mandi)",
        "type": "LABOR_STRIKE",
        "severity": "MEDIUM",
        "timestamp": "2026-09-28T13:45:00Z",
        "title": "Footwear Artisan Association Meeting Halt",
        "description": "Half-day operational stoppage over state electricity tariff revisions.",
        "impacted_clusters": ["Agra"],
        "status": "RESOLVED"
    },
    # Noida
    {
        "event_id": "EVT-NOI-01",
        "location": "Noida (Sector 63)",
        "type": "RAW_MATERIAL_SPIKE",
        "severity": "HIGH",
        "timestamp": "2026-10-06T08:15:00Z",
        "title": "Export Nappa Leather Pre-Christmas Crunch",
        "description": "Surge in European purchase orders for designer leather jackets creates acute deficit in premium nappa.",
        "impacted_clusters": ["Noida"],
        "status": "ACTIVE"
    },
    {
        "event_id": "EVT-NOI-02",
        "location": "Noida (Pari Chowk / Yamuna Expressway)",
        "type": "EXPRESSWAY_FOG",
        "severity": "MEDIUM",
        "timestamp": "2026-10-04T05:30:00Z",
        "title": "Freight Convoy Congestion at Jewar Toll Plaza",
        "description": "RFID tag scanner glitch caused 4 km commercial vehicle queue, adding 2.1 hours to transit time.",
        "impacted_clusters": ["Noida", "Agra"],
        "status": "RESOLVED"
    },
    {
        "event_id": "EVT-NOI-03",
        "location": "Noida (Air Cargo Terminal Link)",
        "type": "REGULATORY_NGT",
        "severity": "MEDIUM",
        "timestamp": "2026-10-02T15:00:00Z",
        "title": "GRAP Stage-III Diesel Truck Entry Restrictions in NCR",
        "description": "Commission for Air Quality Management (CAQM) restricted non-BS6 medium commercial trucks into Noida.",
        "impacted_clusters": ["Noida"],
        "status": "ACTIVE"
    }
]


def generate_inventory_data():
    """Generates inventory for all 4 districts with deliberate belt deficit in Agra and surplus in Kanpur."""
    inventory_records = []
    seed_clusters = {}

    for district in DISTRICTS:
        seed_clusters[district] = {
            "warehouse_id": f"WH-{district[:3].upper()}-01",
            "cluster_name": f"{district} Leather Hub",
            "location": f"Industrial Area, {district}",
            "status": "Operational",
            "last_updated": "2026-10-06T12:00:00Z",
            "inventory": {}
        }

        for product in PRODUCTS:
            metrics = PRODUCT_METRICS[product]
            burn_rate = metrics["burn_rate_base"] + random.randint(-15, 20)
            reorder = metrics["reorder_base"]
            safety = int(reorder * 0.35)
            cost = metrics["unit_cost_inr"]
            capacity = metrics["capacity"]

            # Deliberate specific imbalances requested by user:
            if district == "Agra" and product == "belts":
                # CRITICAL DEFICIT
                quantity = 180  # Far below reorder point of 1,200!
                status = "Critical Low"
                pydantic_status = "CRITICAL_DEFICIT"
            elif district == "Kanpur" and product == "belts":
                # HEALTHY SURPLUS
                quantity = 6800  # High buffer available to replenish Agra!
                status = "Surplus"
                pydantic_status = "SURPLUS"
            elif district == "Noida" and product == "jackets":
                # Low stock on export jackets
                quantity = int(reorder * 0.65)
                status = "Low Stock"
                pydantic_status = "LOW_STOCK"
            elif district == "Unnao" and product == "shoes":
                # Unnao mostly does raw/intermediate, shoe stock is nominal
                quantity = int(reorder * 1.1)
                status = "Normal"
                pydantic_status = "NORMAL"
            else:
                # Normal nominal inventory
                quantity = int(reorder * random.uniform(1.2, 2.2))
                status = "Normal"
                pydantic_status = "NORMAL"

            inv_id = f"INV-{district[:3].upper()}-{product[:3].upper()}"

            # Pydantic model record
            inventory_records.append({
                "inventory_id": inv_id,
                "district": district,
                "product": product,
                "quantity": quantity,
                "unit": metrics["unit"],
                "daily_burn_rate": float(burn_rate),
                "reorder_point": float(reorder),
                "safety_stock": float(safety),
                "unit_cost_inr": float(cost),
                "status": pydantic_status,
                "last_updated": datetime.now(timezone.utc).isoformat()
            })

            # Also prepare seed_inventory.json structure
            seed_clusters[district]["inventory"][product] = {
                "quantity": quantity,
                "unit": metrics["unit"],
                "min_threshold": reorder,
                "capacity": capacity,
                "unit_cost_inr": cost,
                "daily_burn_rate": burn_rate,
                "status": status
            }

    # Save data/inventory.json
    inv_file = os.path.join(DATA_DIR, "inventory.json")
    with open(inv_file, "w", encoding="utf-8") as f:
        json.dump(inventory_records, f, indent=2)

    # Also update data/seed_inventory.json so current agents & dashboard immediately recognize the new items
    seed_file = os.path.join(DATA_DIR, "seed_inventory.json")
    with open(seed_file, "w", encoding="utf-8") as f:
        json.dump({"clusters": seed_clusters}, f, indent=2)

    print(f"[OK] Generated {len(inventory_records)} inventory records -> {inv_file} & seed_inventory.json")
    return inventory_records


def generate_routes_and_carriers():
    """Saves the 12 route lanes and 4 carrier profiles."""
    carriers_file = os.path.join(DATA_DIR, "carriers.json")
    with open(carriers_file, "w", encoding="utf-8") as f:
        json.dump(CARRIERS, f, indent=2)
    print(f"[OK] Generated 4 carrier profiles -> {carriers_file}")

    routes_list = []
    route_idx = 1
    for (origin, dest), rdata in ROUTE_MATRIX.items():
        routes_list.append({
            "lane_id": f"LANE-{route_idx:02d}",
            "origin": origin,
            "destination": dest,
            "route_name": rdata["route_name"],
            "distance_km": rdata["distance_km"],
            "standard_transit_hours": rdata["transit_hours"],
            "base_toll_inr": rdata["toll_inr"]
        })
        route_idx += 1

    routes_file = os.path.join(DATA_DIR, "routes.json")
    with open(routes_file, "w", encoding="utf-8") as f:
        json.dump(routes_list, f, indent=2)
    print(f"[OK] Generated 12 route lanes -> {routes_file}")
    return routes_list


def generate_disruptions():
    """Saves the 12 regional disruption events."""
    disruptions_file = os.path.join(DATA_DIR, "disruptions.json")
    with open(disruptions_file, "w", encoding="utf-8") as f:
        json.dump(DISRUPTIONS, f, indent=2)
    print(f"[OK] Generated 12 disruption events -> {disruptions_file}")


def generate_historical_shipments(num_records=200):
    """Generates 200 realistic historical transit logs across all routes, saved as JSON and CSV."""
    lanes = list(ROUTE_MATRIX.keys())
    base_date = datetime(2026, 7, 1)  # Recent 3 months
    records = []

    for i in range(1, num_records + 1):
        shipment_id = f"SHP-2026-{i:04d}"
        origin, destination = random.choice(lanes)
        lane_info = ROUTE_MATRIX[(origin, destination)]
        carrier = random.choice(CARRIERS)
        product = random.choice(PRODUCTS)
        unit = PRODUCT_METRICS[product]["unit"]
        quantity = random.randint(300, 2500)

        # Scheduled transit time based on distance and carrier speed
        planned_hours = round(lane_info["distance_km"] / carrier["speed_kmh"], 1)

        # Weather & Delay probability based on carrier reliability and random factors
        rand_val = random.random() * 100
        weather = random.choices(["Clear", "Rain / Monsoon", "Foggy / Mist", "Overcast"], weights=[65, 18, 12, 5])[0]

        delay_reason = "None"
        delay_hours = 0.0

        if rand_val > carrier["reliability_pct"]:
            # Delayed trip
            if weather in ("Rain / Monsoon", "Foggy / Mist"):
                delay_hours = round(random.uniform(0.8, 3.5), 1)
                delay_reason = f"Adverse weather ({weather}) on {lane_info['route_name']}"
            elif "Ganga Bridge" in lane_info["route_name"]:
                delay_hours = round(random.uniform(0.5, 2.2), 1)
                delay_reason = "Heavy local freight congestion near Ganga bridge"
            else:
                delay_hours = round(random.uniform(0.5, 1.8), 1)
                delay_reason = "Toll plaza congestion or vehicle mechanical check"

        actual_hours = round(planned_hours + delay_hours, 1)

        # Freight Cost calculation: distance * carrier rate + tolls + minor random fuel variance
        freight_cost = int(lane_info["distance_km"] * carrier["base_rate_per_km_inr"] + lane_info["toll_inr"] + random.randint(100, 800))

        # Date distribution over past 90 days
        shipment_date = base_date + timedelta(days=random.randint(0, 95), hours=random.randint(6, 20))

        rec = {
            "shipment_id": shipment_id,
            "date": shipment_date.strftime("%Y-%m-%d"),
            "origin": origin,
            "destination": destination,
            "carrier": carrier["name"],
            "route": lane_info["route_name"],
            "product": product,
            "quantity": quantity,
            "unit": unit,
            "distance_km": lane_info["distance_km"],
            "planned_hours": planned_hours,
            "actual_hours": actual_hours,
            "delay_hours": delay_hours,
            "cost_inr": freight_cost,
            "weather_condition": weather,
            "delay_reason": delay_reason,
            "status": "Delivered" if delay_hours < 4.0 else "Delivered with Delay"
        }
        records.append(rec)

    # Sort chronologically
    records.sort(key=lambda x: x["date"])

    # 1. Save JSON
    json_path = os.path.join(DATA_DIR, "historical_shipments.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    # 2. Save CSV
    csv_path = os.path.join(DATA_DIR, "historical_shipments.csv")
    fieldnames = list(records[0].keys())
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"[OK] Generated {len(records)} historical shipment records -> {json_path} & {csv_path}")


def main():
    print("=" * 60)
    print("Generating Realistic Sample Data for TAN-IX")
    print("Districts: Kanpur, Unnao, Agra, Noida")
    print("Products : shoes, belts, bags, jackets")
    print("Target   : Agra low on belts; Kanpur surplus on belts")
    print("=" * 60)

    generate_inventory_data()
    generate_routes_and_carriers()
    generate_disruptions()
    generate_historical_shipments(200)

    print("=" * 60)
    print("[SUCCESS] All sample datasets generated successfully in data/")
    print("=" * 60)


if __name__ == "__main__":
    main()
