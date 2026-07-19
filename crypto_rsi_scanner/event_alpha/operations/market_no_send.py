"""Guarded no-send radar generation; publication requires an exact clean doctor.
The bounded path cannot send, trade, paper/RSI-write, or create ``TRIGGERED_FADE``.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from ... import config, universe
from ..artifacts import context as artifact_context
from ..artifacts import run_ledger
from ..dashboard.readiness import (
    DashboardReadinessError,
)
from ..radar import market_anomaly_scanner
from ..radar import market_enrichment
from ..radar.integrated import api as integrated_radar
from .market_no_send_models import (
    MarketNoSendError,
    MarketNoSendGenerationResult,
    MarketNoSendReadiness,
    SAFETY_COUNTERS as _SAFETY_COUNTERS,
)
from .market_no_send_io import (
    ensure_safe_namespace_dir as _ensure_safe_namespace_dir,
    read_json_object as _read_json_object,
    read_regular_bytes as _read_regular_bytes,
    safe_existing_namespace_dir as _safe_existing_namespace_dir,
    write_json_atomic as _write_json_atomic,
)
from . import (
    market_no_send_audit,
    market_no_send_attempt,
    market_no_send_authority,
    market_no_send_campaign_guard,
    market_no_send_campaign_provider,
    market_no_send_calendar,
    market_no_send_features,
    market_no_send_generation,
    market_no_send_history_cache,
    market_no_send_provider,
    market_no_send_publication,
    market_observation_campaign_cadence,
    market_observation_outcomes,
    market_provenance,
)


CONTRACT_VERSION = 2
DEFAULT_PROFILE = "no_key_live"
DEFAULT_NAMESPACE = "radar_market_no_send"
DEFAULT_SMOKE_NAMESPACE = "radar_market_no_send_smoke"
DEFAULT_TOP_N = 30
MAX_TOP_N = 50
REQUEST_CACHE_FILENAME = "event_market_no_send_market_rows.json"
REQUEST_LEDGER_FILENAME = "event_market_no_send_request_ledger.json"
HISTORY_FILENAME = "event_market_history.jsonl"
RUN_MANIFEST_FILENAME = "event_market_no_send_generation.json"
PILOT_AUDIT_JSON_FILENAME = "event_market_no_send_pilot_audit.json"
PILOT_AUDIT_MD_FILENAME = "event_market_no_send_pilot_audit.md"
LIVE_AUTH_ENV = "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE"
_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
MarketRowsProvider = Callable[[int], Sequence[Mapping[str, Any]]]
_smoke_rows = market_no_send_features.smoke_rows


def build_market_no_send_readiness(
    *,
    artifact_base_dir: str | Path | None = None,
    artifact_namespace: str = DEFAULT_NAMESPACE,
    top_n: int = DEFAULT_TOP_N,
    fetch_limit: int | None = None,
    environ: Mapping[str, str] | None = None,
    fixture_dir: str | Path | None | object = ...,  # explicit None means live client mode
    now: datetime | str | None = None,
    _campaign_reservation_id: str | None = None,
) -> MarketNoSendReadiness:
    """Return a no-write/no-network readiness result for the live run."""

    namespace = _validated_namespace(artifact_namespace)
    bounded_top_n = _bounded_top_n(top_n)
    bounded_fetch = _bounded_fetch_limit(fetch_limit, bounded_top_n)
    env = os.environ if environ is None else environ
    authorized = _truthy(env.get(LIVE_AUTH_ENV))
    selected_fixture_dir = config.FIXTURE_DIR if fixture_dir is ... else fixture_dir
    fixture_mode = selected_fixture_dir is not None
    reasons: list[str] = []
    if not authorized:
        reasons.append(f"{LIVE_AUTH_ENV}=1 is required for the live CoinGecko call")
    if fixture_mode:
        reasons.append("FIXTURE_DIR must be unset before a generation may claim live data")
    selected_base = Path(artifact_base_dir or config.EVENT_ALPHA_ARTIFACT_BASE_DIR)
    namespace_blocker = market_no_send_publication.namespace_mutation_blocker(
        selected_base,
        namespace,
    )
    if namespace_blocker:
        reasons.append(namespace_blocker)
    evaluated_at = _as_utc(_parse_time(now) or datetime.now(timezone.utc))
    calendar_snapshot = market_no_send_calendar.load_market_no_send_calendar_snapshot(
        environ=env,
        now=evaluated_at,
        data_mode="live",
        run_mode="operational",
    )
    history_config, history_config_error = _market_history_config()
    if history_config_error: reasons.append(history_config_error)
    baseline = market_no_send_history_cache.cache_readiness(
        selected_base,
        history_filename=HISTORY_FILENAME,
        now=evaluated_at,
        config=history_config,
    )
    if baseline.get("cache_status") == "invalid": reasons.append(str(baseline["cache_error"]))
    if baseline.get("cadence_status") == "waiting":
        reasons.append(
            "observation cadence window has not elapsed; next eligible at "
            f"{baseline.get('next_eligible_observation_at')}"
        )
    provider_state = market_no_send_campaign_provider.assess_shared_provider_state(
        selected_base,
        checked_at=evaluated_at,
    )
    if not provider_state["allowed"]:
        reasons.append(str(provider_state["reason"] or "shared provider backoff is active"))
    reservation_state = market_no_send_campaign_guard.assess_campaign_reservation(
        selected_base, checked_at=evaluated_at,
        owner_reservation_id=_campaign_reservation_id,
    )
    if not reservation_state["allowed"]:
        reasons.append(str(reservation_state["reason"]))
    effective_cadence = market_observation_campaign_cadence.synthesize_next_observation(
        baseline,
        reservation_state,
        provider_state,
        evaluated=evaluated_at,
    )
    readiness_baseline = {
        **baseline,
        "next_eligible_observation_at": effective_cadence[
            "next_eligible_observation_at"
        ],
        "cadence_status": effective_cadence["cadence_status"],
        "history_next_eligible_observation_at": effective_cadence[
            "history_next_eligible_observation_at"
        ],
        "provider_call_reservation_next_at": effective_cadence[
            "provider_call_reservation_next_at"
        ],
        "provider_backoff_disabled_until": effective_cadence[
            "provider_backoff_disabled_until"
        ],
        "cadence_eligible_now": effective_cadence["eligible_now"],
    }
    return MarketNoSendReadiness(
        status="ready" if not reasons else "blocked",
        provider="coingecko",
        live_provider_authorized=authorized,
        provider_call_attempted=False,
        fixture_mode=fixture_mode,
        no_send=True,
        research_only=True,
        top_n=bounded_top_n,
        fetch_limit=bounded_fetch,
        artifact_namespace=namespace,
        reasons=tuple(reasons),
        will_call_provider=not reasons,
        data_acquisition_mode="live_provider" if not reasons else "preflight_only",
        candidate_source_mode="live_no_send" if not reasons else "preflight_only",
        **readiness_baseline,
        spread_data_status="unavailable_from_coingecko_market_endpoint",
        calendar_snapshot_status=calendar_snapshot.status,
        calendar_snapshot_configured=calendar_snapshot.configured,
        calendar_snapshot_retained_rows=calendar_snapshot.retained_row_count,
        calendar_snapshot_source_mode=calendar_snapshot.source_mode,
        measurement_program=market_provenance.DECISION_RADAR_MEASUREMENT_PROGRAM,
        decision_radar_campaign_eligible=not reasons,
        burn_in_eligible=False,
        pointer_eligible=False,
        pointer_eligibility_status=(
            "pending_complete_strict_doctor" if not reasons else "blocked_preflight"
        ),
        artifact_paths=(
            market_no_send_attempt.LATEST_ATTEMPT_FILENAME, market_no_send_attempt.ATTEMPT_LEDGER_FILENAME,
            REQUEST_CACHE_FILENAME,
            REQUEST_LEDGER_FILENAME,
            f"{market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE}/{HISTORY_FILENAME}",
            f"{market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE}/"
            f"{market_no_send_provider.PROVIDER_HEALTH_FILENAME}",
            f"{market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE}/"
            f"{market_no_send_campaign_provider.LATEST_SHARED_FAILURE_FILENAME}",
            HISTORY_FILENAME,
            market_no_send_provider.PROVIDER_HEALTH_FILENAME,
            RUN_MANIFEST_FILENAME,
            market_no_send_calendar.CALENDAR_SOURCE_COPY_FILENAME,
            PILOT_AUDIT_JSON_FILENAME,
            PILOT_AUDIT_MD_FILENAME,
        ),
        next_safe_command=(
            "make radar-daily-ops-readiness"
            if (
                effective_cadence["cadence_status"] != "eligible"
                or not provider_state["allowed"]
                or not reservation_state["allowed"]
            )
            else market_no_send_publication.readiness_next_command(
                authorization_env=LIVE_AUTH_ENV,
                authorized=authorized,
                fixture_mode=fixture_mode,
                namespace_blocker=namespace_blocker,
            )
        ),
    )


def run_market_no_send_generation(
    *,
    artifact_base_dir: str | Path,
    artifact_namespace: str = DEFAULT_NAMESPACE,
    profile: str = DEFAULT_PROFILE,
    run_mode: str = "operational",
    top_n: int = DEFAULT_TOP_N,
    fetch_limit: int | None = None,
    provider: MarketRowsProvider | None = None,
    observed_at: datetime | str | None = None,
    environ: Mapping[str, str] | None = None,
    fixture_dir: str | Path | None | object = ...,
    data_mode: str = "live",
    allow_non_live: bool = False,
) -> MarketNoSendGenerationResult:
    """Build locally after authorization; non-live results cannot be published."""

    namespace = _validated_namespace(artifact_namespace)
    bounded_top_n = _bounded_top_n(top_n)
    bounded_fetch = _bounded_fetch_limit(fetch_limit, bounded_top_n)
    mode = str(data_mode or "").strip().casefold()
    if mode not in {"live", "mock"}:
        raise MarketNoSendError("data_mode must be live or mock")
    policy_environ, policy_fixture_dir = (None, ...) if mode == "live" else (environ, fixture_dir)
    readiness = build_market_no_send_readiness(
        artifact_base_dir=artifact_base_dir,
        artifact_namespace=namespace,
        top_n=bounded_top_n,
        fetch_limit=bounded_fetch,
        environ=policy_environ,
        fixture_dir=policy_fixture_dir,
    )
    if mode != "live" and not allow_non_live:
        raise MarketNoSendError("non-live market generation is reserved for the no-network smoke")
    if mode == "live" and not readiness.ready:
        return market_no_send_campaign_guard.blocked_generation_result(
            readiness=readiness, profile=profile, artifact_namespace=namespace,
            data_mode=mode, observed_at=datetime.now(timezone.utc),
            failure_class="readiness_blocked",
        )
    canonical_base = Path(config.EVENT_ALPHA_ARTIFACT_BASE_DIR).expanduser().resolve()
    if mode == "live" and Path(artifact_base_dir).expanduser().resolve() != canonical_base:
        return market_no_send_campaign_guard.blocked_generation_result(
            readiness=readiness, profile=profile, artifact_namespace=namespace,
            data_mode=mode, observed_at=datetime.now(timezone.utc),
            failure_class="noncanonical_artifact_base",
        )
    market_no_send_provider.require_approved_live_adapter(
        data_mode=mode,
        injected=provider is not None,
    )

    observed = _as_utc(datetime.now(timezone.utc) if mode == "live" else (
        _parse_time(observed_at) or datetime.now(timezone.utc)))
    base = _validated_artifact_base(artifact_base_dir)
    reservation_context = (
        market_no_send_campaign_guard.acquire_campaign_reservation(
            base, artifact_namespace=namespace,
        ) if mode == "live" else nullcontext(None)
    )
    try:
        with reservation_context as reservation:
            attempted_at = datetime.now(timezone.utc)
            if mode == "live":
                observed = attempted_at
                readiness = build_market_no_send_readiness(
                    artifact_base_dir=base, artifact_namespace=namespace,
                    top_n=bounded_top_n, fetch_limit=bounded_fetch,
                    environ=None, fixture_dir=..., now=attempted_at,
                    _campaign_reservation_id=reservation.reservation_id,
                )
                if not readiness.ready:
                    return market_no_send_campaign_guard.blocked_generation_result(
                        readiness=readiness, profile=profile, artifact_namespace=namespace,
                        data_mode=mode, observed_at=observed,
                        failure_class="locked_readiness_blocked",
                    )
            market_no_send_publication.assert_namespace_not_current_authority(base, namespace)
            context = artifact_context.context_from_profile(
                profile, run_mode=run_mode, base_dir=base, artifact_namespace=namespace,
            )
            _require_exact_context(context, base=base, namespace=namespace)
            _ensure_safe_namespace_dir(context.namespace_dir)
            provider_name = "coingecko" if mode == "live" else "mock_coingecko"
            fetch = provider or _fetch_live_coingecko_rows
            provider_run_id = run_ledger.run_id_for(observed, context.profile)
            if reservation is not None:
                market_no_send_campaign_guard.mark_provider_call_reserved(
                    reservation, attempted_at=attempted_at,
                    minimum_spacing=timedelta(
                        seconds=readiness.minimum_observation_spacing_seconds
                    ),
                )
            raw_rows, request_telemetry, provider_failure = _fetch_generation_rows(
                context=context, fetch=fetch, fetch_limit=bounded_fetch,
                provider_name=provider_name, provider_run_id=provider_run_id,
                observed=observed, attempted_at=attempted_at, mode=mode,
                readiness=readiness, top_n=bounded_top_n,
                campaign_reservation=reservation,
            )
            if provider_failure is not None:
                return provider_failure
            return _build_market_generation_from_rows(
                context=context, observed=observed, raw_rows=raw_rows,
                provider_name=provider_name, data_mode=mode, readiness=readiness,
                top_n=bounded_top_n, fetch_limit=bounded_fetch,
                request_telemetry=request_telemetry, campaign_reservation=reservation,
                calendar_environ=_generation_calendar_environ(mode, environ),
            )
    except market_no_send_campaign_guard.CampaignReservationBusy:
        return market_no_send_campaign_guard.blocked_generation_result(
            readiness=readiness, profile=profile, artifact_namespace=namespace,
            data_mode=mode, observed_at=observed,
            failure_class="campaign_reservation_busy",
        )


def _generation_calendar_environ(
    mode: str,
    environ: Mapping[str, str] | None,
) -> Mapping[str, str] | None:
    """Allow a live caller to inject only the closed local-calendar path."""

    if mode != "live" or environ is None:
        return environ
    path = str(
        environ.get(market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV) or ""
    ).strip()
    return (
        {market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV: path}
        if path
        else {}
    )


def _fetch_generation_rows(
    *,
    context: Any,
    fetch: MarketRowsProvider,
    fetch_limit: int,
    provider_name: str,
    provider_run_id: str,
    observed: datetime,
    attempted_at: datetime,
    mode: str,
    readiness: MarketNoSendReadiness,
    top_n: int,
    campaign_reservation: market_no_send_campaign_guard.CampaignReservation | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], MarketNoSendGenerationResult | None]:
    request_telemetry: dict[str, Any] = {}
    try:
        if mode == "live":
            result = market_no_send_provider.fetch_approved_live_rows(
                context.namespace_dir,
                fetch=fetch,
                fetch_limit=fetch_limit,
                provider=provider_name,
                run_id=provider_run_id,
                observed_at=observed,
                attempted_at=attempted_at,
            )
            fetched = result.rows
            request_telemetry = dict(result.telemetry)
            if campaign_reservation is None:
                raise MarketNoSendError("shared campaign provider state is missing")
            market_no_send_campaign_provider.record_shared_provider_success(
                campaign_reservation, provider=provider_name, run_id=provider_run_id,
                attempted_at=attempted_at, request_telemetry=request_telemetry,
            )
        else:
            fetched = fetch(fetch_limit)
        raw_rows = [dict(row) for row in fetched if isinstance(row, Mapping)]
        if mode != "live":
            request_telemetry = {
                "endpoint_path": "/coins/markets",
                "request_started_at": observed.isoformat(),
                "request_ended_at": observed.isoformat(),
                "duration_ms": 0,
                "http_status": None,
                "result_count": len(raw_rows),
                "retry_count": 0,
                "error_class": None,
                "cache_behavior": "mocked_fixture",
            }
        return raw_rows, request_telemetry, None
    except Exception as exc:  # noqa: BLE001 - external provider must fail soft
        telemetry = dict(getattr(exc, "request_telemetry", {}) or {})
        error_class = getattr(exc, "error_class", None) or type(exc).__name__
        if mode == "live" and campaign_reservation is not None:
            market_no_send_campaign_provider.record_shared_provider_failure(
                campaign_reservation, artifact_namespace=context.artifact_namespace,
                provider=provider_name, run_id=provider_run_id,
                attempted_at=attempted_at, error=exc, request_telemetry=telemetry,
            )
        ledger_path = _write_failed_market_request_ledger(
            context=context,
            observed=observed,
            provider_name=provider_name,
            readiness=readiness,
            run_id=provider_run_id,
            telemetry=telemetry,
            error_class=error_class,
        )
        failure = _base_manifest(
            context=context,
            observed=observed,
            data_mode=mode,
            provider=provider_name,
            authorized=readiness.live_provider_authorized,
            fixture_mode=readiness.fixture_mode,
            top_n=top_n,
            fetch_limit=fetch_limit,
            status="provider_unavailable",
        )
        failure.update({
            "run_id": provider_run_id,
            "provider_call_attempted": True,
            "provider_request_succeeded": False,
            "failure_class": error_class,
            "request_ledger_artifact": REQUEST_LEDGER_FILENAME,
            "contract_counted_status": "not_counted",
        })
        manifest_path = context.namespace_dir / RUN_MANIFEST_FILENAME
        _write_json_atomic(manifest_path, failure)
        return [], telemetry, MarketNoSendGenerationResult(
            status="provider_unavailable",
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            namespace_dir=context.namespace_dir,
            data_mode=mode,
            provider=provider_name,
            observed_at=observed.isoformat(),
            live_provider_authorized=readiness.live_provider_authorized,
            provider_call_attempted=True,
            provider_request_succeeded=False,
            manifest_path=manifest_path,
            request_ledger_path=ledger_path,
            failure_class=error_class,
            data_acquisition_mode="live_provider" if mode == "live" else "mocked_fixture",
            candidate_source_mode="live_no_send" if mode == "live" else "mocked_fixture",
        )


def _build_market_generation_from_rows(
    *,
    context: Any,
    observed: datetime,
    raw_rows: Sequence[Mapping[str, Any]],
    provider_name: str,
    data_mode: str,
    readiness: MarketNoSendReadiness,
    top_n: int,
    fetch_limit: int,
    request_telemetry: Mapping[str, Any],
    campaign_reservation: market_no_send_campaign_guard.CampaignReservation | None,
    calendar_environ: Mapping[str, str] | None,
) -> MarketNoSendGenerationResult:
    source_mode = "live_no_send" if data_mode == "live" else "mocked_fixture"
    acquisition_mode = "live_provider" if data_mode == "live" else "mocked_fixture"
    decision_radar_campaign_counted = bool(
        source_mode == "live_no_send"
        and readiness.live_provider_authorized
        and not readiness.fixture_mode
    )
    normalized_rows, universe_audit, history_summary, history_sha256 = (
        _prepare_normalized_market_rows(
            context=context,
            observed=observed,
            raw_rows=raw_rows,
            provider_name=provider_name,
            data_mode=data_mode,
            source_mode=source_mode,
            decision_radar_campaign_counted=decision_radar_campaign_counted,
            top_n=top_n,
            campaign_reservation=campaign_reservation,
        )
    )
    run_id = run_ledger.run_id_for(observed, context.profile)
    calendar_snapshot = market_no_send_calendar.load_market_no_send_calendar_snapshot(
        environ=calendar_environ,
        now=observed,
        data_mode=data_mode,
        run_mode=context.run_mode,
    )
    request_path, source_sha256, request_ledger_path, request_ledger_sha256 = (
        _write_market_request_artifacts(
            context=context,
            observed=observed,
            raw_row_count=len(raw_rows),
            normalized_rows=normalized_rows,
            provider_name=provider_name,
            data_mode=data_mode,
            acquisition_mode=acquisition_mode,
            source_mode=source_mode,
            decision_radar_campaign_counted=decision_radar_campaign_counted,
            readiness=readiness,
            run_id=run_id,
            universe_audit=universe_audit,
            history_sha256=history_sha256,
            request_telemetry=request_telemetry,
        )
    )
    provenance = market_no_send_authority.closed_market_provenance(
        contract_version=CONTRACT_VERSION,
        data_mode=data_mode,
        provider=provider_name,
        observed_at=observed,
        run_id=run_id,
        readiness=readiness,
        source_artifact=REQUEST_CACHE_FILENAME,
        source_artifact_sha256=source_sha256,
        request_ledger_artifact=REQUEST_LEDGER_FILENAME,
        request_ledger_sha256=request_ledger_sha256,
        feature_basis=market_no_send_features.generation_feature_basis(normalized_rows),
        data_quality=market_no_send_features.generation_data_quality(
            normalized_rows,
            history_summary,
            history_filename=HISTORY_FILENAME,
        ),
    )
    manifest_path, manifest = market_no_send_generation.start_generation_manifest(
        context=context, observed=observed, data_mode=data_mode,
        provider_name=provider_name, readiness=readiness, top_n=top_n,
        fetch_limit=fetch_limit, contract_version=CONTRACT_VERSION,
        safety_counters=_SAFETY_COUNTERS, run_id=run_id,
        raw_row_count=len(raw_rows), selected_row_count=len(normalized_rows),
        request_cache_filename=REQUEST_CACHE_FILENAME,
        request_cache_sha256=source_sha256,
        request_ledger_filename=REQUEST_LEDGER_FILENAME,
        request_ledger_sha256=request_ledger_sha256, provenance=provenance,
        history_filename=HISTORY_FILENAME, history_sha256=history_sha256,
        campaign_counted=decision_radar_campaign_counted,
        calendar_snapshot=calendar_snapshot.to_dict(),
        manifest_filename=RUN_MANIFEST_FILENAME,
    )
    try:
        calendar_source_rows = market_no_send_calendar.materialize_market_calendar_snapshot(
            context,
            calendar_snapshot=calendar_snapshot,
            observed=observed,
            run_id=run_id,
            manifest=manifest,
            safety_counters=_SAFETY_COUNTERS,
        )
        _write_json_atomic(manifest_path, manifest)
        anomaly_result = market_anomaly_scanner.run_market_anomaly_scan(
            market_rows=normalized_rows,
            namespace_dir=context.namespace_dir,
            cfg=market_anomaly_scanner.MarketAnomalyScannerConfig(max_assets=top_n),
            observed_at=observed,
            coingecko_universe_rows=normalized_rows,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            run_mode=context.run_mode,
            run_id=run_id,
        )
        anomaly_result = market_no_send_authority.attach_market_no_send_lineage(
            context.namespace_dir,
            scan_result=anomaly_result,
            normalized_rows=normalized_rows,
            provider=provider_name,
            data_mode=data_mode,
            request_cache_artifact=REQUEST_CACHE_FILENAME,
            request_ledger_artifact=REQUEST_LEDGER_FILENAME,
            run_id=run_id,
            provenance=provenance,
            safety_counters=_SAFETY_COUNTERS,
            history_artifact=HISTORY_FILENAME, history_sha256=history_sha256,
            minimum_shadow_sample_count=_market_history_config()[0].min_baseline_observations,
        )
        return _finish_market_generation(
            context=context,
            observed=observed,
            raw_row_count=len(raw_rows),
            normalized_row_count=len(normalized_rows),
            provider_name=provider_name,
            data_mode=data_mode,
            readiness=readiness,
            run_id=run_id,
            request_path=request_path,
            request_ledger_path=request_ledger_path,
            manifest_path=manifest_path,
            manifest=manifest,
            anomaly_result=anomaly_result,
            provenance=provenance,
            universe_audit=universe_audit,
            calendar_source_rows=calendar_source_rows,
        )
    except Exception as exc:
        market_no_send_generation.mark_generation_failed(
            manifest_path, manifest, exc
        )
        raise

def _prepare_normalized_market_rows(
    *,
    context: Any,
    observed: datetime,
    raw_rows: Sequence[Mapping[str, Any]],
    provider_name: str,
    data_mode: str,
    source_mode: str,
    decision_radar_campaign_counted: bool,
    top_n: int,
    campaign_reservation: market_no_send_campaign_guard.CampaignReservation | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], str]:
    rows, universe_audit = normalize_market_rows(
        raw_rows,
        top_n=top_n,
        observed_at=observed,
        provider=provider_name,
        data_mode=data_mode,
        request_cache_artifact=REQUEST_CACHE_FILENAME,
        request_ledger_artifact=REQUEST_LEDGER_FILENAME,
        candidate_source_mode=source_mode,
        decision_radar_campaign_counted=decision_radar_campaign_counted,
    )
    history_rows, history_summary, history_sha256 = (
        market_no_send_history_cache.enrich_and_persist_history(
        rows,
        artifact_base_dir=context.namespace_dir.parent,
        generation_namespace_dir=context.namespace_dir,
        history_filename=HISTORY_FILENAME,
        observed_at=observed,
        live_no_send=data_mode == "live",
        config=_market_history_config()[0],
        campaign_reservation=campaign_reservation,
        )
    )
    rows = [
        market_no_send_features.attach_history_quality(row)
        for row in history_rows
    ]
    audit = {
        **universe_audit,
        "market_history": history_summary,
        "market_history_artifact": HISTORY_FILENAME,
        "market_history_sha256": history_sha256,
    }
    return rows, audit, history_summary, history_sha256


def _write_market_request_artifacts(
    *,
    context: Any,
    observed: datetime,
    raw_row_count: int,
    normalized_rows: Sequence[Mapping[str, Any]],
    provider_name: str,
    data_mode: str,
    acquisition_mode: str,
    source_mode: str,
    decision_radar_campaign_counted: bool,
    readiness: MarketNoSendReadiness,
    run_id: str,
    universe_audit: Mapping[str, Any],
    history_sha256: str,
    request_telemetry: Mapping[str, Any],
) -> tuple[Path, str, Path, str]:
    common = _market_request_common(
        context=context,
        observed=observed,
        raw_row_count=raw_row_count,
        selected_row_count=len(normalized_rows),
        provider_name=provider_name,
        data_mode=data_mode,
        acquisition_mode=acquisition_mode,
        source_mode=source_mode,
        decision_radar_campaign_counted=decision_radar_campaign_counted,
        run_id=run_id,
    )
    request_path = context.namespace_dir / REQUEST_CACHE_FILENAME
    _write_json_atomic(request_path, {
        **common,
        "row_type": "event_market_no_send_source_cache",
        "universe_audit": dict(universe_audit),
        "market_history_artifact": HISTORY_FILENAME,
        "market_history_sha256": history_sha256,
        "rows": [dict(row) for row in normalized_rows],
    })
    source_sha256 = hashlib.sha256(_read_regular_bytes(request_path)).hexdigest()
    request_ledger_path = context.namespace_dir / REQUEST_LEDGER_FILENAME
    _write_json_atomic(request_ledger_path, {
        **common,
        "row_type": "event_market_no_send_request_ledger",
        "live_provider_authorized": readiness.live_provider_authorized,
        "fixture_mode": readiness.fixture_mode,
        "provider_source_artifact": REQUEST_CACHE_FILENAME,
        "provider_source_artifact_sha256": source_sha256,
        "cache_status": "write_through",
        "market_history_artifact": HISTORY_FILENAME,
        "market_history_sha256": history_sha256,
        **_safe_request_telemetry(
            request_telemetry,
            fallback_result_count=raw_row_count,
            succeeded=True,
        ),
    })
    ledger_sha256 = hashlib.sha256(_read_regular_bytes(request_ledger_path)).hexdigest()
    return request_path, source_sha256, request_ledger_path, ledger_sha256


def _write_failed_market_request_ledger(
    *,
    context: Any,
    observed: datetime,
    provider_name: str,
    readiness: MarketNoSendReadiness,
    run_id: str,
    telemetry: Mapping[str, Any],
    error_class: str,
) -> Path:
    path = context.namespace_dir / REQUEST_LEDGER_FILENAME
    _write_json_atomic(path, {
        "contract_version": CONTRACT_VERSION,
        "row_type": "event_market_no_send_request_ledger",
        "profile": context.profile,
        "artifact_namespace": context.artifact_namespace,
        "run_mode": context.run_mode,
        "run_id": run_id,
        "data_mode": "live",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": provider_name,
        "observed_at": observed.isoformat(),
        "provider_call_attempted": True,
        "provider_request_succeeded": False,
        "raw_market_row_count": 0,
        "selected_market_row_count": 0,
        "live_provider_authorized": readiness.live_provider_authorized,
        "fixture_mode": readiness.fixture_mode,
        "provenance_contract_valid": False,
        "measurement_program": market_provenance.DECISION_RADAR_MEASUREMENT_PROGRAM,
        "decision_radar_campaign_eligible": False,
        "decision_radar_campaign_counted": False,
        "decision_radar_campaign_reason": "not_counted_provider_request_failed",
        "burn_in_eligible": False,
        "burn_in_counted": False,
        "burn_in_reason": "not_counted_separate_decision_radar_campaign",
        "contract_counted_status": "not_counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **_safe_request_telemetry(
            telemetry,
            fallback_result_count=0,
            succeeded=False,
            fallback_error_class=error_class,
        ),
        **_SAFETY_COUNTERS,
    })
    return path


def _safe_request_telemetry(
    telemetry: Mapping[str, Any],
    *,
    fallback_result_count: int,
    succeeded: bool,
    fallback_error_class: str | None = None,
) -> dict[str, Any]:
    allowed = {
        "endpoint_path",
        "request_started_at",
        "request_ended_at",
        "duration_ms",
        "http_status",
        "result_count",
        "retry_count",
        "error_class",
        "cache_behavior",
    }
    values = {key: telemetry.get(key) for key in allowed if key in telemetry}
    endpoint = str(values.get("endpoint_path") or "/coins/markets")
    values["endpoint_path"] = endpoint if endpoint == "/coins/markets" else "/unknown"
    values.setdefault("request_started_at", None)
    values.setdefault("request_ended_at", None)
    values["duration_ms"] = max(0, int(values.get("duration_ms") or 0))
    values.setdefault("http_status", 200 if succeeded else None)
    values["result_count"] = max(0, int(values.get("result_count") or fallback_result_count))
    values["retry_count"] = max(0, int(values.get("retry_count") or 0))
    values["error_class"] = None if succeeded else str(values.get("error_class") or fallback_error_class or "provider_error")[:80]
    values.setdefault("cache_behavior", "network")
    return values


def _market_request_common(
    *,
    context: Any,
    observed: datetime,
    raw_row_count: int,
    selected_row_count: int,
    provider_name: str,
    data_mode: str,
    acquisition_mode: str,
    source_mode: str,
    decision_radar_campaign_counted: bool,
    run_id: str,
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "profile": context.profile,
        "artifact_namespace": context.artifact_namespace,
        "run_mode": context.run_mode,
        "run_id": run_id,
        "data_mode": data_mode,
        "data_acquisition_mode": acquisition_mode,
        "candidate_source_mode": source_mode,
        "provider": provider_name,
        "observed_at": observed.isoformat(),
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "raw_market_row_count": raw_row_count,
        "selected_market_row_count": selected_row_count,
        "provenance_contract_valid": True,
        "measurement_program": market_provenance.DECISION_RADAR_MEASUREMENT_PROGRAM,
        "decision_radar_campaign_eligible": decision_radar_campaign_counted,
        "decision_radar_campaign_counted": decision_radar_campaign_counted,
        "decision_radar_campaign_reason": (
            "counted_live_no_send_exact_lineage"
            if decision_radar_campaign_counted else "not_counted_non_live_mode:mocked_fixture"
        ),
        "burn_in_eligible": False,
        "burn_in_counted": False,
        "burn_in_reason": "not_counted_separate_decision_radar_campaign",
        "contract_counted_status": "counted" if decision_radar_campaign_counted else "not_counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **_SAFETY_COUNTERS,
    }


def _finish_market_generation(
    *,
    context: Any,
    observed: datetime,
    raw_row_count: int,
    normalized_row_count: int,
    provider_name: str,
    data_mode: str,
    readiness: MarketNoSendReadiness,
    run_id: str,
    request_path: Path,
    request_ledger_path: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    anomaly_result: Any,
    provenance: Mapping[str, Any],
    universe_audit: Mapping[str, Any],
    calendar_source_rows: tuple[dict[str, Any], ...] | None,
) -> MarketNoSendGenerationResult:
    integrated_result = _run_integrated_without_extra_providers(
        context,
        observed_at=observed,
        calendar_source_rows=calendar_source_rows,
        market_anomaly_scan_result=anomaly_result,
    )
    market_no_send_authority.initialize_exact_operator_state(
        context,
        run_id=run_id,
        provenance=provenance,
    )
    if (
        integrated_result.send_requested
        or integrated_result.send_attempted
        or integrated_result.send_success
        or integrated_result.send_items_delivered
        or integrated_result.strict_alerts
    ):
        raise MarketNoSendError("integrated radar violated the no-send generation contract")
    route_counts = market_no_send_features.decision_route_counts(
        integrated_result.integrated_candidates_path
    )
    # Quality describes the bounded market observation campaign, not only the
    # anomaly subset that happened to become candidates in this cycle.  Reading
    # the exact scanner snapshot also preserves useful maturity telemetry when
    # a valid live cycle produces zero ideas.
    quality_counts = market_no_send_features.market_quality_counts(
        anomaly_result.snapshots_path
    )
    core_path, outcomes_path = Path(integrated_result.core_opportunity_store_path), context.namespace_dir / integrated_radar.INTEGRATED_OUTCOMES_FILENAME
    calendar_metadata = market_no_send_generation.calendar_completion_metadata(
        manifest.get("calendar_snapshot") or {},
        namespace_dir=context.namespace_dir,
        unified_calendar_rows=int(integrated_result.unified_calendar_rows or 0),
        normalization=dict(integrated_result.unified_calendar_normalization or {}),
    )
    manifest.update({
        "status": "complete",
        "market_snapshot_count": anomaly_result.snapshot_count, "market_anomaly_count": anomaly_result.anomaly_count,
        "candidate_count": integrated_result.candidates, "core_row_count": integrated_result.current_generation_core_rows,
        "candidate_artifact": Path(integrated_result.integrated_candidates_path).name,
        "candidate_artifact_sha256": hashlib.sha256(_read_regular_bytes(Path(integrated_result.integrated_candidates_path)) or b"").hexdigest(),
        **market_no_send_publication.supporting_jsonl_artifact_bindings(core_path, outcomes_path),
        "card_count": len(integrated_result.research_card_paths),
        "decision_route_counts": dict(route_counts),
        "market_quality_source_artifact": anomaly_result.snapshots_path.name,
        "calendar_snapshot": calendar_metadata,
        "universe_audit": dict(universe_audit),
        **quality_counts,
        "provenance_contract_valid": provenance.get("provenance_contract_valid") is True,
        "measurement_program": provenance.get("measurement_program"),
        "decision_radar_campaign_eligible": provenance.get("decision_radar_campaign_eligible") is True,
        "decision_radar_campaign_counted": provenance.get("decision_radar_campaign_counted") is True,
        "decision_radar_campaign_reason": provenance.get("decision_radar_campaign_reason"),
        "burn_in_eligible": provenance.get("burn_in_eligible") is True,
        "burn_in_counted": provenance.get("burn_in_counted") is True,
        "burn_in_reason": provenance.get("burn_in_reason"),
        "contract_counted_status": (
            "counted" if provenance.get("decision_radar_campaign_counted") is True else "not_counted"
        ),
        "no_send_status": "enforced",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    _write_json_atomic(manifest_path, manifest)
    if data_mode == "live":
        try:
            outcome_refresh = market_observation_outcomes.refresh_campaign_outcomes(
                context.namespace_dir.parent,
                evaluated_at=observed,
            )
            manifest.update({
                "campaign_outcome_ledger": (
                    f"{market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE}/"
                    f"{market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME}"
                ),
                "campaign_outcome_count": outcome_refresh["outcome_count"],
                "campaign_outcome_maturation_counts": outcome_refresh["maturation_counts"],
                "campaign_outcome_refresh_error_counts": outcome_refresh["build_error_counts"],
            })
        except (OSError, ValueError, MarketNoSendError) as exc:
            manifest["campaign_outcome_refresh_failure_class"] = type(exc).__name__
        _write_json_atomic(manifest_path, manifest)
    market_no_send_authority.record_market_authority_artifacts(
        context,
        run_id=run_id,
        request_path=request_path,
        request_ledger_path=request_ledger_path,
        manifest_path=manifest_path,
        candidates_path=Path(integrated_result.integrated_candidates_path),
        outcomes_path=outcomes_path,
        history_filename=HISTORY_FILENAME,
    )
    return MarketNoSendGenerationResult(
        status="complete",
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        namespace_dir=context.namespace_dir,
        data_mode=data_mode,
        provider=provider_name,
        observed_at=observed.isoformat(),
        live_provider_authorized=readiness.live_provider_authorized,
        provider_call_attempted=True,
        provider_request_succeeded=True,
        raw_market_rows=raw_row_count,
        selected_market_rows=normalized_row_count,
        market_anomalies=anomaly_result.anomaly_count,
        candidates=integrated_result.candidates,
        core_rows=int(integrated_result.current_generation_core_rows or 0),
        cards=len(integrated_result.research_card_paths),
        run_id=run_id,
        request_cache_path=request_path,
        request_ledger_path=request_ledger_path,
        manifest_path=manifest_path,
        outcomes_path=outcomes_path,
        history_path=context.namespace_dir / HISTORY_FILENAME,
        data_acquisition_mode=str(provenance.get("data_acquisition_mode") or "preflight_only"),
        candidate_source_mode=str(provenance.get("candidate_source_mode") or "preflight_only"),
        provenance_contract_valid=provenance.get("provenance_contract_valid") is True,
        measurement_program=str(provenance.get("measurement_program") or ""),
        decision_radar_campaign_eligible=provenance.get("decision_radar_campaign_eligible") is True,
        decision_radar_campaign_counted=provenance.get("decision_radar_campaign_counted") is True,
        decision_radar_campaign_reason=str(provenance.get("decision_radar_campaign_reason") or "not_counted"),
        burn_in_eligible=provenance.get("burn_in_eligible") is True,
        burn_in_counted=provenance.get("burn_in_counted") is True,
        baseline_status=str(quality_counts.get("baseline_status") or "not_evaluated"),
        baseline_warm_assets=int(quality_counts.get("baseline_warm_assets") or 0),
        baseline_warming_assets=int(quality_counts.get("baseline_warming_assets") or 0),
        direct_feature_count=int(quality_counts.get("direct_feature_count") or 0),
        proxy_feature_count=int(quality_counts.get("proxy_feature_count") or 0),
    )


def normalize_market_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    top_n: int,
    observed_at: datetime | str,
    provider: str,
    data_mode: str,
    request_cache_artifact: str,
    request_ledger_artifact: str = REQUEST_LEDGER_FILENAME,
    candidate_source_mode: str | None = None,
    decision_radar_campaign_counted: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select a bounded liquid universe and add transparent market proxies."""

    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc))
    return market_no_send_features.normalize_market_rows(
        rows,
        top_n=_bounded_top_n(top_n),
        observed_at=observed,
        provider=provider,
        data_mode=data_mode,
        request_cache_artifact=request_cache_artifact,
        request_ledger_artifact=request_ledger_artifact,
        candidate_source_mode=candidate_source_mode,
        decision_radar_campaign_counted=decision_radar_campaign_counted,
        burn_in_counted=False,
        safety_counters=_SAFETY_COUNTERS,
    )


