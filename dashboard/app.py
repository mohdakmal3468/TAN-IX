"""
dashboard/app.py
----------------
Streamlit Interactive Dashboard for TAN-IX:
State-Level Multi-Agent Supply Chain Risk & Inventory Manager for UP Leather Goods

Features:
- Live geospatial visualization of the UP Leather Corridor (Kanpur, Unnao, Agra, Noida)
- Real-time warehouse inventory health meters with threshold warnings
- Capstone Disruption Simulator (NGT environmental raids, Ganges monsoon floods, Fog delays)
- Multi-Agent deliberation console (Inventory, Risk, Logistics, Orchestrator)
- Human-in-the-Loop (HITL) approval cockpit with Discord webhook integration
"""

import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import json
import os
import sys

# Ensure parent directory is in path so we can import local modules directly if needed
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import UP_CLUSTERS, FASTAPI_HOST, FASTAPI_PORT, DISCORD_WEBHOOK_URL
from tools.firestore_tools import get_all_clusters_inventory, update_cluster_inventory, check_critical_stockouts
from tools.risk_tools import get_cluster_risk_report, simulate_disruption, clear_disruptions, ACTIVE_DISRUPTIONS
from tools.bigquery_tools import get_corridor_performance_stats
from tools.vector_tools import search_policy_docs
from agents.orchestrator import StateMasterOrchestrator

