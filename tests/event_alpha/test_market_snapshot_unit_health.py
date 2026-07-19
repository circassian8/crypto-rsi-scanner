"""Closed market snapshot unit-health manifest and doctor regressions."""

from __future__ import annotations

import json
from types import SimpleNamespace

from crypto_rsi_scanner.event_alpha.doctor.checks import market_snapshot_units
from crypto_rsi_scanner.event_alpha.operations import market_no_send_features


def _row(*warnings: object) -> dict[str, object]:
    return {
        "market_state_snapshot": {
            "unit_warnings": list(warnings),
            "market_data_quality": {
                "baseline_status": "warming",
                "direct_feature_count": 4,
                "proxy_feature_count": 1,
            },
        }
    }


def _manifest(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "contract_version": 2,
        "row_type": "event_market_no_send_generation",
        "status": "complete",
        "data_acquisition_mode": "live_provider",
        "observed_at": "2026-07-19T00:00:00Z",
        "market_snapshot_count": len(rows),
        **market_no_send_features.market_quality_counts_from_rows(rows),
    }


def test_clean_unit_health_is_closed_and_strict_valid():
    rows = [_row(), _row()]
    manifest = _manifest(rows)

    assert manifest["market_snapshot_unit_validation_contract_version"] == 1
    assert manifest["market_snapshot_unit_validation_status"] == "clean"
    assert manifest["market_snapshot_unit_warning_row_count"] == 0
    assert manifest["market_snapshot_unit_warning_count"] == 0
    assert manifest["market_snapshot_unit_warning_counts"] == {}
    assert market_snapshot_units.validate_snapshot_unit_health(manifest, rows) == ()


def test_empty_unit_health_is_explicitly_not_evaluated():
    quality = market_no_send_features.market_quality_counts_from_rows([])

    assert quality["market_snapshot_unit_validation_contract_version"] == 1
    assert quality["market_snapshot_unit_validation_status"] == "not_evaluated"
    assert quality["market_snapshot_unit_warning_row_count"] == 0
    assert quality["market_snapshot_unit_warning_count"] == 0
    assert quality["market_snapshot_unit_warning_counts"] == {}


def test_any_unit_warning_blocks_new_manifest_contract():
    rows = [
        _row("implausible_normalized_return:return_4h"),
        _row("implausible_normalized_return:return_4h", "return_unit_missing:return_1h"),
    ]
    manifest = _manifest(rows)

    assert manifest["market_snapshot_unit_validation_status"] == "blocked"
    assert manifest["market_snapshot_unit_warning_row_count"] == 2
    assert manifest["market_snapshot_unit_warning_count"] == 3
    assert manifest["market_snapshot_unit_warning_counts"] == {
        "implausible_normalized_return:return_4h": 2,
        "return_unit_missing:return_1h": 1,
    }
    assert market_snapshot_units.validate_snapshot_unit_health(manifest, rows) == (
        "market_snapshot_unit_validation_failed:warning_rows=2,warnings=3",
    )


def test_manifest_drift_and_malformed_warning_shape_fail_closed():
    rows = [{"market_state_snapshot": {"unit_warnings": "not-a-list"}}]
    manifest = _manifest(rows)
    manifest["market_snapshot_unit_warning_count"] = 0

    errors = market_snapshot_units.validate_snapshot_unit_health(manifest, rows)

    assert (
        "market_snapshot_unit_validation_manifest_mismatch:"
        "market_snapshot_unit_warning_count"
    ) in errors
    assert "market_snapshot_unit_validation_failed:warning_rows=1,warnings=1" in errors


def test_contract_activation_preserves_old_evidence_but_closes_future_live_rows():
    base = {
        "contract_version": 2,
        "row_type": "event_market_no_send_generation",
        "status": "complete",
        "data_acquisition_mode": "live_provider",
        "market_snapshot_count": 1,
    }

    assert market_snapshot_units.validate_snapshot_unit_health(
        {**base, "observed_at": "2026-07-18T23:59:59Z"},
        [_row()],
    ) == ()
    assert market_snapshot_units.validate_snapshot_unit_health(
        {**base, "observed_at": "2026-07-19T00:00:00Z"},
        [_row()],
    ) == ("market_snapshot_unit_validation_contract_missing",)
    assert market_snapshot_units.validate_snapshot_unit_health(
        {
            **base,
            "data_acquisition_mode": "mocked_fixture",
            "observed_at": "2026-07-19T00:00:00Z",
        },
        [_row()],
    ) == ()


def test_bool_contract_marker_and_snapshot_count_are_rejected():
    rows = [_row()]
    manifest = _manifest(rows)
    manifest["market_snapshot_unit_validation_contract_version"] = True
    assert market_snapshot_units.validate_snapshot_unit_health(manifest, rows) == (
        "market_snapshot_unit_validation_contract_invalid",
    )

    manifest = _manifest(rows)
    manifest["market_snapshot_count"] = 2
    assert "market_snapshot_unit_validation_snapshot_count_mismatch" in (
        market_snapshot_units.validate_snapshot_unit_health(manifest, rows)
    )


def test_doctor_plugin_emits_registered_blocker_for_warning_rows(tmp_path):
    rows = [_row("return_unit_missing:return_1h")]
    (tmp_path / "event_market_no_send_generation.json").write_text(
        json.dumps(_manifest(rows)),
        encoding="utf-8",
    )
    (tmp_path / "event_market_state_snapshots.jsonl").write_text(
        json.dumps(rows[0]) + "\n",
        encoding="utf-8",
    )
    blockers: list[str] = []

    market_snapshot_units.apply_checks(
        SimpleNamespace(namespace_dir=tmp_path),
        blockers,
    )

    assert any("market_snapshot_unit_validation_failed" in item for item in blockers)
    assert any(item.startswith("namespace.operator_artifact_coherence:") for item in blockers)
