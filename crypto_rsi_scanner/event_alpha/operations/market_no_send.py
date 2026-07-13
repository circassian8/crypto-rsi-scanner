"""Guarded live-market Crypto Radar generation with no-send defaults.

The production command performs exactly one explicitly authorized CoinGecko
market-universe request, turns the bounded liquid universe into the existing
market-anomaly sidecar, and then reuses the integrated radar artifact pipeline.
It never enables notification, trading, paper-trading, normal-RSI writes, or
Event Alpha ``TRIGGERED_FADE`` creation.  Dashboard publication is a separate
step and additionally requires a fresh, exact strict-doctor generation.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from ... import config, universe
from ..artifacts import context as artifact_context
from ..artifacts import operator_state
from ..artifacts import run_ledger
from ..dashboard.readiness import (
    DashboardReadinessError,
    publish_current_namespace_pointer,
    read_current_namespace_pointer,
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
    read_jsonl as _read_jsonl,
    read_regular_bytes as _read_regular_bytes,
    safe_existing_namespace_dir as _safe_existing_namespace_dir,
    write_bytes_atomic as _write_bytes_atomic,
    write_json_atomic as _write_json_atomic,
    write_jsonl as _write_jsonl,
)


CONTRACT_VERSION = 1
DEFAULT_PROFILE = "no_key_live"
DEFAULT_NAMESPACE = "radar_market_no_send"
DEFAULT_SMOKE_NAMESPACE = "radar_market_no_send_smoke"
DEFAULT_TOP_N = 30
MAX_TOP_N = 50
REQUEST_CACHE_FILENAME = "event_market_no_send_market_rows.json"
RUN_MANIFEST_FILENAME = "event_market_no_send_generation.json"
LIVE_AUTH_ENV = "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE"
_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
MarketRowsProvider = Callable[[int], Sequence[Mapping[str, Any]]]


def build_market_no_send_readiness(
    *,
    artifact_namespace: str = DEFAULT_NAMESPACE,
    top_n: int = DEFAULT_TOP_N,
    fetch_limit: int | None = None,
    environ: Mapping[str, str] | None = None,
    fixture_dir: str | Path | None | object = ...,  # explicit None means live client mode
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
    )


def run_market_no_send_generation(
    *,
    artifact_base_dir: str | Path,
    artifact_namespace: str = DEFAULT_NAMESPACE,
    profile: str = DEFAULT_PROFILE,
    run_mode: str = "burn_in",
    top_n: int = DEFAULT_TOP_N,
    fetch_limit: int | None = None,
    provider: MarketRowsProvider | None = None,
    observed_at: datetime | str | None = None,
    environ: Mapping[str, str] | None = None,
    fixture_dir: str | Path | None | object = ...,
    data_mode: str = "live",
    allow_non_live: bool = False,
) -> MarketNoSendGenerationResult:
    """Build one local market-led generation without publishing its pointer.

    The provider callable is not touched until the existing live authorization
    flag and the absence of fixture mode have both been proven.  Tests and the
    smoke command may set ``allow_non_live`` with an injected provider; those
    generations are permanently ineligible for dashboard pointer publication.
    """

    namespace = _validated_namespace(artifact_namespace)
    bounded_top_n = _bounded_top_n(top_n)
    bounded_fetch = _bounded_fetch_limit(fetch_limit, bounded_top_n)
    mode = str(data_mode or "").strip().casefold()
    if mode not in {"live", "mock"}:
        raise MarketNoSendError("data_mode must be live or mock")
    readiness = build_market_no_send_readiness(
        artifact_namespace=namespace,
        top_n=bounded_top_n,
        fetch_limit=bounded_fetch,
        environ=environ,
        fixture_dir=fixture_dir,
    )
    if mode != "live" and not allow_non_live:
        raise MarketNoSendError("non-live market generation is reserved for the no-network smoke")
    if mode == "live" and not readiness.ready:
        return MarketNoSendGenerationResult(
            status="blocked",
            profile=profile,
            artifact_namespace=namespace,
            namespace_dir=None,
            data_mode=mode,
            provider="coingecko",
            observed_at=_as_utc(_parse_time(observed_at) or datetime.now(timezone.utc)).isoformat(),
            live_provider_authorized=readiness.live_provider_authorized,
            provider_call_attempted=False,
            provider_request_succeeded=False,
            failure_class="provider_authorization_missing",
        )

    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc))
    base = _validated_artifact_base(artifact_base_dir)
    context = artifact_context.context_from_profile(
        profile,
        run_mode=run_mode,
        base_dir=base,
        artifact_namespace=namespace,
    )
    _require_exact_context(context, base=base, namespace=namespace)
    _ensure_safe_namespace_dir(context.namespace_dir)
    provider_name = "coingecko" if mode == "live" else "mock_coingecko"
    fetch = provider or _fetch_live_coingecko_rows

    try:
        raw_rows = [dict(row) for row in fetch(bounded_fetch) if isinstance(row, Mapping)]
    except Exception as exc:  # noqa: BLE001 - external provider must fail soft
        failure = _base_manifest(
            context=context,
            observed=observed,
            data_mode=mode,
            provider=provider_name,
            authorized=readiness.live_provider_authorized,
            fixture_mode=readiness.fixture_mode,
            top_n=bounded_top_n,
            fetch_limit=bounded_fetch,
            status="provider_unavailable",
        )
        failure.update({
            "provider_call_attempted": True,
            "provider_request_succeeded": False,
            "failure_class": type(exc).__name__,
            "contract_counted_status": "not_counted",
        })
        manifest_path = context.namespace_dir / RUN_MANIFEST_FILENAME
        _write_json_atomic(manifest_path, failure)
        return MarketNoSendGenerationResult(
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
            failure_class=type(exc).__name__,
        )

    return _build_market_generation_from_rows(
        context=context,
        observed=observed,
        raw_rows=raw_rows,
        provider_name=provider_name,
        data_mode=mode,
        readiness=readiness,
        top_n=bounded_top_n,
        fetch_limit=bounded_fetch,
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
) -> MarketNoSendGenerationResult:
    normalized_rows, universe_audit = normalize_market_rows(
        raw_rows,
        top_n=top_n,
        observed_at=observed,
        provider=provider_name,
        data_mode=data_mode,
        request_cache_artifact=REQUEST_CACHE_FILENAME,
    )
    run_id = run_ledger.run_id_for(observed, context.profile)
    request_path = context.namespace_dir / REQUEST_CACHE_FILENAME
    request_payload = {
        "contract_version": CONTRACT_VERSION,
        "row_type": "event_market_no_send_request_cache",
        "profile": context.profile,
        "artifact_namespace": context.artifact_namespace,
        "run_mode": context.run_mode,
        "run_id": run_id,
        "data_mode": data_mode,
        "provider": provider_name,
        "observed_at": observed.isoformat(),
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "raw_market_row_count": len(raw_rows),
        "selected_market_row_count": len(normalized_rows),
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **_SAFETY_COUNTERS,
        "universe_audit": universe_audit,
        "rows": normalized_rows,
    }
    _write_json_atomic(request_path, request_payload)
    manifest_path = context.namespace_dir / RUN_MANIFEST_FILENAME
    manifest = _base_manifest(
        context=context,
        observed=observed,
        data_mode=data_mode,
        provider=provider_name,
        authorized=readiness.live_provider_authorized,
        fixture_mode=readiness.fixture_mode,
        top_n=top_n,
        fetch_limit=fetch_limit,
        status="building",
    )
    manifest.update({
        "run_id": run_id,
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "raw_market_row_count": len(raw_rows),
        "selected_market_row_count": len(normalized_rows),
        "request_cache_artifact": REQUEST_CACHE_FILENAME,
        "request_cache_sha256": hashlib.sha256(_read_regular_bytes(request_path)).hexdigest(),
        "contract_counted_status": "pending",
    })
    _write_json_atomic(manifest_path, manifest)
    try:
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
        _attach_market_no_send_lineage(
            context.namespace_dir,
            normalized_rows=normalized_rows,
            provider=provider_name,
            data_mode=data_mode,
            request_cache_artifact=REQUEST_CACHE_FILENAME,
            run_id=run_id,
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
            manifest_path=manifest_path,
            manifest=manifest,
            anomaly_result=anomaly_result,
        )
    except Exception as exc:
        manifest.update({
            "status": "failed",
            "contract_counted_status": "not_counted",
            "failure_class": type(exc).__name__,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        })
        _write_json_atomic(manifest_path, manifest)
        raise


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
    manifest_path: Path,
    manifest: dict[str, Any],
    anomaly_result: Any,
) -> MarketNoSendGenerationResult:
    integrated_result = _run_integrated_without_extra_providers(
        context,
        observed_at=observed,
    )
    _initialize_exact_operator_state(
        context,
        run_id=run_id,
        provenance={
            "contract_version": CONTRACT_VERSION,
            "data_mode": data_mode,
            "provider": provider_name,
            "observed_at": observed.isoformat(),
            "request_cache_artifact": REQUEST_CACHE_FILENAME,
            "contract_counted_status": "counted",
            "provider_call_attempted": True,
            "provider_request_succeeded": True,
            "no_send_status": "enforced",
            "no_send": True,
            "research_only": True,
            **_SAFETY_COUNTERS,
        },
    )
    if (
        integrated_result.send_requested
        or integrated_result.send_attempted
        or integrated_result.send_success
        or integrated_result.send_items_delivered
        or integrated_result.strict_alerts
    ):
        raise MarketNoSendError("integrated radar violated the no-send generation contract")
    route_counts = _decision_route_counts(integrated_result.integrated_candidates_path)
    manifest.update({
        "status": "complete",
        "market_snapshot_count": anomaly_result.snapshot_count,
        "market_anomaly_count": anomaly_result.anomaly_count,
        "candidate_count": integrated_result.candidates,
        "core_row_count": integrated_result.current_generation_core_rows,
        "card_count": len(integrated_result.research_card_paths),
        "decision_route_counts": dict(route_counts),
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    _write_json_atomic(manifest_path, manifest)
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
        manifest_path=manifest_path,
    )


def normalize_market_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    top_n: int,
    observed_at: datetime | str,
    provider: str,
    data_mode: str,
    request_cache_artifact: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select a bounded liquid universe and add transparent market proxies."""

    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc))
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    clean, excluded, audit = universe.filter_markets_with_audit(
        materialized,
        limit=None,
        now=observed,
    )
    ranked = sorted(clean, key=_liquid_rank, reverse=True)[: _bounded_top_n(top_n)]
    proxy_zscores = _cross_sectional_turnover_zscores(ranked)
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(ranked):
        if _has_explicit_return_fields(row):
            snapshot = _normalized_explicit_market_row(row)
        else:
            snapshot = market_enrichment.market_snapshot_from_row(row, now=observed)
        coin_id = str(snapshot.get("coin_id") or row.get("id") or row.get("coin_id") or "").strip()
        symbol = str(snapshot.get("symbol") or row.get("symbol") or "").upper().strip()
        market_cap = _finite_float(row.get("market_cap"))
        total_volume = _finite_float(row.get("total_volume") or row.get("volume_24h"))
        explicit_liquidity = _finite_float(row.get("liquidity_usd"))
        liquidity = explicit_liquidity if explicit_liquidity is not None else total_volume
        volume_mcap = (
            total_volume / market_cap
            if total_volume is not None and market_cap is not None and market_cap > 0
            else None
        )
        volume_z = _finite_float(row.get("volume_zscore_24h"))
        if volume_z is None:
            volume_z = proxy_zscores.get(index)
        snapshot.update({
            "coin_id": coin_id,
            "symbol": symbol,
            "canonical_asset_id": str(row.get("canonical_asset_id") or coin_id or symbol),
            "name": str(row.get("name") or "") or None,
            "observed_at": observed.isoformat(),
            "timestamp": observed.isoformat(),
            "freshness_status": "fresh",
            "market_context_freshness_status": "fresh",
            "market_data_source": provider,
            "provider": provider,
            "source": provider,
            "source_class": "market_data",
            "source_pack": "market_anomaly_pack",
            "data_mode": data_mode,
            "provider_request_succeeded": True,
            "provider_source_artifact": request_cache_artifact,
            "request_ledger_path": request_cache_artifact,
            "contract_counted_status": "counted",
            "no_send_status": "enforced",
            "no_send": True,
            "research_only": True,
            "market_cap": market_cap,
            "volume_24h": total_volume,
            "total_volume": total_volume,
            "volume_to_market_cap": volume_mcap,
            "volume_zscore_24h": volume_z,
            "volume_zscore_basis": (
                "provider_observed" if row.get("volume_zscore_24h") is not None
                else "cross_sectional_log_turnover_proxy"
            ),
            "liquidity_usd": liquidity,
            "liquidity_basis": (
                "provider_observed" if explicit_liquidity is not None
                else "coingecko_total_volume_24h_proxy"
            ),
            "spread_bps": _finite_float(row.get("spread_bps")),
            "spread_status": "verified" if row.get("spread_bps") is not None else "unavailable",
            "is_tradable_asset": True,
            "venues": [provider],
            **_SAFETY_COUNTERS,
        })
        normalized.append({key: value for key, value in snapshot.items() if value is not None})
    audit = dict(audit)
    audit.update({
        "requested_limit": _bounded_top_n(top_n),
        "kept_count": len(normalized),
        "excluded_count": int(sum(excluded.values())),
        "selection_order": "total_volume_desc",
        "provider": provider,
        "data_mode": data_mode,
        "observed_at": observed.isoformat(),
    })
    return normalized, audit


