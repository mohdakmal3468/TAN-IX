"""
tests/test_inventory_tools.py
-----------------------------
Unit tests for tools/inventory_tools.py:
1. get_stock_level(district, product)
2. days_of_stock_left(district, product)
3. list_below_reorder_point(district)
4. find_surplus_districts(product, min_surplus)
"""

import unittest
from tools.inventory_tools import (
    get_stock_level,
    days_of_stock_left,
    list_below_reorder_point,
    find_surplus_districts
)


class TestInventoryTools(unittest.TestCase):

    def test_get_stock_level_valid(self):
        """Tests retrieving stock level for Agra belts and Kanpur belts."""
        # 1. Agra belts (should exist and show deficit)
        agra_belts = get_stock_level("Agra", "belts")
        self.assertTrue(agra_belts["found"])
        self.assertEqual(agra_belts["district"], "Agra")
        self.assertEqual(agra_belts["product"], "belts")
        self.assertIsInstance(agra_belts["quantity"], float)
        self.assertGreater(agra_belts["reorder_point"], 0)

        # 2. Kanpur belts (should exist and show surplus)
        kanpur_belts = get_stock_level("Kanpur", "belts")
        self.assertTrue(kanpur_belts["found"])
        self.assertEqual(kanpur_belts["district"], "Kanpur")
        self.assertGreater(kanpur_belts["quantity"], 4000)

    def test_get_stock_level_not_found(self):
        """Tests handling of unknown district or product."""
        res = get_stock_level("UnknownDistrict", "shoes")
        self.assertFalse(res["found"])
        self.assertEqual(res["quantity"], 0.0)

    def test_days_of_stock_left(self):
        """Tests days of stock calculation for deficit vs surplus districts."""
        # Agra belts has critical low stock (e.g. 180 units / 140 burn rate ~= 1.3 days)
        days_agra = days_of_stock_left("Agra", "belts")
        self.assertIsInstance(days_agra, float)
        self.assertGreater(days_agra, 0.0)
        self.assertLess(days_agra, 10.0, "Agra belts should have fewer than 10 days of stock left")

        # Kanpur belts has healthy buffer
        days_kanpur = days_of_stock_left("Kanpur", "belts")
        self.assertIsInstance(days_kanpur, float)
        self.assertGreater(days_kanpur, 30.0, "Kanpur belts should have ample runway")

        # Nonexistent district
        days_invalid = days_of_stock_left("InvalidCity", "belts")
        self.assertEqual(days_invalid, 0.0)

    def test_list_below_reorder_point(self):
        """Tests auditing a district for stock items below reorder threshold."""
        deficits = list_below_reorder_point("Agra")
        self.assertIsInstance(deficits, list)
        self.assertGreater(len(deficits), 0, "Agra should flag at least one stock deficit")

        # Verify belts is in the deficit list
        deficit_products = [d["product"] for d in deficits]
        self.assertIn("belts", deficit_products, "Agra must flag belts as below reorder point")

        # Check required fields
        first_deficit = deficits[0]
        self.assertIn("deficit", first_deficit)
        self.assertIn("reorder_point", first_deficit)
        self.assertIn("days_left", first_deficit)
        self.assertIn("severity", first_deficit)

    def test_find_surplus_districts(self):
        """Tests locating donor districts with surplus stock."""
        # Search for belts with at least 1,000 units surplus
        donors = find_surplus_districts("belts", min_surplus=1000.0)
        self.assertIsInstance(donors, list)
        self.assertGreater(len(donors), 0, "Should find at least one donor district for belts")

        # Kanpur should be the prime donor
        donor_districts = [d["district"] for d in donors]
        self.assertIn("Kanpur", donor_districts, "Kanpur should be listed as a donor district for belts")

        # Agra must NOT be in the donor list for belts
        self.assertNotIn("Agra", donor_districts, "Agra has a deficit and cannot be a surplus donor")

        # Verify donor fields
        kanpur_donor = next(d for d in donors if d["district"] == "Kanpur")
        self.assertGreater(kanpur_donor["available_surplus"], 1000.0)
        self.assertIn("unit", kanpur_donor)


if __name__ == "__main__":
    unittest.main()
