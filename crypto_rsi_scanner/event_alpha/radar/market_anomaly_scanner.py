"""Broad market anomaly scanner for Event Alpha research artifacts.

The scanner consumes already-collected market rows and writes local research
artifacts. It deliberately does not create alert snapshots, Telegram sends,
paper trades, or event-fade triggers.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable as IterableABC
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import schema_v1
from . import asset_registry as event_asset_registry
from . import market_anomaly_receipt
from . import market_anomaly_report
from . import market_state as event_market_state


MARKET_STATE_SNAPSHOT_FILENAME = "event_market_state_snapshots.jsonl"
MARKET_ANOMALY_FILENAME = "event_market_anomalies.jsonl"
MARKET_ANOMALY_CATALYST_SEARCH_QUEUE_FILENAME = "event_market_anomaly_catalyst_search_queue.jsonl"
MARKET_ANOMALY_REPORT_FILENAME = "event_market_anomaly_report.md"
_RECEIPT_ARTIFACT_FILENAMES = (
    MARKET_STATE_SNAPSHOT_FILENAME,
    MARKET_ANOMALY_FILENAME,
    MARKET_ANOMALY_CATALYST_SEARCH_QUEUE_FILENAME,
    MARKET_ANOMALY_REPORT_FILENAME,
)

NO_REACTION = "no_reaction"
STEALTH_ACCUMULATION = "stealth_accumulation"
CONFIRMED_BREAKOUT = "confirmed_breakout"
LATE_MOMENTUM = "late_momentum"
BLOWOFF_CROWDED = "blowoff_crowded"
POST_EVENT_FADE_SETUP = "post_event_fade_setup"
RISK_OFF_SELL_PRESSURE = "risk_off_sell_pressure"
SUSPICIOUS_ILLIQUID_MOVE = "suspicious_illiquid_move"
NEEDS_CATALYST_SEARCH = "needs_catalyst_search"

HIGH_LIQUIDITY_BREAKOUT = "high_liquidity_breakout"
LOW_LIQUIDITY_SUSPICIOUS = "low_liquidity_suspicious"
LATE_MOMENTUM_NEEDS_CROWDING_CHECK = "late_momentum_needs_crowding_check"
SELLOFF_RISK = "selloff_risk"


@dataclass(frozen=True)
class MarketAnomalyScannerConfig:
    max_assets: int = 50
    confirmed_return_4h: float = 8.0
    confirmed_return_24h: float = 15.0
    confirmed_volume_zscore: float = 2.0
    confirmed_relative_btc_4h: float = 5.0
    stealth_return_4h_min: float = 2.0
    stealth_return_4h_max: float = 8.0
    stealth_relative_btc_4h: float = 3.0
    stealth_volume_zscore_min: float = 1.0
    stealth_volume_zscore_max: float = 2.5
    late_momentum_return_24h: float = 25.0
    post_event_fade_return_4h: float = -5.0
    post_event_fade_return_24h: float = -8.0
    risk_off_return_24h: float = -12.0
    suspicious_return_24h: float = 35.0
    suspicious_liquidity_usd: float = 50_000.0
    suspicious_spread_bps: float = 150.0
    high_liquidity_usd: float = 5_000_000.0
    search_deadline_hours: float = 6.0


@dataclass(frozen=True)
class MarketAnomalyScanResult:
    namespace_dir: Path
    artifact_namespace: str | None
    run_id: str | None
    namespace_device: int
    namespace_inode: int
    snapshots_path: Path
    anomalies_path: Path
    catalyst_search_queue_path: Path
    report_path: Path
    snapshot_count: int
    anomaly_count: int
    catalyst_search_queue_count: int
    snapshots: tuple[dict[str, Any], ...]
    anomalies: tuple[dict[str, Any], ...]
    catalyst_search_queue: tuple[dict[str, Any], ...]
    snapshots_sha256: str
    anomalies_sha256: str
    catalyst_search_queue_sha256: str
    report_sha256: str
    warnings: tuple[str, ...] = ()


def load_market_rows(path: str | Path) -> list[dict[str, Any]]:
    """Load fixture/cached market rows from JSON or JSONL."""
    source = Path(path).expanduser()
    if not source.exists():
        return []
    text = source.read_text(encoding="utf-8")
    if not text.strip():
        return []
    if source.suffix.lower() == ".jsonl":
        out: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, Mapping):
                out.append(dict(row))
        return out
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, Mapping):
        rows = data.get("rows") or data.get("markets") or data.get("data") or []
    else:
        rows = data
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def load_coingecko_universe_rows(path: str | Path | None) -> list[dict[str, Any]]:
    """Load cached CoinGecko-style universe rows, if configured."""
    if path is None:
        return []
    return load_market_rows(path)


def scan_market_rows(
    market_rows: Iterable[Mapping[str, Any]],
    *,
    cfg: MarketAnomalyScannerConfig | None = None,
    observed_at: datetime | str | None = None,
    asset_registry: Iterable[event_asset_registry.CanonicalAsset | Mapping[str, Any]] | None = None,
    coingecko_universe_rows: Iterable[Mapping[str, Any]] | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return snapshot rows and anomaly rows from cached/fixture market rows."""
    cfg = cfg or MarketAnomalyScannerConfig()
    rows = _enriched_market_rows(
        market_rows,
        asset_registry=asset_registry or (),
        coingecko_universe_rows=coingecko_universe_rows or (),
    )
    btc, eth = event_market_state.benchmark_rows(rows)
    snapshot_rows: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    for row in rows:
        snapshot = event_market_state.snapshot_from_market_row(
            row,
            observed_at=observed_at,
            btc_benchmark=btc,
            eth_benchmark=eth,
        )
        snapshot_payload = {
            "schema_version": 1,
            "row_type": "event_market_state_snapshot",
            "profile": profile,
            "artifact_namespace": artifact_namespace,
            "run_mode": run_mode,
            "run_id": run_id,
            **snapshot.to_dict(),
        }
        for key in (
            "asset_registry_symbol",
            "asset_registry_coin_id",
            "asset_registry_source",
            "liquidity_tier",
            "venues",
            "spot_symbols",
            "perp_symbols",
            "coinalyze_symbols",
            "bybit_symbols",
            "binance_symbols",
            "is_quote_asset",
            "quote_asset_excluded",
            "is_tradable_asset",
            "is_theme_or_sector",
            "diagnostics_reason",
            "derivatives_available",
            "market_cap",
            "market_data_quality",
            "temporal_baseline_status",
        ):
            if key not in row:
                continue
            if key == "market_cap":
                market_cap = _float(row.get(key))
                if market_cap is not None:
                    snapshot_payload[key] = market_cap
                continue
            snapshot_payload[key] = row.get(key)
        snapshot_rows.append(snapshot_payload)
        if _is_sector_or_theme(snapshot_payload):
            continue
        anomaly_type = classify_market_state(snapshot_payload, row, cfg=cfg)
        if anomaly_type == NO_REACTION:
            continue
        anomalies.append(_anomaly_row(
            snapshot_payload,
            row,
            anomaly_type,
            cfg=cfg,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
        ))
    anomalies.sort(key=lambda item: float(item.get("priority") or 0.0), reverse=True)
    if cfg.max_assets > 0:
        anomalies = anomalies[: cfg.max_assets]
    return snapshot_rows, anomalies


