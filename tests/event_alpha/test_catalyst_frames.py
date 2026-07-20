"""Focused Event Alpha catalyst-frame and downstream role tests."""

from __future__ import annotations

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_catalyst_frames_separate_main_background_and_negation():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as event_catalyst_frames
    import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
    import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
    from crypto_rsi_scanner.event_core.models import NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body, *, external="Aave"):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture_news",
            fetched_at=now,
            published_at=now,
            source_url=f"https://alpha.example/{raw_id}",
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.90,
            content_hash=raw_id,
        ), NormalizedEvent(
            event_id=f"evt_{raw_id}",
            raw_ids=(raw_id,),
            event_name=title,
            event_type="news",
            event_time=None,
            event_time_confidence=0.0,
            first_seen_time=now,
            source="fixture_news",
            source_urls=(f"https://alpha.example/{raw_id}",),
            external_asset=external,
            description=title,
            confidence=0.90,
        )

    aave_raw, aave_event = raw(
        "aave_kraken",
        "Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        "The DeFi lender is rebuilding after the fallout from April's KelpDAO exploit "
        "sparked a multibillion-dollar exodus of deposits despite Aave itself not being hacked.",
    )
    frames = event_catalyst_frames.build_catalyst_frames((aave_raw,), event=aave_event)
    main, supporting = event_catalyst_frames.select_main_catalyst_frame(frames, aave_event)
    assert main is not None
    assert main.frame_role == "main_catalyst"
    assert main.frame_type == "acquisition_or_stake"
    assert main.subject == "Aave"
    assert main.actor == "Kraken"
    assert any(frame.frame_type == "prior_exploit_context" and frame.subject == "KelpDAO" for frame in supporting)
    assert any(frame.frame_type == "denied_or_negated_exploit" and frame.subject == "Aave" for frame in frames)
    aave_claims = event_claim_semantics.extract_event_claims((aave_raw,))
    assert event_claim_semantics.has_ruled_out_claim(aave_claims, "exploit")
    aave_incident = event_incident_graph.build_incidents((aave_event,), {"aave_kraken": aave_raw})[0]
    assert aave_incident.event_archetype == "strategic_investment"
    assert aave_incident.primary_subject == "Aave"
    assert aave_incident.main_frame_type == "acquisition_or_stake"
    assert aave_incident.background_frame_ids
    assert aave_incident.negated_frame_ids
    assert "KelpDAO" in (aave_incident.background_context_summary or "")

    thor_raw, thor_event = raw(
        "thor_exploit",
        "THORChain suffers exploit and RUNE resumes trading",
        "THORChain exploit drained funds before RUNE resumed trading.",
        external="THORChain",
    )
    thor_incident = event_incident_graph.build_incidents((thor_event,), {"thor_exploit": thor_raw})[0]
    assert thor_incident.event_archetype == "exploit_security_event"
    assert thor_incident.main_frame_type == "exploit_security_event"
    assert thor_incident.current_cause_status == "confirmed"

    meme_raw, meme_event = raw(
        "memecore_no_exploit",
        "MemeCore's M token crashes 80% with no exploit or announcement to explain it",
        "No exploit or announcement explains the M token selloff; cause unknown.",
        external="MemeCore",
    )
    meme_frames = event_catalyst_frames.build_catalyst_frames((meme_raw,), event=meme_event)
    meme_main, _ = event_catalyst_frames.select_main_catalyst_frame(meme_frames, meme_event)
    assert meme_main is not None
    assert meme_main.frame_type == "market_dislocation_unknown"
    assert any(frame.frame_type == "denied_or_negated_exploit" for frame in meme_frames)
    meme_incident = event_incident_graph.build_incidents((meme_event,), {"memecore_no_exploit": meme_raw})[0]
    assert meme_incident.event_archetype == "market_dislocation_unknown"
    assert meme_incident.current_cause_status == "ruled_out"


def test_aave_kraken_hypothesis_uses_strategic_frame_in_cards_and_audit():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
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

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="aave_kraken",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/aave-kraken",
        title="Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        body=(
            "The DeFi lender is rebuilding after the fallout from April's KelpDAO exploit "
            "sparked a multibillion-dollar exodus of deposits despite Aave itself not being hacked."
        ),
        raw_json={"market": {}},
        source_confidence=0.90,
        content_hash="aave_kraken",
    )
    event = NormalizedEvent(
        event_id="evt_aave_kraken",
        raw_ids=("aave_kraken",),
        event_name="Kraken stake in Aave",
        event_type="news",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source="fixture_news",
        source_urls=("https://alpha.example/aave-kraken",),
        external_asset="Aave",
        description=raw.title,
        confidence=0.90,
    )
    asset = DiscoveredAsset("aave", "AAVE", "Aave")
    link = EventAssetLink("evt_aave_kraken", "aave", "AAVE", "Aave", 0.95, "fixture", ("Aave",))
    classification = EventClassification(
        "evt_aave_kraken",
        "aave",
        False,
        True,
        "direct_token_event",
        0.90,
        "fixture",
        "Aave named as DeFi lender in strategic stake article",
        ("Aave",),
    )
    candidate = DiscoveredEventFadeCandidate(event, asset, link, classification, None, None, {})
    discovery = EventDiscoveryResult((raw,), (event,), (link,), (classification,), (candidate,))

    hypotheses = event_impact_hypotheses.generate_impact_hypotheses(discovery, taxonomy={}, now=now)
    hypothesis = next(item for item in hypotheses if item.validated_candidate_assets)
    assert hypothesis.impact_category == "strategic_investment_or_valuation"
    assert hypothesis.impact_path_type == "strategic_investment_or_valuation"
    assert hypothesis.impact_path_reason == "strategic_investment"
    assert hypothesis.candidate_role == "direct_subject"
    assert hypothesis.event_archetype == "strategic_investment"
    assert hypothesis.main_frame_type == "acquisition_or_stake"
    assert hypothesis.background_frame_ids
    assert hypothesis.negated_frame_ids
    assert any("prior_exploit_context" in item for item in hypothesis.rejected_impact_paths)
    assert any("denied_or_negated_exploit" in item for item in hypothesis.rejected_impact_paths)
    assert hypothesis.opportunity_level == "validated_digest"
    assert hypothesis.why_not_watchlist == "market_confirmation"
    assert hypothesis.impact_path_type != "exploit_security_event"

    with tempfile.TemporaryDirectory() as tmp:
        watch = event_watchlist.refresh_hypothesis_watchlist(
            [hypothesis],
            cfg=event_watchlist.EventWatchlistConfig(enabled=True, state_path=Path(tmp) / "watch.jsonl"),
            now=now,
        )
    entry = watch.entries[0]
    assert entry.state == event_watchlist.EventWatchlistState.RADAR.value
    assert entry.latest_score_components["main_frame_type"] == "acquisition_or_stake"
    assert "KelpDAO" in entry.latest_score_components["background_context_summary"]
    card = event_research_cards.render_research_card(entry.key, watchlist_entries=[entry])
    assert "Main catalyst: acquisition_or_stake" in card.markdown
    assert "Frame status:" in card.markdown
    assert "prior_exploit_context(KelpDAO)" in card.markdown
    assert "denied_or_negated_exploit" in card.markdown
    assert "Rejected/background impact paths:" in card.markdown
    assert "validated strategic investment / valuation catalyst" in card.markdown
    assert "Talks are denied" in card.markdown
    assert "event/catalyst relationship needs manual review" not in card.markdown
    assert "Source evidence fails identity/catalyst review" not in card.markdown
    audit = event_opportunity_audit.format_opportunity_audit(
        entry.key,
        hypotheses=[hypothesis],
        watchlist_entries=[entry],
        profile="quality_validation",
    )
    assert "main catalyst frame: acquisition_or_stake" in audit
    assert "frame status:" in audit
    assert "background context: background: prior_exploit_context(KelpDAO)" in audit
    assert "negated/corrective frame count: 1" in audit
    assert "rejected/background impact paths:" in audit


