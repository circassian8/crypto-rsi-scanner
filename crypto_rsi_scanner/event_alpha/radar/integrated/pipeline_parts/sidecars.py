"""Sidecars helpers for integrated radar."""

from __future__ import annotations

from .runtime import *


def _load_rsi_signal_context_rows(path: Path | None) -> tuple[dict[str, Any], ...]:
    """Read an explicitly configured local RSI export without touching SQLite."""

    if path is None:
        return ()
    target = Path(path).expanduser()
    try:
        if target.suffix.casefold() == ".jsonl":
            rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            payload = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                nested = next(
                    (
                        payload.get(field)
                        for field in ("signals", "rows", "items")
                        if isinstance(payload.get(field), list)
                    ),
                    None,
                )
                rows = nested if nested is not None else [payload]
            else:
                rows = payload
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ()
    if not isinstance(rows, list):
        return ()
    return tuple(dict(row) for row in rows[:500] if isinstance(row, Mapping))

def _derivatives_manifest_mode(namespace_dir: Path, derivatives_rows: tuple[dict[str, Any], ...]) -> tuple[str, bool, tuple[str, ...]]:
    from ....providers import coinalyze_preflight as event_coinalyze_preflight

    rehearsal_path = namespace_dir / event_coinalyze_preflight.REHEARSAL_JSON
    state_path = namespace_dir / event_derivatives_crowding.DERIVATIVES_STATE_FILENAME
    if derivatives_rows:
        return "loaded_existing", True, ()
    if not rehearsal_path.exists():
        return "skipped_missing_config", False, ("derivatives sidecar artifact missing or empty",)
    try:
        payload = json.loads(rehearsal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    status = str(payload.get("status") or "unknown") if isinstance(payload, Mapping) else "unknown"
    if status == "missing_config":
        return "skipped_missing_config", False, ("coinalyze rehearsal missing_config",)
    if status == "live_call_blocked_by_default":
        return "live_blocked_by_default", True, ("coinalyze live call blocked by default",)
    if state_path.exists():
        return "loaded_existing", True, (f"coinalyze rehearsal status={status}",)
    return "skipped_missing_config", False, (f"coinalyze rehearsal status={status} without derivatives state",)

def _with_coinalyze_sidecar(
    rows: Mapping[str, tuple[dict[str, Any], ...]],
    manifest: Iterable[Mapping[str, Any]],
    *,
    namespace_dir: Path,
    coinalyze_namespace: str | None,
    observed_at: datetime,
) -> tuple[dict[str, tuple[dict[str, Any], ...]], tuple[dict[str, Any], ...]]:
    bundle_rows, bundle_manifest = _load_external_coinalyze_artifacts(
        namespace_dir=namespace_dir,
        coinalyze_namespace=coinalyze_namespace,
        observed_at=observed_at,
    )
    combined = dict(rows)
    combined.update(bundle_rows)
    return combined, (*tuple(dict(item) for item in manifest if isinstance(item, Mapping)), bundle_manifest)

def _load_external_coinalyze_artifacts(
    *,
    namespace_dir: Path,
    coinalyze_namespace: str | None,
    observed_at: datetime,
) -> tuple[dict[str, tuple[dict[str, Any], ...]], dict[str, Any]]:
    selected_namespace, selection_mode, selection_warning = _select_coinalyze_namespace(
        namespace_dir,
        coinalyze_namespace=coinalyze_namespace,
    )
    empty_rows = {
        "coinalyze_derivatives_state": (),
        "coinalyze_derivatives_crowding": (),
        "coinalyze_fade_review": (),
    }
    if not selected_namespace:
        warnings = ("coinalyze_artifact_namespace_not_configured",)
        if selection_warning:
            warnings = (*warnings, selection_warning)
        return empty_rows, _coinalyze_manifest_item(
            namespace_dir=namespace_dir,
            coinalyze_namespace=None,
            coinalyze_dir=None,
            mode="skipped_missing_config",
            configured=False,
            observed_at=observed_at,
            warnings=warnings,
            skip_reason="coinalyze_artifact_namespace_not_configured",
            selection_mode=selection_mode,
        )

    coinalyze_dir = _resolve_sibling_namespace_dir(namespace_dir, selected_namespace)
    if coinalyze_dir is None:
        return empty_rows, _coinalyze_manifest_item(
            namespace_dir=namespace_dir,
            coinalyze_namespace=selected_namespace,
            coinalyze_dir=None,
            mode="skipped_invalid_namespace",
            configured=True,
            observed_at=observed_at,
            warnings=("coinalyze_artifact_namespace_invalid",),
            skip_reason="coinalyze_artifact_namespace_invalid",
            selection_mode=selection_mode,
        )

    namespace_status = event_alpha_namespace_status.load_namespace_status(coinalyze_dir)
    if event_alpha_namespace_status.is_stale_deprecated(namespace_status):
        return empty_rows, _coinalyze_manifest_item(
            namespace_dir=namespace_dir,
            coinalyze_namespace=selected_namespace,
            coinalyze_dir=coinalyze_dir,
            mode="skipped_stale_namespace",
            configured=True,
            observed_at=observed_at,
            warnings=("coinalyze_namespace_stale_deprecated",),
            skip_reason="coinalyze_namespace_stale_deprecated",
            provider_health_status=_coinalyze_rehearsal_value(coinalyze_dir, "provider_health_status") or "not_observed",
            namespace_status=namespace_status.status if namespace_status else "active",
            selection_mode=selection_mode,
        )

    state_rows = tuple(
        _annotate_coinalyze_state_row(row, namespace=selected_namespace, coinalyze_dir=coinalyze_dir)
        for row in event_derivatives_crowding.load_derivatives_state(coinalyze_dir)
    )
    crowding_rows = tuple(
        _annotate_coinalyze_candidate_row(row, namespace=selected_namespace, coinalyze_dir=coinalyze_dir, sidecar="coinalyze_derivatives_crowding")
        for row in event_derivatives_crowding.load_derivatives_candidates(coinalyze_dir)
    )
    fade_rows = tuple(
        _annotate_coinalyze_candidate_row(row, namespace=selected_namespace, coinalyze_dir=coinalyze_dir, sidecar="coinalyze_fade_review")
        for row in event_derivatives_crowding.load_fade_review_candidates(coinalyze_dir)
    )
    provider_health = _coinalyze_rehearsal_value(coinalyze_dir, "provider_health_status") or "not_observed"
    freshness = _coinalyze_freshness_status(state_rows)
    warnings: list[str] = []
    if selection_warning:
        warnings.append(selection_warning)
    if freshness in {"stale", "expired", "unknown"}:
        warnings.append(f"coinalyze_freshness_{freshness}")
    if not (state_rows or crowding_rows or fade_rows):
        warnings.append("coinalyze_artifacts_missing_or_empty")
    mode = "loaded_external_coinalyze" if (state_rows or crowding_rows or fade_rows) else "skipped_missing_artifact"
    skip_reason = None if mode == "loaded_external_coinalyze" else "coinalyze_artifacts_missing_or_empty"
    return {
        "coinalyze_derivatives_state": state_rows,
        "coinalyze_derivatives_crowding": crowding_rows,
        "coinalyze_fade_review": fade_rows,
    }, _coinalyze_manifest_item(
        namespace_dir=namespace_dir,
        coinalyze_namespace=selected_namespace,
        coinalyze_dir=coinalyze_dir,
        mode=mode,
        configured=True,
        observed_at=observed_at,
        rows=(*state_rows, *crowding_rows, *fade_rows),
        warnings=warnings,
        skip_reason=skip_reason,
        provider_health_status=provider_health,
        freshness_status=freshness,
        state_rows_loaded=len(state_rows),
        crowding_rows_loaded=len(crowding_rows),
        fade_rows_loaded=len(fade_rows),
        namespace_status=namespace_status.status if namespace_status else "active",
        selection_mode=selection_mode,
    )

def _select_coinalyze_namespace(namespace_dir: Path, *, coinalyze_namespace: str | None) -> tuple[str | None, str, str | None]:
    requested = str(coinalyze_namespace or "").strip()
    if requested and requested.casefold() not in {"none", "false", "0", "off"}:
        return requested, "explicit", None
    readiness_namespace = _coinalyze_namespace_from_readiness(namespace_dir)
    if readiness_namespace:
        return readiness_namespace, "readiness_auto", None
    default_dir = namespace_dir.parent / event_coinalyze_preflight.DEFAULT_REHEARSAL_NAMESPACE
    if default_dir.exists():
        return event_coinalyze_preflight.DEFAULT_REHEARSAL_NAMESPACE, "default_rehearsal_auto", None
    return None, "auto_none", "coinalyze_readiness_namespace_not_found"

def _coinalyze_namespace_from_readiness(namespace_dir: Path) -> str | None:
    path = namespace_dir / event_live_provider_readiness.READINESS_JSON
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    providers = payload.get("providers") if isinstance(payload, Mapping) else None
    if not isinstance(providers, Iterable) or isinstance(providers, (str, bytes, Mapping)):
        return None
    for provider in providers:
        if not isinstance(provider, Mapping) or str(provider.get("provider_name") or "").casefold() != "coinalyze":
            continue
        for key in ("coinalyze_artifact_namespace", "latest_rehearsal_artifact_namespace"):
            namespace = _safe_namespace_text(provider.get(key))
            if namespace:
                return namespace
        for key in ("latest_request_ledger_path", "request_ledger_path"):
            namespace = _namespace_from_artifact_path_label(provider.get(key))
            if namespace:
                return namespace
        command = str(provider.get("no_send_rehearsal_command") or "")
        match = re.search(r"(?:ARTIFACT_NAMESPACE=|--event-alpha-artifact-namespace\s+)([A-Za-z0-9_.-]+)", command)
        if match:
            return match.group(1)
    return None

def _safe_namespace_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    candidate = Path(text)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts) or len(candidate.parts) != 1:
        return None
    return text

