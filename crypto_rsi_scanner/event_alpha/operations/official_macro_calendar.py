"""Guarded producer for an authoritative U.S. macro calendar snapshot.

Live acquisition is off by default and requires explicit, already-present
authorization plus a contact address for the honest BLS request.  One run
evaluates each source independently and attempts each eligible source exactly
once.  Valid observed sources can form an explicitly partial snapshot; missing
coverage never becomes a false no-events claim.  Local import is an explicit
no-network path.

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
import shlex
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
    write_bytes_immutable,
    write_json_atomic,
    write_json_immutable,
)
from .market_no_send_models import MarketNoSendError
from .official_macro_calendar_readiness_models import (
    OfficialMacroReadiness,
    OfficialMacroSourceReadiness,
    build_official_macro_source_readiness,
)


OFFICIAL_MACRO_LIVE_AUTH_ENV = "RSI_DECISION_RADAR_MACRO_CALENDAR_LIVE"
OFFICIAL_MACRO_CONTACT_ENV = "RSI_DECISION_RADAR_BLS_CONTACT"
DEFAULT_OFFICIAL_MACRO_BASE = Path("event_fade_cache/official_macro_calendar")
OFFICIAL_MACRO_SNAPSHOT_FILENAME = "official_macro_calendar.json"
OFFICIAL_MACRO_RECEIPT_FILENAME = "acquisition_receipt.json"
OFFICIAL_MACRO_STATE_DIRNAME = "state"
OFFICIAL_MACRO_LATEST_ATTEMPT_FILENAME = "latest_attempt.json"
OFFICIAL_MACRO_LATEST_SUCCESS_FILENAME = "latest_success.json"
OFFICIAL_MACRO_CONTRACT_VERSION = 2

OFFICIAL_MACRO_SOURCE_STATUSES = frozenset(
    {
        "observed",
        "no_results",
        "unavailable",
        "missing_configuration",
        "parse_error",
        "rate_limited",
    }
)
OFFICIAL_MACRO_SNAPSHOT_STATUSES = frozenset(
    {"complete", "partial", "unavailable"}
)
_OBSERVED_SOURCE_STATUSES = frozenset({"observed", "no_results"})

_CONTACT_RE = re.compile(r"^[^\s@]{1,120}@[^\s@]{1,120}\.[^\s@]{2,40}$")
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
OFFICIAL_MACRO_READINESS_JSON_COMMAND = (
    "make radar-calendar-official-readiness "
    "RADAR_OFFICIAL_MACRO_READINESS_OUTPUT=json PYTHON=.venv/bin/python"
)


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
    source_coverage_sha256: str | None = None
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

    @property
    def usable(self) -> bool:
        return self.status in {"complete", "partial"}

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("attempt_dir", "snapshot_path", "receipt_path"):
            value = payload.get(key)
            payload[key] = str(value) if value is not None else None
        payload["source_results"] = [dict(row) for row in self.source_results]
        payload["complete"] = self.complete
        payload["usable"] = self.usable
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
    source_readiness = build_official_macro_source_readiness(
        authorized=authorized,
        contact_configured=contact_configured,
    )
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
        success_status = (
            _read_pointer_status(
                base
                / OFFICIAL_MACRO_STATE_DIRNAME
                / OFFICIAL_MACRO_LATEST_SUCCESS_FILENAME
            )
            if success_snapshot is not None
            else "none"
        )
    current_status = (
        "blocked_missing_live_authorization"
        if not authorized
        else "ready_partial_bls_missing_configuration"
        if not contact_configured
        else "ready_all_official_sources_configured"
    )
    command = (
        "make radar-calendar-official-acquire PYTHON=python3"
        if authorized
        else "make radar-calendar-official-readiness PYTHON=python3"
    )
    implications = [
        "readiness_is_read_only_and_performs_no_provider_call_or_artifact_write",
        f"latest_usable_snapshot_status={success_status}",
    ]
    if not authorized:
        implications.append(
            "live_acquisition_remains_blocked; federal_reserve_and_bea_endpoints_"
            "are_configured_but_not_request_eligible; bls_also_lacks_contact"
        )
    elif not contact_configured:
        implications.append(
            "an_acquisition_can_observe_federal_reserve_and_bea_but_must_skip_bls_as_missing_configuration"
        )
    else:
        implications.append(
            "an_acquisition_may_attempt_each_configured_official_source_once"
        )
    return OfficialMacroReadiness(
        status="ready" if authorized else "blocked",
        current_status=current_status,
        live_acquisition_authorized=authorized,
        contact_configured=contact_configured,
        source_readiness=source_readiness,
        live_partial_snapshot_eligible=any(
            row.request_eligible for row in source_readiness
        ),
        local_import_partial_snapshot_supported=True,
        partial_snapshot_eligibility=(
            "live_acquisition_can_publish_partial_when_at_least_one_eligible_"
            "source_is_observed_or_has_no_results"
            if authorized
            else "live_acquisition_blocked; local_import_can_publish_partial_after_"
            "the_operator_supplies_at_least_one_genuine_source_and_its_real_"
            "acquisition_time"
        ),
        local_import_command=(
            f"OFFICIAL_MACRO_OUTPUT_BASE={shlex.quote(str(base))} "
            "OFFICIAL_MACRO_OBSERVED_AT=\"$OFFICIAL_MACRO_OBSERVED_AT\" "
            "FED_FOMC_HTML=\"$FED_FOMC_HTML\" "
            "BLS_CALENDAR_ICS=\"$BLS_CALENDAR_ICS\" "
            "BEA_RELEASE_DATES_JSON=\"$BEA_RELEASE_DATES_JSON\" "
            "make radar-calendar-official-import-local PYTHON=python3"
        ),
        local_import_requirements=(
            "set_OFFICIAL_MACRO_OBSERVED_AT_to_the_real_ISO_8601_acquisition_time_with_timezone",
            "set_FED_FOMC_HTML_and_or_BEA_RELEASE_DATES_JSON_to_absolute_paths_for_genuine_operator_downloads",
            "BLS_CALENDAR_ICS_is_optional_for_local_import_and_may_be_added_when_available",
            "fixture_test_mock_and_replay_paths_or_bytes_are_rejected",
        ),
        output_base=str(base),
        latest_attempt_status=attempt_status,
        latest_success_status=success_status,
        reason_codes=tuple(reasons),
        implications=tuple(implications),
        next_safe_command=command,
        authorization_boundary=(
            "readiness_never_calls; acquisition_requires_already_present_"
            f"{OFFICIAL_MACRO_LIVE_AUTH_ENV}=1; BLS_also_requires_an_already_present_"
            f"valid_{OFFICIAL_MACRO_CONTACT_ENV}; the_program_never_creates_or_mutates_authorization"
        ),
        expected_provider_activity=(
            "readiness_none; authorized_acquire_at_most_one_request_per_configured_"
            "source_and_skips_missing_configuration"
        ),
        rollback_disable_command=(
            "none_required_program_never_mutates_authorization_or_installs_a_service"
        ),
    )


def format_official_macro_calendar_readiness_summary(
    result: OfficialMacroReadiness,
) -> str:
    """Render bounded operator truth from one already-built readiness result."""

    lines: list[tuple[str, object]] = [
        ("report", "decision_radar_official_macro_calendar_readiness"),
        ("status", result.status),
        ("ready", result.ready),
        ("current_status", result.current_status),
        ("live_acquisition_authorized", result.live_acquisition_authorized),
        ("bls_contact_configured", result.contact_configured),
        ("latest_attempt_status", result.latest_attempt_status),
        ("latest_success_status", result.latest_success_status),
    ]
    for row in result.source_readiness:
        prefix = f"source[{row.source}]"
        lines.extend((
            (f"{prefix}.availability", row.availability),
            (f"{prefix}.request_eligible", row.request_eligible),
            (
                f"{prefix}.maximum_provider_calls_if_acquire",
                row.maximum_provider_calls_if_acquire,
            ),
            (f"{prefix}.reason", row.reason_code),
        ))
    lines.extend((
        ("live_partial_snapshot_eligible", result.live_partial_snapshot_eligible),
        (
            "local_import_partial_snapshot_supported",
            result.local_import_partial_snapshot_supported,
        ),
        ("reasons", result.reason_codes),
        ("implications", result.implications),
        ("next_safe_command", result.next_safe_command),
        ("local_import_command", result.local_import_command),
        ("authorization_boundary", result.authorization_boundary),
        ("expected_provider_activity", result.expected_provider_activity),
        ("rollback_disable_command", result.rollback_disable_command),
        ("provider_call_attempted", result.provider_call_attempted),
        ("provider_call_count", result.provider_call_count),
        ("writes_performed", result.writes_performed),
        ("research_only", result.research_only),
        ("full_json_command", OFFICIAL_MACRO_READINESS_JSON_COMMAND),
    ))
    return "\n".join(
        f"{key}={_summary_value(value)}"
        for key, value in lines
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
    """Acquire one independently covered official pack with at most one call per source."""

    env = os.environ if environ is None else environ
    attempted = _as_utc(observed_at)
    if not _enabled(env.get(OFFICIAL_MACRO_LIVE_AUTH_ENV)):
        return _blocked_result(
            attempted,
            mode="live_provider",
            reason="live_calendar_authorization_missing",
            source_results=tuple(
                _missing_configuration_source_result(spec)
                for spec in OFFICIAL_MACRO_SOURCES
            ),
        )
    contact = str(env.get(OFFICIAL_MACRO_CONTACT_ENV) or "").strip()
    contact_configured = _valid_contact(contact)
    user_agent = (
        f"crypto-rsi-scanner-calendar/1.1 ({contact})"
        if contact_configured
        else "crypto-rsi-scanner-calendar/1.1"
    )
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
        missing_configuration=(frozenset() if contact_configured else frozenset({"bls"})),
    )


def import_official_macro_calendar(
    *,
    federal_reserve_html: str | Path | None = None,
    bls_ics: str | Path | None = None,
    bea_json: str | Path | None = None,
    output_base: str | Path = DEFAULT_OFFICIAL_MACRO_BASE,
    observed_at: datetime | str | None = None,
) -> OfficialMacroOperationResult:
    """Import explicit local official sources without network access."""

    if observed_at is None or str(observed_at).strip() == "":
        return _blocked_result(
            datetime.now(timezone.utc),
            mode="operator_verified_export",
            reason="local_import_observed_at_required",
        )
    attempted = _as_utc(observed_at)
    supplied = {
        "federal_reserve": federal_reserve_html,
        "bls": bls_ics,
        "bea": bea_json,
    }
    paths = {
        source: Path(value).expanduser().absolute()
        for source, value in supplied.items()
        if value is not None and str(value).strip()
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
        except KeyError:
            continue
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
        missing_configuration=frozenset(set(supplied).difference(paths)),
    )


def _produce_pack(
    *,
    output_base: str | Path,
    attempted: datetime,
    acquisition_mode: str,
    source_loader: Callable[[OfficialMacroSourceSpec], OfficialMacroHTTPResponse],
    provider_calls_expected: bool,
    missing_configuration: frozenset[str] = frozenset(),
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

    parsed_sources, source_results, provider_calls, provider_successes = _load_pack_sources(
        attempt_dir=attempt_dir,
        attempted=attempted,
        source_loader=source_loader,
        provider_calls_expected=provider_calls_expected,
        missing_configuration=missing_configuration,
    )

    try:
        statuses = tuple(str(row["status"]) for row in source_results)
        observed_count = sum(status in _OBSERVED_SOURCE_STATUSES for status in statuses)
        snapshot_status = (
            "complete"
            if observed_count == len(OFFICIAL_MACRO_SOURCES)
            else "partial"
            if observed_count
            else "unavailable"
        )
        events = merge_official_macro_sources(parsed_sources, require_all=False)
        source_coverage = _source_coverage_projection(source_results)
        coverage_digest = _source_coverage_sha256(source_coverage)
        snapshot = _snapshot_payload(
            events=events,
            observed_at=attempted,
            acquisition_mode=acquisition_mode,
            snapshot_status=snapshot_status,
            source_coverage=source_coverage,
            source_coverage_sha256=coverage_digest,
        )
        snapshot_bytes = _json_bytes(snapshot)
        snapshot_path = attempt_dir / OFFICIAL_MACRO_SNAPSHOT_FILENAME
        write_bytes_immutable(snapshot_path, snapshot_bytes)
        if snapshot_status in {"complete", "partial"}:
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
        elif events:
            raise OfficialMacroAcquisitionError(
                "unavailable_snapshot_contains_events", source=None
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
            snapshot_status="unavailable",
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
            snapshot_status="unavailable",
        )

    return _finish_attempt(
        base=base,
        attempt_dir=attempt_dir,
        attempt_id=attempt_id,
        attempted=attempted,
        acquisition_mode=acquisition_mode,
        status=snapshot_status,
        reason_code=None,
        failure_source=_first_unobserved_source(source_results),
        source_results=source_results,
        provider_calls=provider_calls,
        provider_successes=provider_successes,
        event_count=len(events),
        snapshot_path=snapshot_path,
        snapshot_sha256=snapshot_digest,
        source_coverage_sha256=coverage_digest,
        snapshot_status=snapshot_status,
    )


def _load_pack_sources(
    *,
    attempt_dir: Path,
    attempted: datetime,
    source_loader: Callable[[OfficialMacroSourceSpec], OfficialMacroHTTPResponse],
    provider_calls_expected: bool,
    missing_configuration: frozenset[str],
) -> tuple[
    list[OfficialMacroParsedSource],
    list[dict[str, Any]],
    int,
    int,
]:
    parsed_sources: list[OfficialMacroParsedSource] = []
    source_results: list[dict[str, Any]] = []
    provider_calls = 0
    provider_successes = 0
    for spec in OFFICIAL_MACRO_SOURCES:
        source_result: dict[str, Any] = {
            "source": spec.name,
            "source_url": spec.url,
            "request_attempted": False,
            "http_status": None,
            "content_type": None,
            "size_bytes": None,
            "sha256": None,
            "raw_filename": None,
            "status": "missing_configuration"
            if spec.name in missing_configuration
            else "unavailable",
            "source_rows_seen": None,
            "accepted_rows": 0,
            "rejected_rows": 0,
            "failure_class": (
                "source_configuration_missing"
                if spec.name in missing_configuration
                else None
            ),
        }
        if spec.name in missing_configuration:
            source_results.append(source_result)
            continue
        if provider_calls_expected:
            provider_calls += 1
            source_result["request_attempted"] = True
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
            write_bytes_immutable(attempt_dir / spec.raw_filename, body)
            parsed = _parse_source(spec.name, body, acquired_at=attempted)
            parsed_sources.append(parsed)
            source_result.update(
                {
                    "status": "observed" if parsed.rows else "no_results",
                    "source_rows_seen": parsed.source_rows_seen,
                    "accepted_rows": len(parsed.rows),
                    "rejected_rows": parsed.rejected_rows,
                    "failure_class": None,
                }
            )
            source_results.append(source_result)
        except OfficialMacroParseError as exc:
            source_result.update(
                {
                    "status": "parse_error",
                    "failure_class": f"parse_{_safe_code(exc.code)}",
                }
            )
        except OfficialMacroAcquisitionError as exc:
            source_result.update(
                {
                    "status": (
                        "rate_limited" if exc.http_status == 429 else "unavailable"
                    ),
                    "failure_class": exc.reason_code,
                    "http_status": exc.http_status,
                }
            )
        except (MarketNoSendError, OSError, ValueError):
            source_result.update(
                {
                    "status": "unavailable",
                    "failure_class": "source_artifact_write_failed",
                    "content_type": None,
                    "size_bytes": None,
                    "sha256": None,
                    "raw_filename": None,
                }
            )
        if source_result not in source_results:
            source_results.append(source_result)
    return (
        parsed_sources,
        source_results,
        provider_calls,
        provider_successes,
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
    source_coverage_sha256: str | None = None,
    snapshot_status: str,
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
        "snapshot_status": snapshot_status,
        "source_coverage_sha256": source_coverage_sha256,
        "observed_sources": _sources_with_status(
            source_results, _OBSERVED_SOURCE_STATUSES
        ),
        "missing_sources": _sources_without_status(
            source_results, _OBSERVED_SOURCE_STATUSES
        ),
        "all_required_sources_accepted": status == "complete",
        "provider_authorization_mutated": False,
        **_safety_fields(),
    }
    try:
        write_json_immutable(receipt_path, receipt)
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
            "snapshot_status": snapshot_status,
            "source_coverage_sha256": source_coverage_sha256,
            "provider_call_count": provider_calls,
            "event_count": event_count,
            **_safety_fields(),
        }
        state_dir = base / OFFICIAL_MACRO_STATE_DIRNAME
        write_json_atomic(state_dir / OFFICIAL_MACRO_LATEST_ATTEMPT_FILENAME, pointer)
        if status in {"complete", "partial"}:
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
            source_coverage_sha256=source_coverage_sha256,
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
        source_coverage_sha256=source_coverage_sha256,
    )


def _snapshot_payload(
    *,
    events: Sequence[Mapping[str, Any]],
    observed_at: datetime,
    acquisition_mode: str,
    snapshot_status: str,
    source_coverage: Sequence[Mapping[str, Any]],
    source_coverage_sha256: str,
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
        "snapshot_status": snapshot_status,
        "source_coverage": [dict(row) for row in source_coverage],
        "source_coverage_sha256": source_coverage_sha256,
        "events": [dict(row) for row in events],
    }


def _source_coverage_projection(
    source_results: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    fields = (
        "source",
        "status",
        "request_attempted",
        "http_status",
        "content_type",
        "size_bytes",
        "sha256",
        "raw_filename",
        "source_rows_seen",
        "accepted_rows",
        "rejected_rows",
        "failure_class",
    )
    return tuple({field: row.get(field) for field in fields} for row in source_results)


def _source_coverage_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    encoded = json.dumps(
        [dict(row) for row in rows],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sources_with_status(
    rows: Sequence[Mapping[str, Any]], statuses: frozenset[str]
) -> list[str]:
    return [
        str(row.get("source"))
        for row in rows
        if str(row.get("status")) in statuses
    ]


def _sources_without_status(
    rows: Sequence[Mapping[str, Any]], statuses: frozenset[str]
) -> list[str]:
    return [
        str(row.get("source"))
        for row in rows
        if str(row.get("status")) not in statuses
    ]


def _first_unobserved_source(
    rows: Sequence[Mapping[str, Any]],
) -> str | None:
    values = _sources_without_status(rows, _OBSERVED_SOURCE_STATUSES)
    return values[0] if values else None


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
        return (
            status
            if status in {"complete", "partial", "unavailable", "failed"}
            else "invalid"
        )
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
        "snapshot_status",
        "source_coverage_sha256",
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
        or pointer.get("status") not in {"complete", "partial"}
        or pointer.get("snapshot_status") != pointer.get("status")
        or pointer.get("reason_code") is not None
        or not re.fullmatch(
            r"official_macro_\d{8}T\d{12}Z_[0-9a-f]{12}", attempt_id
        )
        or mode not in {"live_provider", "operator_verified_export"}
        or isinstance(provider_calls, bool)
        or not isinstance(provider_calls, int)
        or provider_calls < 0
        or provider_calls > (3 if mode == "live_provider" else 0)
        or isinstance(event_count, bool)
        or not isinstance(event_count, int)
        or event_count < 0
        or not _valid_sha256(pointer.get("receipt_sha256"))
        or not _valid_sha256(pointer.get("snapshot_sha256"))
        or not _valid_sha256(pointer.get("source_coverage_sha256"))
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
        "snapshot_status",
        "source_coverage_sha256",
        "observed_sources",
        "missing_sources",
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
        "snapshot_status",
        "source_coverage_sha256",
    )
    source_results = receipt.get("source_results")
    if (
        set(receipt) != expected_fields
        or receipt.get("contract_version") != OFFICIAL_MACRO_CONTRACT_VERSION
        or receipt.get("row_type") != "official_macro_calendar_acquisition_receipt"
        or any(receipt.get(field) != pointer.get(field) for field in linked_fields)
        or receipt.get("reason_code") is not None
        or (
            receipt.get("failure_source") is not None
            and receipt.get("failure_source")
            not in {spec.name for spec in OFFICIAL_MACRO_SOURCES}
        )
        or receipt.get("snapshot_filename") != OFFICIAL_MACRO_SNAPSHOT_FILENAME
        or receipt.get("all_required_sources_accepted")
        is not (pointer.get("status") == "complete")
        or receipt.get("provider_authorization_mutated") is not False
        or not isinstance(source_results, list)
        or len(source_results) != len(OFFICIAL_MACRO_SOURCES)
        or not _valid_provider_success_counts(receipt)
        or not _valid_source_results(receipt)
        or not _valid_safety_attestation(receipt)
    ):
        raise OfficialMacroAcquisitionError("latest_success_receipt_invalid")


def _valid_provider_success_counts(receipt: Mapping[str, Any]) -> bool:
    calls = receipt.get("provider_call_count")
    successes = receipt.get("provider_request_succeeded_count")
    return (
        isinstance(calls, int)
        and not isinstance(calls, bool)
        and isinstance(successes, int)
        and not isinstance(successes, bool)
        and 0 <= successes <= calls <= 3
    )


def _valid_source_results(receipt: Mapping[str, Any]) -> bool:
    rows = receipt.get("source_results")
    if not isinstance(rows, list) or len(rows) != len(OFFICIAL_MACRO_SOURCES):
        return False
    expected_fields = {
        "source",
        "source_url",
        "request_attempted",
        "http_status",
        "content_type",
        "size_bytes",
        "sha256",
        "raw_filename",
        "status",
        "source_rows_seen",
        "accepted_rows",
        "rejected_rows",
        "failure_class",
    }
    mode = str(receipt.get("acquisition_mode") or "")
    for spec, row in zip(OFFICIAL_MACRO_SOURCES, rows, strict=True):
        if not isinstance(row, Mapping) or set(row) != expected_fields:
            return False
        status = str(row.get("status") or "")
        accepted = row.get("accepted_rows")
        rejected = row.get("rejected_rows")
        seen = row.get("source_rows_seen")
        if any(
            (
                row.get("source") != spec.name,
                row.get("source_url") != spec.url,
                status not in OFFICIAL_MACRO_SOURCE_STATUSES,
                not isinstance(row.get("request_attempted"), bool),
                row.get("request_attempted")
                is not (mode == "live_provider" and status != "missing_configuration"),
                isinstance(accepted, bool)
                or not isinstance(accepted, int)
                or accepted < 0,
                isinstance(rejected, bool)
                or not isinstance(rejected, int)
                or rejected < 0,
                seen is not None
                and (
                    isinstance(seen, bool)
                    or not isinstance(seen, int)
                    or seen < accepted
                ),
            )
        ):
            return False
        captured = status in {"observed", "no_results", "parse_error"}
        if captured != (
            row.get("raw_filename") == spec.raw_filename
            and _valid_sha256(row.get("sha256"))
            and isinstance(row.get("size_bytes"), int)
            and not isinstance(row.get("size_bytes"), bool)
            and 0 < int(row.get("size_bytes") or 0) <= spec.maximum_bytes
        ):
            return False
        if status == "observed" and accepted <= 0:
            return False
        if status == "no_results" and accepted != 0:
            return False
        if status in _OBSERVED_SOURCE_STATUSES:
            if row.get("failure_class") is not None or seen is None:
                return False
        elif not isinstance(row.get("failure_class"), str):
            return False
    observed = _sources_with_status(rows, _OBSERVED_SOURCE_STATUSES)
    missing = _sources_without_status(rows, _OBSERVED_SOURCE_STATUSES)
    snapshot_status = str(receipt.get("snapshot_status") or "")
    expected_status = (
        "complete"
        if len(observed) == len(OFFICIAL_MACRO_SOURCES)
        else "partial"
        if observed
        else "unavailable"
    )
    return all(
        (
            receipt.get("observed_sources") == observed,
            receipt.get("missing_sources") == missing,
            snapshot_status == expected_status,
            receipt.get("status") == expected_status,
            receipt.get("source_coverage_sha256")
            == _source_coverage_sha256(_source_coverage_projection(rows)),
        )
    )


def _verify_source_artifacts(
    attempt_dir: Path, receipt: Mapping[str, Any]
) -> None:
    rows = receipt.get("source_results")
    if not isinstance(rows, list):
        raise OfficialMacroAcquisitionError("latest_success_source_receipts_invalid")
    for spec, row in zip(OFFICIAL_MACRO_SOURCES, rows, strict=True):
        if not isinstance(row, Mapping):
            raise OfficialMacroAcquisitionError("latest_success_source_receipts_invalid")
        if row.get("status") not in {"observed", "no_results", "parse_error"}:
            continue
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
            "snapshot_status",
            "source_coverage",
            "source_coverage_sha256",
            "events",
        }
        or snapshot.get("contract_version") != CALENDAR_SNAPSHOT_CONTRACT_VERSION
        or snapshot.get("snapshot_observed_at") != pointer.get("attempted_at")
        or snapshot.get("source_mode") != expected_source_mode
        or snapshot.get("data_acquisition_mode") != mode
        or snapshot.get("source_provider") != "official_us_macro"
        or snapshot.get("snapshot_status") != pointer.get("snapshot_status")
        or snapshot.get("source_coverage_sha256")
        != pointer.get("source_coverage_sha256")
        or not _valid_source_coverage_rows(snapshot.get("source_coverage"))
        or _source_coverage_sha256(snapshot.get("source_coverage") or ())
        != snapshot.get("source_coverage_sha256")
        or not isinstance(events, list)
        or len(events) != pointer.get("event_count")
    ):
        raise OfficialMacroAcquisitionError("latest_success_snapshot_invalid")


def _valid_source_coverage_rows(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != len(OFFICIAL_MACRO_SOURCES):
        return False
    fields = {
        "source",
        "status",
        "request_attempted",
        "http_status",
        "content_type",
        "size_bytes",
        "sha256",
        "raw_filename",
        "source_rows_seen",
        "accepted_rows",
        "rejected_rows",
        "failure_class",
    }
    statuses: list[str] = []
    for spec, row in zip(OFFICIAL_MACRO_SOURCES, value, strict=True):
        if (
            not isinstance(row, Mapping)
            or set(row) != fields
            or row.get("source") != spec.name
            or row.get("status") not in OFFICIAL_MACRO_SOURCE_STATUSES
        ):
            return False
        statuses.append(str(row.get("status")))
    observed = sum(status in _OBSERVED_SOURCE_STATUSES for status in statuses)
    expected_status = (
        "complete"
        if observed == len(OFFICIAL_MACRO_SOURCES)
        else "partial"
        if observed
        else "unavailable"
    )
    return expected_status in OFFICIAL_MACRO_SNAPSHOT_STATUSES


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
    source_results: Sequence[Mapping[str, Any]] = (),
) -> OfficialMacroOperationResult:
    return OfficialMacroOperationResult(
        status="blocked",
        acquisition_mode=mode,
        attempted_at=attempted.isoformat(),
        reason_code=reason,
        failure_source=failure_source,
        source_results=tuple(dict(row) for row in source_results),
    )


def _missing_configuration_source_result(
    spec: OfficialMacroSourceSpec,
) -> dict[str, Any]:
    return {
        "source": spec.name,
        "source_url": spec.url,
        "request_attempted": False,
        "http_status": None,
        "content_type": None,
        "size_bytes": None,
        "sha256": None,
        "raw_filename": None,
        "status": "missing_configuration",
        "source_rows_seen": None,
        "accepted_rows": 0,
        "rejected_rows": 0,
        "failure_class": "source_configuration_missing",
    }


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


def _summary_value(value: object) -> str:
    if value is None:
        return "none"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (list, tuple)):
        return ",".join(_summary_value(item) for item in value) or "none"
    return str(value).replace("\r", " ").replace("\n", " ").strip() or "none"


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
    readiness.add_argument("--output", choices=("json", "summary"), default="json")
    acquire = commands.add_parser("acquire")
    acquire.add_argument("--output-base", default=str(DEFAULT_OFFICIAL_MACRO_BASE))
    local_import = commands.add_parser("import-local")
    local_import.add_argument(
        "--output-base", default=str(DEFAULT_OFFICIAL_MACRO_BASE)
    )
    local_import.add_argument("--observed-at", required=True)
    local_import.add_argument("--federal-reserve-html")
    local_import.add_argument("--bls-ics")
    local_import.add_argument("--bea-json")
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
        status_ok = result.usable
    else:
        result = import_official_macro_calendar(
            federal_reserve_html=args.federal_reserve_html,
            bls_ics=args.bls_ics,
            bea_json=args.bea_json,
            output_base=args.output_base,
            observed_at=args.observed_at,
        )
        status_ok = result.usable
    if args.command == "readiness" and args.output == "summary":
        assert isinstance(result, OfficialMacroReadiness)
        print(format_official_macro_calendar_readiness_summary(result))
    else:
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
    "OFFICIAL_MACRO_SOURCE_STATUSES",
    "OFFICIAL_MACRO_SNAPSHOT_STATUSES",
    "OfficialMacroAcquisitionError",
    "OfficialMacroHTTPResponse",
    "OfficialMacroOperationResult",
    "OfficialMacroReadiness",
    "OfficialMacroSourceReadiness",
    "format_official_macro_calendar_readiness_summary",
    "OfficialMacroSourceSpec",
    "acquire_official_macro_calendar",
    "import_official_macro_calendar",
    "official_macro_calendar_readiness",
    "resolve_latest_official_macro_snapshot",
)