def test_llm_catalyst_frame_fixture_validation_and_downstream_use():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator as event_catalyst_frame_validator
    import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as event_catalyst_frames
    import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
    import crypto_rsi_scanner.event_alpha.radar.impact_path_validator as event_impact_path_validator
    import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
    from crypto_rsi_scanner.event_core.models import NormalizedEvent, RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMCatalystFrameProvider

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body, *, external="Aave"):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture_news",
            fetched_at=now,
            published_at=now,
            source_url=f"https://alpha.example/{raw_id}",
            title=title,
            body=body,
            raw_json={},
            source_confidence=0.90,
            content_hash=raw_id,
        ), NormalizedEvent(
            event_id=f"evt_{raw_id}",
            raw_ids=(raw_id,),
            event_name=title,
            event_type="news",
            event_time=None,
            event_time_confidence=0.0,
            first_seen_time=now,
            source="fixture_news",
            source_urls=(f"https://alpha.example/{raw_id}",),
            external_asset=external,
            description=body,
            confidence=0.90,
        )

    provider = FixtureLLMCatalystFrameProvider(required=True)
    cfg = event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
        enabled=True,
        max_rows_per_run=10,
        min_source_score=0.0,
        only_ambiguous=False,
    )
    aave_raw, aave_event = raw(
        "aave_kraken",
        "Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        "The DeFi lender is rebuilding after the fallout from April's KelpDAO exploit "
        "sparked a multibillion-dollar exodus of deposits despite Aave itself not being hacked.",
    )
    report = event_llm_catalyst_frames.analyze_raw_events((aave_raw,), provider, cfg=cfg)
    assert report and report[0].analysis is not None
    analysis = report[0].analysis
    assert analysis.main_catalyst_frame is not None
    assert analysis.main_catalyst_frame.frame_type == "acquisition_or_stake"
    assert analysis.background_frames[0].frame_type == "prior_exploit_context"
    assert analysis.negated_or_corrective_frames[0].frame_type == "denied_or_negated_exploit"

    rule_exploit = event_catalyst_frames.EventCatalystFrame(
        frame_id="rule:exploit",
        frame_type="exploit_security_event",
        frame_role="main_catalyst",
        subject="Aave",
        event_archetype="exploit_security_event",
        claim_polarity="asserted",
        cause_status="confirmed",
        confidence=0.80,
        evidence_quote="KelpDAO exploit",
    )
    validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(
        analysis,
        (aave_raw,),
        event=aave_event,
        rule_frames=(rule_exploit,),
    )
    assert validation.selected_main_frame is not None
    assert validation.selected_main_frame.frame_type == "acquisition_or_stake"
    assert validation.frame_rule_disagreement is True
    assert validation.resolution == "llm_wins"
    assert any("prior_exploit_context" in item for item in validation.rejected_impact_paths)
    assert any("denied_or_negated_exploit" in item for item in validation.rejected_impact_paths)

    enriched_raw = event_catalyst_frame_validator.apply_validation_to_raw_event(aave_raw, analysis, validation)
    incident = event_incident_graph.build_incidents((aave_event,), {enriched_raw.raw_id: enriched_raw})[0]
    assert incident.event_archetype == "strategic_investment"
    assert incident.main_frame_type == "acquisition_or_stake"
    assert incident.main_frame_role == "main_catalyst"
    assert incident.main_frame_subject == "Aave"
    assert incident.main_frame_actor == "Kraken"
    assert "15% stake" in (incident.main_frame_object or "")
    assert "Kraken in talks" in (incident.main_frame_evidence_quote or "")
    assert incident.background_frame_ids
    assert incident.corrective_frame_ids
    assert incident.frame_rule_disagreement is True
    assert incident.rule_predicted_impact_path == "exploit_security_event"
    assert incident.llm_predicted_main_frame_type == "acquisition_or_stake"
    assert incident.disagreement_resolution == "llm_wins"
    impact = event_impact_path_validator.validate_impact_path(
        enriched_raw,
        SimpleNamespace(impact_category="security_or_regulatory_shock", external_asset="Aave", score_components={}),
        symbol="AAVE",
        coin_id="aave",
    )
    assert impact.impact_path_type == "strategic_investment_or_valuation"
    assert impact.impact_path_type != "exploit_security_event"

    thor_raw, _ = raw(
        "thor_exploit",
        "THORChain suffers exploit and RUNE resumes trading",
        "THORChain exploit drained funds before RUNE resumed trading.",
        external="THORChain",
    )
    thor_report = event_llm_catalyst_frames.analyze_raw_events((thor_raw,), provider, cfg=cfg)
    thor_validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(thor_report[0].analysis, (thor_raw,))
    assert thor_validation.selected_main_frame is not None
    assert thor_validation.selected_main_frame.frame_type == "exploit_security_event"
    assert thor_validation.frame_rule_disagreement is False


def test_llm_catalyst_frame_runtime_deadline_skips_and_bounds_timeout():
    from datetime import datetime, timedelta, timezone
    import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.base import LLMProviderResult

    now = datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="aave_kraken_deadline",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/aave-deadline",
        title="Kraken considers strategic stake in Aave",
        body="Kraken could acquire a stake in Aave after earlier exploit context.",
        raw_json={},
        source_confidence=0.90,
        content_hash="aave_kraken_deadline",
    )

    class ProbeProvider:
        name = "probe"

        def __init__(self):
            self.timeout = 30.0
            self.calls = 0
            self.seen_timeouts = []

        def analyze_catalyst_frames(self, packet):
            self.calls += 1
            self.seen_timeouts.append(float(self.timeout))
            return LLMProviderResult(warning="probe warning")

    expired_provider = ProbeProvider()
    expired_rows = event_llm_catalyst_frames.analyze_raw_events(
        (raw,),
        expired_provider,
        cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=True,
            max_rows_per_run=1,
            min_source_score=0.0,
            only_ambiguous=False,
            deadline_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        ),
    )
    assert expired_provider.calls == 0
    assert expired_rows
    assert any("runtime deadline exhausted" in warning for warning in expired_rows[0].warnings)

    bounded_provider = ProbeProvider()
    bounded_rows = event_llm_catalyst_frames.analyze_raw_events(
        (raw,),
        bounded_provider,
        cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=True,
            max_rows_per_run=1,
            min_source_score=0.0,
            only_ambiguous=False,
            deadline_at=datetime.now(timezone.utc) + timedelta(seconds=5),
        ),
    )
    assert bounded_provider.calls == 1
    assert bounded_rows and any("probe warning" in warning for warning in bounded_rows[0].warnings)
    assert 1.0 <= bounded_provider.seen_timeouts[0] <= 5.0
    assert bounded_provider.timeout == 30.0


