"""Offline golden eval runner for the event LLM raw-event extractor."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .... import event_llm_extractor
from ....event_providers.manual_json import ManualJsonEventProvider
from ....llm_providers.fixture import FixtureLLMExtractionProvider


@dataclass(frozen=True)
class EventLLMExtractEvalResult:
    fixture_path: Path
    total_cases: int
    passed_cases: int
    mismatches: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def success(self) -> bool:
        return not self.mismatches and self.passed_cases == self.total_cases


def run_fixture_eval(path: str | Path) -> EventLLMExtractEvalResult:
    fixture_path = Path(path).expanduser()
    raw_fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    outputs = raw_fixture.get("llm_extractions", []) if isinstance(raw_fixture, Mapping) else []
    if not isinstance(outputs, list):
        outputs = []
    raw_events = ManualJsonEventProvider(fixture_path, required=True).fetch_events(
        datetime(1970, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 1, 1, tzinfo=timezone.utc),
    )
    rows = event_llm_extractor.analyze_raw_events(
        raw_events,
        FixtureLLMExtractionProvider(fixture_path, required=True),
        cfg=event_llm_extractor.EventLLMExtractorConfig(max_events_per_run=500),
    )
    by_raw_id = {row.raw_event.raw_id: row for row in rows}
    mismatches: list[str] = []
    warnings: list[str] = []
    passed = 0
    for idx, item in enumerate(outputs):
        if not isinstance(item, Mapping):
            mismatches.append(f"case[{idx}] is not an object")
            continue
        case_id = str(item.get("case_id") or f"case[{idx}]")
        raw_id = str(item.get("raw_id") or "")
        row = by_raw_id.get(raw_id)
        if row is None:
            mismatches.append(f"{case_id}: missing analyzed raw event for {raw_id}")
            continue
        if row.extraction is None:
            mismatches.append(f"{case_id}: no valid LLM extraction ({'; '.join(row.warnings)})")
            continue
        failures = _compare_expected(case_id, _expected_fields(item), row.extraction)
        if failures:
            mismatches.extend(failures)
            continue
        passed += 1
        warnings.extend(f"{case_id}: {warning}" for warning in row.warnings)
    return EventLLMExtractEvalResult(
        fixture_path=fixture_path,
        total_cases=len(outputs),
        passed_cases=passed,
        mismatches=tuple(mismatches),
        warnings=tuple(warnings),
    )


def format_eval_result(result: EventLLMExtractEvalResult) -> str:
    lines = [
        "EVENT LLM EXTRACTION GOLDEN EVAL",
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
        lines.append("PASS: all golden cases matched expected LLM raw-event extractions.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    fixture = args[0] if args else "fixtures/event_discovery/llm_extraction_golden_cases.json"
    result = run_fixture_eval(fixture)
    print(format_eval_result(result))
    return 0 if result.success else 1


def _expected_fields(item: Mapping[str, Any]) -> Mapping[str, Any]:
    expected = item.get("expected")
    if isinstance(expected, Mapping):
        return expected
    extraction = item.get("extraction")
    return extraction if isinstance(extraction, Mapping) else {}


def _compare_expected(
    case_id: str,
    expected: Mapping[str, Any],
    extraction: event_llm_extractor.EventLLMRawEventExtraction,
) -> list[str]:
    failures: list[str] = []
    catalyst_names = {str(item.name or "").lower() for item in extraction.external_catalysts}
    mention_symbols = {str(item.symbol or "").lower() for item in extraction.crypto_asset_mentions if item.symbol}
    mention_names = {str(item.name or "").lower() for item in extraction.crypto_asset_mentions if item.name}
    mention_types = {str(item.mention_type) for item in extraction.crypto_asset_mentions}
    false_terms = {str(item.text).lower() for item in extraction.false_positive_terms}
    for wanted in expected.get("external_catalysts", []) or []:
        if str(wanted).lower() not in catalyst_names:
            failures.append(f"{case_id}: missing external catalyst {wanted!r}")
    for wanted in expected.get("asset_symbols", []) or []:
        if str(wanted).lower() not in mention_symbols:
            failures.append(f"{case_id}: missing asset symbol {wanted!r}")
    for wanted in expected.get("asset_names", []) or []:
        if str(wanted).lower() not in mention_names:
            failures.append(f"{case_id}: missing asset name {wanted!r}")
    for wanted in expected.get("mention_types", []) or []:
        if str(wanted) not in mention_types:
            failures.append(f"{case_id}: missing mention type {wanted!r}")
    for wanted in expected.get("false_positive_terms", []) or []:
        if str(wanted).lower() not in false_terms:
            failures.append(f"{case_id}: missing false-positive term {wanted!r}")
    min_conf = expected.get("min_confidence")
    if min_conf is not None and extraction.confidence < float(min_conf):
        failures.append(f"{case_id}: confidence expected >= {float(min_conf):.2f}, got {extraction.confidence:.2f}")
    max_conf = expected.get("max_confidence")
    if max_conf is not None and extraction.confidence > float(max_conf):
        failures.append(f"{case_id}: confidence expected <= {float(max_conf):.2f}, got {extraction.confidence:.2f}")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
