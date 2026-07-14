"""Pure query, joining, and prioritization helpers for dashboard pages."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from ..operations import market_provenance
from .loader import candidate_identifier


QUERY_FIELDS = (
    "search",
    "route",
    "origin",
    "bias",
    "actionability",
    "evidence",
    "risk",
    "urgency",
    "timing",
    "market_phase",
    "catalyst",
    "tradability",
    "spread",
    "data_mode",
    "freshness",
    "horizon",
    "sort",
)

_ROUTE_PRIORITY = {
    "high_confidence_watch": 0,
    "actionable_watch": 1,
    "rapid_market_anomaly": 2,
    "dashboard_watch": 3,
    "fade_exhaustion_review": 4,
    "risk_watch": 5,
    "calendar_risk": 6,
    "diagnostic": 7,
}


def dashboard_query(query: Mapping[str, str] | None) -> dict[str, str]:
    """Return bounded allowlisted query values without interpreting raw HTML."""

    if not isinstance(query, Mapping):
        return {}
    out: dict[str, str] = {}
    for field in QUERY_FIELDS:
        value = query.get(field)
        text = value.strip() if isinstance(value, str) else ""
        if text and len(text) <= 120:
            out[field] = text.casefold()
    return out


def filter_sort_candidates(
    rows: Iterable[Mapping[str, Any]],
    query: Mapping[str, str] | None = None,
) -> tuple[Mapping[str, Any], ...]:
    """Apply operator filters and a deterministic allowlisted ordering."""

    filters = dashboard_query(query)
    selected = [row for row in rows if _candidate_matches(row, filters)]
    sort_name = filters.get("sort") or "attention"
    selected.sort(key=lambda row: _candidate_sort_key(row, sort_name))
    return tuple(selected)


def filter_sort_observations(
    rows: Iterable[Mapping[str, Any]],
    query: Mapping[str, str] | None = None,
) -> tuple[Mapping[str, Any], ...]:
    filters = dashboard_query(query)
    selected = []
    for row in rows:
        search = filters.get("search")
        if search and search not in _searchable_text(row):
            continue
        if filters.get("freshness") and token(row.get("freshness_status")) != filters["freshness"]:
            continue
        if filters.get("spread") and token(row.get("spread_status")) != filters["spread"]:
            continue
        if filters.get("data_mode") and filters["data_mode"] not in {
            token(row.get("data_mode")), token(row.get("candidate_source_mode")),
        }:
            continue
        selected.append(row)
    sort_name = filters.get("sort") or "return_24h_desc"
    field, descending = {
        "return_1h_desc": ("return_1h", True),
        "return_4h_desc": ("return_4h", True),
        "return_24h_desc": ("return_24h", True),
        "volume_desc": ("volume_24h", True),
        "turnover_desc": ("volume_to_market_cap", True),
        "market_cap_desc": ("market_cap", True),
    }.get(sort_name, ("return_24h", True))
    selected.sort(
        key=lambda row: (
            _number_sort(row.get(field), descending=descending),
            token(row.get("symbol") or row.get("coin_id")),
        )
    )
    return tuple(selected)


def candidate_provenance(row: Mapping[str, Any]) -> Mapping[str, Any]:
    canonical = market_provenance.market_provenance_values(row)
    if canonical:
        return canonical
    projection = row.get("decision_projection")
    projection = projection if isinstance(projection, Mapping) else {}
    lineage = projection.get("source_provider_lineage")
    lineage = lineage if isinstance(lineage, Mapping) else {}
    containers = (
        projection.get("market_provenance"), row.get("market_provenance"),
        lineage.get("market_provenance"), row.get("market_state_snapshot"),
        row.get("market_snapshot"), lineage,
    )
    merged: dict[str, Any] = {}
    fields = (
        "data_mode", "data_acquisition_mode", "candidate_source_mode", "provider",
        "cache_status", "measurement_program", "decision_radar_campaign_eligible",
        "decision_radar_campaign_counted", "decision_radar_campaign_reason",
        "provider_source_artifact", "provider_source_sha256", "request_ledger_path",
        "request_ledger_sha256", "provenance_contract_valid",
    )
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for field in fields:
            if field not in merged and container.get(field) not in (None, "", [], {}):
                merged[field] = container.get(field)
    return merged


def candidate_data_quality(row: Mapping[str, Any]) -> Mapping[str, Any]:
    projection = row.get("decision_projection")
    projection = projection if isinstance(projection, Mapping) else {}
    for container in (
        row.get("market_state_snapshot"), row.get("market_snapshot"),
        projection.get("market_data_quality"), row.get("market_data_quality"),
        row.get("data_quality"),
    ):
        if not isinstance(container, Mapping):
            continue
        nested = container.get("market_data_quality")
        if isinstance(nested, Mapping):
            return nested
        if any(field in container for field in (
            "baseline_status", "direct_feature_count", "proxy_feature_count",
            "liquidity_basis", "volume_zscore_basis", "spread_basis",
        )):
            return container
    return {}


def origin_tokens(row: Mapping[str, Any]) -> tuple[str, ...]:
    values = [token(row.get("primary_thesis_origin") or row.get("thesis_origin"))]
    origins = row.get("thesis_origins")
    if isinstance(origins, Iterable) and not isinstance(origins, (str, bytes, Mapping)):
        values.extend(token(item) for item in origins)
    return tuple(dict.fromkeys(value for value in values if value))


def score_band_token(value: object) -> str:
    number = finite_number(value)
    if number is None:
        return "unknown"
    if number >= 80:
        return "very_high"
    if number >= 65:
        return "high"
    if number >= 45:
        return "medium"
    return "low"


def risk_band_token(row: Mapping[str, Any]) -> str:
    explicit = token(row.get("risk_band"))
    if explicit in {"low", "medium", "high"}:
        return explicit
    number = finite_number(row.get("risk_score"))
    if number is None:
        return "unknown"
    if number < 40:
        return "low"
    if number < 70:
        return "medium"
    return "high"


def finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def token(value: object) -> str:
    return str(value or "").strip().casefold()


def _candidate_matches(row: Mapping[str, Any], filters: Mapping[str, str]) -> bool:
    if filters.get("search") and filters["search"] not in _searchable_text(row):
        return False
    checks = (
        ("route", token(row.get("_dashboard_route") or row.get("radar_route"))),
        ("bias", token(row.get("directional_bias"))),
        ("timing", token(row.get("timing_state"))),
        ("market_phase", token(row.get("market_phase"))),
        ("catalyst", token(row.get("catalyst_status"))),
        ("tradability", token(row.get("tradability_status"))),
        ("spread", token(row.get("spread_status"))),
        ("freshness", token(row.get("market_data_freshness") or row.get("freshness_status"))),
        ("horizon", token(row.get("preferred_horizon"))),
    )
    if any(filters.get(name) and filters[name] != value for name, value in checks):
        return False
    if filters.get("origin") and filters["origin"] not in origin_tokens(row):
        return False
    provenance = candidate_provenance(row)
    modes = {token(provenance.get("data_mode")), token(provenance.get("candidate_source_mode"))}
    if filters.get("data_mode") and filters["data_mode"] not in modes:
        return False
    score_filters = (
        ("actionability", row.get("actionability_score")),
        ("evidence", row.get("evidence_confidence_score")),
        ("urgency", row.get("urgency_score")),
    )
    if any(filters.get(name) and filters[name] != score_band_token(value) for name, value in score_filters):
        return False
    return not filters.get("risk") or filters["risk"] == risk_band_token(row)


def _candidate_sort_key(row: Mapping[str, Any], sort_name: str) -> tuple[Any, ...]:
    identifier = candidate_identifier(row)
    score_sorts = {
        "actionability_desc": ("actionability_score", True),
        "evidence_desc": ("evidence_confidence_score", True),
        "urgency_desc": ("urgency_score", True),
        "risk_asc": ("risk_score", False),
        "risk_desc": ("risk_score", True),
        "expiry_asc": ("expires_at", False),
    }
    if sort_name == "attention":
        return (
            _ROUTE_PRIORITY.get(token(row.get("_dashboard_route") or row.get("radar_route")), 99),
            _number_sort(row.get("urgency_score"), descending=True),
            _number_sort(row.get("actionability_score"), descending=True), identifier,
        )
    field, descending = score_sorts.get(sort_name, ("actionability_score", True))
    if field == "expires_at":
        return (str(row.get(field) or "~"), identifier)
    return (_number_sort(row.get(field), descending=descending), identifier)


def _number_sort(value: object, *, descending: bool) -> tuple[int, float]:
    number = finite_number(value)
    if number is None:
        return (1, 0.0)
    return (0, -number if descending else number)


def _searchable_text(row: Mapping[str, Any]) -> str:
    values = (
        row.get("symbol"), row.get("coin_id"), row.get("validated_symbol"),
        row.get("validated_coin_id"), row.get("why_now"), row.get("latest_source_title"),
        row.get("radar_route"), row.get("_dashboard_route"), row.get("directional_bias"),
    )
    return " ".join(str(value or "") for value in values).casefold()


__all__ = (
    "QUERY_FIELDS", "candidate_data_quality", "candidate_provenance", "dashboard_query",
    "filter_sort_candidates", "filter_sort_observations", "finite_number", "origin_tokens",
    "risk_band_token", "score_band_token", "token",
)