def test_event_alpha_operating_cycle_applies_llm_catalyst_frame_validation():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as event_catalyst_frames
    import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
    import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMCatalystFrameProvider

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="aave_kraken",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/aave",
        title="Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        body=(
            "The DeFi lender is rebuilding after the fallout from April's KelpDAO exploit "
            "sparked a multibillion-dollar exodus of deposits despite Aave itself not being hacked."
        ),
        raw_json={},
        source_confidence=0.90,
        content_hash="aave_kraken",
    )
    event = NormalizedEvent(
        event_id="evt_aave_kraken",
        raw_ids=("aave_kraken",),
        event_name=raw.title,
        event_type="news",
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=now,
        source="fixture_news",
        source_urls=(raw.source_url or "",),
        external_asset="Aave",
        description=raw.body,
        confidence=0.90,
    )

    def load_discovery_result(observed, raw_event_transform):
        raw_events = (raw,)
        if raw_event_transform is not None:
            raw_events = tuple(raw_event_transform(raw_events))
        return EventDiscoveryResult(
            raw_events=raw_events,
            normalized_events=(event,),
            links=(),
            classifications=(),
            candidates=(),
        )

    result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=load_discovery_result,
        now=now,
        with_llm=True,
        catalyst_frame_provider=FixtureLLMCatalystFrameProvider(required=True),
        catalyst_frame_cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=True,
            max_rows_per_run=10,
            min_source_score=0.0,
            only_ambiguous=False,
        ),
        refresh_watchlist=False,
        route=False,
    )

    assert result.catalyst_frame_analyses == 1
    assert result.catalyst_frame_validations_applied == 1
    enriched_raw = result.discovery_result.raw_events[0]
    validation = enriched_raw.raw_json["llm_catalyst_frame_validation"]
    assert validation["selected_main_frame"]["frame_type"] == "acquisition_or_stake"
    assert validation["rule_predicted_impact_path"] == "acquisition_or_stake"
    assert validation["llm_predicted_main_frame_type"] == "acquisition_or_stake"
    frames = event_catalyst_frames.build_catalyst_frames((enriched_raw,), event=event)
    selected_main, supporting_frames = event_catalyst_frames.select_main_catalyst_frame(frames)
    assert selected_main is not None
    assert selected_main.frame_type == "acquisition_or_stake"
    assert any(frame.frame_type == "prior_exploit_context" for frame in supporting_frames)
    incident = event_incident_graph.build_incidents((event,), {enriched_raw.raw_id: enriched_raw})[0]
    assert incident.event_archetype == "strategic_investment"
    assert incident.background_frame_ids
    assert incident.main_frame_subject == "Aave"
    assert incident.corrective_frame_ids


def test_llm_catalyst_frame_validator_rejects_bad_quotes_and_identity_noise():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator as event_catalyst_frame_validator
    import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMCatalystFrameProvider

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    invalid_raw = RawDiscoveredEvent(
        raw_id="invalid_quote",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/invalid",
        title="Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        body="The source says Aave itself was not hacked.",
        raw_json={},
        source_confidence=0.90,
        content_hash="invalid_quote",
    )
    cfg = event_llm_catalyst_frames.EventLLMCatalystFrameConfig(enabled=True, only_ambiguous=False, min_source_score=0.0)
    provider = FixtureLLMCatalystFrameProvider(required=True)
    report = event_llm_catalyst_frames.analyze_raw_events((invalid_raw,), provider, cfg=cfg)
    validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(report[0].analysis, (invalid_raw,))
    assert validation.selected_main_frame is None
    assert validation.invalid_frames[0]["reason"] == "llm_frame_quote_not_found"

    packet = event_llm_catalyst_frames.build_catalyst_frame_packet(invalid_raw, cfg=cfg)
    openai_noise = event_llm_catalyst_frames.parse_catalyst_frame_analysis(
        {
            "main_catalyst_frame": {
                "frame_type": "proxy_attention",
                "frame_role": "main_catalyst",
                "subject": "OpenAI",
                "actor": None,
                "object": "pre-IPO mention",
                "affected_entities": ["OpenAI"],
                "affected_assets": ["OpenAI"],
                "event_archetype": "proxy_attention",
                "claim_polarity": "asserted",
                "cause_status": "unknown",
                "confidence": 0.80,
                "evidence_quote": "Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
                "why_this_role": "identity-noise test",
            },
            "background_frames": [],
            "negated_or_corrective_frames": [],
            "external_entities": ["OpenAI"],
            "crypto_assets": ["OpenAI"],
            "rejected_impact_paths": [],
            "manual_verification_items": [],
            "semantic_confidence": 0.70,
            "warnings": [],
        },
        packet=packet,
        cfg=cfg,
    )
    openai_validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(openai_noise, (invalid_raw,))
    assert openai_validation.invalid_frames[0]["reason"] == "external_entity_cannot_be_crypto_asset"

    hype_noise = event_llm_catalyst_frames.parse_catalyst_frame_analysis(
        {
            "main_catalyst_frame": {
                "frame_type": "proxy_attention",
                "frame_role": "main_catalyst",
                "subject": "HYPE",
                "actor": None,
                "object": "IPO hype",
                "affected_entities": ["HYPE"],
                "affected_assets": ["HYPE"],
                "event_archetype": "proxy_attention",
                "claim_polarity": "asserted",
                "cause_status": "unknown",
                "confidence": 0.80,
                "evidence_quote": "Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
                "why_this_role": "generic ticker-noise test",
            },
            "background_frames": [],
            "negated_or_corrective_frames": [],
            "external_entities": [],
            "crypto_assets": ["HYPE"],
            "rejected_impact_paths": [],
            "manual_verification_items": [],
            "semantic_confidence": 0.70,
            "warnings": [],
        },
        packet=packet,
        cfg=cfg,
    )
    hype_validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(hype_noise, (invalid_raw,))
    assert hype_validation.invalid_frames[0]["reason"] == "ticker_word_collision_rejected"


