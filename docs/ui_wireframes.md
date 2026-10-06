# TAN-IX UI Wireframes & Layout Specification
**Project:** State-Level Multi-Agent Supply Chain Risk & Inventory Manager for Leather Goods (TAN-IX)  
**Platform:** Streamlit (Python) / Modular Frontend Architecture  
**Corridors:** Kanpur $\leftrightarrow$ Unnao $\leftrightarrow$ Agra $\leftrightarrow$ Noida

---

## 1. Global Navigation & Layout Architecture

The application layout utilizes a dark glassmorphic theme with a sticky top command bar and a multi-tab view:

```
+--------------------------------------------------------------------------------------------------------+
|  🛡️ TAN-IX: UP LEATHER LOGISTICS COMMAND CENTER    [API: ONLINE]  [STATUS: CRITICAL_ALERT 🔴]  [⚙️ SIM]  |
+--------------------------------------------------------------------------------------------------------+
|  [Tab 1: 🌐 3D Corridor Map]  [Tab 2: 📦 Hub Inventory]  [Tab 3: ⚠️ Risk Scoring]  [Tab 4: 🤖 Agent Feed] |
+--------------------------------------------------------------------------------------------------------+
```

---

## 2. Wireframe 1: 3D Geographic Corridor Map & Disruption Radar
**Target File:** `dashboard/frontend/pages/live_map.py`

```
+--------------------------------------------------------------------------------------------------------+
| 3D CORRIDOR VISUALIZATION & LIVE INCIDENT RADAR                                                         |
|                                                                                                        |
| +---------------------------------------------------+  +---------------------------------------------+ |
| |                                                   |  | ACTIVE DISRUPTIONS & CLOSURES               | |
| |                     [Noida Hub]                   |  |---------------------------------------------| |
| |                        /                          |  | 🔴 EVT-UNO-04: Transporter Strike on NH-27  | |
| |           (LANE-11)   / (LANE-09)                 |  |    Location: Unnao Banthar Junction         | |
| |                      /                            |  |    Impact: LANE-01 & LANE-02 Blocked        | |
| |               [Agra Hub]                          |  |    Score: 84.0/100 | Delay: 3.5 Days        | |
| |                   \                               |  |---------------------------------------------| |
| |         (LANE-03)  \                              |  | 🟠 EVT-AGR-01: Winter Fog Visibility <40m  | |
| |                     \                             |  |    Location: Yamuna Expressway              | |
| |            [Unnao]-----[Kanpur Hub]               |  |    Impact: LANE-11 & LANE-12 Slowed         | |
| |                    (LANE-01: BLOCKED)             |  |    Score: 66.0/100 | Speed Cap: 50 km/h     | |
| +---------------------------------------------------+  +---------------------------------------------+ |
|                                                                                                        |
| CLUSTER HEALTH METRICS:                                                                                |
| +------------------+ +------------------+ +------------------+ +-------------------------------------+ |
| | Kanpur (Tannery) | | Unnao (Complex)  | | Agra (Footwear)  | | Noida (Export Apparel)              | |
| | Stock: 14,200 sqft| | Stock: 8,400 sqft| | Belts: 180 (DEFICIT| | Stock: 6,800 garments             | |
| | Status: ELEVATED | | Status: BLOCKED  | | Status: LOW_STOCK| | Status: OPERATIONAL                 | |
| +------------------+ +------------------+ +------------------+ +-------------------------------------+ |
+--------------------------------------------------------------------------------------------------------+
```

---

## 3. Wireframe 2: Warehouse Inventory & Reorder Tracker
**Target File:** `dashboard/frontend/pages/inventory.py`

```
+--------------------------------------------------------------------------------------------------------+
| DISTRICT WAREHOUSE STOCK BALANCES & CONSUMPTION RUNWAY                                                 |
|                                                                                                        |
| FILTER BY DISTRICT: [ Agra (Footwear Cluster) ▼ ]    PRODUCT: [ Belts ▼ ]                             |
|                                                                                                        |
| +------------------------+ +------------------------+ +------------------------+ +-------------------+ |
| | Current Stock          | | Minimum Safety Stock   | | Daily Consumption      | | Days Runway Left  | |
| | 180 units              | | 1,200 units            | | 150 units/day          | | 1.2 Days 🔴       | |
| +------------------------+ +------------------------+ +------------------------+ +-------------------+ |
|                                                                                                        |
| STOCK REPLENISHMENT STATUS:                                                                            |
| [====================================                                                  ] 15% of Target |
|                                                                                                        |
| PROPOSED REBALANCING TRANSFERS (Autonomous Inventory Agent):                                           |
| +----------------------------------------------------------------------------------------------------+ |
| | DONOR CLUSTER: Kanpur Hub (Surplus: +1,020 units available)                                        | |
| | RECIPIENT:     Agra Manufacturing Facility                                                         | |
| | COMMODITY:     Leather Belts (Finished)                                                            | |
| | QUANTITY:      1,020 units                                                                         | |
| | URGENCY:       CRITICAL (Stockout imminent within 28 hours)                                        | |
| +----------------------------------------------------------------------------------------------------+ |
+--------------------------------------------------------------------------------------------------------+
```

