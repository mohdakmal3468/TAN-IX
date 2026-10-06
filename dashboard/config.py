"""
dashboard/config.py
-------------------
Frontend and Dashboard configuration for TAN-IX.
Loads API_BASE_URL and service endpoints from environment variables.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Backend FastAPI Service Base URL
API_BASE_URL: str = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# Specific API Endpoints
API_ENDPOINTS = {
    "health": f"{API_BASE_URL}/health",
    "inventory": f"{API_BASE_URL}/inventory",
    "stock_update": f"{API_BASE_URL}/stock-update",
    "disruption": f"{API_BASE_URL}/disruption",
    "shipment": f"{API_BASE_URL}/shipment",
    "disruptions_active": f"{API_BASE_URL}/disruptions/active",
    "lanes_risk": f"{API_BASE_URL}/lanes/risk-scores",
    "approval_callback": f"{API_BASE_URL}/approval/discord-callback"
}

# Dashboard UI Settings
APP_TITLE = "TAN-IX: UP Leather Supply Chain & Risk Command Center"
APP_ICON = "🛡️"
DEFAULT_REFRESH_INTERVAL_SEC = int(os.getenv("DASHBOARD_REFRESH_SEC", "15"))

# Palette Configuration (Tailored UP Industrial Hues)
THEME_COLORS = {
    "primary": "#D97706",      # Amber Leather
    "secondary": "#1E293B",    # Dark Slate
    "accent": "#059669",       # Emerald Forest
    "critical": "#DC2626",     # Crimson Alert
    "warning": "#F59E0B",      # Warning Orange
    "background": "#0F172A",   # Midnight Blue
    "surface": "#1E293B"       # Slate Surface
}
