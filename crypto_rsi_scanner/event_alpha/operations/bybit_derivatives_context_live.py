"""Guarded venue-native Bybit derivatives-context collection.

Readiness is no-network/no-write. Collection requires one complete current
execution-quality capture, a separate already-present authorization flag, and
an explicit operator confirmation. The adapter performs four public GETs per
exact instrument without retries and has no credential, private-data, order,
trading, notification, persistence, campaign, or Decision-policy path.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ... import config
from ..dashboard.readiness import resolve_authoritative_dashboard
from .bybit_derivatives_context import (
    ACCOUNT_RATIO_PATH,
    DEFAULT_FRESHNESS_SECONDS,
    FUNDING_HISTORY_PATH,
    MAX_PLANNED_REQUESTS,
    OPEN_INTEREST_PATH,
    TICKERS_PATH,
    BybitDerivativesContextError,
    build_bybit_derivatives_requests,
    normalize_bybit_derivatives_context,
)
from .bybit_derivatives_context_capture import (
    BybitDerivativesContextCaptureError,
    persist_bybit_derivatives_context_capture,
)
from .bybit_derivatives_context_capture_status import (
    bybit_derivatives_context_capture_status,
)
from .bybit_execution_quality import (
    QUOTE_ASSET,
    BybitEligibleInstrument,
    BybitPublicRequest,
)
from .bybit_execution_quality_capture import (
    BybitCapturedJSONResponse,
    load_latest_bybit_execution_quality_capture,
)
from .bybit_execution_quality_live import (
    BybitExecutionQualityLiveError,
    _fetch_public_json,
)
from .bybit_intraday_live import (
    BybitIntradayLiveError,
    _enabled,
    _execution_capture_context,
    _instrument_from_values,
    _payload_and_timing,
)


CONTRACT_VERSION = "crypto_radar_bybit_derivatives_context_live_v2"
LIVE_AUTH_ENV = "RSI_DECISION_RADAR_BYBIT_DERIVATIVES_LIVE"
DEFAULT_TIMEOUT_SECONDS = 10.0
READINESS_COMMAND = "make radar-derivatives-bybit-readiness PYTHON=.venv/bin/python"
COLLECT_COMMAND = (
    "CONFIRM=1 make radar-derivatives-bybit-collect PYTHON=.venv/bin/python"
)
CAPTURE_COMMAND = (
    "CONFIRM=1 make radar-derivatives-bybit-capture PYTHON=.venv/bin/python"
)
STATUS_COMMAND = "make radar-derivatives-bybit-status PYTHON=.venv/bin/python"
AUTHORIZATION_ACTION = (
    f"set_{LIVE_AUTH_ENV}=1_in_local_gitignored_dotenv_then_rerun_readiness"
)
_PATH_LABELS = {
    TICKERS_PATH: "ticker",
    FUNDING_HISTORY_PATH: "funding_history",
    OPEN_INTEREST_PATH: "open_interest",
    ACCOUNT_RATIO_PATH: "account_ratio",
}
_SAFETY = {
    "research_only": True,
    "no_send": True,
    "credentials_read": False,
    "private_data_read": False,
    "orders_available": False,
    "trades_created": 0,
    "paper_trades_created": 0,
    "normal_rsi_signal_rows_written": 0,
    "triggered_fade_created": 0,
    "telegram_sends": 0,
    "writes_performed": False,
}


class _BybitDerivativesContextLiveError(RuntimeError):
    """Closed live-boundary failure without provider payload leakage."""

    def __init__(
        self,
        reason_code: str,
        *,
        provider_status: str | None = None,
        http_status: int | None = None,
        request_count: int = 0,
    ) -> None:
        self.reason_code = _safe_code(reason_code)
        self.provider_status = _safe_code(provider_status) if provider_status else None
        self.http_status = (
            int(http_status)
            if isinstance(http_status, int) and 100 <= http_status <= 599
            else None
        )
        self.request_count = max(0, min(int(request_count), MAX_PLANNED_REQUESTS))
        super().__init__(self.reason_code)


BybitDerivativesContextLiveError = _BybitDerivativesContextLiveError
CaptureLoader = Callable[[str | Path], Mapping[str, object]]
Resolver = Callable[..., Any]
Clock = Callable[[], datetime]
FetchResult = Mapping[str, object] | BybitCapturedJSONResponse
FetchJSON = Callable[[BybitPublicRequest, float], FetchResult]


def _safe_code(value: object) -> str:
    text = str(value or "unknown").strip().casefold()
    cleaned = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in text
    )
    return cleaned[:96] or "unknown"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BybitDerivativesContextLiveError("clock_must_include_timezone")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _context_age_seconds(context: Mapping[str, object], completed: datetime) -> float:
    value = context.get("provider_observed_at")
    if not isinstance(value, str):
        raise BybitDerivativesContextLiveError("context_provider_clock_invalid")
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BybitDerivativesContextLiveError(
            "context_provider_clock_invalid"
        ) from exc
    return max(0.0, (_utc(completed) - _utc(observed)).total_seconds())


def _execution_prerequisites(
    artifact_base_dir: str | Path,
    *,
    checked_at: datetime,
    capture_loader: CaptureLoader,
    resolver: Resolver,
) -> tuple[dict[str, object] | None, tuple[BybitEligibleInstrument, ...], list[str]]:
    capture, instruments, reasons = _execution_capture_context(
        artifact_base_dir,
        now=checked_at,
        loader=capture_loader,
        resolver=resolver,
    )
    return (
        dict(capture) if isinstance(capture, Mapping) else None,
        tuple(instruments),
        list(reasons),
    )


def build_bybit_derivatives_live_readiness(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
) -> dict[str, object]:
    """Inspect exact prerequisites and authorization without a call or write."""

    checked = _utc(now or datetime.now(timezone.utc))
    env = os.environ if environ is None else environ
    authorized = _enabled(env.get(LIVE_AUTH_ENV))
    capture, instruments, reasons = _execution_prerequisites(
        artifact_base_dir,
        checked_at=checked,
        capture_loader=capture_loader,
        resolver=resolver,
    )
    if not authorized:
        reasons.append("runtime_provider_authorization_absent")
    request_bound = len(instruments) * len(_PATH_LABELS)
    latest_capture = bybit_derivatives_context_capture_status(artifact_base_dir)
    ready = not reasons
    only_auth_missing = reasons == ["runtime_provider_authorization_absent"]
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_derivatives_context_live_readiness",
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "checked_at": _iso(checked),
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "category": "linear",
        "quote_asset": QUOTE_ASSET,
        "context_fields": [
            "ticker_mark_index_basis_current_funding",
            "settled_funding_history",
            "open_interest_1h",
            "long_short_account_ratio_1h",
        ],
        "composite_freshness_policy": "oldest_required_provider_response",
        "runtime_authorization_env": LIVE_AUTH_ENV,
        "runtime_provider_authorized": authorized,
        "authorization_mutated": False,
        "source_execution_quality_capture": capture,
        "source_execution_quality_capture_id": (
            capture.get("capture_id") if isinstance(capture, Mapping) else None
        ),
        "eligible_instrument_count": len(instruments),
        "eligible_instruments": [row.to_dict() for row in instruments],
        "maximum_provider_requests_for_current_capture": request_bound,
        "absolute_provider_request_bound": MAX_PLANNED_REQUESTS,
        "provider_call_planned": False,
        "provider_call_attempted": False,
        "artifact_persisted": False,
        "exact_response_capture_contract_implemented": True,
        "immutable_capture_implemented": True,
        "capture_publication_available": True,
        "latest_derivatives_capture_status": latest_capture.get("status"),
        "latest_derivatives_capture": latest_capture,
        "campaign_attached": False,
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_input_quality_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "reasons": list(dict.fromkeys(reasons)),
        "next_safe_command": COLLECT_COMMAND if ready else READINESS_COMMAND,
        "readiness_recheck_command": READINESS_COMMAND,
        "diagnostic_collect_command": COLLECT_COMMAND,
        "immutable_capture_command": CAPTURE_COMMAND,
        "capture_status_command": STATUS_COMMAND,
        "operator_action_required": (
            AUTHORIZATION_ACTION
            if only_auth_missing
            else "resolve_readiness_reasons_then_rerun_readiness"
            if reasons
            else "none"
        ),
        "authorization_action_required": (
            AUTHORIZATION_ACTION if not authorized else "none"
        ),
        "collection_confirmation_required": True,
        "expected_provider_activity": (
            f"collect_exactly_{request_bound}_public_GETs_no_retries"
            if ready
            else "none_readiness_only"
        ),
        "authorization_boundary": (
            f"collection_requires_already_present_{LIVE_AUTH_ENV}=1;"
            "this_command_never_creates_or_mutates_authorization"
        ),
        "rollback_disable_command": f"unset {LIVE_AUTH_ENV}",
        "recorded_403_policy": (
            "fail_closed_no_retry_proxy_VPN_region_bypass_or_alternate_host"
        ),
        **_SAFETY,
    }


def _revalidate_prerequisites(
    artifact_base_dir: str | Path,
    *,
    expected_capture_id: object,
    expected_instruments: Sequence[BybitEligibleInstrument],
    checked_at: datetime,
    capture_loader: CaptureLoader,
    resolver: Resolver,
) -> None:
    capture, instruments, reasons = _execution_prerequisites(
        artifact_base_dir,
        checked_at=checked_at,
        capture_loader=capture_loader,
        resolver=resolver,
    )
    if (
        reasons
        or capture is None
        or capture.get("capture_id") != expected_capture_id
        or instruments != tuple(expected_instruments)
    ):
        raise BybitDerivativesContextLiveError(
            "derivatives_source_prerequisite_drifted"
        )


def _collect_instrument(
    instrument: BybitEligibleInstrument,
    *,
    instrument_index: int,
    lineage_seed: str,
    fetch: FetchJSON,
    clock: Clock,
    timeout_seconds: float,
) -> tuple[dict[str, object], list[BybitCapturedJSONResponse], list[dict[str, object]]]:
    payloads: dict[str, Mapping[str, object]] = {}
    lineage: dict[str, str] = {}
    captured: list[BybitCapturedJSONResponse] = []
    timing: list[dict[str, object]] = []
    acquired_values: list[datetime] = []
    for request_index, request in enumerate(
        build_bybit_derivatives_requests((instrument,)), start=1
    ):
        label = _PATH_LABELS[request.path]
        fallback_started = _utc(clock())
        try:
            result = fetch(request, timeout_seconds)
        except BybitExecutionQualityLiveError as exc:
            raise BybitDerivativesContextLiveError(
                exc.reason_code,
                provider_status=exc.provider_status,
                http_status=exc.http_status,
                request_count=request_index,
            ) from exc
        except BybitDerivativesContextLiveError:
            raise
        except Exception as exc:
            raise BybitDerivativesContextLiveError(
                getattr(exc, "reason_code", "provider_request_failed"),
                request_count=request_index,
            ) from exc
        fallback_acquired = _utc(clock())
        if isinstance(result, BybitCapturedJSONResponse):
            if result.request != request:
                raise BybitDerivativesContextLiveError(
                    "provider_response_request_mismatch",
                    request_count=request_index,
                )
            captured.append(result)
        try:
            payload, request_started, acquired = _payload_and_timing(
                result,
                fallback_started=fallback_started,
                fallback_acquired=fallback_acquired,
            )
        except BybitIntradayLiveError as exc:
            raise BybitDerivativesContextLiveError(
                exc.reason_code,
                request_count=request_index,
            ) from exc
        lineage_id = (
            f"bybit.derivatives.{lineage_seed}.{instrument_index}.{request_index}"
        )
        payloads[label] = payload
        lineage[label] = lineage_id
        acquired_values.append(acquired)
        timing.append({
            "instrument_id": instrument.instrument_id,
            "source": label,
            "request_lineage_id": lineage_id,
            "request_started_at": _iso(request_started),
            "response_received_at": _iso(acquired),
        })
    snapshot = normalize_bybit_derivatives_context(
        payloads["ticker"],
        payloads["funding_history"],
        payloads["open_interest"],
        payloads["account_ratio"],
        instrument=instrument,
        acquired_at=max(acquired_values),
        request_lineage_ids=lineage,
    )
    return snapshot.to_dict(), captured, timing


def _observation_set_summary(
    *,
    started: datetime,
    completed: datetime,
    readiness: Mapping[str, object],
    capture_id: object,
    instruments: Sequence[BybitEligibleInstrument],
    contexts: list[dict[str, object]],
    request_timing: list[dict[str, object]],
    request_count: int,
    captured_responses: Sequence[BybitCapturedJSONResponse],
) -> dict[str, object]:
    completion_ages = [
        _context_age_seconds(context, completed) for context in contexts
    ]
    fresh_at_acquisition = all(
        row["freshness_status"] == "fresh" for row in contexts
    )
    fresh_at_completion = fresh_at_acquisition and all(
        age <= DEFAULT_FRESHNESS_SECONDS for age in completion_ages
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_derivatives_context_observation_set",
        "status": "complete",
        "started_at": _iso(started),
        "completed_at": _iso(completed),
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "category": "linear",
        "quote_asset": QUOTE_ASSET,
        "source_execution_quality_capture_id": capture_id,
        "source_execution_quality_capture": readiness[
            "source_execution_quality_capture"
        ],
        "eligible_instrument_count": len(instruments),
        "eligible_instruments": [row.to_dict() for row in instruments],
        "context_count": len(contexts),
        "contexts": contexts,
        "composite_freshness_policy": "oldest_required_provider_response",
        "request_timing": request_timing,
        "all_context_fresh": fresh_at_completion,
        "all_context_fresh_at_acquisition": fresh_at_acquisition,
        "all_context_fresh_at_completion": fresh_at_completion,
        "maximum_context_age_at_completion_seconds": round(
            max(completion_ages, default=0.0), 6
        ),
        "maximum_context_age_policy_seconds": DEFAULT_FRESHNESS_SECONDS,
        "provider_call_authorized": True,
        "provider_call_attempted": request_count > 0,
        "provider_request_succeeded": True,
        "provider_request_count": request_count,
        "provider_request_bound": len(instruments) * len(_PATH_LABELS),
        "retries": 0,
        "redirects_followed": 0,
        "exact_response_capture_count": len(captured_responses),
        "exact_response_capture_available": (
            len(captured_responses) == request_count
        ),
        "artifact_persisted": False,
        "immutable_capture_implemented": False,
        "campaign_attached": False,
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_input_quality_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "recorded_403_policy": (
            "fail_closed_no_retry_proxy_VPN_region_bypass_or_alternate_host"
        ),
        **_SAFETY,
    }


def _collect_authoritative_bybit_derivatives(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[dict[str, object], tuple[BybitCapturedJSONResponse, ...]]:
    clock = now or (lambda: datetime.now(timezone.utc))
    started = _utc(clock())
    if timeout_seconds <= 0 or timeout_seconds > 30:
        raise BybitDerivativesContextLiveError("timeout_seconds_out_of_bounds")
    readiness = build_bybit_derivatives_live_readiness(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=started,
        capture_loader=capture_loader,
        resolver=resolver,
    )
    reasons = readiness["reasons"]
    if isinstance(reasons, list) and reasons:
        raise BybitDerivativesContextLiveError(str(reasons[0]))
    try:
        instruments = tuple(
            _instrument_from_values(row) for row in readiness["eligible_instruments"]
        )
    except BybitIntradayLiveError as exc:
        raise BybitDerivativesContextLiveError(exc.reason_code) from exc
    capture_id = readiness["source_execution_quality_capture_id"]
    fetch = fetch_json or _fetch_public_json
    contexts: list[dict[str, object]] = []
    captured_responses: list[BybitCapturedJSONResponse] = []
    request_timing: list[dict[str, object]] = []
    request_count = 0
    lineage_seed = hashlib.sha256(
        f"{capture_id}|{_iso(started)}".encode("utf-8")
    ).hexdigest()[:24]
    try:
        for instrument_index, instrument in enumerate(instruments, start=1):
            context, captured, timing = _collect_instrument(
                instrument,
                instrument_index=instrument_index,
                lineage_seed=lineage_seed,
                fetch=fetch,
                clock=clock,
                timeout_seconds=timeout_seconds,
            )
            request_count += len(_PATH_LABELS)
            contexts.append(context)
            captured_responses.extend(captured)
            request_timing.extend(timing)
    except BybitDerivativesContextLiveError as exc:
        attempted = request_count + max(1, exc.request_count)
        raise BybitDerivativesContextLiveError(
            exc.reason_code,
            provider_status=exc.provider_status,
            http_status=exc.http_status,
            request_count=attempted,
        ) from exc
    except BybitExecutionQualityLiveError as exc:
        raise BybitDerivativesContextLiveError(
            exc.reason_code,
            provider_status=exc.provider_status,
            http_status=exc.http_status,
            request_count=request_count + 1,
        ) from exc
    except BybitDerivativesContextError as exc:
        raise BybitDerivativesContextLiveError(
            str(exc), request_count=request_count + len(_PATH_LABELS)
        ) from exc
    except Exception as exc:
        raise BybitDerivativesContextLiveError(
            getattr(exc, "reason_code", "provider_request_failed"),
            request_count=request_count + 1,
        ) from exc
    completed = _utc(clock())
    _revalidate_prerequisites(
        artifact_base_dir,
        expected_capture_id=capture_id,
        expected_instruments=instruments,
        checked_at=completed,
        capture_loader=capture_loader,
        resolver=resolver,
    )
    expected = len(instruments) * len(_PATH_LABELS)
    if request_count != expected or len(contexts) != len(instruments):
        raise BybitDerivativesContextLiveError(
            "derivatives_collection_count_mismatch",
            request_count=request_count,
        )
    summary = _observation_set_summary(
        started=started,
        completed=completed,
        readiness=readiness,
        capture_id=capture_id,
        instruments=instruments,
        contexts=contexts,
        request_timing=request_timing,
        request_count=request_count,
        captured_responses=captured_responses,
    )
    return summary, tuple(captured_responses)


def collect_authoritative_bybit_derivatives(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Collect exact venue-native context without persistence or policy use."""

    summary, _responses = _collect_authoritative_bybit_derivatives(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=now,
        capture_loader=capture_loader,
        resolver=resolver,
        fetch_json=fetch_json,
        timeout_seconds=timeout_seconds,
    )
    return summary


