# TAN-IX REST API Contract & Integration Specification
**Service:** TAN-IX Multi-Agent Supply Chain Engine  
**Version:** `1.3.0`  
**Base URL:** `http://127.0.0.1:8000` (or configured via `API_BASE_URL`)  
**Interactive Docs:** `http://127.0.0.1:8000/docs` (Swagger UI) / `http://127.0.0.1:8000/redoc`

---

## 1. Overview & General Conventions

- **Transport:** Standard HTTP/1.1 with JSON request and response payloads (`Content-Type: application/json`).
- **CORS Support:** Cross-Origin Resource Sharing is enabled for all origins (`allow_origins=["*"]`) with full support for GET, POST, PUT, DELETE, and OPTIONS preflight requests.
- **Timestamps:** Standard UTC ISO-8601 format (`YYYY-MM-DDTHH:MM:SSZ`).
- **Consistent Enums & Status Colors:**
  - **Inventory Health Colors:** `"ok"` (green, surplus or safe balance), `"low"` (amber, near reorder point), `"critical"` (crimson, stockout danger).
  - **Risk Tiers:** `"LOW"`, `"MODERATE"`, `"ELEVATED"`, `"CRITICAL"`.
  - **Network Status:** `"NORMAL"`, `"ELEVATED_RISK"`, `"CRITICAL_ALERT"`.

---

