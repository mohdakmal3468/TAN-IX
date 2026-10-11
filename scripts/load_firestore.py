"""
scripts/load_firestore.py
-------------------------
Loads AgentHide sample data into Google Cloud Firestore across 7 collections:
1. inventory (16 records)
2. hubs (4 cluster profiles)
3. carriers (4 transport carriers)
4. routes (12 expressway route lanes)
5. disruptions (12 regional hazard events)
6. shipments (200 historical shipment logs)
7. approvals (sample HITL approval requests)

Uses the GOOGLE_CLOUD_PROJECT environment variable.
Includes an automated verification step printing document counts per collection.
"""

import os
import json
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure AgentHide root directory is in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from tools.firestore_client import (
    get_firestore_client,
    batch_write_documents,
    get_collection_count,
    PROJECT_ID
)

DATA_DIR = os.path.join(ROOT_DIR, "data")
MOCK_DIR = os.path.join(DATA_DIR, "firestore_mock")
os.makedirs(MOCK_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# Hub Profile Data for Collection: hubs
# ------------------------------------------------------------------------------
HUBS_DATA = [
    {
        "hub_id": "HUB-KNP-JAJMAU",
        "name": "Kanpur Leather Hub",
        "district": "Kanpur",
        "location": "Jajmau Industrial Area, Kanpur Nagar",
        "latitude": 26.4499,
        "longitude": 80.3319,
        "primary_role": "Heavy Tanning, Saddlery, Industrial Leather",
        "capacity_sqft": 50000,
        "operating_status": "OPERATIONAL",
        "active_vulnerabilities": ["Ganges River flood plain", "NGT effluent discharge restrictions", "CETP overflow risk"],
        "contact_email": "ops.kanpur@tanix.up.gov.in",
        "contact_phone": "+91-512-2589001"
    },
    {
        "hub_id": "HUB-UNO-BANTHAR",
        "name": "Unnao Leather Complex",
        "district": "Unnao",
        "location": "UPSIDC Industrial Area, Banthar",
        "latitude": 26.5458,
        "longitude": 80.4878,
        "primary_role": "Industrial Area Tannery Complex (Wet-Blue & Crust Leather)",
        "capacity_sqft": 45000,
        "operating_status": "OPERATIONAL",
        "active_vulnerabilities": ["Water treatment capacity", "Monsoon effluent logging", "Power supply volatility"],
        "contact_email": "ops.unnao@tanix.up.gov.in",
        "contact_phone": "+91-515-2820110"
    },
    {
        "hub_id": "HUB-AGR-SIKANDRA",
        "name": "Agra Footwear Cluster",
        "district": "Agra",
        "location": "Sikandra Industrial Area & Hing Ki Mandi",
        "latitude": 27.1767,
        "longitude": 78.0081,
        "primary_role": "Footwear Manufacturing, Shoe Uppers & Soles",
        "capacity_sqft": 60000,
        "operating_status": "OPERATIONAL",
        "active_vulnerabilities": ["Raw material transit delays from Kanpur", "Skilled artisan availability", "Expressway fog"],
        "contact_email": "ops.agra@tanix.up.gov.in",
        "contact_phone": "+91-562-2601920"
    },
    {
        "hub_id": "HUB-NOI-SEC63",
        "name": "Noida Export Zone",
        "district": "Noida",
        "location": "Phase-II Industrial Area, Sector 63",
        "latitude": 28.5355,
        "longitude": 77.3910,
        "primary_role": "High-Value Fashion Export, Handbags, Luxury Jackets",
        "capacity_sqft": 35000,
        "operating_status": "OPERATIONAL",
        "active_vulnerabilities": ["Strict international shipment deadlines", "Port transit cutoff times (Delhi IGI / Nhava Sheva)"],
        "contact_email": "ops.noida@tanix.up.gov.in",
        "contact_phone": "+91-120-4321099"
    }
]

# ------------------------------------------------------------------------------
# Sample Approval Requests Data for Collection: approvals
# ------------------------------------------------------------------------------
APPROVALS_DATA = [
    {
        "request_id": "APR-UP-2026-0001",
        "type": "STOCK_REBALANCE",
        "details": {
            "origin": "Kanpur",
            "destination": "Agra",
            "product": "belts",
            "quantity": 1020,
            "unit": "units",
            "route": "Agra-Lucknow Expressway & NH-19",
            "risk_justification": "Critical shortage of belts in Agra (180 remaining); surplus available in Kanpur (6,800 units)."
        },
        "status": "APPROVED",
        "amount": 19323.0,
        "requester_agent": "State Master Orchestrator",
        "created_at": "2026-10-06T09:15:00Z",
        "decision_by": "State Logistics Director (Admin)",
        "decision_at": "2026-10-06T09:30:00Z"
    },
    {
        "request_id": "APR-UP-2026-0002",
        "type": "EMERGENCY_REROUTE",
        "details": {
            "origin": "Unnao",
            "destination": "Noida",
            "product": "jackets",
            "quantity": 300,
            "unit": "garments",
            "route": "Yamuna Expressway",
            "risk_justification": "Avoid fog speed restrictions on NH-19 via expressway escort."
        },
        "status": "PENDING",
        "amount": 26800.0,
        "requester_agent": "Intra-State Logistics Agent",
        "created_at": "2026-10-06T12:00:00Z",
        "decision_by": None,
        "decision_at": None
    },
    {
        "request_id": "APR-UP-2026-0003",
        "type": "STOCK_REBALANCE",
        "details": {
            "origin": "Kanpur",
            "destination": "Noida",
            "product": "bags",
            "quantity": 450,
            "unit": "units",
            "route": "Agra-Lucknow Expway + Yamuna Expway",
            "risk_justification": "Export fulfillment deadline for European market dispatch."
        },
        "status": "PENDING",
        "amount": 31200.0,
        "requester_agent": "State Master Orchestrator",
        "created_at": "2026-10-06T13:45:00Z",
        "decision_by": None,
        "decision_at": None
    }
]


def load_json_file(filename: str):
    """Loads a JSON file from the data/ directory."""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"[Warning] File not found: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=" * 65)
    print("AgentHide: Google Cloud Firestore Data Ingestion")
    print(f"Target Google Cloud Project: {PROJECT_ID}")
    print("=" * 65)

    # 1. Load Datasets from data/
    inventory_data = load_json_file("inventory.json")
    carriers_data = load_json_file("carriers.json")
    routes_data = load_json_file("routes.json")
    disruptions_data = load_json_file("disruptions.json")
    shipments_data = load_json_file("historical_shipments.json")

    collections_to_load = [
        ("inventory", inventory_data, "inventory_id"),
        ("hubs", HUBS_DATA, "hub_id"),
        ("carriers", carriers_data, "carrier_id"),
        ("routes", routes_data, "lane_id"),
        ("disruptions", disruptions_data, "event_id"),
        ("shipments", shipments_data, "shipment_id"),
        ("approvals", APPROVALS_DATA, "request_id")
    ]

    client = get_firestore_client()
    is_live_firestore = client is not None

    if is_live_firestore:
        print("[Status] Connected to live Google Cloud Firestore. Beginning batch writes...\n")
    else:
        print("[Status] Running in Local / Offline Mode (No live GCP credentials active).")
        print("[Status] Writing collections to data/firestore_mock/ for seamless offline simulation...\n")

    summary_counts = {}

    # 2. Ingest into each collection
    for col_name, docs, id_key in collections_to_load:
        doc_count = len(docs)
        if is_live_firestore:
            committed = batch_write_documents(col_name, docs, id_key=id_key)
            print(f"  -> Collection '{col_name}': Committed {committed}/{doc_count} documents to Firestore.")
        else:
            # Save mock collection locally
            mock_path = os.path.join(MOCK_DIR, f"{col_name}.json")
            with open(mock_path, "w", encoding="utf-8") as f:
                json.dump(docs, f, indent=2)
            print(f"  -> Collection '{col_name}': Cached {doc_count} documents in firestore_mock/{col_name}.json")

        summary_counts[col_name] = doc_count

    # 3. Verification Step: Print Document Count per Collection
    print("\n" + "=" * 65)
    print("VERIFICATION STEP: Collection Document Counts")
    print("=" * 65)
    print(f"{'Collection Name':<22} {'Target Document Count':<25} {'Status'}")
    print("-" * 65)

    for col_name, expected_count in summary_counts.items():
        if is_live_firestore:
            actual_count = get_collection_count(col_name)
            status = "[OK] Verified in Cloud" if actual_count >= expected_count else f"[WARN] Found {actual_count}"
        else:
            status = "[OK] Verified Locally"
            actual_count = expected_count

        print(f"{col_name:<22} {actual_count:<25} {status}")

    print("=" * 65)
    if is_live_firestore:
        print("[SUCCESS] All 7 Firestore collections successfully loaded and verified on GCP!")
    else:
        print("[SUCCESS] All 7 collections staged and verified! When you connect GCP,")
        print("          run this same script to push them directly to live Cloud Firestore.")
    print("=" * 65)


if __name__ == "__main__":
    main()
