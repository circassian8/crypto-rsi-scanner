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


def test_event_alpha_alert_store_snapshots_and_fills_outcomes():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    alerts = event_alerts.build_event_alert_candidates(
        _full_event_discovery_fixture_result(),
        now=now,
    )
    assert any(alert.symbol == "TESTVELVET" for alert in alerts)

    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "event_alpha_alerts.jsonl"
        cfg = event_alpha_alert_store.EventAlphaAlertStoreConfig(path=store_path)
        wrote = event_alpha_alert_store.write_alert_snapshots(alerts, cfg=cfg, now=now)
        assert wrote.rows_written == len(alerts)
        loaded = event_alpha_alert_store.load_alert_snapshots(store_path)
        assert loaded.rows_read == len(alerts)
        report = event_alpha_alert_store.format_alert_snapshot_report(loaded)
        assert "EVENT ALPHA ALERT SNAPSHOT REPORT" in report
        assert "by playbook:" in report
        assert "by expected direction:" in report
        assert "by tier:" in report

        prices_path = Path(tmp) / "prices.json"
        prices_path.write_text(json.dumps({
            "source": "fixture",
            "interval": "1h",
            "prices": [
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-15T17:00:00Z", "close": 9.0, "high": 9.2, "low": 8.8},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-15T20:00:00Z", "close": 8.2, "high": 8.5, "low": 8.0},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-16T16:00:00Z", "close": 7.2, "high": 7.4, "low": 6.9},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-18T16:00:00Z", "close": 6.0, "high": 6.3, "low": 5.8},
                {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-22T16:00:00Z", "close": 5.4, "high": 5.6, "low": 5.1},
            ],
        }), encoding="utf-8")
        out_path = Path(tmp) / "with_outcomes.jsonl"
        filled = event_alpha_alert_store.fill_alert_outcomes(
            loaded.rows,
            prices_path,
            out_path,
            source_path=store_path,
        )
        assert filled.rows_written == len(alerts)
        assert filled.rows_with_outcomes >= 1
        out_rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
        velvet = next(row for row in out_rows if row.get("asset_symbol") == "TESTVELVET")
        assert velvet["outcome_price_interval"] == "1h"
        assert velvet["outcome_status"] == "filled"
        assert velvet["outcome_source"] == "fixture"
        assert velvet["return_1h"] is not None
        assert velvet["return_24h"] is not None
        assert velvet["return_72h"] is not None
        assert velvet["return_7d"] is not None
        assert velvet["primary_horizon_return"] is not None
        assert velvet["direction_hit"] is True
        assert velvet["max_favorable_excursion"] is not None
        assert velvet["max_adverse_excursion"] is not None
        outcome_report = event_alpha_alert_store.format_alert_snapshot_report(
            event_alpha_alert_store.load_alert_snapshots(out_path)
        )
        assert "outcomes:" in outcome_report

        status_out = Path(tmp) / "status_outcomes.jsonl"
        status_result = event_alpha_alert_store.fill_alert_outcomes(
            [
                {"observed_at": "2026-06-15T16:00:00+00:00", "asset_symbol": "TESTVELVET", "entry_reference_price": 10.0},
                {"observed_at": "2026-06-15T16:00:00+00:00", "asset_symbol": "MEME", "entry_reference_price": 1.0},
                {"observed_at": "2026-06-15T16:00:00+00:00", "entry_reference_price": 1.0},
            ],
            prices_path,
            status_out,
        )
        status_rows = [json.loads(line) for line in status_out.read_text(encoding="utf-8").splitlines()]
        assert [row["outcome_status"] for row in status_rows] == [
            "filled",
            "insufficient_market_data",
            "skipped_no_asset",
        ]
        assert status_result.missing_price_rows == 2
        assert "MFE/MAE by playbook:" in outcome_report
        assert "Outcome metrics by playbook:" in outcome_report


