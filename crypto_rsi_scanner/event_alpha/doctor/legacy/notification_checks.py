"""Notification Checks for the legacy artifact doctor."""

from __future__ import annotations

from .runtime import *

def _alert_has_feedback_target(row: Mapping[str, Any]) -> bool:
    return any(str(row.get(key) or "").strip() for key in (
        "feedback_target",
        "core_opportunity_id",
        "alert_id",
        "card_id",
        "alert_key",
        "snapshot_id",
    ))

def _alert_snapshot_should_have_core_id(row: Mapping[str, Any]) -> bool:
    if str(row.get("row_type") or "") not in {"", "event_alpha_alert_snapshot"}:
        return False
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or "")
    level = str(row.get("opportunity_level") or "").casefold()
    state = str(row.get("final_state_after_quality_gate") or row.get("state") or "")
    if event_alpha_router.route_value_is_alertable(route):
        return True
    if route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value:
        return True
    if level in {"validated_digest", "watchlist", "high_priority"}:
        return True
    return state in {
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
    }

def _alert_snapshot_is_diagnostic(row: Mapping[str, Any]) -> bool:
    return event_alpha_notification_inbox.alert_snapshot_is_diagnostic(row)

def _audit_primary_snapshot_not_canonical_when_canonical_exists(
    alerts: Iterable[Mapping[str, Any]],
    store_core_ids: set[str],
) -> int:
    by_core: dict[str, list[dict[str, Any]]] = {}
    for row in alerts:
        core_id = str(row.get("core_opportunity_id") or row.get("diagnostic_support_for_core_opportunity_id") or "").strip()
        if not core_id or core_id not in store_core_ids:
            continue
        by_core.setdefault(core_id, []).append(dict(row))
    conflicts = 0
    for rows in by_core.values():
        has_canonical = any(_snapshot_is_canonical(row) for row in rows)
        if not has_canonical:
            continue
        primary = _best_snapshot_for_doctor(rows)
        if not _snapshot_is_canonical(primary):
            conflicts += 1
    return conflicts

