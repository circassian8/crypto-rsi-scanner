"""Focused Event Alpha incident semantics and relevance tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_incident_policy_flags_require_semantic_truth():
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.radar.incidents as incidents

    false_context = incidents._incident_market_context(  # noqa: SLF001
        [
            {
                "market_reaction_confirmed": "false",
                "causal_mechanism_confirmed": "off",
                "market_confirmation_score": True,
                "market_confirmation_level": "none",
            }
        ],
        [],
    )
    true_context = incidents._incident_market_context(  # noqa: SLF001
        [
            {
                "market_reaction_confirmed": "yes",
                "causal_mechanism_confirmed": 1,
                "market_confirmation_score": 80,
                "market_confirmation_level": "strong",
            }
        ],
        [],
    )

    assert false_context["market_reaction_observed"] is False
    assert false_context["market_reaction_confirmed"] is False
    assert false_context["causal_mechanism_confirmed"] is False
    assert true_context["market_reaction_observed"] is True
    assert true_context["market_reaction_confirmed"] is True
    assert true_context["causal_mechanism_confirmed"] is True

    effective = incidents._row_with_effective_relevance(  # noqa: SLF001
        {
            "incident_id": "incident:false-like",
            "canonical_name": "False-like incident",
            "event_archetype": "unknown",
            "diagnostic_only": "false",
            "market_reaction_observed": "false",
            "market_reaction_confirmed": "off",
            "causal_mechanism_confirmed": "no",
        }
    )
    assert effective["incident_relevance_status"] == "raw_observation"
    assert effective["diagnostic_hidden_by_default"] is True
    assert incidents._has_active_watchlist_row(  # noqa: SLF001
        ({"state": "QUALITY_BLOCKED", "should_alert": "false"},)
    ) is False

    result = incidents.EventIncidentStoreReadResult(
        path=Path("event_incidents.jsonl"),
        rows_read=1,
        rows=[effective],
        total_rows_read=1,
        filters={"include_raw": "false", "include_diagnostic": "off"},
    )
    report = incidents.format_incidents_report(result)
    assert "raw_observation_rows_hidden: 1" in report
    assert "No stored incidents matched" in report

    lines = "\n".join(incidents._incident_lines(effective))  # noqa: SLF001
    assert "reaction_observed=false" in lines
    assert "reaction_confirmed=false" in lines
    assert "causal=false" in lines


def test_incident_market_context_rejects_malformed_scores_and_preserves_raw_asset():
    from types import SimpleNamespace

    import crypto_rsi_scanner.event_alpha.radar.incidents as incidents

    context = incidents._incident_market_context(  # noqa: SLF001
        [
            {
                "market_context_source": "malformed",
                "market_confirmation_score": 1000,
                "market_confirmation_level": "malformed",
                "market_context_age_seconds": float("nan"),
                "symbol": "BAD",
            },
            {
                "market_context_source": "validated",
                "market_confirmation_score": 80,
                "market_confirmation_level": "strong",
                "market_context_age_seconds": 3600,
                "symbol": "GOOD",
            },
        ],
        [],
    )

    assert context["market_context_source"] == "validated"
    assert context["market_context_asset"] == "GOOD"
    assert context["market_reaction_level"] == "strong"
    assert context["market_context_age"] == 3600.0

    for malformed in (True, float("nan"), float("inf"), float("-inf"), -1, 101):
        malformed_only = incidents._incident_market_context(  # noqa: SLF001
            [{"market_confirmation_score": malformed}],
            [],
        )
        assert malformed_only["market_reaction_observed"] is False

    incident = SimpleNamespace(raw_ids=("shadowed", "valid"))
    raw_by_id = {
        "shadowed": SimpleNamespace(raw_json={
            "market": {
                "symbol": "SHADOWED",
                "coin_id": "shadowed",
                "anomaly_score": 99,
            },
            "anomaly": {"score": 0},
        }),
        "valid": SimpleNamespace(raw_json={
            "market": {"symbol": "VALID", "coin_id": "valid"},
            "anomaly": {"score": 0.5},
        }),
    }
    raw_context = incidents._incident_market_context(  # noqa: SLF001
        [],
        [],
        incident=incident,
        raw_by_id=raw_by_id,
    )

    assert raw_context["market_context_source"] == "raw_market_anomaly_snapshot"
    assert raw_context["market_context_asset"] == "VALID"


def test_incident_relevance_numeric_evidence_fails_closed():
    from types import SimpleNamespace

    import crypto_rsi_scanner.event_alpha.radar.incidents as incidents

    incident = SimpleNamespace(
        event_archetype="rwa_preipo_proxy",
        raw_ids=("raw",),
    )
    valid_link = {
        "validated_symbol": "SAFE",
        "validated_coin_id": "safe",
        "candidate_role": "direct_subject",
        "impact_path_type": "exploit_security_event",
        "evidence_specificity": "direct_token_mechanism",
        "opportunity_level": "watchlist",
        "opportunity_score_final": 80,
    }
    assert incidents._link_row_quality(  # noqa: SLF001
        valid_link,
        incident=incident,
        source="hypothesis",
    )["qualified"] is True
    assert incidents._link_row_quality(  # noqa: SLF001
        {**valid_link, "state_quality_capped": "false"},
        incident=incident,
        source="hypothesis",
    )["qualified"] is True

    for malformed in (101, 1000, "101"):
        result = incidents._link_row_quality(  # noqa: SLF001
            {**valid_link, "opportunity_score_final": malformed},
            incident=incident,
            source="hypothesis",
        )
        assert result["qualified"] is False
        assert result["quality_blocked"] is True

    capped = incidents._link_row_quality(  # noqa: SLF001
        {**valid_link, "state_quality_capped": "true"},
        incident=incident,
        source="hypothesis",
    )
    assert capped["qualified"] is False
    assert capped["quality_blocked"] is True

    for malformed in (
        True,
        float("nan"),
        float("inf"),
        float("-inf"),
        -0.1,
        1.1,
        100,
    ):
        raw_by_id = {"raw": SimpleNamespace(source_confidence=malformed)}
        assert incidents._high_quality_external_candidate(  # noqa: SLF001
            incident,
            raw_by_id,
            (),
        ) is False
    assert incidents._high_quality_external_candidate(  # noqa: SLF001
        incident,
        {"raw": SimpleNamespace(source_confidence=0.80)},
        (),
    ) is True

    base_persisted = {
        "incident_relevance_status": "active_incident",
        "canonical_name": "Persisted numeric evidence",
        "event_archetype": "exploit_security_event",
        "qualified_link_count": 1,
        "link_quality_reasons": ("qualified_hypothesis_link",),
    }
    assert incidents._row_with_effective_relevance(  # noqa: SLF001
        base_persisted
    )["incident_relevance_status"] == "active_incident"
    for malformed in (True, float("nan"), "1", -1):
        projected = incidents._row_with_effective_relevance(  # noqa: SLF001
            {**base_persisted, "qualified_link_count": malformed}
        )
        assert projected["qualified_link_count"] == 0
        assert projected["incident_relevance_status"] == "incident_candidate"


def test_incident_link_identity_and_role_confidence_are_typed_and_canonical():
    from types import SimpleNamespace

    import crypto_rsi_scanner.event_alpha.radar.incidents as incidents

    incident = SimpleNamespace(
        event_archetype="rwa_preipo_proxy",
        linked_assets=(),
    )
    malformed_identity = incidents._link_row_quality(  # noqa: SLF001
        {
            "validated_symbol": True,
            "validated_coin_id": False,
            "candidate_role": True,
            "impact_path_type": "venue_value_capture",
            "evidence_specificity": "direct_token_mechanism",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 80,
        },
        incident=incident,
        source="hypothesis",
    )
    assert malformed_identity["qualified"] is False
    assert malformed_identity["unknown_role"] is True

    watchlist_assets = incidents._linked_assets(  # noqa: SLF001
        [],
        [
            {
                "symbol": "ZERO",
                "coin_id": "zero",
                "candidate_role": "direct_subject",
                "role_confidence": 0,
                "latest_score_components": {"role_confidence": 0.9},
            },
            {
                "symbol": "INVALID",
                "coin_id": "invalid",
                "candidate_role": "direct_subject",
                "role_confidence": 1.1,
                "latest_score_components": {"role_confidence": 0.8},
            },
        ],
        incident=incident,
    )
    by_symbol = {row["symbol"]: row for row in watchlist_assets}
    assert by_symbol["ZERO"]["role_confidence"] == 0.0
    assert by_symbol["INVALID"]["role_confidence"] is None

    hypothesis_assets = incidents._linked_assets(  # noqa: SLF001
        [
            {
                "candidate_symbols": (True, "FALLBACK"),
                "candidate_coin_ids": (False, "fallback"),
                "candidate_role": "direct_subject",
                "role_confidence": float("nan"),
            },
            {
                "validated_asset": {"validated": True},
                "candidate_symbols": ("UNVERIFIED",),
                "candidate_coin_ids": ("unverified",),
                "candidate_role": "direct_subject",
                "role_confidence": 0.7,
            },
        ],
        [],
        incident=incident,
    )
    assert hypothesis_assets[0]["symbol"] == "FALLBACK"
    assert hypothesis_assets[0]["coin_id"] == "fallback"
    assert hypothesis_assets[0]["role"] == "candidate_suggestion"
    assert hypothesis_assets[0]["role_confidence"] is None
    unverified = next(
        row for row in hypothesis_assets if row["symbol"] == "UNVERIFIED"
    )
    assert unverified["role"] == "candidate_suggestion"
    assert unverified["source"] == "hypothesis_candidate_suggestion"

    incident_with_bad_confidence = SimpleNamespace(
        event_archetype="rwa_preipo_proxy",
        linked_assets=(
            SimpleNamespace(
                symbol="INC",
                coin_id="incident",
                role="direct_subject",
                confidence=float("inf"),
                evidence=(),
            ),
            SimpleNamespace(
                symbol=True,
                coin_id=False,
                role=True,
                confidence=0.9,
                evidence=(),
            ),
        ),
    )
    incident_assets = incidents._linked_assets(  # noqa: SLF001
        [],
        [],
        incident=incident_with_bad_confidence,
    )
    assert len(incident_assets) == 1
    assert incident_assets[0]["role_confidence"] is None


def test_event_incident_relevance_gates_raw_external_observations():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
    import crypto_rsi_scanner.event_alpha.radar.incidents as event_incident_store
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 26, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id: str, title: str, body: str, *, provider: str = "fixture_news", confidence: float = 0.65, payload=None):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider=provider,
            fetched_at=now,
            published_at=now,
            source_url=f"https://example.test/{raw_id}",
            title=title,
            body=body,
            raw_json=dict(payload or {}),
            source_confidence=confidence,
            content_hash=raw_id,
        )

    broad_raw = raw(
        "trump_putin_polymarket",
        "Where will Trump meet Putin?",
        "A Polymarket question asks where Trump will meet Putin. No crypto asset, token, venue value capture, or market anomaly is mentioned.",
        provider="polymarket",
        confidence=0.58,
    )
    broad_event = NormalizedEvent(
        "evt_trump_putin_polymarket",
        (broad_raw.raw_id,),
        "Where will Trump meet Putin?",
        "prediction_market",
        None,
        0.0,
        now,
        "polymarket",
        (broad_raw.source_url,),
        "Trump Putin meeting",
        broad_raw.body,
        0.58,
    )
    broad_result = EventDiscoveryResult((broad_raw,), (broad_event,), (), (), ())
    with tempfile.TemporaryDirectory() as tmp:
        live_path = Path(tmp) / "live_incidents.jsonl"
        live_write = event_incident_store.write_incidents(
            broad_result,
            cfg=event_incident_store.EventIncidentStoreConfig(path=live_path),
            now=now,
            run_id="run-broad-live",
            profile="notify_llm_quality_fresh",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm_quality_fresh",
        )
        assert live_write.success is True
        assert live_write.rows_written == 0

        debug_path = Path(tmp) / "debug_incidents.jsonl"
        debug_write = event_incident_store.write_incidents(
            broad_result,
            cfg=event_incident_store.EventIncidentStoreConfig(path=debug_path),
            now=now,
            run_id="run-broad-debug",
            profile="quality_validation",
            run_mode="test",
            artifact_namespace="quality_validation",
        )
        assert debug_write.success is True
        assert debug_write.rows_written == 1
        hidden = event_incident_store.load_incidents(debug_path)
        assert hidden.rows[0]["incident_relevance_status"] == "external_context_only"
        assert hidden.rows[0]["diagnostic_only"] is False
        assert hidden.rows[0]["external_context_only"] is True
        assert hidden.rows[0]["diagnostic_hidden_by_default"] is True
        hidden_report = event_incident_store.format_incidents_report(hidden)
        assert "diagnostic_rows_hidden: 0" in hidden_report
        assert "external_context_rows_hidden: 1" in hidden_report
        assert "Where will Trump meet Putin?" not in hidden_report
        visible_report = event_incident_store.format_incidents_report(
            event_incident_store.load_incidents(debug_path, include_diagnostic=True)
        )
        assert "diagnostic_rows_hidden: 0" in visible_report
        assert "external_context_rows_hidden: 0" in visible_report
        assert "Putin · prediction market" in visible_report
        debug_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-broad-debug", "profile": "quality_validation", "run_mode": "test"}],
            incident_rows=hidden.rows,
            include_test_artifacts=True,
            strict=True,
        )
        assert debug_doctor.diagnostic_incident_rows == 0
        assert debug_doctor.raw_observation_incident_rows == 0
        assert debug_doctor.external_context_incident_rows == 1
        assert debug_doctor.incident_rows_without_linked_hypotheses == 0
        assert debug_doctor.incident_rows_without_linked_watchlist == 0

        raw_observation = raw(
            "unstructured_unlinked_note",
            "Unstructured source note",
            "A source note has no clear external catalyst, no crypto token, and no market anomaly.",
            provider="fixture_news",
            confidence=0.42,
        )
        raw_event = NormalizedEvent(
            "evt_unstructured_note",
            (raw_observation.raw_id,),
            "Unstructured source note",
            "news",
            None,
            0.0,
            now,
            "fixture_news",
            (raw_observation.source_url,),
            None,
            raw_observation.body,
            0.42,
        )
        raw_path = Path(tmp) / "raw_incidents.jsonl"
        raw_write = event_incident_store.write_incidents(
            EventDiscoveryResult((raw_observation,), (raw_event,), (), (), ()),
            cfg=event_incident_store.EventIncidentStoreConfig(path=raw_path, store_raw_observations=True),
            now=now,
            run_id="run-raw-opt-in",
            profile="notify_llm_quality_fresh",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm_quality_fresh",
        )
        assert raw_write.success is True
        assert raw_write.rows_written == 1
        raw_rows = event_incident_store.load_incidents(raw_path)
        assert raw_rows.rows[0]["incident_relevance_status"] == "raw_observation"
        assert raw_rows.rows[0]["raw_observation"] is True
        assert "raw_observation_rows_hidden: 1" in event_incident_store.format_incidents_report(raw_rows)

        missing_relevance = {
            "schema_version": event_incident_store.INCIDENT_STORE_SCHEMA_VERSION,
            "row_type": "event_incident",
            "run_id": "run-missing-relevance",
            "profile": "notify_llm_quality_fresh",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_quality_fresh",
            "incident_id": "incident:missing_relevance",
            "canonical_name": "Missing relevance crypto incident",
            "event_archetype": "exploit_security_event",
            "primary_subject": "THORChain",
            "incident_subject_quality": "valid",
            "diagnostic_only": False,
            "linked_hypothesis_ids": [],
            "linked_watchlist_keys": [],
        }
        strict_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-missing-relevance", "profile": "notify_llm_quality_fresh", "run_mode": "notification_burn_in"}],
            incident_rows=[missing_relevance],
            strict=True,
        )
        assert strict_doctor.status == "BLOCKED"
        assert strict_doctor.incident_relevance_missing == 1

    thor_raw = raw(
        "thorchain_relevance",
        "THORChain confirms RUNE exploit",
        "THORChain confirms a RUNE exploit and security incident affecting the RUNE token.",
        confidence=0.91,
    )
    thor_event = NormalizedEvent(
        "evt_thorchain_relevance",
        (thor_raw.raw_id,),
        "THORChain RUNE exploit",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (thor_raw.source_url,),
        "THORChain",
        thor_raw.body,
        0.91,
    )
    thor_incident = event_incident_graph.build_incidents((thor_event,), {thor_raw.raw_id: thor_raw})[0]
    thor_relevance = event_incident_store.classify_incident_relevance(
        thor_incident,
        raw_by_id={thor_raw.raw_id: thor_raw},
        hypotheses=({
            "hypothesis_id": "hyp:rune",
            "incident_id": thor_incident.incident_id,
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "candidate_role": "direct_subject",
            "impact_path_type": "exploit_security_event",
            "evidence_specificity": "direct_token_mechanism",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 82,
        },),
        watchlist_rows=({
            "key": "watch:rune",
            "incident_id": thor_incident.incident_id,
            "state": "WATCHLIST",
            "final_state_after_quality_gate": "WATCHLIST",
            "symbol": "RUNE",
            "coin_id": "thorchain",
            "candidate_role": "direct_subject",
            "impact_path_type": "exploit_security_event",
            "evidence_specificity": "direct_token_mechanism",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 82,
        },),
    )
    assert thor_relevance["incident_relevance_status"] == "active_incident"
    assert thor_relevance["canonical_persistence_reason"] == "qualified_watchlist_link"
    assert thor_relevance["qualified_link_count"] == 2

    sol_raw = raw(
        "sol_market_anomaly_relevance",
        "SOL market anomaly",
        "SOL matched market-anomaly filters with no confirmed catalyst.",
        provider="market_anomaly",
        payload={
            "market": {"symbol": "SOL", "coin_id": "solana", "return_24h": 42},
            "anomaly": {"score": 91, "research_only": True},
        },
    )
    sol_event = NormalizedEvent(
        "evt_sol_market_anomaly_relevance",
        (sol_raw.raw_id,),
        "SOL market anomaly",
        "market_anomaly",
        None,
        0.0,
        now,
        "market_anomaly",
        (),
        None,
        sol_raw.body,
        0.72,
    )
    sol_incident = event_incident_graph.build_incidents((sol_event,), {sol_raw.raw_id: sol_raw})[0]
    sol_relevance = event_incident_store.classify_incident_relevance(sol_incident, raw_by_id={sol_raw.raw_id: sol_raw})
    assert sol_relevance["incident_relevance_status"] == "canonical_incident"
    assert sol_relevance["canonical_persistence_reason"] == "market_dislocation"

    openai_raw = raw(
        "openai_preipo_sector_relevance",
        "OpenAI pre-IPO markets expand",
        "OpenAI pre-IPO exposure could affect tokenized-stock crypto venues if listed by a venue.",
        confidence=0.86,
    )
    openai_event = NormalizedEvent(
        "evt_openai_preipo_relevance",
        (openai_raw.raw_id,),
        "OpenAI pre-IPO markets expand",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (openai_raw.source_url,),
        "OpenAI",
        openai_raw.body,
        0.86,
    )
    openai_incident = event_incident_graph.build_incidents((openai_event,), {openai_raw.raw_id: openai_raw})[0]
    openai_relevance = event_incident_store.classify_incident_relevance(
        openai_incident,
        raw_by_id={openai_raw.raw_id: openai_raw},
        hypotheses=({"hypothesis_id": "hyp:openai-sector", "incident_id": openai_incident.incident_id, "candidate_sectors": ("tokenized_stock_venues",)},),
    )
    assert openai_relevance["incident_relevance_status"] == "incident_candidate"
    assert openai_relevance["qualified_link_count"] == 0
    assert "weak_unqualified_hypothesis_link" in openai_relevance["link_quality_reasons"]

    sports_raw = raw(
        "sweden_sports_sector_relevance",
        "Sweden World Cup odds move",
        "A broad sports event references fan-token sectors, but no concrete crypto asset is validated.",
        confidence=0.84,
    )
    sports_event = NormalizedEvent(
        "evt_sweden_sports_sector_relevance",
        (sports_raw.raw_id,),
        "Sweden World Cup odds move",
        "sports_event",
        None,
        0.0,
        now,
        "fixture_news",
        (sports_raw.source_url,),
        "World Cup",
        sports_raw.body,
        0.84,
    )
    sports_incident = event_incident_graph.build_incidents((sports_event,), {sports_raw.raw_id: sports_raw})[0]
    sports_relevance = event_incident_store.classify_incident_relevance(
        sports_incident,
        raw_by_id={sports_raw.raw_id: sports_raw},
        watchlist_rows=({
            "key": "watch:sector:sports",
            "incident_id": sports_incident.incident_id,
            "state": "WATCHLIST",
            "final_state_after_quality_gate": "WATCHLIST",
            "symbol": "SECTOR",
            "coin_id": "sports_fan_proxy",
            "candidate_role": "proxy_instrument",
            "impact_path_type": "fan_token_attention",
            "evidence_specificity": "direct_token_mechanism",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 82,
        },),
    )
    assert sports_relevance["incident_relevance_status"] != "active_incident"
    assert sports_relevance["qualified_link_count"] == 0
    assert sports_relevance["sector_only_link_count"] == 1
    assert "sector_only_unqualified_link" in sports_relevance["link_quality_reasons"]

    fannie_raw = raw(
        "fannie_rwa_candidate",
        "Fannie Mae pre-IPO tokenized stock venue watch",
        "A high-quality source says Fannie Mae pre-IPO and tokenized stock venues may become relevant to RWA markets.",
        confidence=0.88,
    )
    fannie_event = NormalizedEvent(
        "evt_fannie_rwa_candidate",
        (fannie_raw.raw_id,),
        "Fannie Mae pre-IPO tokenized stock venue watch",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (fannie_raw.source_url,),
        "Fannie Mae",
        fannie_raw.body,
        0.88,
    )
    fannie_incident = event_incident_graph.build_incidents((fannie_event,), {fannie_raw.raw_id: fannie_raw})[0]
    fannie_relevance = event_incident_store.classify_incident_relevance(
        fannie_incident,
        raw_by_id={fannie_raw.raw_id: fannie_raw},
    )
    assert fannie_relevance["incident_relevance_status"] == "incident_candidate"

    def classify_weak_event(raw_id: str, title: str, body: str, event_type: str, symbol: str, coin_id: str):
        event_raw = raw(raw_id, title, body, confidence=0.76)
        event = NormalizedEvent(
            f"evt_{raw_id}",
            (event_raw.raw_id,),
            title,
            event_type,
            None,
            0.0,
            now,
            "fixture_news",
            (event_raw.source_url,),
            title,
            event_raw.body,
            0.76,
        )
        incident = event_incident_graph.build_incidents((event,), {event_raw.raw_id: event_raw})[0]
        weak_watchlist = {
            "key": f"watch:{raw_id}",
            "incident_id": incident.incident_id,
            "state": "WATCHLIST",
            "requested_state_before_quality_gate": "WATCHLIST",
            "final_state_after_quality_gate": "QUALITY_BLOCKED",
            "state_quality_capped": True,
            "symbol": symbol,
            "coin_id": coin_id,
            "candidate_role": "unknown",
            "impact_path_type": "insufficient_data",
            "evidence_specificity": "insufficient_data",
            "opportunity_level": "local_only",
            "opportunity_score_final": 0,
        }
        return event_incident_store.classify_incident_relevance(
            incident,
            raw_by_id={event_raw.raw_id: event_raw},
            watchlist_rows=(weak_watchlist,),
        )

    annexation = classify_weak_event(
        "annexation_weak_link",
        "Annexation prediction market",
        "A broad annexation prediction market mentions no validated crypto token impact path.",
        "political_event",
        "UMA",
        "uma",
    )
    assert annexation["incident_relevance_status"] == "external_context_only"
    assert annexation["qualified_link_count"] == 0
    assert "quality_blocked_link_only" in annexation["link_quality_reasons"]

    macron = classify_weak_event(
        "macron_weak_link",
        "Macron election odds move",
        "A broad election article mentions Macron and prediction markets but no direct TRUMP token value path.",
        "political_event",
        "TRUMP",
        "official-trump",
    )
    assert macron["incident_relevance_status"] == "external_context_only"
    assert macron["unknown_role_link_count"] == 1

    openai_fet = classify_weak_event(
        "openai_fet_weak_link",
        "OpenAI pre-IPO markets expand",
        "OpenAI pre-IPO exposure may matter to crypto AI tokens someday, but no FET value-capture path is validated.",
        "ai_ipo_proxy",
        "FET",
        "fetch-ai",
    )
    assert openai_fet["incident_relevance_status"] == "incident_candidate"
    assert openai_fet["canonical_persistence_reason"] == "quality_blocked_link_only"

    databricks_velvet_weak = classify_weak_event(
        "databricks_velvet_weak_link",
        "Databricks IPO closing",
        "Databricks IPO closing is broad pre-IPO news, while the VELVET link has not been quality validated.",
        "rwa_preipo_proxy",
        "VELVET",
        "velvet",
    )
    assert databricks_velvet_weak["incident_relevance_status"] == "incident_candidate"
    assert databricks_velvet_weak["qualified_link_count"] == 0

    velvet_quality_raw = raw(
        "velvet_spacex_quality_link",
        "Velvet offers SpaceX pre-IPO exposure",
        "VELVET users can trade SpaceX pre-IPO exposure through the Velvet crypto venue.",
        confidence=0.92,
    )
    velvet_event = NormalizedEvent(
        "evt_velvet_spacex_quality",
        (velvet_quality_raw.raw_id,),
        "Velvet offers SpaceX pre-IPO exposure",
        "rwa_preipo_proxy",
        None,
        0.0,
        now,
        "fixture_news",
        (velvet_quality_raw.source_url,),
        "SpaceX",
        velvet_quality_raw.body,
        0.92,
    )
    velvet_incident = event_incident_graph.build_incidents((velvet_event,), {velvet_quality_raw.raw_id: velvet_quality_raw})[0]
    velvet_relevance = event_incident_store.classify_incident_relevance(
        velvet_incident,
        raw_by_id={velvet_quality_raw.raw_id: velvet_quality_raw},
        hypotheses=({
            "hypothesis_id": "hyp:velvet-spacex",
            "incident_id": velvet_incident.incident_id,
            "validated_symbol": "VELVET",
            "validated_coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_path_type": "venue_value_capture",
            "evidence_specificity": "direct_token_mechanism",
            "opportunity_level": "watchlist",
            "opportunity_score_final": 84,
        },),
    )
    assert velvet_relevance["incident_relevance_status"] == "active_incident"
    assert velvet_relevance["canonical_persistence_reason"] == "qualified_hypothesis_link"
    assert velvet_relevance["qualified_link_count"] == 1


def test_event_opportunity_upgrade_path_and_audit_sections():
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.radar.opportunity_verdict as event_opportunity_verdict

    weak = event_opportunity_verdict.explain_upgrade_path(components={
        "impact_path_type": "generic_cooccurrence_only",
        "candidate_role": "generic_mention",
        "market_confirmation_level": "weak",
        "market_confirmation_score": 20,
        "evidence_quality_score": 35,
        "opportunity_score_final": 42,
    })
    assert "blocked_by_generic_cooccurrence" in weak.upgrade_requirements
    assert "needs_market_confirmation" in weak.upgrade_requirements
    assert "no_value_capture" in weak.downgrade_warnings

    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    decision = _notify_route_decision(
        "VELVET",
        event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
    )
    incident_row = {
        "row_type": "event_incident",
        "incident_id": "incident:velvet",
        "canonical_name": "SpaceX proxy attention",
        "primary_subject": "SpaceX",
        "affected_ecosystem": "Velvet",
        "current_cause_status": "unknown",
        "claim_history": [{"claim_type": "proxy", "polarity": "asserted", "cause_status": "unknown"}],
        "source_update_count": 2,
        "independent_source_count": 2,
        "market_reaction_confirmed": True,
        "causal_mechanism_confirmed": False,
        "market_context_source": "candidate_event_market_snapshot",
        "linked_assets": [{"symbol": "VELVET", "coin_id": "velvet", "role": "proxy_venue"}],
    }
    report = event_opportunity_audit.format_opportunity_audit(
        "incident:velvet",
        route_decisions=[decision],
        incident_rows=[incident_row],
        profile="fixture",
    )
    assert "EVENT OPPORTUNITY AUDIT" in report
    assert "## Incident" in report
    assert "SpaceX proxy attention" in report
    assert "market reaction vs causal mechanism" in report
    assert "## What would upgrade this candidate" in report
    assert "## What would downgrade / invalidate this candidate" in report
    assert "No secrets, Telegram sends, trades" in report


def test_event_incident_context_appears_in_daily_brief_and_cards():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    incident_row = {
        "row_type": "event_incident",
        "profile": "quality_validation",
        "run_mode": "test",
        "artifact_namespace": "quality_validation",
        "incident_id": "incident:rune",
        "canonical_name": "THORChain exploit security event",
        "event_archetype": "exploit_security_event",
        "primary_subject": "THORChain",
        "affected_ecosystem": "THORChain",
        "current_cause_status": "confirmed",
        "claim_history": [{"claim_type": "exploit", "polarity": "asserted", "cause_status": "confirmed"}],
        "source_update_count": 2,
        "independent_source_count": 2,
        "linked_assets": [{"symbol": "RUNE", "coin_id": "thorchain", "role": "direct_subject"}],
        "market_reaction_confirmed": True,
        "causal_mechanism_confirmed": True,
        "market_context_source": "candidate_event_market_snapshot",
        "incident_confidence": 91,
    }
    brief = event_alpha_daily_brief.build_daily_brief(
        incident_rows=[incident_row],
        requested_profile="quality_validation",
        artifact_namespace="quality_validation",
        include_test_artifacts=True,
    )
    assert "## Canonical Incidents" in brief
    assert "THORChain exploit security event" in brief
    assert "confirmed=1" in brief

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|incident:rune|security_or_regulatory_shock",
        cluster_id="incident:rune",
        event_id="hyp:rune",
        coin_id="thorchain",
        symbol="RUNE",
        relationship_type="impact_hypothesis",
        external_asset="THORChain",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=event_watchlist.EventWatchlistState.HYPOTHESIS.value,
        first_seen_at="2026-06-26T12:00:00+00:00",
        last_seen_at="2026-06-26T12:00:00+00:00",
        source_count=2,
        highest_score=82,
        latest_score=82,
        latest_tier="RADAR_DIGEST",
        latest_event_name="THORChain RUNE exploit validated",
        latest_source="impact_hypothesis",
        latest_playbook_type="security_or_regulatory_shock",
        latest_effective_playbook_type="direct_event",
        latest_score_components={
            "hypothesis_id": "hyp:rune",
            "incident_id": "incident:rune",
            "canonical_incident_name": "THORChain exploit security event",
            "event_archetype": "exploit_security_event",
            "primary_subject": "THORChain",
            "affected_ecosystem": "THORChain",
            "cause_status": "confirmed",
            "claim_polarities": ["asserted"],
            "claim_history": incident_row["claim_history"],
            "independent_source_domains": ["source-a.example", "source-b.example"],
            "conflicting_claims": [],
            "incident_confidence": 91,
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "validated_asset": {"symbol": "RUNE", "coin_id": "thorchain", "name": "THORChain"},
            "impact_path_type": "exploit_security_event",
            "impact_path_strength": "strong",
            "impact_path_reason": "exploit_security_event",
            "candidate_role": "direct_subject",
            "role_confidence": 0.9,
            "role_evidence": ["candidate_named_as_primary_subject"],
            "market_context_source": "candidate_event_market_snapshot",
            "market_context_age_seconds": 600,
            "market_context_data_quality": "fresh",
            "market_reaction_confirmed": True,
            "causal_mechanism_confirmed": True,
            "market_confirmation_level": "strong",
            "market_confirmation_score": 78,
            "evidence_quality_score": 82,
            "source_class": "crypto_news",
            "evidence_specificity": "direct_token_mechanism",
            "opportunity_score_final": 82,
            "opportunity_level": "watchlist",
            "opportunity_verdict_reasons": ["confirmed_direct_incident"],
            "manual_verification_items": ["verify incident source"],
        },
        should_alert=True,
    )
    card = event_research_cards.render_research_card(
        "ea:" + entry.key,
        watchlist_entries=[entry],
    )
    assert "## Impact Hypothesis Context" in card.markdown
    assert "Incident confidence: 91" in card.markdown
    assert "Claim history: exploit:asserted/confirmed" in card.markdown
    assert "Market context source: candidate_event_market_snapshot (fresh; age=10m; cap_applied=false)" in card.markdown
