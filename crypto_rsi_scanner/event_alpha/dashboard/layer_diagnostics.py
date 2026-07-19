"""Truthful exact-generation coverage and market-observation dashboard blocks."""

from __future__ import annotations

import html
import math
from typing import Any, Callable, Iterable, Mapping

from .models import DashboardSnapshot


_LAYER_SOURCE_PACKS = {
    "anomalies": {"market_anomaly_pack", "dex_liquidity_pack"},
    "catalysts": {
        "official_exchange_listing_pack",
        "official_exchange_risk_pack",
        "official_perp_listing_pack",
        "proxy_preipo_rwa_pack",
        "strategic_investment_pack",
        "security_shock_pack",
        "fan_sports_pack",
        "listing_liquidity_pack",
    },
    "fade_risk": {
        "official_exchange_risk_pack",
        "official_perp_listing_pack",
        "perp_listing_squeeze_pack",
        "unlock_supply_pack",
        "security_shock_pack",
        "market_anomaly_pack",
    },
    "calendar": {"unlock_supply_pack"},
}


def render_layer_status(
    snapshot: DashboardSnapshot,
    layer: str,
    visible_count: int,
) -> str:
    """Describe whether an empty layer was observed or simply not acquired."""

    observation_count = len(snapshot.current_market_observations)
    if layer == "calendar":
        calendar_snapshot = snapshot.market_generation.get("calendar_snapshot")
        if isinstance(calendar_snapshot, Mapping):
            return _calendar_snapshot_layer_status(calendar_snapshot, visible_count)
    packs = _coverage_pack_rows(snapshot, layer)
    statuses = {
        _token(row.get("provider_coverage_status") or row.get("source_pack_coverage_status"))
        for row in packs
    }
    statuses.discard("")
    if visible_count:
        headline = f"Observed: {visible_count} exact-generation row(s)."
    elif layer in {"today", "anomalies"} and observation_count:
        headline = (
            f"Observed zero Decision rows after loading {observation_count} exact-generation "
            "market observation(s)."
        )
    else:
        headline = "No exact-generation rows are available in this layer."

    if not packs:
        if snapshot.source_coverage:
            detail = (
                "The exact source-coverage artifact has no per-pack assessment for this layer, "
                "so this zero must not be interpreted as proof that no relevant events exist."
            )
        else:
            detail = (
                "Exact source-coverage detail is unavailable; this zero must not be interpreted "
                "as proof that no relevant events exist."
            )
    elif statuses and statuses <= {"not_configured"}:
        detail = (
            "Relevant source packs were not configured for this generation. This layer was "
            "unavailable, and zero rows is not evidence that no relevant events exist."
        )
    elif "skipped_live_calls_disabled" in statuses:
        detail = (
            "At least one relevant source pack was skipped because live calls were disabled. "
            "Coverage is incomplete, so zero rows is not evidence that no relevant events exist."
        )
    elif statuses & {"partial", "degraded", "unavailable", "provider_unavailable", "backoff"}:
        detail = (
            "Relevant source coverage was partial or degraded. Treat this layer as incomplete, "
            "not as a confirmed absence of relevant events."
        )
    elif statuses & {"observed_healthy", "observed_no_results", "complete"}:
        detail = "Relevant configured source packs were observed for this exact generation."
    else:
        detail = (
            "Relevant source-pack coverage was not fully observed. Treat this zero as unknown, "
            "not as a confirmed absence of relevant events."
        )
    status_text = ", ".join(sorted(statuses)) or "no per-pack status"
    return (
        '<div class="scope"><strong>Layer status:</strong> '
        + _h(headline)
        + " "
        + _h(detail)
        + f" <span class=\"muted\">Coverage: {_h(status_text)}.</span></div>"
    )


