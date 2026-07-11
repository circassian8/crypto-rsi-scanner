"""Namespace run ledgers, locks, delivery isolation, stale markers, and scheduled-target regressions."""

from __future__ import annotations

from pathlib import Path

from crypto_rsi_scanner.event_alpha.namespace import lifecycle

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alpha_run_ledger_records_send_accounting():
    import tempfile
    from dataclasses import replace
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as event_alpha_run_ledger
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult

    now = datetime(2026, 6, 18, 13, 0, tzinfo=timezone.utc)

    def empty_loader(observed, raw_event_transform):
        return EventDiscoveryResult((), (), (), (), ())

    with tempfile.TemporaryDirectory() as tmp:
        watch_path = Path(tmp) / "watchlist.jsonl"
        no_decisions = event_alpha_pipeline.run_event_alpha_operating_cycle(
            load_discovery_result=empty_loader,
            now=now,
            watchlist_cfg=event_watchlist.EventWatchlistConfig(enabled=True, state_path=watch_path),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=False,
            route=True,
            send=True,
            send_callback=lambda decisions: event_alpha_pipeline.EventAlphaSendResult(
                requested=True,
                attempted=True,
                success=True,
                items_attempted=len(decisions),
                items_delivered=len(decisions),
            ),
        )
        assert no_decisions.send_requested is True
        assert no_decisions.send_attempted is False
        assert no_decisions.send_block_reason == "no alertable route decisions"
        cfg = event_alpha_run_ledger.EventAlphaRunLedgerConfig(path=Path(tmp) / "runs.jsonl")
        row = event_alpha_run_ledger.append_run_record(
            no_decisions,
            cfg=cfg,
            profile="fixture",
            started_at=now,
            finished_at=now,
            with_llm=False,
            send_requested=True,
        )
        assert row["send_requested"] is True
        assert row["send_attempted"] is False
        assert row["send_success"] is False
        assert row["send_block_reason"] == "no alertable route decisions"

        delivered = event_alpha_pipeline._normalize_send_result(True, [])
        delivered_result = event_alpha_pipeline._with_send_result(no_decisions, delivered)
        delivered_result = replace(
            delivered_result,
            clock_status={
                "clock_mode": "fixed",
                "research_now": "2026-06-15T16:00:00+00:00",
                "wall_clock_now": "2026-06-20T12:00:00+00:00",
                "fixed_clock_age_hours": 116.0,
            },
        )
        row2 = event_alpha_run_ledger.append_run_record(
            delivered_result,
            cfg=cfg,
            profile="fixture",
            started_at=now,
            finished_at=now,
            with_llm=False,
            send_requested=True,
        )
        assert row2["send_attempted"] is True
        assert row2["send_success"] is True
        assert row2["clock_mode"] == "fixed"
        assert row2["fixed_clock_age_hours"] == 116.0
        assert "send=0/0" in event_alpha_run_ledger.format_run_ledger_report(
            event_alpha_run_ledger.load_run_records(cfg.path)
        )


