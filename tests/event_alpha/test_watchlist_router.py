"""Focused Event Alpha operator behavior tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_watchlist_refresh_tracks_escalations_and_suppresses_duplicates():
    import tempfile
    from dataclasses import replace
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="watch-pumpx",
        provider="test",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/watch-pumpx",
        title="PumpX token offers synthetic exposure to SpaceX pre-IPO market",
        body="PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
        raw_json={
            "event": {
                "event_id": "watch-pumpx",
                "event_name": "PumpX SpaceX proxy watch",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-20T13:30:00Z",
                "event_time_confidence": 0.90,
                "external_asset": "SpaceX",
                "confidence": 0.90,
                "description": "PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
            }
        },
        source_confidence=0.90,
        content_hash="watch-pumpx",
    )
    asset = DiscoveredAsset(
        coin_id="pumpx",
        symbol="PUMPX",
        name="PumpX",
        aliases=("pumpx token", "PumpX"),
    )
    discovery = event_discovery.run_discovery([raw], [asset], now=now)
    base = event_alerts.build_event_alert_candidates(discovery, now=now)[0]
    active_quality = {
        **base.score_components,
        "impact_path_type": "proxy_exposure",
        "impact_path_strength": "strong",
        "candidate_role": "proxy_instrument",
        "evidence_quality_score": 82,
        "source_class": "crypto_news",
        "evidence_specificity": "direct_value_capture",
        "market_confirmation_score": 58,
        "market_confirmation_level": "weak",
        "opportunity_score_final": 72,
        "opportunity_level": "validated_digest",
        "opportunity_verdict_reasons": ["fixture_valid_proxy_watch"],
        "why_local_only": "not_local_only",
        "why_not_watchlist": "needs_strong_market_confirmation",
        "manual_verification_items": ["verify proxy instrument and market confirmation"],
        "upgrade_requirements": ["needs_strong_market_confirmation"],
        "downgrade_warnings": [],
    }
    radar = replace(base, tier=event_alerts.EventAlertTier.RADAR_DIGEST, opportunity_score=60, score_components=active_quality)
    watch_quality = {**active_quality, "market_confirmation_score": 70, "market_confirmation_level": "moderate", "opportunity_score_final": 82, "opportunity_level": "watchlist", "why_not_watchlist": "already_watchlisted", "upgrade_requirements": []}
    watch = replace(base, tier=event_alerts.EventAlertTier.WATCHLIST, opportunity_score=75, score_components=watch_quality)

    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "watchlist.jsonl"
        cfg = event_watchlist.EventWatchlistConfig(enabled=True, state_path=state_path)
        first = event_watchlist.refresh_watchlist([radar], cfg=cfg, now=now)
        assert first.rows_written == 1
        assert first.entries[0].state == event_watchlist.EventWatchlistState.RADAR.value
        assert first.entries[0].should_alert is True
        assert first.entries[0].first_radar_at == now.isoformat()

        duplicate = event_watchlist.refresh_watchlist(
            [radar],
            cfg=cfg,
            now=datetime(2026, 6, 18, 13, 0, tzinfo=timezone.utc),
        )
        assert duplicate.entries[0].state == event_watchlist.EventWatchlistState.RADAR.value
        assert duplicate.entries[0].should_alert is False
        assert duplicate.entries[0].suppressed_reason == "duplicate state, no escalation"
        assert duplicate.entries[0].first_seen_at == first.entries[0].first_seen_at

        escalated = event_watchlist.refresh_watchlist(
            [watch],
            cfg=cfg,
            now=datetime(2026, 6, 18, 14, 0, tzinfo=timezone.utc),
        )
        assert escalated.entries[0].state == event_watchlist.EventWatchlistState.WATCHLIST.value
        assert escalated.entries[0].previous_state == event_watchlist.EventWatchlistState.RADAR.value
        assert escalated.entries[0].should_alert is True
        assert escalated.entries[0].highest_score == 75
        assert len(event_watchlist.load_watchlist(state_path, latest_only=False).entries) == 3


def test_event_watchlist_expiration_and_backward_compatible_reads():
    import json
    import tempfile
    from dataclasses import replace
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="expired-proxy",
        provider="test",
        fetched_at=now,
        published_at=now,
        source_url="https://example.test/expired",
        title="PumpX token offers synthetic exposure to SpaceX pre-IPO market",
        body="PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
        raw_json={
            "event": {
                "event_id": "expired-proxy",
                "event_name": "Expired proxy event",
                "event_type": "ipo_proxy",
                "event_time": "2026-06-14T13:30:00Z",
                "event_time_confidence": 0.90,
                "external_asset": "SpaceX",
                "confidence": 0.90,
                "description": "PumpX token holders can trade synthetic exposure to SpaceX before the IPO.",
            }
        },
        source_confidence=0.90,
        content_hash="expired-proxy",
    )
    asset = DiscoveredAsset(coin_id="pumpx", symbol="PUMPX", name="PumpX", aliases=("pumpx token",))
    alert = event_alerts.build_event_alert_candidates(
        event_discovery.run_discovery([raw], [asset], now=now),
        now=now,
    )[0]
    alert = replace(alert, tier=event_alerts.EventAlertTier.RADAR_DIGEST, opportunity_score=60)

    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "watchlist.jsonl"
        cfg = event_watchlist.EventWatchlistConfig(
            enabled=True,
            state_path=state_path,
            expire_hours_after_event=72,
        )
        result = event_watchlist.refresh_watchlist([alert], cfg=cfg, now=now)
        assert result.entries[0].state == event_watchlist.EventWatchlistState.EXPIRED.value
        assert result.entries[0].should_alert is False
        assert result.entries[0].suppressed_reason == "terminal non-alert state"

        old_path = Path(tmp) / "old-watchlist.jsonl"
        old_path.write_text(
            json.dumps({
                "row_type": "event_watchlist_state",
                "key": "old|coin|rel||",
                "event_id": "old",
                "coin_id": "coin",
                "symbol": "OLD",
                "relationship_type": "proxy_attention",
                "state": "RADAR",
                "last_seen_at": now.isoformat(),
                "latest_score": 61,
            }) + "\nnot-json\n",
            encoding="utf-8",
        )
        loaded = event_watchlist.load_watchlist(old_path)
        assert loaded.rows_read == 1
        assert loaded.entries[0].state == event_watchlist.EventWatchlistState.RADAR.value
        assert loaded.entries[0].highest_score == 61


def test_event_alpha_router_routes_watchlist_escalations_safely():
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    def row(
        symbol,
        state,
        playbook,
        *,
        should_alert=True,
        score=75,
        suppressed_reason=None,
    ):
        quality = {
            "impact_path_type": "proxy_exposure",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_instrument",
            "evidence_quality_score": 78,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_value_capture",
            "market_confirmation_score": 62,
            "market_confirmation_level": "moderate",
            "opportunity_score_final": score,
            "opportunity_level": "high_priority"
            if state in {"HIGH_PRIORITY", "ARMED", "EVENT_PASSED"}
            else "watchlist",
            "opportunity_verdict_reasons": ["test_quality_fixture"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify catalyst and market confirmation"],
            "upgrade_requirements": [],
            "downgrade_warnings": ["none"],
        }
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol}|coin|rel|asset|time",
            cluster_id="spacex|ipo_proxy|2026-06-20",
            event_id=f"{symbol}-event",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_exposure",
            external_asset="SpaceX",
            event_time="2026-06-20T13:30:00+00:00",
            state=state,
            previous_state="RADAR",
            first_seen_at="2026-06-18T12:00:00+00:00",
            last_seen_at="2026-06-18T13:00:00+00:00",
            source_count=1,
            highest_score=score,
            latest_score=score,
            latest_tier=state,
            latest_event_name=f"{symbol} SpaceX event",
            latest_source="test",
            latest_playbook_type=playbook,
            latest_playbook_score=score,
            latest_playbook_action="watchlist",
            latest_score_components=quality,
            should_alert=should_alert,
            suppressed_reason=suppressed_reason,
        )

    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=6,
        latest_only=True,
        entries=[
            row(
                "PFADE",
                event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
                event_playbooks.EventPlaybookType.PROXY_FADE.value,
                score=95,
            ),
            row(
                "BADTRIG",
                event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
                event_playbooks.EventPlaybookType.DIRECT_EVENT.value,
                score=90,
            ),
            row(
                "ATTN",
                event_watchlist.EventWatchlistState.WATCHLIST.value,
                event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
                score=74,
            ),
            row(
                "DUP",
                event_watchlist.EventWatchlistState.WATCHLIST.value,
                event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
                should_alert=False,
                suppressed_reason="duplicate state, no escalation",
            ),
            row(
                "ANOM",
                event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
                event_playbooks.EventPlaybookType.MARKET_ANOMALY.value,
                should_alert=False,
            ),
            row(
                "NOISE",
                event_watchlist.EventWatchlistState.RADAR.value,
                event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value,
            ),
        ],
    )
    result = event_alpha_router.route_watchlist(
        read,
        cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
    )
    by_symbol = {decision.entry.symbol: decision for decision in result.decisions}
    assert by_symbol["PFADE"].route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
    assert by_symbol["PFADE"].alertable is True
    assert by_symbol["BADTRIG"].route == event_alpha_router.EventAlphaRoute.LOCAL_REPORT
    assert by_symbol["BADTRIG"].alertable is False
    assert "non-proxy playbook cannot route triggered fade" in by_symbol["BADTRIG"].warnings
    assert by_symbol["ATTN"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["DUP"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert by_symbol["ANOM"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["NOISE"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY

    text = event_alpha_router.format_router_report(result)
    assert "EVENT ALPHA ROUTER REPORT" in text
    assert "TRIGGERED_FADE_RESEARCH" in text
    assert "SUPPRESS_DUPLICATE" in text
    assert "no sends, trades, or paper rows" in text
    routed_digest = event_alpha_router.format_routed_telegram_digest(result.alertable_decisions)
    assert "Event Alpha routed research alerts" in routed_digest
    assert "PFADE" in routed_digest
    assert "ATTN" in routed_digest
    assert "BADTRIG" not in routed_digest
    assert "alert_id: ea:" in text
    assert "card_id: card_" in text
    assert "FEEDBACK_TARGET=ea:" in text
    assert "alert_id=ea:" in routed_digest


def test_event_alpha_router_daily_digest_for_validated_impact_hypotheses():
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    def entry(
        symbol,
        score=78,
        *,
        should_alert=True,
        impact_category="security_or_regulatory_shock",
        playbook="security_or_regulatory_shock",
        external_asset="unknown",
        evidence=None,
        validation_stage="impact_path_validated",
        impact_path_reason="exploit_security_event",
        impact_path_type=None,
        impact_path_strength="strong",
        candidate_role="direct_subject",
        opportunity_score_v2=None,
        opportunity_score_final=None,
        opportunity_level="validated_digest",
        market_confirmation_level="moderate",
        digest_eligible_by_impact_path=True,
        state=None,
    ):
        impact_path_type = impact_path_type or impact_path_reason
        opportunity_score_v2 = opportunity_score_v2 if opportunity_score_v2 is not None else score
        opportunity_score_final = opportunity_score_final if opportunity_score_final is not None else opportunity_score_v2
        evidence = evidence or (f"{symbol} {symbol.lower()} exploit catalyst link",)
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"hypothesis|cluster:{symbol}|{impact_category}",
            cluster_id=f"cluster:{symbol}",
            event_id=f"hyp:{symbol}",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="impact_hypothesis",
            external_asset=external_asset,
            event_time=None,
            state=state or event_watchlist.EventWatchlistState.RADAR.value,
            previous_state=event_watchlist.EventWatchlistState.HYPOTHESIS.value,
            first_seen_at="2026-06-23T12:00:00+00:00",
            last_seen_at="2026-06-23T12:30:00+00:00",
            source_count=1,
            highest_score=score,
            latest_score=score,
            latest_tier="HIGH_PRIORITY_WATCH" if state == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value else "RADAR_DIGEST",
            latest_event_name=f"{symbol} validated impact hypothesis",
            latest_source="impact_hypothesis",
            latest_playbook_type=playbook,
            latest_effective_playbook_type=playbook,
            latest_playbook_score=score,
            latest_playbook_action="high_priority_watch" if state == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value else "radar_digest",
            latest_score_components={
                "hypothesis_id": f"hyp:{symbol}",
                "impact_category": impact_category,
                "validation_stage": validation_stage,
                "impact_path_reason": impact_path_reason,
                "impact_path_type": impact_path_type,
                "impact_path_strength": impact_path_strength,
                "candidate_role": candidate_role,
                "evidence_specificity_score": 88,
                "digest_eligible_by_impact_path": digest_eligible_by_impact_path,
                "opportunity_score_v2": opportunity_score_v2,
                "opportunity_score_final": opportunity_score_final,
                "opportunity_level": opportunity_level,
                "market_confirmation_score": 50,
                "market_confirmation_level": market_confirmation_level,
                "evidence_quality_score": 82,
                "source_class": "crypto_news",
                "evidence_specificity": "direct_token_mechanism",
                "opportunity_verdict_reasons": ["direct_token_event_with_strong_evidence"],
                "manual_verification_items": ["verify independent source"],
                "opportunity_score_components": {
                    "impact_path_strength": 95 if impact_path_strength == "strong" else 35,
                    "source_evidence_specificity": 88,
                    "market_confirmation": 50,
                },
                "hypothesis_score": score,
                "score": score,
                "playbook_type": playbook,
                "effective_playbook_type": playbook,
                "validated_symbol": symbol,
                "validated_coin_id": symbol.lower(),
                "validated_asset": {"symbol": symbol, "coin_id": symbol.lower(), "name": symbol, "validated": True},
                "evidence_quotes": list(evidence),
                "validation_reasons": list(evidence),
            },
            material_change_reasons=("hypothesis_validated",),
            should_alert=should_alert,
        )

    def proxy_entry(symbol, score=72):
        quality = {
            "impact_path_type": "proxy_exposure",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_instrument",
            "evidence_quality_score": 78,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_value_capture",
            "market_confirmation_score": 55,
            "market_confirmation_level": "moderate",
            "opportunity_score_final": score,
            "opportunity_level": "watchlist",
            "opportunity_verdict_reasons": ["proxy_impact_path_explained"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify market confirmation"],
            "upgrade_requirements": [],
            "downgrade_warnings": [],
        }
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"proxy|cluster:{symbol}|proxy_attention",
            cluster_id=f"cluster:{symbol}",
            event_id=f"proxy:{symbol}",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_attention",
            external_asset="SpaceX",
            event_time=None,
            state=event_watchlist.EventWatchlistState.RADAR.value,
            previous_state=event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
            first_seen_at="2026-06-23T12:00:00+00:00",
            last_seen_at="2026-06-23T12:30:00+00:00",
            source_count=2,
            highest_score=score,
            latest_score=score,
            latest_tier="RADAR_DIGEST",
            latest_event_name=f"{symbol} proxy candidate",
            latest_source="test",
            latest_playbook_type="proxy_attention",
            latest_playbook_score=score,
            latest_playbook_action="radar_digest",
            latest_score_components=quality,
            should_alert=True,
        )

    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=4,
        latest_only=True,
        entries=[
            entry("RUNE", 90, evidence=("THORChain RUNE faces an exploit and security incident investigation.",)),
            entry(
                "ZEC",
                82,
                impact_category="listing_liquidity_event",
                playbook="listing_volatility",
                evidence=("Zcash ZEC miner completes a Nasdaq listing and public market access changes.",),
                impact_path_reason="listing_liquidity_event",
            ),
            entry(
                "BTC",
                88,
                impact_category="political_meme_proxy",
                playbook="political_meme_event",
                evidence=("Bitcoin quantum-computing policy debate drew Trump comments.",),
                validation_stage="catalyst_link_validated",
                impact_path_reason="generic_policy_only",
                impact_path_type="technology_risk",
                impact_path_strength="weak",
                candidate_role="macro_affected_asset",
                opportunity_score_v2=76,
                digest_eligible_by_impact_path=False,
            ),
            entry("LOW", 50, evidence=("LOW token exploit catalyst link.",)),
            proxy_entry("VELVET", 72),
            entry("SECTOR", 70),
        ],
    )
    enabled = event_alpha_router.route_watchlist(
        read,
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            validated_hypothesis_digest_enabled=True,
            max_validated_hypothesis_digest_items=1,
            max_digest_items=2,
        ),
    )
    by_symbol = {decision.entry.symbol: decision for decision in enabled.decisions}
    assert by_symbol["RUNE"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["RUNE"].lane == event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST
    assert by_symbol["RUNE"].alertable is True
    assert "digest opportunity verdict" in by_symbol["RUNE"].reason
    assert by_symbol["ZEC"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert by_symbol["ZEC"].alertable is False
    assert by_symbol["ZEC"].reason == "Validated impact hypothesis digest cap reached for this run."
    assert by_symbol["BTC"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["BTC"].alertable is False
    assert "impact_path_not_digest_eligible" in by_symbol["BTC"].reason
    assert by_symbol["LOW"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert by_symbol["LOW"].alertable is False
    assert "opportunity_score_final_below_threshold" in by_symbol["LOW"].reason
    assert by_symbol["VELVET"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert by_symbol["VELVET"].alertable is True
    assert by_symbol["SECTOR"].alertable is False
    assert by_symbol["SECTOR"].route != event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH

    canonical = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=2,
            latest_only=True,
            entries=[
                entry("AAVE", 72, opportunity_score_v2=64, opportunity_score_final=72, opportunity_level="validated_digest"),
                entry("VELVET", 96, opportunity_score_final=96, opportunity_level="high_priority", impact_category="tokenized_stock_venue", playbook="proxy_attention", impact_path_reason="venue_value_capture", impact_path_type="venue_value_capture", candidate_role="proxy_venue", external_asset="SpaceX", state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value),
                entry("BAD", 88, opportunity_score_v2=88, opportunity_score_final=40, opportunity_level="local_only"),
            ],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            validated_hypothesis_digest_enabled=True,
            max_validated_hypothesis_digest_items=5,
        ),
    )
    canonical_by_symbol = {decision.entry.symbol: decision for decision in canonical.decisions}
    assert canonical_by_symbol["AAVE"].route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert canonical_by_symbol["AAVE"].alertable is True
    assert canonical_by_symbol["AAVE"].routing_score_used == 72
    assert canonical_by_symbol["AAVE"].routing_score_source == "opportunity_score_final"
    assert canonical_by_symbol["AAVE"].routing_verdict_used == "validated_digest"
    assert canonical_by_symbol["VELVET"].route == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH
    assert canonical_by_symbol["VELVET"].alertable is True
    assert "Validated impact hypothesis reached high-priority opportunity verdict" in canonical_by_symbol["VELVET"].reason
    assert canonical_by_symbol["BAD"].route == event_alpha_router.EventAlphaRoute.STORE_ONLY
    assert canonical_by_symbol["BAD"].alertable is False
    canonical_report = event_alpha_router.format_router_report(canonical)
    assert "source=opportunity_score_final value=72" in canonical_report
    assert "opportunity_score_v2_below_threshold" not in canonical_report

    disabled = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=1,
            latest_only=True,
            entries=[entry("RUNE", 90, evidence=("THORChain RUNE exploit catalyst link.",))],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            validated_hypothesis_digest_enabled=False,
        ),
    )
    only = disabled.decisions[0]
    assert only.route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST
    assert only.alertable is False

    message = event_alpha_router.format_routed_telegram_digest([by_symbol["RUNE"]], profile="notify_llm")
    assert "Validated impact hypothesis" in message
    assert "Not a trade signal" in message
    assert "not a calibrated strategy" in message

    card = event_research_cards.render_research_card(
        "RUNE",
        watchlist_entries=[by_symbol["RUNE"].entry],
        route_decisions=[by_symbol["RUNE"]],
    )
    assert card.found is True
    assert "## Impact Hypothesis Context" in card.markdown
    assert "Validated asset: RUNE/rune" in card.markdown
    assert "Final opportunity verdict" in card.markdown
    assert "Evidence quality" in card.markdown
    assert "Market confirmation" in card.markdown
    assert "Impact path reason: exploit_security_event" in card.markdown
    assert "Quality gate: passed" in card.markdown
    assert "not a calibrated strategy or trade signal" in card.markdown
    assert "OPENAI_API_KEY" not in card.markdown
    assert "TELEGRAM_BOT_TOKEN" not in card.markdown


def test_event_alpha_near_miss_refreshes_market_context_without_triggering_fade():
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.radar.near_miss as event_near_miss
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    base_components = {
        "validated_symbol": "ENA",
        "validated_coin_id": "ethena",
        "impact_category": "security_or_regulatory_shock",
        "playbook_type": "security_or_regulatory_shock",
        "impact_path_type": "exploit_security_event",
        "impact_path_strength": "strong",
        "candidate_role": "direct_subject",
        "source_class": "crypto_news",
        "evidence_specificity": "direct_token_mechanism",
        "source_quality": 82,
        "evidence_quality_score": 82,
        "market_confirmation": 15,
        "market_confirmation_score": 15,
        "market_confirmation_level": "weak",
        "opportunity_score_final": 64,
        "opportunity_level": "exploratory",
        "missing_requirements": ["market_confirmation"],
        "why_not_watchlist": "market_confirmation",
        "opportunity_score_v2": 80,
    }
    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:ena",
        event_cluster_id="cluster:ena",
        event_type="security_event",
        external_asset="Ethena",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("security",),
        candidate_symbols=("ENA",),
        candidate_coin_ids=("ethena",),
        validated_candidate_assets=({"symbol": "ENA", "coin_id": "ethena", "validated": True},),
        crypto_candidate_assets=({"symbol": "ENA", "coin_id": "ethena", "accepted": True},),
        playbook_hint="security_or_regulatory_shock",
        confidence=0.86,
        hypothesis_score=82,
        score_components=base_components,
        validation_stage="impact_path_validated",
        status="validated",
        evidence_quotes=("ENA exploit security event was confirmed.",),
        impact_path_reason="exploit_security_event",
        impact_path_type="exploit_security_event",
        impact_path_strength="strong",
        candidate_role="direct_subject",
        evidence_quality_score=82,
        source_class="crypto_news",
        evidence_specificity="direct_token_mechanism",
        market_confirmation_score=15,
        market_confirmation_level="weak",
        market_confirmation_missing_fields=("market_confirmation",),
        opportunity_score_v2=80,
        opportunity_score_final=64,
        opportunity_level="exploratory",
        missing_requirements=("market_confirmation",),
        why_not_watchlist="market_confirmation",
    )
    near = event_near_miss.detect_near_miss_rows((hypothesis,), cfg=event_near_miss.EventNearMissConfig())
    assert len(near) == 1
    assert near[0].symbol == "ENA"
    assert near[0].core_opportunity_id
    assert "targeted_market_refresh" in near[0].recommended_refresh_actions
    queue = event_near_miss.targeted_market_refresh_queue((hypothesis,), cfg=event_near_miss.EventNearMissConfig())
    assert queue[0].refresh_id == f"refresh:{near[0].core_opportunity_id}"
    duplicate_hypothesis = __import__("dataclasses").replace(
        hypothesis,
        hypothesis_id="hyp:ena:support",
        opportunity_score_final=63,
        score_components={**hypothesis.score_components, "opportunity_score_final": 63},
    )
    deduped_queue = event_near_miss.targeted_market_refresh_queue(
        (hypothesis, duplicate_hypothesis),
        cfg=event_near_miss.EventNearMissConfig(),
    )
    assert len(deduped_queue) == 1
    assert deduped_queue[0].core_opportunity_id == near[0].core_opportunity_id
    assert queue[0].reason == "market_confirmation"

    generic = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:generic",
        event_cluster_id="cluster:generic",
        event_type="macro",
        external_asset="Bitcoin World",
        impact_category="market_anomaly_unknown",
        candidate_sectors=("macro",),
        candidate_symbols=("BTC",),
        candidate_coin_ids=("bitcoin",),
        score_components={
            **base_components,
            "validated_symbol": "BTC",
            "validated_coin_id": "bitcoin",
            "impact_path_type": "generic_cooccurrence_only",
            "candidate_role": "generic_mention",
            "opportunity_score_final": 64,
            "opportunity_level": "exploratory",
        },
        impact_path_type="generic_cooccurrence_only",
        candidate_role="generic_mention",
        opportunity_score_final=64,
        opportunity_level="exploratory",
    )
    assert event_near_miss.detect_near_miss_rows((generic,), cfg=event_near_miss.EventNearMissConfig()) == ()

    stale_velvet = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:velvet-stale",
        event_cluster_id="cluster:spacex",
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category="tokenized_stock_venue",
        candidate_sectors=("rwa",),
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        validated_candidate_assets=({"symbol": "VELVET", "coin_id": "velvet", "validated": True},),
        crypto_candidate_assets=({"symbol": "VELVET", "coin_id": "velvet", "accepted": True},),
        playbook_hint="proxy_attention",
        confidence=0.91,
        hypothesis_score=90,
        score_components={
            **base_components,
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "impact_category": "tokenized_stock_venue",
            "playbook_type": "proxy_attention",
            "impact_path_type": "venue_value_capture",
            "candidate_role": "proxy_venue",
            "external_asset": "SpaceX",
            "market_confirmation": 49,
            "market_confirmation_score": 49,
            "market_confirmation_level": "weak",
            "market_context_freshness_status": "stale",
            "market_context_freshness_cap_applied": True,
            "market_context_timestamp": "2026-06-14T00:00:00+00:00",
            "market_confirmation_warnings": ("market_context_stale_capped",),
            "market_confirmation_missing_fields": ("needs_fresh_market_confirmation",),
            "opportunity_score_final": 70,
            "opportunity_level": "validated_digest",
            "missing_requirements": ("needs_fresh_market_confirmation",),
            "why_not_watchlist": "needs_fresh_market_confirmation",
            "opportunity_score_v2": 88,
        },
        validation_stage="impact_path_validated",
        status="validated",
        evidence_quotes=("VELVET gives users SpaceX pre-IPO exposure.",),
        impact_path_reason="venue_value_capture",
        impact_path_type="venue_value_capture",
        impact_path_strength="strong",
        candidate_role="proxy_venue",
        evidence_quality_score=86,
        source_class="crypto_native",
        evidence_specificity="asset_and_catalyst",
        market_confirmation_score=49,
        market_confirmation_level="weak",
        market_confirmation_warnings=("market_context_stale_capped",),
        market_confirmation_missing_fields=("needs_fresh_market_confirmation",),
        market_context_timestamp="2026-06-14T00:00:00+00:00",
        market_context_freshness_status="stale",
        market_context_freshness_cap_applied=True,
        opportunity_score_v2=88,
        opportunity_score_final=70,
        opportunity_level="validated_digest",
        missing_requirements=("needs_fresh_market_confirmation",),
        why_not_watchlist="needs_fresh_market_confirmation",
    )
    stale_near = event_near_miss.detect_near_miss_rows((stale_velvet,), cfg=event_near_miss.EventNearMissConfig())
    assert len(stale_near) == 1
    assert stale_near[0].opportunity_level_before == "validated_digest"
    assert event_near_miss.is_upgrade_candidate(stale_near[0]) is True
    near_section, upgrade_section = event_near_miss.split_near_miss_candidates((*near, *stale_near))
    assert [item.symbol for item in near_section] == ["ENA"]
    assert [item.symbol for item in upgrade_section] == ["VELVET"]
    split_report = event_near_miss.format_near_miss_report((*near, *stale_near), profile="fixture")
    assert "## Near-Miss Candidates" in split_report
    assert "## Upgrade Candidates" in split_report
    assert "- ENA/ethena" in split_report.split("## Upgrade Candidates", 1)[0]
    assert "- VELVET/velvet" in split_report.split("## Upgrade Candidates", 1)[1]
    assert "targeted_market_refresh" in stale_near[0].recommended_refresh_actions
    stale_queue = event_near_miss.targeted_market_refresh_queue((stale_velvet,), cfg=event_near_miss.EventNearMissConfig())
    assert stale_queue[0].symbol == "VELVET"
    probe = event_near_miss.refresh_market_context_for_candidates(
        stale_queue,
        market_rows=({
            "coin_id": "velvet",
            "symbol": "VELVET",
            "return_24h": 82,
            "return_72h": 148,
            "volume_zscore_24h": 5.4,
            "volume_to_market_cap": 0.44,
            "timestamp": "2026-06-15T15:30:00+00:00",
            "source": "fixture_targeted_market_refresh",
        },),
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    assert probe[0]["success"] is True
    assert probe[0]["market_context_after"]["data_quality"] == "fresh"

    class FailingProvider:
        name = "failing_provider"

        def fetch_market_rows(self, coin_ids, *, max_assets=50):
            raise RuntimeError("boom")

    failed_probe = event_near_miss.refresh_market_context_for_candidates(
        stale_queue,
        targeted_market_provider=FailingProvider(),
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    assert failed_probe[0]["success"] is False
    assert failed_probe[0]["error_class"] == "RuntimeError"

    refreshed = event_near_miss.refresh_near_miss_hypotheses(
        (hypothesis,),
        cfg=event_near_miss.EventNearMissConfig(market_refresh_enabled=True, max_market_refresh_assets=5),
        market_rows=({
            "coin_id": "ethena",
            "symbol": "ENA",
            "return_24h": 58,
            "return_72h": 96,
            "volume_zscore_24h": 4.5,
            "volume_to_market_cap": 0.42,
            "timestamp": "2026-06-26T10:00:00+00:00",
            "source": "fixture_market",
        },),
        now=datetime(2026, 6, 26, 11, 0, tzinfo=timezone.utc),
    )
    updated = refreshed.hypotheses[0]
    refreshed_near = refreshed.near_misses[0]
    assert refreshed_near.market_refresh_attempted is True
    assert refreshed_near.market_refresh_success is True
    assert refreshed_near.market_refresh_provider == "cycle_rows"
    assert refreshed_near.refresh_upgrade_status in {"upgraded", "improved_score"}
    assert refreshed_near.opportunity_score_after > refreshed_near.opportunity_score_before
    assert updated.opportunity_level in {"validated_digest", "watchlist", "high_priority"}
    assert updated.opportunity_score_final >= 65
    assert updated.market_context_data_quality == "fresh"
    assert updated.opportunity_level_before_refresh == "exploratory"
    assert updated.opportunity_level_after_refresh == updated.opportunity_level
    assert updated.market_confirmation_after_refresh == updated.market_confirmation_score
    assert updated.score_components["final_opportunity_level"] == updated.opportunity_level
    assert updated.score_components["final_opportunity_score"] == updated.opportunity_score_final
    assert updated.score_components["final_verdict_source"] == "market_refresh"
    assert updated.score_components["market_data_freshness"] == "fresh"
    assert updated.score_components["market_reaction_confirmation"] in {"moderate", "strong"}
    assert updated.score_components["opportunity_score_v2"] == 80
    assert "TRIGGERED_FADE" not in event_near_miss.format_near_miss_report(refreshed.near_misses)

    report = event_near_miss.format_near_miss_report(refreshed.near_misses, profile="quality_validation")
    assert "ENA/ethena" in report
    assert "market_refresh: attempted=true success=true" in report
    assert "provider=cycle_rows" in report

    hypothesis_row = {
        **updated.__dict__,
        "profile": "quality_validation",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "quality_validation",
    }
    daily = event_alpha_daily_brief.build_daily_brief(
        hypothesis_rows=[hypothesis_row],
        requested_profile="quality_validation",
        artifact_namespace="quality_validation",
    )
    assert "## Near-Miss Candidates" in daily
    assert "ENA/ethena" in daily

    audit = event_opportunity_audit.format_opportunity_audit("ENA", hypotheses=[updated], profile="quality_validation")
    assert "## Near-miss status" in audit
    assert "status: targeted refresh previously applied" in audit
    assert "targeted refresh:" in audit
    assert "market_confirmation=" in audit

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|cluster:ena|security_or_regulatory_shock",
        cluster_id="cluster:ena",
        event_id="hyp:ena",
        coin_id="ethena",
        symbol="ENA",
        relationship_type="impact_hypothesis",
        external_asset="Ethena",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=event_watchlist.EventWatchlistState.HYPOTHESIS.value,
        first_seen_at="2026-06-26T10:00:00+00:00",
        last_seen_at="2026-06-26T11:00:00+00:00",
        latest_score=80,
        latest_tier="RADAR_DIGEST",
        latest_event_name="ENA refreshed near miss",
        latest_source="fixture",
        latest_score_components=updated.score_components,
        opportunity_score_final=updated.opportunity_score_final,
        opportunity_level=updated.opportunity_level,
        should_alert=True,
    )
    routed = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=1,
            latest_only=True,
            entries=[entry],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True, validated_hypothesis_digest_enabled=True),
    )
    assert routed.decisions[0].route != event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH


def test_event_alpha_router_routes_material_changes_with_lanes():
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    def row(symbol, *, reasons=(), score_jump=0, state=None, playbook=None, should_alert=True, history=None):
        quality = {
            "impact_path_type": "proxy_exposure",
            "impact_path_strength": "strong",
            "candidate_role": "proxy_instrument",
            "evidence_quality_score": 78,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_value_capture",
            "market_confirmation_score": 62,
            "market_confirmation_level": "moderate",
            "opportunity_score_final": 80,
            "opportunity_level": "watchlist",
            "opportunity_verdict_reasons": ["test_quality_fixture"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify catalyst and market confirmation"],
            "upgrade_requirements": [],
            "downgrade_warnings": [],
        }
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol}|coin|rel",
            cluster_id="spacex|ipo_proxy|2026-06-20",
            event_id=f"{symbol}-event",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_attention",
            external_asset="SpaceX",
            event_time="2026-06-20T13:30:00+00:00",
            state=state or event_watchlist.EventWatchlistState.WATCHLIST.value,
            previous_state=state or event_watchlist.EventWatchlistState.WATCHLIST.value,
            first_seen_at="2026-06-18T12:00:00+00:00",
            last_seen_at="2026-06-18T14:00:00+00:00",
            source_count=2,
            highest_score=80,
            latest_score=80,
            latest_tier="WATCHLIST",
            latest_event_name=f"{symbol} SpaceX event",
            latest_source="test",
            latest_playbook_type=playbook or event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
            latest_playbook_score=80,
            latest_playbook_action="watchlist",
            latest_score_components=quality,
            should_alert=should_alert,
            score_jump=score_jump,
            material_change_reasons=tuple(reasons),
            alert_history=history or [
                {"observed_at": "2026-06-18T12:00:00+00:00", "should_alert": False},
                {"observed_at": "2026-06-18T14:00:00+00:00", "should_alert": should_alert},
            ],
            suppressed_reason=None if should_alert else "duplicate state, no escalation",
        )

    read = event_watchlist.EventWatchlistReadResult(
        state_path=Path("watchlist.jsonl"),
        rows_read=5,
        latest_only=True,
        entries=[
            row("JUMP", reasons=("score_jump",), score_jump=15),
            row("SRC", reasons=("new_independent_source",)),
            row("TIME", reasons=("event_time_upgrade",)),
            row(
                "COOL",
                reasons=("score_jump",),
                score_jump=15,
                history=[
                    {"observed_at": "2026-06-18T13:00:00+00:00", "should_alert": True},
                    {"observed_at": "2026-06-18T14:00:00+00:00", "should_alert": True},
                ],
            ),
            row("DUP", should_alert=False),
            row(
                "TRIG",
                state=event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
                playbook=event_playbooks.EventPlaybookType.PROXY_FADE.value,
                should_alert=False,
            ),
        ],
    )
    result = event_alpha_router.route_watchlist(read, cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True))
    by_symbol = {decision.entry.symbol: decision for decision in result.decisions}
    assert by_symbol["JUMP"].alertable is True
    assert by_symbol["JUMP"].lane == event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST
    assert by_symbol["SRC"].alertable is True
    assert by_symbol["TIME"].alertable is True
    assert by_symbol["COOL"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert "cooldown" in by_symbol["COOL"].reason.lower()
    assert by_symbol["DUP"].route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE
    assert by_symbol["TRIG"].route == event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH
    assert by_symbol["TRIG"].lane == event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE


def test_event_alpha_cycle_send_uses_router_approved_decisions_only():
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    class FakeStorage:
        meta = {}

        def __init__(self, path):
            self.path = path
            self.closed = False

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

        def active_subscribers(self):
            return ["chat"]

        def close(self):
            self.closed = True

    def entry(symbol, *, alertable=True, playbook=None, state=None):
        state = state or event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
        playbook = playbook or event_playbooks.EventPlaybookType.PROXY_ATTENTION.value
        return event_watchlist.EventWatchlistEntry(
            schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
            row_type="event_watchlist_state",
            key=f"{symbol}|coin|{playbook}",
            cluster_id="spacex|ipo_proxy|2026-06-20",
            event_id=f"{symbol}-event",
            coin_id=symbol.lower(),
            symbol=symbol,
            relationship_type="proxy_attention",
            external_asset="SpaceX",
            event_time="2026-06-20T13:30:00+00:00",
            state=state,
            previous_state="WATCHLIST",
            first_seen_at="2026-06-18T12:00:00+00:00",
            last_seen_at="2026-06-18T13:00:00+00:00",
            source_count=1,
            highest_score=82,
            latest_score=82,
            latest_tier="HIGH_PRIORITY_WATCH",
            latest_event_name=f"{symbol} route event",
            latest_source="test",
            latest_playbook_type=playbook,
            latest_playbook_score=82,
            latest_playbook_action="high_priority_watch",
            should_alert=alertable,
            suppressed_reason=None if alertable else "duplicate state, no escalation",
        )

    sent = []

    def fake_send(message, *, parse_mode=None, chat_ids=None):
        sent.append((message, parse_mode, tuple(chat_ids or ())))
        return True

    original_storage = scanner.Storage
    original_send = scanner.send_telegram
    original_structured_send = scanner.send_telegram_structured
    original_ids = config.TELEGRAM_CHAT_IDS
    original_notification_flags = {
        "EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY": config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY,
        "EVENT_ALPHA_NOTIFY_SCOPE": config.EVENT_ALPHA_NOTIFY_SCOPE,
        "EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED": config.EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED,
        "EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED": config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED,
    }
    FakeStorage.meta = {}
    scanner.Storage = FakeStorage
    scanner.send_telegram = fake_send
    scanner.send_telegram_structured = fake_send
    config.TELEGRAM_CHAT_IDS = ["fallback"]
    config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY = True
    config.EVENT_ALPHA_NOTIFY_SCOPE = "global"
    config.EVENT_ALPHA_EXPLORATORY_DIGEST_ENABLED = False
    config.EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED = False
    try:
        cfg = event_alerts.EventAlertConfig(enabled=True)
        result = scanner._send_event_alpha_routed_digest([], cfg)
        assert result.requested is True
        assert result.attempted is False
        assert result.success is False
        assert result.block_reason == "no router-approved escalations"
        assert sent == []

        suppressed = event_alpha_router.EventAlphaRouteDecision(
            entry=entry("DUP", alertable=False),
            route=event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE,
            alertable=False,
            reason="duplicate",
        )
        result = scanner._send_event_alpha_routed_digest([suppressed], cfg)
        assert result.attempted is False
        assert result.block_reason == "no router-approved escalations"
        assert sent == []

        high = event_alpha_router.EventAlphaRouteDecision(
            entry=entry("HIGH"),
            route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
            alertable=True,
            reason="watchlist escalation",
        )
        result = scanner._send_event_alpha_routed_digest([suppressed, high], cfg)
        assert result.attempted is True
        assert result.success is True
        assert result.items_attempted == 1
        assert result.items_delivered == 1
        assert len(sent) == 1
        assert sent[0][1] == "HTML"
        assert sent[0][2] == ("chat",)
        assert "Event Alpha High-Priority Research" in sent[0][0]
        assert "high-priority research" in sent[0][0]
        assert "HIGH" in sent[0][0]
        assert "DUP" not in sent[0][0]
        assert any(
            key.startswith("event_alpha_sent_count_instant_") and value == "1"
            for key, value in FakeStorage.meta.items()
        )

        FakeStorage.meta = {}
        scanner.send_telegram = lambda message, *, parse_mode=None, chat_ids=None: False
        scanner.send_telegram_structured = lambda message, *, parse_mode=None, chat_ids=None: False
        failed = scanner._send_event_alpha_routed_digest([high], cfg)
        assert failed.attempted is True
        assert failed.success is False
        assert failed.items_attempted == 1
        assert failed.items_delivered == 0
        assert "no channel delivered" in failed.block_reason
        disabled = scanner._send_event_alpha_routed_digest([high], event_alerts.EventAlertConfig(enabled=False))
        assert disabled.requested is True
        assert disabled.attempted is False
        assert disabled.block_reason == "event alerts disabled"
    finally:
        scanner.Storage = original_storage
        scanner.send_telegram = original_send
        scanner.send_telegram_structured = original_structured_send
        config.TELEGRAM_CHAT_IDS = original_ids
        for name, value in original_notification_flags.items():
            setattr(config, name, value)
