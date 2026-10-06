"""
agents/guardrails.py   (USE ONLY IF YOUR PROJECT DOES NOT ALREADY HAVE ONE)
Human-in-the-loop rules. Function names match what orchestrator.py and api/main.py import.
Approvals are stored in data/firestore_mock/approvals.json (the file the API already reads).
"""
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPROVAL_FILE = os.path.join(ROOT, "data", "firestore_mock", "approvals.json")

AUTO_APPROVE_LIMIT_INR = 10_000    # lower it to see more approval cards in your demo
MAX_REROUTE_INCREASE_PCT = 30


@dataclass
class GuardrailDecision:
    approved: bool
    requires_human_approval: bool
    status: str            # "approved" or "pending"
    rule_name: str
    reason: str
    action_type: str


def evaluate_guardrails(payload: dict) -> GuardrailDecision:
    """Check one proposed action. Returns whether a human must approve it."""
    action_type = str(payload.get("type", "transfer"))
    cost = float(payload.get("amount") or payload.get("estimated_cost_inr") or 0)

    rule, reason = None, None
    if payload.get("requires_compliance_signoff"):
        rule, reason = "COMPLIANCE_SIGNOFF", "Compliance paperwork always needs a human."
    elif action_type == "purchase_order" and cost > AUTO_APPROVE_LIMIT_INR:
        rule, reason = "PURCHASE_ORDER_LIMIT", f"Purchase order Rs {cost:,.0f} is above the limit."
    elif payload.get("is_reroute"):
        old = float(payload.get("original_cost_inr") or 0)
        new = float(payload.get("new_cost_inr") or cost)
        if old > 0 and (new - old) / old * 100 > MAX_REROUTE_INCREASE_PCT:
            rule, reason = "REROUTE_COST_INCREASE", f"Reroute costs more than {MAX_REROUTE_INCREASE_PCT}% extra."
    if rule is None and cost > AUTO_APPROVE_LIMIT_INR:
        rule, reason = "TRANSFER_COST_LIMIT", f"Cost Rs {cost:,.0f} is above the auto-approve limit Rs {AUTO_APPROVE_LIMIT_INR:,}."

    if rule:
        return GuardrailDecision(False, True, "pending", rule, reason, action_type)
    return GuardrailDecision(True, False, "approved", "AUTO_APPROVE_TIER_1",
                             f"Within the auto-approve limit of Rs {AUTO_APPROVE_LIMIT_INR:,}.", action_type)


# ---- storage helpers --------------------------------------------------------
def _load() -> list:
    try:
        with open(APPROVAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(items: list) -> None:
    os.makedirs(os.path.dirname(APPROVAL_FILE), exist_ok=True)
    with open(APPROVAL_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def save_approval_item(approval_id, item_type, details, amount, status, rule_triggered, reason):
    items = [i for i in _load() if i.get("request_id") != approval_id]
    record = {
        "request_id": approval_id, "type": item_type, "details": details, "amount": amount,
        "status": status, "rule_triggered": rule_triggered, "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision_by": None, "note": None,
    }
    items.append(record)
    _save(items)
    return record


def update_approval_status(plan_id, status, decision_by="", note=""):
    items = _load()
    for i in items:
        if i.get("request_id") == plan_id:
            i["status"], i["decision_by"], i["note"] = status, decision_by, note
            i["decided_at"] = datetime.now(timezone.utc).isoformat()
            _save(items)
            return True
    return False


def get_approval_status(plan_id):
    for i in _load():
        if i.get("request_id") == plan_id:
            return i.get("status")
    return None


def wait_for_approval_resolution(plan_id, timeout_seconds=0.0, poll_seconds=1.0) -> dict:
    """Pause until a human approves/rejects, or until the timeout ends."""
    end = time.time() + float(timeout_seconds)
    while True:
        st = get_approval_status(plan_id)
        if st and str(st).lower() in ("approved", "rejected"):
            return {"resolved": True, "status": str(st).lower()}
        if time.time() >= end:
            return {"resolved": False, "status": st or "pending"}
        time.sleep(poll_seconds)