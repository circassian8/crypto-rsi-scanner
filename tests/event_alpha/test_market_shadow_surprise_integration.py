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
    market_observation_campaign_shadow_surprise,
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
        "price": row["current_price"],
        "volume_24h": 125_000_000.0,
        "turnover_24h": 125_000_000.0 / 420_000_000.0,
        "market_history_observation_id": "obs-current",
        "feature_basis": {
            "price": "provider_observed",
            "volume_24h": "provider_observed",
            "market_cap": "provider_observed",
            "turnover_24h": "derived_provider_ratio",
        },
    })
    return row


def _history_rows(current: dict) -> list[dict]:
    history: list[dict] = []
    for offset in range(9, 0, -1):
        volume = float(45_000_000 + (9 - offset) * 5_000_000)
        history.append({
            "observation_id": f"obs-prior-{offset}",
            "canonical_asset_id": "token-b",
            "coin_id": "token-b",
            "observed_at": (NOW - timedelta(hours=offset)).isoformat(),
            "price": 1.70 + (9 - offset) * 0.01,
            "volume_24h": volume,
            "market_cap": 420_000_000.0,
            "turnover_24h": volume / 420_000_000.0,
            "feature_basis": {
                "price": "provider_observed",
                "volume_24h": "provider_observed",
                "market_cap": "provider_observed",
                "turnover_24h": "derived_provider_ratio",
            },
            "baseline_counted": True,
            "baseline_counting_status": "counted",
            "research_only": True,
        })
    for asset_id, start_price, hourly_change in (
        ("bitcoin", 65_000.0, 17.0),
        ("ethereum", 3_400.0, 2.0),
    ):
        for offset in range(9, -1, -1):
            history.append({
                "observation_id": f"{asset_id}-obs-{offset}",
                "canonical_asset_id": asset_id,
                "coin_id": asset_id,
                "observed_at": (NOW - timedelta(hours=offset)).isoformat(),
                "price": start_price + (9 - offset) * hourly_change,
                "volume_24h": 1_000_000_000.0,
                "market_cap": 10_000_000_000.0,
                "turnover_24h": 0.1,
                "feature_basis": {
                    "price": "provider_observed",
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
        "price": current["price"],
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


def _campaign_history_snapshot(rows: list[dict], *, seed: bytes = b"history") -> dict:
    return {
        "rows": tuple(deepcopy(rows)),
        "status": "observed" if rows else "observed_empty",
        "artifact": market_no_send.HISTORY_FILENAME,
        "sha256": hashlib.sha256(seed).hexdigest(),
        "size_bytes": len(seed),
        "row_count": len(rows),
        "binding_source": "campaign_market_history_exact_bytes",
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
    assert shadow["schema_version"] == 4
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
    assert shadow["features"]["volume_24h"]["sample_count"] == 9
    assert shadow["features"]["volume_24h"]["robust_z"] is not None
    assert shadow["return_features"]["return_1h"]["status"] == "ready"
    assert shadow["return_features"]["return_1h"]["current_value"] > 0
    assert shadow["return_features"]["relative_return_vs_btc_1h"][
        "status"
    ] == "ready"
    assert all("shadow_temporal_surprise" not in row for row in queue)
    assert current == current_before
    assert history_path.read_bytes() == history_before
    assert b"shadow_temporal_surprise" not in history_before
    assert refreshed.snapshots_sha256 != pre_snapshot_sha
    assert refreshed.anomalies_sha256 != pre_anomaly_sha
    assert refreshed.catalyst_search_queue_sha256 == pre_queue_sha
    assert refreshed.report_sha256 == pre_report_sha


def test_shadow_enrichment_fails_closed_without_path_rollback_when_history_drifts(
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
            and target == market_anomaly_scanner.MARKET_STATE_SNAPSHOT_FILENAME
            and isinstance(source, str)
            and source.endswith(".tmp")
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
    assert scan.snapshots_path.read_bytes() != scanner_before[scan.snapshots_path.name]
    assert {
        path.name: path.read_bytes() for path in scanner_paths[1:]
    } == {
        path.name: scanner_before[path.name] for path in scanner_paths[1:]
    }
    retained_stages = tuple(
        path for path in namespace.iterdir() if path.name.endswith(".tmp")
    )
    assert len(retained_stages) == 3
    assert {path.name for path in namespace.iterdir()} == {
        market_no_send.HISTORY_FILENAME,
        *scanner_before,
        *(path.name for path in retained_stages),
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


def test_campaign_shadow_replay_accounts_for_exact_history_without_policy_effects():
    rows = _history_rows(_current_market_row())

    audit = (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            _campaign_history_snapshot(rows),
            minimum_sample_count=4,
        )
    )

    assert audit["schema_id"] == (
        "decision_radar.shadow_temporal_surprise_campaign_audit"
    )
    assert audit["schema_version"] == 5
    assert audit["shadow_schema_version"] == 4
    assert audit["input_row_count"] == 31
    assert audit["excluded_not_baseline_counted_count"] == 1
    assert audit["input_rejected_count"] == 0
    assert audit["valid_baseline_counted_row_count"] == 30
    assert audit["evaluated_observation_count"] == 30
    assert audit["evaluation_error_count"] == 0
    assert audit["asset_count"] == 3
    assert audit["feature_coverage"]["return_1h"]["ready_count"] > 0
    assert audit["feature_coverage"]["relative_return_vs_btc_1h"][
        "ready_count"
    ] > 0
    assert audit["feature_coverage"]["return_24h"]["ready_count"] == 0
    volume_distribution = audit["feature_coverage"]["volume_24h"]
    assert volume_distribution["distribution_ready_count"] == (
        volume_distribution["ready_count"]
    )
    assert volume_distribution["descriptive_quantile_method"] == (
        "linear_interpolation_sorted_ready_values"
    )
    assert volume_distribution["descriptive_tail_rank_kind"] == "upper"
    assert volume_distribution["tail_ranks_are_p_values"] is False
    assert volume_distribution["overlapping_samples_are_independent"] is False
    assert volume_distribution["variation_observation_basis"] == (
        "closed_shadow_v4_projection_meeting_existing_minimum_sample_count"
    )
    assert volume_distribution["variation_observation_count"] > 0
    assert volume_distribution["minimum_distinct_baseline_value_count"] is None
    assert volume_distribution["variation_diagnostics_are_policy"] is False
    assert volume_distribution["effective_sample_size_claimed"] is False
    assert 0.0 < volume_distribution[
        "distinct_baseline_value_ratio_minimum"
    ] <= volume_distribution[
        "distinct_baseline_value_ratio_median"
    ] <= volume_distribution[
        "distinct_baseline_value_ratio_p95"
    ] <= volume_distribution[
        "distinct_baseline_value_ratio_maximum"
    ] <= 1.0
    assert 0.0 < volume_distribution[
        "maximum_baseline_value_tie_ratio_minimum"
    ] <= volume_distribution[
        "maximum_baseline_value_tie_ratio_median"
    ] <= volume_distribution[
        "maximum_baseline_value_tie_ratio_p95"
    ] <= volume_distribution[
        "maximum_baseline_value_tie_ratio_maximum"
    ] <= 1.0
    minimum_distinct = volume_distribution[
        "minimum_distinct_baseline_value_ratio_observation"
    ]
    assert minimum_distinct["distinct_baseline_value_ratio"] == (
        volume_distribution["distinct_baseline_value_ratio_minimum"]
    )
    assert minimum_distinct["sample_count"] >= 4
    assert volume_distribution["robust_z_minimum"] <= (
        volume_distribution["robust_z_p05"]
    ) <= volume_distribution["robust_z_median"] <= (
        volume_distribution["robust_z_p95"]
    ) <= volume_distribution["robust_z_maximum"]
    assert 0.0 < volume_distribution["descriptive_tail_rank_minimum"] <= (
        volume_distribution["descriptive_tail_rank_median"]
    ) <= volume_distribution["descriptive_tail_rank_p95"] <= (
        volume_distribution["descriptive_tail_rank_maximum"]
    ) <= 1.0
    assert set(volume_distribution["minimum_robust_z_observation"]) == {
        "canonical_asset_id",
        "observation_id",
        "observed_at",
    }
    return_distribution = audit["feature_coverage"]["return_1h"]
    assert return_distribution["descriptive_tail_rank_kind"] == "two_sided"
    unavailable_distribution = audit["feature_coverage"]["return_24h"]
    assert unavailable_distribution["distribution_ready_count"] == 0
    assert unavailable_distribution["variation_observation_count"] == 0
    assert unavailable_distribution[
        "distinct_baseline_value_ratio_median"
    ] is None
    assert unavailable_distribution[
        "minimum_distinct_baseline_value_ratio_observation"
    ] is None
    assert unavailable_distribution["robust_z_median"] is None
    assert unavailable_distribution[
        "minimum_descriptive_tail_rank_observation"
    ] is None
    assert audit["all_features_have_ready_evidence"] is False
    assert audit["status"] == "warming"
    assert audit["statistical_independence_claimed"] is False
    assert audit["routing_eligible"] is False
    assert audit["decision_score_eligible"] is False
    assert audit["threshold_change_eligible"] is False
    assert audit["protocol_v2_evidence_eligible"] is False
    assert audit["historical_rows_rewritten"] is False
    assert audit["provider_calls"] == audit["writes"] == 0
    assert len(audit["asset_variation_summaries"]) == 3
    bitcoin_variation = next(
        row
        for row in audit["asset_variation_summaries"]
        if row["canonical_asset_id"] == "bitcoin"
    )
    assert bitcoin_variation["source_context_is_causal_attribution"] is False
    assert bitcoin_variation["retained_provider_counts"] == {"unavailable": 10}
    assert bitcoin_variation["retained_feature_basis_counts"]["volume_24h"] == {
        "provider_observed": 10
    }
    assert bitcoin_variation["feature_with_repeated_baseline_value_count"] > 0
    bitcoin_volume = bitcoin_variation["feature_variation"]["volume_24h"]
    assert bitcoin_volume["variation_observation_count"] == 6
    assert bitcoin_volume["repeated_baseline_value_observation_count"] == 6
    assert bitcoin_volume["all_distinct_baseline_value_observation_count"] == 0
    assert bitcoin_volume["descriptive_repetition_observation_share"] == 1.0
    assert bitcoin_volume["distinct_baseline_value_ratio_minimum"] == round(1 / 9, 12)
    assert bitcoin_volume["maximum_baseline_value_tie_ratio_maximum"] == 1.0
    assert bitcoin_volume["latest_variation_observation"]["sample_count"] == 9
    assert bitcoin_volume["variation_diagnostics_are_policy"] is False
    assert bitcoin_volume["effective_sample_size_claimed"] is False
    assert bitcoin_volume["input_trace_observation_count"] == 6
    assert bitcoin_volume["input_trace_status_counts"] == {
        "source_tuple_repetition": 6
    }
    assert bitcoin_volume["source_tuple_repetition_observation_count"] == 6
    assert bitcoin_volume["transform_collision_observation_count"] == 0
    assert bitcoin_volume["mixed_source_and_transform_observation_count"] == 0
    assert bitcoin_volume["source_value_tuple_kind_counts"] == {
        "provider_volume_value": 6
    }
    assert bitcoin_volume[
        "maximum_source_value_tuple_repeat_excess_count"
    ] == 8
    assert bitcoin_volume[
        "maximum_transform_collision_distinct_value_loss_count"
    ] == 0
    assert bitcoin_volume["maximum_consecutive_source_value_tuple_count"] == 9
    assert bitcoin_volume["maximum_consecutive_derived_value_count"] == 9
    assert bitcoin_volume["latest_input_trace_observation"][
        "input_trace_status"
    ] == "source_tuple_repetition"
    assert bitcoin_volume["input_trace_diagnostics_are_policy"] is False
    assert bitcoin_volume["provider_causation_claimed"] is False
    assert len(bitcoin_volume["input_trace_projection_digest"]) == 64
    assert (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(audit)
    ) == []


def test_campaign_shadow_replay_causal_digest_ignores_later_source_rows():
    rows = _history_rows(_current_market_row())
    before = (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            _campaign_history_snapshot(rows, seed=b"before"),
            minimum_sample_count=4,
        )
    )
    future = deepcopy(next(
        row for row in rows if row["observation_id"] == "obs-current"
    ))
    future.update({
        "observation_id": "obs-future",
        "observed_at": (NOW + timedelta(hours=1)).isoformat(),
        "price": float(future["price"]) * 1.01,
    })
    after = (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            _campaign_history_snapshot([*rows, future], seed=b"after"),
            minimum_sample_count=4,
        )
    )
    before_asset = next(
        row
        for row in before["asset_projection_summaries"]
        if row["canonical_asset_id"] == "token-b"
    )
    after_asset = next(
        row
        for row in after["asset_projection_summaries"]
        if row["canonical_asset_id"] == "token-b"
    )

    assert before_asset["first_causal_projection_sha256"] == after_asset[
        "first_causal_projection_sha256"
    ]
    assert before_asset["first_source_bound_projection_sha256"] != after_asset[
        "first_source_bound_projection_sha256"
    ]
    assert after_asset["evaluated_observation_count"] == (
        before_asset["evaluated_observation_count"] + 1
    )


def test_campaign_shadow_replay_rejects_duplicate_identity_and_closes_counts():
    rows = _history_rows(_current_market_row())
    rows.append(deepcopy(rows[0]))

    audit = (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            _campaign_history_snapshot(rows),
            minimum_sample_count=4,
        )
    )

    assert audit["status"] == "partial"
    assert audit["input_rejected_count"] == 2
    assert audit["input_rejection_reason_counts"] == {
        "duplicate_observation_id": 2
    }
    assert audit["input_row_count"] == (
        audit["excluded_not_baseline_counted_count"]
        + audit["input_rejected_count"]
        + audit["valid_baseline_counted_row_count"]
    )
    assert (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(audit)
    ) == []


def test_campaign_shadow_replay_validator_rejects_policy_and_count_drift():
    audit = (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            _campaign_history_snapshot(_history_rows(_current_market_row())),
            minimum_sample_count=4,
        )
    )
    tampered = deepcopy(audit)
    tampered["routing_eligible"] = True
    tampered["evaluated_observation_count"] += 1

    errors = (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(tampered)
    )

    assert "routing_eligible_must_be_false" in errors
    assert "evaluation_count_not_closed" in errors
    assert "projection_status_count_total_mismatch" in errors


def test_campaign_shadow_replay_validator_rejects_distribution_drift():
    audit = (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            _campaign_history_snapshot(_history_rows(_current_market_row())),
            minimum_sample_count=4,
        )
    )
    tampered = deepcopy(audit)
    volume = tampered["feature_coverage"]["volume_24h"]
    volume["robust_z_p95"] = volume["robust_z_minimum"] - 1.0
    volume["tail_ranks_are_p_values"] = True

    errors = (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(tampered)
    )

    assert (
        "feature_coverage_volume_24h_robust_z_distribution_order_invalid"
        in errors
    )
    assert (
        "feature_coverage_volume_24h_tail_rank_p_value_claim_invalid"
        in errors
    )


