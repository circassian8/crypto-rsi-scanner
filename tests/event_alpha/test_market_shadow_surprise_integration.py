"""Post-scan isolation tests for robust temporal-surprise shadow evidence."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    market_no_send,
    market_no_send_authority,
    market_no_send_io,
)
from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner
from crypto_rsi_scanner.event_alpha.radar import market_anomaly_receipt


NOW = datetime(2026, 6, 15, 16, tzinfo=timezone.utc)


def _current_market_row() -> dict:
    fixture = market_anomaly_scanner.load_market_rows(
        "fixtures/event_market_anomaly/market_rows.json"
    )
    row = deepcopy(next(item for item in fixture if item.get("id") == "token-b"))
    row.update({
        "coin_id": "token-b",
        "canonical_asset_id": "token-b",
        "volume_24h": 125_000_000.0,
        "turnover_24h": 125_000_000.0 / 420_000_000.0,
        "market_history_observation_id": "obs-current",
        "feature_basis": {
            "volume_24h": "provider_observed",
            "market_cap": "provider_observed",
            "turnover_24h": "derived_provider_ratio",
        },
    })
    return row


def _history_rows(current: dict) -> list[dict]:
    history: list[dict] = []
    for offset in range(8, 0, -1):
        volume = float(45_000_000 + (8 - offset) * 5_000_000)
        history.append({
            "observation_id": f"obs-prior-{offset}",
            "canonical_asset_id": "token-b",
            "coin_id": "token-b",
            "observed_at": (NOW - timedelta(hours=offset)).isoformat(),
            "volume_24h": volume,
            "market_cap": 420_000_000.0,
            "turnover_24h": volume / 420_000_000.0,
            "feature_basis": {
                "volume_24h": "provider_observed",
                "market_cap": "provider_observed",
                "turnover_24h": "derived_provider_ratio",
            },
            "baseline_counted": True,
            "baseline_counting_status": "counted",
            "research_only": True,
        })
    history.append({
        "observation_id": "obs-too-close",
        "canonical_asset_id": "token-b",
        "coin_id": "token-b",
        "observed_at": (NOW - timedelta(minutes=30)).isoformat(),
        "volume_24h": 124_000_000.0,
        "market_cap": 420_000_000.0,
        "turnover_24h": 124_000_000.0 / 420_000_000.0,
        "feature_basis": current["feature_basis"],
        "baseline_counted": False,
        "baseline_counting_status": "too_close",
        "research_only": True,
    })
    history.append({
        "observation_id": "obs-current",
        "canonical_asset_id": "token-b",
        "coin_id": "token-b",
        "observed_at": NOW.isoformat(),
        "volume_24h": current["volume_24h"],
        "market_cap": current["market_cap"],
        "turnover_24h": current["turnover_24h"],
        "feature_basis": current["feature_basis"],
        "baseline_counted": True,
        "baseline_counting_status": "counted",
        "research_only": True,
    })
    return history


def _route_truth(row: dict) -> dict:
    return {
        key: deepcopy(row.get(key))
        for key in (
            "anomaly_type",
            "anomaly_bucket",
            "market_state_class",
            "priority",
            "priority_components",
            "search_queries",
        )
    }


def _run_scan(namespace, current):
    market_rows = market_anomaly_scanner.load_market_rows(
        "fixtures/event_market_anomaly/market_rows.json"
    )
    market_rows = [
        {
            **row,
            "coin_id": row.get("id"),
            "canonical_asset_id": row.get("id"),
        }
        for row in market_rows
    ]
    market_rows = [
        current if row.get("coin_id") == "token-b" else row
        for row in market_rows
    ]
    history_path = namespace / market_no_send.HISTORY_FILENAME
    market_no_send_io.write_jsonl(history_path, _history_rows(current))
    history_before = history_path.read_bytes()
    scan = market_anomaly_scanner.run_market_anomaly_scan(
        market_rows=market_rows,
        namespace_dir=namespace,
        observed_at=NOW,
        profile="fixture",
        artifact_namespace=namespace.name,
        run_mode="mock_no_send",
        run_id="shadow-run",
    )
    return market_rows, history_path, history_before, scan


def test_shadow_surprise_attaches_only_after_route_and_preserves_authority_bytes(tmp_path):
    namespace = tmp_path / "shadow_post_scan"
    namespace.mkdir()
    current = _current_market_row()
    current_before = deepcopy(current)
    market_rows, history_path, history_before, scan = _run_scan(namespace, current)
    assert scan.anomaly_count == 5
    pre_anomaly = next(row for row in scan.anomalies if row.get("coin_id") == "token-b")
    pre_route = _route_truth(pre_anomaly)
    pre_nested_snapshot = deepcopy(pre_anomaly["market_state_snapshot"])
    assert "shadow_temporal_surprise" not in pre_anomaly
    pre_snapshot_sha = scan.snapshots_sha256
    pre_anomaly_sha = scan.anomalies_sha256
    pre_queue_sha = scan.catalyst_search_queue_sha256
    pre_report_sha = scan.report_sha256

    refreshed = market_no_send_authority.attach_market_no_send_lineage(
        namespace,
        scan_result=scan,
        normalized_rows=market_rows,
        provider="coingecko",
        data_mode="mock",
        request_cache_artifact=market_no_send.REQUEST_CACHE_FILENAME,
        request_ledger_artifact=market_no_send.REQUEST_LEDGER_FILENAME,
        run_id="shadow-run",
        provenance={
            "data_acquisition_mode": "mocked_fixture",
            "candidate_source_mode": "mocked_fixture",
            "decision_radar_campaign_counted": False,
            "burn_in_eligible": False,
            "burn_in_counted": False,
            "provenance_contract_valid": True,
        },
        safety_counters=market_no_send._SAFETY_COUNTERS,
        history_artifact=market_no_send.HISTORY_FILENAME,
        history_sha256=hashlib.sha256(history_before).hexdigest(),
        minimum_shadow_sample_count=8,
    )

    snapshots = market_no_send_io.read_jsonl(refreshed.snapshots_path)
    anomalies = market_no_send_io.read_jsonl(refreshed.anomalies_path)
    queue = market_no_send_io.read_jsonl(refreshed.catalyst_search_queue_path)
    anomaly = next(row for row in anomalies if row.get("coin_id") == "token-b")
    snapshot = next(row for row in snapshots if row.get("coin_id") == "token-b")
    shadow = anomaly["shadow_temporal_surprise"]
    assert shadow["history_artifact"] == market_no_send.HISTORY_FILENAME
    assert shadow["history_artifact_sha256"] == hashlib.sha256(
        history_before
    ).hexdigest()
    assert _route_truth(anomaly) == pre_route
    for key, value in pre_nested_snapshot.items():
        assert anomaly["market_state_snapshot"][key] == value
    assert "shadow_temporal_surprise" not in anomaly["market_state_snapshot"]
    assert snapshot["shadow_temporal_surprise"] == shadow
    assert shadow["routing_eligible"] is False
    assert shadow["priority_eligible"] is False
    assert shadow["decision_score_eligible"] is False
    assert shadow["auto_apply"] is False
    assert shadow["features"]["volume_24h"]["sample_count"] == 8
    assert shadow["features"]["volume_24h"]["robust_z"] is not None
    assert all("shadow_temporal_surprise" not in row for row in queue)
    assert current == current_before
    assert history_path.read_bytes() == history_before
    assert b"shadow_temporal_surprise" not in history_before
    assert refreshed.snapshots_sha256 != pre_snapshot_sha
    assert refreshed.anomalies_sha256 != pre_anomaly_sha
    assert refreshed.catalyst_search_queue_sha256 == pre_queue_sha
    assert refreshed.report_sha256 == pre_report_sha


def test_shadow_enrichment_rolls_back_scanner_bundle_when_history_drifts(
    tmp_path,
    monkeypatch,
):
    namespace = tmp_path / "shadow_history_drift"
    namespace.mkdir()
    current = _current_market_row()
    market_rows, history_path, history_before, scan = _run_scan(namespace, current)
    scanner_paths = (
        scan.snapshots_path,
        scan.anomalies_path,
        scan.catalyst_search_queue_path,
        scan.report_path,
    )
    scanner_before = {path.name: path.read_bytes() for path in scanner_paths}
    real_rename = market_anomaly_receipt.os.rename
    drifted = False

    def drift_history_before_first_bundle_replace(source, target, *args, **kwargs):
        nonlocal drifted
        if (
            not drifted
            and source == market_anomaly_scanner.MARKET_STATE_SNAPSHOT_FILENAME
            and kwargs.get("src_dir_fd") is not None
        ):
            drifted = True
            history_path.write_bytes(history_before + b"\n")
        return real_rename(source, target, *args, **kwargs)

    monkeypatch.setattr(
        market_anomaly_receipt.os,
        "rename",
        drift_history_before_first_bundle_replace,
    )
    with pytest.raises(
        RuntimeError,
        match="market_anomaly_completion_receipt_invalid:artifact_identity",
    ):
        market_no_send_authority.attach_market_no_send_lineage(
            namespace,
            scan_result=scan,
            normalized_rows=market_rows,
            provider="coingecko",
            data_mode="mock",
            request_cache_artifact=market_no_send.REQUEST_CACHE_FILENAME,
            request_ledger_artifact=market_no_send.REQUEST_LEDGER_FILENAME,
            run_id="shadow-run",
            provenance={},
            safety_counters=market_no_send._SAFETY_COUNTERS,
            history_artifact=market_no_send.HISTORY_FILENAME,
            history_sha256=hashlib.sha256(history_before).hexdigest(),
            minimum_shadow_sample_count=8,
        )

    assert drifted is True
    assert history_path.read_bytes() == history_before + b"\n"
    assert {path.name: path.read_bytes() for path in scanner_paths} == scanner_before
    assert {path.name for path in namespace.iterdir()} == {
        market_no_send.HISTORY_FILENAME,
        *scanner_before,
    }


def test_shadow_enrichment_namespace_swap_cannot_mutate_substitute(
    tmp_path,
    monkeypatch,
):
    namespace = tmp_path / "shadow_namespace_swap"
    namespace.mkdir()
    current = _current_market_row()
    market_rows, _history_path, history_before, scan = _run_scan(namespace, current)
    retired = tmp_path / "shadow_namespace_swap_retired"
    original_payloads = market_anomaly_receipt.artifact_payloads
    swapped = False

    def read_then_swap(*args, **kwargs):
        nonlocal swapped
        payloads = original_payloads(*args, **kwargs)
        namespace.rename(retired)
        namespace.mkdir()
        (namespace / "sentinel.txt").write_text(
            "substitute-unchanged\n",
            encoding="utf-8",
        )
        swapped = True
        return payloads

    monkeypatch.setattr(market_anomaly_receipt, "artifact_payloads", read_then_swap)
    with pytest.raises(
        RuntimeError,
        match="market_anomaly_completion_receipt_invalid:namespace_identity",
    ):
        market_no_send_authority.attach_market_no_send_lineage(
            namespace,
            scan_result=scan,
            normalized_rows=market_rows,
            provider="coingecko",
            data_mode="mock",
            request_cache_artifact=market_no_send.REQUEST_CACHE_FILENAME,
            request_ledger_artifact=market_no_send.REQUEST_LEDGER_FILENAME,
            run_id="shadow-run",
            provenance={},
            safety_counters=market_no_send._SAFETY_COUNTERS,
            history_artifact=market_no_send.HISTORY_FILENAME,
            history_sha256=hashlib.sha256(history_before).hexdigest(),
            minimum_shadow_sample_count=8,
        )

    assert swapped is True
    assert tuple(path.name for path in namespace.iterdir()) == ("sentinel.txt",)
    assert (namespace / "sentinel.txt").read_text(encoding="utf-8") == (
        "substitute-unchanged\n"
    )
    assert b"shadow_temporal_surprise" not in (
        retired / market_anomaly_scanner.MARKET_STATE_SNAPSHOT_FILENAME
    ).read_bytes()


def test_shadow_surprise_rejects_nonmatching_history_fingerprint_before_attachment(
    tmp_path,
):
    namespace = tmp_path / "shadow_bad_fingerprint"
    namespace.mkdir()
    current = _current_market_row()
    market_rows, _history_path, _history_before, scan = _run_scan(namespace, current)

    with pytest.raises(
        market_no_send_authority.MarketNoSendError,
        match="history artifact fingerprint mismatch",
    ):
        market_no_send_authority.attach_market_no_send_lineage(
            namespace,
            scan_result=scan,
            normalized_rows=market_rows,
            provider="coingecko",
            data_mode="mock",
            request_cache_artifact=market_no_send.REQUEST_CACHE_FILENAME,
            request_ledger_artifact=market_no_send.REQUEST_LEDGER_FILENAME,
            run_id="shadow-run",
            provenance={},
            safety_counters=market_no_send._SAFETY_COUNTERS,
            history_artifact=market_no_send.HISTORY_FILENAME,
            history_sha256="0" * 64,
            minimum_shadow_sample_count=8,
        )


def test_shadow_surprise_requires_exact_unique_current_history_identity():
    current = _current_market_row()
    history = _history_rows(current)

    with pytest.raises(
        market_no_send_authority.MarketNoSendError,
        match="no unique history row",
    ):
        market_no_send_authority._shadow_surprise_by_observation_id(  # noqa: SLF001
            [current],
            [row for row in history if row["observation_id"] != "obs-current"],
            minimum_sample_count=8,
            history_artifact=market_no_send.HISTORY_FILENAME,
            history_sha256="a" * 64,
        )

    mismatched = deepcopy(history)
    next(
        row for row in mismatched if row["observation_id"] == "obs-current"
    )["canonical_asset_id"] = "different-asset"
    with pytest.raises(
        market_no_send_authority.MarketNoSendError,
        match="observation identity is invalid",
    ):
        market_no_send_authority._shadow_surprise_by_observation_id(  # noqa: SLF001
            [current],
            mismatched,
            minimum_sample_count=8,
            history_artifact=market_no_send.HISTORY_FILENAME,
            history_sha256="a" * 64,
        )

    with pytest.raises(
        market_no_send_authority.MarketNoSendError,
        match="source observation identity is not unique",
    ):
        market_no_send_authority._shadow_surprise_by_observation_id(  # noqa: SLF001
            [current, deepcopy(current)],
            history,
            minimum_sample_count=8,
            history_artifact=market_no_send.HISTORY_FILENAME,
            history_sha256="a" * 64,
        )
