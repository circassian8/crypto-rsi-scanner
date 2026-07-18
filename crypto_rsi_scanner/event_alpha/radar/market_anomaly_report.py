"""Pure Markdown rendering for one bounded market-anomaly scan."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from typing import Any, Mapping


def format_market_anomaly_report(
    anomalies: Iterable[Mapping[str, Any]],
    *,
    snapshots: Iterable[Mapping[str, Any]] | None = None,
    catalyst_search_queue: Iterable[Mapping[str, Any]] | None = None,
    snapshot_count: int = 0,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    cfg: Any,
    limit: int = 20,
) -> str:
    rows = [dict(row) for row in anomalies if isinstance(row, Mapping)]
    snapshot_rows = [dict(row) for row in snapshots or () if isinstance(row, Mapping)]
    if snapshot_rows:
        snapshot_count = len(snapshot_rows)
    queue_rows = [dict(row) for row in catalyst_search_queue or () if isinstance(row, Mapping)]
    counts: dict[str, int] = {}
    bucket_counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("market_state_class") or row.get("anomaly_type") or "unknown")
        counts[key] = counts.get(key, 0) + 1
        bucket = str(row.get("anomaly_bucket") or row.get("market_anomaly_bucket") or "unknown")
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
    lines = [
        "# Event Alpha Market Anomaly Report",
        "",
        "Research-only. Not a trade signal, paper trade, live RSI signal, or execution.",
        f"Profile: {profile or 'unknown'}",
        f"Artifact namespace: {artifact_namespace or 'unknown'}",
        f"Market state snapshots: {snapshot_count}",
        f"Anomalies: {len(rows)}",
        f"Catalyst enrichment queue: {len(queue_rows)}",
        "Counts: " + (", ".join(f"{key}={value}" for key, value in sorted(counts.items())) if counts else "none"),
        "Buckets: " + (", ".join(f"{key}={value}" for key, value in sorted(bucket_counts.items())) if bucket_counts else "none"),
        "",
        "## Scan Coverage and Gate Inputs",
        *_scan_coverage_lines(snapshot_rows, anomaly_count=len(rows)),
        "",
        "## Current Classification Contract",
        *_classification_contract_lines(cfg),
        "",
        "## Strongest Observed Movements (Diagnostic Only)",
        *_diagnostic_movement_lines(snapshot_rows, limit=min(5, max(0, limit))),
        "",
        "## Top Market Anomalies for Catalyst Enrichment",
    ]
    if not rows:
        lines.append(
            "- None. No row satisfied a configured anomaly rule. This is a healthy-empty "
            "classification result, not evidence that market collection was empty."
        )
    for row in rows[: max(0, limit)]:
        snapshot = row.get("market_state_snapshot") if isinstance(row.get("market_state_snapshot"), Mapping) else {}
        market_state_class = row.get("market_state_class") or row.get("anomaly_type") or "unknown"
        lines.append(
            f"- {row.get('symbol') or row.get('coin_id') or 'UNKNOWN'}: "
            f"{market_state_class} "
            f"bucket={row.get('anomaly_bucket') or row.get('market_anomaly_bucket') or 'unknown'} "
            f"return_4h={_format_pct(snapshot.get('return_4h'))} "
            f"return_24h={_format_pct(snapshot.get('return_24h'))} "
            f"volume_z={_format_number(snapshot.get('volume_zscore_24h'))} "
            f"priority={_format_number(row.get('priority'))} "
            f"catalyst_search_role={row.get('catalyst_search_role') or 'confidence_enrichment'} "
            f"catalyst_required={str(bool(row.get('decision_model_v2_catalyst_required'))).lower()}"
        )
        confirms = row.get("what_confirms") if isinstance(row.get("what_confirms"), list) else []
        invalidates = row.get("what_invalidates") if isinstance(row.get("what_invalidates"), list) else []
        if confirms:
            lines.append("  - What confirms: " + "; ".join(str(item) for item in confirms[:3]))
        if invalidates:
            lines.append("  - What invalidates: " + "; ".join(str(item) for item in invalidates[:3]))
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more in local artifacts.")
    if queue_rows:
        lines.extend(["", "## Catalyst Enrichment Queue"])
        for row in queue_rows[: max(0, limit)]:
            queries = _string_list(row.get("search_queries"))
            packs = _string_list(row.get("suggested_source_packs"))
            lines.append(
                f"- {row.get('symbol') or row.get('coin_id') or 'UNKNOWN'}: "
                f"priority={_format_number(row.get('priority'))} "
                f"deadline={row.get('search_deadline') or 'unknown'} "
                f"packs={', '.join(packs[:3]) if packs else 'missing'}"
            )
            if queries:
                lines.append("  - Queries: " + "; ".join(queries[:3]))
    return "\n".join(lines) + "\n"


def _scan_coverage_lines(
    snapshots: Iterable[Mapping[str, Any]],
    *,
    anomaly_count: int,
) -> list[str]:
    rows = [dict(row) for row in snapshots if isinstance(row, Mapping)]
    if not rows:
        return [
            "- Snapshot details unavailable to this renderer; counts alone cannot prove input coverage."
        ]
    excluded = sum(1 for row in rows if _is_sector_or_theme(row))
    evaluated = max(0, len(rows) - excluded)
    no_reaction = max(0, evaluated - anomaly_count)
    freshness = Counter(str(row.get("freshness_status") or "unknown") for row in rows)
    baseline = Counter(_snapshot_baseline_status(row) for row in rows)
    feature_fields = (
        "return_4h",
        "return_24h",
        "relative_return_vs_btc_4h",
        "volume_zscore_24h",
        "liquidity_usd",
        "spread_bps",
    )
    feature_counts = {
        field: sum(_float(row.get(field)) is not None for row in rows)
        for field in feature_fields
    }
    derivatives_count = sum(
        any(
            _float(row.get(field)) is not None
            for field in (
                "funding_level",
                "funding_zscore",
                "open_interest_delta",
                "liquidation_imbalance",
            )
        )
        for row in rows
    )
    unit_warning_rows = sum(bool(_string_list(row.get("unit_warnings"))) for row in rows)
    unit_warnings = Counter(
        warning
        for row in rows
        for warning in _string_list(row.get("unit_warnings"))
    )
    return [
        f"- Classifier coverage: evaluated={evaluated}, diagnostic_or_sector_excluded={excluded}, "
        f"classified_anomaly={anomaly_count}, no_configured_reaction={no_reaction}.",
        "- Freshness: " + _counter_summary(freshness) + ".",
        "- Temporal baseline: " + _counter_summary(baseline) + ".",
        f"- Unit validation: warning_rows={unit_warning_rows}/{len(rows)}, warnings="
        + _counter_summary(unit_warnings)
        + ".",
        "- Input availability: "
        + ", ".join(
            f"{field}={feature_counts[field]}/{len(rows)}" for field in feature_fields
        )
        + f", derivatives_crowding_any={derivatives_count}/{len(rows)}.",
        "- Missing inputs remain unavailable and are handled conservatively; they are not "
        "reported as observed zero. Spread absence never becomes a verified-spread claim.",
    ]


def _classification_contract_lines(cfg: Any) -> list[str]:
    return [
        "- Return thresholds use percentage points; volume and funding thresholds use their "
        "declared native normalized fields.",
        f"- Confirmed breakout: return_4h>={cfg.confirmed_return_4h:.1f} or "
        f"return_24h>={cfg.confirmed_return_24h:.1f}, plus volume_zscore_24h>="
        f"{cfg.confirmed_volume_zscore:.1f} and relative_return_vs_btc_4h>="
        f"{cfg.confirmed_relative_btc_4h:.1f}.",
        f"- Stealth accumulation: return_4h in [{cfg.stealth_return_4h_min:.1f}, "
        f"{cfg.stealth_return_4h_max:.1f}), relative BTC 4h>="
        f"{cfg.stealth_relative_btc_4h:.1f}, and volume z-score in "
        f"[{cfg.stealth_volume_zscore_min:.1f}, {cfg.stealth_volume_zscore_max:.1f}].",
        f"- Late momentum / selloff / suspicious move: return_24h>="
        f"{cfg.late_momentum_return_24h:.1f}, <= {cfg.risk_off_return_24h:.1f}, or >= "
        f"{cfg.suspicious_return_24h:.1f} with liquidity below "
        f"${cfg.suspicious_liquidity_usd:,.0f} or spread >= "
        f"{cfg.suspicious_spread_bps:.1f} bps.",
        "- These are the current configured research rules. This report does not "
        "recommend threshold or score changes.",
    ]


def _diagnostic_movement_lines(
    snapshots: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    rows = [
        dict(row)
        for row in snapshots
        if isinstance(row, Mapping)
        and (
            _float(row.get("return_4h")) is not None
            or _float(row.get("return_24h")) is not None
        )
    ]
    ranked = sorted(
        rows,
        key=lambda row: max(
            abs(_float(row.get("return_4h")) or 0.0),
            abs(_float(row.get("return_24h")) or 0.0),
        ),
        reverse=True,
    )
    if not ranked or limit <= 0:
        return ["- None available."]
    lines = [
        "- Descriptive ranking by max absolute observed 4h/24h return; it is not an anomaly "
        "score, threshold distance, route, or tuning queue."
    ]
    for row in ranked[:limit]:
        lines.append(
            f"- {row.get('symbol') or row.get('coin_id') or 'UNKNOWN'}: "
            f"return_4h={_format_pct(row.get('return_4h'))}, "
            f"return_24h={_format_pct(row.get('return_24h'))}, "
            f"relative_btc_4h={_format_pct(row.get('relative_return_vs_btc_4h'))}, "
            f"volume_z={_format_number(row.get('volume_zscore_24h'))}, "
            f"freshness={row.get('freshness_status') or 'unknown'}, "
            f"baseline={_snapshot_baseline_status(row)}."
        )
    return lines


def _snapshot_baseline_status(row: Mapping[str, Any]) -> str:
    quality = row.get("market_data_quality")
    if isinstance(quality, Mapping) and quality.get("baseline_status"):
        return str(quality["baseline_status"])
    return str(row.get("market_history_status") or row.get("temporal_baseline_status") or "unknown")


def _counter_summary(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def _is_sector_or_theme(snapshot: Mapping[str, Any]) -> bool:
    symbol = str(snapshot.get("symbol") or "").upper()
    coin_id = str(snapshot.get("coin_id") or "").casefold()
    if (
        bool(snapshot.get("is_theme_or_sector"))
        or bool(snapshot.get("quote_asset_excluded"))
        or bool(snapshot.get("is_quote_asset"))
    ):
        return True
    if snapshot.get("is_tradable_asset") is False:
        return True
    return symbol == "SECTOR" or coin_id.startswith("sector:") or coin_id.endswith("_proxy")


def _string_list(value: object) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return [str(item) for item in value if str(item or "")]
    return [str(value)]


def _format_pct(value: object) -> str:
    parsed = _float(value)
    return "n/a" if parsed is None else f"{parsed:+.1f}%"


def _format_number(value: object) -> str:
    parsed = _float(value)
    return "n/a" if parsed is None else f"{parsed:.1f}"


def _float(value: object) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None
