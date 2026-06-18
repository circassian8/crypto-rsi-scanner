"""Offline golden evals for Event Alpha Radar route and feedback behavior."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import event_alpha_router, event_feedback, event_watchlist


@dataclass(frozen=True)
class EventAlphaEvalResult:
    total: int
    passed: int
    failures: tuple[str, ...]


def run_eval(path: str | Path) -> EventAlphaEvalResult:
    fixture_path = Path(path)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    total = 0

    for case in payload.get("watchlist_routes") or ():
        total += 1
        entry = _entry_from_case(case)
        read = event_watchlist.EventWatchlistReadResult(
            state_path=fixture_path,
            rows_read=1,
            entries=[entry],
            latest_only=True,
        )
        result = event_alpha_router.route_watchlist(
            read,
            cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
        )
        actual = result.decisions[0].route.value if result.decisions else "NONE"
        expected = str(case.get("expected_route") or "")
        if actual != expected:
            failures.append(f"{case.get('id', entry.symbol)}: expected route {expected}, got {actual}")

    expected_labels = tuple(str(label) for label in payload.get("feedback_labels") or ())
    total += len(expected_labels)
    valid_labels = set(event_feedback.valid_labels())
    for label in expected_labels:
        if label not in valid_labels:
            failures.append(f"feedback label {label!r}: not accepted by EventFeedbackLabel")

    return EventAlphaEvalResult(total=total, passed=total - len(failures), failures=tuple(failures))


def format_eval_result(result: EventAlphaEvalResult, path: str | Path) -> str:
    rows = [
        "EVENT ALPHA GOLDEN EVAL",
        f"Fixture: {path}",
        f"Cases: {result.passed}/{result.total} passed",
    ]
    if result.failures:
        rows.append("Failures:")
        rows.extend(f"  - {failure}" for failure in result.failures)
        rows.append("FAIL: one or more Event Alpha golden checks failed.")
    else:
        rows.append("PASS: Event Alpha route and feedback golden checks matched.")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    path = argv[0] if argv else "fixtures/event_discovery/event_alpha_golden_cases.json"
    result = run_eval(path)
    print(format_eval_result(result, path))
    return 0 if not result.failures else 1


def _entry_from_case(case: Mapping[str, Any]) -> event_watchlist.EventWatchlistEntry:
    symbol = str(case.get("symbol") or case.get("id") or "TEST").upper()
    state = str(case.get("state") or event_watchlist.EventWatchlistState.RAW_EVIDENCE.value)
    score = int(case.get("score") or 0)
    return event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key=str(case.get("key") or f"{case.get('id', symbol)}|coin|rel|asset|time"),
        event_id=str(case.get("event_id") or case.get("id") or f"{symbol}-event"),
        coin_id=str(case.get("coin_id") or symbol.lower()),
        symbol=symbol,
        relationship_type=str(case.get("relationship_type") or "proxy_exposure"),
        external_asset=case.get("external_asset") or "SpaceX",
        event_time=case.get("event_time") or "2026-06-20T13:30:00+00:00",
        state=state,
        previous_state=case.get("previous_state") or "RADAR",
        first_seen_at=str(case.get("first_seen_at") or "2026-06-18T12:00:00+00:00"),
        last_seen_at=str(case.get("last_seen_at") or "2026-06-18T13:00:00+00:00"),
        source_count=int(case.get("source_count") or 1),
        highest_score=int(case.get("highest_score") or score),
        latest_score=score,
        latest_tier=str(case.get("latest_tier") or state),
        latest_event_name=str(case.get("event_name") or f"{symbol} Event Alpha candidate"),
        latest_source=str(case.get("source") or "fixture"),
        latest_playbook_type=case.get("playbook_type"),
        latest_playbook_score=score,
        latest_playbook_action=case.get("playbook_action") or "watchlist",
        should_alert=bool(case.get("should_alert", True)),
        suppressed_reason=case.get("suppressed_reason"),
        warnings=tuple(str(value) for value in case.get("warnings") or ()),
    )


if __name__ == "__main__":
    raise SystemExit(main())