def _best_snapshot_for_doctor(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = [dict(row) for row in rows]
    if not items:
        return {}

    def rank(row: Mapping[str, Any]) -> tuple[int, int, str]:
        diagnostic = _alert_snapshot_is_diagnostic(row)
        return (
            3 if _snapshot_is_canonical(row) else 0,
            1 if event_alpha_router.route_value_is_alertable(str(row.get("final_route_after_quality_gate") or row.get("route") or "")) and not diagnostic else 0,
            str(row.get("observed_at") or row.get("snapshot_id") or ""),
        )

    return max(items, key=rank)

def _snapshot_is_canonical(row: Mapping[str, Any]) -> bool:
    if _alert_snapshot_is_diagnostic(row):
        return False
    status = str(row.get("snapshot_core_resolution_status") or row.get("core_resolution_status") or "")
    return (
        str(row.get("snapshot_class") or "") == event_alpha_alert_store.SNAPSHOT_CLASS_CANONICAL_CORE
        or status in {"canonical", event_alpha_alert_store.SNAPSHOT_CORE_RECONCILED}
        or bool(row.get("snapshot_core_reconciled"))
    )

def _expected_card_group_for_store_core(
    opportunity: event_core_opportunities.CoreOpportunity | None,
) -> str | None:
    if opportunity is None:
        return None
    primary = opportunity.primary_row
    lane_group = (
        event_research_cards.card_group_for_opportunity_lane(
            primary.get("opportunity_type")
            or primary.get("opportunity_lane")
        )
    )
    if lane_group is not None:
        return lane_group
    if opportunity.is_high_priority or opportunity.is_watchlist or opportunity.is_validated_digest or opportunity.alertable:
        return "Core Opportunity Cards"
    if (
        str(opportunity.final_state_after_quality_gate or "").strip()
        == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        or str(opportunity.primary_row.get("state_quality_capped") or "").strip().casefold()
        in {"1", "true", "yes", "y"}
        or opportunity.quality_capped_supporting_rows > 0
    ):
        return "Local-Only / Quality-Capped Cards"
    if str(opportunity.opportunity_level or "").casefold() == "local_only":
        return "Local-Only / Quality-Capped Cards"
    if str(opportunity.opportunity_level or "").casefold() == "exploratory" or opportunity.opportunity_score_final >= 50:
        return "Near-Miss Cards"
    if event_core_opportunities.core_opportunity_visibility_group(opportunity) is None:
        return "Diagnostic / Source-Noise / Control Cards"
    return "Local-Only / Quality-Capped Cards"

def _core_has_fresh_rows(opportunity: event_core_opportunities.CoreOpportunity) -> bool:
    return any(
        not event_alpha_artifacts.is_legacy_row(row)
        for row in (opportunity.primary_row, *opportunity.supporting_rows)
    )

def _card_primary_mismatches(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    mismatches = 0
    for path in card_paths:
        core_id = event_research_cards.card_core_opportunity_id(path)
        if not core_id:
            continue
        core = core_rows_by_id.get(core_id)
        if not core:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        route = str(core.get("final_route_after_quality_gate") or "").strip()
        state = str(core.get("final_state_after_quality_gate") or "").strip()
        level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or "").strip()
        route_line = _card_line_value(text, "Final route")
        verdict_line = _card_line_value(text, "Opportunity verdict")
        summary_line = _card_line_value(text, "State / alert tier")
        mismatch = False
        if route_line and route and route_line != route:
            mismatch = True
        if verdict_line and level and not verdict_line.startswith(level):
            mismatch = True
        if summary_line and state and not summary_line.startswith(f"{state} /"):
            mismatch = True
        if summary_line and route and not summary_line.endswith(f"/ {route}"):
            mismatch = True
        mismatches += int(mismatch)
    return mismatches

def _card_acquisition_count_mismatches(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
    acquisition_rows: Iterable[Mapping[str, Any]],
) -> int:
    mismatches = 0
    acquisition_list = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    for path in card_paths:
        core_id = event_research_cards.card_core_opportunity_id(path)
        if not core_id:
            continue
        core = core_rows_by_id.get(core_id)
        if not core:
            continue
        view = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
            core_id,
            core_rows=[core],
            evidence_acquisition_rows=acquisition_list,
        )
        if view.accepted_evidence_count <= 0:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rendered = _card_evidence_count(text, "accepted")
        if rendered is not None and rendered != view.accepted_evidence_count:
            mismatches += 1
    return mismatches

def _card_source_pack_mismatches(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
    acquisition_rows: Iterable[Mapping[str, Any]],
) -> int:
    mismatches = 0
    acquisition_list = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    for path in card_paths:
        core_id = event_research_cards.card_core_opportunity_id(path)
        if not core_id:
            continue
        core = core_rows_by_id.get(core_id)
        if not core:
            continue
        view = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
            core_id,
            core_rows=[core],
            evidence_acquisition_rows=acquisition_list,
        )
        if not view.source_pack:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rendered = _card_line_value(text, "Source pack")
        if rendered and rendered != view.source_pack:
            mismatches += 1
    return mismatches

