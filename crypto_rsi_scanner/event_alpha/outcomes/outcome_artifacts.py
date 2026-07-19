"""Playbook-specific Event Alpha outcome metrics for research snapshots."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import median
from typing import Any, Iterable, Mapping


def compute_playbook_outcome_metrics(
    row: Mapping[str, Any],
    price_rows: Iterable[Mapping[str, Any]] = (),
    *,
    entry_price: float | None = None,
    observed_at: datetime | None = None,
    returns: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute playbook-specific research metrics from local OHLCV evidence."""
    returns = dict(returns or {})
    observed = observed_at or _dt(row.get("observed_at"))
    prices = sorted(
        (dict(item) for item in price_rows),
        key=lambda item: _dt(item.get("timestamp")) or datetime.max.replace(tzinfo=timezone.utc),
    )
    entry, entry_invalid = _numeric_alias_resolution(
        ({"entry_price": entry_price}, ("entry_price",)),
        (row, ("entry_reference_price", "market_price")),
        minimum=0.0,
        exclusive=True,
    )
    if entry is None and not entry_invalid and observed is not None:
        first = _first_after(prices, observed)
        entry = _positive_price(first, "close") if first else None

    metrics: dict[str, Any] = {
        "volatility_hit": None,
        "up_then_fade_hit": None,
        "mfe_mae_ratio": None,
        "underperformance_vs_btc": None,
        "underperformance_vs_alt_basket": None,
        "time_to_peak_hours": None,
        "time_to_trough_hours": None,
        "event_window_return": None,
        "catalyst_found_after_anomaly": _catalyst_found_after_anomaly(row),
    }
    if entry is None or entry <= 0 or observed is None:
        return metrics

    window = [
        item for item in prices
        if (ts := _dt(item.get("timestamp"))) is not None
        and observed <= ts <= observed + _horizon_delta_days(7)
    ]
    peak = _extreme(window, key="high", fallback="close", mode="max")
    trough = _extreme(window, key="low", fallback="close", mode="min")
    if peak is not None:
        metrics["time_to_peak_hours"] = _hours_between(observed, _dt(peak.get("timestamp")))
    if trough is not None:
        metrics["time_to_trough_hours"] = _hours_between(observed, _dt(trough.get("timestamp")))

    mfe = _numeric_alias_value(
        (returns, ("max_favorable_excursion",)),
        (row, ("max_favorable_excursion",)),
        minimum=0.0,
    )
    mae = _numeric_alias_value(
        (returns, ("max_adverse_excursion",)),
        (row, ("max_adverse_excursion",)),
        minimum=0.0,
    )
    if mfe is not None and mae is not None and mae > 0:
        metrics["mfe_mae_ratio"] = mfe / mae

    max_abs = max(abs(value) for value in (mfe, mae) if value is not None) if (mfe is not None or mae is not None) else None
    expected_direction = str(row.get("expected_direction") or "")
    success_metric = str(row.get("success_metric") or "")
    playbook = str(row.get("playbook_type") or "")
    metrics["volatility_hit"] = (
        bool(max_abs is not None and max_abs >= 0.08)
        if expected_direction == "volatility" or success_metric == "volatility" or "listing" in playbook
        else None
    )

    return_72h = _numeric_alias_value(
        (returns, ("return_72h",)), (row, ("return_72h",)),
    )
    return_7d = _numeric_alias_value(
        (returns, ("return_7d",)), (row, ("return_7d",)),
    )
    up_leg = _up_leg_from_prices(entry, window)
    if expected_direction == "up_then_fade" or success_metric == "mfe_mae":
        metrics["up_then_fade_hit"] = bool(up_leg is not None and up_leg > 0.05 and ((return_72h or 0) < 0 or (return_7d or 0) < 0))

    primary_return = _numeric_alias_value(
        (returns, ("primary_horizon_return",)),
        (row, ("primary_horizon_return",)),
    )
    btc_return = _numeric_alias_value(
        (row, (
            "btc_primary_horizon_return", "btc_return_primary", "benchmark_btc_return",
        )),
    )
    alt_return = _numeric_alias_value(
        (row, (
            "alt_basket_primary_horizon_return",
            "alt_basket_return_primary",
            "benchmark_alt_basket_return",
        )),
    )
    if primary_return is not None and btc_return is not None:
        metrics["underperformance_vs_btc"] = primary_return - btc_return
    if primary_return is not None and alt_return is not None:
        metrics["underperformance_vs_alt_basket"] = primary_return - alt_return

    event_time = _dt(row.get("event_time"))
    if event_time is not None and prices:
        start = _first_after(prices, event_time)
        end = _first_after(prices, observed)
        start_close = _positive_price(start, "close") if start else None
        end_close = _positive_price(end, "close") if end else None
        if start_close is not None and end_close is not None:
            metrics["event_window_return"] = (end_close - start_close) / start_close
    return metrics