def render_market_observation_summary(snapshot: DashboardSnapshot) -> str:
    rows = snapshot.current_market_observations
    if not rows:
        return (
            '<p class="muted">No exact fingerprinted market-source rows were attached to this '
            "operator generation.</p>"
        )
    freshness_counts = _field_counts(rows, lambda row: row.get("freshness_status"))
    baseline_counts = _field_counts(rows, _observation_baseline_status)
    providers = sorted(
        {
            str(row.get("provider") or row.get("market_data_source") or row.get("source")).strip()
            for row in rows
            if str(row.get("provider") or row.get("market_data_source") or row.get("source") or "").strip()
        }
    )
    spread_confirmed = sum(1 for row in rows if _observation_spread_confirmed(row))
    market_decisions = sum(
        1
        for row in snapshot.current_candidates
        if row.get("_decision_model_status") == "v2"
        and "market_led" in _origin_tokens(row)
    )
    return _definition_list(
        (
            ("Exact market observations", len(rows)),
            ("Freshness", _count_label(freshness_counts)),
            ("Temporal baseline", _count_label(baseline_counts)),
            ("Execution spread confirmed", f"{spread_confirmed} / {len(rows)}"),
            ("Market-led Decision rows", market_decisions),
            ("Providers", ", ".join(providers) or "not recorded"),
        )
    )


def render_market_observation_table(rows: Iterable[Mapping[str, Any]]) -> str:
    ordered = sorted(
        tuple(rows),
        key=lambda row: (
            -abs(_normalized_return_percent(row, "return_24h") or 0.0),
            str(row.get("symbol") or row.get("coin_id") or ""),
        ),
    )
    body_rows = [
        (
            _h(row.get("symbol") or row.get("coin_id") or "unknown"),
            _h(row.get("observed_at") or row.get("timestamp") or "not recorded"),
            _h(_market_number(row.get("price"), money=True)),
            _h(_return_label(row, "return_1h")),
            _h(_return_label(row, "return_4h")),
            _h(_return_label(row, "return_24h")),
            _h(_market_number(row.get("volume_zscore_24h"))),
            _h(
                _market_number(
                    _first_present(row.get("liquidity_usd"), row.get("volume_24h")),
                    money=True,
                )
            ),
            _h(_observation_baseline_status(row)),
            _h(row.get("spread_status") or _observation_quality(row).get("spread_basis") or "unknown"),
            _h(row.get("freshness_status") or "unknown"),
            _h(row.get("provider") or row.get("market_data_source") or row.get("source") or "unknown"),
        )
        for row in ordered
    ]
    return _table(
        (
            "Asset", "Observed", "Price", "Return 1h", "Return 4h", "Return 24h",
            "Volume z", "Liquidity / volume proxy", "Baseline", "Spread", "Freshness", "Provider",
        ),
        body_rows,
        empty="No exact-generation market observation rows.",
    )


def render_market_anomaly_evidence_table(
    rows: Iterable[Mapping[str, Any]],
) -> str:
    """Render exact scanner outputs as evidence, never as Decision candidates."""

    ordered = sorted(
        tuple(rows),
        key=lambda row: str(row.get("symbol") or row.get("coin_id") or ""),
    )
    body_rows = []
    for row in ordered:
        market_state = row.get("market_state_snapshot")
        state = market_state if isinstance(market_state, Mapping) else {}
        evidence = row if row.get("return_24h") is not None else state
        body_rows.append(
            (
                _h(row.get("symbol") or row.get("coin_id") or "unknown"),
                _h(
                    row.get("anomaly_type")
                    or row.get("market_anomaly_type")
                    or row.get("market_state_class")
                    or state.get("market_state_class")
                    or "unclassified"
                ),
                _h(row.get("observed_at") or state.get("observed_at") or "not recorded"),
                _h(
                    _market_number(
                        _first_present(
                            row.get("anomaly_strength"), row.get("anomaly_score")
                        )
                    )
                ),
                _h(_return_label(evidence, "return_24h")),
                _h(row.get("freshness_status") or state.get("freshness_status") or "unknown"),
                _h(
                    row.get("provider")
                    or row.get("source_provider")
                    or state.get("provider")
                    or "unknown"
                ),
            )
        )
    return _table(
        ("Asset", "Observed anomaly", "Observed", "Strength", "24h return", "Freshness", "Provider"),
        body_rows,
        empty="No exact-generation anomaly scan evidence.",
    )


