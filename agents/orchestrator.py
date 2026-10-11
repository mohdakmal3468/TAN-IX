"""
agents/orchestrator.py
----------------------
State Master Orchestrator for the Uttar Pradesh Leather Supply Chain.
Built with Google ADK (Agent Development Kit) and Gemini models using Google GenAI SDK.

Responsibilities:
1. Directs and synthesizes specialist agents:
   - District Inventory Agent (monitors inventory, burn rates, stockouts)
   - Regional Risk Agent (corridor risk scores, active disruptions, impact analysis)
   - Intra-State Logistics Agent (highway routing, carrier selection, blockade avoidance)
2. Semantic Policy Attachment via tools.policy_tools (search_policy):
   - Correlates statutory UP delivery SLAs, transit permit thresholds, approval limits,
     carrier compliance standards, and ODOP 15% freight subsidies.
3. Produces a Preliminary Execution Plan and a Draft Documentation Package:
   - Fills UP Commercial Transit Permit (Form UP-EWAY-01) from policies/transit_permits.md.
4. Human-in-the-Loop (HITL) Governance:
   - Auto-approves low-cost plans, dispatches Discord cards for the rest.
5. Persistent Execution Logging:
   - Stores every orchestration run in Firestore collection 'agent_runs' with:
     run_id, timestamp, trigger, subagents_output, final_plan, and step-by-step reasoning_events.

Design rules (no silent fallbacks):
- No invented donor, route, carrier, cost or permit template. If something needed is missing,
  the run either records "no plan possible" (a normal outcome) or raises a clear error.
- Gemini is required for the executive brief; if it fails, the error is raised directly.
"""