def test_llm_catalyst_frames_bind_one_raw_hash_field_and_exact_span():
    from dataclasses import replace
    from datetime import datetime, timezone

    import pytest

    import crypto_rsi_scanner.event_alpha.radar.catalyst_frame_binding as event_catalyst_frame_binding
    import crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator as event_catalyst_frame_validator
    import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as event_catalyst_frames
    import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
    import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)

    def raw(raw_id, title, body="", *, content_hash=None, raw_json=None):
        return RawDiscoveredEvent(
            raw_id=raw_id,
            provider="fixture_news",
            fetched_at=now,
            published_at=now,
            source_url=f"https://alpha.example/{raw_id}",
            title=title,
            body=body,
            raw_json=raw_json or {},
            source_confidence=0.90,
            content_hash=content_hash or f"hash:{raw_id}",
        )

    first = raw("first", "Alpha source reports an unrelated protocol upgrade")
    second = raw("second", "Beta exchange lists TEST token today")
    frame = event_llm_catalyst_frames.EventLLMCatalystFrame(
        frame_type="listing_liquidity_event",
        frame_role="main_catalyst",
        subject="TEST",
        actor="the Beta Exchange",
        affected_entities=("TEST",),
        event_archetype="listing_liquidity_event",
        claim_polarity="asserted",
        cause_status="confirmed",
        confidence=0.91,
        evidence_quote="  BETA exchange   lists TEST token TODAY  ",
        found_in_source=True,
    )
    analysis = event_llm_catalyst_frames.EventLLMCatalystFrameAnalysis(
        schema_version=event_llm_catalyst_frames.LLM_CATALYST_FRAME_SCHEMA_VERSION,
        provider="fixture",
        model=None,
        prompt_version="test",
        raw_id=second.raw_id,
        main_catalyst_frame=frame,
    )

    validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(
        analysis,
        (first, second),
    )
    assert validation.source_raw_id == second.raw_id
    assert validation.source_provider == second.provider
    assert validation.source_url == second.source_url
    assert validation.source_published_at == second.published_at.isoformat()
    assert validation.source_content_hash == second.content_hash
    assert validation.source_surface_hash == event_catalyst_frame_binding.source_surface_hash(second)
    assert validation.selected_main_frame is not None
    assert validation.selected_main_frame.source_raw_id == second.raw_id
    assert validation.selected_main_frame.evidence_source_field == "title"
    assert validation.selected_main_frame.evidence_normalized_start == 0
    assert validation.selected_main_frame.evidence_normalized_end == len(second.title.casefold())

    stored = event_catalyst_frame_validator.apply_validation_to_raw_event(second, analysis, validation)
    serialized = stored.raw_json["llm_catalyst_frame_validation"]
    assert serialized["schema_version"] == "event_llm_catalyst_frame_validation_v2"
    assert serialized["valid_frames"][0]["evidence_quote"] == frame.evidence_quote
    rehydrated = tuple(
        item for item in event_catalyst_frames.build_catalyst_frames((stored,))
        if item.frame_id.startswith("frame:llm:")
    )
    assert len(rehydrated) == 1
    assert rehydrated[0].evidence_quote == frame.evidence_quote
    assert rehydrated[0].actor == frame.actor
    assert event_catalyst_frames.frame_summary(rehydrated)[0] == serialized["valid_frames"][0]

    long_quote = "TEST Beta exchange evidence " + ("very " * 80) + "specific catalyst"
    long_raw = raw("long_quote", "Long source report", long_quote)
    long_analysis = replace(
        analysis,
        raw_id=long_raw.raw_id,
        main_catalyst_frame=replace(frame, evidence_quote=long_quote),
    )
    long_validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(
        long_analysis,
        (long_raw,),
    )
    long_stored = event_catalyst_frame_validator.apply_validation_to_raw_event(
        long_raw,
        long_analysis,
        long_validation,
    )
    long_rehydrated = tuple(
        item for item in event_catalyst_frames.build_catalyst_frames((long_stored,))
        if item.frame_id.startswith("frame:llm:")
    )
    assert len(long_quote) > 320
    assert long_rehydrated[0].evidence_quote == long_quote

    wrong_raw = replace(analysis, raw_id=first.raw_id)
    wrong_validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(
        wrong_raw,
        (first, second),
    )
    assert not wrong_validation.valid_frames
    assert wrong_validation.invalid_frames[0]["reason"] == "llm_frame_quote_not_found"
    with pytest.raises(ValueError, match="raw_id does not match"):
        event_catalyst_frame_validator.apply_validation_to_raw_event(first, analysis, validation)
    with pytest.raises(ValueError, match="selected catalyst frame binding"):
        event_catalyst_frame_validator.apply_validation_to_raw_event(
            second,
            analysis,
            replace(
                validation,
                selected_main_frame=replace(
                    validation.selected_main_frame,
                    evidence_normalized_start=1,
                ),
            ),
        )

    for raw_id, raws, expected_reason in (
        ("", (first, second), "llm_frame_analysis_raw_id_missing"),
        ("missing", (first, second), "llm_frame_analysis_raw_id_not_found"),
        (second.raw_id, (second, replace(second, source_url="https://beta.example/duplicate")),
         "llm_frame_analysis_raw_id_not_unique"),
    ):
        invalid = event_catalyst_frame_validator.validate_llm_catalyst_frames(
            replace(analysis, raw_id=raw_id),
            raws,
        )
        assert not invalid.valid_frames
        assert invalid.invalid_frames[0]["reason"] == expected_reason

    reordered = replace(
        analysis,
        main_catalyst_frame=replace(frame, evidence_quote="Beta TEST token exchange lists today"),
    )
    assert event_catalyst_frame_validator.validate_llm_catalyst_frames(
        reordered,
        (second,),
    ).invalid_frames[0]["reason"] == "llm_frame_quote_not_found"

    split = raw("split", "Beta exchange lists", "TEST token today")
    split_analysis = replace(
        analysis,
        raw_id=split.raw_id,
        main_catalyst_frame=replace(frame, evidence_quote="Beta exchange lists TEST token today"),
    )
    assert event_catalyst_frame_validator.validate_llm_catalyst_frames(
        split_analysis,
        (split,),
    ).invalid_frames[0]["reason"] == "llm_frame_quote_not_found"

    rejected_enrichment = raw(
        "rejected_enrichment",
        "Generic article",
        raw_json={
            "source_enrichment": {
                "article_quality_status": "paywall_or_blocked",
                "enriched_text": "Beta exchange lists TEST token today",
            },
        },
    )
    rejected_analysis = replace(analysis, raw_id=rejected_enrichment.raw_id)
    assert event_catalyst_frame_validator.validate_llm_catalyst_frames(
        rejected_analysis,
        (rejected_enrichment,),
    ).invalid_frames[0]["reason"] == "llm_frame_quote_not_found"

    accepted_enrichment = replace(
        rejected_enrichment,
        raw_id="accepted_enrichment",
        content_hash="hash:accepted_enrichment",
        raw_json={
            "source_enrichment": {
                "article_quality_status": "good",
                "enriched_text": "Beta exchange lists TEST token today",
            },
        },
    )
    accepted_analysis = replace(analysis, raw_id=accepted_enrichment.raw_id)
    accepted_validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(
        accepted_analysis,
        (accepted_enrichment,),
    )
    assert accepted_validation.valid_frames[0].evidence_source_field == "enriched_text"

    parser_packet = event_llm_catalyst_frames.build_catalyst_frame_packet(second)
    parser_result = event_llm_catalyst_frames.parse_catalyst_frame_analysis(
        {
            "main_catalyst_frame": {
                "frame_type": "listing_liquidity_event",
                "frame_role": "main_catalyst",
                "subject": "TEST",
                "actor": "Beta exchange",
                "object": "listing",
                "affected_entities": ["TEST"],
                "affected_assets": [],
                "event_archetype": "listing_liquidity_event",
                "claim_polarity": "asserted",
                "cause_status": "confirmed",
                "confidence": 0.9,
                "evidence_quote": "Beta TEST token exchange lists today",
                "why_this_role": "parser exact-match regression",
            },
            "background_frames": [],
            "negated_or_corrective_frames": [],
            "external_entities": [],
            "crypto_assets": [],
            "rejected_impact_paths": [],
            "manual_verification_items": [],
            "semantic_confidence": 0.9,
            "warnings": [],
        },
        packet=parser_packet,
    )
    assert parser_result.main_catalyst_frame is not None
    assert parser_result.main_catalyst_frame.found_in_source is False
    assert "quote_not_found:listing_liquidity_event:main_catalyst" in parser_result.warnings

    for mutated in (
        replace(stored, title="Beta exchange delists TEST token today"),
        replace(stored, content_hash="different-content-hash"),
        replace(stored, provider="different_provider"),
        replace(stored, source_url="https://beta.example/moved"),
    ):
        assert not any(
            item.frame_id.startswith("frame:llm:")
            for item in event_catalyst_frames.build_catalyst_frames((mutated,))
        )

    tampered_payload = dict(stored.raw_json)
    tampered_validation = dict(tampered_payload["llm_catalyst_frame_validation"])
    tampered_frames = [dict(item) for item in tampered_validation["valid_frames"]]
    tampered_frames[0]["evidence_normalized_start"] = 1
    tampered_validation["valid_frames"] = tampered_frames
    tampered_payload["llm_catalyst_frame_validation"] = tampered_validation
    tampered = replace(stored, raw_json=tampered_payload)
    assert event_catalyst_frame_binding.current_validation_for_raw(tampered) is None
    assert not any(
        item.frame_id.startswith("frame:llm:")
        for item in event_catalyst_frames.build_catalyst_frames((tampered,))
    )
    assert event_incident_graph._frame_validation_metadata((tampered,)) == {
        "rule_predicted_impact_path": None,
        "llm_predicted_main_frame_type": None,
        "frame_rule_disagreement": False,
        "disagreement_resolution": None,
    }

    legacy_payload = {
        "llm_catalyst_frame_validation": {
            "valid_frames": serialized["valid_frames"],
        },
    }
    assert not any(
        item.frame_id.startswith("frame:llm:")
        for item in event_catalyst_frames.build_catalyst_frames((replace(second, raw_json=legacy_payload),))
    )


