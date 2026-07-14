from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.dashboard.layer_coverage import (
    dashboard_layer_coverage_by_key,
)
from crypto_rsi_scanner.event_alpha.dashboard.models import DashboardSnapshot
from crypto_rsi_scanner.event_alpha.dashboard.system_pages import (
    render_health_page,
    render_outcomes_page,
)
from crypto_rsi_scanner.event_alpha.dashboard.today_page import render_today_page


def _manifest_row(
    sidecar_name: str,
    *,
    mode: str,
    configured: bool,
    rows: int = 0,
    freshness: str = "fresh",
    warnings: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "sidecar_name": sidecar_name,
        "mode": mode,
        "configured": configured,
        "provider_status": "configured" if configured else "not_configured",
        "freshness_status": freshness,
        "row_counts": {"rows": rows},
        "warnings": warnings,
        "errors": errors,
    }


def _snapshot() -> DashboardSnapshot:
    return DashboardSnapshot(
        namespace_dir=Path("/private/tmp/radar/current"),
        run_id="run-current",
        profile="no_key_live",
        artifact_namespace="current",
        revision=4,
        manifest_status="complete",
        doctor_status="ok",
        doctor_verified_revision=4,
        generation_authority_status="authoritative",
        generation_authority_reasons=(),
        generation_authority_checked_at="2026-07-14T10:05:00+00:00",
        operator_state_sha256="a" * 64,
        operator_state={
            "research_only": True,
            "send_attempted": False,
            "generated_at": "2026-07-14T10:00:00+00:00",
            "artifacts": {},
        },
        current_market_observations=(
            {
                "symbol": "BTC",
                "freshness_status": "fresh",
                "spread_status": "verified_good",
                "market_data_quality": {
                    "baseline_status": "warm",
                    "spread_available": True,
                },
            },
        ),
        source_coverage={
            "packs": [
                {
                    "source_pack": "official_exchange_listing_pack",
                    "provider_coverage_status": "observed_no_results",
                    "accepted_evidence_count": 0,
                },
                {
                    "source_pack": "unlock_supply_pack",
                    "provider_coverage_status": "observed_no_results",
                    "accepted_evidence_count": 0,
                },
            ],
            "input_manifest": [
                _manifest_row(
                    "derivatives",
                    mode="loaded_local_read_only_empty",
                    configured=True,
                ),
                _manifest_row(
                    "rsi_signal_context",
                    mode="loaded_local_read_only_empty",
                    configured=True,
                ),
            ],
        },
        market_generation={
            "status": "complete",
            "candidate_source_mode": "fixture",
            "calendar_snapshot": {
                "status": "healthy_empty",
                "normalization_status": "healthy_empty",
                "normalization_rejected_count": 0,
                "configured": True,
            },
        },
        current_outcomes_metadata={
            "authority": "current_generation_fingerprint_verified",
            "sha256": "b" * 64,
            "source_row_count": 0,
            "returned_row_count": 0,
            "error": None,
        },
    )


@pytest.mark.parametrize(
    ("row", "expected"),
    (
        (_manifest_row("derivatives", mode="loaded_existing", configured=True, rows=1), "healthy_nonempty"),
        (_manifest_row("derivatives", mode="loaded_local_read_only_empty", configured=True), "healthy_empty"),
        (_manifest_row("derivatives", mode="skipped_missing_config", configured=False, freshness="missing"), "not_configured"),
        (_manifest_row("derivatives", mode="not_applicable", configured=False, freshness="missing"), "not_applicable"),
        (_manifest_row("derivatives", mode="skipped_missing_artifact", configured=True, freshness="missing"), "unavailable"),
        (_manifest_row("derivatives", mode="loaded_existing_empty_unverified", configured=True, freshness="unknown"), "degraded"),
        (_manifest_row("derivatives", mode="loaded_existing", configured=True, freshness="stale"), "stale"),
        (
            _manifest_row(
                "derivatives",
                mode="local_read_error",
                configured=True,
                freshness="unknown",
                errors=("schema_validation_failed",),
            ),
            "rejected",
        ),
    ),
)
def test_derivatives_projection_distinguishes_every_coverage_state(
    row: dict[str, object],
    expected: str,
) -> None:
    snapshot = _snapshot()
    source_coverage = dict(snapshot.source_coverage)
    source_coverage["input_manifest"] = [
        row,
        _manifest_row(
            "rsi_signal_context",
            mode="loaded_local_read_only_empty",
            configured=True,
        ),
    ]

    layer = dashboard_layer_coverage_by_key(
        replace(snapshot, source_coverage=source_coverage)
    )["derivatives"]

    assert layer.status == expected
    assert layer.action_required is (expected not in {"healthy_nonempty", "healthy_empty", "not_applicable"})


