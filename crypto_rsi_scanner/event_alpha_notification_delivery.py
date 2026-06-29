"""Idempotent delivery ledger for research-only Event Alpha notifications.

Scheduled notify cycles must not double-send the same research digest if a run
retries, overlaps, or re-fires within a cooldown gap. This module records each
lane send attempt as an append-only JSONL event (planned -> sending ->
delivered/partial_delivered/failed, or skipped_duplicate/skipped_in_flight/
blocked) keyed by a stable dedupe key with a content-hash fallback, and answers
"did we already deliver or start sending this lane recently?".

It owns *delivery bookkeeping* only. It never ranks alerts, sends, trades, paper
trades, writes normal RSI signal rows, or creates ``TRIGGERED_FADE``. Records and
channel summaries are redacted: no tokens, chat ids, or env values are stored.
All writes fail soft so a delivery-ledger problem cannot crash the scan.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

DELIVERY_SCHEMA_VERSION = "event_alpha_notification_delivery_v1"

STATE_PLANNED = "planned"
STATE_SENDING = "sending"
STATE_DELIVERED = "delivered"
STATE_PARTIAL_DELIVERED = "partial_delivered"
STATE_FAILED = "failed"
STATE_SKIPPED_DUPLICATE = "skipped_duplicate"
STATE_SKIPPED_IN_FLIGHT = "skipped_in_flight"
STATE_BLOCKED = "blocked"

STATES = (
    STATE_PLANNED,
    STATE_SENDING,
    STATE_DELIVERED,
    STATE_PARTIAL_DELIVERED,
    STATE_FAILED,
    STATE_SKIPPED_DUPLICATE,
    STATE_SKIPPED_IN_FLIGHT,
    STATE_BLOCKED,
)
TERMINAL_STATES = (
    STATE_DELIVERED,
    STATE_PARTIAL_DELIVERED,
    STATE_FAILED,
    STATE_SKIPPED_DUPLICATE,
    STATE_SKIPPED_IN_FLIGHT,
    STATE_BLOCKED,
)
_STAGE_RANK = {
    STATE_PLANNED: 0,
    STATE_SENDING: 1,
    STATE_BLOCKED: 2,
    STATE_SKIPPED_DUPLICATE: 2,
    STATE_SKIPPED_IN_FLIGHT: 2,
    STATE_FAILED: 3,
    STATE_DELIVERED: 3,
    STATE_PARTIAL_DELIVERED: 3,
}

_DELIVERIES_PATH_ENV = "RSI_EVENT_ALPHA_NOTIFICATION_DELIVERIES_PATH"
_SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer)\s*[=:]\s*\S+")
_SECRET_KEY_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer)")


@dataclass(frozen=True)
class NotificationDeliveryConfig:
    path: Path
    dedupe_by_content: bool = True
    dedupe_window_hours: float = 24.0
    in_flight_grace_minutes: float = 10.0
    partial_marks_cooldown: bool = True


@dataclass(frozen=True)
class NotificationDeliveryRecord:
    delivery_id: str
    run_id: str
    alert_id: str
    profile: str
    namespace: str
    lane: str
    route: str
    content_hash: str
    state: str
    dedupe_key: str | None = None
    dedupe_bucket: str | None = None
    requested_alert_id: str | None = None
    core_opportunity_id: str | None = None
    canonical_symbol: str | None = None
    canonical_coin_id: str | None = None
    canonical_card_path: str | None = None
    feedback_target: str | None = None
    source_alert_ids: tuple[str, ...] = ()
    notification_item_ids: tuple[str, ...] = ()
    identity_reconciled: bool = False
    identity_reconciliation_reason: str | None = None
    notification_preview_path: str | None = None
    notification_preview_relpath: str | None = None
    attempted_at: str | None = None
    delivered_at: str | None = None
    error_class: str | None = None
    error_message_safe: str | None = None
    recipient_count: int = 0
    delivered_count: int = 0
    failed_count: int = 0
    chunk_count: int = 0
    delivered_chunks: int = 0
    failed_chunks: int = 0
    channel_summary: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {
            "schema_version": DELIVERY_SCHEMA_VERSION,
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": self.delivery_id,
            "run_id": self.run_id,
            "alert_id": self.alert_id,
            "profile": self.profile,
            "namespace": self.namespace,
            "artifact_namespace": self.namespace,
            "lane": self.lane,
            "route": self.route,
            "content_hash": self.content_hash,
            "dedupe_key": self.dedupe_key,
            "dedupe_bucket": self.dedupe_bucket,
            "requested_alert_id": self.requested_alert_id,
            "core_opportunity_id": self.core_opportunity_id,
            "canonical_symbol": self.canonical_symbol,
            "canonical_coin_id": self.canonical_coin_id,
            "canonical_card_path": self.canonical_card_path,
            "feedback_target": self.feedback_target,
            "source_alert_ids": list(self.source_alert_ids),
            "notification_item_ids": list(self.notification_item_ids),
            "identity_reconciled": bool(self.identity_reconciled),
            "identity_reconciliation_reason": self.identity_reconciliation_reason,
            "notification_preview_path": self.notification_preview_path,
            "notification_preview_relpath": self.notification_preview_relpath,
            "state": self.state,
            "attempted_at": self.attempted_at,
            "delivered_at": self.delivered_at,
            "error_class": self.error_class,
            "error_message_safe": self.error_message_safe,
            "recipient_count": int(self.recipient_count or 0),
            "delivered_count": int(self.delivered_count or 0),
            "failed_count": int(self.failed_count or 0),
            "chunk_count": int(self.chunk_count or 0),
            "delivered_chunks": int(self.delivered_chunks or 0),
            "failed_chunks": int(self.failed_chunks or 0),
            "channel_summary": _json_ready(self.channel_summary or {}),
        }


@dataclass(frozen=True)
class DeliverySummary:
    rows: int = 0
    delivered: int = 0
    partial_delivered: int = 0
    failed: int = 0
    skipped_duplicate: int = 0
    skipped_in_flight: int = 0
    blocked: int = 0
    in_flight: int = 0

    @property
    def records_written(self) -> int:
        return (
            self.delivered
            + self.partial_delivered
            + self.failed
            + self.skipped_duplicate
            + self.skipped_in_flight
            + self.blocked
            + self.in_flight
        )


def deliveries_path_for_context(context: Any) -> Path:
    """Namespaced deliveries JSONL path, honoring an explicit env override."""
    override = os.getenv(_DELIVERIES_PATH_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    namespace_dir = Path(getattr(context, "namespace_dir", None) or getattr(context, "base_dir", Path(".")))
    return namespace_dir / "event_alpha_notification_deliveries.jsonl"


def config_for_context(
    context: Any,
    *,
    dedupe_by_content: bool = True,
    dedupe_window_hours: float = 24.0,
    in_flight_grace_minutes: float = 10.0,
    partial_marks_cooldown: bool = True,
) -> NotificationDeliveryConfig:
    return NotificationDeliveryConfig(
        path=deliveries_path_for_context(context),
        dedupe_by_content=bool(dedupe_by_content),
        dedupe_window_hours=float(dedupe_window_hours),
        in_flight_grace_minutes=float(in_flight_grace_minutes),
        partial_marks_cooldown=bool(partial_marks_cooldown),
    )


def compute_content_hash(message: str, *, alert_id: str, lane: str, profile: str | None) -> str:
    """Stable hash of rendered message text + alert_id/lane/profile."""
    parts = "\x1f".join(
        [
            str(profile or "default"),
            str(lane or ""),
            str(alert_id or ""),
            str(message or ""),
        ]
    )
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:40]


def compute_dedupe_key(
    *,
    namespace: str | None,
    lane: str,
    dedupe_bucket: str,
) -> str:
    """Stable delivery dedupe key independent of generated timestamps."""
    parts = "\x1f".join([str(namespace or "default"), str(lane or ""), str(dedupe_bucket or "")])
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:40]


def delivery_id_for(run_id: str, lane: str, content_hash: str) -> str:
    parts = f"{run_id}\x1f{lane}\x1f{content_hash}"
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:24]


def build_record(
    *,
    run_id: str,
    alert_id: str,
    profile: str | None,
    namespace: str | None,
    lane: str,
    route: str | None,
    content_hash: str,
    dedupe_key: str | None = None,
    dedupe_bucket: str | None = None,
    requested_alert_id: str | None = None,
    core_opportunity_id: str | None = None,
    canonical_symbol: str | None = None,
    canonical_coin_id: str | None = None,
    canonical_card_path: str | None = None,
    feedback_target: str | None = None,
    source_alert_ids: Iterable[str] = (),
    notification_item_ids: Iterable[str] = (),
    identity_reconciled: bool = False,
    identity_reconciliation_reason: str | None = None,
    notification_preview_path: str | None = None,
    notification_preview_relpath: str | None = None,
    state: str,
    now: datetime,
    delivered_at: datetime | None = None,
    error_class: str | None = None,
    error_message: str | None = None,
    recipient_count: int = 0,
    delivered_count: int = 0,
    failed_count: int = 0,
    chunk_count: int = 0,
    delivered_chunks: int = 0,
    failed_chunks: int = 0,
    channel_summary: Mapping[str, Any] | None = None,
) -> NotificationDeliveryRecord:
    return NotificationDeliveryRecord(
        delivery_id=delivery_id_for(str(run_id), str(lane), str(content_hash)),
        run_id=str(run_id),
        alert_id=str(alert_id or ""),
        profile=str(profile or "default"),
        namespace=str(namespace or "default"),
        lane=str(lane or ""),
        route=str(route or ""),
        content_hash=str(content_hash),
        dedupe_key=str(dedupe_key) if dedupe_key else None,
        dedupe_bucket=str(dedupe_bucket)[:200] if dedupe_bucket else None,
        requested_alert_id=str(requested_alert_id) if requested_alert_id else None,
        core_opportunity_id=str(core_opportunity_id) if core_opportunity_id else None,
        canonical_symbol=str(canonical_symbol) if canonical_symbol else None,
        canonical_coin_id=str(canonical_coin_id) if canonical_coin_id else None,
        canonical_card_path=str(canonical_card_path) if canonical_card_path else None,
        feedback_target=str(feedback_target) if feedback_target else None,
        source_alert_ids=tuple(str(item) for item in source_alert_ids if str(item)),
        notification_item_ids=tuple(str(item) for item in notification_item_ids if str(item)),
        identity_reconciled=bool(identity_reconciled),
        identity_reconciliation_reason=str(identity_reconciliation_reason)[:200] if identity_reconciliation_reason else None,
        notification_preview_path=str(notification_preview_path) if notification_preview_path else None,
        notification_preview_relpath=(
            str(notification_preview_relpath)
            if notification_preview_relpath
            else notification_preview_relpath_for_path(notification_preview_path)
        ),
        state=str(state),
        attempted_at=_iso(now),
        delivered_at=_iso(delivered_at) if delivered_at else None,
        error_class=(str(error_class)[:80] if error_class else None),
        error_message_safe=_safe_error(error_message),
        recipient_count=int(recipient_count or 0),
        delivered_count=int(delivered_count or 0),
        failed_count=int(failed_count or 0),
        chunk_count=int(chunk_count or 0),
        delivered_chunks=int(delivered_chunks or 0),
        failed_chunks=int(failed_chunks or 0),
        channel_summary=_redact_mapping(channel_summary or {}),
    )


def append_delivery_record(
    record: NotificationDeliveryRecord | Mapping[str, Any],
    *,
    path: str | Path,
) -> dict[str, Any]:
    """Append one delivery event to the JSONL ledger; fail soft on I/O errors."""
    row = record.to_row() if isinstance(record, NotificationDeliveryRecord) else dict(record)
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
            fh.write("\n")
    except OSError:
        return row
    return row


def load_delivery_records(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and row.get("row_type") == "event_alpha_notification_delivery":
                    rows.append(row)
    except OSError:
        return rows
    return rows


def notification_preview_relpath_for_path(path: str | Path | None) -> str | None:
    """Return a portable repo-relative preview path when possible."""
    if not path:
        return None
    p = Path(path).expanduser()
    try:
        if p.is_absolute():
            rel = p.resolve().relative_to(Path.cwd().resolve())
            return rel.as_posix()
    except (OSError, ValueError):
        pass
    if not p.is_absolute():
        return p.as_posix()
    parts = p.parts
    if "event_fade_cache" in parts:
        idx = parts.index("event_fade_cache")
        return Path(*parts[idx:]).as_posix()
    return None


def default_notification_preview_relpath(
    *,
    artifact_namespace: str | None,
    artifact_base_dir: str | Path | None = None,
) -> str:
    namespace = str(artifact_namespace or "default").strip() or "default"
    base = Path(artifact_base_dir or os.getenv("RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR", "event_fade_cache")).expanduser()
    path = base / namespace / "event_alpha_notification_preview.md"
    return notification_preview_relpath_for_path(path) or path.as_posix()


def resolve_notification_preview_path(
    row: Mapping[str, Any] | None = None,
    *,
    artifact_namespace: str | None = None,
    artifact_base_dir: str | Path | None = None,
    repo_root: str | Path | None = None,
) -> tuple[Path | None, str]:
    """Resolve a notification preview path in portable order.

    Resolution order:
    1. ``notification_preview_relpath`` under the current checkout.
    2. Namespace default under the current artifact base.
    3. Legacy ``notification_preview_path`` as an absolute/relative fallback.
    """
    row = row or {}
    root = Path(repo_root or Path.cwd()).expanduser()
    relpath = str(row.get("notification_preview_relpath") or "").strip()
    if relpath:
        candidate = Path(relpath).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.exists():
            return candidate, "relpath"
    namespace = artifact_namespace or row.get("artifact_namespace") or row.get("namespace")
    if namespace:
        default_rel = default_notification_preview_relpath(
            artifact_namespace=str(namespace),
            artifact_base_dir=artifact_base_dir,
        )
        candidate = Path(default_rel).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.exists():
            return candidate, "namespace_default"
    legacy = str(row.get("notification_preview_path") or "").strip()
    if legacy:
        candidate = Path(legacy).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.exists():
            return candidate, "absolute" if Path(legacy).expanduser().is_absolute() else "relpath"
    return None, "missing"


def find_recent_delivered(
    rows: Iterable[Mapping[str, Any]],
    *,
    content_hash: str | None,
    dedupe_key: str | None = None,
    namespace: str | None,
    now: datetime,
    window_hours: float,
    include_partial: bool = True,
) -> dict[str, Any] | None:
    """Return the most recent delivered row matching content within the window."""
    if not content_hash and not dedupe_key:
        return None
    cutoff = _as_utc(now) - timedelta(hours=max(0.0, float(window_hours)))
    ns = str(namespace or "default")
    best: dict[str, Any] | None = None
    best_ts: datetime | None = None
    for row in rows:
        allowed = (STATE_DELIVERED, STATE_PARTIAL_DELIVERED) if include_partial else (STATE_DELIVERED,)
        if str(row.get("state") or "") not in allowed:
            continue
        if not _matches_delivery_identity(row, content_hash=content_hash, dedupe_key=dedupe_key):
            continue
        if str(row.get("namespace") or row.get("artifact_namespace") or "default") != ns:
            continue
        ts = _parse_iso(row.get("delivered_at") or row.get("attempted_at"))
        if ts is None or ts < cutoff:
            continue
        if best_ts is None or ts >= best_ts:
            best, best_ts = dict(row), ts
    return best


def find_recent_in_flight(
    rows: Iterable[Mapping[str, Any]],
    *,
    content_hash: str | None,
    dedupe_key: str | None = None,
    namespace: str | None,
    now: datetime,
    grace_minutes: float,
) -> dict[str, Any] | None:
    """Return a recent latest-state planned/sending row for matching content."""
    if not content_hash and not dedupe_key:
        return None
    cutoff = _as_utc(now) - timedelta(minutes=max(0.0, float(grace_minutes)))
    ns = str(namespace or "default")
    best: dict[str, Any] | None = None
    best_ts: datetime | None = None
    for row in latest_rows_by_delivery(rows):
        if str(row.get("state") or "") not in (STATE_PLANNED, STATE_SENDING):
            continue
        if not _matches_delivery_identity(row, content_hash=content_hash, dedupe_key=dedupe_key):
            continue
        if str(row.get("namespace") or row.get("artifact_namespace") or "default") != ns:
            continue
        ts = _parse_iso(row.get("attempted_at"))
        if ts is None or ts < cutoff:
            continue
        if best_ts is None or ts >= best_ts:
            best, best_ts = dict(row), ts
    return best


def summarize_delivery_rows(rows: Iterable[Mapping[str, Any]]) -> DeliverySummary:
    """Collapse append-only rows to one latest state per delivery_id and count."""
    latest: dict[str, dict[str, Any]] = {}
    order = 0
    for row in rows:
        order += 1
        did = str(row.get("delivery_id") or f"_row_{order}")
        current = latest.get(did)
        if current is None or _row_rank(row) >= _row_rank(current):
            latest[did] = dict(row)
    counts = {state: 0 for state in TERMINAL_STATES}
    in_flight = 0
    for row in latest.values():
        state = str(row.get("state") or "")
        if state in counts:
            counts[state] += 1
        elif state in (STATE_PLANNED, STATE_SENDING):
            in_flight += 1
    return DeliverySummary(
        rows=len(latest),
        delivered=counts[STATE_DELIVERED],
        partial_delivered=counts[STATE_PARTIAL_DELIVERED],
        failed=counts[STATE_FAILED],
        skipped_duplicate=counts[STATE_SKIPPED_DUPLICATE],
        skipped_in_flight=counts[STATE_SKIPPED_IN_FLIGHT],
        blocked=counts[STATE_BLOCKED],
        in_flight=in_flight,
    )


def latest_rows_by_delivery(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    order = 0
    for row in rows:
        order += 1
        did = str(row.get("delivery_id") or f"_row_{order}")
        current = latest.get(did)
        if current is None or _row_rank(row) >= _row_rank(current):
            latest[did] = dict(row)
    return list(latest.values())


def format_delivery_report(
    rows: list[dict[str, Any]],
    *,
    path: str | Path,
    profile: str | None,
    namespace: str | None,
    latest_limit: int = 5,
) -> str:
    summary = summarize_delivery_rows(rows)
    collapsed = latest_rows_by_delivery(rows)
    lines = [
        "=" * 76,
        "EVENT ALPHA NOTIFICATION DELIVERIES REPORT (research artifact only)",
        "=" * 76,
        f"path: {path}",
        f"profile: {profile or 'default'} · namespace: {namespace or 'default'}",
        f"rows_read: {len(rows)} · deliveries: {summary.rows}",
        (
            f"delivered={summary.delivered} failed={summary.failed} "
            f"skipped_duplicate={summary.skipped_duplicate} "
            f"skipped_in_flight={summary.skipped_in_flight} "
            f"partial_delivered={summary.partial_delivered} "
            f"blocked={summary.blocked} "
            f"in_flight={summary.in_flight}"
        ),
    ]
    if not rows:
        lines.append("")
        lines.append("No notification delivery rows found for this profile/namespace.")
        return "\n".join(lines)

    by_lane: dict[str, dict[str, int]] = {}
    for row in collapsed:
        lane = str(row.get("lane") or "unknown")
        state = str(row.get("state") or "unknown")
        by_lane.setdefault(lane, {}).setdefault(state, 0)
        by_lane[lane][state] += 1
    lines.append("")
    lines.append("by lane/state:")
    for lane in sorted(by_lane):
        states = by_lane[lane]
        lines.append(
            f"- {lane}: " + ", ".join(f"{state}={count}" for state, count in sorted(states.items()))
        )

    lines.extend(_section("latest failures", _filter_state(collapsed, STATE_FAILED), latest_limit))
    lines.extend(_section("latest partial deliveries", _filter_state(collapsed, STATE_PARTIAL_DELIVERED), latest_limit))
    lines.extend(_section("latest delivered", _filter_state(collapsed, STATE_DELIVERED), latest_limit))
    lines.extend(_section("latest duplicate skips", _filter_state(collapsed, STATE_SKIPPED_DUPLICATE), latest_limit))
    lines.extend(_section("latest in-flight skips", _filter_state(collapsed, STATE_SKIPPED_IN_FLIGHT), latest_limit))
    blocked = _filter_state(collapsed, STATE_BLOCKED)
    if blocked:
        lines.extend(_section("latest blocked", blocked, latest_limit))
    return "\n".join(lines).rstrip()


def failed_deliveries(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Latest-state rows whose terminal state is failed (retry candidates)."""
    return _filter_state(latest_rows_by_delivery(rows), STATE_FAILED)


