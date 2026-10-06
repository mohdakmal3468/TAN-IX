"""
agents/inventory_agent.py
-------------------------
District Inventory Agent for the Uttar Pradesh Leather Supply Chain.
Built with Google ADK (Agent Development Kit) and Gemini 3.1 Flash.

Responsibilities:
1. Monitor warehouse stock, daily burn rates, and reorder points.
2. Raise structured stockout alerts when inventory is below safety thresholds.
3. Suggest inter-district stock rebalancing transfers from donor hubs with surplus.
4. Outputs strictly structured JSON with fields: alerts[], transfer_requests[].
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
from tools.inventory_tools import (
    get_stock_level,
    days_of_stock_left,
    list_below_reorder_point,
    find_surplus_districts
)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# ==============================================================================
# AGENT INSTRUCTION (Job Description & Behavioral Rules)
# ==============================================================================
INSTRUCTION = """
You are the District Inventory Agent for the Uttar Pradesh Leather Supply Chain (Kanpur, Unnao, Agra, Noida).

YOUR CORE RESPONSIBILITIES:
1. Continuously monitor physical inventory levels, daily consumption burn rates, and safety reorder points across warehouses.
2. When investigating a district or alert (such as "Agra is low on belts"):
   - Call `get_stock_level(district, product)` to verify physical balance.
   - Call `days_of_stock_left(district, product)` to evaluate remaining production runway.
   - Call `list_below_reorder_point(district)` to audit all commodities requiring replenishment.
3. If any product is below its reorder point:
   - Formulate a stockout alert in `alerts[]`.
   - Call `find_surplus_districts(product, min_surplus=0)` to locate viable donor clusters holding excess stock.
   - Propose an inter-district replenishment transfer in `transfer_requests[]` matching origin (donor) to destination (deficit hub).

