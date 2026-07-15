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
from typing import Any, Iterable, Mapping

from crypto_rsi_scanner.event_core.models import DiscoveredEventFadeCandidate, EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
from crypto_rsi_scanner.event_alpha.radar.resolver import clean_text
import crypto_rsi_scanner.event_alpha.radar.source_independence as event_source_independence

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
    accepted_kind: str = "none"
    accepted_for_playbook: str | None = None
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
    source_count: int = 0
    independent_source_count: int = 0
    independent_corroboration_count: int = 0
    source_domain_count: int = 0
    source_domains: tuple[str, ...] = ()
    source_content_cluster_count: int = 0
    source_independence: Mapping[str, Any] = field(default_factory=dict)
    source_independence_errors: tuple[str, ...] = ()
    source_quality_score: int = 0
    event_time_consensus: int = 0
    accepted_asset_count: int = 0
    rejected_asset_count: int = 0
    cluster_confidence: int = 0
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

    raw_by_id = {raw.raw_id: raw for raw in result.raw_events}
    clusters = [
        _cluster_from_events(cluster_id, events, candidate_links.get(cluster_id, ()), raw_by_id=raw_by_id)
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
        accepted = [link for link in cluster.asset_links if link.accepted]
        rejected = [link for link in cluster.asset_links if not link.accepted]
        rows.append(
            f"{cluster.cluster_id} · events={len(cluster.event_ids)} · assets={len(cluster.asset_links)} "
            f"· cluster_conf={cluster.cluster_confidence}"
        )
        rows.append(
            f"  external={cluster.external_asset or 'unknown'} · type={cluster.event_type} · "
            f"bucket={cluster.event_date_bucket}"
        )
        rows.append(
            f"  sources: raw={cluster.source_count} domains={cluster.source_domain_count} "
            f"independent={cluster.independent_source_count} "
            f"corroborations={cluster.independent_corroboration_count} "
            f"content_clusters={cluster.source_content_cluster_count} "
            f"quality={cluster.source_quality_score} · event_time_consensus={cluster.event_time_consensus}"
        )
        accepted_kinds = _accepted_kind_summary(cluster.asset_links)
        rows.append(
            f"  accepted assets: {len(accepted)} · rejected/noise assets: {len(rejected)}"
            + (f" · accepted_kinds={accepted_kinds}" if accepted_kinds else "")
        )
        if cluster.warnings:
            rows.append("  warnings: " + "; ".join(cluster.warnings))
        for link in accepted:
            rows.append(
                f"  - {link.symbol}/{link.coin_id} accepted "
                f"kind={link.accepted_kind} playbook={link.playbook_type} "
                f"role={link.asset_role} rel={link.relationship_type}"
            )
        for link in rejected:
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
    *,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
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
    links = tuple(sorted(asset_links, key=lambda link: (link.symbol, link.coin_id)))
    accepted_count = sum(1 for link in links if _counts_for_cluster_confidence(link))
    rejected_count = sum(1 for link in links if not link.accepted)
    source_count = len(raw_ids)
    source_rows = [
        _source_independence_row(raw_by_id[raw_id])
        for raw_id in raw_ids
        if raw_id in raw_by_id
    ]
    independence, independence_errors = event_source_independence.assess_source_independence_safe(
        source_rows,
        expected_document_count=len(raw_ids),
    )
    independent_evidence_count = int(independence.get("independent_evidence_count") or 0)
    corroboration_count = int(independence.get("independent_corroboration_count") or 0)
    source_domains = tuple(str(value) for value in independence.get("distinct_origins", ()) if str(value or ""))
    content_cluster_count = int(independence.get("content_cluster_count") or 0)
    source_quality = _source_quality_score(ordered, corroboration_count)
    time_consensus = _event_time_consensus(ordered)
    confidence = _cluster_confidence(
        source_quality=source_quality,
        independent_source_count=corroboration_count,
        event_time_consensus=time_consensus,
        accepted_asset_count=accepted_count,
        rejected_asset_count=rejected_count,
    )
    warnings = tuple(dict.fromkeys((*_cluster_warnings(
        independent_source_count=corroboration_count,
        event_time_consensus=time_consensus,
        accepted_asset_count=accepted_count,
    ), *independence_errors)))
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
        source_count=source_count,
        independent_source_count=independent_evidence_count,
        independent_corroboration_count=corroboration_count,
        source_domain_count=len(source_domains),
        source_domains=source_domains,
        source_content_cluster_count=content_cluster_count,
        source_independence=independence,
        source_independence_errors=independence_errors,
        source_quality_score=source_quality,
        event_time_consensus=time_consensus,
        accepted_asset_count=accepted_count,
        rejected_asset_count=rejected_count,
        cluster_confidence=confidence,
        evidence=evidence,
        asset_links=links,
        warnings=warnings,
    )


