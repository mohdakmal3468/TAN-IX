# 📋 TAN-IX Data Schemas Specification
### State-Level Multi-Agent Supply Chain Risk & Inventory Manager for UP Leather Goods

This document formalizes the 5 core data models powering the multi-agent system, databases (**Firestore**, **BigQuery**), and REST API endpoints.

---

## 1. Inventory Record Schema

Tracks real-time stock levels, consumption rates, and replenishment thresholds for leather goods across district warehouses (**Kanpur**, **Unnao**, **Agra**, **Noida**).

### Field Definitions:
| Field | Type | Description |
| :--- | :--- | :--- |
| `inventory_id` | `string` | Unique identifier for the inventory record (e.g. `INV-KNP-001`). |
| `district` | `string` | District or cluster name (`Kanpur`, `Unnao`, `Agra`, `Noida`). |
| `product` | `string` | Leather commodity name (`Raw Hides`, `Wet-Blue Leather`, `Finished Cowhide`, etc.). |
| `quantity` | `number` | Current live physical inventory balance. |
| `unit` | `string` | Unit of measure (`sq_ft`, `kg`, `pairs`, `garments`). |
| `daily_burn_rate` | `number` | Expected daily consumption or production demand. |
| `reorder_point` | `number` | Minimum threshold triggering automated replenishment. |
| `safety_stock` | `number` | Buffer stock reserved for emergency disruptions. |
| `unit_cost_inr` | `number` | Cost per unit in Indian Rupees (INR). |
| `status` | `string` | Inventory health state (`NORMAL`, `LOW_STOCK`, `CRITICAL_DEFICIT`, `SURPLUS`). |
| `last_updated` | `string` | ISO 8601 timestamp of last physical or database update. |

### JSON Example:
```json
{
  "inventory_id": "INV-AGR-003",
  "district": "Agra",
  "product": "Finished Calf Leather",
  "quantity": 1450,
  "unit": "sq_ft",
  "daily_burn_rate": 350.0,
  "reorder_point": 3000,
  "safety_stock": 1000,
  "unit_cost_inr": 380.0,
  "status": "CRITICAL_DEFICIT",
  "last_updated": "2026-10-06T12:00:00Z"
}
```

---

## 2. Hub Profile Schema

Defines physical facility parameters, coordinates, industrial roles, and regional vulnerabilities for each cluster warehouse.

### Field Definitions:
| Field | Type | Description |
| :--- | :--- | :--- |
| `hub_id` | `string` | Facility identifier (e.g. `HUB-KNP-JAJMAU`). |
| `name` | `string` | Full descriptive facility title. |
| `district` | `string` | Governing administrative district. |
| `location` | `string` | Industrial area address. |
| `latitude` | `number` | Geographic latitude coordinate for map plotting. |
| `longitude` | `number` | Geographic longitude coordinate for map plotting. |
| `primary_role` | `string` | Industrial specialty (tanning, processing, footwear, export). |
| `capacity_sqft` | `number` | Total covered storage floor space in square feet. |
| `operating_status` | `string` | Facility operational condition (`OPERATIONAL`, `DEGRADED`, `HALTED`). |
| `active_vulnerabilities` | `array[string]` | Known environmental and infrastructure risk factors. |
| `contact_email` | `string` | Warehouse manager communication address. |
| `contact_phone` | `string` | Emergency operational contact telephone number. |

### JSON Example:
```json
{
  "hub_id": "HUB-KNP-JAJMAU",
  "name": "Kanpur Central Leather Logistics Park",
  "district": "Kanpur",
  "location": "Jajmau Industrial Area, Kanpur Nagar, UP",
  "latitude": 26.4499,
  "longitude": 80.3319,
  "primary_role": "Heavy Tanning, Saddlery, Industrial Leather",
  "capacity_sqft": 50000,
  "operating_status": "OPERATIONAL",
  "active_vulnerabilities": [
    "Ganges river flood plain",
    "NGT effluent discharge restrictions",
    "CETP overflow risk"
  ],
  "contact_email": "ops.kanpur@tanix.up.gov.in",
  "contact_phone": "+91-512-2589001"
}
```

---

## 3. Shipment Schema

Models freight transit orders between UP industrial clusters along the expressway network.

