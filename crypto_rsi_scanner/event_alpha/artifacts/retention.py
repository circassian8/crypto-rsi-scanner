"""Retention/pruning helpers for Event Alpha research artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping

from . import locks as event_alpha_locks
from . import operator_state as event_alpha_operator_state


CORE_OPPORTUNITIES_FILENAME = "event_core_opportunities.jsonl"
IMPACT_HYPOTHESES_FILENAME = "event_impact_hypotheses.jsonl"
INCIDENTS_FILENAME = "event_incidents.jsonl"
WATCHLIST_FILENAME = "event_watchlist_state.jsonl"
NOTIFICATION_DELIVERIES_FILENAME = "event_alpha_notification_deliveries.jsonl"
NOTIFICATION_RUNS_FILENAME = "event_alpha_notification_runs.jsonl"
EVIDENCE_ACQUISITION_FILENAME = "event_evidence_acquisition.jsonl"

_GENERATION_FIELDS = (
    "run_id",
    "generation_id",
    "notification_run_id",
    "cycle_id",
    "snapshot_id",
)


@dataclass(frozen=True)
class EventAlphaRetentionConfig:
    runs_path: Path
    alerts_path: Path
    cards_dir: Path
    namespace_dir: Path | None = None
    run_days: int = 90
    alert_days: int = 180
    card_days: int = 180
    keep_eval_cases: bool = True
    store_days: int | None = None
    core_opportunities_path: Path | None = None
    impact_hypotheses_path: Path | None = None
    incidents_path: Path | None = None
    watchlist_path: Path | None = None
    notification_deliveries_path: Path | None = None
    notification_runs_path: Path | None = None
    evidence_acquisition_path: Path | None = None


@dataclass(frozen=True)
class EventAlphaRetentionResult:
    dry_run: bool
    runs_pruned: int = 0
    alerts_pruned: int = 0
    cards_pruned: int = 0
    core_opportunities_pruned: int = 0
    impact_hypotheses_pruned: int = 0
    incidents_pruned: int = 0
    watchlist_pruned: int = 0
    notification_deliveries_pruned: int = 0
    notification_runs_pruned: int = 0
    evidence_acquisition_pruned: int = 0
    mutation_blocked: bool = False
    malformed_files: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _JsonlRetentionPlan:
    name: str
    path: Path
    kept_rows: tuple[dict[str, Any], ...] = ()
    pruned: int = 0
    latest_generation: str | None = None
    malformed_reason: str | None = None
    fingerprint: _FileFingerprint | None = None


@dataclass(frozen=True)
class _FileFingerprint:
    exists: bool
    device: int | None = None
    inode: int | None = None
    size: int | None = None
    mtime_ns: int | None = None
    sha256: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class _CardRetentionPlan:
    root: Path
    cutoff: datetime
    prunable_paths: tuple[Path, ...] = ()
    fingerprints: tuple[tuple[Path, _FileFingerprint], ...] = ()
    current_run_id: str | None = None
    operator_state_run_id: str | None = None
    protected_names: tuple[str, ...] = ()
    index_path: Path | None = None
    index_text: str | None = None
    blocking_reasons: tuple[str, ...] = ()


def prune_event_alpha_artifacts(
    cfg: EventAlphaRetentionConfig,
    *,
    confirm: bool = False,
    now: datetime | None = None,
) -> EventAlphaRetentionResult:
    """Plan or prune local artifacts; dry-run unless ``confirm`` is true.

    Every JSONL file is parsed before any mutation. A malformed row blocks the
    entire confirmed pass so a partial rewrite cannot silently discard evidence.
    The latest append generation in every store is retained even when it falls
    outside the configured age window.
    """
    observed = _as_utc(now or datetime.now(timezone.utc))
    if not confirm:
        result, _changed = _prune_event_alpha_artifacts_unlocked(
            cfg,
            confirm=False,
            observed=observed,
        )
        return result

    base_dir = _canonical_namespace_dir(cfg)
    profile, namespace = _retention_lock_identity(base_dir)
    retention_run_id = f"retention-{observed.strftime('%Y%m%dT%H%M%S%fZ')}-{os.getpid()}"
    lock = event_alpha_locks.acquire_run_lock(
        SimpleNamespace(namespace_dir=base_dir),
        cfg=event_alpha_locks.EventAlphaRunLockConfig(
            enabled=True,
            stale_minutes=24.0 * 60.0,
            allow_overlap=False,
        ),
        run_id=retention_run_id,
        profile=profile,
        namespace=namespace,
        command="retention",
        lock_name="notify",
        now=observed,
    )
    if not lock.acquired or not lock.owned:
        result, _changed = _prune_event_alpha_artifacts_unlocked(
            cfg,
            confirm=False,
            observed=observed,
        )
        reason = f"retention confirmation blocked: {lock.status.message}"
        return replace(
            result,
            mutation_blocked=True,
            warnings=tuple(dict.fromkeys((*result.warnings, *lock.warnings, reason))),
        )

    mutation_lock = event_alpha_locks.acquire_artifact_mutation_lock(
        SimpleNamespace(namespace_dir=base_dir),
        run_id=retention_run_id,
        profile=profile,
        namespace=namespace,
        command="retention",
        now=observed,
    )
    if not mutation_lock.owned:
        result, _changed = _prune_event_alpha_artifacts_unlocked(
            cfg,
            confirm=False,
            observed=observed,
        )
        notify_released = event_alpha_locks.release_run_lock(lock)
        reason = f"retention confirmation blocked: {mutation_lock.status.message}"
        release_warning = () if notify_released else ("retention notify lock release was not confirmed",)
        return replace(
            result,
            mutation_blocked=True,
            warnings=tuple(
                dict.fromkeys(
                    (*result.warnings, *mutation_lock.warnings, reason, *release_warning)
                )
            ),
        )

    changed = False
    try:
        result, changed = _prune_event_alpha_artifacts_unlocked(
            cfg,
            confirm=True,
            observed=observed,
        )
        if changed:
            try:
                from ..namespace import status as event_alpha_namespace_status

                event_alpha_namespace_status.refresh_namespace_status(
                    base_dir,
                    profile=profile,
                    artifact_namespace=namespace,
                    now=observed,
                )
            except (OSError, ValueError) as exc:
                result = replace(
                    result,
                    warnings=tuple(
                        dict.fromkeys(
                            (
                                *result.warnings,
                                f"namespace status refresh failed after retention: {type(exc).__name__}",
                            )
                        )
                    ),
                )
    finally:
        mutation_released = event_alpha_locks.release_run_lock(mutation_lock)
        released = event_alpha_locks.release_run_lock(lock)
    if lock.warnings:
        result = replace(
            result,
            warnings=tuple(dict.fromkeys((*result.warnings, *lock.warnings))),
        )
    if not released:
        result = replace(
            result,
            warnings=tuple(dict.fromkeys((*result.warnings, "retention notify lock release was not confirmed"))),
        )
    if not mutation_released:
        result = replace(
            result,
            warnings=tuple(
                dict.fromkeys((*result.warnings, "retention artifact mutation lock release was not confirmed"))
            ),
        )
    return result


def _prune_event_alpha_artifacts_unlocked(
    cfg: EventAlphaRetentionConfig,
    *,
    confirm: bool,
    observed: datetime,
) -> tuple[EventAlphaRetentionResult, bool]:
    """Plan/apply one pass; confirmed callers must hold the notify lock."""

    warnings: list[str] = []
    base_dir = _canonical_namespace_dir(cfg)
    store_days = cfg.alert_days if cfg.store_days is None else cfg.store_days
    specs = (
        (
            "runs",
            cfg.runs_path,
            cfg.run_days,
            ("finished_at", "started_at", "observed_at", "generated_at", "created_at"),
        ),
        (
            "alerts",
            cfg.alerts_path,
            cfg.alert_days,
            ("observed_at", "trigger_observed_at", "event_time", "generated_at", "created_at"),
        ),
        (
            "core_opportunities",
            _store_path(cfg.core_opportunities_path, base_dir, CORE_OPPORTUNITIES_FILENAME),
            store_days,
            ("generated_at", "observed_at", "created_at"),
        ),
        (
            "impact_hypotheses",
            _store_path(cfg.impact_hypotheses_path, base_dir, IMPACT_HYPOTHESES_FILENAME),
            store_days,
            ("observed_at", "created_at", "generated_at"),
        ),
        (
            "incidents",
            _store_path(cfg.incidents_path, base_dir, INCIDENTS_FILENAME),
            store_days,
            ("observed_at", "updated_at", "created_at", "generated_at"),
        ),
        (
            "watchlist",
            _store_path(cfg.watchlist_path, base_dir, WATCHLIST_FILENAME),
            store_days,
            ("last_seen_at", "first_seen_at", "observed_at", "generated_at"),
        ),
        (
            "notification_deliveries",
            _store_path(cfg.notification_deliveries_path, base_dir, NOTIFICATION_DELIVERIES_FILENAME),
            store_days,
            ("delivered_at", "attempted_at", "observed_at", "generated_at", "created_at"),
        ),
        (
            "notification_runs",
            _store_path(cfg.notification_runs_path, base_dir, NOTIFICATION_RUNS_FILENAME),
            store_days,
            ("finished_at", "started_at", "observed_at", "generated_at", "created_at"),
        ),
        (
            "evidence_acquisition",
            _store_path(cfg.evidence_acquisition_path, base_dir, EVIDENCE_ACQUISITION_FILENAME),
            store_days,
            ("observed_at", "generated_at", "created_at"),
        ),
    )
    plans = tuple(
        _plan_jsonl(
            name,
            path,
            cutoff=observed - timedelta(days=max(0, days)),
            timestamp_fields=timestamp_fields,
        )
        for name, path, days, timestamp_fields in specs
    )
    malformed, path_reasons = _retention_plan_warnings(warnings, plans, base_dir, specs, cfg.cards_dir)
    current_run_id, operator_state_run_id, protected_card_names = _current_card_generation(base_dir, plans)
    card_plan = _plan_cards(
        cfg.cards_dir,
        cutoff=observed - timedelta(days=max(0, cfg.card_days)),
        current_run_id=current_run_id,
        operator_state_run_id=operator_state_run_id,
        protected_names=protected_card_names,
        observed=observed,
    )
    for reason in card_plan.blocking_reasons:
        warnings.append(f"retention blocked: {reason}")
    mutation_blocked = bool(malformed or path_reasons or card_plan.blocking_reasons)
    if confirm and not mutation_blocked:
        changed_reasons = _revalidate_retention_plan(plans, card_plan, namespace_dir=base_dir)
        if changed_reasons:
            mutation_blocked = True
            warnings.extend(f"retention blocked: {reason}" for reason in changed_reasons)
    will_change = bool(card_plan.prunable_paths or any(plan.pruned for plan in plans))
    if confirm and not mutation_blocked and will_change:
        loaded = event_alpha_operator_state.load_operator_state(base_dir)
        if loaded.valid:
            try:
                event_alpha_operator_state.invalidate_operator_state(
                    base_dir,
                    reason="retention_pruned_research_artifacts",
                    updated_at=observed,
                    expected_run_id=str((loaded.state or {}).get("run_id") or ""),
                    expected_revision=int((loaded.state or {}).get("revision") or 0),
                )
            except (OSError, ValueError) as exc:
                mutation_blocked = True
                warnings.append(
                    "retention blocked: operator state could not be invalidated "
                    f"before mutation ({type(exc).__name__})"
                )
        elif loaded.exists:
            warnings.append("operator state already invalid before retention; doctor cannot be current")
    if confirm and mutation_blocked:
        warnings.append("confirmation refused; changed or malformed evidence left every artifact unchanged")
    changed = False
    cards_pruned = len(card_plan.prunable_paths)
    if confirm and not mutation_blocked:
        if card_plan.prunable_paths and card_plan.index_path is not None and card_plan.index_text is not None:
            _write_text_atomic(card_plan.index_path, card_plan.index_text)
            changed = True
        for plan in plans:
            if plan.pruned:
                _write_jsonl_atomic(plan.path, plan.kept_rows)
                changed = True
        cards_pruned = _delete_cards(card_plan.prunable_paths, warnings=warnings)
        changed = changed or cards_pruned > 0
    if cfg.keep_eval_cases:
        warnings.append("canonical fixtures and proposed eval cases were not pruned")
    counts = {plan.name: plan.pruned for plan in plans}
    return EventAlphaRetentionResult(
        dry_run=not confirm or mutation_blocked,
        runs_pruned=counts["runs"],
        alerts_pruned=counts["alerts"],
        cards_pruned=cards_pruned,
        core_opportunities_pruned=counts["core_opportunities"],
        impact_hypotheses_pruned=counts["impact_hypotheses"],
        incidents_pruned=counts["incidents"],
        watchlist_pruned=counts["watchlist"],
        notification_deliveries_pruned=counts["notification_deliveries"],
        notification_runs_pruned=counts["notification_runs"],
        evidence_acquisition_pruned=counts["evidence_acquisition"],
        mutation_blocked=mutation_blocked,
        malformed_files=malformed,
        warnings=tuple(dict.fromkeys(warnings)),
    ), changed


def format_retention_report(result: EventAlphaRetentionResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA ARTIFACT RETENTION (research artifacts only)",
        "=" * 76,
        f"mode: {'blocked' if result.mutation_blocked else ('dry-run' if result.dry_run else 'confirmed')}",
        f"runs_pruned={result.runs_pruned} · alerts_pruned={result.alerts_pruned} · cards_pruned={result.cards_pruned}",
        (
            "append_only_pruned: "
            f"core={result.core_opportunities_pruned} · "
            f"hypotheses={result.impact_hypotheses_pruned} · "
            f"incidents={result.incidents_pruned} · "
            f"watchlist={result.watchlist_pruned} · "
            f"notification_deliveries={result.notification_deliveries_pruned} · "
            f"notification_runs={result.notification_runs_pruned} · "
            f"evidence_acquisition={result.evidence_acquisition_pruned}"
        ),
    ]
    if result.mutation_blocked:
        lines.append("No files were changed because retention safety checks blocked confirmation.")
    elif result.dry_run:
        lines.append("No files were changed. Re-run with --confirm to prune.")
    if result.warnings:
        lines.append("warnings: " + "; ".join(result.warnings))
    lines.append("Canonical fixtures, live DB rows, paper trades, and normal RSI data are untouched.")
    return "\n".join(lines)


def _plan_jsonl(
    name: str,
    path: Path,
    *,
    cutoff: datetime,
    timestamp_fields: tuple[str, ...],
) -> _JsonlRetentionPlan:
    p = path.expanduser()
    before = _file_fingerprint(p)
    if before.error:
        return _JsonlRetentionPlan(
            name=name,
            path=p,
            malformed_reason=f"{p.name}: fingerprint failed ({before.error})",
            fingerprint=before,
        )
    if not before.exists:
        return _JsonlRetentionPlan(name=name, path=p, fingerprint=before)
    rows, malformed_reason = _read_jsonl_strict(p)
    if malformed_reason:
        return _JsonlRetentionPlan(
            name=name,
            path=p,
            malformed_reason=malformed_reason,
            fingerprint=before,
        )
    after = _file_fingerprint(p)
    if after != before:
        return _JsonlRetentionPlan(
            name=name,
            path=p,
            malformed_reason=f"{p.name}: changed while retention was planning",
            fingerprint=before,
        )
    latest_generation = _latest_generation_marker(rows, timestamp_fields)
    kept: list[dict[str, Any]] = []
    pruned = 0
    for index, row in enumerate(rows):
        ts = _first_timestamp(row, timestamp_fields)
        if (
            ts is not None
            and ts < cutoff
            and not _belongs_to_latest_generation(
                row,
                index=index,
                timestamp_fields=timestamp_fields,
                marker=latest_generation,
            )
        ):
            pruned += 1
        else:
            kept.append(row)
    return _JsonlRetentionPlan(
        name=name,
        path=p,
        kept_rows=tuple(kept),
        pruned=pruned,
        latest_generation=_format_generation_marker(latest_generation),
        fingerprint=after,
    )


def _plan_cards(
    cards_dir: Path,
    *,
    cutoff: datetime,
    current_run_id: str | None,
    operator_state_run_id: str | None,
    protected_names: tuple[str, ...],
    observed: datetime,
) -> _CardRetentionPlan:
    root = cards_dir.expanduser()
    if not root.exists():
        return _CardRetentionPlan(
            root=root,
            cutoff=cutoff,
            current_run_id=current_run_id,
            operator_state_run_id=operator_state_run_id,
            protected_names=protected_names,
        )
    try:
        markdown_paths = tuple(sorted(root.glob("*.md")))
    except OSError as exc:
        return _CardRetentionPlan(
            root=root,
            cutoff=cutoff,
            current_run_id=current_run_id,
            operator_state_run_id=operator_state_run_id,
            protected_names=protected_names,
            blocking_reasons=(f"research-card listing failed ({type(exc).__name__})",),
        )
    fingerprints: list[tuple[Path, _FileFingerprint]] = []
    prunable: list[Path] = []
    blockers: list[str] = []
    for path in markdown_paths:
        before = _file_fingerprint(path)
        if before.error:
            fingerprints.append((path, before))
            blockers.append(f"card fingerprint failed for {path.name} ({before.error})")
            continue
        if path.name == "index.md":
            fingerprints.append((path, before))
            continue
        try:
            should_prune = _card_is_prunable(
                path,
                fingerprint=before,
                cutoff=cutoff,
                current_run_id=current_run_id,
                protected_names=protected_names,
            )
        except OSError as exc:
            blockers.append(f"card read failed for {path.name} ({type(exc).__name__})")
            should_prune = False
        after = _file_fingerprint(path)
        fingerprints.append((path, after))
        if after != before:
            blockers.append(f"{path.name}: changed while retention was planning")
            continue
        if should_prune:
            prunable.append(path)
    index_path = root / "index.md"
    if all(path != index_path for path, _fingerprint in fingerprints):
        fingerprints.append((index_path, _file_fingerprint(index_path)))
    index_text: str | None = None
    if prunable and not blockers:
        try:
            from . import research_cards as event_research_cards

            remaining = [
                path
                for path in markdown_paths
                if path.name != "index.md" and path not in prunable
            ]
            groups = event_research_cards._parse_index_groups(index_path)
            index_text = event_research_cards._render_index(remaining, observed, card_groups=groups)
        except OSError as exc:
            blockers.append(f"research-card index planning failed ({type(exc).__name__})")
    return _CardRetentionPlan(
        root=root,
        cutoff=cutoff,
        prunable_paths=tuple(prunable),
        fingerprints=tuple(fingerprints),
        current_run_id=current_run_id,
        operator_state_run_id=operator_state_run_id,
        protected_names=protected_names,
        index_path=index_path,
        index_text=index_text,
        blocking_reasons=tuple(blockers),
    )


def _retention_lock_identity(namespace_dir: Path) -> tuple[str, str]:
    loaded = event_alpha_operator_state.load_operator_state(namespace_dir)
    state = loaded.state if loaded.valid and loaded.state is not None else {}
    profile = str(state.get("profile") or "default")
    namespace = str(state.get("artifact_namespace") or namespace_dir.name or "default")
    return profile, namespace


def _current_card_generation(
    namespace_dir: Path,
    plans: tuple[_JsonlRetentionPlan, ...],
) -> tuple[str | None, str | None, tuple[str, ...]]:
    loaded = event_alpha_operator_state.load_operator_state(namespace_dir)
    state_run_id = (
        str((loaded.state or {}).get("run_id") or "").strip()
        if loaded.valid
        else ""
    )
    runs_plan = next((plan for plan in plans if plan.name == "runs"), None)
    latest_run = runs_plan.kept_rows[-1] if runs_plan and runs_plan.kept_rows else {}
    current_run_id = state_run_id or str(latest_run.get("run_id") or "").strip() or None
    protected_names: list[str] = []
    for field in ("research_card_paths", "card_paths", "canonical_card_paths"):
        raw = latest_run.get(field)
        values = raw if isinstance(raw, (list, tuple, set)) else (raw,)
        for value in values:
            text = str(value or "").strip()
            if text:
                protected_names.append(Path(text).name)
    return current_run_id, state_run_id or None, tuple(dict.fromkeys(protected_names))


def _card_is_prunable(
    path: Path,
    *,
    fingerprint: _FileFingerprint,
    cutoff: datetime,
    current_run_id: str | None,
    protected_names: tuple[str, ...],
) -> bool:
    if not fingerprint.exists or fingerprint.mtime_ns is None or fingerprint.error:
        return False
    modified = datetime.fromtimestamp(fingerprint.mtime_ns / 1_000_000_000, tz=timezone.utc)
    if modified >= cutoff or path.name in protected_names:
        return False
    embedded_run_id = _card_run_id(path)
    return not (current_run_id and embedded_run_id == current_run_id)


def _card_run_id(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"(?im)^-\s*Run ID:\s*(.+?)\s*$", text)
    if match is None:
        return None
    value = match.group(1).strip()
    return value if value and value.casefold() not in {"none", "legacy_lineage_missing"} else None


def _revalidate_retention_plan(
    plans: tuple[_JsonlRetentionPlan, ...],
    cards: _CardRetentionPlan,
    *,
    namespace_dir: Path,
) -> tuple[str, ...]:
    """Recheck every planned artifact before the first confirmed mutation."""

    reasons: list[str] = []
    for plan in plans:
        current = _file_fingerprint(plan.path)
        if plan.fingerprint is None or current != plan.fingerprint:
            reasons.append(f"{plan.path.name}: changed after retention planning")
    for path, planned in cards.fingerprints:
        current = _file_fingerprint(path)
        if current != planned:
            reasons.append(f"{path.name}: changed after retention planning")
    loaded = event_alpha_operator_state.load_operator_state(namespace_dir)
    current_state_run_id = (
        str((loaded.state or {}).get("run_id") or "").strip()
        if loaded.valid
        else None
    )
    if current_state_run_id != cards.operator_state_run_id:
        reasons.append("operator-state current generation changed after retention planning")
    for path in cards.prunable_paths:
        planned = dict(cards.fingerprints).get(path)
        if planned is None:
            reasons.append(f"{path.name}: missing planned card fingerprint")
            continue
        try:
            still_prunable = _card_is_prunable(
                path,
                fingerprint=planned,
                cutoff=cards.cutoff,
                current_run_id=cards.current_run_id,
                protected_names=cards.protected_names,
            )
        except OSError:
            still_prunable = False
        if _file_fingerprint(path) != planned:
            reasons.append(f"{path.name}: changed while card eligibility was rechecked")
            continue
        if not still_prunable:
            reasons.append(f"{path.name}: no longer eligible for card retention")
    return tuple(dict.fromkeys(reasons))


def _file_fingerprint(path: Path) -> _FileFingerprint:
    try:
        before = path.stat()
    except FileNotFoundError:
        return _FileFingerprint(exists=False)
    except OSError as exc:
        return _FileFingerprint(exists=True, error=type(exc).__name__)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.stat()
    except OSError as exc:
        return _FileFingerprint(exists=True, error=type(exc).__name__)
    before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_identity != after_identity:
        return _FileFingerprint(exists=True, error="changed_during_fingerprint")
    return _FileFingerprint(
        exists=True,
        device=after.st_dev,
        inode=after.st_ino,
        size=after.st_size,
        mtime_ns=after.st_mtime_ns,
        sha256=digest.hexdigest(),
    )


def _read_jsonl_strict(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line_number, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    return [], f"{path.name}: line {line_number} is invalid JSON"
                if not isinstance(parsed, dict):
                    return [], f"{path.name}: line {line_number} is not a JSON object"
                rows.append(parsed)
    except OSError as exc:
        return [], f"{path.name}: read failed ({type(exc).__name__})"
    return rows, None


def _latest_generation_marker(
    rows: list[dict[str, Any]],
    timestamp_fields: tuple[str, ...],
) -> tuple[str, object] | None:
    if not rows:
        return None
    latest = rows[-1]
    for field in _GENERATION_FIELDS:
        value = str(latest.get(field) or "").strip()
        if value:
            return field, value
    timestamp = _first_timestamp(latest, timestamp_fields)
    if timestamp is not None:
        return "__timestamp__", timestamp
    return "__row_index__", len(rows) - 1


def _belongs_to_latest_generation(
    row: Mapping[str, Any],
    *,
    index: int,
    timestamp_fields: tuple[str, ...],
    marker: tuple[str, object] | None,
) -> bool:
    if marker is None:
        return False
    field, value = marker
    if field == "__row_index__":
        return index == value
    if field == "__timestamp__":
        return _first_timestamp(row, timestamp_fields) == value
    return str(row.get(field) or "").strip() == value


def _format_generation_marker(marker: tuple[str, object] | None) -> str | None:
    if marker is None:
        return None
    field, value = marker
    if isinstance(value, datetime):
        value = value.isoformat()
    return f"{field}={value}"


def _write_jsonl_atomic(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original_mode = path.stat().st_mode & 0o777
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".retention.tmp",
            delete=False,
        ) as fh:
            temp_name = fh.name
            for row in rows:
                fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
                fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(temp_name, original_mode)
        os.replace(temp_name, path)
        temp_name = None
        _fsync_directory(path.parent)
    finally:
        if temp_name is not None:
            try:
                Path(temp_name).unlink()
            except FileNotFoundError:
                pass


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original_mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".retention.tmp",
            delete=False,
        ) as fh:
            temp_name = fh.name
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(temp_name, original_mode)
        os.replace(temp_name, path)
        temp_name = None
        _fsync_directory(path.parent)
    finally:
        if temp_name is not None:
            try:
                Path(temp_name).unlink()
            except FileNotFoundError:
                pass


def _delete_cards(paths: Iterable[Path], *, warnings: list[str]) -> int:
    deleted = 0
    parents: set[Path] = set()
    for path in paths:
        try:
            path.unlink()
            deleted += 1
            parents.add(path.parent)
        except OSError as exc:
            warnings.append(f"card prune failed for {path}: {exc}")
    for parent in parents:
        _fsync_directory(parent)
    return deleted


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _store_path(configured: Path | None, base_dir: Path, filename: str) -> Path:
    return configured.expanduser() if configured is not None else base_dir / filename


def _canonical_namespace_dir(cfg: EventAlphaRetentionConfig) -> Path:
    """Return the lock/state identity independently from any custom artifact path."""

    return (
        cfg.namespace_dir.expanduser()
        if cfg.namespace_dir is not None
        else cfg.runs_path.expanduser().parent
    )


def _retention_path_validation_reasons(
    namespace_dir: Path,
    specs: Iterable[tuple[str, Path, int, tuple[str, ...]]],
    cards_dir: Path,
) -> tuple[str, ...]:
    """Reject ambiguous/destructive path configurations before confirmation."""

    reasons: list[str] = []
    namespace = namespace_dir.expanduser().resolve(strict=False)
    if namespace.exists() and not namespace.is_dir():
        reasons.append("canonical namespace path is not a directory")
    seen: dict[Path, str] = {}
    forbidden = {
        (namespace / event_alpha_operator_state.OPERATOR_STATE_FILENAME).resolve(strict=False),
        (namespace / "event_alpha_namespace_status.json").resolve(strict=False),
    }
    for name, raw_path, _days, _timestamps in specs:
        path = raw_path.expanduser().resolve(strict=False)
        if path.suffix.casefold() != ".jsonl":
            reasons.append(f"{name}: retention target must be a .jsonl file")
        if path in forbidden:
            reasons.append(f"{name}: retention target overlaps lifecycle state")
        prior = seen.setdefault(path, name)
        if prior != name:
            reasons.append(f"{name}: retention target duplicates {prior}")
        if path.exists() and not path.is_file():
            reasons.append(f"{name}: retention target is not a file")
    cards = cards_dir.expanduser().resolve(strict=False)
    if cards in seen:
        reasons.append(f"cards: retention directory overlaps {seen[cards]}")
    if cards.exists() and not cards.is_dir():
        reasons.append("cards: retention target is not a directory")
    return tuple(dict.fromkeys(reasons))


def _retention_plan_warnings(
    warnings: list[str],
    plans: tuple[_JsonlRetentionPlan, ...],
    namespace_dir: Path,
    specs: tuple[tuple[str, Path, int, tuple[str, ...]], ...],
    cards_dir: Path,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    malformed = tuple(plan.path.name for plan in plans if plan.malformed_reason)
    warnings.extend(
        f"retention blocked: {plan.malformed_reason}"
        for plan in plans
        if plan.malformed_reason
    )
    path_reasons = _retention_path_validation_reasons(namespace_dir, specs, cards_dir)
    warnings.extend(f"retention blocked: {reason}" for reason in path_reasons)
    return malformed, path_reasons


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
