"""Exact-generation lineage helpers for guarded provider rehearsals."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


def provider_generation_id(
    provider: str,
    observed_at: datetime,
    *,
    attempt_nonce: str | None = None,
) -> str:
    """Return a stable opaque id for one explicitly guarded provider attempt."""
    observed = observed_at.replace(tzinfo=timezone.utc) if observed_at.tzinfo is None else observed_at.astimezone(timezone.utc)
    # ``observed_at`` may be a fixed research clock.  It therefore cannot be
    # the attempt identity on its own: a retry at the same clock must not see a
    # successful ledger row from an earlier attempt as its own evidence.
    nonce = str(attempt_nonce or uuid.uuid4().hex).strip()
    digest = hashlib.sha256(f"{provider}|{observed.isoformat()}|{nonce}".encode("utf-8")).hexdigest()[:20]
    return f"provider-generation:{provider}:{digest}"


def generation_rows(
    rows: Iterable[Mapping[str, Any]],
    generation_id: str | None,
    *,
    provider: str | None = None,
    run_id: str | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Select only rows owned by ``generation_id``; legacy rows never match."""
    target = str(generation_id or "").strip()
    if not target:
        return ()
    expected = {
        "provider": str(provider or "").strip(),
        "run_id": str(run_id or "").strip(),
        "profile": str(profile or "").strip(),
        "artifact_namespace": str(artifact_namespace or "").strip(),
    }
    return tuple(
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("provider_generation_id") or "").strip() == target
        and all(
            not value or str(row.get(key) or "").strip() == value
            for key, value in expected.items()
        )
    )


def generation_has_success(
    rows: Iterable[Mapping[str, Any]],
    generation_id: str | None,
    **lineage: str | None,
) -> bool:
    return any(
        row.get("success") is True and row.get("no_send_rehearsal") is True
        for row in generation_rows(rows, generation_id, **lineage)
    )


__all__ = ("generation_has_success", "generation_rows", "provider_generation_id")
