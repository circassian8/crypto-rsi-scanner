"""Local read-only Event Alpha radar dashboard."""

from .app import RadarDashboardApp, serve_dashboard
from .loader import load_dashboard_snapshot
from .models import DashboardLoadError, DashboardSnapshot

__all__ = (
    "DashboardLoadError",
    "DashboardSnapshot",
    "RadarDashboardApp",
    "load_dashboard_snapshot",
    "serve_dashboard",
)
