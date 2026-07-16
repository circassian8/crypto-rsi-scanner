"""Exact source-independence reference hydration for dashboard loading."""

from __future__ import annotations

from typing import Any, Mapping

from ..artifacts import fingerprints as event_alpha_fingerprints
from ..radar import source_independence_store as event_source_independence_store
from .secure_reader import AnchoredNamespaceReader


def hydrate_source_independence_references(
    value: Any,
    *,
    reader: AnchoredNamespaceReader,
    cache: dict[bytes, dict[str, Any]],
    max_nodes: int = 100_000,
) -> Any:
    """Resolve exact store references through the already-anchored namespace."""

    visited = 0

    def _hydrate(current: Any) -> Any:
        nonlocal visited
        visited += 1
        if visited > max_nodes:
            raise event_source_independence_store.SourceIndependenceStoreError(
                "source_independence_dashboard_node_limit_exceeded"
            )
        if isinstance(current, Mapping):
            if (
                current.get("schema_id")
                == event_source_independence_store.REFERENCE_SCHEMA_ID
            ):
                errors = event_source_independence_store.validate_reference(current)
                if errors:
                    raise event_source_independence_store.SourceIndependenceStoreError(
                        "source_independence_reference_invalid:" + ",".join(errors)
                    )
                try:
                    key = event_alpha_fingerprints.canonical_json_bytes(dict(current))
                except event_alpha_fingerprints.FingerprintError as exc:
                    raise event_source_independence_store.SourceIndependenceStoreError(
                        "source_independence_reference_canonicalization_failed"
                    ) from exc
                cached = cache.get(key)
                if cached is not None:
                    return dict(cached)
                raw, read_error = reader.read_bytes(current["artifact_relative_path"])
                if read_error or raw is None:
                    raise event_source_independence_store.SourceIndependenceStoreError(
                        "source_independence_store_blob_unreadable:"
                        + str(read_error or "missing")
                    )
                contract = event_source_independence_store.resolve_bytes(current, raw)
                cache[key] = contract
                return dict(contract)
            return {key: _hydrate(item) for key, item in current.items()}
        if isinstance(current, list):
            return [_hydrate(item) for item in current]
        return current

    return _hydrate(value)
