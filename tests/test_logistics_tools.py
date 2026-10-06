"""
tests/test_logistics_tools.py
-----------------------------
Unit test suite for tools/logistics_tools.py:
1. get_routes(origin, destination)
2. get_carriers()
3. calculate_route_cost(route_id, carrier_id, quantity)
4. mark_route_blocked(route_id)
"""

import unittest
from tools.logistics_tools import (
    get_routes,
    get_carriers,
    calculate_route_cost,
    mark_route_blocked,
    unblock_route,
    reset_blocked_routes
)


class TestLogisticsTools(unittest.TestCase):

    def setUp(self):
        # Reset any blocked routes before each test
        reset_blocked_routes()

    def tearDown(self):
        # Clean up after each test
        reset_blocked_routes()

    def test_get_routes_valid(self):
        """Tests finding active routes between Kanpur and Agra."""
        routes = get_routes("Kanpur", "Agra")
        self.assertIsInstance(routes, list)
        self.assertGreater(len(routes), 0, "Should return at least one route lane between Kanpur and Agra")

        first_route = routes[0]
        self.assertEqual(first_route["origin"], "Kanpur")
        self.assertEqual(first_route["destination"], "Agra")
        self.assertGreater(first_route["distance_km"], 200)
        self.assertGreater(first_route["standard_transit_hours"], 0)
        self.assertIn("route_id", first_route)
        self.assertIn("route_name", first_route)

    def test_get_carriers(self):
        """Tests retrieving commercial carrier profiles."""
        carriers = get_carriers()
        self.assertIsInstance(carriers, list)
        self.assertGreaterEqual(len(carriers), 4, "Should load all 4 registered commercial carriers")

        carrier_ids = [c["carrier_id"] for c in carriers]
        self.assertIn("CAR-01", carrier_ids)
        self.assertIn("CAR-02", carrier_ids)

        for c in carriers:
            self.assertIn("name", c)
            self.assertGreater(c["speed_kmh"], 0)
            self.assertGreater(c["base_rate_per_km_inr"], 0)
            self.assertGreater(c["reliability_pct"], 0)

    def test_calculate_route_cost(self):
        """Tests calculating itemized transit cost and duration."""
        # Calculate cost for Kanpur -> Agra (LANE-03) using UP State Freight Express (CAR-02)
        cost_breakdown = calculate_route_cost("LANE-03", "CAR-02", quantity=1000.0)

        self.assertNotIn("error", cost_breakdown)
        self.assertEqual(cost_breakdown["route_id"], "LANE-03")
        self.assertEqual(cost_breakdown["carrier_id"], "CAR-02")
        self.assertGreater(cost_breakdown["base_freight_inr"], 5000)
        self.assertGreater(cost_breakdown["toll_inr"], 0)
        self.assertGreater(cost_breakdown["handling_inr"], 0)
        self.assertGreater(cost_breakdown["total_cost_inr"], 5000)
        self.assertGreater(cost_breakdown["estimated_transit_hours"], 2.0)
        self.assertIn("vehicle_assigned", cost_breakdown)

    def test_mark_route_blocked(self):
        """Tests route blocking mechanism and exclusion from active options."""
        # 1. Verify route initially exists
        initial_routes = get_routes("Kanpur", "Agra")
        self.assertGreater(len(initial_routes), 0)
        target_route_id = initial_routes[0]["route_id"]

        # 2. Mark the route as blocked
        block_result = mark_route_blocked(target_route_id)
        self.assertTrue(block_result["success"])
        self.assertEqual(block_result["status"], "BLOCKED")

        # 3. Verify get_routes now excludes the blocked route
        updated_routes = get_routes("Kanpur", "Agra")
        updated_route_ids = [r["route_id"] for r in updated_routes]
        self.assertNotIn(target_route_id, updated_route_ids, "Blocked route must be excluded from get_routes options")

        # 4. Verify calculate_route_cost refuses blocked route
        cost_attempt = calculate_route_cost(target_route_id, "CAR-02", quantity=500.0)
        self.assertIn("error", cost_attempt)
        self.assertIn("blocked", cost_attempt["error"].lower())

        # 5. Unblock and verify restored
        unblock_res = unblock_route(target_route_id)
        self.assertTrue(unblock_res["success"])
        restored_routes = get_routes("Kanpur", "Agra")
        restored_ids = [r["route_id"] for r in restored_routes]
        self.assertIn(target_route_id, restored_ids, "Route should be available again after unblocking")


if __name__ == "__main__":
    unittest.main()