def test_event_alpha_outcomes_playbook_specific_metrics():
    import crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts as event_alpha_outcomes

    listing_row = {
        "observed_at": "2026-06-18T12:00:00+00:00",
        "entry_reference_price": 10.0,
        "playbook_type": "listing_volatility",
        "expected_direction": "volatility",
        "success_metric": "volatility",
        "primary_horizon": "24h",
    }
    prices = [
        {"timestamp": "2026-06-18T13:00:00+00:00", "close": 10.5, "high": 11.5, "low": 9.8},
        {"timestamp": "2026-06-18T20:00:00+00:00", "close": 9.2, "high": 10.0, "low": 8.8},
    ]
    metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(
        listing_row,
        prices,
        returns={"max_favorable_excursion": 0.15, "max_adverse_excursion": 0.12, "primary_horizon_return": -0.08},
    )
    assert metrics["volatility_hit"] is True
    assert metrics["mfe_mae_ratio"] > 1.0

    proxy_row = {
        "observed_at": "2026-06-18T12:00:00+00:00",
        "entry_reference_price": 10.0,
        "playbook_type": "proxy_attention",
        "expected_direction": "up_then_fade",
        "success_metric": "mfe_mae",
        "primary_horizon": "72h",
    }
    proxy_metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(
        proxy_row,
        prices,
        returns={"return_72h": -0.10, "max_favorable_excursion": 0.15, "max_adverse_excursion": 0.05},
    )
    assert proxy_metrics["up_then_fade_hit"] is True

    unlock_row = {
        "observed_at": "2026-06-18T12:00:00+00:00",
        "entry_reference_price": 10.0,
        "playbook_type": "unlock_supply_pressure",
        "expected_direction": "down",
        "success_metric": "direction_hit",
        "primary_horizon": "24h",
        "btc_primary_horizon_return": 0.02,
    }
    unlock_metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(
        unlock_row,
        prices,
        returns={"primary_horizon_return": -0.08},
    )
    assert unlock_metrics["underperformance_vs_btc"] == -0.10

    anomaly_row = {
        "event_type": "exchange_listing",
        "source": "market_anomaly+catalyst_search",
    }
    anomaly_metrics = event_alpha_outcomes.compute_playbook_outcome_metrics(anomaly_row, [])
    assert anomaly_metrics["catalyst_found_after_anomaly"] is True


def test_event_alpha_alert_store_snapshot_policy_filters_rows():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    alerts = event_alerts.build_event_alert_candidates(_full_event_discovery_fixture_result(), now=now)
    store_only_count = sum(1 for alert in alerts if alert.tier == event_alerts.EventAlertTier.STORE_ONLY)
    non_store_count = len(alerts) - store_only_count
    assert store_only_count > 2
    assert non_store_count > 0

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        all_path = root / "all.jsonl"
        all_result = event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=all_path, snapshot_policy="all"),
            now=now,
        )
        assert all_result.rows_written == len(alerts)
        all_rows = [
            json.loads(line)
            for line in all_path.read_text(encoding="utf-8").splitlines()
        ]
        final_store_only_count = sum(
            1 for row in all_rows
            if row["final_tier_after_quality_gate"] == event_alerts.EventAlertTier.STORE_ONLY.value
        )
        final_non_store_count = len(all_rows) - final_store_only_count

        non_store_path = root / "non-store.jsonl"
        non_store_result = event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=non_store_path, snapshot_policy="non_store"),
            now=now,
        )
        assert non_store_result.rows_written == final_non_store_count
        assert all(
            json.loads(line)["final_tier_after_quality_gate"] != event_alerts.EventAlertTier.STORE_ONLY.value
            for line in non_store_path.read_text(encoding="utf-8").splitlines()
        )

        sampled_path = root / "sampled.jsonl"
        sampled_result = event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(
                path=sampled_path,
                snapshot_policy="sampled_controls",
                sampled_controls_limit=2,
            ),
            now=now,
        )
        assert sampled_result.rows_written == final_non_store_count + 2
        sampled_rows = [
            json.loads(line)
            for line in sampled_path.read_text(encoding="utf-8").splitlines()
        ]
        assert sum(
            1 for row in sampled_rows
            if row["final_tier_after_quality_gate"] == event_alerts.EventAlertTier.STORE_ONLY.value
        ) == 2


