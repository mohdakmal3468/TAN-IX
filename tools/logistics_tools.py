"""
tools/logistics_tools.py
------------------------
Autonomous logistics and highway routing tools for Google ADK and TAN-IX agents.
All functions include explicit type hints and detailed Google-style docstrings.

Core Functions:
1. get_routes(origin, destination) -> List of active route lanes (excludes blocked paths)
2. get_carriers() -> List of commercial freight carriers with rate/speed/reliability profiles
3. calculate_route_cost(route_id, carrier_id, quantity) -> Itemized transit cost & duration
4. mark_route_blocked(route_id) -> Marks route as blocked due to flooding, fog, or protests

Reads route and carrier data from Firestore, with local fallback to data/routes.json and data/carriers.json.
"""

import os
import json
from typing import Dict, Any, List, Optional, Set
from config import HIGHWAY_CORRIDORS
from tools.firestore_client import list_documents, set_document

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ROUTES_PATH = os.path.join(DATA_DIR, "routes.json")
CARRIERS_PATH = os.path.join(DATA_DIR, "carriers.json")

# In-memory tracking for dynamically blocked routes
BLOCKED_ROUTES: Set[str] = set()

# Standard fleet vehicle classes for backwards compatibility
FLEET_TYPES = {
    "light_commercial": {"name": "Tata 407 (3.5 Ton)", "capacity_sqft": 4000, "base_rate_per_km": 38},
    "medium_commercial": {"name": "Eicher Pro (9 Ton)", "capacity_sqft": 10000, "base_rate_per_km": 52},
    "heavy_truck": {"name": "Multi-Axle Truck (16 Ton)", "capacity_sqft": 20000, "base_rate_per_km": 72}
}