def classify_market_state(
    snapshot: Mapping[str, Any],
    source_row: Mapping[str, Any] | None = None,
    *,
    cfg: MarketAnomalyScannerConfig | None = None,
) -> str:
    cfg = cfg or MarketAnomalyScannerConfig()
    row = source_row or {}
    r4 = _float(snapshot.get("return_4h")) or 0.0
    r24 = _float(snapshot.get("return_24h")) or 0.0
    rel_btc_4h = _float(snapshot.get("relative_return_vs_btc_4h")) or 0.0
    volume_z = _float(snapshot.get("volume_zscore_24h")) or 0.0
    liquidity = _float(snapshot.get("liquidity_usd"))
    spread = _float(snapshot.get("spread_bps"))
    funding = _float(snapshot.get("funding_level")) or 0.0
    funding_z = _float(snapshot.get("funding_zscore")) or 0.0
    oi_delta = _float(snapshot.get("open_interest_delta")) or 0.0
    liquidation_imbalance = abs(_float(snapshot.get("liquidation_imbalance")) or 0.0)
    negative_catalyst = bool(row.get("negative_catalyst") or row.get("risk_off_catalyst"))
    event_passed = bool(row.get("event_passed") or row.get("event_has_passed") or row.get("post_event") or row.get("post_event_monitoring"))
    post_event_failure = bool(row.get("post_event_failure") or row.get("failed_reclaim") or row.get("price_below_event_vwap"))
    fade_crowding = oi_delta >= 10.0 or funding_z >= 1.5 or funding >= 0.03 or liquidation_imbalance >= 0.50 or volume_z >= 2.0

    if event_passed and fade_crowding and (post_event_failure or r4 <= cfg.post_event_fade_return_4h or r24 <= cfg.post_event_fade_return_24h):
        return POST_EVENT_FADE_SETUP
    if r24 <= cfg.risk_off_return_24h or negative_catalyst:
        return RISK_OFF_SELL_PRESSURE
    if (
        r24 >= cfg.suspicious_return_24h
        and ((liquidity is not None and liquidity < cfg.suspicious_liquidity_usd) or (spread is not None and spread >= cfg.suspicious_spread_bps))
    ):
        return SUSPICIOUS_ILLIQUID_MOVE
    crowded = oi_delta >= 25.0 or funding_z >= 2.5 or funding >= 0.05 or liquidation_imbalance >= 0.70
    if r24 >= cfg.late_momentum_return_24h and crowded:
        return BLOWOFF_CROWDED
    if (
        (r4 >= cfg.confirmed_return_4h or r24 >= cfg.confirmed_return_24h)
        and volume_z >= cfg.confirmed_volume_zscore
        and rel_btc_4h >= cfg.confirmed_relative_btc_4h
    ):
        return CONFIRMED_BREAKOUT
    if r24 >= cfg.late_momentum_return_24h:
        return LATE_MOMENTUM
    if (
        cfg.stealth_return_4h_min <= r4 < cfg.stealth_return_4h_max
        and rel_btc_4h >= cfg.stealth_relative_btc_4h
        and cfg.stealth_volume_zscore_min <= volume_z <= cfg.stealth_volume_zscore_max
    ):
        return STEALTH_ACCUMULATION
    return NO_REACTION