def publish_market_no_send_generation(
    artifact_base_dir: str | Path,
    artifact_namespace: str = DEFAULT_NAMESPACE,
    *,
    now: datetime | str | None = None,
    publisher: Callable[..., Any] = publish_current_namespace_pointer,
) -> Any:
    """Publish only a complete, fresh, live, authorized, strict-clean run."""

    base = _validated_artifact_base(artifact_base_dir)
    namespace = _validated_namespace(artifact_namespace)
    namespace_dir = _safe_existing_namespace_dir(base, namespace)
    manifest = _read_json_object(namespace_dir / RUN_MANIFEST_FILENAME)
    checked_at = _as_utc(_parse_time(now) or datetime.now(timezone.utc))
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


def _fetch_live_coingecko_rows(fetch_limit: int) -> Sequence[Mapping[str, Any]]:
    rows, warnings = market_enrichment.load_market_enrichment_rows_safe(
        None,
        live=True,
        fetch_limit=fetch_limit,
        limit=fetch_limit,
        client_factory=lambda: __import__(
            "crypto_rsi_scanner.client", fromlist=["CoinGeckoClient"]
        ).CoinGeckoClient(timeout_seconds=8.0, max_retries=1),
        fail_soft=True,
        now=datetime.now(timezone.utc),
    )
    if warnings:
        raise MarketNoSendError("CoinGecko market request was unavailable")
    return rows


