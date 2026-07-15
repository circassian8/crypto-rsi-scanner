"""Adversarial exact-provenance tests for LLM catalyst frames."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import crypto_rsi_scanner.event_alpha.radar.catalyst_frame_binding as binding
import crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator as validator
import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as frames
import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as llm_frames
import crypto_rsi_scanner.event_alpha.radar.pipeline as pipeline
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent


def _source_and_analysis():
    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    raw = RawDiscoveredEvent(
        raw_id="bound",
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url="https://alpha.example/bound",
        title="Beta exchange lists TEST token today",
        body="The TEST listing is confirmed by Beta exchange.",
        raw_json={},
        source_confidence=0.9,
        content_hash="hash:bound",
    )
    frame = llm_frames.EventLLMCatalystFrame(
        frame_type="listing_liquidity_event",
        frame_role="main_catalyst",
        subject="TEST",
        actor="Beta exchange",
        affected_entities=("TEST",),
        affected_assets=("TEST",),
        event_archetype="listing_liquidity_event",
        claim_polarity="asserted",
        cause_status="confirmed",
        confidence=0.9,
        evidence_quote=raw.title,
        found_in_source=True,
    )
    analysis = llm_frames.EventLLMCatalystFrameAnalysis(
        schema_version=llm_frames.LLM_CATALYST_FRAME_SCHEMA_VERSION,
        provider="fixture",
        model=None,
        prompt_version="test",
        raw_id=raw.raw_id,
        main_catalyst_frame=frame,
    )
    return raw, frame, analysis


def _stored():
    raw, _frame, analysis = _source_and_analysis()
    result = validator.validate_llm_catalyst_frames(analysis, (raw,))
    return validator.apply_validation_to_raw_event(raw, analysis, result), analysis, result


def _tamper_both_frame_copies(raw, mutator):
    payload = deepcopy(raw.raw_json)
    validation = payload["llm_catalyst_frame_validation"]
    validation["valid_frames"][0] = mutator(validation["valid_frames"][0])
    validation["selected_main_frame"] = deepcopy(validation["valid_frames"][0])
    validation["llm_predicted_main_frame_type"] = validation["selected_main_frame"]["frame_type"]
    rule_type = validation["rule_predicted_impact_path"]
    llm_type = validation["llm_predicted_main_frame_type"]
    disagreement = bool(rule_type and llm_type and rule_type != llm_type)
    validation["frame_rule_disagreement"] = disagreement
    validation["disagreement_reason"] = f"rules={rule_type};llm={llm_type}" if disagreement else None
    validation["resolution"] = "llm_wins" if disagreement else "rules_win"
    validation["rule_llm_disagreements"] = (
        [validation["disagreement_reason"]] if disagreement else []
    )
    validation["validation_payload_sha256"] = binding.validation_payload_sha256(validation)
    return replace(raw, raw_json=payload)


def test_validation_is_bound_to_exact_analysis_and_invalid_identity_is_fail_soft():
    raw, frame, analysis = _source_and_analysis()
    result = validator.validate_llm_catalyst_frames(analysis, (raw,))
    contradictory = replace(
        analysis,
        main_catalyst_frame=replace(frame, object="materially different analysis"),
    )
    with pytest.raises(ValueError, match="different analysis"):
        validator.apply_validation_to_raw_event(raw, contradictory, result)

    stored = validator.apply_validation_to_raw_event(raw, analysis, result)
    payload = deepcopy(stored.raw_json)
    payload["llm_catalyst_frame_analysis"]["main_catalyst_frame"]["object"] = "mutated"
    assert binding.current_validation_for_raw(replace(stored, raw_json=payload)) is None
    forged = deepcopy(payload)
    forged_sha = binding.canonical_payload_sha256(forged["llm_catalyst_frame_analysis"])
    forged_validation = forged["llm_catalyst_frame_validation"]
    forged_validation["analysis_sha256"] = forged_sha
    for frame_row in forged_validation["valid_frames"]:
        frame_row["analysis_sha256"] = forged_sha
    forged_validation["selected_main_frame"]["analysis_sha256"] = forged_sha
    forged_validation["validation_payload_sha256"] = binding.validation_payload_sha256(
        forged_validation
    )
    assert binding.current_validation_for_raw(replace(stored, raw_json=forged)) is None

    unbound = pipeline._operating_cycle_validated_catalyst_frame_raw(
        raw,
        analysis=replace(analysis, raw_id="wrong"),
        required=True,
        required_reason="test",
    )
    assert unbound.raw_json["catalyst_frame_status"] == "unresolved"
    assert unbound.raw_json["catalyst_frame_skip_reason"] == "catalyst_frame_source_binding_invalid"
    assert "llm_catalyst_frame_validation" not in unbound.raw_json


def test_weak_quotes_and_ticker_substring_identity_fail_closed():
    raw, frame, analysis = _source_and_analysis()
    weak = replace(analysis, main_catalyst_frame=replace(frame, evidence_quote="a"))
    weak_result = validator.validate_llm_catalyst_frames(weak, (raw,))
    assert weak_result.invalid_frames[0]["reason"] == "llm_frame_quote_too_weak"
    invalid_type = replace(analysis, main_catalyst_frame=replace(frame, frame_type="made_up_route"))
    assert validator.validate_llm_catalyst_frames(
        invalid_type, (raw,)
    ).invalid_frames[0]["reason"] == "llm_frame_type_invalid"
    invalid_confidence = replace(analysis, main_catalyst_frame=replace(frame, confidence=float("nan")))
    assert validator.validate_llm_catalyst_frames(
        invalid_confidence, (raw,)
    ).invalid_frames[0]["reason"] == "llm_frame_confidence_invalid"
    missing_identity = replace(
        analysis,
        main_catalyst_frame=replace(
            frame,
            subject=None,
            actor=None,
            affected_entities=(),
            affected_assets=(),
        ),
    )
    assert validator.validate_llm_catalyst_frames(
        missing_identity, (raw,)
    ).invalid_frames[0]["reason"] == "llm_frame_identity_missing"

    collision_raw = replace(
        raw,
        title="Someone announced a market catalyst today",
        body="No named crypto asset appears in this article.",
        content_hash="hash:collision",
    )
    collision_frame = replace(
        frame,
        subject="ONE",
        actor=None,
        affected_entities=("ONE",),
        affected_assets=("ONE",),
        evidence_quote=collision_raw.title,
    )
    collision = replace(
        analysis,
        raw_id=collision_raw.raw_id,
        main_catalyst_frame=collision_frame,
    )
    collision_result = validator.validate_llm_catalyst_frames(collision, (collision_raw,))
    assert collision_result.invalid_frames[0]["reason"] == "crypto_asset_identity_not_in_source"
    assert binding.asset_identity_in_evidence("ONE", "someone announced the news") is False
    assert binding.asset_identity_in_evidence("IN", "policy changed in parliament") is False
    assert binding.asset_identity_in_evidence("ARB", "an arbitrary result appeared") is False
    assert binding.asset_identity_in_evidence("ZEC", "ZEC treasury strategy") is True


@pytest.mark.parametrize(
    "mutation",
    [
        "type",
        "confidence",
        "frame_id",
        "offset_type",
        "source_confidence_type",
        "extra_frame_key",
        "extra_validation_key",
        "validation_list_type",
        "derived",
    ],
)
def test_rehydration_rejects_semantic_frame_and_derived_metadata_forgery(mutation):
    stored, _analysis, _result = _stored()

    def mutate(frame):
        row = deepcopy(frame)
        if mutation == "type":
            row["frame_type"] = "made_up_route"
            row["frame_id"] = binding.canonical_llm_frame_id(
                raw_id=stored.raw_id,
                frame_type=row["frame_type"],
                frame_role=row["frame_role"],
                subject=row["subject"],
                evidence_quote=row["evidence_quote"],
            )
        elif mutation == "confidence":
            row["confidence"] = "not-a-number"
        elif mutation == "frame_id":
            row["frame_id"] = "frame:rule:forged"
        elif mutation == "offset_type":
            row["evidence_normalized_start"] = 0.0
        elif mutation == "source_confidence_type":
            row["source_confidence"] = "0.9"
        elif mutation == "extra_frame_key":
            row["unrecognized_semantic_override"] = "trusted"
        return row

    forged = _tamper_both_frame_copies(stored, mutate)
    if mutation == "derived":
        payload = deepcopy(forged.raw_json)
        validation = payload["llm_catalyst_frame_validation"]
        validation["frame_rule_disagreement"] = not validation["frame_rule_disagreement"]
        validation["validation_payload_sha256"] = binding.validation_payload_sha256(validation)
        forged = replace(forged, raw_json=payload)
    if mutation == "extra_validation_key":
        payload = deepcopy(forged.raw_json)
        validation = payload["llm_catalyst_frame_validation"]
        validation["unrecognized_policy_override"] = True
        validation["validation_payload_sha256"] = binding.validation_payload_sha256(validation)
        forged = replace(forged, raw_json=payload)
    if mutation == "validation_list_type":
        payload = deepcopy(forged.raw_json)
        validation = payload["llm_catalyst_frame_validation"]
        validation["frame_warnings"] = [1]
        validation["validation_payload_sha256"] = binding.validation_payload_sha256(validation)
        forged = replace(forged, raw_json=payload)
    assert binding.current_validation_for_raw(forged) is None
    assert not any(
        frame.frame_id.startswith("frame:llm:")
        for frame in frames.build_catalyst_frames((forged,))
    )


def test_fetch_clock_and_enriched_provenance_drift_invalidate_binding():
    stored, _analysis, _result = _stored()
    assert binding.current_validation_for_raw(stored) is not None
    assert binding.current_validation_for_raw(
        replace(stored, fetched_at=stored.fetched_at + timedelta(minutes=1))
    ) is None
    assert binding.current_validation_for_raw(replace(stored, source_confidence=0.8)) is None

    raw, frame, analysis = _source_and_analysis()
    enriched = replace(
        raw,
        raw_json={
            "source_enrichment": {
                "article_quality_status": "good",
                "cleaner_version": "cleaner-v1",
                "enriched_text": raw.title,
                "article": {"final_url": raw.source_url},
            },
        },
    )
    enriched_result = validator.validate_llm_catalyst_frames(analysis, (enriched,))
    enriched_stored = validator.apply_validation_to_raw_event(enriched, analysis, enriched_result)
    payload = deepcopy(enriched_stored.raw_json)
    payload["source_enrichment"]["cleaner_version"] = "cleaner-v2"
    assert binding.current_validation_for_raw(replace(enriched_stored, raw_json=payload)) is None
