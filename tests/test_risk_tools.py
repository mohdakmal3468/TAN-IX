"""
tests/test_risk_tools.py
------------------------
Unit tests for tools/risk_tools.py:
1. get_active_disruptions()
2. lanes_affected_by(disruption_id)
3. calculate_lane_risk_score(lane_id)
4. estimate_impact(lane_id)
5. Backwards-compatible cluster risk & simulation
"""

import unittest
from tools.risk_tools import (
    get_active_disruptions,
    lanes_affected_by,
    calculate_lane_risk_score,
    estimate_impact,
    get_cluster_risk_report,
    simulate_disruption,
    clear_disruptions,
    ACTIVE_DISRUPTIONS
)


class TestRiskTools(unittest.TestCase):

    def setUp(self):
        # Ensure fresh in-memory baseline
        clear_disruptions()

    def tearDown(self):
        clear_disruptions()

    # --------------------------------------------------------------------------
    # 1. Tests for get_active_disruptions()
    # --------------------------------------------------------------------------
    def test_get_active_disruptions(self):
        """Tests that active disruptions are retrieved with valid required fields."""
        disruptions = get_active_disruptions(include_monitoring=True)
        self.assertIsInstance(disruptions, list)
        self.assertGreater(len(disruptions), 0, "Should find active/monitored disruption events")

        for d in disruptions:
            self.assertIn("event_id", d)
            self.assertIn("location", d)
            self.assertIn("type", d)
            self.assertIn("severity", d)
            self.assertIn("title", d)
            self.assertIn("status", d)
            self.assertIn(d["status"], ["ACTIVE", "MONITORING"])

    def test_get_active_disruptions_strict_active_only(self):
        """Tests filtering strictly by ACTIVE status without MONITORING."""
        active_only = get_active_disruptions(include_monitoring=False)
        self.assertIsInstance(active_only, list)
        for d in active_only:
            self.assertEqual(d["status"], "ACTIVE")

    # --------------------------------------------------------------------------
    # 2. Tests for lanes_affected_by()
    # --------------------------------------------------------------------------
    def test_lanes_affected_by_yamuna_fog(self):
        """Tests that EVT-AGR-01 (Yamuna Expressway fog) maps to Agra-Noida lanes."""
        affected = lanes_affected_by("EVT-AGR-01")
        self.assertIsInstance(affected, list)
        self.assertIn("LANE-11", affected, "Yamuna Expressway (Agra->Noida) should be affected by EVT-AGR-01")
        self.assertIn("LANE-12", affected, "Yamuna Expressway (Noida->Agra) should be affected by EVT-AGR-01")

    def test_lanes_affected_by_ganges_flood(self):
        """Tests that EVT-KNP-02 (Ganges flood at Kanpur/Unnao) maps to NH-27 bridge lanes."""
        affected = lanes_affected_by("EVT-KNP-02")
        self.assertIsInstance(affected, list)
        self.assertIn("LANE-01", affected, "NH-27 (Kanpur->Unnao) should be affected by EVT-KNP-02")
        self.assertIn("LANE-02", affected, "NH-27 (Unnao->Kanpur) should be affected by EVT-KNP-02")

    def test_lanes_affected_by_invalid_id(self):
        """Tests that non-existent disruption returns an empty list."""
        affected = lanes_affected_by("NON-EXISTENT-ID-999")
        self.assertEqual(affected, [])

    # --------------------------------------------------------------------------
    # 3. Tests for calculate_lane_risk_score()
    # --------------------------------------------------------------------------
    def test_calculate_lane_risk_score_parameterized_formula(self):
        """Tests the formula directly using explicit parameters:
        Severity (HIGH = 30) + Duration (2 days = 20) + Shipments (6 = 12) = 62.0
        """
        score = calculate_lane_risk_score(
            lane_id="TEST-LANE",
            severity="HIGH",
            duration_days=2.0,
            num_shipments=6
        )
        self.assertEqual(score, 62.0)

    def test_calculate_lane_risk_score_capped_at_100(self):
        """Tests that extreme inputs are strictly capped at 100.0:
        Severity (CRITICAL = 40) + Duration (5 days = 30 max) + Shipments (20 = 30 max) = 100.0
        """
        score = calculate_lane_risk_score(
            lane_id="TEST-LANE",
            severity="CRITICAL",
            duration_days=5.0,
            num_shipments=20
        )
        self.assertEqual(score, 100.0)

    def test_calculate_lane_risk_score_low_disruption(self):
        """Tests a low disruption calculation:
        Severity (LOW = 10) + Duration (0.5 days = 5) + Shipments (2 = 4) = 19.0
        """
        score = calculate_lane_risk_score(
            lane_id="TEST-LANE",
            severity="LOW",
            duration_days=0.5,
            num_shipments=2
        )
        self.assertEqual(score, 19.0)

    def test_calculate_lane_risk_score_active_corridor(self):
        """Tests auto-calculating risk score for LANE-11 (affected by active fog disruption EVT-AGR-01)."""
        score = calculate_lane_risk_score("LANE-11")
        self.assertGreater(score, 0.0, "LANE-11 should have elevated risk score due to active fog disruption")
        self.assertLessEqual(score, 100.0)

    # --------------------------------------------------------------------------
    # 4. Tests for estimate_impact()
    # --------------------------------------------------------------------------
    def test_estimate_impact_on_active_lane(self):
        """Tests impact estimation on LANE-11 (Yamuna Expressway under active fog disruption)."""
        impact = estimate_impact("LANE-11")
        self.assertIsInstance(impact, dict)
        self.assertEqual(impact["lane_id"], "LANE-11")
        self.assertGreater(impact["shipments_delayed"], 0, "Should have delayed shipments")
        self.assertGreater(impact["delay_in_days"], 0.0, "Should have positive delay days")
        self.assertEqual(impact["severity"], "HIGH")
        self.assertIn("EVT-AGR-01", impact["disruption_id"])
        self.assertGreater(impact["estimated_cost_inr"], 0.0)

        # Attribute access
        self.assertEqual(impact.shipments_delayed, impact["shipments_delayed"])
        self.assertEqual(impact.delay_in_days, impact["delay_in_days"])

    def test_estimate_impact_on_clear_lane(self):
        """Tests impact estimation on a clear route with no active disruptions."""
        # LANE-07 (Unnao -> Agra) has no active disruptions
        impact = estimate_impact("LANE-07")
        self.assertIsInstance(impact, dict)
        self.assertEqual(impact["lane_id"], "LANE-07")
        self.assertEqual(impact["shipments_delayed"], 0)
        self.assertEqual(impact["delay_in_days"], 0.0)
        self.assertEqual(impact["severity"], "NONE")
        self.assertEqual(impact["estimated_cost_inr"], 0.0)

    # --------------------------------------------------------------------------
    # 5. Backwards Compatibility & Dynamic Simulation Tests
    # --------------------------------------------------------------------------
    def test_cluster_risk_report_and_simulation(self):
        """Tests get_cluster_risk_report, simulate_disruption, and clear_disruptions."""
        report = get_cluster_risk_report("Kanpur")
        self.assertIsInstance(report, dict)
        self.assertIn("composite_risk_score", report)
        self.assertIn("risk_level", report)

        # Simulate emergency
        sim = simulate_disruption("Agra", "WEATHER_FLOOD", "Yamuna river waterlogging at highway ramp")
        self.assertEqual(sim["status"], "Disruption active")

        # Verify it appears in active disruptions
        active = get_active_disruptions()
        sim_ids = [d["event_id"] for d in active]
        self.assertIn(sim["disruption"]["event_id"], sim_ids)

        # Clear disruptions
        clear_res = clear_disruptions()
        self.assertEqual(clear_res["status"], "All active disruptions cleared.")


if __name__ == "__main__":
    unittest.main()
