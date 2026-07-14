"""Guarded producer for an authoritative U.S. macro calendar snapshot.

Live acquisition is off by default and requires explicit, already-present
authorization plus a contact address for the honest BLS user agent.  One run
attempts each source exactly once, in a fixed order, and accepts only a complete
Federal Reserve/BLS/BEA pack.  Local import is an explicit no-network path.

Every attempted pack gets a new immutable directory.  A failed attempt records
an allowlisted receipt but never changes the last-success pointer.  The emitted
snapshot is the existing Decision Radar market-no-send calendar contract; the
market generation remains responsible for copying and fingerprinting that exact
snapshot into its own immutable generation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import socket
import stat
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from ..radar.calendar.official_macro import (
    OfficialMacroParseError,
    OfficialMacroParsedSource,
    merge_official_macro_sources,
    parse_bea_release_dates_json,
    parse_bls_release_calendar_ics,
    parse_federal_reserve_fomc_html,
)
from ._official_macro_sources import (
    OFFICIAL_MACRO_SOURCES,
    OfficialMacroAcquisitionError,
    OfficialMacroFetcher,
    OfficialMacroHTTPResponse,
    OfficialMacroSourceSpec,
    checked_in_nonlive_source_path as _checked_in_nonlive_source_path,
    fetch_official_source as _fetch_official_source,
    is_checked_in_fixture_content as _is_checked_in_fixture_content,
    local_content_type as _local_content_type,
    normalized_content_type as _normalized_content_type,
    read_local_source as _read_local_source,
    safe_code as _safe_code,
    validate_response as _validate_response,
)
from .market_no_send_calendar import (
    CALENDAR_SNAPSHOT_CONTRACT_VERSION,
    CALENDAR_SNAPSHOT_PATH_ENV,
    load_market_no_send_calendar_snapshot,
)
from .market_no_send_io import (
    ensure_safe_namespace_dir,
    read_regular_bytes,
    write_bytes_atomic,
    write_json_atomic,
)
from .market_no_send_models import MarketNoSendError


OFFICIAL_MACRO_LIVE_AUTH_ENV = "RSI_DECISION_RADAR_MACRO_CALENDAR_LIVE"
OFFICIAL_MACRO_CONTACT_ENV = "RSI_DECISION_RADAR_BLS_CONTACT"
DEFAULT_OFFICIAL_MACRO_BASE = Path("event_fade_cache/official_macro_calendar")
OFFICIAL_MACRO_SNAPSHOT_FILENAME = "official_macro_calendar.json"
OFFICIAL_MACRO_RECEIPT_FILENAME = "acquisition_receipt.json"
OFFICIAL_MACRO_STATE_DIRNAME = "state"
OFFICIAL_MACRO_LATEST_ATTEMPT_FILENAME = "latest_attempt.json"
OFFICIAL_MACRO_LATEST_SUCCESS_FILENAME = "latest_success.json"
OFFICIAL_MACRO_CONTRACT_VERSION = 1

_CONTACT_RE = re.compile(r"^[^\s@]{1,120}@[^\s@]{1,120}\.[^\s@]{2,40}$")
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
@dataclass(frozen=True)
class _OfficialMacroReadiness:
    status: str
    live_acquisition_authorized: bool
    contact_configured: bool
    provider_call_attempted: bool = False
    provider_authorization_mutated: bool = False
    output_base: str = ""
    latest_attempt_status: str = "none"
    latest_success_status: str = "none"
    reason_codes: tuple[str, ...] = ()
    next_safe_command: str = ""
    research_only: bool = True
    no_send: bool = True
    strict_alerts_created: int = 0
    telegram_sends: int = 0
    trades_created: int = 0
    paper_trades_created: int = 0
    normal_rsi_signal_rows_written: int = 0
    triggered_fade_created: int = 0

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reason_codes"] = list(self.reason_codes)
        payload["ready"] = self.ready
        return payload


OfficialMacroReadiness = _OfficialMacroReadiness


@dataclass(frozen=True)
class _OfficialMacroOperationResult:
    status: str
    acquisition_mode: str
    attempted_at: str
    attempt_id: str | None = None
    reason_code: str | None = None
    failure_source: str | None = None
    provider_call_count: int = 0
    provider_request_succeeded_count: int = 0
    source_results: tuple[Mapping[str, Any], ...] = ()
    event_count: int = 0
    attempt_dir: Path | None = None
    snapshot_path: Path | None = None
    receipt_path: Path | None = None
    snapshot_sha256: str | None = None
    provider_authorization_mutated: bool = False
    research_only: bool = True
    no_send: bool = True
    strict_alerts_created: int = 0
    telegram_sends: int = 0
    trades_created: int = 0
    paper_trades_created: int = 0
    normal_rsi_signal_rows_written: int = 0
    triggered_fade_created: int = 0

    @property
    def complete(self) -> bool:
        return self.status == "complete"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("attempt_dir", "snapshot_path", "receipt_path"):
            value = payload.get(key)
            payload[key] = str(value) if value is not None else None
        payload["source_results"] = [dict(row) for row in self.source_results]
        payload["complete"] = self.complete
        return payload


OfficialMacroOperationResult = _OfficialMacroOperationResult


def official_macro_calendar_readiness(
    *,
    environ: Mapping[str, str] | None = None,
    output_base: str | Path = DEFAULT_OFFICIAL_MACRO_BASE,
) -> OfficialMacroReadiness:
    """Inspect live authorization and existing receipts without I/O mutation."""

    env = os.environ if environ is None else environ
    authorized = _enabled(env.get(OFFICIAL_MACRO_LIVE_AUTH_ENV))
    contact_configured = _valid_contact(env.get(OFFICIAL_MACRO_CONTACT_ENV))
    reasons: list[str] = []
    if not authorized:
        reasons.append("live_calendar_authorization_missing")
    if not contact_configured:
        reasons.append("bls_contact_missing_or_invalid")
    base = Path(output_base).expanduser().absolute()
    attempt_status = _read_pointer_status(
        base / OFFICIAL_MACRO_STATE_DIRNAME / OFFICIAL_MACRO_LATEST_ATTEMPT_FILENAME
    )
    try:
        success_snapshot = resolve_latest_official_macro_snapshot(base)
    except OfficialMacroAcquisitionError:
        success_status = "invalid"
    else:
        success_status = "complete" if success_snapshot is not None else "none"
    command = (
        "python -m crypto_rsi_scanner.event_alpha.operations.official_macro_calendar acquire"
        if authorized and contact_configured
        else "configure explicit calendar authorization or use import-local"
    )
    return OfficialMacroReadiness(
        status="ready" if not reasons else "blocked",
        live_acquisition_authorized=authorized,
        contact_configured=contact_configured,
        output_base=str(base),
        latest_attempt_status=attempt_status,
        latest_success_status=success_status,
        reason_codes=tuple(reasons),
        next_safe_command=command,
    )


def resolve_latest_official_macro_snapshot(
    output_base: str | Path = DEFAULT_OFFICIAL_MACRO_BASE,
) -> Path | None:
    """Return the exact latest-success snapshot only after full hash attestation."""

    base = Path(output_base).expanduser().absolute()
    pointer_path = (
        base / OFFICIAL_MACRO_STATE_DIRNAME / OFFICIAL_MACRO_LATEST_SUCCESS_FILENAME
    )
    if not pointer_path.parent.exists():
        return None
    try:
        pointer_raw = read_regular_bytes(pointer_path, missing_ok=True)
        if pointer_raw is None:
            return None
        pointer = _decoded_json_object(pointer_raw)
        _validate_success_pointer(pointer)
        attempt_id = str(pointer["attempt_id"])
        attempt_dir = base / attempt_id
        receipt_path = attempt_dir / OFFICIAL_MACRO_RECEIPT_FILENAME
        snapshot_path = attempt_dir / OFFICIAL_MACRO_SNAPSHOT_FILENAME
        if Path(str(pointer["receipt_path"])).expanduser().absolute() != receipt_path:
            raise OfficialMacroAcquisitionError("latest_success_receipt_path_invalid")
        if Path(str(pointer["snapshot_path"])).expanduser().absolute() != snapshot_path:
            raise OfficialMacroAcquisitionError("latest_success_snapshot_path_invalid")

        receipt_raw = read_regular_bytes(receipt_path)
        snapshot_raw = read_regular_bytes(snapshot_path)
        if receipt_raw is None or snapshot_raw is None:
            raise OfficialMacroAcquisitionError("latest_success_artifact_missing")
        if hashlib.sha256(receipt_raw).hexdigest() != pointer["receipt_sha256"]:
            raise OfficialMacroAcquisitionError("latest_success_receipt_digest_mismatch")
        if hashlib.sha256(snapshot_raw).hexdigest() != pointer["snapshot_sha256"]:
            raise OfficialMacroAcquisitionError("latest_success_snapshot_digest_mismatch")

        receipt = _decoded_json_object(receipt_raw)
        _validate_success_receipt(receipt, pointer)
        _validate_success_snapshot(_decoded_json_object(snapshot_raw), pointer)
        _verify_source_artifacts(attempt_dir, receipt)
        attempted_at = _as_utc(str(pointer["attempted_at"]))
        snapshot_check = load_market_no_send_calendar_snapshot(
            environ={CALENDAR_SNAPSHOT_PATH_ENV: str(snapshot_path)},
            now=attempted_at,
            data_mode="live",
            run_mode="operational",
        )
        if not snapshot_check.usable:
            raise OfficialMacroAcquisitionError("latest_success_snapshot_contract_invalid")
        return snapshot_path
    except OfficialMacroAcquisitionError:
        raise
    except (MarketNoSendError, OSError, ValueError, KeyError, TypeError):
        raise OfficialMacroAcquisitionError("latest_success_attestation_failed") from None


def acquire_official_macro_calendar(
    *,
    environ: Mapping[str, str] | None = None,
    output_base: str | Path = DEFAULT_OFFICIAL_MACRO_BASE,
    observed_at: datetime | str | None = None,
    fetcher: OfficialMacroFetcher | None = None,
) -> OfficialMacroOperationResult:
    """Acquire one all-required official pack with at most one call per source."""

    env = os.environ if environ is None else environ
    attempted = _as_utc(observed_at)
    if not _enabled(env.get(OFFICIAL_MACRO_LIVE_AUTH_ENV)):
        return _blocked_result(
            attempted, mode="live_provider", reason="live_calendar_authorization_missing"
        )
    contact = str(env.get(OFFICIAL_MACRO_CONTACT_ENV) or "").strip()
    if not _valid_contact(contact):
        return _blocked_result(
            attempted, mode="live_provider", reason="bls_contact_missing_or_invalid"
        )
    user_agent = f"crypto-rsi-scanner-calendar/1.0 ({contact})"
    provider = fetcher or _fetch_official_source

    def load_source(spec: OfficialMacroSourceSpec) -> OfficialMacroHTTPResponse:
        try:
            response = provider(spec, user_agent)
        except OfficialMacroAcquisitionError:
            raise
        except (HTTPError, URLError, TimeoutError, socket.timeout, OSError) as exc:
            status = exc.code if isinstance(exc, HTTPError) else None
            raise OfficialMacroAcquisitionError(
                "source_request_failed", source=spec.name, http_status=status
            ) from None
        except Exception:
            raise OfficialMacroAcquisitionError(
                "source_request_failed", source=spec.name
            ) from None
        return response

    return _produce_pack(
        output_base=output_base,
        attempted=attempted,
        acquisition_mode="live_provider",
        source_loader=load_source,
        provider_calls_expected=True,
    )


def import_official_macro_calendar(
    *,
    federal_reserve_html: str | Path,
    bls_ics: str | Path,
    bea_json: str | Path,
    output_base: str | Path = DEFAULT_OFFICIAL_MACRO_BASE,
    observed_at: datetime | str | None = None,
) -> OfficialMacroOperationResult:
    """Import an explicit complete local source pack without network access."""

    if observed_at is None or str(observed_at).strip() == "":
        return _blocked_result(
            datetime.now(timezone.utc),
            mode="operator_verified_export",
            reason="local_import_observed_at_required",
        )
    attempted = _as_utc(observed_at)
    paths = {
        "federal_reserve": Path(federal_reserve_html).expanduser().absolute(),
        "bls": Path(bls_ics).expanduser().absolute(),
        "bea": Path(bea_json).expanduser().absolute(),
    }
    for source, path in paths.items():
        if _checked_in_nonlive_source_path(path):
            return _blocked_result(
                attempted,
                mode="operator_verified_export",
                reason="local_import_nonlive_path_rejected",
                failure_source=source,
            )

    local_bodies: dict[str, bytes] = {}
    local_failures: dict[str, OfficialMacroAcquisitionError] = {}
    for spec in OFFICIAL_MACRO_SOURCES:
        try:
            body = _read_local_source(
                paths[spec.name], maximum_bytes=spec.maximum_bytes
            )
        except OfficialMacroAcquisitionError as exc:
            local_failures[spec.name] = exc
            continue
        if _is_checked_in_fixture_content(spec.name, body):
            return _blocked_result(
                attempted,
                mode="operator_verified_export",
                reason="local_import_nonlive_content_rejected",
                failure_source=spec.name,
            )
        local_bodies[spec.name] = body

    def load_source(spec: OfficialMacroSourceSpec) -> OfficialMacroHTTPResponse:
        if spec.name in local_failures:
            raise local_failures[spec.name]
        return OfficialMacroHTTPResponse(
            body=local_bodies[spec.name],
            status=200,
            content_type=_local_content_type(spec.name),
            final_url=spec.url,
        )

    return _produce_pack(
        output_base=output_base,
        attempted=attempted,
        acquisition_mode="operator_verified_export",
        source_loader=load_source,
        provider_calls_expected=False,
    )


def _produce_pack(
    *,
    output_base: str | Path,
    attempted: datetime,
    acquisition_mode: str,
    source_loader: Callable[[OfficialMacroSourceSpec], OfficialMacroHTTPResponse],
    provider_calls_expected: bool,
) -> OfficialMacroOperationResult:
    base = Path(output_base).expanduser().absolute()
    try:
        _prepare_output_base(base)
        attempt_id = _attempt_id(attempted)
        attempt_dir = base / attempt_id
        _create_attempt_dir(base, attempt_id)
    except (MarketNoSendError, OSError, ValueError):
        return OfficialMacroOperationResult(
            status="failed",
            acquisition_mode=acquisition_mode,
            attempted_at=attempted.isoformat(),
            reason_code="artifact_base_unavailable",
        )

    (
        parsed_sources,
        source_results,
        provider_calls,
        provider_successes,
        failure,
    ) = _load_pack_sources(
        attempt_dir=attempt_dir,
        attempted=attempted,
        source_loader=source_loader,
        provider_calls_expected=provider_calls_expected,
    )

    if failure is not None:
        return _finish_attempt(
            base=base,
            attempt_dir=attempt_dir,
            attempt_id=attempt_id,
            attempted=attempted,
            acquisition_mode=acquisition_mode,
            status="failed",
            reason_code=failure.reason_code,
            failure_source=failure.source,
            source_results=source_results,
            provider_calls=provider_calls,
            provider_successes=provider_successes,
        )

    try:
        events = merge_official_macro_sources(parsed_sources)
        snapshot = _snapshot_payload(
            events=events,
            observed_at=attempted,
            acquisition_mode=acquisition_mode,
        )
        snapshot_bytes = _json_bytes(snapshot)
        snapshot_path = attempt_dir / OFFICIAL_MACRO_SNAPSHOT_FILENAME
        write_bytes_atomic(snapshot_path, snapshot_bytes)
        verification = load_market_no_send_calendar_snapshot(
            environ={CALENDAR_SNAPSHOT_PATH_ENV: str(snapshot_path)},
            now=attempted,
            data_mode="live",
            run_mode="operational",
        )
        if not verification.usable:
            raise OfficialMacroAcquisitionError(
                "snapshot_contract_rejected", source=None
            )
        snapshot_digest = hashlib.sha256(snapshot_bytes).hexdigest()
    except OfficialMacroAcquisitionError as exc:
        return _finish_attempt(
            base=base,
            attempt_dir=attempt_dir,
            attempt_id=attempt_id,
            attempted=attempted,
            acquisition_mode=acquisition_mode,
            status="failed",
            reason_code=exc.reason_code,
            failure_source=exc.source,
            source_results=source_results,
            provider_calls=provider_calls,
            provider_successes=provider_successes,
        )
    except (OfficialMacroParseError, MarketNoSendError, OSError, ValueError):
        return _finish_attempt(
            base=base,
            attempt_dir=attempt_dir,
            attempt_id=attempt_id,
            attempted=attempted,
            acquisition_mode=acquisition_mode,
            status="failed",
            reason_code="snapshot_materialization_failed",
            failure_source=None,
            source_results=source_results,
            provider_calls=provider_calls,
            provider_successes=provider_successes,
        )

    return _finish_attempt(
        base=base,
        attempt_dir=attempt_dir,
        attempt_id=attempt_id,
        attempted=attempted,
        acquisition_mode=acquisition_mode,
        status="complete",
        reason_code=None,
        failure_source=None,
        source_results=source_results,
        provider_calls=provider_calls,
        provider_successes=provider_successes,
        event_count=len(events),
        snapshot_path=snapshot_path,
        snapshot_sha256=snapshot_digest,
    )


def _load_pack_sources(
    *,
    attempt_dir: Path,
    attempted: datetime,
    source_loader: Callable[[OfficialMacroSourceSpec], OfficialMacroHTTPResponse],
    provider_calls_expected: bool,
) -> tuple[
    list[OfficialMacroParsedSource],
    list[dict[str, Any]],
    int,
    int,
    OfficialMacroAcquisitionError | None,
]:
    parsed_sources: list[OfficialMacroParsedSource] = []
    source_results: list[dict[str, Any]] = []
    provider_calls = 0
    provider_successes = 0
    failure: OfficialMacroAcquisitionError | None = None
    for spec in OFFICIAL_MACRO_SOURCES:
        source_result: dict[str, Any] = {
            "source": spec.name,
            "source_url": spec.url,
            "request_attempted": provider_calls_expected,
        }
        if provider_calls_expected:
            provider_calls += 1
        try:
            response = source_loader(spec)
            body = _validate_response(spec, response)
            if provider_calls_expected:
                provider_successes += 1
            source_result.update(
                {
                    "http_status": response.status if provider_calls_expected else None,
                    "content_type": _normalized_content_type(response.content_type),
                    "size_bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "raw_filename": spec.raw_filename,
                }
            )
            write_bytes_atomic(attempt_dir / spec.raw_filename, body)
            parsed = _parse_source(spec.name, body, acquired_at=attempted)
            parsed_sources.append(parsed)
            source_result.update(
                {
                    "status": "accepted",
                    "source_rows_seen": parsed.source_rows_seen,
                    "accepted_rows": len(parsed.rows),
                    "rejected_rows": parsed.rejected_rows,
                }
            )
            source_results.append(source_result)
        except OfficialMacroParseError as exc:
            failure = OfficialMacroAcquisitionError(
                f"parse_{_safe_code(exc.code)}", source=spec.name
            )
        except OfficialMacroAcquisitionError as exc:
            failure = OfficialMacroAcquisitionError(
                exc.reason_code,
                source=exc.source or spec.name,
                http_status=exc.http_status,
            )
        except (MarketNoSendError, OSError, ValueError):
            failure = OfficialMacroAcquisitionError(
                "source_artifact_write_failed", source=spec.name
            )
        if failure is not None:
            source_result.update(
                {
                    "status": "failed",
                    "failure_class": failure.reason_code,
                    "http_status": failure.http_status
                    if failure.http_status is not None
                    else source_result.get("http_status"),
                }
            )
            source_results.append(source_result)
            break
    return (
        parsed_sources,
        source_results,
        provider_calls,
        provider_successes,
        failure,
    )


def _finish_attempt(
    *,
    base: Path,
    attempt_dir: Path,
    attempt_id: str,
    attempted: datetime,
    acquisition_mode: str,
    status: str,
    reason_code: str | None,
    failure_source: str | None,
    source_results: Sequence[Mapping[str, Any]],
    provider_calls: int,
    provider_successes: int,
    event_count: int = 0,
    snapshot_path: Path | None = None,
    snapshot_sha256: str | None = None,
) -> OfficialMacroOperationResult:
    receipt_path = attempt_dir / OFFICIAL_MACRO_RECEIPT_FILENAME
    receipt = {
        "contract_version": OFFICIAL_MACRO_CONTRACT_VERSION,
        "row_type": "official_macro_calendar_acquisition_receipt",
        "attempt_id": attempt_id,
        "status": status,
        "attempted_at": attempted.isoformat(),
        "acquisition_mode": acquisition_mode,
        "reason_code": reason_code,
        "failure_source": failure_source,
        "provider_call_count": provider_calls,
        "provider_request_succeeded_count": provider_successes,
        "source_results": [dict(row) for row in source_results],
        "event_count": event_count,
        "snapshot_filename": snapshot_path.name if snapshot_path else None,
        "snapshot_sha256": snapshot_sha256,
        "all_required_sources_accepted": status == "complete",
        "provider_authorization_mutated": False,
        **_safety_fields(),
    }
    try:
        write_json_atomic(receipt_path, receipt)
        receipt_digest = hashlib.sha256(read_regular_bytes(receipt_path) or b"").hexdigest()
        pointer = {
            "contract_version": OFFICIAL_MACRO_CONTRACT_VERSION,
            "row_type": "official_macro_calendar_attempt_pointer",
            "attempt_id": attempt_id,
            "status": status,
            "attempted_at": attempted.isoformat(),
            "acquisition_mode": acquisition_mode,
            "reason_code": reason_code,
            "receipt_path": str(receipt_path),
            "receipt_sha256": receipt_digest,
            "snapshot_path": str(snapshot_path) if snapshot_path else None,
            "snapshot_sha256": snapshot_sha256,
            "provider_call_count": provider_calls,
            "event_count": event_count,
            **_safety_fields(),
        }
        state_dir = base / OFFICIAL_MACRO_STATE_DIRNAME
        write_json_atomic(state_dir / OFFICIAL_MACRO_LATEST_ATTEMPT_FILENAME, pointer)
        if status == "complete":
            success_pointer = dict(pointer)
            success_pointer["row_type"] = "official_macro_calendar_success_pointer"
            write_json_atomic(
                state_dir / OFFICIAL_MACRO_LATEST_SUCCESS_FILENAME,
                success_pointer,
            )
    except (MarketNoSendError, OSError, ValueError):
        return OfficialMacroOperationResult(
            status="failed",
            acquisition_mode=acquisition_mode,
            attempted_at=attempted.isoformat(),
            attempt_id=attempt_id,
            reason_code="attempt_receipt_write_failed",
            failure_source=failure_source,
            provider_call_count=provider_calls,
            provider_request_succeeded_count=provider_successes,
            source_results=tuple(dict(row) for row in source_results),
            attempt_dir=attempt_dir,
            snapshot_path=snapshot_path,
            receipt_path=receipt_path,
            snapshot_sha256=snapshot_sha256,
        )
    return OfficialMacroOperationResult(
        status=status,
        acquisition_mode=acquisition_mode,
        attempted_at=attempted.isoformat(),
        attempt_id=attempt_id,
        reason_code=reason_code,
        failure_source=failure_source,
        provider_call_count=provider_calls,
        provider_request_succeeded_count=provider_successes,
        source_results=tuple(dict(row) for row in source_results),
        event_count=event_count,
        attempt_dir=attempt_dir,
        snapshot_path=snapshot_path,
        receipt_path=receipt_path,
        snapshot_sha256=snapshot_sha256,
    )


def _snapshot_payload(
    *,
    events: Sequence[Mapping[str, Any]],
    observed_at: datetime,
    acquisition_mode: str,
) -> dict[str, Any]:
    live = acquisition_mode == "live_provider"
    return {
        "contract_version": CALENDAR_SNAPSHOT_CONTRACT_VERSION,
        "snapshot_observed_at": observed_at.isoformat(),
        "source_mode": (
            "live_provider_snapshot" if live else "operator_verified_calendar_snapshot"
        ),
        "data_acquisition_mode": acquisition_mode,
        "source_provider": "official_us_macro",
        "events": [dict(row) for row in events],
    }


def _parse_source(
    source: str, body: bytes, *, acquired_at: datetime
) -> OfficialMacroParsedSource:
    if source == "bls":
        return parse_bls_release_calendar_ics(body, acquired_at=acquired_at)
    if source == "federal_reserve":
        return parse_federal_reserve_fomc_html(body, acquired_at=acquired_at)
    if source == "bea":
        return parse_bea_release_dates_json(body, acquired_at=acquired_at)
    raise OfficialMacroAcquisitionError("unsupported_source", source=None)


def _prepare_output_base(base: Path) -> None:
    if not base.parent.exists():
        raise MarketNoSendError("official macro artifact parent is missing")
    ensure_safe_namespace_dir(base)
    ensure_safe_namespace_dir(base / OFFICIAL_MACRO_STATE_DIRNAME)


def _create_attempt_dir(base: Path, attempt_id: str) -> None:
    """Create a never-reused attempt directory through the verified base fd."""

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", attempt_id):
        raise MarketNoSendError("official macro attempt id is invalid")
    descriptor: int | None = None
    try:
        before = os.stat(base, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            raise OSError("official macro base is not a directory")
        descriptor = os.open(
            base,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0),
        )
        opened = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise OSError("official macro base changed")
        os.mkdir(attempt_id, 0o700, dir_fd=descriptor)
        created = os.stat(attempt_id, dir_fd=descriptor, follow_symlinks=False)
        if not stat.S_ISDIR(created.st_mode):
            raise OSError("official macro attempt is not a directory")
        current = os.stat(base, follow_symlinks=False)
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise OSError("official macro base changed")
        os.fsync(descriptor)
    except FileExistsError:
        raise MarketNoSendError("official macro attempt already exists") from None
    except MarketNoSendError:
        raise
    except OSError as exc:
        raise MarketNoSendError("official macro attempt creation failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    ensure_safe_namespace_dir(base / attempt_id)


def _read_pointer_status(path: Path) -> str:
    try:
        if not path.parent.exists():
            return "none"
        raw = read_regular_bytes(path, missing_ok=True)
        if raw is None:
            return "none"
        parsed = json.loads(raw, object_pairs_hook=_unique_json_object)
        if not isinstance(parsed, Mapping):
            return "invalid"
        status = str(parsed.get("status") or "").strip()
        return status if status in {"complete", "failed"} else "invalid"
    except (MarketNoSendError, OSError, ValueError, json.JSONDecodeError):
        return "unavailable"


def _decoded_json_object(raw: bytes) -> Mapping[str, Any]:
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise OfficialMacroAcquisitionError("latest_success_json_invalid") from None
    if not isinstance(parsed, Mapping):
        raise OfficialMacroAcquisitionError("latest_success_object_required")
    return parsed


def _validate_success_pointer(pointer: Mapping[str, Any]) -> None:
    expected_fields = {
        "contract_version",
        "row_type",
        "attempt_id",
        "status",
        "attempted_at",
        "acquisition_mode",
        "reason_code",
        "receipt_path",
        "receipt_sha256",
        "snapshot_path",
        "snapshot_sha256",
        "provider_call_count",
        "event_count",
        *_safety_fields(),
    }
    attempt_id = str(pointer.get("attempt_id") or "")
    mode = str(pointer.get("acquisition_mode") or "")
    provider_calls = pointer.get("provider_call_count")
    event_count = pointer.get("event_count")
    if (
        set(pointer) != expected_fields
        or pointer.get("contract_version") != OFFICIAL_MACRO_CONTRACT_VERSION
        or pointer.get("row_type") != "official_macro_calendar_success_pointer"
        or pointer.get("status") != "complete"
        or pointer.get("reason_code") is not None
        or not re.fullmatch(
            r"official_macro_\d{8}T\d{12}Z_[0-9a-f]{12}", attempt_id
        )
        or mode not in {"live_provider", "operator_verified_export"}
        or provider_calls != (3 if mode == "live_provider" else 0)
        or isinstance(event_count, bool)
        or not isinstance(event_count, int)
        or event_count <= 0
        or not _valid_sha256(pointer.get("receipt_sha256"))
        or not _valid_sha256(pointer.get("snapshot_sha256"))
        or _as_utc(str(pointer.get("attempted_at") or "")) is None
        or not _valid_safety_attestation(pointer)
    ):
        raise OfficialMacroAcquisitionError("latest_success_pointer_invalid")


def _validate_success_receipt(
    receipt: Mapping[str, Any], pointer: Mapping[str, Any]
) -> None:
    expected_fields = {
        "contract_version",
        "row_type",
        "attempt_id",
        "status",
        "attempted_at",
        "acquisition_mode",
        "reason_code",
        "failure_source",
        "provider_call_count",
        "provider_request_succeeded_count",
        "source_results",
        "event_count",
        "snapshot_filename",
        "snapshot_sha256",
        "all_required_sources_accepted",
        "provider_authorization_mutated",
        *_safety_fields(),
    }
    linked_fields = (
        "attempt_id",
        "status",
        "attempted_at",
        "acquisition_mode",
        "provider_call_count",
        "event_count",
        "snapshot_sha256",
    )
    source_results = receipt.get("source_results")
    if (
        set(receipt) != expected_fields
        or receipt.get("contract_version") != OFFICIAL_MACRO_CONTRACT_VERSION
        or receipt.get("row_type") != "official_macro_calendar_acquisition_receipt"
        or any(receipt.get(field) != pointer.get(field) for field in linked_fields)
        or receipt.get("reason_code") is not None
        or receipt.get("failure_source") is not None
        or receipt.get("snapshot_filename") != OFFICIAL_MACRO_SNAPSHOT_FILENAME
        or receipt.get("all_required_sources_accepted") is not True
        or receipt.get("provider_authorization_mutated") is not False
        or not isinstance(source_results, list)
        or len(source_results) != len(OFFICIAL_MACRO_SOURCES)
        or receipt.get("provider_request_succeeded_count")
        != receipt.get("provider_call_count")
        or not _valid_safety_attestation(receipt)
    ):
        raise OfficialMacroAcquisitionError("latest_success_receipt_invalid")


def _verify_source_artifacts(
    attempt_dir: Path, receipt: Mapping[str, Any]
) -> None:
    rows = receipt.get("source_results")
    if not isinstance(rows, list):
        raise OfficialMacroAcquisitionError("latest_success_source_receipts_invalid")
    mode = str(receipt.get("acquisition_mode") or "")
    for spec, row in zip(OFFICIAL_MACRO_SOURCES, rows, strict=True):
        if (
            not isinstance(row, Mapping)
            or row.get("source") != spec.name
            or row.get("source_url") != spec.url
            or row.get("raw_filename") != spec.raw_filename
            or row.get("status") != "accepted"
            or not isinstance(row.get("request_attempted"), bool)
            or row.get("request_attempted") is not (mode == "live_provider")
            or not _valid_sha256(row.get("sha256"))
        ):
            raise OfficialMacroAcquisitionError("latest_success_source_receipts_invalid")
        body = read_regular_bytes(attempt_dir / spec.raw_filename)
        if body is None or hashlib.sha256(body).hexdigest() != row.get("sha256"):
            raise OfficialMacroAcquisitionError("latest_success_source_digest_mismatch")
        if len(body) != row.get("size_bytes") or len(body) > spec.maximum_bytes:
            raise OfficialMacroAcquisitionError("latest_success_source_size_mismatch")


def _validate_success_snapshot(
    snapshot: Mapping[str, Any], pointer: Mapping[str, Any]
) -> None:
    events = snapshot.get("events")
    mode = str(pointer.get("acquisition_mode") or "")
    expected_source_mode = (
        "live_provider_snapshot"
        if mode == "live_provider"
        else "operator_verified_calendar_snapshot"
    )
    if (
        set(snapshot)
        != {
            "contract_version",
            "snapshot_observed_at",
            "source_mode",
            "data_acquisition_mode",
            "source_provider",
            "events",
        }
        or snapshot.get("contract_version") != CALENDAR_SNAPSHOT_CONTRACT_VERSION
        or snapshot.get("snapshot_observed_at") != pointer.get("attempted_at")
        or snapshot.get("source_mode") != expected_source_mode
        or snapshot.get("data_acquisition_mode") != mode
        or snapshot.get("source_provider") != "official_us_macro"
        or not isinstance(events, list)
        or len(events) != pointer.get("event_count")
    ):
        raise OfficialMacroAcquisitionError("latest_success_snapshot_invalid")


def _valid_safety_attestation(row: Mapping[str, Any]) -> bool:
    expected = _safety_fields()
    for key, value in expected.items():
        observed = row.get(key)
        if isinstance(value, bool):
            if observed is not value:
                return False
        elif isinstance(observed, bool) or not isinstance(observed, int) or observed != value:
            return False
    return True


def _valid_sha256(value: object) -> bool:
    return re.fullmatch(r"[0-9a-f]{64}", str(value or "")) is not None


def _blocked_result(
    attempted: datetime,
    *,
    mode: str,
    reason: str,
    failure_source: str | None = None,
) -> OfficialMacroOperationResult:
    return OfficialMacroOperationResult(
        status="blocked",
        acquisition_mode=mode,
        attempted_at=attempted.isoformat(),
        reason_code=reason,
        failure_source=failure_source,
    )


def _safety_fields() -> dict[str, Any]:
    return {
        "research_only": True,
        "no_send": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
    }


def _attempt_id(observed_at: datetime) -> str:
    stamp = observed_at.strftime("%Y%m%dT%H%M%S%fZ")
    return f"official_macro_{stamp}_{secrets.token_hex(6)}"


def _as_utc(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("observed_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("observed_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _enabled(value: Any) -> bool:
    return str(value or "").strip().casefold() in _TRUE_VALUES


def _valid_contact(value: Any) -> bool:
    return _CONTACT_RE.fullmatch(str(value or "").strip()) is not None


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(payload), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    readiness = commands.add_parser("readiness")
    readiness.add_argument(
        "--output-base", default=str(DEFAULT_OFFICIAL_MACRO_BASE)
    )
    acquire = commands.add_parser("acquire")
    acquire.add_argument("--output-base", default=str(DEFAULT_OFFICIAL_MACRO_BASE))
    local_import = commands.add_parser("import-local")
    local_import.add_argument(
        "--output-base", default=str(DEFAULT_OFFICIAL_MACRO_BASE)
    )
    local_import.add_argument("--observed-at", required=True)
    local_import.add_argument("--federal-reserve-html", required=True)
    local_import.add_argument("--bls-ics", required=True)
    local_import.add_argument("--bea-json", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "readiness":
        result: OfficialMacroReadiness | OfficialMacroOperationResult = (
            official_macro_calendar_readiness(output_base=args.output_base)
        )
        status_ok = result.ready
    elif args.command == "acquire":
        result = acquire_official_macro_calendar(output_base=args.output_base)
        status_ok = result.complete
    else:
        result = import_official_macro_calendar(
            federal_reserve_html=args.federal_reserve_html,
            bls_ics=args.bls_ics,
            bea_json=args.bea_json,
            output_base=args.output_base,
            observed_at=args.observed_at,
        )
        status_ok = result.complete
    json.dump(result.to_dict(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if status_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "DEFAULT_OFFICIAL_MACRO_BASE",
    "OFFICIAL_MACRO_CONTACT_ENV",
    "OFFICIAL_MACRO_LIVE_AUTH_ENV",
    "OFFICIAL_MACRO_SOURCES",
    "OfficialMacroAcquisitionError",
    "OfficialMacroHTTPResponse",
    "OfficialMacroOperationResult",
    "OfficialMacroReadiness",
    "OfficialMacroSourceSpec",
    "acquire_official_macro_calendar",
    "import_official_macro_calendar",
    "official_macro_calendar_readiness",
    "resolve_latest_official_macro_snapshot",
)
