"""
agents/orchestrator.py
----------------------
State Master Orchestrator for the Uttar Pradesh Leather Supply Chain.

Responsibilities:
1. Directs the Multi-Agent team:
   - District Inventory Agent (live stock & deficits)
   - Regional Risk Agent (NGT notices, floods, policy vector search)
   - Intra-State Logistics Agent (expressways, freight rates, fleet)
2. Synthesizes data into an actionable State Rebalancing Plan.
3. Enforces Human-in-the-Loop (HITL) governance via Discord Webhook.
4. Executes stock movement across Firestore upon authorized human approval.
"""

from typing import Dict, Any, List
from agents.inventory_agent import DistrictInventoryAgent
from agents.risk_agent import RegionalRiskAgent
from agents.logistics_agent import IntraStateLogisticsAgent
from tools.discord_tools import send_discord_approval_request, record_approval_decision, PENDING_APPROVALS
from tools.firestore_tools import update_cluster_inventory
from tools.vector_tools import search_policy_docs
from config import GEMINI_API_KEY, GEMINI_MODEL


class StateMasterOrchestrator:
    """
    Master coordination agent synthesizing supply chain risks, logistics routes,
    and inventory replenishment with human authorization.
    """

    def __init__(self):
        self.name = "State Master Orchestrator"
        self.inventory_agent = DistrictInventoryAgent()
        self.risk_agent = RegionalRiskAgent()
        self.logistics_agent = IntraStateLogisticsAgent()
        self.execution_history: List[Dict[str, Any]] = []

    def run_state_assessment(self) -> Dict[str, Any]:
        """
        Executes a complete multi-agent cycle:
        1. Checks inventory levels and shortages.
        2. Evaluates regional risks across UP corridors.
        3. Generates optimal logistics recommendations if rebalancing is required.
        4. Triggers Human-in-the-Loop approval via Discord if critical action is needed.
        """
        # Step 1: Query Specialist Agents
        inventory_report = self.inventory_agent.analyze_inventory()
        risk_report = self.risk_agent.assess_all_clusters()

        deficits = inventory_report.get("critical_deficits", [])
        surpluses = inventory_report.get("available_surpluses", [])

        proposed_plans = []

        # Step 2: Formulate Rebalancing Strategy
        if deficits:
            # Match top deficit to available surplus
            top_deficit = deficits[0]
            target_cluster = top_deficit["cluster"]
            needed_qty = top_deficit["deficit"]

            # Look for suitable donor cluster with surplus or normal buffer
            donor_cluster = "Kanpur" if target_cluster != "Kanpur" else "Unnao"
            donor_item = "Finished Cowhide"

            # Check if donor has surplus
            for s in surpluses:
                if s["cluster"] != target_cluster:
                    donor_cluster = s["cluster"]
                    donor_item = s["item"]
                    break

            # Step 3: Consult Logistics Agent for Route Optimization
            logistics_plan = self.logistics_agent.plan_transfer(
                origin=donor_cluster,
                destination=target_cluster,
                required_sqft=needed_qty,
                urgency="urgent" if top_deficit.get("severity") == "CRITICAL" else "normal"
            )

            # Step 4: Check ODOP Policy for Freight Subsidy via Vector Search
            policy_matches = search_policy_docs("ODOP leather goods freight subsidy inter-cluster transfer")
            subsidy_note = "Eligible for 15% UP ODOP freight rebate" if policy_matches else "Standard state tariff"

            # Step 5: Construct Master Plan
            plan_id = f"PLAN-UP-{len(self.execution_history) + 1:04d}"
            est_cost = logistics_plan["route"]["total_estimated_cost_inr"]

            master_plan = {
                "plan_id": plan_id,
                "action": "INTER_CLUSTER_STOCK_REBALANCE",
                "origin": donor_cluster,
                "destination": target_cluster,
                "item": donor_item,
                "quantity": needed_qty,
                "estimated_cost_inr": est_cost,
                "transit_hours": logistics_plan["route"]["estimated_transit_hours"],
                "route_name": logistics_plan["route"]["route_name"],
                "policy_incentive": subsidy_note,
                "risk_justification": (
                    f"Replenish critical deficit in {target_cluster} ({top_deficit['item']}: {top_deficit['current_quantity']} remaining). "
                    f"Proactively safeguards against potential production halt amid regional environmental warnings."
                ),
                "logistics_details": logistics_plan,
                "approval_status": "PENDING"
            }

            # Step 6: Dispatch to Discord for Human-in-the-Loop Approval
            discord_dispatch = send_discord_approval_request(master_plan)
            master_plan["discord_dispatch"] = discord_dispatch
            proposed_plans.append(master_plan)

        # Step 7: Formulate AI Orchestrator Executive Synthesis
        ai_synthesis = self._generate_orchestrator_brief(inventory_report, risk_report, proposed_plans)

        cycle_result = {
            "orchestrator": self.name,
            "system_status": "CRITICAL_ACTION_PENDING_APPROVAL" if proposed_plans else "ALL_SYSTEMS_STABLE",
            "inventory_report": inventory_report,
            "risk_report": risk_report,
            "proposed_rebalance_plans": proposed_plans,
            "orchestrator_synthesis": ai_synthesis
        }

        return cycle_result

    def execute_approved_plan(self, plan_id: str) -> Dict[str, Any]:
        """
        Executes an approved plan by updating live inventory in the data store.
        """
        decision = record_approval_decision(plan_id, "approve")
        if not decision.get("success"):
            return decision

        plan = decision["plan"]
        origin = plan["origin"]
        destination = plan["destination"]
        item = plan["item"]
        qty = plan["quantity"]

        # Deduct from donor warehouse
        deduct_res = update_cluster_inventory(origin, item, -qty)
        # Add to recipient warehouse
        add_res = update_cluster_inventory(destination, item, qty)

        execution_record = {
            "plan_id": plan_id,
            "execution_status": "COMPLETED",
            "donor_update": deduct_res,
            "recipient_update": add_res,
            "summary": f"Dispatched {qty} units of {item} from {origin} to {destination}."
        }
        self.execution_history.append(execution_record)
        return execution_record

    def _generate_orchestrator_brief(self, inv_report: dict, risk_report: dict, plans: list) -> str:
        """Helper to create an executive summary using Gemini or heuristic template."""
        if GEMINI_API_KEY:
            try:
                from google import genai
                client = genai.Client(api_key=GEMINI_API_KEY)
                prompt = f"""
                You are the State Master Orchestrator for the Uttar Pradesh Leather Supply Chain.
                Synthesize the state of the supply chain in 3 concise bullet points:
                - Inventory health across Kanpur, Unnao, Agra, Noida: {inv_report.get('status')}
                - Regional risk alerts: {risk_report.get('system_threat_level')}
                - Proposed rebalancing action: {plans[0] if plans else 'No action required'}
                """
                resp = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt
                )
                return resp.text
            except Exception:
                pass

        if plans:
            p = plans[0]
            return (
                f"• Strategic Rebalancing Proposed: Transfer {p['quantity']} units of {p['item']} from {p['origin']} to {p['destination']}.\n"
                f"• Logistics Route: {p['route_name']} (~{p['transit_hours']} hrs, ₹{p['estimated_cost_inr']:,}).\n"
                f"• Human Governance: High-priority approval card sent via Discord webhook. Awaiting authorization."
            )
        return "• All clusters operating within nominal inventory thresholds. No emergency dispatch required."
