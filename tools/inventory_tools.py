"""
tools/inventory_tools.py
------------------------
Autonomous inventory tools for Google ADK and TAN-IX agents.
All functions include explicit type hints and detailed Google-style docstrings
so that Google ADK and Gemini 3.1 Flash can inspect and convert them into
accurate function declarations.

Reads live data from Cloud Firestore (collection: 'inventory'),
with seamless local fallback to data/inventory.json.
"""

import os
import json
from typing import Dict, Any, List, Optional
from tools.firestore_client import list_documents

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
LOCAL_INVENTORY_PATH = os.path.join(DATA_DIR, "inventory.json")


def _get_all_inventory_records() -> List[Dict[str, Any]]:
    """Helper to fetch inventory records from Firestore, falling back to local JSON."""
    docs = list_documents("inventory", limit=100)
    if docs:
        return docs

    # Local fallback
    if os.path.exists(LOCAL_INVENTORY_PATH):
        with open(LOCAL_INVENTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    # Secondary fallback to seed_inventory.json
    seed_path = os.path.join(DATA_DIR, "seed_inventory.json")
    if os.path.exists(seed_path):
        with open(seed_path, "r", encoding="utf-8") as f:
            seed_data = json.load(f)
            records = []
            for d_name, d_val in seed_data.get("clusters", {}).items():
                for p_name, p_val in d_val.get("inventory", {}).items():
                    records.append({
                        "inventory_id": f"INV-{d_name[:3].upper()}-{p_name[:3].upper()}",
                        "district": d_name,
                        "product": p_name,
                        "quantity": p_val.get("quantity", 0),
                        "unit": p_val.get("unit", "units"),
                        "daily_burn_rate": p_val.get("daily_burn_rate", 100),
                        "reorder_point": p_val.get("min_threshold", 1000),
                        "safety_stock": p_val.get("safety_stock", 300),
                        "unit_cost_inr": p_val.get("unit_cost_inr", 350),
                        "status": p_val.get("status", "NORMAL")
                    })
            return records
    return []


def get_stock_level(district: str, product: str) -> Dict[str, Any]:
    """Retrieves current physical inventory balance, unit, and health status for a product in a district warehouse.

    Args:
        district: The UP district name (e.g. 'Kanpur', 'Unnao', 'Agra', 'Noida').
        product: The leather product category (e.g. 'shoes', 'belts', 'bags', 'jackets').

    Returns:
        A dictionary containing the district, product, current quantity, measurement unit,
        reorder threshold, and status tag. Returns an error dictionary if the record is not found.
    """
    target_district = district.capitalize().strip()
    target_product = product.lower().strip()

    # Route through MCP server if USE_MCP flag is enabled
    if os.getenv("USE_MCP", "false").lower() in ("true", "1", "yes"):
        try:
            from tools.mcp_server import call_mcp_tool
            res = call_mcp_tool("get_stock_level", district=target_district, product=target_product)
            if res.get("status") != "NOT_FOUND":
                return {
                    "district": target_district,
                    "product": target_product,
                    "quantity": res["quantity"],
                    "unit": res["unit"],
                    "daily_burn_rate": res["daily_burn_rate"],
                    "reorder_point": res["reorder_point"],
                    "safety_stock": 300,
                    "unit_cost_inr": 350,
                    "status": res["status"],
                    "days_left": res["days_left"],
                    "via_mcp": True
                }
        except Exception:
            pass

    records = _get_all_inventory_records()
    for rec in records:
        if (rec.get("district", "").capitalize() == target_district and
                rec.get("product", "").lower() == target_product):
            return {
                "found": True,
                "district": target_district,
                "product": target_product,
                "quantity": float(rec.get("quantity", 0)),
                "unit": rec.get("unit", "units"),
                "daily_burn_rate": float(rec.get("daily_burn_rate", 1)),
                "reorder_point": float(rec.get("reorder_point", 0)),
                "safety_stock": float(rec.get("safety_stock", 0)),
                "unit_cost_inr": float(rec.get("unit_cost_inr", 0)),
                "status": rec.get("status", "NORMAL"),
                "inventory_id": rec.get("inventory_id", "")
            }

    return {
        "found": False,
        "error": f"No inventory record found for product '{product}' in district '{district}'.",
        "district": target_district,
        "product": target_product,
        "quantity": 0.0
    }


def days_of_stock_left(district: str, product: str) -> float:
    """Calculates how many operating days of inventory remain before a warehouse faces a stockout.

    This function divides the current available stock quantity by the expected daily consumption
    burn rate (burn_rate).

    Args:
        district: The UP district name (e.g. 'Agra', 'Kanpur').
        product: The leather product name (e.g. 'belts', 'shoes').

    Returns:
        The estimated number of days left as a float (rounded to 1 decimal place).
        Returns 0.0 if stock is exhausted, or 999.0 if burn rate is zero.
    """
    stock_info = get_stock_level(district, product)
    if not stock_info.get("found"):
        return 0.0

    qty = stock_info["quantity"]
    burn_rate = stock_info.get("daily_burn_rate", 0.0)

    if qty <= 0:
        return 0.0
    if burn_rate <= 0:
        return 999.0

    days_left = round(qty / burn_rate, 1)
    return days_left


def list_below_reorder_point(district: str) -> List[Dict[str, Any]]:
    """Identifies all leather commodities in a district whose stock has dropped below safety thresholds.

    Scans the warehouse inventory and flags items where current quantity is strictly
    less than the designated reorder point, indicating an urgent need for replenishment.

    Args:
        district: The UP district name to audit (e.g. 'Agra', 'Noida').

    Returns:
        A list of dictionaries, where each entry represents a deficit product, including the current
        quantity, reorder threshold, missing deficit volume, days of stock remaining, and severity.
    """
    target_district = district.capitalize().strip()
    records = _get_all_inventory_records()
    deficits = []

    for rec in records:
        if rec.get("district", "").capitalize() != target_district:
            continue

        qty = float(rec.get("quantity", 0))
        reorder = float(rec.get("reorder_point", 0))
        burn_rate = float(rec.get("daily_burn_rate", 1))

        if qty < reorder:
            deficit_amount = round(reorder - qty, 1)
            days_left = round(qty / burn_rate, 1) if burn_rate > 0 else 0.0
            severity = "CRITICAL" if qty < (reorder * 0.4) else "WARNING"

            deficits.append({
                "district": target_district,
                "product": rec.get("product"),
                "current_quantity": qty,
                "reorder_point": reorder,
                "deficit": deficit_amount,
                "unit": rec.get("unit", "units"),
                "days_left": days_left,
                "severity": severity,
                "status": rec.get("status", "LOW_STOCK")
            })

    # Sort descending by deficit severity
    deficits.sort(key=lambda x: x["deficit"], reverse=True)
    return deficits


def find_surplus_districts(product: str, min_surplus: float = 0.0) -> List[Dict[str, Any]]:
    """Finds candidate donor districts that maintain surplus inventory of a given leather product.

    An inventory balance is classified as a surplus if the current stock exceeds the reorder point
    by at least the specified `min_surplus` margin, making it eligible for inter-district transfer.

    Args:
        product: The leather product commodity to search for (e.g. 'belts', 'shoes').
        min_surplus: Minimum buffer excess required (default: 0.0).

    Returns:
        A list of dictionaries representing donor districts with their current quantity,
        reorder point, surplus margin available for transfer, and location.
    """
    target_product = product.lower().strip()
    records = _get_all_inventory_records()
    donors = []

    for rec in records:
        if rec.get("product", "").lower() != target_product:
            continue

        qty = float(rec.get("quantity", 0))
        reorder = float(rec.get("reorder_point", 0))
        surplus = qty - reorder

        if surplus >= min_surplus and surplus > 0:
            donors.append({
                "district": rec.get("district"),
                "product": target_product,
                "current_quantity": qty,
                "reorder_point": reorder,
                "available_surplus": round(surplus, 1),
                "unit": rec.get("unit", "units"),
                "status": rec.get("status", "SURPLUS")
            })

    # Sort descending by available surplus volume
    donors.sort(key=lambda x: x["available_surplus"], reverse=True)
    return donors