def capture_authoritative_bybit_derivatives(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Collect once and seal exact derivatives bytes as immutable evidence."""

    summary, responses = _collect_authoritative_bybit_derivatives(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=now,
        capture_loader=capture_loader,
        resolver=resolver,
        fetch_json=fetch_json,
        timeout_seconds=timeout_seconds,
    )
    request_count = int(summary["provider_request_count"])
    if len(responses) != request_count:
        raise BybitDerivativesContextLiveError(
            "exact_provider_response_capture_unavailable",
            request_count=request_count,
        )
    try:
        return persist_bybit_derivatives_context_capture(
            artifact_base_dir,
            summary=summary,
            responses=responses,
        )
    except BybitDerivativesContextCaptureError as exc:
        raise BybitDerivativesContextLiveError(
            f"capture_{exc}",
            request_count=request_count,
        ) from exc


def _failure_payload(exc: BybitDerivativesContextLiveError) -> dict[str, object]:
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_derivatives_context_live_failure",
        "status": "blocked",
        "reason": exc.reason_code,
        "provider_status": exc.provider_status,
        "http_status": exc.http_status,
        "provider_request_count": exc.request_count,
        "provider_request_succeeded": False,
        "artifact_persisted": False,
        "campaign_attached": False,
        "context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_input_quality_eligible": False,
        "protocol_v2_evidence_eligible": False,
        **_SAFETY,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("readiness", "collect", "capture", "status"):
        command = commands.add_parser(name)
        command.add_argument(
            "--artifact-base",
            type=Path,
            default=Path(config.EVENT_ALPHA_ARTIFACT_BASE_DIR),
        )
    for name in ("collect", "capture"):
        commands.choices[name].add_argument(
            "--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS
        )
        commands.choices[name].add_argument("--confirm", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "readiness":
        payload = build_bybit_derivatives_live_readiness(
            artifact_base_dir=args.artifact_base
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.command == "status":
        payload = bybit_derivatives_context_capture_status(args.artifact_base)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if not args.confirm:
        payload = _failure_payload(
            BybitDerivativesContextLiveError(
                "explicit_collection_confirmation_required"
            )
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    try:
        operation = (
            capture_authoritative_bybit_derivatives
            if args.command == "capture"
            else collect_authoritative_bybit_derivatives
        )
        payload = operation(
            artifact_base_dir=args.artifact_base,
            timeout_seconds=args.timeout_seconds,
        )
    except BybitDerivativesContextLiveError as exc:
        print(json.dumps(_failure_payload(exc), indent=2, sort_keys=True))
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


__all__ = (
    "AUTHORIZATION_ACTION",
    "CAPTURE_COMMAND",
    "COLLECT_COMMAND",
    "CONTRACT_VERSION",
    "LIVE_AUTH_ENV",
    "MAX_PLANNED_REQUESTS",
    "READINESS_COMMAND",
    "STATUS_COMMAND",
    "BybitDerivativesContextLiveError",
    "_collect_authoritative_bybit_derivatives",
    "build_bybit_derivatives_live_readiness",
    "capture_authoritative_bybit_derivatives",
    "collect_authoritative_bybit_derivatives",
    "main",
)


if __name__ == "__main__":
    raise SystemExit(main())
