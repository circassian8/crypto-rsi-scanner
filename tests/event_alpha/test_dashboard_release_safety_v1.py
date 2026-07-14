from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from crypto_rsi_scanner.event_alpha.dashboard.components import safe_external_href
from crypto_rsi_scanner.event_alpha.dashboard.loader import (
    candidate_identifier,
    load_dashboard_snapshot,
)
from crypto_rsi_scanner.event_alpha.dashboard.render import render_dashboard_page


_NOW = datetime(2026, 7, 12, 7, 0, tzinfo=timezone.utc)
_FIXTURE = Path("fixtures/event_alpha/radar_dashboard/current")


def _snapshot():
    return load_dashboard_snapshot(
        _FIXTURE.parent,
        _FIXTURE.name,
        now=_NOW,
    )


def test_untrusted_generation_quarantines_current_rows_on_every_primary_surface() -> None:
    source = _snapshot()
    candidate = {**source.current_candidates[0], "symbol": "LEAKED-CURRENT-VALUE"}
    untrusted = replace(
        source,
        generation_authority_status="untrusted",
        generation_authority_reasons=("forced_release_safety_test",),
        current_candidates=(candidate,),
        current_market_observations=({"symbol": "LEAKED-CURRENT-VALUE"},),
        current_market_anomalies=({"symbol": "LEAKED-CURRENT-VALUE"},),
        current_calendar_events=({"title": "LEAKED-CURRENT-VALUE"},),
        current_outcomes=({"symbol": "LEAKED-CURRENT-VALUE"},),
        current_request_ledger={"endpoint_path": "LEAKED-CURRENT-VALUE"},
        market_generation={"failure_reason": "LEAKED-CURRENT-VALUE"},
    )

    for route in (
        "/",
        "/market-radar",
        "/ideas",
        "/calendar",
        "/health",
        "/outcomes",
        "/campaign-history",
    ):
        page = render_dashboard_page(untrusted, route)
        assert "LEAKED-CURRENT-VALUE" not in page.body, route
        assert "current rows suppressed" in page.body, route
        assert "candidate rows" not in page.body, route

    outcomes = render_dashboard_page(untrusted, "/outcomes")
    campaign = render_dashboard_page(untrusted, "/campaign-history")
    health = render_dashboard_page(untrusted, "/health")
    assert "Exact current-generation outcomes" not in outcomes.body
    assert "Current outcome rows suppressed" in outcomes.body
    assert "Current campaign authority suppressed" in campaign.body
    assert "No action-required health constraint" not in health.body


def test_failed_current_outcome_fingerprint_is_quarantined_not_demoted_to_history(
    tmp_path: Path,
) -> None:
    namespace = tmp_path / "current"
    shutil.copytree(_FIXTURE, namespace)
    outcome_path = namespace / "event_integrated_radar_outcomes.jsonl"
    outcome_path.write_text(
        json.dumps(
            {
                "row_type": "event_integrated_radar_outcome",
                "run_id": "dashboard-run-current",
                "profile": "notify_no_key",
                "artifact_namespace": "current",
                "symbol": "LEAKED-TAMPERED-OUTCOME",
                "research_only": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    state_path = namespace / "event_alpha_operator_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["artifacts"]["integrated_outcomes"] = {
        "count": 1,
        "fingerprint_contract_version": 1,
        "fingerprint_kind": "jsonl_lines",
        "generated_at": state["updated_at"],
        "item_count": 1,
        "path": outcome_path.name,
        "reason": None,
        "run_id": state["run_id"],
        "sha256": "0" * 64,
        "size_bytes": outcome_path.stat().st_size,
        "status": "current",
    }
    state_path.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")

    snapshot = load_dashboard_snapshot(tmp_path, "current", now=_NOW)

    assert snapshot.generation_authoritative is False
    assert snapshot.current_outcomes == ()
    assert snapshot.cumulative_outcomes == ()
    assert snapshot.current_outcomes_metadata["authority"] == "current_generation_invalid"
    assert snapshot.current_outcomes_metadata["error"] == "current_artifact_quarantined"
    page = render_dashboard_page(snapshot, "/outcomes")
    assert "LEAKED-TAMPERED-OUTCOME" not in page.body


def test_external_links_reject_embedded_credentials_on_all_dashboard_components() -> None:
    credential_url = "https://operator:secret-token@example.com/research"
    assert safe_external_href(credential_url) is None

    source = _snapshot()
    candidate = {**source.current_candidates[0], "source_url": credential_url}
    snapshot = replace(source, current_candidates=(candidate,))
    identifier = candidate_identifier(candidate)
    page = render_dashboard_page(snapshot, f"/ideas/{identifier}")

    assert "secret-token" not in page.body
    assert "operator:" not in page.body
    assert "unsafe or unavailable source URL" in page.body


def test_mixed_return_units_and_turnover_ratio_render_with_field_level_units() -> None:
    source = _snapshot()
    row = {
        "symbol": "UNIT",
        "coin_id": "unit-test",
        "price": 1.0,
        "return_1h": 0.01,
        "return_4h": 0.05,
        "return_24h": 0.10,
        "relative_return_vs_btc_4h": 10.0,
        "relative_return_vs_eth_4h": 10.0,
        "return_unit": "fraction",
        "return_units": {
            "relative_return_vs_btc_4h": "percent_points",
            "relative_return_vs_eth_4h": "percent_points",
        },
        "volume_24h": 1_000_000.0,
        "turnover_24h": 0.10,
        "spread_status": "unavailable",
        "freshness_status": "fresh",
        "market_data_quality": {"baseline_status": "warm"},
    }
    history = (
        {
            "symbol": "UNIT",
            "coin_id": "unit-test",
            "observed_at": "2026-07-12T05:00:00+00:00",
            "price": 0.9,
            "volume_24h": 900_000.0,
            "turnover_24h": 0.10,
        },
    )
    snapshot = replace(
        source,
        current_candidates=(),
        current_market_observations=(row,),
        exact_market_history=history,
    )

    market = render_dashboard_page(snapshot, "/market-radar")
    today = render_dashboard_page(snapshot, "/")

    assert "+1,000.00%" not in market.body
    assert market.body.count("+10%") >= 3
    assert "+10%" in today.body
    assert "+10.0%" in market.body
