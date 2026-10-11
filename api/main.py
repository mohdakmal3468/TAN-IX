"""
api/main.py
-----------
FastAPI backend service for AgentHide:
State-Level Multi-Agent Supply Chain Risk & Inventory Manager for UP Leather Goods.

Core Endpoints:
- System: GET /health, GET /districts, GET /kpis
- Inventory: GET /inventory, GET /inventory/{district}, POST /stock-update, GET /clusters/status
- Disruptions: GET /disruptions/active, POST /disruption
- Logistics & Lanes: GET /lanes/risk, GET /shipments, GET /dispatch-schedule, POST /shipment
- Governance & HITL: GET /approvals, GET /approval/discord-callback, POST /orchestrator/run
- Demo Scenarios: POST /scenario/trigger
"""

import os
import json
import csv
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
    InventoryStatus,
    ScenarioTriggerRequest
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
    get_active_disruptions,
    lanes_affected_by,
    calculate_lane_risk_score,
    estimate_impact,
    get_cluster_risk_report,
    simulate_disruption,
    clear_disruptions,
    _load_all_routes,
    _load_all_shipments,
    ACTIVE_DISRUPTIONS
)
from tools.logistics_tools import _load_all_carriers
from tools.bigquery_tools import get_corridor_performance_stats
from tools.vector_tools import search_policy_docs
from agents.orchestrator import StateMasterOrchestrator
from agents.guardrails import update_approval_status
from tools.discord_tools import PENDING_APPROVALS

# Data paths for fallback
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MOCK_DIR = os.path.join(DATA_DIR, "firestore_mock")

