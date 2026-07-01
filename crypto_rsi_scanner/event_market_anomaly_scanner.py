"""Broad market anomaly scanner for Event Alpha research artifacts.

The scanner consumes already-collected market rows and writes local research
artifacts. It deliberately does not create alert snapshots, Telegram sends,
paper trades, or event-fade triggers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_market_state


MARKET_STATE_SNAPSHOT_FILENAME = "event_market_state_snapshots.jsonl"
MARKET_ANOMALY_FILENAME = "event_market_anomalies.jsonl"
MARKET_ANOMALY_REPORT_FILENAME = "event_market_anomaly_report.md"

NO_REACTION = "no_reaction"
STEALTH_ACCUMULATION = "stealth_accumulation"
CONFIRMED_BREAKOUT = "confirmed_breakout"
LATE_MOMENTUM = "late_momentum"
BLOWOFF_CROWDED = "blowoff_crowded"
POST_EVENT_FADE_SETUP = "post_event_fade_setup"
RISK_OFF_SELL_PRESSURE = "risk_off_sell_pressure"
SUSPICIOUS_ILLIQUID_MOVE = "suspicious_illiquid_move"
NEEDS_CATALYST_SEARCH = "needs_catalyst_search"


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


@dataclass(frozen=True)
class MarketAnomalyScanResult:
    namespace_dir: Path
    snapshots_path: Path
    anomalies_path: Path
    report_path: Path
    snapshot_count: int
    anomaly_count: int
    anomalies: tuple[dict[str, Any], ...]
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


def scan_market_rows(
    market_rows: Iterable[Mapping[str, Any]],
    *,
    cfg: MarketAnomalyScannerConfig | None = None,
    observed_at: datetime | str | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return snapshot rows and anomaly rows from cached/fixture market rows."""
    cfg = cfg or MarketAnomalyScannerConfig()
    rows = [dict(row) for row in market_rows if isinstance(row, Mapping)]
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
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
) -> MarketAnomalyScanResult:
    """Scan rows and write research-only market anomaly artifacts."""
    directory = Path(namespace_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    snapshots, anomalies = scan_market_rows(
        market_rows,
        cfg=cfg,
        observed_at=observed_at,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_id=run_id,
    )
    snapshots_path = directory / MARKET_STATE_SNAPSHOT_FILENAME
    anomalies_path = directory / MARKET_ANOMALY_FILENAME
    report_path = directory / MARKET_ANOMALY_REPORT_FILENAME
    _write_jsonl(snapshots_path, snapshots)
    _write_jsonl(anomalies_path, anomalies)
    report = format_market_anomaly_report(anomalies, snapshot_count=len(snapshots), profile=profile, artifact_namespace=artifact_namespace)
    report_path.write_text(report, encoding="utf-8")
    return MarketAnomalyScanResult(
        namespace_dir=directory,
        snapshots_path=snapshots_path,
        anomalies_path=anomalies_path,
        report_path=report_path,
        snapshot_count=len(snapshots),
        anomaly_count=len(anomalies),
        anomalies=tuple(anomalies),
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


def format_market_anomaly_report(
    anomalies: Iterable[Mapping[str, Any]],
    *,
    snapshot_count: int = 0,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    limit: int = 20,
) -> str:
    rows = [dict(row) for row in anomalies if isinstance(row, Mapping)]
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("market_state_class") or row.get("anomaly_type") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    lines = [
        "# Event Alpha Market Anomaly Report",
        "",
        "Research-only. Not a trade signal, paper trade, live RSI signal, or execution.",
        f"Profile: {profile or 'unknown'}",
        f"Artifact namespace: {artifact_namespace or 'unknown'}",
        f"Market state snapshots: {snapshot_count}",
        f"Anomalies: {len(rows)}",
        "Counts: " + (", ".join(f"{key}={value}" for key, value in sorted(counts.items())) if counts else "none"),
        "",
        "## Market Anomalies Without Confirmed Catalyst",
    ]
    if not rows:
        lines.append("- None.")
    for row in rows[: max(0, limit)]:
        snapshot = row.get("market_state_snapshot") if isinstance(row.get("market_state_snapshot"), Mapping) else {}
        market_state_class = row.get("market_state_class") or row.get("anomaly_type") or "unknown"
        lines.append(
            f"- {row.get('symbol') or row.get('coin_id') or 'UNKNOWN'}: "
            f"{market_state_class} "
            f"return_4h={_format_pct(snapshot.get('return_4h'))} "
            f"return_24h={_format_pct(snapshot.get('return_24h'))} "
            f"volume_z={_format_number(snapshot.get('volume_zscore_24h'))} "
            f"priority={_format_number(row.get('priority'))} "
            f"needs_catalyst_search={str(bool(row.get('needs_catalyst_search'))).lower()}"
        )
        confirms = row.get("what_confirms") if isinstance(row.get("what_confirms"), list) else []
        invalidates = row.get("what_invalidates") if isinstance(row.get("what_invalidates"), list) else []
        if confirms:
            lines.append("  - What confirms: " + "; ".join(str(item) for item in confirms[:3]))
        if invalidates:
            lines.append("  - What invalidates: " + "; ".join(str(item) for item in invalidates[:3]))
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more in local artifacts.")
    return "\n".join(lines) + "\n"


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
    priority = _priority(snapshot, anomaly_type)
    packs = _suggested_source_packs(anomaly_type, source_row)
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
        "market_state": anomaly_type,
        "market_state_class": anomaly_type,
        "market_state_snapshot": dict(snapshot),
        "needs_catalyst_search": True,
        "priority": round(priority, 2),
        "suggested_source_packs_to_search": packs,
        "why_interesting": _why_interesting(snapshot, anomaly_type),
        "why_not_alertable_yet": [
            "market_anomaly_needs_catalyst_evidence",
            "no_confirmed_catalyst",
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
    base = ["independent source evidence explaining the move", "validated asset identity and catalyst link"]
    if anomaly_type in {CONFIRMED_BREAKOUT, STEALTH_ACCUMULATION, LATE_MOMENTUM}:
        base.append("official project/exchange or token-tagged news confirmation")
    if anomaly_type in {BLOWOFF_CROWDED, POST_EVENT_FADE_SETUP, RISK_OFF_SELL_PRESSURE}:
        base.append("fresh derivatives/supply/security evidence matching the direction")
    if packs:
        base.append("source packs: " + ", ".join(packs[:3]))
    return base


def _what_invalidates(anomaly_type: str) -> list[str]:
    out = ["no independent catalyst after bounded search", "stale or missing market data"]
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


def _priority(snapshot: Mapping[str, Any], anomaly_type: str) -> float:
    r4 = abs(_float(snapshot.get("return_4h")) or 0.0)
    r24 = abs(_float(snapshot.get("return_24h")) or 0.0)
    rel = max(0.0, _float(snapshot.get("relative_return_vs_btc_4h")) or 0.0)
    volume_z = max(0.0, _float(snapshot.get("volume_zscore_24h")) or 0.0)
    volume_mcap = max(0.0, _float(snapshot.get("volume_to_market_cap")) or 0.0)
    base = min(35.0, r24 * 0.9) + min(20.0, r4 * 1.4) + min(18.0, rel * 1.5) + min(17.0, volume_z * 5.0) + min(10.0, volume_mcap * 20.0)
    if anomaly_type == CONFIRMED_BREAKOUT:
        base += 8
    elif anomaly_type == BLOWOFF_CROWDED:
        base += 10
    elif anomaly_type == POST_EVENT_FADE_SETUP:
        base += 9
    elif anomaly_type == SUSPICIOUS_ILLIQUID_MOVE:
        base -= 10
    return max(0.0, min(100.0, base))


def _is_sector_or_theme(snapshot: Mapping[str, Any]) -> bool:
    symbol = str(snapshot.get("symbol") or "").upper()
    coin_id = str(snapshot.get("coin_id") or "").casefold()
    return symbol == "SECTOR" or coin_id.startswith("sector:") or coin_id.endswith("_proxy")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(dict(row), sort_keys=True, default=str, separators=(",", ":")) + "\n")


def _market_anomaly_id(*, symbol: str, coin_id: str, anomaly_type: str, observed_at: str) -> str:
    key = f"{coin_id or symbol}|{anomaly_type}|{observed_at[:13]}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"mkt:{coin_id or symbol}:{digest}"


def _format_pct(value: object) -> str:
    parsed = _float(value)
    return "n/a" if parsed is None else f"{parsed:+.1f}%"


def _format_number(value: object) -> str:
    parsed = _float(value)
    return "n/a" if parsed is None else f"{parsed:.1f}"


def _float(value: object) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed else None
