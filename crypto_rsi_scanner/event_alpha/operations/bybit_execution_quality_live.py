"""Guarded public Bybit execution-quality acquisition for Decision Radar.

This module is deliberately narrower than a general provider framework.  It
binds one read to the exact authoritative Radar market generation, intersects
that point-in-time universe with active Bybit USDT-linear perpetuals, and
normalizes public order-book snapshots through the existing offline contract.

Readiness performs no network call or write.  Collection requires the already-
present execution-quality-specific authorization flag, uses public GETs only,
does not retry, and has no credential, private-data, order, or trading path.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (
    HTTPRedirectHandler,
    OpenerDirector,
    ProxyHandler,
    build_opener,
)

from ... import config
from ...event_providers.bybit_announcements.provider_support import (
    BybitAPIResponseError,
    build_bybit_public_request,
    bybit_response_diagnostics,
    classify_bybit_failure,
    raise_for_bybit_api_error,
)
from ..dashboard.readiness import (
    DashboardReadinessError,
    resolve_authoritative_dashboard,
)
from .bybit_execution_quality import (
    BYBIT_CATEGORY,
    CONTRACT_TYPE,
    INSTRUMENTS_PATH,
    INSTRUMENT_STATUS,
    MAX_RADAR_ASSETS,
    ORDERBOOK_PATH,
    PUBLIC_API_BASE,
    QUOTE_ASSET,
    BybitEligibleInstrument,
    BybitExecutionQualityError,
    BybitPublicRequest,
    normalize_bybit_orderbook,
    select_bybit_usdt_perpetual_instruments,
)
from .bybit_execution_quality_universe import (
    BybitExecutionQualityUniverseError,
    partition_bybit_provider_query_assets as _partition_provider_query_assets,
)
from .bybit_execution_quality_capture import (
    BybitCapturedJSONResponse,
    BybitExecutionQualityCaptureError,
    bybit_execution_quality_capture_status,
    persist_bybit_execution_quality_capture,
)


CONTRACT_VERSION = "crypto_radar_bybit_execution_quality_live_v1"
LIVE_AUTH_ENV = "RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_PROVIDER_REQUESTS = MAX_RADAR_ASSETS * 2
READINESS_COMMAND = (
    "make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python"
)
COLLECT_COMMAND = (
    "CONFIRM=1 make radar-execution-quality-bybit-collect PYTHON=.venv/bin/python"
)
CAPTURE_COMMAND = (
    "CONFIRM=1 make radar-execution-quality-bybit-capture PYTHON=.venv/bin/python"
)
SAFETY = {
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


class BybitExecutionQualityLiveError(RuntimeError):
    """Closed, credential-free live acquisition failure."""

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
        self.request_count = max(0, min(int(request_count), MAX_PROVIDER_REQUESTS))
        super().__init__(self.reason_code)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: object,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


Resolver = Callable[..., Any]
FetchResult = Mapping[str, object] | BybitCapturedJSONResponse
FetchJSON = Callable[[BybitPublicRequest, float], FetchResult]
Clock = Callable[[], datetime]


def _safe_code(value: object) -> str:
    text = str(value or "unknown").strip().casefold()
    cleaned = "".join(character if character.isalnum() or character == "_" else "_" for character in text)
    return cleaned[:96] or "unknown"


def _enabled(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BybitExecutionQualityLiveError("clock_must_include_timezone")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _positive_number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise BybitExecutionQualityLiveError(f"{label}_invalid")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise BybitExecutionQualityLiveError(f"{label}_invalid") from exc
    if not 0 < parsed < float("inf"):
        raise BybitExecutionQualityLiveError(f"{label}_invalid")
    return parsed


def project_authoritative_radar_assets(
    observations: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Project the exact top-liquid live observations into the Bybit matcher."""

    if not observations:
        raise BybitExecutionQualityLiveError("authoritative_market_observations_empty")
    if len(observations) > MAX_RADAR_ASSETS:
        raise BybitExecutionQualityLiveError("authoritative_market_observations_exceed_30")

    projected: list[tuple[float, str, str]] = []
    canonical_ids: set[str] = set()
    symbols: set[str] = set()
    for raw in observations:
        if not isinstance(raw, Mapping):
            raise BybitExecutionQualityLiveError("authoritative_market_observation_invalid")
        if (
            raw.get("data_mode") != "live"
            or raw.get("candidate_source_mode") != "live_no_send"
            or raw.get("decision_radar_campaign_counted") is not True
            or raw.get("provenance_contract_valid") is not True
            or raw.get("research_only") is not True
            or raw.get("no_send") is not True
            or raw.get("freshness_status") != "fresh"
        ):
            raise BybitExecutionQualityLiveError(
                "authoritative_market_observation_provenance_invalid"
            )
        canonical_id = str(raw.get("canonical_asset_id") or "").strip()
        symbol = str(raw.get("symbol") or "").strip().upper()
        if not canonical_id or not symbol:
            raise BybitExecutionQualityLiveError(
                "authoritative_market_observation_identity_missing"
            )
        if canonical_id in canonical_ids or symbol in symbols:
            raise BybitExecutionQualityLiveError(
                "authoritative_market_observation_identity_duplicate"
            )
        canonical_ids.add(canonical_id)
        symbols.add(symbol)
        projected.append(
            (
                _positive_number(raw.get("liquidity_usd"), "liquidity_usd"),
                canonical_id,
                symbol,
            )
        )

    projected.sort(key=lambda row: (-row[0], row[1], row[2]))
    return tuple(
        {
            "canonical_asset_id": canonical_id,
            "symbol": symbol,
            "liquidity_rank": rank,
            "liquidity_usd": liquidity,
        }
        for rank, (liquidity, canonical_id, symbol) in enumerate(projected, start=1)
    )


