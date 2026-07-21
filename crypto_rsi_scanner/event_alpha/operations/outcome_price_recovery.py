"""Guarded CoinGecko historical-price recovery for Decision Radar outcomes.

Readiness is local, no-network, and no-write. Diagnostic collection requires
both the existing general CoinGecko authorization and a separate recovery flag
plus explicit confirmation. It performs at most one fixed-host GET per exact
missing primary-horizon window, never retries, retains exact response bytes only
in memory, and cannot write baseline history, outcomes, decisions, or authority.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from ... import config
from ..outcomes import outcome_eligibility
from . import market_no_send_campaign_provider, market_observation_campaign
from .market_no_send_io import parse_json_object_bytes
from .outcome_price_recovery_error import OutcomePriceRecoveryError
from .outcome_price_recovery_request import OutcomePriceRecoveryRequest
from .outcome_price_recovery_response import CapturedCoinGeckoResponse


CONTRACT_VERSION = "decision_radar_outcome_price_recovery_v1"
LIVE_AUTH_ENV = "RSI_DECISION_RADAR_OUTCOME_PRICE_RECOVERY_LIVE"
GENERAL_COINGECKO_AUTH_ENV = "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE"
PUBLIC_API_BASE = "https://api.coingecko.com/api/v3"
PRO_API_BASE = "https://pro-api.coingecko.com/api/v3"
MARKET_CHART_RANGE_PATH = "/coins/{coin_id}/market_chart/range"
SOURCE_DOCUMENTATION_URL = (
    "https://docs.coingecko.com/reference/coins-id-market-chart-range"
)
READINESS_COMMAND = (
    "make radar-outcome-price-recovery-readiness PYTHON=.venv/bin/python"
)
COLLECT_COMMAND = (
    "CONFIRM=1 make radar-outcome-price-recovery-collect PYTHON=.venv/bin/python"
)
CAPTURE_COMMAND = (
    "CONFIRM=1 make radar-outcome-price-recovery-capture PYTHON=.venv/bin/python"
)
MAX_RECOVERY_REQUESTS = 20
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_PRICE_POINTS = 10_000
DEFAULT_TIMEOUT_SECONDS = 10.0
_COIN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_ALLOWED_RESPONSE_KEYS = frozenset({"prices", "market_caps", "total_volumes"})
_RECOVERABLE_STATUSES = frozenset({
    "first_post_due_price_outside_allowed_window",
    "no_post_due_price_retained",
    "post_due_prices_already_allocated_to_other_horizons",
})


ReportBuilder = Callable[..., Mapping[str, Any]]
ProviderStateAssessor = Callable[..., Mapping[str, Any]]
FetchExact = Callable[[OutcomePriceRecoveryRequest, float], CapturedCoinGeckoResponse]
Clock = Callable[[], datetime]


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


def recovery_request_values(
    request: OutcomePriceRecoveryRequest,
) -> dict[str, Any]:
    """Return the closed, credential-free projection of one request plan."""

    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_outcome_price_recovery_request",
        "request_id": request.request_id,
        "outcome_identity_key": request.outcome_identity_key,
        "source_artifact_namespace": request.source_artifact_namespace,
        "candidate_id": request.candidate_id,
        "core_opportunity_id": request.core_opportunity_id,
        "symbol": request.symbol,
        "coin_id": request.coin_id,
        "observed_at": request.observed_at,
        "primary_horizon": request.primary_horizon,
        "due_at": request.due_at,
        "allowed_latest_price_at": request.allowed_latest_price_at,
        "allowed_lag_seconds": request.allowed_lag_seconds,
        "provider": "coingecko",
        "method": "GET",
        "endpoint_path": request.endpoint_path,
        "query": dict(request.query),
        "interval_parameter_omitted": True,
        "granularity_policy": "provider_auto_historical_one_day_expected_hourly",
        "source_documentation_url": SOURCE_DOCUMENTATION_URL,
        "maximum_provider_requests": 1,
        "retry_count": 0,
        "research_only": True,
        "baseline_eligible": False,
        "protocol_v2_evidence_eligible": False,
    }


def build_recovery_requests(
    outcomes: Mapping[str, Any],
) -> tuple[OutcomePriceRecoveryRequest, ...]:
    """Build deterministic one-request plans from canonical gap diagnostics."""

    details = outcomes.get("due_missing_price_details")
    if not isinstance(details, (list, tuple)):
        raise OutcomePriceRecoveryError("due_missing_price_details_missing")
    if len(details) > MAX_RECOVERY_REQUESTS:
        raise OutcomePriceRecoveryError("recovery_request_bound_exceeded")
    requests: list[OutcomePriceRecoveryRequest] = []
    identities: set[str] = set()
    for raw in details:
        if not isinstance(raw, Mapping):
            raise OutcomePriceRecoveryError("due_missing_price_detail_invalid")
        if raw.get("ledger_refresh_can_resolve_from_retained_history") is True:
            continue
        request = _request_from_gap(raw)
        if request.outcome_identity_key in identities:
            raise OutcomePriceRecoveryError("recovery_outcome_identity_duplicate")
        identities.add(request.outcome_identity_key)
        requests.append(request)
    return tuple(sorted(requests, key=lambda row: row.request_id))


def build_outcome_price_recovery_readiness(
    *,
    artifact_base_dir: str | Path,
    environ: Mapping[str, str] | None = None,
    now: datetime | None = None,
    fixture_dir: str | Path | None | object = ...,
    report_builder: ReportBuilder = (
        market_observation_campaign.build_outcome_recovery_projection
    ),
    provider_state_assessor: ProviderStateAssessor = (
        market_no_send_campaign_provider.assess_shared_provider_state
    ),
) -> dict[str, Any]:
    """Inspect exact local gaps and authorization without calls or writes."""

    checked = _utc(now or datetime.now(timezone.utc))
    env = os.environ if environ is None else environ
    base = Path(artifact_base_dir).expanduser().resolve()
    selected_fixture = config.FIXTURE_DIR if fixture_dir is ... else fixture_dir
    general_authorized = _enabled(env.get(GENERAL_COINGECKO_AUTH_ENV))
    recovery_authorized = _enabled(env.get(LIVE_AUTH_ENV))
    reasons: list[str] = []
    try:
        report = dict(report_builder(base, evaluated_at=checked))
        outcomes = _mapping(report.get("outcomes"))
        requests = build_recovery_requests(outcomes)
    except (OutcomePriceRecoveryError, OSError, RuntimeError, TypeError, ValueError):
        report, outcomes, requests = {}, {}, ()
        reasons.append("campaign_outcome_gap_contract_invalid")
    details = outcomes.get("due_missing_price_details")
    gap_rows = (
        tuple(row for row in details if isinstance(row, Mapping))
        if isinstance(details, (list, tuple))
        else ()
    )
    ledger_refresh_count = sum(
        row.get("ledger_refresh_can_resolve_from_retained_history") is True
        for row in gap_rows
    )
    if not gap_rows and not reasons:
        reasons.append("no_due_missing_price_outcomes")
    if ledger_refresh_count:
        reasons.append("campaign_outcome_ledger_refresh_required")
    if gap_rows and not requests and not ledger_refresh_count:
        reasons.append("no_recoverable_historical_price_windows")
    if selected_fixture is not None:
        reasons.append("fixture_mode_must_be_disabled")
    if not general_authorized:
        reasons.append("general_coingecko_authorization_absent")
    if not recovery_authorized:
        reasons.append("outcome_price_recovery_authorization_absent")
    try:
        provider_state = dict(
            provider_state_assessor(base, checked_at=checked)
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        provider_state = {"allowed": False, "reason": "provider_state_unavailable"}
    if provider_state.get("allowed") is not True:
        reasons.append(_safe_code(provider_state.get("reason") or "provider_backoff_active"))
    reasons = list(dict.fromkeys(reasons))
    ready = bool(requests) and not reasons
    public_pointer = _public_pointer(report.get("pointer"))
    plan_payload = {
        "history_sha256": _mapping(outcomes.get("price_history_snapshot")).get("sha256"),
        "pointer": public_pointer,
        "requests": [recovery_request_values(row) for row in requests],
    }
    plan_digest = _digest(plan_payload)
    only_recovery_auth_missing = reasons == [
        "outcome_price_recovery_authorization_absent"
    ]
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_outcome_price_recovery_readiness",
        "status": "ready" if ready else "no_work" if reasons == ["no_due_missing_price_outcomes"] else "blocked",
        "ready": ready,
        "checked_at": _iso(checked),
        "campaign_status": report.get("campaign_status"),
        "campaign_report_generated_at": report.get("generated_at"),
        "campaign_projection_schema_id": report.get("schema_id"),
        "campaign_projection_scope": report.get("projection_scope"),
        "full_campaign_report_rebuilt": report.get("full_campaign_report_rebuilt"),
        "campaign_pointer": public_pointer,
        "due_missing_price_count": len(gap_rows),
        "ledger_refreshable_count": ledger_refresh_count,
        "historical_recovery_request_count": len(requests),
        "historical_recovery_requests": [
            recovery_request_values(row) for row in requests
        ],
        "absolute_provider_request_bound": MAX_RECOVERY_REQUESTS,
        "plan_digest": plan_digest,
        "price_history_snapshot": _public_history_snapshot(
            outcomes.get("price_history_snapshot")
        ),
        "provider": "coingecko",
        "provider_endpoint": "coins_id_market_chart_range",
        "provider_call_planned": ready,
        "provider_call_attempted": False,
        "provider_requests_made": 0,
        "provider_retries_per_request": 0,
        "general_authorization_env": GENERAL_COINGECKO_AUTH_ENV,
        "general_provider_authorized": general_authorized,
        "recovery_authorization_env": LIVE_AUTH_ENV,
        "recovery_provider_authorized": recovery_authorized,
        "authorization_mutated": False,
        "fixture_mode": selected_fixture is not None,
        "shared_provider_state": _public_provider_state(provider_state),
        "exact_response_input_contract_implemented": True,
        "diagnostic_collection_implemented": True,
        "immutable_capture_implemented": True,
        "baseline_history_mutated": False,
        "campaign_outcomes_mutated": False,
        "calibration_eligible": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "reasons": reasons,
        "next_safe_command": CAPTURE_COMMAND if ready else READINESS_COMMAND,
        "operator_action_required": (
            f"set_{LIVE_AUTH_ENV}=1_in_local_gitignored_dotenv_then_rerun_readiness"
            if only_recovery_auth_missing
            else "resolve_readiness_reasons_then_rerun_readiness"
            if reasons
            else "none"
        ),
        **_safety(writes_performed=False),
    }


def normalize_captured_recovery_response(
    request: OutcomePriceRecoveryRequest,
    response: CapturedCoinGeckoResponse,
) -> dict[str, Any]:
    """Rederive one historical recovery result from exact response bytes."""

    if response.request_id != request.request_id:
        raise OutcomePriceRecoveryError("response_request_identity_mismatch")
    if response.provider_base_url not in {PUBLIC_API_BASE, PRO_API_BASE}:
        raise OutcomePriceRecoveryError("response_provider_host_invalid")
    if response.http_status != 200:
        raise OutcomePriceRecoveryError(
            "response_http_status_invalid",
            http_status=response.http_status,
        )
    requested = _utc(response.requested_at)
    received = _utc(response.received_at)
    if received < requested:
        raise OutcomePriceRecoveryError("response_clock_order_invalid")
    raw = bytes(response.body)
    if not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise OutcomePriceRecoveryError("response_size_invalid")
    try:
        payload = parse_json_object_bytes(raw)
    except Exception as exc:
        raise OutcomePriceRecoveryError("response_json_invalid") from exc
    if set(payload) != _ALLOWED_RESPONSE_KEYS:
        raise OutcomePriceRecoveryError("response_schema_invalid")
    if not all(isinstance(payload.get(key), list) for key in _ALLOWED_RESPONSE_KEYS):
        raise OutcomePriceRecoveryError("response_schema_invalid")
    prices = _validated_prices(request, payload["prices"])
    due = _aware(request.due_at, "request_due_at_invalid")
    latest = _aware(
        request.allowed_latest_price_at,
        "request_allowed_latest_price_at_invalid",
    )
    selected = next(
        (row for row in prices if due <= row[0] <= latest),
        None,
    )
    response_sha256 = hashlib.sha256(raw).hexdigest()
    recovery_id = (
        "outcome-price-recovery-v1:"
        + _digest({
            "request_id": request.request_id,
            "response_sha256": response_sha256,
            "selected": (
                [selected[0].isoformat(), selected[1]] if selected else None
            ),
        })
    )
    observation_id = (
        "mhrecovery-" + recovery_id.rsplit(":", 1)[-1][:24]
        if selected is not None
        else None
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_outcome_price_recovery_result",
        "status": "complete" if selected is not None else "no_results",
        "recovery_id": recovery_id,
        "request": recovery_request_values(request),
        "provider": "coingecko",
        "provider_base_url": response.provider_base_url,
        "endpoint_path": request.endpoint_path,
        "request_started_at": _iso(requested),
        "response_received_at": _iso(received),
        "http_status": 200,
        "raw_response_sha256": response_sha256,
        "raw_response_size_bytes": len(raw),
        "raw_response_retained_in_memory": True,
        "raw_response_persisted": False,
        "price_point_count": len(prices),
        "qualifying_price_found": selected is not None,
        "price_observation_id": observation_id,
        "price_observed_at": _iso(selected[0]) if selected else None,
        "price_usd": selected[1] if selected else None,
        "price_unit": "USD_per_asset",
        "price_source": "coingecko_market_chart_range_historical_recovery",
        "acquisition_lag_seconds": (
            max(0.0, (received - selected[0]).total_seconds())
            if selected is not None
            else None
        ),
        "historical_provider_series": True,
        "point_in_time_collection_at_market_time": False,
        "outcome_completion_input_eligible": selected is not None,
        "baseline_eligible": False,
        "baseline_history_written": False,
        "campaign_observation_counted": False,
        "decision_candidate_created": False,
        "calibration_eligible": False,
        "calibration_ineligible_reason": "historical_recovery_not_protocol_v2_annex_bound",
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        **_safety(writes_performed=False),
    }


def collect_outcome_price_recovery(
    *,
    artifact_base_dir: str | Path,
    confirm: bool,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    fixture_dir: str | Path | None | object = ...,
    report_builder: ReportBuilder = (
        market_observation_campaign.build_outcome_recovery_projection
    ),
    provider_state_assessor: ProviderStateAssessor = (
        market_no_send_campaign_provider.assess_shared_provider_state
    ),
    fetch_exact: FetchExact | None = None,
    clock: Clock = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Collect exact responses diagnostically without retries or persistence."""

    collected = collect_outcome_price_recovery_capture_inputs(
        artifact_base_dir=artifact_base_dir,
        confirm=confirm,
        environ=environ,
        timeout_seconds=timeout_seconds,
        fixture_dir=fixture_dir,
        report_builder=report_builder,
        provider_state_assessor=provider_state_assessor,
        fetch_exact=fetch_exact,
        clock=clock,
    )
    results = collected["results"]
    request_count = collected["provider_request_count"]
    readiness = collected["readiness"]
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_outcome_price_recovery_collection",
        "status": "complete",
        "plan_digest": readiness["plan_digest"],
        "provider": "coingecko",
        "provider_request_count": request_count,
        "provider_retry_count": 0,
        "results": [dict(row) for row in results],
        "qualifying_price_count": sum(
            row.get("qualifying_price_found") is True for row in results
        ),
        "artifact_persisted": False,
        "immutable_capture_implemented": False,
        "baseline_history_mutated": False,
        "campaign_outcomes_mutated": False,
        "authorization_mutated": False,
        **_safety(writes_performed=False),
    }


