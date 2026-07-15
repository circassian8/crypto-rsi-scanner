"""Pure, closed source-independence assessment for catalyst evidence.

The contract deliberately measures content and origin independence only.  It
does not infer that a source is authoritative, accurate, or causally relevant.
Those are separate policy decisions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import re
import unicodedata
from typing import Any
from urllib.parse import urlsplit, urlunsplit


SCHEMA_ID = "event_alpha.source_independence"
SCHEMA_VERSION = 1
SHINGLE_SIZE = 3
MIN_NEAR_DUPLICATE_TOKENS = 12
NEAR_DUPLICATE_JACCARD_THRESHOLD = 0.80
MAX_DOCUMENTS = 128
MAX_SOURCE_ID_CHARS = 256
MAX_METADATA_CHARS = 256
MAX_URL_CHARS = 2_048
MAX_TITLE_CHARS = 2_048
MAX_BODY_CHARS = 32_768
MAX_NORMALIZED_TEXT_CHARS = 34_816
MAX_SHINGLES_PER_DOCUMENT = 4_096

ALGORITHM = {
    "normalization": "unicode_nfkc_casefold_alnum_whitespace_v1",
    "exact_match": "sha256_normalized_title_newline_body",
    "shingle_size_words": SHINGLE_SIZE,
    "minimum_near_duplicate_tokens": MIN_NEAR_DUPLICATE_TOKENS,
    "near_duplicate_metric": "set_jaccard",
    "near_duplicate_threshold": NEAR_DUPLICATE_JACCARD_THRESHOLD,
    "cluster_assignment": (
        "public_time_then_source_id_sorted_canonical_representatives_only"
    ),
    "origin_normalization": (
        "http_https_urlsplit_hostname_lower_strip_trailing_dot_strip_www"
    ),
    "max_documents": MAX_DOCUMENTS,
    "max_source_id_chars": MAX_SOURCE_ID_CHARS,
    "max_metadata_chars": MAX_METADATA_CHARS,
    "max_url_chars": MAX_URL_CHARS,
    "max_title_chars": MAX_TITLE_CHARS,
    "max_body_chars": MAX_BODY_CHARS,
    "max_normalized_text_chars": MAX_NORMALIZED_TEXT_CHARS,
    "max_shingles_per_document": MAX_SHINGLES_PER_DOCUMENT,
    "authority_policy": "not_assessed",
}

_TOP_KEYS = {
    "schema_id",
    "schema_version",
    "algorithm",
    "raw_document_count",
    "distinct_origin_count",
    "distinct_origins",
    "content_cluster_count",
    "corroboration_eligible_cluster_count",
    "independent_evidence_count",
    "independent_corroboration_count",
    "has_independent_corroboration",
    "independent_representative_ids",
    "corroborating_representative_ids",
    "documents",
    "clusters",
    "unassessable_document_ids",
    "rejected_document_ids",
    "reason_codes",
    "authority_assessed",
    "research_only",
    "contract_digest",
}

_DOCUMENT_INPUT_KEYS = {
    "source_id",
    "source_id_status",
    "source_id_input_digest",
    "source_provider",
    "source_provider_status",
    "source_class",
    "source_class_status",
    "source_url",
    "source_url_input_digest",
    "source_url_status",
    "canonical_origin",
    "published_at",
    "published_at_status",
    "published_at_input_digest",
    "fetched_at",
    "fetched_at_status",
    "fetched_at_input_digest",
    "public_time",
    "public_time_status",
    "normalized_title",
    "title_input_status",
    "title_input_length",
    "title_input_digest",
    "normalized_body",
    "body_input_status",
    "body_input_length",
    "body_input_digest",
}

_DOCUMENT_KEYS = _DOCUMENT_INPUT_KEYS | {
    "document_id",
    "input_digest",
    "normalized_text",
    "content_digest",
    "token_count",
    "shingle_count",
    "content_similarity_status",
    "assessment_status",
    "cluster_id",
    "match_kind",
    "representative_similarity",
    "authority_status",
    "reason_codes",
}

_CLUSTER_KEYS = {
    "cluster_id",
    "representative_id",
    "evidence_representative_id",
    "representative_content_digest",
    "member_count",
    "members",
    "canonical_origins",
    "corroboration_eligible",
    "independent_evidence_unit",
    "corroborating_unit",
}

_MEMBER_KEYS = {"document_id", "match_kind", "similarity"}
_HOST_RE = re.compile(r"^[a-z0-9.-]+$")


def assess_source_independence(
    sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return a deterministic closed v1 assessment for bounded source rows."""

    if isinstance(sources, (str, bytes, bytearray)) or not isinstance(
        sources, Sequence
    ):
        raise TypeError("sources must be a bounded sequence of mappings")
    if len(sources) > MAX_DOCUMENTS:
        raise ValueError("source_independence_document_limit_exceeded")
    prepared: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, Mapping):
            raise TypeError("every source-independence input must be a mapping")
        prepared.append(_prepare_source(source))
    return _build_contract(prepared)


