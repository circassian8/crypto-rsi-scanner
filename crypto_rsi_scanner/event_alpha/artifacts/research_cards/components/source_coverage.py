"""Source Coverage helpers for research cards."""

from __future__ import annotations

from .runtime import *
from ....radar.decision_model_surfaces import decision_model_values

def _source_lines(entry: event_watchlist.EventWatchlistEntry | None, alert: Mapping[str, Any] | None) -> list[str]:
    components = _card_components(entry, alert)
    sample = _first_accepted_evidence_sample(components)
    official_event = components.get("official_exchange_event") if isinstance(components.get("official_exchange_event"), Mapping) else {}
    scheduled_event = components.get("scheduled_catalyst_event") if isinstance(components.get("scheduled_catalyst_event"), Mapping) else {}
    unlock_event = components.get("unlock_event") if isinstance(components.get("unlock_event"), Mapping) else {}
    structured_event = official_event or scheduled_event or unlock_event
    latest_source = _display_text(
        components.get("latest_source")
        or components.get("source")
        or components.get("source_provider")
        or structured_event.get("provider")
        or structured_event.get("exchange")
    ) or _display_text(sample.get("provider") if sample else None) or _display_text(sample.get("provider_hint") if sample else None)
    source_url = (
        components.get("source_url")
        or components.get("latest_source_url")
        or structured_event.get("source_url")
        or structured_event.get("url")
        or (sample.get("source_url") if sample else None)
    )
    source_title = components.get("latest_source_title") or structured_event.get("title") or structured_event.get("event_name") or (sample.get("title") if sample else None)
    accepted_count = _int_value(components.get("evidence_acquisition_accepted_count")) or len(_accepted_evidence_samples(components))
    source_count = _int_value(components.get("source_count")) or (entry.source_count if entry is not None else 0) or accepted_count
    lines: list[str] = [
        f"- Latest source: {latest_source or 'not available'}",
        f"- Source count: {source_count if source_count else 'not available'}",
    ]
    if accepted_count:
        lines.append(f"- Accepted evidence count: {accepted_count}")
    if source_title:
        lines.append(f"- Latest evidence title: {source_title}")
    if source_url:
        lines.append(f"- URL: {source_url}")
    provider = _display_text(components.get("source_provider")) or _display_text(sample.get("provider") if sample else None)
    if provider:
        lines.append(f"- Provider: {provider}")
    return lines

def _official_exchange_evidence_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[str]:
    components = _card_components(entry, alert)
    event = components.get("official_exchange_event") if isinstance(components.get("official_exchange_event"), Mapping) else {}
    source_pack = str(components.get("source_pack") or "")
    source_class = str(components.get("source_class") or "")
    event_type = str(components.get("official_exchange_event_type") or event.get("event_type") or components.get("event_type") or "")
    if (
        source_class != "official_exchange"
        and not source_pack.startswith("official_exchange")
        and not source_pack.startswith("official_perp")
        and not event
    ):
        return []
    reason_codes = _list_strings(
        components.get("official_exchange_reason_codes")
        or event.get("reason_codes")
        or components.get("reason_codes")
        or components.get("accepted_evidence_reason_codes")
    )
    pairs = _list_strings(components.get("pairs") or event.get("pairs") or components.get("announcement_pairs"))
    contracts = _list_strings(components.get("contracts") or event.get("contracts") or components.get("announcement_contracts"))
    exchange = components.get("official_exchange") or event.get("exchange") or components.get("exchange")
    title = components.get("official_exchange_title") or event.get("title") or event.get("event_name") or components.get("latest_source_title")
    url = components.get("official_exchange_url") or event.get("source_url") or event.get("url") or components.get("source_url")
    published = components.get("official_exchange_published_at") or event.get("published_at") or components.get("published_at")
    effective = components.get("official_exchange_effective_time") or event.get("effective_time") or components.get("effective_time")
    lines = [
        f"- Exchange: {_display_text(exchange) or 'unknown'}",
        f"- Event type: {event_type or 'unknown'}",
        f"- Title: {_display_text(title) or 'unknown'}",
        f"- Source pack: {source_pack or 'unknown'}",
        f"- Token identity: {'resolved' if components.get('coin_id') or components.get('validated_coin_id') else 'unresolved'}",
        f"- Impact path: {_display_text(components.get('impact_path_type')) or 'unknown'}",
    ]
    if pairs:
        lines.append("- Pairs: " + ", ".join(pairs[:6]))
    if contracts:
        lines.append("- Contracts: " + ", ".join(contracts[:6]))
    if reason_codes:
        lines.append("- Reason codes: " + ", ".join(reason_codes[:8]))
    if published or effective:
        lines.append(
            "- Timing: "
            f"published={published or 'unknown'} "
            f"effective={effective or 'unknown'}"
        )
    if url:
        lines.append(f"- Official source: {url}")
    return lines

