"""Merge helpers for integrated radar."""

from __future__ import annotations

import crypto_rsi_scanner.event_alpha.operations.market_provenance as event_market_provenance
import crypto_rsi_scanner.event_alpha.radar.catalyst_attribution as event_catalyst_attribution
import crypto_rsi_scanner.event_alpha.radar.source_independence as event_source_independence

from ... import decision_model as event_radar_decision_model
from ... import decision_safety as event_radar_decision_safety
from .runtime import *
from .merge_policy import *


@dataclass(frozen=True)
class _MergedFamilyContext:
    origins: tuple[str, ...]
    source_packs: tuple[str, ...]
    symbol: str
    coin_id: str
    canonical_asset_id: str
    resolver_confidences: list[float | None]
    resolver_warnings: tuple[str, ...]
    is_theme_or_sector: bool
    is_quote_asset: bool
    is_tradable_asset: bool
    market_snapshot: dict[str, Any]
    official_row: dict[str, Any] | None
    scheduled_row: dict[str, Any] | None
    unlock_row: dict[str, Any] | None
    dex_row: dict[str, Any] | None
    protocol_row: dict[str, Any] | None
    dex_liquidity_snapshot: dict[str, Any]
    protocol_metrics_snapshot: dict[str, Any]
    source_strength: str
    source_class: str
    source_pack: str
    impact_path: str
    accepted_evidence_count: int
    evidence_status: str
    raw_reaction: event_market_reaction.MarketReactionResult
    market_confirmation: event_market_confirmation.EventMarketConfirmationResult
    opportunity: str
    score: float
    level: str
    route: str
    state: str
    reason_codes: tuple[str, ...]
    warnings: tuple[str, ...]
    derivatives_metadata: dict[str, Any]
    derivatives_state_snapshot: dict[str, Any] | None
    integrated_market: dict[str, Any]
    latest_source: str
    latest_source_url: str
    latest_source_title: str