def assess_source_independence_safe(
    sources: Sequence[Mapping[str, Any]],
    *,
    expected_document_count: int | None = None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Fail soft for runtime cycles while retaining explicit closed errors."""

    if expected_document_count is not None and (
        type(expected_document_count) is not int or expected_document_count < 0
    ):
        return {}, ("source_independence_expected_count_invalid",)
    if isinstance(sources, (str, bytes, bytearray)) or not isinstance(
        sources, Sequence
    ):
        return {}, ("source_independence_inputs_invalid",)
    if expected_document_count is not None and len(sources) != expected_document_count:
        return {}, ("source_independence_source_context_incomplete",)
    if len(sources) > MAX_DOCUMENTS:
        return {}, ("source_independence_document_limit_exceeded",)
    try:
        contract = assess_source_independence(sources)
    except (TypeError, ValueError, OverflowError):
        return {}, ("source_independence_assessment_failed",)
    if validate_contract(contract):
        return {}, ("source_independence_contract_validation_failed",)
    return contract, ()


def validate_contract(value: Mapping[str, Any]) -> list[str]:
    """Validate and fully recompute a source-independence v1 contract."""

    errors: list[str] = []
    if not isinstance(value, Mapping):
        return ["source_independence_contract_not_mapping"]
    keys = set(value)
    if keys != _TOP_KEYS:
        errors.append("source_independence_contract_keys_invalid")
    if value.get("schema_id") != SCHEMA_ID:
        errors.append("source_independence_schema_id_invalid")
    version = value.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        errors.append("source_independence_schema_version_invalid")
    if value.get("algorithm") != ALGORITHM:
        errors.append("source_independence_algorithm_invalid")
    if value.get("research_only") is not True:
        errors.append("source_independence_research_only_invalid")
    if value.get("authority_assessed") is not False:
        errors.append("source_independence_authority_scope_invalid")
    digest = value.get("contract_digest")
    try:
        digest_valid = isinstance(digest, str) and digest == _digest_without(
            value, "contract_digest"
        )
    except (TypeError, ValueError, OverflowError):
        digest_valid = False
    if not digest_valid:
        errors.append("source_independence_contract_digest_invalid")

    documents = value.get("documents")
    clusters = value.get("clusters")
    if not isinstance(documents, list):
        errors.append("source_independence_documents_invalid")
        return sorted(set(errors))
    if len(documents) > MAX_DOCUMENTS:
        errors.append("source_independence_document_limit_exceeded")
        return sorted(set(errors))
    if not isinstance(clusters, list):
        errors.append("source_independence_clusters_invalid")
    prepared: list[dict[str, Any]] = []
    for document in documents:
        if not isinstance(document, Mapping) or set(document) != _DOCUMENT_KEYS:
            errors.append("source_independence_document_contract_invalid")
            continue
        input_values = {key: document.get(key) for key in _DOCUMENT_INPUT_KEYS}
        prepared.append(input_values)
    if isinstance(clusters, list):
        for cluster in clusters:
            if not isinstance(cluster, Mapping) or set(cluster) != _CLUSTER_KEYS:
                errors.append("source_independence_cluster_contract_invalid")
                continue
            members = cluster.get("members")
            if not isinstance(members, list) or any(
                not isinstance(member, Mapping) or set(member) != _MEMBER_KEYS
                for member in members
            ):
                errors.append("source_independence_cluster_members_invalid")
    if errors:
        return sorted(set(errors))
    try:
        expected = _build_contract(prepared)
    except (TypeError, ValueError, OverflowError):
        return [
            "source_independence_contract_recomputation_failed",
            "source_independence_contract_semantics_mismatch",
        ]
    if dict(value) != expected:
        errors.append("source_independence_contract_semantics_mismatch")
    return sorted(set(errors))


validate_source_independence_contract = validate_contract


def validate_source_independence_container(
    container: Mapping[str, Any], *, prefix: str = ""
) -> list[str]:
    """Validate the closed status/error/count wrapper around one contract."""

    if not isinstance(container, Mapping):
        return ["source_independence_container_not_mapping"]
    errors: list[str] = []
    status = container.get(f"{prefix}source_independence_status")
    if status != "assessed":
        errors.append("source_independence_container_not_assessed")
    reported = container.get(f"{prefix}source_independence_errors")
    if (
        not isinstance(reported, (list, tuple))
        or any(not isinstance(item, str) or not item for item in reported)
    ):
        errors.append("source_independence_container_errors_invalid")
    elif reported:
        errors.append("source_independence_container_has_errors")
    contract = container.get(f"{prefix}source_independence")
    if not isinstance(contract, Mapping):
        errors.append("source_independence_container_contract_missing")
        return sorted(set(errors))
    errors.extend(validate_contract(contract))
    aliases = {
        f"{prefix}independent_source_count": "independent_evidence_count",
        f"{prefix}independent_corroboration_count": "independent_corroboration_count",
        f"{prefix}source_content_cluster_count": "content_cluster_count",
    }
    for alias, contract_key in aliases.items():
        value = container.get(alias)
        if type(value) is not int or value != contract.get(contract_key):
            errors.append("source_independence_container_alias_mismatch")
    return sorted(set(errors))


def validated_source_independence_container(
    container: Mapping[str, Any], *, prefix: str = ""
) -> dict[str, Any]:
    """Return the inner contract only when the complete wrapper is coherent."""

    if validate_source_independence_container(container, prefix=prefix):
        return {}
    return dict(container[f"{prefix}source_independence"])


def combine_contracts(
    contracts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return one exact union for validated contracts from the same evidence scope.

    Duplicate document inputs are retained once. Callers remain responsible for
    keeping event-source and later acquisition-source scopes separate.
    """

    if isinstance(contracts, (str, bytes, bytearray)) or not isinstance(
        contracts, Sequence
    ):
        raise TypeError("contracts must be a bounded sequence of mappings")
    prepared_by_digest: dict[str, dict[str, Any]] = {}
    for contract in contracts:
        errors = validate_contract(contract)
        if errors:
            raise ValueError("source_independence_contract_invalid:" + ",".join(errors))
        documents = contract.get("documents")
        if not isinstance(documents, list):
            raise ValueError("source_independence_documents_invalid")
        for document in documents:
            if not isinstance(document, Mapping):
                raise ValueError("source_independence_document_contract_invalid")
            input_digest = document.get("input_digest")
            if not isinstance(input_digest, str) or not _is_sha256(input_digest):
                raise ValueError("source_independence_input_digest_invalid")
            prepared = {
                key: document.get(key) for key in _DOCUMENT_INPUT_KEYS
            }
            existing = prepared_by_digest.get(input_digest)
            if existing is not None and existing != prepared:
                raise ValueError("source_independence_input_digest_collision")
            prepared_by_digest[input_digest] = prepared
    if len(prepared_by_digest) > MAX_DOCUMENTS:
        raise ValueError("source_independence_document_limit_exceeded")
    return _build_contract(list(prepared_by_digest.values()))


combine_source_independence_contracts = combine_contracts


def _prepare_source(source: Mapping[str, Any]) -> dict[str, Any]:
    source_id_raw = _first(source, "source_id", "raw_id", "event_id", "id")
    source_id, source_id_status, source_id_digest = _bounded_identity(source_id_raw)
    provider, provider_status = _bounded_metadata(
        _first(source, "provider", "source_provider")
    )
    source_class, source_class_status = _bounded_metadata(source.get("source_class"))

    raw_url = _first(source, "source_url", "url", "link")
    safe_url, origin, url_status, url_digest = _canonical_url(raw_url)
    title = _normalize_text_input(
        _first(source, "title", "headline", "name"), MAX_TITLE_CHARS
    )
    body = _normalize_text_input(
        _first(source, "body", "summary", "description", "content", "text"),
        MAX_BODY_CHARS,
    )
    published = _canonical_time(source.get("published_at"))
    fetched = _canonical_time(source.get("fetched_at"))
    public_time, public_status = _public_time(published, fetched)
    base = {
        "source_id": source_id,
        "source_id_status": source_id_status,
        "source_id_input_digest": source_id_digest,
        "source_provider": provider,
        "source_provider_status": provider_status,
        "source_class": source_class,
        "source_class_status": source_class_status,
        "source_url": safe_url,
        "source_url_input_digest": url_digest,
        "source_url_status": url_status,
        "canonical_origin": origin,
        "published_at": published[0],
        "published_at_status": published[1],
        "published_at_input_digest": published[2],
        "fetched_at": fetched[0],
        "fetched_at_status": fetched[1],
        "fetched_at_input_digest": fetched[2],
        "public_time": public_time,
        "public_time_status": public_status,
        "normalized_title": title[0],
        "title_input_status": title[1],
        "title_input_length": title[2],
        "title_input_digest": title[3],
        "normalized_body": body[0],
        "body_input_status": body[1],
        "body_input_length": body[2],
        "body_input_digest": body[3],
    }
    if not source_id:
        identity_surface = {key: base[key] for key in sorted(base) if key != "source_id"}
        base["source_id"] = "derived:" + _digest(identity_surface)[:24]
    return base


def _build_contract(prepared: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    documents, shingle_sets = _derive_documents(prepared)
    clusters = _cluster_documents(documents, shingle_sets)
    finalized_documents, selected_representatives = _finalize_cluster_semantics(
        documents, clusters
    )
    return _build_contract_row(
        finalized_documents, clusters, selected_representatives
    )


def _derive_documents(
    prepared: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, frozenset[str]]]:
    canonical_inputs = [_validate_prepared_input(item) for item in prepared]
    canonical_inputs.sort(key=_canonical_json)
    occurrences: dict[str, int] = {}
    documents: list[dict[str, Any]] = []
    shingle_sets: dict[str, frozenset[str]] = {}
    for item in canonical_inputs:
        input_digest = _digest(item)
        occurrences[input_digest] = occurrences.get(input_digest, 0) + 1
        document_id = (
            f"source:{input_digest[:24]}:{occurrences[input_digest]:03d}"
        )
        document, shingles = _derive_document(item, document_id, input_digest)
        documents.append(document)
        shingle_sets[document_id] = shingles
    documents.sort(key=_document_sort_key)
    return documents, shingle_sets


def _cluster_documents(
    documents: list[dict[str, Any]],
    shingle_sets: Mapping[str, frozenset[str]],
) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    exact_clusters: dict[str, dict[str, Any]] = {}
    for document in documents:
        if document["assessment_status"] == "rejected" or not document["content_digest"]:
            continue
        exact = exact_clusters.get(document["content_digest"])
        if exact is not None:
            _append_cluster_member(exact, document, "exact", 1.0)
            continue
        selected: dict[str, Any] | None = None
        selected_similarity = 0.0
        if document["content_similarity_status"] == "assessable":
            current = shingle_sets[document["document_id"]]
            for cluster in clusters:
                representative_id = cluster["representative_id"]
                representative = _document_by_id(documents, representative_id)
                if representative["content_similarity_status"] != "assessable":
                    continue
                similarity = _jaccard(current, shingle_sets[representative_id])
                if similarity < NEAR_DUPLICATE_JACCARD_THRESHOLD:
                    continue
                if selected is None or (
                    similarity,
                    _reverse_text(cluster["representative_id"]),
                ) > (
                    selected_similarity,
                    _reverse_text(selected["representative_id"]),
                ):
                    selected = cluster
                    selected_similarity = similarity
        if selected is not None:
            _append_cluster_member(
                selected, document, "near_duplicate", selected_similarity
            )
            exact_clusters[document["content_digest"]] = selected
            continue
        cluster_id = "cluster:" + _digest(
            {
                "representative_id": document["document_id"],
                "content_digest": document["content_digest"],
            }
        )[:24]
        cluster = {
            "cluster_id": cluster_id,
            "representative_id": document["document_id"],
            "evidence_representative_id": None,
            "representative_content_digest": document["content_digest"],
            "member_count": 0,
            "members": [],
            "canonical_origins": [],
            "corroboration_eligible": False,
            "independent_evidence_unit": False,
            "corroborating_unit": False,
        }
        _append_cluster_member(cluster, document, "representative", 1.0)
        clusters.append(cluster)
        exact_clusters[document["content_digest"]] = cluster
    return clusters


def _finalize_cluster_semantics(
    documents: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    document_lookup = {document["document_id"]: document for document in documents}
    for cluster in clusters:
        member_documents = [
            document_lookup[member["document_id"]] for member in cluster["members"]
        ]
        eligible = [
            document
            for document in member_documents
            if document["assessment_status"] == "eligible"
        ]
        cluster["canonical_origins"] = sorted(
            {
                document["canonical_origin"]
                for document in member_documents
                if document["canonical_origin"]
            }
        )
        cluster["corroboration_eligible"] = bool(eligible)
        cluster["evidence_representative_id"] = (
            min(eligible, key=_document_sort_key)["document_id"] if eligible else None
        )
        cluster["member_count"] = len(cluster["members"])

    selected_representatives: list[str] = []
    seen_origins: set[str] = set()
    for cluster in clusters:
        if not cluster["corroboration_eligible"]:
            continue
        eligible_origins = set(cluster["canonical_origins"])
        if selected_representatives and not (eligible_origins - seen_origins):
            seen_origins.update(eligible_origins)
            continue
        cluster["independent_evidence_unit"] = True
        cluster["corroborating_unit"] = bool(selected_representatives)
        selected_representatives.append(cluster["evidence_representative_id"])
        seen_origins.update(eligible_origins)

    cluster_lookup = {cluster["cluster_id"]: cluster for cluster in clusters}
    member_lookup = {
        member["document_id"]: (cluster["cluster_id"], member)
        for cluster in clusters
        for member in cluster["members"]
    }
    finalized_documents: list[dict[str, Any]] = []
    for document in documents:
        cluster_member = member_lookup.get(document["document_id"])
        if cluster_member:
            cluster_id, member = cluster_member
            document["cluster_id"] = cluster_id
            document["match_kind"] = member["match_kind"]
            document["representative_similarity"] = member["similarity"]
            if member["match_kind"] == "exact":
                document["reason_codes"] = sorted(
                    {*document["reason_codes"], "content_exact_duplicate"}
                )
            elif member["match_kind"] == "near_duplicate":
                document["reason_codes"] = sorted(
                    {*document["reason_codes"], "content_near_duplicate"}
                )
            if not cluster_lookup[cluster_id]["corroboration_eligible"]:
                document["reason_codes"] = sorted(
                    {*document["reason_codes"], "cluster_not_corroboration_eligible"}
                )
        finalized_documents.append(document)
    return finalized_documents, selected_representatives


def _build_contract_row(
    finalized_documents: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    selected_representatives: list[str],
) -> dict[str, Any]:
    independent_count = len(selected_representatives)
    corroborating_ids = selected_representatives[1:]
    distinct_origins = sorted(
        {
            document["canonical_origin"]
            for document in finalized_documents
            if document["canonical_origin"]
        }
    )
    unassessable = sorted(
        document["document_id"]
        for document in finalized_documents
        if document["assessment_status"] == "unassessable"
    )
    rejected = sorted(
        document["document_id"]
        for document in finalized_documents
        if document["assessment_status"] == "rejected"
    )
    reasons: set[str] = set()
    if unassessable:
        reasons.add("sources_unassessable")
    if rejected:
        reasons.add("sources_rejected")
    if independent_count < 2:
        reasons.add("independent_corroboration_absent")
    row: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "algorithm": dict(ALGORITHM),
        "raw_document_count": len(finalized_documents),
        "distinct_origin_count": len(distinct_origins),
        "distinct_origins": distinct_origins,
        "content_cluster_count": len(clusters),
        "corroboration_eligible_cluster_count": sum(
            bool(cluster["corroboration_eligible"]) for cluster in clusters
        ),
        "independent_evidence_count": independent_count,
        "independent_corroboration_count": max(0, independent_count - 1),
        "has_independent_corroboration": independent_count >= 2,
        "independent_representative_ids": selected_representatives,
        "corroborating_representative_ids": corroborating_ids,
        "documents": finalized_documents,
        "clusters": clusters,
        "unassessable_document_ids": unassessable,
        "rejected_document_ids": rejected,
        "reason_codes": sorted(reasons),
        "authority_assessed": False,
        "research_only": True,
    }
    row["contract_digest"] = _digest(row)
    return row


def _validate_prepared_input(item: Mapping[str, Any]) -> dict[str, Any]:
    if set(item) != _DOCUMENT_INPUT_KEYS:
        raise ValueError("source_independence_prepared_input_invalid")
    values = {key: item.get(key) for key in _DOCUMENT_INPUT_KEYS}
    digest_keys = {
        "source_id_input_digest",
        "source_url_input_digest",
        "published_at_input_digest",
        "fetched_at_input_digest",
        "title_input_digest",
        "body_input_digest",
    }
    if any(not _is_sha256(values[key]) for key in digest_keys):
        raise ValueError("source_independence_input_digest_invalid")

    source_id = values["source_id"]
    source_id_status = values["source_id_status"]
    if source_id_status == "present":
        if (
            not isinstance(source_id, str)
            or not source_id.strip()
            or source_id != source_id.strip()
            or len(source_id) > MAX_SOURCE_ID_CHARS
        ):
            raise ValueError("source_independence_source_id_invalid")
    elif source_id_status in {"derived", "invalid_type", "overflow"}:
        if (
            not isinstance(source_id, str)
            or not source_id.startswith("derived:")
            or len(source_id) > MAX_SOURCE_ID_CHARS
        ):
            raise ValueError("source_independence_derived_source_id_invalid")
    else:
        raise ValueError("source_independence_source_id_status_invalid")

    for field in ("source_provider", "source_class"):
        status = values[f"{field}_status"]
        field_value = values[field]
        if status == "present":
            normalized, normalized_status = _bounded_metadata(field_value)
            if normalized_status != "present" or normalized != field_value:
                raise ValueError(f"source_independence_{field}_invalid")
        elif status in {"missing", "invalid_type", "overflow"}:
            if field_value is not None:
                raise ValueError(f"source_independence_{field}_must_be_absent")
        else:
            raise ValueError(f"source_independence_{field}_status_invalid")

    url_status = values["source_url_status"]
    if url_status == "present":
        safe_url, origin, status, _ = _canonical_url(values["source_url"])
        if (
            status != "present"
            or safe_url != values["source_url"]
            or origin != values["canonical_origin"]
        ):
            raise ValueError("source_independence_canonical_origin_invalid")
    elif url_status in {
        "missing",
        "invalid_type",
        "overflow",
        "malformed",
        "userinfo_rejected",
        "port_rejected",
        "scheme_rejected",
        "host_rejected",
    }:
        if values["source_url"] is not None or values["canonical_origin"] is not None:
            raise ValueError("source_independence_rejected_origin_present")
    else:
        raise ValueError("source_independence_source_url_status_invalid")

    canonical_times: dict[str, tuple[str | None, str, str]] = {}
    for field in ("published_at", "fetched_at"):
        status = values[f"{field}_status"]
        field_value = values[field]
        if status == "present":
            canonical = _canonical_time(field_value)
            if canonical[1] != "present" or canonical[0] != field_value:
                raise ValueError(f"source_independence_{field}_invalid")
            canonical_times[field] = (field_value, "present", "")
        elif status in {"missing", "invalid_type", "malformed"}:
            if field_value is not None:
                raise ValueError(f"source_independence_{field}_must_be_absent")
            canonical_times[field] = (None, status, "")
        else:
            raise ValueError(f"source_independence_{field}_status_invalid")
    public_time, public_status = _public_time(
        canonical_times["published_at"], canonical_times["fetched_at"]
    )
    if (
        values["public_time"] != public_time
        or values["public_time_status"] != public_status
    ):
        raise ValueError("source_independence_public_time_invalid")

    for field, limit in (("title", MAX_TITLE_CHARS), ("body", MAX_BODY_CHARS)):
        normalized_key = f"normalized_{field}"
        status_key = f"{field}_input_status"
        length_key = f"{field}_input_length"
        normalized_value = values[normalized_key]
        status = values[status_key]
        length = values[length_key]
        if type(length) is not int or length < 0:
            raise ValueError(f"source_independence_{field}_length_invalid")
        if status == "present":
            normalized = _normalize_text_input(normalized_value, limit)
            if (
                normalized[1] != "present"
                or normalized[0] != normalized_value
                # NFKC/casefold can expand one raw code point into several
                # normalized characters (for example the ffi ligature).
                # The persisted length describes the bounded raw input, so it
                # must not be compared with the normalized output length.
                or length == 0
                or length > limit
            ):
                raise ValueError(f"source_independence_normalized_{field}_invalid")
        elif status == "missing":
            if normalized_value is not None or length > limit:
                raise ValueError(f"source_independence_missing_{field}_invalid")
        elif status == "overflow":
            if normalized_value is not None or length <= limit:
                raise ValueError(f"source_independence_overflow_{field}_invalid")
        elif status == "invalid_type":
            if normalized_value is not None or length != 0:
                raise ValueError(f"source_independence_invalid_{field}_invalid")
        else:
            raise ValueError(f"source_independence_{field}_status_invalid")
    return values


def _derive_document(
    item: Mapping[str, Any], document_id: str, input_digest: str
) -> tuple[dict[str, Any], frozenset[str]]:
    reasons: list[str] = []
    rejection_statuses = {
        "invalid_type",
        "overflow",
        "malformed",
        "userinfo_rejected",
        "port_rejected",
        "scheme_rejected",
        "host_rejected",
    }
    status_values = {
        item["source_id_status"],
        item["source_provider_status"],
        item["source_class_status"],
        item["source_url_status"],
        item["published_at_status"],
        item["fetched_at_status"],
        item["title_input_status"],
        item["body_input_status"],
    }
    rejected = bool(status_values & rejection_statuses)
    for field, status in (
        ("source_id", item["source_id_status"]),
        ("source_provider", item["source_provider_status"]),
        ("source_class", item["source_class_status"]),
        ("source_url", item["source_url_status"]),
        ("published_at", item["published_at_status"]),
        ("fetched_at", item["fetched_at_status"]),
        ("title", item["title_input_status"]),
        ("body", item["body_input_status"]),
    ):
        if status not in {"present", "missing", "derived"}:
            reasons.append(f"{field}_{status}")
    if item["public_time_status"] == "missing":
        reasons.append("public_time_missing")
    if item["source_url_status"] == "missing":
        reasons.append("source_url_missing")

    parts = [
        value
        for value in (item["normalized_title"], item["normalized_body"])
        if value
    ]
    normalized_text = "\n".join(parts) if parts else None
    content_digest = _digest_text(normalized_text) if normalized_text else None
    tokens = normalized_text.replace("\n", " ").split() if normalized_text else []
    shingles = _shingles(tokens) if len(tokens) >= SHINGLE_SIZE else frozenset()
    content_status = "assessable"
    if normalized_text and len(normalized_text) > MAX_NORMALIZED_TEXT_CHARS:
        rejected = True
        content_status = "overflow"
        reasons.append("normalized_text_overflow")
        shingles = frozenset()
    elif len(shingles) > MAX_SHINGLES_PER_DOCUMENT:
        rejected = True
        content_status = "overflow"
        reasons.append("shingle_limit_exceeded")
        shingles = frozenset()
    elif not normalized_text:
        content_status = "missing"
        reasons.append("content_missing")
    elif len(tokens) < MIN_NEAR_DUPLICATE_TOKENS:
        content_status = "too_short"
        reasons.append("content_too_short")

    if rejected:
        assessment_status = "rejected"
    elif not item["canonical_origin"] or content_status != "assessable":
        assessment_status = "unassessable"
    else:
        assessment_status = "eligible"
    document = {
        **dict(item),
        "document_id": document_id,
        "input_digest": input_digest,
        "normalized_text": normalized_text,
        "content_digest": content_digest,
        "token_count": len(tokens),
        "shingle_count": len(shingles),
        "content_similarity_status": content_status,
        "assessment_status": assessment_status,
        "cluster_id": None,
        "match_kind": None,
        "representative_similarity": None,
        "authority_status": "not_assessed",
        "reason_codes": sorted(set(reasons)),
    }
    return document, shingles


def _append_cluster_member(
    cluster: dict[str, Any],
    document: Mapping[str, Any],
    match_kind: str,
    similarity: float,
) -> None:
    cluster["members"].append(
        {
            "document_id": document["document_id"],
            "match_kind": match_kind,
            "similarity": round(float(similarity), 6),
        }
    )


def _document_sort_key(document: Mapping[str, Any]) -> tuple[Any, ...]:
    public_time = document.get("public_time")
    return (
        public_time is None,
        public_time or "",
        str(document.get("source_id") or "").casefold(),
        str(document.get("document_id") or ""),
    )


def _document_by_id(
    documents: Sequence[Mapping[str, Any]], document_id: str
) -> Mapping[str, Any]:
    for document in documents:
        if document["document_id"] == document_id:
            return document
    raise ValueError("source_independence_representative_missing")


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _shingles(tokens: Sequence[str]) -> frozenset[str]:
    return frozenset(
        " ".join(tokens[index : index + SHINGLE_SIZE])
        for index in range(len(tokens) - SHINGLE_SIZE + 1)
    )


def _bounded_identity(value: Any) -> tuple[str | None, str, str]:
    digest = _input_digest(value)
    if value is None or value == "":
        return None, "derived", digest
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None, "invalid_type", digest
    text = str(value).strip()
    if not text:
        return None, "derived", digest
    if len(text) > MAX_SOURCE_ID_CHARS:
        return None, "overflow", digest
    return text, "present", digest


def _bounded_metadata(value: Any) -> tuple[str | None, str]:
    if value is None or value == "":
        return None, "missing"
    if not isinstance(value, str):
        return None, "invalid_type"
    text = " ".join(value.strip().split())
    if not text:
        return None, "missing"
    if len(text) > MAX_METADATA_CHARS:
        return None, "overflow"
    return text, "present"


def _normalize_text_input(
    value: Any, limit: int
) -> tuple[str | None, str, int, str]:
    digest = _input_digest(value)
    if value is None or value == "":
        return None, "missing", 0, digest
    if not isinstance(value, str):
        return None, "invalid_type", 0, digest
    length = len(value)
    if length > limit:
        return None, "overflow", length, digest
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = " ".join(
        "".join(character if character.isalnum() else " " for character in normalized).split()
    )
    if not normalized:
        return None, "missing", length, digest
    return normalized, "present", length, digest


def _canonical_url(value: Any) -> tuple[str | None, str | None, str, str]:
    digest = _input_digest(value)
    if value is None or value == "":
        return None, None, "missing", digest
    if not isinstance(value, str):
        return None, None, "invalid_type", digest
    raw = value.strip()
    if not raw:
        return None, None, "missing", digest
    if len(raw) > MAX_URL_CHARS:
        return None, None, "overflow", digest
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None, None, "malformed", digest
    if parsed.scheme.lower() not in {"http", "https"}:
        return None, None, "scheme_rejected", digest
    if not parsed.netloc or "@" in parsed.netloc or parsed.username or parsed.password:
        return None, None, "userinfo_rejected", digest
    try:
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None, None, "port_rejected", digest
    if not hostname:
        return None, None, "host_rejected", digest
    try:
        hostname = hostname.rstrip(".").lower().encode("idna").decode("ascii")
    except UnicodeError:
        return None, None, "host_rejected", digest
    if hostname.startswith("www."):
        hostname = hostname[4:]
    if (
        not hostname
        or len(hostname) > 253
        or not _HOST_RE.fullmatch(hostname)
        or ".." in hostname
        or any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            for label in hostname.split(".")
        )
    ):
        return None, None, "host_rejected", digest
    netloc = hostname + (f":{port}" if port is not None else "")
    safe_url = urlunsplit(
        (parsed.scheme.lower(), netloc, parsed.path or "/", "", "")
    )
    return safe_url, hostname, "present", digest