def publish_market_no_send_generation(
    artifact_base_dir: str | Path,
    artifact_namespace: str = DEFAULT_NAMESPACE,
    *,
    now: datetime | str | None = None,
    publisher: Callable[..., Any] | None = None,
) -> Any:
    """Validate and publish only through an explicit coordinating transition.

    Daily Operations owns the public operator transition because it closes the
    prepublication audit, final publication receipt, owned-dashboard restart,
    operations receipt, terminal journal, and campaign report.  Requiring the
    caller to supply that transition prevents the lower-level collection CLI
    from advancing operator authority on its own.
    """

    if publisher is None:
        raise MarketNoSendError(
            "direct market generation publication is disabled; "
            "use make radar-daily-ops-cycle"
        )

    base = _validated_artifact_base(artifact_base_dir)
    namespace = _validated_namespace(artifact_namespace)
    namespace_dir = _safe_existing_namespace_dir(base, namespace)
    manifest = _read_json_object(namespace_dir / RUN_MANIFEST_FILENAME)
    checked_at = _as_utc(datetime.now(timezone.utc) if manifest.get("data_mode") == "live" else (_parse_time(now) or datetime.now(timezone.utc)))
    _validate_publishable_manifest(
        manifest,
        namespace_dir=namespace_dir,
        namespace=namespace,
        checked_at=checked_at,
    )
    try:
        return publisher(base, namespace, now=checked_at)
    except DashboardReadinessError as exc:
        raise MarketNoSendError(f"market generation is not dashboard-authoritative: {exc}") from exc


