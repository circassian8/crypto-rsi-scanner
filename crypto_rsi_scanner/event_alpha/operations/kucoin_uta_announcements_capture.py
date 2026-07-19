"""Immutable, provider-detached capture for KuCoin's current UTA endpoint.

This module has no HTTP client, environment access, pointer, or operator live
capture command.  It accepts already-read UTA response bytes plus exact
transport facts, writes only an explicitly confirmed fixture bundle, and
re-derives every artifact during strict validation.  The historical v1 capture
remains a separate audit contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

from .kucoin_announcements import (
    DEFAULT_ANNOUNCEMENT_TYPE,
    DEFAULT_LANGUAGE,
    MAX_REQUESTED_PAGE_SIZE,
    MAX_RESPONSE_BYTES_PER_PAGE,
    MAX_RESPONSE_PAGES,
    PROVIDER_ID,
    PUBLIC_API_BASE,
    KuCoinAnnouncementError,
)
from .kucoin_announcements_capture import (
    KuCoinAnnouncementCaptureError,
    _artifact,
    _aware_utc,
    _canonical_bytes,
    _fingerprint,
    _iso,
    _page_filename,
    _parse_object,
    _pretty_bytes,
    _publication_lock,
    _read_exact_capture_files,
    _sha256,
)
from .kucoin_uta_announcements import (
    ANNOUNCEMENTS_PATH,
    CONTRACT_VERSION as RESPONSE_CONTRACT_VERSION,
    build_kucoin_uta_announcement_request_plan,
    normalize_kucoin_uta_announcement_pages,
)
from .market_no_send_io import ensure_safe_namespace_dir, write_bytes_immutable
from .market_no_send_models import MarketNoSendError


CONTRACT_VERSION = "decision_radar_kucoin_uta_announcement_capture_v1"
CAPTURE_MODE_FIXTURE = "offline_fixture"
CAPTURE_MODE_LIVE = "live_public_http"
CAPTURE_MODES = frozenset({CAPTURE_MODE_FIXTURE})
LEDGER_FILENAME = "request_ledger.json"
SNAPSHOT_FILENAME = "normalized_snapshot.json"
MANIFEST_FILENAME = "capture_manifest.json"
RECEIPT_FILENAME = "capture_completion_receipt.json"
PAGINATION_POLICY = "contiguous_pageNumber_from_one_using_response_totalPage"
_NAMESPACE_RE = re.compile(
    r"^radar_kucoin_uta_announcements_[0-9]{8}t[0-9]{12}z_[a-f0-9]{12}$"
)
_LINEAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

# The shared exception and descriptor-held helpers are provider-local hardened
# I/O primitives.  The UTA endpoint, namespace, schemas, and identities below
# remain completely separate from the historical v1 capture contract.
KuCoinUtaAnnouncementCaptureError = KuCoinAnnouncementCaptureError


@dataclass(frozen=True)
class KuCoinUtaAnnouncementPageCapture:
    """Exact non-secret facts for one already-read UTA response page."""

    page_number: int
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


@dataclass(frozen=True)
class _PreparedCapture:
    namespace: str
    capture_id: str
    completed_at: str
    payloads: tuple[tuple[str, bytes], ...]
    summary: Mapping[str, object]


def _expected_url(
    page_number: int,
    *,
    start_time: datetime,
    end_time: datetime,
    requested_page_size: int,
    announcement_type: str,
    language: str,
) -> str:
    plan = build_kucoin_uta_announcement_request_plan(
        start_time=start_time,
        end_time=end_time,
        page_size=requested_page_size,
        announcement_type=announcement_type,
        language=language,
    )
    query = dict(plan["initial_query"])
    query["pageNumber"] = page_number
    return f"{PUBLIC_API_BASE}{ANNOUNCEMENTS_PATH}?{urlencode(query)}"


def _validate_page_capture(
    page: KuCoinUtaAnnouncementPageCapture,
    *,
    expected_page: int,
    start_time: datetime,
    end_time: datetime,
    requested_page_size: int,
    announcement_type: str,
    language: str,
) -> tuple[datetime, datetime, datetime]:
    if page.page_number != expected_page:
        raise KuCoinUtaAnnouncementCaptureError("capture_page_sequence_invalid")
    try:
        expected_url = _expected_url(
            expected_page,
            start_time=start_time,
            end_time=end_time,
            requested_page_size=requested_page_size,
            announcement_type=announcement_type,
            language=language,
        )
    except KuCoinAnnouncementError as exc:
        raise KuCoinUtaAnnouncementCaptureError(
            f"capture_request_contract_invalid:{exc}"
        ) from exc
    if page.request_url != expected_url:
        raise KuCoinUtaAnnouncementCaptureError("capture_request_url_invalid")
    started = _aware_utc(page.request_started_at, "capture_request_started_at")
    headers = _aware_utc(page.response_headers_at, "capture_response_headers_at")
    body_read = _aware_utc(page.response_body_read_at, "capture_response_body_read_at")
    if not started <= headers <= body_read:
        raise KuCoinUtaAnnouncementCaptureError("capture_transport_clock_order_invalid")
    if (
        type(page.status_code) is not int
        or page.status_code != 200
        or not isinstance(page.content_type, str)
        or len(page.content_type) > 128
        or any(ord(char) < 32 or ord(char) == 127 for char in page.content_type)
        or page.content_type.split(";", 1)[0].strip().casefold()
        != "application/json"
        or type(page.redirect_count) is not int
        or page.redirect_count != 0
        or type(page.retry_count) is not int
        or page.retry_count != 0
    ):
        raise KuCoinUtaAnnouncementCaptureError("capture_transport_contract_invalid")
    if not isinstance(page.request_lineage_id, str) or not _LINEAGE_RE.fullmatch(
        page.request_lineage_id
    ):
        raise KuCoinUtaAnnouncementCaptureError("capture_lineage_invalid")
    if (
        not isinstance(page.body, bytes)
        or not page.body
        or len(page.body) > MAX_RESPONSE_BYTES_PER_PAGE
    ):
        raise KuCoinUtaAnnouncementCaptureError("capture_response_bytes_invalid")
    return started, headers, body_read


def _transport_row(
    page: KuCoinUtaAnnouncementPageCapture,
    *,
    started: datetime,
    headers: datetime,
    body_read: datetime,
) -> dict[str, object]:
    return {
        "page_number": page.page_number,
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
    pages: Sequence[KuCoinUtaAnnouncementPageCapture],
    *,
    start_time: datetime,
    end_time: datetime,
    requested_page_size: int,
    announcement_type: str,
    language: str,
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
            requested_page_size=requested_page_size,
            announcement_type=announcement_type,
            language=language,
        )
        if prior_body_read is not None and started < prior_body_read:
            raise KuCoinUtaAnnouncementCaptureError("capture_requests_overlap")
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
    complete = snapshot["coverage_status"] == "complete"
    return {
        "contract_version": CONTRACT_VERSION,
        "response_contract_version": RESPONSE_CONTRACT_VERSION,
        "artifact_namespace": namespace,
        "capture_id": capture_id,
        "capture_mode": capture_mode,
        "provider": PROVIDER_ID,
        "source_class": "official_exchange",
        "endpoint": f"GET {PUBLIC_API_BASE}{ANNOUNCEMENTS_PATH}",
        "completed_at": completed_at,
        "coverage_status": snapshot["coverage_status"],
        "coverage_complete": complete,
        "completion_evidence": (
            "all_reported_pages_observed"
            if complete
            else "missing_reported_pages"
        ),
        "accepted_announcement_count": snapshot["accepted_announcement_count"],
        "request_count": request_count,
        "requested_page_size": snapshot["requested_page_size"],
        "response_page_size": snapshot["response_page_size"],
        "provider_adjusted_page_size": snapshot["provider_adjusted_page_size"],
        "total_pages_reported": snapshot["total_pages_reported"],
        "transport_captured_by_project": False,
        "runtime_provider_authorized_at_capture": False,
        "provider_calls_recorded": 0,
        "input_quality_eligible": False,
        "evidence_authority_eligible": False,
        "campaign_attached": False,
        "dashboard_authority_eligible": False,
        "pointer_publication_available": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "research_only": True,
        "no_send": True,
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
    pages: Sequence[KuCoinUtaAnnouncementPageCapture],
    *,
    start_time: str,
    end_time: str,
    capture_mode: str,
    requested_page_size: int = MAX_REQUESTED_PAGE_SIZE,
    announcement_type: str = DEFAULT_ANNOUNCEMENT_TYPE,
    language: str = DEFAULT_LANGUAGE,
) -> _PreparedCapture:
    """Close an in-memory current-UTA bundle without I/O."""

    if capture_mode == CAPTURE_MODE_LIVE:
        raise KuCoinUtaAnnouncementCaptureError(
            "live_capture_transport_not_implemented"
        )
    if capture_mode not in CAPTURE_MODES:
        raise KuCoinUtaAnnouncementCaptureError("capture_mode_invalid")
    if not pages or len(pages) > MAX_RESPONSE_PAGES:
        raise KuCoinUtaAnnouncementCaptureError("capture_page_count_invalid")
    start = _aware_utc(start_time, "capture_window_start")
    end = _aware_utc(end_time, "capture_window_end")
    if start >= end:
        raise KuCoinUtaAnnouncementCaptureError("capture_window_invalid")
    transport_rows, body_read_times = _validated_transport_rows(
        pages,
        start_time=start,
        end_time=end,
        requested_page_size=requested_page_size,
        announcement_type=announcement_type,
        language=language,
    )
    try:
        snapshot = normalize_kucoin_uta_announcement_pages(
            [page.body for page in pages],
            acquired_at_by_page=[_iso(value) for value in body_read_times],
            request_lineage_ids=[page.request_lineage_id for page in pages],
            start_time=_iso(start),
            end_time=_iso(end),
            requested_page_size=requested_page_size,
            announcement_type=announcement_type,
            language=language,
        ).to_dict()
    except KuCoinAnnouncementError as exc:
        raise KuCoinUtaAnnouncementCaptureError(
            f"capture_response_contract_invalid:{exc}"
        ) from exc
    completed_at = _iso(body_read_times[-1])
    identity_input = {
        "contract_version": CONTRACT_VERSION,
        "response_contract_version": RESPONSE_CONTRACT_VERSION,
        "capture_mode": capture_mode,
        "window_start": _iso(start),
        "window_end": _iso(end),
        "requested_page_size": requested_page_size,
        "announcement_type": announcement_type,
        "language": language,
        "pagination_policy": PAGINATION_POLICY,
        "transport_rows": transport_rows,
        "snapshot_sha256": _sha256(_pretty_bytes(snapshot)),
    }
    capture_id = _sha256(_canonical_bytes(identity_input))
    stamp = body_read_times[-1].strftime("%Y%m%dt%H%M%S%fz")
    namespace = f"radar_kucoin_uta_announcements_{stamp}_{capture_id[:12]}"
    status = "complete" if snapshot["coverage_status"] == "complete" else "partial"
    ledger = {
        "schema_id": "decision_radar.kucoin_uta_announcement_request_ledger",
        "schema_version": 1,
        "status": status,
        "contract_version": CONTRACT_VERSION,
        "response_contract_version": RESPONSE_CONTRACT_VERSION,
        "artifact_namespace": namespace,
        "capture_id": capture_id,
        "capture_mode": capture_mode,
        "provider": PROVIDER_ID,
        "method": "GET",
        "base_url": PUBLIC_API_BASE,
        "path": ANNOUNCEMENTS_PATH,
        "window_start": _iso(start),
        "window_end": _iso(end),
        "requested_page_size": requested_page_size,
        "announcement_type": announcement_type,
        "language": language,
        "pagination_policy": PAGINATION_POLICY,
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
    snapshot_raw = _pretty_bytes(snapshot)
    raw_payloads = tuple(
        (_page_filename(page.page_number), page.body) for page in pages
    )
    descriptors = [
        *(
            _artifact(name, "exact_current_uta_provider_response_body", raw)
            for name, raw in raw_payloads
        ),
        _artifact(LEDGER_FILENAME, "exact_current_uta_request_ledger", ledger_raw),
        _artifact(SNAPSHOT_FILENAME, "deterministic_current_uta_snapshot", snapshot_raw),
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
        "schema_id": "decision_radar.kucoin_uta_announcement_capture_manifest",
        "schema_version": 1,
        "status": status,
        **common,
        "artifacts": descriptors,
    }
    manifest_raw = _pretty_bytes(manifest)
    receipt = {
        "schema_id": "decision_radar.kucoin_uta_announcement_completion_receipt",
        "schema_version": 1,
        "status": status,
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
            "status": status,
            **common,
            "artifact_count": len(payloads),
            "writes_performed": False,
        },
    )


def _pages_from_ledger(
    ledger: Mapping[str, Any], files: Mapping[str, bytes]
) -> tuple[KuCoinUtaAnnouncementPageCapture, ...]:
    requests = ledger.get("requests")
    if not isinstance(requests, list) or not requests or len(requests) > MAX_RESPONSE_PAGES:
        raise KuCoinUtaAnnouncementCaptureError("capture_ledger_requests_invalid")
    expected_keys = {
        "page_number",
        "method",
        "request_url",
        "request_started_at",
        "response_headers_at",
        "response_body_read_at",
        "request_lineage_id",
        "status_code",
        "content_type",
        "redirect_count",
        "retry_count",
        "response_artifact",
        "response_sha256",
        "response_size_bytes",
    }
    pages = []
    for index, row in enumerate(requests, start=1):
        if (
            not isinstance(row, Mapping)
            or set(row) != expected_keys
            or row.get("method") != "GET"
        ):
            raise KuCoinUtaAnnouncementCaptureError("capture_ledger_request_invalid")
        name = _page_filename(index)
        raw = files.get(name)
        if (
            row.get("page_number") != index
            or row.get("response_artifact") != name
            or raw is None
            or row.get("response_sha256") != _sha256(raw)
            or row.get("response_size_bytes") != len(raw)
        ):
            raise KuCoinUtaAnnouncementCaptureError("capture_ledger_response_invalid")
        pages.append(
            KuCoinUtaAnnouncementPageCapture(
                page_number=index,
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
    """Strictly re-derive one immutable current-UTA namespace."""

    if not _NAMESPACE_RE.fullmatch(namespace):
        raise KuCoinUtaAnnouncementCaptureError("capture_namespace_invalid")
    base = Path(artifact_base_dir).expanduser().absolute()
    files = _read_exact_capture_files(base / namespace)
    ledger = _parse_object(files[LEDGER_FILENAME], "capture_ledger_invalid")
    ledger_keys = {
        "schema_id",
        "schema_version",
        "status",
        "contract_version",
        "response_contract_version",
        "artifact_namespace",
        "capture_id",
        "capture_mode",
        "provider",
        "method",
        "base_url",
        "path",
        "window_start",
        "window_end",
        "requested_page_size",
        "announcement_type",
        "language",
        "pagination_policy",
        "maximum_request_count",
        "redirects_allowed",
        "retries_allowed",
        "alternate_hosts_allowed",
        "proxy_or_vpn_bypass_allowed",
        "capture_started_at",
        "capture_completed_at",
        "requests",
    }
    if (
        set(ledger) != ledger_keys
        or ledger.get("schema_id")
        != "decision_radar.kucoin_uta_announcement_request_ledger"
        or ledger.get("schema_version") != 1
        or ledger.get("contract_version") != CONTRACT_VERSION
        or ledger.get("response_contract_version") != RESPONSE_CONTRACT_VERSION
        or ledger.get("artifact_namespace") != namespace
        or ledger.get("provider") != PROVIDER_ID
        or ledger.get("method") != "GET"
        or ledger.get("base_url") != PUBLIC_API_BASE
        or ledger.get("path") != ANNOUNCEMENTS_PATH
        or ledger.get("pagination_policy") != PAGINATION_POLICY
        or ledger.get("maximum_request_count") != MAX_RESPONSE_PAGES
        or any(
            ledger.get(key) is not False
            for key in (
                "redirects_allowed",
                "retries_allowed",
                "alternate_hosts_allowed",
                "proxy_or_vpn_bypass_allowed",
            )
        )
    ):
        raise KuCoinUtaAnnouncementCaptureError("capture_ledger_contract_invalid")
    pages = _pages_from_ledger(ledger, files)
    prepared = prepare_capture(
        pages,
        start_time=ledger["window_start"],
        end_time=ledger["window_end"],
        capture_mode=ledger["capture_mode"],
        requested_page_size=ledger["requested_page_size"],
        announcement_type=ledger["announcement_type"],
        language=ledger["language"],
    )
    expected = dict(prepared.payloads)
    if prepared.namespace != namespace or set(expected) != set(files):
        raise KuCoinUtaAnnouncementCaptureError("capture_identity_invalid")
    for name, raw in expected.items():
        if files[name] != raw:
            raise KuCoinUtaAnnouncementCaptureError(f"capture_artifact_drift:{name}")
    return {
        **dict(prepared.summary),
        "artifact_path": str(base / namespace),
        "receipt": {"name": RECEIPT_FILENAME, **_fingerprint(files[RECEIPT_FILENAME])},
        "strict_doctor_status": "pass",
    }


def persist_capture(
    artifact_base_dir: str | Path,
    pages: Sequence[KuCoinUtaAnnouncementPageCapture],
    *,
    start_time: str,
    end_time: str,
    capture_mode: str,
    confirm: bool = False,
    requested_page_size: int = MAX_REQUESTED_PAGE_SIZE,
    announcement_type: str = DEFAULT_ANNOUNCEMENT_TYPE,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, object]:
    """Seal supplied current UTA bytes; never call or publish."""

    if not confirm:
        raise KuCoinUtaAnnouncementCaptureError("explicit_confirmation_required")
    base = Path(artifact_base_dir).expanduser().absolute()
    if not base.is_dir():
        raise KuCoinUtaAnnouncementCaptureError("artifact_base_unavailable")
    prepared = prepare_capture(
        pages,
        start_time=start_time,
        end_time=end_time,
        capture_mode=capture_mode,
        requested_page_size=requested_page_size,
        announcement_type=announcement_type,
        language=language,
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
            raise KuCoinUtaAnnouncementCaptureError(
                "capture_immutable_write_failed"
            ) from exc
        result = validate_capture(base, prepared.namespace)
    return {
        **result,
        "created": True,
        "idempotent": False,
        "writes_performed": True,
    }


def run_fixture_capture_smoke(fixture_dir: Path) -> dict[str, object]:
    """Prove current UTA persistence/doctor in one disposable root."""

    bodies = tuple(path.read_bytes() for path in sorted(fixture_dir.glob("page_*.json")))
    if len(bodies) != 2:
        raise KuCoinUtaAnnouncementCaptureError("fixture_capture_page_count_invalid")
    request_times = (
        ("2026-07-19T01:35:00.100000Z", "2026-07-19T01:35:00.500000Z", "2026-07-19T01:35:01Z"),
        ("2026-07-19T01:35:01.100000Z", "2026-07-19T01:35:01.500000Z", "2026-07-19T01:35:02Z"),
    )
    pages = tuple(
        KuCoinUtaAnnouncementPageCapture(
            page_number=index,
            request_url=_expected_url(
                index,
                start_time=datetime(2026, 7, 19, tzinfo=timezone.utc),
                end_time=datetime(2026, 7, 19, 1, 35, tzinfo=timezone.utc),
                requested_page_size=MAX_REQUESTED_PAGE_SIZE,
                announcement_type=DEFAULT_ANNOUNCEMENT_TYPE,
                language=DEFAULT_LANGUAGE,
            ),
            request_started_at=request_times[index - 1][0],
            response_headers_at=request_times[index - 1][1],
            response_body_read_at=request_times[index - 1][2],
            request_lineage_id=f"fixture.kucoin.uta.capture.page{index}",
            status_code=200,
            content_type=(
                "application/json; charset=utf-8" if index == 1 else "application/json"
            ),
            redirect_count=0,
            retry_count=0,
            body=body,
        )
        for index, body in enumerate(bodies, start=1)
    )
    with tempfile.TemporaryDirectory(prefix="radar_kucoin_uta_capture_smoke_") as root:
        result = persist_capture(
            root,
            pages,
            start_time="2026-07-19T00:00:00Z",
            end_time="2026-07-19T01:35:00Z",
            capture_mode=CAPTURE_MODE_FIXTURE,
            confirm=True,
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
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=(
            Path(__file__).resolve().parents[3]
            / "fixtures"
            / "kucoin_uta_announcements"
        ),
    )
    args = parser.parse_args(argv)
    try:
        result = run_fixture_capture_smoke(args.fixture_dir)
    except (KuCoinUtaAnnouncementCaptureError, OSError, ValueError) as exc:
        print(f"radar_kucoin_uta_announcement_capture_smoke_blocked: {type(exc).__name__}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


__all__ = (
    "CAPTURE_MODE_FIXTURE",
    "CAPTURE_MODE_LIVE",
    "CONTRACT_VERSION",
    "KuCoinUtaAnnouncementCaptureError",
    "KuCoinUtaAnnouncementPageCapture",
    "persist_capture",
    "prepare_capture",
    "run_fixture_capture_smoke",
    "validate_capture",
)


if __name__ == "__main__":
    raise SystemExit(main())
