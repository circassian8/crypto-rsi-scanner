"""Validation sample outcome filling helpers."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote_plus, urlparse

from ..discovery import VALIDATION_SAMPLE_FIELDS, VALIDATION_SAMPLE_SCHEMA_VERSION
from .models import *  # noqa: F403 - split modules share legacy model names


def load_validation_sample(path: str | Path) -> list[dict[str, Any]]:
    """Load a validation sample export from JSONL or CSV."""
    sample_path = Path(path).expanduser()
    text = sample_path.read_text(encoding="utf-8")
    if sample_path.suffix.casefold() == ".csv":
        return [_parse_csv_row(row) for row in csv.DictReader(text.splitlines())]
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def load_outcome_price_fixture(path: str | Path) -> dict[str, list[ValidationOutcomeCandle]]:
    """Load local price candles for artifact-only validation outcome filling."""
    fixture_path = Path(path).expanduser()
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    if isinstance(raw, Mapping):
        if isinstance(raw.get("prices"), list):
            items = raw["prices"]
            return _price_index_from_flat_rows(
                items,
                interval=str(raw.get("interval") or ""),
                source=str(raw.get("source") or ""),
            )
        return _price_index_from_mapping(raw)
    if isinstance(raw, list):
        return _price_index_from_flat_rows(raw)
    raise ValueError("outcome price fixture must be a list, mapping, or {'prices': [...]}")


def fill_validation_outcomes(
    rows: Iterable[Mapping[str, Any]],
    price_index: Mapping[str, Iterable[ValidationOutcomeCandle]],
    *,
    overwrite: bool = False,
) -> ValidationOutcomeFillResult:
    """Fill triggered event-fade outcome fields from local price candles."""
    data = [dict(row) for row in rows]
    normalized_prices = {
        _asset_key(key): sorted(tuple(candles), key=lambda candle: candle.timestamp)
        for key, candles in price_index.items()
    }
    triggered = 0
    filled = 0
    missing_history = 0
    insufficient_history = 0
    skipped_existing = 0
    output: list[dict[str, Any]] = []
    for row in data:
        out = dict(row)
        if _signal_type(row) != "SHORT_TRIGGERED":
            output.append(out)
            continue
        triggered += 1
        if not overwrite and all(_num(row.get(field)) is not None for field in OUTCOME_FIELDS):
            skipped_existing += 1
            output.append(out)
            continue

        candles = _candles_for_row(row, normalized_prices)
        if not candles:
            missing_history += 1
            output.append(out)
            continue
        decision_time = _dt(row.get("trigger_observed_at")) or _review_event_time(row)
        if decision_time is None:
            insufficient_history += 1
            output.append(out)
            continue
        trigger_outcome = _short_outcome(
            candles,
            decision_time,
            entry_price=_num(row.get("entry_reference_price")),
        )
        if trigger_outcome is None:
            insufficient_history += 1
            output.append(out)
            continue
        changed = False
        for field in OUTCOME_FIELDS:
            if field.startswith("event_time_"):
                continue
            value = trigger_outcome.get(field)
            if value is None:
                continue
            if overwrite or _num(out.get(field)) is None:
                out[field] = value
                changed = True
        event_time = _review_event_time(row)
        if event_time is not None:
            event_time_outcome = _short_outcome(
                candles,
                event_time,
                entry_price=_close_asof(candles, event_time),
            )
            if event_time_outcome is not None:
                event_time_fields = _event_time_outcome_fields(event_time_outcome)
                for field, value in event_time_fields.items():
                    if value is None:
                        continue
                    if overwrite or _num(out.get(field)) is None:
                        out[field] = value
                        changed = True
        if changed:
            interval, source = _price_fixture_metadata(candles)
            if interval and (overwrite or not out.get("outcome_price_interval")):
                out["outcome_price_interval"] = interval
            if source and (overwrite or not out.get("outcome_price_source")):
                out["outcome_price_source"] = source
            filled += 1
        output.append(out)
    return ValidationOutcomeFillResult(
        rows=output,
        sample_rows=len(data),
        triggered_rows=triggered,
        filled_rows=filled,
        missing_history_rows=missing_history,
        insufficient_history_rows=insufficient_history,
        skipped_existing_rows=skipped_existing,
    )


def _price_index_from_mapping(raw: Mapping[str, Any]) -> dict[str, list[ValidationOutcomeCandle]]:
    out: dict[str, list[ValidationOutcomeCandle]] = {}
    for key, values in raw.items():
        if key == "prices":
            continue
        if not isinstance(values, list):
            continue
        candles = [_parse_price_candle(item) for item in values]
        parsed = [candle for candle in candles if candle is not None]
        if parsed:
            out[_asset_key(key)] = sorted(parsed, key=lambda candle: candle.timestamp)
    return out


def _price_index_from_flat_rows(
    items: Iterable[Any],
    *,
    interval: str = "",
    source: str = "",
) -> dict[str, list[ValidationOutcomeCandle]]:
    out: dict[str, list[ValidationOutcomeCandle]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        candle = _parse_price_candle(item, interval=interval, source=source)
        if candle is None:
            continue
        keys = _price_row_keys(item)
        for key in keys:
            out.setdefault(key, []).append(candle)
    return {
        key: sorted(candles, key=lambda candle: candle.timestamp)
        for key, candles in out.items()
    }


def _parse_price_candle(
    item: Mapping[str, Any],
    *,
    interval: str = "",
    source: str = "",
) -> ValidationOutcomeCandle | None:
    ts = _dt(item.get("timestamp") or item.get("time") or item.get("date"))
    close = _num(item.get("close") or item.get("price"))
    if ts is None or close is None or close <= 0:
        return None
    high = _num(item.get("high"))
    low = _num(item.get("low"))
    row_interval = str(item.get("interval") or interval or "")
    row_source = str(item.get("source") or source or "")
    return ValidationOutcomeCandle(
        timestamp=ts,
        close=close,
        high=high if high is not None and high > 0 else None,
        low=low if low is not None and low > 0 else None,
        interval=row_interval or None,
        source=row_source or None,
    )


def _price_row_keys(item: Mapping[str, Any]) -> tuple[str, ...]:
    keys = {
        _asset_key(item.get("asset_coin_id")),
        _asset_key(item.get("coin_id")),
        _asset_key(item.get("id")),
        _asset_key(item.get("asset_symbol")),
        _asset_key(item.get("symbol")),
    }
    return tuple(key for key in keys if key)


def _candles_for_row(
    row: Mapping[str, Any],
    price_index: Mapping[str, list[ValidationOutcomeCandle]],
) -> list[ValidationOutcomeCandle]:
    for key in (
        _asset_key(row.get("asset_coin_id")),
        _asset_key(row.get("asset_symbol")),
    ):
        if key and key in price_index:
            return price_index[key]
    return []


def _price_fixture_metadata(candles: list[ValidationOutcomeCandle]) -> tuple[str | None, str | None]:
    for candle in candles:
        if candle.interval or candle.source:
            return candle.interval, candle.source
    return None, None


def _short_outcome(
    candles: list[ValidationOutcomeCandle],
    decision_time: datetime,
    *,
    entry_price: float | None = None,
) -> dict[str, float] | None:
    entry = entry_price or _close_asof(candles, decision_time)
    if entry is None or entry <= 0:
        return None
    future = [
        candle for candle in candles
        if decision_time < candle.timestamp <= decision_time + timedelta(days=7)
    ]
    if not future:
        return None
    lows = [candle.low if candle.low is not None else candle.close for candle in future]
    highs = [candle.high if candle.high is not None else candle.close for candle in future]
    outcome: dict[str, float] = {
        "entry_price": entry,
        "max_favorable_excursion": max(0.0, (entry - min(lows)) / entry),
        "max_adverse_excursion": max(0.0, (max(highs) - entry) / entry),
    }
    for hours, field in (
        (24, "post_event_return_24h"),
        (72, "post_event_return_72h"),
        (168, "post_event_return_7d"),
    ):
        close = _close_asof_after(candles, decision_time, decision_time + timedelta(hours=hours))
        if close is not None:
            outcome[field] = close / entry - 1.0
    return outcome if all(field in outcome for field in REQUIRED_TRIGGER_OUTCOME_FIELDS) else None


def _event_time_outcome_fields(outcome: Mapping[str, float]) -> dict[str, float]:
    return {
        "event_time_entry_price": outcome.get("entry_price"),
        "event_time_max_adverse_excursion": outcome.get("max_adverse_excursion"),
        "event_time_max_favorable_excursion": outcome.get("max_favorable_excursion"),
        "event_time_post_event_return_24h": outcome.get("post_event_return_24h"),
        "event_time_post_event_return_72h": outcome.get("post_event_return_72h"),
        "event_time_post_event_return_7d": outcome.get("post_event_return_7d"),
    }


def _close_asof(
    candles: list[ValidationOutcomeCandle],
    ts: datetime,
) -> float | None:
    prior = [candle.close for candle in candles if candle.timestamp <= ts]
    return prior[-1] if prior else None


def _close_asof_after(
    candles: list[ValidationOutcomeCandle],
    start: datetime,
    ts: datetime,
) -> float | None:
    prior = [candle.close for candle in candles if start < candle.timestamp <= ts]
    return prior[-1] if prior else None


def _asset_key(value: object) -> str:
    return str(value or "").strip().casefold()