def state_for_send_counts(*, delivered_count: int, failed_count: int) -> str:
    """Map structured recipient counts to the delivery terminal state."""
    delivered = max(0, int(delivered_count or 0))
    failed = max(0, int(failed_count or 0))
    if delivered > 0 and failed <= 0:
        return STATE_DELIVERED
    if delivered > 0 and failed > 0:
        return STATE_PARTIAL_DELIVERED
    return STATE_FAILED


def _section(title: str, rows: list[dict[str, Any]], limit: int) -> list[str]:
    out = ["", f"{title}:"]
    if not rows:
        out.append("- none")
        return out
    rows = sorted(rows, key=lambda row: str(row.get("attempted_at") or ""), reverse=True)[: max(0, limit)]
    for row in rows:
        stamp = row.get("delivered_at") or row.get("attempted_at") or "unknown"
        identity = str(row.get("core_opportunity_id") or row.get("alert_id") or "n/a")
        symbol = str(row.get("canonical_symbol") or row.get("canonical_coin_id") or "").strip()
        if symbol:
            identity = f"{identity} ({symbol})"
        detail = (
            f"- {stamp} lane={row.get('lane') or 'unknown'} item={identity} "
            f"route={row.get('route') or 'n/a'} key={str(row.get('dedupe_key') or row.get('content_hash') or '')[:12]}"
        )
        status_detail = _delivery_status_detail(row)
        if status_detail:
            detail += f" status_detail={status_detail}"
        if row.get("source_alert_ids") and row.get("identity_reconciled"):
            detail += " source_alerts=" + ",".join(str(item) for item in row.get("source_alert_ids") or [])
        if row.get("error_class"):
            detail += f" error_class={row.get('error_class')}"
        if row.get("error_message_safe"):
            detail += f" error={row.get('error_message_safe')}"
        out.append(detail)
    return out


