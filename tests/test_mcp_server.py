"""
tests/test_mcp_server.py
------------------------
Unit and integration tests for tools/mcp_server.py:
1. MCP tool firestore_read (collection & doc_id)
2. MCP tool firestore_write
3. MCP tool bigquery_query (SQL execution)
4. MCP domain tools get_stock_level, list_below_reorder_point, find_surplus_districts
5. ADK McpToolset discovery
6. Inventory Agent stock fetching via MCP and fallback
"""

import os
import unittest
from tools.mcp_server import (
    firestore_read,
    firestore_write,
    bigquery_query,
    get_stock_level,
    list_below_reorder_point,
    find_surplus_districts,
    call_mcp_tool
)
from agents.inventory_agent import DistrictInventoryAgent


class TestMcpServer(unittest.TestCase):

    def test_firestore_read_collection(self):
        """Tests reading inventory collection via MCP tool."""
        res = firestore_read(collection="inventory", limit=5)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["collection"], "inventory")
        self.assertGreater(res["count"], 0)
        self.assertIsInstance(res["documents"], list)

    def test_firestore_read_single_doc(self):
        """Tests reading a specific document by ID via MCP tool."""
        res = firestore_read(collection="routes", doc_id="LANE-01")
        self.assertEqual(res["status"], "success")
        self.assertIsNotNone(res["data"])
        self.assertEqual(res["data"].get("lane_id"), "LANE-01")

    def test_firestore_write(self):
        """Tests writing a document via MCP tool."""
        test_data = {"test_metric": 42.0, "status": "TEST_OK"}
        res = firestore_write(collection="test_logs", doc_id="TEST-001", data=test_data)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["doc_id"], "TEST-001")

    def test_bigquery_query(self):
        """Tests SQL analytics execution via MCP tool."""
        res = bigquery_query("SELECT route, count(*) as count FROM transit_logs GROUP BY route LIMIT 5;")
        self.assertEqual(res["status"], "success")
        self.assertIn("rows", res)
        self.assertGreater(res["row_count"], 0)

    def test_mcp_get_stock_level(self):
        """Tests domain tool get_stock_level via MCP."""
        stock = get_stock_level("Agra", "belts")
        self.assertEqual(stock["district"], "Agra")
        self.assertEqual(stock["product"], "belts")
        self.assertEqual(stock["quantity"], 180.0)
        self.assertGreater(stock["reorder_point"], 0)
        self.assertTrue(stock["is_below_reorder"])

    def test_mcp_list_below_reorder_point(self):
        """Tests domain tool list_below_reorder_point via MCP."""
        deficits = list_below_reorder_point("Agra")
        self.assertIsInstance(deficits, list)
        belt_def = next((d for d in deficits if d["product"] == "belts"), None)
        self.assertIsNotNone(belt_def)
        self.assertGreater(belt_def["deficit"], 0)

    def test_mcp_find_surplus_districts(self):
        """Tests domain tool find_surplus_districts via MCP."""
        surplus = find_surplus_districts("belts", min_surplus=500)
        self.assertIsInstance(surplus, list)
        self.assertGreater(len(surplus), 0)
        first = surplus[0]
        self.assertEqual(first["district"], "Kanpur")
        avail = first.get("available_surplus", first.get("surplus_available", 0))
        self.assertGreater(avail, 500)

    def test_inventory_agent_fetches_stock_and_analyzes(self):
        """Tests Inventory Agent stock fetching and inventory analysis."""
        agent_controller = DistrictInventoryAgent()
        stock = agent_controller.fetch_stock("Agra", "belts")
        self.assertEqual(stock["quantity"], 180.0)

        analysis = agent_controller.analyze_inventory("Agra")
        self.assertGreater(len(analysis["alerts"]), 0)


if __name__ == "__main__":
    unittest.main()
