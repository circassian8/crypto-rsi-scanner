"""Integrated fixture-route and return-unit regressions for Decision v2."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def _fixture_cycle_rows() -> tuple[list[dict], list[dict]]:
    from crypto_rsi_scanner.event_alpha.artifacts import context as artifact_context
    from crypto_rsi_scanner.event_alpha.radar import integrated_radar

    with TemporaryDirectory() as tmp:
        context = artifact_context.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=tmp,
            artifact_namespace="pytest_decision_v2_routes",
        )
        result = integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
        )
        candidates = [
            json.loads(line)
            for line in result.integrated_candidates_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        core_rows = [
            json.loads(line)
            for line in context.core_opportunity_store_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return candidates, core_rows


def test_integrated_fixture_proves_every_decision_v2_route_end_to_end():
    candidates, core_rows = _fixture_cycle_rows()
    by_symbol = {row["symbol"]: row for row in candidates}
    core_by_symbol = {row["symbol"]: row for row in core_rows}

    expected_routes = {
        "high_confidence_watch",
        "actionable_watch",
        "rapid_market_anomaly",
        "dashboard_watch",
        "fade_exhaustion_review",
        "risk_watch",
        "calendar_risk",
        "diagnostic",
    }
    assert expected_routes <= {row["radar_route"] for row in candidates}
    assert by_symbol["TESTHIGH"]["radar_route"] == "high_confidence_watch"
    assert by_symbol["TESTFLOW"]["radar_route"] == "actionable_watch"
    assert by_symbol["TESTRAPID"]["radar_route"] == "rapid_market_anomaly"
    assert by_symbol["AAVE"]["radar_route"] == "dashboard_watch"
    assert by_symbol["TESTFADE"]["radar_route"] == "fade_exhaustion_review"
    assert by_symbol["TKND"]["radar_route"] == "risk_watch"
    assert by_symbol["TESTLIST"]["radar_route"] == "calendar_risk"
    assert by_symbol["TESTFLOWLOW"]["radar_route"] == "diagnostic"

    for symbol in ("TESTHIGH", "TESTFLOW", "TESTRAPID", "TESTFADE"):
        assert core_by_symbol[symbol]["radar_route"] == by_symbol[symbol]["radar_route"]
        assert by_symbol[symbol]["research_only"] is True
        assert by_symbol[symbol]["created_alert"] is False
        assert by_symbol[symbol]["normal_rsi_signal_written"] is False
        assert by_symbol[symbol]["triggered_fade_created"] is False
        assert by_symbol[symbol]["paper_trade_created"] is False
        assert by_symbol[symbol]["notification_send_enabled"] is False


def test_fixture_freshness_is_explicit_without_weakening_stale_blockers():
    candidates, _ = _fixture_cycle_rows()
    by_symbol = {row["symbol"]: row for row in candidates}

    for symbol in ("TESTPERP", "TESTFADE", "TESTRAPID"):
        row = by_symbol[symbol]
        assert row["market_state_snapshot"]["freshness_status"] == "fresh"
        assert "market_data_freshness_unverified" not in row["decision_hard_blockers"]
    assert by_symbol["TESTRAPID"]["catalyst_status"] == "unknown"
    assert by_symbol["TESTRAPID"]["radar_actionable"] is True
    assert by_symbol["TESTRAPID"]["urgency_score"] >= 72.0
    assert by_symbol["TESTFLOWLOW"]["radar_actionable"] is False
    assert "liquidity_below_minimum" in by_symbol["TESTFLOWLOW"]["decision_hard_blockers"]


def test_market_state_per_field_units_normalize_without_a_100x_guess():
    from crypto_rsi_scanner.event_alpha.radar import market_state

    fraction = market_state.snapshot_from_market_row({
        "symbol": "MIXED",
        "coin_id": "mixed",
        "return_unit": "fraction",
        "return_4h": 0.10,
        "relative_return_vs_btc_4h": 0.10,
        "freshness_status": "fresh",
    }).to_dict()
    percent_points = market_state.snapshot_from_market_row({
        "symbol": "MIXED",
        "coin_id": "mixed",
        "return_unit": "percent_points",
        "return_4h": 10.0,
        "relative_return_vs_btc_4h": 10.0,
        "freshness_status": "fresh",
    }).to_dict()
    mixed = market_state.snapshot_from_market_row({
        "symbol": "MIXED",
        "coin_id": "mixed",
        "return_unit": "fraction",
        "return_units": {"relative_return_vs_btc_4h": "percent_points"},
        "return_4h": 0.10,
        "relative_return_vs_btc_4h": 10.0,
        "freshness_status": "fresh",
    }).to_dict()

    assert fraction["return_4h"] == percent_points["return_4h"] == mixed["return_4h"] == 10.0
    assert (
        fraction["relative_return_vs_btc_4h"]
        == percent_points["relative_return_vs_btc_4h"]
        == mixed["relative_return_vs_btc_4h"]
        == 10.0
    )
    assert mixed["return_units"]["relative_return_vs_btc_4h"] == "percent_points"
    assert mixed["source_return_units"]["return_4h"] == "fraction"
    assert mixed["source_return_units"]["relative_return_vs_btc_4h"] == "percent_points"
    assert mixed["unit_warnings"] == []


def test_fraction_value_that_looks_like_percent_points_fails_unit_validation():
    from crypto_rsi_scanner.event_alpha.radar import market_state, market_units

    invalid = {
        "return_unit": "fraction",
        "return_4h": 0.10,
        "relative_return_vs_btc_4h": 10.0,
    }
    warnings = market_units.validate_market_snapshot_units(invalid)
    snapshot = market_state.snapshot_from_market_row({
        "symbol": "BADUNIT",
        "coin_id": "bad-unit",
        "freshness_status": "fresh",
        **invalid,
    }).to_dict()

    assert "implausible_fraction_return:relative_return_vs_btc_4h" in warnings
    assert "implausible_normalized_return:relative_return_vs_btc_4h" in snapshot["unit_warnings"]


def test_integrated_fixture_uses_one_exact_source_independence_blob_end_to_end():
    from crypto_rsi_scanner.event_alpha.artifacts import context as artifact_context
    from crypto_rsi_scanner.event_alpha.artifacts import operator_state
    from crypto_rsi_scanner.event_alpha.outcomes import integrated_radar_outcomes
    from crypto_rsi_scanner.event_alpha.radar import core_opportunity_store
    from crypto_rsi_scanner.event_alpha.radar import integrated_radar
    from crypto_rsi_scanner.event_alpha.radar import source_independence_store

    with TemporaryDirectory() as tmp:
        context = artifact_context.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=tmp,
            artifact_namespace="pytest_source_store",
        )
        result = integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
        )
        namespace = Path(context.namespace_dir)
        artifact_paths = (
            result.integrated_candidates_path,
            context.core_opportunity_store_path,
            namespace / integrated_radar.INTEGRATED_OUTCOMES_FILENAME,
        )
        references = []
        persisted_bytes = 0
        for path in artifact_paths:
            persisted_bytes += path.stat().st_size
            for line in path.read_text(encoding="utf-8").splitlines():
                references.extend(_source_store_references(json.loads(line)))

        assert len(references) >= 6
        assert len(
            {
                (
                    ref["contract_digest"],
                    ref["blob_fingerprint"]["sha256"],
                )
                for ref in references
            }
        ) == 1
        store_files = tuple(
            (namespace / source_independence_store.STORE_DIRECTORY).iterdir()
        )
        assert len(store_files) == 1
        assert store_files[0].stat().st_size == references[0]["blob_fingerprint"][
            "size_bytes"
        ]

        core_rows = core_opportunity_store.load_core_opportunities(
            context.core_opportunity_store_path,
            latest_run=True,
        ).rows
        outcome_rows = integrated_radar_outcomes.load_integrated_radar_outcomes(
            namespace
        )
        testhigh_core = next(row for row in core_rows if row["symbol"] == "TESTHIGH")
        testhigh_outcome = next(
            row for row in outcome_rows if row["symbol"] == "TESTHIGH"
        )
        assert testhigh_core["source_independence"]["schema_id"] == (
            "event_alpha.source_independence"
        )
        assert (
            testhigh_core["source_independence"]["contract_digest"]
            == testhigh_outcome["source_independence"]["contract_digest"]
            == references[0]["contract_digest"]
        )
        measured = source_independence_store.measurement_stats(
            [testhigh_core, testhigh_outcome]
        )
        assert measured.inline_contract_occurrences >= 4
        assert measured.projected_inline_savings_bytes > 0
        assert persisted_bytes > 0

        state = operator_state.load_operator_state(namespace)
        assert state.valid is True
        assert state.state["artifacts"][
            "source_independence_contract_store"
        ]["status"] == "current"

        store_files[0].unlink()
        with pytest.raises(
            source_independence_store.SourceIndependenceStoreError,
            match="blob_unreadable",
        ):
            core_opportunity_store.load_core_opportunities(
                context.core_opportunity_store_path,
                latest_run=True,
            )


def _source_store_references(value: object) -> list[dict]:
    references: list[dict] = []
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if current.get("schema_id") == "event_alpha.source_independence_reference":
                references.append(current)
            else:
                stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return references