def run_market_anomaly_scan(
    *,
    market_rows: Iterable[Mapping[str, Any]],
    namespace_dir: str | Path,
    cfg: MarketAnomalyScannerConfig | None = None,
    observed_at: datetime | str | None = None,
    asset_registry: Iterable[event_asset_registry.CanonicalAsset | Mapping[str, Any]] | None = None,
    coingecko_universe_rows: Iterable[Mapping[str, Any]] | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
) -> MarketAnomalyScanResult:
    """Scan rows and write research-only market anomaly artifacts."""
    directory = Path(namespace_dir).expanduser()
    snapshots, anomalies = scan_market_rows(
        market_rows,
        cfg=cfg,
        observed_at=observed_at,
        asset_registry=asset_registry,
        coingecko_universe_rows=coingecko_universe_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_id=run_id,
    )
    catalyst_search_queue = build_catalyst_search_queue(
        anomalies,
        cfg=cfg,
        observed_at=observed_at,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_id=run_id,
    )
    snapshots_path = directory / MARKET_STATE_SNAPSHOT_FILENAME
    anomalies_path = directory / MARKET_ANOMALY_FILENAME
    catalyst_search_queue_path = directory / MARKET_ANOMALY_CATALYST_SEARCH_QUEUE_FILENAME
    report_path = directory / MARKET_ANOMALY_REPORT_FILENAME
    report = format_market_anomaly_report(
        anomalies,
        snapshots=snapshots,
        catalyst_search_queue=catalyst_search_queue,
        snapshot_count=len(snapshots),
        profile=profile,
        artifact_namespace=artifact_namespace,
        cfg=cfg,
    )
    namespace_device, namespace_inode = market_anomaly_receipt.write_artifacts_atomic(
        directory,
        payloads={
            MARKET_STATE_SNAPSHOT_FILENAME: _jsonl_payload(snapshots_path, snapshots),
            MARKET_ANOMALY_FILENAME: _jsonl_payload(anomalies_path, anomalies),
            MARKET_ANOMALY_CATALYST_SEARCH_QUEUE_FILENAME: _jsonl_payload(
                catalyst_search_queue_path,
                catalyst_search_queue,
            ),
            MARKET_ANOMALY_REPORT_FILENAME: report.encode("utf-8"),
        },
        expected_names=_RECEIPT_ARTIFACT_FILENAMES,
    )
    payloads = market_anomaly_receipt.artifact_payloads(
        directory,
        namespace_identity=(namespace_device, namespace_inode),
        paths=(
            snapshots_path,
            anomalies_path,
            catalyst_search_queue_path,
            report_path,
        ),
        expected_names=_RECEIPT_ARTIFACT_FILENAMES,
    )
    bound_snapshots = market_anomaly_receipt.strict_jsonl(
        payloads[MARKET_STATE_SNAPSHOT_FILENAME],
        row_type="event_market_state_snapshot",
    )
    bound_anomalies = market_anomaly_receipt.strict_jsonl(
        payloads[MARKET_ANOMALY_FILENAME],
        row_type="event_market_anomaly",
    )
    bound_queue = market_anomaly_receipt.strict_jsonl(
        payloads[MARKET_ANOMALY_CATALYST_SEARCH_QUEUE_FILENAME],
        row_type="event_market_anomaly_catalyst_search_queue",
    )
    return MarketAnomalyScanResult(
        namespace_dir=directory,
        artifact_namespace=artifact_namespace,
        run_id=run_id,
        namespace_device=namespace_device,
        namespace_inode=namespace_inode,
        snapshots_path=snapshots_path,
        anomalies_path=anomalies_path,
        catalyst_search_queue_path=catalyst_search_queue_path,
        report_path=report_path,
        snapshot_count=len(snapshots),
        anomaly_count=len(anomalies),
        catalyst_search_queue_count=len(catalyst_search_queue),
        snapshots=bound_snapshots,
        anomalies=bound_anomalies,
        catalyst_search_queue=bound_queue,
        snapshots_sha256=market_anomaly_receipt.sha256(payloads[MARKET_STATE_SNAPSHOT_FILENAME]),
        anomalies_sha256=market_anomaly_receipt.sha256(payloads[MARKET_ANOMALY_FILENAME]),
        catalyst_search_queue_sha256=market_anomaly_receipt.sha256(
            payloads[MARKET_ANOMALY_CATALYST_SEARCH_QUEUE_FILENAME]
        ),
        report_sha256=market_anomaly_receipt.sha256(payloads[MARKET_ANOMALY_REPORT_FILENAME]),
    )


def refresh_market_anomaly_scan_result(
    result: MarketAnomalyScanResult,
) -> MarketAnomalyScanResult:
    """Rebind exact bytes after one trusted same-namespace artifact enrichment."""

    identity = (result.namespace_device, result.namespace_inode)
    payloads = market_anomaly_receipt.artifact_payloads(
        result.namespace_dir,
        namespace_identity=identity,
        paths=(
            result.snapshots_path,
            result.anomalies_path,
            result.catalyst_search_queue_path,
            result.report_path,
        ),
        expected_names=_RECEIPT_ARTIFACT_FILENAMES,
    )
    snapshots = market_anomaly_receipt.strict_jsonl(
        payloads[MARKET_STATE_SNAPSHOT_FILENAME],
        row_type="event_market_state_snapshot",
    )
    anomalies = market_anomaly_receipt.strict_jsonl(
        payloads[MARKET_ANOMALY_FILENAME],
        row_type="event_market_anomaly",
    )
    queue = market_anomaly_receipt.strict_jsonl(
        payloads[MARKET_ANOMALY_CATALYST_SEARCH_QUEUE_FILENAME],
        row_type="event_market_anomaly_catalyst_search_queue",
    )
    if (len(snapshots), len(anomalies), len(queue)) != (
        result.snapshot_count,
        result.anomaly_count,
        result.catalyst_search_queue_count,
    ):
        raise RuntimeError("market_anomaly_completion_receipt_invalid:count")
    return replace(
        result,
        snapshots=snapshots,
        anomalies=anomalies,
        catalyst_search_queue=queue,
        snapshots_sha256=market_anomaly_receipt.sha256(payloads[MARKET_STATE_SNAPSHOT_FILENAME]),
        anomalies_sha256=market_anomaly_receipt.sha256(payloads[MARKET_ANOMALY_FILENAME]),
        catalyst_search_queue_sha256=market_anomaly_receipt.sha256(
            payloads[MARKET_ANOMALY_CATALYST_SEARCH_QUEUE_FILENAME]
        ),
        report_sha256=market_anomaly_receipt.sha256(payloads[MARKET_ANOMALY_REPORT_FILENAME]),
    )


def load_market_anomaly_rows(path: str | Path | None) -> tuple[dict[str, Any], ...]:
    if path is None:
        return ()
    source = Path(path).expanduser()
    if source.is_dir():
        source = source / MARKET_ANOMALY_FILENAME
    if not source.exists():
        return ()
    rows: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, Mapping):
            rows.append(dict(row))
    return tuple(rows)


