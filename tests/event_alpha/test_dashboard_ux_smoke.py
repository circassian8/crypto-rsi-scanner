from __future__ import annotations

from datetime import datetime, timezone

import pytest

from crypto_rsi_scanner.event_alpha.dashboard.loader import DashboardLoadError
from crypto_rsi_scanner.event_alpha.dashboard.loader import load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.dashboard.render import render_dashboard_page
from crypto_rsi_scanner.event_alpha.dashboard.ux_smoke import run_ux_smoke


_BASE = "fixtures/event_alpha/radar_dashboard"
_NAMESPACE = "current"
_NOW = datetime(2026, 7, 12, 7, 0, tzinfo=timezone.utc).isoformat()


def test_dashboard_ux_smoke_covers_primary_operator_surface(capsys) -> None:
    assert run_ux_smoke(_BASE, _NAMESPACE, now=_NOW) == 0

    output = capsys.readouterr().out
    assert "pages=9" in output
    assert "semantic_shell=ok" in output
    assert "responsive_css_contract=ok" in output
    assert "writes=0" in output


def test_dashboard_ux_smoke_fails_closed_for_missing_generation(tmp_path) -> None:
    with pytest.raises(DashboardLoadError):
        run_ux_smoke(tmp_path, "missing", now=_NOW)


def test_idea_detail_keeps_ideas_navigation_selected() -> None:
    snapshot = load_dashboard_snapshot(_BASE, _NAMESPACE, now=_NOW)
    page = render_dashboard_page(snapshot, "/ideas/core:alpha")

    assert page.status_code == 200
    assert '<a href="/ideas" aria-current="page">Ideas</a>' in page.body
