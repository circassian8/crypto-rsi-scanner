"""Market Anomalies helpers for daily brief."""

from __future__ import annotations

from .runtime import *

def _market_anomaly_daily_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    candidates = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("symbol") or "").upper() != "SECTOR"
        and str(row.get("row_type") or "") == "event_market_anomaly"
    ]
    if not candidates:
        return ["- None."]
    candidates.sort(key=lambda row: float(row.get("priority") or 0.0), reverse=True)
    lines: list[str] = []
    seen: set[str] = set()
    displayed = 0
    for row in candidates:
        key = str(row.get("canonical_asset_id") or row.get("coin_id") or row.get("symbol") or "")
        family = str(row.get("market_state_class") or row.get("anomaly_type") or "")
        dedupe_key = f"{key}|{family}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        snapshot = row.get("market_state_snapshot") if isinstance(row.get("market_state_snapshot"), Mapping) else {}
        packs = row.get("suggested_source_packs_to_search") if isinstance(row.get("suggested_source_packs_to_search"), list) else []
        why = row.get("why_interesting") if isinstance(row.get("why_interesting"), list) else []
        confirms = row.get("what_confirms") if isinstance(row.get("what_confirms"), list) else []
        invalidates = row.get("what_invalidates") if isinstance(row.get("what_invalidates"), list) else []
        lines.append(
            f"- {row.get('symbol') or row.get('coin_id') or 'UNKNOWN'}/{row.get('coin_id') or 'unknown'}: "
            f"type={row.get('market_state_class') or row.get('anomaly_type') or 'unknown'} "
            f"bucket={row.get('anomaly_bucket') or row.get('market_anomaly_bucket') or 'unknown'} "
            f"return_4h={_format_signed_pct(snapshot.get('return_4h'))} "
            f"return_24h={_format_signed_pct(snapshot.get('return_24h'))} "
            f"volume_z={_format_float(snapshot.get('volume_zscore_24h'))} "
            f"needs_catalyst_search={str(bool(row.get('needs_catalyst_search'))).lower()} "
            f"priority={_format_float(row.get('priority'))}"
        )
        if packs:
            lines.append("  search packs: " + ", ".join(str(item) for item in packs[:4]))
        if why:
            lines.append("  why_interesting: " + "; ".join(str(item) for item in why[:4]))
        if confirms:
            lines.append("  what_confirms: " + "; ".join(str(item) for item in confirms[:3]))
        if invalidates:
            lines.append("  what_invalidates: " + "; ".join(str(item) for item in invalidates[:3]))
        displayed += 1
        if displayed >= limit:
            break
    remaining = max(0, len(candidates) - displayed)
    if remaining:
        lines.append(f"- +{remaining} more market anomaly rows in local artifacts.")
    return lines

def _official_exchange_daily_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    candidates = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("row_type") or "") == "official_listing_candidate"
    ]
    if not candidates:
        return ["- None."]
    priority = {
        "CONFIRMED_LONG_RESEARCH": 0,
        "EARLY_LONG_RESEARCH": 1,
        "FADE_SHORT_REVIEW": 2,
        "RISK_ONLY": 3,
        "UNCONFIRMED_RESEARCH": 4,
        "DIAGNOSTIC": 5,
    }
    candidates.sort(key=lambda row: (priority.get(str(row.get("opportunity_type") or ""), 9), str(row.get("published_at") or "")))
    lines: list[str] = []
    displayed = 0
    for row in candidates:
        lines.append(
            f"- {row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'}: "
            f"{row.get('event_type') or 'unknown'} on {row.get('exchange') or 'exchange'} "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'} "
            f"pack={row.get('source_pack') or 'unknown'}"
        )
        if row.get("effective_time") or row.get("published_at"):
            lines.append(
                f"  timing: published={row.get('published_at') or 'unknown'} "
                f"effective={row.get('effective_time') or 'unknown'}"
            )
        warnings = [str(item) for item in row.get("resolver_warnings") or () if str(item)]
        if warnings:
            lines.append("  resolver: " + "; ".join(warnings[:3]))
        why_not = [str(item) for item in row.get("why_not_alertable") or () if str(item)]
        if why_not:
            lines.append("  why_not_alertable: " + "; ".join(why_not[:3]))
        if row.get("source_url"):
            lines.append(f"  source: {row.get('source_url')}")
        displayed += 1
        if displayed >= limit:
            break
    remaining = max(0, len(candidates) - displayed)
    if remaining:
        lines.append(f"- +{remaining} more official exchange rows in local artifacts.")
    return lines

