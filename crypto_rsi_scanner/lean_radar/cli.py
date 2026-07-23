"""Small operator CLI for Lean Crypto Radar foundation commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Mapping, Sequence

from .bybit_universe import BybitUniverseError, load_catalog
from .config import LeanRadarConfigError, load_settings
from .store import LeanRadarStore, LeanRadarStoreError
from .universe import LeanUniverseError, build_universe, load_market_rows


_CANONICAL_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,159}$")
_SYMBOL = re.compile(r"^[A-Z0-9]{2,24}$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lean Crypto Radar operator tools")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("readiness")
    subparsers.add_parser("bybit-readiness")

    importer = subparsers.add_parser("bybit-import")
    importer.add_argument("--catalog", type=Path, required=True)
    importer.add_argument("--confirm", action="store_true")

    universe = subparsers.add_parser("universe")
    universe.add_argument("--markets", type=Path)

    watchlist = subparsers.add_parser("watchlist-add")
    watchlist.add_argument("--canonical-asset-id", required=True)
    watchlist.add_argument("--symbol", required=True)
    watchlist.add_argument("--note", default="")
    watchlist.add_argument("--confirm", action="store_true")
    return parser


def run(argv: Sequence[str] | None = None) -> tuple[int, dict[str, object]]:
    args = _parser().parse_args(argv)
    settings = load_settings()
    store = LeanRadarStore(args.db or settings.db_path)
    if args.command in {"readiness", "bybit-readiness"}:
        catalog = store.catalog_status()
        ready = catalog["status"] == "ready"
        payload = {
            "status": "ready" if ready else "setup_required",
            "product": "Lean Crypto Radar V1",
            "default_operator_path": True,
            "venue": "bybit",
            "instrument_type": "usdt_perpetual",
            "top_liquid_limit": settings.top_liquid_limit,
            "cadence_minutes": settings.cadence_minutes,
            "bybit_catalog": catalog,
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
            "research_only": True,
            "next_safe_command": (
                "make lean-radar-universe"
                if ready
                else "CONFIRM=1 make lean-radar-bybit-universe-import "
                "LEAN_RADAR_BYBIT_CATALOG=/absolute/path/to/instruments-info.json"
            ),
        }
        return 0, payload
    if args.command == "bybit-import":
        if not args.confirm:
            return 2, {
                "status": "confirmation_required",
                "provider_call_attempted": False,
                "research_only": True,
            }
        instruments = load_catalog(args.catalog, source_mode="imported_catalog")
        store.replace_bybit_catalog(instruments)
        return 0, {
            "status": "imported",
            "instrument_count": len(instruments),
            "source_mode": "imported_catalog",
            "source_observed_at": instruments[0].source_observed_at,
            "provider_call_attempted": False,
            "research_only": True,
            "next_safe_command": "make lean-radar-universe",
        }
    if args.command == "watchlist-add":
        if not args.confirm:
            return 2, {"status": "confirmation_required", "research_only": True}
        canonical_id = args.canonical_asset_id.strip().casefold()
        symbol = args.symbol.strip().upper()
        if not _CANONICAL_ID.fullmatch(canonical_id) or not _SYMBOL.fullmatch(symbol):
            raise LeanUniverseError("watchlist identity is invalid")
        store.upsert_watchlist(
            canonical_asset_id=canonical_id,
            symbol=symbol,
            note=args.note.strip()[:500],
        )
        instrument_bases = {row.base_coin for row in store.list_bybit_instruments()}
        return 0, {
            "status": "active_pending_market_data" if symbol in instrument_bases else "blocked_unverified",
            "canonical_asset_id": canonical_id,
            "symbol": symbol,
            "bybit_usdt_perpetual_confirmed": symbol in instrument_bases,
            "provider_call_attempted": False,
            "research_only": True,
        }
    if args.command == "universe":
        rows = load_market_rows(args.markets) if args.markets else ()
        result = build_universe(
            rows,
            store.list_bybit_instruments(),
            store.list_watchlist(),
        )
        return 0, {
            **result.to_dict(),
            "provider_call_attempted": False,
            "next_safe_command": "make lean-radar-readiness",
            "next_product_step": (
                "lean-radar-scan is the next implementation slice"
                if result.status == "ready"
                else "complete the reported readiness prerequisite"
            ),
        }
    raise AssertionError("unreachable command")


def render_summary(payload: Mapping[str, object]) -> str:
    status = payload.get("status", "unknown")
    lines = ["Lean Crypto Radar", f"Status: {status}"]
    if "instrument_count" in payload:
        lines.append(f"Confirmed Bybit USDT perpetuals: {payload['instrument_count']}")
    catalog = payload.get("bybit_catalog")
    if isinstance(catalog, Mapping):
        lines.append(
            "Bybit catalog: "
            f"{catalog.get('status', 'unknown')} ({catalog.get('instrument_count', 0)} instruments)"
        )
    if "active_asset_count" in payload:
        lines.append(
            f"Active assets: {payload.get('active_asset_count', 0)} · "
            f"blocked/unverified: {payload.get('blocked_asset_count', 0)}"
        )
    if payload.get("next_safe_command"):
        lines.append(f"Next: {payload['next_safe_command']}")
    lines.append("Research only · no send · no trading")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    forwarded: list[str] = []
    if args.db:
        forwarded.extend(("--db", str(args.db)))
    if args.json:
        forwarded.append("--json")
    forwarded.append(args.command)
    if args.command == "bybit-import":
        forwarded.extend(("--catalog", str(args.catalog)))
        if args.confirm:
            forwarded.append("--confirm")
    elif args.command == "universe" and args.markets:
        forwarded.extend(("--markets", str(args.markets)))
    elif args.command == "watchlist-add":
        forwarded.extend(("--canonical-asset-id", args.canonical_asset_id))
        forwarded.extend(("--symbol", args.symbol))
        forwarded.extend(("--note", args.note))
        if args.confirm:
            forwarded.append("--confirm")
    try:
        code, payload = run(forwarded)
    except (
        BybitUniverseError,
        LeanRadarConfigError,
        LeanRadarStoreError,
        LeanUniverseError,
    ) as exc:
        code = 2
        payload = {
            "status": "blocked",
            "reason": str(exc),
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
            "research_only": True,
        }
    print(
        json.dumps(payload, indent=2, sort_keys=True)
        if args.json
        else render_summary(payload)
    )
    return code


__all__ = ("main", "render_summary", "run")