def _namespace_from_artifact_path_label(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = Path(text).parts
    for filename in (
        event_coinalyze_preflight.REQUEST_LEDGER,
        event_coinalyze_preflight.REHEARSAL_JSON,
        event_derivatives_crowding.DERIVATIVES_STATE_FILENAME,
    ):
        if filename in parts:
            index = parts.index(filename)
            if index > 0:
                return _safe_namespace_text(parts[index - 1])
    return None

def _resolve_sibling_namespace_dir(namespace_dir: Path, namespace: str) -> Path | None:
    text = str(namespace or "").strip()
    if not text:
        return None
    candidate = Path(text)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        return None
    if len(candidate.parts) != 1:
        return None
    return namespace_dir.parent / text

def _coinalyze_manifest_item(
    *,
    namespace_dir: Path,
    coinalyze_namespace: str | None,
    coinalyze_dir: Path | None,
    mode: str,
    configured: bool,
    observed_at: datetime,
    rows: Iterable[Mapping[str, Any]] = (),
    warnings: Iterable[str] = (),
    skip_reason: str | None = None,
    provider_health_status: str = "not_observed",
    freshness_status: str = "missing",
    state_rows_loaded: int = 0,
    crowding_rows_loaded: int = 0,
    fade_rows_loaded: int = 0,
    namespace_status: str = "active",
    selection_mode: str = "auto_none",
) -> dict[str, Any]:
    row = _manifest_item(
        sidecar_name="coinalyze",
        mode=mode,
        namespace_dir=coinalyze_dir or namespace_dir,
        rows=tuple(rows),
        configured=configured,
        sidecar_research_observed_at=observed_at,
        wall_started_at=datetime.now(timezone.utc),
        wall_finished_at=datetime.now(timezone.utc),
        warnings=warnings,
    )
    state_path = (coinalyze_dir / event_derivatives_crowding.DERIVATIVES_STATE_FILENAME) if coinalyze_dir else None
    crowding_path = (coinalyze_dir / event_derivatives_crowding.DERIVATIVES_CROWDING_CANDIDATES_FILENAME) if coinalyze_dir else None
    fade_path = (coinalyze_dir / event_derivatives_crowding.FADE_SHORT_REVIEW_CANDIDATES_FILENAME) if coinalyze_dir else None
    row.update({
        "coinalyze_artifact_namespace": coinalyze_namespace,
        "coinalyze_artifact_namespace_status": namespace_status,
        "coinalyze_artifact_selection_mode": selection_mode,
        "coinalyze_derivatives_state_path": event_artifact_paths.artifact_display_path(state_path) if state_path else None,
        "coinalyze_crowding_candidates_path": event_artifact_paths.artifact_display_path(crowding_path) if crowding_path else None,
        "coinalyze_fade_review_candidates_path": event_artifact_paths.artifact_display_path(fade_path) if fade_path else None,
        "coinalyze_derivatives_state_rows_loaded": int(state_rows_loaded),
        "coinalyze_crowding_candidates_loaded": int(crowding_rows_loaded),
        "coinalyze_fade_review_candidates_loaded": int(fade_rows_loaded),
        "coinalyze_provider_health_status": provider_health_status,
        "coinalyze_freshness_status": freshness_status,
        "coinalyze_skip_reason": skip_reason,
    })
    return row

def _coinalyze_rehearsal_value(coinalyze_dir: Path, key: str) -> str | None:
    try:
        payload = json.loads((coinalyze_dir / event_coinalyze_preflight.REHEARSAL_JSON).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    value = payload.get(key)
    return str(value) if value not in (None, "") else None

def _annotate_coinalyze_state_row(row: Mapping[str, Any], *, namespace: str, coinalyze_dir: Path) -> dict[str, Any]:
    out = dict(row)
    out.update({
        "coinalyze_artifact_namespace": namespace,
        "coinalyze_source_artifact_path": event_artifact_paths.artifact_display_path(coinalyze_dir / event_derivatives_crowding.DERIVATIVES_STATE_FILENAME),
        "coinalyze_external_artifact_loaded": True,
        "coinalyze_provider_health_status": _coinalyze_rehearsal_value(coinalyze_dir, "provider_health_status") or "not_observed",
    })
    return out

def _annotate_coinalyze_candidate_row(row: Mapping[str, Any], *, namespace: str, coinalyze_dir: Path, sidecar: str) -> dict[str, Any]:
    out = dict(row)
    source_path = (
        coinalyze_dir / event_derivatives_crowding.FADE_SHORT_REVIEW_CANDIDATES_FILENAME
        if sidecar == "coinalyze_fade_review"
        else coinalyze_dir / event_derivatives_crowding.DERIVATIVES_CROWDING_CANDIDATES_FILENAME
    )
    state = out.get("derivatives_state_snapshot")
    if isinstance(state, Mapping):
        out["derivatives_state_snapshot"] = _annotate_coinalyze_state_row(state, namespace=namespace, coinalyze_dir=coinalyze_dir)
    out.update({
        "coinalyze_artifact_namespace": namespace,
        "coinalyze_source_artifact_path": event_artifact_paths.artifact_display_path(source_path),
        "coinalyze_external_artifact_loaded": True,
        "coinalyze_provider_health_status": _coinalyze_rehearsal_value(coinalyze_dir, "provider_health_status") or "not_observed",
    })
    return out

def _coinalyze_freshness_status(rows: Iterable[Mapping[str, Any]]) -> str:
    statuses = [
        str(row.get("derivatives_snapshot_freshness_status") or row.get("freshness_status") or "").strip().casefold()
        for row in rows
        if isinstance(row, Mapping)
    ]
    statuses = [status for status in statuses if status]
    if not statuses:
        return "missing"
    for status in ("expired", "stale", "unknown"):
        if status in statuses:
            return status
    return "fresh" if "fresh" in statuses or "fixture_allowed_stale" in statuses else statuses[0]

def _run_fixture_sidecars(
    *,
    namespace_dir: Path,
    observed_at: datetime,
    profile: str,
    artifact_namespace: str,
    run_mode: str,
    run_id: str,
) -> dict[str, tuple[dict[str, Any], ...]]:
    market = event_market_anomaly_scanner.run_market_anomaly_scan(
        market_rows=_fixture_market_rows(),
        namespace_dir=namespace_dir,
        observed_at=observed_at,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_id=run_id,
    )
    with TemporaryDirectory(prefix="event-alpha-integrated-", dir=str(namespace_dir)) as tmpdir:
        tmp = Path(tmpdir)
        binance_path = tmp / "binance.json"
        bybit_path = tmp / "bybit.json"
        tokenomist_path = tmp / "tokenomist.json"
        coinmarketcal_path = tmp / "coinmarketcal.json"
        derivatives_path = tmp / "derivatives.json"
        _write_json(binance_path, {"items": _fixture_binance_announcements()})
        _write_json(bybit_path, {"items": _fixture_bybit_announcements()})
        _write_json(tokenomist_path, {"items": _fixture_unlocks()})
        _write_json(coinmarketcal_path, {"items": _fixture_calendar_events()})
        _write_json(derivatives_path, _fixture_derivatives_payload())
        official = event_official_exchange.run_official_exchange_scan(
            namespace_dir=namespace_dir,
            provider_paths={"binance": binance_path, "bybit": bybit_path},
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
            observed_at=observed_at,
        )
        scheduled = event_scheduled_catalysts.run_scheduled_catalyst_scan(
            namespace_dir=namespace_dir,
            provider_paths={"tokenomist": tokenomist_path, "coinmarketcal": coinmarketcal_path},
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
            observed_at=observed_at,
        )
        derivatives = event_derivatives_crowding.run_derivatives_crowding_scan(
            namespace_dir=namespace_dir,
            derivatives_path=derivatives_path,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
            observed_at=observed_at,
        )
        dex_onchain = event_dex_onchain_readiness.run_dex_onchain_readiness(
            namespace_dir=namespace_dir,
            profile=profile,
            artifact_namespace=artifact_namespace,
            geckoterminal_path=config.EVENT_ALPHA_DEX_GECKOTERMINAL_PATH,
            coingecko_dex_path=config.EVENT_ALPHA_DEX_COINGECKO_PATH,
            defillama_path=config.EVENT_ALPHA_PROTOCOL_DEFILLAMA_PATH,
            smoke_mode=True,
            now=observed_at,
        )
    return {
        "market_anomaly": market.anomalies,
        "official_exchange": _official_exchange_integration_rows(official.events, official.candidates),
        "scheduled_catalyst": scheduled.scheduled_events,
        "unlock": scheduled.unlock_candidates,
        "derivatives": derivatives.candidate_rows,
        "dex_pool_state": dex_onchain.dex_pool_state_rows,
        "dex_pool_anomaly": dex_onchain.dex_pool_anomaly_rows,
        "protocol_fundamentals": dex_onchain.protocol_fundamental_rows,
    }

def _fixture_market_rows() -> tuple[dict[str, Any], ...]:
    return (
        {"symbol": "BTC", "coin_id": "bitcoin", "price": 65000, "return_unit": "fraction", "return_1h": 0.0, "return_4h": 0.0, "return_24h": 0.0, "volume_zscore_24h": 0.0, "liquidity_usd": 5_000_000_000},
        {"symbol": "ETH", "coin_id": "ethereum", "price": 3200, "return_unit": "fraction", "return_1h": 0.001, "return_4h": 0.002, "return_24h": 0.004, "volume_zscore_24h": 0.2, "liquidity_usd": 2_000_000_000},
        {
            "symbol": "TESTFLOW",
            "coin_id": "test-flow",
            "price": 1.2,
            "return_unit": "fraction",
            "return_1h": 0.04,
            "return_4h": 0.10,
            "return_24h": 0.16,
            "relative_return_vs_btc_4h": 0.10,
            "relative_return_vs_eth_4h": 0.098,
            "volume_zscore_24h": 3.4,
            "volume_to_market_cap": 0.28,
            "liquidity_usd": 24_000_000,
            "spread_bps": 16,
            "freshness_status": "fresh",
        },
        {
            "symbol": "TESTFLOWLOW",
            "coin_id": "test-flow-low",
            "price": 0.001,
            "return_unit": "fraction",
            "return_1h": 0.09,
            "return_4h": 0.25,
            "return_24h": 0.55,
            "relative_return_vs_btc_4h": 0.25,
            "relative_return_vs_eth_4h": 0.248,
            "volume_zscore_24h": 4.5,
            "volume_to_market_cap": 0.50,
            "liquidity_usd": 18_000,
            "spread_bps": 320,
            "freshness_status": "fresh",
        },
        {"symbol": "TESTPERP", "coin_id": "test-perp", "price": 2.4, "return_unit": "fraction", "return_1h": 0.035, "return_4h": 0.11, "return_24h": 0.18, "relative_return_vs_btc_4h": 0.10, "volume_zscore_24h": 3.4, "volume_to_market_cap": 0.32, "liquidity_usd": 18_000_000, "spread_bps": 18},
        {"symbol": "TESTFADE", "coin_id": "test-fade", "price": 5.2, "return_unit": "fraction", "return_1h": 0.06, "return_4h": 0.21, "return_24h": 0.42, "volume_zscore_24h": 4.8, "volume_to_market_cap": 0.45, "liquidity_usd": 3_500_000, "spread_bps": 42, "event_age_hours": 3},
        {"symbol": "TESTRUMOR", "coin_id": "test-rumor", "price": 0.5, "return_unit": "fraction", "return_1h": 0.002, "return_4h": 0.004, "return_24h": 0.01, "volume_zscore_24h": 0.4, "liquidity_usd": 1_200_000, "spread_bps": 55},
    )

def _fixture_binance_announcements() -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "binance-testlist",
            "title": "Binance Will List TestList (TESTLIST)",
            "body": "Binance will open spot trading for TESTLIST/USDT.",
            "symbols": ["TESTLIST"],
            "coin_ids": ["test-list"],
            "source_url": "https://www.binance.com/en/support/announcement/testlist",
            "published_at": "2026-06-15T13:00:00Z",
            "effective_time": "2026-06-15T19:00:00Z",
            "market_snapshot": {"return_unit": "fraction", "return_24h": 0.01, "volume_zscore_24h": 0.2, "event_age_hours": -3},
        },
        {
            "id": "binance-testfade",
            "title": "Binance Lists TestFade (TESTFADE)",
            "body": "Binance opened spot trading for TESTFADE/USDT.",
            "symbols": ["TESTFADE"],
            "coin_ids": ["test-fade"],
            "source_url": "https://www.binance.com/en/support/announcement/testfade",
            "published_at": "2026-06-14T12:00:00Z",
            "effective_time": "2026-06-15T13:00:00Z",
            "market_snapshot": {"return_unit": "fraction", "return_4h": 0.21, "return_24h": 0.42, "volume_zscore_24h": 4.8, "event_age_hours": 3, "liquidity_usd": 3_500_000, "spread_bps": 42},
        },
        {
            "id": "binance-btc-pair",
            "title": "Binance Adds BTC/USDT as a New Trading Pair",
            "body": "Binance adds a simple BTC/USDT trading pair.",
            "symbols": ["BTC"],
            "coin_ids": ["bitcoin"],
            "source_url": "https://www.binance.com/en/support/announcement/btcusdt",
            "published_at": "2026-06-15T13:10:00Z",
            "market_snapshot": {"return_unit": "fraction", "return_24h": 0.002, "volume_zscore_24h": 0.1},
        },
    )

