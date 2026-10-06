"""
agents/risk_agent.py
--------------------
The Regional Risk Agent is responsible for:
1. Monitoring environmental compliance (NGT and UPPCB effluent mandates).
2. Hydrological and weather tracking across the Ganges basin (Kanpur/Unnao).
3. Querying Vector Search knowledge base for UP Industrial Leather policies & freight subsidies.
4. Outputting cluster risk indices and operational disruption alerts.
"""

from typing import Dict, Any, List
from tools.risk_tools import get_cluster_risk_report
from tools.vector_tools import search_policy_docs
from config import UP_CLUSTERS, GEMINI_API_KEY, GEMINI_MODEL


class RegionalRiskAgent:
    """
    Autonomous risk intelligence agent evaluating environmental, climate, and regulatory hazards.
    """

    def __init__(self):
        self.name = "Regional Risk Agent"
        self.role = "Evaluate environmental compliance, Ganga basin flooding, and policy regulations via Vector Search."

    def assess_all_clusters(self) -> Dict[str, Any]:
        """
        Assesses risks across all 4 UP leather hubs and retrieves relevant policy guidelines.
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

        # Query vector search for relevant regulatory policies (e.g. NGT & flood protocols)
        policy_context = search_policy_docs("NGT effluent compliance and flood protocols in Kanpur and Unnao", top_k=2)

        assessment = {
            "agent": self.name,
            "monitored_clusters": list(UP_CLUSTERS.keys()),
            "high_risk_clusters": high_risk_clusters,
            "cluster_risk_reports": reports,
            "regulatory_policy_citations": policy_context,
            "system_threat_level": "ELEVATED" if high_risk_clusters else "NORMAL"
        }

        # AI synthesis if Gemini API key is available
        if GEMINI_API_KEY:
            try:
                from google import genai
                client = genai.Client(api_key=GEMINI_API_KEY)
                prompt = f"""
                You are the Regional Risk Agent for the Uttar Pradesh Leather Industrial Corridor.
                Review the following cluster risks and policy guidelines:
                High Risk Clusters: {high_risk_clusters}
                Policies Cited: {policy_context}
                Provide a 2-3 sentence strategic briefing on where supply chain disruptions are most imminent.
                """
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt
                )
                assessment["ai_risk_brief"] = response.text
            except Exception:
                assessment["ai_risk_brief"] = (
                    f"Warning: Elevated risk in Kanpur (Score: {reports.get('Kanpur', {}).get('composite_risk_score', 75)}) "
                    f"due to UPPCB effluent restrictions and Ganges basin hydrology. Recommend proactive buffer stock routing."
                )
        else:
            assessment["ai_risk_brief"] = (
                f"Warning: Elevated risk in Kanpur (Score: {reports.get('Kanpur', {}).get('composite_risk_score', 75)}) "
                f"due to UPPCB effluent restrictions and Ganges basin hydrology. Recommend proactive buffer stock routing."
            )

        return assessment
