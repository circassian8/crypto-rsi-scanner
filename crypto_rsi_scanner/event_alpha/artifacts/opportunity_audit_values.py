"""Normalization and scalar helpers for opportunity audit rendering."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist


def _as_list_values(value: Any) -> set[str]:
    if value in (None, "", [], {}, ()):
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, Iterable) and not isinstance(value, Mapping):
        return {str(item) for item in value if str(item or "")}
    return {str(value)}


def _entry_row(entry: event_watchlist.EventWatchlistEntry | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(entry, Mapping):
        return dict(entry)
    row = asdict(entry)
    row["alert_id"] = event_alpha_router.alert_id_for_entry(entry)
    row["card_id"] = event_alpha_router.card_id_for_entry(entry)
    return row


def _row(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(getattr(value, "__dict__", {}) or {})


def _components(row: Mapping[str, Any]) -> dict[str, Any]:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    if not components and isinstance(row.get("score_components"), Mapping):
        components = row.get("score_components")
    out = dict(components)
    for key, value in row.items():
        if key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS:
            if value not in (None, "", [], {}):
                out[key] = value
        elif key not in out and value not in (None, "", [], {}):
            out[key] = value
    return event_alpha_quality_fields.ensure_quality_fields(out)


def _incident_context(
    row: Mapping[str, Any],
    components: Mapping[str, Any],
    incidents: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    incident_id = str(row.get("incident_id") or components.get("incident_id") or "")
    if not incident_id:
        return row if str(row.get("row_type") or "") == "event_incident" else None
    for incident in incidents:
        if str(incident.get("incident_id") or "") == incident_id:
            return incident
    return row if row.get("incident_id") else None


def _claim_history_value(value: Any) -> str:
    if not value:
        return "none"
    labels: list[str] = []
    for item in list(value)[:4]:
        if isinstance(item, Mapping):
            labels.append(
                f"{item.get('claim_type') or 'claim'}:"
                f"{item.get('polarity') or 'unknown'}/"
                f"{item.get('cause_status') or 'unknown'}"
            )
        else:
            labels.append(str(item))
    return "; ".join(labels) or "none"


def _asset_role_summary(row: Mapping[str, Any], components: Mapping[str, Any]) -> str:
    symbol = components.get("validated_symbol") or row.get("validated_symbol") or row.get("symbol")
    coin_id = components.get("validated_coin_id") or row.get("validated_coin_id") or row.get("coin_id")
    role = components.get("candidate_role") or row.get("candidate_role") or "unknown"
    if symbol or coin_id:
        return f"{symbol or coin_id}({role})"
    return "none"


def _quality_source(row: Mapping[str, Any]) -> str:
    source = event_alpha_quality_fields.quality_source(row, components_key="latest_score_components")
    if source == "nested_score_components":
        return "nested_score_components"
    if source in {"partial_quality_fields", "recomputed"}:
        return "recomputed" if source == "recomputed" else "partial_top_level_recomputed"
    return source


def _value(row: Mapping[str, Any], *keys: Any, default: str = "unknown") -> str:
    for key in keys:
        if isinstance(key, str):
            value = row.get(key)
        else:
            value = key
        if value not in (None, "", [], {}):
            return str(value)
    return default


def _list_value(value: Any) -> str:
    if value in (None, "", [], ()):
        return "none"
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return ", ".join(f"{key}={child}" for key, child in list(value.items())[:6])
    return "; ".join(str(item) for item in list(value)[:6])


def _market_age_value(components: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    age_hours = _float_value(
        components.get("market_context_age_hours")
        if components.get("market_context_age_hours") is not None
        else row.get("market_context_age_hours")
    )
    if age_hours is None:
        age_seconds = _float_value(
            components.get("market_context_age_seconds")
            if components.get("market_context_age_seconds") is not None
            else row.get("market_context_age_seconds")
        )
        if age_seconds is not None:
            age_hours = age_seconds / 3600.0
    if age_hours is None:
        return "n/a"
    if age_hours < 1:
        return f"{age_hours * 60:.0f}m"
    return f"{age_hours:.1f}h"


def _float_value(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _asset_list(value: Any) -> str:
    if not value:
        return "none"
    if isinstance(value, Mapping):
        value = [value]
    rows = []
    for item in list(value)[:6]:
        if isinstance(item, Mapping):
            rows.append(
                f"{item.get('symbol') or item.get('coin_id') or item.get('name') or 'asset'}"
                f"({item.get('rejection_reason') or item.get('identity_reason') or item.get('source') or 'candidate'})"
            )
        else:
            rows.append(str(item))
    return "; ".join(rows)


def _role_capabilities_value(value: Any) -> str:
    if not isinstance(value, Mapping):
        return "unknown"
    enabled = [str(key) for key, child in sorted(value.items()) if bool(child)]
    return ", ".join(enabled) if enabled else "none"


def _collect_core_row_values(rows: Iterable[Mapping[str, Any]], *keys: str) -> tuple[str, ...]:
    values: list[str] = []
    for row in rows:
        for key in keys:
            value = row.get(key)
            if value not in (None, "", [], {}, ()):
                values.append(str(value))
    return tuple(dict.fromkeys(values))
