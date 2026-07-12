"""Strict preview and isolated staging tests for observed outcomes."""

from __future__ import annotations

import json
import os
import shutil
import stat
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.outcomes import observed_outcome_operator as operator


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "event_discovery"
CANDIDATE_FIXTURE = FIXTURE_DIR / "observed_outcome_candidate.jsonl"
CORE_FIXTURE = FIXTURE_DIR / "observed_outcome_core.jsonl"
CLOSES_FIXTURE = FIXTURE_DIR / "observed_outcome_dense_ohlcv.json"
EVALUATED_AT = "2026-06-08T12:20:00Z"


def _run(
    candidate_path: Path = CANDIDATE_FIXTURE,
    core_path: Path = CORE_FIXTURE,
    closes_path: Path = CLOSES_FIXTURE,
    **overrides,
):
    kwargs = {
        "profile_assertion": "fixture",
        "artifact_namespace_assertion": "observed-outcome-builder",
    }
    kwargs.update(overrides)
    return operator.run_observed_outcome_operator(
        candidate_path,
        core_path,
        closes_path,
        "candidate-testobs",
        "core-testobs",
        EVALUATED_AT,
        **kwargs,
    )


def _copy_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    candidate = tmp_path / "candidate.jsonl"
    core = tmp_path / "core.jsonl"
    closes = tmp_path / "closes.json"
    shutil.copyfile(CANDIDATE_FIXTURE, candidate)
    shutil.copyfile(CORE_FIXTURE, core)
    shutil.copyfile(CLOSES_FIXTURE, closes)
    return candidate, core, closes


