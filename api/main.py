"""
api/main.py
-----------
FastAPI backend service for TAN-IX:
State-Level Multi-Agent Supply Chain Risk & Inventory Manager for UP Leather Goods.

Core Endpoints:
- POST /stock-update: Validated via InventoryRecord Pydantic model -> saved to Firestore
- POST /disruption: Validated via DisruptionEvent Pydantic model -> saved to Firestore & Risk feed
- POST /shipment: Validated via Shipment Pydantic model -> saved to Firestore
- GET /health: Healthcheck endpoint
- GET /inventory/{district}: Live inventory records filtered by district
- POST /orchestrator/run: Triggers multi-agent reasoning & rebalance plan
- GET /approval/discord-callback: Human-in-the-Loop authorization callback
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Query, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import UP_CLUSTERS, FASTAPI_HOST, FASTAPI_PORT
from api.models import (
    InventoryRecord,
    DisruptionEvent,
    Shipment,
    ApprovalRequest,
    InventoryStatus
)
from tools.firestore_client import (
    set_document,
    get_document,
    list_documents
)
from tools.firestore_tools import (
    get_all_clusters_inventory,
    get_cluster_inventory,
    update_cluster_inventory,
    _load_local_data,
    _save_local_data
)
from tools.risk_tools import (
    get_cluster_risk_report,
    simulate_disruption,
    clear_disruptions,
    ACTIVE_DISRUPTIONS
)
from tools.bigquery_tools import get_corridor_performance_stats
from tools.vector_tools import search_policy_docs
from agents.orchestrator import StateMasterOrchestrator
from tools.discord_tools import PENDING_APPROVALS

# Initialize FastAPI application
app = FastAPI(
    title="TAN-IX Multi-Agent Supply Chain Engine",
    description="State-Level Multi-Agent Supply Chain Risk & Inventory Manager for Uttar Pradesh Leather Goods",
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for Streamlit dashboard and external integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = StateMasterOrchestrator()


# ==============================================================================
# 1. System & Health Endpoints
# ==============================================================================

@app.get("/", tags=["System"])
def root():
    """Welcome and system metadata endpoint."""
    return {
        "system": "TAN-IX (Tannery Intelligent eXchange)",
        "region": "Uttar Pradesh Leather Corridor (Kanpur, Unnao, Agra, Noida)",
        "status": "Operational",
        "documentation": "/docs",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint to verify backend service liveness."""
    return {
        "status": "ok",
        "service": "TAN-IX Multi-Agent API",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ==============================================================================
# 2. Inventory Endpoints
# ==============================================================================

@app.post("/stock-update", status_code=status.HTTP_201_CREATED, tags=["Inventory"])
def update_stock(record: InventoryRecord):
    """
    Validates and updates or adds an inventory record for a district warehouse.
    Saves to Firestore collection 'inventory' and synchronizes local cluster storage.
    """
    data = record.model_dump(mode="json")
    doc_id = record.inventory_id

    # 1. Save to Firestore via helper module
    saved_firestore = set_document("inventory", doc_id, data)

    # 2. Synchronize with local cluster warehouse data
    district_cap = record.district.capitalize()
    try:
        local_data = _load_local_data()
        clusters = local_data.get("clusters", {})
        if district_cap in clusters:
            clusters[district_cap]["inventory"][record.product] = {
                "quantity": int(record.quantity),
                "unit": record.unit,
                "min_threshold": int(record.reorder_point),
                "capacity": int(record.quantity * 2),
                "unit_cost_inr": int(record.unit_cost_inr or 300),
                "daily_burn_rate": record.daily_burn_rate,
                "status": record.status.value
            }
            _save_local_data(local_data)
    except Exception as e:
        print(f"[Warning] Local seed synchronization note: {e}")

    return {
        "success": True,
        "message": f"Inventory record '{doc_id}' for {record.district} ({record.product}) saved successfully.",
        "firestore_synced": saved_firestore,
        "record": data
    }


@app.get("/inventory/{district}", tags=["Inventory"])
def get_district_inventory(district: str):
    """
    Fetches all inventory records for the specified district (Kanpur, Unnao, Agra, Noida).
    """
    district_clean = district.capitalize().strip()
    valid_districts = ["Kanpur", "Unnao", "Agra", "Noida"]

    if district_clean not in valid_districts:
        raise HTTPException(
            status_code=404,
            detail=f"District '{district}' not recognized. Available districts: {', '.join(valid_districts)}"
        )

    # Fetch from Firestore helper or local inventory data
    matched_records = []
    firestore_docs = list_documents("inventory", limit=50)

    if firestore_docs:
        matched_records = [d for d in firestore_docs if d.get("district", "").capitalize() == district_clean]

    # Fallback to local inventory.json if firestore_docs is empty
    if not matched_records:
        inv_json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "inventory.json")
        if os.path.exists(inv_json_path):
            with open(inv_json_path, "r", encoding="utf-8") as f:
                all_records = json.load(f)
                matched_records = [r for r in all_records if r.get("district", "").capitalize() == district_clean]

    return {
        "district": district_clean,
        "record_count": len(matched_records),
        "inventory": matched_records
    }


