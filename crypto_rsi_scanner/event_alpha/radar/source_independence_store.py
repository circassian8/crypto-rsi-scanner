"""Descriptor-safe content-addressed storage for source-independence contracts.

The store is deliberately namespace local.  It externalizes only the closed
``event_alpha.source_independence`` value object and never treats a reference
as evidence until the exact immutable bytes, fingerprint, and semantic digest
have all been revalidated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

from ..artifacts.fingerprints import (
    FILE_BYTES_KIND,
    FINGERPRINT_FIELDS,
    FingerprintError,
    canonical_json_bytes,
    fingerprint_bytes,
    fingerprint_metadata_error,
    verify_bytes_fingerprint,
)
from ..operations import market_no_send_io
from ..operations.market_no_send_models import MarketNoSendError
from . import source_independence


REFERENCE_SCHEMA_ID = "event_alpha.source_independence_reference"
REFERENCE_SCHEMA_VERSION = 1
STORE_DIRECTORY = "event_source_independence_contracts"
MAX_CONTRACT_BLOB_BYTES = 16 * 1024 * 1024
MAX_TRAVERSAL_DEPTH = 64
MAX_TRAVERSAL_NODES = 10_000
MAX_MEASUREMENT_UNIQUE_CONTRACTS = 1_024

_HEX_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_REFERENCE_KEYS = {
    "schema_id",
    "schema_version",
    "store_directory",
    "artifact_name",
    "artifact_relative_path",
    "contract_digest",
    "blob_fingerprint",
    "validation_status",
    "raw_document_count",
    "content_cluster_count",
    "independent_evidence_count",
    "independent_corroboration_count",
    "distinct_origin_count",
    "syndicated_copy_count",
    "research_only",
}
_SUMMARY_FIELDS = (
    "raw_document_count",
    "content_cluster_count",
    "independent_evidence_count",
    "independent_corroboration_count",
    "distinct_origin_count",
)


class _SourceIndependenceStoreError(RuntimeError):
    """Raised when the closed store contract cannot be satisfied safely."""


# Public compatibility alias without adding a second public ownership class.
SourceIndependenceStoreError = _SourceIndependenceStoreError


@dataclass(frozen=True)
class SourceIndependenceMeasurement:
    """Bounded size and deduplication measurements for one JSON-like value."""

    nodes_visited: int
    inline_contract_occurrences: int
    reference_occurrences: int
    unique_contract_count: int
    inline_contract_bytes: int
    reference_bytes: int
    unique_inline_blob_bytes: int
    duplicate_inline_blob_bytes: int
    projected_reference_bytes: int
    projected_inline_storage_bytes: int
    projected_inline_savings_bytes: int
    max_contract_bytes: int

    def to_dict(self) -> dict[str, int]:
        """Return a JSON-safe representation without weakening field types."""

        return asdict(self)


@dataclass
class _TraversalBudget:
    max_nodes: int
    max_depth: int
    nodes_visited: int = 0

    def visit(self, depth: int) -> None:
        if depth > self.max_depth:
            raise SourceIndependenceStoreError(
                "source_independence_traversal_depth_exceeded"
            )
        self.nodes_visited += 1
        if self.nodes_visited > self.max_nodes:
            raise SourceIndependenceStoreError(
                "source_independence_traversal_node_limit_exceeded"
            )


@dataclass
class _MeasurementAccumulator:
    inline_contract_occurrences: int = 0
    reference_occurrences: int = 0
    inline_contract_bytes: int = 0
    reference_bytes: int = 0
    projected_reference_bytes: int = 0
    max_contract_bytes: int = 0

    def __post_init__(self) -> None:
        self.unique_contracts: dict[tuple[str, str], int] = {}
        self.unique_inline_contracts: dict[tuple[str, str], int] = {}


def validate_reference(value: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate a closed reference without reading the artifact namespace."""

    errors: list[str] = []
    if not isinstance(value, Mapping):
        return ("source_independence_reference_not_mapping",)
    if set(value) != _REFERENCE_KEYS:
        errors.append("source_independence_reference_keys_invalid")
    if value.get("schema_id") != REFERENCE_SCHEMA_ID:
        errors.append("source_independence_reference_schema_id_invalid")
    version = value.get("schema_version")
    if type(version) is not int or version != REFERENCE_SCHEMA_VERSION:
        errors.append("source_independence_reference_schema_version_invalid")
    if value.get("store_directory") != STORE_DIRECTORY:
        errors.append("source_independence_reference_store_directory_invalid")
    if value.get("validation_status") != "validated":
        errors.append("source_independence_reference_validation_status_invalid")
    if value.get("research_only") is not True:
        errors.append("source_independence_reference_research_only_invalid")

    contract_digest = value.get("contract_digest")
    if not _valid_digest(contract_digest):
        errors.append("source_independence_reference_contract_digest_invalid")

    fingerprint = value.get("blob_fingerprint")
    if not isinstance(fingerprint, Mapping):
        errors.append("source_independence_reference_blob_fingerprint_invalid")
        fingerprint = {}
    else:
        if set(fingerprint) != set(FINGERPRINT_FIELDS):
            errors.append("source_independence_reference_blob_fingerprint_keys_invalid")
        metadata_error = fingerprint_metadata_error(
            fingerprint,
            allowed_kinds={FILE_BYTES_KIND},
        )
        if metadata_error:
            errors.append(
                f"source_independence_reference_blob_fingerprint_invalid:{metadata_error}"
            )
        size_bytes = fingerprint.get("size_bytes")
        if (
            type(size_bytes) is not int
            or size_bytes <= 0
            or size_bytes > MAX_CONTRACT_BLOB_BYTES
        ):
            errors.append("source_independence_reference_blob_size_invalid")
        if fingerprint.get("item_count") != 1:
            errors.append("source_independence_reference_blob_item_count_invalid")

    blob_digest = fingerprint.get("sha256")
    artifact_name = value.get("artifact_name")
    expected_name = (
        f"{contract_digest}.{blob_digest}.json"
        if _valid_digest(contract_digest) and _valid_digest(blob_digest)
        else None
    )
    if not isinstance(artifact_name, str) or artifact_name != expected_name:
        errors.append("source_independence_reference_artifact_name_invalid")
    expected_relative_path = (
        f"{STORE_DIRECTORY}/{expected_name}" if expected_name is not None else None
    )
    if value.get("artifact_relative_path") != expected_relative_path:
        errors.append("source_independence_reference_artifact_relative_path_invalid")

    summaries: dict[str, int] = {}
    for field in _SUMMARY_FIELDS:
        summary = value.get(field)
        if type(summary) is not int or summary < 0 or summary > source_independence.MAX_DOCUMENTS:
            errors.append(f"source_independence_reference_{field}_invalid")
        else:
            summaries[field] = summary
    if len(summaries) == len(_SUMMARY_FIELDS):
        raw_count = summaries["raw_document_count"]
        cluster_count = summaries["content_cluster_count"]
        evidence_count = summaries["independent_evidence_count"]
        corroboration_count = summaries["independent_corroboration_count"]
        origin_count = summaries["distinct_origin_count"]
        if cluster_count > raw_count:
            errors.append("source_independence_reference_summary_relationship_invalid")
        if evidence_count > cluster_count:
            errors.append("source_independence_reference_summary_relationship_invalid")
        if corroboration_count > evidence_count:
            errors.append("source_independence_reference_summary_relationship_invalid")
        if origin_count > raw_count:
            errors.append("source_independence_reference_summary_relationship_invalid")
    syndicated = value.get("syndicated_copy_count")
    if (
        type(syndicated) is not int
        or syndicated < 0
        or syndicated > source_independence.MAX_DOCUMENTS
    ):
        errors.append("source_independence_reference_syndicated_copy_count_invalid")
    elif "raw_document_count" in summaries and syndicated > summaries["raw_document_count"]:
        errors.append("source_independence_reference_syndicated_copy_count_invalid")
    return tuple(sorted(set(errors)))


