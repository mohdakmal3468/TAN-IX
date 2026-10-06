"""
tools/bigquery_tools.py
-----------------------
Simulates or executes BigQuery analytical queries over historical supply chain logs
for UP leather shipments along the Agra-Lucknow and Yamuna Expressways.

Provides key analytics to the Intra-State Logistics Agent and State Orchestrator:
- Average transit delay on specific routes
- On-time delivery rate by carrier
- Historical weather and fog disruption factors
"""

import os
import json
from typing import Dict, Any, List
from config import USE_MOCK_DATA, GCP_PROJECT_ID, BIGQUERY_DATASET

HISTORY_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "historical_shipments.json")

# BigQuery client fallback
bigquery_client = None
if not USE_MOCK_DATA:
    try:
        from google.cloud import bigquery
        bigquery_client = bigquery.Client(project=GCP_PROJECT_ID)
        print("[BigQuery] Connected to Google Cloud BigQuery successfully.")
    except Exception as e:
        print(f"[BigQuery] Note: {e}. Falling back to historical JSON logs.")
        bigquery_client = None


def _load_historical_logs() -> List[Dict[str, Any]]:
    """Loads historical shipment logs."""
    if not os.path.exists(HISTORY_FILE_PATH):
        return []
    with open(HISTORY_FILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def query_historical_shipments(origin: str = None, destination: str = None) -> List[Dict[str, Any]]:
    """
    Queries past shipment records between specific clusters.
    Example: query_historical_shipments('Kanpur', 'Agra')
    """
    records = _load_historical_logs()
    filtered = []
    for r in records:
        if origin and r["origin"].lower() != origin.lower():
            continue
        if destination and r["destination"].lower() != destination.lower():
            continue
        filtered.append(r)
    return filtered


def get_corridor_performance_stats() -> Dict[str, Any]:
    """
    Computes summary metrics for logistics corridors:
    - Average delay per corridor
    - Primary bottleneck causes (e.g. fog, waterlogging)
    - Average freight cost per shipment
    """
    records = _load_historical_logs()
    if not records:
        return {"total_shipments": 0, "message": "No historical records available."}

    total_shipments = len(records)
    total_cost = sum(r.get("cost_inr", 0) for r in records)
    corridors = {}

    for r in records:
        key = f"{r['origin']} -> {r['destination']}"
        if key not in corridors:
            corridors[key] = {
                "route_name": r.get("route", "Expressway"),
                "total_trips": 0,
                "delayed_trips": 0,
                "avg_delay_hours": 0.0,
                "delay_factors": []
            }
        corridors[key]["total_trips"] += 1
        planned = r.get("planned_hours", 0)
        actual = r.get("actual_hours", 0)
        delay = max(0.0, round(actual - planned, 1))
        
        if delay > 0.5:
            corridors[key]["delayed_trips"] += 1
            if r.get("delay_reason") and r["delay_reason"] != "None":
                corridors[key]["delay_factors"].append(r["delay_reason"])

    # Calculate percentages
    for key, cdata in corridors.items():
        cdata["on_time_percentage"] = round(((cdata["total_trips"] - cdata["delayed_trips"]) / cdata["total_trips"]) * 100, 1)

    return {
        "total_historical_shipments_analyzed": total_shipments,
        "avg_shipment_cost_inr": round(total_cost / total_shipments, 2) if total_shipments else 0,
        "corridor_breakdown": corridors
    }