# Initialize Streamlit Page Config
st.set_page_config(
    page_title="TAN-IX | UP Leather Multi-Agent Supply Chain",
    page_icon="👞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for rich aesthetics and modern typography
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #b91c1c, #d97706, #2563eb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .status-badge-critical {
        background-color: #fee2e2;
        color: #b91c1c;
        padding: 4px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .status-badge-healthy {
        background-color: #dcfce7;
        color: #15803d;
        padding: 4px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = StateMasterOrchestrator()
if "last_assessment" not in st.session_state:
    st.session_state.last_assessment = None
if "pending_plan" not in st.session_state:
    st.session_state.pending_plan = None
if "execution_message" not in st.session_state:
    st.session_state.execution_message = None


# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/leather.png", width=64)
    st.title("TAN-IX Control Center")
    st.markdown("**Uttar Pradesh Leather Corridors**")
    st.caption("Kanpur • Unnao • Agra • Noida")

    st.divider()

    st.subheader("⚠️ Emergency Simulator")
    st.caption("Test multi-agent reactions during your Capstone presentation:")

    if st.button("🌊 Ganges Basin Flood Warning (Kanpur)"):
        simulate_disruption("Kanpur", "Weather/Flood", "Water levels at Kanpur Barrage crossed alert mark. Jajmau lowlands at risk.")
        st.toast("Injected Ganges Flood Warning into Kanpur!", icon="🌊")
        st.rerun()

    if st.button("📜 NGT Effluent Inspection Shutdown"):
        simulate_disruption("Kanpur", "Regulatory/NGT", "UPPCB ordered temporary 48h halt for 12 Jajmau tanning units.")
        st.toast("Injected NGT Regulatory Notice!", icon="📜")
        st.rerun()

    if st.button("🌫️ Yamuna Expressway Fog Alert"):
        simulate_disruption("Agra", "Logistics/Fog", "Dense fog reducing visibility < 50m. Night commercial vehicle curfew imposed.")
        st.toast("Injected Yamuna Expressway Fog Warning!", icon="🌫️")
        st.rerun()

    if st.button("🔄 Reset Disruptions"):
        clear_disruptions()
        st.toast("All disruptions cleared to baseline.", icon="✅")
        st.rerun()

    st.divider()

    st.subheader("📡 Infrastructure Status")
    st.markdown(f"**Discord Webhook:** {'🟢 Active' if DISCORD_WEBHOOK_URL else '🟡 Local Simulated Queue'}")
    st.markdown(f"**Data Store:** 🟢 Firestore Local Seed Engine")
    st.markdown(f"**Analytics:** 🟢 BigQuery Corridor Logs")


# --- TOP HEADER ---
st.markdown('<div class="main-header">TAN-IX: State-Level Multi-Agent Supply Chain & Risk Manager</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Autonomous Inventory Balancing & Environmental Resilience for Uttar Pradesh Leather Industrial Clusters</div>', unsafe_allow_html=True)

if st.session_state.execution_message:
    st.success(st.session_state.execution_message)
    st.session_state.execution_message = None

# --- TOP SUMMARY METRICS ---
all_inventory = get_all_clusters_inventory()
critical_shortages = check_critical_stockouts()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🏭 Kanpur (Tanneries)",
        value="Operational",
        delta=f"{len(ACTIVE_DISRUPTIONS)} Active Alerts" if any(d['cluster'] == 'Kanpur' for d in ACTIVE_DISRUPTIONS) else "Normal",
        delta_color="inverse" if any(d['cluster'] == 'Kanpur' for d in ACTIVE_DISRUPTIONS) else "normal"
    )

with col2:
    st.metric(
        label="🐂 Unnao (Leather Complex)",
        value="Surplus Available",
        delta="Wet-Blue Buffer Ready",
        delta_color="normal"
    )

with col3:
    agra_deficit = next((c for c in critical_shortages if c["cluster"] == "Agra"), None)
    st.metric(
        label="👞 Agra (Footwear Hub)",
        value="Deficit Warning" if agra_deficit else "Operational",
        delta=f"Short {agra_deficit['deficit']} {agra_deficit['unit']}" if agra_deficit else "Balanced",
        delta_color="inverse" if agra_deficit else "normal"
    )

with col4:
    noida_deficit = next((c for c in critical_shortages if c["cluster"] == "Noida"), None)
    st.metric(
        label="👜 Noida (Luxury Export)",
        value="Critical Low" if noida_deficit else "Operational",
        delta=f"Short {noida_deficit['deficit']} {noida_deficit['unit']}" if noida_deficit else "Balanced",
        delta_color="inverse" if noida_deficit else "normal"
    )

st.divider()

# --- MAIN WORKSPACE: MAP & LIVE STOCK STATUS ---
tab_map, tab_agents, tab_analytics, tab_policy = st.tabs([
    "🗺️ Corridor Geospatial Map & Live Stock",
    "🤖 Multi-Agent Orchestrator & Deliberation",
    "📊 BigQuery Historical Logistics Analytics",
    "📚 Vector Search & UP Leather Policy"
])

# --- TAB 1: GEOSPATIAL MAP & WAREHOUSE INVENTORY ---
with tab_map:
    left_col, right_col = st.columns([1.2, 1])

    with left_col:
        st.subheader("📍 Uttar Pradesh Leather Industrial Corridor")
        
        # Prepare Map Data
        map_points = []
        for cname, cdata in UP_CLUSTERS.items():
            risk_info = get_cluster_risk_report(cname)
            map_points.append({
                "name": cname,
                "lat": cdata["lat"],
                "lon": cdata["lon"],
                "role": cdata["primary_role"],
                "risk_score": risk_info["composite_risk_score"],
                "color": cdata["color"],
                "radius": 15000 + (risk_info["composite_risk_score"] * 150)
            })
        
        map_df = pd.DataFrame(map_points)

        # Pydeck Scatterplot and Arcs connecting clusters along the expressways
        arc_data = [
            {"from_name": "Kanpur", "to_name": "Unnao", "from_lon": 80.3319, "from_lat": 26.4499, "to_lon": 80.4878, "to_lat": 26.5458},
            {"from_name": "Kanpur", "to_name": "Agra", "from_lon": 80.3319, "from_lat": 26.4499, "to_lon": 78.0081, "to_lat": 27.1767},
            {"from_name": "Agra", "to_name": "Noida", "from_lon": 78.0081, "from_lat": 27.1767, "to_lon": 77.3910, "to_lat": 28.5355}
        ]
        arc_df = pd.DataFrame(arc_data)

        view_state = pdk.ViewState(
            latitude=27.2,
            longitude=79.2,
            zoom=6.8,
            pitch=35
        )

        layer_points = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position=["lon", "lat"],
            get_color="color",
            get_radius="radius",
            pickable=True,
            auto_highlight=True
        )

        layer_arcs = pdk.Layer(
            "ArcLayer",
            data=arc_df,
            get_source_position=["from_lon", "from_lat"],
            get_target_position=["to_lon", "to_lat"],
            get_source_color=[220, 53, 69, 160],
            get_target_color=[33, 150, 243, 160],
            get_width=4
        )

        deck = pdk.Deck(
            layers=[layer_points, layer_arcs],
            initial_view_state=view_state,
            tooltip={"text": "{name}\nRole: {role}\nRisk Score: {risk_score}/100"}
        )

        st.pydeck_chart(deck)
        st.caption("🔴 Red: Tanning Hubs (Kanpur) | 🟠 Orange: Banthar (Unnao) | 🟢 Green: Footwear (Agra) | 🔵 Blue: Export (Noida)")

    with right_col:
        st.subheader("📦 Cluster Live Stock Levels (Firestore)")
        
        selected_cluster = st.selectbox("Select Cluster to Inspect Details:", list(UP_CLUSTERS.keys()), index=2)
        cluster_info = all_inventory.get(selected_cluster, {})
        items = cluster_info.get("inventory", {})

        st.markdown(f"**Warehouse ID:** `{cluster_info.get('warehouse_id', 'WH-00')}` | **Status:** `{cluster_info.get('status', 'Operational')}`")

        for item_name, idata in items.items():
            qty = idata.get("quantity", 0)
            min_th = idata.get("min_threshold", 1)
            cap = idata.get("capacity", qty * 2)
            unit = idata.get("unit", "units")
            status = idata.get("status", "Normal")

            pct = min(1.0, qty / cap) if cap else 0.5

            st.write(f"**{item_name}** ({qty:,} / {cap:,} {unit})")
            
            # Color-coded bar
            if "Critical" in status:
                st.progress(pct, text=f"🚨 CRITICAL SHORTAGE - Deficit: {min_th - qty:,} {unit}")
            elif "Low" in status:
                st.progress(pct, text=f"⚠️ Low Stock - Safety Margin at risk")
            elif "Surplus" in status:
                st.progress(pct, text=f"🟢 Healthy Surplus Available for Inter-District Dispatch")
            else:
                st.progress(pct, text=f"✅ Nominal Buffer")