def collect_outcome_price_recovery_capture_inputs(
    *,
    artifact_base_dir: str | Path,
    confirm: bool,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    fixture_dir: str | Path | None | object = ...,
    report_builder: ReportBuilder = (
        market_observation_campaign.build_outcome_recovery_projection
    ),
    provider_state_assessor: ProviderStateAssessor = (
        market_no_send_campaign_provider.assess_shared_provider_state
    ),
    fetch_exact: FetchExact | None = None,
    clock: Clock = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Return exact in-memory capture inputs after post-response revalidation."""

    if not confirm:
        raise OutcomePriceRecoveryError("explicit_confirmation_required")
    checked = _utc(clock())
    readiness = build_outcome_price_recovery_readiness(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=checked,
        fixture_dir=fixture_dir,
        report_builder=report_builder,
        provider_state_assessor=provider_state_assessor,
    )
    if readiness.get("ready") is not True:
        raise OutcomePriceRecoveryError("recovery_readiness_blocked")
    requests = tuple(
        recovery_request_from_values(row)
        for row in readiness["historical_recovery_requests"]
    )
    fetch = fetch_exact or _fetch_exact_coingecko_response
    results: list[dict[str, Any]] = []
    responses: list[CapturedCoinGeckoResponse] = []
    request_count = 0
    for request in requests:
        try:
            request_count += 1
            captured = fetch(request, _positive_timeout(timeout_seconds))
            responses.append(captured)
            results.append(normalize_captured_recovery_response(request, captured))
        except OutcomePriceRecoveryError as exc:
            raise OutcomePriceRecoveryError(
                exc.reason_code,
                http_status=exc.http_status,
                request_count=request_count,
            ) from exc
        except Exception as exc:
            raise OutcomePriceRecoveryError(
                _safe_code(type(exc).__name__),
                request_count=request_count,
            ) from exc
    post = build_outcome_price_recovery_readiness(
        artifact_base_dir=artifact_base_dir,
        environ=environ,
        now=_utc(clock()),
        fixture_dir=fixture_dir,
        report_builder=report_builder,
        provider_state_assessor=provider_state_assessor,
    )
    if post.get("plan_digest") != readiness.get("plan_digest"):
        raise OutcomePriceRecoveryError(
            "recovery_plan_changed_after_provider_response",
            request_count=request_count,
        )
    return {
        "readiness": readiness,
        "requests": requests,
        "responses": tuple(responses),
        "results": tuple(results),
        "provider_request_count": request_count,
    }


def _request_from_gap(row: Mapping[str, Any]) -> OutcomePriceRecoveryRequest:
    if any((
        row.get("resolution_status") not in _RECOVERABLE_STATUSES,
        row.get("historical_point_in_time_evidence_required") is not True,
        row.get("qualifying_price_observation_count") != 0,
        row.get("interpolation_permitted") is not False,
        row.get("automatic_threshold_change_permitted") is not False,
        row.get("research_only") is not True,
    )):
        raise OutcomePriceRecoveryError("due_missing_price_detail_contract_invalid")
    identity = _required_text(row, "outcome_identity_key")
    namespace = _required_text(row, "source_artifact_namespace")
    candidate_id = _required_text(row, "candidate_id")
    core_id = _required_text(row, "core_opportunity_id")
    symbol = _required_text(row, "symbol")
    coin_id = _required_text(row, "coin_id")
    if not _COIN_ID_RE.fullmatch(coin_id):
        raise OutcomePriceRecoveryError("recovery_coin_id_invalid")
    primary = _required_text(row, "primary_horizon")
    if primary not in outcome_eligibility.OUTCOME_HORIZON_SECONDS:
        raise OutcomePriceRecoveryError("recovery_primary_horizon_invalid")
    observed = _aware(row.get("observed_at"), "recovery_observed_at_invalid")
    due = _aware(row.get("due_at"), "recovery_due_at_invalid")
    latest = _aware(
        row.get("allowed_latest_price_at"),
        "recovery_allowed_latest_price_at_invalid",
    )
    expected_due = observed.timestamp() + outcome_eligibility.OUTCOME_HORIZON_SECONDS[primary]
    if abs(due.timestamp() - expected_due) > 1e-6:
        raise OutcomePriceRecoveryError("recovery_due_at_mismatch")
    expected_lag = min(
        outcome_eligibility.OUTCOME_HORIZON_SECONDS[primary],
        24 * 60 * 60,
    )
    if (
        row.get("allowed_lag_seconds") != expected_lag
        or abs((latest - due).total_seconds() - expected_lag) > 1e-6
    ):
        raise OutcomePriceRecoveryError("recovery_allowed_window_mismatch")
    endpoint = MARKET_CHART_RANGE_PATH.format(coin_id=coin_id)
    query = (
        ("vs_currency", "usd"),
        ("from", str(math.floor(due.timestamp()))),
        ("to", str(math.ceil(latest.timestamp()))),
        ("precision", "full"),
    )
    body = {
        "outcome_identity_key": identity,
        "source_artifact_namespace": namespace,
        "candidate_id": candidate_id,
        "core_opportunity_id": core_id,
        "symbol": symbol,
        "coin_id": coin_id,
        "observed_at": _iso(observed),
        "primary_horizon": primary,
        "due_at": _iso(due),
        "allowed_latest_price_at": _iso(latest),
        "allowed_lag_seconds": expected_lag,
        "endpoint_path": endpoint,
        "query": dict(query),
    }
    return OutcomePriceRecoveryRequest(
        request_id="outcome-price-request-v1:" + _digest(body),
        outcome_identity_key=identity,
        source_artifact_namespace=namespace,
        candidate_id=candidate_id,
        core_opportunity_id=core_id,
        symbol=symbol,
        coin_id=coin_id,
        observed_at=_iso(observed),
        primary_horizon=primary,
        due_at=_iso(due),
        allowed_latest_price_at=_iso(latest),
        allowed_lag_seconds=expected_lag,
        endpoint_path=endpoint,
        query=query,
    )


def recovery_request_from_values(
    row: Mapping[str, Any],
) -> OutcomePriceRecoveryRequest:
    query = row.get("query")
    if not isinstance(query, Mapping):
        raise OutcomePriceRecoveryError("recovery_request_projection_invalid")
    try:
        projected = OutcomePriceRecoveryRequest(
            request_id=_required_text(row, "request_id"),
            outcome_identity_key=_required_text(row, "outcome_identity_key"),
            source_artifact_namespace=_required_text(row, "source_artifact_namespace"),
            candidate_id=_required_text(row, "candidate_id"),
            core_opportunity_id=_required_text(row, "core_opportunity_id"),
            symbol=_required_text(row, "symbol"),
            coin_id=_required_text(row, "coin_id"),
            observed_at=_required_text(row, "observed_at"),
            primary_horizon=_required_text(row, "primary_horizon"),
            due_at=_required_text(row, "due_at"),
            allowed_latest_price_at=_required_text(
                row,
                "allowed_latest_price_at",
            ),
            allowed_lag_seconds=int(row.get("allowed_lag_seconds")),
            endpoint_path=_required_text(row, "endpoint_path"),
            query=tuple((str(key), str(value)) for key, value in query.items()),
        )
    except (TypeError, ValueError) as exc:
        raise OutcomePriceRecoveryError(
            "recovery_request_projection_invalid"
        ) from exc
    if recovery_request_values(projected) != dict(row):
        raise OutcomePriceRecoveryError("recovery_request_projection_invalid")
    return projected


def _validated_prices(
    request: OutcomePriceRecoveryRequest,
    value: object,
) -> tuple[tuple[datetime, float], ...]:
    if not isinstance(value, list) or len(value) > MAX_PRICE_POINTS:
        raise OutcomePriceRecoveryError("response_prices_invalid")
    query = dict(request.query)
    lower_ms = int(query["from"]) * 1000
    upper_ms = int(query["to"]) * 1000
    prices: list[tuple[datetime, float]] = []
    prior_timestamp: int | None = None
    for point in value:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or isinstance(point[0], bool)
            or type(point[0]) is not int
            or isinstance(point[1], bool)
            or type(point[1]) not in (int, float)
        ):
            raise OutcomePriceRecoveryError("response_price_point_invalid")
        timestamp_ms = point[0]
        price = float(point[1])
        if (
            timestamp_ms < lower_ms
            or timestamp_ms > upper_ms
            or prior_timestamp is not None
            and timestamp_ms <= prior_timestamp
            or not math.isfinite(price)
            or price <= 0
        ):
            raise OutcomePriceRecoveryError("response_price_point_invalid")
        prior_timestamp = timestamp_ms
        prices.append((
            datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
            price,
        ))
    return tuple(prices)


def _fetch_exact_coingecko_response(
    request: OutcomePriceRecoveryRequest,
    timeout_seconds: float,
) -> CapturedCoinGeckoResponse:
    base_url, provider_headers = _coingecko_base_and_headers()
    url = f"{base_url}{request.endpoint_path}?{urlencode(request.query)}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "crypto-rsi-scanner-decision-radar-research/1",
        **provider_headers,
    }
    opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
    requested = datetime.now(timezone.utc)
    try:
        with opener.open(
            Request(url, headers=headers, method="GET"),
            timeout=_positive_timeout(timeout_seconds),
        ) as response:
            status = int(response.getcode())
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                raise OutcomePriceRecoveryError("response_size_invalid")
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except OutcomePriceRecoveryError:
        raise
    except HTTPError as exc:
        raise OutcomePriceRecoveryError(
            "provider_http_error",
            http_status=int(exc.code),
        ) from exc
    except (URLError, OSError, TimeoutError, ValueError) as exc:
        raise OutcomePriceRecoveryError(_safe_code(type(exc).__name__)) from exc
    received = datetime.now(timezone.utc)
    if len(body) > MAX_RESPONSE_BYTES:
        raise OutcomePriceRecoveryError("response_size_invalid")
    return CapturedCoinGeckoResponse(
        request_id=request.request_id,
        provider_base_url=base_url,
        http_status=status,
        requested_at=requested,
        received_at=received,
        body=body,
    )


def _coingecko_base_and_headers() -> tuple[str, dict[str, str]]:
    key = config.COINGECKO_API_KEY
    key_type = str(config.COINGECKO_KEY_TYPE or "demo").strip().casefold()
    if key and key_type == "pro":
        return PRO_API_BASE, {"x-cg-pro-api-key": key}
    if key:
        return PUBLIC_API_BASE, {"x-cg-demo-api-key": key}
    return PUBLIC_API_BASE, {}


def _public_pointer(value: object) -> dict[str, Any]:
    pointer = _mapping(value)
    return {
        key: pointer.get(key)
        for key in (
            "status",
            "artifact_namespace",
            "run_id",
            "revision",
            "operator_state_sha256",
            "exact_operator_binding",
        )
        if pointer.get(key) is not None
    }


def _public_history_snapshot(value: object) -> dict[str, Any]:
    snapshot = _mapping(value)
    return {
        key: snapshot.get(key)
        for key in ("status", "artifact", "sha256", "row_count", "binding_source")
    }


def _public_provider_state(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "allowed": value.get("allowed") is True,
        "reason": _safe_code(value.get("reason")) if value.get("reason") else None,
        "disabled_until": value.get("disabled_until"),
        "last_failure_at": value.get("last_failure_at"),
    }


def _safety(*, writes_performed: bool) -> dict[str, Any]:
    return {
        "research_only": True,
        "no_send": True,
        "no_live_trading": True,
        "orders_available": False,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "telegram_sends": 0,
        "writes_performed": writes_performed,
        "credential_value_exposed": False,
    }


def _positive_timeout(value: object) -> float:
    if isinstance(value, bool):
        raise OutcomePriceRecoveryError("timeout_invalid")
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise OutcomePriceRecoveryError("timeout_invalid") from exc
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 60:
        raise OutcomePriceRecoveryError("timeout_invalid")
    return timeout


def _required_text(row: Mapping[str, Any], field: str) -> str:
    value = row.get(field)
    if type(value) is not str or not value.strip():
        raise OutcomePriceRecoveryError(f"{field}_invalid")
    return value.strip()


def _aware(value: object, reason: str) -> datetime:
    parsed = outcome_eligibility.parse_aware_time(value)
    if parsed is None:
        raise OutcomePriceRecoveryError(reason)
    return parsed


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OutcomePriceRecoveryError("clock_must_include_timezone")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _enabled(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_code(value: object) -> str:
    text = str(value or "unknown").strip().casefold()
    cleaned = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in text
    )
    return cleaned[:96] or "unknown"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("readiness", "collect"))
    parser.add_argument(
        "--artifact-base",
        default=str(config.EVENT_ALPHA_ARTIFACT_BASE_DIR),
    )
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--confirm", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "readiness":
            result = build_outcome_price_recovery_readiness(
                artifact_base_dir=args.artifact_base,
            )
        else:
            result = collect_outcome_price_recovery(
                artifact_base_dir=args.artifact_base,
                confirm=args.confirm,
                timeout_seconds=args.timeout_seconds,
            )
    except OutcomePriceRecoveryError as exc:
        print(json.dumps({
            "status": "blocked",
            "reason": exc.reason_code,
            "http_status": exc.http_status,
            "provider_request_count": exc.request_count,
            **_safety(writes_performed=False),
        }, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.command == "readiness":
        return 0
    return 0 if result.get("status") == "complete" else 2


if __name__ == "__main__":
    sys.exit(main())


__all__ = (
    "CapturedCoinGeckoResponse",
    "CAPTURE_COMMAND",
    "OutcomePriceRecoveryError",
    "OutcomePriceRecoveryRequest",
    "build_outcome_price_recovery_readiness",
    "build_recovery_requests",
    "collect_outcome_price_recovery",
    "collect_outcome_price_recovery_capture_inputs",
    "normalize_captured_recovery_response",
    "recovery_request_from_values",
    "recovery_request_values",
)
