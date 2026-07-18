"""Persistence boundary for the bounded live market-history baseline.

The mutable cache is deliberately separate from immutable dashboard authority.
Every generation receives its own exact, fingerprinted history snapshot, while
only approved live observations may update the shared rolling cache. Fixture
and mock generations remain namespace-local and cannot warm Decision campaign data.
"""

from __future__ import annotations

import hashlib
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..radar import market_history, market_history_readiness
from . import market_no_send_campaign_guard
from .market_no_send_io import (
    ensure_safe_namespace_dir,
    read_jsonl,
    read_regular_bytes,
    write_jsonl,
)
from .market_no_send_models import MarketNoSendError


LIVE_HISTORY_CACHE_NAMESPACE = market_no_send_campaign_guard.CAMPAIGN_STATE_NAMESPACE


def cache_readiness(
    artifact_base_dir: Path,
    *,
    history_filename: str,
    now: datetime | str | None = None,
    config: market_history.MarketHistoryConfig | None = None,
    current_asset_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Summarize the live cache without creating paths or mutating artifacts."""

    cache_dir = artifact_base_dir.absolute() / LIVE_HISTORY_CACHE_NAMESPACE
    cache_status = "valid"
    try:
        info = cache_dir.lstat()
    except FileNotFoundError:
        rows, cache_status = [], "missing"
    except OSError:
        rows, cache_status = [], "invalid"
    else:
        if not stat.S_ISDIR(info.st_mode):
            rows, cache_status = [], "invalid"
        else:
            try:
                rows = read_jsonl(cache_dir / history_filename)
            except (MarketNoSendError, OSError, ValueError):
                rows, cache_status = [], "invalid"
    evaluated_at = now or datetime.now(timezone.utc)
    assessment = market_history_readiness.assess_market_history_readiness(
        rows,
        now=evaluated_at,
        config=config,
    )
    result = {
        key: value
        for key, value in assessment.items()
        if key.startswith("baseline_")
        or key in {
            "minimum_observation_spacing_seconds",
            "next_eligible_observation_at",
            "cadence_status",
        }
    } | {
        "baseline_rejection_counts": assessment.get("rejection_counts", {}),
        "cache_status": cache_status,
        "cache_error": "shared market history is invalid" if cache_status == "invalid" else None,
    }
    if current_asset_ids is not None:
        result["current_universe_maturity"] = _current_universe_maturity(
            rows,
            current_asset_ids=current_asset_ids,
            now=evaluated_at,
            config=config,
        )
    return result


def _current_universe_maturity(
    rows: Sequence[Mapping[str, Any]],
    *,
    current_asset_ids: Sequence[str],
    now: datetime | str,
    config: market_history.MarketHistoryConfig | None,
) -> dict[str, Any]:
    """Project retained history onto the exact current authoritative universe."""

    expected = tuple(
        sorted(
            {
                str(value).strip()
                for value in current_asset_ids
                if isinstance(value, str) and value.strip()
            }
        )
    )
    if not expected:
        return {
            "status": "unavailable",
            "scope": "current_authoritative_universe",
            "expected_asset_count": 0,
            "observed_asset_count": 0,
            "missing_asset_count": 0,
            "missing_asset_ids": [],
            "baseline_observation_count": 0,
            "baseline_counted_observation_count": 0,
            "baseline_warm_asset_count": 0,
            "baseline_feature_readiness": {},
            "research_only": True,
        }
    expected_set = set(expected)
    filtered = [
        dict(row)
        for row in rows
        if str(row.get("canonical_asset_id") or "").strip() in expected_set
    ]
    assessment = market_history_readiness.assess_market_history_readiness(
        filtered,
        now=now,
        config=config,
    )
    observed = set(_mapping_keys(assessment.get("baseline_asset_readiness")))
    missing = sorted(expected_set - observed)
    status = (
        "incomplete"
        if missing
        else str(assessment.get("baseline_status") or "unknown")
    )
    return {
        "status": status,
        "scope": "current_authoritative_universe",
        "expected_asset_count": len(expected),
        "observed_asset_count": len(observed & expected_set),
        "missing_asset_count": len(missing),
        "missing_asset_ids": missing,
        "baseline_observation_count": int(
            assessment.get("baseline_observation_count") or 0
        ),
        "baseline_counted_observation_count": int(
            assessment.get("baseline_counted_observation_count") or 0
        ),
        "baseline_warm_asset_count": int(
            assessment.get("baseline_warm_asset_count") or 0
        ),
        "baseline_feature_readiness": dict(
            assessment.get("baseline_feature_readiness") or {}
        ),
        "research_only": True,
    }


def _mapping_keys(value: object) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return ()
    return tuple(str(key) for key in value)


def enrich_and_persist_history(
    rows: Sequence[Mapping[str, Any]],
    *,
    artifact_base_dir: Path,
    generation_namespace_dir: Path,
    history_filename: str,
    observed_at: datetime,
    live_no_send: bool,
    config: market_history.MarketHistoryConfig | None = None,
    campaign_reservation: market_no_send_campaign_guard.CampaignReservation | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Enrich rows and persist a generation snapshot plus optional live cache."""

    if live_no_send and campaign_reservation is None:
        raise MarketNoSendError("live market history requires an active campaign reservation")
    if campaign_reservation is not None:
        campaign_reservation.assert_active(artifact_base_dir)
    if live_no_send:
        if campaign_reservation.provider_call_reserved_at is None:
            raise MarketNoSendError("live market history requires a provider-call reservation")
        if campaign_reservation.artifact_namespace != generation_namespace_dir.name:
            raise MarketNoSendError("live market history campaign namespace mismatch")
        _validate_live_campaign_rows(rows)

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
        config=config,
    )
    retained = result.retained_history
    if shared_path is not None:
        write_jsonl(shared_path, retained)
        campaign_reservation.assert_active(artifact_base_dir)
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


def _validate_live_campaign_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    expected = {
        "data_mode": "live", "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send", "provider": "coingecko",
        "provider_request_succeeded": True,
        "measurement_program": "decision_radar_live_observation_campaign_v2",
        "decision_radar_campaign_eligible": True,
        "decision_radar_campaign_counted": True,
        "burn_in_eligible": False, "burn_in_counted": False,
        "contract_counted_status": "counted", "no_send": True, "research_only": True,
    }
    if not rows or any(
        any(row.get(field) != value for field, value in expected.items())
        for row in rows
    ):
        raise MarketNoSendError("live market history rows lack canonical campaign provenance")


__all__ = ("LIVE_HISTORY_CACHE_NAMESPACE", "cache_readiness", "enrich_and_persist_history")
