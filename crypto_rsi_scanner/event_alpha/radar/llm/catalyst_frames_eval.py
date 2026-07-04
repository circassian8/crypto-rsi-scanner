"""Offline eval for LLM catalyst-frame parsing and validation."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator as event_catalyst_frame_validator
import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as event_catalyst_frames
import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from crypto_rsi_scanner.llm_providers.fixture import FixtureLLMCatalystFrameProvider


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    path = Path(args[0]) if args else Path("fixtures/event_discovery/llm_catalyst_frame_cases.json")
    rows = _load_rows(path)
    provider = FixtureLLMCatalystFrameProvider(path, required=True)
    cfg = event_llm_catalyst_frames.EventLLMCatalystFrameConfig(
        enabled=True,
        provider="fixture",
        max_rows_per_run=100,
        min_source_score=0.0,
        only_ambiguous=False,
    )
    failures: list[str] = []
    lines = [
        "EVENT LLM CATALYST-FRAME EVAL",
        f"Fixture: {path}",
    ]
    for item in rows:
        raw = _raw_from_item(item)
        report = event_llm_catalyst_frames.analyze_raw_events((raw,), provider, cfg=cfg)
        analysis = report[0].analysis if report else None
        if analysis is None:
            failures.append(f"{raw.raw_id}: no analysis")
            continue
        validation = event_catalyst_frame_validator.validate_llm_catalyst_frames(
            analysis,
            (raw,),
            rule_frames=_rule_frames_for_eval(raw.raw_id),
        )
        expected = item.get("expected") if isinstance(item.get("expected"), Mapping) else {}
        selected = validation.selected_main_frame.frame_type if validation.selected_main_frame else None
        ok = True
        if expected.get("selected_main_frame_type") and selected != expected.get("selected_main_frame_type"):
            ok = False
            failures.append(f"{raw.raw_id}: selected={selected} expected={expected.get('selected_main_frame_type')}")
        if expected.get("background_frame_count") is not None:
            count = sum(1 for frame in validation.valid_frames if frame.frame_role in {"background_context", "historical_context"})
            if int(expected["background_frame_count"]) != count:
                ok = False
                failures.append(f"{raw.raw_id}: background_count={count} expected={expected['background_frame_count']}")
        if expected.get("negated_frame_count") is not None:
            count = sum(1 for frame in validation.valid_frames if frame.frame_role in {"negated_claim", "corrective_context"})
            if int(expected["negated_frame_count"]) != count:
                ok = False
                failures.append(f"{raw.raw_id}: negated_count={count} expected={expected['negated_frame_count']}")
        lines.append(
            f"{'PASS' if ok else 'FAIL'} {raw.raw_id}: main={selected or 'none'} "
            f"resolution={validation.resolution} warnings={len(validation.frame_warnings)}"
        )
    lines.append(f"Cases: {len(rows) - len(failures)}/{len(rows)} passed")
    if failures:
        lines.extend(f"  failure: {failure}" for failure in failures)
    print("\n".join(lines))
    return 1 if failures else 0


def _load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("llm_catalyst_frames") if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        raise ValueError("LLM catalyst-frame eval fixture must contain llm_catalyst_frames list")
    return [dict(item) for item in rows if isinstance(item, Mapping) and item.get("raw_id") != "invalid_quote"]


def _raw_from_item(item: Mapping[str, Any]) -> RawDiscoveredEvent:
    raw_id = str(item.get("raw_id") or item.get("case_id") or "unknown")
    text = _TEXT_FIXTURES.get(raw_id, {})
    now = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    return RawDiscoveredEvent(
        raw_id=raw_id,
        provider="fixture_news",
        fetched_at=now,
        published_at=now,
        source_url=str(item.get("source_url") or f"https://alpha.example/{raw_id}"),
        title=str(item.get("title") or text.get("title") or raw_id),
        body=str(item.get("body") or text.get("body") or ""),
        raw_json={},
        source_confidence=0.90,
        content_hash=raw_id,
    )


def _rule_frames_for_eval(raw_id: str) -> tuple[event_catalyst_frames.EventCatalystFrame, ...]:
    if raw_id != "aave_kraken":
        return ()
    return (
        event_catalyst_frames.EventCatalystFrame(
            frame_id="rule:exploit",
            frame_type="exploit_security_event",
            frame_role="main_catalyst",
            subject="Aave",
            event_archetype="exploit_security_event",
            claim_polarity="asserted",
            cause_status="confirmed",
            confidence=0.80,
            evidence_quote="KelpDAO exploit",
        ),
    )


_TEXT_FIXTURES = {
    "aave_kraken": {
        "title": "Kraken in talks to buy 15% stake in DeFi lender Aave at $385 million valuation",
        "body": "The DeFi lender is rebuilding after the fallout from April's KelpDAO exploit sparked a multibillion-dollar exodus of deposits despite Aave itself not being hacked.",
    },
    "thor_exploit": {
        "title": "THORChain suffers exploit and RUNE resumes trading",
        "body": "THORChain exploit drained funds before RUNE resumed trading.",
    },
    "memecore_no_exploit": {
        "title": "MemeCore's M token crashes 80% with no exploit or announcement to explain it",
        "body": "No exploit or announcement explains the M token selloff; cause unknown.",
    },
    "zec_miner_listing": {
        "title": "Zcash miner plans Nasdaq listing tied to ZEC treasury strategy",
        "body": "The miner says the public listing gives investors exposure to its ZEC treasury strategy.",
    },
    "velvet_spacex": {
        "title": "Velvet users can trade SpaceX pre-IPO exposure",
        "body": "Velvet users can trade SpaceX pre-IPO exposure through the platform's tokenized market.",
    },
}


if __name__ == "__main__":
    raise SystemExit(main())
