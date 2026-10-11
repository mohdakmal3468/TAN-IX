"""
scripts/run_scenario.py
-----------------------
Executes the End-to-End Multi-Agent Scenario:
- Disruptive Event: Transport strike & highway blockade near Unnao (NH-27)
- Inventory Deficit: Critical belt stockout at Agra Footwear Cluster
- Orchestrator: State Master Orchestrator (Google ADK)
  1. Audits inventory & flags Agra deficit
  2. Evaluates corridor risk & flags Unnao blockade
  3. Optimizes logistics routing & carrier selection
  4. Queries policy vector database & attaches statutory regulations
  5. Generates filled Form UP-EWAY-01 transit permit
  6. Classifies governance tier & saves run to Firestore collection 'agent_runs'
"""

import os
import sys
import json

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agents.orchestrator import StateMasterOrchestrator
from tools.risk_tools import simulate_disruption, clear_disruptions
from tools.logistics_tools import reset_blocked_routes, mark_route_blocked


def run_scenario():
    print("=" * 85)
    print("AgentHide END-TO-END SCENARIO: UNNAO BLOCKADE + AGRA BELT STOCKOUT")
    print("=" * 85)

    # 1. Reset baseline state
    clear_disruptions()
    reset_blocked_routes()

    # 2. Inject Disruptions
    print("\n[Phase 1] Injecting Environmental & Infrastructure Disruptions...")
    disruption = simulate_disruption(
        cluster_name="Unnao",
        disruption_type="HIGHWAY_BLOCKADE",
        description="Transport union strike and truck blockade near Unnao Banthar corridor on NH-27 halting all freight movement.",
        severity="CRITICAL",
        affected_lanes=["LANE-01", "LANE-02"]
    )
    print(f"  -> Disruption Event: {disruption['disruption']['title']}")
    print(f"     Severity:         {disruption['disruption']['severity']}")
    print(f"     Affected Lanes:   {disruption['disruption']['affected_lanes']}")

    # 3. Initialize State Master Orchestrator
    print("\n[Phase 2] Initializing State Master Orchestrator (Google ADK)...")
    orchestrator = StateMasterOrchestrator()

    trigger_msg = "Critical highway blockade near Unnao (NH-27) + Agra Footwear Cluster belt stockout"
    result = orchestrator.run_state_assessment(
        trigger=trigger_msg,
        target_deficit_district="Agra"
    )

    print(f"\n[Phase 3] Orchestrator Deliberation Completed!")
    print(f"  Run ID:        {result['run_id']}")
    print(f"  Timestamp:     {result['timestamp']}")
    print(f"  System Status: {result['system_status']}")

    plan = result.get("preliminary_execution_plan")

    print("\n" + "=" * 85)
    print("PRELIMINARY EXECUTION PLAN")
    print("=" * 85)
    if plan:
        print(f"Plan ID:            {plan['plan_id']}")
        print(f"Action:             {plan['action']}")
        print(f"Transfer Origin:    {plan['origin']} (Donor Cluster)")
        print(f"Destination:        {plan['destination']} (Deficit Hub)")
        print(f"Commodity / Item:   {plan['item']}")
        print(f"Quantity:           {plan['quantity']:,.1f} {plan['unit']}")
        print(f"Assigned Route:     {plan['route_name']}")
        print(f"Assigned Carrier:   {plan['carrier']}")
        print(f"Estimated Transit:  {plan['transit_hours']} hours")
        print(f"Base Freight Cost:  INR {plan['estimated_cost_inr']:,.2f}")
        print(f"ODOP 15% Rebate:   -INR {plan['odop_rebate_inr']:,.2f}")
        print(f"Net Freight Spend:  INR {plan['net_cost_inr']:,.2f}")
        print(f"Governance Tier:    {plan['approval_tier']}")
        print(f"Approval Status:    {plan['approval_status']}")
        print(f"Governance Note:    {plan['governance_note']}")
        print(f"\nRisk Justification:")
        print(f"  {plan['risk_justification']}")

        print("\nAttached Statutory Policies (Semantic Vector Match):")
        for idx, pol in enumerate(plan.get("attached_policies", []), 1):
            print(f"  [{idx}] {pol['title']} -> {pol['section']}")
            print(f"      Doc File: {pol['doc_name']} | Relevance Score: {pol['similarity_score']}")
            print(f"      Snippet:  {pol['snippet'][:110]}...")

    print("\n" + "=" * 85)
    print("DRAFT DOCUMENTATION PACKAGE (Form UP-EWAY-01 Manifest):")
    print("=" * 85)
    doc_pkg = result.get("draft_documentation_package")
    if doc_pkg:
        print(doc_pkg["filled_permit_manifest"])

    print("\n" + "=" * 85)
    print("STEP-BY-STEP REASONING EVENTS TIMELINE:")
    print("=" * 85)
    for evt in result["reasoning_events"]:
        print(f"  [Step {evt['step']}] {evt['timestamp'][:19]}Z | {evt['component']:<28} | {evt['action']}")
        print(f"           Details: {evt['details']}")

    # Clean up
    clear_disruptions()
    reset_blocked_routes()

    return result


if __name__ == "__main__":
    run_scenario()