def test_operator_state_same_run_backfill_preserves_manifest_and_uses_exact_artifacts(tmp_path):
    import json
    from datetime import datetime, timezone

    from crypto_rsi_scanner.event_alpha.artifacts import operator_state, run_counters

    namespace = tmp_path / "event_fade_cache" / "notify_no_key"
    namespace.mkdir(parents=True)
    run_id = "2026-07-11T06:28:17+00:00|notify_no_key"
    core_path = namespace / "event_core_opportunities.jsonl"
    core_rows = [
        {
            "row_type": "event_core_opportunity",
            "schema_version": "event_core_opportunity_store_v1",
            "run_id": run_id if index < 3 else "older-run",
            "profile": "notify_no_key",
            "artifact_namespace": "notify_no_key",
            "core_opportunity_id": f"core-{min(index, 1)}" if index < 3 else "old-core",
            "symbol": f"T{index}",
            "coin_id": f"token-{index}",
            "opportunity_type": "DIAGNOSTIC" if index == 2 else "UNCONFIRMED_RESEARCH",
            "candidate_role": "source_noise" if index == 2 else "candidate_asset",
            "final_opportunity_level": "local_only",
            "final_route_after_quality_gate": "STORE_ONLY",
            "generated_at": "2026-07-11T06:30:00+00:00",
        }
        for index in range(4)
    ]
    core_path.write_text("".join(json.dumps(row) + "\n" for row in core_rows), encoding="utf-8")
    preview_path = namespace / "event_alpha_notification_preview.md"
    preview_path.write_text(
        "# Event Alpha Notification Preview\n\n"
        f"run_id: {run_id}\n\n"
        "- preview_rendered_items: 1\n",
        encoding="utf-8",
    )
    run_row = {
        "row_type": "event_alpha_run",
        "run_id": run_id,
        "profile": "notify_no_key",
        "artifact_namespace": "notify_no_key",
        "run_mode": "notification_burn_in",
        "notification_burn_in": True,
        "started_at": "2026-07-11T06:28:17+00:00",
        "raw_events": 10,
        "candidates": 2,
        "alerts": 2,
        "research_candidates": 0,
        "strict_alerts": 0,
        "snapshot_rows_written": 0,
        "core_opportunity_rows_written": 3,
        "core_opportunity_store_path": str(core_path),
        "notification_preview_path": str(preview_path),
        "send_requested": True,
        "send_attempted": False,
        "send_block_reason": "event alerts disabled",
    }
    state = operator_state.begin_run(
        namespace,
        run_row,
        run_ledger_path=namespace / "event_alpha_runs.jsonl",
    )
    preserved_artifacts = dict(state["artifacts"])
    legacy = dict(state)
    for field in (
        "counter_schema_version",
        *run_counters.COUNTER_FIELDS,
        "burn_in_mode",
        "send_guard_status",
    ):
        legacy.pop(field, None)
    legacy["revision"] = 7
    legacy["doctor"] = {
        "status": "OK",
        "run_id": run_id,
        "authoritative": True,
        "strict": True,
        "schema_only": False,
        "skip_api_checks": False,
        "verified_at": "2026-07-11T06:40:00+00:00",
        "verified_revision": 7,
        "blocker_count": 0,
        "warning_count": 0,
    }
    operator_state.write_json_atomic(operator_state.operator_state_path(namespace), legacy)

    backfilled = operator_state.begin_run_if_newer(
        namespace,
        run_row,
        run_ledger_path=namespace / "event_alpha_runs.jsonl",
        updated_at=datetime(2026, 7, 11, 7, 0, tzinfo=timezone.utc),
    )

    assert backfilled is not None
    assert backfilled["revision"] == 8
    assert backfilled["artifacts"] == preserved_artifacts
    assert backfilled["doctor"]["status"] == "stale"
    assert backfilled["invalidation_reason"] == "exact_run_semantics_backfilled"
    assert backfilled["research_candidates"] == 2
    assert backfilled["strict_alerts"] == 0
    assert backfilled["current_generation_core_rows"] == 3
    assert backfilled["current_generation_visible_core_rows"] == 2
    assert backfilled["cumulative_store_rows"] == 4
    assert backfilled["preview_rendered_items"] == 1
    assert backfilled["burn_in_mode"] == "no_send_notification_burn_in"
    assert backfilled["send_requested"] is True
    assert backfilled["send_attempted"] is False
    assert backfilled["no_send_rehearsal"] is True