def _scheduled_catalyst_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[str]:
    components = _card_components(entry, alert)
    scheduled_event = components.get("scheduled_catalyst_event") if isinstance(components.get("scheduled_catalyst_event"), Mapping) else {}
    unlock_event = components.get("unlock_event") if isinstance(components.get("unlock_event"), Mapping) else {}
    event = unlock_event or scheduled_event
    row_type = str(components.get("row_type") or "")
    source_pack = str(components.get("source_pack") or "")
    impact = str(components.get("impact_path_type") or "")
    if not (
        row_type in {"scheduled_catalyst_event", "unlock_event"}
        or event
        or "unlock" in source_pack
        or "project_event" in source_pack
        or "unlock" in impact
    ):
        return []
    lines = [
        f"- Event type: {_display_text(components.get('event_type') or event.get('event_type')) or 'unknown'}",
        f"- Event status: {_display_text(components.get('event_status') or event.get('event_status')) or 'unknown'}",
        f"- Source class: {_display_text(components.get('source_class') or event.get('source_class')) or 'unknown'}",
        f"- Source pack: {source_pack or 'unknown'}",
        f"- Event start: {_display_text(components.get('event_start_time') or components.get('unlock_time') or event.get('event_start_time') or event.get('unlock_time')) or 'unknown'}",
        f"- Market state: {_display_text(components.get('market_state')) or 'unknown'}",
        f"- Opportunity type: {_display_text(components.get('opportunity_type')) or 'unknown'}",
    ]
    if components.get("unlock_time") or event.get("unlock_time") or components.get("unlock_pct_circulating_supply") is not None or event.get("unlock_pct_circulating_supply") is not None:
        lines.extend([
            f"- Unlock time: {_display_text(components.get('unlock_time') or event.get('unlock_time')) or 'unknown'}",
            f"- Unlock type: {_display_text(components.get('unlock_type') or event.get('unlock_type')) or 'unknown'}",
            f"- Unlock pct circulating: {_display_text(components.get('unlock_pct_circulating_supply') or event.get('unlock_pct_circulating_supply')) or 'n/a'}",
            f"- Unlock vs 30d ADV: {_display_text(components.get('unlock_vs_30d_adv') or event.get('unlock_vs_30d_adv')) or 'n/a'}",
            f"- Structured unlock proof: {str(bool(components.get('structured_unlock_evidence') or event.get('structured_unlock_evidence'))).lower()}",
        ])
    confirms = _list_strings(components.get("what_confirms"))
    invalidates = _list_strings(components.get("what_invalidates"))
    why_not = _list_strings(components.get("why_not_alertable"))
    if confirms:
        lines.append("- What confirms: " + "; ".join(confirms[:4]))
    if invalidates:
        lines.append("- What invalidates: " + "; ".join(invalidates[:4]))
    if why_not:
        lines.append(
            "- Why not eligible for strict catalyst alert: "
            + "; ".join(why_not[:5])
        )
    source_url = components.get("source_url") or event.get("source_url") or event.get("url")
    if source_url:
        lines.append(f"- Source: {source_url}")
    return lines

