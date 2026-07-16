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


def _write_exact_reviewed_priors(path, alert):
    """Write the strict v2 artifact used by positive prior/replay tests."""
    import crypto_rsi_scanner.event_alpha.outcomes.calibration as calibration
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    core_rows = []
    feedback_rows = []
    for index in range(2):
        core_id = f"core-prior-{index}"
        core_rows.append({
            "schema_id": "core_opportunity_v1",
            "schema_version": "event_core_opportunity_store_v1",
            "row_type": "event_core_opportunity",
            "run_id": "run-prior-replay",
            "profile": "fixture",
            "artifact_namespace": "prior_replay",
            "core_opportunity_id": core_id,
            "feedback_target": core_id,
            "feedback_target_type": "core_opportunity_id",
            "generated_at": "2026-06-18T00:00:00+00:00",
            "research_only": True,
            "symbol": alert.symbol,
            "coin_id": alert.coin_id,
            "opportunity_type": "UNCONFIRMED_RESEARCH",
            "source_provider": alert.discovery_candidate.event.source,
            "source_provider_domain": "fixture.example",
            "source_domain": "fixture.example",
            "source_pack": "fixture-pack",
            "source_class": "fixture",
            "lane": "research",
            "playbook_type": alert.effective_playbook_type,
            "effective_playbook_type": alert.effective_playbook_type,
            "impact_path_type": "fixture",
            "opportunity_level": "watchlist",
            "final_opportunity_level": "watchlist",
            "final_route_after_quality_gate": alert.tier.value,
            "thesis_origin": "catalyst_led",
            "directional_bias": "long",
            "catalyst_status": "confirmed",
            "confidence_band": "exploratory",
            "timing_state": "early",
            "tradability_status": "acceptable",
            "radar_route": "diagnostic",
            "actionability_score_cohort": "70_79",
            "anomaly_type": "none",
        })
        feedback = {
            "run_id": "run-prior-replay",
            "profile": "fixture",
            "artifact_namespace": "prior_replay",
            "core_opportunity_id": core_id,
            "feedback_id": f"feedback-prior-{index}",
            "feedback_target_type": "core_opportunity_id",
            "feedback_target": core_id,
            "target": core_id,
            "label": "useful",
            "marked_at": "2026-06-18T01:00:00+00:00",
            "marked_by": "human-reviewer",
            "source": "manual_cli",
            "research_only": True,
            "notes": "reviewed fixture",
        }
        feedback.update(firewall.build_feedback_eligibility_fields(feedback))
        feedback_rows.append(feedback)
    payload = calibration.build_calibration_priors(
        [],
        feedback_rows=feedback_rows,
        core_rows=core_rows,
        generated_at=datetime(2026, 6, 18, 2, 0, tzinfo=timezone.utc),
        now=datetime(2026, 6, 18, 2, 0, tzinfo=timezone.utc),
        min_sample=2,
    )
    assert payload["eligible_for_auto_apply"] is True
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return payload


def test_event_alpha_feedback_marks_watchlist_rows_and_missed_items():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_labels as event_feedback
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="feed|solana|proxy_attention|SpaceX|",
        cluster_id="spacex|ipo_proxy|2026-06-18",
        event_id="feed",
        coin_id="solana",
        symbol="SOL",
        relationship_type="proxy_attention",
        external_asset="SpaceX",
        event_time=None,
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        previous_state="RADAR",
        first_seen_at="2026-06-18T12:00:00+00:00",
        last_seen_at="2026-06-18T13:00:00+00:00",
        source_count=2,
        highest_score=74,
        latest_score=74,
        latest_tier="WATCHLIST",
        latest_event_name="SOL proxy attention",
        latest_source="fixture",
        latest_playbook_type=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        latest_playbook_score=74,
        latest_playbook_action="watchlist",
        should_alert=True,
    )
    with tempfile.TemporaryDirectory() as tmp:
        cfg = event_feedback.EventFeedbackConfig(path=Path(tmp) / "feedback.jsonl")
        marked = event_feedback.mark_feedback(
            "SOL",
            "useful",
            watchlist_entries=[entry],
            cfg=cfg,
            marked_by="tester",
            notes="good lead",
            now=datetime(2026, 6, 18, 14, 0, tzinfo=timezone.utc),
        )
        assert marked.label == event_feedback.EventFeedbackLabel.USEFUL.value
        assert marked.key == entry.key
        assert marked.state == event_watchlist.EventWatchlistState.WATCHLIST.value
        assert "No live signal" in event_feedback.format_feedback_record(marked, path=cfg.path)
        by_alert_id = event_feedback.mark_feedback(
            f"ea:{entry.key}",
            "watch",
            watchlist_entries=[entry],
            cfg=cfg,
            marked_by="tester",
        )
        assert by_alert_id.key == entry.key

        try:
            event_feedback.mark_feedback("UNKNOWN", "junk", watchlist_entries=[entry], cfg=cfg)
        except ValueError as exc:
            assert "label=missed" in str(exc)
        else:
            raise AssertionError("expected unmatched non-missed feedback to fail")

        missed = event_feedback.mark_feedback(
            "missed velvet article",
            "missed",
            watchlist_entries=[entry],
            cfg=cfg,
            marked_by="tester",
        )
        assert missed.key is None
        assert missed.label == event_feedback.EventFeedbackLabel.MISSED.value
        loaded = event_feedback.load_feedback(cfg.path)
        assert loaded.rows_read == 3
        report = event_feedback.format_feedback_report(loaded)
        assert "useful=1" in report
        assert "watch=1" in report
        assert "missed=1" in report


