# Financial Delegation & Human Approval Limits
**Document ID:** POL-APL-2026-04  
**Authority:** State Supply Chain Oversight Committee & Directorate of Handlooms and Textiles  
**Applicability:** Automated Multi-Agent Logistics Approvals

---

## 1. Governance Architecture
To balance autonomous operational speed with fiscal governance, AgentHide enforces a strict 3-tiered Delegation of Financial Powers (DoFP) model for freight dispatches and emergency stock rebalancing.

---

## 2. Authorization Threshold Matrix

| Authority Tier | Expenditure Range (INR) | Authorizer / Approver | Governance Workflow |
| :--- | :---: | :--- | :--- |
| **Tier 1: Autonomous** | **$\le$ ₹10,000.00** | **State Master Orchestrator (AI)** | Fully autonomous dispatch. Logged immediately to Firestore audit ledger with zero human latency. |
| **Tier 2: Supervisory** | **₹10,001.00 – ₹50,000.00** | **District Logistics Officer / Supervisor** | Real-time **Human-in-the-Loop (HITL)** approval. Dispatched via interactive Discord webhook card and Dashboard modal. |
| **Tier 3: Executive** | **> ₹50,000.00** | **State Directorate / Principal Secretary** | Dual-key executive sign-off. Requires digital authorization from State Control Center. |

---

## 3. Human-in-the-Loop (HITL) Workflow Rules
1. **Interactive Dispatch:** For all Tier 2 transfer requests, the State Master Orchestrator formats a rich Discord embed card containing:
   - Origin & destination clusters.
   - Commodity and quantity being rebalanced.
   - Proposed commercial carrier and vehicle classification.
   - Estimated transit cost and expressway toll charges.
   - One-click `[Approve]` and `[Reject]` action URLs (`/approval/discord-callback`).
2. **Escalation Window:**
   - Standard decision window: 120 minutes.
   - If stock runway is under 12 hours (imminent plant stoppage) and no human action is logged within 45 minutes, an automated SMS/voice notification escalates the request to the Regional Director.
3. **Audit Trail:** Every approval or rejection is permanently stamped in Firestore collection `approvals` with approver identity, IP, and timestamp.