def _scheduled_catalyst_daily_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    candidates = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("row_type") or "") == "scheduled_catalyst_event"
        and str(row.get("event_type") or "") not in {"token_unlock", "vesting_cliff", "linear_emission"}
    ]
    if not candidates:
        return ["- None."]
    candidates.sort(key=lambda row: (str(row.get("event_start_time") or ""), str(row.get("symbol") or "")))
    lines: list[str] = []
    for row in candidates[: max(0, limit)]:
        lines.append(
            f"- {row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'}: "
            f"{row.get('event_type') or 'unknown'} "
            f"status={row.get('event_status') or 'unknown'} "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'} "
            f"source_class={row.get('source_class') or 'unknown'}"
        )
        lines.append(f"  timing: start={row.get('event_start_time') or 'unknown'}")
        why_not = [str(item) for item in row.get("why_not_alertable") or () if str(item)]
        if why_not:
            lines.append("  why_not_alertable: " + "; ".join(why_not[:4]))
        if row.get("source_url"):
            lines.append(f"  source: {row.get('source_url')}")
    remaining = max(0, len(candidates) - limit)
    if remaining:
        lines.append(f"- +{remaining} more scheduled catalysts in local artifacts.")
    return lines

def _unlock_risk_daily_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    candidates = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("row_type") or "") == "unlock_event"
    ]
    if not candidates:
        return ["- None."]
    priority = {
        "FADE_SHORT_REVIEW": 0,
        "RISK_ONLY": 1,
        "UNCONFIRMED_RESEARCH": 2,
        "DIAGNOSTIC": 3,
    }
    candidates.sort(key=lambda row: (priority.get(str(row.get("opportunity_type") or ""), 9), str(row.get("unlock_time") or "")))
    lines: list[str] = []
    for row in candidates[: max(0, limit)]:
        lines.append(
            f"- {row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'}: "
            f"unlock={row.get('unlock_type') or 'unknown'} "
            f"pct_circ={_format_pct(row.get('unlock_pct_circulating_supply'))} "
            f"vs_adv={_format_float(row.get('unlock_vs_30d_adv'))} "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'}"
        )
        lines.append(f"  timing: unlock_time={row.get('unlock_time') or 'unknown'}")
        why_not = [str(item) for item in row.get("why_not_alertable") or () if str(item)]
        if why_not:
            lines.append("  why_not_alertable: " + "; ".join(why_not[:4]))
        if row.get("source_url"):
            lines.append(f"  source: {row.get('source_url')}")
    remaining = max(0, len(candidates) - limit)
    if remaining:
        lines.append(f"- +{remaining} more unlock rows in local artifacts.")
    return lines

