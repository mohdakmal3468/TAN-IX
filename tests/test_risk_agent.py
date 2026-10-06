"""
tests/test_risk_agent.py
------------------------
Unit tests for agents/risk_agent.py (Regional Risk Agent).
Tests:
1. Baseline corridor risk assessment and structured JSON output.
2. Highway blockade near Unnao increases affected lane risk scores.
3. Backwards-compatibility of assess_all_clusters().
"""

import unittest
from agents.risk_agent import RegionalRiskAgent
from tools.risk_tools import simulate_disruption, clear_disruptions


class TestRiskAgent(unittest.TestCase):

    def setUp(self):
        clear_disruptions()
        self.agent = RegionalRiskAgent()

    def tearDown(self):
        clear_disruptions()

    def test_assess_corridor_risks_structure(self):
        """Tests that assess_corridor_risks returns strictly formatted JSON fields."""
        result = self.agent.assess_corridor_risks()
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)
        self.assertIn("active_disruptions_count", result)
        self.assertIn("lane_risk_scores", result)
        self.assertIn("high_risk_lanes", result)
        self.assertIn("impact_analysis", result)

        impact = result["impact_analysis"]
        self.assertIn("plain_english_summary", impact)
        self.assertIn("total_shipments_delayed", impact)
        self.assertIn("max_delay_days", impact)
        self.assertIn("total_cost_impact_inr", impact)
        self.assertIn("corridor_briefings", impact)
        self.assertIn("recommendations", impact)

    def test_blockade_near_unnao_rises_lane_score(self):
        """Tests that inserting a highway blockade near Unnao raises LANE-01 & LANE-02 scores."""
        # 1. Baseline assessment
        pre_result = self.agent.assess_corridor_risks()
        pre_lane_01 = next(
            (item for item in pre_result["lane_risk_scores"] if item["lane_id"] == "LANE-01"),
            None
        )
        self.assertIsNotNone(pre_lane_01)
        pre_score = pre_lane_01["risk_score"]

        # 2. Insert highway blockade near Unnao
        simulate_disruption(
            cluster_name="Unnao",
            disruption_type="HIGHWAY_BLOCKADE",
            description="Farmers and transporters protest on NH-27 Banthar corridor completely halting freight.",
            severity="CRITICAL",
            affected_lanes=["LANE-01", "LANE-02"]
        )

        # 3. Post-blockade assessment
        post_result = self.agent.assess_corridor_risks()
        post_lane_01 = next(
            (item for item in post_result["lane_risk_scores"] if item["lane_id"] == "LANE-01"),
            None
        )
        self.assertIsNotNone(post_lane_01)
        post_score = post_lane_01["risk_score"]

        # 4. Assert score rises significantly
        self.assertGreater(post_score, pre_score, f"LANE-01 score should rise (was {pre_score}, now {post_score})")
        self.assertEqual(post_lane_01["risk_level"], "CRITICAL")
        self.assertEqual(post_result["status"], "CRITICAL_ALERT")

        # 5. Assert plain-English impact mentions high-risk lanes
        self.assertIn("LANE-01", post_result["high_risk_lanes"])
        self.assertIn("LANE-02", post_result["high_risk_lanes"])

    def test_assess_all_clusters_backwards_compatibility(self):
        """Tests backwards-compatibility of assess_all_clusters for dashboard and orchestrator."""
        cluster_assessment = self.agent.assess_all_clusters()
        self.assertIn("monitored_clusters", cluster_assessment)
        self.assertIn("cluster_risk_reports", cluster_assessment)
        self.assertIn("corridor_risks", cluster_assessment)
        self.assertIn("ai_risk_brief", cluster_assessment)


if __name__ == "__main__":
    unittest.main()
