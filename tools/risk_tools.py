"""
tools/risk_tools.py
-------------------
Monitors regional risks, environmental mandates, highway disruptions, and corridor hazards
affecting the Uttar Pradesh Leather Industrial Corridor (Kanpur, Unnao, Agra, Noida).

Functions:
1. get_active_disruptions(include_monitoring) -> List[Dict[str, Any]]
2. lanes_affected_by(disruption_id) -> List[str]
3. calculate_lane_risk_score(lane_id, severity, duration_days, num_shipments) -> float (0-100)
4. estimate_impact(lane_id) -> Dict[str, Any] (shipments_delayed, delay_in_days)
5. get_cluster_risk_report(cluster_name) -> Dict[str, Any] (cluster-level composite score)
6. simulate_disruption(...) & clear_disruptions() (dynamic scenario injector)
"""

import os
import json
import csv
from typing import Dict, Any, List, Optional
from tools.firestore_client import list_documents

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DISRUPTIONS_PATH = os.path.join(DATA_DIR, "disruptions.json")
ROUTES_PATH = os.path.join(DATA_DIR, "routes.json")
SHIPMENTS_PATH = os.path.join(DATA_DIR, "historical_shipments.csv")
MOCK_SHIPMENTS_PATH = os.path.join(DATA_DIR, "firestore_mock", "shipments.json")

# In-memory simulated disruption state for scenario injection and live demos
ACTIVE_DISRUPTIONS: List[Dict[str, Any]] = [
    {
        "id": "DISRUPT-001",
        "event_id": "DISRUPT-001",
        "cluster": "Kanpur",
        "category": "Regulatory",
        "type": "REGULATORY_NGT",
        "severity": "HIGH",
        "title": "UPPCB & NGT Compliance Notice on Jajmau CETP",
        "description": "Due to effluent discharge limit violations, UPPCB has placed 12 tanneries on a 48-hour temporary reduction warning.",
        "impact": "Tanned leather output from Kanpur may drop by 40% over the next 3 days.",
        "impacted_clusters": ["Kanpur", "Agra"],
        "status": "ACTIVE"
    }
]


# ==============================================================================
# DATA LOADERS & CACHING HELPERS
# ==============================================================================

def _load_all_disruptions() -> List[Dict[str, Any]]:
    """Loads all disruptions from Firestore or local data files, merging in-memory events."""
    events: List[Dict[str, Any]] = []

    # 1. Try Firestore
    docs = list_documents("disruptions", limit=100)
    if docs:
        events.extend(docs)
    elif os.path.exists(DISRUPTIONS_PATH):
        try:
            with open(DISRUPTIONS_PATH, "r", encoding="utf-8") as f:
                events.extend(json.load(f))
        except Exception:
            pass

    # 2. Merge in-memory ACTIVE_DISRUPTIONS (avoid duplicate IDs)
    existing_ids = {d.get("event_id") or d.get("id") for d in events if d.get("event_id") or d.get("id")}
    for sim in ACTIVE_DISRUPTIONS:
        sim_id = sim.get("event_id") or sim.get("id")
        if sim_id and sim_id not in existing_ids:
            events.append(sim)
            existing_ids.add(sim_id)

    return events


