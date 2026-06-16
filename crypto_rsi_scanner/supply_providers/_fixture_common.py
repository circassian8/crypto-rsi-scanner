"""Shared fixture parser for supply/on-chain enrichment providers."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..event_providers.manual_json import parse_datetime
from ..event_resolver import clean_text

log = logging.getLogger(__name__)


def fetch_supply_snapshots(
    path: str | Path | None,
    *,
    provider: str,
    required: bool = False,
) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    p = Path(path).expanduser()
    try:
        rows = _load_rows(p)
    except Exception as exc:  # noqa: BLE001
        if required:
            raise
        log.warning("%s supply fixture load failed: %s", provider, exc)
        return {}

    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        snapshot = _snapshot(row, provider)
        if snapshot is None:
            continue
        for key in _keys(row, snapshot):
            out[key] = snapshot
    return out


def _load_rows(path: Path) -> list[Mapping[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("snapshots", raw.get("data")) if isinstance(raw, Mapping) else raw
    if not isinstance(rows, list):
        raise ValueError("supply fixture must be a list or {'snapshots': [...]}")
    out: list[Mapping[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"supply row {idx} must be an object")
        out.append(row)
    return out


def _snapshot(row: Mapping[str, Any], provider: str) -> dict[str, Any] | None:
    symbol = str(row.get("symbol") or row.get("base_symbol") or row.get("base_asset") or "").upper()
    if not symbol and not row.get("coin_id"):
        return None
    timestamp = _parse_dt(row.get("timestamp") or row.get("time") or row.get("created_at"))
    return {
        "symbol": symbol,
        "timestamp": timestamp.isoformat() if timestamp else None,
        "large_holder_exchange_inflow": _bool_or_none(
            _first_present(row, "large_holder_exchange_inflow", "exchange_inflow")
        ),
        "cex_inflow_amount": _float_or_none(_first_present(row, "cex_inflow_amount", "exchange_inflow_amount")),
        "cex_inflow_pct_supply": _float_or_none(
            _first_present(row, "cex_inflow_pct_supply", "exchange_inflow_pct_supply", "cex_inflow_pct")
        ),
        "unlock_amount": _float_or_none(_first_present(row, "unlock_amount", "unlock_tokens")),
        "unlock_pct_circulating": _float_or_none(
            _first_present(row, "unlock_pct_circulating", "unlock_percent_circulating", "unlock_pct_supply")
        ),
        "top_holder_concentration": _float_or_none(
            _first_present(row, "top_holder_concentration", "holder_concentration")
        ),
        "team_or_mm_wallet_activity": _bool_or_none(
            _first_present(row, "team_or_mm_wallet_activity", "team_wallet_activity")
        ),
        "admin_or_mint_risk": _bool_or_none(_first_present(row, "admin_or_mint_risk", "mint_risk")),
        "notes": row.get("notes") or f"{provider} fixture",
    }


def _keys(row: Mapping[str, Any], snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    values = [
        row.get("coin_id"),
        row.get("base_asset"),
        row.get("base_symbol"),
        snapshot.get("symbol"),
        row.get("symbol"),
        row.get("contract_address"),
    ]
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        raw = str(value).strip()
        for key in (clean_text(raw), raw.upper()):
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return tuple(out)


def _parse_dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    return parse_datetime(value)


def _float_or_none(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        raw = value.strip().casefold()
        if raw in {"1", "true", "yes", "y"}:
            return True
        if raw in {"0", "false", "no", "n"}:
            return False
    return bool(value)


def _first_present(row: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        if key in row:
            return row[key]
    return None