def test_feedback_loader_keeps_non_research_and_legacy_rows_readable_but_ineligible(tmp_path):
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_labels as event_feedback

    base = {
        "row_type": "event_alpha_feedback",
        "schema_version": event_feedback.FEEDBACK_SCHEMA_VERSION,
        "label": "watch",
        "marked_at": "2026-07-12T00:00:00+00:00",
        "marked_by": "tester",
    }
    path = tmp_path / "feedback.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(row, sort_keys=True)
            for row in (
                {**base, "feedback_id": "legacy", "target": "legacy"},
                {
                    **base,
                    "feedback_id": "unsafe",
                    "target": "unsafe",
                    "research_only": False,
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = event_feedback.load_feedback(path)

    assert loaded.rows_read == 2
    by_target = {record.target: record for record in loaded.records}
    assert by_target["legacy"].research_only is None
    assert by_target["legacy"].calibration_eligible is None
    assert by_target["unsafe"].research_only is False
    assert by_target["unsafe"].calibration_eligible is None


def test_event_alpha_missed_calibration_and_research_card_reports():
    import crypto_rsi_scanner.event_alpha.outcomes.calibration as event_alpha_calibration
    import crypto_rsi_scanner.event_alpha.radar.missed as event_alpha_missed
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from pathlib import Path

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="cup|chiliz|fan_sports_event",
        cluster_id="cup|sports|2026-06-20",
        event_id="chz-event",
        coin_id="chiliz",
        symbol="CHZ",
        relationship_type="proxy_attention",
        external_asset="World Cup",
        event_time="2026-06-20T18:00:00+00:00",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        previous_state="WATCHLIST",
        first_seen_at="2026-06-18T10:00:00+00:00",
        last_seen_at="2026-06-18T12:00:00+00:00",
        source_count=3,
        highest_score=86,
        latest_score=86,
        latest_tier="HIGH_PRIORITY_WATCH",
        latest_event_name="CHZ World Cup fan token surge",
        latest_source="fixture",
        latest_playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
        latest_rule_playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
        latest_effective_playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
        latest_playbook_score=86,
        latest_playbook_action="high_priority_watch",
        latest_llm_asset_role="proxy_instrument",
        latest_llm_confidence=0.88,
        latest_score_components={"cluster_confidence": 78, "derivatives_crowding": 20},
        latest_market_snapshot={"price": 0.21, "return_24h": 0.18},
        alert_history=[{"observed_at": "2026-06-18T12:00:00+00:00", "state": "HIGH_PRIORITY", "tier": "HIGH_PRIORITY_WATCH", "score": 86}],
        should_alert=True,
    )
    alerts = [{
        "alert_key": entry.key,
        "asset_symbol": "CHZ",
        "asset_coin_id": "chiliz",
        "event_name": entry.latest_event_name,
        "tier": "HIGH_PRIORITY_WATCH",
        "playbook_type": entry.latest_playbook_type,
        "source": "fixture",
        "feedback_label": "useful",
        "primary_horizon_return": 0.12,
        "mfe_mae_ratio": 1.8,
        "direction_hit": True,
        "volatility_hit": True,
        "llm_asset_role": "proxy_instrument",
        "score_components": {"cluster_confidence": 78},
    }]
    missed = event_alpha_missed.detect_missed_opportunities(
        [
            {
                "id": "new-pump",
                "symbol": "pump",
                "name": "New Pump",
                "current_price": 2.0,
                "price_change_percentage_24h_in_currency": 150,
                "total_volume": 10000000,
                "market_cap": 20000000,
            },
            {
                "id": "chiliz",
                "symbol": "chz",
                "name": "Chiliz",
                "current_price": 0.21,
                "price_change_percentage_24h_in_currency": 150,
            },
        ],
        alert_rows=alerts,
        watchlist_entries=[entry],
    )
    assert [row.symbol for row in missed.rows] == ["PUMP"]
    assert missed.rows[0].failure_stage == "no_source_event"
    assert "PUMP crypto catalyst" in missed.rows[0].suggested_queries
    missed_report = event_alpha_missed.format_missed_report(missed)
    assert "missed=1" in missed_report

    url_only_raw = RawDiscoveredEvent(
        raw_id="url-only",
        provider="gdelt",
        fetched_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        published_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        source_url="https://search.example.test/?q=PUMPUSDT",
        title="Market update",
        body="No asset identity in the source text.",
        raw_json={},
        source_confidence=0.60,
        content_hash="url-only",
    )
    url_only = event_alpha_missed.detect_missed_opportunities(
        [{
            "id": "new-pump",
            "symbol": "pump",
            "name": "New Pump",
            "price_change_percentage_24h_in_currency": 150,
        }],
        raw_events=[url_only_raw],
    )
    assert url_only.rows[0].failure_stage == "no_source_event"
    assert "weak_url_only_identity_hint" in url_only.rows[0].reason

    body_raw = RawDiscoveredEvent(
        raw_id="body-identity",
        provider="gdelt",
        fetched_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        published_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        source_url="https://example.test/article",
        title="PUMPUSDT doubles before listing rumors",
        body="PUMPUSDT volume spiked after a catalyst rumor.",
        raw_json={},
        source_confidence=0.80,
        content_hash="body-identity",
    )
    body_identity = event_alpha_missed.detect_missed_opportunities(
        [{
            "id": "new-pump",
            "symbol": "pump",
            "name": "New Pump",
            "price_change_percentage_24h_in_currency": 150,
        }],
        raw_events=[body_raw],
    )
    assert body_identity.rows[0].failure_stage == "resolver_missed_asset"

    metadata_raw = RawDiscoveredEvent(
        raw_id="metadata-bitcoin",
        provider="Bitcoin World",
        fetched_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        published_at=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
        source_url="https://example.test/market",
        title="SpaceX market opens",
        body="The article is about an external catalyst, not the asset.",
        raw_json={"publisher": "Bitcoin World"},
        source_confidence=0.70,
        content_hash="metadata-bitcoin",
    )
    metadata_only = event_alpha_missed.detect_missed_opportunities(
        [{
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "price_change_percentage_24h_in_currency": 150,
        }],
        raw_events=[metadata_raw],
    )
    assert metadata_only.rows[0].failure_stage == "no_source_event"
    assert "metadata_only_identity_hint" in metadata_only.rows[0].reason

    manual_missing_source = event_alpha_missed.build_manual_missed_opportunity(
        symbol="VELVET",
        coin_id="velvet",
        event_description="SpaceX pre-IPO proxy venue moved before catalyst",
        source_url="https://example.test/velvet-spacex",
        why_it_mattered="large move with proxy catalyst",
        approximate_time="2026-06-18T12:00:00Z",
        expected_playbook="proxy_attention",
    )
    assert manual_missing_source.failure_stage == "source_not_ingested"
    assert manual_missing_source.feedback_target.startswith("missed:velvet")
    assert "VELVET crypto catalyst" in manual_missing_source.suggested_queries

    manual_quality_blocked = event_alpha_missed.build_manual_missed_opportunity(
        symbol="MEME",
        coin_id="memecore",
        event_description="MemeCore moved but stayed local",
        source_text="MemeCore volume surged after a vague catalyst.",
        core_rows=[{
            "core_opportunity_id": "core_memecore",
            "symbol": "MEME",
            "coin_id": "memecore",
            "incident_id": "incident:meme",
            "opportunity_level": "local_only",
            "final_route_after_quality_gate": "STORE_ONLY",
        }],
    )
    assert manual_quality_blocked.failure_stage == "quality_gate_too_strict"
    assert manual_quality_blocked.linked_core_opportunity_id == "core_memecore"

    calibration = event_alpha_calibration.format_calibration_report(
        alerts,
        feedback_rows=[{"key": entry.key, "label": "useful"}],
        missed_rows=[row.__dict__ for row in [*missed.rows, manual_missing_source, manual_quality_blocked]],
    )
    assert "feedback_supplied=1" in calibration
    assert "feedback_eligible=0" in calibration
    assert "feedback_excluded=1" in calibration
    assert "legacy_feedback_contract=1" in calibration
    assert "missed opportunities by failure stage" in calibration
    assert "source_not_ingested=1" in calibration
    assert "quality_gate_too_strict=1" in calibration
    assert "recommendations:" in calibration

    routed = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        alertable=True,
        reason="watchlist escalation",
    )
    cluster = event_graph.EventCluster(
        schema_version=event_graph.EVENT_GRAPH_SCHEMA_VERSION,
        cluster_id=entry.cluster_id,
        external_asset_slug="world-cup",
        event_type="sports_event",
        event_date_bucket="2026-06-20",
        external_asset="World Cup",
        event_time=pd.Timestamp("2026-06-20T18:00:00Z").to_pydatetime(),
        event_ids=("chz-event", "btc-noise"),
        raw_ids=("raw-chz", "raw-btc"),
        source_urls=("https://sports.example.test/chz", "https://bitcoinworld.example.test/noise"),
        source_count=2,
        independent_source_count=2,
        source_quality_score=80,
        event_time_consensus=90,
        accepted_asset_count=1,
        rejected_asset_count=1,
        cluster_confidence=78,
        evidence=(
            event_graph.ClusterEvidence(
                event_id="chz-event",
                raw_ids=("raw-chz",),
                source_urls=("https://sports.example.test/chz",),
                event_name="CHZ World Cup fan token surge",
                source="sports_fixture",
                first_seen_time=pd.Timestamp("2026-06-18T12:00:00Z").to_pydatetime(),
                confidence=0.90,
            ),
        ),
        asset_links=(
            event_graph.EventClusterAssetLink(
                cluster_id=entry.cluster_id,
                event_id="chz-event",
                coin_id="chiliz",
                symbol="CHZ",
                playbook_type=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
                relationship_type="proxy_attention",
                asset_role="proxy_instrument",
                accepted=True,
                link_confidence=0.90,
                classifier_confidence=0.90,
                accepted_kind="proxy",
                accepted_for_playbook=event_playbooks.EventPlaybookType.FAN_SPORTS_EVENT.value,
            ),
            event_graph.EventClusterAssetLink(
                cluster_id=entry.cluster_id,
                event_id="btc-noise",
                coin_id="bitcoin",
                symbol="BTC",
                playbook_type=event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value,
                relationship_type="publisher_suffix_false_positive",
                asset_role="source_noise",
                accepted=False,
                link_confidence=0.20,
                classifier_confidence=0.90,
                rejected_reason="publisher/source noise",
            ),
        ),
        warnings=("single source should be reviewed",),
    )
    card = event_research_cards.render_research_card(
        "CHZ",
        watchlist_entries=[entry],
        alert_rows=alerts,
        route_decisions=[routed],
        clusters=[cluster],
    )
    assert card.found is True
    assert "CHZ Event Research Card" in card.markdown
    assert "Evidence Verdict" in card.markdown
    assert "Cluster Context" in card.markdown
    assert "Accepted links by kind: proxy=CHZ/chiliz" in card.markdown
    assert "Rejected/noise links: BTC/bitcoin:publisher/source noise" in card.markdown
    assert "World Cup" in card.markdown
    assert ".env" not in card.markdown
    card_by_alert_id = event_research_cards.render_research_card(
        routed.alert_id,
        watchlist_entries=[entry],
        alert_rows=alerts,
        route_decisions=[routed],
        clusters=[cluster],
    )
    assert card_by_alert_id.found is True
    card_dir = __import__("pathlib").Path(__import__("tempfile").mkdtemp())
    stale_card = card_dir / "card_stale.md"
    stale_card.write_text("stale absolute path /Users/example/card_stale.md", encoding="utf-8")
    written_cards = event_research_cards.write_research_cards(
        card_dir,
        watchlist_entries=[entry],
        alert_rows=alerts,
        route_decisions=[routed],
        selected_tiers=("HIGH_PRIORITY_WATCH",),
    )
    assert any(routed.card_id in str(path) for path in written_cards.card_paths)
    assert not stale_card.exists()


