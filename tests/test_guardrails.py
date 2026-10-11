"""
tests/test_guardrails.py
------------------------
Unit and integration tests for AgentHide Supply Chain Guardrails (agents/guardrails.py).
Tests all 4 statutory governance rules:
1. Transfers under 50,000 INR are auto-approved; transfers >= 50,000 INR require human approval.
2. Standard reroutes (cost increase <= 30%) are auto-approved; route changes > 30% require human approval.
3. Purchase orders over 50,000 INR require human approval; purchase orders <= 50,000 INR are auto-approved.
4. All compliance paperwork requires human approval.
Also tests Firestore approvals collection lifecycle (pending/approved/rejected) and orchestrator pausing.
"""

import unittest
import os
import sys
import threading
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from agents.guardrails import (
    check_transfer_rule,
    check_reroute_rule,
    check_purchase_order_rule,
    check_compliance_paperwork_rule,
    evaluate_guardrails,
    save_approval_item,
    update_approval_status,
    get_approval_status,
    wait_for_approval_resolution
)
from agents.orchestrator import StateMasterOrchestrator
from tools.firestore_client import get_document
from tools.risk_tools import clear_disruptions
from tools.logistics_tools import reset_blocked_routes


class TestGuardrails(unittest.TestCase):
    """Test suite for Guardrails rules and approval workflows."""

    def setUp(self):
        clear_disruptions()
        reset_blocked_routes()

    def tearDown(self):
        clear_disruptions()
        reset_blocked_routes()

    # --------------------------------------------------------------------------
    # RULE 1: Transfers under 50,000 INR vs >= 50,000 INR
    # --------------------------------------------------------------------------
    def test_rule_1_transfer_under_50k_auto_approved(self):
        """Transfers under 50,000 INR must be auto-approved with status 'approved'."""
        decision_small = check_transfer_rule(16680.0)
        self.assertTrue(decision_small.approved)
        self.assertEqual(decision_small.status, "approved")
        self.assertFalse(decision_small.requires_human_approval)
        self.assertEqual(decision_small.rule_name, "TRANSFER_UNDER_50K_AUTO_APPROVE")

        decision_edge = check_transfer_rule(49999.0)
        self.assertTrue(decision_edge.approved)
        self.assertEqual(decision_edge.status, "approved")
        self.assertFalse(decision_edge.requires_human_approval)

    def test_rule_1_transfer_over_50k_requires_approval(self):
        """Transfers of 50,000 INR or more must require human approval with status 'pending'."""
        decision_exact = check_transfer_rule(50000.0)
        self.assertFalse(decision_exact.approved)
        self.assertEqual(decision_exact.status, "pending")
        self.assertTrue(decision_exact.requires_human_approval)
        self.assertEqual(decision_exact.rule_name, "TRANSFER_OVER_50K_HUMAN_APPROVAL")

        decision_large = check_transfer_rule(85000.0)
        self.assertFalse(decision_large.approved)
        self.assertEqual(decision_large.status, "pending")
        self.assertTrue(decision_large.requires_human_approval)

    # --------------------------------------------------------------------------
    # RULE 2: Standard reroutes vs Route changes above 30% cost increase
    # --------------------------------------------------------------------------
    def test_rule_2_standard_reroute_auto_approved(self):
        """Reroutes with cost increase <= 30% must be auto-approved."""
        # 20% increase: 10,000 -> 12,000
        decision_20pct = check_reroute_rule(original_cost_inr=10000.0, new_cost_inr=12000.0)
        self.assertTrue(decision_20pct.approved)
        self.assertEqual(decision_20pct.status, "approved")
        self.assertFalse(decision_20pct.requires_human_approval)
        self.assertEqual(decision_20pct.rule_name, "STANDARD_REROUTE_AUTO_APPROVE")

        # Exactly 30% increase: 10,000 -> 13,000
        decision_30pct = check_reroute_rule(original_cost_inr=10000.0, new_cost_inr=13000.0)
        self.assertTrue(decision_30pct.approved)
        self.assertEqual(decision_30pct.status, "approved")
        self.assertFalse(decision_30pct.requires_human_approval)

    def test_rule_2_reroute_above_30pct_requires_approval(self):
        """Reroutes with cost increase > 30% must require human approval."""
        # 35% increase: 10,000 -> 13,500
        decision_35pct = check_reroute_rule(original_cost_inr=10000.0, new_cost_inr=13500.0)
        self.assertFalse(decision_35pct.approved)
        self.assertEqual(decision_35pct.status, "pending")
        self.assertTrue(decision_35pct.requires_human_approval)
        self.assertEqual(decision_35pct.rule_name, "REROUTE_COST_EXCEEDS_30PCT_HUMAN_APPROVAL")

        # 60% increase: 10,000 -> 16,000
        decision_60pct = check_reroute_rule(original_cost_inr=10000.0, new_cost_inr=16000.0)
        self.assertFalse(decision_60pct.approved)
        self.assertEqual(decision_60pct.status, "pending")
        self.assertTrue(decision_60pct.requires_human_approval)

    # --------------------------------------------------------------------------
    # RULE 3: Purchase orders over 50,000 INR
    # --------------------------------------------------------------------------
    def test_rule_3_purchase_order_under_50k_auto_approved(self):
        """Purchase orders <= 50,000 INR must be auto-approved."""
        decision = check_purchase_order_rule(35000.0)
        self.assertTrue(decision.approved)
        self.assertEqual(decision.status, "approved")
        self.assertFalse(decision.requires_human_approval)
        self.assertEqual(decision.rule_name, "PURCHASE_ORDER_UNDER_50K_AUTO_APPROVE")

        decision_50k = check_purchase_order_rule(50000.0)
        self.assertTrue(decision_50k.approved)
        self.assertEqual(decision_50k.status, "approved")

    def test_rule_3_purchase_order_over_50k_requires_approval(self):
        """Purchase orders > 50,000 INR must require human approval."""
        decision = check_purchase_order_rule(50001.0)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.status, "pending")
        self.assertTrue(decision.requires_human_approval)
        self.assertEqual(decision.rule_name, "PURCHASE_ORDER_OVER_50K_HUMAN_APPROVAL")

        decision_large = check_purchase_order_rule(150000.0)
        self.assertFalse(decision_large.approved)
        self.assertEqual(decision_large.status, "pending")
        self.assertTrue(decision_large.requires_human_approval)

    # --------------------------------------------------------------------------
    # RULE 4: All compliance paperwork requires human approval
    # --------------------------------------------------------------------------
    def test_rule_4_compliance_paperwork_requires_approval(self):
        """All compliance paperwork must require human approval."""
        d1 = check_compliance_paperwork_rule("Form UP-EWAY-01 Transit Permit")
        self.assertFalse(d1.approved)
        self.assertEqual(d1.status, "pending")
        self.assertTrue(d1.requires_human_approval)
        self.assertEqual(d1.rule_name, "COMPLIANCE_PAPERWORK_HUMAN_APPROVAL")

        d2 = check_compliance_paperwork_rule("Animal Husbandry Vet Certificate")
        self.assertFalse(d2.approved)
        self.assertEqual(d2.status, "pending")
        self.assertTrue(d2.requires_human_approval)

        d3 = check_compliance_paperwork_rule("Chromium Hazmat Clearance")
        self.assertFalse(d3.approved)
        self.assertEqual(d3.status, "pending")
        self.assertTrue(d3.requires_human_approval)

    # --------------------------------------------------------------------------
    # FIRESTORE APPROVALS COLLECTION LIFECYCLE (pending / approved / rejected)
    # --------------------------------------------------------------------------
    def test_firestore_approvals_lifecycle(self):
        """Tests saving pending item to Firestore approvals and updating to approved and rejected."""
        test_appr_id = f"TEST-APPR-{int(time.time() * 1000)}"

        # 1. Save with status 'pending'
        saved = save_approval_item(
            approval_id=test_appr_id,
            item_type="transfer",
            details={"origin": "Kanpur", "destination": "Agra", "amount": 65000.0},
            amount=65000.0,
            status="pending",
            rule_triggered="TRANSFER_OVER_50K_HUMAN_APPROVAL",
            reason="Transfer amount exceeds 50k threshold."
        )
        self.assertEqual(saved["status"], "pending")

        # Verify Firestore read
        doc = get_document("approvals", test_appr_id)
        self.assertIsNotNone(doc)
        self.assertEqual(doc["status"], "pending")
        self.assertEqual(get_approval_status(test_appr_id), "pending")

        # 2. Update status to 'approved'
        updated_appr = update_approval_status(test_appr_id, "approved", decision_by="Supervisor A")
        self.assertEqual(updated_appr["status"], "approved")
        self.assertEqual(get_approval_status(test_appr_id), "approved")

        doc_after_appr = get_document("approvals", test_appr_id)
        self.assertEqual(doc_after_appr["status"], "approved")
        self.assertEqual(doc_after_appr["decision_by"], "Supervisor A")

        # 3. Update status to 'rejected'
        updated_rej = update_approval_status(test_appr_id, "rejected", decision_by="Supervisor B")
        self.assertEqual(updated_rej["status"], "rejected")
        self.assertEqual(get_approval_status(test_appr_id), "rejected")

        doc_after_rej = get_document("approvals", test_appr_id)
        self.assertEqual(doc_after_rej["status"], "rejected")

    # --------------------------------------------------------------------------
    # ORCHESTRATOR PAUSING AND RESUMING UPON APPROVAL
    # --------------------------------------------------------------------------
    def test_orchestrator_pause_and_resume_on_approval(self):
        """Tests orchestrator pausing execution when human approval is required and resuming on status change."""
        orchestrator = StateMasterOrchestrator()
        test_plan_id = f"TEST-PAUSE-{int(time.time() * 1000)}"

        # Save pending item
        save_approval_item(
            approval_id=test_plan_id,
            item_type="purchase_order",
            details={"order_id": "PO-999"},
            amount=75000.0,
            status="pending",
            rule_triggered="PURCHASE_ORDER_OVER_50K_HUMAN_APPROVAL"
        )

        # 1. Wait times out while status is still 'pending'
        wait_pending = wait_for_approval_resolution(test_plan_id, timeout_seconds=0.3, poll_interval=0.1)
        self.assertFalse(wait_pending["resolved"])
        self.assertEqual(wait_pending["status"], "pending")

        # 2. Background thread approves after 0.2s
        def approve_after_delay():
            time.sleep(0.15)
            update_approval_status(test_plan_id, "approved", decision_by="Admin")

        t = threading.Thread(target=approve_after_delay)
        t.start()

        # Orchestrator waiting resolution should unpause upon status change
        wait_resolved = wait_for_approval_resolution(test_plan_id, timeout_seconds=1.5, poll_interval=0.05)
        t.join()

        self.assertTrue(wait_resolved["resolved"])
        self.assertEqual(wait_resolved["status"], "approved")

    def test_orchestrator_auto_approved_transfer_under_50k(self):
        """Verifies that an orchestrator rebalancing plan under 50k is auto-approved."""
        orchestrator = StateMasterOrchestrator()
        result = orchestrator.run_state_assessment(
            trigger="Guardrails Auto-Approval Verification",
            target_deficit_district="Agra"
        )
        plan = result.get("preliminary_execution_plan")
        self.assertIsNotNone(plan)

        # Cost for 1020 belts is ~16,680 INR (< 50,000 INR)
        if plan["estimated_cost_inr"] < 50000.0:
            self.assertEqual(plan["approval_tier"], "AUTO_APPROVED")
            self.assertEqual(plan["approval_status"], "approved")
            self.assertEqual(plan["execution_status"], "AUTO_APPROVED_EXECUTED")


if __name__ == "__main__":
    unittest.main()
