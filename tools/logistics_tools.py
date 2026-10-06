"""
tools/logistics_tools.py
------------------------
Calculates intra-state transport routing, freight costs, and transit times
across Uttar Pradesh's leather manufacturing triangle:
- Kanpur (Jajmau) <-> Unnao (Banthar) <-> Agra (Sikandra) <-> Noida (Sector 63)

Leverages real expressway networks:
- Agra-Lucknow Expressway
- Yamuna Expressway
- NH-19 (National Highway 19)
- NH-27 (Ganga Bridge Corridor)
"""

from typing import Dict, Any, List
from config import HIGHWAY_CORRIDORS

# Standard fleet vehicle classes in UP freight transport
FLEET_TYPES = {
    "light_commercial": {"name": "Tata 407 (3.5 Ton)", "capacity_sqft": 4000, "base_rate_per_km": 38},
    "medium_commercial": {"name": "Eicher Pro (9 Ton)", "capacity_sqft": 10000, "base_rate_per_km": 52},
    "heavy_truck": {"name": "Multi-Axle Truck (16 Ton)", "capacity_sqft": 20000, "base_rate_per_km": 72}
}


def calculate_route(origin: str, destination: str, urgency: str = "normal") -> Dict[str, Any]:
    """
    Computes distance, estimated transit time, primary expressway route,
    and freight cost between two UP leather clusters.
    """
    orig = origin.capitalize().strip()
    dest = destination.capitalize().strip()

    if orig == dest:
        return {"error": "Origin and destination clusters cannot be the same."}

    # Look up in pre-calculated corridor matrix or reverse
    pair = (orig, dest)
    reverse_pair = (dest, orig)

    corridor = HIGHWAY_CORRIDORS.get(pair) or HIGHWAY_CORRIDORS.get(reverse_pair)

    if not corridor:
        # Fallback approximate calculation if indirect
        distance_km = 350
        transit_hours = 5.5
        route_name = "Inter-District State Highway"
    else:
        distance_km = corridor["distance_km"]
        transit_hours = corridor["transit_hours"]
        route_name = corridor["route_name"]

    # Calculate freight rate based on urgency
    # Normal: Medium commercial truck rate
    # Urgent / Emergency: 25% premium for dedicated fast freight dispatch
    base_rate = FLEET_TYPES["medium_commercial"]["base_rate_per_km"]
    multiplier = 1.25 if urgency.lower() in ("urgent", "critical", "emergency") else 1.0

    freight_cost_inr = int(distance_km * base_rate * multiplier)
    toll_estimate_inr = int(distance_km * 2.8)  # Approximate toll per km on UP Expressways

    return {
        "origin": orig,
        "destination": dest,
        "route_name": route_name,
        "distance_km": distance_km,
        "estimated_transit_hours": transit_hours,
        "urgency_level": urgency.capitalize(),
        "freight_cost_inr": freight_cost_inr,
        "toll_charges_inr": toll_estimate_inr,
        "total_estimated_cost_inr": freight_cost_inr + toll_estimate_inr,
        "recommended_vehicle": "Eicher Pro (9 Ton)" if urgency.lower() != "urgent" else "Dedicated Express Carrier"
    }


def get_available_fleet(origin: str) -> List[Dict[str, Any]]:
    """
    Returns simulated available commercial transport vehicles stationed near the cluster.
    """
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
