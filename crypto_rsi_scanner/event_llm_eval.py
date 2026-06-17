"""Offline golden eval runner for the event LLM shadow analyzer."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import event_alerts, event_discovery, event_llm_analyzer
from .event_providers.manual_json import ManualJsonEventProvider
from .event_resolver import load_asset_aliases
from .llm_providers.fixture import FixtureLLMRelationshipProvider


@dataclass(frozen=True)
class EventLLMEvalResult:
    fixture_path: Path
    total_cases: int
    passed_cases: int
    mismatches: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def success(self) -> bool:
        return not self.mismatches and self.passed_cases == self.total_cases


def run_fixture_eval(path: str | Path) -> EventLLMEvalResult:
    """Run deterministic fixture LLM outputs through analyzer validation."""
    fixture_path = Path(path).expanduser()
    raw_fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    outputs = raw_fixture.get("llm_outputs", []) if isinstance(raw_fixture, Mapping) else []
    if not isinstance(outputs, list):
        outputs = []
    result = _discovery_result_from_fixture(fixture_path)
    alerts = event_alerts.build_event_alert_candidates(
        result,
        cfg=event_alerts.EventAlertConfig(),
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    rows = event_llm_analyzer.analyze_event_candidates(
        result,
        alerts,
        FixtureLLMRelationshipProvider(fixture_path, required=True),
        cfg=event_llm_analyzer.EventLLMConfig(min_prefilter_score=0, max_candidates_per_run=500),
    )
    by_identity = {
        (row.candidate.event.event_id, row.candidate.asset.coin_id): row
        for row in rows
    }
    mismatches: list[str] = []
    warnings: list[str] = []
    passed = 0
    for idx, item in enumerate(outputs):
        if not isinstance(item, Mapping):
            mismatches.append(f"case[{idx}] is not an object")
            continue
        case_id = str(item.get("case_id") or f"case[{idx}]")
        event_id = str(item.get("event_id") or "")
        coin_id = str(item.get("coin_id") or "")
        row = by_identity.get((event_id, coin_id))
        if row is None:
            mismatches.append(f"{case_id}: missing analyzed candidate for {event_id}/{coin_id}")
            continue
        if row.analysis is None:
            mismatches.append(f"{case_id}: no valid LLM analysis ({'; '.join(row.warnings)})")
            continue
        expected = _expected_fields(item)
        failures = _compare_expected(case_id, expected, row.analysis)
        if failures:
            mismatches.extend(failures)
            continue
        passed += 1
        warnings.extend(f"{case_id}: {warning}" for warning in row.warnings)
    return EventLLMEvalResult(
        fixture_path=fixture_path,
        total_cases=len(outputs),
        passed_cases=passed,
        mismatches=tuple(mismatches),
        warnings=tuple(warnings),
    )


def format_eval_result(result: EventLLMEvalResult) -> str:
    lines = [
        "EVENT LLM GOLDEN EVAL",
        f"Fixture: {result.fixture_path}",
        f"Cases: {result.passed_cases}/{result.total_cases} passed",
    ]
    if result.warnings:
        lines.append(f"Warnings: {len(result.warnings)}")
        for warning in result.warnings[:10]:
            lines.append(f"  warning: {warning}")
        if len(result.warnings) > 10:
            lines.append(f"  ... {len(result.warnings) - 10} more warning(s)")
    if result.mismatches:
        lines.append(f"Mismatches: {len(result.mismatches)}")
        for mismatch in result.mismatches:
            lines.append(f"  FAIL: {mismatch}")
    else:
        lines.append("PASS: all golden cases matched expected LLM shadow classifications.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    fixture = args[0] if args else "fixtures/event_discovery/llm_golden_cases.json"
    result = run_fixture_eval(fixture)
    print(format_eval_result(result))
    return 0 if result.success else 1


def _discovery_result_from_fixture(path: Path) -> event_discovery.EventDiscoveryResult:
    raw = ManualJsonEventProvider(path, required=True).fetch_events(
        datetime(1970, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 1, 1, tzinfo=timezone.utc),
    )
    assets = load_asset_aliases(path)
    return event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )


def _expected_fields(item: Mapping[str, Any]) -> Mapping[str, Any]:
    expected = item.get("expected")
    if isinstance(expected, Mapping):
        return expected
    analysis = item.get("analysis")
    return analysis if isinstance(analysis, Mapping) else {}


def _compare_expected(
    case_id: str,
    expected: Mapping[str, Any],
    analysis: event_llm_analyzer.EventLLMAnalysis,
) -> list[str]:
    failures: list[str] = []
    comparisons = {
        "asset_role": analysis.asset_role,
        "relationship_type": analysis.relationship_type,
        "recommended_alert_action": analysis.recommended_alert_action,
    }
    for field, actual in comparisons.items():
        wanted = expected.get(field)
        if wanted is not None and str(wanted) != actual:
            failures.append(f"{case_id}: {field} expected {wanted!r}, got {actual!r}")
    min_conf = expected.get("min_confidence")
    if min_conf is not None and analysis.confidence < float(min_conf):
        failures.append(f"{case_id}: confidence expected >= {float(min_conf):.2f}, got {analysis.confidence:.2f}")
    max_conf = expected.get("max_confidence")
    if max_conf is not None and analysis.confidence > float(max_conf):
        failures.append(f"{case_id}: confidence expected <= {float(max_conf):.2f}, got {analysis.confidence:.2f}")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
