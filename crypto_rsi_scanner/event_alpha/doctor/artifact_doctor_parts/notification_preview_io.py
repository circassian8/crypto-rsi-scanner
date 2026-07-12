"""Notification preview path resolution and body loading for artifact doctor checks."""

from __future__ import annotations

from .runtime import *


def _delivery_preview_body(
    row: Mapping[str, Any],
    out: dict[str, int],
    *,
    is_latest_run: bool,
    notification_preview_path: str | Path | None = None,
) -> str:
    preview_relpath = str(row.get("notification_preview_relpath") or "").strip()
    if not preview_relpath and is_latest_run:
        out["notification_preview_relpath_missing"] += 1
    if notification_preview_path is not None:
        path = Path(notification_preview_path).expanduser()
    else:
        path, _source = _delivery.resolve_notification_preview_path(
            row,
            artifact_namespace=row.get("artifact_namespace") or row.get("namespace"),
        )
    if path is None:
        out["notification_preview_missing"] += 1
        out["notification_preview_path_unresolvable"] += 1
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        out["notification_preview_missing"] += 1
        out["notification_preview_path_unresolvable"] += 1
        return ""
    telegram_body = "\n".join(_telegram_preview_bodies(text)) or text
    if re.search(r"/Users/|/tmp/|/private/tmp/", telegram_body):
        out["telegram_message_contains_absolute_path"] += 1
    if re.search(r"\b(alert_id|card_id|research_card|route|lane)=", telegram_body):
        out["telegram_message_contains_raw_debug_dump"] += 1
    return telegram_body


def _active_preview_api_alerts_wording_count(
    delivery_rows: Iterable[Mapping[str, Any]],
    *,
    latest_run: Mapping[str, Any] | None,
    latest_run_id: str | None,
    notification_preview_path: str | Path | None = None,
) -> int:
    paths: set[Path] = (
        {Path(notification_preview_path).expanduser()}
        if notification_preview_path is not None
        else set()
    )
    if notification_preview_path is None:
        for row in _delivery.latest_rows_by_delivery(delivery_rows):
            if latest_run_id and str(row.get("run_id") or "") != str(latest_run_id):
                continue
            path, _source = _delivery.resolve_notification_preview_path(
                row,
                artifact_namespace=row.get("artifact_namespace") or row.get("namespace"),
            )
            if path is not None:
                paths.add(path)
    count = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _notification_preview_api_alerts_wording(text, latest_run=latest_run):
            count += 1
    return count


def _notification_preview_api_alerts_wording(
    text: str,
    *,
    latest_run: Mapping[str, Any] | None,
) -> bool:
    strict_alerts = event_alpha_run_counters.canonical_run_counters(latest_run)["strict_alerts"]
    bodies = "\n".join(_telegram_preview_bodies(text)) or text
    if strict_alerts > 0:
        return False
    return bool(
        re.search(
            r"(?im)^Alertable decisions:\s*\d+\s*(?:·|-|\|)\s*Alerts:\s*[1-9]\d*\b",
            bodies,
        )
    )


def _latest_preview_path(
    delivery_rows: Iterable[Mapping[str, Any]],
    *,
    latest_run_id: str | None,
    notification_preview_path: str | Path | None = None,
) -> Path | None:
    if notification_preview_path is not None:
        path = Path(notification_preview_path).expanduser()
        return path if path.exists() else None
    latest = _delivery.latest_rows_by_delivery(delivery_rows)
    candidates: list[tuple[str, str]] = []
    for row in latest:
        if latest_run_id and str(row.get("run_id") or "") != str(latest_run_id):
            continue
        path, _source = _delivery.resolve_notification_preview_path(
            row,
            artifact_namespace=row.get("artifact_namespace") or row.get("namespace"),
        )
        if path is None:
            continue
        stamp = str(row.get("attempted_at") or row.get("delivered_at") or "")
        candidates.append((stamp, str(path)))
    if not candidates:
        return None
    candidates.sort()
    return Path(candidates[-1][1])


def _telegram_preview_bodies(text: str) -> tuple[str, ...]:
    bodies = re.findall(r"```html\n(.*?)```", text, flags=re.DOTALL)
    if bodies:
        return tuple(bodies)
    if "Telegram Body" in text:
        return (text.split("Telegram Body", 1)[-1],)
    return ()


__all__ = (
    "_delivery_preview_body",
    "_active_preview_api_alerts_wording_count",
    "_notification_preview_api_alerts_wording",
    "_latest_preview_path",
    "_telegram_preview_bodies",
)