def test_today_green_state_requires_every_expected_layer() -> None:
    healthy = render_today_page(_snapshot())

    assert "No action-required system warnings" in healthy
    assert "every expected exact-generation product layer" in healthy

    snapshot = _snapshot()
    source_coverage = dict(snapshot.source_coverage)
    source_coverage["input_manifest"] = [
        _manifest_row(
            "derivatives",
            mode="skipped_missing_config",
            configured=False,
            freshness="missing",
        ),
        _manifest_row(
            "rsi_signal_context",
            mode="skipped_missing_config",
            configured=False,
            freshness="missing",
        ),
    ]
    incomplete = replace(
        snapshot,
        source_coverage=source_coverage,
        market_generation={
            **snapshot.market_generation,
            "candidate_source_mode": "live_no_send",
            "provider_call_attempted": True,
        },
        current_request_ledger={},
        current_request_ledger_metadata={"authority": "not_available"},
    )

    page = render_today_page(incomplete)

    assert "No action-required system warnings" not in page
    assert "Derivatives context not configured" in page
    assert "RSI context not configured" in page
    assert "Provider request ledger unavailable" in page


def test_untrusted_projection_suppresses_underlying_layer_counts_and_green_states() -> None:
    snapshot = replace(
        _snapshot(),
        generation_authority_status="untrusted",
        generation_authority_reasons=("doctor:blockers_present",),
    )

    coverage = dashboard_layer_coverage_by_key(snapshot)

    assert set(coverage) == {
        "market",
        "catalyst",
        "calendar",
        "derivatives",
        "rsi",
        "outcomes",
        "request_ledger",
    }
    assert all(layer.status == "rejected" for layer in coverage.values())
    assert all(layer.row_count == 0 for layer in coverage.values())
    assert all(layer.action_required for layer in coverage.values())
    health = render_health_page(snapshot)
    assert "No action-required health constraint" not in health
    assert "Current generation is not authoritative" in health
    assert "underlying row count" in health


def test_health_uses_same_projection_and_warns_for_missing_live_request_ledger() -> None:
    snapshot = _snapshot()
    live = replace(
        snapshot,
        market_generation={
            **snapshot.market_generation,
            "candidate_source_mode": "live_no_send",
            "provider_call_attempted": True,
        },
        current_request_ledger={},
        current_request_ledger_metadata={"authority": "not_available"},
    )

    page = render_health_page(live)

    assert "Product-layer coverage" in page
    assert "Canonical exact-generation layer coverage" in page
    assert "Provider request ledger unavailable" in page
    assert "live/provider-backed generation is missing" in page
    assert "No action-required health constraint" not in page


def test_outcomes_without_exact_metadata_never_default_to_verified() -> None:
    snapshot = replace(
        _snapshot(),
        current_candidates=({"candidate_id": "candidate:btc", "symbol": "BTC"},),
        current_outcomes=(),
        current_outcomes_metadata={},
    )

    page = render_outcomes_page(snapshot, {})

    assert "Fingerprint-verified placeholders" not in page
    assert "Current generation fingerprint verified" not in page
    assert "No fingerprint-verified exact outcome artifact is available" in page
    assert "not a verified empty result" in page


def test_outcome_empty_artifact_and_filter_empty_are_distinct() -> None:
    verified_empty = render_outcomes_page(_snapshot(), {})

    assert "fingerprint-verified outcome artifact is empty" in verified_empty
    assert "verified empty result, not a missing artifact" in verified_empty

    snapshot = replace(
        _snapshot(),
        current_candidates=({"candidate_id": "candidate:btc", "symbol": "BTC"},),
        current_outcomes=(
            {
                "candidate_id": "candidate:btc",
                "symbol": "BTC",
                "outcome_status": "pending",
                "radar_route": "dashboard_watch",
            },
        ),
        current_outcomes_metadata={
            "authority": "current_generation_fingerprint_verified",
            "sha256": "c" * 64,
            "source_row_count": 1,
            "returned_row_count": 1,
            "error": None,
        },
    )

    filtered = render_outcomes_page(snapshot, {"status": "matured"})

    assert "Exact current outcome rows exist, but none match the selected filters" in filtered
    assert "verified empty result, not a missing artifact" not in filtered


def test_calendar_partial_normalization_is_degraded_not_clean() -> None:
    snapshot = replace(
        _snapshot(),
        current_calendar_events=({"calendar_event_id": "event-1", "title": "Event"},),
        market_generation={
            **_snapshot().market_generation,
            "calendar_snapshot": {
                "status": "healthy_nonempty",
                "normalization_status": "healthy_nonempty",
                "normalization_rejected_count": 2,
                "configured": True,
            },
        },
    )

    layer = dashboard_layer_coverage_by_key(snapshot)["calendar"]

    assert layer.status == "degraded"
    assert layer.action_required is True
    assert "some source rows were rejected" in layer.detail