def _jsonl_row(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8").strip())


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _closes_document(path: Path = CLOSES_FIXTURE) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _observed_closes_document() -> dict[str, object]:
    payload = _closes_document()
    payload["schema_version"] = operator.OBSERVED_CLOSES_SCHEMA_VERSION
    rows = payload["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        row["source"] = "binance_spot_ohlcv"
        row["observation_id"] = str(row["observation_id"]).replace(
            "fixture:", "binance:"
        )
    return payload


def test_preview_is_zero_write_synthetic_and_stable(tmp_path):
    candidate, core, closes = _copy_inputs(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    result = _run(candidate, core, closes)

    after = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    assert before == after
    assert result.ok is True
    assert result.mode == "preview"
    assert result.errors == ()
    assert result.written is False
    assert result.candidate_rows_supplied == result.core_rows_supplied == 1
    assert result.observations_supplied == result.observations_accepted == 339
    assert result.outcome is not None
    assert result.outcome["outcome_data_source"] == "synthetic_fixture"
    assert result.outcome["calibration_eligible"] is False
    assert "synthetic_fixture" in result.outcome["calibration_ineligible_reasons"]
    assert schema_v1.validate_row_against_schema(result.outcome, "outcome_row_v1") == []
    telemetry = result.to_dict()
    assert telemetry["ok"] is True
    assert telemetry["notifications_sent"] == telemetry["trades_created"] == 0
    assert telemetry["paper_trades_created"] == 0
    assert telemetry["normal_rsi_signal_rows_written"] == 0
    assert telemetry["triggered_fades_created"] == 0
    assert json.loads(result.to_json()) == telemetry


def test_explicit_observed_document_can_produce_exact_eligible_preview(tmp_path):
    candidate, core, closes = _copy_inputs(tmp_path)
    closes.write_text(
        json.dumps(_observed_closes_document(), sort_keys=True),
        encoding="utf-8",
    )

    result = _run(candidate, core, closes)

    assert result.ok is True
    assert result.outcome is not None
    assert result.outcome["outcome_data_source"] == "observed_market_prices"
    assert result.outcome["calibration_eligible"] is True
    assert result.outcome["include_in_performance"] is True
    assert result.outcome["validation_status"] == "validated"


def test_observed_contract_rejects_fixture_lineage(tmp_path):
    candidate, core, closes = _copy_inputs(tmp_path)
    payload = _closes_document(closes)
    payload["schema_version"] = operator.OBSERVED_CLOSES_SCHEMA_VERSION
    closes.write_text(json.dumps(payload), encoding="utf-8")

    result = _run(candidate, core, closes)

    assert result.ok is False
    assert result.errors == ("observed_closes_claim_fixture_lineage",)
    assert result.outcome is None


def test_exact_authority_selection_and_assertions_fail_closed(tmp_path):
    candidate, core, closes = _copy_inputs(tmp_path)
    missing = operator.run_observed_outcome_operator(
        candidate,
        core,
        closes,
        "missing-candidate",
        "core-testobs",
        EVALUATED_AT,
    )
    assert missing.errors == ("candidate_selection_count_invalid",)

    wrong_core = operator.run_observed_outcome_operator(
        candidate,
        core,
        closes,
        "candidate-testobs",
        "other-core",
        EVALUATED_AT,
    )
    assert "candidate_core_id_mismatch" in wrong_core.errors
    assert "core_selection_count_invalid" in wrong_core.errors

    wrong_context = _run(candidate, core, closes, profile_assertion="other")
    assert wrong_context.errors == ("profile_assertion_mismatch",)
    wrong_namespace = _run(
        candidate,
        core,
        closes,
        artifact_namespace_assertion="other",
    )
    assert wrong_namespace.errors == ("artifact_namespace_assertion_mismatch",)


def test_whole_authority_files_reject_malformed_duplicate_and_unsafe_rows(tmp_path):
    candidate, core, closes = _copy_inputs(tmp_path)
    candidate.write_text(
        '{"candidate_id":"candidate-testobs","candidate_id":"shadow"}\n',
        encoding="utf-8",
    )
    duplicate_key = _run(candidate, core, closes)
    assert duplicate_key.errors == ("candidate_jsonl_invalid",)

    shutil.copyfile(CANDIDATE_FIXTURE, candidate)
    candidate.write_text(
        candidate.read_text(encoding="utf-8") + "{}\n",
        encoding="utf-8",
    )
    invalid_unrelated = _run(candidate, core, closes)
    assert invalid_unrelated.errors == ("candidate_authority_file_invalid",)

    candidate.unlink()
    candidate.symlink_to(CANDIDATE_FIXTURE)
    symlink = _run(candidate, core, closes)
    assert symlink.errors == ("candidate_path_unsafe",)


def test_evaluation_clock_is_explicit_aware_and_not_future(monkeypatch):
    monkeypatch.setattr(
        operator,
        "_utc_now",
        lambda: datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc),
    )
    naive = operator.run_observed_outcome_operator(
        CANDIDATE_FIXTURE,
        CORE_FIXTURE,
        CLOSES_FIXTURE,
        "candidate-testobs",
        "core-testobs",
        "2026-06-08T12:20:00",
    )
    assert naive.errors == ("evaluated_at_invalid",)

    future = operator.run_observed_outcome_operator(
        CANDIDATE_FIXTURE,
        CORE_FIXTURE,
        CLOSES_FIXTURE,
        "candidate-testobs",
        "core-testobs",
        "2026-07-12T12:00:00.000001Z",
    )
    assert future.errors == ("evaluated_at_in_future",)


def test_close_document_contract_rejects_unknown_bad_ohlcv_and_ambiguity(tmp_path):
    candidate, core, closes = _copy_inputs(tmp_path)
    payload = _closes_document(closes)
    payload["unknown"] = True
    closes.write_text(json.dumps(payload), encoding="utf-8")
    assert _run(candidate, core, closes).errors == ("closes_document_invalid",)

    payload = _closes_document()
    rows = payload["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    rows[0]["close"] = True
    closes.write_text(json.dumps(payload), encoding="utf-8")
    assert _run(candidate, core, closes).errors == ("closes_rows_invalid",)

    payload = _closes_document()
    rows = payload["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict) and isinstance(rows[1], dict)
    rows[1]["observation_id"] = rows[0]["observation_id"]
    closes.write_text(json.dumps(payload), encoding="utf-8")
    assert _run(candidate, core, closes).errors == ("closes_rows_ambiguous",)


def test_outcome_projection_blocks_secret_values_and_drops_core_debug_paths(tmp_path):
    candidate, core, closes = _copy_inputs(tmp_path)
    candidate_row = _jsonl_row(candidate)
    candidate_row["provider"] = "Bearer abcdefghijklmnopqrstuvwxyz"
    _write_jsonl(candidate, [candidate_row])

    secret = _run(candidate, core, closes)
    assert secret.errors == ("outcome_secret_like_value_forbidden",)
    assert secret.outcome is None
    assert "Bearer" not in secret.to_json()

    candidate_row["provider"] = "fixture-provider"
    candidate_row["providers"] = [{"token": "ghp_abcdefghijklmnopqrstuvwx"}]
    _write_jsonl(candidate, [candidate_row])
    nested_secret = _run(candidate, core, closes)
    assert nested_secret.errors == ("outcome_secret_like_value_forbidden",)
    assert nested_secret.outcome is None
    assert "ghp_" not in nested_secret.to_json()

    shutil.copyfile(CANDIDATE_FIXTURE, candidate)
    core_row = _jsonl_row(core)
    core_row["card_path_abs_debug"] = "/Users/example/private/card.md"
    _write_jsonl(core, [core_row])
    projected = _run(candidate, core, closes)
    assert projected.ok is True
    assert projected.outcome is not None
    assert "/Users/" not in json.dumps(projected.outcome)
    assert "core_card_path_abs_debug" not in projected.outcome

    candidate_row = _jsonl_row(candidate)
    candidate_row["provider"] = "/etc/private-provider"
    _write_jsonl(candidate, [candidate_row])
    absolute = _run(candidate, core, closes)
    assert absolute.errors == ("outcome_absolute_path_forbidden",)
    assert absolute.outcome is None
    assert "/etc/private-provider" not in absolute.to_json()

    candidate_row["provider"] = float("nan")
    _write_jsonl(candidate, [candidate_row])
    nonfinite = _run(candidate, core, closes)
    assert nonfinite.errors == ("candidate_jsonl_invalid",)
    assert nonfinite.outcome is None


def test_staging_is_confirm_gated_create_only_atomic_and_mode_0600(tmp_path):
    candidate, core, closes = _copy_inputs(tmp_path)
    target = tmp_path.resolve() / "staged-outcome.jsonl"

    no_confirm = _run(candidate, core, closes, out_path=target)
    assert no_confirm.errors == ("confirmation_required",)
    assert target.exists() is False
    confirm_without_output = _run(candidate, core, closes, confirm=True)
    assert confirm_without_output.errors == ("confirmation_without_output",)

    staged = _run(candidate, core, closes, out_path=target, confirm=True)
    assert staged.ok is True
    assert staged.mode == "stage"
    assert staged.written is True
    assert target.exists()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    persisted = json.loads(lines[0])
    assert persisted == staged.outcome
    assert schema_v1.validate_row_against_schema(persisted, "outcome_row_v1") == []
    assert not list(tmp_path.glob(".staged-outcome.jsonl.*.tmp"))
    assert not list(tmp_path.glob(".event_alpha_observed_outcome_*.lock"))

    repeated = _run(candidate, core, closes, out_path=target, confirm=True)
    assert repeated.errors == ("output_target_exists",)
    assert target.read_text(encoding="utf-8").splitlines() == lines


def test_staging_rejects_relative_canonical_configured_and_symlink_paths(
    tmp_path,
    monkeypatch,
):
    from crypto_rsi_scanner import config

    candidate, core, closes = _copy_inputs(tmp_path)
    real_tmp = tmp_path.resolve()
    relative = _run(
        candidate,
        core,
        closes,
        out_path=Path("relative-stage.jsonl"),
        confirm=True,
    )
    assert relative.errors == ("output_path_must_be_absolute",)

    canonical = _run(
        candidate,
        core,
        closes,
        out_path=real_tmp / "event_alpha_outcomes.jsonl",
        confirm=True,
    )
    assert canonical.errors == ("output_canonical_name_forbidden",)
    canonical_case = _run(
        candidate,
        core,
        closes,
        out_path=real_tmp / "EVENT_ALPHA_OUTCOMES.JSONL",
        confirm=True,
    )
    assert canonical_case.errors == ("output_canonical_name_forbidden",)

    configured = tmp_path / "configured"
    configured.mkdir()
    monkeypatch.setattr(config, "EVENT_ALPHA_ARTIFACT_BASE_DIR", configured)
    monkeypatch.setattr(config, "EVENT_DISCOVERY_CACHE_DIR", configured)
    under_root = _run(
        candidate,
        core,
        closes,
        out_path=configured / "stage.jsonl",
        confirm=True,
    )
    assert under_root.errors == ("output_configured_root_forbidden",)

    referent = tmp_path / "referent.jsonl"
    referent.write_text("safe\n", encoding="utf-8")
    linked = tmp_path / "linked.jsonl"
    linked.symlink_to(referent)
    symlink = _run(candidate, core, closes, out_path=linked, confirm=True)
    assert symlink.errors == ("output_target_exists",)

    real_parent = real_tmp / "real-parent"
    real_parent.mkdir()
    alias_parent = real_tmp / "alias-parent"
    alias_parent.symlink_to(real_parent, target_is_directory=True)
    parent_alias = _run(
        candidate,
        core,
        closes,
        out_path=alias_parent / "stage.jsonl",
        confirm=True,
    )
    assert parent_alias.errors == ("output_parent_unsafe",)


def test_staging_fails_closed_when_configured_roots_cannot_be_resolved(
    tmp_path,
    monkeypatch,
):
    candidate, core, closes = _copy_inputs(tmp_path)

    def fail_context(*_args, **_kwargs):
        raise ValueError("simulated")

    monkeypatch.setattr(operator.artifact_context, "context_from_profile", fail_context)
    target = tmp_path.resolve() / "stage.jsonl"
    result = _run(candidate, core, closes, out_path=target, confirm=True)
    assert result.errors == ("output_configured_roots_unverifiable",)
    assert not target.exists()


def test_atomic_publish_failure_leaves_no_target_or_temporary_file(tmp_path, monkeypatch):
    candidate, core, closes = _copy_inputs(tmp_path)
    target = tmp_path.resolve() / "failed-stage.jsonl"

    def fail_link(*_args, **_kwargs):
        raise OSError("simulated")

    monkeypatch.setattr(operator.os, "link", fail_link)
    result = _run(candidate, core, closes, out_path=target, confirm=True)

    assert result.errors == ("output_write_failed",)
    assert result.written is False
    assert not target.exists()
    assert not list(tmp_path.glob(".failed-stage.jsonl.*.tmp"))
    assert not list(tmp_path.glob(".event_alpha_observed_outcome_*.lock"))


def test_result_errors_are_payload_free_and_sorted(tmp_path):
    candidate, core, closes = _copy_inputs(tmp_path)
    result = operator.run_observed_outcome_operator(
        candidate,
        core,
        closes,
        " bad ",
        " bad-core ",
        "not-a-time",
        profile_assertion=" bad-profile ",
        artifact_namespace_assertion=" bad-namespace ",
    )
    assert result.errors == tuple(sorted(result.errors))
    assert result.outcome is None
    text = result.to_json()
    assert str(tmp_path) not in text
    assert "not-a-time" not in text
    assert "bad-profile" not in text
    assert result.to_dict()["notifications_sent"] == 0


def test_invalid_input_and_output_path_types_return_closed_errors(tmp_path):
    invalid_input = operator.run_observed_outcome_operator(
        None,  # type: ignore[arg-type]
        CORE_FIXTURE,
        CLOSES_FIXTURE,
        "candidate-testobs",
        "core-testobs",
        EVALUATED_AT,
    )
    assert invalid_input.errors == ("candidate_path_invalid",)

    invalid_output = _run(
        out_path=object(),  # type: ignore[arg-type]
        confirm=True,
    )
    assert invalid_output.errors == ("output_path_invalid",)


def test_future_price_rows_are_accepted_but_never_selected_past_evaluation():
    result = operator.run_observed_outcome_operator(
        CANDIDATE_FIXTURE,
        CORE_FIXTURE,
        CLOSES_FIXTURE,
        "candidate-testobs",
        "core-testobs",
        "2026-06-01T13:20:00Z",
    )
    assert result.ok is True
    assert result.observations_accepted == 339
    assert result.outcome is not None
    assert result.outcome["horizon_metadata"]["4h"]["maturity_status"] == "pending"
    assert result.outcome["horizon_metadata"]["4h"]["price_observed_at"] is None