def _derivatives_crowding_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[str]:
    components = _card_components(entry, alert)
    state = components.get("derivatives_state_snapshot")
    if not isinstance(state, Mapping):
        state = {}
    opportunity = str(components.get("opportunity_type") or components.get("opportunity_type_original") or "")
    crowding = str(components.get("crowding_class") or "").strip()
    has_derivatives = bool(state) or opportunity == "FADE_SHORT_REVIEW" or bool(crowding)
    if not has_derivatives:
        return []
    evidence = _list_strings(components.get("crowding_exhaustion_evidence"))
    confirms = _list_strings(components.get("what_confirms_fade_review") or components.get("what_confirms"))
    invalidates = _list_strings(components.get("what_invalidates_fade_review") or components.get("what_invalidates"))
    lines = [
        "- Research-only. Not a trade signal.",
        f"- Provider: {_display_text(state.get('provider')) or 'unknown'}",
        f"- Market: {_display_text(state.get('market')) or 'unknown'}",
        f"- OI delta: 1h={_display_pct(state.get('open_interest_delta_1h'))} "
        f"4h={_display_pct(state.get('open_interest_delta_4h'))} "
        f"24h={_display_pct(state.get('open_interest_delta_24h'))}",
        f"- Funding: current={_display_pct(state.get('funding_rate'))} "
        f"predicted={_derivatives_metric_pct(state, 'predicted_funding', 'predicted_funding_rate')} "
        f"z={_display_text(state.get('funding_zscore')) or 'n/a'} "
        f"unit={_display_text(state.get('funding_rate_unit')) or 'unknown'}",
        f"- Basis: {_derivatives_metric_pct(state, 'basis', 'basis')} "
        f"unit={_display_text(state.get('basis_unit')) or 'unknown'}",
        f"- Liquidation imbalance: {_display_text(state.get('liquidation_imbalance')) or 'n/a'}",
        f"- Metric status: {_derivatives_metric_status_summary(state)}",
        f"- Unit metadata: {_derivatives_unit_summary(state)}",
        f"- Freshness: snapshot={_display_text(state.get('derivatives_snapshot_freshness_status') or state.get('freshness_status')) or 'unknown'} "
        f"oi={_display_text(state.get('open_interest_freshness')) or 'unknown'} "
        f"funding={_display_text(state.get('funding_freshness')) or 'unknown'} "
        f"liquidations={_display_text(state.get('liquidation_freshness')) or 'unknown'} "
        f"long_short={_display_text(state.get('long_short_freshness')) or 'unknown'} "
        f"basis={_display_text(state.get('basis_freshness')) or 'unknown'}",
        f"- Crowding class: {crowding or 'unknown'}",
        f"- Fade readiness: {_display_text(components.get('fade_readiness')) or 'unknown'}",
    ]
    coinalyze_namespace = _display_text(state.get("coinalyze_artifact_namespace") or components.get("coinalyze_artifact_namespace"))
    coinalyze_path = _display_text(state.get("coinalyze_source_artifact_path") or components.get("coinalyze_source_artifact_path"))
    coinalyze_health = _display_text(state.get("coinalyze_provider_health_status") or components.get("coinalyze_provider_health_status"))
    if coinalyze_namespace or coinalyze_path:
        lines.append(
            "- Coinalyze source: "
            f"namespace={coinalyze_namespace or 'unknown'} "
            f"path={coinalyze_path or 'unknown'} "
            f"provider_health={coinalyze_health or 'not_observed'}"
        )
    if evidence:
        lines.append("- Crowding / exhaustion evidence: " + "; ".join(evidence[:8]))
    if confirms:
        lines.append("- What confirms fade review: " + "; ".join(confirms[:5]))
    if invalidates:
        lines.append("- What invalidates fade review: " + "; ".join(invalidates[:5]))
    warnings = _list_strings(components.get("warnings"))
    if warnings:
        lines.append("- Warnings: " + "; ".join(warnings[:6]))
    return lines

