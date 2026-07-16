"""Closed Decision-v2 projection tests for source-independence evidence."""

from __future__ import annotations

from copy import deepcopy

from crypto_rsi_scanner.event_alpha.radar import decision_model
from crypto_rsi_scanner.event_alpha.radar import source_independence_store
from crypto_rsi_scanner.event_alpha.artifacts.schema.decision_model import (
    LEGACY_DECISION_PROJECTION_SCHEMA_VERSION,
)
from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
    decision_model_values,
)
from crypto_rsi_scanner.event_alpha.radar.source_independence import (
    assess_source_independence,
)


def _candidate(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": "source-projection-candidate",
        "core_opportunity_id": "source-projection-core",
        "market_anomaly_id": "source-projection-anomaly",
        "observed_at": "2026-07-15T12:00:00Z",
        "canonical_asset_id": "source-token",
        "coin_id": "source-token",
        "symbol": "SRC",
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.99,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "market_state_class": "confirmed_breakout",
        "market_anomaly_bucket": "high_liquidity_breakout",
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 12.0,
            "return_24h": 20.0,
            "relative_return_vs_btc_4h": 8.0,
            "volume_zscore_24h": 3.0,
            "volume_to_market_cap": 0.25,
            "liquidity_usd": 10_000_000,
            "spread_bps": 20.0,
            "freshness_status": "fresh",
        },
        "source_pack": "market_anomaly_pack",
        "source_origin": "market_anomaly",
        "source_origins": ["market_anomaly"],
        "research_only": True,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    row.update(overrides)
    row.update(decision_model.evaluate_radar_decision(row).to_dict())
    return row


def _independence_contract() -> dict[str, object]:
    return assess_source_independence(
        [
            {
                "source_id": "official-a",
                "url": "https://project.example/news/a",
                "published_at": "2026-07-15T11:00:00Z",
                "title": "Protocol launches audited mainnet upgrade",
                "body": (
                    "The protocol team launched its audited mainnet upgrade after "
                    "months of testing with validators and independent security "
                    "reviewers today."
                ),
            },
            {
                "source_id": "news-b",
                "url": "https://news.example/report/b",
                "published_at": "2026-07-15T11:05:00Z",
                "title": "Independent analysts confirm network upgrade deployment",
                "body": (
                    "Independent analysts observed the new network software producing "
                    "blocks while exchanges completed deposits and withdrawals without "
                    "reported disruption."
                ),
            },
        ]
    )


def test_closed_projection_preserves_exact_source_independence_and_is_idempotent():
    contract = _independence_contract()
    candidate = _candidate(
        source_independence=contract,
        independent_source_count=2,
        independent_corroboration_count=1,
        source_content_cluster_count=2,
    )

    projection = decision_model_values(candidate)

    assert projection["source_independence"] == contract
    assert projection["independent_source_count"] == contract[
        "independent_evidence_count"
    ]
    assert projection["independent_corroboration_count"] == contract[
        "independent_corroboration_count"
    ]
    assert projection["source_content_cluster_count"] == contract[
        "content_cluster_count"
    ]
    assert projection["source_independence_status"] == "assessed"
    assert projection["source_independence_errors"] == []
    assert decision_model_values(projection) == projection


def test_projection_without_contract_uses_explicit_unassessed_zeroes_only():
    candidate = _candidate(
        independent_source_count=99,
        independent_corroboration_count=98,
        source_content_cluster_count=99,
        source_domain_count=99,
        raw_event_ids=["raw-a", "raw-b"],
    )

    projection = decision_model_values(candidate)

    assert projection["source_independence"] == {}
    assert projection["independent_source_count"] == 0
    assert projection["independent_corroboration_count"] == 0
    assert projection["source_content_cluster_count"] == 0
    assert projection["source_independence_status"] == "unassessed"
    assert projection["source_independence_errors"] == []
    assert decision_model_values(projection) == projection


def test_runtime_assessment_error_projects_as_explicit_rejected_zeroes():
    projection = decision_model_values(
        _candidate(
            source_independence={},
            independent_source_count=0,
            independent_corroboration_count=0,
            source_content_cluster_count=0,
            source_independence_status="rejected",
            source_independence_errors=[
                "source_independence_source_context_incomplete"
            ],
        )
    )

    assert projection["source_independence"] == {}
    assert projection["source_independence_status"] == "rejected"
    assert projection["source_independence_errors"] == [
        "source_independence_source_context_incomplete"
    ]
    assert projection["independent_source_count"] == 0
    assert decision_model_values(projection) == projection


def test_projection_rejects_explicit_status_contract_contradictions():
    contract = _independence_contract()

    assessed_without_contract = decision_model_values(
        _candidate(source_independence={}, source_independence_status="assessed")
    )
    unassessed_with_contract = decision_model_values(
        _candidate(
            source_independence=contract,
            source_independence_status="unassessed",
        )
    )

    assert assessed_without_contract["source_independence_status"] == "rejected"
    assert assessed_without_contract["source_independence_errors"] == [
        "source_independence_assessed_without_contract"
    ]
    assert unassessed_with_contract["source_independence"] == {}
    assert unassessed_with_contract["source_independence_status"] == "rejected"
    assert unassessed_with_contract["source_independence_errors"] == [
        "source_independence_status_contract_mismatch"
    ]