### Field Definitions:
| Field | Type | Description |
| :--- | :--- | :--- |
| `shipment_id` | `string` | Formal tracking manifest identifier (e.g. `SHP-UP-2026-0891`). |
| `origin` | `string` | Source cluster/hub name (`Kanpur`, `Unnao`, etc.). |
| `destination` | `string` | Recipient cluster/hub name (`Agra`, `Noida`, etc.). |
| `carrier` | `string` | Commercial freight company name. |
| `route` | `string` | Highway or expressway corridor used. |
| `cost` | `number` | Total estimated or actual freight invoice cost in INR. |
| `status` | `string` | Current delivery status (`PLANNED`, `DISPATCHED`, `IN_TRANSIT`, `DELIVERED`, `DELAYED`, `CANCELLED`). |
| `product` | `string` | Commodity loaded on vehicle. |
| `quantity` | `number` | Volume of commodity transported. |
| `unit` | `string` | Unit of measure for the cargo. |
| `vehicle_type` | `string` | Commercial transport vehicle model/capacity. |
| `planned_transit_hours` | `number` | Scheduled duration in hours. |
| `actual_transit_hours` | `number` | Actual duration in hours (optional, updated post-delivery). |
| `departure_time` | `string` | ISO 8601 timestamp of dispatch. |

### JSON Example:
```json
{
  "shipment_id": "SHP-UP-2026-0891",
  "origin": "Kanpur",
  "destination": "Agra",
  "carrier": "UP State Freight Express",
  "route": "Agra-Lucknow Expressway & NH-19",
  "cost": 19323.0,
  "status": "DISPATCHED",
  "product": "Finished Cowhide",
  "quantity": 1550,
  "unit": "sq_ft",
  "vehicle_type": "Eicher Pro (9 Ton)",
  "planned_transit_hours": 4.5,
  "actual_transit_hours": null,
  "departure_time": "2026-10-06T14:30:00Z"
}
```

---

## 4. Disruption Event Schema

Captures sudden climate, regulatory, or infrastructure events that impair leather supply operations.

### Field Definitions:
| Field | Type | Description |
| :--- | :--- | :--- |
| `event_id` | `string` | Unique disturbance event code (e.g. `EVT-2026-004`). |
| `location` | `string` | Affected city, district, or highway corridor. |
| `type` | `string` | Disruption category (`WEATHER_FLOOD`, `REGULATORY_NGT`, `EXPRESSWAY_FOG`, `LABOR_STRIKE`, `RAW_MATERIAL_SPIKE`). |
| `severity` | `string` | Disruption intensity (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). |
| `timestamp` | `string` | ISO 8601 moment when the disruption was reported or detected. |
| `title` | `string` | Brief incident summary headline. |
| `description` | `string` | Complete narrative of the event. |
| `impacted_clusters` | `array[string]` | List of clusters suffering direct or indirect output cuts. |
| `status` | `string` | Life-cycle condition (`ACTIVE`, `MONITORING`, `RESOLVED`). |

### JSON Example:
```json
{
  "event_id": "EVT-2026-004",
  "location": "Kanpur",
  "type": "REGULATORY_NGT",
  "severity": "HIGH",
  "timestamp": "2026-10-06T11:45:00Z",
  "title": "UPPCB & NGT Compliance Notice on Jajmau CETP",
  "description": "Due to effluent discharge limit violations, UPPCB ordered temporary 48-hour production cutbacks for 12 Jajmau tanning units.",
  "impacted_clusters": [
    "Kanpur",
    "Agra"
  ],
  "status": "ACTIVE"
}
```

---

## 5. Approval Request Schema

Encapsulates human-in-the-loop governance for emergency inter-cluster transfers dispatched to Discord or the supervisor cockpit.

### Field Definitions:
| Field | Type | Description |
| :--- | :--- | :--- |
| `request_id` | `string` | Governance request code (e.g. `APR-UP-2026-0012`). |
| `type` | `string` | Nature of action (`STOCK_REBALANCE`, `EMERGENCY_REROUTE`, `OVERTIME_PRODUCTION`). |
| `details` | `object` | Structured dictionary containing action origin, destination, cargo, and justification. |
| `status` | `string` | Authorization state (`PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`). |
| `amount` | `number` | Financial liability or logistics expenditure in INR. |
| `requester_agent` | `string` | Autonomous agent proposing the transaction (`State Master Orchestrator`). |
| `created_at` | `string` | ISO 8601 generation timestamp. |
| `decision_by` | `string` | Identity of the human operator authorizing or rejecting (null if pending). |
| `decision_at` | `string` | ISO 8601 resolution timestamp (null if pending). |

### JSON Example:
```json
{
  "request_id": "APR-UP-2026-0012",
  "type": "STOCK_REBALANCE",
  "details": {
    "origin": "Kanpur",
    "destination": "Agra",
    "product": "Finished Cowhide",
    "quantity": 1550,
    "unit": "sq_ft",
    "route": "Agra-Lucknow Expressway",
    "risk_justification": "Replenish critical deficit in Agra ahead of potential Kanpur CETP shutdown."
  },
  "status": "PENDING",
  "amount": 19323.0,
  "requester_agent": "State Master Orchestrator",
  "created_at": "2026-10-06T14:00:00Z",
  "decision_by": null,
  "decision_at": null
}
```