def _fixture_bybit_announcements() -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "bybit-testperp",
            "title": "Bybit Lists TESTPERPUSDT Perpetual Contract",
            "body": "Bybit will launch TESTPERPUSDT perpetual futures.",
            "symbols": ["TESTPERP"],
            "coin_ids": ["test-perp"],
            "source_url": "https://announcements.bybit.com/article/testperp",
            "published_at": "2026-06-15T14:00:00Z",
            "effective_time": "2026-06-15T16:30:00Z",
            "market_snapshot": {"return_unit": "fraction", "return_4h": 0.11, "return_24h": 0.18, "volume_zscore_24h": 3.4, "relative_return_vs_btc": 0.10, "liquidity_usd": 18_000_000, "spread_bps": 18},
        },
    )

def _fixture_unlocks() -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "tokenomist-testunlock",
            "title": "TESTUNLOCK cliff unlock",
            "symbol": "TESTUNLOCK",
            "coin_id": "test-unlock",
            "source_url": "https://tokenomist.ai/testunlock",
            "unlock_time": "2026-06-16T08:00:00Z",
            "unlock_pct_circulating_supply": 14.0,
            "unlock_vs_30d_adv": 2.6,
            "unlock_usd": 12_000_000,
            "market_snapshot": {"return_unit": "fraction", "return_24h": -0.01, "volume_zscore_24h": 0.4, "event_age_hours": -16, "liquidity_usd": 650_000, "spread_bps": 80},
        },
    )