def _derivatives_metric_pct(state: Mapping[str, Any], metric: str, key: str) -> str:
    if _float(state.get(key)) is not None:
        return _display_pct(state.get(key))
    status = state.get("supported_metric_status")
    if isinstance(status, Mapping) and status.get(metric):
        return str(status.get(metric))
    return "missing_from_response"

def _derivatives_metric_status_summary(state: Mapping[str, Any]) -> str:
    status = state.get("supported_metric_status")
    if not isinstance(status, Mapping):
        return "none"
    metrics = ("open_interest", "funding_rate", "predicted_funding", "liquidations", "long_short_ratio", "basis", "perp_volume")
    parts = [f"{metric}={status.get(metric)}" for metric in metrics if status.get(metric)]
    return ", ".join(parts) if parts else "none"

def _derivatives_unit_summary(state: Mapping[str, Any]) -> str:
    units = state.get("unit_metadata") if isinstance(state.get("unit_metadata"), Mapping) else state
    keys = ("open_interest_unit", "funding_rate_unit", "basis_unit", "liquidation_unit", "volume_unit")
    parts = [f"{key}={units.get(key)}" for key in keys if units.get(key)]  # type: ignore[union-attr]
    return ", ".join(parts) if parts else "none"

def _display_pct(value: Any) -> str:
    parsed = _float(value)
    if parsed is None:
        return "n/a"
    if abs(parsed) <= 3.0:
        parsed *= 100.0
    return f"{parsed:+.2f}%"

def _list_strings(value: Any) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [str(key) for key in value.keys()]
    if isinstance(value, Iterable):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]

def _display_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if text.casefold() in {
        "",
        "unknown",
        "missing",
        "none",
        "not available",
        "n/a",
        "insufficient_data",
        "impact_hypothesis",
        "watchlist",
        "alert_snapshot",
        "core_opportunity",
    }:
        return None
    return text

