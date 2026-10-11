"""
agents/risk_agent.py
--------------------
Regional Risk Agent for the Uttar Pradesh Leather Industrial Corridor.
Built with Google ADK (Agent Development Kit) and Gemini 3.1 Flash.

Responsibilities:
1. Monitors active supply chain disruptions, regulatory mandates (NGT/UPPCB), and weather hazards.
2. Evaluates lane-level quantitative risk scores (0 to 100) across all highway corridors.
3. Quantifies operational delays (shipments delayed, duration in days, financial demurrage).
4. Generates a plain-English impact analysis and strategic guidance as structured JSON.
"""

import os
import sys
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Ensure root directory is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from google.adk import Agent
from tools.risk_tools import (
    get_active_disruptions,
    lanes_affected_by,
    calculate_lane_risk_score,
    estimate_impact,
    get_cluster_risk_report,
    simulate_disruption,
    clear_disruptions,
    _load_all_routes
)
from tools.vector_tools import search_policy_docs
from config import UP_CLUSTERS, HIGHWAY_CORRIDORS

from tools.llm import ask_gemini, MODEL_NAME

# ==============================================================================
# AGENT INSTRUCTION (Job Description & Decision Framework)
# ==============================================================================
INSTRUCTION = """
You are the Regional Risk Agent for the Uttar Pradesh Leather Supply Chain (Kanpur, Unnao, Agra, Noida).

CORE MISSION:
1. Continuously monitor active disruptions (flooding along the Ganges river basin, winter fog on Yamuna Expressway, NGT effluent compliance notices, and highway blockades).
2. For each highway transit corridor, evaluate quantitative lane risk scores (0 to 100) using `calculate_lane_risk_score(lane_id)`.
3. For all disrupted or degraded lanes, call `estimate_impact(lane_id)` to determine delayed shipments, delay duration in days, and demurrage cost.
4. Translate technical and numerical risks into a clear, plain-English impact analysis that non-technical dispatchers, plant managers, and the State Orchestrator can immediately act upon.

RISK TIERS:
- 0 to 24:   LOW (Green - Normal transit conditions, all clear)
- 25 to 49:  MODERATE (Yellow - Minor delays, monitor transit)
- 50 to 74:  ELEVATED (Orange - Active disruption, reroute priority shipments)
- 75 to 100: CRITICAL (Red - Corridor impassable or blocked, mandatory detour)

STRICT JSON OUTPUT FORMAT:
You must output valid structured JSON matching this schema:
{
  "status": "NORMAL | ELEVATED_RISK | CRITICAL_ALERT",
  "active_disruptions_count": int,
  "active_disruptions": [
    {
      "event_id": "string",
      "title": "string",
      "location": "string",
      "severity": "string",
      "status": "string",
      "affected_lanes": ["LANE-..."]
    }
  ],
  "lane_risk_scores": [
    {
      "lane_id": "string",
      "route_name": "string",
      "origin": "string",
      "destination": "string",
      "risk_score": float,
      "risk_level": "LOW | MODERATE | ELEVATED | CRITICAL",
      "is_disrupted": bool,
      "shipments_delayed": int,
      "delay_in_days": float,
      "estimated_cost_inr": float
    }
  ],
  "high_risk_lanes": ["LANE-..."],
  "impact_analysis": {
    "plain_english_summary": "string",
    "total_shipments_delayed": int,
    "max_delay_days": float,
    "total_cost_impact_inr": float,
    "corridor_briefings": [
      {
        "lane_id": "string",
        "impact": "string",
        "recommended_action": "string"
      }
    ],
    "recommendations": ["string"]
  }
}
"""

# ==============================================================================
# GOOGLE ADK AGENT DEFINITION
# ==============================================================================
agent = Agent(
    name="regional_risk_agent",
    model=MODEL_NAME,
    description="Monitors UP leather logistics disruptions, calculates lane risk scores, and generates plain-English impact assessments.",
    instruction=INSTRUCTION,
    tools=[
        get_active_disruptions,
        lanes_affected_by,
        calculate_lane_risk_score,
        estimate_impact,
        get_cluster_risk_report
    ]
)

