"""Retention/pruning helpers for Event Alpha research artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class EventAlphaRetentionConfig:
    runs_path: Path
    alerts_path: Path
    cards_dir: Path
    run_days: int = 90
    alert_days: int = 180
    card_days: int = 180
    keep_eval_cases: bool = True


@dataclass(frozen=True)
class EventAlphaRetentionResult:
    dry_run: bool
    runs_pruned: int = 0
    alerts_pruned: int = 0
    cards_pruned: int = 0
    warnings: tuple[str, ...] = ()


def prune_event_alpha_artifacts(
    cfg: EventAlphaRetentionConfig,
    *,
    confirm: bool = False,
    now: datetime | None = None,
) -> EventAlphaRetentionResult:
    """Prune old local artifacts; dry-run unless ``confirm`` is true."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    warnings: list[str] = []
    runs_pruned = _prune_jsonl(
        cfg.runs_path,
        cutoff=observed - timedelta(days=max(0, cfg.run_days)),
        timestamp_fields=("finished_at", "started_at", "observed_at"),
        confirm=confirm,
        warnings=warnings,
    )
    alerts_pruned = _prune_jsonl(
        cfg.alerts_path,
        cutoff=observed - timedelta(days=max(0, cfg.alert_days)),
        timestamp_fields=("observed_at", "trigger_observed_at", "event_time"),
        confirm=confirm,
        warnings=warnings,
    )
    cards_pruned = _prune_cards(
        cfg.cards_dir,
        cutoff=observed - timedelta(days=max(0, cfg.card_days)),
        confirm=confirm,
        warnings=warnings,
    )
    if cfg.keep_eval_cases:
        warnings.append("canonical fixtures and proposed eval cases were not pruned")
    return EventAlphaRetentionResult(
        dry_run=not confirm,
        runs_pruned=runs_pruned,
        alerts_pruned=alerts_pruned,
        cards_pruned=cards_pruned,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def format_retention_report(result: EventAlphaRetentionResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA ARTIFACT RETENTION (research artifacts only)",
        "=" * 76,
        f"mode: {'dry-run' if result.dry_run else 'confirmed'}",
        f"runs_pruned={result.runs_pruned} · alerts_pruned={result.alerts_pruned} · cards_pruned={result.cards_pruned}",
    ]
    if result.dry_run:
        lines.append("No files were changed. Re-run with --confirm to prune.")
    if result.warnings:
        lines.append("warnings: " + "; ".join(result.warnings))
    lines.append("Canonical fixtures, live DB rows, paper trades, and normal RSI data are untouched.")
    return "\n".join(lines)


def _prune_jsonl(
    path: Path,
    *,
    cutoff: datetime,
    timestamp_fields: tuple[str, ...],
    confirm: bool,
    warnings: list[str],
) -> int:
    p = path.expanduser()
    if not p.exists():
        return 0
    rows = _read_jsonl(p)
    kept: list[dict[str, Any]] = []
    pruned = 0
    for row in rows:
        ts = _first_timestamp(row, timestamp_fields)
        if ts is not None and ts < cutoff:
            pruned += 1
        else:
            kept.append(row)
    if confirm and pruned:
        with p.open("w", encoding="utf-8") as fh:
            for row in kept:
                fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
                fh.write("\n")
    return pruned


def _prune_cards(
    cards_dir: Path,
    *,
    cutoff: datetime,
    confirm: bool,
    warnings: list[str],
) -> int:
    root = cards_dir.expanduser()
    if not root.exists():
        return 0
    count = 0
    for path in root.glob("*.md"):
        if path.name == "index.md":
            continue
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError as exc:
            warnings.append(f"card stat failed for {path}: {exc}")
            continue
        if modified >= cutoff:
            continue
        count += 1
        if confirm:
            try:
                path.unlink()
            except OSError as exc:
                warnings.append(f"card prune failed for {path}: {exc}")
    return count


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def _first_timestamp(row: Mapping[str, Any], fields: Iterable[str]) -> datetime | None:
    for field in fields:
        parsed = _dt(row.get(field))
        if parsed is not None:
            return parsed
    return None


def _dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    return value
