"""Small operator CLI for Lean Crypto Radar foundation commands."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Mapping, Sequence

from .bybit_universe import BybitUniverseError, load_catalog
from .calendar import LeanCalendarError, load_calendar_snapshot
from .config import LeanRadarConfigError, LeanRadarSettings, load_settings
from .health import refresh_system_health
from .market_data import MarketDataError, live_provider_authorized
from .outcomes import LeanOutcomeError, refresh_outcomes
from .safety import SAFETY_COUNTERS
from .scan import run_scan, scan_readiness
from .store import LeanRadarStore, LeanRadarStoreError
from .telegram import (
    LeanTelegramError,
    build_telegram_plan,
    render_telegram_preview,
    render_telegram_readiness,
    send_telegram_plan,
    telegram_readiness,
)
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
    subparsers.add_parser("calendar-readiness")
    outcomes = subparsers.add_parser("outcomes")
    outcomes.add_argument("--evaluated-at", type=_time)
    health = subparsers.add_parser("health")
    health.add_argument("--evaluated-at", type=_time)
    telegram_preview = subparsers.add_parser("telegram-preview")
    telegram_preview.add_argument("--evaluated-at", type=_time)
    telegram_readiness_parser = subparsers.add_parser("telegram-readiness")
    telegram_readiness_parser.add_argument("--evaluated-at", type=_time)
    telegram_send = subparsers.add_parser("telegram-send")
    telegram_send.add_argument("--evaluated-at", type=_time)
    telegram_send.add_argument("--confirm", action="store_true")

    importer = subparsers.add_parser("bybit-import")
    importer.add_argument("--catalog", type=Path, required=True)
    importer.add_argument("--confirm", action="store_true")

    calendar_importer = subparsers.add_parser("calendar-import")
    calendar_importer.add_argument("--calendar", type=Path, required=True)
    calendar_importer.add_argument("--confirm", action="store_true")

    universe = subparsers.add_parser("universe")
    universe.add_argument("--markets", type=Path)

    watchlist = subparsers.add_parser("watchlist-add")
    watchlist.add_argument("--canonical-asset-id", required=True)
    watchlist.add_argument("--symbol", required=True)
    watchlist.add_argument("--note", default="")
    watchlist.add_argument("--confirm", action="store_true")

    scan = subparsers.add_parser("scan")
    scan.add_argument(
        "--source-mode",
        choices=("live_no_send", "imported_snapshot", "fixture"),
        default="live_no_send",
    )
    scan.add_argument("--markets", type=Path)
    scan.add_argument("--observed-at", type=_time)
    cycle = subparsers.add_parser("cycle")
    cycle.add_argument(
        "--source-mode",
        choices=("live_no_send", "imported_snapshot", "fixture"),
        default="live_no_send",
    )
    cycle.add_argument("--markets", type=Path)
    cycle.add_argument("--observed-at", type=_time)
    return parser


def run(argv: Sequence[str] | None = None) -> tuple[int, dict[str, object]]:
    args = _parser().parse_args(argv)
    settings = load_settings()
    store = LeanRadarStore(args.db or settings.db_path)
    if args.command == "telegram-preview":
        return 0, build_telegram_plan(store, evaluated_at=args.evaluated_at)
    if args.command == "telegram-readiness":
        return 0, telegram_readiness(store, evaluated_at=args.evaluated_at)
    if args.command == "telegram-send":
        payload = send_telegram_plan(
            store,
            confirm=args.confirm,
            evaluated_at=args.evaluated_at,
        )
        return (0 if payload["status"] in {"complete", "no_due_messages"} else 2), payload
    if args.command == "outcomes":
        payload = refresh_outcomes(store, evaluated_at=args.evaluated_at)
        payload["next_safe_command"] = (
            "make lean-radar-health"
            if payload["status"] != "setup_required"
            else "make lean-radar-readiness"
        )
        return 0, payload
    if args.command == "health":
        return 0, refresh_system_health(
            store,
            settings,
            evaluated_at=args.evaluated_at,
        )
    if args.command == "cycle":
        return _run_cycle(args, store, settings)
    if args.command == "calendar-readiness":
        calendar = store.calendar_status()
        return 0, {
            "status": "ready" if calendar["status"] == "ready" else "setup_required",
            "calendar": calendar,
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
            "research_only": True,
            "next_safe_command": (
                "make lean-radar-cycle"
                if calendar["status"] == "ready"
                else "CONFIRM=1 make lean-radar-calendar-import "
                "LEAN_RADAR_CALENDAR_SNAPSHOT=/absolute/path/to/calendar.json"
            ),
        }
    if args.command == "calendar-import":
        if not args.confirm:
            return 2, {
                "status": "confirmation_required",
                "provider_call_attempted": False,
                "research_only": True,
            }
        events = load_calendar_snapshot(
            args.calendar,
            source_mode="imported_snapshot",
        )
        store.upsert_calendar_events(events)
        return 0, {
            "status": "imported",
            "calendar_event_count": len(events),
            "source_name": events[0].source_name,
            "source_observed_at": events[0].source_observed_at,
            "source_sha256": events[0].source_sha256,
            "context_only": True,
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
            "research_only": True,
            "next_safe_command": "make lean-radar-cycle",
        }
    if args.command in {"readiness", "bybit-readiness"}:
        catalog = store.catalog_status()
        if args.command == "readiness":
            scan_status = scan_readiness(
                store,
                settings,
                source_mode="live_no_send",
            )
            ready = scan_status["status"] == "ready"
        else:
            scan_status = None
            ready = catalog["status"] == "ready"
        if catalog["status"] != "ready":
            next_safe_command = (
                "CONFIRM=1 make lean-radar-bybit-universe-import "
                "LEAN_RADAR_BYBIT_CATALOG=/absolute/path/to/instruments-info.json"
            )
        elif args.command == "bybit-readiness":
            next_safe_command = "make lean-radar-universe"
        elif ready:
            next_safe_command = "make lean-radar-cycle"
        elif not live_provider_authorized():
            next_safe_command = (
                "authorize CoinGecko under the existing provider policy, then run "
                "make lean-radar-readiness"
            )
        else:
            next_safe_command = "run make lean-radar-readiness after the reported cadence wait"
        payload = {
            "status": "ready" if ready else "setup_required",
            "product": "Lean Crypto Radar V1",
            "default_operator_path": True,
            "venue": "bybit",
            "instrument_type": "usdt_perpetual",
            "top_liquid_limit": settings.top_liquid_limit,
            "cadence_minutes": settings.cadence_minutes,
            "bybit_catalog": catalog,
            "scan_readiness": scan_status,
            "live_provider_authorized": live_provider_authorized(),
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
            "research_only": True,
            "next_safe_command": next_safe_command,
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
            "status": (
                "active_pending_market_data"
                if symbol in instrument_bases
                else "blocked_unverified"
            ),
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
    if args.command == "scan":
        result = _execute_scan(args, store, settings)
        return (0 if result.get("status") == "complete" else 2), result
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
    if "snapshot_count" in payload:
        lines.append(
            f"Snapshots: {payload.get('snapshot_count', 0)} · "
            f"ideas: {payload.get('idea_count', 0)}"
        )
    if "calendar_event_count" in payload:
        lines.append(f"Calendar events: {payload['calendar_event_count']}")
    if "outcome_count" in payload:
        lines.append(
            f"Outcomes: {payload.get('matured_count', 0)} matured · "
            f"{payload.get('pending_count', 0)} pending · "
            f"{payload.get('unresolved_count', 0)} unresolved"
        )
    if "data_freshness" in payload:
        lines.append(
            f"Market data: {payload.get('data_freshness', 'unavailable')} · "
            f"provider eligibility: "
            f"{payload.get('current_provider_call_eligibility', 'unavailable')}"
        )
        lines.append(
            f"Telegram: {payload.get('telegram_mode', 'disabled_no_send')} · no send"
        )
    scan = payload.get("scan")
    if isinstance(scan, Mapping):
        lines.append(
            f"Scan: {scan.get('status', 'unknown')} · "
            f"{scan.get('snapshot_count', 0)} snapshots · "
            f"{scan.get('idea_count', 0)} ideas"
        )
    cycle_outcomes = payload.get("outcomes")
    if isinstance(cycle_outcomes, Mapping):
        lines.append(
            f"Outcomes: {cycle_outcomes.get('status', 'unknown')} · "
            f"{cycle_outcomes.get('matured_count', 0)} matured · "
            f"{cycle_outcomes.get('pending_count', 0)} pending"
        )
    preview = payload.get("telegram_preview")
    if isinstance(preview, Mapping):
        lines.append(
            f"Telegram preview: {preview.get('message_count', 0)} messages · "
            f"{preview.get('due_item_count', 0)} due items · no send"
        )
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        lines.append("Attention: " + "; ".join(str(value) for value in errors[:4]))
    calendar = payload.get("calendar")
    if isinstance(calendar, Mapping):
        lines.append(
            f"Calendar: {calendar.get('status', 'unknown')} · "
            f"events: {calendar.get('event_count', 0)} · "
            f"upcoming: {calendar.get('upcoming_event_count', 0)}"
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
    elif args.command == "calendar-import":
        forwarded.extend(("--calendar", str(args.calendar)))
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
    elif args.command in {"scan", "cycle"}:
        forwarded.extend(("--source-mode", args.source_mode))
        if args.markets:
            forwarded.extend(("--markets", str(args.markets)))
        if args.observed_at:
            forwarded.extend(("--observed-at", args.observed_at.isoformat()))
    elif args.command in {
        "outcomes",
        "health",
        "telegram-preview",
        "telegram-readiness",
        "telegram-send",
    } and args.evaluated_at:
        forwarded.extend(("--evaluated-at", args.evaluated_at.isoformat()))
    if args.command == "telegram-send" and args.confirm:
        forwarded.append("--confirm")
    try:
        code, payload = run(forwarded)
    except (
        BybitUniverseError,
        LeanCalendarError,
        LeanOutcomeError,
        LeanRadarConfigError,
        LeanRadarStoreError,
        LeanTelegramError,
        LeanUniverseError,
        MarketDataError,
    ) as exc:
        code = 2
        payload = {
            "status": "blocked",
            "reason": str(exc),
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
            "research_only": True,
        }
    if args.json:
        output = json.dumps(payload, indent=2, sort_keys=True)
    elif args.command == "telegram-preview":
        output = render_telegram_preview(payload)
    elif args.command == "telegram-readiness":
        output = render_telegram_readiness(payload)
    else:
        output = render_summary(payload)
    print(output)
    return code


def _execute_scan(
    args: argparse.Namespace,
    store: LeanRadarStore,
    settings: LeanRadarSettings,
) -> dict[str, object]:
    if args.source_mode == "live_no_send":
        if args.markets is not None or args.observed_at is not None:
            raise MarketDataError(
                "live scan does not accept local market rows or an observation clock"
            )
        return run_scan(
            store,
            settings,
            source_mode="live_no_send",
        )
    if args.markets is None or args.observed_at is None:
        raise MarketDataError("local scan requires --markets and --observed-at")
    rows = load_market_rows(
        args.markets,
        require_genuine=args.source_mode == "imported_snapshot",
    )
    return run_scan(
        store,
        settings,
        source_mode=args.source_mode,
        rows=rows,
        observed_at=args.observed_at,
        evaluated_at=args.observed_at,
    )


def _run_cycle(
    args: argparse.Namespace,
    store: LeanRadarStore,
    settings: LeanRadarSettings,
) -> tuple[int, dict[str, object]]:
    """Run one explicit no-send scan/outcome/health/preview sequence."""

    try:
        scan = _execute_scan(args, store, settings)
    except (LeanUniverseError, MarketDataError) as exc:
        scan = {
            "status": "blocked",
            "reason": str(exc),
            "source_mode": args.source_mode,
            "provider_call_attempted": False,
            "provider_call_succeeded": False,
        }
    cycle_at = _cycle_clock(args, scan)
    try:
        outcomes = refresh_outcomes(store, evaluated_at=cycle_at)
    except (LeanOutcomeError, LeanRadarStoreError, TypeError, ValueError):
        outcomes = {
            "status": "blocked",
            "reason": "retained outcome evidence could not be refreshed",
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
        }
    health = refresh_system_health(store, settings, evaluated_at=cycle_at)
    try:
        preview = build_telegram_plan(store, evaluated_at=cycle_at)
    except LeanTelegramError:
        preview = {
            "status": "blocked",
            "reason": "Telegram preview state could not be validated",
            "message_count": 0,
            "due_item_count": 0,
            "suppressed_count": 0,
            "market_idea_freshness": "unavailable",
        }
    scan_status = str(scan.get("status", "blocked"))
    if (
        scan_status == "complete"
        and outcomes.get("status") != "blocked"
        and preview.get("status") != "blocked"
    ):
        status, code = "complete", 0
    elif scan.get("cadence_eligible") is False and scan.get("provider_call_attempted") is False:
        status, code = "waiting", 0
    elif scan_status in {"provider_failed", "market_data_blocked"}:
        status, code = "failed", 2
    else:
        status, code = "blocked", 2
    next_safe_command = (
        "make lean-radar-dashboard"
        if status == "complete"
        else health.get("next_safe_command", "make lean-radar")
    )
    payload = {
        "schema_version": "lean_operator_cycle_v1",
        "status": status,
        "source_mode": args.source_mode,
        "scan": _scan_cycle_summary(scan),
        "outcomes": _outcome_cycle_summary(outcomes),
        "health": {
            "status": health.get("status", "unavailable"),
            "data_freshness": health.get("data_freshness", "unavailable"),
            "current_provider_call_eligibility": health.get(
                "current_provider_call_eligibility", "unavailable"
            ),
        },
        "telegram_preview": {
            "status": preview.get("status", "unavailable"),
            "message_count": preview.get("message_count", 0),
            "due_item_count": preview.get("due_item_count", 0),
            "suppressed_count": preview.get("suppressed_count", 0),
            "market_idea_freshness": preview.get(
                "market_idea_freshness", "unavailable"
            ),
        },
        "provider_call_attempted": scan.get("provider_call_attempted") is True,
        "provider_call_succeeded": scan.get("provider_call_succeeded") is True,
        "telegram_send_attempted": False,
        "database_write_attempted": store.path.exists(),
        "no_send": True,
        "research_only": True,
        "next_safe_command": next_safe_command,
        **SAFETY_COUNTERS,
    }
    return code, payload


def _scan_cycle_summary(scan: Mapping[str, object]) -> dict[str, object]:
    return {
        key: scan.get(key)
        for key in (
            "status",
            "reason",
            "reasons",
            "source_mode",
            "scan_id",
            "observed_at",
            "next_scan_at",
            "cadence_minutes",
            "cadence_eligible",
            "provider_call_attempted",
            "provider_call_succeeded",
            "snapshot_count",
            "idea_count",
            "outcome_placeholder_count",
        )
        if key in scan
    }


def _outcome_cycle_summary(outcomes: Mapping[str, object]) -> dict[str, object]:
    return {
        key: outcomes.get(key)
        for key in (
            "status",
            "reason",
            "outcome_count",
            "matured_count",
            "pending_count",
            "unresolved_count",
        )
        if key in outcomes
    }


def _cycle_clock(
    args: argparse.Namespace,
    scan: Mapping[str, object],
) -> datetime:
    if args.observed_at is not None:
        return args.observed_at.astimezone(timezone.utc)
    checked_at = scan.get("checked_at")
    if isinstance(checked_at, str):
        try:
            parsed = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None and parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed


__all__ = ("main", "render_summary", "run")