def _card_primary_section_contains_support_row_blockers(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    blockers = (
        "blocked by generic cooccurrence",
        "needs proof that this event directly affects the token",
        "no token value-capture mechanism is visible",
    )
    count = 0
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core or not _core_row_is_promoted(core):
            continue
        text = _read_card_text(path).casefold()
        count += int(any(blocker in text for blocker in blockers))
    return count

def _card_upgrade_text_inconsistent_with_final_level(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    count = 0
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core or not _core_row_is_promoted(core):
            continue
        text = _read_card_text(path).casefold()
        if str(core.get("opportunity_level") or core.get("final_opportunity_level") or "").casefold() == "high_priority":
            count += int("already high priority" not in text)
    return count

def _card_market_confirmation_missing_but_core_has_market_confirmation(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    count = 0
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core:
            continue
        has_market = core.get("market_confirmation_level") not in (None, "", "none") or core.get("market_confirmation_score") not in (None, "")
        if not has_market:
            continue
        text = _read_card_text(path).casefold()
        count += int("no market snapshot stored" in text or "market data: not available" in text)
    return count

def _card_latest_source_unknown_but_accepted_evidence_exists(
    card_paths: Iterable[Path],
    core_rows_by_id: Mapping[str, Mapping[str, Any]],
    acquisition_rows: Iterable[Mapping[str, Any]],
) -> int:
    count = 0
    acquisition_list = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    for path in card_paths:
        core = _card_core_row(path, core_rows_by_id)
        if not core:
            continue
        core_id = event_research_cards.card_core_opportunity_id(path) or ""
        view = event_core_opportunity_store.core_evidence_acquisition_view_from_rows(
            core_id,
            core_rows=[core],
            evidence_acquisition_rows=acquisition_list,
        )
        accepted = max(int(core.get("evidence_acquisition_accepted_count") or 0), view.accepted_evidence_count)
        if accepted <= 0:
            continue
        text = _read_card_text(path).casefold()
        count += int("- latest source: unknown" in text or "- latest source: not available" in text)
    return count

def _card_core_row(path: Path, core_rows_by_id: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    core_id = event_research_cards.card_core_opportunity_id(path)
    return core_rows_by_id.get(core_id or "")

def _read_card_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

def _core_row_is_promoted(row: Mapping[str, Any]) -> bool:
    level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").casefold()
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").upper()
    return level in {"validated_digest", "watchlist", "high_priority"} or event_alpha_router.route_value_is_alertable(route)

def _card_evidence_count(text: str, label: str) -> int | None:
    match = re.search(rf"\b{re.escape(label)}=(\d+)\b", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None

def _promoted_core_rows_that_are_weak(core_rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    for row in core_rows:
        level = str(row.get("opportunity_level") or row.get("final_opportunity_level") or "")
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "")
        impact = str(row.get("impact_path_type") or row.get("primary_impact_path") or "")
        if level in {"validated_digest", "watchlist", "high_priority"} or event_alpha_router.route_value_is_alertable(route):
            if impact in {"generic_cooccurrence_only", "insufficient_data"}:
                count += 1
    return count

def _card_line_value(text: str, label: str) -> str | None:
    match = re.search(rf"^-\s*{re.escape(label)}:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None

def _core_row_has_market_freshness_contradiction(row: Mapping[str, Any]) -> bool:
    status = str(row.get("market_context_freshness_status") or "").casefold()
    source = str(row.get("market_context_source") or "").casefold()
    age = row.get("market_context_age_hours")
    cap = row.get("market_context_freshness_cap_applied")
    if status not in {"fresh", "fixture_allowed_stale"}:
        return False
    if source not in {"", "missing", "unknown"}:
        return False
    return age in (None, "", "unknown") and bool(cap)

def _quality_missing_summary(
    *,
    hypotheses: Iterable[Mapping[str, Any]],
    watchlist: Iterable[Mapping[str, Any]],
    alerts: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    hypothesis_rows = [dict(row) for row in hypotheses if dict(row).get("row_type") in {"event_impact_hypothesis", ""}]
    watchlist_rows = [dict(row) for row in watchlist if dict(row).get("row_type") in {"event_watchlist_state", ""}]
    alert_rows = [dict(row) for row in alerts if dict(row).get("row_type") in {"event_alpha_alert_snapshot", ""}]
    hypothesis_missing_verdict = sum(
        1
        for row in hypothesis_rows
        if event_alpha_quality_fields.is_missing_quality_value(row.get("opportunity_level"))
        or event_alpha_quality_fields.is_missing_quality_value(row.get("opportunity_score_final"))
    )
    watchlist_missing = sum(1 for row in watchlist_rows if event_alpha_quality_fields.missing_top_level_quality_fields(row))
    alert_missing = sum(1 for row in alert_rows if event_alpha_quality_fields.missing_top_level_quality_fields(row))
    all_rows = [*hypothesis_rows, *watchlist_rows, *alert_rows]
    missing_rows = [
        row
        for row in all_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
    ]
    legacy_missing = sum(1 for row in missing_rows if event_alpha_artifacts.is_legacy_row(row))
    fresh_hypothesis_missing = sum(
        1
        for row in hypothesis_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
        and not event_alpha_artifacts.is_legacy_row(row)
    )
    fresh_watchlist_missing = sum(
        1
        for row in watchlist_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
        and not event_alpha_artifacts.is_legacy_row(row)
    )
    fresh_alert_missing = sum(
        1
        for row in alert_rows
        if event_alpha_quality_fields.missing_top_level_quality_fields(row)
        and not event_alpha_artifacts.is_legacy_row(row)
    )
    return {
        "quality_fields_missing_count": len(missing_rows),
        "hypothesis_rows_missing_opportunity_verdict": hypothesis_missing_verdict,
        "watchlist_rows_missing_quality_fields": watchlist_missing,
        "alert_rows_missing_quality_fields": alert_missing,
        "fresh_hypothesis_rows_missing_top_level_quality": fresh_hypothesis_missing,
        "fresh_watchlist_rows_missing_top_level_quality": fresh_watchlist_missing,
        "fresh_alert_rows_missing_top_level_quality": fresh_alert_missing,
        "legacy_quality_missing_rows": legacy_missing,
        "non_legacy_quality_missing": max(0, len(missing_rows) - legacy_missing),
    }

def _latest_run_rows(rows: Iterable[Mapping[str, Any]], run_rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    run_ids = [str(row.get("run_id") or "") for row in run_rows if str(row.get("run_id") or "")]
    if not run_ids:
        return [row for row in rows]
    latest = sorted(run_ids)[-1]
    latest_rows = [row for row in rows if str(row.get("run_id") or "") == latest]
    return latest_rows

def _alertable_quality_route_conflicts(alerts: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for row in alerts if _row_has_alertable_quality_conflict(row))

def _alert_snapshot_core_conflicts(
    alerts: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    out = {
        "route_mismatch": 0,
        "level_mismatch": 0,
        "live_confirmation_stale": 0,
        "core_resolution_missing": 0,
        "pre_reconciliation_alertable": 0,
        "diagnostic_support_alertable": 0,
        "diagnostic_support_inherits_core_route": 0,
        "duplicate_alertable_snapshot_for_core": 0,
        "canonical_snapshot_missing_for_visible_core": 0,
    }
    core_rows_tuple = tuple(core_rows)
    core_by_id = {
        str(row.get("core_opportunity_id") or "").strip(): row
        for row in core_rows_tuple
        if str(row.get("core_opportunity_id") or "").strip()
    }
    alertable_canonical_by_core_route: dict[tuple[str, str], int] = {}
    canonical_alertable_core_ids: set[str] = set()
    for row in alerts:
        if event_alpha_artifacts.is_legacy_row(row):
            continue
        if _is_diagnostic_support_snapshot(row):
            route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
            alertable = bool(row.get("alertable_after_quality_gate", row.get("route_alertable")))
            if alertable or event_alpha_router.route_value_is_alertable(route):
                out["diagnostic_support_alertable"] += 1
            if event_alpha_router.route_value_is_alertable(route):
                out["diagnostic_support_inherits_core_route"] += 1
            continue
        core_id = str(row.get("core_opportunity_id") or "").strip()
        if not core_id:
            continue
        core = core_by_id.get(core_id)
        if core is None:
            out["core_resolution_missing"] += 1
            continue
        snapshot_reconciled = bool(row.get("snapshot_core_reconciled"))
        snapshot_route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        core_route = str(core.get("final_route_after_quality_gate") or core.get("route") or "").strip()
        snapshot_level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").strip()
        core_level = str(core.get("final_opportunity_level") or core.get("opportunity_level") or "").strip()
        if snapshot_route != core_route and not snapshot_reconciled:
            out["route_mismatch"] += 1
        if snapshot_level != core_level and not snapshot_reconciled:
            out["level_mismatch"] += 1
        snapshot_promoted = (
            snapshot_level in {"validated_digest", "watchlist", "high_priority"}
            or event_alpha_router.route_value_is_alertable(snapshot_route)
        )
        core_promoted = (
            core_level in {"validated_digest", "watchlist", "high_priority"}
            or event_alpha_router.route_value_is_alertable(core_route)
        )
        if (
            bool(core.get("live_confirmation_capped")) or str(core.get("live_confirmation_status") or "") in {"missing", "unresolved"}
        ) and snapshot_promoted and not core_promoted and not snapshot_reconciled:
            out["live_confirmation_stale"] += 1
        requested_route = str(row.get("requested_route_before_core_reconciliation") or "").strip()
        if (
            snapshot_reconciled
            and event_alpha_router.route_value_is_alertable(requested_route)
            and not event_alpha_router.route_value_is_alertable(snapshot_route)
        ):
            out["pre_reconciliation_alertable"] += 1
        if event_alpha_router.route_value_is_alertable(snapshot_route):
            canonical_alertable_core_ids.add(core_id)
            key = (core_id, snapshot_route)
            alertable_canonical_by_core_route[key] = alertable_canonical_by_core_route.get(key, 0) + 1
    out["duplicate_alertable_snapshot_for_core"] = sum(
        max(0, count - 1)
        for count in alertable_canonical_by_core_route.values()
        if count > 1
    )
    alertable_visible_core_ids = {
        str(row.get("core_opportunity_id") or "").strip()
        for row in core_rows_tuple
        if str(row.get("core_opportunity_id") or "").strip()
        and event_alpha_router.route_value_is_alertable(
            row.get("final_route_after_quality_gate") or row.get("route")
        )
        and not event_core_opportunities.row_is_diagnostic(row)
    }
    out["canonical_snapshot_missing_for_visible_core"] = len(alertable_visible_core_ids - canonical_alertable_core_ids)
    return out

def _is_diagnostic_support_snapshot(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("snapshot_class") or "") == event_alpha_alert_store.SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
        or str(row.get("core_resolution_status") or "") == "diagnostic_support"
        or str(row.get("snapshot_core_resolution_status") or "") == "diagnostic_support"
        or bool(row.get("is_diagnostic_snapshot"))
    )

def _quality_route_conflicts(alerts: Iterable[Mapping[str, Any]], *, legacy: bool) -> int:
    count = 0
    for row in alerts:
        is_legacy = event_alpha_artifacts.is_legacy_row(row)
        if legacy != is_legacy:
            continue
        classification = event_alpha_alert_store.classify_alert_snapshot(row)
        if classification == event_alpha_alert_store.SNAPSHOT_LEGACY_CONFLICT or _row_has_alertable_quality_conflict(row):
            count += 1
    return count

def _missing_final_route_rows(alerts: Iterable[Mapping[str, Any]], *, legacy: bool | None = None) -> int:
    count = 0
    for row in alerts:
        if legacy is not None and event_alpha_artifacts.is_legacy_row(row) != legacy:
            continue
        classification = event_alpha_alert_store.classify_alert_snapshot(row)
        if classification in {
            event_alpha_alert_store.SNAPSHOT_MISSING_FINAL_ROUTE,
            event_alpha_alert_store.SNAPSHOT_STALE_PRE_QUALITY_GATE,
        }:
            count += 1
    return count

def _core_route_conflicts_with_opportunity_level(rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    for row in rows:
        level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").strip()
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        if level not in {"validated_digest", "watchlist", "high_priority"}:
            continue
        if route in {
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
        }:
            continue
        if bool(row.get("state_quality_capped")):
            continue
        components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
        _, block = event_alpha_router.quality_gate_route_for_row(row, components=components, require_quality=True)
        if block:
            continue
        count += 1
    return count

def _live_confirmation_conflicts(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
) -> dict[str, int]:
    out = {
        "live_validated_without_confirmation": 0,
        "live_sector_digest_without_asset": 0,
        "live_rejected_results_promoted": 0,
        "live_skipped_budget_promoted": 0,
    }
    for row in rows:
        level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").strip()
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        if level not in {"validated_digest", "watchlist", "high_priority"}:
            continue
        if route not in {
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
        }:
            continue
        if not event_opportunity_verdict.live_confirmation_required(
            profile=str(row.get("profile") or profile or ""),
            run_mode=str(row.get("run_mode") or ""),
            artifact_namespace=str(row.get("artifact_namespace") or artifact_namespace or ""),
        ):
            continue
        if bool(row.get("live_confirmation_passed")):
            continue
        if str(row.get("live_confirmation_status") or "") == "confirmed":
            continue
        out["live_validated_without_confirmation"] += 1
        symbol = str(row.get("symbol") or "").strip().upper()
        coin_id = str(row.get("coin_id") or "").strip().casefold()
        if symbol == "SECTOR" or coin_id in {"sports_fan_proxy", "political_meme_proxy", "ai_ipo_proxy", "rwa_preipo_proxy", "sector"}:
            out["live_sector_digest_without_asset"] += 1
        status = str(row.get("evidence_acquisition_status") or "").strip()
        if status == "rejected_results_only":
            out["live_rejected_results_promoted"] += 1
        if status == "skipped_budget":
            out["live_skipped_budget_promoted"] += 1
    return out

def _raw_core_live_confirmation_conflicts(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None,
    artifact_namespace: str | None,
) -> dict[str, int]:
    out = {
        "raw_core_validated_without_confirmation": 0,
        "raw_core_source_only_narrative_validated": 0,
        "raw_core_cryptopanic_tag_only_direct_path_confirmed": 0,
        "raw_core_suppressed_duplicate_validated_stale": 0,
    }
    for row in rows:
        level = str(row.get("final_opportunity_level") or row.get("opportunity_level") or "").strip()
        if level not in {"validated_digest", "watchlist", "high_priority"}:
            continue
        if not event_opportunity_verdict.live_confirmation_required(
            profile=str(row.get("profile") or profile or ""),
            run_mode=str(row.get("run_mode") or ""),
            artifact_namespace=str(row.get("artifact_namespace") or artifact_namespace or ""),
        ):
            continue
        verdict = event_opportunity_verdict.apply_live_confirmation_policy(
            row,
            profile=str(row.get("profile") or profile or ""),
            run_mode=str(row.get("run_mode") or ""),
            artifact_namespace=str(row.get("artifact_namespace") or artifact_namespace or ""),
        )
        raw_stale = bool(not verdict.confirmed or verdict.capped_level)
        if raw_stale:
            out["raw_core_validated_without_confirmation"] += 1
        if raw_stale and _raw_core_source_only_narrative(row):
            out["raw_core_source_only_narrative_validated"] += 1
        if _raw_core_cryptopanic_tag_only_direct_path(row) and str(row.get("live_confirmation_status") or "") == "confirmed":
            out["raw_core_cryptopanic_tag_only_direct_path_confirmed"] += 1
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        if raw_stale and route == event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value:
            out["raw_core_suppressed_duplicate_validated_stale"] += 1
    return out

__all__ = (
    '_alert_has_feedback_target',
    '_alert_snapshot_should_have_core_id',
    '_alert_snapshot_is_diagnostic',
    '_audit_primary_snapshot_not_canonical_when_canonical_exists',
    '_best_snapshot_for_doctor',
    '_snapshot_is_canonical',
    '_expected_card_group_for_store_core',
    '_core_has_fresh_rows',
    '_card_primary_mismatches',
    '_card_acquisition_count_mismatches',
    '_card_source_pack_mismatches',
    '_card_primary_section_contains_support_row_blockers',
    '_card_upgrade_text_inconsistent_with_final_level',
    '_card_market_confirmation_missing_but_core_has_market_confirmation',
    '_card_latest_source_unknown_but_accepted_evidence_exists',
    '_card_core_row',
    '_read_card_text',
    '_core_row_is_promoted',
    '_card_evidence_count',
    '_promoted_core_rows_that_are_weak',
    '_card_line_value',
    '_core_row_has_market_freshness_contradiction',
    '_quality_missing_summary',
    '_latest_run_rows',
    '_alertable_quality_route_conflicts',
    '_alert_snapshot_core_conflicts',
    '_is_diagnostic_support_snapshot',
    '_quality_route_conflicts',
    '_missing_final_route_rows',
    '_core_route_conflicts_with_opportunity_level',
    '_live_confirmation_conflicts',
    '_raw_core_live_confirmation_conflicts',
)