def _run_integrated_without_extra_providers(context: Any, *, observed_at: datetime) -> Any:
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
        )
    finally:
        config.EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED = previous_refresh


def _initialize_exact_operator_state(
    context: Any,
    *,
    run_id: str,
    provenance: Mapping[str, Any],
) -> None:
    """Restore in-namespace absolute paths for the operator-state constructor.

    Persisted run ledgers deliberately expose only portable paths, retaining the
    exact local values under ``*_abs_debug``.  An artifact base outside the repo
    cannot resolve a bare portable filename from the process cwd, so build the
    state from the already-persisted exact debug paths and let operator-state
    fingerprinting immediately convert them back to namespace-relative paths.
    """

    rows = run_ledger.load_run_records(context.run_ledger_path, limit=20).rows
    matching = [
        dict(row)
        for row in rows
        if str(row.get("run_id") or "") == run_id
        and str(row.get("profile") or "default") == context.profile
        and str(row.get("artifact_namespace") or "") == context.artifact_namespace
    ]
    if len(matching) != 1:
        raise MarketNoSendError("market generation has no unique persisted run-ledger authority")
    exact = matching[0]
    for key, value in tuple(exact.items()):
        if key.endswith("_abs_debug") and value not in (None, "", [], {}):
            exact[key[: -len("_abs_debug")]] = value
    if exact.get("integrated_source_coverage_json_path_abs_debug"):
        exact["source_coverage_json_path_rel"] = exact[
            "integrated_source_coverage_json_path_abs_debug"
        ]
    if exact.get("source_coverage_path_abs_debug"):
        exact["source_coverage_md_path_rel"] = exact[
            "source_coverage_path_abs_debug"
        ]
    operator_state.begin_run(
        context.namespace_dir,
        exact,
        run_ledger_path=context.run_ledger_path,
        updated_at=datetime.now(timezone.utc),
    )
    _record_market_no_send_operator_provenance(
        context,
        run_id=run_id,
        provenance=provenance,
    )


