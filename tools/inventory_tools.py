"""
tools/inventory_tools.py
------------------------
Autonomous inventory tools for Google ADK and TAN-IX agents.
All functions include explicit type hints and detailed Google-style docstrings
so that Google ADK and Gemini can inspect and convert them into
accurate function declarations.

Data source: the 'inventory' collection (Cloud Firestore, or data/firestore_mock/
inventory.json in mock mode) through tools/firestore_client.py.

Each stored record holds only raw inputs:
    inventory_id, district, product, quantity, unit, unit_cost_inr, daily_burn_rate_pct
Safety stock, reorder point, days left and status are PREDICTED on every read
by tools/inventory_model.py. There are no local-file fallbacks: if no inventory
exists, a clear error is raised.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List

from tools.firestore_client import list_documents, set_document
from tools.inventory_model import enrich_record


def _get_all_inventory_records() -> List[Dict[str, Any]]:
    """Reads every inventory record and adds the predicted fields."""
    docs = list_documents("inventory", limit=100)
    if not docs:
        raise RuntimeError(
            "No inventory records found. Mock mode: restore data/firestore_mock/inventory.json. "
            "Cloud mode: run scripts/load_firestore.py."
        )
    records = []
    for doc in docs:
        rec = enrich_record(doc)
        rec["daily_burn_rate"] = rec["daily_burn_units"]   # units per day, used by the tools below
        records.append(rec)
    return records


def get_stock_level(district: str, product: str) -> Dict[str, Any]:
    """Retrieves current physical inventory balance, unit, and predicted health status for a product in a district warehouse.

    Args:
        district: The UP district name (e.g. 'Kanpur', 'Unnao', 'Agra', 'Noida').
        product: The leather product category (e.g. 'shoes', 'belts', 'bags', 'jackets').

    Returns:
        A dictionary containing the district, product, current quantity, measurement unit,
        burn rate, predicted safety stock and reorder point, days of stock left and status tag.
        Returns found=False with an error message if the record does not exist.
    """
    target_district = district.capitalize().strip()
    target_product = product.lower().strip()

    try:
        rec = next(
            r for r in _get_all_inventory_records()
            if r["district"].capitalize() == target_district and r["product"].lower() == target_product
        )
    except StopIteration:
        return {
            "found": False,
            "error": f"No inventory record found for product '{product}' in district '{district}'.",
            "district": target_district,
            "product": target_product,
            "quantity": 0.0
        }

    return {
        "found": True,
        "inventory_id": rec["inventory_id"],
        "district": target_district,
        "product": target_product,
        "quantity": float(rec["quantity"]),
        "unit": rec["unit"],
        "daily_burn_rate": rec["daily_burn_rate"],
        "daily_burn_rate_pct": rec["daily_burn_rate_pct"],
        "reorder_point": rec["reorder_point"],
        "safety_stock": rec["safety_stock"],
        "unit_cost_inr": float(rec["unit_cost_inr"]),
        "days_left": rec["days_left"],
        "status": rec["status"]
    }


def days_of_stock_left(district: str, product: str) -> float:
    """Calculates how many operating days of inventory remain before a warehouse faces a stockout.

    This divides the current stock quantity by the daily consumption (burn rate, converted
    from its percentage of warehouse capacity).

    Args:
        district: The UP district name (e.g. 'Agra', 'Kanpur').
        product: The leather product name (e.g. 'belts', 'shoes').

    Returns:
        The estimated number of days left as a float (rounded to 1 decimal place).
        Returns 0.0 if stock is exhausted, or 999.0 if burn rate is zero.
        Raises ValueError if the district/product pair does not exist.
    """
    stock = get_stock_level(district, product)
    if not stock.get("found"):
        return 0.0
    return stock["days_left"]


def list_below_reorder_point(district: str) -> List[Dict[str, Any]]:
    """Identifies all leather commodities in a district whose stock has dropped below the reorder point.

    Scans the warehouse inventory and flags items where current quantity is strictly
    less than the predicted reorder point, indicating a need for replenishment.

    Args:
        district: The UP district name to audit (e.g. 'Agra', 'Noida').

    Returns:
        A list of dictionaries, where each entry represents a deficit product, including the current
        quantity, reorder threshold, missing deficit volume, days of stock remaining, and severity
        (CRITICAL when the predicted status is CRITICAL_DEFICIT, otherwise WARNING).
    """
    target_district = district.capitalize().strip()
    deficits = []

    for rec in _get_all_inventory_records():
        if rec["district"].capitalize() != target_district:
            continue
        qty = float(rec["quantity"])
        if qty >= rec["reorder_point"]:
            continue
        deficits.append({
            "district": target_district,
            "product": rec["product"],
            "current_quantity": qty,
            "reorder_point": rec["reorder_point"],
            "deficit": round(rec["reorder_point"] - qty, 1),
            "unit": rec["unit"],
            "days_left": rec["days_left"],
            "severity": "CRITICAL" if rec["status"] == "CRITICAL_DEFICIT" else "WARNING",
            "status": rec["status"]
        })

    deficits.sort(key=lambda x: x["deficit"], reverse=True)   # biggest deficit first
    return deficits


def find_surplus_districts(product: str, min_surplus: float = 0.0) -> List[Dict[str, Any]]:
    """Finds candidate donor districts that maintain surplus inventory of a given leather product.

    A district is a donor if its stock exceeds the predicted reorder point by at least
    `min_surplus`, so giving stock away never pushes it below its own reorder point.

    Args:
        product: The leather product commodity to search for (e.g. 'belts', 'shoes').
        min_surplus: Minimum buffer excess required (default: 0.0).

    Returns:
        A list of dictionaries representing donor districts with their current quantity,
        reorder point and available surplus, largest surplus first.
    """
    target_product = product.lower().strip()
    donors = []

    for rec in _get_all_inventory_records():
        if rec["product"].lower() != target_product:
            continue
        surplus = float(rec["quantity"]) - rec["reorder_point"]
        if surplus > 0 and surplus >= min_surplus:
            donors.append({
                "district": rec["district"],
                "product": target_product,
                "current_quantity": float(rec["quantity"]),
                "reorder_point": rec["reorder_point"],
                "available_surplus": round(surplus, 1),
                "unit": rec["unit"],
                "status": rec["status"]
            })

    donors.sort(key=lambda x: x["available_surplus"], reverse=True)
    return donors


def adjust_stock(district: str, product: str, delta: float) -> Dict[str, Any]:
    """Adds (positive delta) or removes (negative delta) stock and saves it to the inventory store.

    This is the ONLY place that changes quantities, so the API, the agents and the
    dashboard all see the same numbers. It is not given to the LLM as a tool.
    Raises ValueError for an unknown record or if the stock would go below zero.
    """
    target_district = district.capitalize().strip()
    target_product = product.lower().strip()

    try:
        doc = next(
            d for d in list_documents("inventory", limit=100)
            if d["district"].capitalize() == target_district and d["product"].lower() == target_product
        )
    except StopIteration:
        raise ValueError(f"No inventory record for '{product}' in '{district}'.")

    previous = float(doc["quantity"])
    new_quantity = previous + float(delta)
    if new_quantity < 0:
        raise ValueError(f"Cannot remove {abs(delta)} from {previous} in stock ({target_district} {target_product}).")

    saved = set_document(
        "inventory", doc["inventory_id"],
        {"quantity": new_quantity, "last_updated": datetime.now(timezone.utc).isoformat()},
        merge=True
    )
    if not saved:
        raise RuntimeError(f"Could not save inventory update for {doc['inventory_id']}.")

    return {
        "district": target_district,
        "product": target_product,
        "previous_quantity": previous,
        "new_quantity": new_quantity
    }