"""
tests/test_policy_tools.py
--------------------------
Unit and integration tests for tools/policy_tools.py and policy vector search.
"""

import unittest
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from tools.policy_tools import search_policy


class TestPolicyTools(unittest.TestCase):
    """Test suite for policy vector search functionality."""

    def test_search_delivery_sla_agra(self):
        """Test user requested query 'delivery SLA for Agra'."""
        results = search_policy("delivery SLA for Agra", top_k=3)
        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 1)

        top_match = results[0]
        self.assertEqual(top_match["doc_name"], "delivery_sla.md")
        self.assertIn("Agra", top_match["section"])
        self.assertGreater(top_match["similarity_score"], 0.4)
        self.assertIn("Agra", top_match["cluster_scope"])
        self.assertIn("24.0 hours", top_match["full_clause"])

    def test_search_transit_permit_rules(self):
        """Test query for transit permits and e-way bill rules."""
        results = search_policy("transit permit e-way bill threshold", top_k=2)
        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 1)

        doc_names = [r["doc_name"] for r in results]
        self.assertIn("transit_permits.md", doc_names)

    def test_search_emergency_freight_subsidy(self):
        """Test query for emergency freight and ODOP subsidy."""
        results = search_policy("emergency freight ODOP 15% subsidy", top_k=2)
        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 1)

        doc_names = [r["doc_name"] for r in results]
        self.assertIn("emergency_freight.md", doc_names)

    def test_search_approval_limits(self):
        """Test query for financial approval limits."""
        results = search_policy("approval limits Tier 1 autonomous AI", top_k=2)
        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 1)

        doc_names = [r["doc_name"] for r in results]
        self.assertIn("approval_limits.md", doc_names)

    def test_search_carrier_compliance(self):
        """Test query for carrier compliance standards."""
        results = search_policy("carrier compliance GPS ping 10 minutes", top_k=2)
        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 1)

        doc_names = [r["doc_name"] for r in results]
        self.assertIn("carrier_compliance.md", doc_names)

    def test_search_blockade_handling(self):
        """Test query for highway blockade and winter fog rerouting."""
        results = search_policy("Yamuna Expressway winter fog blockade rerouting", top_k=2)
        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 1)

        doc_names = [r["doc_name"] for r in results]
        self.assertIn("blockade_handling.md", doc_names)

    def test_top_k_parameter(self):
        """Test that top_k limit is respected."""
        results = search_policy("leather delivery transit", top_k=2)
        self.assertLessEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