def test_signal_quality_fixture_rehydrates_bound_llm_frames():
    import crypto_rsi_scanner.event_alpha.outcomes.quality as event_signal_quality
    import crypto_rsi_scanner.event_alpha.outcomes.quality.case_eval as event_signal_quality_cases
    import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as event_catalyst_frames

    case = next(
        item for item in event_signal_quality.load_signal_quality_cases()
        if item["case_id"] == "aave_kraken_kelpdao_background"
    )
    raw = event_signal_quality_cases._raw_event(case)
    frames = tuple(
        frame for frame in event_catalyst_frames.build_catalyst_frames((raw,))
        if frame.frame_id.startswith("frame:llm:")
    )
    assert len(frames) == 3
    assert {frame.source_raw_id for frame in frames} == {raw.raw_id}
    assert {frame.source_content_hash for frame in frames} == {raw.content_hash}
    assert all(frame.source_surface_hash for frame in frames)
    assert {frame.evidence_source_field for frame in frames} == {"title", "body"}


def test_north_star_records_exact_llm_catalyst_frame_binding_policy():
    from crypto_rsi_scanner.project_health import radar_north_star

    payload = radar_north_star.build_north_star()
    policy = payload["llm_catalyst_frame_binding_policy"]
    assert policy["analysis_raw_resolution"] == "exactly_one_matching_raw_id_required"
    assert policy["cross_raw_event_or_cross_field_quote_matching"] is False
    assert policy["fuzzy_term_overlap_allowed"] is False
    assert policy["provider_output_schema_changed"] is False
    assert policy["legacy_unbound_frames"] == "historical_bytes_preserved_but_not_current_evidence"
    assert "source_surface_hash" in policy["binding_fields"]
    assert "## LLM Catalyst-Frame Source Binding" in radar_north_star.format_north_star(payload)