def market_no_send_generation_status(
    artifact_base_dir: str | Path,
    artifact_namespace: str = DEFAULT_NAMESPACE,
) -> dict[str, Any]:
    """Read one attempt status without provider calls or artifact mutation."""
    return market_no_send_attempt.exact_generation_status(
        _validated_artifact_base(artifact_base_dir),
        _validated_namespace(artifact_namespace), manifest_filename=RUN_MANIFEST_FILENAME,
    )


def write_market_no_send_pilot_audit(
    artifact_base_dir: str | Path,
    artifact_namespace: str = DEFAULT_NAMESPACE,
    *,
    result: MarketNoSendGenerationResult | None = None,
    now: datetime | str | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    """Write the credential-free post-attempt JSON and Markdown pilot audit."""

    base = _validated_artifact_base(artifact_base_dir)
    namespace = _validated_namespace(artifact_namespace)
    checked_at = _as_utc(_parse_time(now) or datetime.now(timezone.utc))
    readiness = build_market_no_send_readiness(
        artifact_base_dir=base,
        artifact_namespace=namespace,
        environ=os.environ,
        fixture_dir=config.FIXTURE_DIR,
        now=checked_at,
    )
    return market_no_send_audit.write_pilot_audit(
        base=base,
        namespace=namespace,
        checked_at=checked_at,
        readiness=readiness,
        result=result,
        manifest_filename=RUN_MANIFEST_FILENAME,
        json_filename=PILOT_AUDIT_JSON_FILENAME,
        markdown_filename=PILOT_AUDIT_MD_FILENAME,
        safety_counters=_SAFETY_COUNTERS,
    )


def _fetch_live_coingecko_rows(fetch_limit: int) -> market_no_send_provider.MarketProviderResponse:
    client_holder: dict[str, Any] = {}

    def client_factory() -> Any:
        client = __import__(
            "crypto_rsi_scanner.client", fromlist=["CoinGeckoClient"]
        ).CoinGeckoClient(timeout_seconds=8.0, max_retries=1)
        client_holder["client"] = client
        return client

    rows, warnings = market_enrichment.load_market_enrichment_rows_safe(
        None,
        live=True,
        fetch_limit=fetch_limit,
        limit=fetch_limit,
        client_factory=client_factory,
        fail_soft=True,
        now=datetime.now(timezone.utc),
    )
    client = client_holder.get("client")
    telemetry = dict(getattr(client, "last_request_telemetry", {}) or {})
    if warnings:
        raise market_no_send_provider.MarketProviderRequestError(
            str(telemetry.get("error_class") or "CoinGeckoUnavailable"),
            telemetry,
        )
    return market_no_send_provider.MarketProviderResponse(
        tuple(rows),
        telemetry,
    )


def _run_integrated_without_extra_providers(
    context: Any,
    *,
    observed_at: datetime,
    calendar_source_rows: tuple[dict[str, Any], ...] | None = None,
    market_anomaly_scan_result: Any | None = None,
) -> Any:
    previous_refresh = config.EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED
    try:
        config.EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED = False
        return integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=False,
            observed_at=observed_at,
            input_mode=integrated_radar.INPUT_MODE_LOAD_EXISTING,
            coinalyze_namespace=context.artifact_namespace,
            targeted_market_provider=None,
            calendar_source_rows=calendar_source_rows,
            market_anomaly_scan_result=market_anomaly_scan_result,
        )
    finally:
        config.EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED = previous_refresh