def load_market_anomaly_catalyst_search_queue(path: str | Path | None) -> tuple[dict[str, Any], ...]:
    if path is None:
        return ()
    source = Path(path).expanduser()
    if source.is_dir():
        source = source / MARKET_ANOMALY_CATALYST_SEARCH_QUEUE_FILENAME
    if not source.exists():
        return ()
    rows: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, Mapping):
            rows.append(dict(row))
    return tuple(rows)


def build_catalyst_search_queue(
    anomalies: Iterable[Mapping[str, Any]],
    *,
    cfg: MarketAnomalyScannerConfig | None = None,
    observed_at: datetime | str | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Build deterministic catalyst-search queue rows from anomaly rows."""
    cfg = cfg or MarketAnomalyScannerConfig()
    queue: list[dict[str, Any]] = []
    for anomaly in anomalies:
        if not isinstance(anomaly, Mapping) or not bool(anomaly.get("needs_catalyst_search")):
            continue
        anomaly_id = str(anomaly.get("market_anomaly_id") or anomaly.get("anomaly_id") or "")
        snapshot = anomaly.get("market_state_snapshot") if isinstance(anomaly.get("market_state_snapshot"), Mapping) else {}
        row_observed = _queue_observed_at(anomaly, snapshot, observed_at)
        search_deadline = row_observed + timedelta(hours=max(0.5, float(cfg.search_deadline_hours)))
        suggested_packs = _string_list(
            anomaly.get("suggested_source_packs_to_search") or anomaly.get("suggested_source_packs")
        )
        search_queries = _search_queries_for_anomaly(anomaly, suggested_packs=suggested_packs)
        queue.append({
            "schema_version": 1,
            "row_type": "event_market_anomaly_catalyst_search_queue",
            "profile": profile or anomaly.get("profile"),
            "artifact_namespace": artifact_namespace or anomaly.get("artifact_namespace"),
            "run_mode": run_mode or anomaly.get("run_mode"),
            "run_id": run_id or anomaly.get("run_id"),
            "anomaly_id": anomaly_id,
            "market_anomaly_id": anomaly_id,
            "canonical_asset_id": anomaly.get("canonical_asset_id"),
            "symbol": anomaly.get("symbol"),
            "coin_id": anomaly.get("coin_id"),
            "market_state_class": anomaly.get("market_state_class") or anomaly.get("anomaly_type"),
            "anomaly_bucket": anomaly.get("anomaly_bucket") or anomaly.get("market_anomaly_bucket"),
            "priority": anomaly.get("priority"),
            "suggested_source_packs": suggested_packs,
            "search_queries": search_queries,
            "search_deadline": search_deadline.astimezone(timezone.utc).isoformat(),
            "no_alert_until_evidence": True,
            "decision_model_v2_catalyst_required": False,
            "catalyst_search_role": "confidence_enrichment",
            "source_plan_status": "planned" if suggested_packs and search_queries else "missing_plan",
            "created_alert": False,
            "strict_alerts_created": 0,
            "telegram_sends": 0,
            "trades_created": 0,
            "paper_trades_created": 0,
            "normal_rsi_signal_rows_written": 0,
            "triggered_fade_created": 0,
            "research_only": True,
        })
    queue.sort(key=lambda item: float(item.get("priority") or 0.0), reverse=True)
    return queue


def _enriched_market_rows(
    market_rows: Iterable[Mapping[str, Any]],
    *,
    asset_registry: Iterable[event_asset_registry.CanonicalAsset | Mapping[str, Any]],
    coingecko_universe_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    source_rows = [dict(row) for row in market_rows if isinstance(row, Mapping)]
    universe_rows = [dict(row) for row in coingecko_universe_rows if isinstance(row, Mapping)]
    base_rows = source_rows or universe_rows
    universe_index = _market_row_index(universe_rows)
    assets = [
        *_asset_rows(asset_registry),
        *_assets_from_universe_rows(universe_rows),
    ]
    asset_index = _asset_index(assets)
    enriched_rows: list[dict[str, Any]] = []
    for row in base_rows:
        enriched = dict(row)
        universe_row = _lookup_mapping(universe_index, _row_key_variants(enriched))
        if universe_row:
            _merge_universe_metadata(enriched, universe_row)
        asset = _lookup_mapping(asset_index, _row_key_variants(enriched))
        if isinstance(asset, event_asset_registry.CanonicalAsset):
            _merge_asset_metadata(enriched, asset)
        if not enriched.get("liquidity_tier"):
            enriched["liquidity_tier"] = _liquidity_tier_from_row(enriched)
        enriched_rows.append(enriched)
    return enriched_rows


def _asset_rows(
    rows: Iterable[event_asset_registry.CanonicalAsset | Mapping[str, Any]],
) -> list[event_asset_registry.CanonicalAsset]:
    assets: list[event_asset_registry.CanonicalAsset] = []
    for row in rows:
        if isinstance(row, event_asset_registry.CanonicalAsset):
            assets.append(row)
        elif isinstance(row, Mapping):
            assets.append(event_asset_registry.CanonicalAsset.from_mapping(row, source="market_anomaly_registry"))
    return assets


def _assets_from_universe_rows(rows: Iterable[Mapping[str, Any]]) -> list[event_asset_registry.CanonicalAsset]:
    assets: list[event_asset_registry.CanonicalAsset] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        symbol = event_asset_registry.normalize_symbol(row.get("symbol"))
        coin_id = str(row.get("coin_id") or row.get("id") or "").strip()
        if not symbol or not coin_id:
            continue
        is_quote = symbol in event_asset_registry.QUOTE_ASSETS
        is_theme = symbol in event_asset_registry.THEME_OR_SECTOR_SYMBOLS
        assets.append(event_asset_registry.CanonicalAsset(
            canonical_asset_id=str(row.get("canonical_asset_id") or coin_id),
            symbol=symbol,
            coin_id=coin_id,
            name=str(row.get("name") or "") or None,
            aliases=tuple(dict.fromkeys(str(item) for item in (symbol, coin_id, row.get("name")) if str(item or ""))),
            is_quote_asset=is_quote,
            quote_asset_excluded=is_quote,
            major_base_asset=symbol in event_asset_registry.MAJOR_BASE_ASSETS,
            liquidity_tier=_liquidity_tier_from_row(row),
            venues=("coingecko",),
            eligible_lanes=("research",),
            is_tradable_asset=not (is_quote or is_theme),
            is_theme_or_sector=is_theme,
            diagnostics_reason="quote_asset_excluded" if is_quote else "theme_or_sector_diagnostic" if is_theme else None,
            source="coingecko_universe_cache",
        ))
    return assets


def _market_row_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        for key in _row_key_variants(row):
            index.setdefault(key, row)
    return index


def _asset_index(assets: Iterable[event_asset_registry.CanonicalAsset]) -> dict[str, event_asset_registry.CanonicalAsset]:
    index: dict[str, event_asset_registry.CanonicalAsset] = {}
    for asset in assets:
        for key in event_asset_registry.registry_index_keys(asset):
            index.setdefault(key, asset)
    return index


def _lookup_mapping(index: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in index:
            return index[key]
    return None


def _row_key_variants(row: Mapping[str, Any]) -> tuple[str, ...]:
    keys: list[str] = []
    for value in (
        row.get("canonical_asset_id"),
        row.get("coin_id"),
        row.get("id"),
        row.get("symbol"),
        row.get("ticker"),
        row.get("name"),
        row.get("market"),
        row.get("market_symbol"),
        row.get("coinalyze_symbol"),
        row.get("base_symbol"),
        row.get("base_asset"),
    ):
        keys.extend(event_asset_registry.identifier_key_variants(value))
    for value in _string_list(row.get("perp_symbols")) + _string_list(row.get("spot_symbols")):
        keys.extend(event_asset_registry.identifier_key_variants(value))
    return tuple(dict.fromkeys(key for key in keys if key))


def _merge_universe_metadata(row: dict[str, Any], universe_row: Mapping[str, Any]) -> None:
    for key in (
        "id",
        "coin_id",
        "symbol",
        "name",
        "current_price",
        "price",
        "market_cap",
        "mcap",
        "total_volume",
        "volume_24h",
        "liquidity_usd",
        "liquidity_tier",
        "market_context_freshness_status",
        "freshness_status",
    ):
        if row.get(key) in (None, "", [], (), {}):
            value = universe_row.get(key)
            if value not in (None, "", [], (), {}):
                row[key] = value


def _merge_asset_metadata(row: dict[str, Any], asset: event_asset_registry.CanonicalAsset) -> None:
    if not row.get("canonical_asset_id"):
        row["canonical_asset_id"] = asset.canonical_asset_id
    if not row.get("coin_id") and asset.coin_id:
        row["coin_id"] = asset.coin_id
    if not row.get("symbol") and asset.symbol:
        row["symbol"] = asset.symbol
    row["asset_registry_symbol"] = asset.symbol
    row["asset_registry_coin_id"] = asset.coin_id
    row["asset_registry_source"] = asset.source
    if not row.get("liquidity_tier") and asset.liquidity_tier:
        row["liquidity_tier"] = asset.liquidity_tier
    for key, values in (
        ("venues", asset.venues),
        ("spot_symbols", asset.spot_symbols),
        ("perp_symbols", asset.perp_symbols),
        ("coinalyze_symbols", asset.coinalyze_symbols),
        ("bybit_symbols", asset.bybit_symbols),
        ("binance_symbols", asset.binance_symbols),
    ):
        if values:
            row[key] = list(values)
    row["is_quote_asset"] = asset.is_quote_asset
    row["quote_asset_excluded"] = asset.quote_asset_excluded
    row["is_tradable_asset"] = asset.is_tradable_asset
    row["is_theme_or_sector"] = asset.is_theme_or_sector
    if asset.diagnostics_reason:
        row["diagnostics_reason"] = asset.diagnostics_reason
    if asset.perp_symbols or asset.coinalyze_symbols or asset.eligible_lanes and "derivatives" in asset.eligible_lanes:
        row["derivatives_available"] = True



def format_market_anomaly_report(
    anomalies: Iterable[Mapping[str, Any]],
    *,
    snapshots: Iterable[Mapping[str, Any]] | None = None,
    catalyst_search_queue: Iterable[Mapping[str, Any]] | None = None,
    snapshot_count: int = 0,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    cfg: MarketAnomalyScannerConfig | None = None,
    limit: int = 20,
) -> str:
    return market_anomaly_report.format_market_anomaly_report(
        anomalies,
        snapshots=snapshots,
        catalyst_search_queue=catalyst_search_queue,
        snapshot_count=snapshot_count,
        profile=profile,
        artifact_namespace=artifact_namespace,
        cfg=cfg or MarketAnomalyScannerConfig(),
        limit=limit,
    )


def _anomaly_row(
    snapshot: Mapping[str, Any],
    source_row: Mapping[str, Any],
    anomaly_type: str,
    *,
    cfg: MarketAnomalyScannerConfig,
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
) -> dict[str, Any]:
    symbol = str(snapshot.get("symbol") or "").upper()
    coin_id = str(snapshot.get("coin_id") or "")
    observed_at = str(snapshot.get("observed_at") or "")
    bucket = _anomaly_bucket(snapshot, source_row, anomaly_type, cfg=cfg)
    priority_components = _priority_components(snapshot, source_row, anomaly_type, bucket=bucket)
    priority = sum(priority_components.values())
    packs = _suggested_source_packs(anomaly_type, source_row)
    search_queries = _search_queries_for_anomaly(
        {
            "symbol": symbol,
            "coin_id": coin_id,
            "name": source_row.get("name"),
            "canonical_asset_id": snapshot.get("canonical_asset_id") or coin_id or symbol,
            "market_state_class": anomaly_type,
            "anomaly_bucket": bucket,
        },
        suggested_packs=packs,
    )
    row = {
        "schema_version": 1,
        "row_type": "event_market_anomaly",
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "run_mode": run_mode,
        "run_id": run_id,
        "market_anomaly_id": _market_anomaly_id(symbol=symbol, coin_id=coin_id, anomaly_type=anomaly_type, observed_at=observed_at),
        "symbol": symbol,
        "coin_id": coin_id,
        "canonical_asset_id": snapshot.get("canonical_asset_id") or coin_id or symbol,
        "anomaly_type": anomaly_type,
        "anomaly_bucket": bucket,
        "market_anomaly_bucket": bucket,
        "market_state": anomaly_type,
        "market_state_class": anomaly_type,
        "market_state_snapshot": dict(snapshot),
        "needs_catalyst_search": True,
        "decision_model_v2_catalyst_required": False,
        "catalyst_search_role": "confidence_enrichment",
        "priority": round(max(0.0, min(100.0, priority)), 2),
        "priority_components": {key: round(value, 2) for key, value in priority_components.items()},
        "derivatives_available": _derivatives_available(snapshot, source_row),
        "source_catalyst_knownness": "unknown" if not _has_confirming_source(source_row) else "known",
        "suggested_source_packs_to_search": packs,
        "search_queries": search_queries,
        "why_interesting": _why_interesting(snapshot, anomaly_type),
        "why_not_alertable_yet": [
            "legacy_strict_alert_route_needs_catalyst_evidence",
            "awaiting_crypto_radar_decision_model_v2_evaluation",
            "scanner_is_research_only",
        ],
        "what_confirms": _what_confirms(anomaly_type, packs),
        "what_invalidates": _what_invalidates(anomaly_type),
        "created_alert": False,
        "research_only": True,
    }
    return row


def _why_interesting(snapshot: Mapping[str, Any], anomaly_type: str) -> list[str]:
    reasons = [f"market_state={anomaly_type}"]
    r4 = _float(snapshot.get("return_4h"))
    r24 = _float(snapshot.get("return_24h"))
    rel = _float(snapshot.get("relative_return_vs_btc_4h"))
    vz = _float(snapshot.get("volume_zscore_24h"))
    vol_mcap = _float(snapshot.get("volume_to_market_cap"))
    if r4 is not None:
        reasons.append(f"return_4h={r4:.1f}%")
    if r24 is not None:
        reasons.append(f"return_24h={r24:.1f}%")
    if rel is not None:
        reasons.append(f"relative_return_vs_btc_4h={rel:.1f}%")
    if vz is not None:
        reasons.append(f"volume_zscore_24h={vz:.1f}")
    if vol_mcap is not None:
        reasons.append(f"volume_to_market_cap={vol_mcap:.2f}")
    return reasons


def _what_confirms(anomaly_type: str, packs: list[str]) -> list[str]:
    base = [
        "fresh identity/liquidity/spread/volume gates continue to pass",
        "independent catalyst evidence would raise confidence but is not universally required",
    ]
    if anomaly_type in {CONFIRMED_BREAKOUT, STEALTH_ACCUMULATION, LATE_MOMENTUM}:
        base.append("official project/exchange or token-tagged news confirmation")
    if anomaly_type in {BLOWOFF_CROWDED, POST_EVENT_FADE_SETUP, RISK_OFF_SELL_PRESSURE}:
        base.append("fresh derivatives/supply/security evidence matching the direction")
    if packs:
        base.append("source packs: " + ", ".join(packs[:3]))
    return base


def _what_invalidates(anomaly_type: str) -> list[str]:
    out = [
        "market snapshot becomes stale or invalid",
        "identity, liquidity, spread, turnover, volume, or dedupe gate fails",
    ]
    if anomaly_type == SUSPICIOUS_ILLIQUID_MOVE:
        out.append("thin liquidity or wide spread makes move non-actionable")
    elif anomaly_type == CONFIRMED_BREAKOUT:
        out.append("volume breakout reverses without source confirmation")
    elif anomaly_type in {BLOWOFF_CROWDED, POST_EVENT_FADE_SETUP}:
        out.append("crowding metrics normalize before post-event failure evidence")
    return out


def _suggested_source_packs(anomaly_type: str, source_row: Mapping[str, Any]) -> list[str]:
    explicit = source_row.get("suggested_source_packs_to_search")
    if isinstance(explicit, list) and explicit:
        return [str(item) for item in explicit if str(item)]
    if anomaly_type in {RISK_OFF_SELL_PRESSURE}:
        return ["security_shock_pack", "regulatory_pack", "cryptopanic_tagged"]
    if anomaly_type in {BLOWOFF_CROWDED, POST_EVENT_FADE_SETUP}:
        return ["perp_listing_squeeze_pack", "cryptopanic_tagged", "coinalyze_derivatives"]
    if anomaly_type == SUSPICIOUS_ILLIQUID_MOVE:
        return ["market_anomaly_pack", "dex_liquidity_pack", "cryptopanic_tagged"]
    return ["market_anomaly_pack", "cryptopanic_tagged", "official_project", "project_blog_rss"]


def _anomaly_bucket(
    snapshot: Mapping[str, Any],
    source_row: Mapping[str, Any],
    anomaly_type: str,
    *,
    cfg: MarketAnomalyScannerConfig,
) -> str:
    if anomaly_type == SUSPICIOUS_ILLIQUID_MOVE:
        return LOW_LIQUIDITY_SUSPICIOUS
    if anomaly_type == STEALTH_ACCUMULATION:
        return STEALTH_ACCUMULATION
    if anomaly_type == RISK_OFF_SELL_PRESSURE:
        return SELLOFF_RISK
    if anomaly_type in {LATE_MOMENTUM, BLOWOFF_CROWDED, POST_EVENT_FADE_SETUP}:
        return LATE_MOMENTUM_NEEDS_CROWDING_CHECK
    if anomaly_type == CONFIRMED_BREAKOUT and _high_liquidity(snapshot, source_row, cfg=cfg):
        return HIGH_LIQUIDITY_BREAKOUT
    if anomaly_type == CONFIRMED_BREAKOUT:
        return NEEDS_CATALYST_SEARCH
    return NEEDS_CATALYST_SEARCH


def _priority_components(
    snapshot: Mapping[str, Any],
    source_row: Mapping[str, Any],
    anomaly_type: str,
    *,
    bucket: str,
) -> dict[str, float]:
    r4 = abs(_float(snapshot.get("return_4h")) or 0.0)
    r24 = abs(_float(snapshot.get("return_24h")) or 0.0)
    rel_btc = abs(_float(snapshot.get("relative_return_vs_btc_4h")) or 0.0)
    rel_eth = abs(_float(snapshot.get("relative_return_vs_eth_4h")) or 0.0)
    volume_z = max(0.0, _float(snapshot.get("volume_zscore_24h")) or 0.0)
    volume_mcap = max(0.0, _float(snapshot.get("volume_to_market_cap")) or 0.0)
    market_cap = _float(
        _canonical_or_source_value(snapshot, source_row, "market_cap", "mcap")
    )
    event_age = _float(
        _canonical_or_source_value(snapshot, source_row, "event_age_hours")
    )
    liquidity_score = _liquidity_score(snapshot, source_row)
    derivatives_score = 8.0 if _derivatives_available(snapshot, source_row) else 0.0
    unknownness_score = 7.0 if not _has_confirming_source(source_row) else -4.0
    age_score = _event_age_score(event_age)
    bucket_adjustment = {
        HIGH_LIQUIDITY_BREAKOUT: 7.0,
        STEALTH_ACCUMULATION: 4.0,
        LATE_MOMENTUM_NEEDS_CROWDING_CHECK: 6.0,
        SELLOFF_RISK: 3.0,
        LOW_LIQUIDITY_SUSPICIOUS: -12.0,
    }.get(bucket, 0.0)
    if anomaly_type == BLOWOFF_CROWDED:
        bucket_adjustment += 4.0
    elif anomaly_type == POST_EVENT_FADE_SETUP:
        bucket_adjustment += 5.0
    market_cap_score = 0.0
    if market_cap is not None:
        if market_cap >= 10_000_000_000:
            market_cap_score = 5.0
        elif market_cap >= 1_000_000_000:
            market_cap_score = 3.5
        elif market_cap >= 100_000_000:
            market_cap_score = 2.0
    return {
        "absolute_return": min(35.0, r24 * 0.9) + min(16.0, r4 * 1.2),
        "relative_return_vs_btc_eth": min(18.0, max(rel_btc, rel_eth) * 1.5),
        "volume_zscore": min(17.0, volume_z * 5.0),
        "liquidity_tier": liquidity_score,
        "market_cap_turnover": market_cap_score + min(8.0, volume_mcap * 16.0),
        "derivatives_availability": derivatives_score,
        "source_catalyst_unknownness": unknownness_score,
        "event_age": age_score,
        "bucket_adjustment": bucket_adjustment,
    }


def _priority(snapshot: Mapping[str, Any], anomaly_type: str) -> float:
    bucket = _anomaly_bucket(snapshot, {}, anomaly_type, cfg=MarketAnomalyScannerConfig())
    components = _priority_components(snapshot, {}, anomaly_type, bucket=bucket)
    return max(0.0, min(100.0, sum(components.values())))


def _high_liquidity(
    snapshot: Mapping[str, Any],
    source_row: Mapping[str, Any],
    *,
    cfg: MarketAnomalyScannerConfig,
) -> bool:
    tier = str(snapshot.get("liquidity_tier") or source_row.get("liquidity_tier") or "").casefold()
    if tier in {"large", "large_cap", "high", "top", "blue_chip"}:
        return True
    liquidity = _float(
        _canonical_or_source_value(snapshot, source_row, "liquidity_usd")
    )
    return liquidity is not None and liquidity >= cfg.high_liquidity_usd


def _liquidity_score(snapshot: Mapping[str, Any], source_row: Mapping[str, Any]) -> float:
    tier = str(snapshot.get("liquidity_tier") or source_row.get("liquidity_tier") or "").casefold()
    if tier in {"large", "large_cap", "high", "top", "blue_chip"}:
        return 10.0
    if tier in {"mid", "medium", "mid_cap"}:
        return 6.0
    if tier in {"small", "small_cap"}:
        return 2.0
    if tier in {"thin", "micro", "low"}:
        return -6.0
    liquidity = _float(
        _canonical_or_source_value(snapshot, source_row, "liquidity_usd")
    )
    if liquidity is None:
        return 0.0
    if liquidity >= 5_000_000:
        return 9.0
    if liquidity >= 1_000_000:
        return 5.0
    if liquidity >= 250_000:
        return 1.0
    return -7.0


def _event_age_score(event_age_hours: float | None) -> float:
    if event_age_hours is None:
        return 2.0
    if event_age_hours < 0:
        return 4.0
    if event_age_hours <= 6:
        return 6.0
    if event_age_hours <= 24:
        return 3.0
    if event_age_hours <= 72:
        return 0.0
    return -6.0


def _derivatives_available(snapshot: Mapping[str, Any], source_row: Mapping[str, Any]) -> bool:
    if bool(source_row.get("derivatives_available") or snapshot.get("derivatives_available")):
        return True
    for key in ("perp_symbols", "coinalyze_symbols", "open_interest_delta", "funding_level", "funding_zscore"):
        value = source_row.get(key) if key in source_row else snapshot.get(key)
        if value not in (None, "", [], (), {}):
            return True
    return False


def _has_confirming_source(source_row: Mapping[str, Any]) -> bool:
    for key in ("source_url", "official_source_url", "published_at", "event_time", "catalyst_confirmed"):
        if source_row.get(key):
            return True
    accepted = _count(source_row.get("accepted_evidence_count"))
    return bool((accepted is not None and accepted > 0) or source_row.get("source_urls"))


def _search_queries_for_anomaly(
    anomaly: Mapping[str, Any],
    *,
    suggested_packs: Iterable[str],
) -> list[str]:
    symbol = str(anomaly.get("symbol") or "").upper()
    coin_id = str(anomaly.get("coin_id") or anomaly.get("canonical_asset_id") or "").strip()
    name = str(anomaly.get("name") or "").strip()
    bucket = str(anomaly.get("anomaly_bucket") or anomaly.get("market_anomaly_bucket") or "").strip()
    roots = [value for value in (symbol, name, coin_id) if value and value.casefold() not in {"unknown", "sector"}]
    roots = list(dict.fromkeys(roots))[:3]
    pack_text = " ".join(str(item) for item in suggested_packs).casefold()
    queries: list[str] = []
    for root in roots[:2]:
        queries.append(f"{root} crypto catalyst")
        queries.append(f"{root} token announcement")
    for root in roots[:1]:
        if "official" in pack_text or "project_blog" in pack_text:
            queries.append(f"{root} official project announcement")
        if "cryptopanic" in pack_text:
            queries.append(f"{root} crypto news catalyst")
        if "exchange" in pack_text or "listing" in pack_text:
            queries.append(f"{root} Binance Bybit listing")
        if "coinalyze" in pack_text or "perp" in pack_text:
            queries.append(f"{root} funding open interest liquidations")
        if "dex" in pack_text or "liquidity" in pack_text:
            queries.append(f"{root} DEX liquidity volume pool")
        if "security" in pack_text or "regulatory" in pack_text or bucket == SELLOFF_RISK:
            queries.append(f"{root} exploit hack regulatory risk")
    if bucket:
        for root in roots[:1]:
            queries.append(f"{root} {bucket.replace('_', ' ')}")
    return list(dict.fromkeys(query for query in queries if query))[:8]


def _is_sector_or_theme(snapshot: Mapping[str, Any]) -> bool:
    symbol = str(snapshot.get("symbol") or "").upper()
    coin_id = str(snapshot.get("coin_id") or "").casefold()
    if bool(snapshot.get("is_theme_or_sector")) or bool(snapshot.get("quote_asset_excluded")) or bool(snapshot.get("is_quote_asset")):
        return True
    if snapshot.get("is_tradable_asset") is False:
        return True
    return symbol == "SECTOR" or coin_id.startswith("sector:") or coin_id.endswith("_proxy")


def _jsonl_payload(path: Path, rows: Iterable[Mapping[str, Any]]) -> bytes:
    lines = [
        json.dumps(
            schema_v1.stamp_artifact_row(row, path=path),
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        for row in rows
    ]
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def _market_anomaly_id(*, symbol: str, coin_id: str, anomaly_type: str, observed_at: str) -> str:
    key = f"{coin_id or symbol}|{anomaly_type}|{observed_at[:13]}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"mkt:{coin_id or symbol}:{digest}"


def _liquidity_tier_from_row(row: Mapping[str, Any]) -> str | None:
    explicit = str(row.get("liquidity_tier") or "").strip()
    if explicit:
        return explicit
    liquidity = _float(_first_present_value(row, "liquidity_usd", "order_book_liquidity_usd"))
    market_cap = _float(_first_present_value(row, "market_cap", "mcap"))
    volume = _float(_first_present_value(row, "total_volume", "volume_24h", "spot_volume_24h"))
    if liquidity is not None:
        if liquidity >= 20_000_000:
            return "large"
        if liquidity >= 1_000_000:
            return "mid"
        if liquidity >= 250_000:
            return "small"
        return "thin"
    if market_cap is not None:
        if market_cap >= 10_000_000_000:
            return "large"
        if market_cap >= 1_000_000_000:
            return "mid"
        if market_cap >= 100_000_000:
            return "small"
        return "thin"
    if volume is not None and volume >= 100_000_000:
        return "large"
    if volume is not None and volume >= 10_000_000:
        return "mid"
    return None


def _queue_observed_at(
    anomaly: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    observed_at: datetime | str | None,
) -> datetime:
    for field_name, value in (
        ("anomaly observed_at", anomaly.get("observed_at")),
        ("snapshot observed_at", snapshot.get("observed_at")),
        ("fallback observed_at", observed_at),
    ):
        if value in (None, ""):
            continue
        return _parse_time(value, field_name=field_name)
    return datetime.now(timezone.utc)


def _parse_time(value: object, *, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise ValueError(f"market anomaly catalyst queue {field_name} is invalid")


def _string_list(value: object) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, IterableABC) and not isinstance(value, (str, bytes, Mapping)):
        return [str(item) for item in value if str(item or "")]
    return [str(value)]


def _float(value: object) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _count(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        parsed = int(value)
        return parsed if parsed >= 0 else None
    return None


def _first_present_value(row: Mapping[str, Any], *keys: str) -> object:
    """Return the first explicit non-empty value without treating zero as absent."""
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _canonical_or_source_value(
    snapshot: Mapping[str, Any],
    source_row: Mapping[str, Any],
    canonical_key: str,
    *source_aliases: str,
) -> object:
    value = _first_present_value(snapshot, canonical_key)
    if value is not None:
        return value
    return _first_present_value(source_row, canonical_key, *source_aliases)
