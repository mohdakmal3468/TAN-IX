# 📋 Project Scope: TAN-IX
### State-Level Multi-Agent Supply Chain Risk & Inventory Manager for UP Leather Goods

---

## 🎯 1. The Problem (In 2 Simple Sentences)
> Shoe and leather factories in Uttar Pradesh suffer sudden production halts when monsoon floods or National Green Tribunal (NGT) environmental shutdowns hit upstream tanneries in Kanpur and Unnao, cutting off leather supplies to Agra. Because inventory tracking is currently fragmented across manual spreadsheets and phone calls, supply chain managers cannot predict shortages or reroute freight fast enough to stop expensive factory downtime.

---

## 📍 2. Geographic Coverage
* **Version 1 (Core Capstone Scope):**
  * **Kanpur (Jajmau):** Heavy tanning, saddlery, and finished cowhide (upstream supplier).
  * **Unnao (Banthar):** Raw hide soaking, wet-blue leather, and vegetable tanning extracts (buffer hub).
  * **Agra (Sikandra & Hing Ki Mandi):** Footwear manufacturing, shoe uppers, and leather soles (downstream consumer).
* **Version 2 (Future / Stretch Scope):**
  * **Noida / Greater Noida (Sector 63/65):** Luxury fashion export garments, designer bags, and air-cargo connections (added in next phase).

---

## ✅ 3. Must-Have Feature List (V1 Deliverables)
1. **Live Warehouse Stock Tracking:** Real-time visibility into leather inventory, safety thresholds, and critical shortages across Kanpur, Unnao, and Agra.
2. **Regional Risk Monitoring & Simulation:** Autonomous detection of Ganges flood levels and NGT effluent shutdown notices, with one-click emergency simulation buttons for demo presentations.
3. **Expressway Transit & Cost Calculator:** Accurate route distance, transit time, and freight/toll calculations along the **Agra-Lucknow Expressway** and **NH-19**.
4. **4-Agent Collaborative Deliberation:** Specialist agents (Inventory, Risk, Logistics) orchestrated by a State Master Agent using Gemini reasoning to formulate proactive rebalance plans.
5. **Human-in-the-Loop (HITL) Discord Authorization:** High-priority transfer proposal cards sent to Discord/webhooks with one-click `Approve` / `Reject` links before live stock is committed.
6. **Interactive Streamlit Dashboard:** Visual map of the UP leather corridor, stock level progress bars, agent conversation logs, and one-click crisis injectors.

---

## 🚫 4. Out-of-Scope (What We Are NOT Building)
To ensure successful completion within your capstone deadline, the following items are intentionally excluded:
* **No Real-Time Vehicle GPS Hardware:** No physical IoT GPS tracking on trucks; transit times are simulated using real expressway distances and speed limits.
* **No Real Banking or Payment Gateways:** Freight charges and ODOP subsidies are calculated for decision support, but no actual money/UPI is transferred.
* **No Enterprise Multi-Tenant Authentication:** No complex user sign-up/login/passwords; the system runs as a centralized state supervisor cockpit.
* **No Hardware Barcode / RFID Scanners:** Warehouse inputs are updated digitally via API or dashboard, not physical handheld scanners.

---

## 📅 5. 10-Day Beginner-Friendly Timeline

| Day | Focus Area | Milestone Deliverable |
| :---: | :--- | :--- |
| **Day 1–2** | **Project Setup & Data Layer** | Install dependencies, set up `.env`, verify `seed_inventory.json` (Kanpur, Unnao, Agra) and mock Firestore/BigQuery connectors. |
| **Day 3–4** | **Logistics & Risk Engine** | Test Agra-Lucknow Expressway calculator, NGT regulatory notices, and policy vector search. |
| **Day 5–6** | **Specialist Multi-Agents** | Test District Inventory Agent, Regional Risk Agent, and Intra-State Logistics Agent standalone logic. |
| **Day 7–8** | **Orchestrator & Discord Webhook** | Connect State Master Orchestrator, dispatch Discord approval cards, and test automatic database updates upon approval. |
| **Day 9** | **Streamlit Dashboard Polish** | Verify corridor map, stock health gauges, emergency simulation buttons, and test on `localhost:8501`. |
| **Day 10** | **Demo Rehearsal & Documentation** | Rehearse 5-minute presentation walkthrough, take screenshots for capstone report, and freeze code. |
