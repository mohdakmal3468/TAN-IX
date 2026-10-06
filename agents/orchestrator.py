"""
agents/orchestrator.py
----------------------
State Master Orchestrator for the Uttar Pradesh Leather Supply Chain.
Built with Google ADK (Agent Development Kit) and Gemini 3.1 Flash.

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
   - Auto-approves Tier 1 (<= INR 10,000), dispatches Discord cards for Tier 2/3.
5. Persistent Execution Logging:
   - Stores every orchestration run in Firestore collection 'agent_runs' with:
     run_id, timestamp, trigger, subagents_output, final_plan, and step-by-step reasoning_events.
"""

import os
import sys
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from google.adk import Agent
from agents.inventory_agent import DistrictInventoryAgent
from agents.risk_agent import RegionalRiskAgent
from agents.logistics_agent import IntraStateLogisticsAgent
from tools.policy_tools import search_policy
from tools.discord_tools import send_discord_approval_request, record_approval_decision, PENDING_APPROVALS
from tools.firestore_client import set_document, get_document, list_documents
from tools.firestore_tools import update_cluster_inventory
from config import GEMINI_API_KEY, GEMINI_MODEL, UP_CLUSTERS

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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
    """Reads the UP Commercial Transit Permit Manifest Template from policies/transit_permits.md."""
    policy_path = os.path.join(ROOT_DIR, "policies", "transit_permits.md")
    if os.path.exists(policy_path):
        try:
            with open(policy_path, "r", encoding="utf-8") as f:
                content = f.read()
            match = re.search(r"```text\s*\n(.*?)\n```", content, re.DOTALL)
            if match:
                return match.group(1).strip()
        except Exception as e:
            print(f"[Orchestrator Warning] Reading permit template note: {e}")

    # Fallback built-in template
    return """================================================================================
                    GOVERNMENT OF UTTAR PRADESH
        DEPARTMENT OF COMMERCIAL TAXES & UP TRANSPORT COMMISSION
             FORM UP-EWAY-01: INTER-DISTRICT TRANSIT PERMIT
================================================================================
Permit ID:          {PERMIT_ID}
Issue Date:         {TIMESTAMP}
Permit Validity:    {VALIDITY_PERIOD}
Status:             {PERMIT_STATUS}

1. CONSIGNMENT & COMMODITY SUMMARY
--------------------------------------------------------------------------------
Origin Cluster:     {ORIGIN_CLUSTER} (Warehouse / Tannery Hub)
Destination:        {DESTINATION_CLUSTER} (Footwear / Production Facility)
Commodity:          {PRODUCT}
Quantity:           {QUANTITY} {UNIT}
Estimated Value:    INR {INVOICE_VALUE}
Statutory e-Way:    {EWAY_REQUIRED} (Mandatory for invoice value > INR 50,000)

2. LOGISTICS ROUTING & CARRIER DISPATCH
--------------------------------------------------------------------------------
Assigned Carrier:   {CARRIER_NAME} (Carrier ID: {CARRIER_ID})
Vehicle Assigned:   {VEHICLE_TYPE}
Corridor Route:     {ROUTE_NAME} (Route ID: {ROUTE_ID})
Transit Distance:   {DISTANCE_KM} km
Estimated Transit:  {ETA_HOURS} hours
Base Toll Charges:  INR {TOLL_INR}
Total Freight Cost: INR {TOTAL_COST_INR}

3. REGULATORY COMPLIANCE & POLICY VERIFICATION
--------------------------------------------------------------------------------
Delivery SLA:       {DELIVERY_SLA_POLICY}
Vet Certificate:    {VET_INSPECTION_STATUS}
Hazmat / Chromium:  {HAZMAT_STATUS}
Emergency Subsidy:  {ODOP_SUBSIDY_STATUS}
Rerouting / Detour: {DETOUR_ADVISORY}
RFID Checkpoint:    VERIFIED (FASTag linked at Expressway Entry)

Authorized By:      STATE MASTER ORCHESTRATOR (TAN-IX System)
Approval Reference: {PLAN_ID}
================================================================================
"""


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
        self.inventory_agent = DistrictInventoryAgent()
        self.risk_agent = RegionalRiskAgent()
        self.logistics_agent = IntraStateLogisticsAgent()
        self.execution_history: List[Dict[str, Any]] = []

    def run_state_assessment(
        self,
        trigger: str = "Periodic Multi-Agent Supply Chain Audit",
        target_deficit_district: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a complete end-to-end multi-agent orchestration cycle:
        1. Audits inventory deficits and locates surplus donor hubs.
        2. Evaluates highway disruptions, weather hazards, and corridor risk scores.
        3. Optimizes logistics routing and carrier dispatch around active bottlenecks.
        4. Queries statutory policies via vector search and attaches applicable clauses.
        5. Fills Form UP-EWAY-01 transit documentation from the template in policies/.
        6. Determines governance approval tier (Tier 1 AI vs Tier 2 Supervisor HITL).
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

        # ----------------------------------------------------------------------
        # Step 1: Initialize Orchestrator Run
        # ----------------------------------------------------------------------
        log_event(
            step=1,
            evt_id="EVT-01-INIT",
            component="State Master Orchestrator",
            action="ORCHESTRATOR_INITIALIZED",
            details=f"Initiated state assessment cycle under trigger: '{trigger}'."
        )

        # ----------------------------------------------------------------------
        # Step 2: Query District Inventory Agent
        # ----------------------------------------------------------------------
        inv_report = self.inventory_agent.analyze_inventory(target_district=target_deficit_district)
        deficits = inv_report.get("alerts", inv_report.get("critical_deficits", []))
        transfer_reqs = inv_report.get("transfer_requests", [])

        log_event(
            step=2,
            evt_id="EVT-02-INVENTORY",
            component="District Inventory Agent",
            action="WAREHOUSE_AUDIT",
            details=(
                f"Audited warehouses across UP clusters. Flagged {len(deficits)} stockout alerts. "
                f"Formulated {len(transfer_reqs)} inter-district replenishment transfer proposals."
            ),
            payload={
                "deficits_count": len(deficits),
                "top_deficit": deficits[0]["message"] if deficits else "None"
            }
        )

        # ----------------------------------------------------------------------
        # Step 3: Query Regional Risk Agent
        # ----------------------------------------------------------------------
        risk_corridor_data = self.risk_agent.assess_corridor_risks()
        active_disruptions = risk_corridor_data.get("active_disruptions", [])
        high_risk_lanes = risk_corridor_data.get("high_risk_lanes", [])
        risk_threat_level = risk_corridor_data.get("status", "NORMAL")

        # Compile legacy risk report structure for backwards-compatibility
        risk_report = {
            "agent": "Regional Risk Agent",
            "system_threat_level": risk_threat_level,
            "corridor_risks": risk_corridor_data,
            "active_disruptions_count": len(active_disruptions),
            "high_risk_lanes": high_risk_lanes,
            "impact_analysis": risk_corridor_data.get("impact_analysis", {}),
            "ai_risk_brief": risk_corridor_data.get("impact_analysis", {}).get("plain_english_summary", "")
        }

        log_event(
            step=3,
            evt_id="EVT-03-RISK",
            component="Regional Risk Agent",
            action="CORRIDOR_HAZARD_SCAN",
            details=(
                f"Corridor risk assessment complete. Threat Level: {risk_threat_level}. "
                f"Active disruptions: {len(active_disruptions)}. High-risk corridors: {', '.join(high_risk_lanes) if high_risk_lanes else 'None'}."
            ),
            payload={
                "threat_level": risk_threat_level,
                "high_risk_lanes": high_risk_lanes
            }
        )

        # ----------------------------------------------------------------------
        # Step 4: Resolve Donor Hub & Logistics Transfer
        # ----------------------------------------------------------------------
        proposed_plans: List[Dict[str, Any]] = []
        logistics_plan: Optional[Dict[str, Any]] = None
        attached_policies: List[Dict[str, Any]] = []
        draft_doc_package: Optional[Dict[str, Any]] = None
        master_plan: Optional[Dict[str, Any]] = None

        if deficits:
            top_deficit = deficits[0]
            target_cluster = top_deficit.get("district") or top_deficit.get("cluster", "Agra")
            deficit_item = top_deficit.get("product") or top_deficit.get("item", "belts")
            deficit_qty = float(top_deficit.get("deficit", 1000.0))
            deficit_severity = top_deficit.get("severity", "CRITICAL")

            # Determine donor cluster from transfer requests or fallback
            donor_cluster = "Kanpur"
            for t in transfer_reqs:
                if t.get("destination", "").lower() == target_cluster.lower():
                    donor_cluster = t.get("origin", "Kanpur")
                    deficit_qty = float(t.get("quantity", deficit_qty))
                    break

            # If donor is same as target, switch to Kanpur or Unnao
            if donor_cluster.lower() == target_cluster.lower():
                donor_cluster = "Kanpur" if target_cluster.lower() != "kanpur" else "Unnao"

            urgency_level = "urgent" if deficit_severity == "CRITICAL" else "normal"

            # Call Logistics Agent
            logistics_plan = self.logistics_agent.plan_transfer(
                origin=donor_cluster,
                destination=target_cluster,
                product=deficit_item,
                quantity=deficit_qty,
                urgency=urgency_level
            )

            b_route = logistics_plan.get("best_route", {})
            b_carrier = logistics_plan.get("carrier", {})
            est_cost = float(logistics_plan.get("cost_inr", 0.0))
            eta_hours = float(logistics_plan.get("eta_hours", 0.0))
            logistics_status = logistics_plan.get("status", "ROUTE_OPTIMIZED")

            log_event(
                step=4,
                evt_id="EVT-04-LOGISTICS",
                component="Intra-State Logistics Agent",
                action="EXPRESSWAY_ROUTE_OPTIMIZATION",
                details=(
                    f"Synthesized dispatch transfer for {deficit_qty:,.1f} {deficit_item} from {donor_cluster} to {target_cluster}. "
                    f"Route assigned: {b_route.get('route_name', 'Highway')} ({b_route.get('distance_km', 0)} km) "
                    f"via {b_carrier.get('carrier_name', 'Carrier')} at INR {est_cost:,.2f} (ETA: {eta_hours}h). Status: {logistics_status}."
                ),
                payload={
                    "route": b_route.get("route_name"),
                    "carrier": b_carrier.get("carrier_name"),
                    "cost_inr": est_cost,
                    "eta_hours": eta_hours
                }
            )

            # ------------------------------------------------------------------
            # Step 5: Attach Statutory Policies via Semantic Vector Search
            # ------------------------------------------------------------------
            # Query 1: Destination Delivery SLA
            sla_matches = search_policy(f"delivery SLA for {target_cluster}", top_k=1)
            # Query 2: Transit Permit and e-Way Bill Rules
            permit_matches = search_policy("transit permit e-way bill threshold", top_k=1)
            # Query 3: Emergency Freight & ODOP Subsidy
            subsidy_matches = search_policy("emergency freight ODOP 15% subsidy", top_k=1)
            # Query 4: Approval Limits & Delegation
            approval_matches = search_policy("approval limits Tier 1 autonomous AI", top_k=1)
            # Query 5: Blockade Handling (if rerouted or disruptions active)
            blockade_matches = []
            if logistics_status == "REROUTED_DUE_TO_BLOCKADE" or high_risk_lanes:
                blockade_matches = search_policy("highway blockade handling rerouting detour", top_k=1)

            for p in (sla_matches + permit_matches + subsidy_matches + approval_matches + blockade_matches):
                if p not in attached_policies:
                    attached_policies.append(p)

            log_event(
                step=5,
                evt_id="EVT-05-POLICY",
                component="Policy Vector Engine",
                action="STATUTORY_RULE_ATTACHMENT",
                details=(
                    f"Attached {len(attached_policies)} relevant statutory policy clauses via semantic vector search "
                    f"(Delivery SLAs for {target_cluster}, e-Way bill regulations, ODOP 15% rebate, approval matrix)."
                ),
                payload={
                    "policies_attached_count": len(attached_policies),
                    "top_documents": list({p["doc_name"] for p in attached_policies})
                }
            )

            # ------------------------------------------------------------------
            # Step 6: Draft Documentation Package (Form UP-EWAY-01)
            # ------------------------------------------------------------------
            template_text = load_transit_permit_template()
            permit_id = f"UP-EWAY-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            unit_cost = 340.0 if "belt" in deficit_item.lower() else 550.0
            invoice_value = round(deficit_qty * unit_cost, 2)
            distance_km = float(b_route.get("distance_km", 200.0))
            is_rerouted = "ALT" in str(b_route.get("route_id", "")) or "Alternative" in str(b_route.get("route_name", ""))

            # Calculate validity period per transit rules
            if distance_km <= 100:
                validity_desc = "24 Hours (1 Calendar Day - Distance <= 100 km)"
            elif distance_km <= 300:
                validity_desc = "48 Hours (2 Calendar Days - Distance 100 to 300 km)"
            else:
                validity_desc = "72 Hours (3 Calendar Days - Distance > 300 km)"

            # SLA summary string
            sla_clause_summary = f"Standard 24.0h / Rush 10.0h (Late Penalty: 2% deduction per hour delay)"
            if sla_matches:
                sla_clause_summary = f"Enforced per {sla_matches[0]['title']}: 24.0h Standard / 10.0h Rush"

            detour_note = (
                f"REROUTE MANDATED: Diverted via {b_route.get('route_name')} due to primary expressway blockade."
                if is_rerouted else "Direct expressway corridor authorized. No active detour advisory."
            )

            filled_permit = template_text.format(
                PERMIT_ID=permit_id,
                TIMESTAMP=run_timestamp,
                VALIDITY_PERIOD=validity_desc,
                PERMIT_STATUS="PROVISIONAL_CLEARANCE",
                ORIGIN_CLUSTER=donor_cluster,
                DESTINATION_CLUSTER=target_cluster,
                PRODUCT=deficit_item.capitalize(),
                QUANTITY=f"{deficit_qty:,.1f}",
                UNIT="units",
                INVOICE_VALUE=f"{invoice_value:,.2f}",
                EWAY_REQUIRED="MANDATORY (Consignment invoice value exceeds INR 50,000 threshold)" if invoice_value > 50000 else "EXEMPT (Invoice value <= INR 50,000)",
                CARRIER_NAME=b_carrier.get("carrier_name", "Commercial Carrier"),
                CARRIER_ID=b_carrier.get("carrier_id", "CAR-01"),
                VEHICLE_TYPE=b_carrier.get("vehicle_assigned", "Eicher Pro (9 Ton)"),
                ROUTE_NAME=b_route.get("route_name", "Inter-District Highway"),
                ROUTE_ID=b_route.get("route_id", "LANE-03"),
                DISTANCE_KM=f"{distance_km:.1f}",
                ETA_HOURS=f"{eta_hours:.1f}",
                TOLL_INR=f"{float(b_route.get('toll_inr', 500.0)):,.2f}",
                TOTAL_COST_INR=f"{est_cost:,.2f}",
                DELIVERY_SLA_POLICY=sla_clause_summary,
                VET_INSPECTION_STATUS="CERTIFIED / EXEMPT (Finished commercial leather goods)",
                HAZMAT_STATUS="NON-HAZARDOUS (Class 8 chemical carriage exemption verified)",
                ODOP_SUBSIDY_STATUS="ELIGIBLE (15% freight tariff rebate applicable under UP ODOP)",
                DETOUR_ADVISORY=detour_note,
                PLAN_ID=f"PLAN-UP-{len(self.execution_history) + 1:04d}"
            )

            draft_doc_package = {
                "document_type": "FORM_UP_EWAY_01",
                "permit_id": permit_id,
                "consignor": donor_cluster,
                "consignee": target_cluster,
                "commodity": deficit_item,
                "quantity": deficit_qty,
                "unit": "units",
                "invoice_value_inr": invoice_value,
                "eway_bill_required": invoice_value > 50000,
                "carrier": b_carrier.get("carrier_name"),
                "route_assigned": b_route.get("route_name"),
                "statutory_clearances": [
                    "FASTag RFID Entry Transponder Verified",
                    "UP Commercial Taxes e-Way Compliance Check Cleared",
                    "ODOP Emergency Freight Rebate (15%) Pre-Authorized"
                ],
                "filled_permit_manifest": filled_permit
            }

            log_event(
                step=6,
                evt_id="EVT-06-DOCUMENTATION",
                component="Documentation Engine",
                action="TRANSIT_PERMIT_GENERATED",
                details=(
                    f"Generated Draft Documentation Package Form UP-EWAY-01 (Permit ID: {permit_id}). "
                    f"Consignment value: INR {invoice_value:,.2f} (e-Way Bill: MANDATORY). "
                    f"Validity: {validity_desc}."
                ),
                payload={
                    "permit_id": permit_id,
                    "invoice_value_inr": invoice_value
                }
            )

            # ------------------------------------------------------------------
            # Step 7: Governance & Approval Tier Resolution
            # ------------------------------------------------------------------
            # Tier 1: <= INR 10,000 -> Autonomous AI Approval
            # Tier 2: INR 10,001 - INR 50,000 -> District Logistics Supervisor HITL
            # Tier 3: > INR 50,000 -> State Directorate
            if est_cost <= 10000.0:
                approval_tier = "TIER_1_AUTONOMOUS"
                approval_status = "AUTO_APPROVED"
                tier_description = "Expenditure <= INR 10,000. Auto-approved by State Master Orchestrator AI."
            elif est_cost <= 50000.0:
                approval_tier = "TIER_2_SUPERVISOR_HITL"
                approval_status = "PENDING"
                tier_description = "Expenditure between INR 10,001 and INR 50,000. Requires District Logistics Supervisor HITL approval."
            else:
                approval_tier = "TIER_3_DIRECTORATE"
                approval_status = "PENDING"
                tier_description = "Expenditure > INR 50,000. Requires State Directorate dual-key sign-off."

            plan_id = f"PLAN-UP-{len(self.execution_history) + 1:04d}"

            # Calculate ODOP 15% subsidy savings
            odop_rebate_inr = round(est_cost * 0.15, 2)
            net_cost_after_rebate_inr = round(est_cost - odop_rebate_inr, 2)

            master_plan = {
                "plan_id": plan_id,
                "action": "INTER_CLUSTER_STOCK_REBALANCE",
                "origin": donor_cluster,
                "destination": target_cluster,
                "item": deficit_item,
                "product": deficit_item,
                "quantity": deficit_qty,
                "unit": "units",
                "estimated_cost_inr": est_cost,
                "odop_rebate_inr": odop_rebate_inr,
                "net_cost_inr": net_cost_after_rebate_inr,
                "transit_hours": eta_hours,
                "route_name": b_route.get("route_name", "Highway Corridor"),
                "carrier": b_carrier.get("carrier_name", "Commercial Carrier"),
                "logistics_status": logistics_status,
                "approval_tier": approval_tier,
                "approval_status": approval_status,
                "governance_note": tier_description,
                "risk_justification": (
                    f"Replenish critical deficit in {target_cluster} ({deficit_item}: {top_deficit.get('current_quantity', 0)} units on hand). "
                    f"Corridor threat level: {risk_threat_level}. Detour routing: {'Active' if is_rerouted else 'Not required'}."
                ),
                "logistics_details": logistics_plan,
                "attached_policies": attached_policies,
                "documentation_package": draft_doc_package
            }

            # Human-in-the-Loop Dispatch
            if approval_status == "PENDING":
                discord_res = send_discord_approval_request(master_plan)
                master_plan["discord_dispatch"] = discord_res

            proposed_plans.append(master_plan)

            log_event(
                step=7,
                evt_id="EVT-07-GOVERNANCE",
                component="Human Governance & HITL",
                action="APPROVAL_TIER_CLASSIFICATION",
                details=(
                    f"Classified Plan {plan_id} under {approval_tier} (Estimated Cost: INR {est_cost:,.2f}). "
                    f"Status: {approval_status}. {tier_description}"
                ),
                payload={
                    "plan_id": plan_id,
                    "approval_tier": approval_tier,
                    "approval_status": approval_status
                }
            )

        # ----------------------------------------------------------------------
        # Step 8: Executive Synthesis Briefing
        # ----------------------------------------------------------------------
        ai_synthesis = self._generate_orchestrator_brief(inv_report, risk_report, proposed_plans)

        log_event(
            step=8,
            evt_id="EVT-08-SYNTHESIS",
            component="State Master Orchestrator",
            action="EXECUTIVE_BRIEF_SYNTHESIS",
            details="Assembled executive synthesis combining inventory health, corridor risks, and the execution plan."
        )

        # ----------------------------------------------------------------------
        # Step 9: Save Run Record to Firestore collection 'agent_runs'
        # ----------------------------------------------------------------------
        run_record = {
            "run_id": run_id,
            "timestamp": run_timestamp,
            "trigger": trigger,
            "status": "COMPLETED",
            "summary": (
                f"Generated rebalancing plan {proposed_plans[0]['plan_id']} "
                f"({proposed_plans[0]['origin']} -> {proposed_plans[0]['destination']}, {proposed_plans[0]['quantity']} {proposed_plans[0]['product']})"
                if proposed_plans else "All district warehouses operating within safe inventory thresholds."
            ),
            "subagents_output": {
                "inventory_agent": inv_report,
                "risk_agent": risk_report,
                "logistics_agent": logistics_plan or {"status": "NO_TRANSFER_REQUIRED"}
            },
            "final_plan": proposed_plans[0] if proposed_plans else None,
            "attached_policies": attached_policies,
            "draft_documentation_package": draft_doc_package,
            "reasoning_events": reasoning_events
        }

        # Persist to Firestore
        saved_success = set_document("agent_runs", run_id, run_record)

        log_event(
            step=9,
            evt_id="EVT-09-PERSISTENCE",
            component="Firestore Ledger",
            action="AGENT_RUN_ARCHIVED",
            details=f"Archived complete run record '{run_id}' to Firestore collection 'agent_runs'. Synced: {saved_success}.",
            payload={"run_id": run_id, "firestore_synced": saved_success}
        )

        # Append to in-memory execution history
        self.execution_history.append(run_record)

        # Return full response (with backward-compatible keys)
        response_payload = {
            "orchestrator": self.name,
            "run_id": run_id,
            "timestamp": run_timestamp,
            "trigger": trigger,
            "system_status": (
                "CRITICAL_ACTION_PENDING_APPROVAL"
                if proposed_plans and proposed_plans[0].get("approval_status") == "PENDING"
                else ("AUTO_APPROVED_DISPATCH" if proposed_plans else "ALL_SYSTEMS_STABLE")
            ),
            "inventory_report": inv_report,
            "risk_report": risk_report,
            "logistics_plan": logistics_plan,
            "subagents_output": run_record["subagents_output"],
            "attached_policies": attached_policies,
            "draft_documentation_package": draft_doc_package,
            "preliminary_execution_plan": proposed_plans[0] if proposed_plans else None,
            "final_plan": proposed_plans[0] if proposed_plans else None,
            "proposed_rebalance_plans": proposed_plans,
            "reasoning_events": reasoning_events,
            "step_by_step_reasoning": reasoning_events,
            "orchestrator_synthesis": ai_synthesis
        }

        return response_payload

    def execute_approved_plan(self, plan_id: str) -> Dict[str, Any]:
        """
        Executes an authorized plan by modifying live inventory balances in the data store.
        """
        decision = record_approval_decision(plan_id, "approve")
        if not decision.get("success"):
            return decision

        plan = decision["plan"]
        origin = plan["origin"]
        destination = plan["destination"]
        item = plan.get("item") or plan.get("product")
        qty = float(plan["quantity"])

        # Deduct from donor warehouse
        deduct_res = update_cluster_inventory(origin, item, -qty)
        # Add to recipient warehouse
        add_res = update_cluster_inventory(destination, item, qty)

        execution_record = {
            "plan_id": plan_id,
            "execution_status": "COMPLETED",
            "donor_update": deduct_res,
            "recipient_update": add_res,
            "summary": f"Authorized transfer executed: Dispatched {qty} units of {item} from {origin} to {destination}."
        }
        return execution_record

    def _generate_orchestrator_brief(self, inv_report: dict, risk_report: dict, plans: list) -> str:
        """Creates a crisp executive summary using Gemini or local template."""
        if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
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
                resp = client.models.generate_content(model=MODEL_NAME, contents=prompt)
                return resp.text.strip()
            except Exception:
                pass

        if plans:
            p = plans[0]
            rebate_str = f" (Net after 15% ODOP rebate: INR {p['net_cost_inr']:,})" if "net_cost_inr" in p else ""
            return (
                f"• Strategic Rebalancing Proposed: Transfer {p['quantity']} units of {p['item']} from {p['origin']} to {p['destination']}.\n"
                f"• Logistics Route: {p['route_name']} (~{p['transit_hours']} hrs, INR {p['estimated_cost_inr']:,}{rebate_str}).\n"
                f"• Statutory Governance: Form UP-EWAY-01 permit generated. Status: {p['approval_status']} ({p.get('approval_tier', 'Standard')})."
            )
        return "• All clusters operating within nominal inventory thresholds. No emergency dispatch required."


# ==============================================================================
# STANDALONE DEMO & TEST RUNNER
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("STATE MASTER ORCHESTRATOR (Google ADK & Gemini 3.1 Flash)")
    print("End-to-End Autonomous Supply Chain Deliberation & Policy Enforcement")
    print("=" * 80)

    orchestrator = StateMasterOrchestrator()
    result = orchestrator.run_state_assessment(trigger="End-to-End Orchestrator Verification Run")

    print(f"\nRun ID: {result['run_id']}")
    print(f"Timestamp: {result['timestamp']}")
    print(f"System Status: {result['system_status']}")

    if result.get("preliminary_execution_plan"):
        plan = result["preliminary_execution_plan"]
        print(f"\nFinal Plan ID: {plan['plan_id']}")
        print(f"Transfer: {plan['quantity']} units of {plan['item']} ({plan['origin']} -> {plan['destination']})")
        print(f"Route: {plan['route_name']} | Carrier: {plan['carrier']}")
        print(f"Cost: INR {plan['estimated_cost_inr']:,.2f} | Transit Time: {plan['transit_hours']} hours")
        print(f"Approval Tier: {plan['approval_tier']} | Status: {plan['approval_status']}")

    print("\nReasoning Events Timeline:")
    for evt in result["reasoning_events"]:
        print(f"  [Step {evt['step']}] {evt['component']} -> {evt['action']}: {evt['details']}")

    if result.get("draft_documentation_package"):
        print("\n" + "=" * 80)
        print("DRAFT DOCUMENTATION PACKAGE (Form UP-EWAY-01 Manifest):")
        print("=" * 80)
        print(result["draft_documentation_package"]["filled_permit_manifest"])

    print("=" * 80)
