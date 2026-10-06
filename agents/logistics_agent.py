"""
agents/logistics_agent.py
-------------------------
Intra-State Logistics Agent for the Uttar Pradesh Leather Industrial Corridor.
Built with Google ADK (Agent Development Kit) and Gemini 3.1 Flash.

Responsibilities:
1. Evaluates highway route lanes between UP clusters (Kanpur, Unnao, Agra, Noida).
2. Computes transit costs, toll charges, and ETAs across commercial freight carriers.
3. Automatically avoids blocked routes (e.g. Ganges flood on NH-27, fog curfew on Yamuna Expressway).
4. Prefers cost-effective carriers while meeting delivery urgency requirements.
5. Returns strictly structured JSON with:
   - best_route, carrier, cost_inr, eta_hours, vehicle_type, decision_rationale.
"""

import os
import sys
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

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

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# ==============================================================================
# AGENT INSTRUCTION (Job Description & Decision Logic)
# ==============================================================================
INSTRUCTION = """
You are the Intra-State Logistics Agent for the Uttar Pradesh Leather Supply Chain.

MISSION:
Given a transfer request (origin, destination, product, quantity, urgency):
1. Call `get_routes(origin, destination)` to retrieve all available, unblocked route lanes.
2. Call `get_carriers()` to inspect registered commercial freight carriers and rates.
3. For each viable route and carrier combination, call `calculate_route_cost(route_id, carrier_id, quantity)`.
4. Selection Strategy:
   - Prefer CHEAPER options for standard/normal shipments to optimize state logistics spend.
   - For URGENT shipments, select faster/high-reliability carriers (e.g. Yamuna Fast Haulers or UP State Freight Express).
   - If any route is marked as blocked, you MUST exclude it and select the best available alternative route.

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
# CALLABLE CONTROLLER CLASS (For Orchestrator & Standalone Testing)
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
        Takes a transfer request and returns the optimal route, carrier, cost, and ETA.
        Prefers cheaper carriers unless urgency is high or a route is blocked.
        """
        orig_clean = origin.capitalize().strip()
        dest_clean = destination.capitalize().strip()
        qty = float(quantity if quantity is not None else (required_sqft if required_sqft is not None else 1000.0))

        # Step 1: Query available routes (excludes blocked paths)
        routes = get_routes(orig_clean, dest_clean)
        carriers = get_carriers()

        if not routes:
            return {
                "status": "NO_ROUTE_AVAILABLE",
                "origin": orig_clean,
                "destination": dest_clean,
                "product": product,
                "quantity": qty,
                "cost_inr": 0.0,
                "eta_hours": 0.0,
                "decision_rationale": f"All known direct route lanes between {orig_clean} and {dest_clean} are currently blocked or impassable."
            }

        # Step 2: Evaluate candidate options across unblocked routes and carriers
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
                "decision_rationale": "Unable to calculate feasible carrier assignment."
            }

        # Step 3: Optimization Strategy
        # If urgent/critical: sort by eta_hours ascending, breaking ties by reliability
        # If normal: prioritize primary expressway routes over slower alternatives, then prefer cheapest carrier
        is_urgent = urgency.lower() in ("urgent", "high", "critical", "emergency")
        if is_urgent:
            candidates.sort(key=lambda x: (
                1 if "ALT" in x["route"]["route_id"] else 0,
                x["cost_eval"]["estimated_transit_hours"],
                -x["carrier"]["reliability_pct"]
            ))
        else:
            candidates.sort(key=lambda x: (
                1 if "ALT" in x["route"]["route_id"] else 0,
                x["cost_eval"]["total_cost_inr"]
            ))

        best = candidates[0]
        b_route = best["route"]
        b_carrier = best["carrier"]
        b_cost = best["cost_eval"]

        # Check if this route is an alternative/fallback route
        is_alternative = "ALT" in b_route["route_id"] or "Alternative" in b_route["route_name"]

        if is_alternative:
            status_code = "REROUTED_DUE_TO_BLOCKADE"
            rationale = (
                f"Primary expressway route blocked. Successfully rerouted via {b_route['route_name']} "
                f"({b_route['distance_km']} km) using {b_carrier['name']} at INR {b_cost['total_cost_inr']:,.2f} "
                f"(ETA: {b_cost['estimated_transit_hours']} hrs)."
            )
        else:
            status_code = "ROUTE_OPTIMIZED"
            rationale = (
                f"Selected optimal route {b_route['route_name']} ({b_route['distance_km']} km). "
                f"Assigned cost-effective carrier {b_carrier['name']} at INR {b_cost['total_cost_inr']:,.2f} "
                f"with {b_carrier['reliability_pct']}% reliability rating (ETA: {b_cost['estimated_transit_hours']} hrs)."
            )

        structured_output = {
            "status": status_code,
            "origin": orig_clean,
            "destination": dest_clean,
            "product": product,
            "quantity": qty,
            "urgency": urgency.upper(),
            "best_route": {
                "route_id": b_route["route_id"],
                "route_name": b_route["route_name"],
                "distance_km": b_route["distance_km"],
                "toll_inr": b_route["base_toll_inr"]
            },
            "carrier": {
                "carrier_id": b_carrier["carrier_id"],
                "carrier_name": b_carrier["name"],
                "reliability_pct": b_carrier["reliability_pct"],
                "vehicle_assigned": b_cost["vehicle_assigned"]
            },
            "cost_inr": b_cost["total_cost_inr"],
            "eta_hours": b_cost["estimated_transit_hours"],
            "decision_rationale": rationale,
            # Backwards-compatible fields for State Orchestrator
            "route": {
                "route_name": b_route["route_name"],
                "distance_km": b_route["distance_km"],
                "estimated_transit_hours": b_cost["estimated_transit_hours"],
                "total_estimated_cost_inr": b_cost["total_cost_inr"],
                "toll_charges_inr": b_cost["toll_inr"],
                "freight_cost_inr": b_cost["base_freight_inr"]
            },
            "assigned_vehicle": {
                "type": b_cost["vehicle_assigned"],
                "carrier": b_carrier["name"]
            },
            "corridor_historical_reliability": f"{b_carrier['reliability_pct']}% on-time",
            "ai_logistics_brief": rationale
        }

        # If live Gemini API key is configured, enrich with AI reasoning brief
        if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
            try:
                from google import genai
                client = genai.Client(api_key=GEMINI_API_KEY)
                prompt = f"""
                You are the Intra-State Logistics Agent for UP leather corridors.
                Explain the dispatch selection in 2 crisp sentences for the State Orchestrator:
                Route: {b_route['route_name']} ({b_route['distance_km']} km)
                Carrier: {b_carrier['name']} (INR {b_cost['total_cost_inr']:,})
                ETA: {b_cost['estimated_transit_hours']} hrs
                Status: {status_code}
                """
                resp = client.models.generate_content(model=MODEL_NAME, contents=prompt)
                structured_output["ai_logistics_brief"] = resp.text.strip()
            except Exception:
                pass

        return structured_output