def _filter_state(rows: Iterable[Mapping[str, Any]], state: str) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if str(row.get("state") or "") == state]


def _delivery_status_detail(row: Mapping[str, Any]) -> str:
    state = str(row.get("state") or "")
    error_class = str(row.get("error_class") or "").casefold()
    error = str(row.get("error_message_safe") or "").casefold()
    if state == STATE_BLOCKED:
        if error_class == "guard_blocked" and ("event alerts disabled" in error or "rsi_event_alerts_enabled" in error):
            return "would_send_but_guard_disabled"
        if "quality" in error:
            return "blocked_by_quality_gate"
        if "cooldown" in error or "duplicate" in error:
            return "blocked_by_cooldown"
        return "blocked_by_send_guard"
    if state == STATE_SKIPPED_DUPLICATE:
        return "blocked_by_cooldown"
    if state == STATE_SKIPPED_IN_FLIGHT:
        return "skipped_in_flight"
    return ""


def _row_rank(row: Mapping[str, Any]) -> tuple[int, str]:
    state = str(row.get("state") or "")
    return (_STAGE_RANK.get(state, 0), str(row.get("delivered_at") or row.get("attempted_at") or ""))


def _matches_delivery_identity(
    row: Mapping[str, Any],
    *,
    content_hash: str | None,
    dedupe_key: str | None,
) -> bool:
    row_key = str(row.get("dedupe_key") or "")
    if dedupe_key and row_key:
        return row_key == str(dedupe_key)
    if content_hash:
        return str(row.get("content_hash") or "") == str(content_hash)
    return False


def _safe_error(text: object) -> str | None:
    if text in (None, ""):
        return None
    cleaned = _SECRET_RE.sub(r"\1=[redacted]", str(text).replace("\n", " ").strip())
    return cleaned[:240] if cleaned else None


def _redact_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        key_text = str(key)
        if _SECRET_KEY_RE.search(key_text):
            out[key_text] = "[redacted]"
        elif isinstance(value, str):
            out[str(key)] = _SECRET_RE.sub(r"\1=[redacted]", value)
        elif isinstance(value, Mapping):
            out[str(key)] = _redact_mapping(value)
        else:
            out[key_text] = value
    return out


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _iso(value: datetime | None) -> str | None:
    return _as_utc(value).isoformat() if value else None


def _parse_iso(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