def summarize_outcome_metrics(rows: Iterable[Mapping[str, Any]]) -> str:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("playbook_type") or "unknown"), []).append(row)
    parts: list[str] = []
    for playbook, items in sorted(grouped.items()):
        direction_values = [row.get("direction_hit") for row in items if row.get("direction_hit") is not None]
        volatility_values = [row.get("volatility_hit") for row in items if row.get("volatility_hit") is not None]
        ratios = [_num(row.get("mfe_mae_ratio")) for row in items]
        ratios = [value for value in ratios if value is not None]
        primary_returns = [_num(row.get("primary_horizon_return")) for row in items]
        primary_returns = [value for value in primary_returns if value is not None]
        bits = [f"{playbook}: n={len(items)}"]
        if direction_values:
            bits.append(f"dir_hit={sum(bool(v) for v in direction_values)}/{len(direction_values)}")
        if volatility_values:
            bits.append(f"vol_hit={sum(bool(v) for v in volatility_values)}/{len(volatility_values)}")
        if ratios:
            bits.append(f"med_mfe_mae={median(ratios):.2f}")
        if primary_returns:
            bits.append(f"med_primary={median(primary_returns) * 100:+.1f}%")
        useful = sum(1 for row in items if str(row.get("feedback_label") or "") == "useful")
        junk = sum(1 for row in items if str(row.get("feedback_label") or "") == "junk")
        if useful or junk:
            bits.append(f"feedback useful={useful} junk={junk}")
        parts.append(" ".join(bits))
    return "Outcome metrics by playbook: " + "; ".join(parts) if parts else ""


def _catalyst_found_after_anomaly(row: Mapping[str, Any]) -> bool | None:
    if row.get("catalyst_found_after_anomaly") is not None:
        return bool(row.get("catalyst_found_after_anomaly"))
    source = str(row.get("source") or "")
    event_type = str(row.get("event_type") or "")
    if "market_anomaly" in source and event_type != "market_anomaly":
        return True
    if event_type == "market_anomaly":
        return False
    return None


def _up_leg_from_prices(entry: float, rows: Iterable[Mapping[str, Any]]) -> float | None:
    values = [_positive_price(row, "high", "close") for row in rows]
    values = [value for value in values if value is not None]
    return None if not values else (max(values) - entry) / entry


def _extreme(rows: Iterable[Mapping[str, Any]], *, key: str, fallback: str, mode: str) -> Mapping[str, Any] | None:
    valid = []
    for row in rows:
        value = _positive_price(row, key, fallback)
        if value is not None:
            valid.append((value, row))
    if not valid:
        return None
    return (max if mode == "max" else min)(valid, key=lambda item: item[0])[1]


def _first_after(rows: Iterable[Mapping[str, Any]], ts: datetime) -> Mapping[str, Any] | None:
    for row in rows:
        row_ts = _dt(row.get("timestamp"))
        if row_ts is not None and row_ts >= ts:
            return row
    return None


def _hours_between(start: datetime, end: datetime | None) -> float | None:
    if end is None:
        return None
    return round((end - start).total_seconds() / 3600.0, 4)


def _horizon_delta_days(days: int):
    from datetime import timedelta

    return timedelta(days=days)


def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _num(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _numeric_alias_value(
    *sources: tuple[Mapping[str, Any], tuple[str, ...]],
    minimum: float | None = None,
    exclusive: bool = False,
) -> float | None:
    """Resolve the first supplied numeric field without truthiness fallback."""

    return _numeric_alias_resolution(
        *sources,
        minimum=minimum,
        exclusive=exclusive,
    )[0]


def _numeric_alias_resolution(
    *sources: tuple[Mapping[str, Any], tuple[str, ...]],
    minimum: float | None = None,
    exclusive: bool = False,
) -> tuple[float | None, bool]:
    """Return the ordered numeric value and whether supplied evidence was invalid."""

    for source, keys in sources:
        for key in keys:
            if key not in source:
                continue
            raw = source.get(key)
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                continue
            value = _num(raw)
            if value is None:
                return None, True
            if minimum is not None and (
                value < minimum or (exclusive and value == minimum)
            ):
                return None, True
            return value, False
    return None, False


def _positive_price(row: Mapping[str, Any], *keys: str) -> float | None:
    return _numeric_alias_value(
        (row, tuple(keys)),
        minimum=0.0,
        exclusive=True,
    )
