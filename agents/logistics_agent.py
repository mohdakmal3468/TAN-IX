"""
agents/logistics_agent.py
-------------------------
The Intra-State Logistics Agent is responsible for:
1. Calculating optimal transit paths between UP leather clusters along key expressways:
   - Agra-Lucknow Expressway
   - Yamuna Expressway
   - NH-19 / NH-27
2. Interrogating BigQuery historical logs for bottleneck patterns (e.g. fog speed limits, bridge traffic).
3. Assigning appropriate commercial vehicles and estimating freight & toll expenditures.
"""

from typing import Dict, Any
from tools.logistics_tools import calculate_route, get_available_fleet
from tools.bigquery_tools import get_corridor_performance_stats
from config import GEMINI_API_KEY, GEMINI_MODEL


class IntraStateLogisticsAgent:
    """
    Autonomous logistics agent specialized in UP expressway transport planning and carrier scheduling.
    """

    def __init__(self):
        self.name = "Intra-State Logistics Agent"
        self.role = "Highway routing, freight cost calculation, historical bottleneck analysis, and fleet dispatch."

    def plan_transfer(self, origin: str, destination: str, required_sqft: int, urgency: str = "urgent") -> Dict[str, Any]:
        """
        Creates a comprehensive logistics plan to transport goods from origin to destination.
        """
        route_details = calculate_route(origin, destination, urgency=urgency)
        fleet_options = get_available_fleet(origin)
        historical_stats = get_corridor_performance_stats()

        corridor_key = f"{origin} -> {destination}"
        corridor_history = historical_stats.get("corridor_breakdown", {}).get(corridor_key, {
            "on_time_percentage": 92.0,
            "delay_factors": ["Standard traffic flow"]
        })

        plan = {
            "agent": self.name,
            "origin": origin,
            "destination": destination,
            "required_cargo_volume": f"{required_sqft} sq ft",
            "route": route_details,
            "corridor_historical_reliability": f"{corridor_history.get('on_time_percentage', 90)}% on-time",
            "known_delay_factors": list(set(corridor_history.get("delay_factors", []))),
            "assigned_vehicle": fleet_options[0] if fleet_options else None,
            "status": "ROUTE_OPTIMIZED"
        }

        # AI summary enrichment if Gemini API key is active
        if GEMINI_API_KEY:
            try:
                from google import genai
                client = genai.Client(api_key=GEMINI_API_KEY)
                prompt = f"""
                You are the Intra-State Logistics Agent for Uttar Pradesh Leather Corridors.
                Summarize this transit plan in 2 crisp sentences for the State Master Orchestrator:
                Route: {route_details['route_name']} ({route_details['distance_km']} km, ~{route_details['estimated_transit_hours']} hrs)
                Cost: ₹{route_details['total_estimated_cost_inr']}
                Historical Reliability: {plan['corridor_historical_reliability']}
                Vehicle: {plan['assigned_vehicle']['type']}
                """
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt
                )
                plan["ai_logistics_brief"] = response.text
            except Exception:
                plan["ai_logistics_brief"] = (
                    f"Selected {route_details['route_name']} ({route_details['distance_km']} km, est. {route_details['estimated_transit_hours']}h) "
                    f"via {plan['assigned_vehicle']['type']}. Est total cost ₹{route_details['total_estimated_cost_inr']}."
                )
        else:
            plan["ai_logistics_brief"] = (
                f"Selected {route_details['route_name']} ({route_details['distance_km']} km, est. {route_details['estimated_transit_hours']}h) "
                f"via {plan['assigned_vehicle']['type']}. Est total cost ₹{route_details['total_estimated_cost_inr']}."
            )

        return plan