def source_coverage_rows(payload: Mapping[str, Any]) -> list[tuple[str, ...]]:
    raw = payload.get("packs") if isinstance(payload, Mapping) else None
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
        return []
    return [
        (
            _h(row.get("source_pack") or "unknown"),
            _h(
                row.get("provider_coverage_status")
                or row.get("source_pack_coverage_status")
                or "unknown"
            ),
            _h(row.get("accepted_evidence_count") or 0),
            _h(_joined_values(row.get("configured_providers"))),
            _h(_joined_values(row.get("healthy_providers"))),
            _h(_joined_values(row.get("missing_providers"))),
            _h(
                row.get("coverage_gap_reason")
                or row.get("source_coverage_gap_reason")
                or "none recorded"
            ),
        )
        for row in raw
        if isinstance(row, Mapping)
    ]


def _calendar_snapshot_layer_status(
    calendar_snapshot: Mapping[str, Any],
    visible_count: int,
) -> str:
    status = str(calendar_snapshot.get("status") or "unknown")
    status_token = _token(status)
    configured = calendar_snapshot.get("configured")
    error = calendar_snapshot.get("error_class") or calendar_snapshot.get("error")
    headline = (
        f"Observed: {visible_count} exact-generation calendar row(s)."
        if visible_count
        else "No exact-generation calendar rows are available."
    )
    normalization_rejected = _finite_number(
        calendar_snapshot.get("normalization_rejected_count")
    )
    if normalization_rejected is not None and normalization_rejected > 0:
        detail = (
            "Retained calendar rows failed unified-calendar normalization. This empty dashboard "
            "layer is a normalization failure, not evidence that no scheduled events exist."
        )
    elif configured is False or status_token in {
        "not_configured", "skipped_missing_config", "missing_config",
    }:
        detail = (
            "Calendar acquisition was not configured for this generation. This layer was "
            "unavailable, and zero rows is not evidence that no scheduled events exist."
        )
    elif status_token == "stale":
        detail = (
            "The configured calendar snapshot was stale and was not admitted into this "
            "generation. Zero rows is not evidence that no scheduled events exist."
        )
    elif status_token == "fixture_rejected_live":
        detail = (
            "Fixture, test, mock, or replay calendar provenance was rejected for this live "
            "generation. Zero rows is not evidence that no scheduled events exist."
        )
    elif status_token in {"unavailable", "degraded"} or error not in (None, ""):
        error_suffix = f" ({error})" if error not in (None, "") else ""
        detail = (
            f"Calendar acquisition failed or was unavailable{error_suffix}. This layer is "
            "unavailable, and "
            "zero rows is not evidence that no scheduled events exist."
        )
    elif status_token in {
        "complete", "observed", "usable", "observed_no_results", "healthy_empty", "healthy_nonempty",
    }:
        detail = "The calendar snapshot was observed for this exact generation."
    else:
        detail = (
            "Calendar acquisition was not fully observed. Treat this zero as unknown, not as "
            "a confirmed absence of scheduled events."
        )
    count_detail = _calendar_count_detail(calendar_snapshot)
    configured_label = (
        str(configured).lower() if isinstance(configured, bool) else str(configured or "unknown")
    )
    metadata = f"status={status}; configured={configured_label}"
    if error not in (None, ""):
        metadata += f"; error_class={error}"
    if count_detail:
        metadata += f"; {count_detail}"
    return (
        '<div class="scope"><strong>Layer status:</strong> '
        + _h(headline)
        + " "
        + _h(detail)
        + f" <span class=\"muted\">Calendar snapshot: {_h(metadata)}.</span></div>"
    )


def _calendar_count_detail(calendar_snapshot: Mapping[str, Any]) -> str:
    counts = calendar_snapshot.get("counts")
    if isinstance(counts, Mapping):
        return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    return ", ".join(
        f"{field}={calendar_snapshot.get(field)}"
        for field in (
            "scheduled_row_count", "unlock_row_count", "calendar_row_count", "event_count",
            "retained_row_count", "unified_calendar_count", "normalization_rejected_count",
            "normalization_status",
        )
        if calendar_snapshot.get(field) is not None
    )


