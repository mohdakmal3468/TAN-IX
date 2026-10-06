"""
dashboard/frontend/components/cards.py
--------------------------------------
Reusable UI component helpers for Streamlit metrics, badges, and status indicators.
"""

from typing import Optional


def render_kpi_card(title: str, value: str, subtitle: Optional[str] = None, delta_color: str = "normal") -> str:
    """Returns HTML for a modern glassmorphic KPI card."""
    sub_html = f"<div style='font-size: 0.85rem; color: #94A3B8; margin-top: 4px;'>{subtitle}</div>" if subtitle else ""
    return f"""
    <div style="
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        margin-bottom: 12px;
    ">
        <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94A3B8;">{title}</div>
        <div style="font-size: 1.8rem; font-weight: 700; color: #F8FAFC; margin-top: 4px;">{value}</div>
        {sub_html}
    </div>
    """


def render_risk_badge(risk_score: float) -> str:
    """Returns a color-coded HTML badge for a given risk score (0-100)."""
    if risk_score >= 75.0:
        bg = "#DC2626"
        label = "CRITICAL"
    elif risk_score >= 50.0:
        bg = "#EA580C"
        label = "ELEVATED"
    elif risk_score >= 25.0:
        bg = "#D97706"
        label = "MODERATE"
    else:
        bg = "#059669"
        label = "LOW"

    return f"""
    <span style="
        background-color: {bg};
        color: white;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.75rem;
        letter-spacing: 0.05em;
        display: inline-block;
    ">
        {label} ({risk_score:.1f})
    </span>
    """
