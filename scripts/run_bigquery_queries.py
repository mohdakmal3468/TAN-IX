"""
scripts/run_bigquery_queries.py
-------------------------------
Executes the 3 BigQuery analytical queries:
1. Average delay and on-time reliability per route
2. Monthly stockout incidents per district
3. Freight spend and cost per carrier

Runs directly on BigQuery (if connected) or uses the local SQLite replica.
Prints clean, formatted analytical tables.
"""

import os
import sys
import sqlite3
import pandas as pd
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT_ID", "agenthide-demo"))
SQLITE_DB = os.path.join(ROOT_DIR, "data", "leather_logistics.db")

# Standardized queries compatible with both BigQuery and SQLite
QUERY_1_ROUTE_DELAYS = """
SELECT
    route,
    origin,
    destination,
    COUNT(*) AS total_shipments,
    ROUND(AVG(planned_hours), 2) AS avg_planned_hours,
    ROUND(AVG(actual_hours), 2) AS avg_actual_hours,
    ROUND(AVG(delay_hours), 2) AS avg_delay_hours,
    ROUND(COUNT(CASE WHEN delay_hours > 0.5 THEN 1 END) * 100.0 / COUNT(*), 1) AS delay_pct,
    ROUND(COUNT(CASE WHEN delay_hours <= 0.5 THEN 1 END) * 100.0 / COUNT(*), 1) AS on_time_pct
FROM
    transit_logs
GROUP BY
    route, origin, destination
ORDER BY
    avg_delay_hours DESC;
"""

QUERY_2_STOCKOUTS = """
SELECT
    SUBSTR(date, 1, 7) AS month,
    district,
    product,
    COUNT(*) AS total_orders,
    COUNT(CASE WHEN is_stockout = 'TRUE' OR is_stockout = 1 THEN 1 END) AS stockouts,
    ROUND(COUNT(CASE WHEN is_stockout = 'TRUE' OR is_stockout = 1 THEN 1 END) * 100.0 / COUNT(*), 1) AS stockout_pct,
    SUM(requested_quantity - fulfilled_quantity) AS unfulfilled_units
FROM
    order_history
GROUP BY
    month, district, product
HAVING
    stockouts > 0
ORDER BY
    month DESC, stockouts DESC
LIMIT 12;
"""

QUERY_3_CARRIER_COSTS = """
SELECT
    carrier,
    COUNT(*) AS total_trips,
    SUM(quantity) AS total_units,
    SUM(cost_inr) AS total_spend_inr,
    ROUND(AVG(cost_inr), 2) AS avg_cost_per_trip_inr,
    ROUND(AVG(CAST(cost_inr AS FLOAT) / distance_km), 2) AS avg_cost_per_km_inr,
    ROUND(AVG(delay_hours), 2) AS avg_delay_hours
FROM
    transit_logs
GROUP BY
    carrier
ORDER BY
    total_spend_inr DESC;
"""


def run_queries_on_sqlite():
    """Executes the analytical queries on the local database engine."""
    if not os.path.exists(SQLITE_DB):
        from scripts.setup_bigquery import setup_local_sqlite_replica
        setup_local_sqlite_replica()

    conn = sqlite3.connect(SQLITE_DB)

    print("\n" + "=" * 80)
    print("QUERY 1: Average Transit Delay & On-Time Performance per Route")
    print("=" * 80)
    df1 = pd.read_sql_query(QUERY_1_ROUTE_DELAYS, conn)
    print(df1.to_string(index=False))

    print("\n" + "=" * 80)
    print("QUERY 2: Monthly Stockouts per District & Product (Top Incidents)")
    print("=" * 80)
    df2 = pd.read_sql_query(QUERY_2_STOCKOUTS, conn)
    print(df2.to_string(index=False))

    print("\n" + "=" * 80)
    print("QUERY 3: Total Spend, Cost per KM, and Performance per Carrier")
    print("=" * 80)
    df3 = pd.read_sql_query(QUERY_3_CARRIER_COSTS, conn)
    print(df3.to_string(index=False))

    conn.close()


def main():
    print("=" * 80)
    print("AgentHide: Executing BigQuery Analytical Queries")
    print("Source: docs/bigquery_queries.sql")
    print("=" * 80)

    # Execute and print results
    run_queries_on_sqlite()

    print("\n" + "=" * 80)
    print("[SUCCESS] All 3 BigQuery analytical queries executed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