def _source_independence_row(raw: RawDiscoveredEvent) -> dict[str, Any]:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    provenance = payload.get("provenance") if isinstance(payload.get("provenance"), Mapping) else {}
    source_class = payload.get("source_class") or provenance.get("source_class")
    return {
        "source_id": raw.raw_id,
        "source_url": raw.source_url,
        "title": raw.title,
        "body": raw.body,
        "provider": raw.provider,
        "source_class": source_class,
        "published_at": raw.published_at,
        "fetched_at": raw.fetched_at,
    }


def _asset_link_for_candidate(
    candidate: DiscoveredEventFadeCandidate,
    cluster_id: str,
) -> EventClusterAssetLink:
    classification = candidate.classification
    playbook = _playbook_from_candidate(candidate)
    accepted_kind, accepted_for_playbook = _accepted_link_kind(candidate, playbook)
    accepted = accepted_kind != "none"
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
        accepted_kind=accepted_kind,
        accepted_for_playbook=accepted_for_playbook,
        evidence=tuple((*candidate.link.evidence, *classification.evidence)),
        rejected_reason=rejected,
    )


def _accepted_link_kind(
    candidate: DiscoveredEventFadeCandidate,
    playbook: str,
) -> tuple[str, str | None]:
    classification = candidate.classification
    event_type = candidate.event.event_type
    relationship = classification.relationship_type
    role = classification.asset_role
    if (
        classification.is_proxy_narrative
        and not classification.is_direct_beneficiary
        and role in {"proxy_instrument", "proxy_venue"}
        and relationship in {"proxy_exposure", "proxy_attention"}
    ):
        return "proxy", playbook
    if event_type == "perp_listing" or "perp" in relationship or "futures" in relationship:
        if classification.is_direct_beneficiary or relationship.startswith("direct_"):
            return "derivatives", "perp_listing_squeeze"
    if event_type in {"token_unlock", "airdrop", "tge"} or relationship in {"direct_unlock", "direct_supply_event"}:
        return "supply", "unlock_supply_pressure"
    if (
        classification.is_direct_beneficiary
        or relationship in {"direct_listing", "direct_protocol_event"}
        or event_type in {"exchange_listing", "mainnet_launch", "governance", "protocol_upgrade"}
    ):
        return "direct", playbook
    if role == "infrastructure" or relationship == "infrastructure_provider":
        return "infrastructure", "infrastructure_mention"
    return "none", None


def _counts_for_cluster_confidence(link: EventClusterAssetLink) -> bool:
    return link.accepted_kind in {"proxy", "direct", "supply", "derivatives"}


def _accepted_kind_summary(links: Iterable[EventClusterAssetLink]) -> str:
    counts: dict[str, int] = {}
    for link in links:
        if link.accepted_kind == "none":
            continue
        counts[link.accepted_kind] = counts.get(link.accepted_kind, 0) + 1
    return ", ".join(f"{kind}:{count}" for kind, count in sorted(counts.items()))


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


def _source_quality_score(events: Iterable[NormalizedEvent], independent_corroboration_count: int) -> int:
    values = [max(0.0, min(1.0, float(event.confidence))) for event in events]
    average = (sum(values) / len(values)) * 100 if values else 0.0
    diversity_bonus = min(15, max(0, independent_corroboration_count) * 5)
    return _clamp(average + diversity_bonus)


def _event_time_consensus(events: Iterable[NormalizedEvent]) -> int:
    times = [event.event_time for event in events if event.event_time is not None]
    if not times:
        return 0
    iso_times = {_as_utc(ts).replace(microsecond=0).isoformat() for ts in times}
    if len(iso_times) == 1:
        return 100
    dates = {_as_utc(ts).date().isoformat() for ts in times}
    return 75 if len(dates) == 1 else 35


def _cluster_confidence(
    *,
    source_quality: int,
    independent_source_count: int,
    event_time_consensus: int,
    accepted_asset_count: int,
    rejected_asset_count: int,
) -> int:
    diversity = min(100, 45 + max(0, independent_source_count) * 25)
    accepted = 70 if accepted_asset_count else 25
    noise_penalty = min(20, max(0, rejected_asset_count - accepted_asset_count) * 5)
    return _clamp(
        source_quality * 0.35
        + diversity * 0.20
        + event_time_consensus * 0.25
        + accepted * 0.20
        - noise_penalty
    )


def _cluster_warnings(
    *,
    independent_source_count: int,
    event_time_consensus: int,
    accepted_asset_count: int,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if independent_source_count < 1:
        warnings.append("no independent corroboration")
    if event_time_consensus < 75:
        warnings.append("weak event-time consensus")
    if accepted_asset_count == 0:
        warnings.append("no accepted asset links")
    return tuple(warnings)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(round(max(lo, min(hi, float(value)))))


def _slug(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "unknown"