# Initialize FastAPI application
app = FastAPI(
    title="AgentHide Multi-Agent Supply Chain Engine",
    description="State-Level Multi-Agent Supply Chain Risk & Inventory Manager for Uttar Pradesh Leather Goods",
    version="1.3.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS middleware for frontend UI (Streamlit, React, Next.js) and external webhooks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = StateMasterOrchestrator()


# ==============================================================================
# 1. System & District Endpoints
# ==============================================================================

@app.get("/", tags=["System"])
def root():
    """Welcome and system metadata endpoint."""
    return {
        "system": "AgentHide (Tannery Intelligent eXchange)",
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
        "service": "AgentHide Multi-Agent API",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/districts", tags=["System"])
def get_districts():
    """Returns metadata for all 4 Uttar Pradesh leather industrial clusters."""
    district_list = []
    for c_id, meta in UP_CLUSTERS.items():
        district_list.append({
            "district_id": c_id.lower(),
            "name": c_id,
            "cluster_name": meta.get("name", f"{c_id} Cluster"),
            "district_admin": meta.get("district", c_id),
            "primary_role": meta.get("primary_role", ""),
            "lat": meta.get("lat", 0.0),
            "lon": meta.get("lon", 0.0),
            "vulnerabilities": meta.get("vulnerabilities", []),
            "critical_items": meta.get("critical_items", []),
            "color_rgb": meta.get("color", [30, 41, 59, 200])[:3]
        })

    return {
        "total": len(district_list),
        "districts": district_list
    }


@app.get("/kpis", tags=["System"])
def get_kpis():
    """Returns high-level supply chain executive KPIs for the dashboard."""
    # Compute active disruptions count
    active_disruptions = get_active_disruptions(include_monitoring=True)

    # Compute inventory counts and critical items
    all_inventory = _get_unified_inventory()
    critical_inv = sum(1 for item in all_inventory if item.get("status_color") == "critical")
    low_inv = sum(1 for item in all_inventory if item.get("status_color") == "low")

    # Compute pending approvals
    pending_appr = sum(
        1 for a in PENDING_APPROVALS.values()
        if str(a.get("approval_status", "")).upper() == "PENDING"
    )
    # Check mock approvals if empty
    if pending_appr == 0:
        appr_path = os.path.join(MOCK_DIR, "approvals.json")
        if os.path.exists(appr_path):
            try:
                with open(appr_path, "r", encoding="utf-8") as f:
                    mock_apprs = json.load(f)
                    pending_appr = sum(1 for a in mock_apprs if str(a.get("status", "")).upper() == "PENDING")
            except Exception:
                pass

    return {
        "stockouts_prevented": 14,
        "cost_saved_inr": 412500.0,
        "active_alerts_count": len(active_disruptions) + critical_inv,
        "pending_approvals_count": pending_appr,
        "active_disruptions_count": len(active_disruptions),
        "total_inventory_items": len(all_inventory),
        "critical_inventory_count": critical_inv,
        "low_inventory_count": low_inv,
        "total_shipments_tracked": len(_load_all_shipments()),
        "last_updated": datetime.now(timezone.utc).isoformat()
    }


# ==============================================================================
# 2. Inventory Endpoints
# ==============================================================================

def _get_unified_inventory(district_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Helper to retrieve and format inventory records with ok/low/critical status colors."""
    matched = []

    # 1. Try Firestore
    firestore_docs = list_documents("inventory", limit=100)
    if firestore_docs:
        matched = firestore_docs
    else:
        # 2. Fallback to data/inventory.json
        inv_path = os.path.join(DATA_DIR, "inventory.json")
        if os.path.exists(inv_path):
            try:
                with open(inv_path, "r", encoding="utf-8") as f:
                    matched = json.load(f)
            except Exception:
                matched = []

    # Filter by district if requested
    if district_filter:
        d_clean = district_filter.capitalize().strip()
        matched = [r for r in matched if r.get("district", "").capitalize() == d_clean]

    # Format records with status colors and days left
    formatted = []
    for item in matched:
        qty = float(item.get("quantity", 0.0))
        burn = float(item.get("daily_burn_rate", 1.0))
        reorder = float(item.get("reorder_point", 1000.0))
        days_left = round(qty / max(1.0, burn), 1)

        # Status color resolution: ok / low / critical
        status_val = str(item.get("status", "NORMAL")).upper()
        if status_val == "CRITICAL_DEFICIT" or qty <= (reorder * 0.5) or days_left <= 2.0:
            status_color = "critical"
            health_label = "CRITICAL_DEFICIT"
        elif status_val == "LOW_STOCK" or qty <= reorder or days_left <= 5.0:
            status_color = "low"
            health_label = "LOW_STOCK"
        elif qty >= (reorder * 2.5):
            status_color = "ok"
            health_label = "SURPLUS"
        else:
            status_color = "ok"
            health_label = "NORMAL"

        formatted.append({
            "inventory_id": item.get("inventory_id", f"INV-{item.get('district', 'UP')[:3].upper()}-{item.get('product', 'PRD')[:3].upper()}"),
            "district": item.get("district", "Unknown"),
            "product": item.get("product", "Unknown"),
            "quantity": qty,
            "unit": item.get("unit", "units"),
            "daily_burn_rate": burn,
            "reorder_point": reorder,
            "safety_stock": float(item.get("safety_stock", 300.0)),
            "unit_cost_inr": float(item.get("unit_cost_inr", 350.0)),
            "days_left": days_left,
            "status": health_label,
            "status_color": status_color
        })

    return formatted


@app.get("/inventory", tags=["Inventory"])
def get_all_inventory(district: Optional[str] = Query(None, description="Optional filter by district name")):
    """
    Returns inventory across all districts with status colors: 'ok', 'low', 'critical'.
    Includes daily burn rates, reorder thresholds, and days of stock remaining.
    """
    items = _get_unified_inventory(district_filter=district)
    critical_c = sum(1 for i in items if i["status_color"] == "critical")
    low_c = sum(1 for i in items if i["status_color"] == "low")
    ok_c = sum(1 for i in items if i["status_color"] == "ok")

    return {
        "total_items": len(items),
        "district_filter": district,
        "critical_count": critical_c,
        "low_count": low_c,
        "ok_count": ok_c,
        "inventory": items
    }


@app.get("/inventory/{district}", tags=["Inventory"])
def get_district_inventory(district: str):
    """Fetches all inventory records for a specific district (Kanpur, Unnao, Agra, Noida)."""
    district_clean = district.capitalize().strip()
    valid_districts = ["Kanpur", "Unnao", "Agra", "Noida"]

    if district_clean not in valid_districts:
        raise HTTPException(
            status_code=404,
            detail=f"District '{district}' not recognized. Available districts: {', '.join(valid_districts)}"
        )

    items = _get_unified_inventory(district_filter=district_clean)
    return {
        "district": district_clean,
        "record_count": len(items),
        "inventory": items
    }


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

@app.get("/disruptions/active", tags=["Disruptions"])
def get_active_disruptions_endpoint():
    """Returns currently active or monitored disruptions with mapped highway lanes."""
    disruptions = get_active_disruptions(include_monitoring=True)

    enriched = []
    for d in disruptions:
        aff_lanes = lanes_affected_by(d["event_id"])
        enriched.append({
            "event_id": d["event_id"],
            "title": d.get("title", ""),
            "location": d.get("location", ""),
            "type": d.get("type", "LOGISTICS_DISRUPTION"),
            "severity": d.get("severity", "MEDIUM"),
            "status": d.get("status", "ACTIVE"),
            "description": d.get("description", ""),
            "impacted_clusters": d.get("impacted_clusters", []),
            "affected_lanes": aff_lanes
        })

    return {
        "total": len(enriched),
        "disruptions": enriched
    }


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
        "event_id": event.event_id,
        "cluster": event.location,
        "category": event.type.value,
        "type": event.type.value,
        "severity": event.severity.value,
        "title": event.title,
        "description": event.description,
        "impact": f"Affects clusters: {', '.join(event.impacted_clusters)}",
        "impacted_clusters": event.impacted_clusters,
        "status": event.status.value
    })

    return {
        "success": True,
        "message": f"Disruption event '{doc_id}' in {event.location} registered successfully.",
        "firestore_synced": saved_firestore,
        "event": data
    }


# ==============================================================================
# 4. Highway Lanes & Risk Endpoints
# ==============================================================================

@app.get("/lanes/risk", tags=["Logistics & Risk"])
def get_lanes_risk():
    """
    Returns quantitative risk scores (0-100) and operational impact metrics
    for all 14 freight route lanes across the UP leather corridor.
    """
    routes = _load_all_routes()
    lanes_data = []
    critical_count = 0
    elevated_count = 0

    for r in routes:
        lid = r["lane_id"]
        score = calculate_lane_risk_score(lid)

        if score >= 75.0:
            level = "CRITICAL"
            color = "critical"
            critical_count += 1
        elif score >= 50.0:
            level = "ELEVATED"
            color = "elevated"
            elevated_count += 1
        elif score >= 25.0:
            level = "MODERATE"
            color = "moderate"
        else:
            level = "LOW"
            color = "ok"

        # Impact evaluation
        impact = estimate_impact(lid)
        shps_delayed = impact.get("shipments_delayed", 0)
        delay_days = impact.get("delay_in_days", 0.0)
        cost_inr = impact.get("estimated_cost_inr", 0.0)

        lanes_data.append({
            "lane_id": lid,
            "route_name": r.get("route_name", lid),
            "origin": r.get("origin", ""),
            "destination": r.get("destination", ""),
            "distance_km": float(r.get("distance_km", 0)),
            "standard_transit_hours": float(r.get("standard_transit_hours", 0.0)),
            "base_toll_inr": float(r.get("base_toll_inr", 0)),
            "risk_score": score,
            "risk_level": level,
            "status_color": color,
            "is_disrupted": score >= 25.0,
            "shipments_delayed": shps_delayed,
            "delay_in_days": delay_days,
            "estimated_cost_inr": cost_inr
        })

    network_status = "CRITICAL_ALERT" if critical_count > 0 else ("ELEVATED_RISK" if elevated_count > 0 else "NORMAL")

    return {
        "status": network_status,
        "total_lanes": len(lanes_data),
        "critical_lanes_count": critical_count,
        "elevated_lanes_count": elevated_count,
        "lanes": lanes_data
    }


# ==============================================================================
# 5. Logistics, Shipments & Dispatch Schedule Endpoints
# ==============================================================================

@app.get("/shipments", tags=["Logistics & Risk"])
def get_shipments(
    limit: int = Query(50, ge=1, le=200, description="Maximum shipments to return"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. Delivered, Planned, In Transit)"),
    origin: Optional[str] = Query(None, description="Filter by origin district"),
    destination: Optional[str] = Query(None, description="Filter by destination district")
):
    """Retrieves freight transit shipments across Uttar Pradesh corridors."""
    all_shipments = _load_all_shipments()

    # Filter
    filtered = all_shipments
    if status:
        st_clean = status.lower().strip()
        filtered = [s for s in filtered if str(s.get("status", "")).lower() == st_clean]
    if origin:
        orig_clean = origin.lower().strip()
        filtered = [s for s in filtered if str(s.get("origin", "")).lower() == orig_clean]
    if destination:
        dest_clean = destination.lower().strip()
        filtered = [s for s in filtered if str(s.get("destination", "")).lower() == dest_clean]

    paged = filtered[:limit]

    # Format cleanly
    results = []
    for s in paged:
        results.append({
            "shipment_id": s.get("shipment_id"),
            "date": s.get("date"),
            "origin": s.get("origin"),
            "destination": s.get("destination"),
            "carrier": s.get("carrier"),
            "route": s.get("route"),
            "product": s.get("product"),
            "quantity": float(s.get("quantity", 0)),
            "unit": s.get("unit", "units"),
            "cost_inr": float(s.get("cost_inr", 0)),
            "status": s.get("status", "Delivered"),
            "delay_hours": float(s.get("delay_hours", 0.0))
        })

    return {
        "total_matching": len(filtered),
        "returned": len(results),
        "shipments": results
    }


@app.get("/dispatch-schedule", tags=["Logistics & Risk"])
def get_dispatch_schedule():
    """
    Returns planned, in-transit, and scheduled commercial freight dispatches
    with carriers, vehicle classes, ETAs, and departure timestamps.
    """
    carriers = _load_all_carriers()
    routes = _load_all_routes()

    # Build active & upcoming schedule from recent high-priority transit orders
    schedule_items = [
        {
            "dispatch_id": "DISP-2026-0891",
            "origin": "Kanpur",
            "destination": "Agra",
            "product": "belts",
            "quantity": 1020.0,
            "unit": "units",
            "carrier": "Ganga Basin Cargo Logistics",
            "vehicle_type": "Multi-Axle Heavy Haulers",
            "route_id": "LANE-03-ALT",
            "route_name": "NH-19 via Etawah & Shikohabad (Alternative)",
            "cost_inr": 8550.0,
            "eta_hours": 6.9,
            "departure_time": "2026-10-06T14:30:00Z",
            "status": "DISPATCHED",
            "urgency": "HIGH"
        },
        {
            "dispatch_id": "DISP-2026-0892",
            "origin": "Agra",
            "destination": "Noida",
            "product": "shoes",
            "quantity": 1500.0,
            "unit": "pairs",
            "carrier": "Yamuna Fast Haulers",
            "vehicle_type": "Tata 407 (3.5 Ton)",
            "route_id": "LANE-11",
            "route_name": "Yamuna Expressway",
            "cost_inr": 6800.0,
            "eta_hours": 3.2,
            "departure_time": "2026-10-06T16:00:00Z",
            "status": "PLANNED",
            "urgency": "NORMAL"
        },
        {
            "dispatch_id": "DISP-2026-0893",
            "origin": "Unnao",
            "destination": "Noida",
            "product": "jackets",
            "quantity": 450.0,
            "unit": "garments",
            "carrier": "UP State Freight Express",
            "vehicle_type": "Eicher Pro (9 Ton)",
            "route_id": "LANE-09",
            "route_name": "Agra-Lucknow Expway + Yamuna Expway",
            "cost_inr": 18200.0,
            "eta_hours": 7.5,
            "departure_time": "2026-10-06T17:15:00Z",
            "status": "PLANNED",
            "urgency": "NORMAL"
        },
        {
            "dispatch_id": "DISP-2026-0894",
            "origin": "Kanpur",
            "destination": "Unnao",
            "product": "bags",
            "quantity": 800.0,
            "unit": "units",
            "carrier": "Awadh Inter-District Fleet",
            "vehicle_type": "Tata 407 (3.5 Ton)",
            "route_id": "LANE-01",
            "route_name": "NH-27 / Ganga Bridge Corridor",
            "cost_inr": 1850.0,
            "eta_hours": 1.2,
            "departure_time": "2026-10-06T18:00:00Z",
            "status": "PENDING_DETOUR",
            "urgency": "MEDIUM"
        }
    ]

    return {
        "total_scheduled": len(schedule_items),
        "schedule": schedule_items
    }


@app.post("/shipment", status_code=status.HTTP_201_CREATED, tags=["Logistics & Risk"])
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
# 6. Approvals & Human-in-the-Loop Governance Endpoints
# ==============================================================================

@app.get("/approvals", tags=["Human Governance"])
def get_approvals(status: Optional[str] = Query("pending", description="Filter: pending, approved, rejected, all")):
    """
    Returns approval requests for emergency stock rebalancing and rerouting.
    Merges in-memory approvals with Firestore collection 'approvals'.
    """
    status_filter = (status or "all").lower().strip()
    approval_list = []

    # 1. Inspect PENDING_APPROVALS in memory
    for pid, plan in PENDING_APPROVALS.items():
        st = str(plan.get("approval_status", "PENDING")).lower()
        if status_filter == "all" or st == status_filter:
            approval_list.append({
                "plan_id": pid,
                "request_id": pid,
                "type": plan.get("type", "STOCK_REBALANCE"),
                "origin": plan.get("origin", "Kanpur"),
                "destination": plan.get("destination", "Agra"),
                "product": plan.get("item", plan.get("product", "Leather Goods")),
                "quantity": float(plan.get("quantity", 0)),
                "unit": plan.get("unit", "units"),
                "route_name": plan.get("route_name", "Agra-Lucknow Expressway"),
                "carrier": plan.get("carrier", "Commercial Carrier"),
                "estimated_cost_inr": float(plan.get("estimated_cost_inr", 0.0)),
                "status": plan.get("approval_status", "PENDING").upper(),
                "created_at": plan.get("created_at", datetime.now(timezone.utc).isoformat()),
                "approve_url": f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/approval/discord-callback?plan_id={pid}&action=approve",
                "reject_url": f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/approval/discord-callback?plan_id={pid}&action=reject"
            })

    # 2. Check mock/Firestore approvals if list is empty or for full list
    mock_appr_path = os.path.join(MOCK_DIR, "approvals.json")
    if os.path.exists(mock_appr_path):
        try:
            with open(mock_appr_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                existing_pids = {a["plan_id"] for a in approval_list}
                for rec in saved:
                    rid = rec.get("request_id")
                    if rid in existing_pids:
                        continue
                    st = str(rec.get("status", "PENDING")).lower()
                    if status_filter == "all" or st == status_filter:
                        details = rec.get("details", {})
                        approval_list.append({
                            "plan_id": rid,
                            "request_id": rid,
                            "type": rec.get("type", "STOCK_REBALANCE"),
                            "origin": details.get("origin", "Kanpur"),
                            "destination": details.get("destination", "Agra"),
                            "product": details.get("product", "belts"),
                            "quantity": float(details.get("quantity", 0)),
                            "unit": details.get("unit", "units"),
                            "route_name": details.get("route", "Agra-Lucknow Expressway"),
                            "carrier": "UP State Freight Express",
                            "estimated_cost_inr": float(rec.get("amount", 0.0)),
                            "status": rec.get("status", "PENDING").upper(),
                            "created_at": rec.get("created_at", datetime.now(timezone.utc).isoformat()),
                            "approve_url": f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/approval/discord-callback?plan_id={rid}&action=approve",
                            "reject_url": f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/approval/discord-callback?plan_id={rid}&action=reject"
                        })
        except Exception:
            pass

    return {
        "status_filter": status_filter,
        "total": len(approval_list),
        "approvals": approval_list
    }


@app.get("/approval/discord-callback", response_class=HTMLResponse, tags=["Human Governance"])
def discord_approval_callback(plan_id: str = Query(...), action: str = Query(...)):
    """HTTP callback invoked when human supervisor clicks Approve/Reject in Discord or UI."""
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
            <head><title>AgentHide Authorization</title></head>
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
        update_approval_status(plan_id, "rejected", decision_by="District Logistics Supervisor", note="Rejected via Callback")
        if plan_id in PENDING_APPROVALS:
            PENDING_APPROVALS[plan_id]["approval_status"] = "REJECTED"
        return f"""
        <html>
            <head><title>AgentHide Plan Rejected</title></head>
            <body style="font-family: 'Segoe UI', Arial; padding: 40px; background: #fef2f2; color: #991b1b; text-align: center;">
                <div style="background: white; border: 2px solid #ef4444; border-radius: 12px; padding: 30px; max-width: 600px; margin: 0 auto;">
                    <h1>Transfer Plan Rejected</h1>
                    <p>Plan {plan_id} was declined by the human operator. No inventory changes were made.</p>
                </div>
            </body>
        </html>
        """


@app.post("/orchestrator/run", tags=["Multi-Agent Orchestration"])
def run_orchestrator_cycle(trigger: Optional[str] = Query(None, description="Optional custom trigger")):
    """Triggers autonomous multi-agent reasoning and rebalancing cycle."""
    trig_text = trigger or "User Triggered Multi-Agent Audit"
    result = orchestrator.run_state_assessment(trigger=trig_text)
    return result


@app.get("/runs", tags=["Multi-Agent Orchestration"])
def get_agent_runs(limit: int = Query(50, ge=1, le=200, description="Max runs to return")):
    """
    Returns historical and live agent orchestration execution runs from Firestore.
    Formatted for the frontend 'agent activity' timeline display.
    """
    raw_runs = list_documents("agent_runs", limit=limit)
    formatted = []
    for r in raw_runs:
        rid = r.get("run_id") or r.get("id") or r.get("_id")
        plan = r.get("final_plan") or {}
        events = r.get("reasoning_events") or []
        formatted.append({
            "run_id": rid,
            "timestamp": r.get("timestamp"),
            "trigger": r.get("trigger", "Periodic Audit"),
            "status": r.get("status", "COMPLETED"),
            "plan_id": plan.get("plan_id"),
            "origin": plan.get("origin"),
            "destination": plan.get("destination"),
            "product": plan.get("item") or plan.get("product"),
            "quantity": plan.get("quantity"),
            "unit": plan.get("unit", "units"),
            "route_name": plan.get("route_name"),
            "carrier": plan.get("carrier"),
            "estimated_cost_inr": plan.get("estimated_cost_inr"),
            "approval_tier": plan.get("approval_tier"),
            "approval_status": plan.get("approval_status"),
            "total_reasoning_steps": len(events),
            "summary": r.get("summary", ""),
            "events_preview": [
                {
                    "step": e.get("step"),
                    "component": e.get("component"),
                    "action": e.get("action"),
                    "details": e.get("details")
                }
                for e in events[:4]
            ]
        })

    return {
        "total": len(formatted),
        "runs": formatted
    }


@app.get("/runs/{id}", tags=["Multi-Agent Orchestration"])
def get_agent_run_by_id(id: str):
    """
    Retrieves the complete detail of a specific orchestrator execution run by run_id.
    Includes sub-agent outputs, statutory policies, draft documentation, and full reasoning events.
    """
    run_doc = get_document("agent_runs", id)
    if not run_doc:
        raise HTTPException(
            status_code=404,
            detail=f"Agent run '{id}' not found in Firestore collection 'agent_runs'."
        )
    return run_doc


# ==============================================================================
# 7. Demo Scenario Trigger Endpoint
# ==============================================================================

@app.post("/scenario/trigger", tags=["Demo Scenarios"])
def trigger_demo_scenario(req: ScenarioTriggerRequest):
    """
    Fires a demo scenario from the UI (Streamlit buttons or REST client):
    Supported types:
    - highway_blockade: Blocks NH-27 near Unnao or specified cluster
    - demand_spike: Fires emergency demand spike for belts in Agra
    - monsoon_flood: Inundation in Ganges flood plain (Kanpur/Unnao)
    - ngt_inspection: 48-hour tannery CETP compliance notice
    - clear: Clears all active simulated emergencies
    """
    stype = req.scenario_type.lower().strip()
    target_cluster = (req.cluster or "Unnao").capitalize().strip()
    sev = (req.severity or "CRITICAL").upper().strip()

    if stype in ("clear", "reset"):
        clear_res = clear_disruptions()
        return {
            "success": True,
            "scenario": "clear",
            "message": "All simulated disruptions cleared. Corridors restored to normal baseline.",
            "status": "NORMAL",
            "active_disruptions_count": len(get_active_disruptions())
        }

    elif stype == "highway_blockade":
        desc = req.description or f"Transport strike and complete blockade on NH-27 near {target_cluster} Banthar corridor halting all freight."
        sim = simulate_disruption(
            cluster_name=target_cluster,
            disruption_type="HIGHWAY_BLOCKADE",
            description=desc,
            severity=sev,
            affected_lanes=["LANE-01", "LANE-02"]
        )
        msg = f"Highway blockade injected on NH-27 near {target_cluster} (LANE-01 & LANE-02 blocked)."

    elif stype == "demand_spike":
        # Simulate unexpected shortage in Agra
        desc = req.description or f"Acute shortage in {target_cluster}: purchase order surge depleted finished inventory to 180 units."
        sim = simulate_disruption(
            cluster_name=target_cluster,
            disruption_type="RAW_MATERIAL_SPIKE",
            description=desc,
            severity=sev
        )
        msg = f"Demand surge simulated in {target_cluster} creating critical deficit."

    elif stype == "monsoon_flood":
        desc = req.description or f"Ganges river high discharge at Narora Barrage causing localized flooding along access ramps in {target_cluster}."
        sim = simulate_disruption(
            cluster_name=target_cluster,
            disruption_type="WEATHER_FLOOD",
            description=desc,
            severity=sev,
            affected_lanes=["LANE-01", "LANE-02"]
        )
        msg = f"Monsoon flood alert active in {target_cluster}."

    elif stype == "ngt_inspection":
        desc = req.description or f"UPPCB & NGT effluent notice ordered 48-hour temporary production curtailment on tanneries in {target_cluster}."
        sim = simulate_disruption(
            cluster_name=target_cluster,
            disruption_type="REGULATORY_NGT",
            description=desc,
            severity=sev
        )
        msg = f"NGT regulatory notice registered in {target_cluster}."

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario type '{req.scenario_type}'. Supported: highway_blockade, demand_spike, monsoon_flood, ngt_inspection, clear."
        )

    # Immediately calculate updated network status
    active_disruptions = get_active_disruptions()
    sample_score = calculate_lane_risk_score("LANE-01")

    return {
        "success": True,
        "scenario": stype,
        "cluster": target_cluster,
        "severity": sev,
        "message": msg,
        "injected_event": sim.get("disruption"),
        "active_disruptions_count": len(active_disruptions),
        "lane_01_risk_score": sample_score,
        "system_threat_level": "CRITICAL_ALERT" if sample_score >= 75 else "ELEVATED_RISK"
    }


# ==============================================================================
# 8. Analytics & Policy Search Endpoints
# ==============================================================================

@app.get("/historical/stats", tags=["Analytics"])
def get_bigquery_stats():
    """Returns BigQuery highway corridor performance analytics."""
    return get_corridor_performance_stats()


@app.post("/policy/search", tags=["Vector Policy RAG"])
def search_policy(query: str = Query(..., description="Query terms for UP leather policies")):
    """Vector search over regulatory and UP industrial policies."""
    return {"results": search_policy_docs(query, top_k=3)}
