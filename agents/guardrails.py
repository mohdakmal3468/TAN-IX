"""
agents/guardrails.py
--------------------
Autonomous Supply Chain Governance and Guardrails Engine for TAN-IX.

Statutory Governance Rules Matrix:
1. Transfers under 50,000 INR -> Auto-approved.
   Transfers >= 50,000 INR -> Require human approval.
2. Standard reroutes (cost increase <= 30%) -> Auto-approved.
   Route changes above 30% cost increase -> Require human approval.
3. Purchase orders over 50,000 INR -> Require human approval.
   Purchase orders <= 50,000 INR -> Auto-approved.
4. All compliance paperwork -> Require human approval.

Workflow & Lifecycle:
- Items requiring human approval are saved to the Firestore 'approvals' collection
  with status 'pending' (options: pending, approved, rejected).
- The State Master Orchestrator pauses execution until the approval status changes.
"""

import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from tools.firestore_client import set_document, get_document, list_documents
from tools.discord_tools import PENDING_APPROVALS

# Constants
TRANSFER_AUTO_LIMIT_INR = 50000.0
PURCHASE_ORDER_LIMIT_INR = 50000.0
REROUTE_MAX_COST_INCREASE_PCT = 30.0

VALID_STATUSES = ("pending", "approved", "rejected")


class GuardrailDecision:
    """Represents the structured governance evaluation outcome from Guardrails."""

    def __init__(
        self,
        approved: bool,
        status: str,
        rule_name: str,
        reason: str,
        action_type: str,
        requires_human_approval: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.approved = approved
        self.status = status.lower().strip()
        self.rule_name = rule_name
        self.reason = reason
        self.action_type = action_type
        self.requires_human_approval = requires_human_approval
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "status": self.status,
            "rule_name": self.rule_name,
            "reason": self.reason,
            "action_type": self.action_type,
            "requires_human_approval": self.requires_human_approval,
            "metadata": self.metadata
        }

    def __repr__(self) -> str:
        return f"<GuardrailDecision rule={self.rule_name} status={self.status} requires_human={self.requires_human_approval}>"


# ==============================================================================
# 1. CORE GUARDRAIL RULE CHECKERS
# ==============================================================================

def check_transfer_rule(amount_inr: float, details: Optional[Dict[str, Any]] = None) -> GuardrailDecision:
    """
    Rule 1: Transfers under 50,000 INR are auto-approved;
    transfers >= 50,000 INR require human approval.
    """
    amt = float(amount_inr)
    if amt < TRANSFER_AUTO_LIMIT_INR:
        return GuardrailDecision(
            approved=True,
            status="approved",
            rule_name="TRANSFER_UNDER_50K_AUTO_APPROVE",
            reason=f"Transfer amount INR {amt:,.2f} is under 50,000 INR threshold. Auto-approved.",
            action_type="transfer",
            requires_human_approval=False,
            metadata={"amount_inr": amt, "limit_inr": TRANSFER_AUTO_LIMIT_INR, "details": details or {}}
        )
    else:
        return GuardrailDecision(
            approved=False,
            status="pending",
            rule_name="TRANSFER_OVER_50K_HUMAN_APPROVAL",
            reason=f"Transfer amount INR {amt:,.2f} meets or exceeds 50,000 INR threshold. Requires human approval.",
            action_type="transfer",
            requires_human_approval=True,
            metadata={"amount_inr": amt, "limit_inr": TRANSFER_AUTO_LIMIT_INR, "details": details or {}}
        )


def check_reroute_rule(
    original_cost_inr: float,
    new_cost_inr: float,
    details: Optional[Dict[str, Any]] = None
) -> GuardrailDecision:
    """
    Rule 2: Standard reroutes are auto-approved;
    route changes above 30% cost increase require human approval.
    """
    orig = max(1.0, float(original_cost_inr))
    new_c = float(new_cost_inr)
    cost_diff = new_c - orig
    pct_increase = round((cost_diff / orig) * 100.0, 2)

    if pct_increase > REROUTE_MAX_COST_INCREASE_PCT:
        return GuardrailDecision(
            approved=False,
            status="pending",
            rule_name="REROUTE_COST_EXCEEDS_30PCT_HUMAN_APPROVAL",
            reason=(
                f"Route change cost increase of {pct_increase:.1f}% exceeds 30% threshold "
                f"(INR {orig:,.2f} -> INR {new_c:,.2f}). Requires human approval."
            ),
            action_type="reroute",
            requires_human_approval=True,
            metadata={
                "original_cost_inr": orig,
                "new_cost_inr": new_c,
                "pct_increase": pct_increase,
                "limit_pct": REROUTE_MAX_COST_INCREASE_PCT,
                "details": details or {}
            }
        )
    else:
        return GuardrailDecision(
            approved=True,
            status="approved",
            rule_name="STANDARD_REROUTE_AUTO_APPROVE",
            reason=(
                f"Standard reroute cost increase of {pct_increase:.1f}% is within 30% threshold "
                f"(INR {orig:,.2f} -> INR {new_c:,.2f}). Auto-approved."
            ),
            action_type="reroute",
            requires_human_approval=False,
            metadata={
                "original_cost_inr": orig,
                "new_cost_inr": new_c,
                "pct_increase": pct_increase,
                "limit_pct": REROUTE_MAX_COST_INCREASE_PCT,
                "details": details or {}
            }
        )