root_agent = agent


# ==============================================================================
# CALLABLE CONTROLLER CLASS (For Orchestrator & Standalone Testing)
# ==============================================================================
class RegionalRiskAgent:
    """
    Autonomous risk intelligence agent evaluating environmental, climate,
    highway disruption, and corridor bottleneck hazards.
    """

    def __init__(self):
        self.name = "Regional Risk Agent"
        self.role = "Monitor supply chain disruptions, calculate highway lane risk scores, and deliver plain-English impact analyses."
        self.adk_agent = agent

    def assess_corridor_risks(self) -> Dict[str, Any]:
        """
        Monitors disruptions across UP, evaluates lane-level risk scores (0-100),
        and returns a structured plain-English impact analysis as JSON.
        """
        # Step 1: Query active disruptions
        active_disruptions = get_active_disruptions(include_monitoring=True)

        # Enrich active disruptions with mapped affected lanes
        enriched_disruptions = []
        all_disrupted_lanes = set()
        for d in active_disruptions:
            aff = lanes_affected_by(d["event_id"])
            for l in aff:
                all_disrupted_lanes.add(l)
            enriched_disruptions.append({
                "event_id": d["event_id"],
                "title": d.get("title", ""),
                "location": d.get("location", ""),
                "severity": d.get("severity", "MEDIUM"),
                "status": d.get("status", "ACTIVE"),
                "affected_lanes": aff
            })

        # Step 2: Evaluate all known UP freight route lanes
        lane_risk_scores = []
        high_risk_lanes = []
        corridor_briefings = []

        total_delayed_shipments = 0
        max_delay_days = 0.0
        total_cost_inr = 0.0

        routes = _load_all_routes()
        for r in routes:
            lane_id = r["lane_id"]
            r_name = r.get("route_name", lane_id)
            orig = r.get("origin", "Unknown")
            dest = r.get("destination", "Unknown")

            score = calculate_lane_risk_score(lane_id)

            if score >= 75.0:
                level = "CRITICAL"
                high_risk_lanes.append(lane_id)
            elif score >= 50.0:
                level = "ELEVATED"
                high_risk_lanes.append(lane_id)
            elif score >= 25.0:
                level = "MODERATE"
            else:
                level = "LOW"

            is_disrupted = lane_id in all_disrupted_lanes or score >= 25.0

            # Step 3: Quantify impact if lane is degraded
            if is_disrupted:
                impact = estimate_impact(lane_id)
                shps_del = impact.get("shipments_delayed", 0)
                del_days = impact.get("delay_in_days", 0.0)
                cost = impact.get("estimated_cost_inr", 0.0)

                total_delayed_shipments += shps_del
                if del_days > max_delay_days:
                    max_delay_days = del_days
                total_cost_inr += cost

                corridor_briefings.append({
                    "lane_id": lane_id,
                    "impact": (
                        f"{r_name} ({orig} -> {dest}) is facing {level} risk (Score: {score}/100). "
                        f"{shps_del} shipments delayed by approximately {del_days} days. "
                        f"Est. demurrage loss: INR {cost:,.2f}."
                    ),
                    "recommended_action": (
                        f"Immediately detour freight through alternative corridors or pause dispatches."
                        if level == "CRITICAL"
                        else f"Switch to high-reliability carrier and monitor transit checkpoints."
                    )
                })
            else:
                shps_del = 0
                del_days = 0.0
                cost = 0.0

            lane_risk_scores.append({
                "lane_id": lane_id,
                "route_name": r_name,
                "origin": orig,
                "destination": dest,
                "risk_score": score,
                "risk_level": level,
                "is_disrupted": is_disrupted,
                "shipments_delayed": shps_del,
                "delay_in_days": del_days,
                "estimated_cost_inr": cost
            })

        # Step 4: Determine overall network status
        if any(item["risk_level"] == "CRITICAL" for item in lane_risk_scores):
            overall_status = "CRITICAL_ALERT"
        elif any(item["risk_level"] == "ELEVATED" for item in lane_risk_scores):
            overall_status = "ELEVATED_RISK"
        else:
            overall_status = "NORMAL"

        # Step 5: Synthesize plain-English summary
        if high_risk_lanes:
            affected_summary = ", ".join(high_risk_lanes)
            plain_english = (
                f"Elevated risk detected on {len(high_risk_lanes)} highway corridors ({affected_summary}). "
                f"A total of {total_delayed_shipments} freight shipments are currently stalled or experiencing "
                f"delays of up to {max_delay_days} days across the UP Leather belt. "
                f"Estimated cumulative supply chain holding costs stand at INR {total_cost_inr:,.2f}."
            )
            recommendations = [
                "Execute autonomous rerouting via secondary national highways (e.g. NH-19 arterial alternatives).",
                "Buffer finished inventory at Agra footwear assembly lines to prevent production stoppage.",
                "Prioritize high-reliability carriers over low-cost options during active disruptions."
            ]
        else:
            plain_english = (
                "All primary expressway corridors across Kanpur, Unnao, Agra, and Noida are operating under normal "
                "transit conditions with zero critical bottlenecks."
            )
            recommendations = [
                "Maintain standard dispatch schedules utilizing lowest-cost commercial carriers."
            ]

        structured_output = {
            "status": overall_status,
            "active_disruptions_count": len(enriched_disruptions),
            "active_disruptions": enriched_disruptions,
            "lane_risk_scores": lane_risk_scores,
            "high_risk_lanes": high_risk_lanes,
            "impact_analysis": {
                "plain_english_summary": plain_english,
                "total_shipments_delayed": total_delayed_shipments,
                "max_delay_days": max_delay_days,
                "total_cost_impact_inr": round(total_cost_inr, 2),
                "corridor_briefings": corridor_briefings,
                "recommendations": recommendations
            }
        }

        # AI briefing enrichment
        try:
            prompt = f"""
            You are the Regional Risk Agent for the UP Leather Industrial Corridor.
            Review the following highway risk scores:
            High Risk Lanes: {high_risk_lanes}
            Total Delayed Shipments: {total_delayed_shipments}
            Total Demurrage Cost: INR {total_cost_inr:,.2f}
            Provide a crisp 2-sentence plain-English executive impact summary for state logistics dispatchers.
            """
            structured_output["impact_analysis"]["plain_english_summary"] = ask_gemini(prompt)
        except Exception:
            pass

        return structured_output

    def assess_all_clusters(self) -> Dict[str, Any]:
        """
        Assesses risks across all 4 UP leather hubs and queries policy guidelines.
        Maintained for 100% backwards-compatibility with dashboard/app.py and orchestrator.
        """
        reports = {}
        high_risk_clusters = []

        for cluster_name in UP_CLUSTERS.keys():
            report = get_cluster_risk_report(cluster_name)
            reports[cluster_name] = report
            if report.get("composite_risk_score", 0) >= 50 or report.get("active_disruptions"):
                high_risk_clusters.append({
                    "cluster": cluster_name,
                    "score": report.get("composite_risk_score"),
                    "level": report.get("risk_level"),
                    "active_disruptions": report.get("active_disruptions", [])
                })

        policy_context = search_policy_docs("NGT effluent compliance and flood protocols in Kanpur and Unnao", top_k=2)
        corridor_data = self.assess_corridor_risks()

        return {
            "agent": self.name,
            "monitored_clusters": list(UP_CLUSTERS.keys()),
            "high_risk_clusters": high_risk_clusters,
            "cluster_risk_reports": reports,
            "corridor_risks": corridor_data,
            "regulatory_policy_citations": policy_context,
            "system_threat_level": corridor_data.get("status", "NORMAL"),
            "ai_risk_brief": corridor_data.get("impact_analysis", {}).get("plain_english_summary", "")
        }


