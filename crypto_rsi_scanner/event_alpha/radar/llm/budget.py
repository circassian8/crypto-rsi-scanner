"""Persistent research-only LLM budget ledger for Event Alpha runs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

log = logging.getLogger(__name__)

LLM_BUDGET_SCHEMA_VERSION = "event_llm_budget_v1"


@dataclass(frozen=True)
class EventLLMBudgetConfig:
    ledger_path: Path | None = None
    estimated_cost_per_call_usd: float = 0.0
    max_calls_per_run: int = 0
    max_calls_per_day: int = 0
    max_estimated_cost_usd_per_day: float = 0.0


@dataclass(frozen=True)
class EventLLMBudgetSnapshot:
    cache_hits: int = 0
    cache_misses: int = 0
    calls_attempted: int = 0
    calls_succeeded: int = 0
    calls_failed: int = 0
    skipped_due_budget: int = 0
    skipped_due_provider_backoff: int = 0
    warning: str | None = None


class EventLLMBudgetRunTracker:
    """Track run and day-level LLM usage without making provider calls itself."""

    def __init__(
        self,
        *,
        cfg: EventLLMBudgetConfig,
        provider: str,
        model: str | None,
        prompt_version: str,
        call_kind: str,
        now: datetime | None = None,
    ) -> None:
        self.cfg = cfg
        self.provider = provider
        self.model = model or ""
        self.prompt_version = prompt_version
        self.call_kind = call_kind
        self.date = _as_utc(now or datetime.now(timezone.utc)).date().isoformat()
        self.entry, self.warning = _load_entry(cfg.ledger_path, self.date, provider, self.model, prompt_version)
        self.run_calls = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.skipped = 0
        self.skipped_provider_backoff = 0
        self.calls_succeeded = 0
        self.calls_failed = 0

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        self.cache_misses += 1

    def can_attempt(self) -> bool:
        if self.cfg.max_calls_per_run and self.run_calls >= self.cfg.max_calls_per_run:
            return False
        attempted_today = _int(self.entry.get("extractor_calls_attempted")) + _int(
            self.entry.get("relationship_calls_attempted")
        )
        if self.cfg.max_calls_per_day and attempted_today + self.run_calls >= self.cfg.max_calls_per_day:
            return False
        estimated_today = _float(self.entry.get("estimated_cost_usd"))
        estimated_next = estimated_today + (self.run_calls + 1) * max(0.0, self.cfg.estimated_cost_per_call_usd)
        if self.cfg.max_estimated_cost_usd_per_day and estimated_next > self.cfg.max_estimated_cost_usd_per_day:
            return False
        return True

    def record_attempt(self) -> None:
        self.run_calls += 1

    def record_result(self, *, success: bool) -> None:
        if success:
            self.calls_succeeded += 1
        else:
            self.calls_failed += 1

    def record_skipped(self) -> None:
        self.skipped += 1

    def record_provider_backoff(self) -> None:
        self.skipped_provider_backoff += 1

    def exhausted_warning(self) -> str:
        return "LLM skipped: persistent daily/run budget exhausted"

    def flush(self) -> EventLLMBudgetSnapshot:
        if self.cfg.ledger_path is None:
            return _budget_snapshot(self, warning=self.warning)
        warning = _flush_budget_tracker_entry(self)
        return _budget_snapshot(self, warning=warning)


def _flush_budget_tracker_entry(tracker: EventLLMBudgetRunTracker) -> str | None:
    entry = _updated_budget_entry(tracker)
    warning = tracker.warning
    try:
        _write_entry(tracker.cfg.ledger_path, entry)
    except Exception as exc:  # noqa: BLE001
        warning = f"LLM budget ledger write failed: {exc}"
        log.warning("%s", warning)
    return warning


def _updated_budget_entry(tracker: EventLLMBudgetRunTracker) -> dict[str, Any]:
    entry = dict(tracker.entry)
    entry["schema_version"] = LLM_BUDGET_SCHEMA_VERSION
    entry["date"] = tracker.date
    entry["provider"] = tracker.provider
    entry["model"] = tracker.model
    entry["prompt_version"] = tracker.prompt_version
    entry["cache_hits"] = _int(entry.get("cache_hits")) + tracker.cache_hits
    entry["cache_misses"] = _int(entry.get("cache_misses")) + tracker.cache_misses
    entry["skipped_due_budget"] = _int(entry.get("skipped_due_budget")) + tracker.skipped
    entry["skipped_due_provider_backoff"] = (
        _int(entry.get("skipped_due_provider_backoff")) + tracker.skipped_provider_backoff
    )
    if tracker.call_kind == "extractor":
        entry["extractor_calls_attempted"] = _int(entry.get("extractor_calls_attempted")) + tracker.run_calls
        entry["extractor_calls_succeeded"] = _int(entry.get("extractor_calls_succeeded")) + tracker.calls_succeeded
        entry["extractor_calls_failed"] = _int(entry.get("extractor_calls_failed")) + tracker.calls_failed
    else:
        entry["relationship_calls_attempted"] = _int(entry.get("relationship_calls_attempted")) + tracker.run_calls
        entry["relationship_calls_succeeded"] = (
            _int(entry.get("relationship_calls_succeeded")) + tracker.calls_succeeded
        )
        entry["relationship_calls_failed"] = _int(entry.get("relationship_calls_failed")) + tracker.calls_failed
    entry["estimated_cost_usd"] = round(
        _float(entry.get("estimated_cost_usd"))
        + tracker.run_calls * max(0.0, tracker.cfg.estimated_cost_per_call_usd),
        6,
    )
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    return entry


def _budget_snapshot(tracker: EventLLMBudgetRunTracker, *, warning: str | None) -> EventLLMBudgetSnapshot:
    return EventLLMBudgetSnapshot(
        cache_hits=tracker.cache_hits,
        cache_misses=tracker.cache_misses,
        calls_attempted=tracker.run_calls,
        calls_succeeded=tracker.calls_succeeded,
        calls_failed=tracker.calls_failed,
        skipped_due_budget=tracker.skipped,
        skipped_due_provider_backoff=tracker.skipped_provider_backoff,
        warning=warning,
    )


def _load_entry(
    path: Path | None,
    date: str,
    provider: str,
    model: str,
    prompt_version: str,
) -> tuple[dict[str, Any], str | None]:
    empty = {
        "schema_version": LLM_BUDGET_SCHEMA_VERSION,
        "date": date,
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
        "extractor_calls_attempted": 0,
        "extractor_calls_succeeded": 0,
        "extractor_calls_failed": 0,
        "relationship_calls_attempted": 0,
        "relationship_calls_succeeded": 0,
        "relationship_calls_failed": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "skipped_due_budget": 0,
        "skipped_due_provider_backoff": 0,
        "estimated_cost_usd": 0.0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if path is None or not path.exists():
        return empty, None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return empty, f"LLM budget ledger read failed: {exc}"
    rows = raw.get("entries") if isinstance(raw, Mapping) else None
    if not isinstance(rows, list):
        return empty, "LLM budget ledger ignored: old or invalid format"
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if (
            str(row.get("date") or "") == date
            and str(row.get("provider") or "") == provider
            and str(row.get("model") or "") == model
            and str(row.get("prompt_version") or "") == prompt_version
        ):
            merged = dict(empty)
            merged.update(dict(row))
            return merged, None
    return empty, None


def _write_entry(path: Path, entry: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            existing = raw.get("entries") if isinstance(raw, Mapping) else []
            if isinstance(existing, list):
                rows = [dict(row) for row in existing if isinstance(row, Mapping)]
        except Exception:
            rows = []
    key = (
        str(entry.get("date") or ""),
        str(entry.get("provider") or ""),
        str(entry.get("model") or ""),
        str(entry.get("prompt_version") or ""),
    )
    replaced = False
    for idx, row in enumerate(rows):
        row_key = (
            str(row.get("date") or ""),
            str(row.get("provider") or ""),
            str(row.get("model") or ""),
            str(row.get("prompt_version") or ""),
        )
        if row_key == key:
            rows[idx] = dict(entry)
            replaced = True
            break
    if not replaced:
        rows.append(dict(entry))
    payload = {"schema_version": LLM_BUDGET_SCHEMA_VERSION, "entries": rows}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
