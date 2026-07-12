"""Provider Readiness Checks for the artifact doctor."""

from __future__ import annotations

from .runtime import *
from .context_loading import _read_jsonl
from .integrated_radar_checks import (
    _daily_brief_has_integrated_diagnostic_leak,
    _integrated_candidate_core_card_conflicts,
    _integrated_coinalyze_manifest_conflicts,
    _integrated_manifest_mixed_timestamp_pairs,
    _opportunity_lane_cryptopanic_only_narrative,
    _opportunity_lane_diagnostic_visible,
    _opportunity_lane_risk_only_missing_evidence,
    _safe_float,
)
from .outcome_checks import (
    _integrated_calibration_conflicts,
    _integrated_delivery_conflicts,
    _integrated_outcome_conflicts,
    _integrated_performance_dashboard_conflicts,
    _structured_operator_path_conflicts,
)
from .source_coverage_checks import _card_text_by_core, _truthy, _tuple_value

def _opportunity_lane_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "confirmed_long_without_source_market": 0,
        "fade_short_without_crowding_exhaustion": 0,
        "early_long_without_fresh_strong_source": 0,
        "risk_only_missing_evidence_only": 0,
        "cryptopanic_only_narrative_confirmed_lane": 0,
        "diagnostic_visible_default_operator_lane": 0,
        "core_missing_market_state_snapshot": 0,
        "market_state_return_unit_missing": 0,
        "market_state_possible_double_scaled": 0,
        "market_state_lane_possible_double_scaled": 0,
    }
    for row in rows:
        if _fixture_support_row(row):
            continue
        lane = str(row.get("opportunity_type") or "").strip()
        if not lane:
            continue
        snapshot = row.get("market_state_snapshot")
        if not isinstance(snapshot, Mapping) or not snapshot:
            out["core_missing_market_state_snapshot"] += 1
            snapshot = {}
        elif not str(snapshot.get("return_unit") or "").strip():
            out["market_state_return_unit_missing"] += 1
        unit_warnings = set(event_market_units.validate_market_snapshot_units(
            snapshot if isinstance(snapshot, Mapping) else {},
            row.get("latest_market_snapshot") if isinstance(row.get("latest_market_snapshot"), Mapping) else row.get("market_snapshot") if isinstance(row.get("market_snapshot"), Mapping) else None,
        ))
        if any("possible_double_scaled" in warning or "unit_mismatch" in warning for warning in unit_warnings):
            out["market_state_possible_double_scaled"] += 1
            if lane in {"CONFIRMED_LONG_RESEARCH", "FADE_SHORT_REVIEW"}:
                out["market_state_lane_possible_double_scaled"] += 1
        source_met = _truthy(row.get("source_requirements_met") if row.get("source_requirements_met") is not None else row.get("opportunity_type_source_requirements_met"))
        market_met = _truthy(row.get("market_requirements_met") if row.get("market_requirements_met") is not None else row.get("opportunity_type_market_requirements_met"))
        fade_met = _truthy(row.get("fade_requirements_met") if row.get("fade_requirements_met") is not None else row.get("opportunity_type_fade_requirements_met"))
        source_strength = str(row.get("source_strength") or row.get("opportunity_type_source_strength") or "").casefold()
        market_state = str(row.get("market_state_class") or row.get("market_state") or "").casefold()
        if lane == "CONFIRMED_LONG_RESEARCH" and (not source_met or not market_met):
            out["confirmed_long_without_source_market"] += 1
        if lane == "FADE_SHORT_REVIEW" and (not fade_met or market_state not in {"blowoff_crowded", "post_event_fade_setup", "late_momentum"}):
            out["fade_short_without_crowding_exhaustion"] += 1
        if lane == "EARLY_LONG_RESEARCH" and (source_strength not in {"strong", "official_structured"} or market_state != "no_reaction"):
            out["early_long_without_fresh_strong_source"] += 1
        if lane == "CONFIRMED_LONG_RESEARCH" and _opportunity_lane_cryptopanic_only_narrative(row):
            out["cryptopanic_only_narrative_confirmed_lane"] += 1
        if lane == "RISK_ONLY" and _opportunity_lane_risk_only_missing_evidence(row):
            out["risk_only_missing_evidence_only"] += 1
        if lane == "DIAGNOSTIC" and _opportunity_lane_diagnostic_visible(row):
            out["diagnostic_visible_default_operator_lane"] += 1
    return out