def _base_manifest(
    *,
    context: Any,
    observed: datetime,
    data_mode: str,
    provider: str,
    authorized: bool,
    fixture_mode: bool,
    top_n: int,
    fetch_limit: int,
    status: str,
) -> dict[str, Any]:
    return market_no_send_publication.base_manifest(
        context=context,
        observed=observed,
        data_mode=data_mode,
        provider=provider,
        authorized=authorized,
        fixture_mode=fixture_mode,
        top_n=top_n,
        fetch_limit=fetch_limit,
        status=status,
        contract_version=CONTRACT_VERSION,
        safety_counters=_SAFETY_COUNTERS,
    )


def _validate_publishable_manifest(
    manifest: Mapping[str, Any],
    *,
    namespace_dir: Path,
    namespace: str,
    checked_at: datetime,
) -> None:
    market_no_send_publication.validate_publishable_manifest(
        manifest,
        namespace_dir=namespace_dir,
        namespace=namespace,
        checked_at=checked_at,
        contract_version=CONTRACT_VERSION,
        default_profile=DEFAULT_PROFILE,
        request_cache_filename=REQUEST_CACHE_FILENAME,
        request_ledger_filename=REQUEST_LEDGER_FILENAME,
        safety_counters=_SAFETY_COUNTERS,
    )