# --- TAB 2: MULTI-AGENT ORCHESTRATOR & DELIBERATION ---
with tab_agents:
    st.subheader("🤖 Autonomous Multi-Agent Deliberation Console")
    st.write("Click below to trigger the collaborative agent reasoning cycle across Kanpur, Unnao, Agra, and Noida:")

    if st.button("🚀 Trigger Full State Multi-Agent Assessment", type="primary", use_container_width=True):
        with st.spinner("Specialist Agents collaborating... (Inventory -> Risk -> Logistics -> Master Orchestrator)"):
            assessment = st.session_state.orchestrator.run_state_assessment()
            st.session_state.last_assessment = assessment
            if assessment.get("proposed_rebalance_plans"):
                st.session_state.pending_plan = assessment["proposed_rebalance_plans"][0]
        st.rerun()

    if st.session_state.last_assessment:
        ass = st.session_state.last_assessment

        st.markdown("### 📋 Orchestrator Executive Synthesis")
        st.info(ass.get("orchestrator_synthesis", "Assessment completed."))

        # 3 Specialist Agent Outputs in columns
        ag1, ag2, ag3 = st.columns(3)

        with ag1:
            st.markdown("#### 1️⃣ District Inventory Agent")
            inv_rep = ass.get("inventory_report", {})
            st.markdown(f"**Status:** `{inv_rep.get('status')}`")
            st.markdown(f"**Deficits Flagged:** `{inv_rep.get('critical_deficits_count')}`")
            st.caption(inv_rep.get("ai_executive_brief", ""))
            if inv_rep.get("critical_deficits"):
                st.error(f"Urgent Replenishment Needed in: {inv_rep['critical_deficits'][0]['cluster']}")

        with ag2:
            st.markdown("#### 2️⃣ Regional Risk Agent")
            risk_rep = ass.get("risk_report", {})
            st.markdown(f"**Threat Level:** `{risk_rep.get('system_threat_level')}`")
            st.caption(risk_rep.get("ai_risk_brief", ""))
            if risk_rep.get("high_risk_clusters"):
                st.warning(f"Vulnerable Zone: {risk_rep['high_risk_clusters'][0]['cluster']} (Risk: {risk_rep['high_risk_clusters'][0]['score']}/100)")

        with ag3:
            st.markdown("#### 3️⃣ Intra-State Logistics Agent")
            if ass.get("proposed_rebalance_plans"):
                log_rep = ass["proposed_rebalance_plans"][0].get("logistics_details", {})
                st.markdown(f"**Route:** `{log_rep.get('route', {}).get('route_name')}`")
                st.markdown(f"**Transit:** `{log_rep.get('route', {}).get('estimated_transit_hours')} hrs` | **Cost:** `₹{log_rep.get('route', {}).get('total_estimated_cost_inr'):,}`")
                st.caption(log_rep.get("ai_logistics_brief", ""))
            else:
                st.write("No active inter-cluster transit required.")

        st.divider()

        # Human-in-the-Loop Cockpit
        if st.session_state.pending_plan and st.session_state.pending_plan.get("approval_status") == "PENDING":
            plan = st.session_state.pending_plan
            st.markdown("### 🛑 Human-in-the-Loop Approval Action Card")
            st.warning("The Autonomous System has formulated an action plan that requires human authorization before warehouse inventory is committed.")

            card_c1, card_c2 = st.columns([2, 1])
            with card_c1:
                st.markdown(f"**Plan ID:** `{plan['plan_id']}`")
                st.markdown(f"**Proposed Movement:** Transfer **{plan['quantity']:,} units** of `{plan['item']}` from **{plan['origin']}** to **{plan['destination']}**")
                st.markdown(f"**Expressway Route:** {plan['route_name']} (Est. {plan['transit_hours']} hours transit)")
                st.markdown(f"**Estimated Logistics Cost:** ₹{plan['estimated_cost_inr']:,} ({plan['policy_incentive']})")
                st.markdown(f"**Risk Justification:** {plan['risk_justification']}")

            with card_c2:
                st.markdown("**Authorize Dispatch:**")
                if st.button("✅ AUTHORIZE STOCK REBALANCE", type="primary", use_container_width=True):
                    exec_res = st.session_state.orchestrator.execute_approved_plan(plan["plan_id"])
                    st.session_state.execution_message = f"✅ Plan {plan['plan_id']} authorized & executed! Stock moved from {plan['origin']} to {plan['destination']}."
                    st.session_state.pending_plan = None
                    st.rerun()

                if st.button("❌ REJECT PLAN", use_container_width=True):
                    st.session_state.pending_plan = None
                    st.session_state.execution_message = "❌ Rebalance Plan rejected by human supervisor."
                    st.rerun()

    else:
        st.info("Click 'Trigger Full State Multi-Agent Assessment' above to initiate the pipeline.")