def test_event_alpha_eval_fixture_passes():
    import crypto_rsi_scanner.event_alpha.outcomes.eval as event_alpha_eval

    path = "fixtures/event_discovery/event_alpha_golden_cases.json"
    result = event_alpha_eval.run_eval(path)
    assert result.passed == result.total
    assert result.failures == ()
    assert "PASS" in event_alpha_eval.format_eval_result(result, path)


def test_event_fade_validation_outcome_fill_from_local_prices():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    prices = event_validation.load_outcome_price_fixture(_outcome_prices_fixture_path())
    result = event_validation.fill_validation_outcomes(rows, prices)
    assert result.sample_rows == len(rows)
    assert result.triggered_rows == 1
    assert result.filled_rows == 1
    assert result.missing_history_rows == 0
    assert result.insufficient_history_rows == 0
    assert result.skipped_existing_rows == 0

    velvet = next(row for row in result.rows if row["asset_symbol"] == "TESTVELVET")
    assert round(velvet["max_favorable_excursion"], 4) == 0.3333
    assert round(velvet["max_adverse_excursion"], 4) == 0.0833
    assert round(velvet["post_event_return_24h"], 4) == -0.1111
    assert round(velvet["post_event_return_72h"], 4) == -0.2083
    assert round(velvet["post_event_return_7d"], 4) == -0.2778
    assert round(velvet["event_time_entry_price"], 4) == 8.0
    assert round(velvet["event_time_post_event_return_24h"], 4) == -0.1
    assert round(velvet["event_time_post_event_return_72h"], 4) == -0.2
    assert round(velvet["event_time_post_event_return_7d"], 4) == -0.2875

    velvet["human_label"] = "valid_proxy_fade"
    velvet["review_status"] = "reviewed"
    _stamp_review_provenance(velvet)
    queue = event_validation.build_labeling_queue(result.rows)
    assert not any(item.asset_symbol == "TESTVELVET" for item in queue.items)

    second = event_validation.fill_validation_outcomes(result.rows, prices)
    assert second.filled_rows == 0
    assert second.skipped_existing_rows == 1


