"""
tools/mcp_server.py
-------------------
Model Context Protocol (MCP) Server for the AgentHide UP Leather Supply Chain.
Exposes standardized MCP tools for:
1. firestore_read(collection, doc_id, limit) -> Reads collections or documents
2. firestore_write(collection, doc_id, data, merge) -> Writes or merges documents
3. bigquery_query(query) -> Runs SQL analytics across shipments and order logs
4. get_stock_level(district, product) -> Retrieves warehouse inventory and runway
5. list_below_reorder_point(district) -> Audits products needing replenishment
6. find_surplus_districts(product, min_surplus) -> Finds clusters with excess stock

Supports:
- ADK McpToolset integration via stdio connection params.
- In-process execution through call_mcp_tool() when USE_MCP=true.

Design rules:
- The inventory tools delegate to tools/inventory_tools.py, so MCP and direct mode
  always return the same fields and the same predicted reorder points.
- Local mock-file handling lives only in tools/firestore_client.py (not repeated here).
- Errors are raised or returned as errors; no made-up default data is returned.
"""

import contextlib
import os
import sys
import sqlite3
from typing import Dict, Any, List
from dotenv import load_dotenv

# Ensure root directory is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

try:
    from mcp.server.mcpserver import MCPServer          # mcp >= 2.0
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer  # mcp 1.x (what google-adk installs)

from tools import inventory_tools
from tools.firestore_client import get_document, set_document, list_documents

DATA_DIR = os.path.join(ROOT_DIR, "data")
SQLITE_DB_PATH = os.path.join(DATA_DIR, "leather_logistics.db")

# Initialize Model Context Protocol Server
server = MCPServer("agenthide-logistics-mcp")


# ==============================================================================
# 1. MCP TOOL: FIRESTORE READ
# ==============================================================================

@server.tool()
def firestore_read(collection: str, doc_id: str = "", limit: int = 50) -> Dict[str, Any]:
    """Reads data from a Firestore collection or retrieves a single document by ID.

    Args:
        collection: The target Firestore collection name (e.g. 'inventory', 'hubs', 'routes', 'disruptions').
        doc_id: Optional unique document ID. If empty, returns a list of documents in the collection.
        limit: Maximum number of documents to return when listing (default: 50).

    Returns:
        Dict[str, Any]: Document dictionary or list of documents with metadata.
    """
    col = collection.strip().lower()

    if doc_id:
        doc = get_document(col, doc_id)
        if doc is None:
            return {"status": "not_found", "collection": col, "doc_id": doc_id, "data": None}
        return {"status": "success", "collection": col, "doc_id": doc_id, "data": doc}

    docs = list_documents(col, limit=limit)
    return {
        "status": "success" if docs else "empty",
        "collection": col,
        "count": len(docs),
        "documents": docs,
    }


# ==============================================================================
# 2. MCP TOOL: FIRESTORE WRITE
# ==============================================================================

@server.tool()
def firestore_write(collection: str, doc_id: str, data: Dict[str, Any], merge: bool = True) -> Dict[str, Any]:
    """Writes or merges a document into a Firestore collection.

    Args:
        collection: The target Firestore collection name (e.g. 'inventory', 'shipments', 'approvals').
        doc_id: Unique document identifier to create or update.
        data: Dictionary of fields to store.
        merge: If True, merges fields into existing document without overwriting (default: True).

    Returns:
        Dict[str, Any]: Status confirmation dictionary.
    """
    col = collection.strip().lower()
    # set_document already keeps the local mock file in sync, so it is not repeated here.
    written = set_document(col, doc_id, data, merge=merge)
    return {
        "status": "success" if written else "error",
        "collection": col,
        "doc_id": doc_id,
        "firestore_synced": written,
        "data_written": data,
    }


# ==============================================================================
# 3. MCP TOOL: BIGQUERY QUERY
# ==============================================================================

