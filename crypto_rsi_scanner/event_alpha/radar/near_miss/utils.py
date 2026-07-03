"""Event Alpha near-miss utility helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from .... import (
    event_alpha_router,
    event_alpha_quality_fields,
    event_core_opportunities,
    event_llm_evidence_planner,
    event_market_confirmation,
    event_opportunity_verdict,
    event_source_packs,
    event_source_registry,
)
from .models import *  # noqa: F403 - split modules share legacy model names


def _playbook_needs_derivatives(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(row.get(key) or "") for key in ("playbook_type", "playbook_hint", "impact_category", "impact_path_type")).casefold()
    return any(token in text for token in ("perp", "squeeze", "proxy", "listing"))


def _playbook_needs_supply(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(row.get(key) or "") for key in ("playbook_type", "playbook_hint", "impact_category", "impact_path_type")).casefold()
    return "unlock" in text or "supply" in text


def _level_rank(level: str) -> int:
    order = {
        "local_only": 0,
        "exploratory": 1,
        "validated_digest": 2,
        "watchlist": 3,
        "high_priority": 4,
    }
    return order.get(str(level or ""), 0)


def _clean_reason(value: str) -> str:
    return str(value or "").strip().replace(" ", "_")


def _iter_texts(value: Any) -> tuple[str, ...]:
    if value in (None, "", [], {}, ()):
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(str(key) for key in value)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _age_seconds(timestamp: Any, now: datetime) -> float | None:
    if timestamp in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    parsed = _as_utc(parsed)
    return max(0.0, (now - parsed).total_seconds())


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _row_from_object(item: Mapping[str, Any] | object | None) -> dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, Mapping):
        data = dict(item)
    else:
        data = dict(getattr(item, "__dict__", {}) or {})
    components = data.get("latest_score_components")
    if isinstance(components, Mapping):
        for key, value in components.items():
            data.setdefault(key, value)
    score_components = data.get("score_components")
    if isinstance(score_components, Mapping):
        for key, value in score_components.items():
            data.setdefault(key, value)
    return data