# --- TAB 3: BIGQUERY HISTORICAL ANALYTICS ---
with tab_analytics:
    st.subheader("📊 BigQuery Historical Logistics Corridor Performance")
    bq_stats = get_corridor_performance_stats()

    m1, m2 = st.columns(2)
    m1.metric("Historical Shipments Analyzed", bq_stats.get("total_historical_shipments_analyzed", 0))
    m2.metric("Average Freight Shipment Cost", f"₹{bq_stats.get('avg_shipment_cost_inr', 0):,}")

    st.markdown("#### Expressway Reliability Breakdown")
    corridor_data = []
    for corridor_name, cinfo in bq_stats.get("corridor_breakdown", {}).items():
        corridor_data.append({
            "Corridor": corridor_name,
            "Route": cinfo.get("route_name"),
            "Trips": cinfo.get("total_trips"),
            "Delayed Trips": cinfo.get("delayed_trips"),
            "On-Time %": f"{cinfo.get('on_time_percentage')}%",
            "Delay Factors": ", ".join(cinfo.get("delay_factors", [])) or "None"
        })
    st.dataframe(pd.DataFrame(corridor_data), use_container_width=True)


# --- TAB 4: VECTOR SEARCH & UP LEATHER POLICIES ---
with tab_policy:
    st.subheader("📚 Semantic Knowledge Base: UP Leather & Environmental Policies")
    st.write("Query the vector knowledge store to inspect statutory policies, NGT guidelines, and freight subsidies:")

    query = st.text_input("Enter search query (e.g., 'NGT effluent shutdown Kanpur' or 'ODOP freight subsidy')", "ODOP leather goods freight subsidy")
    if query:
        matches = search_policy_docs(query, top_k=3)
        for m in matches:
            with st.expander(f"📄 {m.get('title')} (Relevance: {m.get('relevance_score')})"):
                st.markdown(f"**Cluster:** `{m.get('cluster')}` | **Category:** `{m.get('category')}`")
                st.write(m.get("content"))