def _derivatives_fade_review_daily_lines(
    fade_rows: Iterable[Mapping[str, Any]],
    state_rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    candidates = [dict(row) for row in fade_rows if isinstance(row, Mapping)]
    states = [dict(row) for row in state_rows if isinstance(row, Mapping)]
    lines = [
        "Research-only. Not a trade signal. FADE_SHORT_REVIEW means manual review of crowding/exhaustion risk after a completed move.",
        f"- Derivatives state rows: {len(states)}",
    ]
    if not candidates:
        lines.append("- Fade / short-review candidates: none.")
        return lines
    priority = {"extreme": 0, "high": 1, "moderate": 2, "none": 3}
    candidates.sort(
        key=lambda row: (
            priority.get(str(row.get("crowding_class") or "none"), 9),
            str(row.get("symbol") or ""),
        )
    )
    displayed = 0
    for row in candidates[: max(0, limit)]:
        lines.append(
            f"- {row.get('symbol') or 'UNKNOWN'}/{row.get('coin_id') or 'unknown'}: "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'} "
            f"crowding={row.get('crowding_class') or 'unknown'} "
            f"fade_ready={row.get('fade_readiness') or 'unknown'}"
        )
        lines.append(f"  move: {_derivatives_move_summary(row)}")
        evidence = [str(item) for item in row.get("crowding_exhaustion_evidence") or () if str(item)]
        lines.append("  crowding/exhaustion: " + ("; ".join(evidence[:6]) if evidence else "none"))
        invalidates = [str(item) for item in row.get("what_invalidates_fade_review") or () if str(item)]
        if invalidates:
            lines.append("  invalidates: " + "; ".join(invalidates[:4]))
        warnings = [str(item) for item in row.get("warnings") or () if str(item)]
        if warnings:
            lines.append("  warnings: " + "; ".join(warnings[:4]))
        displayed += 1
    remaining = max(0, len(candidates) - displayed)
    if remaining:
        lines.append(f"- +{remaining} more derivatives fade-review rows in local artifacts.")
    return lines

def _derivatives_move_summary(row: Mapping[str, Any]) -> str:
    snapshot = row.get("market_state_snapshot")
    if not isinstance(snapshot, Mapping):
        snapshot = {}
    unit = event_market_units.infer_return_unit(snapshot, default=event_market_units.RETURN_UNIT_PERCENT_POINTS)
    return (
        f"4h={event_market_units.format_return_pct(snapshot.get('return_4h'), unit)} "
        f"24h={event_market_units.format_return_pct(snapshot.get('return_24h'), unit)} "
        f"liquidity={_format_compact_number(snapshot.get('liquidity_usd'))} "
        f"spread_bps={_format_float(snapshot.get('spread_bps'))}"
    )

def _format_compact_number(value: object) -> str:
    parsed = _optional_float(value)
    if parsed is None:
        return "n/a"
    if abs(parsed) >= 1_000_000:
        return f"{parsed / 1_000_000:.1f}m"
    if abs(parsed) >= 1_000:
        return f"{parsed / 1_000:.1f}k"
    return f"{parsed:.1f}".rstrip("0").rstrip(".")

def _calendar_gap_daily_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    gaps: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        why_not = {str(item) for item in row.get("why_not_alertable") or ()}
        if (
            "source_url_missing" in why_not
            or "unlock_time_missing" in why_not
            or "structured_unlock_proof_missing" in why_not
            or not row.get("source_url")
        ):
            gaps.append(dict(row))
    if not gaps:
        return ["- None."]
    lines: list[str] = []
    for row in gaps[: max(0, limit)]:
        why_not = [str(item) for item in row.get("why_not_alertable") or () if str(item)]
        lines.append(
            f"- {row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'}: "
            f"{row.get('event_type') or 'unknown'} missing={'; '.join(why_not[:3]) or 'source confirmation'}"
        )
    remaining = max(0, len(gaps) - limit)
    if remaining:
        lines.append(f"- +{remaining} more calendar gaps in local artifacts.")
    return lines

def _scheduled_market_watch_lines(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> list[str]:
    watch_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        lane = str(row.get("opportunity_type") or "")
        state = str(row.get("market_state") or "")
        if lane in {"EARLY_LONG_RESEARCH", "UNCONFIRMED_RESEARCH"} and state in {"no_reaction", "stealth_accumulation"}:
            watch_rows.append(dict(row))
    if not watch_rows:
        return ["- None."]
    watch_rows.sort(key=lambda row: (str(row.get("event_start_time") or row.get("unlock_time") or ""), str(row.get("symbol") or "")))
    lines: list[str] = []
    for row in watch_rows[: max(0, limit)]:
        lines.append(
            f"- {row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'}: "
            f"{row.get('event_type') or 'unknown'} "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'} "
            f"next={row.get('event_start_time') or row.get('unlock_time') or 'unknown'}"
        )
    remaining = max(0, len(watch_rows) - limit)
    if remaining:
        lines.append(f"- +{remaining} more near-term events needing market watch.")
    return lines

def _format_signed_pct(value: object) -> str:
    parsed = _optional_float(value)
    return "n/a" if parsed is None else f"{parsed:+.1f}%"

def _format_float(value: object) -> str:
    parsed = _optional_float(value)
    return "n/a" if parsed is None else f"{parsed:.1f}"

def _format_pct(value: object) -> str:
    parsed = _optional_float(value)
    if parsed is None:
        return "n/a"
    if abs(parsed) <= 3.0:
        parsed *= 100.0
    return f"{parsed:.1f}%"

def _optional_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

def _live_confirmation_gated_core_lines(
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
    *,
    limit: int,
) -> list[str]:
    rows = [
        item
        for item in opportunities
        if bool(item.primary_row.get("live_confirmation_capped"))
        or (
            bool(item.primary_row.get("live_confirmation_required"))
            and not bool(item.primary_row.get("live_confirmation_passed"))
        )
    ]
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        row = item.primary_row
        missing = row.get("live_confirmation_missing_requirements")
        if not isinstance(missing, list):
            missing = []
        upgrades = row.get("upgrade_requirements")
        if not isinstance(upgrades, list):
            upgrades = []
        lines.append(
            f"- {item.core_opportunity_id} {item.symbol}/{item.coin_id}: "
            f"requested={row.get('requested_opportunity_level_before_live_confirmation') or item.opportunity_level} "
            f"capped={row.get('final_opportunity_level') or item.opportunity_level} "
            f"status={row.get('evidence_acquisition_status') or 'unknown'} "
            f"confirmation={row.get('acquisition_confirmation_status') or 'unknown'} "
            f"reason={row.get('live_confirmation_reason') or row.get('quality_gate_block_reason') or 'live_confirmation_missing'}"
        )
        lines.append(
            "  upgrade: "
            + "; ".join(str(value) for value in (missing or upgrades)[:3])
        )
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more live-confirmation gated candidates")
    return lines

__all__ = (
    '_market_anomaly_daily_lines',
    '_official_exchange_daily_lines',
    '_scheduled_catalyst_daily_lines',
    '_unlock_risk_daily_lines',
    '_derivatives_fade_review_daily_lines',
    '_derivatives_move_summary',
    '_format_compact_number',
    '_calendar_gap_daily_lines',
    '_scheduled_market_watch_lines',
    '_format_signed_pct',
    '_format_float',
    '_format_pct',
    '_optional_float',
    '_live_confirmation_gated_core_lines',
)