def _record_market_no_send_operator_provenance(
    context: Any,
    *,
    run_id: str,
    provenance: Mapping[str, Any],
) -> None:
    """Attach bounded generation provenance to the exact operator state."""

    with operator_state._state_lock(context.namespace_dir):  # noqa: SLF001 - exact atomic state extension
        loaded = operator_state.load_operator_state(context.namespace_dir)
        state = dict(loaded.state or {}) if loaded.valid else {}
        if not operator_state.state_matches_run(
            state,
            {"run_id": run_id, "profile": context.profile, "artifact_namespace": context.artifact_namespace},
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
        ):
            raise MarketNoSendError("market provenance has no matching operator generation")
        state["market_no_send_provenance"] = dict(provenance)
        state["revision"] = int(state.get("revision") or 0) + 1
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        state["doctor"] = {
            "status": "not_run",
            "run_id": run_id,
            "authoritative": False,
            "strict": False,
            "schema_only": False,
            "skip_api_checks": False,
            "verified_at": None,
            "verified_revision": None,
            "blocker_count": 0,
            "warning_count": 0,
        }
        operator_state.write_json_atomic(
            operator_state.operator_state_path(context.namespace_dir),
            state,
        )


def _attach_market_no_send_lineage(
    namespace_dir: Path,
    *,
    normalized_rows: Iterable[Mapping[str, Any]],
    provider: str,
    data_mode: str,
    request_cache_artifact: str,
    run_id: str,
) -> None:
    by_coin = {
        str(row.get("coin_id") or ""): dict(row)
        for row in normalized_rows
        if str(row.get("coin_id") or "")
    }
    snapshot_path = namespace_dir / market_anomaly_scanner.MARKET_STATE_SNAPSHOT_FILENAME
    anomaly_path = namespace_dir / market_anomaly_scanner.MARKET_ANOMALY_FILENAME
    snapshot_rows = _read_jsonl(snapshot_path)
    anomaly_rows = _read_jsonl(anomaly_path)
    lineage = {
        "provider": provider,
        "source_provider": provider,
        "latest_source": provider,
        "source_class": "market_data",
        "source_pack": "market_anomaly_pack",
        "data_mode": data_mode,
        "provider_request_succeeded": True,
        "provider_source_artifact": request_cache_artifact,
        "request_ledger_path": request_cache_artifact,
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **_SAFETY_COUNTERS,
    }
    for row in snapshot_rows:
        source = by_coin.get(str(row.get("coin_id") or ""), {})
        row.update(lineage)
        for key in ("liquidity_basis", "volume_zscore_basis", "spread_status"):
            if source.get(key) is not None:
                row[key] = source[key]
    for row in anomaly_rows:
        source = by_coin.get(str(row.get("coin_id") or ""), {})
        row.update(lineage)
        row["provider_generation_id"] = run_id
        snapshot = row.get("market_state_snapshot")
        if isinstance(snapshot, Mapping):
            attached = dict(snapshot)
            attached.update(lineage)
            for key in ("liquidity_basis", "volume_zscore_basis", "spread_status"):
                if source.get(key) is not None:
                    attached[key] = source[key]
            row["market_state_snapshot"] = attached
    _write_jsonl(snapshot_path, snapshot_rows)
    _write_jsonl(anomaly_path, anomaly_rows)


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
    return {
        "contract_version": CONTRACT_VERSION,
        "row_type": "event_market_no_send_generation",
        "status": status,
        "profile": context.profile,
        "artifact_namespace": context.artifact_namespace,
        "run_mode": context.run_mode,
        "data_mode": data_mode,
        "provider": provider,
        "observed_at": observed.isoformat(),
        "top_n": top_n,
        "fetch_limit": fetch_limit,
        "live_provider_authorized": authorized,
        "fixture_mode": fixture_mode,
        "provider_call_attempted": False,
        "provider_request_succeeded": False,
        "contract_counted_status": "not_counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        "pointer_published": False,
        **_SAFETY_COUNTERS,
    }