def _fixture_calendar_events() -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "coinmarketcal-rumor",
            "title": "TESTRUMOR rumored partnership AMA",
            "description": "Social rumor and calendar mention without official confirmation.",
            "symbol": "TESTRUMOR",
            "coin_id": "test-rumor",
            "source_class": "cryptopanic_tagged",
            "source_url": "https://cryptopanic.com/news/test-rumor",
            "event_time": "2026-06-17T12:00:00Z",
            "market_snapshot": {"return_unit": "fraction", "return_24h": 0.01, "volume_zscore_24h": 0.4, "event_age_hours": -44},
        },
        {
            "id": "sector-ai-theme",
            "title": "AI sector narrative heats up",
            "description": "Broad theme row for diagnostics only.",
            "symbol": "SECTOR",
            "coin_id": "ai_theme",
            "source_class": "broad_news",
            "source_url": "https://example.com/ai-sector",
            "event_time": "2026-06-17T12:00:00Z",
        },
    )

def _fixture_derivatives_payload() -> dict[str, Any]:
    return {
        "derivatives": [
            {"symbol": "TESTFADEUSDT", "coin_id": "test-fade", "open_interest_delta_24h": 0.52, "funding_rate": 0.12, "funding_zscore": 3.2, "liquidation_long_usd": 2_800_000, "liquidation_short_usd": 500_000, "perp_volume": 90_000_000, "spot_volume": 30_000_000, "freshness_status": "fresh"},
            {"symbol": "TESTPERPUSDT", "coin_id": "test-perp", "open_interest_delta_24h": 0.06, "funding_rate": 0.01, "funding_zscore": 0.2, "liquidation_long_usd": 120_000, "liquidation_short_usd": 90_000, "perp_volume": 12_000_000, "spot_volume": 10_000_000, "freshness_status": "fresh"},
        ],
        "candidates": [
            {"symbol": "TESTFADE", "coin_id": "test-fade", "event_name": "TESTFADE listing blowoff", "source_class": "official_exchange", "source_pack": "listing_liquidity_pack", "impact_path_type": "listing_liquidity_event", "evidence_quality_score": 92, "accepted_evidence_count": 1, "market_snapshot": {"return_unit": "fraction", "return_4h": 0.21, "return_24h": 0.42, "volume_zscore_24h": 4.8, "volume_to_market_cap": 0.45, "liquidity_usd": 3_500_000, "spread_bps": 42, "event_age_hours": 3}},
            {"symbol": "TESTPERP", "coin_id": "test-perp", "event_name": "TESTPERP perp breakout", "source_class": "official_exchange", "source_pack": "perp_listing_squeeze_pack", "impact_path_type": "listing_liquidity_event", "evidence_quality_score": 92, "accepted_evidence_count": 1, "market_snapshot": {"return_unit": "fraction", "return_4h": 0.11, "return_24h": 0.18, "volume_zscore_24h": 3.4, "relative_return_vs_btc": 0.10, "liquidity_usd": 18_000_000, "spread_bps": 18, "event_age_hours": -1}},
        ],
    }

