"""Shared Event Alpha signal-quality artifact field helpers."""

from __future__ import annotations

from typing import Any, Mapping


REQUIRED_QUALITY_FIELDS: tuple[str, ...] = (
    "impact_path_type",
    "impact_path_strength",
    "candidate_role",
    "evidence_quality_score",
    "source_class",
    "evidence_specificity",
    "market_confirmation_score",
    "market_confirmation_level",
    "opportunity_score_final",
    "opportunity_level",
    "opportunity_verdict_reasons",
    "why_local_only",
    "why_not_watchlist",
    "manual_verification_items",
)

_ZERO_DEFAULTS = {
    "evidence_quality_score",
    "market_confirmation_score",
    "opportunity_score_final",
}

_LIST_DEFAULTS = {
    "opportunity_verdict_reasons",
    "manual_verification_items",
}


def quality_field_defaults() -> dict[str, Any]:
    """Return conservative defaults for newly written research artifacts."""
    defaults: dict[str, Any] = {}
    for key in REQUIRED_QUALITY_FIELDS:
        if key in _ZERO_DEFAULTS:
            defaults[key] = 0.0
        elif key in _LIST_DEFAULTS:
            defaults[key] = []
        elif key in {"why_local_only", "why_not_watchlist"}:
            defaults[key] = None
        else:
            defaults[key] = "unknown"
    return defaults


def ensure_quality_fields(row: Mapping[str, Any] | None, *, components: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a dict with all required quality fields present.

    Values already present on ``row`` win, then values from ``components``, then
    conservative defaults. This is artifact hygiene only; it does not score or
    promote candidates.
    """
    out = dict(row or {})
    component_values = dict(components or {})
    defaults = quality_field_defaults()
    for key in REQUIRED_QUALITY_FIELDS:
        if out.get(key) in (None, "") and component_values.get(key) not in (None, ""):
            out[key] = component_values.get(key)
        elif key not in out:
            out[key] = defaults[key]
    return out


def missing_quality_fields(row: Mapping[str, Any] | None, *, components_key: str = "score_components") -> tuple[str, ...]:
    """Return required quality fields absent from a row and nested components."""
    data = dict(row or {})
    components = data.get(components_key)
    if not isinstance(components, Mapping):
        components = data.get("latest_score_components")
    if not isinstance(components, Mapping):
        components = {}
    missing: list[str] = []
    for key in REQUIRED_QUALITY_FIELDS:
        if key in data or key in components:
            continue
        missing.append(key)
    return tuple(missing)


def has_any_quality_field(row: Mapping[str, Any] | None, *, components_key: str = "score_components") -> bool:
    """Return true when a row carries any modern quality-field metadata."""
    return len(missing_quality_fields(row, components_key=components_key)) < len(REQUIRED_QUALITY_FIELDS)


def quality_components(row: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge top-level row values and nested score components for reports."""
    data = dict(row or {})
    nested = data.get("latest_score_components")
    if not isinstance(nested, Mapping):
        nested = data.get("score_components")
    out = dict(nested or {})
    for key, value in data.items():
        if key not in out and value not in (None, "", [], {}):
            out[key] = value
    return ensure_quality_fields(out)
