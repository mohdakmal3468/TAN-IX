"""
config.py
---------
Central configuration for AgentHide.
Loads environment variables safely and defines constants for Uttar Pradesh clusters:
- Kanpur (Tanneries, Saddlery, Industrial Leather)
- Unnao (Leather Complex, Raw to Wet Blue processing)
- Agra (Shoe & Footwear Hub)
- Noida / Greater Noida (Export Leather Apparel & Luxury Goods)
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# --- AI & Model Settings ---
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
# Default to standard gemini-2.5-flash or user-configured model
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# --- Google Cloud Platform Settings ---
GCP_PROJECT_ID: str = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT_ID", "agenthide-demo"))
FIRESTORE_DATABASE: str = os.getenv("FIRESTORE_DATABASE", "(default)")
BIGQUERY_DATASET: str = os.getenv("BIGQUERY_DATASET", "up_leather_logistics")

# --- Mock Mode ---
# When True, the system reads from local JSON files instead of failing if GCP credentials are not active.
# This makes it 100% beginner friendly!
USE_MOCK_DATA: bool = os.getenv("USE_MOCK_DATA", "true").lower() in ("true", "1", "yes")

# --- Discord Notification Settings ---
DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

# --- API and Dashboard Ports ---
FASTAPI_HOST: str = os.getenv("FASTAPI_HOST", "127.0.0.1")
FASTAPI_PORT: int = int(os.getenv("FASTAPI_PORT", "8000"))
STREAMLIT_PORT: int = int(os.getenv("STREAMLIT_PORT", "8501"))

# --- UP Leather Cluster Metadata & Coordinates ---
# Lat/Lon coordinates used for distance calculation and Streamlit 3D map rendering
UP_CLUSTERS: Dict[str, Dict[str, Any]] = {
    "Kanpur": {
        "name": "Kanpur Leather Hub",
        "district": "Kanpur Nagar",
        "lat": 26.4499,
        "lon": 80.3319,
        "primary_role": "Heavy Tanning, Saddlery, Industrial Leather (Jajmau)",
        "vulnerabilities": ["Ganges River flood plain", "NGT effluent discharge restrictions", "CETP overflow risk"],
        "critical_items": ["Raw Hides", "Crust Leather", "Chromium Tanning Salts", "Finished Cowhide"],
        "color": [220, 53, 69, 200]  # Red tone
    },
    "Unnao": {
        "name": "Unnao Leather Complex",
        "district": "Unnao",
        "lat": 26.5458,
        "lon": 80.4878,
        "primary_role": "Industrial Area Tannery Complex (Wet-Blue & Crust Leather)",
        "vulnerabilities": ["Water treatment capacity", "Monsoon effluent logging", "Power supply volatility"],
        "critical_items": ["Raw Buffalo Hides", "Wet-Blue Leather", "Vegetable Tanning Extracts"],
        "color": [255, 152, 0, 200]  # Orange tone
    },
    "Agra": {
        "name": "Agra Footwear Cluster",
        "district": "Agra",
        "lat": 27.1767,
        "lon": 78.0081,
        "primary_role": "Footwear Manufacturing, Shoe Uppers & Soles (Sikandra/Hing ki Mandi)",
        "vulnerabilities": ["Raw material transit delays from Kanpur", "Skilled artisan availability", "Expressway fog"],
        "critical_items": ["Shoe Uppers", "Leather Soles", "Finished Calf Leather", "Adhesives"],
        "color": [40, 167, 69, 200]  # Green tone
    },
    "Noida": {
        "name": "Noida Export Zone",
        "district": "Gautam Buddha Nagar",
        "lat": 28.5355,
        "lon": 77.3910,
        "primary_role": "High-Value Fashion Export, Handbags, Luxury Jackets (Sec 63/65)",
        "vulnerabilities": ["Strict international shipment deadlines", "Port transit cutoff times (Delhi IGI / Nhava Sheva)"],
        "critical_items": ["Premium Nappa Leather", "Designer Hardware/Zippers", "Finished Export Garments"],
        "color": [33, 150, 243, 200]  # Blue tone
    }
}

# --- Key Expressways & Highway Corridors ---
HIGHWAY_CORRIDORS = {
    ("Kanpur", "Unnao"): {"distance_km": 25, "transit_hours": 0.8, "route_name": "NH-27 / Ganga Bridge"},
    ("Kanpur", "Agra"): {"distance_km": 285, "transit_hours": 4.5, "route_name": "Agra-Lucknow Expressway & NH-19"},
    ("Unnao", "Agra"): {"distance_km": 290, "transit_hours": 4.6, "route_name": "Agra-Lucknow Expressway"},
    ("Agra", "Noida"): {"distance_km": 195, "transit_hours": 2.5, "route_name": "Yamuna Expressway"},
    ("Kanpur", "Noida"): {"distance_km": 465, "transit_hours": 6.8, "route_name": "Agra-Lucknow Expway + Yamuna Expway"}
}