def _merge_family(
    key: str,
    rows: list[dict[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
    observed_at: str,
) -> dict[str, Any]:
    context = _merge_family_context(key, rows, observed_at=observed_at)
    candidate = _merge_family_base_fields(
        key,
        run_id=run_id,
        profile=profile,
        run_mode=run_mode,
        artifact_namespace=artifact_namespace,
        candidate_id=f"iar:{_digest(key)}",
    )
    candidate.update(_merge_family_identity_fields(
        rows,
        symbol=context.symbol,
        coin_id=context.coin_id,
        canonical_asset_id=context.canonical_asset_id,
        resolver_confidences=context.resolver_confidences,
        resolver_warnings=context.resolver_warnings,
        is_tradable_asset=context.is_tradable_asset,
        is_theme_or_sector=context.is_theme_or_sector,
        is_quote_asset=context.is_quote_asset,
    ))
    candidate.update(_merge_family_source_fields(
        rows,
        context.origins,
        context.source_packs,
        source_pack=context.source_pack,
        source_class=context.source_class,
        source_strength=context.source_strength,
    ))
    candidate.update(_merge_family_opportunity_fields(
        rows,
        context.raw_reaction,
        context.market_confirmation,
        opportunity=context.opportunity,
        level=context.level,
        route=context.route,
        state=context.state,
        score=context.score,
        source_strength=context.source_strength,
    ))
    candidate.update(_merge_family_market_fields(
        context.raw_reaction,
        market_snapshot=context.market_snapshot,
        integrated_market=context.integrated_market,
    ))
    candidate.update(_merge_family_derivatives_fields(
        context.market_confirmation,
        derivatives_metadata=context.derivatives_metadata,
        derivatives_state_snapshot=context.derivatives_state_snapshot,
        dex_liquidity_snapshot=context.dex_liquidity_snapshot,
        dex_row=context.dex_row,
        protocol_metrics_snapshot=context.protocol_metrics_snapshot,
        protocol_row=context.protocol_row,
    ))
    candidate.update(_merge_family_sidecar_event_fields(
        context.official_row,
        context.scheduled_row,
        context.unlock_row,
    ))
    candidate.update(_merge_family_evidence_fields(
        rows,
        context.raw_reaction,
        opportunity=context.opportunity,
        evidence_status=context.evidence_status,
        accepted_evidence_count=context.accepted_evidence_count,
        reason_codes=context.reason_codes,
        warnings=context.warnings,
    ))
    candidate.update(_merge_family_catalyst_attribution_fields(rows))
    candidate.update(_merge_family_source_independence_fields(rows))
    candidate.update(_merge_family_safety_fields(rows))
    candidate.update(_merge_family_incident_source_fields(
        rows,
        key=key,
        symbol=context.symbol,
        opportunity=context.opportunity,
        impact_path=context.impact_path,
        latest_source=context.latest_source,
        latest_source_url=context.latest_source_url,
        latest_source_title=context.latest_source_title,
    ))
    candidate.update(_merge_family_supporting_fields(
        rows,
        context.origins,
        impact_path=context.impact_path,
        score=context.score,
        route=context.route,
        observed_at=observed_at,
    ))
    if context.opportunity == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value:
        candidate["diagnostic_row_count"] = max(1, len(rows))
    candidate.update(
        event_radar_decision_model.evaluate_radar_decision(
            candidate,
            source_rows=rows,
            cfg=event_radar_decision_model.RadarDecisionConfig.from_runtime(config),
        ).to_dict()
    )
    return candidate


def _family_rows_with_catalyst_attributions(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Bind relevant family sources to one exact anomaly before merge policy."""

    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    anomalies = [row for row in materialized if _is_market_anomaly_row(row)]
    if not anomalies:
        return [
            _without_catalyst_attributions(
                row, rejection_reason="catalyst_attribution_without_anomaly"
            )
            if _row_catalyst_attributions(row)
            else row
            for row in materialized
        ]
    attributed: list[dict[str, Any]] = []
    for row in materialized:
        supplied = _row_catalyst_attributions(row)
        if _is_market_anomaly_row(row):
            attributed.append(
                _without_catalyst_attributions(
                    row, rejection_reason="catalyst_attribution_on_anomaly_row"
                )
                if supplied else row
            )
            continue
        if not _is_integrated_catalyst_source_row(row):
            attributed.append(
                _without_catalyst_attributions(
                    row, rejection_reason="catalyst_attribution_on_non_source_row"
                )
                if supplied else row
            )
            continue
        anomaly = _exact_attribution_anomaly(row, anomalies)
        if anomaly is None:
            attributed.append(
                _without_catalyst_attributions(
                    row, rejection_reason="catalyst_attribution_anomaly_binding_unavailable"
                )
                if supplied else row
            )
            continue
        binding_results = [
            (
                value,
                event_catalyst_attribution.validate_mapping_binding(
                    value, anomaly, row
                ),
            )
            for value in supplied
        ]
        if any(errors for _value, errors in binding_results):
            attributed.append(
                _without_catalyst_attributions(
                    row, rejection_reason="catalyst_attribution_mapping_binding_mismatch"
                )
            )
            continue
        existing = [dict(value) for value, _errors in binding_results]
        if existing:
            existing.sort(key=lambda value: str(value.get("attribution_digest") or ""))
            clean = _without_catalyst_attributions(row)
            clean["catalyst_attribution"] = existing[0]
            attributed.append(clean)
            continue
        source = dict(row)
        source.pop("catalyst_attribution", None)
        source.pop("catalyst_attributions", None)
        value = event_catalyst_attribution.assess_mapping_attribution(anomaly, source)
        if event_catalyst_attribution.validate_contract(value):
            attributed.append(row)
            continue
        row["catalyst_attribution"] = value
        attributed.append(row)
    return attributed


def _without_catalyst_attributions(
    row: Mapping[str, Any],
    *,
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    clean = dict(row)
    clean.pop("catalyst_attribution", None)
    clean.pop("catalyst_attributions", None)
    for key in ("data_quality", "score_components", "latest_score_components"):
        nested = clean.get(key)
        if not isinstance(nested, Mapping):
            continue
        copied = dict(nested)
        copied.pop("catalyst_attribution", None)
        copied.pop("catalyst_attributions", None)
        clean[key] = copied
    if rejection_reason:
        clean["catalyst_attribution_rejected"] = True
        clean["catalyst_attribution_rejection_reasons"] = [rejection_reason]
    return clean


def _merge_family_catalyst_attribution_fields(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    values: dict[str, dict[str, Any]] = {}
    rejection_reasons: list[str] = []
    for row in rows:
        if row.get("catalyst_attribution_rejected") is True:
            raw_reasons = row.get("catalyst_attribution_rejection_reasons")
            if isinstance(raw_reasons, (list, tuple)):
                rejection_reasons.extend(str(reason) for reason in raw_reasons)
        for value in _row_catalyst_attributions(row):
            if event_catalyst_attribution.validate_contract(value):
                continue
            copied = dict(value)
            values[str(copied["attribution_digest"])] = copied
    ordered = sorted(
        values.values(),
        key=lambda value: (
            not bool(value.get("causal_eligible")),
            str(value.get("source_public_at") or ""),
            str(value.get("source_id") or ""),
            str(value.get("attribution_digest") or ""),
        ),
    )
    result: dict[str, Any] = {}
    if ordered:
        result.update({
            "catalyst_attribution": dict(ordered[0]),
            "catalyst_attributions": [dict(value) for value in ordered],
        })
    if rejection_reasons:
        result.update({
            "catalyst_attribution_rejected": True,
            "catalyst_attribution_rejection_reasons": sorted(
                set(rejection_reasons)
            ),
        })
    return result


def _row_catalyst_attributions(row: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    values: list[Mapping[str, Any]] = []
    containers = [row]
    for key in ("data_quality", "score_components", "latest_score_components"):
        value = row.get(key)
        if isinstance(value, Mapping):
            containers.append(value)
    for container in containers:
        single = container.get("catalyst_attribution")
        if isinstance(single, Mapping):
            values.append(single)
        multiple = container.get("catalyst_attributions")
        if isinstance(multiple, (list, tuple)):
            values.extend(value for value in multiple if isinstance(value, Mapping))
    return tuple(values)


def _merge_family_source_independence_fields(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    contracts: dict[str, dict[str, Any]] = {}
    invalid_seen = False
    assessment_errors: list[str] = []
    statuses: list[str] = []
    for row in rows:
        containers: list[Mapping[str, Any]] = []
        for key in ("latest_score_components", "score_components"):
            value = row.get(key)
            if isinstance(value, Mapping):
                containers.append(value)
        containers.append(row)
        value = row.get("data_quality")
        if isinstance(value, Mapping):
            containers.append(value)
        assessment_errors.extend(
            str(item).strip()[:160]
            for container in containers
            for item in _source_independence_error_items(
                container.get("source_independence_errors")
            )
            if str(item).strip()
        )
        for container in containers:
            if "source_independence_status" not in container:
                continue
            status = str(
                container.get("source_independence_status") or ""
            ).strip().casefold()
            statuses.append(status)
            if status not in {"assessed", "unassessed", "rejected"}:
                assessment_errors.append("source_independence_status_invalid")
        selected = next(
            (container.get("source_independence") for container in containers if container.get("source_independence") not in (None, {})),
            None,
        )
        if selected is None:
            continue
        if not isinstance(selected, Mapping) or event_source_independence.validate_source_independence_contract(selected):
            invalid_seen = True
            continue
        copied = dict(selected)
        contracts[str(copied.get("contract_digest") or "")] = copied
    if contracts and any(status != "assessed" for status in statuses):
        assessment_errors.append("source_independence_status_contract_mismatch")
    if not contracts and "assessed" in statuses:
        assessment_errors.append("source_independence_assessed_without_contract")
    if "rejected" in statuses and not assessment_errors:
        assessment_errors.append("source_independence_rejected_without_error")
    assessment_errors = list(dict.fromkeys(assessment_errors))[:16]
    if invalid_seen or assessment_errors:
        return {
            "source_independence": {},
            "source_independence_status": "rejected",
            "source_independence_errors": assessment_errors or [
                "source_independence_contract_invalid"
            ],
            "source_independence_rejected": True,
            "source_independence_rejection_reason": (
                "assessment_error" if assessment_errors else "invalid_contract"
            ),
            "independent_source_count": 0,
            "independent_corroboration_count": 0,
            "source_content_cluster_count": 0,
        }
    if not contracts:
        return {
            "source_independence": {},
            "source_independence_status": "unassessed",
            "source_independence_errors": [],
            "independent_source_count": 0,
            "independent_corroboration_count": 0,
            "source_content_cluster_count": 0,
        }
    try:
        contract = event_source_independence.combine_source_independence_contracts(
            list(contracts.values())
        )
    except (TypeError, ValueError):
        return {
            "source_independence": {},
            "source_independence_status": "rejected",
            "source_independence_errors": [
                "source_independence_contract_union_failed"
            ],
            "source_independence_rejected": True,
            "source_independence_rejection_reason": "contract_union_failed",
            "independent_source_count": 0,
            "independent_corroboration_count": 0,
            "source_content_cluster_count": 0,
        }
    return {
        "source_independence": contract,
        "source_independence_status": "assessed",
        "source_independence_errors": [],
        "independent_source_count": int(contract.get("independent_evidence_count") or 0),
        "independent_corroboration_count": int(contract.get("independent_corroboration_count") or 0),
        "source_content_cluster_count": int(contract.get("content_cluster_count") or 0),
    }


def _source_independence_error_items(value: Any) -> tuple[Any, ...]:
    if value in (None, "", [], (), {}):
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


def _is_market_anomaly_row(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("row_type") or "") == "event_market_anomaly"
        or str(row.get("_source_origin") or "") == "market_anomaly"
    )


def _is_integrated_catalyst_source_row(row: Mapping[str, Any]) -> bool:
    if _row_catalyst_attributions(row):
        return True
    origin = str(row.get("_source_origin") or "").casefold()
    if origin in {
        "official_exchange", "scheduled_catalyst", "unlock", "news",
        "catalyst_search", "cryptopanic", "gdelt", "public_rss",
        "project_blog_rss", "external_catalyst",
    }:
        return True
    row_type = str(row.get("row_type") or "").casefold()
    return any(
        token in row_type
        for token in ("listing", "announcement", "catalyst", "unlock", "news", "source_evidence")
    )


def _exact_attribution_anomaly(
    source: Mapping[str, Any],
    anomalies: list[dict[str, Any]],
) -> dict[str, Any] | None:
    explicit_ids: set[str] = set()
    for key in ("market_anomaly_id", "anomaly_raw_id", "anomaly_id"):
        value = str(source.get(key) or "").strip()
        if value:
            explicit_ids.add(value)
    search = source.get("market_anomaly_catalyst_search")
    parent = search.get("parent") if isinstance(search, Mapping) else None
    if isinstance(parent, Mapping) and str(parent.get("raw_id") or "").strip():
        explicit_ids.add(str(parent["raw_id"]).strip())
    if explicit_ids:
        matches = [
            anomaly for anomaly in anomalies
            if explicit_ids & {
                str(anomaly.get(key) or "").strip()
                for key in ("raw_id", "market_anomaly_id", "anomaly_id")
            }
        ]
        return matches[0] if len(matches) == 1 else None
    return anomalies[0] if len(anomalies) == 1 else None

def _merge_family_context(key: str, rows: list[dict[str, Any]], *, observed_at: str) -> _MergedFamilyContext:
    origins = tuple(dict.fromkeys(str(row.get("_source_origin") or "unknown") for row in rows))
    source_packs = tuple(dict.fromkeys(str(row.get("source_pack") or "unknown") for row in rows if row.get("source_pack")))
    _select_primary(rows)
    symbol = _text(_first_value(rows, "symbol", "validated_symbol")) or "UNKNOWN"
    coin_id = _text(_first_value(rows, "coin_id", "validated_coin_id")) or symbol.casefold()
    canonical_asset_id = _text(_first_value(rows, "canonical_asset_id")) or coin_id or symbol
    resolver_confidences = [
        _float_value(row.get("instrument_resolver_confidence"))
        for row in rows
        if _float_value(row.get("instrument_resolver_confidence")) is not None
    ]
    resolver_warnings = tuple(dict.fromkeys(_merged_list(rows, "instrument_resolver_warnings")))
    is_theme_or_sector = any(_truthy(row.get("is_theme_or_sector")) for row in rows)
    is_quote_asset = any(_truthy(row.get("is_quote_asset")) or _truthy(row.get("quote_asset_excluded")) for row in rows)
    is_tradable_asset = not (is_theme_or_sector or is_quote_asset)
    explicit_tradable_values = [row.get("is_tradable_asset") for row in rows if row.get("is_tradable_asset") is not None]
    if explicit_tradable_values:
        is_tradable_asset = all(_truthy(value) for value in explicit_tradable_values) and not (is_theme_or_sector or is_quote_asset)
    market_snapshot = _best_market_snapshot(rows)
    derivatives_row = _best_derivatives_row(rows)
    official_row = _best_row(
        rows,
        lambda row: str(row.get("row_type")) in {
            "official_listing_candidate",
            "official_exchange_event_candidate",
        },
    )
    scheduled_row = _best_row(rows, lambda row: str(row.get("row_type")) == "scheduled_catalyst_event")
    unlock_row = _best_row(rows, lambda row: str(row.get("row_type")) in {"unlock_event", "unlock_candidate"})
    dex_row = _best_dex_row(rows)
    protocol_row = _best_protocol_row(rows)
    dex_liquidity_snapshot = _snapshot_from_row(dex_row, "dex_liquidity_snapshot")
    protocol_metrics_snapshot = _snapshot_from_row(protocol_row, "protocol_metrics_snapshot")
    source_strength = _best_source_strength(rows)
    source_class = _best_text(rows, "source_class") or "unknown"
    source_pack = _best_source_pack(rows, source_packs)
    impact_path = _best_impact_path(rows, source_pack)
    accepted_evidence_count = max(_int(row.get("accepted_evidence_count")) for row in rows)
    evidence_status = _best_text(rows, "evidence_acquisition_status") or ("accepted_evidence_found" if accepted_evidence_count else "not_executed")
    raw_reaction = event_market_reaction.evaluate_market_reaction({
        "symbol": symbol,
        "coin_id": coin_id,
        "source_class": source_class,
        "source_pack": source_pack,
        "impact_path_type": impact_path,
        "evidence_quality_score": _evidence_score(source_strength, accepted_evidence_count),
        "accepted_evidence_count": accepted_evidence_count or (1 if source_strength == "official_structured" else 0),
        "accepted_evidence_reason_codes": _merged_list(rows, "reason_codes"),
        "evidence_acquisition_status": evidence_status,
        "market_snapshot": market_snapshot,
        "derivatives_snapshot": dict(derivatives_row.get("derivatives_state_snapshot") or {}) if derivatives_row else {},
        "dex_liquidity_snapshot": dex_liquidity_snapshot,
        "event_age_hours": _first_value(rows, "event_age_hours"),
        "catalyst_fresh": True,
        "negative_catalyst": _negative_candidate(rows, impact_path, source_pack),
    })
    market_confirmation = event_market_confirmation.evaluate_market_confirmation({
        "market_snapshot": market_snapshot,
        "derivatives_snapshot": dict(derivatives_row.get("derivatives_state_snapshot") or {}) if derivatives_row else {},
        "dex_liquidity_snapshot": dex_liquidity_snapshot,
        "protocol_metrics_snapshot": protocol_metrics_snapshot,
        "playbook_type": impact_path,
        "now": observed_at,
        "allow_stale_fixture_market_context": True,
    })
    opportunity = _policy_opportunity_type(
        raw_reaction,
        rows,
        origins,
        official_row=official_row,
        dex_row=dex_row,
        protocol_row=protocol_row,
        market_confirmation=market_confirmation,
    )
    score = _score_for(opportunity, raw_reaction, rows, source_strength)
    level, route, state = _level_route_state(opportunity)
    reason_codes = tuple(dict.fromkeys((*_merged_list(rows, "reason_codes"), *raw_reaction.reason_codes)))
    warnings = tuple(dict.fromkeys((
        *_merged_list(rows, "warnings"),
        *resolver_warnings,
        *_policy_warnings(
            opportunity,
            rows,
            raw_reaction,
            dex_row=dex_row,
            protocol_row=protocol_row,
            market_confirmation=market_confirmation,
        ),
    )))
    derivatives_metadata = _derivatives_metadata(derivatives_row)
    derivatives_state_snapshot = dict(derivatives_row.get("derivatives_state_snapshot") or {}) if derivatives_row else None
    integrated_market = _integrated_market_confirmation(opportunity, raw_reaction, market_confirmation=market_confirmation)
    latest_source = _best_text(rows, "latest_source", "source_provider", "provider", "source")
    latest_source_url = _best_text(rows, "latest_source_url", "source_url", "url")
    latest_source_title = _best_text(rows, "latest_source_title", "source_title", "title", "event_name")
    return _MergedFamilyContext(
        origins=origins,
        source_packs=source_packs,
        symbol=symbol,
        coin_id=coin_id,
        canonical_asset_id=canonical_asset_id,
        resolver_confidences=resolver_confidences,
        resolver_warnings=resolver_warnings,
        is_theme_or_sector=is_theme_or_sector,
        is_quote_asset=is_quote_asset,
        is_tradable_asset=is_tradable_asset,
        market_snapshot=market_snapshot,
        official_row=official_row,
        scheduled_row=scheduled_row,
        unlock_row=unlock_row,
        dex_row=dex_row,
        protocol_row=protocol_row,
        dex_liquidity_snapshot=dex_liquidity_snapshot,
        protocol_metrics_snapshot=protocol_metrics_snapshot,
        source_strength=source_strength,
        source_class=source_class,
        source_pack=source_pack,
        impact_path=impact_path,
        accepted_evidence_count=accepted_evidence_count,
        evidence_status=evidence_status,
        raw_reaction=raw_reaction,
        market_confirmation=market_confirmation,
        opportunity=opportunity,
        score=score,
        level=level,
        route=route,
        state=state,
        reason_codes=reason_codes,
        warnings=warnings,
        derivatives_metadata=derivatives_metadata,
        derivatives_state_snapshot=derivatives_state_snapshot,
        integrated_market=integrated_market,
        latest_source=latest_source,
        latest_source_url=latest_source_url,
        latest_source_title=latest_source_title,
    )

def _merge_family_base_fields(
    key: str,
    *,
    run_id: str | None,
    profile: str | None,
    run_mode: str | None,
    artifact_namespace: str | None,
    candidate_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": candidate_id,
        "candidate_family_id": key,
        "core_opportunity_id": f"agg:{_digest(key)}",
        "run_id": run_id,
        "profile": profile,
        "run_mode": run_mode,
        "artifact_namespace": artifact_namespace,
    }

def _merge_family_identity_fields(
    rows: list[dict[str, Any]],
    *,
    symbol: str,
    coin_id: str,
    canonical_asset_id: str,
    resolver_confidences: list[float | None],
    resolver_warnings: tuple[str, ...],
    is_tradable_asset: bool,
    is_theme_or_sector: bool,
    is_quote_asset: bool,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "validated_symbol": symbol,
        "coin_id": coin_id,
        "validated_coin_id": coin_id,
        "canonical_asset_id": canonical_asset_id,
        "asset_registry_symbol": _best_text(rows, "asset_registry_symbol"),
        "asset_registry_coin_id": _best_text(rows, "asset_registry_coin_id"),
        "asset_registry_name": _best_text(rows, "asset_registry_name"),
        "asset_registry_liquidity_tier": _best_text(rows, "asset_registry_liquidity_tier"),
        "asset_registry_source": _best_text(rows, "asset_registry_source"),
        "asset_registry_venues": list(dict.fromkeys(_merged_list(rows, "asset_registry_venues"))),
        "asset_registry_spot_symbols": list(dict.fromkeys(_merged_list(rows, "asset_registry_spot_symbols"))),
        "asset_registry_perp_symbols": list(dict.fromkeys(_merged_list(rows, "asset_registry_perp_symbols"))),
        "asset_registry_coinalyze_symbols": list(dict.fromkeys(_merged_list(rows, "asset_registry_coinalyze_symbols"))),
        "asset_registry_bybit_symbols": list(dict.fromkeys(_merged_list(rows, "asset_registry_bybit_symbols"))),
        "asset_registry_binance_symbols": list(dict.fromkeys(_merged_list(rows, "asset_registry_binance_symbols"))),
        "instrument_resolver_status": _best_text(rows, "instrument_resolver_status"),
        "instrument_resolver_confidence": max(resolver_confidences) if resolver_confidences else 0.0,
        "instrument_resolver_match_reason": _best_text(rows, "instrument_resolver_match_reason"),
        "instrument_resolver_warnings": list(resolver_warnings),
        "instrument_identity_trusted": any(
            row.get("instrument_identity_trusted") is True for row in rows
        ),
        "is_tradable_asset": is_tradable_asset,
        "is_theme_or_sector": is_theme_or_sector,
        "is_quote_asset": is_quote_asset,
        "quote_asset_excluded": any(_truthy(row.get("quote_asset_excluded")) for row in rows),
        "base_asset_excluded": any(_truthy(row.get("base_asset_excluded")) for row in rows),
        "diagnostics_reason": _best_text(rows, "diagnostics_reason"),
    }

def _merge_family_source_fields(
    rows: list[dict[str, Any]],
    origins: tuple[str, ...],
    source_packs: tuple[str, ...],
    *,
    source_pack: str,
    source_class: str,
    source_strength: str,
) -> dict[str, Any]:
    fields = {
        "source_origin": "merged" if len(origins) > 1 else origins[0],
        "source_origins": list(origins),
        "source_pack": source_pack,
        "source_packs": list(source_packs or (source_pack,)),
        "source_class": source_class,
        "source_strength": source_strength,
        "candidate_provenance": _best_text(rows, "candidate_provenance"),
        "provider_generation_id": _best_text(rows, "provider_generation_id"),
        "provider_request_succeeded": any(_truthy(row.get("provider_request_succeeded")) for row in rows),
        "provider_source_artifact": _portable_evidence_path(
            _best_text(rows, "provider_source_artifact", "coinalyze_source_artifact_path")
        ),
        "request_ledger_path": _portable_evidence_path(_best_text(rows, "request_ledger_path")),
    }
    provenance = event_market_provenance.merge_market_provenance(rows)
    if provenance:
        fields["market_provenance"] = provenance
        fields.update(event_market_provenance.market_provenance_flat_fields(provenance))
    return fields

def _merge_family_opportunity_fields(
    rows: list[dict[str, Any]],
    raw_reaction: event_market_reaction.MarketReactionResult,
    market_confirmation: event_market_confirmation.EventMarketConfirmationResult,
    *,
    opportunity: str,
    level: str,
    route: str,
    state: str,
    score: float,
    source_strength: str,
) -> dict[str, Any]:
    anomaly_rows = [
        row
        for row in rows
        if str(row.get("row_type") or "") == "event_market_anomaly"
        or str(row.get("_source_origin") or "") == "market_anomaly"
    ]
    anomaly_type = _best_text(anomaly_rows, "anomaly_type", "market_state_class")
    anomaly_bucket = _best_text(
        anomaly_rows,
        "anomaly_bucket",
        "market_anomaly_bucket",
    )
    return {
        "opportunity_type": opportunity,
        "market_state_class": raw_reaction.market_state,
        "market_state": raw_reaction.market_state,
        "anomaly_type": anomaly_type,
        "anomaly_bucket": anomaly_bucket,
        "market_anomaly_bucket": anomaly_bucket,
        "market_anomaly_id": _best_text(anomaly_rows, "market_anomaly_id", "anomaly_id"),
        "final_opportunity_level": level,
        "opportunity_level": level,
        "opportunity_score_final": score,
        "final_opportunity_score": score,
        "route": route,
        "tier": route,
        "final_route_after_quality_gate": route,
        "alertable_after_quality_gate": False,
        "state": state,
        "final_state_after_quality_gate": state,
        "score": score,
        "source_requirements_met": _source_requirements_met(opportunity, rows, source_strength),
        "market_requirements_met": _market_requirements_met(opportunity, raw_reaction, market_confirmation=market_confirmation),
        "fade_requirements_met": _fade_requirements_met(opportunity, rows),
        "risk_requirements_met": _risk_requirements_met(opportunity, rows),
    }

def _merge_family_market_fields(
    raw_reaction: event_market_reaction.MarketReactionResult,
    *,
    market_snapshot: dict[str, Any],
    integrated_market: Mapping[str, Any],
) -> dict[str, Any]:
    quality = (
        market_snapshot.get("market_data_quality")
        if isinstance(market_snapshot.get("market_data_quality"), Mapping)
        else {}
    )
    source = (
        market_snapshot.get("market_data_source")
        or market_snapshot.get("source_provider")
        or market_snapshot.get("latest_source")
        or market_snapshot.get("source")
        or integrated_market["source"]
    )
    freshness = (
        market_snapshot.get("market_context_freshness_status")
        or market_snapshot.get("freshness_status")
        or integrated_market["freshness"]
    )
    snapshot_id = (
        market_snapshot.get("market_snapshot_id")
        or market_snapshot.get("market_history_observation_id")
        or quality.get("market_snapshot_id")
        or quality.get("baseline_observation_id")
    )
    return {
        "integrated_market_confirmation_level": integrated_market["level"],
        "integrated_market_confirmation_score": integrated_market["score"],
        "integrated_market_reaction_confirmation": integrated_market["reaction"],
        "integrated_market_context_source": integrated_market["source"],
        "integrated_market_freshness_status": integrated_market["freshness"],
        "market_context_source": source,
        "market_context_observed_at": (
            market_snapshot.get("observed_at") or market_snapshot.get("timestamp")
        ),
        "market_context_freshness_status": freshness,
        "market_data_freshness": freshness,
        "market_snapshot_id": snapshot_id,
        "market_state_snapshot": raw_reaction.market_state_snapshot.to_dict(),
        "latest_market_snapshot": market_snapshot,
        "market_snapshot": market_snapshot,
    }

def _merge_family_derivatives_fields(
    market_confirmation: event_market_confirmation.EventMarketConfirmationResult,
    *,
    derivatives_metadata: Mapping[str, Any],
    derivatives_state_snapshot: dict[str, Any] | None,
    dex_liquidity_snapshot: dict[str, Any],
    dex_row: Mapping[str, Any] | None,
    protocol_metrics_snapshot: dict[str, Any],
    protocol_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "derivatives_state_snapshot": derivatives_state_snapshot,
        "derivatives_snapshot": derivatives_state_snapshot,
        "crowding_class": derivatives_metadata.get("crowding_class"),
        "fade_readiness": derivatives_metadata.get("fade_readiness"),
        "crowding_exhaustion_evidence": derivatives_metadata.get("crowding_exhaustion_evidence") or [],
        "what_confirms_fade_review": derivatives_metadata.get("what_confirms_fade_review") or [],
        "what_invalidates_fade_review": derivatives_metadata.get("what_invalidates_fade_review") or [],
        "derivatives_warning_codes": derivatives_metadata.get("derivatives_warning_codes") or [],
        "dex_liquidity_snapshot": dex_liquidity_snapshot,
        "dex_liquidity_score": market_confirmation.dex_liquidity_score,
        "dex_liquidity_level": market_confirmation.dex_liquidity_level,
        "dex_liquidity_reasons": list(market_confirmation.dex_liquidity_reasons),
        "dex_freshness_status": market_confirmation.dex_freshness_status,
        "dex_onchain_classification": dex_row.get("classification") if dex_row else None,
        "protocol_metrics_snapshot": protocol_metrics_snapshot,
        "protocol_metrics_score": market_confirmation.protocol_metrics_score,
        "protocol_metrics_level": market_confirmation.protocol_metrics_level,
        "protocol_metrics_reasons": list(market_confirmation.protocol_metrics_reasons),
        "protocol_metrics_freshness_status": market_confirmation.protocol_metrics_freshness_status,
        "protocol_fundamentals_class": protocol_row.get("classification") if protocol_row else None,
        "coinalyze_derivatives_attached": bool(derivatives_metadata.get("coinalyze_derivatives_attached")),
        "coinalyze_artifact_namespace": derivatives_metadata.get("coinalyze_artifact_namespace"),
        "coinalyze_source_artifact_path": derivatives_metadata.get("coinalyze_source_artifact_path"),
        "coinalyze_provider_health_status": derivatives_metadata.get("coinalyze_provider_health_status"),
        "coinalyze_freshness_status": derivatives_metadata.get("coinalyze_freshness_status"),
    }

def _merge_family_sidecar_event_fields(
    official_row: Mapping[str, Any] | None,
    scheduled_row: Mapping[str, Any] | None,
    unlock_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "official_exchange_event": _compact_event(official_row) if official_row else None,
        "scheduled_catalyst_event": _compact_event(scheduled_row) if scheduled_row else None,
        "unlock_event": _compact_event(unlock_row) if unlock_row else None,
    }

def _merge_family_evidence_fields(
    rows: list[dict[str, Any]],
    raw_reaction: event_market_reaction.MarketReactionResult,
    *,
    opportunity: str,
    evidence_status: str,
    accepted_evidence_count: int,
    reason_codes: tuple[str, ...],
    warnings: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "evidence_acquisition_status": evidence_status,
        "accepted_evidence_count": accepted_evidence_count,
        "rejected_evidence_count": max(_int(row.get("rejected_evidence_count")) for row in rows),
        "why_now": _why_now_for(opportunity, raw_reaction, rows),
        "what_confirms": list(raw_reaction.what_confirms),
        "what_invalidates": list(raw_reaction.what_invalidates),
        "why_not_alertable": list(dict.fromkeys((*raw_reaction.why_not_alertable, *_lane_why_not(opportunity, rows)))),
        "reason_codes": list(reason_codes),
        "warnings": list(warnings),
    }

def _merge_family_safety_fields(rows: Iterable[Mapping[str, Any]]) -> dict[str, bool]:
    return {
        "research_only": True,
        "created_alert": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "notification_send_enabled": False,
        **event_radar_decision_safety.source_safety_attestations(rows),
    }

def _merge_family_incident_source_fields(
    rows: list[dict[str, Any]],
    *,
    key: str,
    symbol: str,
    opportunity: str,
    impact_path: str,
    latest_source: str,
    latest_source_url: str,
    latest_source_title: str,
) -> dict[str, Any]:
    incident_name = _canonical_incident_name(rows, symbol, opportunity)
    event_name = _best_text(rows, "event_name", "title") or incident_name
    return {
        "candidate_role": _best_text(rows, "candidate_role", "asset_role") or _candidate_role_for(opportunity),
        "primary_impact_path": impact_path,
        "impact_path_type": impact_path,
        "effective_playbook_type": impact_path,
        "playbook_type": impact_path,
        "impact_category": impact_path,
        "canonical_incident_name": incident_name,
        "incident_id": f"incident:{_digest(key)}",
        "event_name": event_name,
        "latest_event_name": event_name,
        "latest_source": latest_source,
        "source_provider": latest_source,
        "primary_source_provider": latest_source,
        "latest_source_url": latest_source_url,
        "source_url": latest_source_url,
        "latest_source_title": latest_source_title,
        "source_title": latest_source_title,
    }

def _merge_family_supporting_fields(
    rows: list[dict[str, Any]],
    origins: tuple[str, ...],
    *,
    impact_path: str,
    score: float,
    route: str,
    observed_at: str,
) -> dict[str, Any]:
    return {
        "supporting_evidence_quotes": _supporting_quotes(rows),
        "supporting_categories": list(dict.fromkeys(_merged_list(rows, "impact_path_type") or [impact_path])),
        "supporting_impact_paths": list(dict.fromkeys(_merged_list(rows, "impact_path_type") or [impact_path])),
        "source_count": len(origins),
        "latest_score": score,
        "latest_tier": route,
        "observed_at": observed_at,
        "created_at": observed_at,
    }


__all__ = ("_family_rows_with_catalyst_attributions", "_merge_family")
