"""Merge helpers for legacy integrated radar."""

from __future__ import annotations

from .runtime import *

def _coinalyze_match_index(sidecar_rows: Mapping[str, Iterable[Mapping[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for origin in ("coinalyze_derivatives_state", "coinalyze_derivatives_crowding", "coinalyze_fade_review"):
        for raw in sidecar_rows.get(origin, ()):
            if not isinstance(raw, Mapping):
                continue
            row = _coinalyze_integration_row(raw, origin=origin)
            for key in _asset_lookup_keys(row):
                out.setdefault(key, []).append(row)
    return out

def _coinalyze_integration_row(row: Mapping[str, Any], *, origin: str) -> dict[str, Any]:
    out = dict(row)
    out["_source_origin"] = origin
    out.setdefault("source_class", "derivatives_provider")
    out.setdefault("source_pack", "derivatives_crowding_pack")
    out.setdefault("impact_path_type", "derivatives_crowding_research")
    out.setdefault("accepted_evidence_count", 1)
    out.setdefault("evidence_quality_score", 82)
    if str(out.get("row_type") or "") == "derivatives_state_snapshot":
        state = dict(out)
        out.update({
            "row_type": "coinalyze_derivatives_state_integration",
            "event_name": f"{out.get('symbol') or out.get('market') or 'Coinalyze'} derivatives state",
            "derivatives_state_snapshot": state,
            "crowding_class": _state_crowding_class(state),
            "fade_readiness": "not_ready",
            "crowding_exhaustion_evidence": _state_crowding_evidence(state),
            "warnings": tuple(dict.fromkeys((*_list_values(out.get("warnings")), "coinalyze_state_attached_without_candidate"))),
        })
    return out

def _matching_coinalyze_rows(row: Mapping[str, Any], index: Mapping[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], ...]:
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in _asset_lookup_keys(row):
        for match in index.get(key, ()):
            match_id = _coinalyze_match_id(match)
            if match_id in seen:
                continue
            seen.add(match_id)
            matches.append(dict(match))
    return tuple(matches)

def _coinalyze_match_id(row: Mapping[str, Any]) -> str:
    for key in ("fade_review_candidate_id", "derivatives_state_id", "candidate_id"):
        value = str(row.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    return hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode("utf-8")).hexdigest()

def _state_crowding_evidence(state: Mapping[str, Any]) -> tuple[str, ...]:
    evidence: list[str] = []
    oi4 = _percent_value(state.get("open_interest_delta_4h"))
    oi24 = _percent_value(state.get("open_interest_delta_24h"))
    funding = _percent_value(state.get("funding_rate"))
    funding_z = _float_value(state.get("funding_zscore"))
    liq = _float_value(state.get("liquidation_imbalance"))
    perp_spot = _float_value(state.get("perp_spot_volume_ratio"))
    if oi4 is not None and oi4 >= 30:
        evidence.append("open_interest_delta_4h_high")
    if oi24 is not None and oi24 >= 35:
        evidence.append("open_interest_delta_24h_high")
    if funding is not None and abs(funding) >= 0.05:
        evidence.append("funding_elevated")
    if funding_z is not None and abs(funding_z) >= 2:
        evidence.append("funding_zscore_elevated")
    if liq is not None and abs(liq) >= 1.5:
        evidence.append("liquidation_imbalance_extreme")
    if perp_spot is not None and perp_spot >= 3:
        evidence.append("perp_spot_volume_divergence")
    return tuple(evidence)

def _state_crowding_class(state: Mapping[str, Any]) -> str:
    count = len(_state_crowding_evidence(state))
    if count >= 4:
        return "extreme"
    if count >= 2:
        return "high"
    if count == 1:
        return "moderate"
    return "none"

def _percent_value(value: Any) -> float | None:
    number = _float_value(value)
    if number is None:
        return None
    return number * 100.0 if abs(number) <= 3.0 else number

def _float_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _asset_lookup_keys(row: Mapping[str, Any]) -> set[str]:
    values: list[Any] = []
    for key in (
        "coin_id",
        "validated_coin_id",
        "canonical_asset_id",
        "symbol",
        "validated_symbol",
        "market",
        "market_symbol",
        "base_symbol",
    ):
        values.append(row.get(key))
    state = row.get("derivatives_state_snapshot")
    if isinstance(state, Mapping):
        for key in ("coin_id", "symbol", "market", "market_symbol", "canonical_asset_id"):
            values.append(state.get(key))
    out: set[str] = set()
    for value in values:
        text = _text(value)
        if not text:
            continue
        out.update(_asset_key_variants(text))
    return out

def _asset_key_variants(value: str) -> tuple[str, ...]:
    raw = value.strip()
    if not raw:
        return ()
    upper = raw.upper()
    market = upper.split(".", 1)[0]
    market = market.replace("_PERP", "")
    for suffix in ("USDT_PERP", "USD_PERP", "USDC_PERP", "USDT", "USDC", "USD", "PERP"):
        if market.endswith(suffix) and len(market) > len(suffix):
            market = market[: -len(suffix)]
            break
    return tuple(dict.fromkeys((raw.casefold(), upper, market.casefold(), market)))

def _official_exchange_integration_rows(
    events: Iterable[Mapping[str, Any]],
    candidates: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Return official listing candidates plus capped event rows filtered out by the sidecar."""
    rows = [_normalize_official_integration_row(row) for row in candidates if isinstance(row, Mapping)]
    represented: set[tuple[str, str]] = set()
    for row in rows:
        event_id = _text(row.get("official_exchange_event_id") or row.get("source_event_id") or row.get("event_id"))
        symbol = _text(row.get("symbol") or row.get("validated_symbol")).upper()
        if event_id and symbol:
            represented.add((event_id, symbol))
    for event in events:
        if not isinstance(event, Mapping):
            continue
        event_id = _text(event.get("official_exchange_event_id") or event.get("event_id"))
        symbols = [str(item).upper() for item in event.get("symbols") or () if str(item).strip()]
        coin_ids = [str(item) for item in event.get("coin_ids") or () if str(item).strip()]
        if not symbols:
            continue
        for index, symbol in enumerate(symbols):
            if event_id and (event_id, symbol) in represented:
                continue
            coin_id = coin_ids[index] if index < len(coin_ids) else symbol.casefold()
            row = dict(event)
            row.update({
                "row_type": "official_exchange_event_candidate",
                "symbol": symbol,
                "validated_symbol": symbol,
                "coin_id": coin_id,
                "validated_coin_id": coin_id,
                "accepted_evidence_count": 1,
                "rejected_evidence_count": 0,
                "evidence_acquisition_status": "accepted_evidence_found",
                "reason_codes": list(dict.fromkeys([
                    *(str(item) for item in event.get("reason_codes") or () if str(item)),
                    "official_exchange_event_observed",
                ])),
            })
            rows.append(row)
    return tuple(rows)

def _normalize_official_integration_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    symbol = _text(normalized.get("symbol") or normalized.get("validated_symbol"))
    coin_id = _text(normalized.get("coin_id") or normalized.get("validated_coin_id"))
    if not symbol:
        symbol = _symbol_for_coin_id(coin_id)
        if symbol:
            normalized["symbol"] = symbol
            normalized["validated_symbol"] = symbol
    event_type = str(normalized.get("event_type") or "").casefold()
    if (
        (symbol.upper() in {"BTC", "ETH", "USDT", "USDC", "FDUSD"} or coin_id in {"bitcoin", "ethereum", "tether", "usd-coin", "first-digital-usd"})
        and event_type in {"new_trading_pair", "spot_listing"}
    ):
        normalized["major_pair_simple_announcement"] = True
        reason_codes = [str(item) for item in normalized.get("reason_codes") or () if str(item)]
        normalized["reason_codes"] = list(dict.fromkeys((*reason_codes, "major_pair_simple_announcement_capped")))
    return normalized

def _symbol_for_coin_id(coin_id: str) -> str:
    return {
        "bitcoin": "BTC",
        "ethereum": "ETH",
        "tether": "USDT",
        "usd-coin": "USDC",
        "first-digital-usd": "FDUSD",
    }.get(str(coin_id or "").casefold(), "")

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
    origins = tuple(dict.fromkeys(str(row.get("_source_origin") or "unknown") for row in rows))
    source_packs = tuple(dict.fromkeys(str(row.get("source_pack") or "unknown") for row in rows if row.get("source_pack")))
    primary = _select_primary(rows)
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
    candidate_id = f"iar:{_digest(key)}"
    derivatives_metadata = _derivatives_metadata(derivatives_row)
    derivatives_state_snapshot = dict(derivatives_row.get("derivatives_state_snapshot") or {}) if derivatives_row else None
    integrated_market = _integrated_market_confirmation(opportunity, raw_reaction, market_confirmation=market_confirmation)
    latest_source = _best_text(rows, "latest_source", "source_provider", "provider", "source")
    latest_source_url = _best_text(rows, "latest_source_url", "source_url", "url")
    latest_source_title = _best_text(rows, "latest_source_title", "source_title", "title", "event_name")
    candidate = {
        "schema_version": 1,
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": candidate_id,
        "candidate_family_id": key,
        "core_opportunity_id": f"agg:{_digest(key)}",
        "run_id": run_id,
        "profile": profile,
        "run_mode": run_mode,
        "artifact_namespace": artifact_namespace,
        "symbol": symbol,
        "validated_symbol": symbol,
        "coin_id": coin_id,
        "validated_coin_id": coin_id,
        "canonical_asset_id": canonical_asset_id,
        "asset_registry_symbol": _best_text(rows, "asset_registry_symbol"),
        "asset_registry_coin_id": _best_text(rows, "asset_registry_coin_id"),
        "asset_registry_name": _best_text(rows, "asset_registry_name"),
        "asset_registry_liquidity_tier": _best_text(rows, "asset_registry_liquidity_tier"),
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
        "is_tradable_asset": is_tradable_asset,
        "is_theme_or_sector": is_theme_or_sector,
        "is_quote_asset": is_quote_asset,
        "quote_asset_excluded": any(_truthy(row.get("quote_asset_excluded")) for row in rows),
        "base_asset_excluded": any(_truthy(row.get("base_asset_excluded")) for row in rows),
        "diagnostics_reason": _best_text(rows, "diagnostics_reason"),
        "source_origin": "merged" if len(origins) > 1 else origins[0],
        "source_origins": list(origins),
        "source_pack": source_pack,
        "source_packs": list(source_packs or (source_pack,)),
        "source_class": source_class,
        "source_strength": source_strength,
        "opportunity_type": opportunity,
        "market_state_class": raw_reaction.market_state,
        "market_state": raw_reaction.market_state,
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
        "integrated_market_confirmation_level": integrated_market["level"],
        "integrated_market_confirmation_score": integrated_market["score"],
        "integrated_market_reaction_confirmation": integrated_market["reaction"],
        "integrated_market_context_source": integrated_market["source"],
        "integrated_market_freshness_status": integrated_market["freshness"],
        "market_state_snapshot": raw_reaction.market_state_snapshot.to_dict(),
        "latest_market_snapshot": market_snapshot,
        "market_snapshot": market_snapshot,
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
        "official_exchange_event": _compact_event(official_row) if official_row else None,
        "scheduled_catalyst_event": _compact_event(scheduled_row) if scheduled_row else None,
        "unlock_event": _compact_event(unlock_row) if unlock_row else None,
        "evidence_acquisition_status": evidence_status,
        "accepted_evidence_count": accepted_evidence_count,
        "rejected_evidence_count": max(_int(row.get("rejected_evidence_count")) for row in rows),
        "why_now": _why_now_for(opportunity, raw_reaction, rows),
        "what_confirms": list(raw_reaction.what_confirms),
        "what_invalidates": list(raw_reaction.what_invalidates),
        "why_not_alertable": list(dict.fromkeys((*raw_reaction.why_not_alertable, *_lane_why_not(opportunity, rows)))),
        "reason_codes": list(reason_codes),
        "warnings": list(warnings),
        "research_only": True,
        "created_alert": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "notification_send_enabled": False,
        "candidate_role": _best_text(rows, "candidate_role", "asset_role") or _candidate_role_for(opportunity),
        "primary_impact_path": impact_path,
        "impact_path_type": impact_path,
        "effective_playbook_type": impact_path,
        "playbook_type": impact_path,
        "impact_category": impact_path,
        "canonical_incident_name": _canonical_incident_name(rows, symbol, opportunity),
        "incident_id": f"incident:{_digest(key)}",
        "event_name": _best_text(rows, "event_name", "title") or _canonical_incident_name(rows, symbol, opportunity),
        "latest_event_name": _best_text(rows, "event_name", "title") or _canonical_incident_name(rows, symbol, opportunity),
        "latest_source": latest_source,
        "source_provider": latest_source,
        "primary_source_provider": latest_source,
        "latest_source_url": latest_source_url,
        "source_url": latest_source_url,
        "latest_source_title": latest_source_title,
        "source_title": latest_source_title,
        "supporting_evidence_quotes": _supporting_quotes(rows),
        "supporting_categories": list(dict.fromkeys(_merged_list(rows, "impact_path_type") or [impact_path])),
        "supporting_impact_paths": list(dict.fromkeys(_merged_list(rows, "impact_path_type") or [impact_path])),
        "source_count": len(origins),
        "latest_score": score,
        "latest_tier": route,
        "observed_at": observed_at,
        "created_at": observed_at,
    }
    if opportunity == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value:
        candidate["diagnostic_row_count"] = max(1, len(rows))
    return candidate

def _candidate_family_key(row: Mapping[str, Any]) -> str:
    asset = _text(
        row.get("canonical_asset_id")
        or row.get("coin_id")
        or row.get("validated_coin_id")
        or row.get("symbol")
        or row.get("validated_symbol")
        or "unknown"
    ).casefold()
    family = _impact_family(row)
    return "|".join(part for part in (asset, family) if part)

def _impact_family(row: Mapping[str, Any]) -> str:
    text = " ".join(str(row.get(key) or "") for key in ("source_pack", "impact_path_type", "event_type", "row_type")).casefold()
    if "unlock" in text:
        return "unlock_supply"
    if "protocol_fundamentals" in text:
        return "protocol_fundamentals"
    if "dex_liquidity" in text or str(row.get("row_type") or "") in {"event_dex_pool_state", "event_dex_pool_anomaly"}:
        return "listing_liquidity"
    if str(row.get("row_type") or "") == "event_market_anomaly":
        return "listing_liquidity"
    if (
        "perp" in text
        or "listing" in text
        or "exchange" in text
        or "trading_pair" in text
        or "derivatives" in text
        or "fade_short_review" in text
    ):
        return "listing_liquidity"
    if "sector" in text or str(row.get("symbol") or "").upper() == "SECTOR":
        return "sector_diagnostic"
    return "market_anomaly"

def _select_primary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(rows, key=lambda row: _opportunity_rank(str(row.get("opportunity_type") or "")), reverse=True)[0]

def _policy_opportunity_type(
    reaction: event_market_reaction.MarketReactionResult,
    rows: list[dict[str, Any]],
    origins: Iterable[str],
    *,
    official_row: Mapping[str, Any] | None,
    dex_row: Mapping[str, Any] | None = None,
    protocol_row: Mapping[str, Any] | None = None,
    market_confirmation: event_market_confirmation.EventMarketConfirmationResult | None = None,
) -> str:
    if any(_truthy(row.get("is_theme_or_sector")) or str(row.get("symbol") or "").upper() == "SECTOR" for row in rows):
        return event_market_reaction.EventOpportunityType.DIAGNOSTIC.value
    if any(_truthy(row.get("quote_asset_excluded")) or _truthy(row.get("is_quote_asset")) for row in rows):
        return event_market_reaction.EventOpportunityType.DIAGNOSTIC.value
    if _has_low_liquidity_suspicious_anomaly(rows):
        return event_market_reaction.EventOpportunityType.DIAGNOSTIC.value
    if _dex_row_is_suspicious_low_liquidity(dex_row):
        return event_market_reaction.EventOpportunityType.DIAGNOSTIC.value
    if official_row and bool(official_row.get("major_pair_simple_announcement")):
        return event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
    if _fade_requirements_met(event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value, rows):
        return event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value
    if _risk_requirements_met(event_market_reaction.EventOpportunityType.RISK_ONLY.value, rows):
        return event_market_reaction.EventOpportunityType.RISK_ONLY.value
    origin_set = set(origins)
    has_official = official_row is not None and str(official_row.get("source_class")) == "official_exchange"
    market_confirmed = reaction.market_state in {"confirmed_breakout", "stealth_accumulation"}
    confirmation_score = float(market_confirmation.market_confirmation_score if market_confirmation else 0.0)
    dex_sane = _dex_liquidity_sane(dex_row)
    protocol_growth = _protocol_growth(protocol_row)
    protocol_deterioration = _protocol_deterioration(protocol_row)
    liquidity_sane = dex_sane or _family_liquidity_sane(rows)
    if protocol_deterioration and liquidity_sane:
        return event_market_reaction.EventOpportunityType.RISK_ONLY.value
    if origin_set & {"market_anomaly"} and (origin_set & {"dex_pool_state", "dex_pool_anomaly"}):
        if not dex_sane:
            return event_market_reaction.EventOpportunityType.DIAGNOSTIC.value
        if market_confirmed or confirmation_score >= 50:
            return event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value
        return event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
    if protocol_growth:
        if not liquidity_sane:
            return event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
        if market_confirmed or confirmation_score >= 50:
            return event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value
        return event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value
    if has_official and market_confirmed:
        return event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value
    if (
        has_official
        and reaction.market_state == "no_reaction"
        and _family_extreme_crowding_after_completed_move(rows, reaction)
    ):
        return event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
    if has_official and reaction.market_state == "no_reaction":
        return event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value
    if origin_set == {"market_anomaly"}:
        return event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
    return reaction.opportunity_type

def _has_low_liquidity_suspicious_anomaly(rows: Iterable[Mapping[str, Any]]) -> bool:
    return any(
        str(row.get("anomaly_type") or row.get("market_state_class") or "") == "suspicious_illiquid_move"
        or str(row.get("anomaly_bucket") or row.get("market_anomaly_bucket") or "") == "low_liquidity_suspicious"
        or str(row.get("classification") or "") == event_dex_onchain_readiness.SUSPICIOUS_LOW_LIQUIDITY_PUMP
        for row in rows
    )

def _dex_row_is_suspicious_low_liquidity(row: Mapping[str, Any] | None) -> bool:
    if not isinstance(row, Mapping):
        return False
    return str(row.get("classification") or row.get("dex_anomaly_class") or "") == event_dex_onchain_readiness.SUSPICIOUS_LOW_LIQUIDITY_PUMP

def _dex_liquidity_sane(row: Mapping[str, Any] | None) -> bool:
    if not isinstance(row, Mapping):
        return False
    snapshot = _snapshot_from_row(row, "dex_liquidity_snapshot")
    liquidity = _float_value(snapshot.get("pool_liquidity_usd") or snapshot.get("liquidity_usd") or row.get("pool_liquidity_usd") or row.get("liquidity_usd"))
    if liquidity is None:
        return False
    if liquidity < 250_000:
        return False
    return not _dex_row_is_suspicious_low_liquidity(row)

def _family_liquidity_sane(rows: Iterable[Mapping[str, Any]]) -> bool:
    for row in rows:
        market = row.get("market_snapshot") if isinstance(row.get("market_snapshot"), Mapping) else row.get("market_state_snapshot")
        if not isinstance(market, Mapping):
            continue
        liquidity = _float_value(market.get("liquidity_usd") or market.get("order_book_depth_2pct") or market.get("depth_2pct_usd"))
        spread = _float_value(market.get("spread_bps") or market.get("bid_ask_spread_bps"))
        if liquidity is not None and liquidity >= 250_000 and (spread is None or spread <= 150):
            return True
    return False

def _protocol_growth(row: Mapping[str, Any] | None) -> bool:
    return isinstance(row, Mapping) and str(row.get("classification") or row.get("protocol_fundamentals_class") or "") == event_dex_onchain_readiness.PROTOCOL_REVENUE_TVL_GROWTH

def _protocol_deterioration(row: Mapping[str, Any] | None) -> bool:
    return isinstance(row, Mapping) and str(row.get("classification") or row.get("protocol_fundamentals_class") or "") == event_dex_onchain_readiness.PROTOCOL_FUNDAMENTALS_DETERIORATION

def _level_route_state(opportunity: str) -> tuple[str, str, str]:
    if opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
        return "exploratory", event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value, event_watchlist.EventWatchlistState.RADAR.value
    if opportunity == event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value:
        return "exploratory", event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value, event_watchlist.EventWatchlistState.RADAR.value
    if opportunity == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value:
        return "exploratory", event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value, event_watchlist.EventWatchlistState.RADAR.value
    if opportunity == event_market_reaction.EventOpportunityType.RISK_ONLY.value:
        return "local_only", event_alpha_router.EventAlphaRoute.STORE_ONLY.value, event_watchlist.EventWatchlistState.RAW_EVIDENCE.value
    if opportunity == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value:
        return "local_only", event_alpha_router.EventAlphaRoute.STORE_ONLY.value, event_watchlist.EventWatchlistState.RAW_EVIDENCE.value
    return "local_only", event_alpha_router.EventAlphaRoute.STORE_ONLY.value, event_watchlist.EventWatchlistState.RAW_EVIDENCE.value

def _opportunity_rank(opportunity: str) -> int:
    return {
        event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value: 6,
        event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value: 5,
        event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value: 4,
        event_market_reaction.EventOpportunityType.RISK_ONLY.value: 3,
        event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value: 2,
        event_market_reaction.EventOpportunityType.DIAGNOSTIC.value: 1,
    }.get(opportunity, 0)

def _candidate_sort_key(row: Mapping[str, Any]) -> tuple[int, float, str]:
    return (_opportunity_rank(str(row.get("opportunity_type") or "")), float(row.get("score") or 0), str(row.get("symbol") or ""))

def _score_for(
    opportunity: str,
    reaction: event_market_reaction.MarketReactionResult,
    rows: list[dict[str, Any]],
    source_strength: str,
) -> float:
    base = {
        event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value: 78.0,
        event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value: 66.0,
        event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value: 74.0,
        event_market_reaction.EventOpportunityType.RISK_ONLY.value: 58.0,
        event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value: 42.0,
        event_market_reaction.EventOpportunityType.DIAGNOSTIC.value: 10.0,
    }.get(opportunity, 25.0)
    if source_strength == "official_structured":
        base += 4.0
    if reaction.market_requirements_met:
        base += 4.0
    if any(row.get("accepted_evidence_count") for row in rows):
        base += 2.0
    return min(95.0, base)

def _source_requirements_met(opportunity: str, rows: list[dict[str, Any]], source_strength: str) -> bool:
    if opportunity in {
        event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value,
        event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value,
        event_market_reaction.EventOpportunityType.RISK_ONLY.value,
        event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value,
    }:
        if source_strength == "official_structured" or any(row.get("accepted_evidence_count") for row in rows):
            return True
        if opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
            return any(str(row.get("_source_origin") or "") == "market_anomaly" for row in rows) and _dex_liquidity_sane(_best_dex_row(rows))
        if opportunity in {
            event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value,
            event_market_reaction.EventOpportunityType.RISK_ONLY.value,
        }:
            return _protocol_growth(_best_protocol_row(rows)) or _protocol_deterioration(_best_protocol_row(rows))
    return False

def _market_requirements_met(
    opportunity: str,
    reaction: event_market_reaction.MarketReactionResult,
    *,
    market_confirmation: event_market_confirmation.EventMarketConfirmationResult | None = None,
) -> bool:
    if opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
        confirmation_score = float(market_confirmation.market_confirmation_score if market_confirmation else 0.0)
        return (
            reaction.market_state in {"confirmed_breakout", "stealth_accumulation"}
            or reaction.market_requirements_met
            or confirmation_score >= 50
        )
    if opportunity == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value:
        return reaction.market_state in {"post_event_fade_setup", "blowoff_crowded", "late_momentum"}
    return False

def _fade_requirements_met(opportunity: str, rows: list[dict[str, Any]]) -> bool:
    del opportunity
    return any(
        (
            bool(row.get("fade_requirements_met"))
            or str(row.get("opportunity_type")) == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value
        )
        and _row_derivatives_fresh_for_integration(row)
        and _row_has_crowding_evidence(row)
        and _row_completed_move(row)
        for row in rows
    )

def _risk_requirements_met(opportunity: str, rows: list[dict[str, Any]]) -> bool:
    if any(str(row.get("opportunity_type")) == event_market_reaction.EventOpportunityType.RISK_ONLY.value for row in rows):
        return True
    return any(_protocol_deterioration(row) for row in rows)

def _row_derivatives_state(row: Mapping[str, Any]) -> Mapping[str, Any]:
    state = row.get("derivatives_state_snapshot")
    if isinstance(state, Mapping):
        return state
    snapshot = row.get("derivatives_snapshot")
    if isinstance(snapshot, Mapping):
        return snapshot
    if str(row.get("row_type") or "") == "derivatives_state_snapshot":
        return row
    return {}

def _row_derivatives_fresh_for_integration(row: Mapping[str, Any]) -> bool:
    state = _row_derivatives_state(row)
    status = str(
        row.get("derivatives_snapshot_freshness_status")
        or state.get("derivatives_snapshot_freshness_status")
        or row.get("freshness_status")
        or state.get("freshness_status")
        or ""
    ).strip().casefold()
    return status in {"fresh", "fixture_allowed_stale"}

def _row_has_crowding_evidence(row: Mapping[str, Any]) -> bool:
    evidence = _list_values(row.get("crowding_exhaustion_evidence"))
    if evidence:
        return True
    state = _row_derivatives_state(row)
    return bool(_state_crowding_evidence(state))

def _row_completed_move(row: Mapping[str, Any]) -> bool:
    if bool(row.get("completed_move")):
        return True
    market = row.get("market_snapshot")
    if not isinstance(market, Mapping):
        market = row.get("market_state_snapshot") if isinstance(row.get("market_state_snapshot"), Mapping) else {}
    market_state = str(row.get("market_state") or row.get("market_state_class") or market.get("market_state") or "").casefold()
    r24 = _percent_value(market.get("return_24h") or market.get("price_change_24h"))
    r4 = _percent_value(market.get("return_4h") or market.get("price_change_4h"))
    age = _float_value(row.get("event_age_hours") or market.get("event_age_hours") or market.get("age_hours"))
    return any((
        market_state in {"blowoff_crowded", "post_event_fade_setup", "late_momentum"},
        r24 is not None and r24 >= 25,
        r4 is not None and r4 >= 15,
        age is not None and age >= 0 and ((r24 or 0) >= 15 or (r4 or 0) >= 8),
    ))

def _family_extreme_crowding_after_completed_move(
    rows: list[dict[str, Any]],
    reaction: event_market_reaction.MarketReactionResult,
) -> bool:
    for row in rows:
        crowding = str(row.get("crowding_class") or "").casefold()
        if not crowding:
            crowding = _state_crowding_class(_row_derivatives_state(row))
        if crowding != "extreme":
            continue
        if _row_completed_move(row) or reaction.market_state in {"blowoff_crowded", "post_event_fade_setup", "late_momentum"}:
            return True
    return False

def _best_market_snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    snapshots: list[dict[str, Any]] = []
    for row in rows:
        for key in ("market_state_snapshot", "market_snapshot", "latest_market_snapshot"):
            value = row.get(key)
            if isinstance(value, Mapping):
                snapshots.append(dict(value))
    if not snapshots:
        return {}
    return sorted(snapshots, key=lambda snap: len([v for v in snap.values() if v not in (None, "", [], {})]), reverse=True)[0]

def _best_row(rows: list[dict[str, Any]], predicate: Any) -> dict[str, Any] | None:
    for row in rows:
        if predicate(row):
            return row
    return None

def _best_derivatives_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    classified = [
        row for row in rows
        if isinstance(row.get("derivatives_state_snapshot"), Mapping)
        and (
            row.get("crowding_class")
            or row.get("fade_readiness")
            or row.get("crowding_exhaustion_evidence")
            or row.get("derivatives_warning_codes")
            or row.get("what_confirms_fade_review")
        )
    ]
    if classified:
        return sorted(
            classified,
            key=lambda row: _opportunity_rank(str(row.get("opportunity_type") or "")),
            reverse=True,
        )[0]
    return _best_row(rows, lambda row: bool(row.get("derivatives_state_snapshot")))

def _best_dex_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        row for row in rows
        if str(row.get("row_type") or "") in {"event_dex_pool_state", "event_dex_pool_anomaly"}
        or isinstance(row.get("dex_liquidity_snapshot"), Mapping)
        or str(row.get("source_pack") or "") == "dex_liquidity_pack"
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda row: (
            -1 if _dex_row_is_suspicious_low_liquidity(row) else 0,
            _float_value(row.get("pool_liquidity_usd") or row.get("liquidity_usd")) or 0.0,
            _float_value(row.get("dex_volume_24h") or row.get("volume_24h")) or 0.0,
        ),
        reverse=True,
    )[0]

def _best_protocol_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        row for row in rows
        if str(row.get("row_type") or "") == "event_protocol_fundamentals"
        or isinstance(row.get("protocol_metrics_snapshot"), Mapping)
        or str(row.get("source_pack") or "") == "protocol_fundamentals_pack"
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda row: (
            1 if _protocol_growth(row) or _protocol_deterioration(row) else 0,
            _float_value(row.get("tvl_usd") or row.get("tvl")) or 0.0,
        ),
        reverse=True,
    )[0]

def _snapshot_from_row(row: Mapping[str, Any] | None, key: str) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        return {}
    value = row.get(key)
    if isinstance(value, Mapping):
        return dict(value)
    if key == "dex_liquidity_snapshot":
        fields = (
            "pool_liquidity_usd",
            "liquidity_usd",
            "dex_volume_24h",
            "volume_24h",
            "dex_volume_zscore_24h",
            "dex_volume_change",
            "dex_volume_24h_change_pct",
            "dex_liquidity_change",
            "pool_liquidity_change_pct",
            "pool_age_hours",
            "source_url",
            "observed_at",
            "freshness_status",
            "provider",
        )
    else:
        fields = (
            "tvl",
            "tvl_usd",
            "fees_24h",
            "revenue_24h",
            "protocol_revenue_24h",
            "tvl_change_24h_pct",
            "fees_change_24h_pct",
            "revenue_change_24h_pct",
            "protocol_dex_volume_24h",
            "protocol_volume_change_24h_pct",
            "source_url",
            "observed_at",
            "freshness_status",
            "provider",
        )
    return {field: row.get(field) for field in fields if row.get(field) not in (None, "", [], {})}

def _derivatives_metadata(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        return {}
    warnings = list(dict.fromkeys((*_list_values(row.get("derivatives_warning_codes")), *_list_values(row.get("warnings")))))
    state = row.get("derivatives_state_snapshot") if isinstance(row.get("derivatives_state_snapshot"), Mapping) else {}
    coinalyze_namespace = row.get("coinalyze_artifact_namespace") or state.get("coinalyze_artifact_namespace")
    coinalyze_source_path = row.get("coinalyze_source_artifact_path") or state.get("coinalyze_source_artifact_path")
    coinalyze_provider_status = row.get("coinalyze_provider_health_status") or state.get("coinalyze_provider_health_status")
    coinalyze_freshness = (
        row.get("derivatives_snapshot_freshness_status")
        or state.get("derivatives_snapshot_freshness_status")
        or row.get("freshness_status")
        or state.get("freshness_status")
    )
    return {
        "crowding_class": row.get("crowding_class"),
        "fade_readiness": row.get("fade_readiness"),
        "crowding_exhaustion_evidence": _list_values(row.get("crowding_exhaustion_evidence")),
        "what_confirms_fade_review": _list_values(row.get("what_confirms_fade_review")),
        "what_invalidates_fade_review": _list_values(row.get("what_invalidates_fade_review")),
        "derivatives_warning_codes": warnings,
        "coinalyze_derivatives_attached": bool(coinalyze_namespace or coinalyze_source_path),
        "coinalyze_artifact_namespace": coinalyze_namespace,
        "coinalyze_source_artifact_path": coinalyze_source_path,
        "coinalyze_provider_health_status": coinalyze_provider_status,
        "coinalyze_freshness_status": coinalyze_freshness,
    }

def _integrated_market_confirmation(
    opportunity: str,
    reaction: event_market_reaction.MarketReactionResult,
    *,
    market_confirmation: event_market_confirmation.EventMarketConfirmationResult | None = None,
) -> dict[str, Any]:
    market_state = str(reaction.market_state or "")
    if opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
        confirmation_score = float(market_confirmation.market_confirmation_score if market_confirmation else 0.0)
        if confirmation_score >= 50:
            return {
                "level": "confirmed_breakout" if market_state in {"", "no_reaction"} else market_state,
                "score": confirmation_score,
                "reaction": market_state or "market_confirmation",
                "source": "integrated_market_confirmation",
                "freshness": reaction.market_state_snapshot.freshness_status or "fresh",
            }
        return {
            "level": market_state or "confirmed",
            "score": 80.0 if reaction.market_requirements_met else 0.0,
            "reaction": market_state or "confirmed_breakout",
            "source": "integrated_market_state",
            "freshness": reaction.market_state_snapshot.freshness_status or "fresh",
        }
    if opportunity == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value:
        return {
            "level": market_state or "fade_review_market_state",
            "score": 75.0 if reaction.fade_requirements_met else 0.0,
            "reaction": market_state or "post_event_fade_setup",
            "source": "integrated_market_state",
            "freshness": reaction.market_state_snapshot.freshness_status or "fresh",
        }
    if opportunity == event_market_reaction.EventOpportunityType.RISK_ONLY.value and market_state:
        return {
            "level": market_state,
            "score": 55.0,
            "reaction": market_state,
            "source": "integrated_market_state",
            "freshness": reaction.market_state_snapshot.freshness_status or "fresh",
        }
    return {
        "level": None,
        "score": None,
        "reaction": market_state or None,
        "source": "integrated_market_state" if market_state else None,
        "freshness": reaction.market_state_snapshot.freshness_status if reaction.market_state_snapshot else None,
    }

def _list_values(value: Any) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return [str(item) for item in value if str(item or "")]
    return [str(value)]

def _best_source_strength(rows: list[dict[str, Any]]) -> str:
    values = [str(row.get("source_strength") or "") for row in rows]
    if "official_structured" in values:
        return "official_structured"
    if "strong" in values:
        return "strong"
    if "tagged_context" in values:
        return "tagged_context"
    return "weak"

def _best_source_pack(rows: list[dict[str, Any]], source_packs: Iterable[str]) -> str:
    packs = list(source_packs)
    priority = (
        "perp_listing_squeeze_pack",
        "official_exchange_listing_pack",
        "listing_liquidity_pack",
        "dex_liquidity_pack",
        "protocol_fundamentals_pack",
        "unlock_supply_pack",
        "official_exchange_risk_pack",
        "market_anomaly_pack",
    )
    for wanted in priority:
        if wanted in packs:
            return wanted
    return packs[0] if packs else "integrated_radar_pack"

def _best_impact_path(rows: list[dict[str, Any]], source_pack: str) -> str:
    for row in rows:
        value = _text(row.get("impact_path_type") or row.get("playbook_type"))
        if value:
            return value
    if "unlock" in source_pack:
        return "unlock_supply_event"
    if "protocol_fundamentals" in source_pack:
        return "protocol_fundamentals"
    if "dex_liquidity" in source_pack:
        return "dex_liquidity_reaction"
    if "listing" in source_pack or "exchange" in source_pack or "perp" in source_pack:
        return "listing_liquidity_event"
    return "market_anomaly_unknown"

def _evidence_score(source_strength: str, accepted: int) -> float:
    if source_strength == "official_structured":
        return 92.0
    if accepted:
        return 75.0
    return 45.0

def _negative_candidate(rows: list[dict[str, Any]], impact_path: str, source_pack: str) -> bool:
    text = f"{impact_path} {source_pack}".casefold()
    return "unlock" in text or "delist" in text or any(bool(row.get("negative_catalyst")) for row in rows)

def _policy_warnings(
    opportunity: str,
    rows: list[dict[str, Any]],
    reaction: event_market_reaction.MarketReactionResult,
    *,
    dex_row: Mapping[str, Any] | None = None,
    protocol_row: Mapping[str, Any] | None = None,
    market_confirmation: event_market_confirmation.EventMarketConfirmationResult | None = None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if any(row.get("major_pair_simple_announcement") for row in rows):
        warnings.append("major_pair_simple_announcement_capped")
    if (
        opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value
        and not _market_requirements_met(opportunity, reaction, market_confirmation=market_confirmation)
    ):
        warnings.append("confirmed_long_requires_market_confirmation")
    if opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
        if any(
            (str(row.get("crowding_class") or _state_crowding_class(_row_derivatives_state(row))).casefold() in {"moderate", "high", "extreme"})
            and _row_has_crowding_evidence(row)
            for row in rows
        ):
            warnings.append("confirmed_long_derivatives_crowding_warning")
    if opportunity == event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value and _family_extreme_crowding_after_completed_move(rows, reaction):
        warnings.append("early_long_capped_by_extreme_crowding_after_completed_move")
    if _dex_row_is_suspicious_low_liquidity(dex_row):
        warnings.append("dex_low_liquidity_confirmation_cap")
    if protocol_row and not (_dex_liquidity_sane(dex_row) or _family_liquidity_sane(rows)):
        warnings.append("protocol_fundamentals_require_liquidity_sanity")
    return tuple(warnings)

def _lane_why_not(opportunity: str, rows: list[dict[str, Any]]) -> tuple[str, ...]:
    out: list[str] = []
    if any(row.get("major_pair_simple_announcement") for row in rows):
        out.append("major_pair_simple_announcement_not_alpha")
    if opportunity == event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value:
        out.append("strict_lane_requirements_not_met")
    if any("early_long_capped_by_extreme_crowding_after_completed_move" in _list_values(row.get("warnings")) for row in rows):
        out.append("early_long_capped_by_extreme_crowding_after_completed_move")
    if opportunity == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value:
        out.append("diagnostic_context_hidden_from_default_operator_sections")
    return tuple(out)

def _why_now_for(
    opportunity: str,
    reaction: event_market_reaction.MarketReactionResult,
    rows: list[dict[str, Any]],
) -> str:
    if opportunity == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value:
        return "official/structured source plus fresh market confirmation"
    if opportunity == event_market_reaction.EventOpportunityType.EARLY_LONG_RESEARCH.value:
        return "fresh official/structured catalyst with little market reaction yet"
    if opportunity == event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value:
        return "completed move with derivatives crowding/exhaustion evidence"
    if opportunity == event_market_reaction.EventOpportunityType.RISK_ONLY.value:
        return "credible downside/risk catalyst for research monitoring"
    if any(row.get("major_pair_simple_announcement") for row in rows):
        return "simple major-pair announcement capped as unconfirmed research"
    return reaction.why_now

def _candidate_role_for(opportunity: str) -> str:
    if opportunity == event_market_reaction.EventOpportunityType.DIAGNOSTIC.value:
        return "source_noise_control"
    return "direct_beneficiary"

def _canonical_incident_name(rows: list[dict[str, Any]], symbol: str, opportunity: str) -> str:
    title = _best_text(rows, "event_name", "title")
    return title or f"{symbol} {opportunity}"

def _compact_event(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    keys = (
        "row_type",
        "event_type",
        "exchange",
        "provider",
        "title",
        "event_name",
        "published_at",
        "effective_time",
        "event_start_time",
        "source_url",
        "reason_codes",
    )
    return {key: row.get(key) for key in keys if row.get(key) not in (None, "", [], {})}

def _supporting_quotes(rows: list[dict[str, Any]]) -> list[str]:
    quotes = []
    for row in rows:
        for key in ("title", "event_name", "description_summary"):
            value = _text(row.get(key))
            if value:
                quotes.append(value)
                break
    return list(dict.fromkeys(quotes))

def _candidate_summary_lines(row: Mapping[str, Any], *, compact: bool = False) -> list[str]:
    line = (
        f"- {row.get('symbol')}/{row.get('coin_id')} "
        f"{row.get('opportunity_type')} score={row.get('score')} "
        f"market={row.get('market_state_class')} source={row.get('source_pack')}"
    )
    lines = [line]
    if not compact:
        lines.append(f"  - Why now: {row.get('why_now') or 'unknown'}")
        if row.get("why_not_alertable"):
            lines.append("  - Why not alertable: " + "; ".join(str(item) for item in row.get("why_not_alertable") or ()))
    return lines

def _append_filtered(
    lines: list[str],
    rows: list[dict[str, Any]],
    predicate: Any,
    *,
    include_diagnostics: bool = False,
) -> None:
    selected = [
        row for row in rows
        if predicate(row)
        and (
            include_diagnostics
            or row.get("opportunity_type") != event_market_reaction.EventOpportunityType.DIAGNOSTIC.value
        )
    ]
    if not selected:
        lines.append("- None.")
        return
    for row in selected[:10]:
        lines.extend(_candidate_summary_lines(row, compact=True))

__all__ = (
    '_coinalyze_match_index',
    '_coinalyze_integration_row',
    '_matching_coinalyze_rows',
    '_coinalyze_match_id',
    '_state_crowding_evidence',
    '_state_crowding_class',
    '_percent_value',
    '_float_value',
    '_asset_lookup_keys',
    '_asset_key_variants',
    '_official_exchange_integration_rows',
    '_normalize_official_integration_row',
    '_symbol_for_coin_id',
    '_merge_family',
    '_candidate_family_key',
    '_impact_family',
    '_select_primary',
    '_policy_opportunity_type',
    '_has_low_liquidity_suspicious_anomaly',
    '_dex_row_is_suspicious_low_liquidity',
    '_dex_liquidity_sane',
    '_family_liquidity_sane',
    '_protocol_growth',
    '_protocol_deterioration',
    '_level_route_state',
    '_opportunity_rank',
    '_candidate_sort_key',
    '_score_for',
    '_source_requirements_met',
    '_market_requirements_met',
    '_fade_requirements_met',
    '_risk_requirements_met',
    '_row_derivatives_state',
    '_row_derivatives_fresh_for_integration',
    '_row_has_crowding_evidence',
    '_row_completed_move',
    '_family_extreme_crowding_after_completed_move',
    '_best_market_snapshot',
    '_best_row',
    '_best_derivatives_row',
    '_best_dex_row',
    '_best_protocol_row',
    '_snapshot_from_row',
    '_derivatives_metadata',
    '_integrated_market_confirmation',
    '_list_values',
    '_best_source_strength',
    '_best_source_pack',
    '_best_impact_path',
    '_evidence_score',
    '_negative_candidate',
    '_policy_warnings',
    '_lane_why_not',
    '_why_now_for',
    '_candidate_role_for',
    '_canonical_incident_name',
    '_compact_event',
    '_supporting_quotes',
    '_candidate_summary_lines',
    '_append_filtered',
)
