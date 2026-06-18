"""Daily Markdown brief for Event Alpha research artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import (
    event_alpha_calibration,
    event_alpha_explain,
    event_alpha_router,
    event_research_cards,
    event_source_reliability,
    event_watchlist,
)


@dataclass(frozen=True)
class EventAlphaDailyBriefResult:
    path: Path
    markdown: str
    cards: tuple[Path, ...] = ()


def build_daily_brief(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry] = (),
    router_result: event_alpha_router.EventAlphaRouterResult | None = None,
    card_paths: Iterable[Path] = (),
    generated_at: datetime | None = None,
) -> str:
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    missed = [dict(row) for row in missed_rows if isinstance(row, Mapping)]
    entries = list(watchlist_entries)
    decisions = list(router_result.decisions if router_result else ())
    alertable = list(router_result.alertable_decisions if router_result else ())
    latest = runs[0] if runs else {}
    lines = [
        "# Event Alpha Daily Brief",
        "",
        f"Generated at: {generated.isoformat()}",
        "",
        "Research-only. Not a trade signal, paper trade, live RSI signal, or execution.",
        "",
        "## Last Run Health",
    ]
    if latest:
        lines.extend([
            f"- Run: {latest.get('run_id') or 'unknown'}",
            f"- Profile: {latest.get('profile') or 'default'}",
            f"- Success: {str(bool(latest.get('success'))).lower()}",
            f"- Raw/events/candidates/alerts: {int(latest.get('raw_events') or 0)} / {int(latest.get('candidates') or 0)} / {int(latest.get('alerts') or 0)}",
            f"- Routed/alertable/sent: {int(latest.get('routed') or 0)} / {int(latest.get('alertable') or 0)} / {str(bool(latest.get('sent'))).lower()}",
            f"- LLM calls/skipped budget: {int(latest.get('llm_calls_attempted') or 0)} / {int(latest.get('llm_skipped_due_budget') or 0)}",
        ])
        warnings = [str(w) for w in latest.get("warnings") or [] if str(w)]
        if warnings:
            lines.append("- Warnings: " + "; ".join(warnings[:6]))
    else:
        lines.append("- No run ledger rows found.")
    lines.extend(["", "## Alertable Route Decisions"])
    if alertable:
        for decision in alertable[:10]:
            entry = decision.entry
            lines.append(f"- {decision.route.value}: {entry.symbol}/{entry.coin_id} state={entry.state} score={entry.latest_score} reason={decision.reason}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Active Watchlist"])
    active = [
        entry for entry in entries
        if entry.state in {
            event_watchlist.EventWatchlistState.RADAR.value,
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            event_watchlist.EventWatchlistState.ARMED.value,
        }
    ]
    if active:
        for entry in sorted(active, key=lambda item: item.latest_score, reverse=True)[:10]:
            lines.append(f"- {entry.state}: {entry.symbol}/{entry.coin_id} score={entry.latest_score} playbook={entry.latest_playbook_type or 'unknown'}")
    else:
        lines.append("- No active watchlist entries.")
    lines.extend(["", "## Research Cards"])
    cards = [Path(path) for path in card_paths]
    if cards:
        for path in cards[:20]:
            lines.append(f"- [{path.name}]({path})")
    else:
        lines.append("- No cards written for this brief.")
    lines.extend(["", "## Missed Opportunities"])
    if missed:
        for row in missed[:10]:
            lines.append(f"- {row.get('symbol') or row.get('coin_id')}: {row.get('move_window')} {row.get('return_pct')} stage={row.get('failure_stage')}")
    else:
        lines.append("- No missed-opportunity rows found.")
    lines.extend(["", "## Source Reliability"])
    lines.append(_compact(event_source_reliability.format_source_reliability_report(
        alerts,
        feedback_rows=feedback,
        missed_rows=missed,
        run_rows=runs[:10],
    )))
    lines.extend(["", "## Calibration"])
    lines.append(_compact(event_alpha_calibration.format_calibration_report(
        alerts,
        feedback_rows=feedback,
        missed_rows=missed,
    )))
    if not alertable:
        lines.extend(["", "## Why No Alerts"])
        lines.append(_compact(event_alpha_explain.format_last_run_explanation(runs[:1], alert_rows=alerts)))
    return _strip_sensitive("\n".join(lines).rstrip() + "\n")


def write_daily_brief(
    path: str | Path,
    *,
    markdown: str,
    card_paths: Iterable[Path] = (),
) -> EventAlphaDailyBriefResult:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = _strip_sensitive(markdown)
    target.write_text(clean, encoding="utf-8")
    return EventAlphaDailyBriefResult(path=target, markdown=clean, cards=tuple(Path(p) for p in card_paths))


def format_daily_brief_result(result: EventAlphaDailyBriefResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT ALPHA DAILY BRIEF WRITTEN (research artifact only)",
        "=" * 76,
        f"path: {result.path}",
        f"cards_linked: {len(result.cards)}",
        "No live RSI alerts, paper trades, live DB rows, or execution were changed.",
    ])


def _compact(report: str) -> str:
    lines = [line for line in str(report or "").splitlines() if line and not line.startswith("=")]
    return "\n".join(f"> {line}" for line in lines[:20])


def _strip_sensitive(text: str) -> str:
    return (
        text.replace("OPENAI_API_KEY", "[redacted]")
        .replace("TELEGRAM_BOT_TOKEN", "[redacted]")
        .replace(".env", "[env-file]")
    )
