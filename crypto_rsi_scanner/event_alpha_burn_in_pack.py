"""Clean burn-in export pack for Event Alpha research review."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alpha_artifacts


@dataclass(frozen=True)
class EventAlphaBurnInPackResult:
    path: Path
    files_written: int
    warnings: tuple[str, ...] = ()


REPORTS = {
    "daily_brief": "reports/daily_brief.md",
    "burn_in_scorecard": "reports/burn_in_scorecard.txt",
    "burn_in_checklist": "reports/burn_in_checklist.txt",
    "v1_readiness": "reports/v1_readiness.txt",
    "health_guard": "reports/health_guard.txt",
    "artifact_doctor": "reports/artifact_doctor.txt",
    "source_reliability": "reports/source_reliability.txt",
    "calibration": "reports/calibration.txt",
    "missed": "reports/missed_opportunities.txt",
    "tuning": "reports/tuning_worksheet.txt",
    "priors_shadow": "reports/priors_shadow.txt",
}


def export_burn_in_pack(
    out_path: str | Path,
    *,
    daily_brief: str = "",
    burn_in_scorecard: str = "",
    burn_in_checklist: str = "",
    v1_readiness: str = "",
    health_guard: str = "",
    artifact_doctor: str = "",
    source_reliability: str = "",
    calibration: str = "",
    missed: str = "",
    tuning: str = "",
    priors_shadow: str = "",
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    llm_budget_rows: Iterable[Mapping[str, Any]] = (),
    cards_dir: str | Path | None = None,
    proposed_eval_dir: str | Path | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    date_range: str | None = None,
) -> EventAlphaBurnInPackResult:
    """Write a clean zip for Pro-model/local review without secrets or caches."""
    target = Path(out_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    files = 0
    run_data = _filtered(run_rows, profile, artifact_namespace, include_test_artifacts)
    alert_data = _filtered(alert_rows, profile, artifact_namespace, include_test_artifacts)
    feedback_data = _filtered(feedback_rows, profile, artifact_namespace, include_test_artifacts)
    missed_data = _filtered(missed_rows, profile, artifact_namespace, include_test_artifacts)
    outcome_data = _filtered(outcome_rows, profile, artifact_namespace, include_test_artifacts)
    budget_data = _filtered(llm_budget_rows, profile, artifact_namespace, include_test_artifacts)
    manifest = {
        "profile": profile or "any",
        "artifact_namespace": artifact_namespace or "any",
        "date_range": date_range or "unspecified",
        "include_test_artifacts": bool(include_test_artifacts),
        "run_rows": len(run_data),
        "alert_rows": len(alert_data),
        "feedback_rows": len(feedback_data),
        "missed_rows": len(missed_data),
        "outcome_rows": len(outcome_data),
    }
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _writestr(zf, "manifest.json", json.dumps(_json_ready(manifest), indent=2, sort_keys=True) + "\n")
        files += 1
        for name, arcname in REPORTS.items():
            text = locals().get(name) or f"{name} report not available in this export.\n"
            _writestr(zf, arcname, _strip_sensitive(str(text).rstrip() + "\n"))
            files += 1
        artifacts = {
            "artifacts/run_rows.jsonl": run_data,
            "artifacts/alert_rows.jsonl": alert_data,
            "artifacts/feedback_rows.jsonl": feedback_data,
            "artifacts/missed_rows.jsonl": missed_data,
            "artifacts/outcome_rows.jsonl": outcome_data,
            "artifacts/llm_budget_rows.jsonl": budget_data,
        }
        for arcname, rows in artifacts.items():
            _write_jsonl(zf, arcname, rows)
            files += 1
        _writestr(
            zf,
            "artifacts/provider_health.json",
            json.dumps(_json_ready(provider_health_rows or {}), indent=2, sort_keys=True) + "\n",
        )
        files += 1
        files += _write_tree(zf, cards_dir, root_arc="cards", warnings=warnings)
        files += _write_tree(zf, proposed_eval_dir, root_arc="proposed_eval_cases", warnings=warnings)
        _writestr(zf, "README.md", _readme())
        files += 1
    return EventAlphaBurnInPackResult(path=target, files_written=files, warnings=tuple(dict.fromkeys(warnings)))


def _filtered(
    rows: Iterable[Mapping[str, Any]],
    profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
) -> list[dict[str, Any]]:
    return event_alpha_artifacts.filter_artifact_rows(
        rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
    )


def format_burn_in_pack_result(result: EventAlphaBurnInPackResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA BURN-IN PACK WRITTEN (research artifact only)",
        "=" * 76,
        f"path: {result.path}",
        f"files_written: {result.files_written}",
    ]
    if result.warnings:
        lines.extend(["warnings:", *(f"- {warning}" for warning in result.warnings)])
    lines.append("Export excludes secrets, DB files, logs, caches, virtualenvs, and raw ignored artifacts.")
    return "\n".join(lines).rstrip()


def _write_tree(
    zf: zipfile.ZipFile,
    root: str | Path | None,
    *,
    root_arc: str,
    warnings: list[str],
) -> int:
    if not root:
        return 0
    base = Path(root).expanduser()
    if not base.exists():
        warnings.append(f"{root_arc} source not found: {base}")
        return 0
    count = 0
    for path in sorted(base.rglob("*")):
        if not path.is_file() or not _safe_file(path):
            continue
        try:
            data = _strip_sensitive(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            warnings.append(f"skipped non-text artifact: {path.name}")
            continue
        rel = path.relative_to(base)
        _writestr(zf, str(Path(root_arc) / rel), data)
        count += 1
    return count


def _safe_file(path: Path) -> bool:
    parts = set(path.parts)
    if parts & {".git", ".venv", "__pycache__", ".pytest_cache", "event_fade_cache", "backups"}:
        return False
    name = path.name
    if name.startswith(".env") or name == ".DS_Store":
        return False
    if name.endswith((".db", ".db-wal", ".db-shm", ".log", ".pyc", ".zip")):
        return False
    return path.suffix.lower() in {".md", ".txt", ".json", ".jsonl", ".csv"}


def _write_jsonl(zf: zipfile.ZipFile, arcname: str, rows: Iterable[Mapping[str, Any]]) -> None:
    lines = [
        json.dumps(_json_ready(dict(row)), sort_keys=True, separators=(",", ":"))
        for row in rows
        if isinstance(row, Mapping)
    ]
    _writestr(zf, arcname, "\n".join(lines) + ("\n" if lines else ""))


def _writestr(zf: zipfile.ZipFile, arcname: str, text: str) -> None:
    info = zipfile.ZipInfo(arcname)
    info.date_time = (2026, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, _strip_sensitive(text))


def _strip_sensitive(text: str) -> str:
    out = str(text)
    replacements = {
        "OPENAI_API_KEY": "[redacted-openai-key-name]",
        "TELEGRAM_BOT_TOKEN": "[redacted-telegram-token-name]",
        "DISCORD_WEBHOOK_URL": "[redacted-discord-webhook-name]",
        ".env": "[env-file]",
    }
    for old, new in replacements.items():
        out = out.replace(old, new)
    return out


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _readme() -> str:
    return (
        "# Event Alpha Burn-In Pack\n\n"
        "This zip contains clean Event Alpha research reports and small local "
        "artifact excerpts for review. It is research-only: no live RSI signal "
        "rows, paper trades, execution state, secrets, local DBs, logs, caches, "
        "or virtualenv files are included.\n"
    )
