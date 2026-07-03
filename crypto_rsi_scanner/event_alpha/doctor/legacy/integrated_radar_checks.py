"""Integrated Radar Checks for the legacy artifact doctor."""

from __future__ import annotations

from .runtime import *

def _structured_operator_path_file_conflicts(namespace_dir: str | Path) -> int:
    base = Path(namespace_dir)
    if not base.exists() or not base.is_dir():
        return 0
    conflicts = 0
    for path in sorted((*base.glob("*.json"), *base.glob("*.jsonl"))):
        if path.name.startswith("."):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.suffix == ".jsonl":
            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                conflicts += _structured_operator_path_conflict_count(payload)
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        conflicts += _structured_operator_path_conflict_count(payload)
    return conflicts

def _artifact_namespace_dir(*paths: str | Path | None) -> Path | None:
    for path in paths:
        if path in (None, ""):
            continue
        return Path(path).expanduser().parent
    return None

def _structured_operator_path_conflict_count(value: Any, *, key_name: str = "") -> int:
    if _operator_structured_path_debug_field(key_name):
        return 0
    if isinstance(value, Mapping):
        return sum(
            _structured_operator_path_conflict_count(item, key_name=str(key))
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set)):
        return sum(_structured_operator_path_conflict_count(item, key_name=key_name) for item in value)
    if _operator_structured_path_field(key_name) and event_artifact_paths.has_operator_absolute_path(value):
        return 1
    return 0

def _operator_structured_path_debug_field(key_name: str) -> bool:
    return str(key_name or "").casefold().endswith("_abs_debug")

def _operator_structured_path_field(key_name: str) -> bool:
    clean = str(key_name or "").casefold()
    if not clean or _operator_structured_path_debug_field(clean):
        return False
    if clean.endswith("_relpath") or clean.endswith("_relpaths"):
        return False
    return (
        clean.endswith("_path")
        or clean.endswith("_paths")
        or clean.endswith("_dir")
        or clean.endswith("_dirs")
        or "card_path" in clean
    )

