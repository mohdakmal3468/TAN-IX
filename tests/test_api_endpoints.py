"""
tests/test_api_endpoints.py
---------------------------
Unit and integration tests for FastAPI REST endpoints in api/main.py:
1. CORS headers
2. GET /districts
3. GET /inventory (with ok/low/critical status colors)
4. GET /disruptions/active
5. GET /lanes/risk
6. GET /shipments
7. GET /dispatch-schedule
8. GET /approvals?status=pending
9. GET /kpis
10. POST /scenario/trigger & clear
"""

import unittest
from fastapi.testclient import TestClient
from api.main import app
from tools.risk_tools import clear_disruptions


class TestApiEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        clear_disruptions()

    def tearDown(self):
        clear_disruptions()

    def test_cors_middleware(self):
        """Tests that CORS middleware headers are properly returned."""
        response = self.client.options(
            "/inventory",
            headers={"Origin": "http://localhost:8501", "Access-Control-Request-Method": "GET"}
        )
        self.assertIn("access-control-allow-origin", response.headers)
        self.assertIn(response.headers["access-control-allow-origin"], ["*", "http://localhost:8501"])

    def test_get_districts(self):
        """Tests GET /districts returns all 4 clusters with metadata."""
        resp = self.client.get("/districts")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 4)
        names = [d["name"] for d in data["districts"]]
        self.assertIn("Kanpur", names)
        self.assertIn("Unnao", names)
        self.assertIn("Agra", names)
        self.assertIn("Noida", names)

    def test_get_inventory_with_status_colors(self):
        """Tests GET /inventory returns items with status_color (ok/low/critical)."""
        resp = self.client.get("/inventory")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data["total_items"], 0)
        self.assertIn("critical_count", data)
        self.assertIn("low_count", data)
        self.assertIn("ok_count", data)

        for item in data["inventory"]:
            self.assertIn(item["status_color"], ["ok", "low", "critical"])
            self.assertIn("days_left", item)
            self.assertIn("daily_burn_rate", item)
            self.assertIn("reorder_point", item)

    def test_get_disruptions_active(self):
        """Tests GET /disruptions/active returns mapped highway lanes."""
        resp = self.client.get("/disruptions/active")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["total"], 1)
        for d in data["disruptions"]:
            self.assertIn("event_id", d)
            self.assertIn("affected_lanes", d)
            self.assertIsInstance(d["affected_lanes"], list)

    def test_get_lanes_risk(self):
        """Tests GET /lanes/risk returns quantitative risk scores for all 14 UP lanes."""
        resp = self.client.get("/lanes/risk")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_lanes"], 14)
        self.assertIn(data["status"], ["NORMAL", "ELEVATED_RISK", "CRITICAL_ALERT"])
        for lane in data["lanes"]:
            self.assertIn("lane_id", lane)
            self.assertIn("risk_score", lane)
            self.assertIn("status_color", lane)
            self.assertIn("delay_in_days", lane)

    def test_get_shipments(self):
        """Tests GET /shipments returns paged shipments."""
        resp = self.client.get("/shipments?limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["returned"], 10)
        self.assertGreaterEqual(data["total_matching"], 10)

    def test_get_dispatch_schedule(self):
        """Tests GET /dispatch-schedule returns commercial transit manifests."""
        resp = self.client.get("/dispatch-schedule")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data["total_scheduled"], 0)
        first = data["schedule"][0]
        self.assertIn("carrier", first)
        self.assertIn("eta_hours", first)
        self.assertIn("vehicle_type", first)

    def test_get_approvals_pending(self):
        """Tests GET /approvals?status=pending returns pending human authorization requests."""
        resp = self.client.get("/approvals?status=pending")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status_filter"], "pending")
        self.assertIn("approvals", data)

    def test_get_kpis(self):
        """Tests GET /kpis returns all key executive performance indicators."""
        resp = self.client.get("/kpis")
        self.assertEqual(resp.status_code, 200)
        kpis = resp.json()
        self.assertIn("stockouts_prevented", kpis)
        self.assertIn("cost_saved_inr", kpis)
        self.assertIn("active_alerts_count", kpis)
        self.assertIn("pending_approvals_count", kpis)
        self.assertIn("total_inventory_items", kpis)

    def test_scenario_trigger_and_reset(self):
        """Tests POST /scenario/trigger fires blockade and reset clears it."""
        # 1. Trigger blockade
        trigger_resp = self.client.post("/scenario/trigger", json={
            "scenario_type": "highway_blockade",
            "cluster": "Unnao",
            "severity": "CRITICAL"
        })
        self.assertEqual(trigger_resp.status_code, 200)
        t_data = trigger_resp.json()
        self.assertTrue(t_data["success"])
        self.assertEqual(t_data["scenario"], "highway_blockade")
        self.assertGreater(t_data["lane_01_risk_score"], 70.0)

        # 2. Reset scenario
        reset_resp = self.client.post("/scenario/trigger", json={"scenario_type": "clear"})
        self.assertEqual(reset_resp.status_code, 200)
        r_data = reset_resp.json()
        self.assertTrue(r_data["success"])
        self.assertEqual(r_data["status"], "NORMAL")


if __name__ == "__main__":
    unittest.main()