def test_event_fade_outcome_price_export_from_klines_fixture():
    import json
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.price_history as event_price_history
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "prices.json"
        result = event_price_history.export_outcome_price_fixture(
            rows,
            out_path,
            days=30,
            fixture_dir=_outcome_klines_fixture_dir(),
        )
        assert result.assets_requested == 1
        assert result.assets_written == 1
        assert result.price_rows_written == 5
        assert result.missing_assets == ()
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == event_price_history.PRICE_FIXTURE_SCHEMA_VERSION
        assert payload["source"].startswith("fixture:")
        assert len(payload["prices"]) == 5
        assert payload["prices"][0]["asset_coin_id"] == "testvelvet"
        assert payload["prices"][2]["high"] == 7.8

        prices = event_validation.load_outcome_price_fixture(out_path)
        filled = event_validation.fill_validation_outcomes(rows, prices)
        velvet = next(row for row in filled.rows if row["asset_symbol"] == "TESTVELVET")
        assert round(velvet["max_adverse_excursion"], 4) == 0.0833
        assert round(velvet["post_event_return_7d"], 4) == -0.2778
        assert round(velvet["event_time_post_event_return_72h"], 4) == -0.2


def test_event_fade_validation_labeling_queue_prioritizes_missing_review_work():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    queue = event_validation.build_labeling_queue(rows, limit=10)
    assert queue.total_rows == len(rows)
    assert queue.needed_rows == len(rows)
    assert queue.shown_rows == 10

    first = queue.items[0]
    assert first.asset_symbol == "TESTVELVET"
    assert first.category == "label_triggered_candidate"
    assert first.event_time_source == "explicit"
    assert first.event_time_confidence == 1.0
    assert first.suggested_label == "valid_proxy_fade or false_positive"
    assert first.missing_fields == (
        "human_label",
        "max_adverse_excursion",
        "max_favorable_excursion",
        "post_event_return_72h",
        "event_time_post_event_return_72h",
    )

    assert any(item.category == "label_proxy_candidate" for item in queue.items)
    assert any(item.category == "label_negative_control" for item in queue.items)

    report = event_validation.format_labeling_queue(queue)
    assert "EVENT FADE VALIDATION LABELING QUEUE" in report
    assert "needing labels/status/outcomes: 17" in report
    assert "label_triggered_candidate" in report
    assert "TESTVELVET" in report
    assert "source: explicit" in report
    assert "confidence: 100.0%" in report
    assert "valid_proxy_fade or false_positive" in report


