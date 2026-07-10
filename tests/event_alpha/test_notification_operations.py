"""Focused Event Alpha notification tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alpha_notification_go_no_go_reports_send_blockers():
    from types import SimpleNamespace
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.go_no_go as go

    lock_status = SimpleNamespace(state="held", message="fresh notification lock held by run_id=r1")
    provider_status = SimpleNamespace(ready_event_source_count=2, ready_enrichment_count=1)
    result = go.build_go_no_go(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        telegram_ready=False,
        send_guard_enabled=False,
        lock_status=lock_status,
        provider_status=provider_status,
        provider_health_rows={"gdelt": {"disabled_until": "2026-06-20T12:30:00Z"}},
        delivery_ledger_path=Path("/tmp/event_alpha_notification_deliveries.jsonl"),
        notification_run_ledger_path=Path("/tmp/event_alpha_notification_runs.jsonl"),
        research_cards_dir=Path("/tmp/research_cards"),
        artifact_doctor_status="WARN",
        cooldown_status={"daily_digest": {"due": True, "sent_today": 0, "reason": "due"}},
        llm_budget_status="provider=fixture max_run=0",
        clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
    )
    text = go.format_go_no_go(result)
    assert result.ready_to_preview is True
    assert result.ready_to_send_now is False
    assert "ready_to_send_now: no" in text
    assert "fresh notification lock is held" in text
    assert "real-send blocked: telegram config is missing" in text
    assert "real-send blocked: RSI_EVENT_ALERTS_ENABLED is not set" in text
    assert "provider(s) currently in backoff" in text
    assert "provider health: make event-alpha-provider-health-report PROFILE=notify_no_key" in text
    assert "provider reset: make event-alpha-provider-health-reset PROFILE=notify_no_key PROVIDER_KEY=all CONFIRM=1" in text
    assert "delivery report: make event-alpha-notification-deliveries-report PROFILE=notify_no_key" in text
    assert "notification inbox: make event-alpha-notification-inbox PROFILE=notify_no_key" in text
    assert "SECRET" not in text

    no_backoff = go.build_go_no_go(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        telegram_ready=True,
        send_guard_enabled=True,
        lock_status=SimpleNamespace(state="missing", message="no lock"),
        provider_status=provider_status,
        provider_health_rows={},
        delivery_ledger_path=Path("/tmp/event_alpha_notification_deliveries.jsonl"),
        notification_run_ledger_path=Path("/tmp/event_alpha_notification_runs.jsonl"),
        research_cards_dir=Path("/tmp/research_cards"),
        artifact_doctor_status="OK",
        cooldown_status={"daily_digest": {"due": True, "sent_today": 0, "reason": "due"}},
        llm_budget_status="provider=fixture max_run=0",
        clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
    )
    no_backoff_text = go.format_go_no_go(no_backoff)
    assert "provider reset:" not in no_backoff_text


def test_event_alpha_notification_go_no_go_uses_send_readiness_for_final_recommendation():
    from dataclasses import replace
    from types import SimpleNamespace
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.go_no_go as go
    import crypto_rsi_scanner.event_alpha.notifications.final_check as final_check

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        preview_path = tmp_path / "event_alpha_notification_preview.md"
        preview_path.write_text("# preview\n", encoding="utf-8")
        provider_status = SimpleNamespace(ready_event_source_count=2, ready_enrichment_count=1)
        readiness = SimpleNamespace(
            ready=True,
            blockers=(),
            warnings=("no-send rehearsal: send guard disabled; real Telegram sends remain blocked",),
            latest_run_id="run-1",
            latest_run_completed=True,
            preview_path=str(preview_path),
            preview_path_source="relpath",
            alertable_items=2,
        )
        row = {
            "run_id": "run-1",
            "lane": "daily_digest",
            "delivery_state": delivery.STATE_BLOCKED,
            "status_detail": delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED,
            "delivery_mode": "guarded_no_send",
            "would_send": True,
            "sent": False,
            "failed": False,
            "core_opportunity_id": "agg:velvet",
            "canonical_symbol": "VELVET",
            "canonical_coin_id": "velvet",
            "feedback_target": "agg:velvet",
        }
        review_row = {
            **row,
            "lane": "research_review_digest",
            "core_opportunity_id": "agg:doge-review",
            "canonical_symbol": "DOGE",
            "canonical_coin_id": "dogecoin",
            "feedback_target": "agg:doge-review",
        }
        no_send = go.build_go_no_go(
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep_rehearsal",
            telegram_ready=False,
            send_guard_enabled=False,
            lock_status=SimpleNamespace(state="missing", message="no lock"),
            provider_status=provider_status,
            provider_health_rows={},
            delivery_ledger_path=tmp_path / "deliveries.jsonl",
            notification_run_ledger_path=tmp_path / "runs.jsonl",
            research_cards_dir=tmp_path / "cards",
            artifact_doctor_status="OK",
            cooldown_status={},
            llm_budget_status="provider=openai max_run=200",
            clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
            send_readiness=readiness,
            delivery_rows=[row, review_row],
        )
        text = go.format_go_no_go(no_send)
        assert no_send.final_recommendation == go.RECOMMEND_READY_NO_SEND_REVIEW
        assert no_send.ready_to_send_now is False
        assert "final_recommendation: READY_FOR_NO_SEND_REVIEW" in text
        assert "latest_run_id: run-1" in text
        assert "notification_preview_path_source: relpath" in text
        assert "would_send_lanes: daily_digest, research_review_digest" in text
        assert "canonical_delivery_identity: yes" in text
        final = final_check.build_final_check(
            go_no_go_result=no_send,
            doctor_status="OK",
            delivery_rows=[row, review_row],
            core_rows=[
                {
                    "run_id": "run-1",
                    "core_opportunity_id": "agg:velvet",
                    "final_route_after_quality_gate": "RESEARCH_DIGEST",
                }
            ],
        )
        compact = final_check.format_final_check(final)
        assert final.status == go.RECOMMEND_READY_NO_SEND_REVIEW
        assert final.preview_path == str(preview_path)
        assert final.sends_performed == 0
        assert final.core_ids == ("agg:velvet", "agg:doge-review")
        assert "Final Telegram no-send check:" in compact
        assert "- status: READY_FOR_NO_SEND_REVIEW" in compact
        assert "- would-send lanes: daily_digest, research_review_digest" in compact
        assert "- sends performed: 0" in compact
        assert "EVENT ALPHA NOTIFICATION GO/NO-GO" not in compact
        blocked = final_check.build_final_check(
            go_no_go_result=no_send,
            doctor_status="BLOCKED",
            doctor_blockers=("strict artifact doctor has blockers",),
            delivery_rows=[row],
            core_rows=[],
        )
        assert blocked.status == go.RECOMMEND_NOT_READY
        assert any("strict artifact doctor" in item for item in blocked.blockers)
        missing_preview = final_check.build_final_check(
            go_no_go_result=replace(no_send, notification_preview_exists=False),
            doctor_status="OK",
            delivery_rows=[row],
            core_rows=[],
        )
        assert missing_preview.status == go.RECOMMEND_NOT_READY
        assert any("preview is missing" in item for item in missing_preview.blockers)
        identity_mismatch = final_check.build_final_check(
            go_no_go_result=replace(no_send, canonical_delivery_identity=False),
            doctor_status="OK",
            delivery_rows=[row],
            core_rows=[],
        )
        assert identity_mismatch.status == go.RECOMMEND_NOT_READY
        assert any("canonical core identity" in item for item in identity_mismatch.blockers)
        rejected_selected = final_check.build_final_check(
            go_no_go_result=replace(no_send, rejected_or_unconfirmed_selected=True),
            doctor_status="OK",
            delivery_rows=[row],
            core_rows=[],
        )
        assert rejected_selected.status == go.RECOMMEND_NOT_READY
        assert any("rejected-only or unconfirmed" in item for item in rejected_selected.blockers)
        stale_text = go.format_go_no_go(
            go.build_go_no_go(
                profile="notify_llm_deep",
                artifact_namespace="notify_llm_deep",
                telegram_ready=False,
                send_guard_enabled=False,
                lock_status=SimpleNamespace(state="missing", message="no lock"),
                provider_status=provider_status,
                provider_health_rows={},
                delivery_ledger_path=tmp_path / "deliveries.jsonl",
                notification_run_ledger_path=tmp_path / "runs.jsonl",
                research_cards_dir=tmp_path / "cards",
                artifact_doctor_status="OK",
                cooldown_status={},
                llm_budget_status="provider=openai max_run=200",
                clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
                send_readiness=readiness,
                delivery_rows=[row],
                delivery_history_rows=[
                    {
                        "run_id": "old-run",
                        "lane": "daily_digest",
                        "identity_reconciliation_reason": "source_alert_identity_api",
                    },
                    row,
                ],
            )
        )
        assert "pre-canonical notification delivery rows" in stale_text
        stale_go = go.build_go_no_go(
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            telegram_ready=False,
            send_guard_enabled=False,
            lock_status=SimpleNamespace(state="missing", message="no lock"),
            provider_status=provider_status,
            provider_health_rows={},
            delivery_ledger_path=tmp_path / "deliveries.jsonl",
            notification_run_ledger_path=tmp_path / "runs.jsonl",
            research_cards_dir=tmp_path / "cards",
            artifact_doctor_status="OK",
            cooldown_status={},
            llm_budget_status="provider=openai max_run=200",
            clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
            send_readiness=readiness,
            delivery_rows=[row],
            delivery_history_rows=[
                {
                    "run_id": "old-run",
                    "lane": "daily_digest",
                    "identity_reconciliation_reason": "source_alert_identity_api",
                },
                row,
            ],
        )
        stale_final = final_check.build_final_check(
            go_no_go_result=stale_go,
            doctor_status="OK",
            delivery_rows=[row],
            core_rows=[],
        )
        assert stale_final.status == go.RECOMMEND_NOT_READY
        assert any("stale pre-canonical" in item for item in stale_final.blockers)
        fresh_text = go.format_go_no_go(
            go.build_go_no_go(
                profile="notify_llm_deep",
                artifact_namespace="notify_llm_deep_fixture_rehearsal",
                telegram_ready=False,
                send_guard_enabled=False,
                lock_status=SimpleNamespace(state="missing", message="no lock"),
                provider_status=provider_status,
                provider_health_rows={},
                delivery_ledger_path=tmp_path / "deliveries.jsonl",
                notification_run_ledger_path=tmp_path / "runs.jsonl",
                research_cards_dir=tmp_path / "cards",
                artifact_doctor_status="OK",
                cooldown_status={},
                llm_budget_status="provider=openai max_run=200",
                clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
                send_readiness=readiness,
                delivery_rows=[row],
                delivery_history_rows=[row],
            )
        )
        assert "pre-canonical notification delivery rows" not in fresh_text

        real_send = go.build_go_no_go(
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep_rehearsal",
            telegram_ready=True,
            send_guard_enabled=True,
            lock_status=SimpleNamespace(state="missing", message="no lock"),
            provider_status=provider_status,
            provider_health_rows={},
            delivery_ledger_path=tmp_path / "deliveries.jsonl",
            notification_run_ledger_path=tmp_path / "runs.jsonl",
            research_cards_dir=tmp_path / "cards",
            artifact_doctor_status="OK",
            cooldown_status={},
            llm_budget_status="provider=openai max_run=200",
            clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
            send_readiness=readiness,
            delivery_rows=[{**row, "status_detail": delivery.STATUS_DETAIL_SENT, "delivery_state": delivery.STATE_DELIVERED, "sent": True}],
        )
        assert real_send.final_recommendation == go.RECOMMEND_READY_SEND
        assert real_send.ready_to_send_now is True


def test_event_alpha_rehearsal_and_send_readiness_make_targets_are_no_send():
    import os
    import subprocess
    from tempfile import TemporaryDirectory
    from pathlib import Path

    root = _event_alpha_api_helpers.REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert "Fast deterministic fixture final check with compact output" in makefile
    assert "Full real-profile no-send rehearsal" in makefile
    assert "Startup send commands after review" in makefile
    assert "event-alpha-telegram-final-send-checklist" in makefile
    assert "event-alpha-telegram-one-cycle-send-preflight" in makefile
    assert "event-alpha-telegram-send-one-cycle" in makefile
    assert "event-alpha-telegram-post-send-audit" in makefile
    assert "event-alpha-notification-pause" in makefile

    readiness = subprocess.run(
        ["make", "-n", "event-alpha-send-readiness", "PROFILE=notify_llm_deep_rehearsal", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "main.py --event-alpha-send-readiness" in readiness
    assert "--event-alpha-profile notify_llm_deep" in readiness
    assert "--event-alpha-artifact-namespace notify_llm_deep_rehearsal" in readiness
    assert "RSI_EVENT_ALERTS_ENABLED=0" in readiness
    assert "--event-alert-send" not in readiness

    go_no_go = subprocess.run(
        [
            "make",
            "-n",
            "event-alpha-send-go-no-go",
            "PROFILE=notify_llm_deep",
            "ARTIFACT_NAMESPACE=notify_llm_deep_fixture_rehearsal",
            "PYTHON=python3",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "main.py --event-alpha-notify-go-no-go" in go_no_go
    assert "--event-alpha-profile notify_llm_deep" in go_no_go
    assert "--event-alpha-artifact-namespace notify_llm_deep_fixture_rehearsal" in go_no_go
    assert "--event-alpha-include-test-artifacts" in go_no_go
    assert "RSI_EVENT_ALERTS_ENABLED=0" in go_no_go

    smoke_readiness = subprocess.run(
        ["make", "-n", "event-alpha-send-readiness", "PROFILE=notify_llm_deep_no_send_smoke", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "--event-alpha-profile fixture" in smoke_readiness
    assert "--event-alpha-artifact-namespace notify_llm_deep_no_send_smoke" in smoke_readiness
    assert "--event-alpha-include-test-artifacts" in smoke_readiness
    assert "RSI_EVENT_ALERTS_ENABLED=0" in smoke_readiness

    rehearsal = subprocess.run(
        ["make", "-n", "event-alpha-notify-llm-deep-rehearsal-with-fixture-candidate", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "RSI_EVENT_ALPHA_NOTIFY_FIXTURE_PROFILE=notify_llm_deep" in rehearsal
    assert "RSI_EVENT_ALPHA_NOTIFY_FIXTURE_NO_SEND=1" in rehearsal
    assert "RSI_EVENT_ALERTS_ENABLED=0" in rehearsal
    assert "main.py --event-alpha-notify-fixture-smoke" in rehearsal
    assert "main.py --event-alpha-send-readiness" in rehearsal
    assert "main.py --event-alpha-notify-go-no-go" in rehearsal
    assert "main.py --event-alpha-notification-inbox" in rehearsal
    assert "main.py --event-alpha-daily-brief" in rehearsal
    assert "--event-alert-send" not in rehearsal

    fast = subprocess.run(
        ["make", "-n", "event-alpha-notify-llm-deep-real-no-send-rehearsal-fast", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "RSI_EVENT_ALERTS_ENABLED=0" in fast
    assert "RSI_EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS=180" in fast
    assert "RSI_EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN=10" in fast
    assert "RSI_EVENT_LLM_MAX_CALLS_PER_RUN=40" in fast
    assert "main.py --event-alpha-notify-cycle" in fast
    assert "main.py --event-alpha-artifact-doctor" in fast
    assert "main.py --event-alpha-send-readiness" in fast
    assert "--event-alert-send" in fast

    final_check = subprocess.run(
        ["make", "-n", "event-alpha-telegram-no-send-final-check", "PROFILE=notify_llm_deep_rehearsal", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "event-alpha-notify-llm-deep-real-no-send-rehearsal-fast" in final_check
    assert "event-alpha-artifact-doctor PROFILE=notify_llm_deep_rehearsal STRICT=1" in final_check
    assert "event-alpha-send-readiness PROFILE=notify_llm_deep_rehearsal" in final_check
    assert "event-alpha-send-go-no-go PROFILE=notify_llm_deep_rehearsal" in final_check
    assert "event-alpha-notification-inbox PROFILE=notify_llm_deep_rehearsal BURN_IN_REVIEW=1" in final_check
    assert "event-alpha-daily-brief PROFILE=notify_llm_deep_rehearsal" in final_check
    assert "RSI_EVENT_ALERTS_ENABLED=0" in final_check
    assert "Full Event Alpha no-send final check" in final_check

    fast_final = subprocess.run(
        ["make", "-n", "event-alpha-telegram-no-send-final-check-fast", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "Fast deterministic Event Alpha final check" in fast_final
    assert "main.py --event-alpha-notify-fixture-smoke" in fast_final
    assert "RSI_EVENT_ALPHA_NOTIFY_FIXTURE_PROFILE=notify_llm_deep" in fast_final
    assert "RSI_EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED=1" in fast_final
    assert "RSI_EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_SEND_WITH_ALERTS=1" in fast_final
    assert "event-alpha-notify-llm-deep-fixture-rehearsal-artifacts" not in fast_final
    assert "$(MAKE)" not in fast_final
    assert "main.py --event-alpha-notification-inbox" in fast_final
    assert "main.py --event-alpha-daily-brief" in fast_final
    assert "main.py --event-alpha-telegram-final-check" in fast_final
    assert "--event-alpha-artifact-namespace notify_llm_deep_fixture_rehearsal" in fast_final
    assert "main.py --event-alpha-notify-cycle" not in fast_final
    assert "event-alpha-send-go-no-go" not in fast_final
    assert "event-alpha-telegram-send-readiness-final" not in fast_final
    assert "GDELT" not in fast_final
    assert "CryptoPanic" not in fast_final

    trust_target = subprocess.run(
        ["make", "-n", "event-alpha-telegram-send-readiness-final", "PROFILE=notify_llm_deep_fixture_rehearsal", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "main.py --event-alpha-telegram-final-check" in trust_target
    assert "--event-alpha-profile notify_llm_deep" in trust_target
    assert "--event-alpha-artifact-namespace notify_llm_deep_fixture_rehearsal" in trust_target
    assert "--event-alpha-include-test-artifacts" in trust_target
    assert "main.py --event-alpha-notify-cycle" not in trust_target

    one_cycle_preflight = subprocess.run(
        ["make", "-n", "event-alpha-telegram-one-cycle-send-preflight", "PROFILE=notify_llm_deep_fixture_rehearsal", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "main.py --event-alpha-telegram-final-check" in one_cycle_preflight
    assert "--event-alpha-profile notify_llm_deep" in one_cycle_preflight
    assert "--event-alpha-artifact-namespace notify_llm_deep_fixture_rehearsal" in one_cycle_preflight
    assert "RSI_EVENT_ALERTS_ENABLED=0" in one_cycle_preflight
    assert "event_alpha_one_cycle_send_preflight_passed.marker" in one_cycle_preflight
    assert "main.py --event-alpha-notify-cycle" not in one_cycle_preflight

    guarded_send = subprocess.run(
        ["make", "-n", "event-alpha-telegram-send-one-cycle", "PROFILE=notify_llm_deep", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "Refusing Event Alpha one-cycle Telegram send: set RSI_EVENT_ALERTS_ENABLED=1" in guarded_send
    assert "Refusing Event Alpha one-cycle Telegram send: run make event-alpha-telegram-one-cycle-send-preflight" in guarded_send
    assert "TELEGRAM_BOT_TOKEN" in guarded_send
    assert "This will send Telegram messages." in guarded_send
    assert "--event-alpha-artifact-namespace notify_llm_deep_rehearsal" in guarded_send
    assert "main.py --event-alpha-telegram-final-check" in guarded_send
    assert "main.py --event-alpha-notify-cycle" in guarded_send
    assert "--event-alert-send" in guarded_send

    post_send_audit = subprocess.run(
        ["make", "-n", "event-alpha-telegram-post-send-audit", "PROFILE=notify_llm_deep", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "main.py --event-alpha-artifact-doctor" in post_send_audit
    assert "--event-alpha-artifact-doctor-delivery-scope latest_run" in post_send_audit
    assert "main.py --event-alpha-notification-deliveries-report" in post_send_audit
    assert "main.py --event-alpha-notification-inbox" in post_send_audit
    assert "main.py --event-alpha-feedback-readiness" in post_send_audit
    assert "main.py --event-alpha-telegram-final-check" in post_send_audit

    checklist = subprocess.run(
        ["make", "-n", "event-alpha-telegram-final-send-checklist", "PROFILE=notify_llm_deep_rehearsal", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "Event Alpha Telegram final-send checklist" in checklist
    assert "make event-alpha-telegram-no-send-final-check PROFILE=notify_llm_deep_rehearsal" in checklist
    assert "make event-alpha-telegram-one-cycle-send-preflight PROFILE=notify_llm_deep_rehearsal" in checklist
    assert "RSI_EVENT_ALERTS_ENABLED=1 CONFIRM=1 make event-alpha-telegram-send-one-cycle PROFILE=notify_llm_deep" in checklist
    assert "main.py --event-alpha-telegram-final-check" in checklist
    assert "main.py --event-alpha-notify-cycle" not in checklist

    with TemporaryDirectory() as tmp:
        refused = subprocess.run(
            [
                "make",
                "event-alpha-telegram-send-one-cycle",
                "PROFILE=notify_llm_deep",
                "EVENT_ALPHA_ARTIFACT_BASE_DIR=" + tmp,
                "PYTHON=python3",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            env={**os.environ, "RSI_EVENT_ALERTS_ENABLED": "0"},
        )
        assert refused.returncode != 0
        assert "set RSI_EVENT_ALERTS_ENABLED=1" in (refused.stdout + refused.stderr)

        no_confirm = subprocess.run(
            [
                "make",
                "event-alpha-telegram-send-one-cycle",
                "PROFILE=notify_llm_deep",
                "EVENT_ALPHA_ARTIFACT_BASE_DIR=" + tmp,
                "PYTHON=python3",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            env={**os.environ, "RSI_EVENT_ALERTS_ENABLED": "1"},
        )
        assert no_confirm.returncode != 0
        assert "CONFIRM=1" in (no_confirm.stdout + no_confirm.stderr)

        no_telegram = subprocess.run(
            [
                "make",
                "event-alpha-telegram-send-one-cycle",
                "PROFILE=notify_llm_deep",
                "EVENT_ALPHA_ARTIFACT_BASE_DIR=" + tmp,
                "CONFIRM=1",
                "PYTHON=python3",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            env={**os.environ, "RSI_EVENT_ALERTS_ENABLED": "1", "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""},
        )
        assert no_telegram.returncode != 0
        assert "missing TELEGRAM_BOT_TOKEN" in (no_telegram.stdout + no_telegram.stderr)


def test_event_alpha_pause_blocks_delivery_and_resume_requires_confirm():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.pause as pause
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        state = pause.write_pause_state(ctx, reason="maintenance window", now=datetime(2026, 6, 20, tzinfo=timezone.utc))
        assert state.paused
        refused = pause.clear_pause_state(ctx, confirm=False)
        assert refused.paused
        cleared = pause.clear_pause_state(ctx, confirm=True)
        assert not cleared.paused
        state = pause.write_pause_state(ctx, reason="maintenance window", now=datetime(2026, 6, 20, tzinfo=timezone.utc))

        path = Path(tmp) / "deliveries.jsonl"
        cfg = delivery.NotificationDeliveryConfig(path=path, dedupe_window_hours=24)
        result = notif.send_notifications(
            [_notify_route_decision("VELVET", event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION, event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH)],
            storage=_NotifyFakeStorage(),
            cfg=notif.EventAlphaNotificationConfig(
                enabled=True,
                mode="research_only",
                instant_escalation_cooldown_hours=0,
                health_heartbeat_enabled=False,
            ),
            send_fn=lambda message: True,
            now=datetime(2026, 6, 20, 12, tzinfo=timezone.utc),
            delivery_cfg=cfg,
            run_id="run-paused",
            namespace="notify_no_key",
            pause_state=state,
        )
        assert not result.attempted
        assert result.deliveries_blocked == 1
        rows = delivery.load_delivery_records(path)
        assert rows[-1]["state"] == delivery.STATE_BLOCKED
        assert rows[-1]["error_class"] == "notifications_paused"


def test_event_alpha_scheduler_slo_and_notification_pack_are_redacted():
    import tempfile
    import zipfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.pack as pack
    import crypto_rsi_scanner.event_alpha.notifications.slo as slo
    import crypto_rsi_scanner.event_alpha.config.scheduler as scheduler

    now = datetime(2026, 6, 20, 12, tzinfo=timezone.utc)
    run = {
        "row_type": "event_alpha_notification_run",
        "run_id": "run1",
        "started_at": (now - timedelta(hours=1)).isoformat(),
        "cycle_completed": True,
        "success": True,
        "would_send_count": 1,
        "send_requested": True,
        "send_guard_enabled": True,
        "deliveries_failed": 1,
    }
    failed = {
        "row_type": "event_alpha_notification_delivery",
        "delivery_id": "d1",
        "state": delivery.STATE_FAILED,
        "lane": "daily_digest",
        "attempted_at": (now - timedelta(minutes=5)).isoformat(),
    }
    sched = scheduler.build_scheduler_status(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        run_rows=[run],
        delivery_rows=[failed],
        lock_status=SimpleNamespace(state="held", message="active lock"),
        provider_health_rows={"gdelt": {"disabled_until": now.isoformat()}},
        health_guard_status="DEGRADED",
        scheduled_target_exists=True,
        now=now,
    )
    assert sched.latest_run_age_hours < 2
    assert "lock" in " ".join(sched.warnings)
    assert "event-alpha-notify-no-key-scheduled" in scheduler.generate_launchd_plist(
        profile="notify_no_key",
        repo_path="/repo",
        python_path="/repo/.venv/bin/python",
    )

    slo_result = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[run],
        delivery_rows=[failed],
        provider_health_rows={},
        now=now,
    )
    assert slo_result.status == slo.STATUS_BLOCKED
    assert slo_result.alertable_but_undelivered_count == 1
    assert slo_result.delivery_failed_runs == 1

    with tempfile.TemporaryDirectory() as tmp:
        ctx = SimpleNamespace(profile="notify_no_key", artifact_namespace="notify_no_key")
        out = Path(tmp) / "pack.zip"
        result = pack.export_notification_pack(
            out_path=out,
            context=ctx,
            notification_runs=[run],
            delivery_rows=[failed],
            alert_rows=[{"alert_id": "a1", "token": "secret-value"}],
            provider_health_rows={"svc": {"api_key": "secret-value"}},
            go_no_go_text="TELEGRAM_BOT_TOKEN=secret-value",
            environment_doctor_text="OPENAI_API_KEY=secret-value",
            slo_text="ok",
        )
        assert result.files_written >= 7
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
            assert "reports/go_no_go.txt" in names
            body = "\n".join(zf.read(name).decode("utf-8") for name in names)
            assert "secret-value" not in body
            assert ".env" not in names


def test_event_alpha_notification_operational_make_targets_exist():
    from pathlib import Path
    import inspect
    import subprocess
    from crypto_rsi_scanner import scanner

    text = Path("Makefile").read_text(encoding="utf-8")
    for target in (
        "event-alpha-environment-doctor:",
        "event-alpha-scheduler-status:",
        "event-alpha-notification-slo-report:",
        "event-alpha-export-notification-pack:",
        "event-alpha-pause-notifications:",
        "event-alpha-resume-notifications:",
    ):
        assert target in text
    dry = subprocess.run(
        ["make", "-n", "event-alpha-environment-doctor", "PROFILE=notify_no_key", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-environment-doctor --event-alpha-profile notify_no_key" in dry
    assert "include_diagnostics" in inspect.signature(scanner.event_alpha_notification_slo_report).parameters


def test_event_alpha_notification_slo_distinguishes_preview_config_and_delivery_failures():
    from datetime import datetime, timedelta, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.slo as slo

    now = datetime(2026, 6, 20, 12, tzinfo=timezone.utc)
    base = {
        "row_type": "event_alpha_notification_run",
        "started_at": (now - timedelta(minutes=10)).isoformat(),
        "cycle_completed": True,
        "would_send_count": 1,
    }

    preview = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[{**base, "send_requested": False, "send_guard_enabled": False}],
        delivery_rows=[],
        provider_health_rows={},
        now=now,
    )
    assert preview.status == slo.STATUS_OK
    assert preview.no_send_preview_runs == 1
    assert preview.alertable_delivery_failures == 0
    assert not preview.blockers
    assert any("would-send preview" in warning for warning in preview.warnings)

    config_blocked = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[{
            **base,
            "send_requested": True,
            "send_guard_enabled": False,
            "block_reason": "event alerts disabled",
            "deliveries_blocked": 1,
        }],
        delivery_rows=[{
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "blocked",
            "state": delivery.STATE_BLOCKED,
            "error_class": "guard_blocked",
            "lane": "health_heartbeat",
            "attempted_at": now.isoformat(),
        }],
        provider_health_rows={},
        now=now,
    )
    assert config_blocked.status == slo.STATUS_NO_SEND_CONFIG
    assert config_blocked.config_blocked_runs == 1
    assert config_blocked.alertable_delivery_failures == 0
    assert config_blocked.delivery_failure_count == 0

    delivery_failed = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[{
            **base,
            "send_requested": True,
            "send_guard_enabled": True,
            "deliveries_failed": 1,
            "block_reason": "no channel delivered",
        }],
        delivery_rows=[{
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "failed",
            "state": delivery.STATE_FAILED,
            "lane": "daily_digest",
            "attempted_at": now.isoformat(),
        }],
        provider_health_rows={},
        now=now,
    )
    assert delivery_failed.status == slo.STATUS_BLOCKED
    assert delivery_failed.delivery_failed_runs == 1
    assert delivery_failed.alertable_delivery_failures == 1

    delivered_heartbeat = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[{
            **base,
            "send_requested": True,
            "send_guard_enabled": True,
            "deliveries_delivered": 1,
            "heartbeat_sent": True,
        }],
        delivery_rows=[{
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivered",
            "state": delivery.STATE_DELIVERED,
            "lane": "health_heartbeat",
            "attempted_at": now.isoformat(),
            "delivered_at": now.isoformat(),
        }],
        provider_health_rows={},
        now=now,
    )
    assert delivered_heartbeat.status == slo.STATUS_OK
    assert delivered_heartbeat.last_heartbeat_age_hours == 0

    delivered_after_old_config_block = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[
            {
                **base,
                "started_at": (now - timedelta(minutes=5)).isoformat(),
                "send_requested": True,
                "send_guard_enabled": True,
                "deliveries_delivered": 1,
                "heartbeat_sent": True,
            },
            {
                **base,
                "started_at": (now - timedelta(hours=2)).isoformat(),
                "send_requested": True,
                "send_guard_enabled": False,
                "block_reason": "event alerts disabled",
                "deliveries_blocked": 1,
            },
        ],
        delivery_rows=[{
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivered-latest",
            "state": delivery.STATE_DELIVERED,
            "lane": "health_heartbeat",
            "attempted_at": (now - timedelta(minutes=5)).isoformat(),
            "delivered_at": (now - timedelta(minutes=5)).isoformat(),
        }],
        provider_health_rows={},
        now=now,
    )
    assert delivered_after_old_config_block.status == slo.STATUS_OK
    assert delivered_after_old_config_block.config_blocked_runs == 1
    assert delivered_after_old_config_block.alertable_delivery_failures == 0

    provider_backoff_preview = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[{**base, "send_requested": False, "send_guard_enabled": False}],
        delivery_rows=[],
        provider_health_rows={"gdelt": {"disabled_until": now.isoformat()}},
        now=now,
    )
    assert provider_backoff_preview.status == slo.STATUS_DEGRADED
    assert provider_backoff_preview.alertable_delivery_failures == 0
    assert any("provider" in warning for warning in provider_backoff_preview.warnings)
