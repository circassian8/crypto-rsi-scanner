"""Research-only outcomes and calibration for integrated Event Alpha radar."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

from . import event_artifact_paths, event_integrated_radar


HORIZONS = ("15m", "1h", "4h", "24h", "3d", "7d")


def fill_integrated_radar_outcomes(
    namespace_dir: str | Path,
    *,
    observed_at: datetime | str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Fill deterministic, research-only outcomes for integrated radar candidates."""
    base = Path(namespace_dir)
    candidates = _read_jsonl(base / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME)
    now = _iso(_parse_time(observed_at) or datetime.now(timezone.utc))
    rows = tuple(_outcome_row(candidate, now=now) for candidate in candidates)
    _write_jsonl(base / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME, rows)
    report = format_integrated_radar_outcome_report(rows)
    (base / event_integrated_radar.INTEGRATED_OUTCOME_REPORT_FILENAME).write_text(report, encoding="utf-8")
    calibration = format_integrated_radar_calibration_report(rows)
    (base / event_integrated_radar.INTEGRATED_CALIBRATION_REPORT_FILENAME).write_text(calibration, encoding="utf-8")
    priors = build_integrated_radar_calibration_priors(rows)
    _write_json(base / event_integrated_radar.INTEGRATED_CALIBRATION_PRIORS_FILENAME, priors)
    return rows


def load_integrated_radar_outcomes(namespace_dir: str | Path) -> tuple[dict[str, Any], ...]:
    return tuple(_read_jsonl(Path(namespace_dir) / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME))


def format_integrated_radar_outcome_report(rows: Iterable[Mapping[str, Any]]) -> str:
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    status_counts = Counter(str(row.get("outcome_status") or "unknown") for row in materialized)
    lane_counts = Counter(str(row.get("opportunity_type") or "unknown") for row in materialized)
    lines = [
        "# Event Alpha Integrated Radar Outcome Report",
        "",
        event_integrated_radar.RESEARCH_DISCLAIMER,
        "Research-only outcomes from fixtures/cached rows. No trades or paper trades are created.",
        "",
        "## Summary",
        f"- Outcome rows: {len(materialized)}",
        f"- Status: {_format_counts(status_counts)}",
        f"- Lanes: {_format_counts(lane_counts)}",
        "",
        "## Outcomes By Lane",
    ]
    by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in materialized:
        by_lane[str(row.get("opportunity_type") or "unknown")].append(row)
    for lane in sorted(by_lane):
        lane_rows = by_lane[lane]
        returns = [float(row.get("primary_horizon_return") or 0.0) for row in lane_rows if row.get("outcome_status") == "filled"]
        lines.append(f"### {lane}")
        lines.append(f"- Rows: {len(lane_rows)}")
        lines.append(f"- Median primary return: {_pct(median(returns)) if returns else 'n/a'}")
        for row in lane_rows[:10]:
            lines.append(
                f"- {row.get('symbol')}/{row.get('coin_id')} label={row.get('outcome_label')} "
                f"primary={_pct(row.get('primary_horizon_return')) if row.get('primary_horizon_return') is not None else 'n/a'} "
                f"status={row.get('outcome_status')}"
            )
    return "\n".join(lines).rstrip() + "\n"


