"""
tools/discord_tools.py
----------------------
Manages Human-in-the-Loop (HITL) approval workflows via Discord Webhooks.

Features:
- Formats rich Discord Embed cards with stock deficit details, risk scores, and estimated logistics costs.
- Includes clickable approval/rejection callback URLs connected to the FastAPI backend.
- Gracefully handles offline or mock mode when no live Discord webhook is configured.
"""

import json
import requests
from typing import Dict, Any
from config import DISCORD_WEBHOOK_URL, FASTAPI_HOST, FASTAPI_PORT

# In-memory store for pending human approval requests
PENDING_APPROVALS: Dict[str, Dict[str, Any]] = {}


def send_discord_approval_request(rebalance_plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatches a high-priority approval request card to Discord with full details
    of the suggested supply chain rebalancing action.
    """
    plan_id = rebalance_plan.get("plan_id", f"PLAN-{len(PENDING_APPROVALS) + 1:04d}")
    rebalance_plan["plan_id"] = plan_id
    rebalance_plan["approval_status"] = "PENDING"
    PENDING_APPROVALS[plan_id] = rebalance_plan

    origin = rebalance_plan.get("origin", "Kanpur")
    destination = rebalance_plan.get("destination", "Agra")
    item = rebalance_plan.get("item", "Leather Stock")
    quantity = rebalance_plan.get("quantity", 0)
    cost = rebalance_plan.get("estimated_cost_inr", 0)
    risk_reason = rebalance_plan.get("risk_justification", "Proactive cluster stock balancing")

    base_api_url = f"http://{FASTAPI_HOST}:{FASTAPI_PORT}"
    approve_url = f"{base_api_url}/approval/discord-callback?plan_id={plan_id}&action=approve"
    reject_url = f"{base_api_url}/approval/discord-callback?plan_id={plan_id}&action=reject"

    # Discord Embed Payload format
    discord_payload = {
        "username": "TAN-IX State Orchestrator",
        "avatar_url": "https://img.icons8.com/color/96/leather.png",
        "content": "⚠️ **STATE-LEVEL HUMAN APPROVAL REQUIRED FOR LEATHER REBALANCING**",
        "embeds": [
            {
                "title": f"Inter-Cluster Transfer Request: {plan_id}",
                "description": (
                    f"The Multi-Agent System detected a critical supply chain risk and proposes "
                    f"an emergency stock rebalance along the UP Industrial Corridor."
                ),
                "color": 15158332,  # Crimson / Warning red
                "fields": [
                    {"name": "Origin Cluster", "value": f"🏭 **{origin}**", "inline": True},
                    {"name": "Destination Cluster", "value": f"👞 **{destination}**", "inline": True},
                    {"name": "Transfer Material", "value": f"📦 **{quantity} sq ft** of {item}", "inline": False},
                    {"name": "Estimated Logistics Cost", "value": f"₹{cost:,.2f} (Expressway Tolls Included)", "inline": True},
                    {"name": "Transit Route", "value": rebalance_plan.get("route_name", "Agra-Lucknow Expway"), "inline": True},
                    {"name": "Risk Mitigation Reason", "value": risk_reason, "inline": False},
                    {
                        "name": "One-Click Human Authorization Links",
                        "value": f"✅ [Click Here to APPROVE]({approve_url})\n❌ [Click Here to REJECT]({reject_url})",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "TAN-IX Autonomous Supply Chain Engine | Uttar Pradesh Clusters"
                }
            }
        ]
    }

    # Dispatch to Discord webhook if configured
    if DISCORD_WEBHOOK_URL and "discord.com" in DISCORD_WEBHOOK_URL:
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=discord_payload, timeout=5)
            if resp.status_code in (200, 204):
                return {
                    "dispatched": True,
                    "channel": "Discord Live Webhook",
                    "plan_id": plan_id,
                    "status": "Awaiting Human Approval",
                    "approve_url": approve_url,
                    "reject_url": reject_url
                }
        except Exception as e:
            print(f"[Discord Webhook Error] {e}")

    # Fallback simulation response (when working locally without active Discord webhook)
    print(f"\n[HITL Approval Dispatched Locally] Plan ID: {plan_id}")
    print(f"Transfer: {quantity} {item} from {origin} to {destination} | Est. Cost: INR {cost}")
    print(f"Approve URL: {approve_url}")

    return {
        "dispatched": True,
        "channel": "Local Simulated Approval Queue",
        "plan_id": plan_id,
        "status": "Awaiting Human Approval",
        "approve_url": approve_url,
        "reject_url": reject_url,
        "note": "Discord webhook URL not configured in .env; simulated locally."
    }


def record_approval_decision(plan_id: str, action: str) -> Dict[str, Any]:
    """
    Records human decision (approve or reject) and returns the updated plan status.
    """
    if plan_id not in PENDING_APPROVALS:
        return {"success": False, "message": f"Plan ID '{plan_id}' not found."}

    plan = PENDING_APPROVALS[plan_id]
    if action.lower() == "approve":
        plan["approval_status"] = "APPROVED"
        return {"success": True, "plan_id": plan_id, "status": "APPROVED", "plan": plan}
    else:
        plan["approval_status"] = "REJECTED"
        return {"success": True, "plan_id": plan_id, "status": "REJECTED", "plan": plan}
