"""Live-provider guardrail rows for the daily no-send burn-in loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import common


def live_provider_guardrails(context: Any, provider_status: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provider, status in sorted(provider_status.items()):
        ledger_rel = str(status.get("request_ledger_path") or "")
        ledger_path = context.namespace_dir / Path(ledger_rel).name if ledger_rel else None
        ledger_rows = common.read_jsonl(ledger_path) if ledger_path else []
        report = _provider_rehearsal_report(context, provider)
        rows.append(
            {
                "provider": provider,
                "status": status.get("status"),
                "configured": bool(status.get("configured")),
                "allow_flag_set": bool(status.get("allow_flag_set")),
                "live_call_allowed": bool(status.get("live_call_allowed")),
                "no_send": True,
                "max_request_budget": int(status.get("request_budget") or 0),
                "request_ledger_path": ledger_rel,
                "request_ledger_writable_required": True,
                "request_ledger_present": bool(ledger_rows),
                "requests_used": len(ledger_rows),
                "rows_written": _provider_rows_written(provider, report),
                "provider_health_status": str(report.get("provider_health_status") or "not_observed") if report else "not_observed",
            }
        )
    return rows


def format_live_provider_guardrails_markdown(rows: object) -> list[str]:
    guardrails = [row for row in (rows or []) if isinstance(row, Mapping)]
    if not guardrails:
        return []
    lines = ["", "## Live Provider Guardrails", ""]
    for row in guardrails:
        lines.append(
            f"- {row.get('provider')}: no_send=`{row.get('no_send')}` allow_flag_set=`{row.get('allow_flag_set')}` "
            f"live_call_allowed=`{row.get('live_call_allowed')}` max_request_budget=`{row.get('max_request_budget')}` "
            f"request_ledger_path=`{row.get('request_ledger_path')}` requests_used=`{row.get('requests_used')}` "
            f"rows_written=`{row.get('rows_written')}` provider_health_status=`{row.get('provider_health_status')}` "
            f"status=`{row.get('status')}`"
        )
    return lines


def _provider_rehearsal_report(context: Any, provider: str) -> Mapping[str, Any]:
    filename = {
        "coinalyze": "event_coinalyze_rehearsal_report.json",
        "bybit_announcements": "event_bybit_announcements_rehearsal_report.json",
    }.get(provider)
    return common.read_json(context.namespace_dir / filename) if filename else {}


def _provider_rows_written(provider: str, report: Mapping[str, Any]) -> int:
    if not report:
        return 0
    if provider == "coinalyze":
        return (
            int(report.get("snapshots_written") or 0)
            + int(report.get("crowding_candidates_written") or 0)
            + int(report.get("fade_review_candidates_written") or 0)
        )
    if provider == "bybit_announcements":
        return (
            int(report.get("exchange_announcements_written") or 0)
            + int(report.get("official_events_written") or 0)
            + int(report.get("official_listing_candidates_written") or 0)
        )
    return 0
