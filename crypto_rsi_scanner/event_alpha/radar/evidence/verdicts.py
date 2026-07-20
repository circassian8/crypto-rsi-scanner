"""Evidence acquisition final verdict helpers."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality
import crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner as event_llm_evidence_planner
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ..resolver import clean_text
from ...providers import source_packs as event_source_packs
from ...providers import source_registry as event_source_registry
from .. import catalyst_search as event_catalyst_search
from .. import core_opportunities as event_core_opportunities
from .. import impact_hypotheses as event_impact_hypotheses
from .. import source_enrichment as event_source_enrichment
from .models import *  # noqa: F403 - split modules share historical model names


def _evidence_status(
    status: str,
    *,
    accepted_evidence: Iterable[Mapping[str, Any]],
    rejected_evidence: Iterable[Mapping[str, Any]],
) -> str:
    if tuple(accepted_evidence):
        return "accepted_evidence_found"
    if tuple(rejected_evidence):
        return "rejected_only"
    if status == EvidenceAcquisitionStatus.NO_RESULTS.value:
        return "no_results"
    if status in {
        EvidenceAcquisitionStatus.FAILED_SOFT.value,
        EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value,
        EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value,
    }:
        return "failed"
    return "no_results"


def _canonical_final_verdict(
    *,
    before: object | None,
    after: object | None,
    before_score: float,
    before_level: str,
    after_score: float,
    after_level: str,
    accepted: bool,
) -> tuple[float, str, str, str]:
    before_components = dict(getattr(before, "score_components", {}) or {})
    after_components = dict(getattr(after, "score_components", {}) or {})
    before_has_refresh = _market_refresh_succeeded(before, before_components)
    after_has_refresh = _market_refresh_succeeded(after, after_components)
    after_weaker = (
        _level_rank(after_level) < _level_rank(before_level)
        or after_score < before_score - 0.01
    )
    if before_has_refresh and after_weaker and not after_has_refresh:
        source = "market_refresh"
        reason = "preserved_stronger_market_refresh_verdict"
        return before_score, before_level, source, reason
    if accepted and after_has_refresh:
        return after_score, after_level, "combined_refresh", "accepted_evidence_with_market_refresh"
    if accepted:
        return after_score, after_level, "evidence_acquisition", "accepted_source_pack_evidence"
    if after_has_refresh:
        return after_score, after_level, "market_refresh", "market_refresh_verdict"
    return before_score, before_level, "initial", "no_canonical_refresh_change"


def _score_from_object(item: object | None, fallback: float) -> float:
    if item is None:
        return fallback
    components = dict(getattr(item, "score_components", {}) or {})
    for value in (
        getattr(item, "final_opportunity_score", None),
        components.get("final_opportunity_score"),
        getattr(item, "opportunity_score_final", None),
        components.get("opportunity_score_final"),
        getattr(item, "hypothesis_score", None),
    ):
        if value in (None, "", [], {}, ()):
            continue
        parsed = _float(value)
        # An explicit malformed higher-precedence value fails closed instead of
        # borrowing a potentially stale compatibility alias.
        return parsed if parsed is not None else fallback
    return fallback


def _level_from_object(item: object | None, fallback: str) -> str:
    if item is None:
        return fallback
    components = dict(getattr(item, "score_components", {}) or {})
    return str(
        getattr(item, "final_opportunity_level", "")
        or components.get("final_opportunity_level")
        or getattr(item, "opportunity_level", "")
        or components.get("opportunity_level")
        or fallback
    )


def _level_delta(before: str, after: str) -> str:
    diff = _level_rank(after) - _level_rank(before)
    if diff > 0:
        return "up"
    if diff < 0:
        return "down"
    return "unchanged"


def _level_rank(level: str | None) -> int:
    return {
        "local_only": 0,
        "exploratory": 1,
        "validated_digest": 2,
        "watchlist": 3,
        "high_priority": 4,
    }.get(str(level or "").casefold(), 0)


def _impact_path_rank(value: str | None) -> int:
    text = str(value or "").casefold()
    if "impact_path_validated" in text or "strong" in text:
        return 3
    if "catalyst_link_validated" in text or "medium" in text:
        return 2
    if text and "insufficient" not in text:
        return 1
    return 0


def _market_score_from_components(components: Mapping[str, Any]) -> float:
    for field in ("market_confirmation_score", "market_confirmation"):
        value = components.get(field)
        if value in (None, "", [], {}, ()):
            continue
        parsed = _float(value)
        return parsed if parsed is not None else 0.0
    return 0.0


def _market_level_from_components(components: Mapping[str, Any]) -> str | None:
    value = components.get("market_confirmation_level") or components.get("post_refresh_market_confirmation_level")
    return str(value) if value not in (None, "") else None


def _market_level_from_score(score: float) -> str | None:
    if score >= 70:
        return "strong"
    if score >= 40:
        return "moderate"
    if score > 0:
        return "weak"
    return "none"


def _market_refresh_succeeded(
    item: object | None,
    components: Mapping[str, Any],
) -> bool:
    if "market_refresh_success" in components:
        return _semantic_bool(components.get("market_refresh_success")) is True
    return _semantic_bool(getattr(item, "market_refresh_success", None)) is True


def _semantic_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off", ""}:
        return False
    return None


def _market_freshness_from_components(components: Mapping[str, Any]) -> str | None:
    value = (
        components.get("market_data_freshness")
        or components.get("market_context_freshness_status")
        or _nested_market_freshness(components.get("market_context_after"))
        or _nested_market_freshness(components.get("market_context_before"))
    )
    return str(value) if value not in (None, "") else None


def _best_market_freshness(*components_list: Mapping[str, Any]) -> str | None:
    values = [
        _market_freshness_from_components(components)
        for components in components_list
        if isinstance(components, Mapping)
    ]
    for preferred in ("fresh", "fixture_allowed_stale", "stale", "unknown", "missing"):
        if preferred in values:
            return preferred
    return next((value for value in values if value), None)


def _nested_market_freshness(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    freshness = value.get("freshness_status") or value.get("data_quality")
    return str(freshness) if freshness not in (None, "") else None


def _components_for_final_verdict(
    *,
    final_source: str,
    before_components: Mapping[str, Any],
    after_components: Mapping[str, Any],
) -> Mapping[str, Any]:
    if final_source == "market_refresh":
        return before_components
    if final_source == "combined_refresh":
        merged = dict(before_components)
        merged.update({key: value for key, value in after_components.items() if value not in (None, "", [], {}, ())})
        before_score = _market_score_from_components(before_components)
        after_score = _market_score_from_components(after_components)
        if before_score > after_score:
            merged["market_confirmation_score"] = before_score
            before_level = _market_level_from_components(before_components) or _market_level_from_score(before_score)
            if before_level:
                merged["market_confirmation_level"] = before_level
        if not merged.get("market_context_freshness_status"):
            freshness = _market_freshness_from_components(before_components) or _market_freshness_from_components(after_components)
            if freshness:
                merged["market_context_freshness_status"] = freshness
        return merged
    return after_components or before_components


def _optional_delta(before: object, after: object) -> float | None:
    before_number = _float(before)
    after_number = _float(after)
    if before_number is None or after_number is None:
        return None
    return round(after_number - before_number, 2)


def _no_upgrade_reason(status: str, failures: Iterable[str]) -> str:
    if status == EvidenceAcquisitionStatus.NO_RESULTS.value:
        return "no_source_pack_results"
    if status == EvidenceAcquisitionStatus.REJECTED_RESULTS_ONLY.value:
        return "source_pack_results_rejected"
    if status in {EvidenceAcquisitionStatus.PROVIDER_UNAVAILABLE.value, EvidenceAcquisitionStatus.PROVIDER_BACKOFF.value}:
        return "provider_unavailable_or_backoff"
    if failures:
        return "provider_failures"
    return "no_accepted_evidence"


def _acquisition_id(opportunity_id: str, hypothesis_id: str | None, source_pack: str) -> str:
    seed = "|".join((opportunity_id, hypothesis_id or "", source_pack))
    return "acq:" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        if value in (None, "", [], {}, ()):
            return None
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
