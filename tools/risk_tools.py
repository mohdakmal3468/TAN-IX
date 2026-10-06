"""
tools/risk_tools.py
-------------------
Monitors regional risks affecting the UP leather manufacturing clusters:
1. Environmental Regulations: NGT & UP Pollution Control Board (UPPCB) tannery notices.
2. Hydrological Risk: Ganges basin monsoon flood levels at Kanpur Barrage and Shuklaganj.
3. Transport Disruption: Dense fog speed restrictions on Yamuna Expressway or waterlogging on NH-27.
4. Input Price Spikes: Raw hide and chemical cost volatility.

Includes a dynamic disruption injector so you can test scenarios in your Capstone demo!
"""

from typing import Dict, Any, List

# In-memory simulated disruption state
ACTIVE_DISRUPTIONS: List[Dict[str, Any]] = [
    {
        "id": "DISRUPT-001",
        "cluster": "Kanpur",
        "category": "Regulatory",
        "severity": "HIGH",
        "title": "UPPCB & NGT Compliance Notice on Jajmau CETP",
        "description": "Due to effluent discharge limit violations, UPPCB has placed 12 tanneries on a 48-hour temporary reduction warning.",
        "impact": "Tanned leather output from Kanpur may drop by 40% over the next 3 days."
    }
]


def get_cluster_risk_report(cluster_name: str) -> Dict[str, Any]:
    """
    Computes a composite risk score (0 to 100) and provides active risk warnings
    for a given cluster.
    """
    c_name = cluster_name.capitalize().strip()

    # Base risk profiles by cluster
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

    # Find any active disruption for this cluster
    cluster_disruptions = [d for d in ACTIVE_DISRUPTIONS if d["cluster"].lower() == c_name.lower()]

    # Calculate weighted composite score
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


def simulate_disruption(cluster_name: str, disruption_type: str, description: str) -> Dict[str, Any]:
    """
    Capstone Demo Tool: Allows you to inject an emergency (like heavy Ganges flooding
    or an NGT raid) to demonstrate autonomous agent reactions!
    """
    c_name = cluster_name.capitalize().strip()
    disruption = {
        "id": f"DISRUPT-{len(ACTIVE_DISRUPTIONS) + 1:03d}",
        "cluster": c_name,
        "category": disruption_type,
        "severity": "HIGH",
        "title": f"Simulated Emergency: {disruption_type} in {c_name}",
        "description": description,
        "impact": "Triggered automated multi-agent risk assessment."
    }
    ACTIVE_DISRUPTIONS.append(disruption)
    return {"status": "Disruption active", "disruption": disruption}


def clear_disruptions() -> Dict[str, str]:
    """Clears all simulated disruptions back to normal baseline."""
    ACTIVE_DISRUPTIONS.clear()
    return {"status": "All active disruptions cleared."}
