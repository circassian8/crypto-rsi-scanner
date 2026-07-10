"""Generic value and score helpers for opportunity verdict policy."""

from __future__ import annotations

from typing import Any, Mapping


def _object_mapping(prefix: str, value: object | Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    out: dict[str, Any] = {}
    for key in (
        "opportunity_score_final",
        "opportunity_level",
        "impact_path_type",
        "impact_path_strength",
        "candidate_role",
        "market_confirmation_score",
        "level",
        "market_context_freshness_status",
        "market_context_age_hours",
        "freshness_cap_applied",
        "derivatives_confirmation_score",
        "derivatives_confirmation_level",
        "derivatives_confirmation_reasons",
        "derivatives_freshness_status",
        "dex_liquidity_score",
        "dex_liquidity_level",
        "dex_liquidity_reasons",
        "dex_freshness_status",
        "protocol_metrics_score",
        "protocol_metrics_level",
        "protocol_metrics_reasons",
        "protocol_metrics_freshness_status",
        "evidence_quality_score",
        "source_class",
        "evidence_specificity",
    ):
        if hasattr(value, key):
            out[key] = getattr(value, key)
            out[f"{prefix}_{key}"] = getattr(value, key)
    return out


def _path_strength_score(strength: str) -> float:
    return {
        "strong": 95.0,
        "medium": 68.0,
        "weak": 35.0,
        "none": 0.0,
    }.get(str(strength or ""), 0.0)


def _score(*values: object) -> float:
    for value in values:
        if value in (None, ""):
            continue
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if 0.0 <= number <= 1.0:
            number *= 100.0
        return max(0.0, min(100.0, number))
    return 0.0


def _lower_values(data: Mapping[str, Any], *keys: str) -> set[str]:
    out: set[str] = set()
    for key in keys:
        for value in _as_values(data.get(key)):
            text = str(value or "").strip().casefold()
            if text:
                out.add(text)
    return out


def _lower_text_blob(data: Mapping[str, Any], *keys: str) -> str:
    return " ".join(
        str(data.get(key) or "")
        for key in keys
        if str(data.get(key) or "").strip()
    ).casefold()


def _non_generic_impact_path(path: str, strength: str) -> bool:
    if strength in {"strong", "medium"} and path not in {"", "unknown", "insufficient_data"}:
        return True
    return path not in {
        "",
        "unknown",
        "insufficient_data",
        "generic_cooccurrence_only",
        "macro_attention_only",
        "technology_risk",
        "market_structure_policy",
    }


def _count_value(*values: object) -> int:
    for value in values:
        if value in (None, "", (), [], {}):
            continue
        if isinstance(value, Mapping):
            return len(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 1
        try:
            if isinstance(value, (list, tuple, set)):
                return len(value)
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    return 0


def _as_values(value: object) -> tuple[object, ...]:
    if value in (None, "", [], {}, ()):
        return ()
    if isinstance(value, Mapping):
        return tuple(value.values())
    if isinstance(value, str):
        return (value,)
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return (value,)
