# Transit Permit & Statutory Compliance Rules
**Document ID:** POL-TPM-2026-02  
**Authority:** Department of Commercial Taxes & UP Transport Commission  
**Applicability:** Inter-District Freight Movement across Kanpur, Unnao, Agra, and Noida

---

## 1. Statutory Permit Overview
All freight shipments moving commercial hides, crust, components, or finished leather merchandise within Uttar Pradesh must carry digitized state transit documentation prior to vehicle dispatch.

---

## 2. Mandatory Permit Categories

### A. Electronic Way Bill (e-Way Bill)
- **Threshold:** Mandated for every consignment whose invoice value exceeds ₹50,000 INR.
- **Validity Duration:**
  - Up to 100 km (e.g. Kanpur $\leftrightarrow$ Unnao): Valid for 1 calendar day.
  - 100 km to 300 km (e.g. Kanpur $\leftrightarrow$ Agra): Valid for 2 calendar days.
  - Above 300 km (e.g. Kanpur $\leftrightarrow$ Noida): Valid for 3 calendar days.
- **Extension Rule:** In the event of documented highway blockades or carrier mechanical breakdown, the carrier must log an e-Way Bill extension within 8 hours of expiry.

### B. Animal Husbandry & Hide Inspection Certificate
- **Requirement:** Shipments containing raw salted hides or untanned pelts moving outward from Kanpur or Unnao must carry a veterinary fitness clearance certifying zero foot-and-mouth disease (FMD) vector risks.
- **Verification Point:** Banthar Toll Plaza (Unnao) and Shuklaganj Checkpost (Kanpur).

### C. Chromium Sulfate & Chemical Hazmat Transit Endorsement
- **Requirement:** Tanning chemicals, basic chromium sulfate (BCS), and solvent-based lacquers classified under Class 8 (Corrosives) must carry UPPCB Hazmat Transit Clearance.
- **Expressway Routing:** Hazardous chemical tankers are prohibited on the Yamuna Expressway between 22:00 and 05:00 during dense fog season and must use designated arterial routes (`LANE-03-ALT`).

---

## 3. Automated RFID Checkpoint Verification
1. Every commercial freight truck must possess an active FASTag RFID transponder linked to the carrier’s GSTIN.
2. Toll plaza RFID readers automatically scan the vehicle manifest at Agra-Lucknow Expressway Entry (Kanpur Mile 0, Agra Mile 285) and Jewar Toll Plaza (Yamuna Expressway).
3. Missing or mismatched permit numbers trigger automated vehicle impoundment and state transit fines of ₹10,000 INR.

---

## 4. UP State Transit Permit Manifest Template (Form UP-EWAY-01)

```text
================================================================================
                    GOVERNMENT OF UTTAR PRADESH
        DEPARTMENT OF COMMERCIAL TAXES & UP TRANSPORT COMMISSION
             FORM UP-EWAY-01: INTER-DISTRICT TRANSIT PERMIT
================================================================================
Permit ID:          {PERMIT_ID}
Issue Date:         {TIMESTAMP}
Permit Validity:    {VALIDITY_PERIOD}
Status:             {PERMIT_STATUS}

1. CONSIGNMENT & COMMODITY SUMMARY
--------------------------------------------------------------------------------
Origin Cluster:     {ORIGIN_CLUSTER} (Warehouse / Tannery Hub)
Destination:        {DESTINATION_CLUSTER} (Footwear / Production Facility)
Commodity:          {PRODUCT}
Quantity:           {QUANTITY} {UNIT}
Estimated Value:    INR {INVOICE_VALUE}
Statutory e-Way:    {EWAY_REQUIRED} (Mandatory for invoice value > INR 50,000)

2. LOGISTICS ROUTING & CARRIER DISPATCH
--------------------------------------------------------------------------------
Assigned Carrier:   {CARRIER_NAME} (Carrier ID: {CARRIER_ID})
Vehicle Assigned:   {VEHICLE_TYPE}
Corridor Route:     {ROUTE_NAME} (Route ID: {ROUTE_ID})
Transit Distance:   {DISTANCE_KM} km
Estimated Transit:  {ETA_HOURS} hours
Base Toll Charges:  INR {TOLL_INR}
Total Freight Cost: INR {TOTAL_COST_INR}

3. REGULATORY COMPLIANCE & POLICY VERIFICATION
--------------------------------------------------------------------------------
Delivery SLA:       {DELIVERY_SLA_POLICY}
Vet Certificate:    {VET_INSPECTION_STATUS}
Hazmat / Chromium:  {HAZMAT_STATUS}
Emergency Subsidy:  {ODOP_SUBSIDY_STATUS}
Rerouting / Detour: {DETOUR_ADVISORY}
RFID Checkpoint:    VERIFIED (FASTag linked at Expressway Entry)

Authorized By:      STATE MASTER ORCHESTRATOR (TAN-IX System)
Approval Reference: {PLAN_ID}
================================================================================
```

