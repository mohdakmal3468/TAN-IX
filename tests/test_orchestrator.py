"""
tests/test_orchestrator.py
--------------------------
Unit and integration tests for State Master Orchestrator (agents/orchestrator.py).
Tests multi-agent deliberation, policy attachment, permit generation, and Firestore run persistence.
"""

import unittest
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from agents.orchestrator import StateMasterOrchestrator
from tools.risk_tools import simulate_disruption, clear_disruptions
from tools.logistics_tools import reset_blocked_routes
from tools.firestore_client import get_document, list_documents


class TestStateMasterOrchestrator(unittest.TestCase):
    """Test suite for State Master Orchestrator."""

    def setUp(self):
        clear_disruptions()
        reset_blocked_routes()
        self.orchestrator = StateMasterOrchestrator()

    def tearDown(self):
        clear_disruptions()
        reset_blocked_routes()

    def test_orchestrator_initialization(self):
        """Tests that the orchestrator initializes with ADK agent and specialist sub-agents."""
        self.assertIsNotNone(self.orchestrator.adk_agent)
        self.assertEqual(self.orchestrator.adk_agent.name, "state_master_orchestrator")
        self.assertIsNotNone(self.orchestrator.inventory_agent)
        self.assertIsNotNone(self.orchestrator.risk_agent)
        self.assertIsNotNone(self.orchestrator.logistics_agent)

    def test_run_state_assessment_and_persistence(self):
        """Tests complete orchestration cycle and verifies Firestore persistence in agent_runs."""
        trigger_name = "Automated Test Audit"
        result = self.orchestrator.run_state_assessment(trigger=trigger_name)

        # 1. Structure checks
        self.assertIn("run_id", result)
        self.assertTrue(result["run_id"].startswith("RUN-"))
        self.assertIn("timestamp", result)
        self.assertEqual(result["trigger"], trigger_name)
        self.assertIn("subagents_output", result)
        self.assertIn("inventory_agent", result["subagents_output"])
        self.assertIn("risk_agent", result["subagents_output"])
        self.assertIn("logistics_agent", result["subagents_output"])
        self.assertIn("reasoning_events", result)
        self.assertGreaterEqual(len(result["reasoning_events"]), 5)

        # 2. Persistence check
        run_id = result["run_id"]
        persisted_doc = get_document("agent_runs", run_id)
        self.assertIsNotNone(persisted_doc, f"Run '{run_id}' should be found in Firestore collection 'agent_runs'.")
        self.assertEqual(persisted_doc["run_id"], run_id)
        self.assertEqual(persisted_doc["trigger"], trigger_name)
        self.assertIn("final_plan", persisted_doc)
        self.assertIn("reasoning_events", persisted_doc)

    def test_transit_permit_generation(self):
        """Tests draft documentation package Form UP-EWAY-01 generation."""
        result = self.orchestrator.run_state_assessment(
            trigger="Permit Generation Test",
            target_deficit_district="Agra"
        )
        self.assertIn("draft_documentation_package", result)
        doc_pkg = result["draft_documentation_package"]
        self.assertIsNotNone(doc_pkg)
        self.assertEqual(doc_pkg["document_type"], "FORM_UP_EWAY_01")
        self.assertTrue(doc_pkg["permit_id"].startswith("UP-EWAY-"))
        self.assertIn("filled_permit_manifest", doc_pkg)
        self.assertIn("FORM UP-EWAY-01: INTER-DISTRICT TRANSIT PERMIT", doc_pkg["filled_permit_manifest"])

    def test_scenario_unnao_blockade_and_agra_stockout(self):
        """
        End-to-End scenario: Blockade near Unnao + Agra belt stockout.
        Verifies risk recognition, rerouting, statutory policy citations, and plan output.
        """
        # Inject Unnao blockade
        simulate_disruption(
            cluster_name="Unnao",
            disruption_type="HIGHWAY_BLOCKADE",
            description="Transporters strike on NH-27 near Unnao Banthar corridor.",
            severity="CRITICAL",
            affected_lanes=["LANE-01", "LANE-02"]
        )

        result = self.orchestrator.run_state_assessment(
            trigger="Blockade near Unnao + Agra belt stockout",
            target_deficit_district="Agra"
        )

        # Verify output plan
        plan = result.get("preliminary_execution_plan")
        self.assertIsNotNone(plan, "Preliminary execution plan must be produced for Agra deficit.")
        self.assertEqual(plan["destination"].lower(), "agra")
        self.assertIn("belt", plan["item"].lower())
        self.assertGreater(plan["quantity"], 0)
        self.assertIn("attached_policies", plan)
        self.assertGreaterEqual(len(plan["attached_policies"]), 2)

        # Verify draft permit package
        self.assertIn("documentation_package", plan)
        self.assertIsNotNone(plan["documentation_package"])
        permit_text = plan["documentation_package"]["filled_permit_manifest"]
        self.assertIn("Agra", permit_text)
        self.assertIn("Belts", permit_text)


if __name__ == "__main__":
    unittest.main()
