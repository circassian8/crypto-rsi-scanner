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
    "market_context_freshness_status",
    "market_context_age_hours",
    "market_context_stale",
    "market_context_freshness_cap_applied",
    "opportunity_score_final",
    "opportunity_level",
    "opportunity_verdict_reasons",
    "why_local_only",
    "why_not_watchlist",
    "manual_verification_items",
    "upgrade_requirements",
    "downgrade_warnings",
)

_ZERO_DEFAULTS = {
    "evidence_quality_score",
    "market_confirmation_score",
    "opportunity_score_final",
}

_LIST_DEFAULTS = {
    "opportunity_verdict_reasons",
    "manual_verification_items",
    "upgrade_requirements",
    "downgrade_warnings",
}

_BOOL_DEFAULTS = {
    "market_context_stale",
    "market_context_freshness_cap_applied",
}

_CONSERVATIVE_STRING_DEFAULTS = {
    "impact_path_type": "insufficient_data",
    "impact_path_strength": "none",
    "candidate_role": "unknown_with_reason",
    "source_class": "insufficient_data",
    "evidence_specificity": "insufficient_data",
    "market_confirmation_level": "insufficient_data",
    "market_context_freshness_status": "missing",
    "opportunity_level": "local_only",
}

_CONSERVATIVE_LIST_DEFAULTS = {
    "opportunity_verdict_reasons": ["quality_context_missing"],
    "manual_verification_items": [
        "verify catalyst, asset identity, market confirmation, source quality, and liquidity",
    ],
    "upgrade_requirements": ["needs_quality_context"],
    "downgrade_warnings": ["insufficient_data"],
}


def quality_field_defaults() -> dict[str, Any]:
    """Return conservative defaults for newly written research artifacts."""
    defaults: dict[str, Any] = {}
    for key in REQUIRED_QUALITY_FIELDS:
        if key in _ZERO_DEFAULTS:
            defaults[key] = 0.0
        elif key in _LIST_DEFAULTS:
            defaults[key] = list(_CONSERVATIVE_LIST_DEFAULTS[key])
        elif key in _BOOL_DEFAULTS:
            defaults[key] = False
        elif key in {"why_local_only", "why_not_watchlist"}:
            defaults[key] = "quality_context_missing"
        elif key in _CONSERVATIVE_STRING_DEFAULTS:
            defaults[key] = _CONSERVATIVE_STRING_DEFAULTS[key]
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
        if _is_missing_value(out.get(key)) and not _is_missing_value(component_values.get(key)):
            out[key] = _copy_value(component_values.get(key))
        elif _is_missing_value(out.get(key)):
            out[key] = _contextual_default(key, out, defaults)
    _apply_final_verdict_aliases(out, component_values)
    _attach_upgrade_path(out)
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


