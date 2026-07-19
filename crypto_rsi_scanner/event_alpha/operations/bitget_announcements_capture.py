"""Immutable, provider-detached Bitget announcement capture boundary.

The module has no HTTP client, environment access, pointer, or live operator
command. It accepts already-read response bytes plus exact transport facts,
seals them in one immutable namespace, and re-derives every projection during
strict validation. Live acquisition remains a separate authorization and
implementation boundary.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Iterator, Mapping, Sequence
from urllib.parse import urlencode

from .bitget_announcements import (
    ANNOUNCEMENTS_PATH,
    DEFAULT_LANGUAGE,
    MAX_PAGE_SIZE,
    MAX_RESPONSE_BYTES_PER_PAGE,
    MAX_RESPONSE_PAGES,
    PROVIDER_ID,
    PUBLIC_API_BASE,
    BitgetAnnouncementError,
    build_bitget_announcement_request_plan,
    normalize_bitget_announcement_pages,
)
from .market_no_send_io import (
    _open_verified_namespace_dir,
    ensure_safe_namespace_dir,
    parse_json_object_bytes,
    write_bytes_immutable,
)
from .market_no_send_models import MarketNoSendError


CONTRACT_VERSION = "decision_radar_bitget_announcement_capture_v1"
CAPTURE_MODE_FIXTURE = "offline_fixture"
CAPTURE_MODE_LIVE = "live_public_http"
CAPTURE_MODES = frozenset({CAPTURE_MODE_FIXTURE})
LEDGER_FILENAME = "request_ledger.json"
SNAPSHOT_FILENAME = "normalized_snapshot.json"
MANIFEST_FILENAME = "capture_manifest.json"
RECEIPT_FILENAME = "capture_completion_receipt.json"
_LOCK_FILENAME = ".radar_bitget_announcement_capture.lock"
_NAMESPACE_RE = re.compile(
    r"^radar_bitget_announcements_[0-9]{8}t[0-9]{12}z_[a-f0-9]{12}$"
)
_RAW_PAGE_RE = re.compile(r"^response_page_([0-9]{3})\.json$")
_LINEAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CURSOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_MAX_CAPTURE_ARTIFACT_BYTES = 8_000_000


class BitgetAnnouncementCaptureError(ValueError):
    """Raised when capture preparation, persistence, or validation fails."""


@dataclass(frozen=True)
class _BitgetAnnouncementPageCapture:
    """Exact non-secret transport facts for one already-read response page."""

    page_number: int
    request_cursor: str | None
    request_url: str
    request_started_at: str
    response_headers_at: str
    response_body_read_at: str
    request_lineage_id: str
    status_code: int
    content_type: str
    redirect_count: int
    retry_count: int
    body: bytes


BitgetAnnouncementPageCapture = _BitgetAnnouncementPageCapture


@dataclass(frozen=True)
class _PreparedCapture:
    namespace: str
    capture_id: str
    completed_at: str
    payloads: tuple[tuple[str, bytes], ...]
    summary: Mapping[str, object]


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _pretty_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(dict(value), indent=2, sort_keys=True) + "\n").encode()


def _fingerprint(raw: bytes) -> dict[str, object]:
    return {"sha256": _sha256(raw), "size_bytes": len(raw)}


def _artifact(name: str, role: str, raw: bytes) -> dict[str, object]:
    return {"name": name, "role": role, **_fingerprint(raw)}


def _aware_utc(value: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise BitgetAnnouncementCaptureError(f"{field}_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BitgetAnnouncementCaptureError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BitgetAnnouncementCaptureError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _page_filename(page_number: int) -> str:
    return f"response_page_{page_number:03d}.json"


def _expected_url(
    cursor: str | None,
    *,
    start_time: datetime,
    end_time: datetime,
    limit: int,
    language: str,
    announcement_type: str | None,
) -> str:
    plan = build_bitget_announcement_request_plan(
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        language=language,
        announcement_type=announcement_type,
    )
    params = dict(plan["initial_query"])
    if cursor is not None:
        params["cursor"] = cursor
    return f"{PUBLIC_API_BASE}{ANNOUNCEMENTS_PATH}?{urlencode(params)}"


def _validate_page_capture(
    page: BitgetAnnouncementPageCapture,
    *,
    expected_page: int,
    start_time: datetime,
    end_time: datetime,
    limit: int,
    language: str,
    announcement_type: str | None,
) -> tuple[datetime, datetime, datetime]:
    if page.page_number != expected_page:
        raise BitgetAnnouncementCaptureError("capture_page_sequence_invalid")
    if page.request_cursor is not None and (
        not isinstance(page.request_cursor, str)
        or not _CURSOR_RE.fullmatch(page.request_cursor)
    ):
        raise BitgetAnnouncementCaptureError("capture_cursor_invalid")
    if page.request_url != _expected_url(
        page.request_cursor,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        language=language,
        announcement_type=announcement_type,
    ):
        raise BitgetAnnouncementCaptureError("capture_request_url_invalid")
    started = _aware_utc(page.request_started_at, "capture_request_started_at")
    headers = _aware_utc(page.response_headers_at, "capture_response_headers_at")
    body_read = _aware_utc(page.response_body_read_at, "capture_response_body_read_at")
    if not started <= headers <= body_read:
        raise BitgetAnnouncementCaptureError("capture_transport_clock_order_invalid")
    if (
        type(page.status_code) is not int
        or page.status_code != 200
        or not isinstance(page.content_type, str)
        or len(page.content_type) > 128
        or any(ord(char) < 32 or ord(char) == 127 for char in page.content_type)
        or page.content_type.split(";", 1)[0].strip().casefold() != "application/json"
        or type(page.redirect_count) is not int
        or page.redirect_count != 0
        or type(page.retry_count) is not int
        or page.retry_count != 0
    ):
        raise BitgetAnnouncementCaptureError("capture_transport_contract_invalid")
    if not isinstance(page.request_lineage_id, str) or not _LINEAGE_RE.fullmatch(
        page.request_lineage_id
    ):
        raise BitgetAnnouncementCaptureError("capture_lineage_invalid")
    if (
        not isinstance(page.body, bytes)
        or not page.body
        or len(page.body) > MAX_RESPONSE_BYTES_PER_PAGE
    ):
        raise BitgetAnnouncementCaptureError("capture_response_bytes_invalid")
    return started, headers, body_read


def _transport_row(
    page: BitgetAnnouncementPageCapture,
    *,
    started: datetime,
    headers: datetime,
    body_read: datetime,
) -> dict[str, object]:
    return {
        "page_number": page.page_number,
        "request_cursor": page.request_cursor,
        "method": "GET",
        "request_url": page.request_url,
        "request_started_at": _iso(started),
        "response_headers_at": _iso(headers),
        "response_body_read_at": _iso(body_read),
        "request_lineage_id": page.request_lineage_id,
        "status_code": page.status_code,
        "content_type": page.content_type,
        "redirect_count": page.redirect_count,
        "retry_count": page.retry_count,
        "response_artifact": _page_filename(page.page_number),
        "response_sha256": _sha256(page.body),
        "response_size_bytes": len(page.body),
    }


def _validated_transport_rows(
    pages: Sequence[BitgetAnnouncementPageCapture],
    *,
    start_time: datetime,
    end_time: datetime,
    limit: int,
    language: str,
    announcement_type: str | None,
) -> tuple[list[dict[str, object]], list[datetime]]:
    rows: list[dict[str, object]] = []
    body_read_times: list[datetime] = []
    prior_body_read: datetime | None = None
    for expected_page, page in enumerate(pages, start=1):
        started, headers, body_read = _validate_page_capture(
            page,
            expected_page=expected_page,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            language=language,
            announcement_type=announcement_type,
        )
        if prior_body_read is not None and started < prior_body_read:
            raise BitgetAnnouncementCaptureError("capture_requests_overlap")
        prior_body_read = body_read
        body_read_times.append(body_read)
        rows.append(
            _transport_row(page, started=started, headers=headers, body_read=body_read)
        )
    return rows, body_read_times


def _common(
    *,
    namespace: str,
    capture_id: str,
    capture_mode: str,
    completed_at: str,
    snapshot: Mapping[str, object],
    request_count: int,
) -> dict[str, object]:
    live = capture_mode == CAPTURE_MODE_LIVE
    complete = snapshot["coverage_status"] == "complete"
    return {
        "contract_version": CONTRACT_VERSION,
        "artifact_namespace": namespace,
        "capture_id": capture_id,
        "capture_mode": capture_mode,
        "provider": PROVIDER_ID,
        "source_class": "official_exchange",
        "completed_at": completed_at,
        "coverage_status": snapshot["coverage_status"],
        "coverage_complete": complete,
        "completion_evidence": snapshot["completion_evidence"],
        "accepted_announcement_count": snapshot["accepted_announcement_count"],
        "request_count": request_count,
        "transport_captured_by_project": live,
        "runtime_provider_authorized_at_capture": live,
        "input_quality_eligible": live and complete,
        "evidence_authority_eligible": False,
        "campaign_attached": False,
        "dashboard_authority_eligible": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "context_only": True,
        "directional_authority": False,
        "research_only": True,
        "no_send": True,
        "provider_calls_recorded": request_count if live else 0,
        "credentials_read": 0,
        "private_data_read": 0,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "telegram_sends": 0,
    }


def prepare_capture(
    pages: Sequence[BitgetAnnouncementPageCapture],
    *,
    start_time: str,
    end_time: str,
    capture_mode: str,
    limit: int = MAX_PAGE_SIZE,
    language: str = DEFAULT_LANGUAGE,
    announcement_type: str | None = None,
) -> _PreparedCapture:
    """Close an in-memory capture bundle without I/O."""

    if capture_mode == CAPTURE_MODE_LIVE:
        raise BitgetAnnouncementCaptureError("live_capture_transport_not_implemented")
    if capture_mode not in CAPTURE_MODES:
        raise BitgetAnnouncementCaptureError("capture_mode_invalid")
    if not pages or len(pages) > MAX_RESPONSE_PAGES:
        raise BitgetAnnouncementCaptureError("capture_page_count_invalid")
    start = _aware_utc(start_time, "capture_window_start")
    end = _aware_utc(end_time, "capture_window_end")
    if start >= end:
        raise BitgetAnnouncementCaptureError("capture_window_invalid")
    transport_rows, body_read_times = _validated_transport_rows(
        pages,
        start_time=start,
        end_time=end,
        limit=limit,
        language=language,
        announcement_type=announcement_type,
    )
    try:
        snapshot = normalize_bitget_announcement_pages(
            [page.body for page in pages],
            acquired_at_by_page=[_iso(value) for value in body_read_times],
            request_lineage_ids=[page.request_lineage_id for page in pages],
            request_cursors=[page.request_cursor for page in pages],
            start_time=_iso(start),
            end_time=_iso(end),
            limit=limit,
            language=language,
            announcement_type=announcement_type,
        )
    except BitgetAnnouncementError as exc:
        raise BitgetAnnouncementCaptureError(
            f"capture_response_contract_invalid:{exc}"
        ) from exc
    completed_at = _iso(body_read_times[-1])
    snapshot_raw = _pretty_bytes(snapshot)
    identity_input = {
        "contract_version": CONTRACT_VERSION,
        "capture_mode": capture_mode,
        "window_start": _iso(start),
        "window_end": _iso(end),
        "limit": limit,
        "language": language,
        "announcement_type": announcement_type,
        "transport_rows": transport_rows,
        "snapshot_sha256": _sha256(snapshot_raw),
    }
    capture_id = _sha256(_canonical_bytes(identity_input))
    stamp = body_read_times[-1].strftime("%Y%m%dt%H%M%S%fz")
    namespace = f"radar_bitget_announcements_{stamp}_{capture_id[:12]}"
    ledger = {
        "schema_id": "decision_radar.bitget_announcement_request_ledger",
        "schema_version": 1,
        "status": "complete" if snapshot["coverage_status"] == "complete" else "partial",
        "contract_version": CONTRACT_VERSION,
        "artifact_namespace": namespace,
        "capture_id": capture_id,
        "capture_mode": capture_mode,
        "provider": PROVIDER_ID,
        "method": "GET",
        "base_url": PUBLIC_API_BASE,
        "path": ANNOUNCEMENTS_PATH,
        "window_start": _iso(start),
        "window_end": _iso(end),
        "limit": limit,
        "language": language,
        "announcement_type": announcement_type,
        "pagination_policy": "last_annId_cursor_until_explicit_empty_response",
        "maximum_request_count": MAX_RESPONSE_PAGES,
        "redirects_allowed": False,
        "retries_allowed": False,
        "alternate_hosts_allowed": False,
        "proxy_or_vpn_bypass_allowed": False,
        "capture_started_at": transport_rows[0]["request_started_at"],
        "capture_completed_at": completed_at,
        "requests": transport_rows,
    }
    ledger_raw = _pretty_bytes(ledger)
    raw_payloads = tuple(
        (_page_filename(page.page_number), page.body) for page in pages
    )
    descriptors = [
        *(
            _artifact(name, "exact_provider_response_body", raw)
            for name, raw in raw_payloads
        ),
        _artifact(LEDGER_FILENAME, "exact_nonsecret_request_ledger", ledger_raw),
        _artifact(SNAPSHOT_FILENAME, "deterministic_normalized_snapshot", snapshot_raw),
    ]
    common = _common(
        namespace=namespace,
        capture_id=capture_id,
        capture_mode=capture_mode,
        completed_at=completed_at,
        snapshot=snapshot,
        request_count=len(pages),
    )
    manifest = {
        "schema_id": "decision_radar.bitget_announcement_capture_manifest",
        "schema_version": 1,
        "status": ledger["status"],
        **common,
        "artifacts": descriptors,
    }
    manifest_raw = _pretty_bytes(manifest)
    receipt = {
        "schema_id": "decision_radar.bitget_announcement_completion_receipt",
        "schema_version": 1,
        "status": ledger["status"],
        **common,
        "manifest": {"name": MANIFEST_FILENAME, **_fingerprint(manifest_raw)},
    }
    receipt_raw = _pretty_bytes(receipt)
    payloads = (
        *raw_payloads,
        (LEDGER_FILENAME, ledger_raw),
        (SNAPSHOT_FILENAME, snapshot_raw),
        (MANIFEST_FILENAME, manifest_raw),
        (RECEIPT_FILENAME, receipt_raw),
    )
    return _PreparedCapture(
        namespace=namespace,
        capture_id=capture_id,
        completed_at=completed_at,
        payloads=tuple(payloads),
        summary={
            "status": ledger["status"],
            **common,
            "artifact_count": len(payloads),
            "writes_performed": False,
        },
    )


@contextmanager
def _publication_lock(base: Path) -> Iterator[None]:
    descriptor: int | None = None
    locked = False
    try:
        with _open_verified_namespace_dir(base) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(_LOCK_FILENAME, flags, 0o600, dir_fd=namespace_fd)
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                raise BitgetAnnouncementCaptureError("capture_lock_invalid")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            yield
    except BitgetAnnouncementCaptureError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise BitgetAnnouncementCaptureError("capture_lock_unavailable") from exc
    finally:
        if locked and descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        if descriptor is not None:
            os.close(descriptor)


def _read_exact_capture_files(namespace_dir: Path) -> dict[str, bytes]:
    try:
        with _open_verified_namespace_dir(namespace_dir) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            names = set(os.listdir(namespace_fd))
            fixed = {
                LEDGER_FILENAME,
                SNAPSHOT_FILENAME,
                MANIFEST_FILENAME,
                RECEIPT_FILENAME,
            }
            page_names = sorted(name for name in names if _RAW_PAGE_RE.fullmatch(name))
            if (
                not page_names
                or len(page_names) > MAX_RESPONSE_PAGES
                or names != fixed | set(page_names)
                or page_names
                != [_page_filename(index) for index in range(1, len(page_names) + 1)]
            ):
                raise BitgetAnnouncementCaptureError("capture_artifact_set_invalid")
            files: dict[str, bytes] = {}
            for name in sorted(names):
                before = os.stat(name, dir_fd=namespace_fd, follow_symlinks=False)
                if (
                    not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or before.st_size < 0
                    or before.st_size > _MAX_CAPTURE_ARTIFACT_BYTES
                ):
                    raise BitgetAnnouncementCaptureError("capture_artifact_leaf_invalid")
                descriptor = os.open(
                    name,
                    os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=namespace_fd,
                )
                try:
                    opened = os.fstat(descriptor)
                    if not _same_file_snapshot(before, opened):
                        raise BitgetAnnouncementCaptureError(
                            "capture_artifact_identity_invalid"
                        )
                    chunks = []
                    remaining = before.st_size
                    while remaining:
                        chunk = os.read(descriptor, min(65_536, remaining))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        remaining -= len(chunk)
                    raw = b"".join(chunks)
                    current = os.stat(name, dir_fd=namespace_fd, follow_symlinks=False)
                    if (
                        remaining != 0
                        or len(raw) != before.st_size
                        or not _same_file_snapshot(before, os.fstat(descriptor))
                        or not _same_file_snapshot(before, current)
                    ):
                        raise BitgetAnnouncementCaptureError(
                            "capture_artifact_changed_during_read"
                        )
                    files[name] = raw
                finally:
                    os.close(descriptor)
            return files
    except BitgetAnnouncementCaptureError:
        raise
    except (MarketNoSendError, OSError) as exc:
        raise BitgetAnnouncementCaptureError("capture_artifact_unreadable") from exc


def _same_file_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev,
        left.st_ino,
        left.st_mode,
        left.st_nlink,
        left.st_size,
        left.st_mtime_ns,
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_mode,
        right.st_nlink,
        right.st_size,
        right.st_mtime_ns,
    )


def _parse_object(raw: bytes, reason: str) -> dict[str, Any]:
    try:
        return parse_json_object_bytes(raw)
    except MarketNoSendError as exc:
        raise BitgetAnnouncementCaptureError(reason) from exc


def _pages_from_ledger(
    ledger: Mapping[str, Any], files: Mapping[str, bytes]
) -> tuple[BitgetAnnouncementPageCapture, ...]:
    requests = ledger.get("requests")
    if not isinstance(requests, list) or not requests or len(requests) > MAX_RESPONSE_PAGES:
        raise BitgetAnnouncementCaptureError("capture_ledger_requests_invalid")
    expected_keys = {
        "page_number", "request_cursor", "method", "request_url",
        "request_started_at", "response_headers_at", "response_body_read_at",
        "request_lineage_id", "status_code", "content_type", "redirect_count",
        "retry_count", "response_artifact", "response_sha256", "response_size_bytes",
    }
    pages = []
    for index, row in enumerate(requests, start=1):
        if not isinstance(row, Mapping) or set(row) != expected_keys or row.get("method") != "GET":
            raise BitgetAnnouncementCaptureError("capture_ledger_request_invalid")
        name = _page_filename(index)
        raw = files.get(name)
        if (
            row.get("page_number") != index
            or row.get("response_artifact") != name
            or raw is None
            or row.get("response_sha256") != _sha256(raw)
            or row.get("response_size_bytes") != len(raw)
        ):
            raise BitgetAnnouncementCaptureError("capture_ledger_response_invalid")
        pages.append(
            BitgetAnnouncementPageCapture(
                page_number=index,
                request_cursor=row["request_cursor"],
                request_url=row["request_url"],
                request_started_at=row["request_started_at"],
                response_headers_at=row["response_headers_at"],
                response_body_read_at=row["response_body_read_at"],
                request_lineage_id=row["request_lineage_id"],
                status_code=row["status_code"],
                content_type=row["content_type"],
                redirect_count=row["redirect_count"],
                retry_count=row["retry_count"],
                body=raw,
            )
        )
    return tuple(pages)


def validate_capture(artifact_base_dir: str | Path, namespace: str) -> dict[str, object]:
    """Strictly re-derive one immutable namespace from exact response bytes."""

    if not _NAMESPACE_RE.fullmatch(namespace):
        raise BitgetAnnouncementCaptureError("capture_namespace_invalid")
    base = Path(artifact_base_dir).expanduser().absolute()
    files = _read_exact_capture_files(base / namespace)
    ledger = _parse_object(files[LEDGER_FILENAME], "capture_ledger_invalid")
    ledger_keys = {
        "schema_id", "schema_version", "status", "contract_version",
        "artifact_namespace", "capture_id", "capture_mode", "provider", "method",
        "base_url", "path", "window_start", "window_end", "limit", "language",
        "announcement_type", "pagination_policy", "maximum_request_count",
        "redirects_allowed", "retries_allowed", "alternate_hosts_allowed",
        "proxy_or_vpn_bypass_allowed", "capture_started_at", "capture_completed_at",
        "requests",
    }
    if (
        set(ledger) != ledger_keys
        or ledger.get("schema_id") != "decision_radar.bitget_announcement_request_ledger"
        or ledger.get("schema_version") != 1
        or ledger.get("contract_version") != CONTRACT_VERSION
        or ledger.get("artifact_namespace") != namespace
        or ledger.get("provider") != PROVIDER_ID
        or ledger.get("method") != "GET"
        or ledger.get("base_url") != PUBLIC_API_BASE
        or ledger.get("path") != ANNOUNCEMENTS_PATH
        or ledger.get("pagination_policy")
        != "last_annId_cursor_until_explicit_empty_response"
        or ledger.get("maximum_request_count") != MAX_RESPONSE_PAGES
        or any(
            ledger.get(key) is not False
            for key in (
                "redirects_allowed", "retries_allowed", "alternate_hosts_allowed",
                "proxy_or_vpn_bypass_allowed",
            )
        )
    ):
        raise BitgetAnnouncementCaptureError("capture_ledger_contract_invalid")
    pages = _pages_from_ledger(ledger, files)
    prepared = prepare_capture(
        pages,
        start_time=ledger["window_start"],
        end_time=ledger["window_end"],
        capture_mode=ledger["capture_mode"],
        limit=ledger["limit"],
        language=ledger["language"],
        announcement_type=ledger["announcement_type"],
    )
    expected = dict(prepared.payloads)
    if prepared.namespace != namespace or set(expected) != set(files):
        raise BitgetAnnouncementCaptureError("capture_identity_invalid")
    for name, raw in expected.items():
        if files[name] != raw:
            raise BitgetAnnouncementCaptureError(f"capture_artifact_drift:{name}")
    return {
        **dict(prepared.summary),
        "artifact_path": str(base / namespace),
        "receipt": {"name": RECEIPT_FILENAME, **_fingerprint(files[RECEIPT_FILENAME])},
        "strict_doctor_status": "pass",
    }


def persist_capture(
    artifact_base_dir: str | Path,
    pages: Sequence[BitgetAnnouncementPageCapture],
    *,
    start_time: str,
    end_time: str,
    capture_mode: str,
    confirm: bool = False,
    limit: int = MAX_PAGE_SIZE,
    language: str = DEFAULT_LANGUAGE,
    announcement_type: str | None = None,
) -> dict[str, object]:
    """Seal supplied bytes; never call a provider or publish a pointer."""

    if not confirm:
        raise BitgetAnnouncementCaptureError("explicit_confirmation_required")
    base = Path(artifact_base_dir).expanduser().absolute()
    if not base.is_dir():
        raise BitgetAnnouncementCaptureError("artifact_base_unavailable")
    prepared = prepare_capture(
        pages,
        start_time=start_time,
        end_time=end_time,
        capture_mode=capture_mode,
        limit=limit,
        language=language,
        announcement_type=announcement_type,
    )
    namespace_dir = base / prepared.namespace
    with _publication_lock(base):
        if namespace_dir.exists():
            result = validate_capture(base, prepared.namespace)
            return {
                **result,
                "created": False,
                "idempotent": True,
                "writes_performed": False,
            }
        try:
            ensure_safe_namespace_dir(namespace_dir)
            for name, raw in prepared.payloads:
                write_bytes_immutable(namespace_dir / name, raw)
        except MarketNoSendError as exc:
            raise BitgetAnnouncementCaptureError("capture_immutable_write_failed") from exc
        result = validate_capture(base, prepared.namespace)
    return {
        **result,
        "created": True,
        "idempotent": False,
        "writes_performed": True,
    }


def run_fixture_capture_smoke(fixture_dir: Path) -> dict[str, object]:
    """Prove immutable persistence/doctor mechanics in one disposable root."""

    bodies = tuple(path.read_bytes() for path in sorted(fixture_dir.glob("page_*.json")))
    if len(bodies) != 3:
        raise BitgetAnnouncementCaptureError("fixture_capture_page_count_invalid")
    start = _aware_utc("2026-07-19T00:00:00Z", "fixture_window_start")
    end = _aware_utc("2026-07-19T01:35:00Z", "fixture_window_end")
    cursors = (None, "900002", "900001")
    pages = tuple(
        BitgetAnnouncementPageCapture(
            page_number=index,
            request_cursor=cursors[index - 1],
            request_url=_expected_url(
                cursors[index - 1],
                start_time=start,
                end_time=end,
                limit=2,
                language=DEFAULT_LANGUAGE,
                announcement_type=None,
            ),
            request_started_at=f"2026-07-19T01:35:0{index - 1}.100000Z",
            response_headers_at=f"2026-07-19T01:35:0{index - 1}.500000Z",
            response_body_read_at=f"2026-07-19T01:35:0{index}Z",
            request_lineage_id=f"fixture.bitget.capture.page{index}",
            status_code=200,
            content_type="application/json; charset=utf-8",
            redirect_count=0,
            retry_count=0,
            body=body,
        )
        for index, body in enumerate(bodies, start=1)
    )
    with tempfile.TemporaryDirectory(prefix="radar_bitget_capture_smoke_") as root:
        result = persist_capture(
            root,
            pages,
            start_time=_iso(start),
            end_time=_iso(end),
            capture_mode=CAPTURE_MODE_FIXTURE,
            confirm=True,
            limit=2,
        )
        validated = validate_capture(root, str(result["artifact_namespace"]))
        return {
            key: value
            for key, value in {
                **validated,
                "artifact_path": None,
                "fixture_artifacts_retained": False,
                "disposable_artifact_write_count": result["artifact_count"],
                "provider_calls_performed_by_smoke": 0,
                "writes_performed": True,
            }.items()
            if key != "artifact_path" or value is not None
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=(Path(__file__).resolve().parents[3] / "fixtures" / "bitget_announcements"),
    )
    args = parser.parse_args(argv)
    try:
        result = run_fixture_capture_smoke(args.fixture_dir)
    except (BitgetAnnouncementCaptureError, OSError, ValueError) as exc:
        print(f"radar_bitget_announcement_capture_smoke_blocked: {type(exc).__name__}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


__all__ = (
    "CAPTURE_MODE_FIXTURE",
    "CAPTURE_MODE_LIVE",
    "CONTRACT_VERSION",
    "BitgetAnnouncementCaptureError",
    "BitgetAnnouncementPageCapture",
    "persist_capture",
    "prepare_capture",
    "run_fixture_capture_smoke",
    "validate_capture",
)


if __name__ == "__main__":
    raise SystemExit(main())
