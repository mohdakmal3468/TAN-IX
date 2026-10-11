"""
dashboard/app.py
----------------
AgentHide Streamlit dashboard. It talks to the FastAPI backend over HTTP,
so START THE API FIRST:   uvicorn api.main:app --reload
Then run this:            streamlit run dashboard/app.py

Pages: Command Center | Inventory | Approvals | Agent Activity
"""
import os
from datetime import datetime

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

API = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(
    page_title="AgentHide | UP Leather Supply Chain",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# Theme & Custom CSS (Dark & Light Combo Theme with Fixes)
# ----------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
    /* Main App Background (Clean Light Mode Canvas) */
    .stApp {
        background-color: #F8FAFC;
        color: #0F172A;
    }
    
    /* Global Typography */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #0F172A !important;
        font-weight: 700 !important;
    }
    
    /* Top Header Banner */
    .main-header {
        background: linear-gradient(135deg, #FFFFFF 0%, #F1F5F9 100%);
        border: 1px solid #E2E8F0;
        padding: 1.25rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
    }
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem !important;
        color: #D97706 !important;
    }
    .main-header p {
        margin: 4px 0 0 0;
        color: #64748B;
        font-size: 0.9rem;
    }

    /* Custom Metric Cards (Light Surface) */
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
    }
    div[data-testid="stMetric"] label {
        color: #64748B !important;
        font-size: 0.85rem !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #0F172A !important;
        font-weight: 700;
    }

    /* Styled Container Cards & Expanders */
    div[data-testid="stExpander"], div[data-testid="stContainer"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        color: #0F172A !important;
        font-color: #000000 !important;
    }

    /* Fix for Warning / Alert Box Text Contrast */
    div.stAlert {
        background-color: #FEF3C7 !important;
        border: 1px solid #F59E0B !important;
        color: #78350F !important;
        border-radius: 8px !important;
    }
    div.stAlert p, div.stAlert span, div.stAlert strong {
        color: #78350F !important;
    }

    /* Custom Primary & Secondary Buttons */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
    }
    .stButton > button[kind="primary"] {
        background-color: #D97706 !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #B45309 !important;
        box-shadow: 0 4px 12px rgba(217, 119, 6, 0.25);
    }

    /* Sidebar Customization (Dark Theme Contrast) */
    section[data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid #1E293B;
    }
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] span, 
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p {
        color: #F8FAFC !important;
    }

    /* Status Pill Badges */
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-online { background-color: rgba(5, 150, 105, 0.15); color: #059669; border: 1px solid #059669; }
    .badge-offline { background-color: rgba(220, 38, 38, 0.15); color: #DC2626; border: 1px solid #DC2626; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

STATUS_ICON = {"ok": "🟢", "low": "🟠", "critical": "🔴"}
STATUS_RGB = {"ok": [34, 197, 94, 210], "low": [245, 158, 11, 210], "critical": [239, 68, 68, 230]}


# ----------------------------------------------------------------------------
# Small helpers for talking to the API
# ----------------------------------------------------------------------------
def api_get(path, params=None):
    try:
        r = requests.get(f"{API}{path}", params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def api_post(path, params=None, body=None, timeout=180):
    try:
        r = requests.post(f"{API}{path}", params=params, json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API call failed: {e}")
        return None


def decide(plan_id, action):
    """Approve or reject a plan through the existing callback endpoint."""
    try:
        r = requests.get(f"{API}/approval/discord-callback",
                         params={"plan_id": plan_id, "action": action}, timeout=30)
        return r.ok and "Approval Error" not in r.text
    except Exception:
        return False


def flash(kind, msg):
    st.session_state["flash"] = (kind, msg)


def show_flash():
    if "flash" in st.session_state:
        kind, msg = st.session_state.pop("flash")
        getattr(st, kind)(msg)


# ----------------------------------------------------------------------------
# Sidebar (Dark Theme)
# ----------------------------------------------------------------------------
health = api_get("/health")
with st.sidebar:
    st.markdown("## 🛡️ AgentHide")
    st.caption("UP Leather Supply Chain · Corridor Command")
    st.markdown("---")
    
    page = st.radio("Navigation", ["Command Center", "Inventory", "Approvals", "Agent Activity"], label_visibility="collapsed")
    
    st.markdown("---")
    if health:
        st.markdown('<span class="status-badge badge-online">● System Online</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-badge badge-offline">● System Offline</span>', unsafe_allow_html=True)
        st.code("uvicorn api.main:app --reload")
        
    st.write("")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()
    st.caption(f"Last updated: {datetime.now():%H:%M:%S}")

if not health:
    st.warning("Start the API first, then press Refresh.")
    st.stop()


# ----------------------------------------------------------------------------
# Page Header Layout
# ----------------------------------------------------------------------------
def render_header(title, subtitle):
    st.markdown(
        f"""
        <div class="main-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


# ----------------------------------------------------------------------------
# Page 1: Command Center
# ----------------------------------------------------------------------------
def page_command_center():
    render_header("Command Center", "Real-time visibility into freight lanes, risk corridors, and supply chain health.")
    
    k = api_get("/kpis") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Alerts", k.get("active_alerts_count", 0))
    c2.metric("Active Disruptions", k.get("active_disruptions_count", 0))
    c3.metric("Critical Stock Items", k.get("critical_inventory_count", 0))
    c4.metric("Pending Approvals", k.get("pending_approvals_count", 0))

    districts = (api_get("/districts") or {}).get("districts", [])
    inventory = (api_get("/inventory") or {}).get("inventory", [])
    lanes = (api_get("/lanes/risk") or {}).get("lanes", [])

    # Worst stock status per district decides the marker colour
    rank = {"ok": 0, "low": 1, "critical": 2}
    worst = {}
    for item in inventory:
        d, s = item["district"], item["status_color"]
        if rank[s] >= rank[worst.get(d, "ok")]:
            worst[d] = s

    coords = {d["name"]: (d["lon"], d["lat"]) for d in districts}
    points = pd.DataFrame([{
        "name": d["name"], "lon": d["lon"], "lat": d["lat"],
        "stock": worst.get(d["name"], "ok"), "color": STATUS_RGB[worst.get(d["name"], "ok")],
    } for d in districts])

    def lane_rgb(score):
        if score >= 75: return [220, 38, 38]
        if score >= 50: return [249, 115, 22]
        if score >= 25: return [234, 179, 8]
        return [100, 116, 139]

    line_rows = []
    for ln in lanes:
        a, b = coords.get(ln["origin"]), coords.get(ln["destination"])
        if a and b:
            line_rows.append({"sx": a[0], "sy": a[1], "tx": b[0], "ty": b[1],
                              "color": lane_rgb(ln["risk_score"]), "route": ln["route_name"],
                              "risk": ln["risk_score"]})
    lines = pd.DataFrame(line_rows)

    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("Corridor map")
        if not points.empty:
            layers = [pdk.Layer("ScatterplotLayer", data=points, get_position=["lon", "lat"],
                                get_fill_color="color", get_radius=18000, pickable=True)]
            if not lines.empty:
                layers.insert(0, pdk.Layer("LineLayer", data=lines, get_source_position=["sx", "sy"],
                                           get_target_position=["tx", "ty"], get_color="color",
                                           get_width=4, pickable=True))
            # Fixed: Removed restricted map_style URL so the default base map loads properly without tokens
            st.pydeck_chart(pdk.Deck(
                layers=layers,
                initial_view_state=pdk.ViewState(latitude=27.4, longitude=79.2, zoom=6),
                tooltip={"text": "{name}{route}\nStock: {stock}\nRisk: {risk}"}
            ))
        st.caption("Dots = worst stock status in that district. Lines = freight lanes coloured by risk score.")
        
    with right:
        st.subheader("Lane risk scores")
        if lanes:
            df = pd.DataFrame(lanes).sort_values("risk_score", ascending=False).head(8)
            st.bar_chart(df.set_index("route_name")["risk_score"], color="#D97706")
        st.subheader("Active disruptions")
        disruptions = (api_get("/disruptions/active") or {}).get("disruptions", [])
        if not disruptions:
            st.success("No active disruptions")
        for d in disruptions:
            st.warning(f"**{d['title']}** ({d['severity']}) · {d['location']}\n\n"
                       f"Lanes affected: {', '.join(d['affected_lanes']) or 'none'}")

    st.subheader("Dispatch schedule")
    sched = (api_get("/dispatch-schedule") or {}).get("schedule", [])
    if sched:
        cols = ["dispatch_id", "origin", "destination", "product", "quantity",
                "carrier", "route_name", "cost_inr", "eta_hours", "status"]
        st.dataframe(pd.DataFrame(sched)[cols], use_container_width=True, hide_index=True)

    with st.expander("Historical analytics (BigQuery)"):
        stats = api_get("/historical/stats") or {}
        a, b = st.columns(2)
        a.metric("Past shipments analysed", stats.get("total_historical_shipments_analyzed", 0))
        b.metric("Average shipment cost (₹)", f"{stats.get('avg_shipment_cost_inr', 0):,}")
        rows = [{"Corridor": n, "Trips": v.get("total_trips"), "Delayed": v.get("delayed_trips"),
                 "On-time %": v.get("on_time_percentage")}
                for n, v in (stats.get("corridor_breakdown") or {}).items()]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ----------------------------------------------------------------------------
# Page 2: Inventory
# ----------------------------------------------------------------------------
def page_inventory():
    render_header("Inventory Hub", "Monitor stock levels, reorder points, and daily burn rates across processing hubs.")
    
    inventory = (api_get("/inventory") or {}).get("inventory", [])
    if not inventory:
        st.info("No inventory data. Run: python scripts/reset_demo.py")
        return
    df = pd.DataFrame(inventory)
    f1, f2 = st.columns(2)
    district = f1.selectbox("District", ["All"] + sorted(df["district"].unique()))
    product = f2.selectbox("Product", ["All"] + sorted(df["product"].unique()))
    if district != "All":
        df = df[df["district"] == district]
    if product != "All":
        df = df[df["product"] == product]

    m1, m2, m3 = st.columns(3)
    m1.metric("🔴 Critical", int((df["status_color"] == "critical").sum()))
    m2.metric("🟠 Low", int((df["status_color"] == "low").sum()))
    m3.metric("🟢 OK", int((df["status_color"] == "ok").sum()))

    df = df.assign(Status=df["status_color"].map(STATUS_ICON) + " " + df["status"])
    show = df[["Status", "district", "product", "quantity", "reorder_point",
               "daily_burn_rate", "days_left"]].rename(columns={
        "district": "District", "product": "Product", "quantity": "In stock",
        "reorder_point": "Reorder at", "daily_burn_rate": "Used per day", "days_left": "Days left"})
    
    st.dataframe(
        show, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Days left": st.column_config.ProgressColumn(
                "Days left", min_value=0, max_value=20, format="%.1f"
            )
        }
    )
    st.caption("Critical = under half the reorder point or 2 days of stock left. Low = below reorder point.")


# ----------------------------------------------------------------------------
# Page 3: Approvals (human in the loop)
# ----------------------------------------------------------------------------
def page_approvals():
    render_header("Approval Workflow", "Review and authorize autonomous agent inventory transfer recommendations.")
    show_flash()
    
    pending = (api_get("/approvals", {"status": "pending"}) or {}).get("approvals", [])
    if not pending:
        st.success("Nothing waiting for approval.")
    for a in pending:
        pid = a["plan_id"]
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"### **{pid}**")
                st.markdown(f"Move **{a['quantity']:,.0f} {a['product']}** from **{a['origin']}** → **{a['destination']}**")
                st.caption(f"Route: **{a['route_name']}** · Carrier: **{a['carrier']}** · Cost: **₹{a['estimated_cost_inr']:,.0f}**")
            with c2:
                if st.button("✅ Approve", key=f"ok_{pid}", type="primary", use_container_width=True):
                    if decide(pid, "approve"):
                        flash("success", f"{pid} approved. Live stock has been updated.")
                    else:
                        flash("error", f"Could not approve {pid}. Check the API terminal.")
                    st.rerun()
                if st.button("❌ Reject", key=f"no_{pid}", use_container_width=True):
                    decide(pid, "reject")
                    flash("info", f"{pid} rejected. No stock was moved.")
                    st.rerun()
                    
    with st.expander("Approval history"):
        allr = (api_get("/approvals", {"status": "all"}) or {}).get("approvals", [])
        if allr:
            cols = ["plan_id", "origin", "destination", "product", "quantity", "estimated_cost_inr", "status"]
            st.dataframe(pd.DataFrame(allr)[cols], use_container_width=True, hide_index=True)


# ----------------------------------------------------------------------------
# Page 4: Agent Activity + Scenario Simulator
# ----------------------------------------------------------------------------
def render_run(res):
    st.subheader("Result of the run")
    st.caption(f"Run ID: {res.get('run_id')} · Status: {res.get('system_status')}")
    if res.get("orchestrator_synthesis"):
        st.info(res["orchestrator_synthesis"])

    plan = res.get("final_plan")
    if plan:
        a, b, c, d = st.columns(4)
        a.metric("Transfer", f"{plan['quantity']:,.0f} {plan['item']}")
        b.metric("Route", f"{plan['origin']} → {plan['destination']}")
        c.metric("Cost (₹)", f"{plan['estimated_cost_inr']:,.0f}")
        d.metric("Transit (hours)", plan["transit_hours"])
        if str(plan.get("approval_status")).lower() == "approved":
            st.success(f"Auto-approved by guardrails. {plan.get('governance_note', '')}")
        else:
            st.warning(f"Waiting for a human. {plan.get('governance_note', '')} "
                       f"Open the **Approvals** page to approve or reject.")
    else:
        st.success("All districts are within safe stock limits. No transfer needed.")

    st.markdown("#### What the agents did, step by step")
    for e in res.get("reasoning_events", []):
        with st.expander(f"Step {e['step']} · {e['component']} · {e['action']}"):
            st.write(e["details"])

    policies = res.get("attached_policies", [])
    if policies:
        st.markdown("#### Policies the orchestrator applied")
        for p in policies:
            with st.expander(p.get("title", "Policy")):
                st.write(p.get("content") or p.get("text") or "")

    pkg = res.get("draft_documentation_package")
    if pkg:
        st.markdown("#### Draft transit permit (Form UP-EWAY-01)")
        st.code(pkg.get("filled_permit_manifest", ""), language="text")


def page_agent_activity():
    render_header("Agent Activity & Simulation", "Simulate supply disruptions and observe multi-agent orchestration in real time.")
    show_flash()

    st.subheader("1. Create a problem (scenario simulator)")
    c1, c2, c3, c4 = st.columns(4)
    scenarios = [
        (c1, "🚧 Highway blockade (Unnao)", {"scenario_type": "highway_blockade", "cluster": "Unnao"}),
        (c2, "📈 Demand spike (Agra)", {"scenario_type": "demand_spike", "cluster": "Agra"}),
        (c3, "🌊 Ganges flood (Kanpur)", {"scenario_type": "monsoon_flood", "cluster": "Kanpur"}),
        (c4, "✅ Clear all", {"scenario_type": "clear"}),
    ]
    for col, label, body in scenarios:
        if col.button(label, use_container_width=True):
            res = api_post("/scenario/trigger", body={"severity": "CRITICAL", **body})
            if res:
                flash("success", res.get("message", "Scenario applied."))
                st.rerun()
    show_flash()

    st.subheader("2. Let the agents respond")
    if st.button("🚀 Run multi-agent assessment", type="primary", use_container_width=True):
        with st.status("Agents are working...", expanded=True) as status:
            st.write("Inventory Agent → Risk Agent → Logistics Agent → Policies → Guardrails")
            res = api_post("/orchestrator/run", params={"trigger": "Dashboard demo run"})
            status.update(label="Run complete" if res else "Run failed",
                          state="complete" if res else "error")
        if res:
            st.session_state["last_run"] = res

    if st.session_state.get("last_run"):
        render_run(st.session_state["last_run"])

    with st.expander("Earlier runs"):
        runs = (api_get("/runs", {"limit": 10}) or {}).get("runs", [])
        if runs:
            cols = ["timestamp", "trigger", "summary", "approval_status"]
            st.dataframe(pd.DataFrame(runs).reindex(columns=cols), use_container_width=True, hide_index=True)
        else:
            st.caption("No saved runs yet.")


{"Command Center": page_command_center, "Inventory": page_inventory,
 "Approvals": page_approvals, "Agent Activity": page_agent_activity}[page]()