# ==============================================================================
# STANDALONE DEMO & TEST RUNNER
# ==============================================================================
if __name__ == "__main__":
    print("=" * 75)
    print("REGIONAL RISK AGENT (Google ADK & Gemini 3.1 Flash)")
    print("Highway Disruption Monitoring, Corridor Risk Scoring & Impact Analysis")
    print("=" * 75)

    risk_agent = RegionalRiskAgent()

    # --------------------------------------------------------------------------
    # Step 1: Baseline Assessment (Prior to Unnao Blockade)
    # --------------------------------------------------------------------------
    print("\n[Step 1] Baseline Highway Risk Assessment (Normal / Pre-Blockade State)...")
    clear_disruptions()

    baseline_assessment = risk_agent.assess_corridor_risks()

    # Find baseline scores for Unnao corridors (LANE-01: Kanpur->Unnao, LANE-02: Unnao->Kanpur)
    unnao_lanes_pre = {
        item["lane_id"]: item["risk_score"]
        for item in baseline_assessment["lane_risk_scores"]
        if item["lane_id"] in ["LANE-01", "LANE-02", "LANE-07"]
    }
    print("\nBaseline Unnao Corridor Risk Scores:")
    for lid, score in unnao_lanes_pre.items():
        print(f"  - {lid}: {score}/100")

    # --------------------------------------------------------------------------
    # Step 2: Insert Highway Blockade Near Unnao
    # --------------------------------------------------------------------------
    print("\n" + "-" * 75)
    print("[Step 2] Disruptive Event: Inserting Highway Blockade near Unnao...")
    blockade_event = simulate_disruption(
        cluster_name="Unnao",
        disruption_type="HIGHWAY_BLOCKADE",
        description="Transporters union strike and truck blockade near Unnao Banthar corridor on NH-27 halting all freight movement.",
        severity="CRITICAL",
        affected_lanes=["LANE-01", "LANE-02"]
    )
    print(f"-> Disruption Injected: {blockade_event['disruption']['title']}")
    print(f"   Severity: {blockade_event['disruption']['severity']} | Affected Lanes: {blockade_event['disruption']['affected_lanes']}")

    # --------------------------------------------------------------------------
    # Step 3: Post-Blockade Assessment & Score Rise Verification
    # --------------------------------------------------------------------------
    print("\n[Step 3] Re-evaluating Corridor Risks Post-Blockade...")
    post_assessment = risk_agent.assess_corridor_risks()

    unnao_lanes_post = {
        item["lane_id"]: item["risk_score"]
        for item in post_assessment["lane_risk_scores"]
        if item["lane_id"] in ["LANE-01", "LANE-02", "LANE-07"]
    }

    print("\nPost-Blockade Risk Score Comparison:")
    for lid in ["LANE-01", "LANE-02", "LANE-07"]:
        pre = unnao_lanes_pre.get(lid, 0.0)
        post = unnao_lanes_post.get(lid, 0.0)
        rise = post - pre
        symbol = "^" if rise > 0 else "="
        print(f"  - {lid}: {pre:4.1f} -> {post:4.1f}  (+{rise:4.1f} pts) {symbol} [{post_assessment['status']}]")

    print("\n" + "=" * 75)
    print("STRUCTURED JSON OUTPUT (Post-Blockade Impact Analysis):")
    print("=" * 75)
    clean_json_output = {
        "status": post_assessment["status"],
        "active_disruptions_count": post_assessment["active_disruptions_count"],
        "high_risk_lanes": post_assessment["high_risk_lanes"],
        "unnao_affected_lanes": [
            item for item in post_assessment["lane_risk_scores"]
            if item["lane_id"] in ["LANE-01", "LANE-02"]
        ],
        "impact_analysis": post_assessment["impact_analysis"]
    }
    print(json.dumps(clean_json_output, indent=2))

    # Clean up state
    clear_disruptions()

    print("\n" + "=" * 75)
    print("RUN WITH GOOGLE ADK CLI:")
    print("  python -m google.adk.cli run agents/risk_agent \"Analyze active corridor disruptions across UP\" --in_memory")
    print("=" * 75)
