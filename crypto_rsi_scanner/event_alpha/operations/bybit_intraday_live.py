"""Guarded direct Bybit 1h/4h collection for Decision Radar research.

Readiness is no-network/no-write. Collection is unavailable unless a complete
fresh execution-quality capture is bound to the exact current Radar authority,
the separate intraday authorization already exists, and the operator confirms
the command. The adapter performs public GETs only, never retries, and has no
credential, private-data, order, trading, notification, or Radar-publication
path.
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
from ..dashboard.readiness import DashboardReadinessError, resolve_authoritative_dashboard
from .bybit_execution_quality import (
    CONTRACT_TYPE,
    INSTRUMENT_STATUS,
    MAX_RADAR_ASSETS,
    QUOTE_ASSET,
    BybitEligibleInstrument,
    BybitPublicRequest,
)
from .bybit_execution_quality_capture import (
    BybitCapturedJSONResponse,
    BybitExecutionQualityCaptureError,
    load_latest_bybit_execution_quality_capture,
)
from .bybit_execution_quality_live import _fetch_public_json
from .bybit_intraday import (
    INTERVAL_SECONDS,
    BybitIntradayError,
    build_bybit_kline_request,
    normalize_bybit_completed_kline,
)
from .bybit_intraday_capture import (
    BybitIntradayCaptureError,
    bybit_intraday_capture_status,
    persist_bybit_intraday_capture,
)


CONTRACT_VERSION = "crypto_radar_bybit_intraday_live_v1"
LIVE_AUTH_ENV = "RSI_DECISION_RADAR_BYBIT_INTRADAY_LIVE"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_PROVIDER_REQUESTS = MAX_RADAR_ASSETS * len(INTERVAL_SECONDS)
READINESS_COMMAND = "make radar-intraday-bybit-readiness PYTHON=.venv/bin/python"
COLLECT_COMMAND = (
    "CONFIRM=1 make radar-intraday-bybit-collect PYTHON=.venv/bin/python"
)
CAPTURE_COMMAND = (
    "CONFIRM=1 make radar-intraday-bybit-capture PYTHON=.venv/bin/python"
)
STATUS_COMMAND = "make radar-intraday-bybit-status PYTHON=.venv/bin/python"
AUTHORIZATION_ACTION = (
    f"set_{LIVE_AUTH_ENV}=1_in_local_gitignored_dotenv_then_rerun_readiness"
)
_STABLE_AUTHORITY_KEYS = (
    "artifact_namespace",
    "run_id",
    "revision",
    "operator_state_sha256",
)
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


class _BybitIntradayLiveError(RuntimeError):
    """Closed live-boundary failure without provider payload leakage."""

    def __init__(self, reason_code: str, *, request_count: int = 0) -> None:
        self.reason_code = _safe_code(reason_code)
        self.request_count = max(0, min(int(request_count), MAX_PROVIDER_REQUESTS))
        super().__init__(self.reason_code)


BybitIntradayLiveError = _BybitIntradayLiveError
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


def _enabled(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BybitIntradayLiveError("clock_must_include_timezone")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _instrument_from_values(value: object) -> BybitEligibleInstrument:
    if not isinstance(value, Mapping):
        raise BybitIntradayLiveError("eligible_instrument_schema_invalid")
    expected = {
        "base_asset",
        "canonical_asset_id",
        "contract_type",
        "delivery_time_ms",
        "instrument_id",
        "launch_time_ms",
        "liquidity_rank",
        "quantity_step",
        "quote_asset",
        "radar_symbol",
        "settle_asset",
        "status",
        "tick_size",
    }
    if set(value) != expected:
        raise BybitIntradayLiveError("eligible_instrument_schema_invalid")
    try:
        instrument = BybitEligibleInstrument(
            canonical_asset_id=str(value["canonical_asset_id"]),
            radar_symbol=str(value["radar_symbol"]),
            liquidity_rank=int(value["liquidity_rank"]),
            instrument_id=str(value["instrument_id"]),
            base_asset=str(value["base_asset"]),
            quote_asset=str(value["quote_asset"]),
            settle_asset=str(value["settle_asset"]),
            contract_type=str(value["contract_type"]),
            status=str(value["status"]),
            tick_size=str(value["tick_size"]),
            quantity_step=str(value["quantity_step"]),
            launch_time_ms=int(value["launch_time_ms"]),
            delivery_time_ms=int(value["delivery_time_ms"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BybitIntradayLiveError("eligible_instrument_schema_invalid") from exc
    if (
        instrument.quote_asset != QUOTE_ASSET
        or instrument.settle_asset != QUOTE_ASSET
        or instrument.contract_type != CONTRACT_TYPE
        or instrument.status != INSTRUMENT_STATUS
        or instrument.radar_symbol != instrument.base_asset
        or instrument.instrument_id != f"{instrument.base_asset}{QUOTE_ASSET}"
        or not 1 <= instrument.liquidity_rank <= MAX_RADAR_ASSETS
    ):
        raise BybitIntradayLiveError("eligible_instrument_contract_invalid")
    return instrument


def _current_authority(
    artifact_base_dir: str | Path,
    *,
    now: datetime,
    resolver: Resolver,
) -> dict[str, object]:
    try:
        resolved = resolver(artifact_base_dir, now=now)
    except DashboardReadinessError as exc:
        raise BybitIntradayLiveError("authoritative_market_generation_unavailable") from exc
    except Exception as exc:
        raise BybitIntradayLiveError("authoritative_market_generation_unreadable") from exc
    snapshot = resolved.snapshot
    return {
        "artifact_namespace": snapshot.artifact_namespace,
        "run_id": snapshot.run_id,
        "revision": snapshot.revision,
        "operator_state_sha256": snapshot.operator_state_sha256,
        "authority_checked_at": snapshot.generation_authority_checked_at,
    }


def _execution_capture_context(
    artifact_base_dir: str | Path,
    *,
    now: datetime,
    loader: CaptureLoader,
    resolver: Resolver,
) -> tuple[dict[str, object] | None, tuple[BybitEligibleInstrument, ...], list[str]]:
    try:
        capture = dict(loader(artifact_base_dir))
    except (BybitExecutionQualityCaptureError, OSError, ValueError, RuntimeError):
        return None, (), ["execution_quality_capture_unavailable"]
    reasons: list[str] = []
    if (
        capture.get("status") != "complete"
        or capture.get("evidence_authority_eligible") is not True
        or capture.get("protocol_v2_input_quality_eligible") is not True
        or not isinstance(capture.get("capture_id"), str)
    ):
        reasons.append("execution_quality_capture_not_input_quality_eligible")
    values = capture.get("eligible_instruments")
    instruments: tuple[BybitEligibleInstrument, ...] = ()
    if not isinstance(values, list) or not values or len(values) > MAX_RADAR_ASSETS:
        reasons.append("execution_quality_instrument_set_unavailable")
    else:
        try:
            instruments = tuple(_instrument_from_values(row) for row in values)
        except BybitIntradayLiveError as exc:
            reasons.append(exc.reason_code)
        if len({row.instrument_id for row in instruments}) != len(instruments):
            reasons.append("eligible_instrument_identity_duplicate")
    source = capture.get("source_authority")
    if not isinstance(source, Mapping):
        reasons.append("execution_quality_source_authority_invalid")
    else:
        try:
            current = _current_authority(
                artifact_base_dir,
                now=now,
                resolver=resolver,
            )
        except BybitIntradayLiveError as exc:
            reasons.append(exc.reason_code)
        else:
            if any(
                current.get(key) != source.get(key) for key in _STABLE_AUTHORITY_KEYS
            ):
                reasons.append("execution_quality_capture_not_current_authority")
    return capture, instruments, list(dict.fromkeys(reasons))


def build_bybit_intraday_live_readiness(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
) -> dict[str, object]:
    """Inspect prerequisites and authorization with no network call or write."""

    checked = _utc(now or datetime.now(timezone.utc))
    env = os.environ if environ is None else environ
    authorized = _enabled(env.get(LIVE_AUTH_ENV))
    capture, instruments, reasons = _execution_capture_context(
        artifact_base_dir,
        now=checked,
        loader=capture_loader,
        resolver=resolver,
    )
    if not authorized:
        reasons.append("runtime_provider_authorization_absent")
    request_bound = len(instruments) * len(INTERVAL_SECONDS)
    ready = not reasons
    only_auth_missing = reasons == ["runtime_provider_authorization_absent"]
    latest_capture = bybit_intraday_capture_status(artifact_base_dir)
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_intraday_live_readiness",
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "checked_at": _iso(checked),
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "quote_asset": QUOTE_ASSET,
        "intervals": ["1h", "4h"],
        "runtime_authorization_env": LIVE_AUTH_ENV,
        "runtime_provider_authorized": authorized,
        "authorization_mutated": False,
        "execution_quality_capture": capture,
        "execution_quality_capture_id": (
            capture.get("capture_id") if isinstance(capture, Mapping) else None
        ),
        "eligible_instrument_count": len(instruments),
        "eligible_instruments": [row.to_dict() for row in instruments],
        "maximum_provider_requests_for_current_capture": request_bound,
        "absolute_provider_request_bound": MAX_PROVIDER_REQUESTS,
        "provider_call_planned": False,
        "provider_call_attempted": False,
        "artifact_persisted": False,
        "capture_publication_available": True,
        "latest_intraday_capture_status": latest_capture.get("status"),
        "latest_intraday_capture": latest_capture,
        "evidence_publication_status": (
            "latest_immutable_capture_available"
            if latest_capture.get("status") == "complete"
            else "no_immutable_capture_available"
        ),
        "campaign_attached": False,
        "protocol_v2_evidence_eligible": False,
        "reasons": reasons,
        "next_safe_command": CAPTURE_COMMAND if ready else READINESS_COMMAND,
        "readiness_recheck_command": READINESS_COMMAND,
        "authorized_capture_command": CAPTURE_COMMAND,
        "diagnostic_collect_command": COLLECT_COMMAND,
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
        "capture_confirmation_required": True,
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


def _payload_and_timing(
    result: FetchResult,
    *,
    fallback_started: datetime,
    fallback_acquired: datetime,
) -> tuple[Mapping[str, object], datetime, datetime]:
    if isinstance(result, BybitCapturedJSONResponse):
        try:
            started = datetime.fromisoformat(
                result.request_started_at.replace("Z", "+00:00")
            )
            acquired = datetime.fromisoformat(
                result.response_received_at.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise BybitIntradayLiveError("provider_response_timing_invalid") from exc
        return result.payload(), _utc(started), _utc(acquired)
    if isinstance(result, Mapping):
        return result, fallback_started, fallback_acquired
    raise BybitIntradayLiveError("provider_json_root_invalid")


def _revalidate_prerequisites(
    artifact_base_dir: str | Path,
    *,
    expected_capture_id: object,
    expected_instruments: Sequence[BybitEligibleInstrument],
    checked_at: datetime,
    capture_loader: CaptureLoader,
    resolver: Resolver,
) -> None:
    capture, instruments, reasons = _execution_capture_context(
        artifact_base_dir,
        now=checked_at,
        loader=capture_loader,
        resolver=resolver,
    )
    if (
        reasons
        or capture is None
        or capture.get("capture_id") != expected_capture_id
        or instruments != tuple(expected_instruments)
    ):
        raise BybitIntradayLiveError("intraday_source_prerequisite_drifted")


def _collect_authoritative_bybit_intraday(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[dict[str, object], list[BybitCapturedJSONResponse]]:
    """Collect bars and retain exact responses when the transport exposes them."""

    clock = now or (lambda: datetime.now(timezone.utc))
    started = _utc(clock())
    if timeout_seconds <= 0 or timeout_seconds > 30:
        raise BybitIntradayLiveError("timeout_seconds_out_of_bounds")
    readiness = build_bybit_intraday_live_readiness(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=started,
        capture_loader=capture_loader,
        resolver=resolver,
    )
    reasons = readiness["reasons"]
    if isinstance(reasons, list) and reasons:
        raise BybitIntradayLiveError(str(reasons[0]))
    instruments = tuple(
        _instrument_from_values(row) for row in readiness["eligible_instruments"]
    )
    capture_id = readiness["execution_quality_capture_id"]
    fetch = fetch_json or _fetch_public_json
    request_count = 0
    bars: list[dict[str, object]] = []
    captured_responses: list[BybitCapturedJSONResponse] = []
    lineage_seed = hashlib.sha256(
        f"{capture_id}|{_iso(started)}".encode("utf-8")
    ).hexdigest()[:24]
    try:
        for instrument_index, instrument in enumerate(instruments, start=1):
            for interval_index, interval in enumerate(INTERVAL_SECONDS, start=1):
                request = build_bybit_kline_request(
                    instrument,
                    interval=interval,
                    as_of=started,
                )
                fallback_started = _utc(clock())
                request_count += 1
                result = fetch(request, timeout_seconds)
                fallback_acquired = _utc(clock())
                if isinstance(result, BybitCapturedJSONResponse):
                    if result.request != request:
                        raise BybitIntradayLiveError(
                            "provider_response_request_mismatch",
                            request_count=request_count,
                        )
                    captured_responses.append(result)
                payload, request_started, acquired = _payload_and_timing(
                    result,
                    fallback_started=fallback_started,
                    fallback_acquired=fallback_acquired,
                )
                bar = normalize_bybit_completed_kline(
                    payload,
                    instrument=instrument,
                    request=request,
                    request_started_at=request_started,
                    acquired_at=acquired,
                    request_lineage_id=(
                        f"bybit.intraday.{lineage_seed}."
                        f"{instrument_index}.{interval_index}"
                    ),
                )
                bars.append(bar.to_dict())
    except BybitIntradayLiveError as exc:
        raise BybitIntradayLiveError(
            exc.reason_code,
            request_count=request_count,
        ) from exc
    except BybitIntradayError as exc:
        raise BybitIntradayLiveError(
            str(exc),
            request_count=request_count,
        ) from exc
    except Exception as exc:
        reason = getattr(exc, "reason_code", "provider_request_failed")
        raise BybitIntradayLiveError(
            str(reason),
            request_count=request_count,
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
    expected = len(instruments) * len(INTERVAL_SECONDS)
    if request_count != expected or len(bars) != expected:
        raise BybitIntradayLiveError(
            "intraday_collection_count_mismatch",
            request_count=request_count,
        )
    summary = {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_intraday_observation_set",
        "status": "complete",
        "started_at": _iso(started),
        "completed_at": _iso(completed),
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "quote_asset": QUOTE_ASSET,
        "intervals": ["1h", "4h"],
        "source_execution_quality_capture_id": capture_id,
        "source_execution_quality_capture": readiness[
            "execution_quality_capture"
        ],
        "eligible_instrument_count": len(instruments),
        "eligible_instruments": [row.to_dict() for row in instruments],
        "bar_count": len(bars),
        "bars": bars,
        "all_bars_fresh": all(row["freshness_status"] == "fresh" for row in bars),
        "provider_call_authorized": True,
        "provider_call_attempted": request_count > 0,
        "provider_request_succeeded": True,
        "provider_request_count": request_count,
        "provider_request_bound": expected,
        "retries": 0,
        "redirects_followed": 0,
        "artifact_persisted": False,
        "campaign_attached": False,
        "protocol_v2_evidence_eligible": False,
        "recorded_403_policy": (
            "fail_closed_no_retry_proxy_VPN_region_bypass_or_alternate_host"
        ),
        **_SAFETY,
    }
    return summary, captured_responses


def collect_authoritative_bybit_intraday(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Collect direct completed bars without persistence or campaign mutation."""

    summary, _responses = _collect_authoritative_bybit_intraday(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=now,
        capture_loader=capture_loader,
        resolver=resolver,
        fetch_json=fetch_json,
        timeout_seconds=timeout_seconds,
    )
    return summary