def test_event_alpha_run_ledger_normalizer_migrates_legacy_absolute_paths(tmp_path):
    import json
    from unittest import mock
    import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as event_alpha_run_ledger

    namespace_dir = tmp_path / "event_fade_cache" / "notify_no_key"
    run_path = namespace_dir / "event_alpha_runs.jsonl"
    run_path.parent.mkdir(parents=True)
    legacy = {
        "row_type": "event_alpha_run",
        "run_id": "legacy-live-send",
        "profile": "notify_no_key",
        "sent": True,
        "send_requested": True,
        "send_attempted": True,
        "send_success": True,
        "send_items_delivered": 1,
        "run_ledger_path": str(run_path),
        "alert_store_path": str(namespace_dir / "event_alpha_alerts.jsonl"),
        "watchlist_state_path": str(namespace_dir / "event_watchlist_state.jsonl"),
        "research_cards_dir": str(namespace_dir / "research_cards"),
    }
    second = {
        **legacy,
        "run_id": "legacy-live-send-second",
        "send_items_delivered": 2,
        "business_note": "preserve row order and evidence",
    }
    original_bytes = (json.dumps(legacy) + "\n" + json.dumps(second) + "\n").encode()
    run_path.write_bytes(original_bytes)

    with mock.patch.object(
        event_alpha_run_ledger.os,
        "replace",
        side_effect=OSError("simulated atomic replace failure"),
    ):
        assert event_alpha_run_ledger.rewrite_normalized_run_records(run_path) == 0
        assert run_path.read_bytes() == original_bytes
        assert list(run_path.parent.glob(f".{run_path.name}.*.tmp")) == []

    assert event_alpha_run_ledger.rewrite_normalized_run_records(run_path) == 2
    migrated_rows = [json.loads(line) for line in run_path.read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in migrated_rows] == [legacy["run_id"], second["run_id"]]
    migrated = migrated_rows[0]
    assert migrated["sent"] is True
    assert migrated["run_ledger_path"] == "event_fade_cache/notify_no_key/event_alpha_runs.jsonl"
    assert migrated["research_cards_dir"] == "event_fade_cache/notify_no_key/research_cards"
    assert migrated["run_ledger_path_abs_debug"] == str(run_path)
    assert migrated["research_cards_dir_abs_debug"] == str(namespace_dir / "research_cards")
    assert migrated_rows[1]["business_note"] == second["business_note"]
    assert migrated_rows[1]["send_items_delivered"] == 2
    assert event_alpha_run_ledger.rewrite_normalized_run_records(run_path) == 0


def test_event_alpha_run_lock_acquire_skip_recover_and_release():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.locks as lock

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        cfg = lock.EventAlphaRunLockConfig(enabled=True, stale_minutes=30, allow_overlap=False)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        first = lock.acquire_run_lock(ctx, cfg=cfg, run_id="r1", now=now)
        assert first.acquired and first.owned
        assert first.status.state == lock.STATE_ACQUIRED
        assert first.path.name == "event_alpha_notify.lock"
        assert first.path.exists()

        second = lock.acquire_run_lock(ctx, cfg=cfg, run_id="r2", now=now)
        assert not second.acquired
        assert second.skipped_due_to_active_lock
        assert second.status.state == lock.STATE_ACTIVE
        assert not second.owned

        stale_now = datetime(2026, 6, 20, 13, 0, tzinfo=timezone.utc)
        recovered = lock.acquire_run_lock(ctx, cfg=cfg, run_id="r3", now=stale_now)
        assert recovered.acquired
        assert recovered.stale_recovered
        assert lock.STALE_LOCK_RECOVERED_WARNING in recovered.warnings

        assert lock.release_run_lock(recovered) is True
        assert not recovered.path.exists()
        assert lock.inspect_run_lock(ctx, now=stale_now).state == lock.STATE_MISSING


def test_event_alpha_run_lock_release_after_failsoft_and_distinct_profile_paths():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.locks as lock

    with tempfile.TemporaryDirectory() as tmp:
        no_key = _notify_artifact_context(tmp, "notify_no_key")
        llm = _notify_artifact_context(tmp, "notify_llm")
        cfg = lock.EventAlphaRunLockConfig(enabled=True, stale_minutes=30)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        assert lock.lock_path_for_context(no_key) != lock.lock_path_for_context(llm)
        held = lock.acquire_run_lock(no_key, cfg=cfg, run_id="r1", now=now)
        try:
            raise RuntimeError("provider blew up (fail-soft)")
        except RuntimeError:
            pass
        assert lock.release_run_lock(held) is True
        assert not held.path.exists()
        assert lock.lock_path_for_context(no_key, lock_name="other").name == "event_alpha_other.lock"


