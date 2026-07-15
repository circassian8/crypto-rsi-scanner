"""Static evidence-policy fragments for the Event Alpha North Star report."""

from __future__ import annotations

from typing import Any


SOURCE_AUTHORITY_POLICY: dict[str, Any] = {
    "canonical_classifier": "event_alpha.providers.source_registry",
    "authority_inputs": ["exact canonical provider id", "exact or child trusted hostname"],
    "article_text_may_establish_authority": False,
    "source_origin_or_source_class_hint_may_establish_authority": False,
    "shared_hosting_authority": {
        "medium.com": "context_only_without_separate_ownership_attestation",
        "github.com": "context_only_without_separate_ownership_attestation",
    },
    "lookalike_hostname_policy": "exact-or-child boundary match; sibling and suffix lookalikes fail closed",
    "project_blog_rss_role": "transport_not_automatic_official_project_attestation",
    "evidence_quality_reuses_registry_authority": True,
    "source_pack_impact_validation": "requires membership in declared impact_path_validating_sources",
    "unverified_authority_claim_action": "retain as capped context with source_authority_unverified",
    "historical_artifacts_rewritten": False,
}

LLM_CATALYST_FRAME_BINDING_POLICY: dict[str, Any] = {
    "analysis_raw_resolution": "exactly_one_matching_raw_id_required",
    "eligible_source_fields": ["title", "body", "quality_gated_enriched_text"],
    "quote_matching": "normalized_contiguous_span_within_one_source_field",
    "minimum_quote_contract": "at_least_10_normalized_chars_two_terms_and_one_four_char_term",
    "cross_raw_event_or_cross_field_quote_matching": False,
    "fuzzy_term_overlap_allowed": False,
    "analysis_binding": "canonical_analysis_payload_sha256_required",
    "validation_integrity": "canonical_validation_payload_sha256_required",
    "frame_schema_validation": "closed_keys_enums_types_finite_confidence_and_canonical_frame_id",
    "short_ticker_identity": "token_boundary_plus_crypto_context_or_dollar_ticker_required",
    "binding_fields": [
        "source_raw_id",
        "source_provider",
        "source_url",
        "source_published_at",
        "source_fetched_at",
        "source_confidence",
        "source_content_hash",
        "source_surface_hash",
        "source_surface_provenance_hash",
        "analysis_sha256",
        "validation_payload_sha256",
        "evidence_source_field",
        "evidence_normalized_start",
        "evidence_normalized_end",
    ],
    "apply_and_rehydration": "fail_closed_on_any_binding_drift",
    "invalid_analysis_identity": "fail_soft_unresolved_without_current_validation",
    "enriched_source_provenance": "quality_triage_extractor_cleaner_url_and_source_enrichment_hash_bound",
    "legacy_unbound_frames": "historical_bytes_preserved_but_not_current_evidence",
    "provider_output_schema_changed": False,
    "routing_authority": "deterministic_validation_only",
    "research_only": True,
}

CATALYST_ATTRIBUTION_POLICY: dict[str, Any] = {
    "schema": "event_alpha.catalyst_attribution v1",
    "unit_of_evidence": "one exact source bound to one exact market anomaly",
    "anomaly_binding": "digest of anomaly id, UTC clock, provider/content identity, canonical asset, snapshot identity, state, bucket, and market snapshot",
    "source_public_clock": "published_at_then_fetched_at",
    "claimed_event_time_is_separate": True,
    "contemporaneous_tolerance_seconds": 300,
    "temporal_relations": [
        "antecedent", "contemporaneous", "retrospective", "unknown",
    ],
    "causal_eligibility": (
        "antecedent_or_contemporaneous plus direct official evidence or a "
        "validated direct beneficiary with a strong impact path"
    ),
    "retrospective_source_use": "context_only_never_causal_confirmation",
    "background_historical_reaction_side_note_use": "context_only",
    "semantic_role_contract": "only the eight canonical catalyst-frame roles; unrecognized explicit roles are noncausal",
    "negated_corrective_ruled_out_use": "disproof",
    "scheduled_future_event": (
        "may be scheduled_anticipation only when its source was already public"
    ),
    "missing_or_naive_clock": "unknown_and_not_causal",
    "source_url_credentials": "credential paths or userinfo rejected; all query and fragment data removed",
    "canonical_propagation": [
        "raw catalyst-search attachment",
        "discovery candidate data quality",
        "alert evidence components",
        "integrated candidate",
        "CoreOpportunity",
        "Decision v2 projection",
        "pending outcome",
    ],
    "decision_policy": (
        "once attribution is supplied, malformed or exclusively noncausal "
        "evidence cannot fall back to hostname or accepted-count confirmation"
    ),
    "foreign_or_mixed_binding": "reject the complete supplied attribution set and retain rejection telemetry",
    "historical_rows_without_attribution": "retain_v2_compatibility_heuristic",
    "historical_artifacts_rewritten": False,
    "research_only": True,
    "auto_apply": False,
    "research_basis": [
        "MacKinlay 1997 event-study timing and event-window discipline",
        "Miller 2023 event-study design and interpretation guidance",
    ],
}