def check_purchase_order_rule(amount_inr: float, details: Optional[Dict[str, Any]] = None) -> GuardrailDecision:
    """
    Rule 3: Purchase orders over 50,000 INR require human approval;
    purchase orders <= 50,000 INR are auto-approved.
    """
    amt = float(amount_inr)
    if amt > PURCHASE_ORDER_LIMIT_INR:
        return GuardrailDecision(
            approved=False,
            status="pending",
            rule_name="PURCHASE_ORDER_OVER_50K_HUMAN_APPROVAL",
            reason=f"Purchase order amount INR {amt:,.2f} exceeds 50,000 INR threshold. Requires human approval.",
            action_type="purchase_order",
            requires_human_approval=True,
            metadata={"amount_inr": amt, "limit_inr": PURCHASE_ORDER_LIMIT_INR, "details": details or {}}
        )
    else:
        return GuardrailDecision(
            approved=True,
            status="approved",
            rule_name="PURCHASE_ORDER_UNDER_50K_AUTO_APPROVE",
            reason=f"Purchase order amount INR {amt:,.2f} is within 50,000 INR threshold. Auto-approved.",
            action_type="purchase_order",
            requires_human_approval=False,
            metadata={"amount_inr": amt, "limit_inr": PURCHASE_ORDER_LIMIT_INR, "details": details or {}}
        )


def check_compliance_paperwork_rule(
    document_type: str = "statutory_manifest",
    details: Optional[Dict[str, Any]] = None
) -> GuardrailDecision:
    """
    Rule 4: All compliance paperwork requires human approval.
    """
    doc_label = str(document_type or "statutory_manifest").strip()
    return GuardrailDecision(
        approved=False,
        status="pending",
        rule_name="COMPLIANCE_PAPERWORK_HUMAN_APPROVAL",
        reason=f"All compliance paperwork ({doc_label}) requires human supervisor sign-off and verification.",
        action_type="compliance_paperwork",
        requires_human_approval=True,
        metadata={"document_type": doc_label, "details": details or {}}
    )


# ==============================================================================
# 2. COMPOSITE GUARDRAILS EVALUATOR
# ==============================================================================

def evaluate_guardrails(item: Dict[str, Any]) -> GuardrailDecision:
    """
    Evaluates a general supply chain request or rebalancing plan against the 4 rules:
    - Transfers under 50,000 INR vs >= 50,000 INR
    - Standard reroutes vs route changes > 30% cost increase
    - Purchase orders over 50,000 INR
    - All compliance paperwork
    """
    item_type = str(item.get("type") or item.get("action") or "").lower().strip()

    # Check 1: Compliance paperwork flag or explicit type
    if (
        item_type in ("compliance_paperwork", "transit_permit", "statutory_manifest", "paperwork")
        or item.get("is_compliance_paperwork") is True
        or item.get("requires_compliance_signoff") is True
    ):
        doc_type = item.get("document_type") or item.get("paperwork_type") or "Form UP-EWAY-01 Transit Permit"
        return check_compliance_paperwork_rule(document_type=doc_type, details=item)

    # Check 2: Purchase Order
    if item_type in ("purchase_order", "po", "procurement"):
        amt = float(item.get("amount") or item.get("order_value_inr") or item.get("total_cost_inr") or 0.0)
        return check_purchase_order_rule(amount_inr=amt, details=item)

    # Check 3: Reroute / Route Change
    is_reroute = (
        item_type in ("reroute", "route_change", "emergency_reroute")
        or item.get("is_reroute") is True
        or "reroute" in str(item.get("logistics_status", "")).lower()
    )
    if is_reroute and ("original_cost_inr" in item or "new_cost_inr" in item):
        orig = float(item.get("original_cost_inr", 10000.0))
        new_c = float(item.get("new_cost_inr", item.get("estimated_cost_inr", orig)))
        return check_reroute_rule(original_cost_inr=orig, new_cost_inr=new_c, details=item)

    # Check 4: Stock Rebalancing Transfer (Default for logistics dispatch)
    cost = float(
        item.get("estimated_cost_inr")
        or item.get("amount")
        or item.get("cost_inr")
        or item.get("total_estimated_cost_inr")
        or 0.0
    )
    return check_transfer_rule(amount_inr=cost, details=item)


