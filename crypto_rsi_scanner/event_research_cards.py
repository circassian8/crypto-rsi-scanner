"""Markdown research cards for routed Event Alpha candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from . import event_alpha_router, event_graph, event_watchlist


@dataclass(frozen=True)
class EventResearchCardResult:
    key: str
    markdown: str
    found: bool


def render_research_card(
    key: str,
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision] = (),
    clusters: Iterable[event_graph.EventCluster] = (),
) -> EventResearchCardResult:
    """Render one Markdown card from local research artifacts."""
    clean_key = str(key or "").strip()
    entry = _find_entry(clean_key, list(watchlist_entries))
    alert = _find_alert(clean_key, list(alert_rows))
    decision = _find_decision(clean_key, list(route_decisions))
    cluster = _find_cluster(clean_key, list(clusters), entry, alert)
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
    state = entry.state if entry is not None else str(alert.get("state") or "snapshot")
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
        lines.append(f"- Route: {decision.route.value} ({decision.reason})")
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
        "## Why This Matters",
        _why_it_matters(playbook),
        "",
        "## What To Verify",
    ])
    lines.extend(_verify_lines(alert, playbook))
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
        f"- Expected direction: {_value(None, alert, '', 'expected_direction') or 'unknown'}",
        f"- Primary horizon: {_value(None, alert, '', 'primary_horizon') or 'unknown'}",
        f"- Success metric: {_value(None, alert, '', 'success_metric') or 'manual'}",
        f"- Primary horizon return: {_value(None, alert, '', 'primary_horizon_return') or 'blank'}",
        f"- MFE/MAE: {_value(None, alert, '', 'mfe_mae_ratio') or 'blank'}",
    ])
    return EventResearchCardResult(key=clean_key, markdown="\n".join(lines).rstrip() + "\n", found=True)


def render_selected_cards(
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    alert_rows: Iterable[Mapping[str, Any]] = (),
    route_decisions: Iterable[event_alpha_router.EventAlphaRouteDecision] = (),
    clusters: Iterable[event_graph.EventCluster] = (),
    limit: int = 10,
) -> str:
    cluster_rows = list(clusters)
    entries = [
        entry for entry in watchlist_entries
        if entry.state in {
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
            event_watchlist.EventWatchlistState.WATCHLIST.value,
        }
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
        ).markdown
        for entry in entries
    ]
    return "\n---\n\n".join(cards)


def _find_entry(key: str, entries: list[event_watchlist.EventWatchlistEntry]) -> event_watchlist.EventWatchlistEntry | None:
    key_l = key.lower()
    matches = [
        entry for entry in entries
        if key in {entry.key, entry.event_id}
        or key_l in {entry.symbol.lower(), entry.coin_id.lower()}
    ]
    return matches[0] if matches else None


def _find_alert(key: str, rows: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    key_l = key.lower()
    for row in rows:
        values = {
            str(row.get("alert_key") or ""),
            str(row.get("event_id") or ""),
            str(row.get("asset_symbol") or ""),
            str(row.get("asset_coin_id") or ""),
        }
        if key in values or key_l in {value.lower() for value in values}:
            return row
    return None


def _find_decision(
    key: str,
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
) -> event_alpha_router.EventAlphaRouteDecision | None:
    key_l = key.lower()
    for decision in decisions:
        entry = decision.entry
        if key in {entry.key, entry.event_id} or key_l in {entry.symbol.lower(), entry.coin_id.lower()}:
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
