"""Export proposed Event Alpha eval cases from feedback and missed artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class EventAlphaEvalExportResult:
    out_dir: Path
    files_written: tuple[Path, ...]
    proposed_cases: int
    source: str


def export_cases_from_feedback(
    alert_rows: Iterable[Mapping[str, Any]],
    feedback_rows: Iterable[Mapping[str, Any]],
    out_dir: str | Path,
    *,
    now: datetime | None = None,
) -> EventAlphaEvalExportResult:
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    by_key = {str(row.get("alert_key") or row.get("key") or ""): row for row in alerts}
    cases: list[dict[str, Any]] = []
    for row in feedback:
        if row.get("label") not in {"junk", "useful", "watch"}:
            continue
        alert = by_key.get(str(row.get("key") or row.get("target") or ""))
        if not alert:
            continue
        cases.append(_feedback_case(alert, row))
    return _write_cases(out_dir, {"proposed_llm_golden_cases.json": cases}, "feedback", now=now)


def export_cases_from_missed(
    missed_rows: Iterable[Mapping[str, Any]],
    out_dir: str | Path,
    *,
    now: datetime | None = None,
) -> EventAlphaEvalExportResult:
    extraction_cases: list[dict[str, Any]] = []
    alpha_cases: list[dict[str, Any]] = []
    for row in missed_rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("failure_stage") == "resolver_missed_asset":
            extraction_cases.append(_missed_extraction_case(row))
        alpha_cases.append(_missed_alpha_case(row))
    return _write_cases(
        out_dir,
        {
            "proposed_llm_extraction_golden_cases.json": extraction_cases,
            "proposed_event_alpha_golden_cases.json": alpha_cases,
        },
        "missed",
        now=now,
    )


def format_eval_export_result(result: EventAlphaEvalExportResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT ALPHA PROPOSED EVAL CASES EXPORTED (research-only)",
        "=" * 76,
        f"source: {result.source}",
        f"out_dir: {result.out_dir}",
        f"files_written: {len(result.files_written)} · proposed_cases={result.proposed_cases}",
        *(f"- {path}" for path in result.files_written),
        "Canonical fixtures were not modified.",
    ])


def _feedback_case(alert: Mapping[str, Any], feedback: Mapping[str, Any]) -> dict[str, Any]:
    label = str(feedback.get("label") or "")
    expected_role = "source_noise" if label == "junk" else str(alert.get("llm_asset_role") or alert.get("asset_role") or "ambiguous")
    expected_action = "store_only" if label == "junk" else str(alert.get("tier") or "radar_digest").lower()
    return _redact({
        "case_id": f"feedback_{alert.get('alert_key') or alert.get('snapshot_id')}",
        "source": "feedback_export",
        "label": label,
        "title": alert.get("event_name"),
        "body": alert.get("reason"),
        "source_url": alert.get("source_url"),
        "symbol": alert.get("asset_symbol"),
        "coin_id": alert.get("asset_coin_id"),
        "expected_asset_role": expected_role,
        "expected_relationship_type": alert.get("llm_relationship_type") or alert.get("relationship_type"),
        "expected_recommended_alert_action": expected_action,
        "feedback_notes": feedback.get("notes"),
    })


def _missed_extraction_case(row: Mapping[str, Any]) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "")
    name = str(row.get("name") or row.get("coin_id") or symbol)
    return _redact({
        "case_id": f"missed_extraction_{symbol or row.get('coin_id')}",
        "source": "missed_export",
        "title": f"{name} missed opportunity follow-up",
        "body": row.get("reason"),
        "expected_crypto_asset_mentions": [{
            "symbol": symbol,
            "coin_id": row.get("coin_id"),
            "name": name,
            "mention_type": "project_or_token",
        }],
        "suggested_queries": list(row.get("suggested_queries") or []),
    })


def _missed_alpha_case(row: Mapping[str, Any]) -> dict[str, Any]:
    return _redact({
        "case_id": f"missed_alpha_{row.get('symbol') or row.get('coin_id')}_{row.get('move_window')}",
        "source": "missed_export",
        "symbol": row.get("symbol"),
        "coin_id": row.get("coin_id"),
        "move_window": row.get("move_window"),
        "return_pct": row.get("return_pct"),
        "expected_failure_stage": row.get("failure_stage"),
        "suggested_queries": list(row.get("suggested_queries") or []),
    })


def _write_cases(
    out_dir: str | Path,
    files: Mapping[str, list[dict[str, Any]]],
    source: str,
    *,
    now: datetime | None,
) -> EventAlphaEvalExportResult:
    target = Path(out_dir).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    generated = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    written: list[Path] = []
    total = 0
    for filename, cases in files.items():
        payload = {
            "schema_version": "event_alpha_proposed_eval_cases_v1",
            "generated_at": generated,
            "source": source,
            "cases": cases,
        }
        path = target / filename
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
        total += len(cases)
    return EventAlphaEvalExportResult(target, tuple(written), total, source)


def _redact(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        text = str(value)
        if "OPENAI_API_KEY" in text or "TELEGRAM_BOT_TOKEN" in text or ".env" in text:
            out[str(key)] = "[redacted]"
        else:
            out[str(key)] = value
    return out
