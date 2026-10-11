"""
agents/inventory_agent.py
-------------------------
District Inventory Agent for the Uttar Pradesh Leather Supply Chain.
Built with Google ADK (Agent Development Kit) and Gemini.

Responsibilities:
1. Monitor warehouse stock, daily burn rates, and reorder points.
2. Raise structured stockout alerts when inventory is below safety thresholds.
3. Suggest inter-district stock rebalancing transfers from donor hubs with surplus.
4. Outputs strictly structured JSON with fields: alerts[], transfer_requests[].
"""

import os
import sys
import json
from typing import Dict, Any, Optional
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
from tools.llm import ask_gemini, MODEL_NAME

ALL_DISTRICTS = ["Agra", "Kanpur", "Unnao", "Noida"]


# ==============================================================================
# AGENT INSTRUCTION (Job Description & Behavioral Rules)
# ==============================================================================
INSTRUCTION = """
You are the District Inventory Agent for the Uttar Pradesh Leather Supply Chain (Kanpur, Unnao, Agra, Noida).

YOUR CORE RESPONSIBILITIES:
1. Continuously monitor physical inventory levels, daily consumption burn rates, and safety reorder points across warehouses.
2. When investigating a district or alert (such as "Agra is low on belts"):
   - Call `get_stock_level(district, product)` to verify physical balance and runway.
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
# TOOLSET INITIALIZATION
# ==============================================================================
def get_agent_tools():
    """Returns the toolset for the inventory agent."""
    return [
        get_stock_level,
        days_of_stock_left,
        list_below_reorder_point,
        find_surplus_districts
    ]


# ==============================================================================
# GOOGLE ADK AGENT DEFINITION
# ==============================================================================
agent = Agent(
    name="district_inventory_agent",
    model=MODEL_NAME,
    description="Monitors UP leather district warehouses, detects stockouts, and suggests inter-district inventory transfers.",
    instruction=INSTRUCTION,
    tools=get_agent_tools()
)

root_agent = agent


# ==============================================================================
# CALLABLE AGENT CLASS (For Orchestrator & Programmatic Invocations)
# ==============================================================================
class DistrictInventoryAgent:
    """
    District Inventory Agent controller for the multi-agent system.
    Deterministic tools make the decisions; Gemini writes the executive brief.
    """

    def __init__(self):
        self.name = "District Inventory Agent"
        self.role = "Monitor stock levels, burn rates, and formulate transfer requests."
        self.adk_agent = agent

    def fetch_stock(self, district: str, product: str) -> Dict[str, Any]:
        """Fetches stock level directly from inventory tools."""
        return get_stock_level(district=district, product=product)

    @staticmethod
    def _build_alert(d: Dict[str, Any]) -> Dict[str, Any]:
        """Turns one deficit row from the tools into a stockout alert."""
        days = d["days_left"]
        return {
            "district": d["district"],
            "cluster": d["district"],
            "product": d["product"],
            "item": d["product"],
            "current_quantity": d["current_quantity"],
            "reorder_point": d["reorder_point"],
            "deficit": d["deficit"],
            "days_left": days,
            "unit": d["unit"],
            "severity": "CRITICAL" if days < 3.0 or d["deficit"] > 800 else "WARNING",
            "message": (
                f"Inventory for {d['product']} in {d['district']} is below reorder point "
                f"({d['current_quantity']} / {d['reorder_point']} {d['unit']}). "
                f"Estimated runway: {days} days."
            ),
        }

    @staticmethod
    def _build_transfer(alert: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Finds the best donor district for an alert. Returns None when nobody has surplus."""
        district, product = alert["district"], alert["product"]
        donors = find_surplus_districts(product=product, min_surplus=alert["deficit"] * 0.5)
        try:
            # Donors come sorted by surplus (largest first); skip the deficit district itself
            donor = next(x for x in donors if x["district"].capitalize() != district)
        except StopIteration:
            return None

        quantity = min(alert["deficit"], donor["available_surplus"])
        return {
            "origin": donor["district"],
            "destination": district,
            "product": product,
            "quantity": quantity,
            "unit": alert["unit"],
            "urgency": "HIGH" if alert["severity"] == "CRITICAL" else "MEDIUM",
            "reason": (
                f"Replenish {district} {product} deficit of {quantity} {alert['unit']} "
                f"from {donor['district']} surplus buffer ({donor['current_quantity']} on hand)."
            ),
        }

    def analyze_inventory(self, target_district: Optional[str] = None) -> Dict[str, Any]:
        """
        Audits warehouses, runs tool evaluations, and returns structured JSON:
        {
            "alerts": [...],
            "transfer_requests": [...]
        }
        """
        districts = [target_district.capitalize()] if target_district else ALL_DISTRICTS

        alerts = []
        transfer_requests = []

        for district in districts:
            deficits = list_below_reorder_point(district=district)
            for d in deficits:
                alert = self._build_alert(d)
                alerts.append(alert)
                transfer = self._build_transfer(alert)
                if transfer:
                    transfer_requests.append(transfer)

        prompt = f"""
        You are the District Inventory Agent. Based on the following audited data:
        Alerts: {alerts}
        Transfer Requests: {transfer_requests}
        Provide a 2-sentence executive briefing summarizing the stockout risk and recommended replenishment.
        """

        return {
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
            "critical_deficits_count": len(alerts),
            "ai_executive_brief": ask_gemini(prompt),
        }


# ==============================================================================
# STANDALONE DEMO RUNNER
# ==============================================================================
if __name__ == "__main__":
    print("=" * 75)
    print(f"DISTRICT INVENTORY AGENT (Google ADK & {MODEL_NAME})")
    print("Scenario: 'Agra is low on belts'")
    print("=" * 75)

    agent_controller = DistrictInventoryAgent()
    stock = agent_controller.fetch_stock("Agra", "belts")
    print(f"\nAgra belts: {stock['quantity']} {stock['unit']}")

    print("\nRunning full warehouse audit...")
    out = agent_controller.analyze_inventory(target_district="Agra")
    print(json.dumps({
        "alerts": out["alerts"],
        "transfer_requests": out["transfer_requests"],
        "ai_executive_brief": out["ai_executive_brief"],
    }, indent=2))