@server.tool()
def bigquery_query(query: str) -> Dict[str, Any]:
    """Executes a SQL analytics query across historical shipment and order logs.

    Runs against the local SQLite database (data/leather_logistics.db).
    Tables: transit_logs, order_history.

    Args:
        query: Standard SQL query string.

    Returns:
        Dict[str, Any]: Execution results containing row count, column names, and row dictionaries.
    """
    if not os.path.exists(SQLITE_DB_PATH):
        raise FileNotFoundError(f"{SQLITE_DB_PATH} not found. Run scripts/setup_bigquery.py first.")

    # Accept BigQuery-style names such as `leather_logistics.transit_logs`
    sql = query.strip().replace("`leather_logistics`.", "").replace("leather_logistics.", "").replace("`", "")

    try:
        with contextlib.closing(sqlite3.connect(SQLITE_DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            rows = [dict(r) for r in cursor.fetchall()]
            columns = [c[0] for c in cursor.description] if cursor.description else []
    except sqlite3.Error as exc:
        # Returned (not raised) so the calling LLM can read the message and fix its SQL
        return {"status": "error", "engine": "sqlite", "error": str(exc), "query": query}

    return {
        "status": "success",
        "engine": "sqlite",
        "row_count": len(rows),
        "columns": columns,
        "rows": rows[:100],   # cap results for safety
    }


# ==============================================================================
# 4-6. MCP DOMAIN TOOLS (delegate to tools/inventory_tools.py)
# ==============================================================================

@server.tool()
def get_stock_level(district: str, product: str) -> Dict[str, Any]:
    """Retrieves current warehouse stock, unit, and runway for a product in a district.

    Args:
        district: District cluster name (Kanpur, Unnao, Agra, Noida).
        product: Product commodity name (shoes, belts, bags, jackets).

    Returns:
        Dict[str, Any]: Stock balance with quantity, days left, predicted status and reorder flag.
        If the record does not exist, returns found=False with an error message.
    """
    stock = inventory_tools.get_stock_level(district, product)
    if not stock["found"]:
        return stock
    stock["days_left"] = inventory_tools.days_of_stock_left(district, product)
    stock["is_below_reorder"] = stock["quantity"] < stock["reorder_point"]
    return stock


@server.tool()
def list_below_reorder_point(district: str) -> List[Dict[str, Any]]:
    """Lists all commodities in a district warehouse that have fallen below their reorder point.

    Args:
        district: District cluster name (Kanpur, Unnao, Agra, Noida).

    Returns:
        List[Dict[str, Any]]: Commodities in deficit requiring replenishment.
    """
    return inventory_tools.list_below_reorder_point(district)


@server.tool()
def find_surplus_districts(product: str, min_surplus: float = 0.0) -> List[Dict[str, Any]]:
    """Identifies districts holding surplus inventory of a product that can act as transfer donors.

    Args:
        product: Name of the product to replenish.
        min_surplus: Minimum excess units above reorder point required (default: 0.0).

    Returns:
        List[Dict[str, Any]]: Donor candidates with available_surplus, largest first.
    """
    return inventory_tools.find_surplus_districts(product, min_surplus)


# ==============================================================================
# CLIENT HELPERS & ADK MCP TOOLSET FACTORY
# ==============================================================================

def get_mcp_server_path() -> str:
    """Returns absolute path to this MCP server script."""
    return os.path.abspath(__file__)


def get_mcp_connection_params():
    """Builds StdioConnectionParams for Google ADK McpToolset."""
    from mcp import StdioServerParameters
    from google.adk.tools.mcp_tool.mcp_toolset import StdioConnectionParams

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[get_mcp_server_path()],
        cwd=ROOT_DIR,
        env=os.environ.copy()
    )
    return StdioConnectionParams(server_params=server_params)


def get_mcp_toolset():
    """Instantiates a Google ADK McpToolset connecting to this MCP server."""
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
    return McpToolset(connection_params=get_mcp_connection_params())


# In-process tool dispatcher for programmatic calls (used when USE_MCP=true)
TOOL_DISPATCHER = {
    "firestore_read": firestore_read,
    "firestore_write": firestore_write,
    "bigquery_query": bigquery_query,
    "get_stock_level": get_stock_level,
    "list_below_reorder_point": list_below_reorder_point,
    "find_surplus_districts": find_surplus_districts
}


def call_mcp_tool(tool_name: str, **kwargs) -> Any:
    """Executes an MCP tool in-process through the dispatcher."""
    if tool_name not in TOOL_DISPATCHER:
        raise ValueError(f"Unknown MCP tool '{tool_name}'. Available: {list(TOOL_DISPATCHER.keys())}")
    return TOOL_DISPATCHER[tool_name](**kwargs)


# ==============================================================================
# MAIN RUNNER (Starts Stdio Transport for MCP Clients)
# ==============================================================================

if __name__ == "__main__":
    # Start standard I/O transport listening for MCP client requests (ADK, Claude, etc.)
    server.run("stdio")