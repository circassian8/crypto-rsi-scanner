"""End-to-end source-independence policy regressions."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from crypto_rsi_scanner.event_alpha.artifacts import alerts as event_alerts
from crypto_rsi_scanner.event_alpha.artifacts.research_cards.components import source_coverage
from crypto_rsi_scanner.event_alpha.notifications.pipeline_parts import message_renderer
from crypto_rsi_scanner.event_alpha.radar import discovery as event_discovery
from crypto_rsi_scanner.event_alpha.radar import incident_graph
from crypto_rsi_scanner.event_alpha.radar import incidents as event_incidents
from crypto_rsi_scanner.event_alpha.radar import opportunity_verdict
from crypto_rsi_scanner.event_alpha.radar import catalyst_attribution
from crypto_rsi_scanner.event_alpha.radar import source_independence
from crypto_rsi_scanner.event_alpha.radar import watchlist as event_watchlist
from crypto_rsi_scanner.event_alpha.radar.incidents import canonical as incident_canonical
from crypto_rsi_scanner.event_alpha.radar.integrated.pipeline_parts import merge
from crypto_rsi_scanner.event_alpha.radar.watchlist import builders as watchlist_builders
import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_store
from crypto_rsi_scanner.event_alpha.radar.core_opportunities import CoreOpportunity
from crypto_rsi_scanner.event_core.models import (
    DiscoveredAsset,
    EventDiscoveryResult,
    NormalizedEvent,
    RawDiscoveredEvent,
)


NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
BASE_COPY = (
    "PumpX token holders can trade synthetic exposure to SpaceX before the "
    "initial public offering opens for qualified crypto market participants"
)
INDEPENDENT_COPY = (
    "Independent analysts confirm PumpX settlement contracts reference SpaceX "
    "private market exposure with separate custody documentation for participants"
)


def _raw(raw_id: str, domain: str, body: str) -> RawDiscoveredEvent:
    return RawDiscoveredEvent(
        raw_id=raw_id,
        provider="fixture",
        fetched_at=NOW,
        published_at=NOW,
        source_url=f"https://{domain}/story",
        title="PumpX token offers SpaceX synthetic exposure",
        body=body,
        raw_json={
            "source_class": "broad_news",
            "event": {
                "event_id": f"event-{raw_id}",
                "event_name": "PumpX SpaceX proxy exposure",
                "event_type": "ipo_proxy",
                "event_time": "2026-07-17T12:00:00Z",
                "event_time_confidence": 0.9,
                "external_asset": "SpaceX",
                "description": body,
                "confidence": 0.9,
            },
        },
        source_confidence=0.9,
        content_hash=f"hash-{raw_id}",
    )


def _asset() -> DiscoveredAsset:
    return DiscoveredAsset(
        coin_id="pumpx",
        symbol="PUMPX",
        name="PumpX",
        aliases=("pumpx token", "PumpX"),
    )


def _alert(rows: list[RawDiscoveredEvent], *, now: datetime = NOW):
    discovery = event_discovery.run_discovery(rows, [_asset()], now=now)
    return event_alerts.build_event_alert_candidates(discovery, now=now)[0]


def _wrapped(contract, *, status="assessed", errors=()):
    return {
        "source_independence": contract,
        "source_independence_status": status,
        "source_independence_errors": list(errors),
        "independent_source_count": contract["independent_evidence_count"],
        "independent_corroboration_count": contract[
            "independent_corroboration_count"
        ],
        "source_content_cluster_count": contract["content_cluster_count"],
    }


def _incident_result(rows: list[RawDiscoveredEvent]) -> EventDiscoveryResult:
    events = tuple(
        NormalizedEvent(
            event_id=f"normalized-{index}",
            raw_ids=(raw.raw_id,),
            event_name="Solana network upgrade",
            event_type="protocol_upgrade",
            event_time=NOW,
            event_time_confidence=0.9,
            first_seen_time=NOW,
            source=raw.provider,
            source_urls=(raw.source_url,) if raw.source_url else (),
            external_asset="Solana",
            description=raw.body,
            confidence=0.9,
        )
        for index, raw in enumerate(rows)
    )
    return EventDiscoveryResult(tuple(rows), events, (), (), ())


def test_syndicated_cross_domain_copies_do_not_boost_alert_or_incident_confidence():
    single = [_raw("one", "alpha.example", BASE_COPY)]
    syndicated = [
        _raw("one", "alpha.example", BASE_COPY),
        _raw("two", "beta.example", BASE_COPY),
        _raw("three", "gamma.example", BASE_COPY),
    ]
    distinct = [
        _raw("one", "alpha.example", BASE_COPY),
        _raw("two", "beta.example", INDEPENDENT_COPY),
    ]

    single_alert = _alert(single)
    syndicated_alert = _alert(syndicated)
    distinct_alert = _alert(distinct)

    assert syndicated_alert.opportunity_score == single_alert.opportunity_score
    assert syndicated_alert.score_components["source_quality"] == single_alert.score_components["source_quality"]
    assert syndicated_alert.score_components["cluster_confidence"] == single_alert.score_components["cluster_confidence"]
    assert syndicated_alert.score_components["independent_source_count"] == 1
    assert syndicated_alert.score_components["independent_corroboration_count"] == 0
    assert syndicated_alert.score_components["source_content_cluster_count"] == 1
    assert distinct_alert.score_components["independent_source_count"] == 2
    assert distinct_alert.score_components["independent_corroboration_count"] == 1
    assert distinct_alert.opportunity_score > single_alert.opportunity_score

    single_incident = event_incidents.build_incident_rows(
        _incident_result(single), now=NOW
    )[0]
    syndicated_incident = event_incidents.build_incident_rows(
        _incident_result(syndicated), now=NOW
    )[0]
    distinct_incident = event_incidents.build_incident_rows(
        _incident_result(distinct), now=NOW
    )[0]

    assert syndicated_incident["source_update_count"] == 3
    assert syndicated_incident["source_domain_count"] == 3
    assert syndicated_incident["independent_source_domains"] == (
        "alpha.example",
    )
    assert syndicated_incident["independent_source_domain_count"] == 1
    assert syndicated_incident["independent_source_count"] == 1
    assert syndicated_incident["incident_confidence"] == single_incident["incident_confidence"]
    assert distinct_incident["independent_corroboration_count"] == 1
    assert distinct_incident["incident_confidence"] > single_incident["incident_confidence"]


def test_watchlist_material_update_requires_a_valid_new_independent_unit(tmp_path: Path):
    cfg = event_watchlist.EventWatchlistConfig(
        enabled=True,
        state_path=tmp_path / "watchlist.jsonl",
    )
    first = event_watchlist.refresh_watchlist(
        [_alert([_raw("one", "alpha.example", BASE_COPY)])],
        cfg=cfg,
        now=NOW,
    ).entries[0]
    duplicate = event_watchlist.refresh_watchlist(
        [
            _alert(
                [
                    _raw("one", "alpha.example", BASE_COPY),
                    _raw("two", "beta.example", BASE_COPY),
                ],
                now=NOW + timedelta(hours=1),
            )
        ],
        cfg=cfg,
        now=NOW + timedelta(hours=1),
    ).entries[0]
    corroborated = event_watchlist.refresh_watchlist(
        [
            _alert(
                [
                    _raw("one", "alpha.example", BASE_COPY),
                    _raw("two", "beta.example", INDEPENDENT_COPY),
                ],
                now=NOW + timedelta(hours=2),
            )
        ],
        cfg=cfg,
        now=NOW + timedelta(hours=2),
    ).entries[0]

    assert first.source_count == 1
    assert duplicate.source_count == 2
    assert duplicate.latest_score_components["independent_source_count"] == 1
    assert duplicate.latest_score_components["independent_corroboration_count"] == 0
    assert "new_independent_source" not in duplicate.material_change_reasons
    assert duplicate.source_count_increased is False
    assert corroborated.source_count == 2
    assert corroborated.latest_score_components["independent_source_count"] == 2
    assert corroborated.latest_score_components["independent_corroboration_count"] == 1
    assert "new_independent_source" in corroborated.material_change_reasons
    assert corroborated.source_count_increased is True


def test_source_only_narrative_gate_never_uses_accepted_copy_count_as_corroboration():
    first_source = {
        "source_id": "one",
        "source_url": "https://alpha.example/story",
        "title": "Catalyst report",
        "body": BASE_COPY,
        "published_at": NOW,
    }
    copied_source = {
        "source_id": "two",
        "source_url": "https://beta.example/story",
        "title": "Catalyst report",
        "body": BASE_COPY,
        "published_at": NOW + timedelta(minutes=1),
    }
    duplicate_contract = source_independence.assess_source_independence(
        [first_source, copied_source]
    )
    distinct_contract = source_independence.assess_source_independence(
        [
            first_source,
            {
                "source_id": "two",
                "source_url": "https://beta.example/story",
                "title": "Independent catalyst analysis",
                "body": INDEPENDENT_COPY,
                "published_at": NOW + timedelta(minutes=1),
            },
        ]
    )
    policy_input = {
        "profile": "notify_llm_deep",
        "artifact_namespace": "source-independence-fixture",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "source_pack": "fan_sports_pack",
        "final_opportunity_level": "validated_digest",
        "opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "impact_path_type": "fan_token_event",
        "evidence_acquisition_status": "accepted_evidence_found",
        "evidence_acquisition_accepted_count": 2,
        "accepted_provider_counts": {"public_rss": 2},
        "accepted_evidence_reason_codes": [
            "cryptopanic_currency_tag_match",
            "direct_token_mechanism",
        ],
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
    }

    duplicate = opportunity_verdict.apply_live_confirmation_policy(
        {**policy_input, **_wrapped(duplicate_contract)}
    )
    independent = opportunity_verdict.apply_live_confirmation_policy(
        {**policy_input, **_wrapped(distinct_contract)}
    )

    assert duplicate.confirmed is False
    assert duplicate.reason == "source_only_narrative_without_market_confirmation"
    assert independent.confirmed is True
    assert independent.reason == "accepted_evidence_found"


def test_positive_consumers_reject_a_valid_inner_contract_with_invalid_wrapper():
    contract = source_independence.assess_source_independence(
        [
            {
                "source_id": "one",
                "source_url": "https://one.example/story",
                "title": "Initial catalyst evidence",
                "body": BASE_COPY,
                "published_at": NOW,
            },
            {
                "source_id": "two",
                "source_url": "https://two.example/story",
                "title": "Independent catalyst evidence",
                "body": INDEPENDENT_COPY,
                "published_at": NOW + timedelta(minutes=1),
            },
        ]
    )
    rejected = _wrapped(
        contract,
        status="rejected",
        errors=("source_independence_source_context_incomplete",),
    )
    drifted = {**_wrapped(contract), "independent_source_count": 99}

    for invalid in (rejected, drifted):
        entry = SimpleNamespace(latest_score_components=invalid)
        assert message_renderer._independent_corroboration_for_entry(entry) is None
        assert watchlist_builders._validated_corroboration_count(invalid) is None
        assert opportunity_verdict._independent_corroboration_count(invalid) == 0
        card = "\n".join(source_coverage._source_lines(None, invalid))
        assert "Independent evidence units: not assessed" in card
        assert "Additional independent corroborations: not assessed" in card

    result = _incident_result(
        [
            _raw("one", "one.example", BASE_COPY),
            _raw("two", "two.example", INDEPENDENT_COPY),
        ]
    )
    incident = incident_graph.build_incidents(
        result.normalized_events, {row.raw_id: row for row in result.raw_events}
    )[0]
    rejected_incident = replace(
        incident,
        source_independence_errors=(
            "source_independence_source_context_incomplete",
        ),
    )
    fields = incident_canonical._incident_source_independence_row_fields(
        rejected_incident
    )
    assert fields["source_independence_status"] == "rejected"
    assert fields["source_independence"] == {}
    assert fields["independent_source_count"] == 0
    assert fields["independent_corroboration_count"] == 0


def test_card_evidence_verdict_keeps_accepted_rows_distinct_from_corroboration():
    contract = source_independence.assess_source_independence(
        [
            {
                "source_id": "original",
                "source_url": "https://one.example/story",
                "title": "Initial catalyst evidence",
                "body": BASE_COPY,
                "published_at": NOW,
            },
            {
                "source_id": "syndicated",
                "source_url": "https://two.example/story",
                "title": "Initial catalyst evidence",
                "body": BASE_COPY,
                "published_at": NOW + timedelta(minutes=1),
            },
            {
                "source_id": "independent",
                "source_url": "https://three.example/story",
                "title": "Independent catalyst analysis",
                "body": INDEPENDENT_COPY,
                "published_at": NOW + timedelta(minutes=2),
            },
        ]
    )
    attribution = catalyst_attribution.assess_mapping_attribution(
        {
            "market_anomaly_id": "anomaly-card-verdict",
            "observed_at": NOW.isoformat(),
        },
        {
            "raw_id": "official-card-source",
            "provider": "official_exchange",
            "source_url": "https://exchange.example/notices/card-verdict",
            "content_hash": "a" * 64,
            "published_at": (NOW - timedelta(minutes=30)).isoformat(),
            "source_class": "official_exchange",
            "source_strength": "official_structured",
            "main_frame_role": "main_catalyst",
            "candidate_role": "direct_subject",
            "impact_path_strength": "direct",
        },
    )
    components = {
        **_wrapped(contract),
        "source_update_count": 3,
        "evidence_acquisition_accepted_count": 3,
        "latest_source": "official_exchange",
        "latest_source_url": "https://exchange.example/notices/card-verdict",
        "catalyst_attribution": attribution,
    }

    verdict = "\n".join(source_coverage._source_lines(None, components))
    technical = "\n".join(
        source_coverage._technical_evidence_lines(None, components)
    )

    assert "Raw sources: 3" in verdict
    assert "Content clusters: 2" in verdict
    assert "Independent evidence units: 2" in verdict
    assert "Additional independent corroborations: 1" in verdict
    assert "Syndicated copies collapsed: 1" in verdict
    assert "Accepted evidence rows (not corroboration): 3" in verdict
    assert "Catalyst timing: antecedent" in verdict
    assert "Causal eligibility: eligible" in verdict
    assert "Source authority: official" in verdict
    assert contract["contract_digest"] not in verdict
    assert attribution["attribution_digest"] not in verdict
    assert contract["contract_digest"] in technical
    assert attribution["attribution_digest"] in technical
    assert "normalized_body" not in technical

    rejected = {
        **components,
        "source_independence_status": "rejected",
        "source_independence_errors": [f"evidence_error_{index}" for index in range(6)],
    }
    rejected_verdict = "\n".join(source_coverage._source_lines(None, rejected))
    assert "Independent evidence units: not assessed" in rejected_verdict
    assert "evidence_error_0" in rejected_verdict
    assert "evidence_error_3" in rejected_verdict
    assert "evidence_error_4" not in rejected_verdict
    assert "+2 more" in rejected_verdict


def test_oversized_source_group_fails_closed_without_crashing_discovery_cycle():
    rows = [
        _raw(f"copy-{index}", f"source-{index}.example", BASE_COPY)
        for index in range(source_independence.MAX_DOCUMENTS + 1)
    ]

    alert = _alert(rows)

    assert alert.score_components["source_independence"] == {}
    assert alert.score_components["independent_source_count"] == 0
    assert alert.score_components["independent_corroboration_count"] == 0
    assert "source_independence_document_limit_exceeded" in alert.score_components[
        "source_independence_errors"
    ]


def test_acquisition_independence_survives_core_view_and_live_policy_scope():
    event_contract = source_independence.assess_source_independence(
        [
            {
                "source_id": "event-source",
                "source_url": "https://event.example/story",
                "title": "Initial catalyst context",
                "body": BASE_COPY,
                "published_at": NOW,
            }
        ]
    )

    def acquisition_contract(second_body: str):
        return source_independence.assess_source_independence(
            [
                {
                    "source_id": "acquired-one",
                    "source_url": "https://one.example/story",
                    "title": "Acquired catalyst report",
                    "body": BASE_COPY,
                    "published_at": NOW,
                },
                {
                    "source_id": "acquired-two",
                    "source_url": "https://two.example/story",
                    "title": "Second acquired catalyst report",
                    "body": second_body,
                    "published_at": NOW + timedelta(minutes=1),
                },
            ]
        )

    item = CoreOpportunity(
        core_opportunity_id="core-source-scope",
        incident_id="incident-source-scope",
        canonical_incident_name="World Cup",
        symbol="CHZ",
        coin_id="chiliz",
        candidate_role="direct_subject",
        primary_impact_path="fan_token_event",
        opportunity_level="validated_digest",
        opportunity_score_final=72,
        final_route_after_quality_gate="RESEARCH_DIGEST",
        final_state_after_quality_gate="RADAR",
        supporting_hypothesis_ids=(),
        supporting_categories=("sports_fan_proxy",),
        supporting_impact_paths=("fan_token_event",),
        supporting_evidence_quotes=(),
        diagnostic_row_count=0,
        source_noise_control_count=0,
        quality_capped_supporting_rows=0,
        why_opportunity_visible="fixture",
        why_other_rows_hidden="none",
        primary_row={},
    )
    primary = {
        "profile": "notify_llm_deep",
        "artifact_namespace": "source-scope-fixture",
        "source_pack": "fan_sports_pack",
        "source_class": "crypto_news",
        "evidence_specificity": "direct_value_capture",
        "source_independence": event_contract,
        "accepted_evidence_reason_codes": ["direct_token_mechanism"],
    }

    def policy_for(contract):
        acquisition_row = {
            "row_type": "event_evidence_acquisition",
            "core_opportunity_id": item.core_opportunity_id,
            "evidence_acquisition_status": "accepted_evidence_found",
            "evidence_acquisition_accepted_count": 2,
            "accepted_evidence_count": 2,
            "evidence_acquisition_source_update_count": 2,
            "source_independence": contract,
            "accepted_provider_counts": {"public_rss": 2},
            "accepted_evidence_reason_codes": ["direct_token_mechanism"],
        }
        acquisition = event_core_store._build_core_evidence_acquisition_view(
            item.core_opportunity_id, [acquisition_row]
        )
        context = {
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "source-scope-fixture",
            "source_class": "crypto_news",
            "evidence_specificity": "direct_value_capture",
            "evidence_score": 80,
            "market_after": None,
            "market_level": "none",
            "market_context": {"market_context_freshness_status": "missing"},
            "market_snapshot": {},
            "source_pack": "fan_sports_pack",
            "acquisition": acquisition,
            "accepted_source": {},
            "impact_path_reason": "fixture",
            "diagnostic_row_count": 0,
            "source_noise_control_count": 0,
        }
        return acquisition, event_core_store._core_row_policy_context(
            item, primary, [primary, acquisition_row], context
        )["live_policy"]

    copied_view, copied_policy = policy_for(acquisition_contract(BASE_COPY))
    independent_view, independent_policy = policy_for(
        acquisition_contract(INDEPENDENT_COPY)
    )

    assert copied_view.source_update_count == 2
    assert copied_view.independent_corroboration_count == 0
    assert copied_policy.confirmed is False
    assert copied_policy.reason == "source_only_narrative_without_market_confirmation"
    assert independent_view.independent_corroboration_count == 1
    assert independent_policy.confirmed is True
    assert independent_policy.reason == "accepted_evidence_found"


def test_core_and_integrated_merges_reject_status_contract_contradiction():
    contract = source_independence.assess_source_independence(
        [
            {
                "source_id": "contradiction",
                "source_url": "https://source.example/story",
                "title": "Protocol catalyst evidence",
                "body": " ".join(f"evidence{index}" for index in range(24)),
                "published_at": NOW,
            }
        ]
    )
    row = {
        "row_type": "event_evidence_acquisition",
        "core_opportunity_id": "core:contradiction",
        "source_independence": contract,
        "source_independence_status": "unassessed",
    }

    acquisition = event_core_store._build_core_evidence_acquisition_view(
        "core:contradiction", [row]
    )
    integrated = merge._merge_family_source_independence_fields([row])  # noqa: SLF001

    assert acquisition.source_independence == {}
    assert acquisition.source_independence_status == "rejected"
    assert acquisition.source_independence_errors == (
        "source_independence_status_contract_mismatch",
    )
    assert integrated["source_independence"] == {}
    assert integrated["source_independence_status"] == "rejected"
    assert integrated["source_independence_errors"] == [
        "source_independence_status_contract_mismatch"
    ]