STRICT OUTPUT REQUIREMENT:
You must return valid structured JSON matching this exact schema:
{
  "alerts": [
    {
      "district": "string",
      "product": "string",
      "current_quantity": float,
      "reorder_point": float,
      "deficit": float,
      "days_left": float,
      "severity": "CRITICAL | WARNING",
      "message": "string"
    }
  ],
  "transfer_requests": [
    {
      "origin": "string",
      "destination": "string",
      "product": "string",
      "quantity": float,
      "unit": "string",
      "urgency": "HIGH | MEDIUM | LOW",
      "reason": "string"
    }
  ]
}
"""

# ==============================================================================
# GOOGLE ADK AGENT DEFINITION
# ==============================================================================
agent = Agent(
    name="district_inventory_agent",
    model=MODEL_NAME,
    description="Monitors UP leather district warehouses, detects stockouts, and suggests inter-district inventory transfers.",
    instruction=INSTRUCTION,
    tools=[
        get_stock_level,
        days_of_stock_left,
        list_below_reorder_point,
        find_surplus_districts
    ]
)

root_agent = agent


# ==============================================================================
# CALLABLE AGENT CLASS (For Orchestrator & Programmatic Invocations)
# ==============================================================================
class DistrictInventoryAgent:
    """
    District Inventory Agent controller for the multi-agent system.
    Supports LLM-augmented evaluation via Gemini and deterministic tool synthesis.
    """

    def __init__(self):
        self.name = "District Inventory Agent"
        self.role = "Monitor stock levels, burn rates, and formulate transfer requests."
        self.adk_agent = agent

    def analyze_inventory(self, target_district: Optional[str] = None) -> Dict[str, Any]:
        """
        Audits warehouses, runs tool evaluations, and returns structured JSON:
        {
            "alerts": [...],
            "transfer_requests": [...]
        }
        """
        districts_to_scan = [target_district.capitalize()] if target_district else ["Agra", "Kanpur", "Unnao", "Noida"]

        alerts = []
        transfer_requests = []

        # Step 1: Scan for deficits using inventory tools
        for district in districts_to_scan:
            deficits = list_below_reorder_point(district)
            for d in deficits:
                product = d["product"]
                days = days_of_stock_left(district, product)
                alert_item = {
                    "district": district,
                    "cluster": district,
                    "product": product,
                    "item": product,
                    "current_quantity": d["current_quantity"],
                    "reorder_point": d["reorder_point"],
                    "deficit": d["deficit"],
                    "days_left": days,
                    "unit": d["unit"],
                    "severity": "CRITICAL" if days < 3.0 or d["deficit"] > 800 else "WARNING",
                    "message": f"Inventory for {product} in {district} is below reorder point ({d['current_quantity']} / {d['reorder_point']} {d['unit']}). Estimated runway: {days} days."
                }
                alerts.append(alert_item)

                # Step 2: Find donor districts with surplus for this product
                donors = find_surplus_districts(product, min_surplus=d["deficit"] * 0.5)
                # Filter out the deficit district itself
                eligible_donors = [donor for donor in donors if donor["district"].capitalize() != district]

                if eligible_donors:
                    best_donor = eligible_donors[0]
                    transfer_qty = min(d["deficit"], best_donor["available_surplus"])

                    transfer_requests.append({
                        "origin": best_donor["district"],
                        "destination": district,
                        "product": product,
                        "quantity": transfer_qty,
                        "unit": d["unit"],
                        "urgency": "HIGH" if alert_item["severity"] == "CRITICAL" else "MEDIUM",
                        "reason": (
                            f"Replenish {district} {product} deficit of {transfer_qty} {d['unit']} "
                            f"from {best_donor['district']} surplus buffer ({best_donor['current_quantity']} on hand)."
                        )
                    })

        result = {
            "agent": self.name,
            "status": "ACTION_REQUIRED" if alerts else "HEALTHY",
            "alerts": alerts,
            "transfer_requests": transfer_requests,
            # Backwards-compatible fields for state orchestrator
            "critical_deficits": alerts,
            "available_surpluses": [
                {
                    "cluster": t["origin"],
                    "item": t["product"],
                    "quantity": t["quantity"],
                    "unit": t["unit"]
                }
                for t in transfer_requests
            ],
            "critical_deficits_count": len(alerts)
        }

        # If live Gemini API key is configured, enrich with AI reasoning brief
        if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
            try:
                from google import genai
                client = genai.Client(api_key=GEMINI_API_KEY)
                prompt = f"""
                You are the District Inventory Agent. Based on the following audited data:
                Alerts: {alerts}
                Transfer Requests: {transfer_requests}
                Provide a 2-sentence executive briefing summarizing the stockout risk and recommended replenishment.
                """
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt
                )
                result["ai_executive_brief"] = response.text.strip()
            except Exception as e:
                result["ai_executive_brief"] = (
                    f"Heuristic Brief: Flagged {len(alerts)} stockout alerts. "
                    f"Proposing inter-district replenishment from surplus donor hubs."
                )
        else:
            result["ai_executive_brief"] = (
                f"Heuristic Brief: Flagged {len(alerts)} stockout alerts. "
                f"Proposing inter-district replenishment from surplus donor hubs."
            )

        return result


# ==============================================================================
# STANDALONE DEMO RUNNER
# ==============================================================================
if __name__ == "__main__":
    print("=" * 75)
    print("DISTRICT INVENTORY AGENT (Google ADK & Gemini 3.1 Flash)")
    print("Scenario: 'Agra is low on belts'")
    print("=" * 75)

    agent_controller = DistrictInventoryAgent()
    output = agent_controller.analyze_inventory(target_district="Agra")

    # Display clean structured JSON
    filtered_json = {
        "alerts": output["alerts"],
        "transfer_requests": output["transfer_requests"]
    }

    print("\n[Structured JSON Output]:")
    print(json.dumps(filtered_json, indent=2))

    print("\n[AI Executive Brief]:")
    print(output.get("ai_executive_brief", ""))

    print("\n" + "=" * 75)
    print("RUN WITH GOOGLE ADK CLI:")
    print("  python -m google.adk.cli run agents/inventory_agent \"Agra is low on belts\" --in_memory")
    print("=" * 75)