def test_llm_catalyst_frame_profiles_make_target_and_missing_key_fail_soft():
    import subprocess
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles
    from crypto_rsi_scanner.llm_providers.openai_provider import OpenAILLMRelationshipProvider

    assert event_alpha_profiles.get_profile("notify_no_key").config_overrides["EVENT_LLM_CATALYST_FRAMES_ENABLED"] is False
    assert event_alpha_profiles.get_profile("notify_llm_quality").config_overrides["EVENT_LLM_CATALYST_FRAMES_ENABLED"] is True
    assert event_alpha_profiles.get_profile("notify_llm_deep").config_overrides["EVENT_LLM_CATALYST_FRAMES_ENABLED"] is True
    assert event_alpha_profiles.get_profile("notify_llm_deep").config_overrides["EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN"] == 60
    assert event_alpha_profiles.get_profile("notify_llm_deep").config_overrides["EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED"] is True
    assert event_alpha_profiles.get_profile("full_llm_live").config_overrides["EVENT_LLM_CATALYST_FRAMES_ENABLED"] is True
    assert event_alpha_profiles.get_profile("catalyst_frame_validation").config_overrides["EVENT_LLM_CATALYST_FRAMES_PROVIDER"] == "fixture"
    assert event_alpha_profiles.get_profile("catalyst_frame_validation").with_llm is True
    e2e = event_alpha_profiles.get_profile("catalyst_frame_e2e")
    assert e2e.with_llm is True
    assert e2e.send is False
    assert e2e.config_overrides["EVENT_LLM_CATALYST_FRAMES_PROVIDER"] == "fixture"
    assert str(e2e.config_overrides["EVENT_DISCOVERY_EVENTS_PATH"]).endswith("catalyst_frame_e2e_events.json")
    assert e2e.config_overrides["EVENT_ANOMALY_SCANNER_ENABLED"] is False
    assert e2e.config_overrides["EVENT_DISCOVERY_UNIVERSE_LIVE"] is False
    quality_frame = event_alpha_profiles.get_profile("notify_llm_quality_frame")
    assert quality_frame.with_llm is True
    assert quality_frame.send is False
    assert quality_frame.config_overrides["EVENT_LLM_CATALYST_FRAMES_PROVIDER"] == "fixture"
    assert quality_frame.config_overrides["EVENT_LLM_CATALYST_FRAMES_ENABLED"] is True
    assert quality_frame.config_overrides["EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED"] is True
    assert quality_frame.config_overrides["EVENT_ALPHA_SNAPSHOT_POLICY"] == "all"
    quality_frame_report = event_alpha_profiles.format_profile_report(quality_frame)
    assert "catalyst-frame behavior:" in quality_frame_report
    assert "- provider=fixture" in quality_frame_report
    assert "official fixture/no-send proof profile" in quality_frame_report
    market_refresh = event_alpha_profiles.get_profile("market_refresh_smoke")
    assert market_refresh.send is False
    assert market_refresh.config_overrides["EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED"] is True
    assert market_refresh.config_overrides["EVENT_WATCHLIST_MONITOR_MARKET_SOURCE"] == "fixture"
    assert str(market_refresh.config_overrides["EVENT_WATCHLIST_MONITOR_MARKET_PATH"]).endswith("market_refresh_smoke_markets.json")
    quality_live_report = event_alpha_profiles.format_profile_report(event_alpha_profiles.get_profile("notify_llm_quality"))
    assert "official live-style frame-enabled quality profile" in quality_live_report
    report = event_alpha_profiles.format_profile_report(event_alpha_profiles.get_profile("notify_llm_deep"))
    assert "EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN=60" in report
    provider = OpenAILLMRelationshipProvider(api_key="")
    result = provider.analyze_catalyst_frames({"raw_id": "missing-key"})
    assert result.raw is None
    assert "missing OPENAI_API_KEY" in (result.warning or "")
    with open("Makefile", encoding="utf-8") as fh:
        text = fh.read()
    assert "event-alpha-catalyst-frame-validation-cycle" in text
    assert "event-alpha-catalyst-frame-e2e-cycle" in text
    assert "event-alpha-notify-llm-quality-frame-smoke" in text
    assert "event-alpha-market-refresh-smoke" in text
    assert "event-alpha-quality-frame-live-smoke" in text
    assert "event-alpha-feedback-readiness" in text
    assert "event-alpha-frame-quality-loop" in text
    dry = subprocess.run(
        ["make", "-n", "event-alpha-quality-frame-live-smoke", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alert-send" not in dry
    assert "--event-alpha-cycle --event-alpha-profile notify_llm_quality" in dry


def test_event_alpha_catalyst_frame_e2e_cycle_writes_frame_artifacts():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner

    original = {
        name: getattr(config, name)
        for name in dir(config)
        if name.startswith(("EVENT_", "TELEGRAM_"))
    }

    def read_jsonl(path):
        return [
            json.loads(line)
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    with tempfile.TemporaryDirectory() as tmp:
        config.EVENT_ALPHA_ARTIFACT_BASE_DIR = Path(tmp)
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = ""
        config.EVENT_ALPHA_RUN_MODE = ""
        config.EVENT_ALERTS_ENABLED = False
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_cycle(profile_name="catalyst_frame_e2e", event_now="2026-06-15T16:00:00Z")
            text = out.getvalue()
            assert "EVENT ALPHA PIPELINE REPORT" in text
            assert "catalyst_frames=5/5" in text
            assert "send_attempted=false" in text
            with contextlib.redirect_stdout(io.StringIO()):
                scanner.event_alpha_daily_brief_report(
                    profile_name="catalyst_frame_e2e",
                    artifact_namespace="catalyst_frame_e2e",
                    include_test_artifacts=True,
            )
            daily_brief = Path(config.EVENT_ALPHA_DAILY_BRIEF_PATH).read_text(encoding="utf-8")
            assert "No run ledger rows found" not in daily_brief
            assert "Selected run profile: catalyst_frame_e2e" in daily_brief
            assert "Selected run namespace: catalyst_frame_e2e" in daily_brief

            incident_rows = read_jsonl(config.EVENT_INCIDENT_STORE_PATH)
            hypothesis_rows = read_jsonl(config.EVENT_IMPACT_HYPOTHESIS_STORE_PATH)
            watchlist_rows = read_jsonl(config.EVENT_WATCHLIST_STATE_PATH)
            run_rows = read_jsonl(config.EVENT_ALPHA_RUN_LEDGER_PATH)
            assert incident_rows
            assert hypothesis_rows
            assert watchlist_rows
            assert run_rows[-1]["profile"] == "catalyst_frame_e2e"
            assert run_rows[-1]["send_requested"] is False
            assert run_rows[-1]["catalyst_frames_analyzed"] == 5
            assert run_rows[-1]["catalyst_frame_validations"] == 5

            aave_incident = next(row for row in incident_rows if row.get("main_frame_subject") == "Aave")
            assert aave_incident["event_archetype"] == "strategic_investment"
            assert aave_incident["main_frame_type"] == "acquisition_or_stake"
            assert aave_incident["main_frame_actor"] == "Kraken"
            assert aave_incident["corrective_frame_ids"]
            assert aave_incident["main_frame_type"] != "exploit_security_event"

            aave_hypothesis = next(row for row in hypothesis_rows if row.get("main_frame_subject") == "Aave")
            assert aave_hypothesis["main_frame_type"] == "acquisition_or_stake"
            assert aave_hypothesis["impact_path_reason"] == "strategic_investment"
            assert aave_hypothesis["impact_path_type"] == "strategic_investment_or_valuation"
            assert "prior_exploit_context:background_for:KelpDAO" in aave_hypothesis["rejected_impact_paths"]
            assert "background_context_not_primary_catalyst" in aave_hypothesis["rejected_impact_paths"]
            assert aave_hypothesis["selected_main_catalyst_reason"]

            thor_incident = next(row for row in incident_rows if row.get("main_frame_subject") == "THORChain")
            assert thor_incident["main_frame_type"] == "exploit_security_event"
            memecore_incident = next(row for row in incident_rows if row.get("main_frame_subject") == "MemeCore")
            assert memecore_incident["event_archetype"] == "market_dislocation_unknown"
            assert all(row.get("latest_tier") != "TRIGGERED_FADE" for row in watchlist_rows)
            card_files = list(Path(config.EVENT_RESEARCH_CARDS_DIR).glob("*.md"))
            assert card_files
            assert "Main catalyst: acquisition_or_stake" in card_files[0].read_text(encoding="utf-8") or any(
                "Main catalyst: acquisition_or_stake" in path.read_text(encoding="utf-8")
                for path in card_files
            )

            notify_out = io.StringIO()
            with contextlib.redirect_stdout(notify_out):
                scanner.event_alpha_cycle(
                    profile_name="notify_llm_quality_frame",
                    event_now="2026-06-15T16:00:00Z",
                )
            notify_text = notify_out.getvalue()
            assert "catalyst_frames=5/5" in notify_text
            notify_run_rows = read_jsonl(config.EVENT_ALPHA_RUN_LEDGER_PATH)
            notify_latest = notify_run_rows[-1]
            assert notify_latest["profile"] == "notify_llm_quality_frame"
            assert notify_latest["send_requested"] is False
            assert isinstance(notify_latest["catalyst_frames_analyzed"], int)
            assert isinstance(notify_latest["catalyst_frame_validations"], int)
            assert isinstance(notify_latest["catalyst_frame_disagreements"], int)
            assert isinstance(notify_latest["catalyst_frame_unresolved"], int)
            assert isinstance(notify_latest["catalyst_frame_rows_skipped"], int)
            assert isinstance(notify_latest["catalyst_frame_skip_reasons"], dict)
            assert notify_latest["catalyst_frames_analyzed"] == 5
            assert notify_latest["catalyst_frame_validations"] == 5
            notify_incidents = read_jsonl(config.EVENT_INCIDENT_STORE_PATH)
            notify_aave = next(row for row in notify_incidents if row.get("main_frame_subject") == "Aave")
            assert notify_aave["event_archetype"] == "strategic_investment"
            assert notify_aave["main_frame_type"] == "acquisition_or_stake"
            assert notify_aave["main_frame_actor"] == "Kraken"
            assert notify_aave["main_frame_type"] != "exploit_security_event"
        finally:
            for name, value in original.items():
                setattr(config, name, value)


def test_catalyst_frame_missing_provider_records_skip_and_status():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as event_alpha_run_ledger
    import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="aave_kraken",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/aave",
        title="Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        body="The article also references the fallout from a prior KelpDAO exploit despite Aave itself not being hacked.",
        raw_json={},
        source_confidence=0.90,
        content_hash="aave",
    )
    event = NormalizedEvent(
        "evt_aave",
        ("aave_kraken",),
        raw.title,
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (raw.source_url or "",),
        "Aave",
        raw.body,
        0.90,
    )

    def load_discovery_result(observed, raw_event_transform):
        raws = (raw,)
        if raw_event_transform is not None:
            raws = tuple(raw_event_transform(raws))
        return EventDiscoveryResult(raws, (event,), (), (), ())

    result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=load_discovery_result,
        now=now,
        with_llm=True,
        catalyst_frame_provider=None,
        catalyst_frame_cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=True,
            provider="openai",
            only_ambiguous=True,
        ),
        refresh_watchlist=False,
        route=False,
    )
    payload = result.discovery_result.raw_events[0].raw_json
    assert payload["catalyst_frame_required"] is True
    assert payload["catalyst_frame_status"] == "missing_required_frame_analysis"
    assert payload["catalyst_frame_skip_reason"] == "missing_api_key"

    with tempfile.TemporaryDirectory() as tmp:
        row = event_alpha_run_ledger.append_run_record(
            result,
            cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(Path(tmp) / "runs.jsonl"),
            profile="notify_llm_quality",
            started_at=now,
            finished_at=now,
            with_llm=True,
            send_requested=False,
        )
    assert row["catalyst_frames_analyzed"] == 0
    assert row["catalyst_frame_validations"] == 0
    assert row["catalyst_frame_rows_skipped"] == 1
    assert row["catalyst_frame_skip_reasons"]["missing_api_key"] == 1


