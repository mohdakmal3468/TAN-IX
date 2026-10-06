"""
scripts/simulate_events.py
--------------------------
Simulates real-world supply chain disruption and demand shock events by posting
to the TAN-IX FastAPI endpoints:
1. Blockade Event -> POST /disruption (Ganges Bridge / NH-27 flood blockade)
2. Demand-Spike Event -> POST /stock-update (Sudden surge in Agra shoes cutting stock)
3. Fog Restriction Event -> POST /disruption (Yamuna Expressway night fog speed cap)
4. Emergency Dispatch -> POST /shipment (Inter-district replenishment carrier order)

Supports both live HTTP requests (to running server) and in-process FastAPI TestClient!
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone

# Ensure project root is in path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from config import FASTAPI_HOST, FASTAPI_PORT
from api.main import app

BASE_URL = f"http://{FASTAPI_HOST}:{FASTAPI_PORT}"


def get_client():
    """
    Checks if FastAPI server is actively listening on BASE_URL.
    If yes, returns requests session. If no, falls back to in-process FastAPI TestClient.
    """
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=1.0)
        if resp.status_code == 200:
            print(f"[Transport] Connected to live running server at {BASE_URL}")
            return "live", None
    except Exception:
        pass

    # In-process TestClient fallback
    from fastapi.testclient import TestClient
    print(f"[Transport] Server not running on {BASE_URL}. Using in-process FastAPI TestClient.")
    return "testclient", TestClient(app)


def post_event(mode, client, endpoint, payload):
    """Sends POST request via selected transport mode."""
    if mode == "live":
        resp = requests.post(f"{BASE_URL}{endpoint}", json=payload)
        return resp.status_code, resp.json()
    else:
        resp = client.post(endpoint, json=payload)
        return resp.status_code, resp.json()


def get_data(mode, client, endpoint):
    """Sends GET request via selected transport mode."""
    if mode == "live":
        resp = requests.get(f"{BASE_URL}{endpoint}")
        return resp.status_code, resp.json()
    else:
        resp = client.get(endpoint)
        return resp.status_code, resp.json()


def main():
    print("=" * 70)
    print("TAN-IX Event Simulator: Injecting Fake Disruptions & Demand Spikes")
    print("=" * 70)

    mode, client = get_client()

    # --------------------------------------------------------------------------
    # 1. Health Check
    # --------------------------------------------------------------------------
    print("\n[Step 1] Verifying API Health (GET /health)...")
    status_code, data = get_data(mode, client, "/health")
    print(f"Status Code: {status_code} | Response: {data}")

    # --------------------------------------------------------------------------
    # 2. Blockade Disruption Event (POST /disruption)
    # --------------------------------------------------------------------------
    print("\n[Step 2] Sending Highway Blockade Event (POST /disruption)...")
    blockade_payload = {
        "event_id": f"EVT-SIM-{datetime.now().strftime('%H%M%S')}-BLOCKADE",
        "location": "Kanpur",
        "type": "WEATHER_FLOOD",
        "severity": "HIGH",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "title": "Severe Traffic & Flood Blockade at Jajmau Ganga Bridge (NH-27)",
        "description": "Rising Ganges water level combined with multi-axle truck mechanical failure created a complete freight standstill across Kanpur-Unnao corridor.",
        "impacted_clusters": ["Kanpur", "Unnao", "Agra"],
        "status": "ACTIVE"
    }
    status_code, data = post_event(mode, client, "/disruption", blockade_payload)
    print(f"Status Code: {status_code}")
    print(f"Response   : {json.dumps(data, indent=2)}")

    # --------------------------------------------------------------------------
    # 3. Demand-Spike Stock Shock (POST /stock-update)
    # --------------------------------------------------------------------------
    print("\n[Step 3] Sending Demand-Spike Stock Shock in Agra (POST /stock-update)...")
    stock_payload = {
        "inventory_id": "INV-AGR-SHO-SHOCK",
        "district": "Agra",
        "product": "shoes",
        "quantity": 280.0,  # Sudden crash from 2000 due to massive export surge
        "unit": "pairs",
        "daily_burn_rate": 450.0,
        "reorder_point": 2000.0,
        "safety_stock": 600.0,
        "unit_cost_inr": 850.0,
        "status": "CRITICAL_DEFICIT",
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    status_code, data = post_event(mode, client, "/stock-update", stock_payload)
    print(f"Status Code: {status_code}")
    print(f"Response   : {json.dumps(data, indent=2)}")

    # --------------------------------------------------------------------------
    # 4. Dense Fog Expressway Disruption (POST /disruption)
    # --------------------------------------------------------------------------
    print("\n[Step 4] Sending Expressway Fog Hazard Event (POST /disruption)...")
    fog_payload = {
        "event_id": f"EVT-SIM-{datetime.now().strftime('%H%M%S')}-FOG",
        "location": "Agra",
        "type": "EXPRESSWAY_FOG",
        "severity": "HIGH",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "title": "Dense Winter Fog Night Speed Restrictions on Yamuna Expressway",
        "description": "Visibility below 30m; night heavy freight speed restricted to 40 km/h with mandatory pilot escorts.",
        "impacted_clusters": ["Agra", "Noida"],
        "status": "ACTIVE"
    }
    status_code, data = post_event(mode, client, "/disruption", fog_payload)
    print(f"Status Code: {status_code}")
    print(f"Response   : {json.dumps(data, indent=2)}")

    # --------------------------------------------------------------------------
    # 5. Emergency Inter-District Shipment (POST /shipment)
    # --------------------------------------------------------------------------
    print("\n[Step 5] Creating Emergency Inter-District Shipment (POST /shipment)...")
    shipment_payload = {
        "shipment_id": f"SHP-SIM-{datetime.now().strftime('%H%M%S')}",
        "origin": "Kanpur",
        "destination": "Agra",
        "carrier": "UP State Freight Express",
        "route": "Agra-Lucknow Expressway & NH-19",
        "cost": 19323.0,
        "status": "DISPATCHED",
        "product": "belts",
        "quantity": 1020.0,
        "unit": "units",
        "vehicle_type": "Eicher Pro (9 Ton)",
        "planned_transit_hours": 4.5,
        "actual_transit_hours": None,
        "departure_time": datetime.now(timezone.utc).isoformat()
    }
    status_code, data = post_event(mode, client, "/shipment", shipment_payload)
    print(f"Status Code: {status_code}")
    print(f"Response   : {json.dumps(data, indent=2)}")

    # --------------------------------------------------------------------------
    # 6. Verify District Inventory Endpoint (GET /inventory/Agra)
    # --------------------------------------------------------------------------
    print("\n[Step 6] Inspecting Updated Inventory (GET /inventory/Agra)...")
    status_code, data = get_data(mode, client, "/inventory/Agra")
    print(f"Status Code: {status_code}")
    print(f"Record Count: {data.get('record_count')}")
    for item in data.get("inventory", [])[:4]:
        print(f"  • {item.get('product')}: {item.get('quantity')} {item.get('unit')} (Status: {item.get('status')})")

    print("\n" + "=" * 70)
    print("[SUCCESS] All simulated disruption and demand-spike events processed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
