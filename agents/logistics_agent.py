"""
agents/logistics_agent.py
-------------------------
Intra-State Logistics Agent for the Uttar Pradesh Leather Industrial Corridor.
Built with Google ADK (Agent Development Kit) and Gemini models using Google GenAI SDK.

Responsibilities:
1. Evaluates highway route lanes between UP clusters (Kanpur, Unnao, Agra, Noida).
2. Computes transit costs, toll charges, and ETAs across commercial freight carriers.
3. Automatically avoids blocked routes (e.g. Ganges flood on NH-27, fog curfew on Yamuna Expressway).
4. Returns strictly structured JSON with no duplicate keys.
"""

import os
import sys
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Google GenAI SDK
from google import genai
from google.genai import types

# Ensure root directory is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from google.adk import Agent
from tools.logistics_tools import (
    get_routes,
    get_carriers,
    calculate_route_cost,
    mark_route_blocked,
    unblock_route,
    reset_blocked_routes
)

# Initialize Google GenAI Client using GCP Project ID / Application Default Credentials
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")
if PROJECT_ID in (None, "", "your-gcp-project-id", "YOUR_PROJECT_ID"):
    PROJECT_ID = None

LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

client = genai.Client(
    vertexai=True if PROJECT_ID else False,
    project=PROJECT_ID,
    location=LOCATION
)

MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")


# ==============================================================================
# AGENT INSTRUCTION
# ==============================================================================
INSTRUCTION = """
You are the Intra-State Logistics Agent for the Uttar Pradesh Leather Supply Chain.

MISSION:
Given a transfer request (origin, destination, product, quantity, urgency):
1. Call `get_routes(origin, destination)` to retrieve all available, unblocked route lanes.
2. Call `get_carriers()` to inspect registered commercial freight carriers and rates.
3. For each viable route and carrier combination, call `calculate_route_cost(route_id, carrier_id, quantity)`.
4. If any route is marked as blocked, you MUST exclude it and select the best available alternative route.

STRICT JSON OUTPUT FORMAT:
You must output valid structured JSON matching this schema:
{
  "status": "ROUTE_OPTIMIZED | REROUTED_DUE_TO_BLOCKADE | NO_ROUTE_AVAILABLE",
  "origin": "string",
  "destination": "string",
  "product": "string",
  "quantity": float,
  "best_route": {
    "route_id": "string",
    "route_name": "string",
    "distance_km": float,
    "toll_inr": float
  },
  "carrier": {
    "carrier_id": "string",
    "carrier_name": "string",
    "reliability_pct": float,
    "vehicle_assigned": "string"
  },
  "cost_inr": float,
  "eta_hours": float,
  "decision_rationale": "string"
}
"""

# ==============================================================================
# GOOGLE ADK AGENT DEFINITION
# ==============================================================================
agent = Agent(
    name="intra_state_logistics_agent",
    model=MODEL_NAME,
    description="Optimizes highway transit routing, carrier selection, freight costs, and rerouting around blocked roads in UP.",
    instruction=INSTRUCTION,
    tools=[
        get_routes,
        get_carriers,
        calculate_route_cost,
        mark_route_blocked
    ]
)

root_agent = agent


