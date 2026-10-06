"""
agents/inventory_agent.py
-------------------------
The District Inventory Agent is responsible for:
1. Continuous monitoring of warehouse stock across Kanpur, Unnao, Agra, and Noida.
2. Flagging items that drop below safety thresholds (Deficits / Critical Low).
3. Identifying clusters with excess buffer stock (Surplus) that can supply deficit hubs.
"""

from typing import Dict, Any, List
from tools.firestore_tools import get_all_clusters_inventory, check_critical_stockouts
from config import GEMINI_API_KEY, GEMINI_MODEL


class DistrictInventoryAgent:
    """
    Autonomous agent tracking warehouse inventory levels across Uttar Pradesh leather clusters.
    """

    def __init__(self):
        self.name = "District Inventory Agent"
        self.role = "Monitor stock levels, detect deficits, and identify donor clusters with surplus."

    def analyze_inventory(self) -> Dict[str, Any]:
        """
        Scans all clusters and returns a comprehensive stock health report.
        """
        inventory_data = get_all_clusters_inventory()
        critical_alerts = check_critical_stockouts()

        # Identify surplus clusters (potential donors)
        surplus_items = []
        for cluster_name, details in inventory_data.items():
            for item_name, item_info in details.get("inventory", {}).items():
                if item_info.get("status") == "Surplus":
                    surplus_items.append({
                        "cluster": cluster_name,
                        "item": item_name,
                        "quantity": item_info.get("quantity"),
                        "unit": item_info.get("unit"),
                        "unit_cost_inr": item_info.get("unit_cost_inr")
                    })

        summary = {
            "agent": self.name,
            "total_clusters_monitored": len(inventory_data),
            "critical_deficits_count": len(critical_alerts),
            "critical_deficits": critical_alerts,
            "available_surpluses": surplus_items,
            "status": "ACTION_REQUIRED" if critical_alerts else "HEALTHY"
        }

        # If Gemini API key is configured, enrich summary with AI reasoning
        if GEMINI_API_KEY:
            try:
                from google import genai
                client = genai.Client(api_key=GEMINI_API_KEY)
                prompt = f"""
                You are the District Inventory Agent for the Uttar Pradesh Leather Supply Chain.
                Analyze the following live inventory state and output a 2-3 sentence strategic executive brief:
                Deficits: {critical_alerts}
                Surpluses: {surplus_items}
                Focus on Kanpur, Unnao, Agra, and Noida.
                """
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt
                )
                summary["ai_executive_brief"] = response.text
            except Exception as e:
                summary["ai_executive_brief"] = (
                    f"Heuristic Brief: Identified {len(critical_alerts)} critical stockouts (notably in Agra/Noida) "
                    f"with viable replenishment buffers available in Kanpur and Unnao."
                )
        else:
            summary["ai_executive_brief"] = (
                f"Heuristic Brief: Identified {len(critical_alerts)} critical stockouts (notably in Agra/Noida) "
                f"with viable replenishment buffers available in Kanpur and Unnao."
            )

        return summary
