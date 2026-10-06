"""
tools/firestore_tools.py
------------------------
Handles reading and writing live stock states for the 4 UP clusters:
Kanpur, Unnao, Agra, and Noida.

Beginner-Friendly Design:
- If USE_MOCK_DATA is True or GCP credentials are not found, this module automatically
  reads and writes to 'data/seed_inventory.json'.
- If GCP credentials exist, it can synchronize with Google Cloud Firestore collections.
"""

import os
import json
from typing import Dict, Any, List
from config import USE_MOCK_DATA, GCP_PROJECT_ID, FIRESTORE_DATABASE

# Path to the local JSON seed file
SEED_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "seed_inventory.json")

# Attempt Firestore client initialization if not in mock mode
firestore_client = None
if not USE_MOCK_DATA:
    try:
        from google.cloud import firestore
        firestore_client = firestore.Client(project=GCP_PROJECT_ID, database=FIRESTORE_DATABASE)
        print("[Firestore] Connected to Google Cloud Firestore successfully.")
    except Exception as e:
        print(f"[Firestore] GCP Connection note: {e}. Falling back to local data store.")
        firestore_client = None


def _load_local_data() -> Dict[str, Any]:
    """Helper function to load the local inventory JSON file."""
    if not os.path.exists(SEED_FILE_PATH):
        raise FileNotFoundError(f"Inventory seed file not found at: {SEED_FILE_PATH}")
    with open(SEED_FILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_local_data(data: Dict[str, Any]) -> None:
    """Helper function to save changes back to the local inventory JSON file."""
    with open(SEED_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_all_clusters_inventory() -> Dict[str, Any]:
    """
    Retrieves live inventory status across all 4 UP leather clusters:
    Kanpur, Unnao, Agra, and Noida.
    """
    if firestore_client is not None:
        try:
            docs = firestore_client.collection("clusters").stream()
            results = {}
            for doc in docs:
                results[doc.id] = doc.to_dict()
            if results:
                return {"clusters": results}
        except Exception as e:
            print(f"[Firestore Error] Failed to read from Firestore: {e}. Using local copy.")

    # Local fallback
    data = _load_local_data()
    return data.get("clusters", {})


def get_cluster_inventory(cluster_name: str) -> Dict[str, Any]:
    """
    Retrieves inventory for a specific cluster (e.g. 'Kanpur', 'Agra').
    """
    cluster_key = cluster_name.capitalize().strip()
    all_clusters = get_all_clusters_inventory()
    if cluster_key in all_clusters:
        return all_clusters[cluster_key]
    return {"error": f"Cluster '{cluster_name}' not found. Available: Kanpur, Unnao, Agra, Noida."}


def check_critical_stockouts() -> List[Dict[str, Any]]:
    """
    Scans all clusters to find items where current quantity is below the minimum threshold.
    Returns a list of items requiring urgent replenishment.
    """
    all_clusters = get_all_clusters_inventory()
    alerts = []

    for cluster_name, details in all_clusters.items():
        inventory = details.get("inventory", {})
        for item_name, item_data in inventory.items():
            qty = item_data.get("quantity", 0)
            min_thresh = item_data.get("min_threshold", 0)
            
            if qty < min_thresh:
                deficit = min_thresh - qty
                alerts.append({
                    "cluster": cluster_name,
                    "item": item_name,
                    "current_quantity": qty,
                    "min_threshold": min_thresh,
                    "deficit": deficit,
                    "unit": item_data.get("unit", "units"),
                    "severity": "CRITICAL" if qty < (min_thresh * 0.5) else "WARNING",
                    "status": item_data.get("status", "Low Stock")
                })
    return alerts


def update_cluster_inventory(cluster_name: str, item_name: str, quantity_delta: int) -> Dict[str, Any]:
    """
    Updates stock levels for an item in a cluster.
    - Positive delta adds stock (e.g. receipt of goods).
    - Negative delta removes stock (e.g. shipment dispatch).
    """
    cluster_key = cluster_name.capitalize().strip()
    data = _load_local_data()
    clusters = data.get("clusters", {})

    if cluster_key not in clusters:
        return {"success": False, "message": f"Cluster '{cluster_key}' not recognized."}

    inv = clusters[cluster_key].get("inventory", {})
    if item_name not in inv:
        return {"success": False, "message": f"Item '{item_name}' not found in cluster '{cluster_key}'."}

    current_qty = inv[item_name]["quantity"]
    new_qty = current_qty + quantity_delta

    if new_qty < 0:
        return {
            "success": False,
            "message": f"Cannot deduct {abs(quantity_delta)} from current stock of {current_qty}."
        }

    # Update state
    inv[item_name]["quantity"] = new_qty
    min_thresh = inv[item_name]["min_threshold"]
    capacity = inv[item_name].get("capacity", new_qty * 2)

    # Automatically update status tag
    if new_qty < (min_thresh * 0.5):
        inv[item_name]["status"] = "Critical Low"
    elif new_qty < min_thresh:
        inv[item_name]["status"] = "Low Stock"
    elif new_qty > (capacity * 0.8):
        inv[item_name]["status"] = "Surplus"
    else:
        inv[item_name]["status"] = "Normal"

    _save_local_data(data)

    # Also update Firestore if live
    if firestore_client is not None:
        try:
            firestore_client.collection("clusters").document(cluster_key).set(clusters[cluster_key])
        except Exception as e:
            print(f"[Firestore Warning] Sync to cloud failed: {e}")

    return {
        "success": True,
        "cluster": cluster_key,
        "item": item_name,
        "previous_quantity": current_qty,
        "new_quantity": new_qty,
        "status": inv[item_name]["status"]
    }