# ==============================================================================
# STANDALONE DEMO & TEST RUNNER
# ==============================================================================
if __name__ == "__main__":
    print("=" * 75)
    print("INTRA-STATE LOGISTICS AGENT (Google ADK & Gemini 3.1 Flash)")
    print("Corridor Routing, Carrier Cost Optimization & Blockade Rerouting")
    print("=" * 75)

    agent_controller = IntraStateLogisticsAgent()

    # --------------------------------------------------------------------------
    # Scenario 1: Normal Transfer Request (Kanpur -> Agra, 1020 belts)
    # --------------------------------------------------------------------------
    print("\n[Scenario 1] Normal Transfer Request (Kanpur -> Agra, 1020 belts)...")
    reset_blocked_routes()

    plan_1 = agent_controller.plan_transfer(
        origin="Kanpur",
        destination="Agra",
        product="belts",
        quantity=1020.0,
        urgency="normal"
    )

    clean_json_1 = {
        "status": plan_1["status"],
        "origin": plan_1["origin"],
        "destination": plan_1["destination"],
        "product": plan_1["product"],
        "quantity": plan_1["quantity"],
        "best_route": plan_1["best_route"],
        "carrier": plan_1["carrier"],
        "cost_inr": plan_1["cost_inr"],
        "eta_hours": plan_1["eta_hours"],
        "decision_rationale": plan_1["decision_rationale"]
    }
    print(json.dumps(clean_json_1, indent=2))

    # --------------------------------------------------------------------------
    # Scenario 2: Main Route Blockade (Block LANE-03: Agra-Lucknow Expressway)
    # --------------------------------------------------------------------------
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

    clean_json_2 = {
        "status": plan_2["status"],
        "origin": plan_2["origin"],
        "destination": plan_2["destination"],
        "product": plan_2["product"],
        "quantity": plan_2["quantity"],
        "best_route": plan_2["best_route"],
        "carrier": plan_2["carrier"],
        "cost_inr": plan_2["cost_inr"],
        "eta_hours": plan_2["eta_hours"],
        "decision_rationale": plan_2["decision_rationale"]
    }
    print(json.dumps(clean_json_2, indent=2))

    # Reset clean state
    reset_blocked_routes()

    print("\n" + "=" * 75)
    print("RUN WITH GOOGLE ADK CLI:")
    print("  python -m google.adk.cli run agents/logistics_agent \"Find best route from Kanpur to Agra for 1020 belts\" --in_memory")
    print("=" * 75)
