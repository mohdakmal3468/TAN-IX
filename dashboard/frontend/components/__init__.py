"""
dashboard/frontend/components package.
Reusable UI elements: status badges, KPI metrics cards, risk thermometers, and approval cards.
"""

from .cards import render_kpi_card, render_risk_badge

__all__ = ["render_kpi_card", "render_risk_badge"]
