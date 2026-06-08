"""Human-readable operational status for CLI and bot commands."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import config


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _age_hours(dt: datetime | None, now: datetime) -> float | None:
    if dt is None:
        return None
    return max(0.0, (now - dt).total_seconds() / 3600.0)


def _fmt_time(dt: datetime | None) -> str:
    if dt is None:
        return "never"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_age(hours: float | None) -> str:
    if hours is None:
        return "n/a"
    if hours < 1:
        return f"{int(round(hours * 60))}m ago"
    if hours < 48:
        return f"{hours:.1f}h ago"
    return f"{hours / 24:.1f}d ago"


def _duration(start: datetime | None, finish: datetime | None) -> str:
    if start is None or finish is None:
        return "n/a"
    seconds = max(0.0, (finish - start).total_seconds())
    if seconds < 90:
        return f"{seconds:.0f}s"
    return f"{seconds / 60:.1f}m"


def _latest_signal_count(storage) -> int:
    raw = storage.get_meta("latest_signals")
    if not raw:
        return 0
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return 0
    return len(data) if isinstance(data, list) else 0


def build_status(storage, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    raw = storage.scan_status()
    started = _parse_iso(raw.get("started_at"))
    finished = _parse_iso(raw.get("finished_at"))
    last_success = _parse_iso(raw.get("last_success_at")) or storage.last_successful_scan_at()
    last_failure = _parse_iso(raw.get("last_failure_at"))
    last_success_age = _age_hours(last_success, now)
    stale = (
        last_success_age is not None
        and config.STALE_SCAN_HOURS > 0
        and last_success_age >= config.STALE_SCAN_HOURS
    )

    state = raw.get("state") or "unknown"
    if state == "failure":
        health = "FAILED"
    elif state == "running":
        health = "RUNNING"
    elif stale:
        health = "STALE"
    elif last_success is not None:
        health = "OK"
    else:
        health = "UNKNOWN"

    return {
        "health": health,
        "state": state,
        "started_at": started,
        "finished_at": finished,
        "duration": _duration(started, finished),
        "last_success_at": last_success,
        "last_success_age_hours": last_success_age,
        "last_failure_at": last_failure,
        "last_error": raw.get("last_error"),
        "stale_threshold_hours": config.STALE_SCAN_HOURS,
        "requested": raw.get("requested"),
        "fetched": raw.get("fetched"),
        "analyzed": raw.get("analyzed"),
        "coin_count": raw.get("coin_count"),
        "flagged_count": raw.get("flagged_count"),
        "ob_count": raw.get("ob_count"),
        "os_count": raw.get("os_count"),
        "instant_count": raw.get("instant_count"),
        "digest_count": raw.get("digest_count"),
        "matured_outcomes": raw.get("matured_outcomes"),
        "paper_opened": raw.get("paper_opened"),
        "paper_closed": raw.get("paper_closed"),
        "latest_signal_count": _latest_signal_count(storage),
        "active_subscribers": len(storage.active_subscribers()),
        "open_paper_trades": len(storage.open_paper_trades()),
    }


def format_status(storage, now: datetime | None = None) -> str:
    s = build_status(storage, now=now)
    lines = ["RSI SCANNER STATUS", f"health: {s['health']}"]
    lines.append(f"scan state: {s['state']}")
    lines.append(
        "last success: "
        f"{_fmt_time(s['last_success_at'])} ({_fmt_age(s['last_success_age_hours'])})"
    )
    lines.append(f"last failure: {_fmt_time(s['last_failure_at'])}")
    lines.append(
        f"last attempt: started {_fmt_time(s['started_at'])}, "
        f"finished {_fmt_time(s['finished_at'])}, duration {s['duration']}"
    )

    requested = s["requested"]
    fetched = s["fetched"]
    analyzed = s["analyzed"]
    if requested is not None or fetched is not None or analyzed is not None:
        lines.append(f"fetch: requested {requested or 0}, fetched {fetched or 0}, analyzed {analyzed or 0}")

    if s["coin_count"] is not None:
        lines.append(
            f"signals: scanned {s['coin_count']}, flagged {s['flagged_count'] or 0} "
            f"(OB {s['ob_count'] or 0}, OS {s['os_count'] or 0})"
        )
    if s["instant_count"] is not None or s["digest_count"] is not None:
        lines.append(
            f"routing: instant {s['instant_count'] or 0}, digest {s['digest_count'] or 0}"
        )
    if s["matured_outcomes"] is not None or s["paper_opened"] is not None:
        lines.append(
            f"bookkeeping: outcomes {s['matured_outcomes'] or 0}, "
            f"paper opened {s['paper_opened'] or 0}, closed {s['paper_closed'] or 0}"
        )

    lines.append(
        f"bot: {s['active_subscribers']} subscriber(s), "
        f"{s['latest_signal_count']} current snapshot signal(s)"
    )
    lines.append(f"paper: {s['open_paper_trades']} open trade(s)")
    lines.append(f"stale threshold: {s['stale_threshold_hours']:.0f}h")

    if s["last_error"]:
        lines.append(f"last error: {s['last_error']}")
    return "\n".join(lines)
