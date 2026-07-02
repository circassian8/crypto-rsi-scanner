"""Provider instrument resolver for Event Alpha research artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import asset_registry as event_asset_registry


INSTRUMENT_RESOLUTION_JSONL = "event_instrument_resolution.jsonl"
ASSET_RESOLUTION_REPORT_MD = "event_asset_resolution_report.md"
OPPORTUNITY_ROW_TYPES = frozenset(
    {
        "event_integrated_radar_candidate",
        "event_core_opportunity",
        "official_listing_candidate",
        "event_alpha_alert_snapshot",
    }
)
PROMOTED_OPPORTUNITY_TYPES = frozenset(
    {
        "EARLY_LONG_RESEARCH",
        "CONFIRMED_LONG_RESEARCH",
        "FADE_SHORT_REVIEW",
    }
)


@dataclass(frozen=True)
class ResolutionMatch:
    asset: event_asset_registry.CanonicalAsset | None
    confidence: float
    reason: str
    input_identifier: str | None = None


def resolve_sidecar_mapping(
    sidecar_rows: Mapping[str, Iterable[Mapping[str, Any]]],
    registry: Iterable[event_asset_registry.CanonicalAsset],
    *,
    generated_at: datetime | str | None = None,
) -> tuple[dict[str, tuple[dict[str, Any], ...]], tuple[dict[str, Any], ...]]:
    out: dict[str, tuple[dict[str, Any], ...]] = {}
    resolution_rows: list[dict[str, Any]] = []
    for origin, rows in sidecar_rows.items():
        enriched_rows, origin_resolutions = resolve_rows(
            rows,
            registry,
            source_name=origin,
            generated_at=generated_at,
        )
        out[origin] = enriched_rows
        resolution_rows.extend(origin_resolutions)
    return out, tuple(resolution_rows)


def resolve_rows(
    rows: Iterable[Mapping[str, Any]],
    registry: Iterable[event_asset_registry.CanonicalAsset],
    *,
    source_name: str | None = None,
    generated_at: datetime | str | None = None,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    enriched: list[dict[str, Any]] = []
    resolutions: list[dict[str, Any]] = []
    index = _ResolverIndex(tuple(registry))
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        enriched_row, resolution = resolve_row(
            row,
            index,
            source_name=source_name,
            generated_at=generated_at,
        )
        enriched.append(enriched_row)
        resolutions.append(resolution)
    return tuple(enriched), tuple(resolutions)


def resolve_row(
    row: Mapping[str, Any],
    registry: Iterable[event_asset_registry.CanonicalAsset] | "_ResolverIndex",
    *,
    source_name: str | None = None,
    generated_at: datetime | str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    index = registry if isinstance(registry, _ResolverIndex) else _ResolverIndex(tuple(registry))
    original = dict(row)
    match = index.match(row)
    enriched = dict(row)
    warnings = list(dict.fromkeys(_list(enriched.get("warnings"))))
    resolver_warnings: list[str] = []
    reason_codes = list(dict.fromkeys(_list(enriched.get("reason_codes"))))
    asset = match.asset
    status = "unresolved"
    if asset is not None:
        enriched["canonical_asset_id"] = asset.canonical_asset_id
        enriched["asset_registry_symbol"] = asset.symbol
        enriched["asset_registry_coin_id"] = asset.coin_id
        enriched["asset_registry_name"] = asset.name
        enriched["asset_registry_liquidity_tier"] = asset.liquidity_tier
        enriched["asset_registry_venues"] = list(asset.venues)
        enriched["asset_registry_spot_symbols"] = list(asset.spot_symbols)
        enriched["asset_registry_perp_symbols"] = list(asset.perp_symbols)
        enriched["asset_registry_coinalyze_symbols"] = list(asset.coinalyze_symbols)
        enriched["asset_registry_bybit_symbols"] = list(asset.bybit_symbols)
        enriched["asset_registry_binance_symbols"] = list(asset.binance_symbols)
        enriched["eligible_lanes"] = list(asset.eligible_lanes)
        enriched["is_tradable_asset"] = asset.is_tradable_asset
        enriched["is_theme_or_sector"] = asset.is_theme_or_sector
        enriched["is_quote_asset"] = asset.is_quote_asset
        enriched["quote_asset_excluded"] = asset.quote_asset_excluded
        enriched["base_asset_excluded"] = asset.base_asset_excluded
        enriched["major_base_asset"] = asset.major_base_asset
        enriched["diagnostics_reason"] = asset.diagnostics_reason
        if asset.asset_role:
            enriched["asset_role"] = asset.asset_role
        status = "resolved"
        if asset.is_theme_or_sector:
            status = "resolved_theme"
            resolver_warnings.append("theme_or_sector_diagnostic")
            reason_codes.append("theme_or_sector_diagnostic")
        if asset.is_quote_asset or asset.quote_asset_excluded:
            status = "resolved_quote_asset"
            resolver_warnings.append("quote_asset_target_excluded")
            reason_codes.append("quote_asset_target_excluded")
        if _has_coinalyze_symbol(row) and _asset_is_coinalyze_only(asset):
            resolver_warnings.append("coinalyze_symbol_not_linked_to_asset")
        if asset.asset_role and asset.asset_role.startswith("proxy"):
            resolver_warnings.append("proxy_asset_labeled_proxy")
            if str(enriched.get("candidate_role") or "").strip() in {"", "direct_event", "direct_asset"}:
                enriched["candidate_role"] = asset.asset_role
    else:
        if _quote_target_symbol(row):
            enriched["is_tradable_asset"] = False
            enriched["is_quote_asset"] = True
            enriched["quote_asset_excluded"] = True
            enriched["diagnostics_reason"] = "quote_asset_excluded"
            resolver_warnings.append("quote_asset_target_excluded")
            reason_codes.append("quote_asset_target_excluded")
            status = "unresolved_quote_asset"
        if _theme_target_symbol(row):
            enriched["is_tradable_asset"] = False
            enriched["is_theme_or_sector"] = True
            enriched["diagnostics_reason"] = "theme_or_sector_diagnostic"
            resolver_warnings.append("theme_or_sector_diagnostic")
            reason_codes.append("theme_or_sector_diagnostic")
            status = "unresolved_theme"
        if _has_coinalyze_symbol(row):
            resolver_warnings.append("coinalyze_symbol_not_linked_to_asset")
    if _major_pair_simple(row, asset):
        resolver_warnings.append("major_pair_simple_announcement_capped")
        reason_codes.append("major_pair_simple_announcement_capped")
    resolver_warnings = list(dict.fromkeys(item for item in resolver_warnings if item))
    warnings = list(dict.fromkeys((*warnings, *resolver_warnings)))
    reason_codes = list(dict.fromkeys(item for item in reason_codes if item))
    enriched["instrument_resolver_status"] = status
    enriched["instrument_resolver_confidence"] = match.confidence
    enriched["instrument_resolver_match_reason"] = match.reason
    enriched["instrument_resolver_input_identifier"] = match.input_identifier
    enriched["instrument_resolver_warnings"] = resolver_warnings
    if resolver_warnings:
        enriched["warnings"] = warnings
    if reason_codes:
        enriched["reason_codes"] = reason_codes
    resolution = {
        "schema_version": 1,
        "row_type": "event_instrument_resolution",
        "research_only": True,
        "generated_at": _time_text(generated_at),
        "source_name": source_name,
        "original_row_type": _text(row.get("row_type")),
        "provider": _text(row.get("provider") or row.get("exchange")),
        "input_symbol": _text(row.get("symbol") or row.get("validated_symbol") or row.get("base_symbol")),
        "input_coin_id": _text(row.get("coin_id") or row.get("validated_coin_id")),
        "input_market_symbol": _text(row.get("market_symbol") or row.get("market") or row.get("coinalyze_symbol")),
        "canonical_asset_id": enriched.get("canonical_asset_id"),
        "asset_symbol": enriched.get("asset_registry_symbol"),
        "asset_coin_id": enriched.get("asset_registry_coin_id"),
        "resolver_status": status,
        "resolver_confidence": match.confidence,
        "resolver_match_reason": match.reason,
        "resolver_input_identifier": match.input_identifier,
        "resolver_warnings": resolver_warnings,
        "is_tradable_asset": enriched.get("is_tradable_asset"),
        "is_theme_or_sector": enriched.get("is_theme_or_sector"),
        "is_quote_asset": enriched.get("is_quote_asset"),
        "quote_asset_excluded": enriched.get("quote_asset_excluded"),
        "major_base_asset": enriched.get("major_base_asset"),
        "diagnostics_reason": enriched.get("diagnostics_reason"),
        "original_has_canonical_asset_id": bool(_text(original.get("canonical_asset_id"))),
        "enriched_has_canonical_asset_id": bool(_text(enriched.get("canonical_asset_id"))),
        "opportunity_type": _text(enriched.get("opportunity_type")),
    }
    return enriched, resolution


def write_resolution_artifacts(
    namespace_dir: str | Path,
    registry: Iterable[event_asset_registry.CanonicalAsset],
    resolution_rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: datetime | str | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
) -> tuple[Path, Path]:
    directory = Path(namespace_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    resolution_path = directory / INSTRUMENT_RESOLUTION_JSONL
    rows = [dict(row) for row in resolution_rows if isinstance(row, Mapping)]
    with resolution_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload = {
                "profile": profile,
                "artifact_namespace": artifact_namespace,
                "run_mode": run_mode,
                "run_id": run_id,
                **row,
            }
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    report_path = directory / ASSET_RESOLUTION_REPORT_MD
    report_path.write_text(
        format_resolution_report(
            registry,
            rows,
            generated_at=generated_at,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
        ),
        encoding="utf-8",
    )
    return resolution_path, report_path


def format_resolution_report(
    registry: Iterable[event_asset_registry.CanonicalAsset],
    resolution_rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: datetime | str | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
) -> str:
    assets = tuple(registry)
    rows = [dict(row) for row in resolution_rows if isinstance(row, Mapping)]
    statuses: dict[str, int] = {}
    warnings: dict[str, int] = {}
    for row in rows:
        statuses[_text(row.get("resolver_status")) or "unknown"] = statuses.get(_text(row.get("resolver_status")) or "unknown", 0) + 1
        for warning in _list(row.get("resolver_warnings")):
            warnings[warning] = warnings.get(warning, 0) + 1
    lines = [
        "# Event Asset Resolution Report",
        "",
        "Research-only identity normalization. Not a trading, paper trading, RSI signal, or execution artifact.",
        "",
        f"- generated_at: {_time_text(generated_at)}",
        f"- profile: {profile or 'unknown'}",
        f"- artifact_namespace: {artifact_namespace or 'unknown'}",
        f"- run_mode: {run_mode or 'unknown'}",
        f"- registry_assets: {len(assets)}",
        f"- resolution_rows: {len(rows)}",
        "",
        "## Resolver Status Counts",
    ]
    if statuses:
        lines.extend(f"- {key}: {value}" for key, value in sorted(statuses.items()))
    else:
        lines.append("- none")
    lines.extend(["", "## Resolver Warning Counts"])
    if warnings:
        lines.extend(f"- {key}: {value}" for key, value in sorted(warnings.items()))
    else:
        lines.append("- none")
    lines.extend(["", "## Implemented Registry Inputs"])
    lines.extend([
        "- fixture registry",
        "- optional CoinGecko universe cache",
        "- official exchange artifacts",
        "- Coinalyze derivatives symbols",
    ])
    return "\n".join(lines) + "\n"


def artifact_conflicts(namespace_dir: str | Path | None) -> dict[str, int]:
    out = {
        "instrument_resolution_missing_canonical_id_when_fixture_has_it": 0,
        "instrument_resolution_quote_asset_misclassified": 0,
        "instrument_resolution_sector_visible_as_tradable": 0,
        "instrument_resolution_coinalyze_symbol_unlinked": 0,
    }
    if namespace_dir is None:
        return out
    directory = Path(namespace_dir).expanduser()
    registry = event_asset_registry.load_asset_registry_artifact(directory)
    index = _ResolverIndex(registry)
    resolution_rows = _load_jsonl(directory / INSTRUMENT_RESOLUTION_JSONL)
    out["instrument_resolution_coinalyze_symbol_unlinked"] += sum(
        1 for row in resolution_rows if "coinalyze_symbol_not_linked_to_asset" in _list(row.get("resolver_warnings"))
    )
    rows = [
        *_load_jsonl(directory / "event_integrated_radar_candidates.jsonl"),
        *_load_jsonl(directory / "event_official_listing_candidates.jsonl"),
        *_load_jsonl(directory / "event_core_opportunities.jsonl"),
    ]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        match = index.match(row)
        row_type = _text(row.get("row_type"))
        opportunity = _text(row.get("opportunity_type"))
        if match.asset is not None and row_type in OPPORTUNITY_ROW_TYPES and not _text(row.get("canonical_asset_id")):
            out["instrument_resolution_missing_canonical_id_when_fixture_has_it"] += 1
        quote = _bool(row.get("quote_asset_excluded")) or _quote_target_symbol(row) or (
            match.asset is not None and match.asset.quote_asset_excluded
        )
        if quote and (
            _bool(row.get("is_tradable_asset"))
            or opportunity in PROMOTED_OPPORTUNITY_TYPES
        ):
            out["instrument_resolution_quote_asset_misclassified"] += 1
        sector = _bool(row.get("is_theme_or_sector")) or _theme_target_symbol(row) or (
            match.asset is not None and match.asset.is_theme_or_sector
        )
        if sector and (
            _bool(row.get("is_tradable_asset"))
            or opportunity in PROMOTED_OPPORTUNITY_TYPES
        ):
            out["instrument_resolution_sector_visible_as_tradable"] += 1
    return out


class _ResolverIndex:
    def __init__(self, registry: Iterable[event_asset_registry.CanonicalAsset]):
        self.registry = tuple(registry)
        self.by_key: dict[str, list[event_asset_registry.CanonicalAsset]] = {}
        for asset in self.registry:
            for key in event_asset_registry.registry_index_keys(asset):
                self.by_key.setdefault(key, []).append(asset)

    def match(self, row: Mapping[str, Any]) -> ResolutionMatch:
        identifiers = _row_identifiers(row)
        for value, reason, confidence in identifiers:
            for key in event_asset_registry.identifier_key_variants(value):
                matches = self.by_key.get(key)
                if matches:
                    asset = sorted(matches, key=lambda item: _asset_preference(item), reverse=True)[0]
                    return ResolutionMatch(asset=asset, confidence=confidence, reason=reason, input_identifier=_text(value))
        return ResolutionMatch(asset=None, confidence=0.0, reason="unresolved", input_identifier=None)


def _row_identifiers(row: Mapping[str, Any]) -> tuple[tuple[str, str, float], ...]:
    values: list[tuple[str, str, float]] = []
    for key in ("canonical_asset_id",):
        _append_identifier(values, row.get(key), f"{key}_exact", 1.0)
    for key in ("validated_coin_id", "coin_id", "asset_coin_id"):
        _append_identifier(values, row.get(key), f"{key}_exact", 0.98)
    for key in ("asset_registry_coin_id", "asset_registry_symbol"):
        _append_identifier(values, row.get(key), f"{key}_exact", 0.96)
    for key in ("coinalyze_symbol", "market_symbol", "market", "perp_symbol"):
        _append_identifier(values, row.get(key), f"{key}_provider_symbol", 0.94)
    for key in ("base_symbol", "base_asset", "validated_symbol", "symbol", "asset_symbol"):
        _append_identifier(values, row.get(key), f"{key}_symbol", 0.9)
    for key in ("symbols", "announcement_symbols", "pairs", "spot_symbols", "perp_symbols", "coinalyze_symbols"):
        for item in _list(row.get(key)):
            _append_identifier(values, item, f"{key}_member", 0.88)
    for nested_key in ("derivatives_state_snapshot", "derivatives_snapshot", "official_exchange_event"):
        nested = row.get(nested_key)
        if isinstance(nested, Mapping):
            for item in _row_identifiers(nested):
                values.append((item[0], f"{nested_key}.{item[1]}", max(item[2] - 0.02, 0.7)))
    return tuple(dict.fromkeys(values))


def _append_identifier(values: list[tuple[str, str, float]], value: Any, reason: str, confidence: float) -> None:
    text = _text(value)
    if text:
        values.append((text, reason, confidence))


def _asset_preference(asset: event_asset_registry.CanonicalAsset) -> int:
    score = 0
    if asset.source == "fixture_registry":
        score += 50
    if asset.coin_id:
        score += 10
    if asset.coinalyze_symbols:
        score += 4
    if asset.bybit_symbols or asset.binance_symbols:
        score += 3
    if asset.is_tradable_asset:
        score += 1
    return score


def _asset_is_coinalyze_only(asset: event_asset_registry.CanonicalAsset) -> bool:
    return asset.source == "coinalyze_derivatives_artifact" and not (
        asset.bybit_symbols or asset.binance_symbols or asset.spot_symbols or asset.venues and set(asset.venues) - {"coinalyze"}
    )


def _has_coinalyze_symbol(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        _text(row.get(key))
        for key in ("coinalyze_symbol", "market_symbol", "market", "symbol")
    ).upper()
    provider = _text(row.get("provider") or row.get("source_origin") or row.get("_source_origin")).casefold()
    return "coinalyze" in provider or "PERP" in text or text.endswith("USDT")


def _major_pair_simple(row: Mapping[str, Any], asset: event_asset_registry.CanonicalAsset | None) -> bool:
    symbol = event_asset_registry.normalize_symbol(row.get("symbol") or row.get("validated_symbol"))
    major = symbol in event_asset_registry.MAJOR_BASE_ASSETS or bool(asset and asset.major_base_asset)
    return major and _bool(row.get("major_pair_simple_announcement"))


def _quote_target_symbol(row: Mapping[str, Any]) -> bool:
    return any(
        event_asset_registry.is_quote_asset_symbol(value)
        for value in (
            row.get("symbol"),
            row.get("validated_symbol"),
            row.get("base_symbol"),
            row.get("asset_symbol"),
        )
        if _text(value)
    )


def _theme_target_symbol(row: Mapping[str, Any]) -> bool:
    return any(
        event_asset_registry.is_theme_or_sector_symbol(value)
        for value in (row.get("symbol"), row.get("validated_symbol"), row.get("asset_symbol"))
        if _text(value)
    )


def _load_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.exists():
        return ()
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ()
    for line in lines:
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, Mapping):
            rows.append(dict(data))
    return tuple(rows)


def _list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(str(key) for key in value)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def _time_text(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if value:
        return str(value)
    return datetime.now(timezone.utc).isoformat()