def _validate_publishable_manifest(
    manifest: Mapping[str, Any],
    *,
    namespace_dir: Path,
    namespace: str,
    checked_at: datetime,
) -> None:
    expected = {
        "contract_version": CONTRACT_VERSION,
        "status": "complete",
        "profile": DEFAULT_PROFILE,
        "artifact_namespace": namespace,
        "run_mode": "burn_in",
        "data_mode": "live",
        "provider": "coingecko",
        "live_provider_authorized": True,
        "fixture_mode": False,
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        "pointer_published": False,
        **_SAFETY_COUNTERS,
    }
    mismatches = [key for key, value in expected.items() if manifest.get(key) != value]
    if mismatches:
        raise MarketNoSendError(
            "market generation provenance is not publishable (" + ",".join(mismatches[:6]) + ")"
        )
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise MarketNoSendError("market generation provenance has no exact run id")
    observed = _parse_time(manifest.get("observed_at"))
    if observed is None or observed.tzinfo is None:
        raise MarketNoSendError("market generation provenance has an invalid observation clock")
    observed = _as_utc(observed)
    if observed > checked_at + timedelta(minutes=5):
        raise MarketNoSendError("market generation provenance is future-dated")
    max_age = max(0.25, float(config.EVENT_ALPHA_MAX_RUN_AGE_HOURS))
    if checked_at - observed > timedelta(hours=max_age):
        raise MarketNoSendError("market generation provenance is stale")
    request_name = manifest.get("request_cache_artifact")
    if request_name != REQUEST_CACHE_FILENAME:
        raise MarketNoSendError("market generation request-cache lineage is invalid")
    request_path = namespace_dir / REQUEST_CACHE_FILENAME
    request = _read_json_object(request_path)
    request_expected = {
        "contract_version": CONTRACT_VERSION,
        "artifact_namespace": namespace,
        "run_id": run_id,
        "data_mode": "live",
        "provider": "coingecko",
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **_SAFETY_COUNTERS,
    }
    request_mismatches = [
        key for key, value in request_expected.items() if request.get(key) != value
    ]
    if request_mismatches:
        raise MarketNoSendError("market request-cache provenance is not publishable")
    digest = hashlib.sha256(_read_regular_bytes(request_path)).hexdigest()
    if manifest.get("request_cache_sha256") != digest:
        raise MarketNoSendError("market request-cache fingerprint drifted")
    _validate_operator_market_provenance(
        namespace_dir,
        manifest=manifest,
    )


