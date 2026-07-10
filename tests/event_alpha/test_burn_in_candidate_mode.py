"""Candidate-mode burn-in operation tests."""

from __future__ import annotations

import json
import sys
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
    assert no_key["candidate_mode_status"] == "missing_config"
    assert no_key["candidate_mode_ready_status"] == "blocked_by_missing_config"
    assert "coinalyze" in no_key["missing_config"]
    assert no_key["telegram_sends"] == 0

    monkeypatch.setenv("RSI_EVENT_DISCOVERY_COINALYZE_API_KEY", "fake-test-key")
    blocked = daily_burn_in_readiness.build_readiness_report(
        profile="live_burn_in_no_send",
        artifact_namespace="readiness_blocked",
        base_dir=tmp_path,
    )
    assert blocked["candidate_mode_status"] == "blocked_by_default"
    assert blocked["candidate_mode_ready_status"] == "config_ready_no_live"
    assert blocked["can_run_candidate_mode"] is False

    monkeypatch.setenv("RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT", "1")
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
    assert ready["expected_live_calls_default"] == 0
    assert ready["telegram_sends"] == 0


def test_daily_burn_in_candidate_mode_mocked_live_candidate_counts_with_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("RSI_EVENT_DISCOVERY_COINALYZE_API_KEY", "fake-test-key")
    monkeypatch.setenv("RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT", "1")
    monkeypatch.delenv("RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT", raising=False)
    monkeypatch.setattr(daily_burn_in.config, "EVENT_DISCOVERY_COINALYZE_API_KEY", "", raising=False)
    step = daily_burn_in.BurnInStep("integrated_radar_cycle", (sys.executable, "-c", "print('mock')"), required=True, timeout_seconds=5)
    monkeypatch.setattr(daily_burn_in, "build_steps", lambda **kwargs: (step,))

    def fake_run_step(step, *, env, cwd):
        namespace_dir = Path(env["RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR"]) / env["RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE"]
        _write_jsonl(
            namespace_dir / daily_burn_in.COINALYZE_REQUEST_LEDGER,
            [{"provider": "coinalyze", "status": "success", "api_key_redacted": "***"}],
        )
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


def test_daily_burn_in_candidate_mode_fixture_smoke_produces_lanes_without_contract_count(tmp_path, monkeypatch):
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
    assert "Derivatives crowding class: extreme" in fade_card
    assert "Research-only / unvalidated. Not a trade signal." in fade_card
    assert "CONFIRMED_LONG_RESEARCH" in perp_card
    assert "Market confirmation: breakout_confirmed" in perp_card
    assert "Research-only / unvalidated. Not a trade signal." in perp_card
    assert all(row.get("card_path") or row.get("card_not_available_reason") for row in inbox["items"])
    assert all(row.get("card_path") and row.get("card_path") != "none" for row in inbox["items"] if row.get("candidate_provenance") == "core_opportunity")
    assert all(row.get("feedback_target") for row in inbox["items"])
    assert "## Contract-Counted Burn-In Candidates" in inbox_md
    assert "No contract-counted burn-in candidates yet." in inbox_md
    assert "## High-Value Review Candidates Not Contract-Counted" in inbox_md
    assert "## Diagnostic / Support Items" in inbox_md