def missing_top_level_quality_fields(row: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Return required quality fields missing from the top-level artifact row."""
    data = dict(row or {})
    return tuple(key for key in REQUIRED_QUALITY_FIELDS if is_missing_quality_value(data.get(key)))


def has_full_top_level_quality(row: Mapping[str, Any] | None) -> bool:
    """Return true when every canonical quality field is populated at row top level."""
    return not missing_top_level_quality_fields(row)


def has_any_quality_field(row: Mapping[str, Any] | None, *, components_key: str = "score_components") -> bool:
    """Return true when a row carries any modern quality-field metadata."""
    data = dict(row or {})
    components = data.get(components_key)
    if not isinstance(components, Mapping):
        components = data.get("latest_score_components")
    if not isinstance(components, Mapping):
        components = {}
    return any(not _is_missing_value(data.get(key)) or not _is_missing_value(components.get(key)) for key in REQUIRED_QUALITY_FIELDS)


def quality_components(row: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge top-level row values and nested score components for reports."""
    data = dict(row or {})
    nested = data.get("latest_score_components")
    if not isinstance(nested, Mapping):
        nested = data.get("score_components")
    out = dict(nested or {})
    for key, value in data.items():
        if key in REQUIRED_QUALITY_FIELDS:
            if not _is_missing_value(value):
                out[key] = value
        elif key not in out and value not in (None, "", [], {}):
            out[key] = value
    return ensure_quality_fields(out)


def _apply_final_verdict_aliases(out: dict[str, Any], component_values: Mapping[str, Any]) -> None:
    """Prefer canonical post-refresh verdict aliases when present.

    Older artifacts may still carry pre-refresh ``opportunity_*`` fields while
    newer refresh/acquisition paths write ``final_opportunity_*``. The final
    fields are presentation/routing metadata only, but when they exist they are
    the authoritative operator-facing verdict.
    """
    for final_key, canonical_key in (
        ("final_opportunity_score", "opportunity_score_final"),
        ("final_opportunity_level", "opportunity_level"),
    ):
        value = out.get(final_key)
        if _is_missing_value(value):
            value = component_values.get(final_key)
        if not _is_missing_value(value):
            out[canonical_key] = _copy_value(value)
    for final_key, canonical_key in (
        ("post_refresh_market_confirmation_level", "market_confirmation_level"),
        ("post_refresh_market_confirmation_score", "market_confirmation_score"),
        ("post_refresh_evidence_quality_score", "evidence_quality_score"),
    ):
        value = out.get(final_key)
        if _is_missing_value(value):
            value = component_values.get(final_key)
        if not _is_missing_value(value):
            out[canonical_key] = _copy_value(value)
    freshness = out.get("market_data_freshness")
    if _is_missing_value(freshness):
        freshness = component_values.get("market_data_freshness")
    if not _is_missing_value(freshness):
        out["market_context_freshness_status"] = _copy_value(freshness)


def quality_source(row: Mapping[str, Any] | None, *, components_key: str = "score_components") -> str:
    """Classify where usable quality metadata comes from for audit reports."""
    data = dict(row or {})
    if has_full_top_level_quality(data):
        return "top_level"
    components = data.get(components_key)
    if not isinstance(components, Mapping):
        components = data.get("latest_score_components")
    if isinstance(components, Mapping) and all(not is_missing_quality_value(components.get(key)) for key in REQUIRED_QUALITY_FIELDS):
        return "nested_score_components"
    if has_any_quality_field(data, components_key=components_key):
        return "partial_quality_fields"
    return "recomputed"


def _attach_upgrade_path(out: dict[str, Any]) -> None:
    """Fill upgrade/downgrade diagnostics from canonical fields when absent."""
    if not _is_missing_value(out.get("upgrade_requirements")) and not _is_missing_value(out.get("downgrade_warnings")):
        return
    try:
        from crypto_rsi_scanner import event_opportunity_verdict

        upgrade = event_opportunity_verdict.explain_upgrade_path(components=out)
    except Exception:
        upgrade = None
    if _is_missing_value(out.get("upgrade_requirements")):
        out["upgrade_requirements"] = list(getattr(upgrade, "upgrade_requirements", ()) or _CONSERVATIVE_LIST_DEFAULTS["upgrade_requirements"])
    if _is_missing_value(out.get("downgrade_warnings")):
        out["downgrade_warnings"] = list(getattr(upgrade, "downgrade_warnings", ()) or _CONSERVATIVE_LIST_DEFAULTS["downgrade_warnings"])


def _contextual_default(key: str, row: Mapping[str, Any], defaults: Mapping[str, Any]) -> Any:
    if key == "why_local_only":
        level = str(row.get("opportunity_level") or "")
        return "not_local_only" if level in {"validated_digest", "watchlist", "high_priority"} else "quality_context_missing"
    if key == "why_not_watchlist":
        level = str(row.get("opportunity_level") or "")
        return "already_watchlisted" if level in {"watchlist", "high_priority"} else "not_watchlist_without_quality_context"
    return _copy_value(defaults[key])


def _copy_value(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


def _is_missing_value(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == () or value == {}


def is_missing_quality_value(value: Any) -> bool:
    """Return true when a canonical quality field value should be filled."""
    return _is_missing_value(value)