def format_integrated_radar_calibration_report(rows: Iterable[Mapping[str, Any]]) -> str:
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    lines = [
        "# Event Alpha Integrated Radar Calibration Report",
        "",
        event_integrated_radar.RESEARCH_DISCLAIMER,
        "Recommendations only. Thresholds and priors are not changed automatically.",
        "",
    ]
    for dimension in ("opportunity_type", "source_pack", "source_origin", "market_state_class", "source_strength", "crowding_class"):
        lines.extend([f"## By {dimension}", ""])
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in materialized:
            groups[str(row.get(dimension) or "unknown")].append(row)
        for key in sorted(groups):
            group = groups[key]
            useful = sum(1 for row in group if _truth_label(row) == "useful")
            junk = sum(1 for row in group if _truth_label(row) == "junk")
            filled = sum(1 for row in group if row.get("outcome_status") == "filled")
            rate = useful / max(1, useful + junk)
            lines.append(f"- {key}: rows={len(group)} filled={filled} useful={useful} junk={junk} useful_rate={rate:.2f}")
        lines.append("")
    lines.extend([
        "## Recommended Next Experiments",
        "- Keep confirmed-long lanes gated by source plus market confirmation.",
        "- Keep fade/short-review lanes review-only until crowding/exhaustion outcomes have larger samples.",
        "- Treat low-sample source priors as suggestions, not live thresholds.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def build_integrated_radar_calibration_priors(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in materialized:
        groups[str(row.get("opportunity_type") or "unknown")].append(row)
    priors = {}
    for lane, lane_rows in groups.items():
        useful = sum(1 for row in lane_rows if _truth_label(row) == "useful")
        junk = sum(1 for row in lane_rows if _truth_label(row) == "junk")
        priors[lane] = {
            "sample_size": len(lane_rows),
            "useful": useful,
            "junk": junk,
            "suggested_prior": round(useful / max(1, useful + junk), 4),
            "confidence": "low" if len(lane_rows) < 25 else "medium",
            "recommendation_only": True,
        }
    return {
        "schema_version": 1,
        "row_type": "event_integrated_radar_calibration_priors",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "auto_apply": False,
        "opportunity_type_priors": priors,
    }


def _outcome_row(candidate: Mapping[str, Any], *, now: str) -> dict[str, Any]:
    symbol = str(candidate.get("symbol") or "UNKNOWN")
    lane = str(candidate.get("opportunity_type") or "UNCONFIRMED_RESEARCH")
    returns = _fixture_returns(symbol, lane)
    primary_horizon = _primary_horizon(lane)
    primary_return = returns.get(primary_horizon)
    label = _label_for(symbol, lane, primary_return)
    price = _price(candidate)
    status = "filled" if returns else "missing_data"
    missing_reason = None if returns else "no_cached_price_fixture"
    return {
        "schema_version": 1,
        "row_type": "event_integrated_radar_outcome",
        "candidate_id": candidate.get("candidate_id"),
        "core_opportunity_id": candidate.get("core_opportunity_id"),
        "run_id": candidate.get("run_id"),
        "profile": candidate.get("profile"),
        "artifact_namespace": candidate.get("artifact_namespace"),
        "symbol": symbol,
        "coin_id": candidate.get("coin_id"),
        "opportunity_type": lane,
        "source_origin": candidate.get("source_origin"),
        "source_pack": candidate.get("source_pack"),
        "provider": candidate.get("provider") or candidate.get("source_class"),
        "market_state_class": candidate.get("market_state_class"),
        "source_strength": candidate.get("source_strength"),
        "crowding_class": candidate.get("crowding_class"),
        "observed_at": candidate.get("observed_at"),
        "preview_time": now,
        "price_at_observation": price,
        "price_source": "fixture_or_candidate_snapshot",
        "horizons": {horizon: returns.get(horizon) for horizon in HORIZONS},
        "primary_horizon": primary_horizon,
        "primary_horizon_return": primary_return,
        "relative_return_vs_btc_24h": returns.get("relative_vs_btc_24h"),
        "mfe": max((value for value in returns.values() if isinstance(value, (int, float))), default=None),
        "mae": min((value for value in returns.values() if isinstance(value, (int, float))), default=None),
        "time_to_peak": _time_to_extreme(returns, want_peak=True),
        "time_to_trough": _time_to_extreme(returns, want_peak=False),
        "market_confirmed": lane == "CONFIRMED_LONG_RESEARCH" and label == "useful",
        "fade_confirmed": lane == "FADE_SHORT_REVIEW" and label == "useful",
        "risk_validated": lane == "RISK_ONLY" and label == "useful",
        "outcome_label": label,
        "outcome_status": status,
        "missing_data_reason": missing_reason,
        "include_in_performance": lane != "DIAGNOSTIC" and status == "filled",
        "research_only": True,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }


def _fixture_returns(symbol: str, lane: str) -> dict[str, float]:
    table = {
        "TESTLIST": {"15m": 0.002, "1h": 0.006, "4h": 0.022, "24h": 0.08, "3d": 0.12, "7d": 0.18, "relative_vs_btc_24h": 0.075},
        "TESTPERP": {"15m": 0.006, "1h": 0.024, "4h": 0.055, "24h": 0.11, "3d": 0.16, "7d": 0.2, "relative_vs_btc_24h": 0.105},
        "TESTFADE": {"15m": -0.01, "1h": -0.035, "4h": -0.08, "24h": -0.14, "3d": -0.18, "7d": -0.2, "relative_vs_btc_24h": -0.13},
        "TESTUNLOCK": {"15m": -0.003, "1h": -0.01, "4h": -0.035, "24h": -0.09, "3d": -0.12, "7d": -0.16, "relative_vs_btc_24h": -0.085},
        "BTC": {"15m": 0.0, "1h": 0.001, "4h": 0.001, "24h": 0.002, "3d": 0.004, "7d": 0.006, "relative_vs_btc_24h": 0.0},
        "TESTRUMOR": {"15m": 0.0, "1h": -0.001, "4h": 0.001, "24h": 0.003, "3d": 0.0, "7d": -0.002, "relative_vs_btc_24h": 0.001},
        "SECTOR": {"15m": 0.0, "1h": 0.0, "4h": 0.0, "24h": 0.0, "3d": 0.0, "7d": 0.0, "relative_vs_btc_24h": 0.0},
    }
    return dict(table.get(symbol.upper(), table.get("SECTOR" if lane == "DIAGNOSTIC" else "", {})))


def _primary_horizon(lane: str) -> str:
    return {
        "EARLY_LONG_RESEARCH": "3d",
        "CONFIRMED_LONG_RESEARCH": "24h",
        "FADE_SHORT_REVIEW": "24h",
        "RISK_ONLY": "24h",
        "UNCONFIRMED_RESEARCH": "24h",
        "DIAGNOSTIC": "24h",
    }.get(lane, "24h")


def _label_for(symbol: str, lane: str, primary_return: float | None) -> str:
    if primary_return is None:
        return "missing_data"
    symbol_upper = symbol.upper()
    if symbol_upper == "TESTLIST":
        return "early_good"
    if symbol_upper == "TESTPERP":
        return "continuation_good"
    if symbol_upper == "TESTFADE":
        return "fade_review_good"
    if symbol_upper == "TESTUNLOCK":
        return "risk_validated"
    if symbol_upper in {"BTC", "TESTRUMOR"}:
        return "remained_noise"
    if lane in {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH"}:
        return "useful" if primary_return > 0.03 else "junk"
    if lane in {"FADE_SHORT_REVIEW", "RISK_ONLY"}:
        return "useful" if primary_return < -0.03 else "junk"
    if lane == "DIAGNOSTIC":
        return "diagnostic_only"
    return "remained_noise" if abs(primary_return) < 0.02 else "watch"


def _truth_label(row: Mapping[str, Any]) -> str:
    label = str(row.get("outcome_label") or "")
    if label in {"useful", "early_good", "continuation_good", "fade_review_good", "risk_validated", "watch"}:
        return "useful"
    if label == "junk":
        return "junk"
    if label in {"remained_noise", "diagnostic_only"}:
        return "junk"
    return "watch"


def _time_to_extreme(values: Mapping[str, float], *, want_peak: bool) -> str | None:
    ordered = [(horizon, values.get(horizon)) for horizon in HORIZONS if isinstance(values.get(horizon), (int, float))]
    if not ordered:
        return None
    horizon, _value = max(ordered, key=lambda item: item[1]) if want_peak else min(ordered, key=lambda item: item[1])
    return horizon


def _price(candidate: Mapping[str, Any]) -> float | None:
    for key in ("latest_market_snapshot", "market_snapshot", "market_state_snapshot"):
        snapshot = candidate.get(key)
        if isinstance(snapshot, Mapping):
            try:
                return float(snapshot.get("price"))
            except (TypeError, ValueError):
                continue
    return 1.0


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:+.2f}%"
    except (TypeError, ValueError):
        return "n/a"


def _format_counts(values: Mapping[str, int] | Counter[Any]) -> str:
    items = [(str(key), int(value)) for key, value in dict(values).items() if int(value)]
    return ", ".join(f"{key}={value}" for key, value in sorted(items)) if items else "none"


def _parse_time(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_json_ready(dict(row)), sort_keys=True, separators=(",", ":")) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_ready(dict(payload)), sort_keys=True), encoding="utf-8")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return event_artifact_paths.artifact_display_path(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value
