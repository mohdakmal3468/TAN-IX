"""
tests/test_logistics_agent.py
----------------------------
Unit tests for agents/logistics_agent.py (Intra-State Logistics Agent).
Tests:
1. Normal transfer request optimization (Kanpur -> Agra).
2. Blockade rerouting (LANE-03 blocked -> LANE-03-ALT selected).
3. Urgent transfer request handling.
4. Valid JSON structure adhering to required fields.
"""

import unittest
from agents.logistics_agent import IntraStateLogisticsAgent
from tools.logistics_tools import mark_route_blocked, reset_blocked_routes


class TestLogisticsAgent(unittest.TestCase):

    def setUp(self):
        reset_blocked_routes()
        self.agent = IntraStateLogisticsAgent()

    def tearDown(self):
        reset_blocked_routes()

    def test_plan_transfer_normal_kanpur_agra(self):
        """Test normal transfer from Kanpur to Agra returns LANE-03 and status ROUTE_OPTIMIZED."""
        result = self.agent.plan_transfer(
            origin="Kanpur",
            destination="Agra",
            product="belts",
            quantity=1020.0,
            urgency="normal"
        )

        self.assertEqual(result["status"], "ROUTE_OPTIMIZED")
        self.assertEqual(result["origin"], "Kanpur")
        self.assertEqual(result["destination"], "Agra")
        self.assertEqual(result["product"], "belts")
        self.assertEqual(result["quantity"], 1020.0)

        # Main route should be LANE-03 (Agra-Lucknow Expressway)
        self.assertEqual(result["best_route"]["route_id"], "LANE-03")
        self.assertIn("Agra-Lucknow Expressway", result["best_route"]["route_name"])

        # Cost and ETA checks
        self.assertGreater(result["cost_inr"], 0)
        self.assertGreater(result["eta_hours"], 0)
        self.assertIn("carrier", result)
        self.assertIn("carrier_id", result["carrier"])
        self.assertIn("decision_rationale", result)

    def test_plan_transfer_blockade_rerouting(self):
        """Test blocking LANE-03 forces rerouting to LANE-03-ALT with status REROUTED_DUE_TO_BLOCKADE."""
        # Block the primary route
        mark_route_blocked("LANE-03")

        result = self.agent.plan_transfer(
            origin="Kanpur",
            destination="Agra",
            product="belts",
            quantity=1020.0,
            urgency="normal"
        )

        self.assertEqual(result["status"], "REROUTED_DUE_TO_BLOCKADE")
        self.assertEqual(result["best_route"]["route_id"], "LANE-03-ALT")
        self.assertIn("Alternative", result["best_route"]["route_name"])
        self.assertIn("Primary expressway route blocked", result["decision_rationale"])
        self.assertGreater(result["cost_inr"], 0)
        self.assertGreater(result["eta_hours"], 0)

    def test_plan_transfer_all_routes_blocked(self):
        """Test case where all routes between origin and destination are blocked."""
        mark_route_blocked("LANE-03")
        mark_route_blocked("LANE-03-ALT")

        result = self.agent.plan_transfer(
            origin="Kanpur",
            destination="Agra",
            product="belts",
            quantity=1020.0
        )

        self.assertEqual(result["status"], "NO_ROUTE_AVAILABLE")
        self.assertEqual(result["cost_inr"], 0.0)
        self.assertEqual(result["eta_hours"], 0.0)
        self.assertIn("blocked", result["decision_rationale"])


if __name__ == "__main__":
    unittest.main()