def test_catalyst_frame_missing_key_and_disabled_modes_record_clear_skip_reasons():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    import crypto_rsi_scanner.event_alpha.radar.pipeline as event_alpha_pipeline
    import crypto_rsi_scanner.event_alpha.artifacts.run_ledger as event_alpha_run_ledger
    import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
    from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
    from crypto_rsi_scanner.llm_providers.openai_provider import OpenAILLMRelationshipProvider

    now = datetime(2026, 6, 27, 12, 30, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="aave_kraken_missing_key",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/aave-missing-key",
        title="Kraken in talks to buy 15% stake in Aave at $385 million valuation",
        body="The article references KelpDAO exploit fallout but says Aave itself was not hacked.",
        raw_json={},
        source_confidence=0.95,
        content_hash="aave-missing-key",
    )
    event = NormalizedEvent(
        "evt_aave_missing_key",
        (raw.raw_id,),
        raw.title,
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (raw.source_url or "",),
        "Aave",
        raw.body,
        0.95,
    )

    def load_discovery_result(observed, raw_event_transform):
        raws = (raw,)
        if raw_event_transform is not None:
            raws = tuple(raw_event_transform(raws))
        return EventDiscoveryResult(raws, (event,), (), (), ())

    missing_key_result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=load_discovery_result,
        now=now,
        with_llm=True,
        catalyst_frame_provider=OpenAILLMRelationshipProvider(api_key="", model="fixture"),
        catalyst_frame_cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=True,
            provider="openai",
            only_ambiguous=True,
        ),
        refresh_watchlist=False,
        route=False,
    )
    missing_payload = missing_key_result.discovery_result.raw_events[0].raw_json
    assert missing_payload["catalyst_frame_status"] == "missing_required_frame_analysis"
    assert missing_payload["catalyst_frame_skip_reason"] == "missing_api_key"

    disabled_result = event_alpha_pipeline.run_event_alpha_operating_cycle(
        load_discovery_result=load_discovery_result,
        now=now,
        with_llm=True,
        catalyst_frame_provider=None,
        catalyst_frame_cfg=event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
            enabled=False,
            provider="openai",
            only_ambiguous=True,
        ),
        refresh_watchlist=False,
        route=False,
    )
    disabled_payload = disabled_result.discovery_result.raw_events[0].raw_json
    assert disabled_payload["catalyst_frame_status"] == "missing_required_frame_analysis"
    assert disabled_payload["catalyst_frame_skip_reason"] == "disabled"

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "runs.jsonl"
        missing_row = event_alpha_run_ledger.append_run_record(
            missing_key_result,
            cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(path),
            profile="notify_llm_quality",
            started_at=now,
            finished_at=now,
            with_llm=True,
            send_requested=False,
        )
        disabled_row = event_alpha_run_ledger.append_run_record(
            disabled_result,
            cfg=event_alpha_run_ledger.EventAlphaRunLedgerConfig(path),
            profile="notify_llm_quality",
            started_at=now,
            finished_at=now,
            with_llm=True,
            send_requested=False,
        )
        legacy_path = Path(tmp) / "legacy.jsonl"
        legacy_path.write_text(
            '{"row_type":"event_alpha_run","started_at":"2026-06-27T00:00:00+00:00",'
            '"catalyst_frames_analyzed":null,"catalyst_frame_validations":null,'
            '"catalyst_frame_disagreements":null,"catalyst_frame_unresolved":null,'
            '"catalyst_frame_rows_skipped":null,"catalyst_frame_skip_reasons":null}\n',
            encoding="utf-8",
        )
        legacy = event_alpha_run_ledger.load_run_records(legacy_path).rows[0]
    assert missing_row["catalyst_frames_analyzed"] == 0
    assert missing_row["catalyst_frame_skip_reasons"]["missing_api_key"] == 1
    assert disabled_row["catalyst_frame_skip_reasons"]["disabled"] == 1
    assert legacy["catalyst_frames_analyzed"] == 0
    assert legacy["catalyst_frame_validations"] == 0
    assert legacy["catalyst_frame_disagreements"] == 0
    assert legacy["catalyst_frame_unresolved"] == 0
    assert legacy["catalyst_frame_rows_skipped"] == 0
    assert legacy["catalyst_frame_skip_reasons"] == {}