# ==============================================================================
# CALLABLE CONTROLLER CLASS
# ==============================================================================
class IntraStateLogisticsAgent:
    """
    Intra-State Logistics Agent controller for UP Expressway transit optimization.
    Evaluates candidate routes, carrier rates, and road blockades.
    """

    def __init__(self):
        self.name = "Intra-State Logistics Agent"
        self.role = "Optimize expressway routes, assign freight carriers, and calculate ETAs and costs."
        self.adk_agent = agent
        self.client = client

    def plan_transfer(
        self,
        origin: str,
        destination: str,
        required_sqft: Optional[float] = None,
        quantity: Optional[float] = None,
        product: str = "leather goods",
        urgency: str = "normal"
    ) -> Dict[str, Any]:
        """
        Takes a transfer request and returns the route, carrier, cost, and ETA.
        """
        orig_clean = origin.capitalize().strip()
        dest_clean = destination.capitalize().strip()
        qty = float(quantity if quantity is not None else (required_sqft if required_sqft is not None else 1000.0))

        # Query available routes and carriers
        routes = get_routes(orig_clean, dest_clean)
        carriers = get_carriers()

        if not routes:
            return {
                "status": "NO_ROUTE_AVAILABLE",
                "origin": orig_clean,
                "destination": dest_clean,
                "product": product,
                "quantity": qty,
                "best_route": None,
                "carrier": None,
                "cost_inr": 0.0,
                "eta_hours": 0.0,
                "decision_rationale": f"All known direct route lanes between {orig_clean} and {dest_clean} are currently blocked or impassable."
            }

        candidates = []
        for r in routes:
            for c in carriers:
                cost_eval = calculate_route_cost(r["route_id"], c["carrier_id"], quantity=qty)
                if "error" not in cost_eval:
                    candidates.append({
                        "route": r,
                        "carrier": c,
                        "cost_eval": cost_eval
                    })

        if not candidates:
            return {
                "status": "NO_ROUTE_AVAILABLE",
                "origin": orig_clean,
                "destination": dest_clean,
                "product": product,
                "quantity": qty,
                "best_route": None,
                "carrier": None,
                "cost_inr": 0.0,
                "eta_hours": 0.0,
                "decision_rationale": "Unable to calculate feasible carrier assignment."
            }

        selected = candidates[0]
        s_route = selected["route"]
        s_carrier = selected["carrier"]
        s_cost = selected["cost_eval"]

        is_alternative = "ALT" in s_route["route_id"] or "Alternative" in s_route["route_name"]
        status_code = "REROUTED_DUE_TO_BLOCKADE" if is_alternative else "ROUTE_OPTIMIZED"

        prompt = f"""
        You are the Intra-State Logistics Agent for UP leather corridors.
        Provide a unique, context-aware 2-sentence rationale summarizing this dispatch selection:
        Origin: {orig_clean}
        Destination: {dest_clean}
        Route: {s_route['route_name']} ({s_route['distance_km']} km)
        Carrier: {s_carrier['name']} (INR {s_cost['total_cost_inr']:,})
        ETA: {s_cost['estimated_transit_hours']} hrs
        Status: {status_code}
        Quantity: {qty} {product}
        """

        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.9,
            presence_penalty=0.3,
            frequency_penalty=0.3
        )

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=config
        )
        decision_rationale = response.text.strip()

        return {
            "status": status_code,
            "origin": orig_clean,
            "destination": dest_clean,
            "product": product,
            "quantity": qty,
            "best_route": {
                "route_id": s_route["route_id"],
                "route_name": s_route["route_name"],
                "distance_km": s_route["distance_km"],
                "toll_inr": s_route["base_toll_inr"]
            },
            "carrier": {
                "carrier_id": s_carrier["carrier_id"],
                "carrier_name": s_carrier["name"],
                "reliability_pct": s_carrier["reliability_pct"],
                "vehicle_assigned": s_cost["vehicle_assigned"]
            },
            "cost_inr": s_cost["total_cost_inr"],
            "eta_hours": s_cost["estimated_transit_hours"],
            "decision_rationale": decision_rationale
        }


# ==============================================================================
# STANDALONE DEMO & TEST RUNNER
# ==============================================================================
if __name__ == "__main__":
    print("=" * 75)
    print("INTRA-STATE LOGISTICS AGENT (Google ADK & Google GenAI SDK)")
    print("Corridor Routing & Road Blockade Rerouting")
    print("=" * 75)

    agent_controller = IntraStateLogisticsAgent()

    # Scenario 1: Normal Transfer Request
    print("\n[Scenario 1] Normal Transfer Request (Kanpur -> Agra, 1020 belts)...")
    reset_blocked_routes()

    plan_1 = agent_controller.plan_transfer(
        origin="Kanpur",
        destination="Agra",
        product="belts",
        quantity=1020.0,
        urgency="normal"
    )
    print(json.dumps(plan_1, indent=2))

    # Scenario 2: Main Route Blockade
    print("\n" + "-" * 75)
    print("[Scenario 2] Disruptive Event: Blocking Primary Route LANE-03 (Agra-Lucknow Expressway)...")
    mark_route_blocked("LANE-03")
    print("-> Route LANE-03 has been marked as BLOCKED.")

    print("\nRe-evaluating Transfer Request with Blockade Active...")
    plan_2 = agent_controller.plan_transfer(
        origin="Kanpur",
        destination="Agra",
        product="belts",
        quantity=1020.0,
        urgency="normal"
    )
    print(json.dumps(plan_2, indent=2))

    reset_blocked_routes()

    print("\n" + "=" * 75)
    print("=" * 75)