def test_event_alpha_alert_store_scanner_report_and_outcome_fill_commands():
    import contextlib
    import io
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts

    now = datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    alerts = event_alerts.build_event_alert_candidates(_full_event_discovery_fixture_result(), now=now)
    original = {
        "EVENT_ALPHA_ALERT_STORE_PATH": config.EVENT_ALPHA_ALERT_STORE_PATH,
        "EVENT_ALPHA_FEEDBACK_PATH": config.EVENT_ALPHA_FEEDBACK_PATH,
    }
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "alerts.jsonl"
        feedback_path = Path(tmp) / "feedback.jsonl"
        config.EVENT_ALPHA_ALERT_STORE_PATH = store_path
        config.EVENT_ALPHA_FEEDBACK_PATH = feedback_path
        event_alpha_alert_store.write_alert_snapshots(
            alerts,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=store_path),
            now=now,
        )
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_alerts_report()
            text = out.getvalue()
            assert "EVENT ALPHA ALERT SNAPSHOT REPORT" in text
            assert "by playbook:" in text

            prices_path = Path(tmp) / "prices.json"
            prices_path.write_text(json.dumps({
                "source": "fixture",
                "interval": "1h",
                "prices": [
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-15T17:00:00Z", "close": 9.0, "high": 9.1, "low": 8.9},
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-16T16:00:00Z", "close": 7.0, "high": 7.3, "low": 6.8},
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-18T16:00:00Z", "close": 6.0, "high": 6.2, "low": 5.8},
                    {"asset_symbol": "TESTVELVET", "timestamp": "2026-06-22T16:00:00Z", "close": 5.0, "high": 5.3, "low": 4.9},
                ],
            }), encoding="utf-8")
            filled_path = Path(tmp) / "filled.jsonl"
            fill_out = io.StringIO()
            with contextlib.redirect_stdout(fill_out):
                scanner.event_alpha_fill_outcomes(str(prices_path), str(filled_path))
            fill_text = fill_out.getvalue()
            assert "EVENT ALPHA ALERT OUTCOMES FILLED" in fill_text
            assert filled_path.exists()
        finally:
            for name, value in original.items():
                setattr(config, name, value)