def test_event_fade_validation_labeling_queue_flags_reviewed_trigger_outcomes():
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    triggered = next(row for row in rows if row["asset_symbol"] == "TESTVELVET")
    triggered["human_label"] = "valid_proxy_fade"
    triggered["review_status"] = "reviewed"
    _stamp_review_provenance(triggered)
    queue = event_validation.build_labeling_queue(rows)
    item = next(item for item in queue.items if item.asset_symbol == "TESTVELVET")
    assert item.category == "fill_trigger_outcomes"
    assert item.missing_fields == (
        "max_adverse_excursion",
        "max_favorable_excursion",
        "post_event_return_72h",
        "event_time_post_event_return_72h",
    )


def test_event_fade_review_bundle_scanner_merges_prior_reviewed_sample():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    reviewed_row = next(row for row in reviewed if row["asset_symbol"] == "TESTVELVET")
    reviewed_row["review_status"] = "reviewed"
    _stamp_review_provenance(reviewed_row)
    reviewed_row["human_label"] = "valid_proxy_fade"
    reviewed_row["human_notes"] = "Reviewed prior bundle evidence."
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        reviewed_path = Path(tmp) / "reviewed.jsonl"
        bundle_dir = Path(tmp) / "review_bundle"
        event_discovery.write_validation_sample(rows, sample_path)
        event_discovery.write_validation_sample(reviewed, reviewed_path)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_review_bundle(
                str(sample_path),
                str(bundle_dir),
                limit=1,
                prices_path=str(_outcome_prices_fixture_path()),
                reviewed_path=str(reviewed_path),
                event_now="2026-06-15T16:00:00Z",
            )
        text = out.getvalue()
        assert "Review merge: 1 matched row(s)" in text
        assert "0 evidence-changed row(s)" in text
        assert "needing_review=16" in text

        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["review_merge"]["enabled"] is True
        assert manifest["review_merge"]["reviewed_path"] == str(reviewed_path)
        assert manifest["review_merge"]["matched_rows"] == 1
        assert manifest["review_merge"]["copied_fields"] == 5
        assert manifest["queue"]["needed_rows"] == 16

        readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
        assert "Prior reviewed sample" in readme

        copied_rows = [
            json.loads(line)
            for line in (bundle_dir / "validation_sample.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        copied_velvet = next(row for row in copied_rows if row["asset_symbol"] == "TESTVELVET")
        assert copied_velvet["reviewed_by"] == "human"
        assert copied_velvet["reviewed_at"] == "2026-06-17T12:00:00+00:00"
        assert copied_velvet["human_label"] == "valid_proxy_fade"
        assert copied_velvet["human_notes"] == "Reviewed prior bundle evidence."

        filled_rows = [
            json.loads(line)
            for line in (bundle_dir / "validation_sample_with_outcomes.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
        ]
        filled_velvet = next(row for row in filled_rows if row["asset_symbol"] == "TESTVELVET")
        assert filled_velvet["human_label"] == "valid_proxy_fade"
        assert round(filled_velvet["post_event_return_72h"], 4) == -0.2083


def test_event_fade_fill_outcomes_scanner_writes_outcome_jsonl():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        out_path = Path(tmp) / "with_outcomes.jsonl"
        event_discovery.write_validation_sample(rows, sample_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_fill_outcomes(
                str(sample_path),
                str(_outcome_prices_fixture_path()),
                str(out_path),
            )
        text = out.getvalue()
        assert "Event-fade validation outcome fill" in text
        assert "1/1 triggered row(s) filled" in text

        written = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
        velvet = next(row for row in written if row["asset_symbol"] == "TESTVELVET")
        assert round(velvet["post_event_return_72h"], 4) == -0.2083
        assert round(velvet["max_favorable_excursion"], 4) == 0.3333


def test_event_fade_export_outcome_prices_scanner_writes_price_fixture():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        sample_path = Path(tmp) / "sample.jsonl"
        out_path = Path(tmp) / "prices.json"
        event_discovery.write_validation_sample(rows, sample_path)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_fade_export_outcome_prices(
                str(sample_path),
                str(out_path),
                days=30,
                fixture_dir=str(_outcome_klines_fixture_dir()),
            )
        text = out.getvalue()
        assert "Event-fade outcome price export" in text
        assert "assets=1/1" in text
        assert "price_rows=5" in text
        assert "interval=1d" in text
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["interval"] == "1d"
        assert payload["source"].endswith(":1d")
        assert payload["prices"][0]["asset_symbol"] == "TESTVELVET"
        assert payload["prices"][0]["interval"] == "1d"


def test_event_fade_outcome_price_export_supports_1h_fixture_and_metadata():
    import json
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    import crypto_rsi_scanner.event_alpha.radar.price_history as event_price_history
    import crypto_rsi_scanner.event_alpha.radar.validation as event_validation

    rows = event_discovery.event_fade_validation_sample_rows(_full_event_discovery_fixture_result())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fixture_dir = root / "klines"
        fixture_dir.mkdir()
        (fixture_dir / "TESTVELVETUSDT.csv").write_text(
            "\n".join([
                "date,high,low,close,volume,quote_volume",
                "2026-06-15 13:30:00+00:00,8.2,7.9,8.0,1000,8000",
                "2026-06-16 12:00:00+00:00,7.3,7.1,7.2,1000,7200",
                "2026-06-16 13:00:00+00:00,7.5,6.6,6.8,1200,8160",
                "2026-06-17 12:00:00+00:00,6.9,5.9,6.2,1200,7440",
                "2026-06-19 12:00:00+00:00,6.4,5.5,5.8,1100,6380",
                "2026-06-23 12:00:00+00:00,6.0,4.9,5.1,900,4590",
            ]) + "\n",
            encoding="utf-8",
        )
        prices_path = root / "prices-1h.json"
        result = event_price_history.export_outcome_price_fixture(
            rows,
            prices_path,
            days=30,
            fixture_dir=root,
            interval="1h",
            now=None,
        )
        assert result.interval == "1h"
        assert result.source.endswith(":1h")
        assert result.price_rows_written == 6

        payload = json.loads(prices_path.read_text(encoding="utf-8"))
        assert payload["interval"] == "1h"
        assert payload["prices"][0]["interval"] == "1h"

        filled = event_validation.fill_validation_outcomes(
            rows,
            event_validation.load_outcome_price_fixture(prices_path),
        )
        velvet = next(row for row in filled.rows if row["asset_symbol"] == "TESTVELVET")
        assert velvet["outcome_price_interval"] == "1h"
        assert velvet["outcome_price_source"].endswith(":1h")
        assert round(velvet["max_adverse_excursion"], 4) == 0.0417
        assert round(velvet["max_favorable_excursion"], 4) == 0.3194
        assert round(velvet["post_event_return_72h"], 4) == -0.1944

        packet = event_validation.format_review_packet([velvet], limit=1)
        assert "prices=`1h/fixture:" in packet


def test_event_alpha_missed_uses_shared_identity_for_common_words():
    from datetime import datetime, timezone

    import crypto_rsi_scanner.event_alpha.radar.missed as event_alpha_missed
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    raw = RawDiscoveredEvent(
        raw_id="raw-hype",
        provider="news",
        fetched_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        source_url="https://example.com/ipo-hype",
        title="IPO hype keeps building before the event",
        body="No token mention appears here.",
        raw_json={},
        source_confidence=0.7,
        content_hash="h",
    )
    market = [{"id": "hyperliquid", "symbol": "hype", "name": "Hyperliquid", "price_change_percentage_24h_in_currency": 180}]
    result = event_alpha_missed.detect_missed_opportunities(market, raw_events=[raw])
    assert result.rows
    assert result.rows[0].failure_stage == "no_source_event"


def test_event_alpha_calibration_priors_export():
    import tempfile
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.outcomes.calibration as event_alpha_calibration

    alerts = [
        {"alert_key": "a", "playbook_type": "proxy_attention", "source": "rss", "tier": "WATCHLIST", "primary_horizon_return": 0.1},
        {"alert_key": "b", "playbook_type": "proxy_attention", "source": "rss", "tier": "WATCHLIST", "primary_horizon_return": 0.2},
    ]
    feedback = [{"key": "a", "label": "useful"}, {"key": "b", "label": "useful"}]
    out = Path(tempfile.mkdtemp()) / "priors.json"
    payload = event_alpha_calibration.write_calibration_priors(out, alerts, feedback_rows=feedback, min_sample=3)
    assert out.exists()
    assert payload["feedback_rows_supplied"] == 2
    assert payload["feedback_rows_eligible"] == 0
    assert payload["feedback_rows_excluded"] == 2
    assert payload["feedback_exclusion_reason_counts"]["legacy_feedback_contract"] == 2
    assert payload["playbook_priors"] == {}
    assert payload["eligible_for_auto_apply"] is False
    assert payload["auto_apply"] is False


def test_event_alpha_eval_export_from_feedback_and_missed():
    import json
    import tempfile
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.outcomes.feedback as event_alpha_eval_export

    out_dir = Path(tempfile.mkdtemp())
    feedback_result = event_alpha_eval_export.export_cases_from_feedback(
        [{"alert_key": "k1", "event_name": "Bitcoin World article", "asset_symbol": "BTC", "asset_coin_id": "bitcoin"}],
        [{"key": "k1", "label": "junk", "notes": "publisher noise"}],
        out_dir,
    )
    assert feedback_result.proposed_cases == 0
    assert feedback_result.feedback_rows_supplied == 1
    assert feedback_result.feedback_rows_eligible == 0
    assert feedback_result.feedback_rows_excluded == 1
    llm_cases = json.loads((out_dir / "proposed_llm_golden_cases.json").read_text())
    assert llm_cases["cases"] == []
    assert llm_cases["feedback_exclusion_reason_counts"]["legacy_feedback_contract"] == 1

    missed_result = event_alpha_eval_export.export_cases_from_missed(
        [{"symbol": "XYZ", "coin_id": "xyz", "name": "XYZ", "move_window": "24h", "return_pct": 1.5, "failure_stage": "resolver_missed_asset", "suggested_queries": ["XYZ catalyst"]}],
        out_dir,
    )
    assert missed_result.proposed_cases == 2
    extraction = json.loads((out_dir / "proposed_llm_extraction_golden_cases.json").read_text())
    assert extraction["cases"][0]["expected_crypto_asset_mentions"][0]["symbol"] == "XYZ"


def test_event_alpha_priors_reject_legacy_multiplier_payload():
    import json
    import tempfile
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.outcomes.priors as event_alpha_priors

    alerts = event_alerts.build_event_alert_candidates(
        _full_event_discovery_fixture_result(),
        cfg=event_alerts.EventAlertConfig(),
    )
    triggered = next(alert for alert in alerts if alert.tier == event_alerts.EventAlertTier.TRIGGERED_FADE)
    non_triggered = next(alert for alert in alerts if alert.tier != event_alerts.EventAlertTier.TRIGGERED_FADE)
    path = Path(tempfile.mkdtemp()) / "priors.json"
    path.write_text(json.dumps({
        "schema_version": "event_alpha_priors_v1",
        "generated_at": "2026-06-18T00:00:00+00:00",
        "playbook_priors": {
            triggered.effective_playbook_type: {"multiplier": 0.2},
            non_triggered.effective_playbook_type: {"multiplier": 1.3},
        },
    }), encoding="utf-8")
    adjusted = event_alpha_priors.apply_priors_to_alerts(
        [triggered, non_triggered],
        cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=True, path=path, min_multiplier=0.7, max_multiplier=1.3),
        alert_cfg=event_alerts.EventAlertConfig(),
    )
    adjusted_triggered = next(alert for alert in adjusted if alert.symbol == triggered.symbol)
    adjusted_other = next(alert for alert in adjusted if alert.symbol == non_triggered.symbol)
    assert adjusted_triggered == triggered
    assert adjusted_triggered.tier == event_alerts.EventAlertTier.TRIGGERED_FADE
    assert adjusted_triggered.score_after_priors is None
    assert adjusted_other == non_triggered
    assert adjusted_other.score_before_priors is None
    assert adjusted_other.score_after_priors is None
    assert adjusted_other.prior_file is None


def test_event_alpha_priors_shadow_report_and_raw_replay_are_local():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
    import crypto_rsi_scanner.event_alpha.outcomes.priors as event_alpha_priors
    import crypto_rsi_scanner.event_alpha.artifacts.replay as event_alpha_replay
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    result = _full_event_discovery_fixture_result()
    alerts = event_alerts.build_event_alert_candidates(result)
    non_triggered = next(
        alert
        for alert in alerts
        if alert.tier not in {
            event_alerts.EventAlertTier.TRIGGERED_FADE,
            event_alerts.EventAlertTier.STORE_ONLY,
        }
        and alert.opportunity_score < 95
    )
    tmp = Path(tempfile.mkdtemp())
    priors_path = tmp / "priors.json"
    _write_exact_reviewed_priors(priors_path, non_triggered)
    shadow = event_alpha_priors.compare_priors_shadow(
        alerts,
        cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=False, path=priors_path),
        alert_cfg=event_alerts.EventAlertConfig(),
    )
    assert shadow.rows
    text = event_alpha_priors.format_priors_shadow_report(shadow)
    assert "EVENT ALPHA PRIORS SHADOW REPORT" in text
    assert "No sends" in text

    _events_path, aliases_path = _event_discovery_fixture_paths()
    market_rows = event_alpha_replay.load_market_rows(_coingecko_universe_fixture_path())
    assets = event_discovery.load_discovery_assets(aliases_path, universe_path=_coingecko_universe_fixture_path())
    replay = event_alpha_replay.replay_from_raw_events(
        raw_events=result.raw_events,
        assets=assets,
        market_rows=market_rows,
        priors_cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=True, path=priors_path),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    assert replay.raw_events == len(result.raw_events)
    assert replay.candidates > 0
    replay_text = event_alpha_replay.format_replay_report(replay)
    assert "local artifacts only" in replay_text
    assert "No live providers" in replay_text
    comparison = event_alpha_replay.compare_replay_policies(
        raw_events=result.raw_events,
        assets=assets,
        market_rows=market_rows,
        policies=("baseline", "priors", "router_threshold_variant", "profile_variant"),
        priors_cfg=event_alpha_priors.EventAlphaPriorsConfig(enabled=True, path=priors_path),
        router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True, score_jump_threshold=20),
        profile_variant_router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True, score_jump_threshold=5),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    assert [row.policy for row in comparison.rows] == [
        "baseline",
        "priors",
        "router_threshold_variant",
        "profile_variant",
    ]
    assert comparison.diffs
    assert any(diff.policy == "priors" and diff.score_delta for diff in comparison.diffs)
    comparison_text = event_alpha_replay.format_replay_comparison_report(comparison)
    assert "EVENT ALPHA REPLAY POLICY COMPARISON" in comparison_text
    assert "candidate diffs:" in comparison_text
    assert "local-only" in comparison_text
    assert "router_threshold_variant" in comparison_text


def test_replay_comparison_quarantines_loose_historical_annotations():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.replay as event_alpha_replay
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery

    result = _full_event_discovery_fixture_result()
    _events_path, aliases_path = _event_discovery_fixture_paths()
    assets = event_discovery.load_discovery_assets(
        aliases_path,
        universe_path=_coingecko_universe_fixture_path(),
    )
    comparison = event_alpha_replay.compare_replay_policies(
        raw_events=result.raw_events,
        assets=assets,
        policies=("baseline", "router_threshold_variant"),
        feedback_rows=[{"alert_key": "forged", "label": "useful"}],
        outcome_rows=[{"watchlist_key": "forged", "primary_horizon_return": 9.0}],
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )

    assert event_alpha_replay._feedback_by_key(  # noqa: SLF001
        [{"alert_key": "forged", "label": "useful"}]
    ) == {}
    assert event_alpha_replay._outcome_by_key(  # noqa: SLF001
        [{"watchlist_key": "forged", "primary_horizon_return": 9.0}]
    ) == {}
    assert all(diff.feedback_label is None for diff in comparison.diffs)
    assert all(diff.primary_return is None for diff in comparison.diffs)
    assert any("exact canonical Core identity" in warning for warning in comparison.warnings)