def _clear_namespace(namespace_dir: Path) -> None:
    if namespace_dir.exists():
        shutil.rmtree(namespace_dir)

def _sidecar_artifact_paths(namespace_dir: Path, sidecar_name: str) -> tuple[Path, ...]:
    mapping = {
        "market_anomaly": ("event_market_state_snapshots.jsonl", "event_market_anomalies.jsonl"),
        "official_exchange": ("event_official_exchange_events.jsonl", "event_official_listing_candidates.jsonl"),
        "scheduled_catalyst": ("event_scheduled_catalysts.jsonl",),
        "unlock": ("event_unlock_candidates.jsonl",),
        "derivatives": ("event_derivatives_state.jsonl", "event_derivatives_crowding_candidates.jsonl", "event_fade_short_review_candidates.jsonl"),
        "dex_pool_state": (event_dex_onchain_readiness.DEX_POOL_STATE_FILENAME,),
        "dex_pool_anomaly": (event_dex_onchain_readiness.DEX_POOL_ANOMALIES_FILENAME,),
        "protocol_fundamentals": (event_dex_onchain_readiness.PROTOCOL_FUNDAMENTALS_FILENAME,),
    }
    return tuple(namespace_dir / name for name in mapping.get(sidecar_name, ()))

def _sidecar_count_summary(sidecars: Mapping[str, Iterable[Mapping[str, Any]]]) -> dict[str, int]:
    market_rows = list(sidecars.get("market_anomaly", ()))
    official_rows = list(sidecars.get("official_exchange", ()))
    derivatives_rows = list(sidecars.get("derivatives", ()))
    coinalyze_state_rows = list(sidecars.get("coinalyze_derivatives_state", ()))
    coinalyze_crowding_rows = list(sidecars.get("coinalyze_derivatives_crowding", ()))
    coinalyze_fade_rows = list(sidecars.get("coinalyze_fade_review", ()))
    dex_pool_state_rows = list(sidecars.get("dex_pool_state", ()))
    dex_pool_anomaly_rows = list(sidecars.get("dex_pool_anomaly", ()))
    protocol_fundamental_rows = list(sidecars.get("protocol_fundamentals", ()))
    all_derivative_candidates = [*derivatives_rows, *coinalyze_crowding_rows, *coinalyze_fade_rows]
    return {
        "market_anomalies": len(market_rows),
        "market_state_snapshots": len(market_rows),
        "official_exchange_events": sum(
            1 for row in official_rows
            if str(row.get("row_type") or "") in {"official_exchange_event", "official_exchange_event_candidate"}
            or isinstance(row.get("official_exchange_event"), Mapping)
            or row.get("official_exchange_event_id")
            or row.get("source_event_id")
            or row.get("event_id")
        ),
        "official_listing_candidates": sum(1 for row in official_rows if str(row.get("row_type") or "") in {"official_listing_candidate", "official_exchange_event_candidate"}),
        "scheduled_catalysts": len(tuple(sidecars.get("scheduled_catalyst", ()))),
        "unlock_candidates": len(tuple(sidecars.get("unlock", ()))),
        "derivatives_state_rows": sum(
            1 for row in derivatives_rows
            if str(row.get("row_type") or "") == "derivatives_state_snapshot"
            or isinstance(row.get("derivatives_state_snapshot"), Mapping)
        ) + len(coinalyze_state_rows),
        "derivatives_crowding_candidates": len(derivatives_rows) + len(coinalyze_crowding_rows),
        "fade_review_candidates": sum(
            1 for row in all_derivative_candidates
            if str(row.get("opportunity_type") or "") == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value
        ),
        "dex_pool_state_rows": len(dex_pool_state_rows),
        "dex_pool_anomaly_rows": len(dex_pool_anomaly_rows),
        "protocol_fundamental_rows": len(protocol_fundamental_rows),
    }