def test_event_alpha_quality_gate_dominates_router_and_artifacts():
    import json
    import tempfile
    from dataclasses import asdict
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_alpha_quality_review
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality
    import crypto_rsi_scanner.event_alpha.radar.impact_path_validator as event_impact_path_validator
    import crypto_rsi_scanner.event_alpha.radar.market_confirmation as event_market_confirmation
    import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    def quality(level, score, *, path="proxy_exposure", role="proxy_instrument", source="crypto_news", specificity="direct_value_capture"):
        return {
            "impact_path_type": path,
            "impact_path_strength": "strong" if path != "insufficient_data" else "none",
            "candidate_role": role,
            "evidence_quality_score": 80 if source != "insufficient_data" else 0,
            "source_class": source,
            "evidence_specificity": specificity,
            "market_confirmation_score": 60 if level in {"watchlist", "high_priority"} else 35,
            "market_confirmation_level": "moderate" if level in {"watchlist", "high_priority"} else "weak",
            "opportunity_score_final": score,
            "opportunity_level": level,
            "opportunity_verdict_reasons": ["test_quality_gate"],
            "why_local_only": "quality_gate_test_local_only" if level == "local_only" else "not_local_only",
            "why_not_watchlist": "quality_gate_test_not_watchlist" if level in {"local_only", "exploratory", "validated_digest"} else "already_watchlisted",
            "manual_verification_items": ["verify source, identity, market confirmation, and liquidity"],
            "upgrade_requirements": ["needs confirmed impact path"] if level in {"local_only", "exploratory"} else [],
            "downgrade_warnings": ["insufficient_data"] if path == "insufficient_data" else [],
        }

    positive_market_block = quality(
        "local_only",
        35,
        path="proxy_attention",
        role="proxy_instrument",
        source="crypto_news",
        specificity="token_and_catalyst",
    )
    positive_market_block["why_local_only"] = "strong_market_confirmation"
    positive_market_block["impact_path_strength"] = "weak"
    positive_market_block["market_confirmation_level"] = "strong"
    positive_market_block["market_confirmation_score"] = 90
    _, normalized_block = event_watchlist.quality_cap_watchlist_state(
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        positive_market_block,
    )
    assert normalized_block == "weak_impact_path_despite_market_confirmation"
    verdict = event_opportunity_verdict.evaluate_opportunity(
        impact_path=event_impact_path_validator.ImpactPathValidation(
            impact_path_type=event_impact_path_validator.ImpactPathType.TECHNOLOGY_RISK.value,
            impact_path_strength=event_impact_path_validator.ImpactPathStrength.WEAK.value,
            candidate_role=event_impact_path_validator.CandidateRole.MACRO_AFFECTED_ASSET.value,
            evidence_specificity_score=50,
            required_evidence_met=False,
            market_confirmation_required=True,
            digest_eligible_by_impact_path=False,
            why_digest_ineligible="technology_risk",
            impact_path_reason="generic_policy_only",
            opportunity_score_v2=45,
        ),
        market_confirmation=event_market_confirmation.EventMarketConfirmationResult(
            market_confirmation_score=82,
            level=event_market_confirmation.MarketConfirmationLevel.STRONG.value,
            reasons=("price_momentum",),
        ),
        evidence_quality=event_evidence_quality.EvidenceQualityResult(
            evidence_quality_score=72,
            source_class=event_evidence_quality.SourceClass.CRYPTO_NEWS.value,
            evidence_specificity=event_evidence_quality.EvidenceSpecificity.GENERIC_CONTEXT.value,
        ),
    )
    assert verdict.why_local_only != "strong_market_confirmation"
    assert verdict.why_not_watchlist != "strong_market_confirmation"
    assert "weak_impact_path_despite_market_confirmation" in verdict.missing_requirements
    assert verdict.score_components and verdict.score_components["market_confirmation"] > 0

    def entry(symbol, *, state, playbook, q, event_name=None, relationship="proxy_attention", external_asset="World Cup"):
        requested_state = state
        final_state, block_reason = event_watchlist.quality_cap_watchlist_state(requested_state, q)
        capped = bool(block_reason and final_state != requested_state)
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol}|cluster|{playbook}",
            cluster_id=f"cluster:{symbol}",
            event_id=f"event:{symbol}",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type=relationship,
            external_asset=external_asset,
            event_time="2026-06-25T12:00:00+00:00",
            state=final_state,
            previous_state=event_watchlist.EventWatchlistState.RADAR.value,
            requested_state_before_quality_gate=requested_state,
            final_state_after_quality_gate=final_state,
            state_quality_capped=capped,
            quality_state_block_reason=block_reason,
            first_seen_at="2026-06-25T08:00:00+00:00",
            last_seen_at="2026-06-25T08:30:00+00:00",
            source_count=1,
            highest_score=85,
            latest_score=85,
            latest_tier="WATCHLIST" if state == event_watchlist.EventWatchlistState.WATCHLIST.value else "HIGH_PRIORITY_WATCH",
            latest_event_name=event_name or f"{symbol} quality gate fixture",
            latest_source="Bitcoin World" if symbol == "BTC" else "fixture",
            latest_playbook_type=playbook,
            latest_effective_playbook_type=playbook,
            latest_playbook_score=85,
            latest_playbook_action="watchlist",
            latest_score_components=q,
            should_alert=True,
            material_change_reasons=("score_jump",),
            score_jump=20,
        )

    btc = entry(
        "BTC",
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        q=quality(
            "local_only",
            0,
            path="insufficient_data",
            role="unknown_with_reason",
            source="insufficient_data",
            specificity="insufficient_data",
        ),
        event_name="Polymarket World Cup Volume Surges - Bitcoin World",
    )
    zero = entry(
        "ZERO",
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        q=quality("watchlist", 0),
    )
    digest = entry(
        "DIG",
        state=event_watchlist.EventWatchlistState.RADAR.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        q=quality("validated_digest", 72),
    )
    watch = entry(
        "WATCH",
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        q=quality("watchlist", 82),
    )
    rune_quality = quality(
        "watchlist",
        83,
        path="exploit_security_event",
        role="direct_subject",
        source="crypto_news",
        specificity="direct_token_mechanism",
    )
    rune_quality.update({
        "validated_symbol": "RUNE",
        "validated_coin_id": "thorchain",
        "validation_stage": "impact_path_validated",
        "impact_category": event_playbooks.EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK.value,
        "playbook_type": event_playbooks.EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK.value,
        "impact_path_reason": "exploit_security_event",
        "market_confirmation_level": "moderate",
        "market_confirmation_score": 65,
    })
    rune = entry(
        "RUNE",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        playbook=event_playbooks.EventPlaybookType.SECURITY_OR_REGULATORY_SHOCK.value,
        q=rune_quality,
        event_name="THORChain RUNE exploit validated impact hypothesis",
        relationship="impact_hypothesis",
        external_asset="THORChain",
    )
    high = entry(
        "HIGH",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_FADE.value,
        q=quality("high_priority", 92),
    )
    trigger = entry(
        "FADE",
        state=event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
        playbook=event_playbooks.EventPlaybookType.PROXY_FADE.value,
        q=quality("local_only", 0, path="insufficient_data"),
    )

    routed = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=7,
            latest_only=True,
            entries=[btc, zero, digest, watch, rune, high, trigger],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            score_jump_threshold=10,
            validated_hypothesis_digest_enabled=True,
        ),
    )
    by_symbol = {decision.entry.symbol: decision for decision in routed.decisions}
    assert event_watchlist.final_state_value(btc) == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
    assert event_watchlist.requested_state_value(btc) == event_watchlist.EventWatchlistState.WATCHLIST.value
    assert event_watchlist.state_is_quality_capped(btc) is True
    assert event_watchlist.requested_state_value(rune) == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
    assert event_watchlist.final_state_value(rune) == event_watchlist.EventWatchlistState.WATCHLIST.value
    assert event_watchlist.state_is_quality_capped(rune) is True
    assert rune.quality_state_block_reason == "opportunity_level_caps_state:watchlist"
    assert event_watchlist.final_state_value(watch) == event_watchlist.EventWatchlistState.WATCHLIST.value
    assert event_watchlist.final_state_value(high) == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
    assert event_watchlist.final_state_value(trigger) == event_watchlist.EventWatchlistState.TRIGGERED_FADE.value
    assert by_symbol["BTC"].requested_route_before_quality_gate == "RESEARCH_DIGEST"
    assert by_symbol["BTC"].final_route_after_quality_gate == "STORE_ONLY"
    assert by_symbol["BTC"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["BTC"].alertable is False
    assert by_symbol["BTC"].quality_gate_block_reason == "impact_path_type_insufficient_data"
    assert by_symbol["ZERO"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["ZERO"].quality_gate_block_reason == "opportunity_score_final_zero"
    assert by_symbol["DIG"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["WATCH"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["RUNE"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["RUNE"].alertable is True
    assert by_symbol["RUNE"].quality_gate_block_reason in (None, "")
    assert "opportunity_level_caps_state:watchlist" not in by_symbol["RUNE"].reason
    assert by_symbol["HIGH"].route == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH
    assert by_symbol["FADE"].route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
    assert by_symbol["FADE"].alertable is True

    report = event_alpha_router.format_router_report(routed)
    assert "quality gate:" in report
    assert "requested=RESEARCH_DIGEST final=STORE_ONLY" in report

    now = datetime(2026, 6, 25, 8, 31, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "alerts.jsonl"
        write = event_alpha_alert_store.write_alert_snapshots(
            [],
            router_result=routed,
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=out, snapshot_policy="all"),
            now=now,
        )
        rows = event_alpha_alert_store.load_alert_snapshots(write.path).rows
    btc_snapshot = next(row for row in rows if row.get("symbol") == "BTC")
    assert btc_snapshot["requested_route_before_quality_gate"] == "RESEARCH_DIGEST"
    assert btc_snapshot["final_route_after_quality_gate"] == "STORE_ONLY"
    assert btc_snapshot["requested_state_before_quality_gate"] == "WATCHLIST"
    assert btc_snapshot["final_state_after_quality_gate"] == "QUALITY_BLOCKED"
    assert btc_snapshot["quality_state_block_reason"] == "impact_path_type_insufficient_data"
    assert btc_snapshot["state_quality_capped"] is True
    assert btc_snapshot["final_tier_after_quality_gate"] == "STORE_ONLY"
    assert btc_snapshot["quality_gate_block_reason"] == "impact_path_type_insufficient_data"
    assert btc_snapshot["route"] == "STORE_ONLY"
    assert btc_snapshot["lane"] == "LOCAL_ONLY"
    assert btc_snapshot["tier"] == "STORE_ONLY"
    assert btc_snapshot["snapshot_quality_classification"] == "quality_gated_local"
    assert btc_snapshot["requested_tier_before_quality_gate"] == "WATCHLIST"
    assert btc_snapshot["route_alertable"] is False
    assert btc_snapshot["alertable_after_quality_gate"] is False
    snapshots_by_symbol = {row.get("symbol"): row for row in rows}
    assert snapshots_by_symbol["DIG"]["final_route_after_quality_gate"] == "RESEARCH_DIGEST"
    assert snapshots_by_symbol["DIG"]["final_tier_after_quality_gate"] == "RADAR_DIGEST"
    assert snapshots_by_symbol["WATCH"]["final_route_after_quality_gate"] == "RESEARCH_DIGEST"
    assert snapshots_by_symbol["WATCH"]["state_quality_capped"] is False
    assert snapshots_by_symbol["WATCH"]["final_state_after_quality_gate"] == "WATCHLIST"
    assert snapshots_by_symbol["WATCH"]["final_tier_after_quality_gate"] == "WATCHLIST"
    assert snapshots_by_symbol["RUNE"]["requested_state_before_quality_gate"] == "HIGH_PRIORITY"
    assert snapshots_by_symbol["RUNE"]["final_state_after_quality_gate"] == "WATCHLIST"
    assert snapshots_by_symbol["RUNE"]["final_route_after_quality_gate"] == "RESEARCH_DIGEST"
    assert snapshots_by_symbol["RUNE"]["quality_state_block_reason"] == "opportunity_level_caps_state:watchlist"
    assert snapshots_by_symbol["RUNE"]["quality_gate_block_reason"] in (None, "")
    assert snapshots_by_symbol["RUNE"]["core_opportunity_id"]
    assert snapshots_by_symbol["RUNE"]["feedback_target"] == snapshots_by_symbol["RUNE"]["core_opportunity_id"]
    assert snapshots_by_symbol["RUNE"]["feedback_target_type"] == "core_opportunity_id"
    assert snapshots_by_symbol["HIGH"]["final_route_after_quality_gate"] == "HIGH_PRIORITY_RESEARCH"
    assert snapshots_by_symbol["HIGH"]["final_tier_after_quality_gate"] == "HIGH_PRIORITY_WATCH"
    assert snapshots_by_symbol["FADE"]["final_route_after_quality_gate"] == "TRIGGERED_FADE_RESEARCH"
    assert snapshots_by_symbol["FADE"]["final_tier_after_quality_gate"] == "TRIGGERED_FADE"
    inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=[{"run_id": "r1", "would_send_count": 1, "lane_counts_due": {"daily_digest": 1}}],
        alert_rows=rows,
        feedback_rows=[],
        research_cards_dir=Path(tmp) / "cards",
        profile="fixture",
        artifact_namespace="fixture",
        notification_runs_path=Path(tmp) / "runs.jsonl",
        alert_store_path=out,
        feedback_path=Path(tmp) / "feedback.jsonl",
    )
    assert "BTC" in {item.symbol for item in inbox.quality_gated_local_only}
    assert "BTC" not in {item.symbol for item in inbox.would_send_without_feedback}
    inbox_text = event_alpha_notification_inbox.format_notification_inbox(inbox)
    assert "local-only learning rows for optional review" in inbox_text
    review = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(profile="fixture", alert_rows=rows)
    )
    assert "Quality Gate Conflicts" in review
    assert "Quality Gate Conflicts:\n- none" in review
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": len(rows)}],
        alert_rows=rows,
        watchlist_rows=[btc, zero, digest, watch, rune, high, trigger],
        include_api_artifacts=True,
    )
    assert doctor.alertable_route_conflicts_with_opportunity_level == 0
    assert doctor.active_watchlist_rows_quality_capped >= 1
    assert doctor.universal_watchlist_state_conflicts == 0
    assert doctor.non_hypothesis_watchlist_quality_conflicts == 0
    assert doctor.quality_capped_watchlist_rows >= 1
    assert doctor.fresh_watchlist_state_conflict_rows == 0
    doctor_text = event_alpha_artifact_doctor.format_artifact_doctor_report(doctor)
    assert "quality-capped rows present:" in doctor_text
    assert "watchlist quality state:" in doctor_text
    uncapped_watchlist_conflict = asdict(btc)
    uncapped_watchlist_conflict["state"] = "WATCHLIST"
    uncapped_watchlist_conflict["final_state_after_quality_gate"] = "WATCHLIST"
    uncapped_watchlist_conflict["state_quality_capped"] = False
    uncapped_watchlist_conflict["run_mode"] = "burn_in"
    uncapped_watchlist_conflict["artifact_namespace"] = "notify_llm_quality"
    doctor_uncapped_watchlist = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 0}],
        watchlist_rows=[uncapped_watchlist_conflict],
        include_api_artifacts=True,
        strict=True,
    )
    assert doctor_uncapped_watchlist.status == "BLOCKED"
    assert doctor_uncapped_watchlist.fresh_watchlist_state_conflict_rows == 1
    with tempfile.TemporaryDirectory() as stale_tmp:
        stale_path = Path(stale_tmp) / "event_watchlist_state.jsonl"
        stale_non_hypothesis = asdict(btc)
        stale_non_hypothesis["key"] = "stale-non-hypothesis|chz"
        stale_non_hypothesis["symbol"] = "CHZ"
        stale_non_hypothesis["coin_id"] = "chiliz"
        stale_non_hypothesis["hypothesis_id"] = None
        stale_non_hypothesis["incident_id"] = None
        stale_non_hypothesis["state"] = "WATCHLIST"
        stale_non_hypothesis["requested_state_before_quality_gate"] = "WATCHLIST"
        stale_non_hypothesis["final_state_after_quality_gate"] = "WATCHLIST"
        stale_non_hypothesis["state_quality_capped"] = False
        stale_non_hypothesis["run_mode"] = "burn_in"
        stale_non_hypothesis["artifact_namespace"] = "notify_llm_quality"
        stale_path.write_text(json.dumps(stale_non_hypothesis) + "\n", encoding="utf-8")
        loaded_stale = event_watchlist.load_watchlist(stale_path).entries[0]
        assert event_watchlist.requested_state_value(loaded_stale) == "WATCHLIST"
        assert event_watchlist.final_state_value(loaded_stale) == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        assert loaded_stale.state == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        assert loaded_stale.state_quality_capped is True
        assert loaded_stale.quality_state_block_reason == "impact_path_type_insufficient_data"
        assert event_watchlist.final_state_value(stale_non_hypothesis) == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        stale_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "r1", "alertable": 0}],
            watchlist_rows=[stale_non_hypothesis],
            include_api_artifacts=True,
            strict=True,
        )
        assert stale_doctor.status == "BLOCKED"
        assert stale_doctor.universal_watchlist_state_conflicts == 1
        assert stale_doctor.non_hypothesis_watchlist_quality_conflicts == 1
    legacy_conflict = dict(btc_snapshot)
    legacy_conflict["run_id"] = "r1"
    legacy_conflict["route_alertable"] = True
    legacy_conflict["route"] = "RESEARCH_DIGEST"
    legacy_conflict["tier"] = "WATCHLIST"
    legacy_conflict.pop("alertable_after_quality_gate", None)
    legacy_conflict.pop("final_route_after_quality_gate", None)
    legacy_conflict.pop("final_tier_after_quality_gate", None)
    legacy_conflict.pop("snapshot_quality_classification", None)
    assert event_alpha_alert_store.classify_alert_snapshot(legacy_conflict) == "legacy_conflict"
    doctor_conflict = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
        alert_rows=[legacy_conflict],
        include_api_artifacts=True,
        strict=True,
    )
    assert doctor_conflict.alertable_route_conflicts_with_opportunity_level == 1
    assert doctor_conflict.status == "WARN"
    assert "alertable_route_conflicts_with_opportunity_level=1" in event_alpha_artifact_doctor.format_artifact_doctor_report(doctor_conflict)
    doctor_conflict_strict_api = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
        alert_rows=[legacy_conflict],
        include_api_artifacts=True,
        strict=True,
        strict_api=True,
    )
    assert doctor_conflict_strict_api.status == "BLOCKED"
    legacy_review = event_alpha_quality_review.format_quality_review(
        event_alpha_quality_review.build_quality_review(profile="fixture", alert_rows=[legacy_conflict])
    )
    assert "Quality Gate Conflicts" in legacy_review
    assert "BTC" in legacy_review
    legacy_inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=[{"run_id": "r1", "would_send_count": 1, "lane_counts_due": {"daily_digest": 1}}],
        alert_rows=[legacy_conflict],
        feedback_rows=[],
        research_cards_dir=Path(tmp) / "cards",
        profile="fixture",
        artifact_namespace="fixture",
        notification_runs_path=Path(tmp) / "runs.jsonl",
        alert_store_path=out,
        feedback_path=Path(tmp) / "feedback.jsonl",
    )
    assert "BTC" in {item.symbol for item in legacy_inbox.legacy_quality_conflicts}
    assert "BTC" not in {item.symbol for item in legacy_inbox.would_send_without_feedback}
    assert "legacy quality conflicts" in event_alpha_notification_inbox.format_notification_inbox(legacy_inbox)
    fresh_conflict = dict(btc_snapshot)
    fresh_conflict["run_mode"] = "burn_in"
    fresh_conflict["artifact_namespace"] = "notify_llm_quality"
    fresh_conflict["final_route_after_quality_gate"] = "RESEARCH_DIGEST"
    fresh_conflict["route"] = "RESEARCH_DIGEST"
    fresh_conflict["route_alertable"] = True
    assert event_alpha_alert_store.classify_alert_snapshot(fresh_conflict) == "legacy_conflict"
    doctor_fresh_conflict = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
        alert_rows=[fresh_conflict],
        include_api_artifacts=True,
        strict=True,
    )
    assert doctor_fresh_conflict.status == "BLOCKED"
    fresh_missing_final = dict(btc_snapshot)
    fresh_missing_final["run_mode"] = "burn_in"
    fresh_missing_final["artifact_namespace"] = "notify_llm_quality"
    fresh_missing_final.pop("final_route_after_quality_gate", None)
    assert event_alpha_alert_store.classify_alert_snapshot(fresh_missing_final) in {"legacy_conflict", "stale_pre_quality_gate"}
    doctor_missing_final = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r1", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
        alert_rows=[fresh_missing_final],
        include_api_artifacts=True,
        strict=True,
    )
    assert doctor_missing_final.status == "BLOCKED"

    daily = event_alpha_daily_brief.build_daily_brief(router_result=routed, watchlist_entries=[btc, zero, digest, watch, rune, high, trigger])
    assert "### Quality Gate Downgrades" in daily
    assert "BTC/btc:RESEARCH_DIGEST->STORE_ONLY" in daily
    assert "### Quality-Capped Watchlist Rows" in daily
    assert "BTC/btc: requested=WATCHLIST final=QUALITY_BLOCKED" in daily
    active_section = daily.split("### Active Watchlist", 1)[1].split("### Quality-Capped Watchlist Rows", 1)[0]
    assert "BTC/btc" not in active_section
    assert "WATCH/watch" in active_section
    assert "### Legacy Quality Conflicts" in daily
    freshness_section = daily.split("## Market Freshness Readiness", 1)[1].split("## Diagnostics Appendix", 1)[0]
    assert "Core opportunity freshness:" in freshness_section
    assert freshness_section.count("RUNE/thorchain") == 1
    card = event_research_cards.render_research_card(
        "BTC",
        watchlist_entries=[btc],
        alert_rows=[btc_snapshot],
        route_decisions=[by_symbol["BTC"]],
    )
    assert "## Quality Gate Result" in card.markdown
    assert "Requested route: RESEARCH_DIGEST" in card.markdown
    assert "Final route: STORE_ONLY" in card.markdown
    assert "Final tier: STORE_ONLY" in card.markdown
    assert "Snapshot classification: quality_gated_local" in card.markdown
    assert "## Lifecycle State Gate" in card.markdown
    assert "Requested WATCHLIST blocked because impact_path_type_insufficient_data" in card.markdown
    assert "impact_path_type_insufficient_data" in card.markdown