def test_projection_can_close_one_valid_nested_contract_without_count_fallbacks():
    contract = _independence_contract()
    candidate = _candidate(
        latest_score_components={
            "source_independence": contract,
            "independent_source_count": 2,
            "independent_corroboration_count": 1,
            "source_content_cluster_count": 2,
        },
        source_count=27,
        accepted_evidence_count=14,
    )

    projection = decision_model_values(candidate)

    assert projection["source_independence"] == contract
    assert projection["independent_source_count"] == 2
    assert projection["independent_corroboration_count"] == 1
    assert projection["source_content_cluster_count"] == 2


def test_tampered_contract_and_alias_drift_fail_closed():
    contract = _independence_contract()
    tampered = deepcopy(contract)
    tampered["independent_evidence_count"] = 3
    invalid_contract = _candidate(
        source_independence=tampered,
        independent_source_count=3,
        independent_corroboration_count=1,
        source_content_cluster_count=2,
    )
    alias_drift = _candidate(
        source_independence=contract,
        independent_source_count=3,
        independent_corroboration_count=1,
        source_content_cluster_count=2,
    )

    assert decision_model_values(invalid_contract) == {}
    assert decision_model_values(alias_drift) == {}

    projection = decision_model_values(
        _candidate(
            source_independence=contract,
            independent_source_count=2,
            independent_corroboration_count=1,
            source_content_cluster_count=2,
        )
    )
    projection["independent_corroboration_count"] = 0
    assert decision_model_values(projection) == {}


def test_distinct_nested_event_contracts_are_combined_into_one_canonical_scope():
    first = _independence_contract()
    second = assess_source_independence(
        [
            {
                "source_id": "official-a",
                "url": "https://project.example/news/a",
                "published_at": "2026-07-15T11:00:00Z",
                "title": "Protocol launches audited mainnet upgrade",
                "body": (
                    "The protocol team launched its audited mainnet upgrade after "
                    "months of testing with validators and independent security "
                    "reviewers today."
                ),
            }
        ]
    )
    candidate = _candidate(
        score_components={"source_independence": first},
        latest_score_components={"source_independence": second},
    )

    projection = decision_model_values(candidate)

    assert projection["source_independence"]["raw_document_count"] == 2
    assert projection["independent_source_count"] == 2
    assert projection["independent_corroboration_count"] == 1


def test_shipped_projection_v1_without_source_extension_remains_idempotent():
    current = decision_model_values(_candidate())
    legacy = deepcopy(current)
    legacy["decision_projection_schema_version"] = (
        LEGACY_DECISION_PROJECTION_SCHEMA_VERSION
    )
    for field in (
        "source_independence",
        "independent_source_count",
        "independent_corroboration_count",
        "source_content_cluster_count",
        "source_independence_status",
        "source_independence_errors",
    ):
        legacy.pop(field)

    assert decision_model_values(legacy) == legacy


def test_projection_v2_reference_is_idempotent_and_hydrates_exact_contract(
    tmp_path,
):
    contract = _independence_contract()
    projection = decision_model_values(
        _candidate(
            source_independence=contract,
            source_independence_status="assessed",
            source_independence_errors=[],
            independent_source_count=2,
            independent_corroboration_count=1,
            source_content_cluster_count=2,
        )
    )

    persisted = source_independence_store.externalize(tmp_path, projection)

    assert persisted["source_independence"]["schema_id"] == (
        source_independence_store.REFERENCE_SCHEMA_ID
    )
    assert decision_model_values(persisted) == persisted
    assert source_independence_store.hydrate(tmp_path, persisted) == projection


def test_shipped_projection_v1_inline_contract_remains_idempotent():
    legacy = decision_model_values(
        _candidate(
            source_independence=_independence_contract(),
            source_independence_status="assessed",
            source_independence_errors=[],
            independent_source_count=2,
            independent_corroboration_count=1,
            source_content_cluster_count=2,
        )
    )
    legacy["decision_projection_schema_version"] = (
        LEGACY_DECISION_PROJECTION_SCHEMA_VERSION
    )

    assert decision_model_values(legacy) == legacy


def test_projection_reference_summary_tamper_fails_closed(tmp_path):
    projection = decision_model_values(
        _candidate(
            source_independence=_independence_contract(),
            source_independence_status="assessed",
            source_independence_errors=[],
            independent_source_count=2,
            independent_corroboration_count=1,
            source_content_cluster_count=2,
        )
    )
    persisted = source_independence_store.externalize(tmp_path, projection)
    persisted["source_independence"]["independent_evidence_count"] = 1

    assert decision_model_values(persisted) == {}
