"""
tools package initialization.
Exports tool functions for Firestore, BigQuery, Logistics, Risk, Policy Vector Search, and Discord.
"""

from tools.firestore_tools import get_all_clusters_inventory, get_cluster_inventory, update_cluster_inventory, check_critical_stockouts
from tools.logistics_tools import calculate_route, get_available_fleet
from tools.risk_tools import get_cluster_risk_report, simulate_disruption, clear_disruptions
from tools.bigquery_tools import query_historical_shipments, get_corridor_performance_stats
from tools.vector_tools import search_policy_docs
from tools.discord_tools import send_discord_approval_request, record_approval_decision
from tools.firestore_client import (
    get_firestore_client,
    get_document,
    set_document,
    list_documents,
    batch_write_documents,
    get_collection_count
)

from tools.inventory_tools import (
    get_stock_level,
    days_of_stock_left,
    list_below_reorder_point,
    find_surplus_districts
)

__all__ = [
    "get_all_clusters_inventory",
    "get_cluster_inventory",
    "update_cluster_inventory",
    "check_critical_stockouts",
    "calculate_route",
    "get_available_fleet",
    "get_cluster_risk_report",
    "simulate_disruption",
    "clear_disruptions",
    "query_historical_shipments",
    "get_corridor_performance_stats",
    "search_policy_docs",
    "send_discord_approval_request",
    "record_approval_decision",
    "get_firestore_client",
    "get_document",
    "set_document",
    "list_documents",
    "batch_write_documents",
    "get_collection_count",
    "get_stock_level",
    "days_of_stock_left",
    "list_below_reorder_point",
    "find_surplus_districts"
]