## 2. API Endpoint Directory

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | [`/health`](#get-health) | Service health check and liveness verification |
| `GET` | [`/districts`](#get-districts) | Metadata, roles, and coordinates for all 4 UP leather hubs |
| `GET` | [`/kpis`](#get-kpis) | Executive supply chain performance summary & alert counts |
| `GET` | [`/inventory`](#get-inventory) | All district warehouse balances with `ok`/`low`/`critical` status colors |
| `GET` | [`/inventory/{district}`](#get-inventorydistrict) | Warehouse stock filtered by specific district |
| `POST` | [`/stock-update`](#post-stock-update) | Update physical warehouse inventory balance |
| `GET` | [`/disruptions/active`](#get-disruptionsactive) | Active and monitored disruptions mapped to highway lanes |
| `POST` | [`/disruption`](#post-disruption) | Register a climate, regulatory, or flood incident |
| `GET` | [`/lanes/risk`](#get-lanesrisk) | 0–100 quantitative risk scores across all 14 transit lanes |
| `GET` | [`/shipments`](#get-shipments) | List freight transit manifests with optional filters |
| `GET` | [`/dispatch-schedule`](#get-dispatch-schedule) | Planned & scheduled dispatches with assigned carriers and ETAs |
| `POST` | [`/shipment`](#post-shipment) | Create or register a new freight dispatch order |
| `GET` | [`/approvals`](#get-approvals) | Human-in-the-Loop rebalancing proposals filtered by status |
| `GET` | [`/approval/discord-callback`](#get-approvaldiscord-callback) | Action callback for Discord / UI one-click authorizations |
| `POST` | [`/orchestrator/run`](#post-orchestratorrun) | Trigger autonomous multi-agent reasoning & rebalance cycle |
| `POST` | [`/scenario/trigger`](#post-scenariotrigger) | Fire a demo disruption scenario from the frontend UI |

---

## 3. Endpoint Specifications

### `GET /health`
Verifies backend service availability and connectivity.

**Response `200 OK`:**
```json
{
  "status": "ok",
  "service": "TAN-IX Multi-Agent API",
  "timestamp": "2026-10-06T10:02:24.092632Z"
}
```

---

### `GET /districts`
Returns profile metadata, geographic coordinates, and industrial roles for all 4 Uttar Pradesh leather clusters.

**Response `200 OK`:**
```json
{
  "total": 4,
  "districts": [
    {
      "district_id": "kanpur",
      "name": "Kanpur",
      "cluster_name": "Kanpur Leather Hub",
      "district_admin": "Kanpur Nagar",
      "primary_role": "Heavy Tanning, Saddlery, Industrial Leather (Jajmau)",
      "lat": 26.4499,
      "lon": 80.3319,
      "vulnerabilities": ["Ganges River flood plain", "NGT effluent discharge restrictions"],
      "critical_items": ["Raw Hides", "Crust Leather", "Chromium Tanning Salts"],
      "color_rgb": [220, 53, 69]
    },
    {
      "district_id": "unnao",
      "name": "Unnao",
      "cluster_name": "Unnao Leather Complex",
      "district_admin": "Unnao",
      "primary_role": "Industrial Area Tannery Complex (Wet-Blue & Crust Leather)",
      "lat": 26.5458,
      "lon": 80.4878,
      "vulnerabilities": ["Water treatment capacity", "Monsoon effluent logging"],
      "critical_items": ["Raw Buffalo Hides", "Wet-Blue Leather"],
      "color_rgb": [255, 152, 0]
    },
    {
      "district_id": "agra",
      "name": "Agra",
      "cluster_name": "Agra Footwear Cluster",
      "district_admin": "Agra",
      "primary_role": "Footwear Manufacturing, Shoe Uppers & Soles (Sikandra/Hing ki Mandi)",
      "lat": 27.1767,
      "lon": 78.0081,
      "vulnerabilities": ["Raw material transit delays from Kanpur", "Expressway fog"],
      "critical_items": ["Shoe Uppers", "Leather Soles", "Finished Calf Leather"],
      "color_rgb": [40, 167, 69]
    },
    {
      "district_id": "noida",
      "name": "Noida",
      "cluster_name": "Noida Export Zone",
      "district_admin": "Gautam Buddha Nagar",
      "primary_role": "High-Value Fashion Export, Handbags, Luxury Jackets (Sec 63/65)",
      "lat": 28.5355,
      "lon": 77.3910,
      "vulnerabilities": ["Strict international shipment deadlines"],
      "critical_items": ["Premium Nappa Leather", "Designer Hardware/Zippers"],
      "color_rgb": [33, 150, 243]
    }
  ]
}
```

---

### `GET /kpis`
Delivers high-level operational metrics and health statistics for the command dashboard summary cards.

**Response `200 OK`:**
```json
{
  "stockouts_prevented": 14,
  "cost_saved_inr": 412500.0,
  "active_alerts_count": 10,
  "pending_approvals_count": 2,
  "active_disruptions_count": 9,
  "total_inventory_items": 16,
  "critical_inventory_count": 1,
  "low_inventory_count": 1,
  "total_shipments_tracked": 200,
  "last_updated": "2026-10-06T10:02:24.207140Z"
}
```

---

### `GET /inventory`
Returns all warehouse inventory records across all districts. Includes calculated consumption runways (`days_left`) and standardized UI color flags (`"ok"`, `"low"`, `"critical"`).

**Query Parameters:**
- `district` *(optional, string)*: Filter records by district (e.g. `Agra`).

**Response `200 OK`:**
```json
{
  "total_items": 16,
  "district_filter": null,
  "critical_count": 1,
  "low_count": 1,
  "ok_count": 14,
  "inventory": [
    {
      "inventory_id": "INV-AGR-BEL",
      "district": "Agra",
      "product": "belts",
      "quantity": 180.0,
      "unit": "units",
      "daily_burn_rate": 150.0,
      "reorder_point": 1200.0,
      "safety_stock": 350.0,
      "unit_cost_inr": 380.0,
      "days_left": 1.2,
      "status": "CRITICAL_DEFICIT",
      "status_color": "critical"
    },
    {
      "inventory_id": "INV-KNP-BEL",
      "district": "Kanpur",
      "product": "belts",
      "quantity": 6800.0,
      "unit": "units",
      "daily_burn_rate": 80.0,
      "reorder_point": 1000.0,
      "safety_stock": 300.0,
      "unit_cost_inr": 380.0,
      "days_left": 85.0,
      "status": "SURPLUS",
      "status_color": "ok"
    }
  ]
}
```

---

### `GET /disruptions/active`
Returns all currently active and monitored weather, regulatory, and logistics disruptions, including the mapped highway lanes they impact.

**Response `200 OK`:**
```json
{
  "total": 9,
  "disruptions": [
    {
      "event_id": "EVT-AGR-01",
      "title": "Dense Winter Fog Night Speed Restrictions",
      "location": "Agra (Yamuna Expressway Entry)",
      "type": "EXPRESSWAY_FOG",
      "severity": "HIGH",
      "status": "ACTIVE",
      "description": "Visibility below 40m between Agra Mile 20 and Jewar; commercial freight transit capped at 50 km/h.",
      "impacted_clusters": ["Agra", "Noida"],
      "affected_lanes": ["LANE-11", "LANE-12"]
    },
    {
      "event_id": "EVT-KNP-01",
      "title": "UPPCB & NGT Effluent Inspection Shutdown Notice",
      "location": "Kanpur (Jajmau)",
      "type": "REGULATORY_NGT",
      "severity": "HIGH",
      "status": "ACTIVE",
      "description": "Statutory inspection ordered for 14 tanning units along Jajmau PETP; 48-hour output reduction enforced.",
      "impacted_clusters": ["Kanpur", "Agra"],
      "affected_lanes": ["LANE-03", "LANE-03-ALT", "LANE-04", "LANE-04-ALT"]
    }
  ]
}
```

---

### `GET /lanes/risk`
Evaluates the quantitative 0–100 risk score and operational impact for all 14 freight route lanes in the UP corridor.

**Response `200 OK`:**
```json
{
  "status": "ELEVATED_RISK",
  "total_lanes": 14,
  "critical_lanes_count": 0,
  "elevated_lanes_count": 8,
  "lanes": [
    {
      "lane_id": "LANE-01",
      "route_name": "NH-27 / Ganga Bridge Corridor",
      "origin": "Kanpur",
      "destination": "Unnao",
      "distance_km": 25.0,
      "standard_transit_hours": 0.8,
      "base_toll_inr": 80.0,
      "risk_score": 44.0,
      "risk_level": "MODERATE",
      "status_color": "moderate",
      "is_disrupted": true,
      "shipments_delayed": 6,
      "delay_in_days": 2.0,
      "estimated_cost_inr": 26400.0
    },
    {
      "lane_id": "LANE-03",
      "route_name": "Agra-Lucknow Expressway & NH-19",
      "origin": "Kanpur",
      "destination": "Agra",
      "distance_km": 285.0,
      "standard_transit_hours": 4.5,
      "base_toll_inr": 780.0,
      "risk_score": 56.0,
      "risk_level": "ELEVATED",
      "status_color": "elevated",
      "is_disrupted": true,
      "shipments_delayed": 2,
      "delay_in_days": 2.0,
      "estimated_cost_inr": 8800.0
    },
    {
      "lane_id": "LANE-07",
      "route_name": "Agra-Lucknow Expressway",
      "origin": "Unnao",
      "destination": "Agra",
      "distance_km": 290.0,
      "standard_transit_hours": 4.6,
      "base_toll_inr": 810.0,
      "risk_score": 0.0,
      "risk_level": "LOW",
      "status_color": "ok",
      "is_disrupted": false,
      "shipments_delayed": 0,
      "delay_in_days": 0.0,
      "estimated_cost_inr": 0.0
    }
  ]
}
```

---

### `GET /shipments`
Retrieves inter-cluster freight transit orders.

**Query Parameters:**
- `limit` *(optional, default 50, max 200)*: Maximum number of shipments.
- `status` *(optional, string)*: Filter by transit lifecycle state (`Delivered`, `In Transit`, `Planned`).
- `origin` *(optional, string)*: Filter by origin district name.
- `destination` *(optional, string)*: Filter by destination district name.

**Response `200 OK`:**
```json
{
  "total_matching": 200,
  "returned": 5,
  "shipments": [
    {
      "shipment_id": "SHP-2026-0011",
      "date": "2026-07-01",
      "origin": "Kanpur",
      "destination": "Unnao",
      "carrier": "Yamuna Fast Haulers",
      "route": "NH-27 / Ganga Bridge Corridor",
      "product": "bags",
      "quantity": 1693.0,
      "unit": "units",
      "cost_inr": 1994.0,
      "status": "Delivered",
      "delay_hours": 0.0
    }
  ]
}
```

---

### `GET /dispatch-schedule`
Provides planned, in-transit, and scheduled commercial freight dispatches with assigned vehicle types, ETAs, and routes.

**Response `200 OK`:**
```json
{
  "total_scheduled": 4,
  "schedule": [
    {
      "dispatch_id": "DISP-2026-0891",
      "origin": "Kanpur",
      "destination": "Agra",
      "product": "belts",
      "quantity": 1020.0,
      "unit": "units",
      "carrier": "Ganga Basin Cargo Logistics",
      "vehicle_type": "Multi-Axle Heavy Haulers",
      "route_id": "LANE-03-ALT",
      "route_name": "NH-19 via Etawah & Shikohabad (Alternative)",
      "cost_inr": 8550.0,
      "eta_hours": 6.9,
      "departure_time": "2026-10-06T14:30:00Z",
      "status": "DISPATCHED",
      "urgency": "HIGH"
    }
  ]
}
```

---

### `GET /approvals`
Retrieves pending or historical Human-in-the-Loop decision requests.

**Query Parameters:**
- `status` *(optional, default `"pending"`)*: Filter by `pending`, `approved`, `rejected`, or `all`.

**Response `200 OK`:**
```json
{
  "status_filter": "pending",
  "total": 2,
  "approvals": [
    {
      "plan_id": "PLAN-UP-0001",
      "request_id": "PLAN-UP-0001",
      "type": "STOCK_REBALANCE",
      "origin": "Kanpur",
      "destination": "Agra",
      "product": "belts",
      "quantity": 1020.0,
      "unit": "units",
      "route_name": "NH-19 via Etawah (Alternative)",
      "carrier": "Ganga Basin Cargo Logistics",
      "estimated_cost_inr": 8550.0,
      "status": "PENDING",
      "created_at": "2026-10-06T14:45:00Z",
      "approve_url": "http://127.0.0.1:8000/approval/discord-callback?plan_id=PLAN-UP-0001&action=approve",
      "reject_url": "http://127.0.0.1:8000/approval/discord-callback?plan_id=PLAN-UP-0001&action=reject"
    }
  ]
}
```

---

### `POST /scenario/trigger`
Simulates emergency disruptions directly from the frontend UI or external testing scripts.

**Request Body:**
```json
{
  "scenario_type": "highway_blockade",
  "cluster": "Unnao",
  "description": "Transporters union strike near Unnao Banthar corridor on NH-27",
  "severity": "CRITICAL"
}
```

*Supported `scenario_type` options:*
- `"highway_blockade"`: Simulates a complete highway closure on NH-27 (Kanpur $\leftrightarrow$ Unnao).
- `"demand_spike"`: Simulates an acute demand spike and inventory deficit in Agra.
- `"monsoon_flood"`: Inundates Ganges river basin bridge ramps.
- `"ngt_inspection"`: Simulates a 48-hour environmental inspection notice.
- `"clear"`: Restores all simulated incidents back to baseline.

**Response `200 OK`:**
```json
{
  "success": true,
  "scenario": "highway_blockade",
  "cluster": "Unnao",
  "severity": "CRITICAL",
  "message": "Highway blockade injected on NH-27 near Unnao (LANE-01 & LANE-02 blocked).",
  "injected_event": {
    "id": "DISRUPT-001",
    "event_id": "DISRUPT-001",
    "cluster": "Unnao",
    "severity": "CRITICAL",
    "status": "ACTIVE"
  },
  "active_disruptions_count": 10,
  "lane_01_risk_score": 84.0,
  "system_threat_level": "CRITICAL_ALERT"
}
```

---

## 4. Error Responses

All error responses conform to FastAPI standard HTTPException structure:

```json
{
  "detail": "District 'Lucknow' not recognized. Available districts: Kanpur, Unnao, Agra, Noida"
}
```

- **`400 Bad Request`**: Invalid input parameters or unsupported scenario trigger types.
- **`404 Not Found`**: Target district or document not found.
- **`422 Unprocessable Entity`**: Pydantic schema validation failure (missing required fields or invalid types).
- **`500 Internal Server Error`**: Unhandled exception during database write or agent execution.
