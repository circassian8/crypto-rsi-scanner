"""Focused Event Alpha incident semantics and relevance tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alpha_claim_semantics_incidents_roles_and_market_context():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
    import crypto_rsi_scanner.event_alpha.radar.incidents as event_incident_store
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
    from crypto_rsi_scanner.event_core.models import (
        DiscoveredAsset,
        DiscoveredEventFadeCandidate,
        EventAssetLink,
        EventClassification,
        EventDiscoveryResult,
        NormalizedEvent,
        RawDiscoveredEvent,
    )

    now = datetime(2026, 6, 26, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body, *, url, market=None):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture_news",
            fetched_at=now,
            published_at=now,
            source_url=url,
            title=title,
            body=body,
            raw_json={"market": market or {}},
            source_confidence=0.88,
            content_hash=raw_id,
        )

    def anomaly_raw(raw_id, symbol, coin_id, name, *, fetched_at=now, score=86):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="market_anomaly",
            fetched_at=fetched_at,
            published_at=fetched_at,
            source_url=None,
            title=f"{symbol} market anomaly: 24h return 64%",
            body=(
                f"{name} ({symbol}) matched market-anomaly research filters: 24h return 64%, "
                "volume/mcap 0.34. No dated external catalyst has been validated; "
                "keep as radar/store-only until source evidence exists."
            ),
            raw_json={
                "event": {
                    "event_id": f"market_anomaly:{coin_id}:{fetched_at.date().isoformat()}",
                    "event_name": f"{symbol} market anomaly",
                    "event_type": "market_anomaly",
                    "event_time": None,
                    "event_time_confidence": 0.0,
                    "external_asset": None,
                    "description": f"{symbol} market anomaly",
                },
                "market": {
                    "symbol": symbol,
                    "coin_id": coin_id,
                    "name": name,
                    "return_24h": 64,
                    "volume_to_market_cap": 0.34,
                    "volume_zscore_24h": 4.5,
                    "anomaly_score": score,
                },
                "anomaly": {"score": score, "research_only": True, "requires_catalyst_evidence": True},
            },
            source_confidence=0.55,
            content_hash=raw_id,
        )

    claims = event_claim_semantics.claims_from_text(
        "MemeCore's M token crashes 80% with no exploit or announcement to explain it. "
        "The exploit was initially suspected, later ruled out."
    )
    assert any(claim.polarity == "negated" for claim in claims)
    assert any(claim.polarity == "ruled_out" for claim in claims)
    assert event_claim_semantics.current_cause_status(claims, "exploit") == "ruled_out"

    absence_claims = event_claim_semantics.claims_from_text("No dated external catalyst has been validated.")
    assert all(claim.subject != "No" for claim in absence_claims)
    assert any(claim.claim_type == "absence_of_validated_catalyst" for claim in absence_claims)
    assert not any(
        claim.predicate == "explains_market_move" and claim.cause_status == "confirmed"
        for claim in absence_claims
    )
    no_trigger_claims = event_claim_semantics.claims_from_text("No clear trigger for token crash.")
    assert all(claim.subject != "No" for claim in no_trigger_claims)
    assert all(claim.cause_status == "unknown" for claim in no_trigger_claims)
    no_exploit_claims = event_claim_semantics.claims_from_text("No exploit or announcement to explain it.")
    assert event_claim_semantics.has_ruled_out_claim(no_exploit_claims, "exploit")
    assert not event_claim_semantics.has_confirmed_claim(no_exploit_claims, "exploit")

    memecore_raw = raw(
        "memecore",
        "MemeCore's M token crashes 80% with no exploit or announcement to explain it",
        "No exploit or announcement explains the M token selloff; cause unknown.",
        url="https://alpha.example/memecore",
        market={"symbol": "M", "coin_id": "memecore", "return_24h": -71, "volume_zscore_24h": 5.0},
    )
    memecore_event = NormalizedEvent(
        event_id="evt_memecore",
        raw_ids=("memecore",),
        event_name="MemeCore M token crash",
        event_type="news",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source="fixture_news",
        source_urls=("https://alpha.example/memecore",),
        external_asset="MemeCore",
        description=memecore_raw.title,
        confidence=0.86,
    )
    memecore_asset = DiscoveredAsset("memecore", "M", "MemeCore")
    memecore_link = EventAssetLink("evt_memecore", "memecore", "M", "MemeCore", 0.95, "fixture", ("MemeCore M token",))
    memecore_cls = EventClassification("evt_memecore", "memecore", False, True, "direct_token_event", 0.90, "fixture", "fixture", ("MemeCore M token",))
    memecore_candidate = DiscoveredEventFadeCandidate(memecore_event, memecore_asset, memecore_link, memecore_cls, None, None, {})
    memecore_hyp = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((memecore_raw,), (memecore_event,), (memecore_link,), (memecore_cls,), (memecore_candidate,)),
        taxonomy={},
        now=now,
    )[0]
    assert memecore_hyp.impact_category == "market_anomaly_unknown"
    assert memecore_hyp.event_archetype == "market_dislocation_unknown"
    assert memecore_hyp.impact_path_type == "market_dislocation_unknown"
    assert memecore_hyp.cause_status == "ruled_out"
    assert memecore_hyp.market_context_source == "candidate_event_market_snapshot"
    assert memecore_hyp.market_context_snapshot["return_24h"] == -71
    assert memecore_hyp.market_reaction_confirmed is True
    assert memecore_hyp.causal_mechanism_confirmed is False

    sol_a = anomaly_raw("sol_a", "SOL", "solana", "Solana")
    sol_b = anomaly_raw("sol_b", "SOL", "solana", "Solana")
    usdt = anomaly_raw("usdt_a", "USDT", "tether", "Tether")
    anomaly_events = (
        NormalizedEvent("evt_sol_a", ("sol_a",), "SOL market anomaly", "market_anomaly", None, 0.0, now, "market_anomaly", (), None, sol_a.body, 0.55),
        NormalizedEvent("evt_sol_b", ("sol_b",), "SOL market anomaly update", "market_anomaly", None, 0.0, now, "market_anomaly", (), None, sol_b.body, 0.55),
        NormalizedEvent("evt_usdt_a", ("usdt_a",), "USDT market anomaly", "market_anomaly", None, 0.0, now, "market_anomaly", (), None, usdt.body, 0.55),
    )
    anomaly_incidents = event_incident_graph.build_incidents(
        anomaly_events,
        {row.raw_id: row for row in (sol_a, sol_b, usdt)},
    )
    assert len(anomaly_incidents) == 2
    sol_incident = next(item for item in anomaly_incidents if item.primary_subject == "SOL")
    usdt_incident = next(item for item in anomaly_incidents if item.primary_subject == "USDT")
    assert set(sol_incident.raw_ids) == {"sol_a", "sol_b"}
    assert set(usdt_incident.raw_ids) == {"usdt_a"}
    assert sol_incident.canonical_name == "SOL market anomaly"
    assert usdt_incident.canonical_name == "USDT market anomaly"
    assert sol_incident.current_cause_status == "unknown"
    assert all(claim.subject != "No" for claim in sol_incident.claim_history)
    assert any(claim.claim_type == "absence_of_validated_catalyst" for claim in sol_incident.claim_history)
    assert any(
        asset.symbol == "SOL" and asset.coin_id == "solana" and asset.role == "direct_subject"
        for asset in sol_incident.linked_assets
    )
    assert any(
        asset.symbol == "USDT" and asset.coin_id == "tether" and asset.role == "direct_subject"
        for asset in usdt_incident.linked_assets
    )
    missing_market = RawDiscoveredEvent(
        raw_id="missing_market_asset",
        provider="market_anomaly",
        fetched_at=now,
        published_at=now,
        source_url=None,
        title="No clear trigger market anomaly",
        body="No clear trigger or validated catalyst has been found for this market anomaly.",
        raw_json={
            "event": {
                "event_id": "market_anomaly:missing:2026-06-26",
                "event_name": "No clear trigger market anomaly",
                "event_type": "market_anomaly",
                "event_time": None,
                "event_time_confidence": 0.0,
                "external_asset": None,
                "description": "No clear trigger market anomaly",
            },
            "market": {"anomaly_score": 78},
            "anomaly": {"score": 78, "research_only": True, "requires_catalyst_evidence": True},
        },
        source_confidence=0.50,
        content_hash="missing_market_asset",
    )
    missing_incident = event_incident_graph.build_incidents(
        (
            NormalizedEvent(
                "evt_missing_market",
                ("missing_market_asset",),
                "No clear trigger market anomaly",
                "market_anomaly",
                None,
                0.0,
                now,
                "market_anomaly",
                (),
                None,
                missing_market.body,
                0.50,
            ),
        ),
        {"missing_market_asset": missing_market},
    )[0]
    assert missing_incident.primary_subject not in {"No", "SECTOR"}
    assert "market_anomaly_missing_validated_asset" in missing_incident.warnings

    prose_fragment_raw = raw(
        "prose_fragment",
        "Actions Announcements However",
        "However, it notes only announcements and no token-specific incident details.",
        url="https://fragment.example/actions",
    )
    prose_fragment_event = NormalizedEvent(
        "evt_prose_fragment",
        ("prose_fragment",),
        "Actions Announcements However",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (prose_fragment_raw.source_url,),
        None,
        prose_fragment_raw.body,
        0.40,
    )
    prose_fragment_incident = event_incident_graph.build_incidents(
        (prose_fragment_event,),
        {"prose_fragment": prose_fragment_raw},
    )[0]
    assert prose_fragment_incident.primary_subject is None
    assert prose_fragment_incident.subject_quality == "invalid"
    assert prose_fragment_incident.diagnostic_only is True
    assert "incident_primary_subject_invalid" in prose_fragment_incident.warnings
    assert event_claim_semantics.infer_primary_subject("OpenAI This suffered outage reports.") == "OpenAI"
    invalid_subject_examples = (
        "About",
        "All",
        "During",
        "Here",
        "LLM",
        "Need",
        "Not",
        "When",
        "Where",
        "Will",
        "Yes",
        "Best Prediction Market Apps",
        "Bitcoin And MSTR Are",
        "Polymarket Invite Code SBWIRE",
        "Polymarket Referral Code SBWIRE",
    )
    for idx, title in enumerate(invalid_subject_examples):
        bad_raw = raw(
            f"bad_subject_{idx}",
            title,
            f"{title} is a page heading, source label, or SEO phrase with no validated event subject.",
            url=f"https://fragment.example/{idx}",
        )
        bad_event = NormalizedEvent(
            f"evt_bad_subject_{idx}",
            (bad_raw.raw_id,),
            title,
            "news",
            None,
            0.0,
            now,
            "fixture_news",
            (bad_raw.source_url,),
            None,
            bad_raw.body,
            0.35,
        )
        bad_incident = event_incident_graph.build_incidents((bad_event,), {bad_raw.raw_id: bad_raw})[0]
        assert bad_incident.primary_subject != title
        assert bad_incident.subject_quality == "invalid"
        assert bad_incident.diagnostic_only is True
    polymarket_wc_raw = raw(
        "polymarket_world_cup_volume",
        "Polymarket World Cup Volume",
        "Polymarket World Cup volume rises before a prediction-market fixture.",
        url="https://fragment.example/polymarket-world-cup-volume",
    )
    polymarket_wc_event = NormalizedEvent(
        "evt_polymarket_world_cup",
        ("polymarket_world_cup_volume",),
        "Polymarket World Cup Volume",
        "sports_event",
        None,
        0.0,
        now,
        "fixture_news",
        (),
        "World Cup",
        polymarket_wc_raw.body,
        0.72,
    )
    polymarket_wc_incident = event_incident_graph.build_incidents(
        (polymarket_wc_event,),
        {"polymarket_world_cup_volume": polymarket_wc_raw},
    )[0]
    assert polymarket_wc_incident.primary_subject == "World Cup"
    assert polymarket_wc_incident.diagnostic_only is False
    next_bond_raw = raw(
        "next_bond",
        "Next James Bond prediction market",
        "A prediction market asks who will be the Next James Bond.",
        url="https://fragment.example/next-james-bond",
    )
    next_bond_event = NormalizedEvent(
        "evt_next_bond",
        ("next_bond",),
        "Next James Bond prediction market",
        "prediction_market",
        None,
        0.0,
        now,
        "fixture_news",
        (),
        "Next James Bond",
        next_bond_raw.body,
        0.74,
    )
    next_bond_incident = event_incident_graph.build_incidents((next_bond_event,), {"next_bond": next_bond_raw})[0]
    assert next_bond_incident.primary_subject == "Next James Bond"
    for valid_subject in ("SpaceX", "OpenAI", "Anthropic", "THORChain", "SecondFi", "Solana"):
        valid_raw = raw(
            f"valid_{valid_subject.lower()}",
            f"{valid_subject} suffered outage reports",
            f"{valid_subject} is the named subject in a concrete incident source.",
            url=f"https://fragment.example/{valid_subject.lower()}",
        )
        valid_event = NormalizedEvent(
            f"evt_valid_{valid_subject.lower()}",
            (valid_raw.raw_id,),
            f"{valid_subject} incident",
            "news",
            None,
            0.0,
            now,
            "fixture_news",
            (),
            valid_subject,
            valid_raw.body,
            0.80,
        )
        valid_incident = event_incident_graph.build_incidents((valid_event,), {valid_raw.raw_id: valid_raw})[0]
        assert valid_incident.primary_subject == valid_subject
        assert valid_incident.subject_quality == "valid"
    with tempfile.TemporaryDirectory() as diag_tmp:
        diag_write = event_incident_store.write_incidents(
            EventDiscoveryResult((prose_fragment_raw,), (prose_fragment_event,), (), (), ()),
            hypotheses=[],
            watchlist_rows=[],
            cfg=event_incident_store.EventIncidentStoreConfig(path=Path(diag_tmp) / "diagnostic_incidents.jsonl"),
            now=now,
            run_id="run-diagnostic-incident",
            profile="fixture",
            run_mode="test",
            artifact_namespace="fixture",
        )
        diag_loaded = event_incident_store.load_incidents(diag_write.path)
        assert diag_loaded.rows[0]["diagnostic_only"] is True
        diag_report = event_incident_store.format_incidents_report(diag_loaded)
        assert "diagnostic_rows_hidden: 1" in diag_report
        assert "diagnostic_rows_available: 1" in diag_report
        assert "Actions Announcements However" not in diag_report
        diag_visible = event_incident_store.load_incidents(diag_write.path, include_diagnostic=True)
        diag_visible_report = event_incident_store.format_incidents_report(diag_visible)
        assert "diagnostic_rows_hidden: 0" in diag_visible_report
        assert "Unknown subject" in diag_visible_report
        diagnostic_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-diagnostic-incident", "profile": "fixture", "artifact_namespace": "fixture", "run_mode": "test"}],
            incident_rows=diag_loaded.rows,
            include_test_artifacts=True,
            strict=True,
        )
        assert diagnostic_doctor.status == "WARN"
        assert diagnostic_doctor.diagnostic_incident_rows == 1
        assert diagnostic_doctor.garbage_primary_subject_incidents == 0
        canonical_bad = dict(diag_loaded.rows[0])
        canonical_bad["diagnostic_only"] = False
        canonical_bad["incident_subject_quality"] = "invalid"
        canonical_bad["primary_subject"] = "About"
        canonical_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-diagnostic-incident", "profile": "fixture", "artifact_namespace": "fixture", "run_mode": "test"}],
            incident_rows=[canonical_bad],
            include_test_artifacts=True,
            strict=True,
        )
        assert canonical_doctor.status == "BLOCKED"
        assert canonical_doctor.invalid_canonical_incident_rows == 1
        assert canonical_doctor.garbage_primary_subject_incidents == 1

        import json

        stale_garbage_path = Path(diag_tmp) / "stale_garbage_incidents.jsonl"
        stale_garbage_row = {
            "schema_version": event_incident_store.INCIDENT_STORE_SCHEMA_VERSION,
            "row_type": "event_incident",
            "observed_at": now.isoformat(),
            "run_id": "run-stale-garbage",
            "profile": "fixture",
            "run_mode": "test",
            "artifact_namespace": "fixture",
            "incident_id": "incident:stale_garbage",
            "canonical_name": "LLM political event",
            "event_archetype": "political_event",
            "primary_subject": "LLM",
            "incident_subject_quality": "valid",
            "incident_subject_quality_reason": "legacy_artifact",
            "diagnostic_only": False,
            "linked_hypothesis_ids": [],
            "linked_watchlist_keys": [],
            "linked_assets": [],
            "current_cause_status": "unknown",
            "source_update_count": 1,
            "independent_source_count": 1,
            "incident_confidence": 63,
            "warnings": [],
        }
        stale_garbage_path.write_text(json.dumps(stale_garbage_row) + "\n", encoding="utf-8")
        stale_loaded = event_incident_store.load_incidents(stale_garbage_path)
        assert stale_loaded.rows[0]["diagnostic_only"] is True
        assert stale_loaded.rows[0]["incident_subject_quality"] == "diagnostic_only"
        stale_report = event_incident_store.format_incidents_report(stale_loaded)
        assert "diagnostic_rows_hidden: 1" in stale_report
        assert "LLM political event" not in stale_report
        stale_visible = event_incident_store.load_incidents(stale_garbage_path, include_diagnostic=True)
        stale_visible_report = event_incident_store.format_incidents_report(stale_visible)
        assert "diagnostic_rows_hidden: 0" in stale_visible_report
        assert "LLM political event" in stale_visible_report
        stale_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-stale-garbage", "profile": "fixture", "artifact_namespace": "fixture", "run_mode": "test"}],
            incident_rows=stale_loaded.rows,
            include_test_artifacts=True,
            strict=True,
        )
        assert stale_doctor.status == "WARN"
        assert stale_doctor.diagnostic_incident_rows == 1
        assert stale_doctor.garbage_primary_subject_incidents == 1
        assert stale_doctor.invalid_canonical_incident_rows == 0

    secondfi_a = raw(
        "secondfi_a",
        "SecondFi loses $2.4m in Cardano wallet exploit",
        "A third-party SecondFi wallet exploit in the Cardano ecosystem affected ADA sentiment.",
        url="https://source-a.example/secondfi",
        market={"symbol": "ADA", "coin_id": "cardano", "return_24h": -9, "volume_zscore_24h": 2.6},
    )
    secondfi_b = raw(
        "secondfi_b",
        "SecondFi traces Cardano wallet exploit to address-level issue",
        "SecondFi says the Cardano wallet exploit was address-level and did not compromise the Cardano protocol.",
        url="https://source-b.example/secondfi-update",
        market={"symbol": "ADA", "coin_id": "cardano", "return_24h": -11, "volume_zscore_24h": 3.0},
    )
    unrelated = raw(
        "cardano_vote",
        "Cardano governance vote opens",
        "ADA holders discuss a governance vote unrelated to the SecondFi exploit.",
        url="https://source-c.example/cardano-vote",
    )
    events = (
        NormalizedEvent("evt_secondfi_a", ("secondfi_a",), "SecondFi Cardano wallet exploit", "news", None, 0.0, now, "fixture_news", (secondfi_a.source_url,), "SecondFi", secondfi_a.title, 0.84),
        NormalizedEvent("evt_secondfi_b", ("secondfi_b",), "SecondFi Cardano wallet exploit update", "news", None, 0.0, now, "fixture_news", (secondfi_b.source_url,), "SecondFi", secondfi_b.title, 0.84),
        NormalizedEvent("evt_cardano_vote", ("cardano_vote",), "Cardano governance vote", "governance", None, 0.0, now, "fixture_news", (unrelated.source_url,), "Cardano", unrelated.title, 0.70),
    )
    raw_by_id = {row.raw_id: row for row in (secondfi_a, secondfi_b, unrelated)}
    incidents = event_incident_graph.build_incidents(events, raw_by_id)
    secondfi_incidents = [item for item in incidents if item.primary_subject == "SecondFi"]
    assert len(secondfi_incidents) == 1
    assert set(secondfi_incidents[0].raw_ids) == {"secondfi_a", "secondfi_b"}
    assert len(secondfi_incidents[0].independent_source_domains) == 2
    assert len(incidents) == 2

    ada = DiscoveredAsset("cardano", "ADA", "Cardano")
    links = tuple(EventAssetLink(event.event_id, "cardano", "ADA", "Cardano", 0.90, "fixture", ("ADA",)) for event in events[:2])
    classes = tuple(EventClassification(event.event_id, "cardano", False, False, "ecosystem_event", 0.85, "fixture", "fixture", ("ADA",)) for event in events[:2])
    candidates = tuple(DiscoveredEventFadeCandidate(event, ada, link, cls, None, None, {}) for event, link, cls in zip(events[:2], links, classes))
    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((secondfi_a, secondfi_b), events[:2], links, classes, candidates),
        taxonomy={},
        now=now,
    )
    assert len(hypotheses) == 1
    hyp = hypotheses[0]
    assert hyp.primary_subject == "SecondFi"
    assert hyp.affected_ecosystem == "Cardano"
    assert hyp.candidate_role == "ecosystem_affected_asset"
    assert hyp.impact_path_reason == "ecosystem_security_event"
    assert set(hyp.source_raw_ids) == {"secondfi_a", "secondfi_b"}
    assert "incident_evidence_update" in hyp.warnings
    assert len(hyp.independent_source_domains) == 2
    assert hyp.incident_id
    assert hyp.incident_canonical_name == hyp.canonical_incident_name
    assert hyp.incident_primary_subject == "SecondFi"
    assert hyp.incident_affected_ecosystem == "Cardano"
    assert hyp.incident_cause_status == hyp.cause_status
    assert hyp.incident_market_reaction_observed is True
    assert hyp.incident_causal_mechanism_confirmed is True

    thor_raw = raw(
        "thorchain",
        "THORChain confirms RUNE exploit after attack",
        "THORChain confirms a RUNE exploit and security incident after an attack; RUNE trading reacts sharply.",
        url="https://source-d.example/thorchain-rune-exploit",
        market={"symbol": "RUNE", "coin_id": "thorchain", "return_24h": -18, "volume_zscore_24h": 3.4},
    )
    thor_event = NormalizedEvent(
        "evt_thorchain",
        ("thorchain",),
        "THORChain RUNE exploit",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (thor_raw.source_url,),
        "THORChain",
        thor_raw.title,
        0.90,
    )
    rune = DiscoveredAsset("thorchain", "RUNE", "THORChain")
    thor_link = EventAssetLink("evt_thorchain", "thorchain", "RUNE", "THORChain", 0.95, "fixture", ("THORChain RUNE",))
    thor_cls = EventClassification("evt_thorchain", "thorchain", False, True, "direct_token_event", 0.90, "fixture", "fixture", ("THORChain RUNE",))
    thor_candidate = DiscoveredEventFadeCandidate(thor_event, rune, thor_link, thor_cls, None, None, {})
    thor_hyp = event_impact_hypotheses.generate_impact_hypotheses(
        EventDiscoveryResult((thor_raw,), (thor_event,), (thor_link,), (thor_cls,), (thor_candidate,)),
        taxonomy={},
        now=now,
    )[0]
    assert thor_hyp.candidate_role == "direct_subject"
    assert thor_hyp.cause_status == "confirmed"
    assert thor_hyp.market_reaction_confirmed is True
    assert thor_hyp.causal_mechanism_confirmed is True

    discovery = EventDiscoveryResult(
        raw_events=(memecore_raw, secondfi_a, secondfi_b, thor_raw),
        normalized_events=(memecore_event, events[0], events[1], thor_event),
        links=(memecore_link, *links, thor_link),
        classifications=(memecore_cls, *classes, thor_cls),
        candidates=(memecore_candidate, *candidates, thor_candidate),
    )
    with tempfile.TemporaryDirectory() as tmp:
        one_source_hyp = event_impact_hypotheses.generate_impact_hypotheses(
            EventDiscoveryResult((secondfi_a,), (events[0],), (links[0],), (classes[0],), (candidates[0],)),
            taxonomy={},
            now=now,
        )[0]
        watch_cfg = event_watchlist.EventWatchlistConfig(enabled=True, state_path=Path(tmp) / "watchlist.jsonl")
        event_watchlist.refresh_hypothesis_watchlist((one_source_hyp,), cfg=watch_cfg, now=now)
        updated_watch = event_watchlist.refresh_hypothesis_watchlist((hyp,), cfg=watch_cfg, now=now)
        updated_entry = updated_watch.entries[0]
        loaded_watch = event_watchlist.load_watchlist(watch_cfg.state_path)
        assert len(loaded_watch.entries) == 1
        assert loaded_watch.entries[0].key == updated_entry.key
        assert updated_entry.key.startswith(f"hypothesis|{hyp.incident_id}|cardano|ecosystem_affected_asset|")
        assert updated_entry.incident_id == hyp.incident_id
        assert updated_entry.hypothesis_id == hyp.hypothesis_id
        assert updated_entry.incident_canonical_name == hyp.incident_canonical_name
        assert updated_entry.incident_primary_subject == "SecondFi"
        assert updated_entry.incident_cause_status == hyp.cause_status
        assert updated_entry.incident_market_reaction_observed is True
        assert updated_entry.incident_causal_mechanism_confirmed is True
        assert updated_entry.source_count == 2
        assert "independent_source_confirmation" in updated_entry.material_change_reasons
        assert "incident_new_independent_source" in updated_entry.material_change_reasons
        assert "incident_confidence_changed" in updated_entry.material_change_reasons
        watch = event_watchlist.refresh_hypothesis_watchlist(
            (memecore_hyp, hyp, thor_hyp),
            cfg=watch_cfg,
            now=now,
        )
        write = event_incident_store.write_incidents(
            discovery,
            cfg=event_incident_store.EventIncidentStoreConfig(path=Path(tmp) / "event_incidents.jsonl"),
            hypotheses=(memecore_hyp, hyp, thor_hyp),
            watchlist_rows=watch.entries,
            now=now,
            run_id="run-incident-test",
            profile="quality_validation",
            run_mode="test",
            artifact_namespace="quality_validation",
        )
        assert write.success is True
        assert write.rows_written == 3
        loaded = event_incident_store.load_incidents(write.path)
        assert loaded.rows_read == 3
        secondfi_row = next(row for row in loaded.rows if row["primary_subject"] == "SecondFi")
        assert set(secondfi_row["source_raw_ids"]) == {"secondfi_a", "secondfi_b"}
        assert secondfi_row["source_update_count"] == 2
        assert secondfi_row["independent_source_count"] == 2
        assert secondfi_row["linked_hypothesis_ids"] == [hyp.hypothesis_id]
        assert secondfi_row["linked_watchlist_keys"]
        assert secondfi_row["market_reaction_confirmed"] is True
        assert secondfi_row["causal_mechanism_confirmed"] is True
        assert any(asset["role"] == "ecosystem_affected_asset" for asset in secondfi_row["linked_assets"])
        memecore_row = next(row for row in loaded.rows if row["primary_subject"] == "MemeCore")
        assert memecore_row["event_archetype"] == "market_dislocation_unknown"
        assert memecore_row["current_cause_status"] == "ruled_out"
        assert memecore_row["market_reaction_confirmed"] is True
        assert memecore_row["causal_mechanism_confirmed"] is False
        thor_row = next(row for row in loaded.rows if row["primary_subject"] == "THORChain")
        assert thor_row["event_archetype"] == "exploit_security_event"
        assert thor_row["current_cause_status"] == "confirmed"
        assert any(asset["symbol"] == "RUNE" and asset["role"] == "direct_subject" for asset in thor_row["linked_assets"])
        thor_entry = next(entry for entry in watch.entries if entry.symbol == "RUNE")
        assert thor_entry.incident_id == thor_hyp.incident_id
        assert thor_entry.hypothesis_id == thor_hyp.hypothesis_id
        assert thor_entry.incident_canonical_name == thor_hyp.incident_canonical_name
        assert thor_entry.incident_primary_subject == "THORChain"
        decision = event_alpha_router.EventAlphaRouteDecision(
            entry=thor_entry,
            route=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
            alertable=True,
            reason="fixture incident-linked hypothesis",
            lane=event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        )
        snap_path = Path(tmp) / "alerts.jsonl"
        event_alpha_alert_store.write_alert_snapshots(
            [],
            router_result=type("Router", (), {"decisions": [decision]})(),
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=snap_path),
            now=now,
            run_id="run-incident-test",
            profile="quality_validation",
            run_mode="test",
            artifact_namespace="quality_validation",
        )
        snap = event_alpha_alert_store.load_alert_snapshots(snap_path).rows[0]
        assert snap["incident_id"] == thor_hyp.incident_id
        assert snap["hypothesis_id"] == thor_hyp.hypothesis_id
        assert snap["incident_canonical_name"] == thor_hyp.incident_canonical_name
        assert snap["incident_primary_subject"] == "THORChain"
        card_path = Path(tmp) / "rune_card.md"
        card_index_path = Path(tmp) / "index.md"
        core_id = snap.get("core_opportunity_id")
        card_path.write_text(
            "\n".join([
                "# RUNE Event Research Card",
                "- Generated at: 2026-06-28T00:00:00+00:00",
                "- Lineage status: current",
                "- legacy_lineage_missing: false",
                "- Run ID: run-incident-test",
                "- Profile: quality_validation",
                "- Namespace: quality_validation",
                f"- Core opportunity ID: {core_id}",
                f"- Feedback target: {core_id}",
                "- Feedback target type: core_opportunity_id",
            ]),
            encoding="utf-8",
        )
        card_index_path.write_text(f"# Event Research Cards\n\n- [rune_card.md](rune_card.md) · feedback target: `{core_id}`\n", encoding="utf-8")
        assert event_research_cards.card_core_opportunity_id(card_path) == core_id
        clean_quality = {
            "impact_path_type": "exploit_security_event",
            "impact_path_strength": "strong",
            "candidate_role": "direct_subject",
            "evidence_quality_score": 85,
            "source_class": "primary_or_reputable_source",
            "evidence_specificity": "direct_token_mechanism",
            "market_confirmation_score": 80,
            "market_confirmation_level": "confirmed",
            "market_context_freshness_status": "fresh",
            "market_context_age_hours": 0.2,
            "market_context_stale": False,
            "market_context_freshness_cap_applied": False,
            "opportunity_score_final": 75,
            "opportunity_level": "validated_digest",
            "opportunity_verdict_reasons": ["incident_linked"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "not_watchlist_without_market_followthrough",
            "manual_verification_items": ["verify incident source and token-specific market reaction"],
            "upgrade_requirements": ["needs watchlist confirmation"],
            "downgrade_warnings": ["none"],
        }
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-incident-test",
                "profile": "quality_validation",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
                "alertable": 1,
                "snapshot_write_success": True,
                "snapshot_rows_written": 1,
            }],
            hypothesis_rows=[{
                "row_type": "event_impact_hypothesis",
                "run_id": "run-incident-test",
                "profile": "quality_validation",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
                "hypothesis_id": thor_hyp.hypothesis_id,
                "incident_id": thor_hyp.incident_id,
                **clean_quality,
            }],
            watchlist_rows=[thor_entry],
            alert_rows=[snap],
            incident_rows=loaded.rows,
            card_paths=[card_path, card_index_path],
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor.hypothesis_rows_missing_incident_id == 0
        assert doctor.watchlist_hypothesis_rows_missing_incident_id == 0
        assert doctor.alert_hypothesis_rows_missing_incident_id == 0
        assert doctor.status in {"OK", "WARN"}
        thor_with_blocked_support = dict(thor_row)
        thor_with_blocked_support["qualified_link_count"] = max(1, int(thor_with_blocked_support.get("qualified_link_count") or 0))
        thor_with_blocked_support["quality_blocked_link_count"] = 1
        doctor_with_diagnostic_link = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-incident-test",
                "profile": "quality_validation",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
            }],
            incident_rows=[thor_with_blocked_support],
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor_with_diagnostic_link.quality_blocked_links_present == 1
        assert doctor_with_diagnostic_link.quality_blocked_links_promoting_incident == 0
        assert doctor_with_diagnostic_link.status in {"OK", "WARN"}
        assert "quality_blocked_links_present=1" in event_alpha_artifact_doctor.format_artifact_doctor_report(doctor_with_diagnostic_link)
        thor_only_blocked_support = dict(thor_with_blocked_support)
        thor_only_blocked_support["qualified_link_count"] = 0
        doctor_only_blocked_link = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-incident-test",
                "profile": "quality_validation",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
            }],
            incident_rows=[thor_only_blocked_support],
            include_test_artifacts=True,
            strict=True,
        )
        assert doctor_only_blocked_link.quality_blocked_links_promoting_incident == 1
        assert doctor_only_blocked_link.status == "BLOCKED"
        missing_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-incident-test", "alertable": 0}],
            watchlist_rows=[{
                "row_type": "event_watchlist_state",
                "relationship_type": "impact_hypothesis",
                "key": "fresh-missing-incident",
                "event_id": "hyp:missing",
                "coin_id": "missing",
                "symbol": "MISS",
                "run_mode": "burn_in",
                "artifact_namespace": "quality_validation",
                "opportunity_level": "validated_digest",
                "opportunity_score_final": 75,
                "impact_path_type": "exploit_security_event",
                "evidence_specificity": "direct_token_mechanism",
            }],
            include_test_artifacts=True,
            strict=True,
        )
        assert missing_doctor.status == "BLOCKED"
        assert missing_doctor.watchlist_hypothesis_rows_missing_incident_id == 1
        report = event_incident_store.format_incidents_report(loaded)
        assert "EVENT INCIDENTS REPORT" in report
        assert "market_dislocation_unknown=1" in report
        assert "exploit_security_event=2" in report
        assert "multiple_source_updates: 1" in report
        assert "incident_linked_hypotheses_count: 3" in report
        assert "incident_linked_watchlist_count: 3" in report

        anomaly_write = event_incident_store.write_incidents(
            EventDiscoveryResult((sol_a, sol_b, usdt), anomaly_events, (), (), ()),
            cfg=event_incident_store.EventIncidentStoreConfig(path=Path(tmp) / "market_incidents.jsonl"),
            now=now,
            run_id="run-market-anomaly-test",
            profile="quality_validation",
            run_mode="test",
            artifact_namespace="quality_validation",
        )
        assert anomaly_write.success is True
        assert anomaly_write.rows_written == 2
        anomaly_loaded = event_incident_store.load_incidents(anomaly_write.path)
        anomaly_report = event_incident_store.format_incidents_report(anomaly_loaded)
        assert "SOL market anomaly" in anomaly_report
        assert "USDT market anomaly" in anomaly_report
        assert "No · market anomaly" not in anomaly_report
        assert "primary_subjects: SOL=1, USDT=1" in anomaly_report
        assert "absence_of_validated_catalyst_claims: 3" in anomaly_report
        assert "market_reaction_unknown_cause: 2" in anomaly_report
        assert all(row["market_reaction_observed"] is True for row in anomaly_loaded.rows)
        assert all(row["current_cause_status"] == "unknown" for row in anomaly_loaded.rows)
        sol_row = next(row for row in anomaly_loaded.rows if row["primary_subject"] == "SOL")
        usdt_row = next(row for row in anomaly_loaded.rows if row["primary_subject"] == "USDT")
        assert any(
            asset["symbol"] == "SOL" and asset["coin_id"] == "solana" and asset["role"] == "direct_subject"
            for asset in sol_row["linked_assets"]
        )
        assert any(
            asset["symbol"] == "USDT" and asset["coin_id"] == "tether" and asset["role"] == "direct_subject"
            for asset in usdt_row["linked_assets"]
        )
        assert not any(asset["symbol"] == "SECTOR" and asset["role"] == "direct_subject" for asset in sol_row["linked_assets"])
        no_incident_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-no-incident", "alertable": 0}],
            hypothesis_rows=[{
                "row_type": "event_impact_hypothesis",
                "run_id": "run-no-incident",
                "profile": "quality_validation",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
                "hypothesis_id": "hyp:no-incident",
                "incident_link_status": "no_incident",
                "incident_link_reason": "no_canonical_incident_for_event_evidence",
                **clean_quality,
            }],
            watchlist_rows=[{
                "row_type": "event_watchlist_state",
                "relationship_type": "impact_hypothesis",
                "key": "fresh-no-incident",
                "event_id": "hyp:no-incident",
                "coin_id": "noincident",
                "symbol": "NOINC",
                "run_mode": "test",
                "artifact_namespace": "quality_validation",
                "incident_link_status": "no_incident",
                "incident_link_reason": "no_canonical_incident_for_event_evidence",
                "opportunity_level": "validated_digest",
                "opportunity_score_final": 75,
                "impact_path_type": "exploit_security_event",
                "evidence_specificity": "direct_token_mechanism",
            }],
            alert_rows=[{
                "row_type": "event_alpha_alert_snapshot",
                "run_id": "run-no-incident",
                "hypothesis_id": "hyp:no-incident",
                "incident_link_status": "no_incident",
                "incident_link_reason": "no_canonical_incident_for_event_evidence",
                **clean_quality,
            }],
            include_test_artifacts=True,
            strict=True,
        )
        assert no_incident_doctor.hypothesis_rows_missing_incident_id == 0
        assert no_incident_doctor.watchlist_hypothesis_rows_missing_incident_id == 0
        assert no_incident_doctor.alert_hypothesis_rows_missing_incident_id == 0