def _source_acquisition_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    *,
    card_path: str | Path | None = None,
    lineage_context: Mapping[str, Any] | None = None,
) -> list[str]:
    components = _card_components(entry, alert)
    if not components and entry is None:
        return ["- Source pack: unknown", "- Evidence acquisition: no local metadata."]
    pack_name = str(components.get("source_pack") or "")
    if not pack_name:
        impact_for_pack = str(components.get("impact_path_type") or "")
        if impact_for_pack.casefold() in {"proxy_attention", "proxy_exposure"}:
            impact_for_pack = "venue_value_capture"
        pack = event_source_packs.source_pack_for_playbook(
            str(components.get("playbook_type") or components.get("latest_effective_playbook_type") or (entry.latest_playbook_type if entry else "") or ""),
            impact_path_type=impact_for_pack,
            impact_category=str(components.get("impact_category") or ""),
        )
        pack_name = pack.name
    assessment = event_source_registry.assess_source(
        components,
        symbol=str(components.get("validated_symbol") or (entry.symbol if entry else "") or ""),
        coin_id=str(components.get("validated_coin_id") or (entry.coin_id if entry else "") or ""),
        provider_coverage_status=components.get("provider_coverage_status"),
    )
    plan = components.get("evidence_acquisition_plan") if isinstance(components.get("evidence_acquisition_plan"), Mapping) else {}
    needed = plan.get("evidence_needed") if isinstance(plan, Mapping) else components.get("evidence_needed")
    queries = plan.get("evidence_query_plan") if isinstance(plan, Mapping) else components.get("evidence_query_plan")
    failures = components.get("evidence_acquisition_failures") or assessment.warnings
    acquisition = components.get("evidence_acquisition_results") if isinstance(components.get("evidence_acquisition_results"), Mapping) else {}
    accepted_evidence = components.get("evidence_acquisition_accepted_evidence") or ()
    accepted_reasons = components.get("accepted_evidence_reason_codes") or ()
    if isinstance(failures, str):
        failures = [failures]
    if isinstance(needed, str):
        needed = [needed]
    if isinstance(queries, str):
        queries = [queries]
    upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
    verdict_copy = event_opportunity_verdict.build_verdict_aware_upgrade_downgrade_text(components)
    pack = event_source_packs.get_source_pack(pack_name)
    contract = event_source_registry.source_contract_metadata(
        components,
        evidence_rows=tuple(item for item in accepted_evidence if isinstance(item, Mapping)),
        assessment=assessment,
    )
    coverage_pack = _source_coverage_pack_for_card(
        pack_name,
        card_path=card_path,
        lineage_context=lineage_context,
    )
    if coverage_pack:
        failures = _coverage_pack_gap_lines(coverage_pack) or failures
    coverage_status = (
        coverage_pack.get("provider_coverage_status")
        if coverage_pack
        else (components.get("provider_coverage_status") or assessment.provider_coverage_status)
    )
    absence_meaningful = (
        coverage_pack.get("evidence_absence_meaningful")
        if coverage_pack and coverage_pack.get("evidence_absence_meaningful") is not None
        else components.get("evidence_absence_is_meaningful", assessment.evidence_absence_is_meaningful)
    )
    lines = [
        f"- Source pack: {pack_name}",
        f"- Coverage status: {coverage_status or 'unknown'}",
        f"- Evidence absence meaningful: {str(bool(absence_meaningful)).lower()}",
        f"- Source quality prior/cap: {components.get('source_quality_prior') or assessment.source_quality_prior}/{components.get('source_confidence_cap') or assessment.confidence_cap}",
        "- Source can prove: " + _source_contract_text(contract.get("source_can_prove")),
        "- Source cannot prove: " + _source_contract_text(contract.get("source_cannot_prove")),
        "- Relevant playbooks: " + _source_contract_text(contract.get("source_useful_playbooks")),
        f"- Evidence acquisition attempted: {str(bool(components.get('evidence_acquisition_attempted'))).lower()}",
        (
            f"- Evidence acquisition result: status={acquisition.get('status') or components.get('evidence_acquisition_status') or 'not_executed'} "
            f"evidence={components.get('acquisition_evidence_status') or acquisition.get('acquisition_evidence_status') or 'not available'} "
            f"accepted={acquisition.get('accepted', components.get('evidence_acquisition_accepted_count', 0))} "
            f"rejected={acquisition.get('rejected', components.get('evidence_acquisition_rejected_count', 0))} "
            f"final={acquisition.get('final_upgrade_status') or components.get('final_upgrade_status') or components.get('acquisition_upgrade_status') or 'unchanged'}"
        ),
        (
            f"- Final verdict after refresh: {components.get('final_opportunity_level') or components.get('opportunity_level') or 'not available'} "
            f"/ {components.get('final_opportunity_score') or components.get('opportunity_score_final') or 'n/a'} "
            f"source={components.get('final_verdict_source') or 'not available'}"
        ),
        "- Accepted evidence reasons: " + ("; ".join(str(item) for item in list(accepted_reasons or ())[:5]) if accepted_reasons else "none"),
        "- Accepted evidence samples: "
        + (
            "; ".join(_accepted_evidence_sample_text(item) for item in list(accepted_evidence or ())[:2])
            if accepted_evidence
            else "none"
        ),
        "- Article/source quality: " + _source_enrichment_summary(accepted_evidence),
        "- Evidence needed: " + ("; ".join(str(item) for item in list(needed or ())[:5]) if needed else "; ".join(pack.minimum_evidence[:4])),
        f"- Planned queries: {len(queries or ()) if isinstance(queries, Iterable) and not isinstance(queries, (str, bytes, Mapping)) else 0}",
        "- Provider/source gaps: " + ("; ".join(str(item) for item in list(failures or ())[:4]) if failures else "none"),
        "- What source would upgrade this: "
        + (
            verdict_copy.upgrade_text
            if _is_promoted_components(components)
            else (event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.upgrade_requirements, limit=4) or "; ".join(pack.validation_requirements[:4]))
        ),
        "- What source would downgrade this: " + verdict_copy.downgrade_text,
    ]
    return lines

