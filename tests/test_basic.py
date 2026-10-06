"""
tests/test_basic.py
-------------------
Unit tests for TAN-IX multi-agent core tools and orchestrator logic.
Can be executed with: python -m unittest tests/test_basic.py
"""

import unittest
from tools.firestore_tools import get_all_clusters_inventory, check_critical_stockouts
from tools.logistics_tools import calculate_route
from tools.risk_tools import get_cluster_risk_report
from agents.orchestrator import StateMasterOrchestrator


class TestTanIxCore(unittest.TestCase):

    def test_inventory_retrieval(self):
        """Verifies inventory is retrieved for all 4 clusters."""
        clusters = get_all_clusters_inventory()
        self.assertIn("Kanpur", clusters)
        self.assertIn("Agra", clusters)
        self.assertIn("Unnao", clusters)

    def test_critical_stockout_detection(self):
        """Verifies deficit items are flagged properly."""
        alerts = check_critical_stockouts()
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0)

    def test_logistics_route_calculation(self):
        """Verifies transit distance and toll cost calculations."""
        route = calculate_route("Kanpur", "Agra")
        self.assertEqual(route["origin"], "Kanpur")
        self.assertEqual(route["destination"], "Agra")
        self.assertGreater(route["distance_km"], 200)
        self.assertGreater(route["total_estimated_cost_inr"], 0)

    def test_risk_reporting(self):
        """Verifies regional risk scoring."""
        risk = get_cluster_risk_report("Kanpur")
        self.assertIn("composite_risk_score", risk)
        self.assertGreaterEqual(risk["composite_risk_score"], 0)
        self.assertLessEqual(risk["composite_risk_score"], 100)

    def test_orchestrator_assessment(self):
        """Verifies multi-agent orchestrator runs end-to-end without crashing."""
        orchestrator = StateMasterOrchestrator()
        result = orchestrator.run_state_assessment()
        self.assertIn("system_status", result)
        self.assertIn("orchestrator_synthesis", result)


if __name__ == "__main__":
    unittest.main()
