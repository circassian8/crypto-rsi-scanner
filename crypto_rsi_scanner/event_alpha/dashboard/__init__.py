"""Local read-only Event Alpha radar dashboard."""

from .app import RadarDashboardApp, serve_dashboard
from .loader import load_dashboard_snapshot
from .models import DashboardGenerationBinding, DashboardLoadError, DashboardSnapshot
from .readiness import (
    DashboardReadinessError,
    publish_current_namespace_pointer,
    resolve_authoritative_dashboard,
)

__all__ = (
    "DashboardLoadError",
    "DashboardReadinessError",
    "DashboardSnapshot",
    "DashboardGenerationBinding",
    "RadarDashboardApp",
    "load_dashboard_snapshot",
    "publish_current_namespace_pointer",
    "resolve_authoritative_dashboard",
    "serve_dashboard",
)