def _integrated_candidate_core_card_conflicts(
    candidate: Mapping[str, Any],
    core_by_id: Mapping[str, Mapping[str, Any]],
    card_text_by_core: Mapping[str, str],
    out: dict[str, int],
) -> None:
    if str(candidate.get("opportunity_type") or "").strip().upper() == "DIAGNOSTIC":
        return
    core_id = str(candidate.get("core_opportunity_id") or "").strip()
    if not core_id:
        return
    core = core_by_id.get(core_id)
    if core is None:
        out["integrated_candidate_core_missing"] += 1
        return
    candidate_lane = str(candidate.get("opportunity_type") or "").strip()
    core_lane = str(core.get("opportunity_type") or "").strip()
    if candidate_lane and core_lane and candidate_lane != core_lane:
        out["integrated_candidate_core_opportunity_type_mismatch"] += 1
    if _integrated_opportunity_rank(core_lane) > _integrated_opportunity_rank(candidate_lane):
        out["integrated_core_silent_upgrade"] += 1
    candidate_market = str(candidate.get("market_state_class") or candidate.get("market_state") or "").strip()
    core_market = str(core.get("market_state_class") or core.get("market_state") or "").strip()
    if candidate_market and core_market and candidate_market != core_market:
        out["integrated_candidate_core_market_state_mismatch"] += 1
    for key in ("final_route_after_quality_gate", "final_state_after_quality_gate", "final_opportunity_level", "opportunity_level"):
        candidate_value = str(candidate.get(key) or "").strip()
        core_value = str(core.get(key) or "").strip()
        if candidate_value and core_value and candidate_value != core_value:
            out["integrated_candidate_core_route_level_mismatch"] += 1
            break
    candidate_reasons = set(_tuple_value(candidate.get("reason_codes")))
    core_reasons = set(_tuple_value(core.get("reason_codes")))
    if candidate_reasons and not candidate_reasons.issubset(core_reasons):
        out["integrated_candidate_core_reason_code_loss"] += 1
    candidate_url = str(candidate.get("source_url") or candidate.get("latest_source_url") or "").strip()
    core_url = str(core.get("source_url") or core.get("latest_source_url") or core.get("official_exchange_url") or "").strip()
    if candidate_url and not core_url:
        out["integrated_candidate_core_source_url_loss"] += 1
    if isinstance(candidate.get("official_exchange_event"), Mapping) and not isinstance(core.get("official_exchange_event"), Mapping):
        out["integrated_candidate_core_official_event_loss"] += 1
    if isinstance(candidate.get("scheduled_catalyst_event"), Mapping) and not isinstance(core.get("scheduled_catalyst_event"), Mapping):
        out["integrated_candidate_core_scheduled_event_loss"] += 1
    if isinstance(candidate.get("unlock_event"), Mapping) and not isinstance(core.get("unlock_event"), Mapping):
        out["integrated_candidate_core_unlock_event_loss"] += 1
    if isinstance(candidate.get("derivatives_state_snapshot"), Mapping) and not isinstance(core.get("derivatives_state_snapshot"), Mapping):
        out["integrated_candidate_core_derivatives_loss"] += 1
    if str(candidate_lane).upper() == "FADE_SHORT_REVIEW":
        if not str(core.get("crowding_class") or "").strip() or not str(core.get("fade_readiness") or "").strip():
            out["integrated_candidate_core_crowding_metadata_loss"] += 1
        if not _tuple_value(core.get("crowding_exhaustion_evidence")):
            out["integrated_candidate_core_crowding_metadata_loss"] += 1
    card_text = card_text_by_core.get(core_id, "")
    if not card_text:
        return
    derivatives_state = candidate.get("derivatives_state_snapshot")
    if not isinstance(derivatives_state, Mapping):
        derivatives_state = core.get("derivatives_state_snapshot") if isinstance(core.get("derivatives_state_snapshot"), Mapping) else {}
    if derivatives_state:
        if not _derivatives_metric_has_value(derivatives_state, "predicted_funding") and re.search(
            r"(?i)\bpredicted(?: funding)?=(?:n/a|[+-]?\d+(?:\.\d+)?%)",
            card_text,
        ):
            out["derivatives_card_metric_claim_without_data"] += 1
        if not _derivatives_metric_has_value(derivatives_state, "basis") and re.search(
            r"(?im)^-\s*Basis:\s*(?:n/a|[+-]?\d+(?:\.\d+)?%)",
            card_text,
        ):
            out["derivatives_card_metric_claim_without_data"] += 1
    has_coinalyze_crowding = (
        _integrated_row_has_coinalyze(candidate)
        and (
            str(candidate.get("crowding_class") or core.get("crowding_class") or "").casefold() in {"moderate", "high", "extreme"}
            or bool(_tuple_value(candidate.get("crowding_exhaustion_evidence") or core.get("crowding_exhaustion_evidence")))
        )
    )
    if has_coinalyze_crowding and "coinalyze source:" not in card_text.casefold():
        out["integrated_coinalyze_crowding_card_missing"] += 1
    card_lane = _markdown_bullet_value(card_text, "Opportunity type", section="Opportunity Lane")
    core_lane_lit = str(core.get("opportunity_type") or "").strip()
    if candidate_lane and card_lane and card_lane != candidate_lane:
        out["integrated_candidate_card_opportunity_type_mismatch"] += 1
    if core_lane_lit and card_lane and card_lane != core_lane_lit:
        out["card_opportunity_lane_core_mismatch"] += 1
    if (
        str(candidate.get("symbol") or "").upper() in {"BTC", "ETH", "USDT", "USDC", "FDUSD"}
        and _truthy(candidate.get("major_pair_simple_announcement"))
        and card_lane in {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH"}
    ):
        out["integrated_major_pair_card_early_long"] += 1
    card_why = _markdown_bullet_value(card_text, "Why now", section="Opportunity Lane")
    candidate_why = str(candidate.get("why_now") or "").strip()
    if candidate_why and card_why and candidate_why != card_why:
        out["integrated_candidate_card_why_now_mismatch"] += 1
    if card_why and "strong source with no reaction" in card_why.casefold() and candidate_why and candidate_why != card_why:
        out["integrated_card_generic_lane_override"] += 1
    if candidate_lane and not card_lane and candidate_lane not in card_text:
        out["integrated_candidate_card_opportunity_type_mismatch"] += 1
    if str(candidate_lane).upper() == "FADE_SHORT_REVIEW":
        if "Research-only" not in card_text or "Not a trade signal" not in card_text:
            out["integrated_fade_card_missing_disclaimer"] += 1
        if "Crowding class: unknown" in card_text or "Fade readiness: unknown" in card_text:
            out["integrated_fade_card_crowding_unknown"] += 1
        if "Derivatives crowding: n/a" in card_text or "Derivatives crowding: not available" in card_text:
            out["integrated_derivatives_display_contradiction"] += 1
    if str(candidate_lane).upper() in {"FADE_SHORT_REVIEW", "RISK_ONLY"}:
        outcome_section = _markdown_section(card_text, "Outcome Tracking")
        if outcome_section and (
            "Thesis-favorable move:" not in outcome_section
            or "Thesis interpretation:" not in outcome_section
        ):
            out["integrated_outcome_card_thesis_interpretation_missing"] += 1
        lower_outcome = outcome_section.casefold()
        if (
            "profit" in lower_outcome
            or "entry" in lower_outcome
            or "position" in lower_outcome
            or ("pnl" in lower_outcome and "not pnl" not in lower_outcome)
        ):
            out["integrated_outcome_card_trade_wording"] += 1
    if str(candidate_lane).upper() == "CONFIRMED_LONG_RESEARCH":
        if "confirmed_long_derivatives_crowding_warning" in _tuple_value(candidate.get("warnings")) and "confirmed_long_derivatives_crowding_warning" not in card_text:
            out["integrated_confirmed_long_crowding_warning_hidden"] += 1
        if "Market confirmation: none" in card_text and "Integrated market state:" not in card_text:
            out["integrated_market_confirmation_display_contradiction"] += 1
    if _truthy(candidate.get("market_requirements_met")) and "Market confirmation: none" in card_text and "Integrated market state:" not in card_text:
        out["integrated_market_confirmation_display_contradiction"] += 1
    official_event = candidate.get("official_exchange_event")
    if isinstance(official_event, Mapping):
        expected = [
            str(official_event.get("exchange") or "").strip(),
            str(official_event.get("event_type") or "").strip(),
            str(official_event.get("source_url") or "").strip(),
        ]
        if "Official Exchange Evidence" not in card_text and not any(value and value in card_text for value in expected):
            out["integrated_candidate_card_official_event_missing"] += 1
    if candidate_url and candidate_url not in card_text:
        out["integrated_candidate_card_source_url_missing"] += 1

def _integrated_opportunity_rank(value: object) -> int:
    text = str(value or "").strip().upper()
    ranks = {
        "DIAGNOSTIC": 0,
        "UNCONFIRMED_RESEARCH": 1,
        "EARLY_LONG_RESEARCH": 2,
        "RISK_ONLY": 2,
        "CONFIRMED_LONG_RESEARCH": 3,
        "FADE_SHORT_REVIEW": 3,
    }
    return ranks.get(text, 0)

def _markdown_bullet_value(text: str, label: str, *, section: str | None = None) -> str | None:
    body = text
    if section:
        marker = f"## {section}"
        idx = body.find(marker)
        if idx >= 0:
            body = body[idx + len(marker):]
            next_section = body.find("\n## ")
            if next_section >= 0:
                body = body[:next_section]
    pattern = re.compile(rf"^\s*-\s*{re.escape(label)}:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(body)
    return match.group(1).strip() if match else None

def _markdown_section(text: str, section: str) -> str:
    marker = f"## {section}"
    idx = text.find(marker)
    if idx < 0:
        return ""
    body = text[idx + len(marker):]
    next_section = body.find("\n## ")
    if next_section >= 0:
        body = body[:next_section]
    return body.strip()

def _integrated_manifest_mixed_timestamp_pairs(path: str | Path) -> int:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    if not isinstance(data, Mapping):
        return 0
    rows = data.get("sidecars")
    if not isinstance(rows, list):
        return 0
    conflicts = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("sidecar_research_observed_at") and row.get("sidecar_wall_started_at") and row.get("sidecar_wall_finished_at"):
            continue
        started = str(row.get("started_at") or "")
        finished = str(row.get("finished_at") or "")
        research = str(data.get("research_observed_at") or row.get("research_observed_at") or "")
        if started and finished and research and started == research and finished != research:
            conflicts += 1
    return conflicts

def _integrated_coinalyze_manifest_conflicts(
    path: str | Path,
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    out = {
        "integrated_coinalyze_loaded_no_rows_attached": 0,
        "integrated_coinalyze_missing_skip_reason": 0,
        "integrated_coinalyze_stale_loaded_without_warning": 0,
        "integrated_coinalyze_loaded_from_stale_namespace": 0,
    }
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    if not isinstance(data, Mapping):
        return out
    coinalyze = _coinalyze_manifest_row(data)
    if not coinalyze:
        return out
    state_rows = _as_int(coinalyze.get("coinalyze_derivatives_state_rows_loaded") or data.get("coinalyze_derivatives_state_rows_loaded"))
    crowding_rows = _as_int(coinalyze.get("coinalyze_crowding_candidates_loaded") or data.get("coinalyze_crowding_candidates_loaded"))
    fade_rows = _as_int(coinalyze.get("coinalyze_fade_review_candidates_loaded") or data.get("coinalyze_fade_review_candidates_loaded"))
    loaded_count = state_rows + crowding_rows + fade_rows
    skip_reason = str(coinalyze.get("coinalyze_skip_reason") or data.get("coinalyze_skip_reason") or "").strip()
    mode = str(coinalyze.get("mode") or "").strip().casefold()
    warnings = {
        str(item).strip().casefold()
        for item in (*_tuple_value(coinalyze.get("warnings")), *_tuple_value(data.get("warnings")))
        if str(item).strip()
    }
    namespace_status = str(
        coinalyze.get("coinalyze_artifact_namespace_status")
        or data.get("coinalyze_artifact_namespace_status")
        or ""
    ).strip().casefold()
    freshness = str(
        coinalyze.get("coinalyze_freshness_status")
        or data.get("coinalyze_freshness_status")
        or ""
    ).strip().casefold()
    attached = sum(1 for row in rows if _integrated_row_has_coinalyze(row))
    if loaded_count > 0 and attached == 0 and not skip_reason:
        out["integrated_coinalyze_loaded_no_rows_attached"] += 1
    if (mode.startswith("skipped") or loaded_count == 0) and not skip_reason:
        out["integrated_coinalyze_missing_skip_reason"] += 1
    if loaded_count > 0 and freshness in {"stale", "expired"} and not any("coinalyze_freshness" in item for item in warnings):
        out["integrated_coinalyze_stale_loaded_without_warning"] += 1
    if loaded_count > 0 and namespace_status == event_alpha_namespace_status.STATUS_STALE_DEPRECATED:
        out["integrated_coinalyze_loaded_from_stale_namespace"] += 1
    return out

def _coinalyze_manifest_row(data: Mapping[str, Any]) -> Mapping[str, Any]:
    sidecars = data.get("sidecars")
    if isinstance(sidecars, list):
        for item in sidecars:
            if isinstance(item, Mapping) and str(item.get("sidecar_name") or "") == "coinalyze":
                return item
    if data.get("coinalyze_artifact_namespace") or data.get("coinalyze_skip_reason"):
        return data
    return {}

def _integrated_row_has_coinalyze(row: Mapping[str, Any]) -> bool:
    state = row.get("derivatives_state_snapshot")
    if not isinstance(state, Mapping):
        state = row.get("derivatives_snapshot") if isinstance(row.get("derivatives_snapshot"), Mapping) else {}
    return bool(
        row.get("coinalyze_derivatives_attached")
        or row.get("coinalyze_artifact_namespace")
        or row.get("coinalyze_source_artifact_path")
        or state.get("coinalyze_artifact_namespace")
        or state.get("coinalyze_source_artifact_path")
    )

def _daily_brief_has_integrated_diagnostic_leak(text: str, rows: Iterable[Mapping[str, Any]]) -> bool:
    diagnostic_symbols = {
        str(row.get("symbol") or "").strip()
        for row in rows
        if str(row.get("opportunity_type") or "").strip().upper() == "DIAGNOSTIC"
        and str(row.get("symbol") or "").strip()
    }
    if not diagnostic_symbols:
        return False
    diagnostics_pos = text.find("## Diagnostics Appendix")
    visible_text = text if diagnostics_pos < 0 else text[:diagnostics_pos]
    return any(f"{symbol}/" in visible_text for symbol in diagnostic_symbols)

def _safe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

def _opportunity_lane_risk_only_missing_evidence(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            row.get("impact_path_type"),
            row.get("primary_impact_path"),
            row.get("source_pack"),
            row.get("evidence_acquisition_source_pack"),
            row.get("candidate_role"),
            row.get("playbook_type"),
            row.get("effective_playbook_type"),
            " ".join(str(item) for item in row.get("opportunity_type_reason_codes") or row.get("reason_codes") or ()),
            " ".join(str(item) for item in row.get("why_not_alertable") or row.get("opportunity_type_why_not_alertable") or ()),
        )
    ).casefold()
    risk_tokens = (
        "exploit",
        "security",
        "delisting",
        "regulatory",
        "legal",
        "unlock",
        "supply",
        "liquidity_risk",
        "risk_off",
        "sell_pressure",
        "bridge_compromise",
        "chain_halt",
        "protocol_fundamentals_deterioration",
        "fundamentals_deterioration",
    )
    if any(token in text for token in risk_tokens):
        return False
    missing_tokens = ("strong_source_missing", "market_reaction_missing", "confirmed_long_requirements_not_met")
    return any(token in text for token in missing_tokens)

def _opportunity_lane_diagnostic_visible(row: Mapping[str, Any]) -> bool:
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or row.get("tier") or "").upper()
    level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").casefold()
    state = str(row.get("final_state_after_quality_gate") or row.get("state") or "").upper()
    alertable_routes = {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH", "WATCHLIST", "TRIGGERED_FADE_RESEARCH"}
    alertable_states = {"WATCHLIST", "HIGH_PRIORITY", "TRIGGERED_FADE"}
    return route in alertable_routes or state in alertable_states or level in {"validated_digest", "watchlist", "high_priority"}

def _opportunity_lane_cryptopanic_only_narrative(row: Mapping[str, Any]) -> bool:
    source_class = str(row.get("source_class") or "").casefold()
    reason_codes = {str(item).casefold() for item in row.get("accepted_evidence_reason_codes") or row.get("reason_codes") or ()}
    if source_class != "cryptopanic_tagged" and "cryptopanic_currency_tag_match" not in reason_codes:
        return False
    if _raw_core_has_official_or_structured_evidence(row):
        return False
    text = " ".join(
        str(value or "")
        for value in (
            row.get("source_pack"),
            row.get("evidence_acquisition_source_pack"),
            row.get("impact_path_type"),
            row.get("primary_impact_path"),
            row.get("candidate_role"),
            row.get("playbook_type"),
            row.get("effective_playbook_type"),
            " ".join(str(item) for item in row.get("supporting_categories") or ()),
            " ".join(str(item) for item in row.get("supporting_impact_paths") or ()),
        )
    ).casefold()
    return any(token in text for token in ("fan", "sports", "proxy", "preipo", "pre-ipo", "rwa", "political_meme"))

def _raw_core_source_only_narrative(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            row.get("source_pack"),
            row.get("evidence_acquisition_source_pack"),
            row.get("impact_path_type"),
            row.get("primary_impact_path"),
            row.get("candidate_role"),
            row.get("playbook_type"),
            row.get("effective_playbook_type"),
            row.get("canonical_incident_name"),
            row.get("event_name"),
            row.get("latest_source_title"),
            " ".join(str(item) for item in row.get("supporting_categories") or ()),
            " ".join(str(item) for item in row.get("supporting_impact_paths") or ()),
        )
    ).casefold()
    narrative_tokens = (
        "fan_token",
        "fan token",
        "sports_fan",
        "sports fan",
        "world cup",
        "proxy",
        "preipo",
        "pre-ipo",
        "tokenized",
        "rwa",
        "political_meme",
        "venue_value",
    )
    if not any(token in text for token in narrative_tokens):
        return False
    if _raw_core_has_official_or_structured_evidence(row):
        return False
    accepted = _raw_int_value(row.get("accepted_evidence_count"), row.get("evidence_acquisition_accepted_count"))
    market_level = str(row.get("market_confirmation_level") or row.get("market_reaction_confirmation") or "").casefold()
    freshness = str(row.get("market_context_freshness_status") or "").casefold()
    market_score = _raw_float_value(row.get("market_confirmation_score"))
    has_market = market_level in {"moderate", "strong"} or (market_score is not None and market_score >= 40)
    if freshness in {"missing", "stale", "unknown", "none", ""}:
        has_market = False
    return accepted <= 1 and not has_market

def _raw_core_cryptopanic_tag_only_direct_path(row: Mapping[str, Any]) -> bool:
    source_classes = {str(row.get("source_class") or "").casefold()}
    reason_codes = {str(item).casefold() for item in row.get("accepted_evidence_reason_codes") or row.get("reason_codes") or ()}
    cryptopanic_tagged = "cryptopanic_tagged" in source_classes or "cryptopanic_currency_tag_match" in reason_codes
    if not cryptopanic_tagged:
        return False
    if _raw_core_has_official_or_structured_evidence(row):
        return False
    if _raw_core_source_only_narrative(row):
        return True
    impact_path = str(row.get("impact_path_type") or row.get("primary_impact_path") or "").casefold()
    return impact_path == "unlock_supply_event" and _raw_int_value(row.get("accepted_evidence_count"), row.get("evidence_acquisition_accepted_count")) <= 1

def _raw_core_has_official_or_structured_evidence(row: Mapping[str, Any]) -> bool:
    values = {
        str(row.get("source_class") or "").casefold(),
        str(row.get("source_pack") or "").casefold(),
        *(str(item).casefold() for item in row.get("accepted_evidence_reason_codes") or ()),
        *(str(item).casefold() for item in row.get("reason_codes") or ()),
    }
    return any(
        token in value
        for value in values
        for token in ("official", "structured", "tokenomist", "binance", "bybit", "exchange_listing", "direct_token_unlock_fact")
    )

def _raw_int_value(*values: Any) -> int:
    for value in values:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            continue
    return 0

def _raw_float_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

__all__ = (
    '_structured_operator_path_file_conflicts',
    '_artifact_namespace_dir',
    '_structured_operator_path_conflict_count',
    '_operator_structured_path_debug_field',
    '_operator_structured_path_field',
    '_integrated_candidate_core_card_conflicts',
    '_integrated_opportunity_rank',
    '_markdown_bullet_value',
    '_markdown_section',
    '_integrated_manifest_mixed_timestamp_pairs',
    '_integrated_coinalyze_manifest_conflicts',
    '_coinalyze_manifest_row',
    '_integrated_row_has_coinalyze',
    '_daily_brief_has_integrated_diagnostic_leak',
    '_safe_float',
    '_opportunity_lane_risk_only_missing_evidence',
    '_opportunity_lane_diagnostic_visible',
    '_opportunity_lane_cryptopanic_only_narrative',
    '_raw_core_source_only_narrative',
    '_raw_core_cryptopanic_tag_only_direct_path',
    '_raw_core_has_official_or_structured_evidence',
    '_raw_int_value',
    '_raw_float_value',
)
