"""
tools/mcp_server.py
-------------------
Model Context Protocol (MCP) Server for the TAN-IX UP Leather Supply Chain.
Exposes standardized MCP tools for:
1. firestore_read(collection, doc_id, limit) -> Reads collections or documents
2. firestore_write(collection, doc_id, data, merge) -> Writes or merges documents
3. bigquery_query(query) -> Runs SQL analytics across shipments and order logs
4. get_stock_level(district, product) -> Retrieves warehouse inventory and runway
5. list_below_reorder_point(district) -> Audits products needing replenishment
6. find_surplus_districts(product, min_surplus) -> Finds clusters with excess stock

Supports:
- ADK McpToolset integration via stdio connection params.
- Direct fallback execution behind USE_MCP=true/false environment flag.
"""

import os
import sys
import json
import sqlite3
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Ensure root directory is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from mcp.server.mcpserver import MCPServer
from tools.firestore_client import get_document, set_document, list_documents

DATA_DIR = os.path.join(ROOT_DIR, "data")
MOCK_DIR = os.path.join(DATA_DIR, "firestore_mock")
SQLITE_DB_PATH = os.path.join(DATA_DIR, "leather_logistics.db")

# Initialize Model Context Protocol Server
server = MCPServer("tan-ix-logistics-mcp")


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
    col_clean = collection.strip().lower()

    if doc_id:
        # Fetch single document
        doc = get_document(col_clean, doc_id)
        if doc is not None:
            return {"status": "success", "collection": col_clean, "doc_id": doc_id, "data": doc}

        # Fallback to local JSON files
        mock_file = os.path.join(MOCK_DIR, f"{col_clean}.json")
        if not os.path.exists(mock_file):
            mock_file = os.path.join(DATA_DIR, f"{col_clean}.json")

        if os.path.exists(mock_file):
            try:
                with open(mock_file, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    for item in items:
                        if (item.get("id") == doc_id or item.get("_id") == doc_id
                                or item.get(f"{col_clean[:-1]}_id") == doc_id
                                or item.get("inventory_id") == doc_id
                                or item.get("event_id") == doc_id
                                or item.get("lane_id") == doc_id):
                            return {"status": "success", "collection": col_clean, "doc_id": doc_id, "data": item}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "not_found", "collection": col_clean, "doc_id": doc_id, "data": None}

    # Fetch collection list
    docs = list_documents(col_clean, limit=limit)
    if docs:
        return {"status": "success", "collection": col_clean, "count": len(docs), "documents": docs}

    # Fallback to local mock
    mock_file = os.path.join(MOCK_DIR, f"{col_clean}.json")
    if not os.path.exists(mock_file):
        mock_file = os.path.join(DATA_DIR, f"{col_clean}.json")

    if os.path.exists(mock_file):
        try:
            with open(mock_file, "r", encoding="utf-8") as f:
                items = json.load(f)
                return {"status": "success", "collection": col_clean, "count": len(items[:limit]), "documents": items[:limit]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "empty", "collection": col_clean, "count": 0, "documents": []}


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
    col_clean = collection.strip().lower()
    success = set_document(col_clean, doc_id, data, merge=merge)

    # Also sync to local mock file for consistent offline testing
    mock_file = os.path.join(MOCK_DIR, f"{col_clean}.json")
    if os.path.exists(mock_file):
        try:
            with open(mock_file, "r", encoding="utf-8") as f:
                records = json.load(f)
            found = False
            for idx, r in enumerate(records):
                if r.get("id") == doc_id or r.get("inventory_id") == doc_id or r.get("request_id") == doc_id:
                    records[idx] = {**r, **data} if merge else data
                    found = True
                    break
            if not found:
                records.append({**data, "id": doc_id})
            with open(mock_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        except Exception:
            pass

    return {
        "status": "success",
        "collection": col_clean,
        "doc_id": doc_id,
        "firestore_synced": success,
        "data_written": data
    }


# ==============================================================================
# 3. MCP TOOL: BIGQUERY QUERY
# ==============================================================================

@server.tool()
def bigquery_query(query: str) -> Dict[str, Any]:
    """Executes a SQL analytics query across historical shipment and order logs.

    Queries Google Cloud BigQuery or the local SQLite database (data/leather_logistics.db).
    Tables: transit_logs, order_history.

    Args:
        query: Standard SQL query string.

    Returns:
        Dict[str, Any]: Execution results containing row count, column names, and row dictionaries.
    """
    clean_q = query.strip()

    # Try local SQLite fallback
    if os.path.exists(SQLITE_DB_PATH):
        try:
            # Replace BigQuery dataset prefixes if present (e.g. `leather_logistics.transit_logs` -> `transit_logs`)
            sqlite_q = clean_q.replace("leather_logistics.", "").replace("`leather_logistics`.", "")
            sqlite_q = sqlite_q.replace("`", "")

            conn = sqlite3.connect(SQLITE_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sqlite_q)
            rows = cursor.fetchall()
            col_names = [d[0] for d in cursor.description] if cursor.description else []
            dict_rows = [dict(r) for r in rows]
            conn.close()

            return {
                "status": "success",
                "engine": "sqlite_fallback",
                "row_count": len(dict_rows),
                "columns": col_names,
                "rows": dict_rows[:100]  # Cap results for safety
            }
        except Exception as e:
            return {"status": "error", "engine": "sqlite", "error": str(e), "query": clean_q}

    return {"status": "error", "message": "Database not initialized. Please run scripts/setup_bigquery.py."}


# ==============================================================================
# 4. MCP DOMAIN TOOL: GET STOCK LEVEL
# ==============================================================================

@server.tool()
def get_stock_level(district: str, product: str) -> Dict[str, Any]:
    """Retrieves current warehouse stock, unit, and runway for a product in a district.

    Args:
        district: District cluster name (Kanpur, Unnao, Agra, Noida).
        product: Product commodity name (shoes, belts, bags, jackets).

    Returns:
        Dict[str, Any]: Stock balance dictionary with quantity, days left, and reorder status.
    """
    d_clean = district.capitalize().strip()
    p_clean = product.lower().strip()

    # Query inventory over Firestore or local fallback
    read_res = firestore_read(collection="inventory", limit=100)
    items = read_res.get("documents", [])

    matched = None
    for item in items:
        if item.get("district", "").capitalize() == d_clean and item.get("product", "").lower() == p_clean:
            matched = item
            break

    if matched:
        qty = float(matched.get("quantity", 0.0))
        burn = float(matched.get("daily_burn_rate", 100.0))
        reorder = float(matched.get("reorder_point", 1000.0))
        days_left = round(qty / max(1.0, burn), 1)

        return {
            "district": d_clean,
            "product": p_clean,
            "quantity": qty,
            "unit": matched.get("unit", "units"),
            "daily_burn_rate": burn,
            "reorder_point": reorder,
            "days_left": days_left,
            "status": matched.get("status", "NORMAL"),
            "is_below_reorder": qty < reorder
        }

    return {
        "district": d_clean,
        "product": p_clean,
        "quantity": 0.0,
        "unit": "units",
        "daily_burn_rate": 100.0,
        "reorder_point": 1000.0,
        "days_left": 0.0,
        "status": "NOT_FOUND",
        "is_below_reorder": True
    }


# ==============================================================================
# 5. MCP DOMAIN TOOLS: REORDER AUDIT & SURPLUS SEARCH
# ==============================================================================

@server.tool()
def list_below_reorder_point(district: str) -> List[Dict[str, Any]]:
    """Lists all commodities in a district warehouse that have fallen below their safety reorder point.

    Args:
        district: District cluster name (Kanpur, Unnao, Agra, Noida).

    Returns:
        List[Dict[str, Any]]: Commodities in deficit requiring replenishment.
    """
    d_clean = district.capitalize().strip()
    read_res = firestore_read(collection="inventory", limit=100)
    items = read_res.get("documents", [])

    deficits = []
    for item in items:
        if item.get("district", "").capitalize() == d_clean:
            qty = float(item.get("quantity", 0.0))
            reorder = float(item.get("reorder_point", 1000.0))
            if qty < reorder:
                deficits.append({
                    "district": d_clean,
                    "product": item.get("product", ""),
                    "quantity": qty,
                    "reorder_point": reorder,
                    "deficit": round(reorder - qty, 1),
                    "days_left": round(qty / max(1.0, float(item.get("daily_burn_rate", 100.0))), 1)
                })

    return deficits


@server.tool()
def find_surplus_districts(product: str, min_surplus: float = 0.0) -> List[Dict[str, Any]]:
    """Identifies districts holding surplus inventory of a product that can act as transfer donors.

    Args:
        product: Name of the product to replenish.
        min_surplus: Minimum excess units above reorder point required (default: 0.0).

    Returns:
        List[Dict[str, Any]]: Donor candidates with available surplus.
    """
    p_clean = product.lower().strip()
    read_res = firestore_read(collection="inventory", limit=100)
    items = read_res.get("documents", [])

    surplus_districts = []
    for item in items:
        if item.get("product", "").lower() == p_clean:
            qty = float(item.get("quantity", 0.0))
            reorder = float(item.get("reorder_point", 1000.0))
            excess = qty - reorder
            if excess > min_surplus:
                surplus_districts.append({
                    "district": item.get("district", ""),
                    "product": p_clean,
                    "current_quantity": qty,
                    "reorder_point": reorder,
                    "surplus_available": round(excess, 1)
                })

    surplus_districts.sort(key=lambda x: x["surplus_available"], reverse=True)
    return surplus_districts


# ==============================================================================
# 6. CLIENT HELPERS & ADK MCP TOOLSET FACTORY
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


# In-process tool dispatcher for fallback and direct programmatic calls
TOOL_DISPATCHER = {
    "firestore_read": firestore_read,
    "firestore_write": firestore_write,
    "bigquery_query": bigquery_query,
    "get_stock_level": get_stock_level,
    "list_below_reorder_point": list_below_reorder_point,
    "find_surplus_districts": find_surplus_districts
}


def call_mcp_tool(tool_name: str, **kwargs) -> Any:
    """Executes an MCP tool directly via dispatcher or fallback."""
    if tool_name not in TOOL_DISPATCHER:
        raise ValueError(f"Unknown MCP tool '{tool_name}'. Available: {list(TOOL_DISPATCHER.keys())}")
    return TOOL_DISPATCHER[tool_name](**kwargs)


# ==============================================================================
# MAIN RUNNER (Starts Stdio Transport for MCP Clients)
# ==============================================================================

if __name__ == "__main__":
    # Start standard I/O transport listening for MCP client requests (ADK, Claude, etc.)
    server.run("stdio")