def partition_bybit_provider_query_assets(
    assets: Sequence[Mapping[str, object]],
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    """Exclude non-contract-shaped Radar symbols before any provider request."""

    try:
        return _partition_provider_query_assets(assets)
    except BybitExecutionQualityUniverseError as exc:
        reason = (
            "radar_asset_query_schema_invalid"
            if exc.reason_code == "radar_asset_schema_invalid"
            else exc.reason_code
        )
        raise BybitExecutionQualityLiveError(reason) from exc


def _load_authoritative_context(
    artifact_base_dir: str | Path,
    *,
    now: datetime,
    resolver: Resolver,
) -> tuple[dict[str, object] | None, tuple[dict[str, object], ...], list[str]]:
    try:
        resolved = resolver(artifact_base_dir, now=now)
    except DashboardReadinessError:
        return None, (), ["authoritative_market_generation_unavailable"]
    except Exception:
        return None, (), ["authoritative_market_generation_unreadable"]

    snapshot = resolved.snapshot
    identity = {
        "artifact_namespace": snapshot.artifact_namespace,
        "run_id": snapshot.run_id,
        "revision": snapshot.revision,
        "operator_state_sha256": snapshot.operator_state_sha256,
        "authority_checked_at": snapshot.generation_authority_checked_at,
    }
    try:
        assets = project_authoritative_radar_assets(snapshot.current_market_observations)
    except BybitExecutionQualityLiveError as exc:
        return identity, (), [exc.reason_code]
    return identity, assets, []


def build_bybit_execution_quality_live_readiness(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
    resolver: Resolver = resolve_authoritative_dashboard,
) -> dict[str, object]:
    """Inspect exact authority and explicit authorization without network/writes."""

    checked = _utc(now or datetime.now(timezone.utc))
    env = os.environ if environ is None else environ
    authorized = _enabled(env.get(LIVE_AUTH_ENV))
    identity, assets, reasons = _load_authoritative_context(
        artifact_base_dir,
        now=checked,
        resolver=resolver,
    )
    try:
        query_assets, excluded_assets = partition_bybit_provider_query_assets(assets)
    except BybitExecutionQualityLiveError as exc:
        query_assets, excluded_assets = (), ()
        reasons.append(exc.reason_code)
    if assets and not query_assets:
        reasons.append("bybit_provider_query_universe_empty")
    if not authorized:
        reasons.append("runtime_provider_authorization_absent")
    request_bound = len(query_assets) * 2
    ready = not reasons
    latest_capture = bybit_execution_quality_capture_status(artifact_base_dir)
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_execution_quality_live_readiness",
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "checked_at": _iso(checked),
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "category": BYBIT_CATEGORY,
        "quote_asset": QUOTE_ASSET,
        "runtime_authorization_env": LIVE_AUTH_ENV,
        "runtime_provider_authorized": authorized,
        "current_authority": identity,
        "radar_asset_count": len(assets),
        "radar_assets": [dict(row) for row in assets],
        "provider_query_asset_count": len(query_assets),
        "provider_query_assets": [dict(row) for row in query_assets],
        "preflight_excluded_asset_count": len(excluded_assets),
        "preflight_excluded_assets": [dict(row) for row in excluded_assets],
        "maximum_provider_requests_for_current_universe": request_bound,
        "absolute_provider_request_bound": MAX_PROVIDER_REQUESTS,
        "provider_call_planned": False,
        "provider_call_attempted": False,
        "evidence_authority_eligible": False,
        "capture_publication_available": True,
        "latest_capture_status": latest_capture.get("status"),
        "latest_capture": latest_capture,
        "evidence_publication_status": (
            "no_immutable_capture_available"
            if latest_capture.get("status") != "complete"
            else "latest_immutable_capture_available"
        ),
        "reasons": reasons,
        "next_safe_command": CAPTURE_COMMAND if ready else READINESS_COMMAND,
        "expected_provider_activity": (
            f"collect_at_most_{request_bound}_public_GETs_no_retries"
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
        **SAFETY,
    }


def _instrument_request(asset: Mapping[str, object]) -> BybitPublicRequest:
    symbol = str(asset["symbol"])
    return BybitPublicRequest(
        method="GET",
        path=INSTRUMENTS_PATH,
        query=(("category", BYBIT_CATEGORY), ("symbol", f"{symbol}{QUOTE_ASSET}")),
    )


def _orderbook_request(instrument: BybitEligibleInstrument) -> BybitPublicRequest:
    return BybitPublicRequest(
        method="GET",
        path=ORDERBOOK_PATH,
        query=(
            ("category", BYBIT_CATEGORY),
            ("symbol", instrument.instrument_id),
            ("limit", "200"),
        ),
    )


def collect_authoritative_bybit_execution_quality(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Collect one bounded public snapshot set from exact current authority."""

    summary, _responses = _collect_authoritative_bybit_execution_quality(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=now,
        resolver=resolver,
        fetch_json=fetch_json,
        timeout_seconds=timeout_seconds,
    )
    return summary


def _payload_and_capture(result: FetchResult) -> tuple[Mapping[str, object], BybitCapturedJSONResponse | None]:
    if isinstance(result, BybitCapturedJSONResponse):
        return result.payload(), result
    if isinstance(result, Mapping):
        return result, None
    raise BybitExecutionQualityLiveError("provider_json_root_invalid")


def _collect_authoritative_bybit_execution_quality(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[dict[str, object], tuple[BybitCapturedJSONResponse, ...]]:
    """Collect normalized values plus any exact transport response buffers."""

    clock = now or (lambda: datetime.now(timezone.utc))
    started = _utc(clock())
    env = os.environ if environ is None else environ
    identity, assets, reasons = _load_authoritative_context(
        artifact_base_dir,
        now=started,
        resolver=resolver,
    )
    try:
        query_assets, excluded_assets = partition_bybit_provider_query_assets(assets)
    except BybitExecutionQualityLiveError as exc:
        query_assets, excluded_assets = (), ()
        reasons.append(exc.reason_code)
    if assets and not query_assets:
        reasons.append("bybit_provider_query_universe_empty")
    if not _enabled(env.get(LIVE_AUTH_ENV)):
        reasons.append("runtime_provider_authorization_absent")
    if reasons:
        raise BybitExecutionQualityLiveError(reasons[0])
    if timeout_seconds <= 0 or timeout_seconds > 30:
        raise BybitExecutionQualityLiveError("timeout_seconds_out_of_bounds")
    if identity is None:
        raise BybitExecutionQualityLiveError("authoritative_market_generation_unavailable")

    fetch = fetch_json or _fetch_public_json
    requests_attempted = 0
    eligible: list[BybitEligibleInstrument] = []
    captured_responses: list[BybitCapturedJSONResponse] = []
    try:
        for asset in query_assets:
            request = _instrument_request(asset)
            requests_attempted += 1
            payload, captured = _payload_and_capture(fetch(request, timeout_seconds))
            if captured is not None:
                captured_responses.append(captured)
            selected = select_bybit_usdt_perpetual_instruments((asset,), payload)
            if selected:
                eligible.append(selected[0])

        snapshots: list[dict[str, object]] = []
        lineage_seed = hashlib.sha256(
            (
                f"{identity['artifact_namespace']}|{identity['run_id']}|"
                f"{identity['revision']}|{_iso(started)}"
            ).encode("utf-8")
        ).hexdigest()[:24]
        for index, instrument in enumerate(eligible, start=1):
            request = _orderbook_request(instrument)
            requests_attempted += 1
            payload, captured = _payload_and_capture(fetch(request, timeout_seconds))
            if captured is not None:
                captured_responses.append(captured)
            acquired = _utc(clock())
            snapshot = normalize_bybit_orderbook(
                payload,
                instrument=instrument,
                acquired_at=_iso(acquired),
                request_lineage_id=f"bybit.eq.{lineage_seed}.{index}",
            )
            snapshots.append(snapshot.to_dict())
    except BybitExecutionQualityLiveError as exc:
        raise BybitExecutionQualityLiveError(
            exc.reason_code,
            provider_status=exc.provider_status,
            http_status=exc.http_status,
            request_count=requests_attempted,
        ) from exc
    except BybitExecutionQualityError as exc:
        raise BybitExecutionQualityLiveError(
            "provider_payload_contract_invalid",
            request_count=requests_attempted,
        ) from exc
    except Exception as exc:
        raise BybitExecutionQualityLiveError(
            "provider_request_failed",
            request_count=requests_attempted,
        ) from exc

    completed = _utc(clock())
    summary = {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_execution_quality_observation_set",
        "status": "complete",
        "started_at": _iso(started),
        "completed_at": _iso(completed),
        "venue_id": "bybit",
        "execution_mode": "perpetual",
        "category": BYBIT_CATEGORY,
        "quote_asset": QUOTE_ASSET,
        "source_authority": identity,
        "radar_assets": [dict(row) for row in assets],
        "requested_radar_asset_count": len(assets),
        "provider_query_assets": [dict(row) for row in query_assets],
        "provider_query_asset_count": len(query_assets),
        "preflight_excluded_assets": [dict(row) for row in excluded_assets],
        "preflight_excluded_asset_count": len(excluded_assets),
        "eligible_instrument_count": len(eligible),
        "eligible_instruments": [row.to_dict() for row in eligible],
        "execution_quality_snapshot_count": len(snapshots),
        "execution_quality_snapshots": snapshots,
        "provider_call_authorized": True,
        "provider_call_attempted": requests_attempted > 0,
        "provider_request_succeeded": True,
        "provider_request_count": requests_attempted,
        "provider_request_bound": len(query_assets) * 2,
        "retries": 0,
        "redirects_followed": 0,
        "artifact_persisted": False,
        "campaign_attached": False,
        "evidence_authority_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "source_base_url": PUBLIC_API_BASE,
        "instrument_contract": CONTRACT_TYPE,
        "instrument_status": INSTRUMENT_STATUS,
        "recorded_403_policy": (
            "fail_closed_no_retry_proxy_VPN_region_bypass_or_alternate_host"
        ),
        **SAFETY,
    }
    return summary, tuple(captured_responses)


def capture_authoritative_bybit_execution_quality(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: Clock | None = None,
    resolver: Resolver = resolve_authoritative_dashboard,
    fetch_json: FetchJSON | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Collect and seal exact public responses without changing Radar authority."""

    summary, responses = _collect_authoritative_bybit_execution_quality(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=now,
        resolver=resolver,
        fetch_json=fetch_json,
        timeout_seconds=timeout_seconds,
    )
    if len(responses) != summary["provider_request_count"]:
        raise BybitExecutionQualityLiveError(
            "exact_provider_response_capture_unavailable",
            request_count=int(summary["provider_request_count"]),
        )
    try:
        return persist_bybit_execution_quality_capture(
            artifact_base_dir,
            summary=summary,
            responses=responses,
        )
    except BybitExecutionQualityCaptureError as exc:
        raise BybitExecutionQualityLiveError(
            f"capture_{exc}",
            request_count=int(summary["provider_request_count"]),
        ) from exc


def _fetch_public_json(
    request: BybitPublicRequest,
    timeout_seconds: float,
    *,
    opener: OpenerDirector | None = None,
) -> BybitCapturedJSONResponse:
    """Perform one fixed-host public JSON GET without redirects or retries."""

    query = dict(request.query)
    expected_keys = {
        INSTRUMENTS_PATH: {"category", "symbol"},
        ORDERBOOK_PATH: {"category", "symbol", "limit"},
    }
    if (
        request.method != "GET"
        or request.path not in expected_keys
        or set(query) != expected_keys[request.path]
        or query.get("category") != BYBIT_CATEGORY
        or (request.path == ORDERBOOK_PATH and query.get("limit") != "200")
    ):
        raise BybitExecutionQualityLiveError("public_request_contract_invalid")
    url = f"{PUBLIC_API_BASE}{request.path}?{urlencode(request.query)}"
    http_request = build_bybit_public_request(url)
    selected_opener = opener or _build_public_opener()
    response: Any | None = None
    raw: bytes | None = None
    request_started = datetime.now(timezone.utc)
    monotonic_started = time.monotonic_ns()
    try:
        with selected_opener.open(http_request, timeout=timeout_seconds) as response:
            raw_status = getattr(response, "status", None)
            status = int(raw_status if raw_status is not None else response.getcode())
            if status != 200:
                raise BybitExecutionQualityLiveError(
                    "provider_http_status",
                    provider_status=classify_bybit_failure((status,), "") or "provider_unavailable",
                    http_status=status,
                )
            if str(response.geturl()) != url:
                raise BybitExecutionQualityLiveError("provider_redirect_rejected")
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().casefold()
            if content_type not in {"application/json", "text/json"}:
                raise BybitExecutionQualityLiveError("provider_content_type_rejected")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if not raw or len(raw) > MAX_RESPONSE_BYTES:
                raise BybitExecutionQualityLiveError("provider_response_size_invalid")
        response_received = datetime.now(timezone.utc)
        captured = BybitCapturedJSONResponse(
            request=request,
            request_started_at=_iso(request_started),
            response_received_at=_iso(response_received),
            duration_ms=max(0, (time.monotonic_ns() - monotonic_started) // 1_000_000),
            response_url=url,
            http_status=status,
            content_type=content_type,
            raw_bytes=raw,
        )
        payload = captured.payload()
        raise_for_bybit_api_error(payload)
        return captured
    except BybitExecutionQualityLiveError:
        raise
    except HTTPError as exc:
        diagnostics = bybit_response_diagnostics(response=response, payload=raw, error=exc)
        text = str(diagnostics.get("response_body_summary_redacted") or "")
        status = int(exc.code) if isinstance(exc.code, int) else None
        provider_status = classify_bybit_failure((status,) if status else (), text)
        raise BybitExecutionQualityLiveError(
            "provider_http_error",
            provider_status=provider_status or "provider_unavailable",
            http_status=status,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise BybitExecutionQualityLiveError(
            "provider_unavailable",
            provider_status="provider_unavailable",
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BybitExecutionQualityLiveError("provider_json_invalid") from exc
    except BybitAPIResponseError as exc:
        provider_status = classify_bybit_failure((), str(exc))
        raise BybitExecutionQualityLiveError(
            "provider_api_error",
            provider_status=provider_status or "provider_unavailable",
        ) from exc
    except Exception as exc:
        raise BybitExecutionQualityLiveError("provider_response_rejected") from exc


def _build_public_opener() -> OpenerDirector:
    """Create a direct fixed-host opener that ignores ambient proxy settings."""

    return build_opener(ProxyHandler({}), _NoRedirectHandler())


def _failure_payload(exc: BybitExecutionQualityLiveError) -> dict[str, object]:
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_bybit_execution_quality_live_failure",
        "status": "blocked",
        "reason": exc.reason_code,
        "provider_status": exc.provider_status,
        "http_status": exc.http_status,
        "provider_request_count": exc.request_count,
        "provider_request_succeeded": False,
        "artifact_persisted": False,
        "campaign_attached": False,
        "evidence_authority_eligible": False,
        "protocol_v2_evidence_eligible": False,
        "recorded_403_policy": (
            "fail_closed_no_retry_proxy_VPN_region_bypass_or_alternate_host"
        ),
        **SAFETY,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read or collect guarded public Bybit execution-quality evidence."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("readiness", "collect", "capture", "status"):
        selected = subparsers.add_parser(command)
        selected.add_argument(
            "--artifact-base",
            type=Path,
            default=Path(config.EVENT_ALPHA_ARTIFACT_BASE_DIR),
        )
    for command in ("collect", "capture"):
        subparsers.choices[command].add_argument(
            "--timeout-seconds",
            type=float,
            default=DEFAULT_TIMEOUT_SECONDS,
        )
        subparsers.choices[command].add_argument("--confirm", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "readiness":
        payload = build_bybit_execution_quality_live_readiness(
            artifact_base_dir=args.artifact_base
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.command == "status":
        payload = bybit_execution_quality_capture_status(args.artifact_base)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if not args.confirm:
        print(
            json.dumps(
                _failure_payload(
                    BybitExecutionQualityLiveError(
                        "explicit_collection_confirmation_required"
                    )
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    try:
        operation = (
            capture_authoritative_bybit_execution_quality
            if args.command == "capture"
            else collect_authoritative_bybit_execution_quality
        )
        payload = operation(
            artifact_base_dir=args.artifact_base,
            timeout_seconds=args.timeout_seconds,
        )
    except BybitExecutionQualityLiveError as exc:
        print(json.dumps(_failure_payload(exc), indent=2, sort_keys=True))
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


__all__ = (
    "CAPTURE_COMMAND",
    "COLLECT_COMMAND",
    "CONTRACT_VERSION",
    "DEFAULT_TIMEOUT_SECONDS",
    "LIVE_AUTH_ENV",
    "MAX_PROVIDER_REQUESTS",
    "READINESS_COMMAND",
    "BybitExecutionQualityLiveError",
    "build_bybit_execution_quality_live_readiness",
    "capture_authoritative_bybit_execution_quality",
    "collect_authoritative_bybit_execution_quality",
    "main",
    "partition_bybit_provider_query_assets",
    "project_authoritative_radar_assets",
)


if __name__ == "__main__":
    raise SystemExit(main())