def test_event_alpha_artifact_mutation_lock_is_shared_and_survives_namespace_cleanup(tmp_path):
    import shutil
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.locks as lock

    ctx = _notify_artifact_context(str(tmp_path), "notify_no_key")
    ctx.namespace_dir.mkdir(parents=True)
    now = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
    held = lock.acquire_artifact_mutation_lock(
        ctx,
        run_id="writer-a",
        profile=ctx.profile,
        namespace=ctx.artifact_namespace,
        now=now,
    )
    assert held.owned is True
    assert held.path.parent == ctx.namespace_dir.parent
    assert held.path.parent != ctx.namespace_dir
    shutil.rmtree(ctx.namespace_dir)
    assert held.path.exists()

    with lock.artifact_mutation_guard(
        ctx,
        profile=ctx.profile,
        namespace=ctx.artifact_namespace,
        command="writer-b",
        now=now,
    ) as blocked:
        assert blocked.owned is False
        assert blocked.skipped_due_to_active_lock is True

    assert lock.release_run_lock(held) is True
    assert not held.path.exists()


def test_event_alpha_run_lock_acquisition_is_atomic():
    # Two runs starting at the same instant (both would read "no lock") must not
    # both acquire: O_CREAT|O_EXCL makes exactly one win.
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.locks as lock

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        cfg = lock.EventAlphaRunLockConfig(enabled=True, stale_minutes=30)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        a = lock.acquire_run_lock(ctx, cfg=cfg, run_id="A", now=now)
        b = lock.acquire_run_lock(ctx, cfg=cfg, run_id="B", now=now)
        assert [a.acquired, b.acquired].count(True) == 1
        assert [a.skipped_due_to_active_lock, b.skipped_due_to_active_lock].count(True) == 1
        winner = a if a.acquired else b
        holder = lock._read_lock(lock.lock_path_for_context(ctx))
        assert holder is not None and holder["run_id"] == winner.run_id


def test_event_alpha_run_lock_disabled_for_fixture_smoke():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.locks as lock

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "fixture")
        cfg = lock.EventAlphaRunLockConfig(enabled=False)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        disabled = lock.acquire_run_lock(ctx, cfg=cfg, run_id="r1", now=now)
        assert disabled.acquired
        assert disabled.status.state == lock.STATE_DISABLED
        assert not disabled.path.exists()
        assert lock.release_run_lock(disabled) is False


def test_event_alpha_notify_cycle_releases_lock_on_exception():
    # The notify-cycle wrapper must release the run lock in a finally even when
    # the cycle body raises after acquiring (best-effort release on exceptions).
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.artifacts.locks as lock

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        run_lock = lock.acquire_run_lock(
            ctx, cfg=lock.EventAlphaRunLockConfig(enabled=True), run_id="r1",
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
        )
        assert run_lock.owned and run_lock.path.exists()

        def boom(*, lock_holder, **kwargs):
            lock_holder["lock"] = run_lock
            raise RuntimeError("kaboom in cycle body")

        original = scanner._event_alpha_notify_cycle_body
        scanner._event_alpha_notify_cycle_body = boom
        try:
            try:
                scanner.event_alpha_notify_cycle(profile_name="notify_no_key")
            except RuntimeError:
                pass
        finally:
            scanner._event_alpha_notify_cycle_body = original
        assert not run_lock.path.exists()


def test_event_alpha_delivery_ledger_records_dedupe_and_namespace_isolation():
    import tempfile
    from datetime import datetime, timezone, timedelta
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        path = delivery.deliveries_path_for_context(ctx)
        assert path == Path(tmp) / "notify_no_key" / "event_alpha_notification_deliveries.jsonl"
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        content_hash = delivery.compute_content_hash("digest body", alert_id="ea:A", lane="daily_digest", profile="notify_no_key")
        rec = delivery.build_record(
            run_id="r1", alert_id="ea:A", profile="notify_no_key", namespace="notify_no_key",
            lane="daily_digest", route="RESEARCH_DIGEST", content_hash=content_hash,
            state=delivery.STATE_DELIVERED, now=now, delivered_at=now, delivered_count=1,
        )
        delivery.append_delivery_record(rec, path=path)
        rows = delivery.load_delivery_records(path)
        assert len(rows) == 1 and rows[0]["state"] == "delivered"
        assert delivery.find_recent_delivered(rows, content_hash=content_hash, namespace="notify_no_key", now=now, window_hours=24) is not None
        assert delivery.find_recent_delivered(rows, content_hash=content_hash, namespace="notify_llm", now=now, window_hours=24) is None
        assert delivery.find_recent_delivered(rows, content_hash=content_hash, namespace="notify_no_key", now=now + timedelta(hours=48), window_hours=24) is None
        other = delivery.compute_content_hash("digest body", alert_id="ea:B", lane="triggered_fade", profile="notify_no_key")
        assert other != content_hash
        summary = delivery.summarize_delivery_rows(rows)
        assert summary.delivered == 1 and summary.failed == 0


