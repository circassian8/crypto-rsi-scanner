"""Persistence boundary for the bounded live market-history baseline.

The mutable cache is deliberately separate from immutable dashboard authority.
Every generation receives its own exact, fingerprinted history snapshot, while
only approved live observations may update the shared rolling cache.  Fixture
and mock generations remain namespace-local and cannot warm live burn-in data.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..radar import market_history
from .market_no_send_io import (
    ensure_safe_namespace_dir,
    read_jsonl,
    read_regular_bytes,
    write_jsonl,
)
from .market_no_send_models import MarketNoSendError


LIVE_HISTORY_CACHE_NAMESPACE = "radar_market_history_cache"


def cache_readiness(artifact_base_dir: Path, *, history_filename: str) -> dict[str, Any]:
    """Summarize the live cache without creating paths or mutating artifacts."""

    try:
        cache_dir = artifact_base_dir.absolute() / LIVE_HISTORY_CACHE_NAMESPACE
        rows = read_jsonl(cache_dir / history_filename)
    except (MarketNoSendError, OSError):
        rows = []
    counts = Counter(
        str(row.get("canonical_asset_id") or "")
        for row in rows
        if str(row.get("canonical_asset_id") or "")
    )
    observed_times = [
        parsed
        for row in rows
        if (parsed := _aware_time(row.get("observed_at"))) is not None
    ]
    newest = max(observed_times, default=None)
    config = market_history.MarketHistoryConfig()
    minimum = config.min_baseline_observations
    warm_assets = sum(count >= minimum for count in counts.values())
    if not rows:
        status = "cold"
    elif newest is None or datetime.now(timezone.utc) - newest > config.max_history_age:
        status = "stale"
    elif warm_assets == len(counts):
        status = "warm"
    else:
        status = "warming"
    return {
        "baseline_status": status,
        "baseline_observation_count": len(rows),
        "baseline_asset_count": len(counts),
        "baseline_warm_asset_count": warm_assets,
        "baseline_min_observations": minimum,
        "baseline_newest_observed_at": newest.isoformat() if newest else None,
    }


def enrich_and_persist_history(
    rows: Sequence[Mapping[str, Any]],
    *,
    artifact_base_dir: Path,
    generation_namespace_dir: Path,
    history_filename: str,
    observed_at: datetime,
    live_no_send: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Enrich rows and persist a generation snapshot plus optional live cache."""

    generation_path = generation_namespace_dir / history_filename
    local_history = read_jsonl(generation_path)
    shared_path: Path | None = None
    shared_history: list[dict[str, Any]] = []
    if live_no_send:
        if generation_namespace_dir.name == LIVE_HISTORY_CACHE_NAMESPACE:
            raise MarketNoSendError("market generation cannot use the reserved history namespace")
        cache_dir = artifact_base_dir / LIVE_HISTORY_CACHE_NAMESPACE
        ensure_safe_namespace_dir(cache_dir)
        shared_path = cache_dir / history_filename
        shared_history = read_jsonl(shared_path)

    result = market_history.enrich_market_rows_with_history(
        rows,
        (*shared_history, *local_history),
        now=observed_at,
    )
    retained = result.retained_history
    if shared_path is not None:
        write_jsonl(shared_path, retained)
    write_jsonl(generation_path, retained)
    raw = read_regular_bytes(generation_path)
    if raw is None:  # pragma: no cover - write_jsonl either writes or raises
        raise MarketNoSendError("market history snapshot is missing after write")
    summary = {
        **dict(result.summary),
        "cache_scope": "shared_live_no_send" if live_no_send else "generation_local_mock",
        "shared_cache_namespace": LIVE_HISTORY_CACHE_NAMESPACE if live_no_send else None,
        "shared_seed_rows": len(shared_history),
        "generation_seed_rows": len(local_history),
    }
    return (
        [dict(row) for row in result.enriched_rows],
        summary,
        hashlib.sha256(raw).hexdigest(),
    )


def _aware_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


__all__ = ("LIVE_HISTORY_CACHE_NAMESPACE", "cache_readiness", "enrich_and_persist_history")
