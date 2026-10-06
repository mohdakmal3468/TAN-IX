"""
api/main.py
-----------
FastAPI backend service for TAN-IX.
Exposes endpoints for:
- Live cluster inventory inspection
- Multi-Agent Orchestrator execution
- Discord Webhook Human-in-the-Loop approval callback
- Real-time risk disruption injection for capstone demos
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

from config import UP_CLUSTERS, FASTAPI_HOST, FASTAPI_PORT
from tools.firestore_tools import get_all_clusters_inventory, get_cluster_inventory, update_cluster_inventory
from tools.risk_tools import get_cluster_risk_report, simulate_disruption, clear_disruptions
from tools.bigquery_tools import get_corridor_performance_stats
from tools.vector_tools import search_policy_docs
from agents.orchestrator import StateMasterOrchestrator
from tools.discord_tools import PENDING_APPROVALS

app = FastAPI(
    title="TAN-IX Multi-Agent Supply Chain Engine",
    description="State-Level Multi-Agent Supply Chain Risk & Inventory Manager for Uttar Pradesh Leather Goods",
    version="1.0.0"
)

# Enable CORS for frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = StateMasterOrchestrator()


class InventoryUpdateRequest(BaseModel):
    cluster: str
    item: str
    delta: int


class DisruptionRequest(BaseModel):
    cluster: str
    disruption_type: str
    description: str


@app.get("/")
def root():
    return {
        "system": "TAN-IX (Tannery Intelligent eXchange)",
        "region": "Uttar Pradesh (Kanpur, Unnao, Agra, Noida)",
        "status": "Online",
        "docs_url": "/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "TAN-IX Agent Backend"}


@app.get("/clusters/status")
def get_clusters_status():
    """Returns the live inventory and metadata for all UP clusters."""
    inventory = get_all_clusters_inventory()
    combined = {}
    for c_name, meta in UP_CLUSTERS.items():
        combined[c_name] = {
            **meta,
            "warehouse_data": inventory.get(c_name, {})
        }
    return combined


@app.get("/clusters/{cluster_name}")
def get_single_cluster(cluster_name: str):
    """Returns details for a specific cluster."""
    inv = get_cluster_inventory(cluster_name)
    risk = get_cluster_risk_report(cluster_name)
    return {"inventory": inv, "risk_report": risk}


@app.post("/orchestrator/run")
def run_orchestrator_cycle():
    """Triggers the autonomous multi-agent reasoning and rebalancing cycle."""
    result = orchestrator.run_state_assessment()
    return result


@app.get("/approval/discord-callback", response_class=HTMLResponse)
def discord_approval_callback(plan_id: str = Query(...), action: str = Query(...)):
    """
    HTTP callback invoked when a human supervisor clicks the 'Approve' or 'Reject'
    link inside Discord or the web dashboard.
    """
    action_lower = action.lower()
    if action_lower not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'.")

    if action_lower == "approve":
        exec_result = orchestrator.execute_approved_plan(plan_id)
        if not exec_result.get("execution_status") == "COMPLETED":
            return f"""
            <html>
                <body style="font-family: Arial; padding: 40px; background: #fff3f3; color: #333;">
                    <h2>⚠️ Approval Error</h2>
                    <p>{exec_result.get('message', 'Plan could not be executed.')}</p>
                </body>
            </html>
            """
        return f"""
        <html>
            <head><title>TAN-IX Authorization</title></head>
            <body style="font-family: 'Segoe UI', Arial; padding: 40px; background: #f0fdf4; color: #166534; text-align: center;">
                <div style="background: white; border: 2px solid #22c55e; border-radius: 12px; padding: 30px; max-width: 600px; margin: 0 auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
                    <h1 style="color: #15803d; margin-bottom: 8px;">✅ Plan Authorized by Human Supervisor</h1>
                    <h3 style="color: #475569; margin-top: 0;">Plan Reference: {plan_id}</h3>
                    <p style="font-size: 16px; line-height: 1.6; color: #1e293b;">
                        The inter-cluster stock transfer has been authorized and dispatched.<br>
                        <strong>Live stock state updated in Firestore.</strong>
                    </p>
                    <div style="background: #f8fafc; border-radius: 8px; padding: 15px; margin: 20px 0; text-align: left; font-size: 14px;">
                        <strong>Execution Summary:</strong><br>
                        {exec_result.get('summary')}
                    </div>
                    <p style="font-size: 13px; color: #64748b;">You can return to the TAN-IX Streamlit Dashboard to view the updated corridor status.</p>
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
                    <h1>❌ Transfer Plan Rejected</h1>
                    <p>Plan {plan_id} was declined by the human operator. No inventory changes were made.</p>
                </div>
            </body>
        </html>
        """


@app.post("/disruption/simulate")
def inject_disruption(req: DisruptionRequest):
    """Demo endpoint: Injects a disaster/regulatory emergency."""
    res = simulate_disruption(req.cluster, req.disruption_type, req.description)
    return res


@app.post("/disruption/clear")
def reset_disruptions():
    """Resets all disruptions."""
    return clear_disruptions()


@app.get("/historical/stats")
def get_bigquery_stats():
    """Returns BigQuery highway corridor performance analytics."""
    return get_corridor_performance_stats()


@app.post("/policy/search")
def search_policy(query: str = Query(..., description="Query terms for UP leather policies")):
    """Vector search over regulatory and UP industrial policies."""
    return {"results": search_policy_docs(query, top_k=3)}
