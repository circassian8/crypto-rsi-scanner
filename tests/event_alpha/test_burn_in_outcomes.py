"""Focused Event Alpha outcomes and quality tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alpha_daily_brief_replay_retention_and_unmatched_feedback():
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.artifacts.replay as event_alpha_replay
    import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_labels as event_feedback

    entry = _test_watchlist_entry(state="HIGH_PRIORITY", symbol="VELVET", coin_id="velvet")
    markdown = event_alpha_daily_brief.build_daily_brief(
        run_rows=[{
            "run_id": "run-1",
            "run_mode": "burn_in",
            "artifact_namespace": "no_key_live",
            "success": True,
            "raw_events": 2,
            "candidates": 1,
            "alerts": 1,
            "routed": 1,
            "alertable": 0,
            "llm_calls_attempted": 0,
            "llm_skipped_due_budget": 1,
        }],
        alert_rows=[{"run_mode": "burn_in", "artifact_namespace": "no_key_live", "run_id": "run-1", "alert_key": entry.key, "tier": "HIGH_PRIORITY_WATCH", "asset_symbol": "VELVET", "playbook_type": "proxy_attention"}],
        watchlist_entries=[entry],
        provider_health_rows={"gdelt": {"provider_kind": "event_source", "consecutive_failures": 2, "disabled_until": "2026-06-18T10:30:00+00:00"}},
        card_paths=[Path("/tmp/velvet.md")],
    )
    assert "Event Alpha Daily Brief" in markdown
    assert "Why No Strict Alerts" in markdown
    assert "Provider Health" in markdown
    assert "LLM Budget" in markdown
    assert "Watchlist Got Hotter" in markdown
    assert "Calibration Recommendations" in markdown
    assert ".env" not in markdown

    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor as event_watchlist_monitor
    entry_fade = __import__("dataclasses").replace(
        entry,
        latest_playbook_type="proxy_fade",
        latest_effective_playbook_type="proxy_fade",
    )
    monitor_row = event_watchlist_monitor.EventWatchlistMonitorRow(
        key=entry_fade.key,
        symbol="VELVET",
        coin_id="velvet",
        state="HIGH_PRIORITY",
        event_name="SpaceX pre-IPO exposure",
        event_time="2026-06-16T00:00:00+00:00",
        event_countdown_hours=None,
        event_age_hours=12.0,
        current_price=1.23,
        return_24h=0.24,
        return_72h=0.72,
        return_7d=1.4,
        volume_to_market_cap=0.4,
        volume_zscore_24h=4.5,
        derivatives_crowding=68,
        supply_pressure=20,
        cluster_confidence=80,
        state_transition_hints=("MARKET_SCORE_JUMP", "DERIVATIVES_HEATED"),
        material_update=True,
    )
    card = event_research_cards.render_research_card(
        entry_fade.key,
        watchlist_entries=[entry_fade],
        alert_rows=[{
            "alert_key": entry_fade.key,
            "asset_symbol": "VELVET",
            "asset_coin_id": "velvet",
            "event_name": "SpaceX pre-IPO exposure",
            "playbook_type": "proxy_fade",
            "expected_direction": "down",
            "primary_horizon": "24h",
            "playbook_invalidation": "Price reclaims event VWAP",
            "score_components": {"external_catalyst": 90, "event_time_quality": 90, "market_move_volume": 80},
        }],
        monitor_rows=[monitor_row],
    )
    assert "## Research Review Checklist" in card.markdown
    assert "## Latest Monitor Update" in card.markdown
    assert "MARKET_SCORE_JUMP" in card.markdown
    assert "DERIVATIVES_HEATED" in card.markdown
    assert "cannot create TRIGGERED_FADE" in card.markdown
    assert "post-event failure" in card.markdown

    replay = event_alpha_replay.replay_from_artifacts(
        alert_rows=[{"alert_key": "a1", "tier": "WATCHLIST", "route": "RESEARCH_DIGEST", "opportunity_score": 50}],
        watchlist_rows=[{"key": entry.key}],
        priors_enabled=True,
        llm_advisory=True,
    )
    assert replay.alert_rows == 1
    assert "local artifacts only" in event_alpha_replay.format_replay_report(replay)

    tmp = Path(tempfile.mkdtemp())
    feedback_cfg = event_feedback.EventFeedbackConfig(path=tmp / "feedback.jsonl")
    record = event_feedback.mark_feedback(
        "UNKNOWN",
        "junk",
        watchlist_entries=[],
        cfg=feedback_cfg,
        allow_unmatched=True,
        notes="bad key",
    )
    assert record.source == "manual_cli_unmatched"
    assert "warning:" in (record.notes or "")

    runs = tmp / "runs.jsonl"
    alerts = tmp / "alerts.jsonl"
    cards = tmp / "cards"
    cards.mkdir()
    runs.write_text(
        '{"row_type":"event_alpha_run","run_id":"old","started_at":"2024-01-01T00:00:00+00:00"}\n'
        '{"row_type":"event_alpha_run","run_id":"latest","started_at":"2025-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    alerts.write_text('{"row_type":"event_alpha_alert_snapshot","observed_at":"2025-01-01T00:00:00+00:00"}\n', encoding="utf-8")
    old_card = cards / "old.md"
    old_card.write_text("# old\n", encoding="utf-8")
    cfg = event_alpha_retention.EventAlphaRetentionConfig(
        runs_path=runs,
        alerts_path=alerts,
        cards_dir=cards,
        run_days=1,
        alert_days=1,
        card_days=1,
    )
    dry = event_alpha_retention.prune_event_alpha_artifacts(cfg, confirm=False, now=__import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc))
    assert dry.dry_run is True
    assert dry.runs_pruned == 1
    assert runs.read_text(encoding="utf-8").strip()
    confirmed = event_alpha_retention.prune_event_alpha_artifacts(cfg, confirm=True, now=__import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc))
    assert confirmed.dry_run is False
    retained_runs = [json.loads(line) for line in runs.read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in retained_runs] == ["latest"]


def test_event_alpha_retention_plans_major_append_only_stores_and_preserves_latest_generation(tmp_path):
    import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention

    stores = {
        "event_alpha_runs.jsonl": ("started_at", True),
        "event_alpha_alerts.jsonl": ("observed_at", True),
        "event_core_opportunities.jsonl": ("generated_at", True),
        "event_impact_hypotheses.jsonl": ("observed_at", True),
        "event_incidents.jsonl": ("observed_at", True),
        "event_watchlist_state.jsonl": ("last_seen_at", False),
        "event_alpha_notification_deliveries.jsonl": ("attempted_at", True),
        "event_alpha_notification_runs.jsonl": ("started_at", True),
        "event_evidence_acquisition.jsonl": ("observed_at", True),
    }
    before: dict[str, bytes] = {}
    for filename, (timestamp_field, uses_run_id) in stores.items():
        rows = [
            {"row_type": "test", timestamp_field: "2024-01-01T00:00:00+00:00"},
            {"row_type": "test", timestamp_field: "2025-01-01T00:00:00+00:00"},
            {"row_type": "test", timestamp_field: "2025-01-01T00:00:00+00:00"},
        ]
        if uses_run_id:
            rows[0]["run_id"] = "old-generation"
            rows[1]["run_id"] = "latest-generation"
            rows[2]["run_id"] = "latest-generation"
        path = tmp_path / filename
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        before[filename] = path.read_bytes()

    cards = tmp_path / "research_cards"
    cards.mkdir()
    cfg = event_alpha_retention.EventAlphaRetentionConfig(
        runs_path=tmp_path / "event_alpha_runs.jsonl",
        alerts_path=tmp_path / "event_alpha_alerts.jsonl",
        cards_dir=cards,
        run_days=1,
        alert_days=1,
        store_days=1,
    )
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dry = event_alpha_retention.prune_event_alpha_artifacts(cfg, now=now)

    assert dry.dry_run is True
    assert dry.mutation_blocked is False
    assert (
        dry.runs_pruned,
        dry.alerts_pruned,
        dry.core_opportunities_pruned,
        dry.impact_hypotheses_pruned,
        dry.incidents_pruned,
        dry.watchlist_pruned,
        dry.notification_deliveries_pruned,
        dry.notification_runs_pruned,
        dry.evidence_acquisition_pruned,
    ) == (1, 1, 1, 1, 1, 1, 1, 1, 1)
    assert all((tmp_path / filename).read_bytes() == content for filename, content in before.items())

    confirmed = event_alpha_retention.prune_event_alpha_artifacts(cfg, confirm=True, now=now)
    assert confirmed.dry_run is False
    assert confirmed.mutation_blocked is False
    for filename in stores:
        rows = [json.loads(line) for line in (tmp_path / filename).read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 2
        assert all("2025-01-01" in next(value for key, value in row.items() if key.endswith("_at")) for row in rows)
    report = event_alpha_retention.format_retention_report(confirmed)
    assert "append_only_pruned:" in report
    assert "notification_deliveries=1" in report
    assert "evidence_acquisition=1" in report


def test_event_alpha_retention_malformed_row_blocks_every_confirmed_mutation(tmp_path):
    import os
    import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention

    runs = tmp_path / "event_alpha_runs.jsonl"
    runs.write_text(
        '{"run_id":"old","started_at":"2024-01-01T00:00:00+00:00"}\n'
        '{"run_id":"latest","started_at":"2025-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    alerts = tmp_path / "event_alpha_alerts.jsonl"
    alerts.write_text('{"run_id":"latest","observed_at":"2025-01-01T00:00:00+00:00"}\n', encoding="utf-8")
    malformed = tmp_path / "event_core_opportunities.jsonl"
    malformed.write_text('{"run_id":"old","generated_at":"2024-01-01T00:00:00+00:00"}\n{broken\n', encoding="utf-8")
    cards = tmp_path / "research_cards"
    cards.mkdir()
    old_card = cards / "old.md"
    old_card.write_text("# old\n", encoding="utf-8")
    old_epoch = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
    os.utime(old_card, (old_epoch, old_epoch))
    before = {path: path.read_bytes() for path in (runs, alerts, malformed, old_card)}

    result = event_alpha_retention.prune_event_alpha_artifacts(
        event_alpha_retention.EventAlphaRetentionConfig(
            runs_path=runs,
            alerts_path=alerts,
            cards_dir=cards,
            run_days=1,
            alert_days=1,
            store_days=1,
            card_days=1,
        ),
        confirm=True,
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert result.dry_run is True
    assert result.mutation_blocked is True
    assert result.malformed_files == ("event_core_opportunities.jsonl",)
    assert result.runs_pruned == 1
    assert result.cards_pruned == 1
    assert all(path.read_bytes() == content for path, content in before.items())
    assert "mode: blocked" in event_alpha_retention.format_retention_report(result)
    assert any("line 2 is invalid JSON" in warning for warning in result.warnings)
    assert not list(tmp_path.rglob("*.retention.tmp"))


def test_event_alpha_retention_dry_run_never_acquires_notify_lock(tmp_path):
    from unittest.mock import patch

    import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention

    runs = tmp_path / "event_alpha_runs.jsonl"
    runs.write_text(
        '{"run_id":"old","started_at":"2024-01-01T00:00:00+00:00"}\n'
        '{"run_id":"latest","started_at":"2025-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    cfg = event_alpha_retention.EventAlphaRetentionConfig(
        runs_path=runs,
        alerts_path=tmp_path / "event_alpha_alerts.jsonl",
        cards_dir=tmp_path / "research_cards",
        run_days=1,
    )
    with patch.object(
        event_alpha_retention.event_alpha_locks,
        "acquire_run_lock",
        side_effect=AssertionError("dry-run must not acquire a lock"),
    ):
        result = event_alpha_retention.prune_event_alpha_artifacts(
            cfg,
            now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    assert result.dry_run is True
    assert result.mutation_blocked is False
    assert result.runs_pruned == 1


def test_event_alpha_retention_active_notify_lock_blocks_all_mutation(tmp_path):
    from types import SimpleNamespace

    import crypto_rsi_scanner.event_alpha.artifacts.locks as event_alpha_locks
    import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    runs = tmp_path / "event_alpha_runs.jsonl"
    runs.write_text(
        '{"run_id":"old","started_at":"2024-01-01T00:00:00+00:00"}\n'
        '{"run_id":"latest","started_at":"2025-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    before = runs.read_bytes()
    held = event_alpha_locks.acquire_run_lock(
        SimpleNamespace(namespace_dir=tmp_path),
        run_id="active-notify",
        profile="no_key_live",
        namespace=tmp_path.name,
        now=now,
    )
    assert held.owned is True
    try:
        result = event_alpha_retention.prune_event_alpha_artifacts(
            event_alpha_retention.EventAlphaRetentionConfig(
                runs_path=runs,
                alerts_path=tmp_path / "event_alpha_alerts.jsonl",
                cards_dir=tmp_path / "research_cards",
                run_days=1,
            ),
            confirm=True,
            now=now,
        )
    finally:
        assert event_alpha_locks.release_run_lock(held) is True

    assert result.dry_run is True
    assert result.mutation_blocked is True
    assert runs.read_bytes() == before
    assert any("active notification lock" in warning for warning in result.warnings)


def test_event_alpha_retention_active_artifact_mutation_lock_blocks_all_mutation(tmp_path):
    from types import SimpleNamespace

    import crypto_rsi_scanner.event_alpha.artifacts.locks as event_alpha_locks
    import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    runs = tmp_path / "event_alpha_runs.jsonl"
    runs.write_text(
        '{"run_id":"old","started_at":"2024-01-01T00:00:00+00:00"}\n'
        '{"run_id":"latest","started_at":"2025-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    before = runs.read_bytes()
    held = event_alpha_locks.acquire_artifact_mutation_lock(
        SimpleNamespace(namespace_dir=tmp_path),
        run_id="active-writer",
        profile="no_key_live",
        namespace=tmp_path.name,
        now=now,
    )
    assert held.owned is True
    try:
        result = event_alpha_retention.prune_event_alpha_artifacts(
            event_alpha_retention.EventAlphaRetentionConfig(
                runs_path=runs,
                alerts_path=tmp_path / "event_alpha_alerts.jsonl",
                cards_dir=tmp_path / "research_cards",
                run_days=1,
            ),
            confirm=True,
            now=now,
        )
    finally:
        assert event_alpha_locks.release_run_lock(held) is True

    assert result.dry_run is True
    assert result.mutation_blocked is True
    assert runs.read_bytes() == before
    assert any("active artifact mutation lock" in warning for warning in result.warnings)


def test_event_alpha_retention_custom_ledger_uses_canonical_namespace_lock_and_state(tmp_path):
    from types import SimpleNamespace

    import crypto_rsi_scanner.event_alpha.artifacts.locks as event_alpha_locks
    import crypto_rsi_scanner.event_alpha.artifacts.operator_state as event_alpha_operator_state
    import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    namespace_dir = tmp_path / "notify_no_key"
    namespace_dir.mkdir()
    custom_ledger = tmp_path / "custom-ledger" / "runs.jsonl"
    custom_ledger.parent.mkdir()
    custom_ledger.write_text(
        '{"run_id":"old","started_at":"2024-01-01T00:00:00+00:00"}\n'
        '{"run_id":"current","started_at":"2025-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    event_alpha_operator_state.begin_run(
        namespace_dir,
        {
            "run_id": "current",
            "profile": "notify_no_key",
            "artifact_namespace": "notify_no_key",
            "run_mode": "notification_burn_in",
        },
        updated_at=now,
    )
    cfg = event_alpha_retention.EventAlphaRetentionConfig(
        namespace_dir=namespace_dir,
        runs_path=custom_ledger,
        alerts_path=namespace_dir / "event_alpha_alerts.jsonl",
        cards_dir=namespace_dir / "research_cards",
        run_days=1,
    )
    held = event_alpha_locks.acquire_artifact_mutation_lock(
        SimpleNamespace(namespace_dir=namespace_dir),
        run_id="active-writer",
        profile="notify_no_key",
        namespace="notify_no_key",
        now=now,
    )
    assert held.owned is True
    try:
        blocked = event_alpha_retention.prune_event_alpha_artifacts(cfg, confirm=True, now=now)
    finally:
        assert event_alpha_locks.release_run_lock(held) is True

    assert blocked.mutation_blocked is True
    assert len(custom_ledger.read_text(encoding="utf-8").splitlines()) == 2
    confirmed = event_alpha_retention.prune_event_alpha_artifacts(cfg, confirm=True, now=now)
    assert confirmed.mutation_blocked is False
    assert len(custom_ledger.read_text(encoding="utf-8").splitlines()) == 1
    canonical_state = event_alpha_operator_state.load_operator_state(namespace_dir)
    assert canonical_state.valid is True
    assert canonical_state.state is not None
    assert canonical_state.state["doctor"]["status"] == "stale"
    assert event_alpha_operator_state.load_operator_state(custom_ledger.parent).exists is False


def test_event_alpha_retention_fingerprint_change_blocks_every_mutation(tmp_path):
    from unittest.mock import patch

    import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention

    runs = tmp_path / "event_alpha_runs.jsonl"
    runs.write_text(
        '{"run_id":"old","started_at":"2024-01-01T00:00:00+00:00"}\n'
        '{"run_id":"latest","started_at":"2025-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    original_revalidate = event_alpha_retention._revalidate_retention_plan

    def append_before_revalidation(plans, cards, *, namespace_dir):
        with runs.open("a", encoding="utf-8") as handle:
            handle.write('{"run_id":"concurrent","started_at":"2026-01-01T00:00:00+00:00"}\n')
        return original_revalidate(plans, cards, namespace_dir=namespace_dir)

    with patch.object(
        event_alpha_retention,
        "_revalidate_retention_plan",
        side_effect=append_before_revalidation,
    ):
        result = event_alpha_retention.prune_event_alpha_artifacts(
            event_alpha_retention.EventAlphaRetentionConfig(
                runs_path=runs,
                alerts_path=tmp_path / "event_alpha_alerts.jsonl",
                cards_dir=tmp_path / "research_cards",
                run_days=1,
            ),
            confirm=True,
            now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    rows = [json.loads(line) for line in runs.read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in rows] == ["old", "latest", "concurrent"]
    assert result.dry_run is True
    assert result.mutation_blocked is True
    assert any("changed after retention planning" in warning for warning in result.warnings)


def test_event_alpha_retention_invalidation_failure_blocks_before_artifact_mutation(tmp_path):
    from unittest.mock import patch

    import crypto_rsi_scanner.event_alpha.artifacts.operator_state as event_alpha_operator_state
    import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    runs = tmp_path / "event_alpha_runs.jsonl"
    runs.write_text(
        '{"run_id":"old","profile":"no_key_live","artifact_namespace":"retention",'
        '"started_at":"2024-01-01T00:00:00+00:00"}\n'
        '{"run_id":"current","profile":"no_key_live","artifact_namespace":"retention",'
        '"started_at":"2025-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    state = event_alpha_operator_state.begin_run(
        tmp_path,
        {
            "run_id": "current",
            "profile": "no_key_live",
            "artifact_namespace": "retention",
            "run_mode": "notification_burn_in",
        },
        updated_at=now,
    )
    event_alpha_operator_state.record_doctor_status(
        tmp_path,
        run_id="current",
        profile="no_key_live",
        artifact_namespace="retention",
        expected_revision=1,
        strict=True,
        schema_only=False,
        skip_api_checks=False,
        status="OK",
        checked_at=now,
    )
    before_runs = runs.read_bytes()
    with patch.object(
        event_alpha_operator_state,
        "invalidate_operator_state",
        side_effect=OSError("simulated invalidation failure"),
    ):
        result = event_alpha_retention.prune_event_alpha_artifacts(
            event_alpha_retention.EventAlphaRetentionConfig(
                runs_path=runs,
                alerts_path=tmp_path / "event_alpha_alerts.jsonl",
                cards_dir=tmp_path / "research_cards",
                run_days=1,
            ),
            confirm=True,
            now=now,
        )

    assert result.dry_run is True
    assert result.mutation_blocked is True
    assert runs.read_bytes() == before_runs
    loaded = event_alpha_operator_state.load_operator_state(tmp_path)
    assert loaded.valid is True
    assert loaded.state is not None
    assert loaded.state["revision"] == state["revision"]
    assert loaded.state["doctor"]["status"] == "OK"
    assert any("could not be invalidated before mutation" in warning for warning in result.warnings)


def test_event_alpha_retention_preserves_current_card_rebuilds_index_and_invalidates_doctor(tmp_path):
    import os

    import crypto_rsi_scanner.event_alpha.artifacts.operator_state as event_alpha_operator_state
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.artifacts.retention as event_alpha_retention
    import crypto_rsi_scanner.event_alpha.namespace.status as event_alpha_namespace_status

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    runs = tmp_path / "event_alpha_runs.jsonl"
    runs.write_text(
        '{"run_id":"old","profile":"no_key_live","artifact_namespace":"retention",'
        '"started_at":"2024-01-01T00:00:00+00:00"}\n'
        '{"run_id":"current","profile":"no_key_live","artifact_namespace":"retention",'
        '"started_at":"2025-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    state = event_alpha_operator_state.begin_run(
        tmp_path,
        {
            "run_id": "current",
            "profile": "no_key_live",
            "artifact_namespace": "retention",
            "run_mode": "notify_no_key",
        },
        updated_at=now,
    )
    event_alpha_operator_state.record_doctor_status(
        tmp_path,
        run_id="current",
        profile="no_key_live",
        artifact_namespace="retention",
        expected_revision=1,
        strict=True,
        schema_only=False,
        skip_api_checks=False,
        status="OK",
        checked_at=now,
    )
    event_alpha_namespace_status.write_namespace_status(
        tmp_path,
        {
            "namespace": "retention",
            "profile": "no_key_live",
            "status": event_alpha_namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
            "safe_for_send_readiness": False,
            "safe_for_burn_in_measurement": False,
            "safe_for_calibration": False,
        },
        now=now,
    )
    cards = tmp_path / "research_cards"
    cards.mkdir()
    old_card = cards / "card_old_asset.md"
    old_card.write_text(
        "# Old\n\n- Run ID: old\n- Feedback target: old\n- Final Opportunity Verdict: WATCHLIST\n",
        encoding="utf-8",
    )
    current_card = cards / "card_current_asset.md"
    current_card.write_text(
        "# Current\n\n- Run ID: current\n- Feedback target: current\n- Final Opportunity Verdict: WATCHLIST\n",
        encoding="utf-8",
    )
    index = cards / "index.md"
    index.write_text(
        event_research_cards._render_index([old_card, current_card], now),
        encoding="utf-8",
    )
    old_epoch = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
    os.utime(old_card, (old_epoch, old_epoch))
    os.utime(current_card, (old_epoch, old_epoch))

    result = event_alpha_retention.prune_event_alpha_artifacts(
        event_alpha_retention.EventAlphaRetentionConfig(
            runs_path=runs,
            alerts_path=tmp_path / "event_alpha_alerts.jsonl",
            cards_dir=cards,
            run_days=1,
            card_days=1,
        ),
        confirm=True,
        now=now,
    )

    assert result.dry_run is False
    assert result.mutation_blocked is False
    assert result.cards_pruned == 1
    assert old_card.exists() is False
    assert current_card.exists() is True
    index_text = index.read_text(encoding="utf-8")
    assert old_card.name not in index_text
    assert current_card.name in index_text
    loaded = event_alpha_operator_state.load_operator_state(tmp_path)
    assert loaded.valid is True
    assert loaded.state["revision"] == state["revision"] + 1
    assert loaded.state["doctor"]["status"] == "stale"
    assert loaded.state["doctor"]["verified_revision"] is None
    assert loaded.state["invalidation_reason"] == "retention_pruned_research_artifacts"
    marker = event_alpha_namespace_status.load_namespace_status(tmp_path)
    assert marker is not None
    assert marker.current_doctor_status == "stale"
    assert marker.operator_state_revision == loaded.state["revision"]
    assert marker.safe_for_send_readiness is False
    assert not (tmp_path / "event_alpha_notify.lock").exists()
    marker_payload = json.loads(
        (tmp_path / event_alpha_namespace_status.NAMESPACE_STATUS_FILENAME).read_text(encoding="utf-8")
    )
    assert marker_payload["artifact_counts"]["files"] == sum(
        path.is_file() and path.suffix != ".lock" for path in tmp_path.rglob("*")
    )


def test_candidate_mode_scorecard_supplied_base_ignores_sibling_poison_cache(tmp_path):
    import os
    from pathlib import Path
    from unittest.mock import patch

    from crypto_rsi_scanner import config
    from crypto_rsi_scanner.event_alpha.operations import (
        candidate_mode_smoke,
        common,
        scorecard,
    )

    checkout = tmp_path / "checkout"
    poison_base = checkout / "event_fade_cache"
    poison_path = poison_base / "poison_namespace" / "event_core_opportunities.jsonl"
    artifact_base = checkout / "isolated_artifacts"
    namespace = "candidate_mode_hermetic_smoke"
    poison_path.parent.mkdir(parents=True)
    with poison_path.open("wb") as handle:
        handle.seek((8 * 1024 * 1024) - 1)
        handle.write(b"\n")

    original_read_jsonl = common.read_jsonl
    observed_reads: list[Path] = []
    poison_root = poison_base.resolve()

    def guarded_read_jsonl(path):
        resolved = Path(path).expanduser().resolve()
        if resolved == poison_root or poison_root in resolved.parents:
            raise AssertionError(f"operation read sibling poison cache: {resolved}")
        observed_reads.append(resolved)
        return original_read_jsonl(path)

    with (
        patch.dict(os.environ, {"RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR": ""}),
        patch.object(config, "EVENT_ALPHA_ARTIFACT_BASE_DIR", poison_base),
        patch.object(config, "EVENT_DISCOVERY_CACHE_DIR", poison_base),
        patch.object(common, "read_jsonl", guarded_read_jsonl),
    ):
        fixture = candidate_mode_smoke.write_candidate_mode_fixture_artifacts(
            profile="fixture",
            artifact_namespace=namespace,
            base_dir=artifact_base,
        )
        result = scorecard.build_scorecard(
            profile="fixture",
            artifact_namespace=namespace,
            base_dir=artifact_base,
        )

    namespace_dir = artifact_base / namespace
    assert poison_path.stat().st_size == 8 * 1024 * 1024
    assert fixture["candidate_count"] == 5
    assert result["candidate_rows_seen"] == 5
    assert result["fixture_candidate_count"] == 5
    assert (namespace_dir / "event_integrated_radar_candidates.jsonl").exists()
    assert (namespace_dir / scorecard.SCORECARD_JSON).exists()
    assert not (poison_base / namespace).exists()
    assert observed_reads
    artifact_root = artifact_base.resolve()
    assert any(artifact_root == path or artifact_root in path.parents for path in observed_reads)


def test_event_alpha_burn_in_scorecard_summarizes_operational_health():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.outcomes.burn_in as event_alpha_burn_in
    import crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist as event_alpha_burn_in_checklist

    now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    meta = {"profile": "no_key_live", "run_mode": "burn_in", "artifact_namespace": "no_key_live"}
    scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[
            {
                **meta,
                "run_id": "run-1",
                "started_at": "2026-06-19T10:00:00+00:00",
                "success": True,
                "raw_events": 5,
                "candidates": 3,
                "alertable": 1,
            },
            {
                **meta,
                "run_id": "run-2",
                "started_at": "2026-06-18T10:00:00+00:00",
                "success": False,
                "raw_events": 0,
                "candidates": 0,
                "alertable": 0,
            },
        ],
        alert_rows=[
            {
                **meta,
                "run_id": "run-1",
                "observed_at": "2026-06-19T10:01:00+00:00",
                "alert_key": "cluster|velvet|proxy_attention",
                "tier": "WATCHLIST",
                "playbook_type": "proxy_attention",
                "source": "gdelt",
            },
            {
                **meta,
                "run_id": "run-1",
                "observed_at": "2026-06-19T10:02:00+00:00",
                "alert_key": "cluster|btc|source_noise_control",
                "tier": "STORE_ONLY",
                "playbook_type": "source_noise_control",
                "source": "rss",
            },
        ],
        feedback_rows=[
            {
                **meta,
                "marked_at": "2026-06-19T11:00:00+00:00",
                "key": "cluster|btc|source_noise_control",
                "label": "junk",
            },
            {
                **meta,
                "marked_at": "2026-06-19T11:05:00+00:00",
                "key": "cluster|velvet|proxy_attention",
                "label": "useful",
            },
        ],
        outcome_rows=[
            {
                **meta,
                "observed_at": "2026-06-19T12:00:00+00:00",
                "alert_key": "cluster|velvet|proxy_attention",
                "primary_horizon_return": 0.18,
            }
        ],
        missed_rows=[
            {
                **meta,
                "observed_at": "2026-06-19T11:30:00+00:00",
                "failure_stage": "resolver_missed_asset",
            }
        ],
        provider_health_rows={
            "gdelt:event_source": {
                "provider_key": "gdelt:event_source",
                "consecutive_failures": 2,
                "disabled_until": "2026-06-19T12:30:00+00:00",
            }
        },
        llm_budget_rows=[
            {
                **meta,
                "date": "2026-06-19",
                "extractor_calls_attempted": 2,
                "relationship_calls_attempted": 1,
                "cache_hits": 4,
                "cache_misses": 3,
                "skipped_due_budget": 1,
                "estimated_cost_usd": 0.12,
            }
        ],
    )
    text = event_alpha_burn_in.format_burn_in_scorecard(scorecard)
    assert "EVENT ALPHA BURN-IN SCORECARD" in text
    assert "runs=2 successful=1 failed=1" in text
    assert "WATCHLIST=1" in text
    assert "resolver_missed_asset=1" in text
    assert "gdelt:event_source(2)" in text
    assert "calls=3" in text
    assert "artifact coverage:" in text
    assert "alert_snapshots=2" in text
    assert "inspect degraded provider health" in text
    assert "No thresholds, alert tiers, paper trades, live DB rows, or execution were changed." in text
    checklist = event_alpha_burn_in_checklist.build_burn_in_checklist(
        scorecard,
        card_paths=("card.md",),
    )
    assert checklist.ready_for_research_send is False
    assert any("backoff" in item for item in checklist.blockers)
    checklist_text = event_alpha_burn_in_checklist.format_burn_in_checklist(checklist)
    assert "READY_FOR_RESEARCH_SEND: no" in checklist_text

    ready_scorecard = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{**meta, "run_id": "ready-run", "started_at": "2026-06-19T10:00:00+00:00", "success": True, "alertable": 1}],
        alert_rows=[{**meta, "run_id": "ready-run", "observed_at": "2026-06-19T10:01:00+00:00", "alert_key": "a", "tier": "WATCHLIST"}],
        feedback_rows=[{**meta, "marked_at": "2026-06-19T11:00:00+00:00", "key": "a", "label": "useful"}],
        outcome_rows=[{**meta, "observed_at": "2026-06-19T12:00:00+00:00", "alert_key": "a", "primary_horizon_return": 0.1}],
        missed_rows=[{**meta, "observed_at": "2026-06-19T12:00:00+00:00", "failure_stage": "unknown"}],
        provider_health_rows={"gdelt:event_source": {"provider_key": "gdelt:event_source", "consecutive_failures": 0}},
    )
    assert event_alpha_burn_in_checklist.build_burn_in_checklist(ready_scorecard).ready_for_research_send is True

    contract_scorecard = {
        "schema_version": "event_alpha_burn_in_scorecard_v1",
        "window_days": 30,
        "live_no_send_cycles_completed": 4,
        "real_burn_in_candidate_count": 0,
        "labels_collected": 0,
        "labeled_near_misses": 0,
        "outcome_rows": 0,
        "enough_data": False,
        "enough_data_reasons": ("min_live_no_send_cycles:4/20", "min_real_candidates:0/300"),
        "promotion_freeze_status_by_lane": {"EARLY_LONG_RESEARCH": "frozen_insufficient_data"},
        "auto_apply_thresholds": False,
        "contract": {
            "duration_days": 30,
            "min_live_no_send_cycles": 20,
            "min_real_candidates": 300,
            "min_human_labels": 150,
            "min_labeled_near_misses": 50,
            "min_outcome_rows": 100,
        },
    }
    contract_checklist = event_alpha_burn_in_checklist.build_burn_in_checklist(contract_scorecard)
    assert contract_checklist.ready_for_research_send is False
    assert contract_checklist.checks["live_no_send_cycles"] == "4/20"
    assert contract_checklist.checks["real_candidates"] == "0/300"
    assert any("min_real_candidates:0/300" in item for item in contract_checklist.blockers)

    missing_snapshots = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{**meta, "run_id": "missing-run", "started_at": "2026-06-19T10:00:00+00:00", "success": True, "alertable": 1}],
        alert_rows=[],
        missed_rows=[],
        profile="no_key_live",
    )
    assert "alert snapshots missing for alertable runs" in missing_snapshots.coverage_warnings
    assert "provider health missing for live profiles" in missing_snapshots.coverage_warnings
    blocked = event_alpha_burn_in_checklist.build_burn_in_checklist(missing_snapshots)
    assert blocked.ready_for_research_send is False
    assert any("alertable runs" in item for item in blocked.blockers)

    legacy_only = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{"run_id": "legacy", "started_at": "2026-06-19T10:00:00+00:00", "success": True}],
        alert_rows=[{"run_id": "legacy", "observed_at": "2026-06-19T10:01:00+00:00", "alert_key": "legacy-a"}],
    )
    assert legacy_only.run_rows == []
    assert legacy_only.legacy_rows_skipped == 2
    assert "no operational burn-in rows found" in legacy_only.coverage_warnings
    legacy_counted = event_alpha_burn_in.build_burn_in_scorecard(
        days=7,
        now=now,
        run_rows=[{"run_id": "legacy", "started_at": "2026-06-19T10:00:00+00:00", "success": True}],
        include_api_artifacts=True,
    )
    assert len(legacy_counted.run_rows) == 1


def test_event_alpha_burn_in_readiness_requires_no_send_and_reviewable_artifacts():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.outcomes.burn_in as event_alpha_burn_in_readiness
    import crypto_rsi_scanner.event_alpha.outcomes.feedback as event_alpha_feedback_readiness
    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status

    with TemporaryDirectory() as tmp:
        brief = Path(tmp) / "event_alpha_daily_brief.md"
        brief.write_text("## Market Freshness Readiness\n- fresh\n", encoding="utf-8")
        provider_report = event_provider_status.EventDiscoveryProviderStatus(
            mode="research_only",
            cache_dir="event_fade_cache/live_burn_in_no_send",
            lookback_hours=72,
            horizon_days=14,
            sources=(event_provider_status.ProviderStatus("gdelt_news", "event_source", True),),
            enrichment=(event_provider_status.ProviderStatus("coingecko_universe", "enrichment", True),),
            warnings=(),
            next_steps=(),
        )
        doctor = event_alpha_artifact_doctor.EventAlphaArtifactDoctorResult(
            status="OK",
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            run_rows=1,
            alert_rows=1,
            feedback_rows=0,
            outcome_rows=0,
            card_files=1,
        )
        feedback = event_alpha_feedback_readiness.EventAlphaFeedbackReadinessResult(
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            cards_checked=1,
            cards_with_lineage=1,
            cards_with_feedback_target=1,
            core_opportunity_cards_ready=1,
            near_miss_cards_ready=0,
            local_only_cards_ready=0,
            alert_rows_checked=1,
            alert_rows_with_feedback_targets=1,
            inbox_review_items=1,
            feedback_rows=0,
            calibration_ready_rows=1,
            visible_core_opportunities=1,
            visible_core_opportunities_with_cards=1,
            visible_core_opportunities_with_feedback_targets=1,
        )
        run = {
            "run_id": "run-live-burn",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "live_burn_in_no_send",
            "success": True,
            "send_requested": False,
            "sent": False,
            "send_items_delivered": 0,
            "raw_events": 4,
            "candidates": 2,
            "evidence_acquisition_attempted": 1,
        }
        result = event_alpha_burn_in_readiness.build_burn_in_readiness(
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            run_rows=[run],
            provider_status=provider_report,
            artifact_doctor=doctor,
            feedback_readiness=feedback,
            core_opportunity_rows=[{"core_opportunity_id": "core:velvet"}],
            evidence_acquisition_rows=[{"accepted_evidence_count": 1}],
            daily_brief_path=brief,
            burn_in_contract_scorecard={
                "enough_data": False,
                "enough_data_reasons": ["min_real_candidates:0/300"],
                "live_no_send_cycles_completed": 4,
                "real_burn_in_candidate_count": 0,
                "labels_collected": 0,
                "labeled_near_misses": 0,
                "outcome_rows": 0,
                "contract": {
                    "min_live_no_send_cycles": 20,
                    "min_real_candidates": 300,
                    "min_human_labels": 150,
                    "min_labeled_near_misses": 50,
                    "min_outcome_rows": 100,
                },
            },
        )
        text = event_alpha_burn_in_readiness.format_burn_in_readiness(result)

        assert result.ready is True
        assert result.no_send_confirmed is True
        assert result.market_freshness_visible is True
        assert "READY_FOR_NO_SEND_BURN_IN_REVIEW: yes" in text
        assert "BURN_IN_CONTRACT_ENOUGH_DATA: no" in text
        assert "real_candidates:0/300" in text
        assert "provider_coverage:" in text
        assert "manual review checklist:" in text

        stale_inbox_feedback = event_alpha_feedback_readiness.EventAlphaFeedbackReadinessResult(
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            cards_checked=1,
            cards_with_lineage=1,
            cards_with_feedback_target=1,
            core_opportunity_cards_ready=1,
            near_miss_cards_ready=0,
            local_only_cards_ready=0,
            alert_rows_checked=1,
            alert_rows_with_feedback_targets=1,
            inbox_review_items=1,
            feedback_rows=0,
            calibration_ready_rows=1,
            visible_core_opportunities=1,
            visible_core_opportunities_with_cards=1,
            visible_core_opportunities_with_feedback_targets=1,
            visible_core_opportunities_missing_cards=0,
            visible_core_opportunities_missing_feedback_targets=0,
            canonical_review_items=1,
            canonical_review_items_with_cards=0,
            canonical_review_items_with_feedback_targets=1,
            blockers=("canonical_review_items_missing_cards",),
        )
        stale_inbox_result = event_alpha_burn_in_readiness.build_burn_in_readiness(
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            run_rows=[run],
            provider_status=provider_report,
            artifact_doctor=doctor,
            feedback_readiness=stale_inbox_feedback,
            core_opportunity_rows=[{"core_opportunity_id": "core:velvet"}],
            evidence_acquisition_rows=[{"accepted_evidence_count": 1}],
            daily_brief_path=brief,
        )
        assert stale_inbox_result.feedback_readiness_ready is True
        assert "feedback readiness has blockers" not in "\n".join(stale_inbox_result.blockers)


def test_makefile_has_event_alpha_burn_in_and_priors_targets():
    text = __import__("pathlib").Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-priors-shadow-report:" in text
    assert "event-alpha-burn-in-no-key:" in text
    assert "event-alpha-source-coverage-report:" in text
    assert "event-alpha-burn-in-llm:" in text
    assert "event-alpha-burn-in-scorecard:" in text
    assert "event-alpha-burn-in-checklist:" in text
    assert "event-alpha-burn-in-checklist: PROFILE = live_burn_in_no_send" in text
    assert "--event-alpha-burn-in-checklist --days 30" in text
    assert "event-alpha-export-burn-in-pack: PROFILE = live_burn_in_no_send" in text
    assert "--event-alpha-export-burn-in-pack $(EVENT_ALPHA_BURN_IN_PACK) --days 30" in text
    assert "--event-alpha-v1-readiness --days 30" in text
    assert "event-alpha-live-burn-in-no-send:" in text
    assert "event-alpha-burn-in-readiness:" in text
    assert "event-alpha-v1-readiness:" in text
    assert "event-alpha-health-guard:" in text
    assert "event-alpha-artifact-doctor:" in text
    assert "event-alpha-preflight:" in text
    assert "event-alpha-notify-cycle:" in text
    assert "event-alpha-notify-no-key:" in text
    assert "event-alpha-notify-llm:" in text
    assert "event-alpha-notify-preview:" in text
    assert "event-alpha-notify-go-no-go:" in text
    assert "event-alpha-provider-health-report:" in text
    assert "event-alpha-provider-health-reset:" in text
    assert "event-alpha-day1-start:" in text
    assert "event-alpha-send-test:" in text
    assert "event-alpha-tuning-worksheet:" in text
    assert "event-alpha-export-burn-in-pack:" in text
    assert "event-alpha-launchd-template:" in text
    assert "event-alpha-weekly-review:" in text
    assert "--event-alpha-priors-shadow-report" in text
    assert "--event-alpha-v1-readiness" in text
    assert "--event-alpha-health-guard" in text
    assert "--event-alpha-artifact-doctor" in text
    assert "--event-alpha-preflight" in text
    assert "--event-alpha-notify-cycle --event-alpha-profile $(PROFILE) --event-alert-send" in text
    assert "--event-alpha-notify-preview --event-alpha-profile $(PROFILE)" in text
    assert "--event-alpha-notify-go-no-go --event-alpha-profile $(PROFILE)" in text
    assert "--event-alpha-notification-checklist --event-alpha-profile $(PROFILE)" in text
    assert "--event-alpha-notification-runs-report" in text
    assert "--event-alpha-send-test --event-alpha-profile $(PROFILE)" in text
    assert "--event-alpha-tuning-worksheet" in text
    assert "--event-alpha-export-burn-in-pack" in text
    assert __import__("pathlib").Path("research/event_alpha_launchd_template.plist").exists()
    assert __import__("pathlib").Path("research/event_alpha_cron_example.txt").exists()
    burn_in = text.split("event-alpha-burn-in-no-key:", 1)[1].split("event-alpha-burn-in-llm:", 1)[0]
    assert "--event-alert-send" not in burn_in
    assert "--event-alpha-profile no_key_live" in burn_in
    live_burn_in = text.split("event-alpha-live-burn-in-no-send:", 1)[1].split("event-alpha-burn-in-readiness:", 1)[0]
    assert "--event-alpha-cycle" in live_burn_in
    assert "--event-alpha-burn-in-readiness" in live_burn_in
    assert "--event-alert-send" not in live_burn_in
    assert "EVENT_ALPHA_PROFILE_DIR" in text
    llm_burn_in = text.split("event-alpha-burn-in-llm:", 1)[1].split("event-alpha-weekly-review:", 1)[0]
    assert "--event-alpha-profile full_llm_live" in llm_burn_in

    import subprocess
    dry = subprocess.run(
        ["make", "-n", "event-alpha-daily-llm-report", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-profile full_llm_live" in dry
    assert "event_fade_cache/full_llm_live/event_alpha_runs.jsonl" in dry
    assert "event_fade_cache/no_key_live/event_alpha_runs.jsonl" not in dry

    preflight = subprocess.run(
        ["make", "-n", "event-alpha-preflight", "PROFILE=no_key_live", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-preflight --event-alpha-profile no_key_live" in preflight

    checklist = subprocess.run(
        ["make", "-n", "event-alpha-notification-checklist", "PROFILE=notify_no_key", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-notification-checklist --event-alpha-profile notify_no_key" in checklist


def test_event_alpha_signal_quality_fixture_passes_and_reports_stage_failure():
    import json
    import tempfile
    import crypto_rsi_scanner.event_alpha.outcomes.quality as quality

    result = quality.evaluate_signal_quality_cases()
    assert result.failed_cases == 0
    assert result.total_cases >= 13
    text = quality.format_signal_quality_eval(result)
    assert "failures_by_stage: none" in text
    assert "brief_section=" in text
    assert "diagnostic_visibility=" in text
    assert "false_positive=" in text
    assert "reason=\"" in text

    cases = list(quality.load_signal_quality_cases())
    cases[0] = {**cases[0], "expected": {**dict(cases[0]["expected"]), "route_tier": "STORE_ONLY"}}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "bad_cases.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"cases": cases[:1]}, fh)
        bad = quality.evaluate_signal_quality_cases(path)
    assert bad.failed_cases == 1
    assert "routing" in bad.case_results[0].stage_failures
    assert any("route_tier" in diff for diff in bad.case_results[0].diffs)