def test_incident_asset_roles_demote_unvalidated_taxonomy_candidates():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
    import crypto_rsi_scanner.event_alpha.radar.incidents as event_incident_store
    from crypto_rsi_scanner.event_core.models import NormalizedEvent, RawDiscoveredEvent

    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        "thor_exploit",
        "fixture_news",
        now,
        now,
        "https://alpha.example/thor",
        "THORChain confirms RUNE exploit after attack",
        "THORChain confirms a RUNE exploit and security incident after an attack; RUNE trading reacts sharply.",
        {},
        0.90,
        "thor",
    )
    event = NormalizedEvent(
        "evt_thor",
        ("thor_exploit",),
        "THORChain RUNE exploit",
        "news",
        None,
        0.0,
        now,
        "fixture_news",
        (raw.source_url or "",),
        "THORChain",
        raw.body,
        0.90,
    )
    incident = event_incident_graph.build_incidents((event,), {raw.raw_id: raw})[0]
    rows = event_incident_store._linked_assets(
        [
            {
                "candidate_symbols": ["LINK", "PYTH", "RUNE"],
                "candidate_coin_ids": ["chainlink", "pyth-network", "thorchain"],
                "candidate_role": "direct_subject",
                "candidate_source": "taxonomy",
                "crypto_candidate_assets": [
                    {"symbol": "LINK", "coin_id": "chainlink", "source": "taxonomy", "validated": False},
                    {"symbol": "PYTH", "coin_id": "pyth-network", "source": "taxonomy", "validated": False},
                ],
            },
            {
                "validated_symbol": "RUNE",
                "validated_coin_id": "thorchain",
                "candidate_role": "direct_subject",
                "validated_asset": {"symbol": "RUNE", "coin_id": "thorchain", "validated": True},
            },
        ],
        [],
        incident=incident,
    )
    assert any(asset["symbol"] == "RUNE" and asset["role"] == "direct_subject" for asset in rows)
    assert not any(asset["symbol"] == "LINK" and asset["role"] == "direct_subject" for asset in rows)
    assert any(asset["symbol"] == "LINK" and asset["role"] == "taxonomy_candidate" for asset in rows)


def test_validated_hypothesis_aggregation_preserves_supporting_paths():
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses

    base = dict(
        event_cluster_id="incident:spacex",
        event_type="news",
        external_asset="SpaceX",
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        validated_candidate_assets=({"symbol": "VELVET", "coin_id": "velvet", "validated": True},),
        crypto_candidate_assets=({"symbol": "VELVET", "coin_id": "velvet", "validated": True},),
        candidate_source="hypothesis_search",
        hypothesis_scope="token",
        direction_hint="up_then_fade",
        confidence=0.86,
        hypothesis_score=86.0,
        validation_stage="impact_path_validated",
        status="validated",
        incident_id="incident:spacex",
        candidate_role="proxy_venue",
        impact_path_type="venue_value_capture",
        impact_path_reason="venue_value_capture",
        opportunity_score_final=88,
        opportunity_level="high_priority",
    )
    first = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:velvet:rwa",
        impact_category="rwa_preipo_proxy",
        evidence_quotes=("VELVET users can trade SpaceX pre-IPO exposure.",),
        **base,
    )
    second = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:velvet:venue",
        impact_category="tokenized_stock_venue",
        evidence_quotes=("Velvet is the venue for tokenized SpaceX exposure.",),
        **base,
    )
    out = event_impact_hypotheses._dedupe_hypotheses((first, second))
    assert len(out) == 1
    item = out[0]
    assert item.aggregated_candidate_id
    assert item.supporting_hypothesis_count == 2
    assert set(item.supporting_categories) == {"rwa_preipo_proxy", "tokenized_stock_venue"}
    assert item.supporting_impact_paths == ("venue_value_capture",)
    assert "VELVET users can trade SpaceX pre-IPO exposure." in item.supporting_evidence_quotes


def test_missing_unresolved_catalyst_frame_caps_validated_hypothesis():
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses

    missing_hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:aave:missing",
        event_cluster_id="incident:aave",
        event_type="news",
        external_asset="Aave",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("defi",),
        candidate_symbols=("AAVE",),
        candidate_coin_ids=("aave",),
        validated_candidate_assets=({"symbol": "AAVE", "coin_id": "aave", "validated": True},),
        confidence=0.90,
        hypothesis_score=90.0,
        validation_stage="impact_path_validated",
        status="validated",
        impact_path_type="exploit_security_event",
        impact_path_reason="exploit_security_event",
        candidate_role="direct_subject",
        opportunity_score_final=88,
        opportunity_level="high_priority",
        frame_required=True,
        frame_status="missing_required_frame_analysis",
        frame_gate_reason="catalyst_frame_missing",
        route_block_reason="catalyst_frame_missing",
    )
    missing_capped = event_impact_hypotheses._with_promotion_diagnostics(missing_hypothesis)
    assert missing_capped.opportunity_level == "exploratory"
    assert missing_capped.route_block_reason == "catalyst_frame_missing"
    assert missing_capped.impact_path_type == "exploit_security_event"

    hypothesis = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:aave:bad",
        event_cluster_id="incident:aave",
        event_type="news",
        external_asset="Aave",
        impact_category="security_or_regulatory_shock",
        candidate_sectors=("defi",),
        candidate_symbols=("AAVE",),
        candidate_coin_ids=("aave",),
        validated_candidate_assets=({"symbol": "AAVE", "coin_id": "aave", "validated": True},),
        confidence=0.90,
        hypothesis_score=90.0,
        validation_stage="impact_path_validated",
        status="validated",
        impact_path_type="exploit_security_event",
        impact_path_reason="exploit_security_event",
        candidate_role="direct_subject",
        opportunity_score_final=88,
        opportunity_level="high_priority",
        frame_required=True,
        frame_status="unresolved",
        frame_gate_reason="catalyst_frame_unresolved",
        route_block_reason="catalyst_frame_unresolved",
    )
    capped = event_impact_hypotheses._with_promotion_diagnostics(hypothesis)
    assert capped.opportunity_level == "exploratory"
    assert capped.opportunity_score_final <= 54
    assert capped.route_block_reason == "catalyst_frame_unresolved"
    assert "catalyst_frame_unresolved" in capped.why_not_promoted


def test_catalyst_frame_route_cap_preserves_zero_and_rejects_malformed_scores():
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses

    def capped(final_score, *, legacy_score=90.0):
        hypothesis = event_impact_hypotheses.EventImpactHypothesis(
            hypothesis_id="hyp:aave:score-cap",
            event_cluster_id="incident:aave:score-cap",
            event_type="news",
            external_asset="Aave",
            impact_category="security_or_regulatory_shock",
            candidate_sectors=("defi",),
            candidate_symbols=("AAVE",),
            candidate_coin_ids=("aave",),
            validated_candidate_assets=({"symbol": "AAVE", "coin_id": "aave", "validated": True},),
            confidence=0.9,
            hypothesis_score=legacy_score,
            validation_stage="impact_path_validated",
            status="validated",
            impact_path_type="exploit_security_event",
            impact_path_reason="exploit_security_event",
            candidate_role="direct_subject",
            opportunity_score_final=final_score,
            opportunity_level="high_priority",
            frame_required=True,
            frame_status="unresolved",
            frame_gate_reason="catalyst_frame_unresolved",
            route_block_reason="catalyst_frame_unresolved",
        )
        return event_impact_hypotheses._with_promotion_diagnostics(hypothesis)

    explicit_zero = capped(0.0)
    assert explicit_zero.opportunity_score_final == 0.0
    assert explicit_zero.opportunity_level == "exploratory"

    for malformed in (True, float("nan"), float("inf"), float("-inf")):
        row = capped(malformed)
        assert row.opportunity_score_final == 0.0
        assert row.opportunity_level == "exploratory"
        assert "catalyst_frame_unresolved" in row.why_not_promoted

    absent = capped(None)
    assert absent.opportunity_score_final == 54.0

    finite_below_cap = capped(20.0)
    assert finite_below_cap.opportunity_score_final == 20.0

    finite_above_cap = capped(88.0)
    assert finite_above_cap.opportunity_score_final == 54.0
