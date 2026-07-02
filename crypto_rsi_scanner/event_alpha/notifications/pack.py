"""Clean notification artifact export for Event Alpha day-1 review."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class NotificationPackExportResult:
    out_path: Path
    files_written: int
    warnings: tuple[str, ...] = ()


def export_notification_pack(
    *,
    out_path: str | Path,
    context: Any,
    notification_runs: Iterable[Mapping[str, Any]],
    delivery_rows: Iterable[Mapping[str, Any]],
    alert_rows: Iterable[Mapping[str, Any]],
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    go_no_go_text: str,
    environment_doctor_text: str,
    slo_text: str,
    daily_brief_text: str = "",
    cards_dir: str | Path | None = None,
) -> NotificationPackExportResult:
    """Write a redacted zip with notification artifacts and operator reports."""
    out = Path(out_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    warnings: list[str] = []
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        written += _write_text(zf, "README.md", _readme(context))
        written += _write_jsonl(zf, "artifacts/notification_runs.jsonl", notification_runs)
        written += _write_jsonl(zf, "artifacts/deliveries.jsonl", delivery_rows)
        written += _write_jsonl(zf, "artifacts/alert_snapshots.jsonl", alert_rows)
        written += _write_json(zf, "artifacts/provider_health.json", provider_health_rows)
        written += _write_text(zf, "reports/go_no_go.txt", go_no_go_text)
        written += _write_text(zf, "reports/environment_doctor.txt", environment_doctor_text)
        written += _write_text(zf, "reports/slo_report.txt", slo_text)
        if daily_brief_text:
            written += _write_text(zf, "reports/daily_brief.md", daily_brief_text)
        if cards_dir:
            card_root = Path(cards_dir).expanduser()
            if card_root.exists():
                for card in sorted(card_root.glob("*.md")):
                    try:
                        zf.writestr(f"research_cards/{card.name}", _redact_text(card.read_text(encoding="utf-8")))
                        written += 1
                    except OSError:
                        warnings.append(f"could not read card {card.name}")
            else:
                warnings.append("research cards directory missing")
    return NotificationPackExportResult(out_path=out, files_written=written, warnings=tuple(warnings))


def format_notification_pack_result(result: NotificationPackExportResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION PACK EXPORT",
        "=" * 76,
        f"out: {result.out_path}",
        f"files_written: {result.files_written}",
        "warnings:",
    ]
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("Export excludes .env, raw LLM caches, DBs, logs, and channel secrets.")
    return "\n".join(lines).rstrip()


def _write_text(zf: zipfile.ZipFile, name: str, text: str) -> int:
    zf.writestr(name, _redact_text(text or ""))
    return 1


def _write_json(zf: zipfile.ZipFile, name: str, value: Any) -> int:
    zf.writestr(name, json.dumps(_redact_json(value), sort_keys=True, indent=2))
    return 1


def _write_jsonl(zf: zipfile.ZipFile, name: str, rows: Iterable[Mapping[str, Any]]) -> int:
    body = "".join(json.dumps(_redact_json(dict(row)), sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    zf.writestr(name, body)
    return 1


def _readme(context: Any) -> str:
    return "\n".join([
        "# Event Alpha Notification Pack",
        "",
        "Research-only notification artifacts for operator review.",
        "",
        f"- profile: {getattr(context, 'profile', 'default')}",
        f"- artifact_namespace: {getattr(context, 'artifact_namespace', 'default')}",
        "",
        "This pack intentionally excludes .env files, databases, logs, and raw LLM caches.",
        "",
    ])


def _redact_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, val in value.items():
            key_text = str(key)
            if any(token in key_text.lower() for token in ("token", "secret", "password", "api_key", "chat_id")):
                out[key_text] = "[redacted]" if val else val
            else:
                out[key_text] = _redact_json(val)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact_json(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(text: str) -> str:
    out = str(text or "")
    return re.sub(
        r"(?i)\b(OPENAI_API_KEY|TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID|TELEGRAM_CHAT_IDS|api[_-]?key|token|secret|password)\s*=\s*\S+",
        lambda match: f"{match.group(1)}=[redacted]",
        out,
    )