# ==============================================================================
# 3. FIRESTORE APPROVALS PERSISTENCE (pending / approved / rejected)
# ==============================================================================

def save_approval_item(
    approval_id: str,
    item_type: str,
    details: Dict[str, Any],
    amount: float = 0.0,
    status: str = "pending",
    rule_triggered: str = "",
    reason: str = ""
) -> Dict[str, Any]:
    """
    Saves an approval item to the Firestore 'approvals' collection with status
    'pending', 'approved', or 'rejected'.
    """
    status_clean = status.lower().strip()
    if status_clean not in VALID_STATUSES:
        status_clean = "pending"

    record = {
        "request_id": approval_id,
        "approval_id": approval_id,
        "plan_id": approval_id,
        "id": approval_id,
        "_id": approval_id,
        "type": item_type.upper(),
        "item_type": item_type.lower(),
        "amount": float(amount),
        "status": status_clean,
        "rule_triggered": rule_triggered,
        "reason": reason,
        "details": details,
        "requester_agent": "State Master Orchestrator",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    # Persist to Firestore collection 'approvals'
    set_document("approvals", approval_id, record)

    # Synchronize with in-memory store for instant lookup
    PENDING_APPROVALS[approval_id] = {
        **details,
        "plan_id": approval_id,
        "type": item_type.upper(),
        "approval_status": status_clean.upper(),
        "status": status_clean,
        "estimated_cost_inr": float(amount),
        "amount": float(amount)
    }

    return record


def update_approval_status(
    approval_id: str,
    new_status: str,
    decision_by: str = "District Logistics Officer",
    note: str = ""
) -> Dict[str, Any]:
    """
    Updates the status of an approval item in Firestore 'approvals' collection
    to 'approved' or 'rejected'.
    """
    status_clean = new_status.lower().strip()
    if status_clean not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of: {', '.join(VALID_STATUSES)}")

    existing = get_document("approvals", approval_id) or {}
    updated_record = {
        **existing,
        "request_id": approval_id,
        "approval_id": approval_id,
        "plan_id": approval_id,
        "id": approval_id,
        "_id": approval_id,
        "status": status_clean,
        "decision_by": decision_by,
        "decision_note": note,
        "decision_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    set_document("approvals", approval_id, updated_record)

    if approval_id in PENDING_APPROVALS:
        PENDING_APPROVALS[approval_id]["approval_status"] = status_clean.upper()
        PENDING_APPROVALS[approval_id]["status"] = status_clean

    return updated_record


def get_approval_status(approval_id: str) -> str:
    """
    Retrieves the current approval status ('pending', 'approved', 'rejected') from Firestore.
    """
    doc = get_document("approvals", approval_id)
    if doc and "status" in doc:
        return str(doc["status"]).lower().strip()

    if approval_id in PENDING_APPROVALS:
        return str(PENDING_APPROVALS[approval_id].get("approval_status", "pending")).lower().strip()

    return "unknown"


# ==============================================================================
# 4. ORCHESTRATOR EXECUTION PAUSING & WAITING
# ==============================================================================

def wait_for_approval_resolution(
    approval_id: str,
    timeout_seconds: float = 2.0,
    poll_interval: float = 0.1
) -> Dict[str, Any]:
    """
    Pauses execution and polls Firestore collection 'approvals' until the status
    changes from 'pending' to 'approved' or 'rejected', or timeout expires.

    Returns:
        Dict containing resolved (bool), status ('approved' | 'rejected' | 'pending'),
        and waited_seconds.
    """
    start_time = time.time()

    while True:
        curr_status = get_approval_status(approval_id)
        if curr_status in ("approved", "rejected"):
            return {
                "resolved": True,
                "status": curr_status,
                "waited_seconds": round(time.time() - start_time, 3),
                "message": f"Approval '{approval_id}' resolved with status '{curr_status}'."
            }

        elapsed = time.time() - start_time
        if elapsed >= timeout_seconds:
            return {
                "resolved": False,
                "status": "pending",
                "waited_seconds": round(elapsed, 3),
                "message": f"Execution paused. Approval '{approval_id}' remains pending after {timeout_seconds}s."
            }

        time.sleep(poll_interval)
