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
5. Supports Model Context Protocol (MCP) toolset via USE_MCP=true/false environment flag.
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

# Check MCP toggle flag (default: false fallback to direct database)
USE_MCP = os.getenv("USE_MCP", "false").lower() in ("true", "1", "yes")

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
# TOOLSET INITIALIZATION (MCP vs Direct Database Fallback)
# ==============================================================================
def get_agent_tools():
    """Initializes ADK agent tools based on the USE_MCP environment flag."""
    if os.getenv("USE_MCP", "false").lower() in ("true", "1", "yes"):
        try:
            from tools.mcp_server import get_mcp_toolset
            return [get_mcp_toolset()]
        except Exception as e:
            print(f"[Inventory Agent Warning] MCP initialization note: {e}. Falling back to direct tools.")

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
    Supports LLM-augmented evaluation via Gemini and deterministic tool synthesis.
    Switches between MCP server execution and direct database fallback via USE_MCP.
    """

    def __init__(self):
        self.name = "District Inventory Agent"
        self.role = "Monitor stock levels, burn rates, and formulate transfer requests."
        self.adk_agent = agent

    def fetch_stock(self, district: str, product: str) -> Dict[str, Any]:
        """Fetches stock level via MCP if USE_MCP=true, otherwise uses direct database tools."""
        use_mcp = os.getenv("USE_MCP", "false").lower() in ("true", "1", "yes")
        if use_mcp:
            from tools.mcp_server import call_mcp_tool
            res = call_mcp_tool("get_stock_level", district=district, product=product)
            res["source"] = "MCP_SERVER"
            return res
        res = get_stock_level(district=district, product=product)
        res["source"] = "DIRECT_DATABASE"
        return res

    def analyze_inventory(self, target_district: Optional[str] = None) -> Dict[str, Any]:
        """
        Audits warehouses, runs tool evaluations, and returns structured JSON:
        {
            "alerts": [...],
            "transfer_requests": [...]
        }
        """
        districts_to_scan = [target_district.capitalize()] if target_district else ["Agra", "Kanpur", "Unnao", "Noida"]
        use_mcp = os.getenv("USE_MCP", "false").lower() in ("true", "1", "yes")

        alerts = []
        transfer_requests = []

        # Step 1: Scan for deficits using inventory tools (MCP or Direct)
        for district in districts_to_scan:
            if use_mcp:
                from tools.mcp_server import call_mcp_tool
                deficits = call_mcp_tool("list_below_reorder_point", district=district)
            else:
                deficits = list_below_reorder_point(district)

            for d in deficits:
                product = d["product"]
                days = d.get("days_left") or days_of_stock_left(district, product)
                alert_item = {
                    "district": district,
                    "cluster": district,
                    "product": product,
                    "item": product,
                    "current_quantity": d.get("current_quantity", d.get("quantity", 0)),
                    "reorder_point": d["reorder_point"],
                    "deficit": d["deficit"],
                    "days_left": days,
                    "unit": d.get("unit", "units"),
                    "severity": "CRITICAL" if days < 3.0 or d["deficit"] > 800 else "WARNING",
                    "message": f"Inventory for {product} in {district} is below reorder point ({d.get('current_quantity', d.get('quantity', 0))} / {d['reorder_point']} {d.get('unit', 'units')}). Estimated runway: {days} days."
                }
                alerts.append(alert_item)

                # Step 2: Find donor districts with surplus for this product
                if use_mcp:
                    from tools.mcp_server import call_mcp_tool
                    donors = call_mcp_tool("find_surplus_districts", product=product, min_surplus=d["deficit"] * 0.5)
                else:
                    donors = find_surplus_districts(product, min_surplus=d["deficit"] * 0.5)

                # Filter out the deficit district itself
                eligible_donors = [donor for donor in donors if donor["district"].capitalize() != district]

                if eligible_donors:
                    best_donor = eligible_donors[0]
                    donor_surplus = best_donor.get("surplus_available", best_donor.get("available_surplus", 0))
                    donor_curr = best_donor.get("current_quantity", 0)
                    transfer_qty = min(d["deficit"], donor_surplus)

                    transfer_requests.append({
                        "origin": best_donor["district"],
                        "destination": district,
                        "product": product,
                        "quantity": transfer_qty,
                        "unit": d.get("unit", "units"),
                        "urgency": "HIGH" if alert_item["severity"] == "CRITICAL" else "MEDIUM",
                        "reason": (
                            f"Replenish {district} {product} deficit of {transfer_qty} {d.get('unit', 'units')} "
                            f"from {best_donor['district']} surplus buffer ({donor_curr} on hand)."
                        )
                    })

        result = {
            "agent": self.name,
            "status": "ACTION_REQUIRED" if alerts else "HEALTHY",
            "execution_mode": "MCP_TOOLSET" if use_mcp else "DIRECT_DATABASE",
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

    # Test 1: Fetch stock via Direct Database Fallback (USE_MCP=False)
    print("\n[Test 1] Direct Database Mode (USE_MCP=False)...")
    os.environ["USE_MCP"] = "false"
    stock_direct = agent_controller.fetch_stock("Agra", "belts")
    print(f"  Source: {stock_direct.get('source')} | Agra Belts Quantity: {stock_direct.get('quantity')} {stock_direct.get('unit')}")

    # Test 2: Fetch stock via MCP Tool (USE_MCP=True)
    print("\n[Test 2] Model Context Protocol Mode (USE_MCP=True)...")
    os.environ["USE_MCP"] = "true"
    stock_mcp = agent_controller.fetch_stock("Agra", "belts")
    print(f"  Source: {stock_mcp.get('source')} | Agra Belts Quantity: {stock_mcp.get('quantity')} {stock_mcp.get('unit')} (Reorder Point: {stock_mcp.get('reorder_point')})")

    # Run full inventory analysis via MCP
    print("\nRunning Full Warehouse Audit via MCP...")
    output_mcp = agent_controller.analyze_inventory(target_district="Agra")

    filtered_json = {
        "execution_mode": output_mcp["execution_mode"],
        "alerts": output_mcp["alerts"],
        "transfer_requests": output_mcp["transfer_requests"]
    }
    print(json.dumps(filtered_json, indent=2))

    # Reset clean environment
    os.environ["USE_MCP"] = "false"

    print("\n" + "=" * 75)
    print("RUN WITH GOOGLE ADK CLI:")
    print("  python -m google.adk.cli run agents/inventory_agent \"Agra is low on belts\" --in_memory")
    print("=" * 75)
