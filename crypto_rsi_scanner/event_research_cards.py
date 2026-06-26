"""Markdown research cards for routed Event Alpha candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from . import event_alpha_router, event_graph, event_opportunity_verdict, event_watchlist, event_watchlist_monitor


@dataclass(frozen=True)
class EventResearchCardResult:
    key: str
    markdown: str
    found: bool


@dataclass(frozen=True)
class EventResearchCardWriteResult:
    out_dir: Path
    cards_written: int
    index_path: Path
    card_paths: tuple[Path, ...]


def render_research_card(
    key: str,
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision] = (),
    clusters: Iterable[event_graph.EventCluster] = (),
    monitor_rows: Iterable[event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: datetime | None = None,
) -> EventResearchCardResult:
    """Render one Markdown card from local research artifacts."""
    clean_key = str(key or "").strip()
    entry = _find_entry(clean_key, list(watchlist_entries))
    alert = _find_alert(clean_key, list(alert_rows))
    decision = _find_decision(clean_key, list(route_decisions))
    cluster = _find_cluster(clean_key, list(clusters), entry, alert)
    monitor_row = _find_monitor_row(clean_key, list(monitor_rows), entry, alert)
    feedback = _matching_rows(clean_key, list(feedback_rows), entry, alert)
    outcome = _find_outcome(clean_key, list(outcome_rows), entry, alert) or alert
    if entry is None and alert is None:
        return EventResearchCardResult(
            key=clean_key,
            markdown=f"# Event Research Card\n\nNo watchlist or alert snapshot matched `{clean_key}`.",
            found=False,
        )
    playbook = _value(entry, alert, "latest_playbook_type", "playbook_type") or "unknown"
    symbol = _value(entry, alert, "symbol", "asset_symbol") or "UNKNOWN"
    coin_id = _value(entry, alert, "coin_id", "asset_coin_id") or "unknown"
    event_name = _value(entry, alert, "latest_event_name", "event_name") or "unknown event"
    tier = _value(entry, alert, "latest_tier", "tier") or "unknown"
    state = event_watchlist.final_state_value(entry) if entry is not None else str(alert.get("final_state_after_quality_gate") or alert.get("state") or "snapshot")
    generated_iso = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    lines = [
        f"# {symbol} Event Research Card",
        "",
        "Research artifact only. Not a trade signal, paper trade, live RSI signal, or execution.",
        "",
        "## Summary",
        f"- Asset: {symbol}/{coin_id}",
        f"- Event: {event_name}",
        f"- State / alert tier: {state} / {tier}",
        f"- Playbook: {playbook}",
    ]
    if decision is not None:
        lines.append(f"- Route: {event_alpha_router.final_route_value(decision)} ({decision.reason})")
        if decision.quality_gate_block_reason or decision.requested_route_before_quality_gate:
            lines.append(
                "- Quality gate: "
                f"{decision.requested_route_before_quality_gate or decision.route.value} -> "
                f"{event_alpha_router.final_route_value(decision)}"
                + (
                    f" ({decision.quality_gate_block_reason})"
                    if decision.quality_gate_block_reason
                    else " (allowed)"
                )
            )
    lines.extend([
        "",
        "## Artifact Lineage",
        f"- Generated at: {generated_iso}",
        f"- Run ID: {_value(None, alert, '', 'run_id') or 'unknown'}",
        f"- Profile: {_value(None, alert, '', 'profile') or 'unknown'}",
        f"- Namespace: {_value(None, alert, '', 'artifact_namespace') or 'unknown'}",
        f"- Snapshot ID: {_value(None, alert, '', 'snapshot_id') or 'unknown'}",
        f"- Watchlist key: {entry.key if entry is not None else (_value(None, alert, '', 'alert_key') or clean_key)}",
        f"- Cluster ID: {_value(entry, alert, 'cluster_id', 'cluster_id') or 'unknown'}",
    ])
    lines.extend([
        "",
        "## Cluster Context",
    ])
    lines.extend(_cluster_lines(cluster))
    lines.extend([
        "",
        "## Playbook",
        _playbook_copy(playbook, alert),
        "",
        "## External Catalyst",
        f"- External asset: {_value(entry, alert, 'external_asset', 'external_asset') or 'unknown'}",
        f"- Event time: {_value(entry, alert, 'event_time', 'event_time') or 'unknown'}",
        "",
        "## Evidence Sources",
    ])
    lines.extend(_source_lines(entry, alert))
    lines.extend([
        "",
        "## Accepted / Rejected Asset Links",
        f"- Relationship: {_value(entry, alert, 'relationship_type', 'relationship_type') or 'unknown'}",
        f"- Rule playbook: {_value(entry, alert, 'latest_rule_playbook_type', 'rule_playbook_type') or 'unknown'}",
        f"- Effective playbook: {_value(entry, alert, 'latest_effective_playbook_type', 'playbook_type') or playbook}",
    ])
    lines.extend(["", "## Quality Gate Result"])
    lines.extend(_quality_gate_lines(entry, alert, decision))
    if entry is not None and event_watchlist.state_is_quality_capped(entry):
        _, state_block_reason = event_watchlist.quality_cap_watchlist_state(
            event_watchlist.requested_state_value(entry),
            entry.latest_score_components,
        )
        lines.extend([
            "",
            "## Lifecycle State Gate",
            "- Local-only after quality/state gate.",
            (
                f"- Requested {event_watchlist.requested_state_value(entry)} blocked because "
                f"{entry.quality_state_block_reason or state_block_reason or 'quality verdict did not allow active watchlist state'}."
            ),
            "- What would upgrade this candidate: " + (
                "; ".join(entry.upgrade_requirements[:3])
                if entry.upgrade_requirements
                else "recompute quality with validated impact path, specific evidence, and market confirmation"
            ),
        ])
    hypothesis_lines = _impact_hypothesis_lines(entry)
    if hypothesis_lines:
        lines.extend(["", "## Impact Hypothesis Context"])
        lines.extend(hypothesis_lines)
    lines.extend([
        "",
        "## LLM Interpretation",
        f"- Role: {_value(entry, alert, 'latest_llm_asset_role', 'llm_asset_role') or 'none'}",
        f"- Confidence: {_value(entry, alert, 'latest_llm_confidence', 'llm_confidence') or 'n/a'}",
        f"- Reason: {str(alert.get('llm_reason') or alert.get('llm_adjustment_reason') or 'n/a') if alert else 'n/a'}",
        "",
        "## Market Confirmation",
    ])
    lines.extend(_market_lines(entry, alert))
    lines.extend([
        "",
        "## Derivatives / Supply / Liquidity",
        f"- Derivatives crowding: {_score(entry, alert, 'derivatives_crowding')}",
        f"- Supply pressure: {_score(entry, alert, 'supply_pressure')}",
        f"- Cluster confidence: {_score(entry, alert, 'cluster_confidence')}",
        "",
        "## Latest Monitor Update",
    ])
    lines.extend(_monitor_lines(monitor_row))
    lines.extend([
        "",
        "## Lifecycle Timeline",
    ])
    lines.extend(_lifecycle_lines(entry, alert, monitor_row, feedback, outcome))
    lines.extend([
        "",
        "## Why This Matters",
        _why_it_matters(playbook),
        "",
        "## What To Verify",
    ])
    lines.extend(_verify_lines(alert, playbook))
    lines.extend([
        "",
        "## Trade-Readiness Checklist",
    ])
    lines.extend(_trade_readiness_lines(entry, alert, playbook, state))
    lines.extend([
        "",
        "## Invalidation / Why Wrong",
        f"- {_value(None, alert, '', 'playbook_invalidation') or _default_invalidation(playbook)}",
        "",
        "## Alert History",
    ])
    lines.extend(_history_lines(entry))
    warnings = _warnings(entry, alert, decision)
    if warnings:
        lines.extend(["", "## Warnings / Source-Noise Rejections"])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend([
        "",
        "## Outcome Tracking Fields",
        f"- Expected direction: {_value(None, outcome, '', 'expected_direction') or 'unknown'}",
        f"- Primary horizon: {_value(None, outcome, '', 'primary_horizon') or 'unknown'}",
        f"- Success metric: {_value(None, outcome, '', 'success_metric') or 'manual'}",
        f"- Primary horizon return: {_value(None, outcome, '', 'primary_horizon_return') or 'blank'}",
        f"- MFE/MAE: {_value(None, outcome, '', 'mfe_mae_ratio') or 'blank'}",
    ])
    return EventResearchCardResult(key=clean_key, markdown="\n".join(lines).rstrip() + "\n", found=True)


def render_selected_cards(
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision] = (),
    clusters: Iterable[event_graph.EventCluster] = (),
    monitor_rows: Iterable[event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    limit: int = 10,
) -> str:
    cluster_rows = list(clusters)
    monitor = list(monitor_rows)
    entries = [
        entry for entry in watchlist_entries
        if event_watchlist.final_state_value(entry) in {
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
            event_watchlist.EventWatchlistState.WATCHLIST.value,
        } and not event_watchlist.state_is_quality_capped(entry)
    ][: max(1, limit)]
    if not entries:
        return "# Event Research Cards\n\nNo selected watchlist entries found.\n"
    cards = [
        render_research_card(
            entry.key,
            watchlist_entries=watchlist_entries,
            alert_rows=alert_rows,
            route_decisions=route_decisions,
            clusters=cluster_rows,
            monitor_rows=monitor,
            feedback_rows=feedback_rows,
            outcome_rows=outcome_rows,
        ).markdown
        for entry in entries
    ]
    return "\n---\n\n".join(cards)


def write_research_cards(
    out_dir: str | Path,
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision] = (),
    clusters: Iterable[event_graph.EventCluster] = (),
    monitor_rows: Iterable[event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    include_all_alertable: bool = True,
    selected_tiers: Iterable[str] | None = None,
    limit: int = 25,
    now: datetime | None = None,
) -> EventResearchCardWriteResult:
    """Write selected Markdown cards and an index under a local artifact dir."""
    target = Path(out_dir).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    entries = _selected_entries(
        list(watchlist_entries),
        list(route_decisions),
        include_all_alertable=include_all_alertable,
        selected_tiers=selected_tiers,
    )
    card_paths: list[Path] = []
    for entry in entries[: max(1, limit)]:
        card = render_research_card(
            entry.key,
            watchlist_entries=entries,
            alert_rows=alert_rows,
            route_decisions=route_decisions,
            clusters=clusters,
            monitor_rows=monitor_rows,
            feedback_rows=feedback_rows,
            outcome_rows=outcome_rows,
            generated_at=observed,
        )
        if not card.found:
            continue
        path = target / _card_filename(entry)
        path.write_text(_strip_sensitive(card.markdown), encoding="utf-8")
        card_paths.append(path)
    index = _render_index(card_paths, observed)
    index_path = target / "index.md"
    index_path.write_text(index, encoding="utf-8")
    return EventResearchCardWriteResult(
        out_dir=target,
        cards_written=len(card_paths),
        index_path=index_path,
        card_paths=tuple(card_paths),
    )


def format_card_write_result(result: EventResearchCardWriteResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT RESEARCH CARDS WRITTEN (research artifact only)",
        "=" * 76,
        f"out_dir: {result.out_dir}",
        f"cards_written: {result.cards_written}",
        f"index: {result.index_path}",
        *(f"- {path}" for path in result.card_paths[:20]),
        "No live RSI alerts, paper trades, live DB rows, or execution were changed.",
    ])


def _find_entry(key: str, entries: list[event_watchlist.EventWatchlistEntry]) -> event_watchlist.EventWatchlistEntry | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    if clean_key.startswith("card_"):
        clean_key = clean_key[5:]
    key_l = clean_key.lower()
    matches = [
        entry for entry in entries
        if clean_key in {entry.key, entry.event_id}
        or key_l in {entry.symbol.lower(), entry.coin_id.lower()}
    ]
    return matches[0] if matches else None


def _selected_entries(
    entries: list[event_watchlist.EventWatchlistEntry],
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
    *,
    include_all_alertable: bool,
    selected_tiers: Iterable[str] | None,
) -> list[event_watchlist.EventWatchlistEntry]:
    selected_by_key: dict[str, event_watchlist.EventWatchlistEntry] = {}
    states = set(selected_tiers or {
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        "HIGH_PRIORITY_WATCH",
    })
    for entry in entries:
        if (
            event_watchlist.final_state_value(entry) in states
            or entry.latest_tier in states
        ) and not event_watchlist.state_is_quality_capped(entry):
            selected_by_key[entry.key] = entry
    if include_all_alertable:
        for decision in decisions:
            if event_alpha_router.alertable_after_quality_gate(decision):
                selected_by_key[decision.entry.key] = decision.entry
    return sorted(
        selected_by_key.values(),
        key=lambda entry: (entry.last_seen_at, entry.latest_score, entry.symbol),
        reverse=True,
    )


def _card_filename(entry: event_watchlist.EventWatchlistEntry) -> str:
    base = event_alpha_router.card_id_for_entry(entry)
    return _slug(base)[:180] + ".md"


def _slug(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9._-]+", "_", value)).strip("._") or "event_card"


def _render_index(paths: list[Path], observed: datetime) -> str:
    lines = [
        "# Event Research Cards",
        "",
        f"Generated at: {observed.isoformat()}",
        "",
    ]
    if not paths:
        lines.append("No cards selected.")
    else:
        for path in paths:
            lines.append(f"- [{path.name}]({path.name})")
    return "\n".join(lines).rstrip() + "\n"


def _strip_sensitive(markdown: str) -> str:
    out = markdown.replace("OPENAI_API_KEY", "[redacted]").replace("TELEGRAM_BOT_TOKEN", "[redacted]")
    out = out.replace(".env", "[env-file]")
    return out


def _find_alert(key: str, rows: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    key_l = clean_key.lower()
    for row in rows:
        values = {
            str(row.get("alert_key") or ""),
            str(row.get("event_id") or ""),
            str(row.get("asset_symbol") or ""),
            str(row.get("asset_coin_id") or ""),
        }
        if clean_key in values or key_l in {value.lower() for value in values}:
            return row
    return None


def _find_decision(
    key: str,
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
) -> event_alpha_router.EventAlphaRouteDecision | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    key_l = clean_key.lower()
    for decision in decisions:
        entry = decision.entry
        if clean_key in {entry.key, entry.event_id, decision.alert_id, decision.card_id} or key_l in {
            entry.symbol.lower(),
            entry.coin_id.lower(),
        }:
            return decision
    return None


def _find_cluster(
    key: str,
    clusters: list[event_graph.EventCluster],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> event_graph.EventCluster | None:
    key_l = key.lower()
    identifiers = {
        key,
        key_l,
        str(getattr(entry, "cluster_id", "") or ""),
        str(getattr(entry, "event_id", "") or ""),
        str(alert.get("cluster_id") or "") if alert else "",
        str(alert.get("event_id") or "") if alert else "",
    }
    identifiers_l = {item.lower() for item in identifiers if item}
    for cluster in clusters:
        if cluster.cluster_id in identifiers or cluster.cluster_id.lower() in identifiers_l:
            return cluster
        if any(str(event_id).lower() in identifiers_l for event_id in cluster.event_ids):
            return cluster
        for link in cluster.asset_links:
            if key_l in {link.symbol.lower(), link.coin_id.lower()}:
                return cluster
    return None


def _find_monitor_row(
    key: str,
    rows: list[event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any]],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any] | None:
    clean_key = key[3:] if key.startswith("ea:") else key
    key_l = clean_key.lower()
    identifiers = {
        clean_key,
        key_l,
        str(getattr(entry, "key", "") or ""),
        str(getattr(entry, "symbol", "") or ""),
        str(getattr(entry, "coin_id", "") or ""),
        str(alert.get("alert_key") or "") if alert else "",
        str(alert.get("asset_symbol") or "") if alert else "",
        str(alert.get("asset_coin_id") or "") if alert else "",
    }
    identifiers_l = {item.lower() for item in identifiers if item}
    for row in rows:
        values = {
            str(_monitor_value(row, "key") or ""),
            str(_monitor_value(row, "symbol") or ""),
            str(_monitor_value(row, "coin_id") or ""),
        }
        if clean_key in values or key_l in {value.lower() for value in values} or identifiers_l & {
            value.lower() for value in values if value
        }:
            return row
    return None


def _matching_rows(
    key: str,
    rows: list[Mapping[str, Any]],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    clean_key = key[3:] if key.startswith("ea:") else key
    key_l = clean_key.lower()
    identifiers = {
        clean_key,
        str(getattr(entry, "key", "") or ""),
        str(getattr(entry, "event_id", "") or ""),
        str(getattr(entry, "symbol", "") or ""),
        str(getattr(entry, "coin_id", "") or ""),
        str(alert.get("alert_key") or "") if alert else "",
        str(alert.get("event_id") or "") if alert else "",
        str(alert.get("asset_symbol") or "") if alert else "",
        str(alert.get("asset_coin_id") or "") if alert else "",
    }
    identifiers_l = {item.lower() for item in identifiers if item}
    matches: list[Mapping[str, Any]] = []
    for row in rows:
        values = {
            str(row.get("key") or ""),
            str(row.get("target") or ""),
            str(row.get("alert_key") or ""),
            str(row.get("event_id") or ""),
            str(row.get("symbol") or row.get("asset_symbol") or ""),
            str(row.get("coin_id") or row.get("asset_coin_id") or ""),
        }
        values_l = {value.lower() for value in values if value}
        if key_l in values_l or identifiers_l & values_l:
            matches.append(row)
    return matches


def _find_outcome(
    key: str,
    rows: list[Mapping[str, Any]],
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    matches = _matching_rows(key, rows, entry, alert)
    if not matches:
        return None
    return sorted(matches, key=lambda row: str(row.get("observed_at") or row.get("updated_at") or ""), reverse=True)[0]


def _value(entry: Any | None, alert: Mapping[str, Any] | None, entry_field: str, alert_field: str) -> Any:
    if entry is not None and entry_field:
        value = getattr(entry, entry_field, None)
        if value not in (None, ""):
            return value
    if alert is not None:
        value = alert.get(alert_field)
        if value not in (None, ""):
            return value
    return None


def _cluster_lines(cluster: event_graph.EventCluster | None) -> list[str]:
    if cluster is None:
        return ["- No cluster graph data found in local artifacts."]
    accepted = [link for link in cluster.asset_links if link.accepted]
    rejected = [link for link in cluster.asset_links if not link.accepted]
    providers = sorted({evidence.source for evidence in cluster.evidence if evidence.source})
    origins = sorted({
        _origin(url)
        for evidence in cluster.evidence
        for url in evidence.source_urls
        if url
    })
    lines = [
        f"- Cluster ID: {cluster.cluster_id}",
        f"- Cluster confidence: {cluster.cluster_confidence}",
        f"- Independent sources: {cluster.independent_source_count}",
        f"- Event-time consensus: {cluster.event_time_consensus}",
        f"- Source providers: {', '.join(providers) if providers else 'unknown'}",
        f"- Source origins: {', '.join(origins) if origins else 'unknown'}",
    ]
    accepted_by_kind: dict[str, list[str]] = {}
    for link in accepted:
        accepted_by_kind.setdefault(link.accepted_kind, []).append(f"{link.symbol}/{link.coin_id}")
    if accepted_by_kind:
        lines.append(
            "- Accepted links by kind: "
            + "; ".join(
                f"{kind}={', '.join(values)}"
                for kind, values in sorted(accepted_by_kind.items())
            )
        )
    else:
        lines.append("- Accepted links by kind: none")
    if rejected:
        lines.append(
            "- Rejected/noise links: "
            + "; ".join(
                f"{link.symbol}/{link.coin_id}:{link.rejected_reason or 'rejected'}"
                for link in rejected[:8]
            )
        )
    else:
        lines.append("- Rejected/noise links: none")
    if cluster.source_urls:
        lines.append("- Top evidence URLs: " + "; ".join(cluster.source_urls[:5]))
    if cluster.warnings:
        lines.append("- Cluster warnings: " + "; ".join(cluster.warnings))
    return lines


def _origin(url: str) -> str:
    parsed = urlparse(str(url))
    return parsed.netloc or parsed.path or "unknown"


def _source_lines(entry: event_watchlist.EventWatchlistEntry | None, alert: Mapping[str, Any] | None) -> list[str]:
    lines: list[str] = []
    if alert is not None:
        if alert.get("source"):
            lines.append(f"- Source: {alert.get('source')}")
        if alert.get("source_url"):
            lines.append(f"- URL: {alert.get('source_url')}")
        if alert.get("source_provider"):
            lines.append(f"- Provider: {alert.get('source_provider')}")
    if entry is not None:
        lines.append(f"- Latest source: {entry.latest_source or 'unknown'}")
        lines.append(f"- Source count: {entry.source_count}")
    return lines or ["- No source details found in local artifacts."]


def _market_lines(entry: event_watchlist.EventWatchlistEntry | None, alert: Mapping[str, Any] | None) -> list[str]:
    snapshot = dict(entry.latest_market_snapshot if entry else {})
    if alert is not None:
        for key in ("market_price", "return_24h", "return_72h", "return_7d", "volume_24h", "market_cap"):
            if alert.get(key) is not None:
                snapshot[key] = alert.get(key)
    if not snapshot:
        return ["- No market snapshot stored."]
    lines = []
    for key in ("price", "market_price", "return_24h", "return_72h", "return_7d", "volume_24h", "market_cap"):
        if snapshot.get(key) is not None:
            lines.append(f"- {key}: {snapshot.get(key)}")
    return lines or ["- No market snapshot stored."]


def _impact_hypothesis_lines(entry: event_watchlist.EventWatchlistEntry | None) -> list[str]:
    if entry is None or entry.relationship_type != "impact_hypothesis":
        return []
    components = dict(entry.latest_score_components or {})
    validated_asset = components.get("validated_asset") if isinstance(components.get("validated_asset"), Mapping) else {}
    validated_symbol = components.get("validated_symbol") or validated_asset.get("symbol") or entry.symbol
    validated_coin_id = components.get("validated_coin_id") or validated_asset.get("coin_id") or entry.coin_id
    candidate_symbols = components.get("candidate_symbols") or []
    validation_reasons = components.get("validation_reasons") or components.get("validation_reason") or []
    if isinstance(validation_reasons, str):
        validation_reasons = [validation_reasons]
    gate_block = event_alpha_router.validated_hypothesis_digest_block_reason(entry)
    gate_line = "passed for capped research digest" if gate_block is None else f"local-only: {gate_block}"
    impact_path_reason = components.get("impact_path_reason") or "unknown"
    impact_path_type = components.get("impact_path_type") or "unknown"
    candidate_role = components.get("candidate_role") or "unknown"
    incident_id = components.get("incident_id") or "unknown"
    canonical_incident_name = components.get("canonical_incident_name") or "unknown"
    event_archetype = components.get("event_archetype") or "unknown"
    primary_subject = components.get("primary_subject") or "unknown"
    affected_ecosystem = components.get("affected_ecosystem") or "unknown"
    cause_status = components.get("cause_status") or "unknown"
    claim_polarities = components.get("claim_polarities") or []
    role_confidence = components.get("role_confidence")
    role_evidence = components.get("role_evidence") or []
    market_context_source = components.get("market_context_source") or "unknown"
    market_context_quality = components.get("market_context_data_quality") or "unknown"
    market_reaction_confirmed = components.get("market_reaction_confirmed")
    causal_mechanism_confirmed = components.get("causal_mechanism_confirmed")
    impact_path_strength = components.get("impact_path_strength") or "unknown"
    opportunity_score_v2 = components.get("opportunity_score_v2")
    evidence_specificity = components.get("evidence_specificity_score")
    why_digest_ineligible = components.get("why_digest_ineligible") or "none"
    digest_eligible = components.get("digest_eligible_by_impact_path")
    evidence_quality_score = components.get("evidence_quality_score")
    source_class = components.get("source_class") or "unknown"
    evidence_specificity_class = components.get("evidence_specificity") or "unknown"
    market_confirmation_score = components.get("market_confirmation_score")
    market_confirmation_level = components.get("market_confirmation_level") or "unknown"
    market_confirmation_summary = components.get("market_confirmation_summary") or "none"
    opportunity_score_final = components.get("opportunity_score_final")
    opportunity_level = components.get("opportunity_level") or "unknown"
    verdict_reasons = components.get("opportunity_verdict_reasons") or []
    missing_requirements = components.get("missing_requirements") or []
    manual_verification_items = components.get("manual_verification_items") or []
    if isinstance(verdict_reasons, str):
        verdict_reasons = [verdict_reasons]
    if isinstance(missing_requirements, str):
        missing_requirements = [missing_requirements]
    if isinstance(manual_verification_items, str):
        manual_verification_items = [manual_verification_items]
    why_not_promoted = components.get("why_not_promoted") or []
    if isinstance(why_not_promoted, str):
        why_not_promoted = [why_not_promoted]
    upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
    lines = [
        f"- Validated asset: {validated_symbol or 'unknown'}/{validated_coin_id or 'unknown'}",
        f"- Incident: {canonical_incident_name} ({incident_id})",
        f"- Event archetype: {event_archetype}",
        f"- Primary subject: {primary_subject}",
        f"- Affected ecosystem: {affected_ecosystem}",
        f"- Cause status: {cause_status}",
        f"- Claim polarity: {', '.join(str(item) for item in claim_polarities[:6]) if claim_polarities else 'unknown'}",
        f"- Original sector hypothesis: {', '.join(str(item) for item in (components.get('candidate_sectors') or [])[:6]) or components.get('hypothesis_scope') or 'unknown'}",
        f"- Candidate source: {entry.latest_source or 'impact_hypothesis'}",
        f"- Candidate Discovery Origin: {components.get('candidate_source') or components.get('source') or entry.latest_source or 'impact_hypothesis'}",
        f"- Candidate symbols considered: {', '.join(str(item) for item in candidate_symbols[:8]) if candidate_symbols else 'none'}",
        f"- Playbook: {entry.latest_playbook_type or 'impact_hypothesis'}",
        f"- Impact path type: {impact_path_type}",
        f"- Candidate role: {candidate_role}",
        f"- Candidate role confidence: {role_confidence if role_confidence is not None else 'n/a'}",
        f"- Candidate role evidence: {'; '.join(str(item) for item in role_evidence[:4]) if role_evidence else 'none'}",
        f"- Impact path strength: {impact_path_strength}",
        f"- Impact path reason: {impact_path_reason}",
        f"- Opportunity score v2: {opportunity_score_v2 if opportunity_score_v2 is not None else 'n/a'}",
        f"- Final opportunity verdict: {opportunity_level} / {opportunity_score_final if opportunity_score_final is not None else 'n/a'}",
        f"- Source/evidence specificity: {evidence_specificity if evidence_specificity is not None else 'n/a'}",
        f"- Evidence quality: {source_class}/{evidence_specificity_class} / {evidence_quality_score if evidence_quality_score is not None else 'n/a'}",
        f"- Market confirmation: {market_confirmation_level} / {market_confirmation_score if market_confirmation_score is not None else 'n/a'}",
        f"- Market context source: {market_context_source} ({market_context_quality})",
        f"- Market reaction confirmed: {str(bool(market_reaction_confirmed)).lower() if market_reaction_confirmed is not None else 'unknown'}",
        f"- Causal mechanism confirmed: {str(bool(causal_mechanism_confirmed)).lower() if causal_mechanism_confirmed is not None else 'unknown'}",
        f"- Market summary: {market_confirmation_summary}",
        f"- Impact path digest eligible: {str(bool(digest_eligible)).lower() if digest_eligible is not None else 'unknown'}",
        f"- Missing evidence / gate failure: {why_digest_ineligible}",
        f"- Opportunity verdict reasons: {'; '.join(str(item) for item in verdict_reasons[:4]) if verdict_reasons else 'none'}",
        f"- Missing requirements: {'; '.join(str(item) for item in missing_requirements[:4]) if missing_requirements else 'none'}",
        f"- Quality gate: {gate_line}",
        f"- Local-only due to weak co-occurrence: {str('impact_path_not_validated' in gate_line or 'weak_validated_local_only' in gate_line or why_digest_ineligible != 'none').lower()}",
        f"- Why promoted/local-only: {entry.suppressed_reason or 'validated impact hypothesis promoted to RADAR'}",
        "- Safety label: catalyst link validated, but this is not a calibrated strategy or trade signal.",
        "- Why it may be wrong: validation may be source-thin, asset link may be narrative-only, and the catalyst impact may not move this token.",
        "- What to verify manually: "
        + (
            "; ".join(str(item) for item in manual_verification_items[:4])
            if manual_verification_items
            else "independent catalyst source, asset identity, liquidity/organic volume, and whether the catalyst actually affects this token."
        ),
        "- What would upgrade this candidate: " + "; ".join(upgrade.upgrade_requirements[:6]),
        "- What would invalidate this candidate: " + "; ".join(upgrade.downgrade_warnings[:6]),
    ]
    if validation_reasons:
        lines.append("- Validation evidence: " + "; ".join(str(item) for item in validation_reasons[:4]))
    if why_not_promoted:
        lines.append("- Why not promoted diagnostics: " + "; ".join(str(item) for item in why_not_promoted[:4]))
    return lines


def _quality_gate_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    decision: event_alpha_router.EventAlphaRouteDecision | None,
) -> list[str]:
    components = dict(entry.latest_score_components if entry else {})
    if alert is not None:
        components.update({key: value for key, value in alert.items() if value not in (None, "", [], {})})
    requested = (
        getattr(decision, "requested_route_before_quality_gate", None)
        if decision is not None
        else components.get("requested_route_before_quality_gate")
    ) or components.get("route") or "unknown"
    final = (
        getattr(decision, "final_route_after_quality_gate", None)
        if decision is not None
        else components.get("final_route_after_quality_gate")
    ) or components.get("route") or "unknown"
    final_tier = components.get("final_tier_after_quality_gate") or components.get("tier") or "unknown"
    classification = components.get("snapshot_quality_classification") or "unknown"
    block = (
        getattr(decision, "quality_gate_block_reason", None)
        if decision is not None
        else components.get("quality_gate_block_reason")
    ) or "none"
    opportunity_level = (
        getattr(decision, "opportunity_level", None)
        if decision is not None
        else components.get("opportunity_level")
    ) or _value(entry, alert, "opportunity_level", "opportunity_level") or "unknown"
    opportunity_score = (
        getattr(decision, "opportunity_score_final", None)
        if decision is not None
        else components.get("opportunity_score_final")
    )
    if opportunity_score is None:
        opportunity_score = _value(entry, alert, "opportunity_score_final", "opportunity_score_final") or "n/a"
    allowed = str(block) == "none" and str(final) == str(requested)
    return [
        f"- Requested route: {requested}",
        f"- Final route: {final}",
        f"- Final tier: {final_tier}",
        f"- Snapshot classification: {classification}",
        f"- Result: {'allowed' if allowed else 'blocked/downgraded'}",
        f"- Block reason: {block}",
        f"- Opportunity verdict: {opportunity_level} / {opportunity_score}",
        f"- Why blocked / allowed: {block if block != 'none' else 'opportunity verdict permits the final route'}",
    ]


def _monitor_lines(row: event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any] | None) -> list[str]:
    if row is None:
        return [
            "- No watchlist monitor row found.",
            "- Monitor data is observation-only and cannot create TRIGGERED_FADE.",
        ]
    hints = _monitor_value(row, "state_transition_hints") or ()
    if isinstance(hints, str):
        hints = tuple(part.strip() for part in hints.split(",") if part.strip())
    lines = [
        f"- Material update: {str(bool(_monitor_value(row, 'material_update'))).lower()}",
        f"- State transition hints: {', '.join(str(item) for item in hints) if hints else 'none'}",
        f"- Return 24h / 72h / 7d: {_monitor_value(row, 'return_24h')} / {_monitor_value(row, 'return_72h')} / {_monitor_value(row, 'return_7d')}",
        f"- Volume z-score / volume-to-market-cap: {_monitor_value(row, 'volume_zscore_24h')} / {_monitor_value(row, 'volume_to_market_cap')}",
        f"- Derivatives crowding: {_monitor_value(row, 'derivatives_crowding')}",
        f"- Supply pressure: {_monitor_value(row, 'supply_pressure')}",
        f"- Event countdown hours: {_monitor_value(row, 'event_countdown_hours') or 'n/a'}",
        f"- Event age hours: {_monitor_value(row, 'event_age_hours') or 'n/a'}",
        "- Monitor data is observation-only and cannot create TRIGGERED_FADE.",
    ]
    return lines


def _lifecycle_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    monitor_row: event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any] | None,
    feedback_rows: list[Mapping[str, Any]],
    outcome: Mapping[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    timeline_fields = (
        ("first_seen", "first_seen_at"),
        ("radar", "first_radar_at"),
        ("watchlisted", "first_watchlisted_at"),
        ("high_priority", "first_high_priority_at"),
        ("event_passed", "first_event_passed_at"),
        ("armed", "first_armed_at"),
        ("triggered", "first_triggered_at"),
        ("invalidated", "first_invalidated_at"),
        ("expired", "first_expired_at"),
        ("last_seen", "last_seen_at"),
    )
    if entry is not None:
        for label, field in timeline_fields:
            value = getattr(entry, field, None)
            if value:
                lines.append(f"- {label}: {value}")
    if alert is not None and alert.get("observed_at"):
        lines.append(f"- alert_snapshot: {alert.get('observed_at')}")
    if monitor_row is not None:
        hints = _monitor_value(monitor_row, "state_transition_hints") or ()
        if isinstance(hints, str):
            hints = tuple(part.strip() for part in hints.split(",") if part.strip())
        lines.append(
            "- latest_monitor: "
            f"material={str(bool(_monitor_value(monitor_row, 'material_update'))).lower()} "
            f"hints={', '.join(str(item) for item in hints) if hints else 'none'}"
        )
    if feedback_rows:
        for row in sorted(feedback_rows, key=lambda item: str(item.get("marked_at") or ""), reverse=True)[:5]:
            lines.append(
                f"- feedback: {row.get('label') or 'unknown'} at {row.get('marked_at') or 'unknown'} "
                f"by {row.get('marked_by') or 'unknown'}"
            )
    else:
        lines.append("- feedback: none")
    if outcome is not None and any(outcome.get(field) not in (None, "") for field in (
        "primary_horizon_return",
        "return_24h",
        "return_72h",
        "return_7d",
        "direction_hit",
        "mfe_mae_ratio",
    )):
        lines.append(
            "- outcome: "
            f"primary={outcome.get('primary_horizon_return', 'blank')} "
            f"24h={outcome.get('return_24h', 'blank')} "
            f"72h={outcome.get('return_72h', 'blank')} "
            f"7d={outcome.get('return_7d', 'blank')} "
            f"direction_hit={outcome.get('direction_hit', 'blank')} "
            f"mfe_mae={outcome.get('mfe_mae_ratio', 'blank')}"
        )
    else:
        lines.append("- outcome: not filled")
    return lines or ["- No lifecycle timestamps found."]


def _monitor_value(row: event_watchlist_monitor.EventWatchlistMonitorRow | Mapping[str, Any], field: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(field)
    return getattr(row, field, None)


def _verify_lines(alert: Mapping[str, Any] | None, playbook: str) -> list[str]:
    items = []
    if alert is not None:
        raw = alert.get("playbook_what_to_verify") or alert.get("what_to_verify")
        if isinstance(raw, (list, tuple)):
            items.extend(str(item) for item in raw if str(item))
    if not items:
        if "listing" in playbook:
            items = ["confirm listing venue/mechanics", "check opening liquidity and spread"]
        elif "unlock" in playbook:
            items = ["confirm unlock size", "compare unlock size to liquidity"]
        elif "market_anomaly" in playbook:
            items = ["find source evidence", "verify asset identity"]
        elif "proxy_fade" in playbook:
            items = ["confirm post-event failure", "confirm invalidation level"]
        else:
            items = ["verify source evidence", "verify asset identity"]
    return [f"- {item}" for item in items]


def _history_lines(entry: event_watchlist.EventWatchlistEntry | None) -> list[str]:
    if entry is None or not entry.alert_history:
        return ["- No watchlist alert history found."]
    lines = []
    for item in entry.alert_history[-8:]:
        lines.append(
            f"- {item.get('observed_at', 'unknown')}: state={item.get('state', 'unknown')} "
            f"tier={item.get('tier', 'unknown')} score={item.get('score', 0)}"
        )
    return lines


def _warnings(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    decision: event_alpha_router.EventAlphaRouteDecision | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if entry is not None:
        warnings.extend(entry.warnings)
    if alert is not None:
        for field in ("warnings", "rejected_reason", "llm_adjustment_reason"):
            value = alert.get(field)
            if isinstance(value, (list, tuple)):
                warnings.extend(str(item) for item in value if str(item))
            elif value:
                warnings.append(str(value))
    if decision is not None:
        warnings.extend(decision.warnings)
    return tuple(dict.fromkeys(warnings))


def _score(entry: event_watchlist.EventWatchlistEntry | None, alert: Mapping[str, Any] | None, key: str) -> Any:
    if entry is not None and key in entry.latest_score_components:
        return entry.latest_score_components.get(key)
    components = alert.get("score_components") if alert is not None else None
    if isinstance(components, Mapping):
        return components.get(key, "n/a")
    return "n/a"


def _playbook_copy(playbook: str, alert: Mapping[str, Any] | None) -> str:
    if alert is not None and alert.get("playbook_hypothesis"):
        return f"- Hypothesis: {alert.get('playbook_hypothesis')}"
    if "listing" in playbook:
        return "- Hypothesis: exchange listing mechanics may create volatility around new liquidity access."
    if "unlock" in playbook:
        return "- Hypothesis: unlock supply may pressure price if liquidity is thin."
    if "market_anomaly" in playbook:
        return "- Hypothesis: market move is unusual, but catalyst evidence is unknown."
    if playbook == "proxy_fade":
        return "- Hypothesis: proxy narrative may fade after the dated catalyst and failed reclaim."
    return "- Hypothesis: event/catalyst relationship needs manual review."


def _why_it_matters(playbook: str) -> str:
    if "listing" in playbook:
        return "Listings can change venue access, liquidity, spreads, and short-term volatility."
    if "unlock" in playbook:
        return "Unlocks can add sellable supply into shallow liquidity."
    if "market_anomaly" in playbook:
        return "Large moves without source evidence are useful missed-opportunity and catalyst-search inputs."
    if playbook == "proxy_fade":
        return "Temporary proxy narratives can unwind after the external catalyst passes."
    return "The row helps calibrate source quality, resolver precision, and playbook thresholds."


def _default_invalidation(playbook: str) -> str:
    if "listing" in playbook:
        return "Listing is stale, liquidity is deep, or volatility does not expand."
    if "unlock" in playbook:
        return "Unlock is small, already absorbed, or liquidity is sufficient."
    if "market_anomaly" in playbook:
        return "No credible catalyst or asset identity evidence emerges."
    if playbook == "proxy_fade":
        return "Price reclaims event VWAP/invalidation level or proxy narrative persists."
    return "Source evidence fails identity/catalyst review."


def _trade_readiness_lines(
    entry: event_watchlist.EventWatchlistEntry | None,
    alert: Mapping[str, Any] | None,
    playbook: str,
    state: str,
) -> list[str]:
    components = alert.get("score_components") if alert is not None and isinstance(alert.get("score_components"), Mapping) else {}
    timing = _value(entry, alert, "event_time", "event_time") or "unknown"
    direction = _value(None, alert, "", "expected_direction") or _playbook_direction(playbook)
    horizon = _value(None, alert, "", "primary_horizon") or "manual"
    invalidation = _value(None, alert, "", "playbook_invalidation") or _default_invalidation(playbook)
    lines = [
        f"- Catalyst clarity: {_check_value(components, 'external_catalyst')}",
        f"- Event timing quality: {timing} / {_check_value(components, 'event_time_quality')}",
        f"- Market confirmation: {_check_value(components, 'market_move_volume')}",
        f"- Derivatives crowding: {_score(entry, alert, 'derivatives_crowding')}",
        f"- Liquidity/supply risk: supply={_score(entry, alert, 'supply_pressure')} liquidity=manual review",
        f"- Current lifecycle state: {state}",
        f"- Primary playbook: {playbook}",
        f"- Expected direction / horizon: {direction} / {horizon}",
        f"- Invalidation / why wrong: {invalidation}",
    ]
    if playbook == "proxy_fade":
        lines.append("- Manual verification: confirm post-event failure, failed reclaim, and invalidation level before treating as research-actionable.")
    elif "listing" in playbook:
        lines.append("- Manual verification: confirm venue, listing mechanics, opening liquidity, spread, and whether the event is already priced.")
    elif "unlock" in playbook:
        lines.append("- Manual verification: confirm unlock size, circulating-supply impact, recipient wallets, and available liquidity.")
    elif "market_anomaly" in playbook:
        lines.append("- Manual verification: catalyst unvalidated; find source evidence and confirm asset identity before escalation.")
    else:
        lines.append("- Manual verification: confirm source evidence, asset identity, playbook fit, and why the thesis could be wrong.")
    return lines


def _check_value(components: Mapping[str, Any], key: str) -> str:
    value = components.get(key)
    return "n/a" if value is None else str(value)


def _playbook_direction(playbook: str) -> str:
    if playbook in {"proxy_fade", "unlock_supply_pressure"}:
        return "down"
    if "listing" in playbook:
        return "volatility"
    if "market_anomaly" in playbook:
        return "unknown"
    return "manual"