def _load_all_routes() -> List[Dict[str, Any]]:
    """Helper to fetch route lanes from Firestore with local fallback."""
    docs = list_documents("routes", limit=50)
    if docs:
        return docs

    if os.path.exists(ROUTES_PATH):
        with open(ROUTES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _load_all_carriers() -> List[Dict[str, Any]]:
    """Helper to fetch carrier profiles from Firestore with local fallback."""
    docs = list_documents("carriers", limit=20)
    if docs:
        return docs

    if os.path.exists(CARRIERS_PATH):
        with open(CARRIERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# ==============================================================================
# 1. GET ROUTES (Excludes Blocked Routes)
# ==============================================================================

def get_routes(origin: str, destination: str) -> List[Dict[str, Any]]:
    """Finds all available highway and expressway routes between two UP districts.

    Filters out any routes that have been flagged as blocked due to flood inundation,
    winter fog curfews, or road blockades.

    Args:
        origin: The origin district name (e.g. 'Kanpur', 'Unnao', 'Agra', 'Noida').
        destination: The destination district name (e.g. 'Agra', 'Noida').

    Returns:
        A list of available route dictionaries with distance (km), standard transit hours,
        highway name, and toll charges. Returns an empty list if no unblocked route exists.
    """
    orig_clean = origin.capitalize().strip()
    dest_clean = destination.capitalize().strip()

    all_routes = _load_all_routes()
    matching_routes = []

    for r in all_routes:
        r_origin = r.get("origin", "").capitalize().strip()
        r_dest = r.get("destination", "").capitalize().strip()
        lane_id = str(r.get("lane_id") or r.get("route_id") or "").upper()

        if r_origin == orig_clean and r_dest == dest_clean:
            # Check if route is marked as blocked
            if lane_id in BLOCKED_ROUTES or r.get("is_blocked") is True:
                continue

            matching_routes.append({
                "route_id": lane_id,
                "lane_id": lane_id,
                "origin": r_origin,
                "destination": r_dest,
                "route_name": r.get("route_name", "Inter-District Highway"),
                "distance_km": float(r.get("distance_km", 200)),
                "standard_transit_hours": float(r.get("standard_transit_hours", 4.0)),
                "base_toll_inr": float(r.get("base_toll_inr", 500)),
                "is_blocked": False
            })

    return matching_routes


# ==============================================================================
# 2. GET CARRIERS
# ==============================================================================

def get_carriers() -> List[Dict[str, Any]]:
    """Retrieves all registered commercial freight carriers and their operational metrics.

    Provides cost rates per kilometer, average transit speeds, fleet types,
    and historical reliability scores.

    Returns:
        A list of carrier dictionaries containing carrier_id, name, speed_kmh,
        base_rate_per_km_inr, reliability_pct, and fleet_type.
    """
    carriers = _load_all_carriers()
    cleaned = []

    for c in carriers:
        c_id = str(c.get("carrier_id") or c.get("id") or "").upper()
        cleaned.append({
            "carrier_id": c_id,
            "name": c.get("name", "Commercial Carrier"),
            "speed_kmh": float(c.get("speed_kmh", 50)),
            "base_rate_per_km_inr": float(c.get("base_rate_per_km_inr", 40.0)),
            "reliability_pct": float(c.get("reliability_pct", 90.0)),
            "fleet_type": c.get("fleet_type", "Standard Commercial Truck"),
            "tier": c.get("tier", "Standard")
        })

    return cleaned


# ==============================================================================
# 3. CALCULATE ROUTE COST
# ==============================================================================

def calculate_route_cost(route_id: str, carrier_id: str, quantity: float) -> Dict[str, Any]:
    """Calculates an itemized freight invoice estimate for a shipment.

    Computes total transit expenditure combining base distance rate, expressway tolls,
    and cargo volume handling, along with expected transit duration.

    Args:
        route_id: The route lane identifier (e.g. 'LANE-03').
        carrier_id: The carrier identifier (e.g. 'CAR-01', 'CAR-02').
        quantity: The volume or unit count of cargo being transported.

    Returns:
        A dictionary with itemized freight cost, toll charges, handling fee, total cost in INR,
        and estimated transit duration in hours. Returns an error dictionary if the route is blocked or not found.
    """
    clean_route_id = str(route_id).upper().strip()
    clean_carrier_id = str(carrier_id).upper().strip()

    # Check if route is currently blocked
    if clean_route_id in BLOCKED_ROUTES:
        return {
            "error": f"Route '{route_id}' is currently marked as blocked and cannot be used for dispatch.",
            "route_id": clean_route_id,
            "carrier_id": clean_carrier_id,
            "total_cost_inr": 0.0
        }

    # Find Route
    all_routes = _load_all_routes()
    route = None
    for r in all_routes:
        rid = str(r.get("lane_id") or r.get("route_id") or "").upper()
        if rid == clean_route_id:
            route = r
            break

    if not route:
        return {"error": f"Route '{route_id}' not found.", "route_id": clean_route_id}

    # Find Carrier
    all_carriers = _load_all_carriers()
    carrier = None
    for c in all_carriers:
        cid = str(c.get("carrier_id") or c.get("id") or "").upper()
        if cid == clean_carrier_id or c.get("name", "").lower() == clean_carrier_id.lower():
            carrier = c
            break

    if not carrier:
        return {"error": f"Carrier '{carrier_id}' not found.", "carrier_id": clean_carrier_id}

    # Calculation logic
    distance_km = float(route.get("distance_km", 200))
    rate_per_km = float(carrier.get("base_rate_per_km_inr", 40.0))
    speed_kmh = max(20.0, float(carrier.get("speed_kmh", 50.0)))

    base_freight_inr = round(distance_km * rate_per_km, 2)
    toll_inr = float(route.get("base_toll_inr", 500))

    # Cargo handling fee: 50 paise per unit for loading/securing
    handling_inr = round(max(0.0, float(quantity)) * 0.50, 2)
    total_cost_inr = round(base_freight_inr + toll_inr + handling_inr, 2)
    transit_hours = round(distance_km / speed_kmh, 1)

    return {
        "route_id": clean_route_id,
        "route_name": route.get("route_name", "Highway"),
        "origin": route.get("origin"),
        "destination": route.get("destination"),
        "carrier_id": str(carrier.get("carrier_id")),
        "carrier_name": carrier.get("name"),
        "distance_km": distance_km,
        "quantity": float(quantity),
        "base_freight_inr": base_freight_inr,
        "toll_inr": toll_inr,
        "handling_inr": handling_inr,
        "total_cost_inr": total_cost_inr,
        "estimated_transit_hours": transit_hours,
        "carrier_reliability_pct": float(carrier.get("reliability_pct", 90.0)),
        "vehicle_assigned": carrier.get("fleet_type", "Eicher Pro (9 Ton)")
    }


# ==============================================================================
# 4. MARK ROUTE BLOCKED
# ==============================================================================

def mark_route_blocked(route_id: str) -> Dict[str, Any]:
    """Marks a highway route lane as impassable, excluding it from active routing options.

    Used when external disruption events occur, such as Ganges River flooding near
    Jajmau Bridge, severe Yamuna Expressway fog accidents, or toll protests.

    Args:
        route_id: The route lane identifier to block (e.g. 'LANE-01', 'LANE-03').

    Returns:
        A confirmation dictionary indicating that the route is now blocked.
    """
    clean_route_id = str(route_id).upper().strip()
    BLOCKED_ROUTES.add(clean_route_id)

    # If Firestore client is available, also record block status in cloud
    set_document("routes", clean_route_id, {"is_blocked": True}, merge=True)

    return {
        "success": True,
        "route_id": clean_route_id,
        "status": "BLOCKED",
        "message": f"Route '{clean_route_id}' has been marked as blocked and excluded from active routing options."
    }


def unblock_route(route_id: str) -> Dict[str, Any]:
    """Clears the blockade status for a highway route, restoring it to active service."""
    clean_route_id = str(route_id).upper().strip()
    if clean_route_id in BLOCKED_ROUTES:
        BLOCKED_ROUTES.remove(clean_route_id)
    set_document("routes", clean_route_id, {"is_blocked": False}, merge=True)
    return {
        "success": True,
        "route_id": clean_route_id,
        "status": "OPERATIONAL",
        "message": f"Route '{clean_route_id}' has been unblocked and restored to service."
    }


def reset_blocked_routes():
    """Resets all blocked routes back to baseline operational state."""
    BLOCKED_ROUTES.clear()


# ==============================================================================
# BACKWARDS-COMPATIBILITY HELPERS (For Existing Agent Implementations)
# ==============================================================================

def calculate_route(origin: str, destination: str, urgency: str = "normal") -> Dict[str, Any]:
    """Backwards-compatible highway calculator used by older agent methods."""
    routes = get_routes(origin, destination)
    if routes:
        selected_route = routes[0]
        carriers = get_carriers()
        selected_carrier = carriers[0] if urgency.lower() in ("urgent", "critical") else (carriers[1] if len(carriers) > 1 else carriers[0])
        cost_calc = calculate_route_cost(selected_route["route_id"], selected_carrier["carrier_id"], quantity=1500)
        return {
            "origin": selected_route["origin"],
            "destination": selected_route["destination"],
            "route_name": selected_route["route_name"],
            "distance_km": selected_route["distance_km"],
            "estimated_transit_hours": cost_calc["estimated_transit_hours"],
            "urgency_level": urgency.capitalize(),
            "freight_cost_inr": cost_calc["base_freight_inr"],
            "toll_charges_inr": cost_calc["toll_inr"],
            "total_estimated_cost_inr": cost_calc["total_cost_inr"],
            "recommended_vehicle": cost_calc["vehicle_assigned"]
        }

    # Fallback to corridor metadata if no dynamic route unblocked
    orig = origin.capitalize().strip()
    dest = destination.capitalize().strip()
    corridor = HIGHWAY_CORRIDORS.get((orig, dest)) or HIGHWAY_CORRIDORS.get((dest, orig), {
        "distance_km": 300,
        "transit_hours": 5.0,
        "route_name": "UP State Highway"
    })
    base_rate = FLEET_TYPES["medium_commercial"]["base_rate_per_km"]
    dist = corridor["distance_km"]
    freight = int(dist * base_rate)
    toll = int(dist * 2.8)
    return {
        "origin": orig,
        "destination": dest,
        "route_name": corridor["route_name"],
        "distance_km": dist,
        "estimated_transit_hours": corridor["transit_hours"],
        "urgency_level": urgency.capitalize(),
        "freight_cost_inr": freight,
        "toll_charges_inr": toll,
        "total_estimated_cost_inr": freight + toll,
        "recommended_vehicle": "Eicher Pro (9 Ton)"
    }


def get_available_fleet(origin: str) -> List[Dict[str, Any]]:
    """Returns simulated available transport fleet near origin."""
    orig = origin.capitalize().strip()
    return [
        {
            "truck_id": f"UP-{orig[:3].upper()}-901",
            "type": "Eicher Pro (9 Ton)",
            "driver_name": "Ramesh Yadav",
            "current_location": f"{orig} Logistics Park",
            "capacity_sqft": 10000,
            "status": "Ready for Dispatch"
        },
        {
            "truck_id": f"UP-{orig[:3].upper()}-404",
            "type": "Tata 407 (3.5 Ton)",
            "driver_name": "Suresh Verma",
            "current_location": f"{orig} Toll Plaza",
            "capacity_sqft": 4000,
            "status": "Ready for Dispatch"
        }
    ]