def _coverage_pack_rows(
    snapshot: DashboardSnapshot,
    layer: str,
) -> tuple[Mapping[str, Any], ...]:
    raw = snapshot.source_coverage.get("packs")
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
        return ()
    rows = tuple(row for row in raw if isinstance(row, Mapping))
    wanted = _LAYER_SOURCE_PACKS.get(layer)
    if wanted is None:
        return rows
    return tuple(row for row in rows if _token(row.get("source_pack")) in wanted)


def _observation_quality(row: Mapping[str, Any]) -> Mapping[str, Any]:
    for field in ("market_data_quality", "data_quality"):
        value = row.get(field)
        if isinstance(value, Mapping):
            return value
    return {}


def _observation_baseline_status(row: Mapping[str, Any]) -> str:
    return str(
        row.get("temporal_baseline_status")
        or row.get("market_history_status")
        or _observation_quality(row).get("baseline_status")
        or "unknown"
    )


def _observation_spread_confirmed(row: Mapping[str, Any]) -> bool:
    status = _token(row.get("spread_status") or _observation_quality(row).get("spread_basis"))
    return bool(
        _observation_quality(row).get("spread_available") is True
        or status in {"verified", "available", "observed", "provider_observed", "good", "tight"}
    )


def _field_counts(
    rows: Iterable[Mapping[str, Any]],
    getter: Callable[[Mapping[str, Any]], object],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(getter(row) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _normalized_return_percent(row: Mapping[str, Any], field: str) -> float | None:
    value = _finite_number(row.get(field))
    if value is None:
        return None
    unit = _token(row.get(f"{field}_unit") or row.get("return_unit"))
    if unit == "fraction":
        return value * 100.0
    if unit in {"percent", "percentage", "percent_points", "percentage_points"}:
        return value
    return None


def _return_label(row: Mapping[str, Any], field: str) -> str:
    value = _normalized_return_percent(row, field)
    if value is not None:
        return f"{value:+.2f}%"
    raw = _finite_number(row.get(field))
    if raw is None:
        return "n/a"
    unit = str(row.get(f"{field}_unit") or row.get("return_unit") or "unit unknown")
    return f"{raw:+.4g} ({unit})"


def _market_number(value: object, *, money: bool = False) -> str:
    number = _finite_number(value)
    if number is None:
        return "n/a"
    if money:
        if abs(number) >= 1_000_000_000:
            return f"${number / 1_000_000_000:.2f}B"
        if abs(number) >= 1_000_000:
            return f"${number / 1_000_000:.2f}M"
        if abs(number) >= 1_000:
            return f"${number:,.0f}"
        return f"${number:,.4g}"
    return f"{number:.3f}"


def _origin_tokens(row: Mapping[str, Any]) -> set[str]:
    tokens = {_token(row.get("primary_thesis_origin") or row.get("thesis_origin"))}
    origins = row.get("thesis_origins")
    if isinstance(origins, Iterable) and not isinstance(origins, (str, bytes, Mapping)):
        tokens.update(_token(value) for value in origins)
    return {token for token in tokens if token}


def _joined_values(value: object) -> str:
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        values = [str(item) for item in value if str(item).strip()]
        return ", ".join(values) or "none"
    return str(value).strip() if value not in (None, "") else "none"


def _count_label(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def _definition_list(items: Iterable[tuple[str, object]]) -> str:
    return "<dl>" + "".join(f"<dt>{_h(key)}</dt><dd>{_h(value)}</dd>" for key, value in items) + "</dl>"


def _table(headers: Iterable[str], rows: Iterable[Iterable[str]], *, empty: str) -> str:
    materialized = [tuple(row) for row in rows]
    if not materialized:
        return f'<p class="muted">{_h(empty)}</p>'
    head = "".join(f"<th>{_h(value)}</th>" for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>"
        for row in materialized
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_present(*values: object) -> object | None:
    return next((value for value in values if value not in (None, "")), None)


def _token(value: object) -> str:
    return str(value or "").strip().casefold()


def _h(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


__all__ = (
    "render_layer_status",
    "render_market_anomaly_evidence_table",
    "render_market_observation_summary",
    "render_market_observation_table",
    "source_coverage_rows",
)
