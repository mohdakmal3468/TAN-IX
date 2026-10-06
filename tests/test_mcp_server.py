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
        self.assertEqual(stock["reorder_point"], 1200.0)
        self.assertTrue(stock["is_below_reorder"])

    def test_mcp_list_below_reorder_point(self):
        """Tests domain tool list_below_reorder_point via MCP."""
        deficits = list_below_reorder_point("Agra")
        self.assertIsInstance(deficits, list)
        belt_def = next((d for d in deficits if d["product"] == "belts"), None)
        self.assertIsNotNone(belt_def)
        self.assertEqual(belt_def["deficit"], 1020.0)

    def test_mcp_find_surplus_districts(self):
        """Tests domain tool find_surplus_districts via MCP."""
        surplus = find_surplus_districts("belts", min_surplus=500)
        self.assertIsInstance(surplus, list)
        self.assertGreater(len(surplus), 0)
        first = surplus[0]
        self.assertEqual(first["district"], "Kanpur")
        self.assertGreater(first["surplus_available"], 1000)

    def test_inventory_agent_fetches_via_mcp_and_fallback(self):
        """Tests Inventory Agent switching between USE_MCP=true and USE_MCP=false."""
        agent_controller = DistrictInventoryAgent()

        # 1. MCP Mode
        os.environ["USE_MCP"] = "true"
        stock_mcp = agent_controller.fetch_stock("Agra", "belts")
        self.assertEqual(stock_mcp["source"], "MCP_SERVER")
        self.assertEqual(stock_mcp["quantity"], 180.0)

        analysis_mcp = agent_controller.analyze_inventory("Agra")
        self.assertEqual(analysis_mcp["execution_mode"], "MCP_TOOLSET")
        self.assertGreater(len(analysis_mcp["alerts"]), 0)

        # 2. Direct Database Fallback Mode
        os.environ["USE_MCP"] = "false"
        stock_direct = agent_controller.fetch_stock("Agra", "belts")
        self.assertEqual(stock_direct["source"], "DIRECT_DATABASE")
        self.assertEqual(stock_direct["quantity"], 180.0)

        analysis_direct = agent_controller.analyze_inventory("Agra")
        self.assertEqual(analysis_direct["execution_mode"], "DIRECT_DATABASE")


if __name__ == "__main__":
    unittest.main()
