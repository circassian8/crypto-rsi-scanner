"""Closed temporal-semantic catalyst attribution regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from crypto_rsi_scanner.event_alpha.radar import catalyst_attribution


def _redigest(value):
    payload = dict(value)
    payload.pop("attribution_digest", None)
    value["attribution_digest"] = hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    return value


def _anomaly(**overrides):
    row = {
        "market_anomaly_id": "anomaly-1",
        "observed_at": "2026-07-15T12:00:00Z",
    }
    row.update(overrides)
    return row


def _official_source(**overrides):
    row = {
        "raw_id": "source-1",
        "provider": "official_exchange",
        "source_url": "https://exchange.example/notices/test",
        "content_hash": "a" * 64,
        "published_at": "2026-07-15T11:30:00Z",
        "row_type": "official_listing_candidate",
        "source_class": "official_exchange",
        "source_strength": "official_structured",
        "accepted_evidence_count": 1,
        "main_frame_role": "main_catalyst",
        "candidate_role": "direct_subject",
        "impact_path_strength": "direct",
    }
    row.update(overrides)
    return row


def test_antecedent_official_source_is_causal_candidate():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(), _official_source()
    )

    assert catalyst_attribution.validate_contract(value) == []
    assert value["temporal_relation"] == "antecedent"
    assert value["publication_lag_seconds"] == -1800.0
    assert value["evidence_use"] == "causal_candidate"
    assert value["causal_eligible"] is True
    assert value["research_only"] is True
    assert value["auto_apply"] is False


def test_later_official_article_is_retrospective_not_causal():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(),
        _official_source(published_at="2026-07-15T12:30:00Z"),
    )

    assert catalyst_attribution.validate_contract(value) == []
    assert value["temporal_relation"] == "retrospective"
    assert value["publication_lag_seconds"] == 1800.0
    assert value["evidence_use"] == "retrospective_context"
    assert value["causal_eligible"] is False
    assert "source_published_after_anomaly" in value["reason_codes"]


def test_backdated_claim_in_later_article_stays_retrospective():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(),
        _official_source(
            published_at="2026-07-15T12:30:00Z",
            event_time="2026-07-15T10:00:00Z",
            event_time_source="article_claim",
            event_time_confidence=0.9,
        ),
    )

    assert value["event_time"] == "2026-07-15T10:00:00+00:00"
    assert value["source_public_at"] == "2026-07-15T12:30:00+00:00"
    assert value["evidence_use"] == "retrospective_context"
    assert value["causal_eligible"] is False


def test_preannounced_future_event_is_scheduled_anticipation():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(),
        _official_source(
            published_at="2026-07-15T10:00:00Z",
            event_time="2026-07-16T08:00:00Z",
            event_time_source="official_schedule",
            event_time_confidence=1.0,
        ),
    )

    assert value["temporal_relation"] == "antecedent"
    assert value["evidence_use"] == "scheduled_anticipation"
    assert value["causal_eligible"] is True


def test_background_role_is_context_only_even_when_official_and_early():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(),
        _official_source(
            main_frame_role="background_context",
            candidate_role="background_context",
        ),
    )

    assert value["evidence_use"] == "background_context"
    assert value["causal_eligible"] is False
    assert "semantic_context_only" in value["reason_codes"]


def test_disproof_role_is_preserved_without_becoming_causal():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(),
        _official_source(main_frame_role="corrective_context"),
    )

    assert value["evidence_use"] == "disproof"
    assert value["causal_eligible"] is False
    assert "source_disproof" in value["reason_codes"]


def test_missing_public_clock_fails_closed_and_records_derived_identity():
    source = _official_source(
        raw_id="",
        content_hash="",
        published_at=None,
        fetched_at=None,
    )
    value = catalyst_attribution.assess_mapping_attribution(_anomaly(), source)

    assert catalyst_attribution.validate_contract(value) == []
    assert value["source_identity_kind"] == "derived"
    assert value["temporal_relation"] == "unknown"
    assert value["evidence_use"] == "unknown"
    assert value["causal_eligible"] is False
    assert "source_public_clock_missing" in value["reason_codes"]


def test_contract_is_idempotent_and_digest_tampering_fails():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(), _official_source()
    )

    assert catalyst_attribution.assess_mapping_attribution(
        _anomaly(), {"catalyst_attribution": value}
    ) == value

    tampered = deepcopy(value)
    tampered["causal_eligible"] = False
    assert "attribution_digest_invalid" in catalyst_attribution.validate_contract(
        tampered
    )


def test_recomputed_digest_cannot_hide_public_clock_or_semantic_drift():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(), _official_source()
    )
    clock_drift = _redigest(
        {
            **deepcopy(value),
            "source_public_at": "2026-07-15T10:00:00+00:00",
            "publication_lag_seconds": -7200.0,
            "temporal_relation": "antecedent",
        }
    )
    semantic_drift = _redigest(
        {
            **deepcopy(value),
            "semantic_role": "background_context",
            "causal_eligible": True,
            "evidence_use": "causal_candidate",
        }
    )

    assert "source_public_clock_mismatch" in catalyst_attribution.validate_contract(
        clock_drift
    )
    assert "causal_semantics_inconsistent" in catalyst_attribution.validate_contract(
        semantic_drift
    )

    downshifted = _redigest(
        {
            **deepcopy(value),
            "causal_eligible": False,
            "evidence_use": "unknown",
        }
    )
    assert "causal_semantics_inconsistent" in catalyst_attribution.validate_contract(
        downshifted
    )
    assert "evidence_use_inconsistent" in catalyst_attribution.validate_contract(
        downshifted
    )

    disproof = catalyst_attribution.assess_mapping_attribution(
        _anomaly(), _official_source(main_frame_role="corrective_context")
    )
    hidden_disproof = _redigest(
        {**deepcopy(disproof), "evidence_use": "unknown"}
    )
    assert "evidence_use_inconsistent" in catalyst_attribution.validate_contract(
        hidden_disproof
    )


def test_source_hints_and_lookalike_domain_do_not_establish_official_authority():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(),
        _official_source(
            provider="public_rss",
            source_url="https://binance.com.attacker.example/notices/test",
            source_class="official_exchange",
            source_strength="official_structured",
            row_type="official_listing_candidate",
        ),
    )

    assert value["source_class"] == "broad_news"
    assert value["source_authority_verified"] is False
    assert value["source_can_validate_catalyst"] is False
    assert value["causal_basis"] == "none"
    assert value["causal_eligible"] is False
    assert "source_authority_unverified" in value["source_registry_reason_codes"]
    assert catalyst_attribution.validate_contract(value) == []

    forged = catalyst_attribution.assess_mapping_attribution(
        _anomaly(), _official_source()
    )
    forged["source_provider"] = "mystery_provider"
    forged["source_url"] = "https://news.example/test"
    _redigest(forged)
    assert "source_registry_identity_inconsistent" in (
        catalyst_attribution.validate_contract(forged)
    )


def test_generic_news_cannot_self_assert_validated_beneficiary_impact():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(),
        _official_source(
            provider="public_rss",
            source_url="https://news.example/articles/test",
            source_class="crypto_news",
            source_strength="strong",
            row_type="news_candidate",
            candidate_role="direct_beneficiary",
            impact_path_strength="strong",
        ),
    )

    assert value["source_class"] == "broad_news"
    assert value["source_can_validate_catalyst"] is True
    assert value["source_can_validate_impact_path"] is False
    assert value["causal_basis"] == "none"
    assert value["causal_eligible"] is False
    assert catalyst_attribution.validate_contract(value) == []


def test_rejected_credential_url_cannot_grant_hostname_authority():
    for source_url in (
        "https://user:password@binance.com/notices/test",
        "https://binance.com/api_key/TOPSECRET",
    ):
        value = catalyst_attribution.assess_mapping_attribution(
            _anomaly(),
            _official_source(
                provider="public_rss",
                source_url=source_url,
                source_class="official_exchange",
            ),
        )

        assert value["source_url"] is None
        assert value["source_class"] in {"broad_news", "social_or_unknown"}
        assert value["source_authority_verified"] is False
        assert value["causal_basis"] == "none"
        assert value["causal_eligible"] is False
        assert catalyst_attribution.validate_contract(value) == []


def test_unrecognized_semantic_role_is_explicit_and_never_causal():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(),
        _official_source(main_frame_role="invented_role"),
    )

    assert value["semantic_role"] == "unknown"
    assert value["semantic_role_validated"] is False
    assert value["causal_basis"] == "none"
    assert value["causal_eligible"] is False
    assert "semantic_role_unrecognized" in value["reason_codes"]
    assert catalyst_attribution.validate_contract(value) == []


def test_mapping_binding_digest_rejects_same_id_time_cross_asset_mutation():
    source = _official_source()
    anomaly = {
        **_anomaly(),
        "canonical_asset_id": "asset-a",
        "coin_id": "asset-a",
        "symbol": "ASSETA",
        "market_state_snapshot": {"return_4h": 12.0},
    }
    value = catalyst_attribution.assess_mapping_attribution(anomaly, source)
    mutated = {
        **anomaly,
        "canonical_asset_id": "asset-b",
        "coin_id": "asset-b",
        "symbol": "ASSETB",
    }

    assert catalyst_attribution.validate_mapping_binding(value, anomaly, source) == []
    assert "mapping_binding_mismatch" in catalyst_attribution.validate_mapping_binding(
        value, mutated, source
    )


def test_schema_version_bool_is_not_integer_one_and_raw_zero_confidence_survives():
    from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(), _official_source()
    )
    value["schema_version"] = True
    _redigest(value)
    assert "schema_version_invalid" in catalyst_attribution.validate_contract(value)

    observed = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
    anomaly = RawDiscoveredEvent(
        raw_id="raw-anomaly",
        provider="market_anomaly",
        fetched_at=observed,
        published_at=observed,
        source_url=None,
        title="Raw anomaly",
        body=None,
        raw_json={"market": {"symbol": "RAW", "coin_id": "raw-token"}},
        source_confidence=0.8,
        content_hash="a" * 64,
    )
    source = RawDiscoveredEvent(
        raw_id="raw-source",
        provider="official_exchange",
        fetched_at=observed,
        published_at=observed,
        source_url="https://exchange.example/raw",
        title="Official exchange lists RAW",
        body=None,
        raw_json={"event": {"event_time_confidence": 0.0}},
        source_confidence=0.9,
        content_hash="b" * 64,
    )

    raw_value = catalyst_attribution.assess_catalyst_attribution(anomaly, source)

    assert raw_value["event_time_confidence"] == 0.0
    assert catalyst_attribution.validate_contract(raw_value) == []


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("temporal_relation", {}),
        ("evidence_use", []),
        ("causal_basis", {}),
        ("source_identity_kind", []),
        ("source_class", {}),
        ("semantic_role", []),
        ("source_url", {}),
        ("reason_codes", [{}]),
        ("source_registry_reason_codes", [{}]),
    ),
)
def test_malformed_contract_fields_fail_closed_without_raising(field, invalid):
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(), _official_source()
    )
    value[field] = invalid
    _redigest(value)

    errors = catalyst_attribution.validate_contract(value)

    assert errors


def test_naive_timestamps_are_rejected_as_unknown_not_localized():
    value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(observed_at="2026-07-15T12:00:00"),
        _official_source(published_at="2026-07-15T11:30:00"),
    )

    assert value["anomaly_observed_at"] is None
    assert value["source_public_at"] is None
    assert value["temporal_relation"] == "unknown"
    assert value["causal_eligible"] is False
    assert catalyst_attribution.validate_contract(value) == []


def test_source_url_credentials_never_enter_closed_attribution():
    query_value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(),
        _official_source(
            source_url=(
                "https://exchange.example/notices/test?lang=en&api_key=do-not-copy"
                "#private-fragment"
            )
        ),
    )
    userinfo_value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(),
        _official_source(source_url="https://user:password@exchange.example/test"),
    )

    assert query_value["source_url"] == "https://exchange.example/notices/test"
    assert "source_url_query_removed" in query_value["reason_codes"]
    assert "do-not-copy" not in str(query_value)
    assert query_value["attribution_digest"]
    assert catalyst_attribution.validate_contract(query_value) == []
    assert userinfo_value["source_url"] is None
    assert "source_url_credential_or_scheme_rejected" in userinfo_value["reason_codes"]
    assert "password" not in str(userinfo_value)
    assert catalyst_attribution.validate_contract(userinfo_value) == []

    for suffix in (
        "?key=TOPSECRET",
        "?auth=BearerTOPSECRET",
        "?credential=TOPSECRET",
        "?token=TOPSECRET",
    ):
        value = catalyst_attribution.assess_mapping_attribution(
            _anomaly(), _official_source(source_url=f"https://exchange.example/test{suffix}")
        )
        assert value["source_url"] == "https://exchange.example/test"
        assert "TOPSECRET" not in str(value)
        assert catalyst_attribution.validate_contract(value) == []

    path_value = catalyst_attribution.assess_mapping_attribution(
        _anomaly(),
        _official_source(source_url="https://exchange.example/api_key/TOPSECRET"),
    )
    assert path_value["source_url"] is None
    assert "source_url_credential_path_rejected" in path_value["reason_codes"]
    assert "TOPSECRET" not in str(path_value)
    assert catalyst_attribution.validate_contract(path_value) == []


def test_north_star_records_closed_catalyst_attribution_policy():
    from crypto_rsi_scanner.project_health import radar_north_star

    policy = radar_north_star.build_north_star()["catalyst_attribution_policy"]

    assert policy["schema"] == "event_alpha.catalyst_attribution v1"
    assert policy["source_public_clock"] == "published_at_then_fetched_at"
    assert policy["claimed_event_time_is_separate"] is True
    assert policy["contemporaneous_tolerance_seconds"] == 300
    assert policy["retrospective_source_use"] == (
        "context_only_never_causal_confirmation"
    )
    assert policy["historical_artifacts_rewritten"] is False
    assert policy["research_only"] is True
    assert policy["auto_apply"] is False