def _validate_operator_market_provenance(
    namespace_dir: Path,
    *,
    manifest: Mapping[str, Any],
) -> None:
    loaded = operator_state.load_operator_state(namespace_dir)
    state = dict(loaded.state or {}) if loaded.valid else {}
    expected_identity = {
        "run_id": manifest.get("run_id"),
        "profile": DEFAULT_PROFILE,
        "artifact_namespace": manifest.get("artifact_namespace"),
        "run_mode": "burn_in",
    }
    if any(state.get(field) != value for field, value in expected_identity.items()):
        raise MarketNoSendError("operator state identity does not match the live generation")
    provenance = state.get("market_no_send_provenance")
    expected = {
        "contract_version": CONTRACT_VERSION,
        "data_mode": "live",
        "provider": "coingecko",
        "observed_at": manifest.get("observed_at"),
        "request_cache_artifact": REQUEST_CACHE_FILENAME,
        "contract_counted_status": "counted",
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **_SAFETY_COUNTERS,
    }
    if not isinstance(provenance, Mapping) or dict(provenance) != expected:
        raise MarketNoSendError("operator market provenance does not match the live generation")


def _normalized_explicit_market_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = {
        key: row.get(key)
        for key in (
            "price",
            "current_price",
            "return_1h",
            "return_4h",
            "return_24h",
            "return_72h",
            "return_7d",
            "relative_return_vs_btc_1h",
            "relative_return_vs_btc_4h",
            "relative_return_vs_btc_24h",
            "relative_return_vs_eth_1h",
            "relative_return_vs_eth_4h",
            "relative_return_vs_eth_24h",
            "return_unit",
        )
        if row.get(key) is not None
    }
    out["price"] = out.pop("current_price", out.get("price", None))
    out.setdefault("return_unit", "fraction")
    out["coin_id"] = str(row.get("coin_id") or row.get("id") or "")
    out["symbol"] = str(row.get("symbol") or "").upper()
    return out


