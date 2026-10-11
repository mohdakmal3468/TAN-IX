# Highway Blockade, Flood & Weather Hazard SOP
**Document ID:** POL-BLK-2026-06  
**Authority:** Uttar Pradesh State Disaster Management Authority (UPSDMA) & UPEIDA  
**Applicability:** Expressway Lanes LANE-01 through LANE-12

---

## 1. Incident Classification & Thresholds

| Disruption Type | Trigger Condition | Affected Corridors | Mandatory Action |
| :--- | :--- | :--- | :--- |
| **Ganges River Inundation** | Water level at Kanpur Barrage exceeds 114.0 meters; access ramps flooded. | `LANE-01`, `LANE-02` (NH-27 / Ganga Bridge) | Total transit suspension. Halt dispatches at Jajmau & Banthar hubs. |
| **Dense Winter Fog** | Visibility drops below 50 meters between 21:00 and 06:00. | `LANE-11`, `LANE-12` (Yamuna Expressway) | Enforce 50 km/h speed limit cap. Pilot vehicle convoy mandatory. |
| **Highway Labor / Toll Strike** | Transporter protest halts freight lanes for > 60 minutes. | `LANE-01`, `LANE-03`, `LANE-04` | Execute automated detour via national highway alternative lanes. |

---

## 2. Autonomous Rerouting Protocols

### A. Agra-Lucknow Expressway Blockade Protocol (`LANE-03`)
If `LANE-03` (Agra-Lucknow Expressway) is obstructed by agricultural protests, multi-vehicle pileups, or structural bridge repairs:
1. The **Regional Risk Agent** immediately updates the lane risk score to $\ge 75.0$ (`CRITICAL`).
2. The **Intra-State Logistics Agent** is mandated to divert all pending and newly dispatched cargo to **`LANE-03-ALT`** (*National Highway NH-19 via Etawah and Shikohabad*).
3. The carrier must be compensated for the 275 km arterial transit with adjusted toll rates (₹340 base toll vs ₹780 expressway toll).

### B. Ganges River Flood Emergency Protocol (`LANE-01` / `LANE-02`)
1. When water levels breach the Shuklaganj or Jajmau access ramps, all transit between Kanpur and Unnao on NH-27 is prohibited.
2. Inter-cluster raw material transfers must be temporarily stored in secondary flood-safe warehouses in Unnao Industrial Area until water recedes below 113.5 meters.

---

## 3. Communication & Stakeholder Notification
1. Downstream manufacturing clusters (Agra footwear assembly lines and Noida export units) must receive an automated digital dispatch advisory within **15 minutes** of any declared corridor blockade.
2. Carrier fleet managers must acknowledge the rerouting directive via the AgentHide dispatch API before departing checkposts.