def intern(
    namespace_dir: str | Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Intern one validated contract and return its closed immutable reference."""

    normalized = _validated_contract(contract)
    blob = _contract_blob(normalized)
    reference = _reference_for(normalized, blob)
    store_dir = Path(namespace_dir).expanduser().absolute() / STORE_DIRECTORY
    artifact_path = store_dir / reference["artifact_name"]
    try:
        market_no_send_io.ensure_safe_namespace_dir(store_dir)
        existing = market_no_send_io.read_regular_bytes(
            artifact_path,
            missing_ok=True,
        )
        if existing is None:
            try:
                market_no_send_io.write_bytes_immutable(artifact_path, blob)
            except MarketNoSendError:
                # A concurrent writer of the same content is safe; every other
                # failure remains closed after the anchored read-back below.
                existing = market_no_send_io.read_regular_bytes(
                    artifact_path,
                    missing_ok=True,
                )
                if existing is None:
                    raise
        read_back = market_no_send_io.read_regular_bytes(artifact_path)
    except MarketNoSendError as exc:
        raise SourceIndependenceStoreError(
            "source_independence_store_write_failed"
        ) from exc
    if read_back != blob:
        raise SourceIndependenceStoreError(
            "source_independence_store_immutable_blob_mismatch"
        )
    return reference


def resolve(
    namespace_dir: str | Path,
    reference: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve and fully revalidate one exact namespace-local reference."""

    errors = validate_reference(reference)
    if errors:
        raise SourceIndependenceStoreError(
            "source_independence_reference_invalid:" + ",".join(errors)
        )
    normalized_reference = dict(reference)
    artifact_path = (
        Path(namespace_dir).expanduser().absolute()
        / STORE_DIRECTORY
        / str(normalized_reference["artifact_name"])
    )
    try:
        raw = market_no_send_io.read_regular_bytes(artifact_path)
    except MarketNoSendError as exc:
        raise SourceIndependenceStoreError(
            "source_independence_store_blob_unreadable"
        ) from exc
    if raw is None:
        raise SourceIndependenceStoreError("source_independence_store_blob_missing")
    return resolve_bytes(reference, raw)


def resolve_bytes(
    reference: Mapping[str, Any],
    raw: bytes,
) -> dict[str, Any]:
    """Resolve one exact already-anchored blob buffer against its reference."""

    errors = validate_reference(reference)
    if errors:
        raise SourceIndependenceStoreError(
            "source_independence_reference_invalid:" + ",".join(errors)
        )
    normalized_reference = dict(reference)
    if not isinstance(raw, bytes):
        raise SourceIndependenceStoreError(
            "source_independence_store_blob_not_bytes"
        )
    if len(raw) > MAX_CONTRACT_BLOB_BYTES:
        raise SourceIndependenceStoreError(
            "source_independence_store_blob_size_limit_exceeded"
        )
    fingerprint = normalized_reference["blob_fingerprint"]
    verified, fingerprint_error = verify_bytes_fingerprint(raw, fingerprint)
    if not verified:
        raise SourceIndependenceStoreError(
            "source_independence_store_blob_fingerprint_mismatch:"
            + str(fingerprint_error or "unknown")
        )
    try:
        parsed = market_no_send_io.parse_json_object_bytes(raw)
    except MarketNoSendError as exc:
        raise SourceIndependenceStoreError(
            "source_independence_store_blob_json_invalid"
        ) from exc
    normalized = _validated_contract(parsed)
    try:
        canonical = canonical_json_bytes(normalized)
    except FingerprintError as exc:
        raise SourceIndependenceStoreError(
            "source_independence_store_blob_canonicalization_failed"
        ) from exc
    if canonical != raw:
        raise SourceIndependenceStoreError(
            "source_independence_store_blob_not_canonical"
        )
    if normalized.get("contract_digest") != normalized_reference["contract_digest"]:
        raise SourceIndependenceStoreError(
            "source_independence_store_contract_digest_mismatch"
        )
    for field in _SUMMARY_FIELDS:
        if normalized.get(field) != normalized_reference.get(field):
            raise SourceIndependenceStoreError(
                f"source_independence_store_reference_summary_mismatch:{field}"
            )
    expected_syndicated = _syndicated_copy_count(normalized)
    if normalized_reference.get("syndicated_copy_count") != expected_syndicated:
        raise SourceIndependenceStoreError(
            "source_independence_store_reference_summary_mismatch:"
            "syndicated_copy_count"
        )
    return normalized


def externalize(
    namespace_dir: str | Path,
    value: Any,
    *,
    max_nodes: int = MAX_TRAVERSAL_NODES,
    max_depth: int = MAX_TRAVERSAL_DEPTH,
    preserve_inline_digests: frozenset[str] = frozenset(),
) -> Any:
    """Recursively replace closed inline contracts with immutable references."""

    if any(not _valid_digest(digest) for digest in preserve_inline_digests):
        raise SourceIndependenceStoreError(
            "source_independence_preserved_digest_invalid"
        )
    budget = _new_budget(max_nodes=max_nodes, max_depth=max_depth)
    return _externalize(
        Path(namespace_dir),
        value,
        budget=budget,
        depth=0,
        preserve_inline_digests=preserve_inline_digests,
    )


def inline_contract_digests(
    value: Any,
    *,
    max_nodes: int = MAX_TRAVERSAL_NODES,
    max_depth: int = MAX_TRAVERSAL_DEPTH,
) -> frozenset[str]:
    """Return validated legacy-inline digests without resolving references."""

    budget = _new_budget(max_nodes=max_nodes, max_depth=max_depth)
    found: set[str] = set()
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        budget.visit(depth)
        if isinstance(current, Mapping):
            if current.get("schema_id") == source_independence.SCHEMA_ID:
                normalized = _validated_contract(current)
                found.add(str(normalized["contract_digest"]))
                continue
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend((item, depth + 1) for item in current)
    return frozenset(found)


def hydrate(
    namespace_dir: str | Path,
    value: Any,
    *,
    max_nodes: int = MAX_TRAVERSAL_NODES,
    max_depth: int = MAX_TRAVERSAL_DEPTH,
) -> Any:
    """Recursively resolve references while preserving legacy inline contracts."""

    budget = _new_budget(max_nodes=max_nodes, max_depth=max_depth)
    return _hydrate(
        Path(namespace_dir),
        value,
        budget=budget,
        depth=0,
        cache={},
    )


def measurement_stats(
    value: Any,
    *,
    max_nodes: int = MAX_TRAVERSAL_NODES,
    max_depth: int = MAX_TRAVERSAL_DEPTH,
    max_unique_contracts: int = MAX_MEASUREMENT_UNIQUE_CONTRACTS,
) -> SourceIndependenceMeasurement:
    """Measure contract/reference duplication with explicit traversal bounds."""

    if type(max_unique_contracts) is not int or max_unique_contracts <= 0:
        raise ValueError("max_unique_contracts must be a positive integer")
    budget = _new_budget(max_nodes=max_nodes, max_depth=max_depth)
    accumulator = _MeasurementAccumulator()
    _measure(
        value,
        budget=budget,
        accumulator=accumulator,
        depth=0,
        max_unique_contracts=max_unique_contracts,
    )
    unique_inline_blob_bytes = sum(accumulator.unique_inline_contracts.values())
    duplicate_inline_blob_bytes = max(
        0,
        accumulator.inline_contract_bytes - unique_inline_blob_bytes,
    )
    projected_inline_storage_bytes = (
        unique_inline_blob_bytes + accumulator.projected_reference_bytes
    )
    return SourceIndependenceMeasurement(
        nodes_visited=budget.nodes_visited,
        inline_contract_occurrences=accumulator.inline_contract_occurrences,
        reference_occurrences=accumulator.reference_occurrences,
        unique_contract_count=len(accumulator.unique_contracts),
        inline_contract_bytes=accumulator.inline_contract_bytes,
        reference_bytes=accumulator.reference_bytes,
        unique_inline_blob_bytes=unique_inline_blob_bytes,
        duplicate_inline_blob_bytes=duplicate_inline_blob_bytes,
        projected_reference_bytes=accumulator.projected_reference_bytes,
        projected_inline_storage_bytes=projected_inline_storage_bytes,
        projected_inline_savings_bytes=(
            accumulator.inline_contract_bytes - projected_inline_storage_bytes
        ),
        max_contract_bytes=accumulator.max_contract_bytes,
    )


def _externalize(
    namespace_dir: Path,
    value: Any,
    *,
    budget: _TraversalBudget,
    depth: int,
    preserve_inline_digests: frozenset[str],
) -> Any:
    budget.visit(depth)
    if isinstance(value, Mapping):
        schema_id = value.get("schema_id")
        if schema_id == REFERENCE_SCHEMA_ID:
            errors = validate_reference(value)
            if errors:
                raise SourceIndependenceStoreError(
                    "source_independence_reference_invalid:" + ",".join(errors)
                )
            return dict(value)
        if schema_id == source_independence.SCHEMA_ID:
            normalized = _validated_contract(value)
            if normalized["contract_digest"] in preserve_inline_digests:
                return normalized
            return intern(namespace_dir, value)
        return {
            key: _externalize(
                namespace_dir,
                item,
                budget=budget,
                depth=depth + 1,
                preserve_inline_digests=preserve_inline_digests,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _externalize(
                namespace_dir,
                item,
                budget=budget,
                depth=depth + 1,
                preserve_inline_digests=preserve_inline_digests,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _externalize(
                namespace_dir,
                item,
                budget=budget,
                depth=depth + 1,
                preserve_inline_digests=preserve_inline_digests,
            )
            for item in value
        )
    return value


def _hydrate(
    namespace_dir: Path,
    value: Any,
    *,
    budget: _TraversalBudget,
    depth: int,
    cache: dict[bytes, dict[str, Any]],
) -> Any:
    budget.visit(depth)
    if isinstance(value, Mapping):
        schema_id = value.get("schema_id")
        if schema_id == REFERENCE_SCHEMA_ID:
            key = _reference_cache_key(value)
            cached = cache.get(key)
            if cached is None:
                cached = resolve(namespace_dir, value)
                cache[key] = cached
            return dict(cached)
        if schema_id == source_independence.SCHEMA_ID:
            # Legacy inline values remain inline.  They are validated so a
            # malformed look-alike cannot bypass the same closed contract.
            return _validated_contract(value)
        return {
            key: _hydrate(
                namespace_dir,
                item,
                budget=budget,
                depth=depth + 1,
                cache=cache,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _hydrate(
                namespace_dir,
                item,
                budget=budget,
                depth=depth + 1,
                cache=cache,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _hydrate(
                namespace_dir,
                item,
                budget=budget,
                depth=depth + 1,
                cache=cache,
            )
            for item in value
        )
    return value


def _reference_cache_key(reference: Mapping[str, Any]) -> bytes:
    errors = validate_reference(reference)
    if errors:
        raise SourceIndependenceStoreError(
            "source_independence_reference_invalid:" + ",".join(errors)
        )
    try:
        return canonical_json_bytes(dict(reference))
    except FingerprintError as exc:
        raise SourceIndependenceStoreError(
            "source_independence_reference_canonicalization_failed"
        ) from exc


def _measure(
    value: Any,
    *,
    budget: _TraversalBudget,
    accumulator: _MeasurementAccumulator,
    depth: int,
    max_unique_contracts: int,
) -> None:
    budget.visit(depth)
    if isinstance(value, Mapping):
        schema_id = value.get("schema_id")
        if schema_id == REFERENCE_SCHEMA_ID:
            errors = validate_reference(value)
            if errors:
                raise SourceIndependenceStoreError(
                    "source_independence_reference_invalid:" + ",".join(errors)
                )
            reference = dict(value)
            fingerprint = reference["blob_fingerprint"]
            key = (reference["contract_digest"], fingerprint["sha256"])
            accumulator.reference_occurrences += 1
            accumulator.reference_bytes += len(canonical_json_bytes(reference))
            accumulator.max_contract_bytes = max(
                accumulator.max_contract_bytes,
                fingerprint["size_bytes"],
            )
            accumulator.unique_contracts.setdefault(key, fingerprint["size_bytes"])
            _enforce_unique_bound(accumulator, max_unique_contracts)
            return
        if schema_id == source_independence.SCHEMA_ID:
            contract = _validated_contract(value)
            blob = _contract_blob(contract)
            reference = _reference_for(contract, blob)
            fingerprint = reference["blob_fingerprint"]
            key = (contract["contract_digest"], fingerprint["sha256"])
            accumulator.inline_contract_occurrences += 1
            accumulator.inline_contract_bytes += len(blob)
            accumulator.projected_reference_bytes += len(
                canonical_json_bytes(reference)
            )
            accumulator.max_contract_bytes = max(
                accumulator.max_contract_bytes,
                len(blob),
            )
            accumulator.unique_contracts.setdefault(key, len(blob))
            accumulator.unique_inline_contracts.setdefault(key, len(blob))
            _enforce_unique_bound(accumulator, max_unique_contracts)
            return
        for item in value.values():
            _measure(
                item,
                budget=budget,
                accumulator=accumulator,
                depth=depth + 1,
                max_unique_contracts=max_unique_contracts,
            )
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _measure(
                item,
                budget=budget,
                accumulator=accumulator,
                depth=depth + 1,
                max_unique_contracts=max_unique_contracts,
            )


def _validated_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SourceIndependenceStoreError(
            "source_independence_store_contract_not_mapping"
        )
    errors = source_independence.validate_source_independence_contract(value)
    if errors:
        raise SourceIndependenceStoreError(
            "source_independence_store_contract_invalid:" + ",".join(errors)
        )
    return dict(value)


def _contract_blob(contract: Mapping[str, Any]) -> bytes:
    try:
        blob = canonical_json_bytes(contract)
    except FingerprintError as exc:
        raise SourceIndependenceStoreError(
            "source_independence_store_contract_canonicalization_failed"
        ) from exc
    if len(blob) > MAX_CONTRACT_BLOB_BYTES:
        raise SourceIndependenceStoreError(
            "source_independence_store_contract_size_limit_exceeded"
        )
    return blob


def _reference_for(contract: Mapping[str, Any], blob: bytes) -> dict[str, Any]:
    fingerprint = fingerprint_bytes(blob, kind=FILE_BYTES_KIND)
    contract_digest = contract.get("contract_digest")
    reference = {
        "schema_id": REFERENCE_SCHEMA_ID,
        "schema_version": REFERENCE_SCHEMA_VERSION,
        "store_directory": STORE_DIRECTORY,
        "artifact_name": (
            f"{contract_digest}.{fingerprint['sha256']}.json"
        ),
        "artifact_relative_path": (
            f"{STORE_DIRECTORY}/{contract_digest}.{fingerprint['sha256']}.json"
        ),
        "contract_digest": contract_digest,
        "blob_fingerprint": fingerprint,
        "validation_status": "validated",
        "raw_document_count": contract.get("raw_document_count"),
        "content_cluster_count": contract.get("content_cluster_count"),
        "independent_evidence_count": contract.get("independent_evidence_count"),
        "independent_corroboration_count": contract.get(
            "independent_corroboration_count"
        ),
        "distinct_origin_count": contract.get("distinct_origin_count"),
        "syndicated_copy_count": _syndicated_copy_count(contract),
        "research_only": True,
    }
    errors = validate_reference(reference)
    if errors:
        raise SourceIndependenceStoreError(
            "source_independence_reference_build_failed:" + ",".join(errors)
        )
    return reference


def _syndicated_copy_count(contract: Mapping[str, Any]) -> int:
    """Count only documents explicitly collapsed as exact or near copies."""

    documents = contract.get("documents")
    if not isinstance(documents, list):
        raise SourceIndependenceStoreError(
            "source_independence_store_contract_documents_invalid"
        )
    return sum(
        1
        for document in documents
        if isinstance(document, Mapping)
        and document.get("match_kind") in {"exact", "near_duplicate"}
    )


def _new_budget(*, max_nodes: int, max_depth: int) -> _TraversalBudget:
    if type(max_nodes) is not int or max_nodes <= 0:
        raise ValueError("max_nodes must be a positive integer")
    if type(max_depth) is not int or max_depth < 0:
        raise ValueError("max_depth must be a non-negative integer")
    return _TraversalBudget(max_nodes=max_nodes, max_depth=max_depth)


def _enforce_unique_bound(
    accumulator: _MeasurementAccumulator,
    max_unique_contracts: int,
) -> None:
    if len(accumulator.unique_contracts) > max_unique_contracts:
        raise SourceIndependenceStoreError(
            "source_independence_measurement_unique_contract_limit_exceeded"
        )


def _valid_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX_DIGEST_RE.fullmatch(value))


__all__ = [
    "MAX_CONTRACT_BLOB_BYTES",
    "MAX_MEASUREMENT_UNIQUE_CONTRACTS",
    "MAX_TRAVERSAL_DEPTH",
    "MAX_TRAVERSAL_NODES",
    "REFERENCE_SCHEMA_ID",
    "REFERENCE_SCHEMA_VERSION",
    "STORE_DIRECTORY",
    "SourceIndependenceMeasurement",
    "SourceIndependenceStoreError",
    "externalize",
    "hydrate",
    "inline_contract_digests",
    "intern",
    "measurement_stats",
    "resolve",
    "resolve_bytes",
    "validate_reference",
]