def test_campaign_shadow_replay_validator_rejects_variation_drift():
    audit = (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            _campaign_history_snapshot(_history_rows(_current_market_row())),
            minimum_sample_count=4,
        )
    )
    tampered = deepcopy(audit)
    volume = tampered["feature_coverage"]["volume_24h"]
    volume["distinct_baseline_value_ratio_p05"] = 1.1
    volume["variation_diagnostics_are_policy"] = True
    volume["minimum_distinct_baseline_value_ratio_observation"][
        "distinct_baseline_value_count"
    ] += 1

    errors = (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(tampered)
    )

    assert (
        "feature_coverage_volume_24h_distinct_ratio_distribution_invalid"
        in errors
    )
    assert (
        "feature_coverage_volume_24h_variation_policy_claim_invalid"
        in errors
    )
    assert (
        "feature_coverage_volume_24h_minimum_distinct_ratio_reference_invalid"
        in errors
    )


def test_campaign_shadow_replay_validator_rejects_asset_attribution_drift():
    audit = (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            _campaign_history_snapshot(_history_rows(_current_market_row())),
            minimum_sample_count=4,
        )
    )
    tampered = deepcopy(audit)
    bitcoin = next(
        row
        for row in tampered["asset_variation_summaries"]
        if row["canonical_asset_id"] == "bitcoin"
    )
    bitcoin["retained_provider_counts"] = {"coingecko": 9}
    bitcoin["source_context_is_causal_attribution"] = True
    bitcoin["feature_variation"]["volume_24h"][
        "descriptive_repetition_observation_share"
    ] = 0.5

    errors = (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(tampered)
    )

    assert "asset_variation_0_retained_provider_counts_count_total_mismatch" in errors
    assert "asset_variation_0_source_attribution_claim_invalid" in errors
    assert (
        "asset_variation_bitcoin_volume_24h_repetition_share_invalid"
        in errors
    )