def _cross_sectional_turnover_zscores(rows: Sequence[Mapping[str, Any]]) -> dict[int, float]:
    values: dict[int, float] = {}
    for index, row in enumerate(rows):
        volume = _finite_float(row.get("total_volume") or row.get("volume_24h"))
        market_cap = _finite_float(row.get("market_cap"))
        if volume is None or market_cap is None or volume < 0 or market_cap <= 0:
            continue
        values[index] = math.log1p(volume / market_cap)
    if len(values) < 3:
        return {index: 0.0 for index in values}
    mean = sum(values.values()) / len(values)
    variance = sum((value - mean) ** 2 for value in values.values()) / len(values)
    stddev = math.sqrt(variance)
    if stddev <= 1e-12:
        return {index: 0.0 for index in values}
    return {index: round((value - mean) / stddev, 4) for index, value in values.items()}


def _decision_route_counts(path: str | Path) -> Counter[str]:
    return Counter(
        str(
            row.get("radar_route")
            or row.get("decision_route")
            or row.get("actionability_route")
            or "diagnostic"
        )
        for row in _read_jsonl(Path(path))
    )


def _liquid_rank(row: Mapping[str, Any]) -> tuple[float, float, float]:
    return (
        _finite_float(row.get("total_volume") or row.get("volume_24h")) or 0.0,
        _finite_float(row.get("liquidity_usd")) or 0.0,
        _finite_float(row.get("market_cap")) or 0.0,
    )


def _has_explicit_return_fields(row: Mapping[str, Any]) -> bool:
    return any(row.get(key) is not None for key in ("return_1h", "return_4h", "return_24h"))


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


def _validated_namespace(value: str) -> str:
    namespace = str(value or "").strip()
    if not _NAMESPACE_RE.fullmatch(namespace) or namespace in {".", ".."}:
        raise MarketNoSendError("invalid market no-send artifact namespace")
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


def _finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


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


def _smoke_rows() -> tuple[dict[str, Any], ...]:
    return (
        {"id": "bitcoin", "coin_id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "price": 65000, "return_unit": "fraction", "return_1h": 0.0005, "return_4h": 0.001, "return_24h": 0.002, "market_cap": 1_200_000_000_000, "total_volume": 30_000_000_000, "volume_zscore_24h": 0.0, "liquidity_usd": 5_000_000_000, "spread_bps": 2},
        {"id": "ethereum", "coin_id": "ethereum", "symbol": "ETH", "name": "Ethereum", "price": 3200, "return_unit": "fraction", "return_1h": 0.001, "return_4h": 0.002, "return_24h": 0.004, "market_cap": 400_000_000_000, "total_volume": 15_000_000_000, "volume_zscore_24h": 0.2, "liquidity_usd": 2_000_000_000, "spread_bps": 3},
        {"id": "market-flow", "coin_id": "market-flow", "symbol": "MKTFLOW", "name": "Market Flow", "price": 1.2, "return_unit": "fraction", "return_1h": 0.04, "return_4h": 0.10, "return_24h": 0.16, "market_cap": 90_000_000, "total_volume": 24_000_000, "volume_zscore_24h": 3.4, "liquidity_usd": 24_000_000, "spread_bps": 16},
        {"id": "market-flow-no-spread", "coin_id": "market-flow-no-spread", "symbol": "MKTNOSPREAD", "name": "Market Flow No Spread", "price": 2.2, "return_unit": "fraction", "return_1h": 0.035, "return_4h": 0.09, "return_24h": 0.15, "market_cap": 120_000_000, "total_volume": 20_000_000, "volume_zscore_24h": 3.1, "liquidity_usd": 18_000_000},
        {"id": "market-flow-low", "coin_id": "market-flow-low", "symbol": "MKTLOW", "name": "Market Flow Low", "price": 0.001, "return_unit": "fraction", "return_1h": 0.09, "return_4h": 0.25, "return_24h": 0.55, "market_cap": 12_000_000, "total_volume": 300_000, "volume_zscore_24h": 4.5, "liquidity_usd": 18_000, "spread_bps": 320},
    )


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
    "build_market_no_send_readiness",
    "main",
    "normalize_market_rows",
    "publish_market_no_send_generation",
    "run_market_no_send_generation",
)