def _load_all_routes() -> List[Dict[str, Any]]:
    """Loads all route lanes from Firestore or local routes.json."""
    docs = list_documents("routes", limit=50)
    if docs:
        return docs
    if os.path.exists(ROUTES_PATH):
        try:
            with open(ROUTES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _load_all_shipments() -> List[Dict[str, Any]]:
    """Loads shipment records from CSV or mock JSON to estimate lane shipment exposure."""
    shipments: List[Dict[str, Any]] = []
    if os.path.exists(SHIPMENTS_PATH):
        try:
            with open(SHIPMENTS_PATH, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    shipments.append(dict(row))
            return shipments
        except Exception:
            pass

    if os.path.exists(MOCK_SHIPMENTS_PATH):
        try:
            with open(MOCK_SHIPMENTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


# ==============================================================================
# 1. GET ACTIVE DISRUPTIONS
# ==============================================================================

def get_active_disruptions(include_monitoring: bool = True) -> List[Dict[str, Any]]:
    """Retrieves all currently active or monitored supply chain disruptions across UP clusters.

    Queries Firestore collection 'disruptions' with local fallback to data/disruptions.json
    and includes any dynamic disruptions simulated in memory.

    Args:
        include_monitoring: If True, includes events in 'MONITORING' status along with 'ACTIVE'.
            Defaults to True.

    Returns:
        List[Dict[str, Any]]: List of active disruption dictionaries with normalized fields:
            event_id, location, type, severity, title, description, impacted_clusters, status.
    """
    raw_events = _load_all_disruptions()
    allowed_statuses = {"ACTIVE", "MONITORING"} if include_monitoring else {"ACTIVE"}

    active_list: List[Dict[str, Any]] = []
    seen_ids = set()

    for evt in raw_events:
        status = str(evt.get("status", "ACTIVE")).upper()
        if status in allowed_statuses:
            e_id = evt.get("event_id") or evt.get("id") or f"EVT-{len(seen_ids)+1:03d}"
            if e_id in seen_ids:
                continue
            seen_ids.add(e_id)

            normalized = {
                "event_id": e_id,
                "disruption_id": e_id,
                "location": evt.get("location", evt.get("cluster", "Uttar Pradesh")),
                "type": evt.get("type", evt.get("category", "LOGISTICS_DISRUPTION")),
                "severity": str(evt.get("severity", "MEDIUM")).upper(),
                "title": evt.get("title", f"Disruption in {evt.get('location', 'Corridor')}"),
                "description": evt.get("description", evt.get("impact", "")),
                "impacted_clusters": evt.get("impacted_clusters", [evt.get("cluster", "Kanpur")]),
                "status": status
            }
            active_list.append(normalized)

    return active_list


# ==============================================================================
# 2. LANES AFFECTED BY DISRUPTION
# ==============================================================================

def lanes_affected_by(disruption_id: str) -> List[str]:
    """Identifies which highway transit lanes are disrupted or impacted by an incident.

    Matches disruption location landmarks, affected district clusters, and highway
    names against known Uttar Pradesh freight corridors.

    Args:
        disruption_id: Unique identifier of the incident (e.g. 'EVT-AGR-01', 'EVT-KNP-01', 'DISRUPT-001').

    Returns:
        List[str]: List of affected lane identifiers (e.g. ['LANE-11', 'LANE-12']).
    """
    d_clean = str(disruption_id).strip().upper()
    all_events = _load_all_disruptions()

    # Find the target disruption
    target = None
    for evt in all_events:
        eid = str(evt.get("event_id") or evt.get("id") or "").strip().upper()
        if eid == d_clean:
            target = evt
            break

    if not target:
        return []

    # If explicit affected_lanes are specified in data, return them
    if target.get("affected_lanes") and isinstance(target.get("affected_lanes"), list):
        return [str(x).upper() for x in target.get("affected_lanes")]
    if target.get("lanes") and isinstance(target.get("lanes"), list):
        return [str(x).upper() for x in target.get("lanes")]

    routes = _load_all_routes()
    affected_lanes: List[str] = []

    text_corpus = (
        f"{target.get('location', '')} {target.get('title', '')} "
        f"{target.get('description', '')} {target.get('impact', '')}"
    ).lower()

    impacted_clusters = [c.capitalize().strip() for c in target.get("impacted_clusters", [])]
    if not impacted_clusters and target.get("cluster"):
        impacted_clusters = [target.get("cluster").capitalize().strip()]

    # 1. Landmark & Highway specific text cues
    is_yamuna_expway = "yamuna expressway" in text_corpus or "yamuna exp" in text_corpus or "jewar" in text_corpus
    is_ganga_bridge = "ganga bridge" in text_corpus or "nh-27" in text_corpus or "shuklaganj" in text_corpus or "banthar" in text_corpus
    is_agra_lucknow = "agra-lucknow" in text_corpus or "lucknow expressway" in text_corpus or "nh-19" in text_corpus or "etawah" in text_corpus

    if is_yamuna_expway:
        # Yamuna expressway directly connects Agra and Noida
        for r in routes:
            r_name = r.get("route_name", "").lower()
            if "yamuna expressway" in r_name and "agra-lucknow" not in r_name:
                affected_lanes.append(r["lane_id"])

    if is_ganga_bridge:
        # NH-27 Ganga bridge connects Kanpur and Unnao
        for r in routes:
            r_name = r.get("route_name", "").lower()
            if "nh-27" in r_name or "ganga bridge" in r_name:
                affected_lanes.append(r["lane_id"])

    if is_agra_lucknow and not affected_lanes:
        # Agra-Lucknow expressway connects Kanpur/Unnao and Agra
        for r in routes:
            r_name = r.get("route_name", "").lower()
            if "agra-lucknow" in r_name and "yamuna" not in r_name:
                affected_lanes.append(r["lane_id"])

    # 2. Origin-Destination cluster connectivity matching
    if not affected_lanes and len(impacted_clusters) >= 2:
        for r in routes:
            orig = r.get("origin", "").capitalize().strip()
            dest = r.get("destination", "").capitalize().strip()
            if orig in impacted_clusters and dest in impacted_clusters:
                affected_lanes.append(r["lane_id"])

    # 3. Single cluster outward flow matching (if still empty)
    if not affected_lanes and len(impacted_clusters) == 1:
        single_cluster = impacted_clusters[0]
        for r in routes:
            orig = r.get("origin", "").capitalize().strip()
            if orig == single_cluster:
                affected_lanes.append(r["lane_id"])

    # Deduplicate while preserving order
    unique_lanes = []
    for lane in affected_lanes:
        if lane not in unique_lanes:
            unique_lanes.append(lane)

    return unique_lanes


# ==============================================================================
# 3. CALCULATE LANE RISK SCORE (0 - 100)
# ==============================================================================

def calculate_lane_risk_score(
    lane_id: str,
    severity: Optional[str] = None,
    duration_days: Optional[float] = None,
    num_shipments: Optional[int] = None
) -> float:
    """Calculates a normalized risk score from 0.0 to 100.0 for a freight transit lane.

    Formula (Documented in docs/risk_scoring.md):
        Total Risk Score = min(100.0, Severity_Points + Duration_Points + Shipment_Points)

    Breakdown:
    1. Severity Points (0 - 40 pts):
       - CRITICAL: 40 pts
       - HIGH:     30 pts
       - MEDIUM:   20 pts
       - LOW:      10 pts
       - NONE:      0 pts (no active disruption)
    2. Duration Points (0 - 30 pts):
       - min(30.0, Duration_Days * 10.0)
    3. Shipment Exposure Points (0 - 30 pts):
       - min(30.0, Exposed_Shipments * 2.0)

    Args:
        lane_id: Unique route lane code (e.g. 'LANE-01', 'LANE-03', 'LANE-11').
        severity: Optional override for severity ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL').
        duration_days: Optional override for disruption duration in days.
        num_shipments: Optional override for number of shipments at risk.

    Returns:
        float: Composite risk score between 0.0 (no risk) and 100.0 (maximum danger).
    """
    lane_clean = str(lane_id).strip().upper()

    # Determine Severity
    active_disruptions = get_active_disruptions(include_monitoring=True)
    matching_disruptions = []

    if severity is None:
        for d in active_disruptions:
            aff_lanes = lanes_affected_by(d["event_id"])
            if lane_clean in aff_lanes:
                matching_disruptions.append(d)

        if not matching_disruptions:
            # Lane has no active disruptions affecting it
            return 0.0

        # Sort to find highest severity disruption, prioritizing ACTIVE over MONITORING
        status_rank = {"ACTIVE": 2, "MONITORING": 1}
        severity_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        matching_disruptions.sort(
            key=lambda x: (
                status_rank.get(x.get("status", "ACTIVE").upper(), 1),
                severity_rank.get(x.get("severity", "MEDIUM").upper(), 1)
            ),
            reverse=True
        )
        primary_disruption = matching_disruptions[0]
        eff_severity = primary_disruption.get("severity", "MEDIUM").upper()
        is_monitoring = primary_disruption.get("status", "ACTIVE").upper() == "MONITORING"
    else:
        eff_severity = str(severity).strip().upper()
        primary_disruption = matching_disruptions[0] if matching_disruptions else None
        is_monitoring = False

    # 1. Severity Points (0 - 40)
    severity_map = {
        "CRITICAL": 40.0,
        "HIGH": 30.0,
        "MEDIUM": 20.0,
        "LOW": 10.0,
        "NONE": 0.0
    }
    sev_points = severity_map.get(eff_severity, 15.0)
    if sev_points == 0.0:
        return 0.0

    # 2. Duration Points (0 - 30)
    if duration_days is not None:
        eff_duration = max(0.0, float(duration_days))
    else:
        # Parse from description or assign sensible default
        desc = primary_disruption.get("description", "").lower() if primary_disruption else ""
        if "72-hour" in desc or "72 hour" in desc:
            eff_duration = 3.0
        elif "48-hour" in desc or "48 hour" in desc:
            eff_duration = 2.0
        elif "24-hour" in desc or "24 hour" in desc or "1 day" in desc:
            eff_duration = 1.0
        elif eff_severity == "CRITICAL":
            eff_duration = 3.0
        elif eff_severity == "HIGH":
            eff_duration = 2.0
        elif eff_severity == "MEDIUM":
            eff_duration = 1.0
        else:
            eff_duration = 0.5

    dur_points = min(30.0, eff_duration * 10.0)

    # 3. Shipment Exposure Points (0 - 30)
    if num_shipments is not None:
        eff_shipments = max(0, int(num_shipments))
    else:
        # Count shipments associated with this lane
        routes = _load_all_routes()
        target_route = next((r for r in routes if r.get("lane_id", "").upper() == lane_clean), None)

        shipments = _load_all_shipments()
        if target_route and shipments:
            orig = target_route.get("origin", "").lower()
            dest = target_route.get("destination", "").lower()
            lane_shipments = [
                s for s in shipments
                if s.get("origin", "").lower() == orig and s.get("destination", "").lower() == dest
            ]
            # Normalize to weekly exposure volume (historical 200 represents ~4-week window)
            eff_shipments = max(1, int(len(lane_shipments) * 0.4))
        else:
            # Fallback baseline
            eff_shipments = 6

    ship_points = min(30.0, eff_shipments * 2.0)

    # Total composite score capped at 100
    total_score = min(100.0, sev_points + dur_points + ship_points)
    if is_monitoring and severity is None:
        total_score *= 0.5  # 50% discount for advisory/monitoring status
    return round(total_score, 1)


# ==============================================================================
# 4. ESTIMATE IMPACT (Shipments Delayed & Delay in Days)
# ==============================================================================

class ImpactEstimate(dict):
    """Dictionary holding impact metrics with convenient attribute access."""
    @property
    def shipments_delayed(self) -> int:
        return self.get("shipments_delayed", 0)

    @property
    def delay_in_days(self) -> float:
        return self.get("delay_in_days", 0.0)


def estimate_impact(lane_id: str) -> Dict[str, Any]:
    """Estimates the operational disruption impact on a lane: shipments delayed and delay duration in days.

    Args:
        lane_id: Unique route lane code (e.g. 'LANE-01', 'LANE-03', 'LANE-11').

    Returns:
        Dict[str, Any]: Dictionary containing:
            - lane_id (str)
            - shipments_delayed (int): Estimated number of freight shipments stalled or slowed
            - delay_in_days (float): Estimated transit delay in days
            - severity (str): Disruption severity level
            - disruption_id (Optional[str]): Triggering event identifier
            - estimated_cost_inr (float): Estimated demurrage and demurrage cost
            - summary (str): Human-readable impact briefing
    """
    lane_clean = str(lane_id).strip().upper()
    active_disruptions = get_active_disruptions(include_monitoring=True)

    matching_disruptions = []
    for d in active_disruptions:
        if lane_clean in lanes_affected_by(d["event_id"]):
            matching_disruptions.append(d)

    routes = _load_all_routes()
    target_route = next((r for r in routes if r.get("lane_id", "").upper() == lane_clean), None)
    lane_name = target_route.get("route_name", lane_clean) if target_route else lane_clean

    if not matching_disruptions:
        return ImpactEstimate({
            "lane_id": lane_clean,
            "route_name": lane_name,
            "shipments_delayed": 0,
            "delay_in_days": 0.0,
            "severity": "NONE",
            "disruption_id": None,
            "disruption_title": "Normal Transit Conditions",
            "estimated_cost_inr": 0.0,
            "summary": f"Lane {lane_clean} ({lane_name}) is fully operational with zero active disruptions."
        })

    # Pick the most critical disruption affecting this lane
    severity_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    matching_disruptions.sort(
        key=lambda x: severity_rank.get(x.get("severity", "MEDIUM").upper(), 1),
        reverse=True
    )
    primary = matching_disruptions[0]
    sev = primary.get("severity", "MEDIUM").upper()

    # Calculate delay in days based on severity and description
    desc = primary.get("description", "").lower()
    if "72-hour" in desc or "72 hour" in desc:
        delay_days = 3.0
    elif "48-hour" in desc or "48 hour" in desc:
        delay_days = 2.0
    elif "24-hour" in desc or "24 hour" in desc or "1 day" in desc:
        delay_days = 1.0
    elif sev == "CRITICAL":
        delay_days = 3.5
    elif sev == "HIGH":
        delay_days = 2.0
    elif sev == "MEDIUM":
        delay_days = 1.0
    else:
        delay_days = 0.5

    # Estimate shipments delayed from historical route density
    shipments = _load_all_shipments()
    if target_route and shipments:
        orig = target_route.get("origin", "").lower()
        dest = target_route.get("destination", "").lower()
        matched = [
            s for s in shipments
            if s.get("origin", "").lower() == orig and s.get("destination", "").lower() == dest
        ]
        # Active exposure estimated around 35-40% of monthly lane flow
        shipments_delayed = max(2, int(len(matched) * 0.35))
    else:
        shipments_delayed = 6

    # Estimated cost: demurrage, truck idling, warehouse holding (~INR 2,200 per truck/day)
    cost_inr = round(shipments_delayed * delay_days * 2200.0, 2)

    summary = (
        f"Lane {lane_clean} ({lane_name}) is degraded: {shipments_delayed} shipments delayed "
        f"by approx. {delay_days} days due to {primary.get('title', 'Active Disruption')} "
        f"[{sev} Severity]. Est. cost impact: INR {cost_inr:,.2f}."
    )

    return ImpactEstimate({
        "lane_id": lane_clean,
        "route_name": lane_name,
        "shipments_delayed": shipments_delayed,
        "delay_in_days": delay_days,
        "severity": sev,
        "disruption_id": primary.get("event_id"),
        "disruption_title": primary.get("title"),
        "estimated_cost_inr": cost_inr,
        "summary": summary
    })


# ==============================================================================
# 5. CLUSTER RISK REPORT & IN-MEMORY SIMULATION (Backwards Compatible)
# ==============================================================================

def get_cluster_risk_report(cluster_name: str) -> Dict[str, Any]:
    """Computes a composite risk score (0 to 100) and active risk warnings for a cluster.

    Maintained for backwards-compatibility with agents/risk_agent.py and dashboard/app.py.
    """
    c_name = cluster_name.capitalize().strip()

    risk_profiles = {
        "Kanpur": {
            "environmental_risk": 75,
            "weather_flood_risk": 60,
            "transport_delay_risk": 30,
            "water_table_status": "High (Ganges River Basin)",
            "ngt_compliance_status": "Yellow Alert (Effluent inspection underway)"
        },
        "Unnao": {
            "environmental_risk": 55,
            "weather_flood_risk": 45,
            "transport_delay_risk": 25,
            "water_table_status": "Moderate",
            "ngt_compliance_status": "Green (Banthar treatment plant normal)"
        },
        "Agra": {
            "environmental_risk": 20,
            "weather_flood_risk": 15,
            "transport_delay_risk": 40,
            "water_table_status": "Normal",
            "ngt_compliance_status": "Green (Footwear assembly - low effluent)"
        },
        "Noida": {
            "environmental_risk": 15,
            "weather_flood_risk": 10,
            "transport_delay_risk": 50,
            "water_table_status": "Normal",
            "ngt_compliance_status": "Green (Export fabrication zone)"
        }
    }

    profile = risk_profiles.get(c_name, {
        "environmental_risk": 30,
        "weather_flood_risk": 30,
        "transport_delay_risk": 30,
        "water_table_status": "Normal",
        "ngt_compliance_status": "Normal"
    })

    cluster_disruptions = [
        d for d in ACTIVE_DISRUPTIONS
        if d.get("cluster", "").lower() == c_name.lower() or c_name in d.get("impacted_clusters", [])
    ]

    composite_score = int(
        (profile["environmental_risk"] * 0.4) +
        (profile["weather_flood_risk"] * 0.3) +
        (profile["transport_delay_risk"] * 0.3)
    )

    if cluster_disruptions:
        composite_score = min(100, composite_score + 15)

    risk_level = "CRITICAL" if composite_score >= 70 else ("ELEVATED" if composite_score >= 45 else "LOW")

    return {
        "cluster": c_name,
        "composite_risk_score": composite_score,
        "risk_level": risk_level,
        "breakdown": profile,
        "active_disruptions": cluster_disruptions,
        "recommendation": (
            "Prepare backup procurement routes from Unnao or buffer stock in Agra."
            if composite_score >= 60 else "Standard operating conditions."
        )
    }


def simulate_disruption(
    cluster_name: str,
    disruption_type: str,
    description: str,
    severity: str = "HIGH",
    affected_lanes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Injects a simulated emergency into active memory for live agent demonstrations."""
    c_name = cluster_name.capitalize().strip()
    sev = severity.upper().strip()
    disruption = {
        "id": f"DISRUPT-{len(ACTIVE_DISRUPTIONS) + 1:03d}",
        "event_id": f"DISRUPT-{len(ACTIVE_DISRUPTIONS) + 1:03d}",
        "cluster": c_name,
        "category": disruption_type,
        "type": disruption_type,
        "severity": sev,
        "title": f"Simulated Emergency: {disruption_type} in {c_name}",
        "description": description,
        "impact": "Triggered automated multi-agent risk assessment.",
        "impacted_clusters": [c_name],
        "status": "ACTIVE"
    }
    if affected_lanes:
        disruption["affected_lanes"] = [str(x).upper() for x in affected_lanes]
        disruption["lanes"] = disruption["affected_lanes"]
    ACTIVE_DISRUPTIONS.append(disruption)
    return {"status": "Disruption active", "disruption": disruption}


def clear_disruptions() -> Dict[str, str]:
    """Clears all in-memory simulated disruptions back to baseline."""
    ACTIVE_DISRUPTIONS.clear()
    return {"status": "All active disruptions cleared."}