@app.get("/clusters/status", tags=["Inventory"])
def get_clusters_status():
    """Returns the live overview of all 4 UP leather clusters."""
    inventory = get_all_clusters_inventory()
    combined = {}
    for c_name, meta in UP_CLUSTERS.items():
        combined[c_name] = {
            **meta,
            "warehouse_data": inventory.get(c_name, {})
        }
    return combined


# ==============================================================================
# 3. Disruption Endpoints
# ==============================================================================

@app.post("/disruption", status_code=status.HTTP_201_CREATED, tags=["Disruptions"])
def register_disruption(event: DisruptionEvent):
    """
    Registers a climate, regulatory, or infrastructure disruption event.
    Saves to Firestore collection 'disruptions' and injects into the active risk feed.
    """
    data = event.model_dump(mode="json")
    doc_id = event.event_id

    # 1. Save to Firestore
    saved_firestore = set_document("disruptions", doc_id, data)

    # 2. Inject into in-memory active disruptions feed for agents
    ACTIVE_DISRUPTIONS.append({
        "id": event.event_id,
        "cluster": event.location,
        "category": event.type.value,
        "severity": event.severity.value,
        "title": event.title,
        "description": event.description,
        "impact": f"Affects clusters: {', '.join(event.impacted_clusters)}"
    })

    return {
        "success": True,
        "message": f"Disruption event '{doc_id}' in {event.location} registered successfully.",
        "firestore_synced": saved_firestore,
        "event": data
    }


# ==============================================================================
# 4. Shipment Endpoints
# ==============================================================================

@app.post("/shipment", status_code=status.HTTP_201_CREATED, tags=["Logistics"])
def create_shipment(shipment: Shipment):
    """
    Creates or registers an inter-district shipment order.
    Saves to Firestore collection 'shipments'.
    """
    data = shipment.model_dump(mode="json")
    doc_id = shipment.shipment_id

    # Save to Firestore
    saved_firestore = set_document("shipments", doc_id, data)

    return {
        "success": True,
        "message": f"Shipment '{doc_id}' from {shipment.origin} to {shipment.destination} created successfully.",
        "firestore_synced": saved_firestore,
        "shipment": data
    }


# ==============================================================================
# 5. Multi-Agent Orchestrator & Human Approval Endpoints
# ==============================================================================

@app.post("/orchestrator/run", tags=["Multi-Agent Orchestration"])
def run_orchestrator_cycle():
    """Triggers autonomous multi-agent reasoning and rebalancing cycle."""
    result = orchestrator.run_state_assessment()
    return result


@app.get("/approval/discord-callback", response_class=HTMLResponse, tags=["Human Governance"])
def discord_approval_callback(plan_id: str = Query(...), action: str = Query(...)):
    """
    HTTP callback invoked when human supervisor clicks Approve/Reject in Discord or UI.
    """
    action_lower = action.lower()
    if action_lower not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'.")

    if action_lower == "approve":
        exec_result = orchestrator.execute_approved_plan(plan_id)
        if exec_result.get("execution_status") != "COMPLETED":
            return f"""
            <html>
                <body style="font-family: Arial; padding: 40px; background: #fff3f3; color: #333;">
                    <h2>Approval Error</h2>
                    <p>{exec_result.get('message', 'Plan could not be executed.')}</p>
                </body>
            </html>
            """
        return f"""
        <html>
            <head><title>TAN-IX Authorization</title></head>
            <body style="font-family: 'Segoe UI', Arial; padding: 40px; background: #f0fdf4; color: #166534; text-align: center;">
                <div style="background: white; border: 2px solid #22c55e; border-radius: 12px; padding: 30px; max-width: 600px; margin: 0 auto;">
                    <h1 style="color: #15803d; margin-bottom: 8px;">Plan Authorized by Human Supervisor</h1>
                    <h3 style="color: #475569; margin-top: 0;">Plan Reference: {plan_id}</h3>
                    <p style="font-size: 16px; line-height: 1.6; color: #1e293b;">
                        The inter-cluster stock transfer has been authorized and dispatched.<br>
                        <strong>Live stock state updated in Firestore.</strong>
                    </p>
                    <div style="background: #f8fafc; border-radius: 8px; padding: 15px; margin: 20px 0; text-align: left; font-size: 14px;">
                        <strong>Execution Summary:</strong><br>
                        {exec_result.get('summary')}
                    </div>
                </div>
            </body>
        </html>
        """
    else:
        PENDING_APPROVALS[plan_id]["approval_status"] = "REJECTED"
        return f"""
        <html>
            <head><title>TAN-IX Plan Rejected</title></head>
            <body style="font-family: 'Segoe UI', Arial; padding: 40px; background: #fef2f2; color: #991b1b; text-align: center;">
                <div style="background: white; border: 2px solid #ef4444; border-radius: 12px; padding: 30px; max-width: 600px; margin: 0 auto;">
                    <h1>Transfer Plan Rejected</h1>
                    <p>Plan {plan_id} was declined by the human operator. No inventory changes were made.</p>
                </div>
            </body>
        </html>
        """


@app.get("/historical/stats", tags=["Analytics"])
def get_bigquery_stats():
    """Returns BigQuery highway corridor performance analytics."""
    return get_corridor_performance_stats()


@app.post("/policy/search", tags=["Vector Policy RAG"])
def search_policy(query: str = Query(..., description="Query terms for UP leather policies")):
    """Vector search over regulatory and UP industrial policies."""
    return {"results": search_policy_docs(query, top_k=3)}
