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
NEXT_CYCLE_POINT_IN_TIME_BASIS = (
    "same_asset_retained_history_before_future_observation"
)


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
        result["current_universe_maturity"] = (
            _unavailable_current_universe_maturity(current_asset_ids)
            if cache_status == "invalid"
            else _current_universe_maturity(
                rows,
                current_asset_ids=current_asset_ids,
                now=evaluated_at,
                config=config,
                next_eligible_observation_at=assessment.get(
                    "next_eligible_observation_at"
                ),
            )
        )
    return result


def _current_universe_maturity(
    rows: Sequence[Mapping[str, Any]],
    *,
    current_asset_ids: Sequence[str],
    now: datetime | str,
    config: market_history.MarketHistoryConfig | None,
    next_eligible_observation_at: object = None,
) -> dict[str, Any]:
    """Project retained history onto the exact current authoritative universe."""

    expected = _expected_asset_ids(current_asset_ids)
    if not expected:
        return _unavailable_current_universe_maturity(())
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
    asset_readiness = _mapping(assessment.get("baseline_asset_readiness"))
    observed = set(_mapping_keys(asset_readiness))
    missing = sorted(expected_set - observed)
    warm = {
        asset_id
        for asset_id, raw in asset_readiness.items()
        if isinstance(raw, Mapping) and raw.get("status") == "warm"
    }
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
        "observed_asset_ids": sorted(observed & expected_set),
        "missing_asset_count": len(missing),
        "missing_asset_ids": missing,
        "non_warm_asset_ids": sorted((observed & expected_set) - warm),
        "baseline_observation_count": int(
            assessment.get("baseline_observation_count") or 0
        ),
        "baseline_counted_observation_count": int(
            assessment.get("baseline_counted_observation_count") or 0
        ),
        "baseline_warm_asset_count": len(warm),
        "next_cycle_point_in_time_eligible_at": next_eligible_observation_at,
        "next_cycle_point_in_time_eligible_asset_count": len(warm),
        "next_cycle_point_in_time_basis": NEXT_CYCLE_POINT_IN_TIME_BASIS,
        "baseline_feature_readiness": _next_cycle_feature_readiness(
            assessment.get("baseline_feature_readiness"),
            asset_readiness=asset_readiness,
        ),
        "research_only": True,
    }


def _unavailable_current_universe_maturity(
    current_asset_ids: Sequence[str],
) -> dict[str, Any]:
    expected = _expected_asset_ids(current_asset_ids)
    return {
        "status": "unavailable",
        "scope": "current_authoritative_universe",
        "expected_asset_count": len(expected),
        "observed_asset_count": 0,
        "observed_asset_ids": [],
        "missing_asset_count": 0,
        "missing_asset_ids": [],
        "non_warm_asset_ids": [],
        "baseline_observation_count": 0,
        "baseline_counted_observation_count": 0,
        "baseline_warm_asset_count": 0,
        "next_cycle_point_in_time_eligible_at": None,
        "next_cycle_point_in_time_eligible_asset_count": 0,
        "next_cycle_point_in_time_basis": NEXT_CYCLE_POINT_IN_TIME_BASIS,
        "baseline_feature_readiness": {},
        "research_only": True,
    }


def _expected_asset_ids(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(value).strip()
                for value in values
                if isinstance(value, str) and value.strip()
            }
        )
    )


def _next_cycle_feature_readiness(
    value: object,
    *,
    asset_readiness: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Add conditional next-observation truth from existing per-asset readiness."""

    summaries = _mapping(value)
    output: dict[str, dict[str, Any]] = {}
    for group, raw_summary in summaries.items():
        summary = dict(raw_summary) if isinstance(raw_summary, Mapping) else {}
        eligible = 0
        deficits: list[dict[str, Any]] = []
        for asset_id, raw_asset in sorted(asset_readiness.items()):
            asset = _mapping(raw_asset)
            group_readiness = _mapping(
                _mapping(asset.get("feature_readiness")).get(group)
            )
            status = str(group_readiness.get("status") or "")
            if status not in {"warm", "warming", "cold", "not_configured"}:
                raise ValueError("unexpected market-history feature readiness status")
            if status == "warm":
                eligible += 1
                continue
            sample_count = _nonnegative_int(group_readiness.get("sample_count"))
            required_sample_count = _nonnegative_int(
                group_readiness.get("required_sample_count")
            )
            coverage_seconds = _nonnegative_int(
                group_readiness.get("coverage_seconds")
            )
            required_coverage_seconds = _nonnegative_int(
                group_readiness.get("required_coverage_seconds")
            )
            deficits.append(
                {
                    "canonical_asset_id": str(asset_id),
                    "status": status,
                    "sample_count": sample_count,
                    "required_sample_count": required_sample_count,
                    "sample_deficit": max(
                        0, required_sample_count - sample_count
                    ),
                    "coverage_seconds": coverage_seconds,
                    "required_coverage_seconds": required_coverage_seconds,
                    "coverage_deficit_seconds": max(
                        0, required_coverage_seconds - coverage_seconds
                    ),
                }
            )
        summary["next_cycle_point_in_time_eligible_asset_count"] = eligible
        summary["deficit_assets"] = deficits
        output[str(group)] = summary
    return output


def _mapping_keys(value: object) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return ()
    return tuple(str(key) for key in value)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


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


__all__ = (
    "LIVE_HISTORY_CACHE_NAMESPACE",
    "NEXT_CYCLE_POINT_IN_TIME_BASIS",
    "cache_readiness",
    "enrich_and_persist_history",
)