def _source_coverage_pack_for_card(
    pack_name: str,
    *,
    card_path: str | Path | None,
    lineage_context: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    json_paths: list[Path] = []
    if lineage_context:
        for key in ("source_coverage_json_path", "event_alpha_source_coverage_json_path"):
            value = lineage_context.get(key)
            if value:
                json_paths.append(Path(str(value)).expanduser())
    if card_path:
        path = Path(card_path).expanduser()
        json_paths.append(path.parent.parent / "event_alpha_source_coverage.json")
    seen: set[Path] = set()
    for path in json_paths:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for pack in data.get("packs") or ():
            if isinstance(pack, Mapping) and str(pack.get("source_pack") or "") == str(pack_name or ""):
                return pack
    return None

def _coverage_pack_gap_lines(pack: Mapping[str, Any]) -> list[str]:
    items: list[str] = []
    for label, key in (
        ("missing", "providers_missing_for_confirmation"),
        ("degraded", "providers_degraded_for_confirmation"),
        ("missing", "missing_providers"),
        ("degraded", "degraded_or_backoff_providers"),
    ):
        values = pack.get(key)
        if isinstance(values, Iterable) and not isinstance(values, (str, bytes, Mapping)):
            for value in values:
                text = str(value or "").strip()
                if text:
                    items.append(f"{label}:{text}")
    reason = str(pack.get("coverage_gap_reason") or "").strip()
    if reason and reason not in {"none", "unknown"}:
        items.append(reason)
    return list(dict.fromkeys(items))

def _analyst_summary_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[str]:
    components = _card_components(entry, alert)
    if not components:
        return []
    plan = components.get("evidence_acquisition_plan") if isinstance(components.get("evidence_acquisition_plan"), Mapping) else None
    summary = event_llm_evidence_planner.generate_analyst_summary(components, plan=plan)
    catalyst_eligibility = str(summary.why_not_alertable)
    if decision_model_values(alert, components):
        catalyst_eligibility = catalyst_eligibility.replace(
            "Not alertable on final route",
            "Ineligible on strict catalyst route",
        ).replace("Not alertable", "Ineligible for strict catalyst alert")
    lines = [
        f"- Why surfaced: {summary.why_surfaced}",
        f"- Strict catalyst alert eligibility: {catalyst_eligibility}",
        f"- What would upgrade: {summary.what_would_upgrade}",
        f"- What would invalidate: {summary.what_would_invalidate}",
        "- Check next: " + "; ".join(summary.what_to_check_next[:4]),
    ]
    if summary.warnings:
        lines.append("- Analyst warnings: " + "; ".join(summary.warnings[:4]))
    return lines

def _source_contract_text(values: object, *, limit: int = 5) -> str:
    if values in (None, "", [], {}, ()):
        return "none"
    if isinstance(values, str):
        items = [part.strip() for part in values.replace(";", ",").split(",") if part.strip()]
    elif isinstance(values, Mapping):
        items = [str(value) for value in values.values() if str(value)]
    elif isinstance(values, Iterable):
        items = [str(value) for value in values if str(value)]
    else:
        items = [str(values)]
    items = list(dict.fromkeys(items))
    if not items:
        return "none"
    shown = [_human_contract_value(item) for item in items[:limit]]
    suffix = f"; +{len(items) - limit} more" if len(items) > limit else ""
    return "; ".join(shown) + suffix

def _accepted_evidence_sample_text(item: object) -> str:
    if not isinstance(item, Mapping):
        return str(item)[:160]
    title = str(item.get("title") or item.get("source_url") or "evidence")[:120]
    details: list[str] = []
    tags = item.get("currency_tags")
    if tags:
        if isinstance(tags, str):
            tag_text = tags
        elif isinstance(tags, Iterable) and not isinstance(tags, (bytes, bytearray, Mapping)):
            tag_text = ",".join(str(tag) for tag in list(tags)[:4] if str(tag))
        else:
            tag_text = str(tags)
        if tag_text:
            details.append(f"tags={tag_text}")
    if item.get("cryptopanic_currency_tag_match"):
        details.append("tag_match=true")
    exchange = item.get("exchange")
    if exchange:
        details.append(f"exchange={exchange}")
    pairs = item.get("announcement_pairs")
    if pairs:
        pair_text = pairs if isinstance(pairs, str) else ",".join(str(pair) for pair in list(pairs)[:4] if str(pair))
        if pair_text:
            details.append(f"pairs={pair_text}")
    contracts = item.get("announcement_contracts")
    if contracts:
        contract_text = contracts if isinstance(contracts, str) else ",".join(str(contract) for contract in list(contracts)[:4] if str(contract))
        if contract_text:
            details.append(f"contracts={contract_text}")
    event_time = item.get("structured_event_time")
    if event_time:
        details.append(f"event_time={event_time}")
    category = item.get("calendar_event_category")
    if category:
        details.append(f"category={category}")
    unlock_pct = item.get("unlock_pct_circulating")
    if unlock_pct not in (None, ""):
        details.append(f"unlock_pct={unlock_pct}")
    materiality = item.get("unlock_materiality")
    if materiality:
        details.append(f"materiality={materiality}")
    enrichment = item.get("source_enrichment") if isinstance(item.get("source_enrichment"), Mapping) else {}
    quality_status = enrichment.get("article_quality_status")
    if quality_status:
        details.append(f"article={quality_status}")
    return title + (f" ({'; '.join(details)})" if details else "")

def _source_enrichment_summary(items: object) -> str:
    if not isinstance(items, Iterable) or isinstance(items, (str, bytes, Mapping)):
        return "not available"
    parts: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        enrichment = item.get("source_enrichment") if isinstance(item.get("source_enrichment"), Mapping) else {}
        status = enrichment.get("article_quality_status")
        cleaner = enrichment.get("cleaner_version")
        ratio = enrichment.get("boilerplate_ratio")
        triage = enrichment.get("source_triage_decision")
        warnings = enrichment.get("warnings") or ()
        if status:
            detail = f"{status}"
            if cleaner:
                detail += f" cleaner={cleaner}"
            if ratio not in (None, ""):
                detail += f" boilerplate={ratio}"
            if triage:
                detail += f" triage={triage}"
            if warnings:
                detail += " warnings=" + ",".join(str(warning) for warning in list(warnings)[:3])
            parts.append(detail)
    return "; ".join(parts[:3]) if parts else "not available"

def _human_contract_value(value: object) -> str:
    return str(value).replace("_", " ")

__all__ = (
    '_source_lines',
    '_official_exchange_evidence_lines',
    '_scheduled_catalyst_lines',
    '_derivatives_crowding_lines',
    '_derivatives_metric_pct',
    '_derivatives_metric_status_summary',
    '_derivatives_unit_summary',
    '_display_pct',
    '_list_strings',
    '_display_text',
    '_source_acquisition_lines',
    '_source_coverage_pack_for_card',
    '_coverage_pack_gap_lines',
    '_analyst_summary_lines',
    '_source_contract_text',
    '_accepted_evidence_sample_text',
    '_source_enrichment_summary',
    '_human_contract_value',
)