def test_event_alpha_artifact_doctor_short_circuits_stale_namespace_marker():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.namespace.status as event_alpha_namespace_status
    import crypto_rsi_scanner.event_alpha.notifications.readiness as event_alpha_send_readiness

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        namespace_dir = base / "notify_llm_deep"
        preview = namespace_dir / "event_alpha_notification_preview.md"
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_text("send guard: no-send rehearsal\n", encoding="utf-8")
        marker = event_alpha_namespace_status.mark_namespace_stale(
            namespace_dir,
            namespace="notify_llm_deep",
            reason="pre-canonical notification artifacts",
            superseded_by="notify_llm_deep_rehearsal",
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
        )
        assert marker.exists()
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "old", "profile": "notify_llm_deep", "artifact_namespace": "notify_llm_deep", "run_mode": "burn_in"}],
            source_coverage_report_path=namespace_dir / "event_alpha_source_coverage.md",
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            strict=True,
        )
        assert result.status == "STALE"
        assert result.namespace_stale_deprecated == 1
        assert result.namespace_superseded_by == "notify_llm_deep_rehearsal"
        assert result.schema_rows_validated == 0
        assert result.schema_validation_errors == 0
        assert "safe_for_send_readiness: false" in "\n".join(result.warnings)
        included = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "old", "profile": "notify_llm_deep", "artifact_namespace": "notify_llm_deep", "run_mode": "burn_in"}],
            source_coverage_report_path=namespace_dir / "event_alpha_source_coverage.md",
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            strict=False,
            include_stale_artifacts=True,
        )
        assert included.namespace_stale_deprecated == 1
        plan = event_alpha_namespace_status.stale_namespace_plan(namespace_dir)
        assert plan["dry_run_only"] is True
        assert plan["file_count"] >= 1
        readiness = event_alpha_send_readiness.build_send_readiness(
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            run_rows=[{
                "run_id": "old",
                "profile": "notify_llm_deep",
                "artifact_namespace": "notify_llm_deep",
                "run_mode": "burn_in",
                "cycle_completed": True,
                "success": True,
            }],
            core_opportunity_rows=[],
            alert_rows=[],
            delivery_rows=[],
            artifact_doctor=included,
            send_guard_enabled=False,
            telegram_ready=False,
            preview_path=preview,
            include_api_artifacts=True,
        )
        assert readiness.ready is False
        assert any("stale/deprecated" in item for item in readiness.blockers)


def test_event_alpha_scheduled_make_targets_use_profile_lock_and_no_fixed_clock():
    import subprocess
    from pathlib import Path

    root = _event_alpha_api_helpers.REPO_ROOT
    for target, profile in (
        ("event-alpha-notify-no-key-scheduled", "notify_no_key"),
        ("event-alpha-notify-llm-scheduled", "notify_llm"),
        ("event-alpha-notify-llm-deep-scheduled", "notify_llm_deep"),
    ):
        out = subprocess.run(["make", "-n", target], cwd=root, capture_output=True, text=True, check=True).stdout
        assert f"--event-alpha-profile {profile}" in out
        assert "RSI_EVENT_ALPHA_NOTIFY_LOCK_ENABLED=1" in out
        assert "RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT=0" in out
        assert "RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_WINDOW_HOURS=0" in out
        assert f"RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE={profile}" in out
        assert "RSI_EVENT_RESEARCH_NOW" not in out
        assert "--score" not in out
        assert "paper" not in out
        assert "main.py --event-alpha-notify-cycle" in out