def _bounded_top_n(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise MarketNoSendError("top_n must be an integer") from exc
    if parsed < 1 or parsed > MAX_TOP_N:
        raise MarketNoSendError(f"top_n must be between 1 and {MAX_TOP_N}")
    return parsed


def _bounded_fetch_limit(value: int | None, top_n: int) -> int:
    selected = int(value or config.EVENT_DISCOVERY_UNIVERSE_FETCH_LIMIT or universe.candidate_count(top_n))
    return min(250, max(top_n, selected))


def _market_history_config() -> tuple[Any, str | None]:
    from ..radar import market_history

    try:
        minutes = int(config.DECISION_RADAR_MIN_OBSERVATION_SPACING_MINUTES)
        return (
            market_history.MarketHistoryConfig(
                minimum_observation_spacing=timedelta(minutes=minutes),
            ),
            None,
        )
    except (TypeError, ValueError):
        return (
            market_history.MarketHistoryConfig(),
            "RSI_DECISION_RADAR_MIN_OBSERVATION_SPACING_MINUTES must be a positive integer",
        )


def _validated_namespace(value: str) -> str:
    namespace = str(value or "").strip()
    if not _NAMESPACE_RE.fullmatch(namespace) or namespace in {".", ".."}:
        raise MarketNoSendError("invalid market no-send artifact namespace")
    if namespace == market_no_send_history_cache.LIVE_HISTORY_CACHE_NAMESPACE:
        raise MarketNoSendError("market no-send namespace is reserved for rolling history")
    return namespace


def _validated_artifact_base(value: str | Path) -> Path:
    base = Path(value).expanduser().resolve()
    try:
        info = base.lstat()
    except FileNotFoundError:
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = base.lstat()
    except OSError as exc:
        raise MarketNoSendError("market no-send artifact base is unreadable") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise MarketNoSendError("market no-send artifact base is not a directory")
    return base


def _require_exact_context(context: Any, *, base: Path, namespace: str) -> None:
    if context.base_dir.resolve() != base or context.artifact_namespace != namespace:
        raise MarketNoSendError("environment overrides changed the requested market artifact context")
    if context.namespace_dir.parent.resolve() != base:
        raise MarketNoSendError("market artifact namespace escapes the selected base")
    if context.provider_health_path != (
        context.namespace_dir / market_no_send_provider.PROVIDER_HEALTH_FILENAME
    ):
        raise MarketNoSendError("market provider-health path is not namespace-local")


def _parse_time(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else None
    return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise MarketNoSendError("market generation clock must be timezone-aware")
    return value.astimezone(timezone.utc)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def main(argv: Sequence[str] | None = None) -> int:
    from .market_no_send_cli import main as cli_main

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "CONTRACT_VERSION",
    "DEFAULT_NAMESPACE",
    "DEFAULT_SMOKE_NAMESPACE",
    "MarketNoSendError",
    "MarketNoSendGenerationResult",
    "MarketNoSendReadiness",
    "RUN_MANIFEST_FILENAME",
    "REQUEST_CACHE_FILENAME",
    "REQUEST_LEDGER_FILENAME",
    "HISTORY_FILENAME",
    "PILOT_AUDIT_JSON_FILENAME",
    "PILOT_AUDIT_MD_FILENAME",
    "build_market_no_send_readiness",
    "main",
    "normalize_market_rows",
    "market_no_send_generation_status",
    "publish_market_no_send_generation",
    "run_market_no_send_generation",
    "write_market_no_send_pilot_audit",
)
