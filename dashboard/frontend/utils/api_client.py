"""
dashboard/frontend/utils/api_client.py
--------------------------------------
Lightweight HTTP client communicating with the AgentHide FastAPI backend.
Utilizes API_BASE_URL configured in dashboard/config.py.
"""

from typing import Dict, Any, List, Optional
import requests
from dashboard.config import API_BASE_URL, API_ENDPOINTS


def fetch_health() -> Dict[str, Any]:
    """Checks FastAPI backend health status."""
    try:
        resp = requests.get(API_ENDPOINTS["health"], timeout=3)
        if resp.status_code == 200:
            return resp.json()
        return {"status": "DEGRADED", "code": resp.status_code}
    except Exception as e:
        return {"status": "OFFLINE", "error": str(e), "url": API_BASE_URL}


def fetch_inventory_by_district(district: str) -> List[Dict[str, Any]]:
    """Retrieves live inventory items for a specific cluster."""
    url = f"{API_ENDPOINTS['inventory']}/{district}"
    try:
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            return resp.json().get("items", [])
        return []
    except Exception:
        return []


def fetch_active_disruptions() -> List[Dict[str, Any]]:
    """Retrieves active highway disruption events from the backend."""
    try:
        resp = requests.get(API_ENDPOINTS["disruptions_active"], timeout=4)
        if resp.status_code == 200:
            return resp.json().get("disruptions", [])
        return []
    except Exception:
        return []