def _canonical_time(value: Any) -> tuple[str | None, str, str]:
    digest = _input_digest(value)
    if value is None or value == "":
        return None, "missing", digest
    parsed: datetime
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None, "malformed", digest
    else:
        return None, "invalid_type", digest
    if parsed.tzinfo is None:
        return None, "malformed", digest
    return parsed.astimezone(timezone.utc).isoformat(), "present", digest


def _public_time(
    published: tuple[str | None, str, str],
    fetched: tuple[str | None, str, str],
) -> tuple[str | None, str]:
    if published[1] == "present":
        return published[0], "published"
    if published[1] not in {"missing", "present"}:
        return None, "invalid"
    if fetched[1] == "present":
        return fetched[0], "fetched"
    if fetched[1] not in {"missing", "present"}:
        return None, "invalid"
    return None, "missing"


def _first(source: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source and source.get(key) not in (None, ""):
            return source.get(key)
    return None


def _input_digest(value: Any) -> str:
    if isinstance(value, datetime):
        value = value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        payload = {"type": type(value).__name__, "value": value}
    else:
        payload = {"type": type(value).__name__}
    return _digest(payload)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest_without(value: Mapping[str, Any], key: str) -> str:
    return _digest({name: item for name, item in value.items() if name != key})


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _reverse_text(value: str) -> tuple[int, ...]:
    """Make lexicographically smaller ids win a max-key similarity tie."""

    return tuple(-ord(character) for character in value)


__all__ = [
    "ALGORITHM",
    "MAX_DOCUMENTS",
    "MIN_NEAR_DUPLICATE_TOKENS",
    "NEAR_DUPLICATE_JACCARD_THRESHOLD",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SHINGLE_SIZE",
    "assess_source_independence",
    "assess_source_independence_safe",
    "combine_contracts",
    "combine_source_independence_contracts",
    "validate_contract",
    "validate_source_independence_contract",
]