def test_campaign_shadow_replay_validator_rejects_input_trace_drift():
    audit = (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            _campaign_history_snapshot(_history_rows(_current_market_row())),
            minimum_sample_count=4,
        )
    )
    tampered = deepcopy(audit)
    bitcoin = next(
        row
        for row in tampered["asset_variation_summaries"]
        if row["canonical_asset_id"] == "bitcoin"
    )
    volume = bitcoin["feature_variation"]["volume_24h"]
    volume["transform_collision_observation_count"] = 2
    volume["latest_input_trace_observation"][
        "source_value_tuple_repeat_excess_count"
    ] = 0
    volume["provider_causation_claimed"] = True

    errors = (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(tampered)
    )

    assert (
        "asset_variation_bitcoin_volume_24h_transform_collision_count_invalid"
        in errors
    )
    assert (
        "asset_variation_bitcoin_volume_24h_latest_input_trace_invalid"
        in errors
    )
    assert (
        "asset_variation_bitcoin_volume_24h_provider_causation_claim_invalid"
        in errors
    )


def test_campaign_shadow_replay_keeps_v1_through_v4_audits_readable():
    current = (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            _campaign_history_snapshot(_history_rows(_current_market_row())),
            minimum_sample_count=4,
        )
    )
    legacy_v4 = deepcopy(current)
    legacy_v4["schema_version"] = 4
    legacy_v4["shadow_schema_version"] = 3
    for asset in legacy_v4["asset_variation_summaries"]:
        for feature in asset["feature_variation"].values():
            for key in tuple(feature):
                if key not in (
                    market_observation_campaign_shadow_surprise
                    ._ASSET_FEATURE_VARIATION_KEYS_V4  # noqa: SLF001
                ):
                    feature.pop(key)
    assert (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(legacy_v4)
    ) == []

    legacy_v3 = deepcopy(legacy_v4)
    legacy_v3["schema_version"] = 3
    legacy_v3.pop("asset_variation_summaries")
    assert (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(legacy_v3)
    ) == []

    legacy_v2 = deepcopy(legacy_v3)
    legacy_v2["schema_version"] = 2
    for coverage in legacy_v2["feature_coverage"].values():
        for key in tuple(coverage):
            if key not in (
                market_observation_campaign_shadow_surprise
                ._FEATURE_COVERAGE_KEYS_V2  # noqa: SLF001
            ):
                coverage.pop(key)
    assert (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(legacy_v2)
    ) == []

    legacy_v1 = deepcopy(legacy_v2)
    legacy_v1["schema_version"] = 1
    legacy_v1["shadow_schema_version"] = 2
    for coverage in legacy_v1["feature_coverage"].values():
        for key in tuple(coverage):
            if key not in (
                market_observation_campaign_shadow_surprise
                ._FEATURE_COVERAGE_KEYS_V1  # noqa: SLF001
            ):
                coverage.pop(key)
    assert (
        market_observation_campaign_shadow_surprise
        .validate_campaign_shadow_surprise_audit(legacy_v1)
    ) == []
