"""Optional append-only human feedback for empirical targeted-review items.

The ledger is deliberately separate from replay, scoring, and policy selection.
It accepts only closed-taxonomy labels bound to one immutable queue item and
uses a confirmed, descriptor-anchored append as its sole side effect.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .empirical_review import LABEL_TAXONOMY


SCHEMA_ID = "decision_radar.empirical_review_feedback_event"
SCHEMA_VERSION = 1
REPORT_SCHEMA_ID = "decision_radar.empirical_review_feedback_report"
MAX_EVENT_BYTES = 8 * 1024
MAX_LEDGER_BYTES = 4 * 1024 * 1024
MAX_LEDGER_EVENTS = 4096
MAX_REPORT_EVENTS = 256

_QUEUE_SCHEMA_ID = "decision_radar.empirical_targeted_review_queue"
_QUEUE_SCHEMA_VERSION = 1
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ITEM_ID = re.compile(r"^empirical-review-item-v1:[0-9a-f]{64}$")
_EVENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_EVIDENCE_MODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.jsonl$")
_SECRET_MARKER = re.compile(
    rb"(?:authorization\s*[:=]\s*bearer|(?:api[_-]?key|access[_-]?token|"
    rb"password|passwd|secret|credential)\s*[:=]|-----BEGIN\s+(?:RSA\s+)?"
    rb"PRIVATE\s+KEY-----)",
    re.IGNORECASE,
)

_FORBIDDEN_COUNTERS = (
    "provider_calls",
    "authorization_mutations",
    "telegram_sends",
    "trades",
    "orders",
    "event_alpha_paper_trades",
    "normal_rsi_writes",
    "event_alpha_triggered_fade",
    "dashboard_authority_mutations",
    "production_policy_mutations",
)
_EVENT_FIELDS = frozenset({
    "schema_id",
    "schema_version",
    "label_event_id",
    "event_digest",
    "queue_digest",
    "run_fingerprint",
    "protocol_version",
    "protocol_sha256",
    "review_item_id",
    "review_item_evidence_digest",
    "evidence_mode",
    "label",
    "observed_at",
    "reviewer_alias",
    "human_supplied",
    "optional_feedback",
    "feedback_effect",
    "research_only",
    "policy_eligible",
    "auto_apply",
    "safety",
})


def build_feedback_event(
    queue: Mapping[str, Any],
    *,
    review_item_id: str,
    label: str,
    observed_at: str,
    reviewer_alias: str,
    label_event_id: str | None = None,
) -> dict[str, Any]:
    """Build one canonical human label event without writing it anywhere."""

    queue_errors, items = _validate_queue(queue)
    if queue_errors:
        raise ValueError("empirical feedback queue invalid:" + ";".join(queue_errors))
    item = items.get(review_item_id)
    if item is None:
        raise ValueError("empirical feedback review item not in queue")
    body: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "queue_digest": queue["queue_digest"],
        "run_fingerprint": queue["run_fingerprint"],
        "protocol_version": queue["protocol_version"],
        "protocol_sha256": queue["protocol_sha256"],
        "review_item_id": review_item_id,
        "review_item_evidence_digest": item["evidence_digest"],
        "evidence_mode": item["evidence_mode"],
        "label": label,
        "observed_at": observed_at,
        "reviewer_alias": reviewer_alias,
        "human_supplied": True,
        "optional_feedback": True,
        "feedback_effect": "review_metadata_only",
        "research_only": True,
        "policy_eligible": False,
        "auto_apply": False,
        "safety": {field: 0 for field in _FORBIDDEN_COUNTERS},
    }
    if label_event_id is None:
        label_event_id = "empirical-review-label-v1:" + _digest_value(body)
    body["label_event_id"] = label_event_id
    event = {**body, "event_digest": _digest_value(body)}
    errors = validate_feedback_event(queue, event)
    if errors:
        raise ValueError("empirical feedback event invalid:" + ";".join(errors))
    return event


def validate_feedback_event(
    queue: Mapping[str, Any], event: Mapping[str, Any]
) -> tuple[str, ...]:
    """Purely validate an event against the exact immutable review queue."""

    queue_errors, items = _validate_queue(queue)
    errors = list(queue_errors)
    if not isinstance(queue, Mapping):
        return tuple(errors)
    if not isinstance(event, Mapping):
        return tuple(errors + ["event_not_mapping"])
    if set(event) != _EVENT_FIELDS:
        errors.append("event_fields_invalid")
    if event.get("schema_id") != SCHEMA_ID or event.get("schema_version") != SCHEMA_VERSION:
        errors.append("event_schema_invalid")
    event_id = str(event.get("label_event_id") or "")
    if not _EVENT_ID.fullmatch(event_id):
        errors.append("label_event_id_invalid")
    if event.get("queue_digest") != queue.get("queue_digest"):
        errors.append("queue_digest_mismatch")
    if event.get("run_fingerprint") != queue.get("run_fingerprint"):
        errors.append("run_fingerprint_mismatch")
    if event.get("protocol_version") != queue.get("protocol_version"):
        errors.append("protocol_version_mismatch")
    if event.get("protocol_sha256") != queue.get("protocol_sha256"):
        errors.append("protocol_sha256_mismatch")
    item_id = str(event.get("review_item_id") or "")
    item = items.get(item_id)
    if item is None:
        errors.append("review_item_not_in_queue")
    else:
        if event.get("review_item_evidence_digest") != item.get("evidence_digest"):
            errors.append("review_item_evidence_digest_mismatch")
        if event.get("evidence_mode") != item.get("evidence_mode"):
            errors.append("evidence_mode_mismatch")
    if str(event.get("label") or "") not in LABEL_TAXONOMY:
        errors.append("label_outside_closed_taxonomy")
    if not _valid_timestamp(event.get("observed_at")):
        errors.append("observed_at_invalid")
    if not _ALIAS.fullmatch(str(event.get("reviewer_alias") or "")):
        errors.append("reviewer_alias_invalid")
    if not _EVIDENCE_MODE.fullmatch(str(event.get("evidence_mode") or "")):
        errors.append("evidence_mode_invalid")
    if (
        event.get("human_supplied") is not True
        or event.get("optional_feedback") is not True
        or event.get("feedback_effect") != "review_metadata_only"
        or event.get("research_only") is not True
        or event.get("policy_eligible") is not False
        or event.get("auto_apply") is not False
    ):
        errors.append("feedback_safety_state_invalid")
    safety = event.get("safety")
    if not isinstance(safety, Mapping) or set(safety) != set(_FORBIDDEN_COUNTERS):
        errors.append("safety_counters_invalid")
    elif any(type(safety.get(field)) is not int or safety.get(field) != 0 for field in _FORBIDDEN_COUNTERS):
        errors.append("safety_counters_invalid")
    try:
        payload = canonical_json_bytes(event)
    except ValueError:
        errors.append("event_not_canonical_json_value")
    else:
        if len(payload) > MAX_EVENT_BYTES:
            errors.append("event_too_large")
        if _SECRET_MARKER.search(payload):
            errors.append("event_secret_marker_detected")
        declared = str(event.get("event_digest") or "")
        digest_body = {key: value for key, value in event.items() if key != "event_digest"}
        if not _DIGEST.fullmatch(declared) or declared != _digest_value(digest_body):
            errors.append("event_digest_invalid")
    return tuple(dict.fromkeys(errors))


def append_feedback_event(
    ledger_path: str | Path,
    queue: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    confirm: bool,
) -> dict[str, Any]:
    """Append one validated event after explicit confirmation.

    An exact retry is idempotent. Reusing an event ID for different canonical
    bytes is immutable drift and fails closed.
    """

    if confirm is not True:
        raise PermissionError("empirical_feedback_append_confirmation_required")
    errors = validate_feedback_event(queue, event)
    if errors:
        raise ValueError("empirical feedback event invalid:" + ";".join(errors))
    event_payload = canonical_json_bytes(event)
    path = _ledger_path(ledger_path)
    parent_fd = _open_parent(path.parent)
    descriptor = -1
    try:
        before = _entry_stat(parent_fd, path.name)
        if before is not None and not stat.S_ISREG(before.st_mode):
            raise RuntimeError("empirical_feedback_ledger_unsafe")
        flags = (
            os.O_RDWR
            | os.O_APPEND
            | os.O_CREAT
            | getattr(os, "O_CLOEXEC", 0)
            | _required_flag("O_NOFOLLOW")
        )
        descriptor = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (
            before is not None and _identity(before) != _identity(opened)
        ):
            raise RuntimeError("empirical_feedback_ledger_unsafe")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        payload = _read_descriptor(descriptor)
        rows, row_payloads = _parse_ledger(payload, queue)
        event_id = str(event["label_event_id"])
        if event_id in row_payloads:
            if row_payloads[event_id] != event_payload:
                raise RuntimeError("empirical_feedback_label_event_id_drift")
            return _append_result("already_present", event, len(rows), 0)
        if len(rows) >= MAX_LEDGER_EVENTS:
            raise RuntimeError("empirical_feedback_ledger_event_limit")
        appended = event_payload + b"\n"
        if len(payload) + len(appended) > MAX_LEDGER_BYTES:
            raise RuntimeError("empirical_feedback_ledger_size_limit")
        _write_all(descriptor, appended)
        os.fsync(descriptor)
        after = os.fstat(descriptor)
        named = _entry_stat(parent_fd, path.name)
        if named is None or _identity(named) != _identity(after):
            raise RuntimeError("empirical_feedback_ledger_identity_drift")
        os.fsync(parent_fd)
        return _append_result("appended", event, len(rows) + 1, 1)
    finally:
        if descriptor >= 0:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
        os.close(parent_fd)


def read_feedback_ledger(
    ledger_path: str | Path, queue: Mapping[str, Any]
) -> tuple[dict[str, Any], ...]:
    """Read and validate the bounded exact ledger without writing."""

    queue_errors, _items = _validate_queue(queue)
    if queue_errors:
        raise ValueError("empirical feedback queue invalid:" + ";".join(queue_errors))
    path = _ledger_path(ledger_path)
    parent_fd = _open_parent(path.parent)
    descriptor = -1
    try:
        before = _entry_stat(parent_fd, path.name)
        if before is None:
            return ()
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError("empirical_feedback_ledger_unsafe")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | _required_flag("O_NOFOLLOW")
        descriptor = os.open(path.name, flags, dir_fd=parent_fd)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _identity(before) != _identity(opened):
            raise RuntimeError("empirical_feedback_ledger_unsafe")
        payload = _read_descriptor(descriptor)
        after = os.fstat(descriptor)
        named = _entry_stat(parent_fd, path.name)
        if named is None or _identity(named) != _identity(after):
            raise RuntimeError("empirical_feedback_ledger_identity_drift")
        rows, _payloads = _parse_ledger(payload, queue)
        return tuple(rows)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def build_feedback_report(
    queue: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
    *,
    maximum_events: int = MAX_REPORT_EVENTS,
) -> dict[str, Any]:
    """Build a bounded descriptive report, separated by evidence mode."""

    if type(maximum_events) is not int or not 1 <= maximum_events <= MAX_REPORT_EVENTS:
        raise ValueError("empirical feedback report bound invalid")
    queue_errors, _items = _validate_queue(queue)
    if queue_errors:
        raise ValueError("empirical feedback queue invalid:" + ";".join(queue_errors))
    rows: list[dict[str, Any]] = []
    identities: dict[str, bytes] = {}
    for raw in events:
        if len(rows) >= MAX_LEDGER_EVENTS:
            raise ValueError("empirical feedback event count exceeds bound")
        row = _json_mapping(raw)
        errors = validate_feedback_event(queue, row)
        if errors:
            raise ValueError("empirical feedback event invalid:" + ";".join(errors))
        payload = canonical_json_bytes(row)
        event_id = str(row["label_event_id"])
        previous = identities.get(event_id)
        if previous is not None:
            if previous != payload:
                raise ValueError("empirical feedback duplicate event id drift")
            raise ValueError("empirical feedback duplicate event id")
        identities[event_id] = payload
        rows.append(row)
    rows.sort(key=lambda row: (str(row["observed_at"]), str(row["label_event_id"])))
    visible = rows[-maximum_events:]
    by_mode: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_mode.setdefault(str(row["evidence_mode"]), []).append(row)
    mode_reports = []
    for evidence_mode in sorted(by_mode):
        mode_rows = by_mode[evidence_mode]
        label_counts = {
            label: sum(row["label"] == label for row in mode_rows)
            for label in LABEL_TAXONOMY
        }
        mode_reports.append({
            "evidence_mode": evidence_mode,
            "event_count": len(mode_rows),
            "reviewed_item_count": len({row["review_item_id"] for row in mode_rows}),
            "label_counts": label_counts,
            "descriptive_only": True,
            "policy_eligible": False,
        })
    body = {
        "schema_id": REPORT_SCHEMA_ID,
        "schema_version": 1,
        "queue_digest": queue["queue_digest"],
        "run_fingerprint": queue["run_fingerprint"],
        "protocol_version": queue["protocol_version"],
        "protocol_sha256": queue["protocol_sha256"],
        "event_count": len(rows),
        "reviewed_item_count": len({row["review_item_id"] for row in rows}),
        "evidence_modes": mode_reports,
        "events": visible,
        "events_truncated": len(rows) > len(visible),
        "maximum_events": maximum_events,
        "cross_evidence_mode_conclusions_allowed": False,
        "human_feedback_optional": True,
        "descriptive_only": True,
        "research_only": True,
        "policy_eligible": False,
        "auto_apply": False,
    }
    return {**body, "report_digest": _digest_value(body)}


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("empirical feedback value is not canonical JSON") from exc


def _validate_queue(
    queue: Mapping[str, Any],
) -> tuple[tuple[str, ...], dict[str, Mapping[str, Any]]]:
    errors: list[str] = []
    items: dict[str, Mapping[str, Any]] = {}
    if not isinstance(queue, Mapping):
        return ("queue_not_mapping",), items
    if queue.get("schema_id") != _QUEUE_SCHEMA_ID or queue.get("schema_version") != _QUEUE_SCHEMA_VERSION:
        errors.append("queue_schema_invalid")
    for field in ("queue_digest", "run_fingerprint", "protocol_sha256"):
        if not _DIGEST.fullmatch(str(queue.get(field) or "")):
            errors.append(f"queue_{field}_invalid")
    if not str(queue.get("protocol_version") or ""):
        errors.append("queue_protocol_version_invalid")
    declared = str(queue.get("queue_digest") or "")
    body = {key: value for key, value in queue.items() if key != "queue_digest"}
    try:
        calculated = _digest_value(body)
    except ValueError:
        errors.append("queue_not_canonical_json_value")
    else:
        if declared != calculated:
            errors.append("queue_digest_mismatch")
    raw_items = queue.get("items")
    if not isinstance(raw_items, list) or len(raw_items) > 64:
        errors.append("queue_items_invalid")
        raw_items = []
    if queue.get("item_count") != len(raw_items):
        errors.append("queue_item_count_mismatch")
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            errors.append("queue_item_invalid")
            continue
        item_id = str(raw.get("review_item_id") or "")
        if not _ITEM_ID.fullmatch(item_id):
            errors.append("queue_item_id_invalid")
            continue
        if item_id in items:
            errors.append("queue_item_id_duplicate")
            continue
        if raw.get("run_fingerprint") != queue.get("run_fingerprint"):
            errors.append("queue_item_run_mismatch")
        if raw.get("protocol_sha256") != queue.get("protocol_sha256"):
            errors.append("queue_item_protocol_mismatch")
        mode = str(raw.get("evidence_mode") or "")
        if not _EVIDENCE_MODE.fullmatch(mode):
            errors.append("queue_item_evidence_mode_invalid")
        evidence_digest = str(raw.get("evidence_digest") or "")
        item_body = {
            key: value for key, value in raw.items()
            if key not in {"rank", "evidence_digest"}
        }
        try:
            calculated_evidence = _digest_value(item_body)
        except ValueError:
            errors.append("queue_item_not_canonical_json_value")
            calculated_evidence = ""
        if (
            not _DIGEST.fullmatch(evidence_digest)
            or evidence_digest != calculated_evidence
        ):
            errors.append("queue_item_evidence_digest_invalid")
        if raw.get("research_only") is not True or raw.get("auto_apply") is not False:
            errors.append("queue_item_safety_invalid")
        items[item_id] = raw
    return tuple(dict.fromkeys(errors)), items


def _parse_ledger(
    payload: bytes, queue: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    if not payload:
        return [], {}
    if len(payload) > MAX_LEDGER_BYTES:
        raise RuntimeError("empirical_feedback_ledger_size_limit")
    if not payload.endswith(b"\n"):
        raise RuntimeError("empirical_feedback_ledger_partial_row")
    lines = payload[:-1].split(b"\n")
    if len(lines) > MAX_LEDGER_EVENTS:
        raise RuntimeError("empirical_feedback_ledger_event_limit")
    rows: list[dict[str, Any]] = []
    row_payloads: dict[str, bytes] = {}
    for line in lines:
        if not line or len(line) > MAX_EVENT_BYTES:
            raise RuntimeError("empirical_feedback_ledger_row_invalid")
        try:
            raw = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("empirical_feedback_ledger_row_invalid") from exc
        row = _json_mapping(raw)
        if canonical_json_bytes(row) != line:
            raise RuntimeError("empirical_feedback_ledger_row_noncanonical")
        errors = validate_feedback_event(queue, row)
        if errors:
            raise RuntimeError("empirical_feedback_ledger_row_invalid:" + ";".join(errors))
        event_id = str(row["label_event_id"])
        if event_id in row_payloads:
            if row_payloads[event_id] != line:
                raise RuntimeError("empirical_feedback_label_event_id_drift")
            raise RuntimeError("empirical_feedback_duplicate_label_event_id")
        row_payloads[event_id] = line
        rows.append(row)
    return rows, row_payloads


def _ledger_path(value: str | Path) -> Path:
    path = Path(value).expanduser().absolute()
    if not _SAFE_FILENAME.fullmatch(path.name):
        raise ValueError("empirical feedback ledger filename invalid")
    if not path.parent.exists():
        raise ValueError("empirical feedback ledger parent missing")
    return path


def _open_parent(path: Path) -> int:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | _required_flag("O_DIRECTORY")
        | _required_flag("O_NOFOLLOW")
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError("empirical_feedback_ledger_parent_unsafe") from exc
    opened = os.fstat(descriptor)
    if not stat.S_ISDIR(opened.st_mode):
        os.close(descriptor)
        raise RuntimeError("empirical_feedback_ledger_parent_unsafe")
    return descriptor


def _entry_stat(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _read_descriptor(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(descriptor, min(64 * 1024, MAX_LEDGER_BYTES + 1 - total))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_LEDGER_BYTES:
            raise RuntimeError("empirical_feedback_ledger_size_limit")


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise RuntimeError("empirical_feedback_ledger_append_failed")
        offset += written


def _identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _required_flag(name: str) -> int:
    value = getattr(os, name, 0)
    if not value:
        raise RuntimeError("empirical_feedback_descriptor_features_unavailable")
    return value


def _append_result(
    status_value: str, event: Mapping[str, Any], event_count: int, write_count: int
) -> dict[str, Any]:
    return {
        "status": status_value,
        "label_event_id": event["label_event_id"],
        "queue_digest": event["queue_digest"],
        "run_fingerprint": event["run_fingerprint"],
        "evidence_mode": event["evidence_mode"],
        "event_count": event_count,
        "feedback_ledger_appends": write_count,
        "research_only": True,
        "auto_apply": False,
    }


def _valid_timestamp(value: Any) -> bool:
    text = str(value or "")
    if not text or len(text) > 64:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _json_mapping(value: Any) -> dict[str, Any]:
    try:
        decoded = json.loads(canonical_json_bytes(value))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("empirical feedback event is not canonical JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("empirical feedback event is not a mapping")
    return decoded


def _digest_value(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("empirical feedback value is not canonical JSON") from exc
    return hashlib.sha256(payload).hexdigest()


__all__ = (
    "MAX_LEDGER_BYTES",
    "MAX_LEDGER_EVENTS",
    "MAX_REPORT_EVENTS",
    "REPORT_SCHEMA_ID",
    "SCHEMA_ID",
    "append_feedback_event",
    "build_feedback_event",
    "build_feedback_report",
    "canonical_json_bytes",
    "read_feedback_ledger",
    "validate_feedback_event",
)