def capture_authoritative_bybit_intraday(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    capture_loader: CaptureLoader = load_latest_bybit_execution_quality_capture,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Collect once and seal exact response bytes as immutable research evidence."""

    summary, responses = _collect_authoritative_bybit_intraday(
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
        raise BybitIntradayLiveError(
            "exact_provider_response_capture_unavailable",
            request_count=request_count,
        )
    try:
        return persist_bybit_intraday_capture(
            artifact_base_dir,
            summary=summary,
            responses=responses,
        )
    except BybitIntradayCaptureError as exc:
        raise BybitIntradayLiveError(
            f"capture_{exc}",
            request_count=request_count,
        ) from exc


def _failure_payload(exc: BybitIntradayLiveError) -> dict[str, object]:
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_intraday_live_failure",
        "status": "blocked",
        "reason": exc.reason_code,
        "provider_request_count": exc.request_count,
        "provider_request_succeeded": False,
        "artifact_persisted": False,
        "campaign_attached": False,
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
        payload = build_bybit_intraday_live_readiness(
            artifact_base_dir=args.artifact_base
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.command == "status":
        payload = bybit_intraday_capture_status(args.artifact_base)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if not args.confirm:
        payload = _failure_payload(
            BybitIntradayLiveError("explicit_collection_confirmation_required")
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    try:
        operation = (
            capture_authoritative_bybit_intraday
            if args.command == "capture"
            else collect_authoritative_bybit_intraday
        )
        payload = operation(
            artifact_base_dir=args.artifact_base,
            timeout_seconds=args.timeout_seconds,
        )
    except BybitIntradayLiveError as exc:
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
    "MAX_PROVIDER_REQUESTS",
    "READINESS_COMMAND",
    "STATUS_COMMAND",
    "BybitIntradayLiveError",
    "_collect_authoritative_bybit_intraday",
    "build_bybit_intraday_live_readiness",
    "capture_authoritative_bybit_intraday",
    "collect_authoritative_bybit_intraday",
    "main",
)


if __name__ == "__main__":
    raise SystemExit(main())
