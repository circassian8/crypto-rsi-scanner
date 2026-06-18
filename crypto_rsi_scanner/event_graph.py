"""Research-only event clustering for Event Alpha Radar.

Clusters group differently worded source events around the same external
catalyst. They do not create candidates, alerts, trades, or event-fade
eligibility; they only provide stable research identity for watchlist state and
review reports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from .event_models import DiscoveredEventFadeCandidate, EventDiscoveryResult, NormalizedEvent
from .event_resolver import clean_text

EVENT_GRAPH_SCHEMA_VERSION = "event_graph_v1"


@dataclass(frozen=True)
class ClusterEvidence:
    event_id: str
    raw_ids: tuple[str, ...]
    source_urls: tuple[str, ...]
    event_name: str
    source: str
    first_seen_time: datetime
    confidence: float


@dataclass(frozen=True)
class EventClusterAssetLink:
    cluster_id: str
    event_id: str
    coin_id: str
    symbol: str
    playbook_type: str
    relationship_type: str
    asset_role: str
    accepted: bool
    link_confidence: float
    classifier_confidence: float
    evidence: tuple[str, ...] = ()
    rejected_reason: str | None = None


@dataclass(frozen=True)
class EventCluster:
    schema_version: str
    cluster_id: str
    external_asset_slug: str
    event_type: str
    event_date_bucket: str
    external_asset: str | None
    event_time: datetime | None
    event_ids: tuple[str, ...]
    raw_ids: tuple[str, ...]
    source_urls: tuple[str, ...]
    evidence: tuple[ClusterEvidence, ...] = ()
    asset_links: tuple[EventClusterAssetLink, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)


def build_event_clusters(result: EventDiscoveryResult) -> tuple[EventCluster, ...]:
    """Build catalyst clusters from normalized events and candidate links."""
    grouped: dict[str, list[NormalizedEvent]] = {}
    for event in result.normalized_events:
        grouped.setdefault(cluster_id_for_event(event), []).append(event)

    candidate_links: dict[str, list[EventClusterAssetLink]] = {}
    for candidate in result.candidates:
        cluster_id = cluster_id_for_event(candidate.event)
        candidate_links.setdefault(cluster_id, []).append(_asset_link_for_candidate(candidate, cluster_id))

    clusters = [
        _cluster_from_events(cluster_id, events, candidate_links.get(cluster_id, ()))
        for cluster_id, events in grouped.items()
    ]
    return tuple(sorted(clusters, key=_cluster_sort_key))


def cluster_id_for_event(event: NormalizedEvent) -> str:
    external_slug = _slug(event.external_asset or event.event_name)
    event_type = _slug(event.event_type or "unknown")
    bucket = event_date_bucket(event)
    return f"{external_slug}|{event_type}|{bucket}"


def event_date_bucket(event: NormalizedEvent) -> str:
    dt = event.event_time or event.first_seen_time
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.date().isoformat()


def format_event_cluster_report(clusters: Iterable[EventCluster]) -> str:
    rows = [
        "=" * 76,
        "EVENT CLUSTER REPORT (research-only; no candidates or alerts created)",
        "=" * 76,
    ]
    clusters = list(clusters)
    rows.append(f"clusters: {len(clusters)}")
    if not clusters:
        rows.append("")
        rows.append("No clusters.")
        return "\n".join(rows)
    rows.append("")
    for cluster in clusters:
        rows.append(
            f"{cluster.cluster_id} · events={len(cluster.event_ids)} · assets={len(cluster.asset_links)}"
        )
        rows.append(
            f"  external={cluster.external_asset or 'unknown'} · type={cluster.event_type} · "
            f"bucket={cluster.event_date_bucket}"
        )
        for link in cluster.asset_links:
            status = "accepted" if link.accepted else "rejected"
            rows.append(
                f"  - {link.symbol}/{link.coin_id} {status} "
                f"playbook={link.playbook_type} role={link.asset_role} rel={link.relationship_type}"
            )
            if link.rejected_reason:
                rows.append(f"    rejected: {link.rejected_reason}")
    return "\n".join(rows).rstrip()


def _cluster_from_events(
    cluster_id: str,
    events: Iterable[NormalizedEvent],
    asset_links: Iterable[EventClusterAssetLink],
) -> EventCluster:
    ordered = sorted(events, key=lambda event: (event.first_seen_time, event.event_id))
    first = ordered[0]
    raw_ids = tuple(sorted({raw_id for event in ordered for raw_id in event.raw_ids}))
    urls = tuple(sorted({url for event in ordered for url in event.source_urls if url}))
    evidence = tuple(
        ClusterEvidence(
            event_id=event.event_id,
            raw_ids=tuple(event.raw_ids),
            source_urls=tuple(event.source_urls),
            event_name=event.event_name,
            source=event.source,
            first_seen_time=event.first_seen_time,
            confidence=event.confidence,
        )
        for event in ordered
    )
    best_time = next((event.event_time for event in ordered if event.event_time is not None), None)
    return EventCluster(
        schema_version=EVENT_GRAPH_SCHEMA_VERSION,
        cluster_id=cluster_id,
        external_asset_slug=_slug(first.external_asset or first.event_name),
        event_type=first.event_type,
        event_date_bucket=event_date_bucket(first),
        external_asset=first.external_asset,
        event_time=best_time,
        event_ids=tuple(event.event_id for event in ordered),
        raw_ids=raw_ids,
        source_urls=urls,
        evidence=evidence,
        asset_links=tuple(sorted(asset_links, key=lambda link: (link.symbol, link.coin_id))),
    )


def _asset_link_for_candidate(
    candidate: DiscoveredEventFadeCandidate,
    cluster_id: str,
) -> EventClusterAssetLink:
    classification = candidate.classification
    playbook = _playbook_from_candidate(candidate)
    accepted = bool(
        classification.is_proxy_narrative
        and not classification.is_direct_beneficiary
        and classification.asset_role in {"proxy_instrument", "proxy_venue"}
    )
    rejected = None if accepted else _rejected_reason(candidate)
    return EventClusterAssetLink(
        cluster_id=cluster_id,
        event_id=candidate.event.event_id,
        coin_id=candidate.asset.coin_id,
        symbol=candidate.asset.symbol,
        playbook_type=playbook,
        relationship_type=classification.relationship_type,
        asset_role=classification.asset_role,
        accepted=accepted,
        link_confidence=candidate.link.link_confidence,
        classifier_confidence=classification.confidence,
        evidence=tuple((*candidate.link.evidence, *classification.evidence)),
        rejected_reason=rejected,
    )


def _playbook_from_candidate(candidate: DiscoveredEventFadeCandidate) -> str:
    classification = candidate.classification
    if classification.is_proxy_narrative and classification.relationship_type == "proxy_exposure":
        return "proxy_fade"
    if classification.is_proxy_narrative:
        return "proxy_attention"
    if classification.is_direct_beneficiary or classification.relationship_type.startswith("direct_"):
        return "direct_event"
    if classification.asset_role == "infrastructure":
        return "infrastructure_mention"
    if candidate.event.event_type == "market_anomaly":
        return "market_anomaly_unknown"
    return "source_noise_control" if classification.asset_role in {"ticker_word_collision", "mentioned_asset"} else "ambiguous_control"


def _rejected_reason(candidate: DiscoveredEventFadeCandidate) -> str:
    classification = candidate.classification
    if classification.is_direct_beneficiary:
        return "direct beneficiary"
    if classification.asset_role in {"ticker_word_collision", "mentioned_asset", "infrastructure"}:
        return classification.asset_role
    if not classification.is_proxy_narrative:
        return "not proxy narrative"
    return "not accepted by graph"


def _cluster_sort_key(cluster: EventCluster) -> tuple[str, str, str]:
    return (cluster.event_date_bucket, cluster.external_asset_slug, cluster.event_type)


def _slug(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "unknown"
