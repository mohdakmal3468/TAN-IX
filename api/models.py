"""
api/models.py
-------------
Pydantic v2 data models for AgentHide:
1. InventoryRecord
2. HubProfile
3. Shipment
4. DisruptionEvent
5. ApprovalRequest
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ==============================================================================
# Enumerations for Categorical Fields
# ==============================================================================

class InventoryStatus(str, Enum):
    NORMAL = "NORMAL"
    LOW_STOCK = "LOW_STOCK"
    CRITICAL_DEFICIT = "CRITICAL_DEFICIT"
    SURPLUS = "SURPLUS"


class HubStatus(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    DEGRADED = "DEGRADED"
    HALTED = "HALTED"


class ShipmentStatus(str, Enum):
    PLANNED = "PLANNED"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"


class DisruptionType(str, Enum):
    WEATHER_FLOOD = "WEATHER_FLOOD"
    REGULATORY_NGT = "REGULATORY_NGT"
    EXPRESSWAY_FOG = "EXPRESSWAY_FOG"
    LABOR_STRIKE = "LABOR_STRIKE"
    RAW_MATERIAL_SPIKE = "RAW_MATERIAL_SPIKE"


class DisruptionSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DisruptionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"


class ApprovalType(str, Enum):
    STOCK_REBALANCE = "STOCK_REBALANCE"
    EMERGENCY_REROUTE = "EMERGENCY_REROUTE"
    OVERTIME_PRODUCTION = "OVERTIME_PRODUCTION"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# ==============================================================================
# 1. Inventory Record Schema
# ==============================================================================

class InventoryRecord(BaseModel):
    """
    Live warehouse stock balance, threshold, and burn rate model.
    """
    inventory_id: str = Field(..., description="Unique inventory item identifier", example="INV-AGR-003")
    district: str = Field(..., description="District or cluster name (Kanpur, Unnao, Agra, Noida)", example="Agra")
    product: str = Field(..., description="Name of the leather good or raw material", example="Finished Calf Leather")
    quantity: float = Field(..., ge=0, description="Current live stock on hand", example=1450.0)
    unit: str = Field(..., description="Measurement unit (sq_ft, kg, pairs, garments)", example="sq_ft")
    daily_burn_rate: float = Field(..., ge=0, description="Expected daily consumption volume", example=350.0)
    reorder_point: float = Field(..., ge=0, description="Minimum stock level triggering replenishment", example=3000.0)
    safety_stock: Optional[float] = Field(0.0, ge=0, description="Emergency buffer reserve", example=1000.0)
    unit_cost_inr: Optional[float] = Field(0.0, ge=0, description="Unit cost in INR", example=380.0)
    status: InventoryStatus = Field(default=InventoryStatus.NORMAL, description="Stock health status")
    last_updated: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Last update timestamp")


# ==============================================================================
# 2. Hub Profile Schema
# ==============================================================================

class HubProfile(BaseModel):
    """
    Cluster warehouse facility profile, location, and regional risk factors.
    """
    hub_id: str = Field(..., description="Unique facility identifier", example="HUB-KNP-JAJMAU")
    name: str = Field(..., description="Descriptive facility title", example="Kanpur Central Leather Logistics Park")
    district: str = Field(..., description="Administrative district", example="Kanpur")
    location: str = Field(..., description="Physical industrial area address", example="Jajmau Industrial Area, Kanpur")
    latitude: float = Field(..., description="GPS Latitude coordinate", example=26.4499)
    longitude: float = Field(..., description="GPS Longitude coordinate", example=80.3319)
    primary_role: str = Field(..., description="Industrial specialty", example="Heavy Tanning, Saddlery, Industrial Leather")
    capacity_sqft: float = Field(..., ge=0, description="Total storage capacity in sq ft", example=50000.0)
    operating_status: HubStatus = Field(default=HubStatus.OPERATIONAL, description="Operational condition")
    active_vulnerabilities: List[str] = Field(default_factory=list, description="Known environmental and logistics risks")
    contact_email: Optional[str] = Field(None, description="Manager email address")
    contact_phone: Optional[str] = Field(None, description="Emergency contact phone number")


# ==============================================================================
# 3. Shipment Schema
# ==============================================================================

class Shipment(BaseModel):
    """
    Inter-cluster freight transit order along UP expressways.
    """
    shipment_id: str = Field(..., description="Unique shipment manifest code", example="SHP-UP-2026-0891")
    origin: str = Field(..., description="Origin cluster/hub", example="Kanpur")
    destination: str = Field(..., description="Destination cluster/hub", example="Agra")
    carrier: str = Field(..., description="Freight carrier or fleet operator", example="UP State Freight Express")
    route: str = Field(..., description="Expressway or highway corridor", example="Agra-Lucknow Expressway & NH-19")
    cost: float = Field(..., ge=0, description="Total transportation cost in INR", example=19323.0)
    status: ShipmentStatus = Field(default=ShipmentStatus.PLANNED, description="Transit lifecycle status")
    product: str = Field(..., description="Commodity loaded on carrier", example="Finished Cowhide")
    quantity: float = Field(..., gt=0, description="Quantity shipped", example=1550.0)
    unit: str = Field(..., description="Unit of measurement", example="sq_ft")
    vehicle_type: Optional[str] = Field("Eicher Pro (9 Ton)", description="Vehicle classification")
    planned_transit_hours: float = Field(..., gt=0, description="Scheduled duration in hours", example=4.5)
    actual_transit_hours: Optional[float] = Field(None, description="Actual recorded duration in hours")
    departure_time: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Departure timestamp")


# ==============================================================================
# 4. Disruption Event Schema
# ==============================================================================

class DisruptionEvent(BaseModel):
    """
    Environmental, flood, or regulatory shock event.
    """
    event_id: str = Field(..., description="Incident tracking code", example="EVT-2026-004")
    location: str = Field(..., description="Affected cluster or corridor", example="Kanpur")
    type: DisruptionType = Field(..., description="Incident category")
    severity: DisruptionSeverity = Field(..., description="Impact severity level")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Detection timestamp")
    title: str = Field(..., description="Brief headline of incident", example="UPPCB & NGT Compliance Notice on Jajmau CETP")
    description: str = Field(..., description="Detailed narrative of disruption", example="Temporary 48-hour production curtailment ordered.")
    impacted_clusters: List[str] = Field(default_factory=list, description="Downstream clusters impacted", example=["Kanpur", "Agra"])
    status: DisruptionStatus = Field(default=DisruptionStatus.ACTIVE, description="Incident tracking state")


# ==============================================================================
# 5. Approval Request Schema
# ==============================================================================

class ApprovalRequest(BaseModel):
    """
    Human-in-the-Loop decision request for emergency stock rebalancing.
    """
    request_id: str = Field(..., description="Authorization request identifier", example="APR-UP-2026-0012")
    type: ApprovalType = Field(default=ApprovalType.STOCK_REBALANCE, description="Type of governance request")
    details: Dict[str, Any] = Field(..., description="Detailed cargo, origin, destination, and risk context")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING, description="Human authorization state")
    amount: float = Field(..., ge=0, description="Financial expenditure or logistics cost in INR", example=19323.0)
    requester_agent: str = Field(default="State Master Orchestrator", description="Agent issuing the proposal")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")
    decision_by: Optional[str] = Field(None, description="Supervisor identity authorizing/rejecting")
    decision_at: Optional[datetime] = Field(None, description="Authorization timestamp")


# ==============================================================================
# 6. Scenario Simulation Trigger Schema
# ==============================================================================

class ScenarioTriggerRequest(BaseModel):
    """
    Demo scenario simulation trigger from UI.
    """
    scenario_type: str = Field(
        ...,
        description="Type of emergency scenario: highway_blockade, demand_spike, monsoon_flood, ngt_inspection, clear",
        example="highway_blockade"
    )
    cluster: Optional[str] = Field(default="Unnao", description="Target district cluster", example="Unnao")
    description: Optional[str] = Field(None, description="Optional incident narrative details")
    severity: Optional[str] = Field(default="CRITICAL", description="Disruption severity level: LOW, MEDIUM, HIGH, CRITICAL")