def _first_value(rows: list[Mapping[str, Any]], *keys: str) -> Any:
    for row in rows:
        for key in keys:
            value = row.get(key)
            if value not in (None, "", [], {}):
                return value
    return None

def _best_text(rows: list[Mapping[str, Any]], *keys: str) -> str | None:
    value = _first_value(rows, *keys)
    text = _text(value)
    return text or None

def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            stamped = schema_v1.stamp_artifact_row(row, path=path)
            handle.write(json.dumps(_json_ready(stamped), sort_keys=True, separators=(",", ":")) + "\n")

def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows

def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamped = schema_v1.stamp_artifact_payload(payload, path=path)
    path.write_text(json.dumps(_json_ready(stamped), sort_keys=True), encoding="utf-8")

__all__ = (
    '_derivatives_manifest_mode',
    '_with_coinalyze_sidecar',
    '_load_external_coinalyze_artifacts',
    '_select_coinalyze_namespace',
    '_coinalyze_namespace_from_readiness',
    '_safe_namespace_text',
    '_namespace_from_artifact_path_label',
    '_resolve_sibling_namespace_dir',
    '_coinalyze_manifest_item',
    '_coinalyze_rehearsal_value',
    '_annotate_coinalyze_state_row',
    '_annotate_coinalyze_candidate_row',
    '_coinalyze_freshness_status',
    '_run_fixture_sidecars',
    '_fixture_market_rows',
    '_fixture_binance_announcements',
    '_fixture_bybit_announcements',
    '_fixture_unlocks',
    '_fixture_calendar_events',
    '_fixture_derivatives_payload',
    '_clear_namespace',
    '_sidecar_artifact_paths',
    '_sidecar_count_summary',
    '_first_value',
    '_best_text',
    '_write_jsonl',
    '_read_jsonl',
    '_write_json',
)