---

## 4. Wireframe 3: Highway Corridor Risk Scoring & Demurrage Matrix
**Target File:** `dashboard/frontend/pages/risk_analytics.py`

```
+--------------------------------------------------------------------------------------------------------+
| HIGHWAY CORRIDOR QUANTITATIVE RISK SCORING (0 - 100)                                                   |
|                                                                                                        |
| +----------------------------------------------------------------------------------------------------+ |
| | Lane ID     | Corridor Name                     | Endpoints     | Score | Status     | Impact Days | |
| |-------------|-----------------------------------|---------------|-------|------------|-------------| |
| | LANE-01     | NH-27 / Ganga Bridge Corridor     | Kanpur->Unnao | 84.0  | 🔴 CRITICAL| 3.5 Days    | |
| | LANE-02     | NH-27 / Ganga Bridge Corridor     | Unnao->Kanpur | 82.0  | 🔴 CRITICAL| 3.5 Days    | |
| | LANE-03     | Agra-Lucknow Expressway & NH-19   | Kanpur->Agra  | 56.0  | 🟠 ELEVATED| 2.0 Days    | |
| | LANE-03-ALT | NH-19 via Etawah (Arterial Fallback| Kanpur->Agra | 56.0  | 🟠 ELEVATED| 2.0 Days    | |
| | LANE-07     | Agra-Lucknow Expressway           | Unnao->Agra   |  0.0  | 🟢 NORMAL  | 0.0 Days    | |
| | LANE-11     | Yamuna Expressway                 | Agra->Noida   | 66.0  | 🟠 ELEVATED| 2.0 Days    | |
| +----------------------------------------------------------------------------------------------------+ |
|                                                                                                        |
| DEMURRAGE & HOLDING IMPACT SUMMARY:                                                                    |
| - Total Shipments Delayed: 57 Freight Trucks                                                           |
| - Maximum Transit Delay:   3.5 Days                                                                    |
| - Est. Financial Demurrage: ₹2,76,100.00 INR                                                          |
|                                                                                                        |
| ACTIONABLE RECOMMENDATION:                                                                             |
| Primary expressway route LANE-03 is constrained; dispatch cargo via fallback lane LANE-03-ALT.        |
+--------------------------------------------------------------------------------------------------------+
```

---

## 5. Wireframe 4: Multi-Agent Deliberation & Discord HITL Console
**Target File:** `dashboard/frontend/pages/orchestrator_feed.py`

```
+--------------------------------------------------------------------------------------------------------+
| STATE MASTER ORCHESTRATOR & HUMAN-IN-THE-LOOP (HITL) CONSOLE                                           |
|                                                                                                        |
| LIVE AGENT DELIBERATION STREAM:                                                                        |
| [14:45] 📦 Inventory Agent:   "Alert: Agra belts at 180 units. Requested transfer of 1,020 belts."    |
| [14:46] ⚠️ Risk Agent:        "Warning: NH-27 Banthar corridor score is 84.0 (CRITICAL). Detour req."  |
| [14:47] 🚚 Logistics Agent:   "Selected LANE-03-ALT (NH-19 Etawah). Carrier: Ganga Basin Cargo."      |
| [14:48] 👑 Master Orchestrator:"Constructed rebalancing plan PLAN-UP-0001. Est. Cost: ₹8,550.00."      |
|                                                                                                        |
| DISCORD DISPATCH CARD PREVIEW:                                                                         |
| +----------------------------------------------------------------------------------------------------+ |
| | 🔔 TAN-IX URGENT APPROVAL REQUIRED                                                                 | |
| | Plan ID: PLAN-UP-0001                                                                              | |
| | Action: Emergency Transfer 1,020 Belts (Kanpur -> Agra)                                             | |
| | Route: NH-19 via Etawah (LANE-03-ALT) | Carrier: Ganga Basin Cargo                                  | |
| | Estimated Cost: INR 8,550.00 | ETA: 6.9 Hours                                                      | |
| |                                                                                                    | |
| | [ ✅ APPROVE DISPATCH (HTTP 200) ]           [ ❌ REJECT / HOLD ]                                  | |
| +----------------------------------------------------------------------------------------------------+ |
+--------------------------------------------------------------------------------------------------------+
```

---

## 6. Frontend File & Folder Directory Structure

```
dashboard/
├── __init__.py
├── app.py                      # Main Streamlit entrance
├── config.py                   # API_BASE_URL, endpoints & theme palette
└── frontend/
    ├── __init__.py
    ├── pages/                  # Modular view scripts
    │   ├── __init__.py
    │   ├── live_map.py
    │   ├── inventory.py
    │   ├── risk_analytics.py
    │   └── orchestrator_feed.py
    ├── components/             # Reusable UI widgets
    │   ├── __init__.py
    │   ├── cards.py            # KPI cards & risk badges
    │   └── tables.py           # Styled DataFrames
    ├── utils/                  # Network & helper routines
    │   ├── __init__.py
    │   └── api_client.py       # FastAPI HTTP client
    └── assets/                 # Static branding & SVGs
        └── README.md
```
