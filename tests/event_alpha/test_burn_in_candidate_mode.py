"""Candidate-mode burn-in operation tests."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from crypto_rsi_scanner.event_alpha.operations import (
    common,
    daily_burn_in,
    daily_burn_in_plan,
    daily_burn_in_readiness,
    review_inbox,
    scorecard,
    source_yield,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def test_daily_burn_in_candidate_mode_no_provider_config_is_safe(tmp_path, monkeypatch):
    monkeypatch.delenv("RSI_EVENT_DISCOVERY_COINALYZE_API_KEY", raising=False)
    monkeypatch.delenv("RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT", raising=False)
    monkeypatch.delenv("RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT", raising=False)
    monkeypatch.setattr(daily_burn_in.config, "EVENT_DISCOVERY_COINALYZE_API_KEY", "", raising=False)
    monkeypatch.setattr(daily_burn_in, "build_steps", lambda **kwargs: ())
    payload = daily_burn_in.run_daily_burn_in(
        profile="live_burn_in_no_send",
        artifact_namespace="burn_candidate_safe",
        base_dir=tmp_path,
        python=sys.executable,
        candidate_mode=True,
    )
    manifest = common.read_json(tmp_path / "burn_candidate_safe" / daily_burn_in.CANDIDATE_MODE_MANIFEST_JSON)
    assert payload["candidate_mode"] is True
    assert payload["live_provider_calls_allowed"] is False
    assert manifest["candidate_mode"] is True
    assert manifest["contract_counted_candidate_count"] == 0
    assert manifest["real_burn_in_candidate_count"] == 0
    assert "coinalyze" in manifest["skipped_missing_config"]
    assert "bybit_announcements" in manifest["skipped_live_calls_disabled"]
    assert manifest["next_steps"]
    assert payload["telegram_sends"] == 0
    assert payload["trades_created"] == 0
    assert payload["paper_trades_created"] == 0
    assert payload["normal_rsi_signal_rows_written"] == 0
    assert payload["triggered_fade_created"] == 0
    assert payload["status"] == "passed_no_candidates"
    assert payload["final_status_reason"]
    assert payload["started_at"]
    assert payload["finished_at"]
    assert manifest["status"] == "completed_no_candidate_providers"
    assert manifest["provider_attempts"] == 0
    assert manifest["provider_skips"] == 2
    assert manifest["provider_successes"] == 0
    assert manifest["request_ledgers"] == []
    for field in (
        "preflight_diagnostic_rows",
        "readiness_rows",
        "source_coverage_rows",
        "integrated_candidate_rows",
        "notification_preview_rows",
        "skipped_request_budget",
        "skipped_not_required_for_profile",
    ):
        assert field in manifest


def test_daily_burn_in_targeted_market_env_requires_feature_and_universe_authority(tmp_path, monkeypatch):
    context = common.context_for(
        profile="live_burn_in_no_send",
        artifact_namespace="targeted_env",
        base_dir=tmp_path,
    )
    monkeypatch.setenv("RSI_EVENT_DISCOVERY_UNIVERSE_LIVE", "1")
    monkeypatch.delenv("RSI_EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED", raising=False)
    disabled = daily_burn_in._safe_env(  # noqa: SLF001 - guarded environment contract
        context,
        profile=context.profile,
        namespace=context.artifact_namespace,
        candidate_mode=False,
    )
    candidate = daily_burn_in._safe_env(  # noqa: SLF001 - guarded environment contract
        context,
        profile=context.profile,
        namespace=context.artifact_namespace,
        candidate_mode=True,
    )
    monkeypatch.setenv("RSI_EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED", "1")
    explicit = daily_burn_in._safe_env(  # noqa: SLF001 - guarded environment contract
        context,
        profile=context.profile,
        namespace=context.artifact_namespace,
        candidate_mode=False,
    )
    assert disabled["RSI_EVENT_DISCOVERY_UNIVERSE_LIVE"] == "0"
    assert candidate["RSI_EVENT_DISCOVERY_UNIVERSE_LIVE"] == "1"
    assert explicit["RSI_EVENT_DISCOVERY_UNIVERSE_LIVE"] == "1"


def test_daily_burn_in_scoped_doctor_is_default_and_timeout_records_partial_status(tmp_path, monkeypatch):
    doctor_step = daily_burn_in.BurnInStep(
        "artifact_doctor",
        (sys.executable, "-m", "crypto_rsi_scanner.event_alpha.operations.daily_burn_in", "--scoped-doctor"),
        required=False,
        timeout_seconds=0.05,
    )
    monkeypatch.setattr(daily_burn_in, "build_steps", lambda **kwargs: (doctor_step,))

    def fake_timeout(step, *, env, cwd):
        return {
            "name": step.name,
            "status": "timeout",
            "required": step.required,
            "timeout_seconds": step.timeout_seconds,
            "duration_seconds": 0.05,
            "command": " ".join(step.command),
            "stdout_tail": "",
            "stderr_tail": "timed out",
        }

    monkeypatch.setattr(daily_burn_in, "_run_step", fake_timeout)
    payload = daily_burn_in.run_daily_burn_in(
        profile="live_burn_in_no_send",
        artifact_namespace="burn_doctor_timeout",
        base_dir=tmp_path,
        python=sys.executable,
        doctor_required=False,
        candidate_mode=True,
    )
    doctor = common.read_json(tmp_path / "burn_doctor_timeout" / daily_burn_in.SCOPED_DOCTOR_JSON)
    assert payload["status"] == "timeout_non_required_step"
    assert payload["steps"][0]["status"] == "timeout"
    assert payload["steps"][0]["timeout_seconds"] == 0.05
    assert payload["steps"][0]["required"] is False
    assert doctor["status"] == "timeout"
    assert doctor["scoped_to_current_namespace"] is True
    assert "scoped_doctor_timeout" in doctor["blockers"]


def test_daily_burn_in_build_steps_uses_scoped_doctor_by_default():
    steps = daily_burn_in.build_steps(
        python=sys.executable,
        profile="live_burn_in_no_send",
        namespace="burn",
        include_coinalyze_rehearsal=False,
        candidate_mode=True,
    )
    doctor = next(step for step in steps if isinstance(step, daily_burn_in.BurnInStep) and step.name == "artifact_doctor")
    contract = next(step for step in steps if isinstance(step, daily_burn_in.BurnInStep) and step.name == "burn_in_contract")
    assert "--check-burn-in-contract" in contract.command
    assert "--burn-in-contract-only" not in contract.command
    assert "--scoped-doctor" in doctor.command
    assert "--event-alpha-artifact-doctor" not in doctor.command
    skipped = [step for step in steps if isinstance(step, dict) and step.get("status") == "skipped"]
    assert skipped
    assert all(step.get("command") for step in skipped)
    assert any("--event-alpha-coinalyze-no-send-rehearsal" in step["command"] for step in skipped)
    full = daily_burn_in.build_steps(
        python=sys.executable,
        profile="live_burn_in_no_send",
        namespace="burn",
        include_coinalyze_rehearsal=False,
        candidate_mode=True,
        doctor_mode="full_namespace",
    )
    full_doctor = next(step for step in full if isinstance(step, daily_burn_in.BurnInStep) and step.name == "artifact_doctor")
    assert "--event-alpha-artifact-doctor" in full_doctor.command


def test_daily_burn_in_plan_module_preserves_public_sequence_and_no_send_boundary():
    assert daily_burn_in.BurnInStep is daily_burn_in_plan.BurnInStep
    assert daily_burn_in.build_steps is daily_burn_in_plan.build_steps
    assert daily_burn_in.default_namespace is daily_burn_in_plan.default_namespace

    steps = daily_burn_in.build_steps(
        python=sys.executable,
        profile="live_burn_in_no_send",
        namespace="burn",
        include_coinalyze_rehearsal=False,
    )
    assert [
        step.name if isinstance(step, daily_burn_in.BurnInStep) else step["name"]
        for step in steps
    ] == [
        "burn_in_contract",
        "live_provider_readiness",
        "cryptopanic_preflight",
        "coinalyze_preflight",
        "coinalyze_no_send_rehearsal",
        "bybit_announcements_preflight",
        "integrated_radar_cycle",
        "source_coverage",
        "notification_preview",
        "daily_brief",
        "review_inbox",
        "artifact_doctor",
        "burn_in_scorecard",
    ]
    commands = "\n".join(
        " ".join(step.command)
        if isinstance(step, daily_burn_in.BurnInStep)
        else str(step.get("command") or "")
        for step in steps
    )
    assert "--event-alpha-telegram-send-one-cycle" not in commands
    assert "--event-alpha-cycle-send" not in commands
    assert "--event-alpha-notify-cycle" not in commands
    assert "RSI_EVENT_ALERTS_ENABLED=1" not in commands


def test_daily_burn_in_readiness_no_key_and_mock_allow_paths(tmp_path, monkeypatch):
    import urllib.request

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("readiness must not fetch providers")),
    )
    monkeypatch.delenv("RSI_EVENT_DISCOVERY_COINALYZE_API_KEY", raising=False)
    monkeypatch.delenv("RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT", raising=False)
    monkeypatch.delenv("RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT", raising=False)
    monkeypatch.setattr(daily_burn_in.config, "EVENT_DISCOVERY_COINALYZE_API_KEY", "", raising=False)
    no_key = daily_burn_in_readiness.build_readiness_report(
        profile="live_burn_in_no_send",
        artifact_namespace="readiness_no_key",
        base_dir=tmp_path,
    )
    assert no_key["expected_live_calls_default"] == 0
    assert no_key["can_run_candidate_mode"] is False
    assert no_key["candidate_mode_status"] == "blocked_by_default"
    assert no_key["candidate_mode_ready_status"] == "config_ready_no_live"
    assert no_key["candidate_mode_ready_with_any_provider"] is False
    assert no_key["candidate_mode_ready_with_all_priority_providers"] is False
    assert no_key["fastest_ready_provider"] == "bybit_announcements"
    assert "bybit_announcements" in no_key["providers_config_ready_no_live"]
    assert "coinalyze" in no_key["providers_missing_config"]
    assert "bybit_announcements" in no_key["providers_missing_allow_flag"]
    assert "event-alpha-bybit-announcements-preflight" in no_key["next_safe_commands"][0]
    assert no_key["telegram_sends"] == 0

    monkeypatch.setenv("RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT", "1")
    bybit_only = daily_burn_in_readiness.build_readiness_report(
        profile="live_burn_in_no_send",
        artifact_namespace="readiness_bybit_only",
        base_dir=tmp_path,
    )
    assert bybit_only["candidate_mode_ready_with_any_provider"] is True
    assert bybit_only["candidate_mode_ready_with_all_priority_providers"] is False
    assert bybit_only["can_run_candidate_mode"] is True
    assert "coinalyze" in bybit_only["providers_missing_config"]

    monkeypatch.setenv("RSI_EVENT_DISCOVERY_COINALYZE_API_KEY", "fake-test-key")
    monkeypatch.delenv("RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT", raising=False)
    monkeypatch.setenv("RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT", "1")
    blocked = daily_burn_in_readiness.build_readiness_report(
        profile="live_burn_in_no_send",
        artifact_namespace="readiness_coinalyze_only",
        base_dir=tmp_path,
    )
    assert blocked["candidate_mode_ready_with_any_provider"] is True
    assert blocked["candidate_mode_ready_with_all_priority_providers"] is False
    assert blocked["can_run_candidate_mode"] is True
    assert blocked["fastest_ready_provider"] == "coinalyze"
    assert "bybit_announcements" in blocked["providers_config_ready_no_live"]
    assert "bybit_announcements" in blocked["providers_missing_allow_flag"]

    monkeypatch.setenv("RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT", "1")
    monkeypatch.setenv("RSI_EVENT_ALPHA_DAILY_BURN_IN_MOCK_PROVIDER_FIXTURES", "1")
    ready = daily_burn_in_readiness.build_readiness_report(
        profile="live_burn_in_no_send",
        artifact_namespace="readiness_ready",
        base_dir=tmp_path,
    )
    assert ready["candidate_mode_status"] == "ready_for_mocked_candidate_mode"
    assert ready["candidate_mode_ready_status"] == "ready_for_bounded_no_send_rehearsal"
    assert ready["can_run_candidate_mode"] is True
    assert ready["candidate_mode_ready_with_any_provider"] is True
    assert ready["candidate_mode_ready_with_all_priority_providers"] is True
    assert ready["providers_missing_config"] == []
    assert ready["providers_missing_allow_flag"] == []
    assert ready["expected_live_calls_default"] == 0
    assert ready["telegram_sends"] == 0


def test_bybit_live_readiness_preserves_specific_forbidden_statuses(tmp_path, monkeypatch):
    from crypto_rsi_scanner import config
    from crypto_rsi_scanner.event_alpha.providers import live_provider_readiness

    namespace = "bybit_failure_status"
    namespace_dir = tmp_path / namespace
    namespace_dir.mkdir(parents=True)
    monkeypatch.setattr(config, "EVENT_ALPHA_ARTIFACT_BASE_DIR", tmp_path)

    for status in ("edge_forbidden", "region_restricted"):
        common.write_json(
            namespace_dir / "event_bybit_announcements_rehearsal_report.json",
            {
                "provider": "bybit_announcements",
                "status": status,
                "provider_health_status": status,
                "configured": True,
                "live_call_allowed": True,
            },
        )
        history = live_provider_readiness._bybit_announcements_history(namespace)  # noqa: SLF001
        assert history["latest_rehearsal_status"] == status
        assert history["latest_provider_health_status"] == status
        assert history["activation_phase"] == status


def test_daily_burn_in_candidate_mode_mocked_live_candidate_counts_with_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("RSI_EVENT_DISCOVERY_COINALYZE_API_KEY", "fake-test-key")
    monkeypatch.setenv("RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT", "1")
    monkeypatch.delenv("RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT", raising=False)
    monkeypatch.setattr(daily_burn_in.config, "EVENT_DISCOVERY_COINALYZE_API_KEY", "", raising=False)
    step = daily_burn_in.BurnInStep("integrated_radar_cycle", (sys.executable, "-c", "print('mock')"), required=True, timeout_seconds=5)
    monkeypatch.setattr(daily_burn_in, "build_steps", lambda **kwargs: (step,))

    def fake_run_step(step, *, env, cwd):
        namespace_dir = Path(env["RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR"]) / env["RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE"]
        provider_run_id = "coinalyze-provider-run-1"
        provider_generation_id = "coinalyze:generation-1"
        _write_jsonl(
            namespace_dir / daily_burn_in.COINALYZE_REQUEST_LEDGER,
            [{
                "provider": "coinalyze",
                "status": "success",
                "success": True,
                "no_send_rehearsal": True,
                "provider_generation_id": provider_generation_id,
                "run_id": provider_run_id,
                "profile": "live_burn_in_no_send",
                "artifact_namespace": "live_burn_in_20260705",
                "api_key_redacted": "***",
            }],
        )
        _write_jsonl(
            namespace_dir / "event_derivatives_state.jsonl",
            [{
                "row_type": "derivatives_state_snapshot",
                "symbol": "TESTFADE",
                "provider": "coinalyze",
                "provider_generation_id": provider_generation_id,
                "run_id": provider_run_id,
                "profile": "live_burn_in_no_send",
                "artifact_namespace": "live_burn_in_20260705",
            }],
        )
        common.write_json(namespace_dir / "event_coinalyze_rehearsal_report.json", {
            "provider": "coinalyze",
            "status": "live_rehearsal_success",
            "live_call_allowed": True,
            "no_send": True,
            "research_only": True,
            "provider_generation_id": provider_generation_id,
            "run_id": provider_run_id,
        })
        _write_jsonl(
            namespace_dir / "event_integrated_radar_candidates.jsonl",
            [
                {
                    "row_type": "event_integrated_radar_candidate",
                    "candidate_id": "cand:testfade",
                    "symbol": "TESTFADE",
                    "coin_id": "testfade",
                    "opportunity_type": "FADE_SHORT_REVIEW",
                    "provider": "coinalyze",
                    "source_pack": "derivatives_crowding",
                    "source_origin": "coinalyze",
                    "opportunity_score_final": 81,
                    "provider_generation_id": provider_generation_id,
                    "provider_request_succeeded": True,
                    "provider_source_artifact": "event_derivatives_state.jsonl",
                        "run_id": "integrated-run-1",
                        "profile": "live_burn_in_no_send",
                        "artifact_namespace": "live_burn_in_20260705",
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
        )
        return {
            "name": step.name,
            "status": "passed",
            "required": step.required,
            "timeout_seconds": step.timeout_seconds,
            "duration_seconds": 0.01,
            "command": " ".join(step.command),
        }

    monkeypatch.setattr(daily_burn_in, "_run_step", fake_run_step)
    payload = daily_burn_in.run_daily_burn_in(
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_20260705",
        base_dir=tmp_path,
        python=sys.executable,
        candidate_mode=True,
    )
    namespace_dir = tmp_path / "live_burn_in_20260705"
    rows = common.read_jsonl(namespace_dir / "event_integrated_radar_candidates.jsonl")
    manifest = common.read_json(namespace_dir / daily_burn_in.CANDIDATE_MODE_MANIFEST_JSON)
    assert payload["live_provider_calls_allowed"] is True
    assert rows[0]["candidate_source_mode"] == "live_no_send"
    assert rows[0]["contract_counted_candidate"] is True
    assert rows[0]["request_ledger_path"].endswith(daily_burn_in.COINALYZE_REQUEST_LEDGER)
    assert rows[0]["telegram_sends"] == 0
    assert rows[0]["trades_created"] == 0
    assert rows[0]["paper_trades_created"] == 0
    assert rows[0]["normal_rsi_signal_rows_written"] == 0
    assert rows[0]["triggered_fade_created"] == 0
    assert manifest["contract_counted_candidate_count"] == 1
    guardrails = {row["provider"]: row for row in payload["live_provider_guardrails"]}
    assert guardrails["coinalyze"]["no_send"] is True
    assert guardrails["coinalyze"]["allow_flag_set"] is True
    assert guardrails["coinalyze"]["request_ledger_present"] is True
    assert guardrails["coinalyze"]["requests_used"] == 1
    assert "## Live Provider Guardrails" in (namespace_dir / daily_burn_in.RUN_MD).read_text(encoding="utf-8")
    score = scorecard.build_scorecard(
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_20260705",
        base_dir=tmp_path,
        count_explicit_namespace_for_burn_in=True,
    )
    assert score["evidence_scope"] == "real_burn_in_evidence"
    assert score["contract_counted_candidate_count"] == 1
    yield_report = source_yield.build_source_yield_report(
        profile="live_burn_in_no_send",
        base_dir=tmp_path,
    )
    assert yield_report["providers"]["coinalyze"]["candidate_count"] == 1
    assert yield_report["providers"]["coinalyze"]["candidates_produced"] == 1
    assert yield_report["providers"]["coinalyze"]["source_yield_confidence"] == "insufficient_labels"


def test_candidate_contract_rejects_stale_or_failed_provider_generation(tmp_path):
    context = common.context_for(
        profile="live_burn_in_no_send",
        artifact_namespace="generation_contract",
        base_dir=tmp_path,
    )
    context.namespace_dir.mkdir(parents=True, exist_ok=True)
    provider_run_id = "coinalyze-provider-run-new"
    common.write_json(context.namespace_dir / "event_coinalyze_rehearsal_report.json", {
        "provider": "coinalyze",
        "status": "live_rehearsal_success",
        "live_call_allowed": True,
        "no_send": True,
        "research_only": True,
        "provider_generation_id": "generation-new",
        "run_id": provider_run_id,
    })
    _write_jsonl(
        context.namespace_dir / "event_derivatives_state.jsonl",
        [{
            "row_type": "derivatives_state_snapshot",
            "symbol": "TEST",
            "provider": "coinalyze",
            "provider_generation_id": "generation-new",
            "run_id": provider_run_id,
            "profile": context.profile,
            "artifact_namespace": context.artifact_namespace,
        }],
    )
    provider_status = {
        "coinalyze": {
            "provider": "coinalyze",
            "live_call_allowed": True,
            "request_ledger_path": common.rel_path(
                context.namespace_dir / daily_burn_in.COINALYZE_REQUEST_LEDGER
            ),
        }
    }
    base_row = {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "candidate:test",
        "symbol": "TEST",
        "coin_id": "test",
        "provider": "coinalyze",
        "source_pack": "derivatives_crowding",
        "source_origin": "coinalyze",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "provider_generation_id": "generation-new",
        "provider_source_artifact": "event_derivatives_state.jsonl",
        "run_id": "integrated-run-new",
        "profile": context.profile,
        "artifact_namespace": context.artifact_namespace,
    }
    _write_jsonl(
        context.namespace_dir / daily_burn_in.COINALYZE_REQUEST_LEDGER,
        [{
            "provider": "coinalyze",
            "provider_generation_id": "generation-old",
            "success": True,
            "no_send_rehearsal": True,
            "run_id": "coinalyze-provider-run-old",
            "profile": context.profile,
            "artifact_namespace": context.artifact_namespace,
        }],
    )
    stale = dict(base_row)
    daily_burn_in._annotate_candidate_row(  # noqa: SLF001 - exact-generation contract regression
        stale,
        context=context,
        provider_status=provider_status,
    )
    assert stale["candidate_source_mode"] == "artifact_replay"
    assert stale["contract_counted_candidate"] is False

    _write_jsonl(
        context.namespace_dir / daily_burn_in.COINALYZE_REQUEST_LEDGER,
        [{
            "provider": "coinalyze",
            "provider_generation_id": "generation-new",
            "success": False,
            "no_send_rehearsal": True,
            "run_id": provider_run_id,
            "profile": context.profile,
            "artifact_namespace": context.artifact_namespace,
        }],
    )
    failed = dict(base_row)
    daily_burn_in._annotate_candidate_row(  # noqa: SLF001 - exact-generation contract regression
        failed,
        context=context,
        provider_status=provider_status,
    )
    assert failed["candidate_source_mode"] == "artifact_replay"
    assert failed["provider_request_succeeded"] is False
    assert failed["contract_counted_candidate"] is False

    bybit_run_id = "bybit-provider-run-new"
    common.write_json(context.namespace_dir / "event_bybit_announcements_rehearsal_report.json", {
        "provider": "bybit_announcements",
        "status": "live_rehearsal_success",
        "live_call_allowed": True,
        "no_send": True,
        "research_only": True,
        "provider_generation_id": "bybit-generation-new",
        "run_id": bybit_run_id,
    })
    _write_jsonl(
        context.namespace_dir / "event_exchange_announcements.jsonl",
        [{
            "row_type": "exchange_announcement",
            "title": "Bybit lists TEST",
            "provider": "bybit_announcements",
            "provider_generation_id": "bybit-generation-new",
            "run_id": bybit_run_id,
            "profile": context.profile,
            "artifact_namespace": context.artifact_namespace,
        }],
    )
    _write_jsonl(
        context.namespace_dir / daily_burn_in.BYBIT_REQUEST_LEDGER,
        [{
            "provider": "bybit_announcements",
            "provider_generation_id": "bybit-generation-new",
            "success": True,
            "no_send_rehearsal": True,
            "run_id": bybit_run_id,
            "profile": context.profile,
            "artifact_namespace": context.artifact_namespace,
        }],
    )
    bybit_status = {
        "bybit_announcements": {
            "provider": "bybit_announcements",
            "live_call_allowed": True,
            "request_ledger_path": common.rel_path(
                context.namespace_dir / daily_burn_in.BYBIT_REQUEST_LEDGER
            ),
        }
    }
    bybit = {
        **base_row,
        "provider": "bybit_announcements",
        "source_origin": "bybit_announcements",
        "provider_generation_id": "bybit-generation-new",
        "provider_source_artifact": "event_exchange_announcements.jsonl",
        "source_url": "https://announcements.bybit.com/test",
        "title": "Bybit lists TEST",
        "published_at": "2026-07-11T12:00:00+00:00",
    }
    daily_burn_in._annotate_candidate_row(  # noqa: SLF001 - exact-generation contract regression
        bybit,
        context=context,
        provider_status=bybit_status,
    )
    assert bybit["candidate_source_mode"] == "live_no_send"
    assert bybit["provider_request_succeeded"] is True
    assert bybit["contract_counted_candidate"] is True
    from types import SimpleNamespace

    from crypto_rsi_scanner.event_alpha.doctor.checks import operations as doctor_operations

    doctor_context = SimpleNamespace(
        namespace_dir=context.namespace_dir,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
    )
    assert doctor_operations._exact_contract_ledger_valid(  # noqa: SLF001 - doctor exact-lineage regression
        doctor_context,
        bybit,
    ) is True

    # A later failed attempt is a new exact generation.  The old successful
    # ledger/source rows remain append-only, but cannot count for the retry.
    common.write_json(context.namespace_dir / "event_bybit_announcements_rehearsal_report.json", {
        "provider": "bybit_announcements",
        "status": "edge_forbidden",
        "live_call_allowed": True,
        "no_send": True,
        "research_only": True,
        "provider_generation_id": "bybit-generation-retry",
        "run_id": "bybit-provider-run-retry",
    })
    retry = dict(bybit)
    daily_burn_in._annotate_candidate_row(  # noqa: SLF001 - current-attempt contract regression
        retry,
        context=context,
        provider_status=bybit_status,
    )
    assert retry["candidate_source_mode"] == "artifact_replay"
    assert retry["provider_request_succeeded"] is False
    assert retry["contract_counted_candidate"] is False
    assert doctor_operations._exact_contract_ledger_valid(  # noqa: SLF001 - stale attempt must fail closed
        doctor_context,
        bybit,
    ) is False


def test_provider_attempt_generation_is_unique_at_a_fixed_research_clock():
    from datetime import datetime, timezone

    from crypto_rsi_scanner.event_alpha.providers import request_lineage

    observed = datetime(2026, 7, 11, 12, tzinfo=timezone.utc)
    first = request_lineage.provider_generation_id("bybit_announcements", observed)
    second = request_lineage.provider_generation_id("bybit_announcements", observed)
    assert first != second
    assert first.startswith("provider-generation:bybit_announcements:")
    assert second.startswith("provider-generation:bybit_announcements:")


def test_bybit_failed_retry_at_same_clock_cannot_inherit_prior_success(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from urllib.error import HTTPError

    from crypto_rsi_scanner.event_alpha.providers import bybit_announcements_preflight as bybit

    class Response:
        status = 200

        def __init__(self, payload: dict) -> None:
            self.payload = json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self) -> bytes:
            return self.payload

    payload = json.loads(
        Path("fixtures/event_discovery/official_exchange_bybit_announcements.json").read_text(encoding="utf-8")
    )
    payload["result"]["list"] = payload["result"]["list"][:1]
    monkeypatch.setenv(bybit.ENV_ALLOW_LIVE_PREFLIGHT, "1")
    monkeypatch.setenv(bybit.ENV_PREFLIGHT_MAX_PAGES, "1")
    monkeypatch.setenv(bybit.ENV_PREFLIGHT_LIMIT, "20")
    observed = datetime(2026, 7, 11, 12, tzinfo=timezone.utc)
    _preflight, first, _paths = bybit.run_no_send_rehearsal(
        namespace_dir=tmp_path,
        provider_health_path=tmp_path / "event_provider_health.json",
        profile="fixture",
        artifact_namespace="fixed_clock_retry",
        allow_live_preflight=True,
        opener=lambda _request, _timeout: Response(payload),
        now=observed,
    )

    def rate_limited(request, _timeout):
        raise HTTPError(request.full_url, 429, "blocked", None, None)

    _preflight, retry, _paths = bybit.run_no_send_rehearsal(
        namespace_dir=tmp_path,
        provider_health_path=tmp_path / "event_provider_health.json",
        profile="fixture",
        artifact_namespace="fixed_clock_retry",
        allow_live_preflight=True,
        opener=rate_limited,
        now=observed,
    )
    assert first.status == "live_rehearsal_success"
    assert retry.status == "rate_limited"
    assert retry.provider_generation_id != first.provider_generation_id
    assert retry.run_id != first.run_id
    assert retry.http_successes == 0
    assert retry.requests_used == 1


def test_candidate_lineage_propagation_never_rewrites_historical_same_core_id(tmp_path):
    context = common.context_for(
        profile="live_burn_in_no_send",
        artifact_namespace="lineage_history",
        base_dir=tmp_path,
    )
    context.namespace_dir.mkdir(parents=True, exist_ok=True)
    core_id = "agg:stable-family"
    old = {
        "row_type": "event_core_opportunity",
        "core_opportunity_id": core_id,
        "run_id": "integrated-run-old",
        "profile": context.profile,
        "artifact_namespace": context.artifact_namespace,
        "candidate_source_mode": "artifact_replay",
        "contract_counted_candidate": False,
    }
    current = {
        **old,
        "run_id": "integrated-run-current",
    }
    _write_jsonl(
        context.namespace_dir / "event_core_opportunities.jsonl",
        [old, current],
    )
    candidate = {
        "core_opportunity_id": core_id,
        "run_id": "integrated-run-current",
        "profile": context.profile,
        "artifact_namespace": context.artifact_namespace,
        "candidate_source_mode": "live_no_send",
        "contract_counted_candidate": True,
        "provider": "bybit_announcements",
        "provider_generation_id": "provider-generation-current",
        "provider_request_succeeded": True,
        "provider_source_artifact": "event_exchange_announcements.jsonl",
        "request_ledger_path": daily_burn_in.BYBIT_REQUEST_LEDGER,
    }

    assert daily_burn_in._propagate_candidate_lineage_to_core(  # noqa: SLF001 - exact-run propagation regression
        context,
        [candidate],
    ) is True
    rows = common.read_jsonl(context.namespace_dir / "event_core_opportunities.jsonl")
    historical, latest = rows
    assert historical["candidate_source_mode"] == "artifact_replay"
    assert historical["contract_counted_candidate"] is False
    assert "provider_generation_id" not in historical
    assert latest["candidate_source_mode"] == "live_no_send"
    assert latest["contract_counted_candidate"] is True
    assert latest["provider_generation_id"] == "provider-generation-current"


def test_daily_burn_in_candidate_mode_fixture_smoke_produces_lanes_without_contract_count(tmp_path, monkeypatch):
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    monkeypatch.delenv("RSI_EVENT_DISCOVERY_COINALYZE_API_KEY", raising=False)
    monkeypatch.delenv("RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT", raising=False)
    monkeypatch.delenv("RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT", raising=False)
    monkeypatch.setattr(daily_burn_in.config, "EVENT_DISCOVERY_COINALYZE_API_KEY", "", raising=False)
    payload = daily_burn_in.run_daily_burn_in(
        profile="fixture",
        artifact_namespace="daily_burn_in_candidate_mode_smoke",
        base_dir=tmp_path,
        python=sys.executable,
        candidate_mode=True,
        candidate_mode_smoke=True,
        report_timeout_seconds=10,
        doctor_timeout_seconds=10,
    )
    ns = tmp_path / "daily_burn_in_candidate_mode_smoke"
    rows = common.read_jsonl(ns / "event_integrated_radar_candidates.jsonl")
    lanes = {row["opportunity_type"] for row in rows}
    assert {
        "EARLY_LONG_RESEARCH",
        "CONFIRMED_LONG_RESEARCH",
        "FADE_SHORT_REVIEW",
        "RISK_ONLY",
        "UNCONFIRMED_RESEARCH",
    }.issubset(lanes)
    assert rows
    assert all(row["candidate_source_mode"] == "mocked_fixture" for row in rows)
    assert all(row["contract_counted_candidate"] is False for row in rows)
    assert all(row["research_only"] is True and row["no_send_rehearsal"] is True for row in rows)
    manifest = common.read_json(ns / daily_burn_in.CANDIDATE_MODE_MANIFEST_JSON)
    score = common.read_json(ns / scorecard.SCORECARD_JSON)
    inbox = common.read_json(ns / review_inbox.INBOX_JSON)
    inbox_md = (ns / review_inbox.INBOX_MD).read_text(encoding="utf-8")
    cards = sorted((ns / "research_cards").glob("*.md"))
    card_files = [path for path in cards if path.name != "index.md"]
    rows_by_symbol = {row["symbol"]: row for row in rows}
    review_step = next(row for row in payload["steps"] if row.get("name") == "review_inbox")
    assert payload["status"] == "passed"
    assert review_step["status"] == "passed"
    assert manifest["status"] == "completed_fixture_candidates_only"
    assert manifest["fixture_candidate_count"] >= 5
    assert manifest["contract_counted_candidate_count"] == 0
    assert manifest["research_cards_written"] >= 5
    assert score["evidence_scope"] == "fixture_candidate_mode_smoke"
    assert score["contract_counted_candidate_count"] == 0
    assert score["enough_data"] is False
    assert cards
    assert len(card_files) == 5
    assert all(path.name.startswith("card_") for path in card_files)
    assert all(not Path(str(row.get("card_path") or "none")).is_absolute() for row in rows)
    assert all(not Path(str(row.get("card_path") or "none")).is_absolute() for row in inbox["items"])
    assert "/tmp/" not in inbox_md
    assert "/mnt/data/" not in inbox_md
    assert "/Users/" not in inbox_md
    assert rows_by_symbol["TESTFADE"]["card_path"]
    assert rows_by_symbol["TESTPERP"]["card_path"]
    fade_card = (tmp_path / rows_by_symbol["TESTFADE"]["card_path"]).read_text(encoding="utf-8")
    perp_card = (tmp_path / rows_by_symbol["TESTPERP"]["card_path"]).read_text(encoding="utf-8")
    assert "FADE_SHORT_REVIEW" in fade_card
    assert "Crowding class: extreme" in fade_card
    assert "Research artifact only. Not a trade signal" in fade_card
    assert "Source provider:" in fade_card
    assert "Provider source artifact:" in fade_card
    assert "Market refresh artifact:" in fade_card
    assert "Request ledger:" in fade_card
    assert "Contract-counted burn-in candidate:" in fade_card
    assert "CONFIRMED_LONG_RESEARCH" in perp_card
    assert "Market confirmation: breakout_confirmed" in perp_card
    assert "Research artifact only. Not a trade signal" in perp_card
    assert all(row.get("card_path") or row.get("card_not_available_reason") for row in inbox["items"])
    assert all(row.get("card_path") and row.get("card_path") != "none" for row in inbox["items"] if row.get("candidate_provenance") == "core_opportunity")
    assert all(row.get("feedback_target") for row in inbox["items"])
    assert all(
        {
            "candidate_source_mode",
            "provider_generation_id",
            "provider_request_succeeded",
            "provider_source_artifact",
            "request_ledger_path",
            "market_refresh_artifact",
        }.issubset(row)
        for row in inbox["items"]
    )
    assert "## Contract-Counted Burn-In Candidates" in inbox_md
    assert "No contract-counted burn-in candidates yet." in inbox_md
    assert "## High-Value Non-Counted Review Candidates" in inbox_md
    assert "## Diagnostics / Support" in inbox_md
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=common.read_jsonl(ns / "event_alpha_runs.jsonl"),
        core_opportunity_rows=common.read_jsonl(ns / "event_core_opportunities.jsonl"),
        card_paths=cards,
        profile="fixture",
        artifact_namespace="daily_burn_in_candidate_mode_smoke",
        include_test_artifacts=True,
        strict=True,
    )
    assert doctor.daily_brief_card_group_mismatch_with_index == 0