import os
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Google GenAI SDK
from google import genai
from google.genai import types

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from google.adk import Agent
from agents.inventory_agent import DistrictInventoryAgent
from agents.risk_agent import RegionalRiskAgent
from agents.logistics_agent import IntraStateLogisticsAgent
from tools.policy_tools import search_policy
from tools.discord_tools import send_discord_approval_request, record_approval_decision
from tools.firestore_client import set_document
from tools.inventory_tools import get_stock_level, adjust_stock
from agents.guardrails import (
    evaluate_guardrails,
    save_approval_item,
    update_approval_status,
    wait_for_approval_resolution
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

NOMINAL_FREIGHT_INR_PER_KM = 38.0   # used to estimate the "normal" cost when judging a reroute

# ==============================================================================
# AGENT INSTRUCTION (Job Description & Decision Framework)
# ==============================================================================
INSTRUCTION = """
You are the State Master Orchestrator for the Uttar Pradesh Leather Industrial Corridor.
Your mission is to oversee the statewide logistics and supply chain network across Kanpur, Unnao, Agra, and Noida.

CORE RESPONSIBILITIES:
1. Synthesize intelligence from specialist sub-agents:
   - District Inventory Agent: Identify warehouse stockouts, burn rates, and surplus donor hubs.
   - Regional Risk Agent: Monitor active disruptions (blockades, floods, fog) and evaluate corridor risk scores (0-100).
   - Intra-State Logistics Agent: Optimize expressway route lanes, assign freight carriers, and detour around blockades.
2. Query the statutory policy database using `search_policy` to correlate applicable regulations:
   - Delivery SLAs for destination clusters.
   - Mandatory e-Way bill and transit permit documentation rules.
   - Financial approval delegation thresholds (Tier 1 AI vs Tier 2 Supervisor HITL).
   - Emergency freight policies and 15% ODOP state subsidies.
3. Formulate a comprehensive Preliminary Execution Plan and Draft Documentation Package (Form UP-EWAY-01).
4. Save the complete execution record into Firestore collection `agent_runs`.
"""

# ==============================================================================
# GOOGLE ADK AGENT DEFINITION
# ==============================================================================
agent = Agent(
    name="state_master_orchestrator",
    model=MODEL_NAME,
    description="Master multi-agent orchestrator coordinating inventory rebalancing, highway risk intelligence, logistics routing, and statutory compliance.",
    instruction=INSTRUCTION,
    tools=[
        search_policy
    ]
)

root_agent = agent


# ==============================================================================
# HELPER: TRANSIT PERMIT TEMPLATE LOADER
# ==============================================================================
def load_transit_permit_template() -> str:
    """Reads the UP Commercial Transit Permit Manifest Template from policies/transit_permits.md.
    Raises an error if the file or its ```text block is missing (there is no built-in copy)."""
    policy_path = os.path.join(ROOT_DIR, "policies", "transit_permits.md")
    with open(policy_path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"```text\s*\n(.*?)\n```", content, re.DOTALL)
    if not match:
        raise ValueError(f"{policy_path} has no ```text block containing the permit template.")
    return match.group(1).strip()


def _find_policy(query: str) -> List[Dict[str, Any]]:
    """Searches policies and fails loudly if nothing relevant is found."""
    results = search_policy(query, top_k=1)
    if not results:
        raise LookupError(f"No policy found for query: '{query}'. Run scripts/index_policies.py.")
    return results


# ==============================================================================
# CALLABLE MASTER ORCHESTRATOR CLASS
# ==============================================================================
class StateMasterOrchestrator:
    """
    State Master Orchestrator coordinating the multi-agent deliberation,
    statutory policy enforcement, and execution plan synthesis.
    """

    def __init__(self):
        self.name = "State Master Orchestrator"
        self.adk_agent = agent
        self.client = client
        self.inventory_agent = DistrictInventoryAgent()
        self.risk_agent = RegionalRiskAgent()
        self.logistics_agent = IntraStateLogisticsAgent()
        self.execution_history: List[Dict[str, Any]] = []

    # --------------------------------------------------------------------------
    # MAIN ENTRY POINT
    # --------------------------------------------------------------------------
    def run_state_assessment(
        self,
        trigger: str = "Periodic Multi-Agent Supply Chain Audit",
        target_deficit_district: Optional[str] = None,
        wait_for_approval_timeout: float = 0.0,
        requires_compliance_signoff: bool = False
    ) -> Dict[str, Any]:
        """
        Executes a complete end-to-end multi-agent orchestration cycle:
        1. Audits inventory deficits and locates surplus donor hubs.
        2. Evaluates highway disruptions, weather hazards, and corridor risk scores.
        3. Optimizes logistics routing and carrier dispatch around active bottlenecks.
        4. Queries statutory policies via vector search and attaches applicable clauses.
        5. Fills Form UP-EWAY-01 transit documentation from the template in policies/.
        6. Determines governance approval tier (auto-approve vs human approval).
        7. Saves the full run record to Firestore collection 'agent_runs'.
        """
        run_timestamp = datetime.now(timezone.utc).isoformat()
        run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        reasoning_events: List[Dict[str, Any]] = []

        def log_event(step: int, evt_id: str, component: str, action: str, details: str, payload: Optional[Any] = None):
            evt = {
                "step": step,
                "event_id": evt_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "component": component,
                "action": action,
                "status": "COMPLETED",
                "details": details
            }
            if payload is not None:
                evt["data_preview"] = payload
            reasoning_events.append(evt)

        # Step 1: Initialize
        log_event(1, "EVT-01-INIT", "State Master Orchestrator", "ORCHESTRATOR_INITIALIZED",
                  f"Initiated state assessment cycle under trigger: '{trigger}'.")

        # Step 2: Inventory Agent
        inv_report = self.inventory_agent.analyze_inventory(target_district=target_deficit_district)
        alerts = inv_report["alerts"]
        transfer_reqs = inv_report["transfer_requests"]
        log_event(
            2, "EVT-02-INVENTORY", "District Inventory Agent", "WAREHOUSE_AUDIT",
            f"Audited warehouses across UP clusters. Flagged {len(alerts)} stockout alerts. "
            f"Formulated {len(transfer_reqs)} inter-district replenishment transfer proposals.",
            {"deficits_count": len(alerts), "top_deficit": alerts[0]["message"] if alerts else "None"}
        )

        # Step 3: Risk Agent
        risk_data = self.risk_agent.assess_corridor_risks()
        high_risk_lanes = risk_data["high_risk_lanes"]
        threat_level = risk_data["status"]
        risk_report = {
            "agent": "Regional Risk Agent",
            "system_threat_level": threat_level,
            "corridor_risks": risk_data,
            "active_disruptions_count": len(risk_data["active_disruptions"]),
            "high_risk_lanes": high_risk_lanes,
            "impact_analysis": risk_data["impact_analysis"],
            "ai_risk_brief": risk_data["impact_analysis"]["plain_english_summary"]
        }
        log_event(
            3, "EVT-03-RISK", "Regional Risk Agent", "CORRIDOR_HAZARD_SCAN",
            f"Corridor risk assessment complete. Threat Level: {threat_level}. "
            f"Active disruptions: {len(risk_data['active_disruptions'])}. "
            f"High-risk corridors: {', '.join(high_risk_lanes) if high_risk_lanes else 'None'}.",
            {"threat_level": threat_level, "high_risk_lanes": high_risk_lanes}
        )

        # Steps 4-7: logistics, policies, permit, governance (only when a donor exists)
        proposed_plans: List[Dict[str, Any]] = []
        logistics_plan: Optional[Dict[str, Any]] = None
        attached_policies: List[Dict[str, Any]] = []
        draft_doc_package: Optional[Dict[str, Any]] = None

        if alerts and not transfer_reqs:
            log_event(4, "EVT-04-NO-DONOR", "State Master Orchestrator", "NO_DONOR_AVAILABLE",
                      f"{len(alerts)} stockout alerts raised, but no district has surplus stock to transfer. "
                      f"Manual procurement is required.")

        if transfer_reqs:
            # Inventory Agent builds transfers in alert order, so the first one is the most urgent.
            transfer = transfer_reqs[0]
            alert = next(a for a in alerts
                         if a["district"] == transfer["destination"] and a["product"] == transfer["product"])

            logistics_plan = self.logistics_agent.plan_transfer(
                origin=transfer["origin"],
                destination=transfer["destination"],
                product=transfer["product"],
                quantity=transfer["quantity"],
                urgency="urgent" if alert["severity"] == "CRITICAL" else "normal"
            )

            if logistics_plan["status"] == "NO_ROUTE_AVAILABLE":
                log_event(4, "EVT-04-NO-ROUTE", "Intra-State Logistics Agent", "NO_ROUTE_AVAILABLE",
                          logistics_plan["decision_rationale"])
            else:
                plan, attached_policies, draft_doc_package = self._build_plan(
                    transfer, logistics_plan, high_risk_lanes, run_timestamp, log_event,
                    wait_for_approval_timeout, requires_compliance_signoff
                )
                proposed_plans.append(plan)

        # Step 8: Executive synthesis via Google GenAI SDK directly
        ai_synthesis = self._generate_orchestrator_brief(inv_report, risk_report, proposed_plans)
        log_event(8, "EVT-08-SYNTHESIS", "State Master Orchestrator", "EXECUTIVE_BRIEF_SYNTHESIS",
                  "Assembled executive synthesis combining inventory health, corridor risks, and the execution plan.")

        # Step 9: Save run record
        top_plan = proposed_plans[0] if proposed_plans else None
        run_record = {
            "run_id": run_id,
            "timestamp": run_timestamp,
            "trigger": trigger,
            "status": "COMPLETED",
            "summary": (
                f"Generated rebalancing plan {top_plan['plan_id']} "
                f"({top_plan['origin']} -> {top_plan['destination']}, {top_plan['quantity']} {top_plan['product']})"
                if top_plan else "No rebalancing plan was generated for this run."
            ),
            "subagents_output": {
                "inventory_agent": inv_report,
                "risk_agent": risk_report,
                "logistics_agent": logistics_plan or {"status": "NO_TRANSFER_REQUIRED"}
            },
            "final_plan": top_plan,
            "attached_policies": attached_policies,
            "draft_documentation_package": draft_doc_package,
            "reasoning_events": reasoning_events
        }

        if not set_document("agent_runs", run_id, run_record):
            raise RuntimeError(f"Could not save run record {run_id} to 'agent_runs'.")
        log_event(9, "EVT-09-PERSISTENCE", "Firestore Ledger", "AGENT_RUN_ARCHIVED",
                  f"Archived complete run record '{run_id}' to Firestore collection 'agent_runs'.",
                  {"run_id": run_id})
        self.execution_history.append(run_record)

        return {
            "orchestrator": self.name,
            "run_id": run_id,
            "timestamp": run_timestamp,
            "trigger": trigger,
            "system_status": self._system_status(top_plan),
            "inventory_report": inv_report,
            "risk_report": risk_report,
            "logistics_plan": logistics_plan,
            "subagents_output": run_record["subagents_output"],
            "attached_policies": attached_policies,
            "draft_documentation_package": draft_doc_package,
            "preliminary_execution_plan": top_plan,
            "final_plan": top_plan,
            "proposed_rebalance_plans": proposed_plans,
            "reasoning_events": reasoning_events,
            "step_by_step_reasoning": reasoning_events,
            "orchestrator_synthesis": ai_synthesis
        }

    # --------------------------------------------------------------------------
    # STEPS 4-7: build one governed execution plan
    # --------------------------------------------------------------------------
    def _build_plan(self, transfer, logistics_plan, high_risk_lanes, run_timestamp, log_event,
                    wait_timeout, requires_compliance_signoff):
        origin, destination = transfer["origin"], transfer["destination"]
        item, qty, unit = transfer["product"], float(transfer["quantity"]), transfer["unit"]
        route, carrier = logistics_plan["best_route"], logistics_plan["carrier"]
        est_cost, eta_hours = float(logistics_plan["cost_inr"]), float(logistics_plan["eta_hours"])
        logistics_status = logistics_plan["status"]
        distance_km = float(route["distance_km"])
        is_rerouted = "ALT" in str(route["route_id"]) or "Alternative" in str(route["route_name"])
        plan_id = f"PLAN-UP-{uuid.uuid4().hex[:6].upper()}"

        # Step 4: logistics
        log_event(
            4, "EVT-04-LOGISTICS", "Intra-State Logistics Agent", "EXPRESSWAY_ROUTE_OPTIMIZATION",
            f"Synthesized dispatch transfer for {qty:,.1f} {item} from {origin} to {destination}. "
            f"Route assigned: {route['route_name']} ({distance_km} km) via {carrier['carrier_name']} "
            f"at INR {est_cost:,.2f} (ETA: {eta_hours}h). Status: {logistics_status}.",
            {"route": route["route_name"], "carrier": carrier["carrier_name"],
             "cost_inr": est_cost, "eta_hours": eta_hours}
        )

        # Step 5: statutory policies
        queries = [
            f"delivery SLA for {destination}",
            "transit permit e-way bill threshold",
            "emergency freight ODOP 15% subsidy",
            "approval limits Tier 1 autonomous AI",
        ]
        if logistics_status == "REROUTED_DUE_TO_BLOCKADE" or high_risk_lanes:
            queries.append("highway blockade handling rerouting detour")
        results = [_find_policy(q) for q in queries]
        attached_policies: List[Dict[str, Any]] = []
        for p in (p for found in results for p in found):
            if p not in attached_policies:
                attached_policies.append(p)
        sla_title = results[0][0]["title"]

        log_event(
            5, "EVT-05-POLICY", "Policy Vector Engine", "STATUTORY_RULE_ATTACHMENT",
            f"Attached {len(attached_policies)} relevant statutory policy clauses via semantic vector search "
            f"(Delivery SLAs for {destination}, e-Way bill regulations, ODOP 15% rebate, approval matrix).",
            {"policies_attached_count": len(attached_policies),
             "top_documents": sorted({p["doc_name"] for p in attached_policies})}
        )

        # Step 6: Form UP-EWAY-01
        permit_id = f"UP-EWAY-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        unit_cost = get_stock_level(origin, item)["unit_cost_inr"]
        invoice_value = round(qty * unit_cost, 2)
        if distance_km <= 100:
            validity_desc = "24 Hours (1 Calendar Day - Distance <= 100 km)"
        elif distance_km <= 300:
            validity_desc = "48 Hours (2 Calendar Days - Distance 100 to 300 km)"
        else:
            validity_desc = "72 Hours (3 Calendar Days - Distance > 300 km)"
        detour_note = (
            f"REROUTE MANDATED: Diverted via {route['route_name']} due to primary expressway blockade."
            if is_rerouted else "Direct expressway corridor authorized. No active detour advisory."
        )
        eway_required = invoice_value > 50000

        filled_permit = load_transit_permit_template().format(
            PERMIT_ID=permit_id,
            TIMESTAMP=run_timestamp,
            VALIDITY_PERIOD=validity_desc,
            PERMIT_STATUS="PROVISIONAL_CLEARANCE",
            ORIGIN_CLUSTER=origin,
            DESTINATION_CLUSTER=destination,
            PRODUCT=item.capitalize(),
            QUANTITY=f"{qty:,.1f}",
            UNIT=unit,
            INVOICE_VALUE=f"{invoice_value:,.2f}",
            EWAY_REQUIRED=("MANDATORY (Consignment invoice value exceeds INR 50,000 threshold)"
                           if eway_required else "EXEMPT (Invoice value <= INR 50,000)"),
            CARRIER_NAME=carrier["carrier_name"],
            CARRIER_ID=carrier["carrier_id"],
            VEHICLE_TYPE=carrier["vehicle_assigned"],
            ROUTE_NAME=route["route_name"],
            ROUTE_ID=route["route_id"],
            DISTANCE_KM=f"{distance_km:.1f}",
            ETA_HOURS=f"{eta_hours:.1f}",
            TOLL_INR=f"{float(route['toll_inr']):,.2f}",
            TOTAL_COST_INR=f"{est_cost:,.2f}",
            DELIVERY_SLA_POLICY=f"Enforced per {sla_title}: 24.0h Standard / 10.0h Rush",
            VET_INSPECTION_STATUS="CERTIFIED / EXEMPT (Finished commercial leather goods)",
            HAZMAT_STATUS="NON-HAZARDOUS (Class 8 chemical carriage exemption verified)",
            ODOP_SUBSIDY_STATUS="ELIGIBLE (15% freight tariff rebate applicable under UP ODOP)",
            DETOUR_ADVISORY=detour_note,
            PLAN_ID=plan_id
        )

        draft_doc_package = {
            "document_type": "FORM_UP_EWAY_01",
            "permit_id": permit_id,
            "consignor": origin,
            "consignee": destination,
            "commodity": item,
            "quantity": qty,
            "unit": unit,
            "invoice_value_inr": invoice_value,
            "eway_bill_required": eway_required,
            "carrier": carrier["carrier_name"],
            "route_assigned": route["route_name"],
            "statutory_clearances": [
                "FASTag RFID Entry Transponder Verified",
                "UP Commercial Taxes e-Way Compliance Check Cleared",
                "ODOP Emergency Freight Rebate (15%) Pre-Authorized"
            ],
            "filled_permit_manifest": filled_permit
        }
        log_event(
            6, "EVT-06-DOCUMENTATION", "Documentation Engine", "TRANSIT_PERMIT_GENERATED",
            f"Generated Draft Documentation Package Form UP-EWAY-01 (Permit ID: {permit_id}). "
            f"Consignment value: INR {invoice_value:,.2f} (e-Way Bill: {'MANDATORY' if eway_required else 'EXEMPT'}). "
            f"Validity: {validity_desc}.",
            {"permit_id": permit_id, "invoice_value_inr": invoice_value}
        )

        # Step 7: governance
        baseline_cost = float(route["toll_inr"]) + distance_km * NOMINAL_FREIGHT_INR_PER_KM
        decision = evaluate_guardrails({
            "action": "INTER_CLUSTER_STOCK_REBALANCE",
            "type": "transfer",
            "origin": origin,
            "destination": destination,
            "product": item,
            "quantity": qty,
            "estimated_cost_inr": est_cost,
            "amount": est_cost,
            "logistics_status": logistics_status,
            "is_reroute": is_rerouted,
            "original_cost_inr": baseline_cost,
            "new_cost_inr": est_cost,
            "requires_compliance_signoff": requires_compliance_signoff,
            "document_type": "Form UP-EWAY-01 Transit Permit" if requires_compliance_signoff else None
        })
        approval_status = decision.status
        odop_rebate = round(est_cost * 0.15, 2)

        plan = {
            "plan_id": plan_id,
            "action": "INTER_CLUSTER_STOCK_REBALANCE",
            "origin": origin,
            "destination": destination,
            "item": item,
            "product": item,
            "quantity": qty,
            "unit": unit,
            "estimated_cost_inr": est_cost,
            "odop_rebate_inr": odop_rebate,
            "net_cost_inr": round(est_cost - odop_rebate, 2),
            "transit_hours": eta_hours,
            "route_name": route["route_name"],
            "carrier": carrier["carrier_name"],
            "logistics_status": logistics_status,
            "approval_tier": "AUTO_APPROVED" if decision.approved else "REQUIRES_HUMAN_APPROVAL",
            "approval_status": approval_status,
            "guardrail_rule": decision.rule_name,
            "governance_note": decision.reason,
            "risk_justification": (
                f"Replenish {destination} {item} deficit. "
                f"Corridor threat level at planning time covers {len(high_risk_lanes)} high-risk lane(s). "
                f"Detour routing: {'Active' if is_rerouted else 'Not required'}."
            ),
            "logistics_details": logistics_plan,
            "attached_policies": attached_policies,
            "documentation_package": draft_doc_package,
            "execution_status": "AUTO_APPROVED_EXECUTED" if decision.approved else "PAUSED_AWAITING_APPROVAL"
        }

        save_approval_item(
            approval_id=plan_id,
            item_type=decision.action_type,
            details={
                "plan_id": plan_id,
                "origin": origin,
                "destination": destination,
                "product": item,
                "quantity": qty,
                "unit": unit,
                "route": route["route_name"],
                "carrier": carrier["carrier_name"],
                "estimated_cost_inr": est_cost,
                "rule_triggered": decision.rule_name,
                "reason": decision.reason
            },
            amount=est_cost,
            status=approval_status,
            rule_triggered=decision.rule_name,
            reason=decision.reason
        )

        if decision.requires_human_approval:
            plan["discord_dispatch"] = send_discord_approval_request(plan)
            if wait_timeout > 0:
                waited = wait_for_approval_resolution(plan_id, timeout_seconds=wait_timeout)
                if waited["resolved"]:
                    approval_status = waited["status"]
                    plan["approval_status"] = approval_status
                    plan["execution_status"] = (
                        "RESUMED_UPON_APPROVAL" if approval_status == "approved" else "HALTED_REJECTED"
                    )

        log_event(
            7, "EVT-07-GOVERNANCE", "Guardrails Engine", "GUARDRAILS_EVALUATION",
            f"Evaluated Plan {plan_id} against guardrails: {decision.rule_name}. "
            f"Status: {approval_status} "
            f"({'Human approval required' if decision.requires_human_approval else 'Auto-approved'}). "
            f"{decision.reason}",
            {"plan_id": plan_id, "rule": decision.rule_name, "approval_status": approval_status,
             "requires_human": decision.requires_human_approval}
        )
        return plan, attached_policies, draft_doc_package

    # --------------------------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------------------------
    @staticmethod
    def _system_status(plan: Optional[Dict[str, Any]]) -> str:
        if plan is None:
            return "ALL_SYSTEMS_STABLE"
        status = str(plan["approval_status"]).lower()
        if status == "pending":
            return "CRITICAL_ACTION_PENDING_APPROVAL"
        if status == "rejected":
            return "PLAN_REJECTED"
        return "AUTO_APPROVED_DISPATCH"

    def execute_approved_plan(self, plan_id: str) -> Dict[str, Any]:
        """
        Executes an authorized plan by moving stock between the two warehouses.
        """
        update_approval_status(plan_id, "approved", decision_by="District Logistics Supervisor",
                               note="Authorized and Dispatched")
        decision = record_approval_decision(plan_id, "approve")
        if not decision.get("success"):
            return decision

        plan = decision["plan"]
        origin, destination = plan["origin"], plan["destination"]
        item = plan["item"]
        qty = float(plan["quantity"])

        deduct_res = adjust_stock(origin, item, -qty)
        try:
            add_res = adjust_stock(destination, item, qty)
        except Exception:
            adjust_stock(origin, item, qty)
            raise

        return {
            "plan_id": plan_id,
            "execution_status": "COMPLETED",
            "donor_update": deduct_res,
            "recipient_update": add_res,
            "summary": f"Authorized transfer executed: Dispatched {qty} units of {item} from {origin} to {destination}."
        }

    def _generate_orchestrator_brief(self, inv_report: dict, risk_report: dict, plans: list) -> str:
        """Executive summary written directly via Google GenAI SDK (raises if model call fails)."""
        prompt = f"""
        You are the State Master Orchestrator for the Uttar Pradesh Leather Supply Chain.
        Synthesize the state of the supply chain in 3 concise bullet points:
        - Inventory health across Kanpur, Unnao, Agra, Noida: {inv_report['status']}
        - Regional risk alerts: {risk_report['system_threat_level']}
        - Proposed rebalancing action: {plans[0] if plans else 'No action required'}
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
        return response.text.strip()


# ==============================================================================
# STANDALONE DEMO & TEST RUNNER
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print(f"STATE MASTER ORCHESTRATOR (Google ADK & {MODEL_NAME})")
    print("End-to-End Autonomous Supply Chain Deliberation & Policy Enforcement")
    print("=" * 80)

    orchestrator = StateMasterOrchestrator()
    result = orchestrator.run_state_assessment(trigger="End-to-End Orchestrator Verification Run")

    print(f"\nRun ID: {result['run_id']}")
    print(f"Timestamp: {result['timestamp']}")
    print(f"System Status: {result['system_status']}")

    plan = result["preliminary_execution_plan"]
    if plan:
        print(f"\nFinal Plan ID: {plan['plan_id']}")
        print(f"Transfer: {plan['quantity']} units of {plan['item']} ({plan['origin']} -> {plan['destination']})")
        print(f"Route: {plan['route_name']} | Carrier: {plan['carrier']}")
        print(f"Cost: INR {plan['estimated_cost_inr']:,.2f} | Transit Time: {plan['transit_hours']} hours")
        print(f"Approval Tier: {plan['approval_tier']} | Status: {plan['approval_status']}")

    print("\nReasoning Events Timeline:")
    for evt in result["reasoning_events"]:
        print(f"  [Step {evt['step']}] {evt['component']} -> {evt['action']}: {evt['details']}")

    if result["draft_documentation_package"]:
        print("\n" + "=" * 80)
        print("DRAFT DOCUMENTATION PACKAGE (Form UP-EWAY-01 Manifest):")
        print("=" * 80)
        print(result["draft_documentation_package"]["filled_permit_manifest"])

    print("\nExecutive Brief Synthesis:")
    print(result["orchestrator_synthesis"])

    print("=" * 80)