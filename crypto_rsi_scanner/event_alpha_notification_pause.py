"""Emergency pause switch for Event Alpha notification sends.

The pause is artifact-scoped and research-only. It blocks Telegram delivery
while still allowing discovery, run ledgers, and blocked delivery rows to be
written for audit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "event_alpha_notifications_pause_v1"


@dataclass(frozen=True)
class EventAlphaNotificationPauseState:
    paused: bool
    reason: str
    path: Path
    updated_at: str | None = None
    source: str = "none"


def pause_path_for_context(context: Any) -> Path:
    namespace_dir = Path(getattr(context, "namespace_dir", None) or getattr(context, "base_dir", Path(".")))
    return namespace_dir / "event_alpha_notifications_pause.json"


def read_pause_state(
    context: Any,
    *,
    env_paused: bool = False,
    env_reason: str = "",
) -> EventAlphaNotificationPauseState:
    """Return the effective pause state from env override plus namespace file."""
    path = pause_path_for_context(context)
    file_state = _read_file_state(path)
    if bool(env_paused):
        reason = str(env_reason or "").strip() or "RSI_EVENT_ALPHA_NOTIFICATIONS_PAUSED=1"
        return EventAlphaNotificationPauseState(True, reason, path, source="env")
    if file_state.get("paused"):
        reason = str(file_state.get("reason") or "").strip() or "pause file present"
        return EventAlphaNotificationPauseState(
            True,
            reason,
            path,
            updated_at=str(file_state.get("updated_at") or "") or None,
            source="file",
        )
    return EventAlphaNotificationPauseState(False, "", path, source="none")


def write_pause_state(
    context: Any,
    *,
    reason: str,
    now: datetime | None = None,
) -> EventAlphaNotificationPauseState:
    observed = _as_utc(now or datetime.now(timezone.utc))
    path = pause_path_for_context(context)
    row = {
        "schema_version": SCHEMA_VERSION,
        "paused": True,
        "reason": str(reason or "").strip() or "operator pause",
        "updated_at": observed.isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return EventAlphaNotificationPauseState(True, row["reason"], path, updated_at=row["updated_at"], source="file")


def clear_pause_state(context: Any, *, confirm: bool = False) -> EventAlphaNotificationPauseState:
    path = pause_path_for_context(context)
    if not confirm:
        current = _read_file_state(path)
        reason = str(current.get("reason") or "confirmation required")
        return EventAlphaNotificationPauseState(bool(current.get("paused")), reason, path, source="file")
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    return EventAlphaNotificationPauseState(False, "", path, source="none")


def format_pause_state(state: EventAlphaNotificationPauseState, *, action: str = "status") -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION PAUSE (research-only)",
        "=" * 76,
        f"action: {action}",
        f"paused: {_yes_no(state.paused)}",
        f"source: {state.source}",
        f"path: {state.path}",
    ]
    if state.reason:
        lines.append(f"reason: {state.reason}")
    if state.updated_at:
        lines.append(f"updated_at: {state.updated_at}")
    lines.append("Pause blocks Telegram sends only; discovery/report artifacts can still update.")
    return "\n".join(lines).rstrip()


def _read_file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"paused": True, "reason": "pause file unreadable"}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