def _market_anomaly_artifact_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "market_anomaly_missing_market_state_snapshot": 0,
        "market_anomaly_missing_market_state_class": 0,
        "market_anomaly_confirmed_breakout_missing_evidence": 0,
        "market_anomaly_suspicious_illiquid_promoted_confirmed": 0,
        "market_anomaly_created_alert_rows": 0,
        "market_anomaly_missing_freshness_status": 0,
        "market_anomaly_needs_search_without_plan": 0,
    }
    alertable_routes = {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH", "WATCHLIST", "TRIGGERED_FADE_RESEARCH"}
    alertable_tiers = {"RADAR_DIGEST", "WATCHLIST", "HIGH_PRIORITY", "TRIGGERED_FADE"}
    for row in rows:
        if str(row.get("row_type") or "") != "event_market_anomaly":
            continue
        anomaly_type = str(row.get("anomaly_type") or row.get("market_state") or "")
        if anomaly_type and not str(row.get("market_state_class") or "").strip():
            out["market_anomaly_missing_market_state_class"] += 1
        snapshot = row.get("market_state_snapshot")
        if not isinstance(snapshot, Mapping) or not snapshot:
            out["market_anomaly_missing_market_state_snapshot"] += 1
            snapshot = {}
        freshness = str(snapshot.get("freshness_status") or row.get("freshness_status") or "").strip()
        if not freshness:
            out["market_anomaly_missing_freshness_status"] += 1
        if anomaly_type == "confirmed_breakout":
            r4 = _safe_float(snapshot.get("return_4h"))
            r24 = _safe_float(snapshot.get("return_24h"))
            volume_z = _safe_float(snapshot.get("volume_zscore_24h"))
            rel_btc_4h = _safe_float(snapshot.get("relative_return_vs_btc_4h"))
            has_price = (r4 is not None and r4 >= 8.0) or (r24 is not None and r24 >= 15.0)
            has_volume = volume_z is not None and volume_z >= 2.0
            has_relative = rel_btc_4h is not None and rel_btc_4h >= 5.0
            if not (has_price and has_volume and has_relative):
                out["market_anomaly_confirmed_breakout_missing_evidence"] += 1
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").upper()
        tier = str(row.get("tier") or row.get("alert_tier") or "").upper()
        opportunity_type = str(row.get("opportunity_type") or "").upper()
        anomaly_bucket = str(row.get("anomaly_bucket") or row.get("market_anomaly_bucket") or "").strip()
        created_alert = bool(row.get("created_alert")) or bool(row.get("alert_id")) or route in alertable_routes or tier in alertable_tiers
        if created_alert:
            out["market_anomaly_created_alert_rows"] += 1
        if (anomaly_type == "suspicious_illiquid_move" or anomaly_bucket == "low_liquidity_suspicious") and (
            opportunity_type == "CONFIRMED_LONG_RESEARCH"
            or route in alertable_routes
            or tier in {"WATCHLIST", "HIGH_PRIORITY", "TRIGGERED_FADE"}
        ):
            out["market_anomaly_suspicious_illiquid_promoted_confirmed"] += 1
        has_source_plan = bool(row.get("suggested_source_packs_to_search")) or bool(row.get("search_queries"))
        if bool(row.get("needs_catalyst_search")) and not has_source_plan:
            out["market_anomaly_needs_search_without_plan"] += 1
    return out

def _official_exchange_artifact_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "official_exchange_candidate_missing_source_fields": 0,
        "official_exchange_listing_without_official_source": 0,
        "official_exchange_secret_leak": 0,
        "official_exchange_delisting_long_research": 0,
        "official_exchange_quote_asset_misclassified": 0,
        "official_exchange_major_pair_noise_promoted_early_long": 0,
        "official_exchange_created_alert_rows": 0,
    }
    quote_assets = {"USD", "USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "BTC", "ETH", "BNB", "EUR", "TRY", "BRL"}
    long_lanes = {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH"}
    alertable_routes = {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH", "WATCHLIST", "TRIGGERED_FADE_RESEARCH"}
    alertable_tiers = {"RADAR_DIGEST", "WATCHLIST", "HIGH_PRIORITY", "TRIGGERED_FADE"}
    listing_packs = {"official_exchange_listing_pack", "official_perp_listing_pack", "listing_liquidity_pack", "perp_listing_squeeze_pack"}
    for row in rows:
        if str(row.get("row_type") or "") != "official_listing_candidate":
            continue
        missing_required = any(not str(row.get(key) or "").strip() for key in ("source_url", "title", "published_at"))
        if missing_required:
            out["official_exchange_candidate_missing_source_fields"] += 1
        source_class = str(row.get("source_class") or "").strip()
        source_pack = str(row.get("source_pack") or "").strip()
        if source_pack in listing_packs and source_class != "official_exchange":
            out["official_exchange_listing_without_official_source"] += 1
        payload_text = json.dumps(row, sort_keys=True, default=str)
        if any(token in payload_text.casefold() for token in ("api_key", "apikey", "secret", "signature=", "x-mbx-apikey", "telegram_bot_token")):
            out["official_exchange_secret_leak"] += 1
        event_type = str(row.get("event_type") or "").strip()
        opportunity_type = str(row.get("opportunity_type") or "").strip().upper()
        if event_type == "delisting" and opportunity_type in long_lanes:
            out["official_exchange_delisting_long_research"] += 1
        symbol = str(row.get("symbol") or "").upper().strip()
        pair_text = " ".join(
            str(value or "")
            for value in (
                row.get("pairs"),
                row.get("announcement_pairs"),
                row.get("title"),
                row.get("body"),
                row.get("event_name"),
            )
        ).upper()
        quote_assets_for_row = {str(value).upper() for value in row.get("quote_assets") or () if str(value).strip()}
        symbol_is_quote_side = (
            symbol in quote_assets_for_row
            or bool(symbol and re.search(rf"/{re.escape(symbol)}\b", pair_text))
        )
        if symbol in quote_assets and symbol_is_quote_side:
            out["official_exchange_quote_asset_misclassified"] += 1
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").upper()
        tier = str(row.get("tier") or row.get("alert_tier") or "").upper()
        if bool(row.get("major_pair_simple_announcement")) and opportunity_type == "EARLY_LONG_RESEARCH":
            out["official_exchange_major_pair_noise_promoted_early_long"] += 1
        if bool(row.get("created_alert")) or bool(row.get("alert_id")) or route in alertable_routes or tier in alertable_tiers:
            out["official_exchange_created_alert_rows"] += 1
    return out

def _scheduled_catalyst_artifact_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "unlock_without_structured_evidence": 0,
        "unlock_missing_event_time": 0,
        "unlock_promoted_without_size_metrics": 0,
        "media_unlock_promoted_structured": 0,
        "stale_completed_catalyst_upcoming": 0,
        "calendar_event_missing_source_url": 0,
        "cryptopanic_unlock_proof": 0,
        "scheduled_catalyst_created_alert_rows": 0,
    }
    strict_lanes = {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH", "FADE_SHORT_REVIEW", "RISK_ONLY"}
    promoted_risk_lanes = {"FADE_SHORT_REVIEW", "RISK_ONLY"}
    media_classes = {"cryptopanic_tagged", "crypto_news", "broad_news", "media_calendar", "social_or_unknown"}
    trusted_unlock_classes = {
        "structured_unlock",
        "supply_data",
        "official_project",
        "official_exchange",
        "structured_calendar",
    }
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_type = str(row.get("row_type") or "")
        if row_type not in {"scheduled_catalyst_event", "unlock_event"}:
            continue
        event_type = str(row.get("event_type") or "")
        impact = str(row.get("impact_path_type") or "")
        source_class = str(row.get("source_class") or "").strip()
        lane = str(row.get("opportunity_type") or "").strip().upper()
        is_unlock = row_type == "unlock_event" or event_type in {"token_unlock", "vesting_cliff", "linear_emission"} or impact == "unlock_supply_event"
        if is_unlock:
            structured = bool(row.get("structured_unlock_evidence")) or source_class in trusted_unlock_classes
            if not structured and lane in strict_lanes:
                out["unlock_without_structured_evidence"] += 1
            if source_class in media_classes and lane in strict_lanes:
                out["media_unlock_promoted_structured"] += 1
            if source_class == "cryptopanic_tagged" and (
                bool(row.get("structured_unlock_evidence"))
                or "structured_unlock_source" in {str(item) for item in row.get("reason_codes") or ()}
                or lane in strict_lanes
            ):
                out["cryptopanic_unlock_proof"] += 1
            if not str(row.get("unlock_time") or row.get("event_start_time") or "").strip():
                out["unlock_missing_event_time"] += 1
            size_fields = (
                row.get("unlock_pct_circulating_supply"),
                row.get("unlock_pct_circulating"),
                row.get("unlock_pct_total_supply"),
                row.get("unlock_vs_30d_adv"),
                row.get("tokens_unlocked"),
                row.get("unlock_usd"),
            )
            if lane in promoted_risk_lanes and all(value in (None, "", [], {}, ()) for value in size_fields):
                out["unlock_promoted_without_size_metrics"] += 1
        if row_type == "scheduled_catalyst_event":
            if not str(row.get("source_url") or row.get("url") or "").strip():
                out["calendar_event_missing_source_url"] += 1
            status = str(row.get("event_status") or "").strip()
            age = _safe_float(row.get("event_age_hours"))
            if status == "completed" and age is not None and age > 24 and lane in {
                "EARLY_LONG_RESEARCH",
                "CONFIRMED_LONG_RESEARCH",
            }:
                out["stale_completed_catalyst_upcoming"] += 1
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").upper()
        tier = str(row.get("tier") or row.get("alert_tier") or "").upper()
        if bool(row.get("created_alert")) or bool(row.get("alert_id")) or route in {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH", "WATCHLIST", "TRIGGERED_FADE_RESEARCH"} or tier in {"RADAR_DIGEST", "WATCHLIST", "HIGH_PRIORITY", "TRIGGERED_FADE"}:
            out["scheduled_catalyst_created_alert_rows"] += 1
    return out

def _derivatives_crowding_artifact_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "fade_review_without_completed_move": 0,
        "fade_review_without_crowding_exhaustion": 0,
        "fade_review_created_triggered_fade": 0,
        "fade_review_created_normal_rsi_signal": 0,
        "fade_review_notification_missing_disclaimer": 0,
        "derivatives_artifact_secret_leak": 0,
        "derivatives_state_missing_freshness_status": 0,
        "derivatives_metric_claim_implemented_missing": 0,
        "derivatives_unit_metadata_missing": 0,
        "stale_derivatives_snapshot_promoted_fade_review": 0,
        "confirmed_long_crowded_without_warning": 0,
    }
    implemented_claims: set[str] = set()
    metrics_with_values: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_type = str(row.get("row_type") or "")
        text = json.dumps(row, sort_keys=True, default=str).casefold()
        if _derivatives_row_has_secret_leak(row) or any(token in text for token in ("bearer ", "sk-proj-")):
            out["derivatives_artifact_secret_leak"] += 1
        if row_type == "derivatives_state_snapshot":
            if not str(row.get("freshness_status") or "").strip():
                out["derivatives_state_missing_freshness_status"] += 1
            metric_status = row.get("supported_metric_status")
            if isinstance(metric_status, Mapping):
                for metric, status in metric_status.items():
                    if str(status) == event_derivatives_crowding.METRIC_STATUS_IMPLEMENTED:
                        implemented_claims.add(str(metric))
            for metric in event_derivatives_crowding.DERIVATIVES_SUPPORTED_METRICS:
                if _derivatives_metric_has_value(row, metric):
                    metrics_with_values.add(metric)
            out["derivatives_unit_metadata_missing"] += _derivatives_unit_metadata_missing(row)
            continue
        if row_type != "fade_short_review_candidate":
            continue
        opportunity = str(row.get("opportunity_type") or "").upper()
        crowding = str(row.get("crowding_class") or "").casefold()
        evidence = [str(item) for item in row.get("crowding_exhaustion_evidence") or () if str(item)]
        warnings = [str(item) for item in row.get("warnings") or () if str(item)]
        disclaimer = str(row.get("research_only_disclaimer") or "")
        state = row.get("derivatives_state_snapshot") if isinstance(row.get("derivatives_state_snapshot"), Mapping) else row
        if opportunity == "FADE_SHORT_REVIEW":
            if not bool(row.get("completed_move")):
                out["fade_review_without_completed_move"] += 1
            if not bool(row.get("fade_requirements_met")) or not evidence:
                out["fade_review_without_crowding_exhaustion"] += 1
            if "Research-only" not in disclaimer or "Not a trade signal" not in disclaimer:
                out["fade_review_notification_missing_disclaimer"] += 1
            freshness = str(state.get("derivatives_snapshot_freshness_status") or state.get("freshness_status") or "").casefold()
            if freshness in {"stale", "expired"}:
                out["stale_derivatives_snapshot_promoted_fade_review"] += 1
        if bool(row.get("triggered_fade_created")) or str(row.get("signal_type") or "").upper() == "TRIGGERED_FADE":
            out["fade_review_created_triggered_fade"] += 1
        if bool(row.get("normal_rsi_signal_written")):
            out["fade_review_created_normal_rsi_signal"] += 1
        if opportunity == "CONFIRMED_LONG_RESEARCH" and crowding in {"high", "extreme"}:
            if not any("crowding" in warning.casefold() for warning in warnings):
                out["confirmed_long_crowded_without_warning"] += 1
    for metric in sorted(implemented_claims - metrics_with_values):
        if metric:
            out["derivatives_metric_claim_implemented_missing"] += 1
    return out

def _derivatives_metric_has_value(row: Mapping[str, Any], metric: str) -> bool:
    values = {
        "open_interest": ("open_interest", "open_interest_delta_1h", "open_interest_delta_4h", "open_interest_delta_24h"),
        "funding_rate": ("funding_rate",),
        "predicted_funding": ("predicted_funding_rate",),
        "liquidations": ("liquidation_long_usd", "liquidation_short_usd", "liquidation_imbalance"),
        "long_short_ratio": ("long_short_ratio",),
        "basis": ("basis",),
        "perp_volume": ("perp_volume", "perp_spot_volume_ratio"),
    }
    return any(row.get(key) not in (None, "", [], {}, ()) for key in values.get(metric, ()))

def _derivatives_unit_metadata_missing(row: Mapping[str, Any]) -> int:
    checks = (
        ("open_interest", "open_interest_unit"),
        ("funding_rate", "funding_rate_unit"),
        ("predicted_funding", "funding_rate_unit"),
        ("basis", "basis_unit"),
        ("liquidations", "liquidation_unit"),
        ("perp_volume", "volume_unit"),
    )
    missing = 0
    for metric, unit_key in checks:
        if _derivatives_metric_has_value(row, metric) and not str(row.get(unit_key) or "").strip():
            missing += 1
    return missing

def _derivatives_row_has_secret_leak(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            lower = str(key).casefold()
            if any(token in lower for token in ("api_key", "auth_token", "secret", "token")):
                text = str(nested).strip()
                if text and text not in {"<redacted>", "redacted", "***", "none", "null"}:
                    return True
            if _derivatives_row_has_secret_leak(nested):
                return True
    elif isinstance(value, (list, tuple, set)):
        return any(_derivatives_row_has_secret_leak(item) for item in value)
    return False

def _integrated_radar_artifact_conflicts(
    rows: Iterable[Mapping[str, Any]],
    *,
    core_rows: Iterable[Mapping[str, Any]] = (),
    research_card_paths: Iterable[Path] = (),
    daily_brief_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    source_coverage_json_path: str | Path | None = None,
    delivery_path: str | Path | None = None,
    outcome_path: str | Path | None = None,
    preview_path: str | Path | None = None,
) -> dict[str, int]:
    out = _empty_integrated_radar_artifact_conflicts()
    materialized_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    production_rows = [row for row in materialized_rows if not _fixture_support_row(row)]
    materialized_core_rows = tuple(core_rows)
    cores_by_exact_context: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    cores_by_id: dict[str, list[dict[str, Any]]] = {}
    for core in materialized_core_rows:
        if not isinstance(core, Mapping):
            continue
        core_id = str(core.get("core_opportunity_id") or "").strip()
        if not core_id:
            continue
        materialized_core = dict(core)
        cores_by_id.setdefault(core_id, []).append(materialized_core)
        exact_key = _integrated_core_context_key(core)
        if exact_key is not None:
            cores_by_exact_context.setdefault(exact_key, []).append(materialized_core)
    card_text_by_core = _card_text_by_core(research_card_paths)
    row_count = 0
    for row in production_rows:
        row_count += 1
        core_id = str(row.get("core_opportunity_id") or "").strip()
        exact_key = _integrated_core_context_key(row)
        matches = (
            cores_by_exact_context.get(exact_key, ())
            if exact_key is not None
            else cores_by_id.get(core_id, ())
        )
        exact_core_by_id = {core_id: matches[0]} if core_id and len(matches) == 1 else {}
        _add_integrated_candidate_conflicts(
            row,
            exact_core_by_id,
            card_text_by_core,
            out,
        )

    _add_integrated_manifest_conflicts(out, row_count, manifest_path, production_rows)
    _add_integrated_source_coverage_conflicts(out, row_count, source_coverage_json_path)
    _add_integrated_daily_brief_conflicts(out, row_count, daily_brief_path, manifest_path, production_rows)
    _add_integrated_preview_conflicts(out, row_count, preview_path)
    _add_integrated_operator_path_conflicts(out, research_card_paths, daily_brief_path=daily_brief_path, preview_path=preview_path)
    delivery_rows = _integrated_delivery_rows(out, row_count, delivery_path, preview_path=preview_path)
    outcome_rows = _integrated_outcome_rows(out, materialized_rows, outcome_path)
    _add_integrated_calibration_performance_conflicts(out, outcome_path)
    out["operator_structured_path_absolute"] += _structured_operator_path_conflicts(
        (*materialized_rows, *materialized_core_rows, *delivery_rows, *outcome_rows)
    )
    return out


def _integrated_core_context_key(
    row: Mapping[str, Any],
) -> tuple[str, str, str, str] | None:
    values = tuple(
        row.get(field)
        for field in ("core_opportunity_id", "run_id", "profile", "artifact_namespace")
    )
    if not all(
        type(value) is str and value and value == value.strip()
        for value in values
    ):
        return None
    return values  # type: ignore[return-value]

def _empty_integrated_radar_artifact_conflicts() -> dict[str, int]:
    return {
        "integrated_candidate_missing_opportunity_type": 0,
        "integrated_candidate_missing_market_state_snapshot": 0,
        "integrated_confirmed_long_without_source_market": 0,
        "integrated_early_long_without_fresh_strong_source": 0,
        "integrated_fade_without_crowding_exhaustion": 0,
        "integrated_risk_without_evidence": 0,
        "integrated_market_anomaly_confirmed": 0,
        "integrated_cryptopanic_confirmed": 0,
        "integrated_major_pair_early_long": 0,
        "integrated_input_manifest_missing": 0,
        "integrated_source_coverage_json_missing": 0,
        "integrated_candidate_core_missing": 0,
        "integrated_candidate_core_opportunity_type_mismatch": 0,
        "integrated_candidate_core_market_state_mismatch": 0,
        "integrated_candidate_core_route_level_mismatch": 0,
        "integrated_candidate_core_reason_code_loss": 0,
        "integrated_candidate_core_source_url_loss": 0,
        "integrated_candidate_core_official_event_loss": 0,
        "integrated_candidate_core_scheduled_event_loss": 0,
        "integrated_candidate_core_unlock_event_loss": 0,
        "integrated_candidate_core_derivatives_loss": 0,
        "integrated_candidate_card_opportunity_type_mismatch": 0,
        "integrated_candidate_card_why_now_mismatch": 0,
        "integrated_major_pair_card_early_long": 0,
        "integrated_card_generic_lane_override": 0,
        "card_opportunity_lane_core_mismatch": 0,
        "integrated_candidate_card_official_event_missing": 0,
        "integrated_candidate_card_source_url_missing": 0,
        "integrated_candidate_core_crowding_metadata_loss": 0,
        "derivatives_card_metric_claim_without_data": 0,
        "integrated_coinalyze_crowding_card_missing": 0,
        "integrated_coinalyze_loaded_no_rows_attached": 0,
        "integrated_coinalyze_missing_skip_reason": 0,
        "integrated_coinalyze_stale_loaded_without_warning": 0,
        "integrated_coinalyze_loaded_from_stale_namespace": 0,
        "integrated_fade_card_crowding_unknown": 0,
        "integrated_fade_card_missing_disclaimer": 0,
        "integrated_confirmed_long_crowding_warning_hidden": 0,
        "integrated_dex_low_liquidity_promoted_confirmed": 0,
        "integrated_market_confirmation_display_contradiction": 0,
        "integrated_derivatives_display_contradiction": 0,
        "integrated_manifest_mixed_timestamp_pair": 0,
        "integrated_core_silent_upgrade": 0,
        "integrated_diagnostic_visible_in_default_operator_section": 0,
        "integrated_preview_missing_disclaimer": 0,
        "integrated_delivery_ledger_missing": 0,
        "integrated_preview_lane_mismatch": 0,
        "integrated_delivery_missing_disclaimer": 0,
        "integrated_delivery_sent_in_no_send": 0,
        "integrated_delivery_side_effect_flag": 0,
        "integrated_delivery_missing_skip_reasons": 0,
        "integrated_delivery_card_path_absolute": 0,
        "integrated_delivery_card_path_not_rendered": 0,
        "integrated_operator_markdown_absolute_path": 0,
        "operator_structured_path_absolute": 0,
        "integrated_api_preview_alerts_wording": 0,
        "integrated_manifest_daily_brief_unavailable": 0,
        "integrated_outcome_missing_for_candidate": 0,
        "integrated_outcome_side_effect_flag": 0,
        "integrated_outcome_schema_missing": 0,
        "integrated_outcome_missing_identity": 0,
        "integrated_outcome_returns_without_price": 0,
        "integrated_outcome_diagnostic_in_performance": 0,
        "integrated_calibration_diagnostic_in_main_priors": 0,
        "integrated_calibration_prior_safety_missing": 0,
        "integrated_calibration_api_alias_top_level": 0,
        "integrated_outcome_return_double_scaled": 0,
        "integrated_outcome_missing_data_unlabeled": 0,
        "integrated_outcome_thesis_move_missing": 0,
        "integrated_outcome_eligibility_contract_invalid": 0,
        "integrated_outcome_synthetic_evidence_leak": 0,
        "integrated_outcome_immature_validation_claim": 0,
        "integrated_outcome_duplicate_exact_identity": 0,
        "integrated_outcome_ambiguous_exact_identity": 0,
        "integrated_outcome_eligible_provenance_missing": 0,
        "integrated_outcome_identity_mismatch": 0,
        "integrated_outcome_card_thesis_interpretation_missing": 0,
        "integrated_outcome_card_trade_wording": 0,
        "integrated_performance_diagnostic_in_main_aggregate": 0,
        "integrated_performance_auto_apply_enabled": 0,
        "integrated_performance_low_sample_missing_warning": 0,
        "integrated_performance_trade_pnl_wording": 0,
        "integrated_created_normal_rsi_signal": 0,
        "integrated_created_triggered_fade": 0,
    }

def _add_integrated_candidate_conflicts(
    row: Mapping[str, Any],
    core_by_id: Mapping[str, Mapping[str, Any]],
    card_text_by_core: Mapping[str, str],
    out: dict[str, int],
) -> None:
    if _fixture_support_row(row):
        return
    lane = str(row.get("opportunity_type") or "").strip().upper()
    if not lane:
        out["integrated_candidate_missing_opportunity_type"] += 1
        return
    source_origins, source_packs = _integrated_source_sets(row)
    snapshot = row.get("market_state_snapshot")
    if lane not in {"UNCONFIRMED_RESEARCH", "DIAGNOSTIC"} and (not isinstance(snapshot, Mapping) or not snapshot):
        out["integrated_candidate_missing_market_state_snapshot"] += 1
    source_met = _truthy(row.get("source_requirements_met"))
    market_met = _truthy(row.get("market_requirements_met"))
    fade_met = _truthy(row.get("fade_requirements_met"))
    risk_met = _truthy(row.get("risk_requirements_met"))
    source_strength = str(row.get("source_strength") or "").casefold()
    market_state = str(row.get("market_state_class") or row.get("market_state") or "").casefold()
    if lane == "CONFIRMED_LONG_RESEARCH" and (not source_met or not market_met):
        out["integrated_confirmed_long_without_source_market"] += 1
    if lane == "EARLY_LONG_RESEARCH" and (
        source_strength not in {"strong", "official_structured"}
        or market_state != "no_reaction"
    ):
        out["integrated_early_long_without_fresh_strong_source"] += 1
    if lane == "FADE_SHORT_REVIEW" and (
        not fade_met
        or market_state not in {"blowoff_crowded", "post_event_fade_setup", "late_momentum"}
    ):
        out["integrated_fade_without_crowding_exhaustion"] += 1
    if lane == "RISK_ONLY" and not (
        risk_met
        or row.get("unlock_event")
        or "unlock_supply_pack" in source_packs
        or str(row.get("event_type") or "").casefold() in {"unlock", "delisting", "exploit"}
    ):
        out["integrated_risk_without_evidence"] += 1
    if lane == "CONFIRMED_LONG_RESEARCH" and source_origins == {"market_anomaly"}:
        out["integrated_market_anomaly_confirmed"] += 1
    if lane == "CONFIRMED_LONG_RESEARCH" and any("cryptopanic" in item for item in source_packs) and not (
        source_origins - {"source_news", "news", "cryptopanic"}
    ):
        out["integrated_cryptopanic_confirmed"] += 1
    if lane == "EARLY_LONG_RESEARCH" and _truthy(row.get("major_pair_simple_announcement")):
        out["integrated_major_pair_early_long"] += 1
    _add_integrated_dex_and_side_effect_conflicts(row, lane, out)
    _integrated_candidate_core_card_conflicts(row, core_by_id, card_text_by_core, out)

def _integrated_source_sets(row: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    source_origins = {str(item).strip().casefold() for item in row.get("source_origins") or () if str(item).strip()}
    source_packs = {str(item).strip().casefold() for item in row.get("source_packs") or () if str(item).strip()}
    if not source_origins:
        source_origin = str(row.get("source_origin") or "").strip().casefold()
        if source_origin:
            source_origins.add(source_origin)
    if not source_packs:
        source_pack = str(row.get("source_pack") or "").strip().casefold()
        if source_pack:
            source_packs.add(source_pack)
    return source_origins, source_packs


def _fixture_support_row(row: Mapping[str, Any]) -> bool:
    source_mode = str(row.get("candidate_source_mode") or "").strip().casefold()
    if source_mode in {"mocked_fixture", "fixture"}:
        return True
    if row.get("fixture_only") is True or row.get("test_fixture") is True:
        return True
    if row.get("contract_counted_candidate") is False and source_mode in {"mocked_fixture", "fixture", "fixture_smoke"}:
        return True
    run_mode = str(row.get("run_mode") or "").strip().casefold()
    return run_mode == "fixture" and source_mode in {"mocked_fixture", "fixture", ""}

def _add_integrated_dex_and_side_effect_conflicts(
    row: Mapping[str, Any],
    lane: str,
    out: dict[str, int],
) -> None:
    dex_class = str(row.get("dex_onchain_classification") or row.get("dex_anomaly_class") or "").strip()
    row_warnings = {str(item) for item in _tuple_value(row.get("warnings"))}
    if (
        lane == "CONFIRMED_LONG_RESEARCH"
        and (
            dex_class == event_dex_onchain_readiness.SUSPICIOUS_LOW_LIQUIDITY_PUMP
            or "dex_low_liquidity_confirmation_cap" in row_warnings
        )
    ):
        out["integrated_dex_low_liquidity_promoted_confirmed"] += 1
    if _truthy(row.get("normal_rsi_signal_written")):
        out["integrated_created_normal_rsi_signal"] += 1
    if _truthy(row.get("triggered_fade_created")) or str(row.get("signal_type") or "").upper() == "TRIGGERED_FADE":
        out["integrated_created_triggered_fade"] += 1

def _add_integrated_manifest_conflicts(
    out: dict[str, int],
    row_count: int,
    manifest_path: str | Path | None,
    materialized_rows: Iterable[Mapping[str, Any]],
) -> None:
    if row_count and manifest_path is not None and not Path(manifest_path).exists():
        out["integrated_input_manifest_missing"] += 1
    elif row_count and manifest_path is not None:
        out["integrated_manifest_mixed_timestamp_pair"] += _integrated_manifest_mixed_timestamp_pairs(manifest_path)
        _add_integrated_conflicts(out, _integrated_coinalyze_manifest_conflicts(manifest_path, materialized_rows))

def _add_integrated_source_coverage_conflicts(
    out: dict[str, int],
    row_count: int,
    source_coverage_json_path: str | Path | None,
) -> None:
    if row_count and source_coverage_json_path is not None and not Path(source_coverage_json_path).exists():
        out["integrated_source_coverage_json_missing"] += 1

def _add_integrated_daily_brief_conflicts(
    out: dict[str, int],
    row_count: int,
    daily_brief_path: str | Path | None,
    manifest_path: str | Path | None,
    materialized_rows: Iterable[Mapping[str, Any]],
) -> None:
    if row_count and daily_brief_path is not None:
        try:
            daily_text = Path(daily_brief_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            daily_text = ""
        if (
            manifest_path is not None
            and Path(manifest_path).exists()
            and "Input manifest: not available" in daily_text
        ):
            out["integrated_manifest_daily_brief_unavailable"] += 1
        if _daily_brief_has_integrated_diagnostic_leak(daily_text, materialized_rows):
            out["integrated_diagnostic_visible_in_default_operator_section"] += 1

def _add_integrated_preview_conflicts(
    out: dict[str, int],
    row_count: int,
    preview_path: str | Path | None,
) -> None:
    if row_count and preview_path is not None:
        try:
            preview_text = Path(preview_path).read_text(encoding="utf-8")
        except OSError:
            preview_text = ""
        if "Research-only" not in preview_text or "Not a trade signal" not in preview_text:
            out["integrated_preview_missing_disclaimer"] += 1
        if re.search(r"\bAlertable decisions:.*\bAlerts:\s*\d+", preview_text):
            out["integrated_api_preview_alerts_wording"] += 1
        if event_artifact_paths.has_operator_absolute_path(preview_text):
            out["integrated_operator_markdown_absolute_path"] += 1

def _add_integrated_operator_path_conflicts(
    out: dict[str, int],
    research_card_paths: Iterable[Path],
    *,
    daily_brief_path: str | Path | None,
    preview_path: str | Path | None,
) -> None:
    for operator_path in (*research_card_paths, *(path for path in (daily_brief_path, preview_path) if path is not None)):
        try:
            text = Path(operator_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if event_artifact_paths.has_operator_absolute_path(text):
            out["integrated_operator_markdown_absolute_path"] += 1

def _integrated_delivery_rows(
    out: dict[str, int],
    row_count: int,
    delivery_path: str | Path | None,
    *,
    preview_path: str | Path | None,
) -> list[Mapping[str, Any]]:
    delivery_rows = _read_jsonl(delivery_path) if delivery_path is not None and Path(delivery_path).exists() else []
    if row_count and delivery_path is not None and not Path(delivery_path).exists():
        out["integrated_delivery_ledger_missing"] += 1
    if delivery_rows:
        _add_integrated_conflicts(out, _integrated_delivery_conflicts(delivery_rows, preview_path=preview_path))
    return delivery_rows

def _integrated_outcome_rows(
    out: dict[str, int],
    materialized_rows: Iterable[Mapping[str, Any]],
    outcome_path: str | Path | None,
) -> list[Mapping[str, Any]]:
    outcome_rows = _read_jsonl(outcome_path) if outcome_path is not None and Path(outcome_path).exists() else []
    if outcome_rows:
        _add_integrated_conflicts(out, _integrated_outcome_conflicts(materialized_rows, outcome_rows))
    return outcome_rows

def _add_integrated_calibration_performance_conflicts(
    out: dict[str, int],
    outcome_path: str | Path | None,
) -> None:
    if outcome_path is not None:
        priors_path = Path(outcome_path).parent / event_integrated_radar.INTEGRATED_CALIBRATION_PRIORS_FILENAME
        _add_integrated_conflicts(out, _integrated_calibration_conflicts(priors_path))
        _add_integrated_conflicts(out, _integrated_performance_dashboard_conflicts(Path(outcome_path).parent))

def _add_integrated_conflicts(out: dict[str, int], updates: Mapping[str, int]) -> None:
    out.update(_merge_conflicts(out, updates))

def _merge_conflicts(base: Mapping[str, int], updates: Mapping[str, int]) -> dict[str, int]:
    out = dict(base)
    for key, value in updates.items():
        out[key] = int(out.get(key, 0)) + int(value or 0)
    return out

__all__ = (
    '_opportunity_lane_conflicts',
    '_market_anomaly_artifact_conflicts',
    '_official_exchange_artifact_conflicts',
    '_scheduled_catalyst_artifact_conflicts',
    '_derivatives_crowding_artifact_conflicts',
    '_derivatives_metric_has_value',
    '_derivatives_unit_metadata_missing',
    '_derivatives_row_has_secret_leak',
    '_integrated_radar_artifact_conflicts',
    '_merge_conflicts',
)
