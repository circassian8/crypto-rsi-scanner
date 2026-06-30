"""Source-pack coverage dashboard for Event Alpha research artifacts.

This module is read-only. It summarizes configured provider coverage,
provider-health state, and evidence-acquisition outcomes by source pack so the
operator can see why strict Event Alpha gates stayed quiet without relaxing
those gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from . import event_provider_health, event_provider_status, event_source_packs


SOURCE_COVERAGE_PACK_ORDER = (
    "proxy_preipo_rwa_pack",
    "strategic_investment_pack",
    "security_shock_pack",
    "listing_liquidity_pack",
    "fan_sports_pack",
    "market_anomaly_pack",
    "unlock_supply_pack",
    "perp_listing_squeeze_pack",
)

_READY_PROVIDER_ALIASES = {
    "binance_announcements": "binance_announcements",
    "bybit_announcements": "bybit_announcements",
    "coinmarketcal_calendar": "coinmarketcal",
    "tokenomist_unlocks": "tokenomist",
    "tokenomist_supply": "tokenomist",
    "cryptopanic_news": "cryptopanic",
    "gdelt_news": "gdelt",
    "project_blog_rss": "project_blog_rss",
    "sports_fixtures": "sports_fixtures",
    "prediction_market_events": "polymarket",
    "coinalyze_derivatives": "coinalyze",
    "coingecko_universe": "coingecko",
}

_HEALTH_PROVIDER_ALIASES = {
    "binance": "binance_announcements",
    "bybit": "bybit_announcements",
    "cryptopanic": "cryptopanic",
    "gdelt": "gdelt",
    "rss": "project_blog_rss",
    "project_blog_rss": "project_blog_rss",
    "polymarket": "polymarket",
    "coinalyze": "coinalyze",
    "coingecko": "coingecko",
    "tokenomist": "tokenomist",
    "coinmarketcal": "coinmarketcal",
    "sports_fixtures": "sports_fixtures",
    "defillama": "defillama",
}

_HIGH_SPECIFICITY_PROVIDERS = {
    "binance_announcements",
    "bybit_announcements",
    "coinmarketcal",
    "tokenomist",
    "cryptopanic",
    "project_blog_rss",
    "coinalyze",
    "coingecko",
    "defillama",
}

_BROAD_CONTEXT_PROVIDERS = {"gdelt", "polymarket"}

_COVERAGE_GAP_STATUSES = {
    "skipped_budget",
    "no_results",
    "rejected_results_only",
    "provider_unavailable",
    "provider_backoff",
    "failed_soft",
    "skipped_config",
}

_COVERAGE_GAP_REASONS = {
    "live_confirmation_missing",
    "evidence_acquisition_not_confirming",
    "source_pack_confirmation_missing",
    "sector_only_digest_not_allowed",
    "rejected_results_only_not_confirmation",
    "skipped_budget_not_confirmation",
    "no_results_not_confirmation",
    "provider_unavailable_not_confirmation",
    "source_pack_confirmation_missing",
}


@dataclass(frozen=True)
class EventAlphaSourceCoveragePack:
    source_pack: str
    configured_providers: tuple[str, ...]
    missing_providers: tuple[str, ...]
    healthy_providers: tuple[str, ...]
    unknown_or_unobserved_providers: tuple[str, ...]
    degraded_or_backoff_providers: tuple[str, ...]
    provider_coverage_status: str
    provider_role_statuses: tuple[str, ...]
    evidence_absence_meaningful: bool
    coverage_gap_reason: str | None = None
    providers_missing_for_confirmation: tuple[str, ...] = ()
    providers_degraded_for_confirmation: tuple[str, ...] = ()
    candidates_blocked_by_coverage_gap: int = 0
    accepted_evidence_count: int = 0
    rejected_only_count: int = 0
    skipped_budget_count: int = 0
    provider_unavailable_count: int = 0
    article_quality_counts: tuple[str, ...] = ()
    recommended_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_pack": self.source_pack,
            "configured_providers": list(self.configured_providers),
            "missing_providers": list(self.missing_providers),
            "healthy_providers": list(self.healthy_providers),
            "unknown_or_unobserved_providers": list(self.unknown_or_unobserved_providers),
            "degraded_or_backoff_providers": list(self.degraded_or_backoff_providers),
            "provider_coverage_status": self.provider_coverage_status,
            "source_pack_coverage_status": self.provider_coverage_status,
            "provider_role_statuses": list(self.provider_role_statuses),
            "evidence_absence_meaningful": self.evidence_absence_meaningful,
            "coverage_gap_reason": self.coverage_gap_reason,
            "source_coverage_gap_reason": self.coverage_gap_reason,
            "providers_missing_for_confirmation": list(self.providers_missing_for_confirmation),
            "providers_degraded_for_confirmation": list(self.providers_degraded_for_confirmation),
            "candidates_blocked_by_coverage_gap": self.candidates_blocked_by_coverage_gap,
            "accepted_evidence_count": self.accepted_evidence_count,
            "rejected_only_count": self.rejected_only_count,
            "skipped_budget_count": self.skipped_budget_count,
            "provider_unavailable_count": self.provider_unavailable_count,
            "article_quality_counts": list(self.article_quality_counts),
            "recommended_actions": list(self.recommended_actions),
        }


@dataclass(frozen=True)
class EventAlphaSourceCoverageReport:
    profile: str
    artifact_namespace: str
    packs: tuple[EventAlphaSourceCoveragePack, ...]
    provider_health_rows: int = 0
    acquisition_rows: int = 0
    core_rows: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "artifact_namespace": self.artifact_namespace,
            "provider_health_rows": self.provider_health_rows,
            "acquisition_rows": self.acquisition_rows,
            "core_rows": self.core_rows,
            "packs": [pack.to_dict() for pack in self.packs],
        }


def build_source_coverage_report(
    *,
    provider_status_report: event_provider_status.EventDiscoveryProviderStatus,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    evidence_acquisition_rows: Iterable[Mapping[str, Any]] = (),
    core_opportunity_rows: Iterable[Mapping[str, Any]] = (),
    profile: str = "default",
    artifact_namespace: str = "default",
    now: datetime | None = None,
) -> EventAlphaSourceCoverageReport:
    """Build source-pack coverage from readiness, health, and artifact rows."""
    observed = now or datetime.now(timezone.utc)
    health_by_provider = _health_by_provider(provider_health_rows or {}, now=observed)
    configured = _configured_providers(provider_status_report, health_by_provider)
    acquisition = [dict(row) for row in evidence_acquisition_rows if isinstance(row, Mapping)]
    core_rows = [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)]

    packs: list[EventAlphaSourceCoveragePack] = []
    for pack_name in SOURCE_COVERAGE_PACK_ORDER:
        pack = event_source_packs.get_source_pack(pack_name)
        preferred = tuple(dict.fromkeys(pack.preferred_providers))
        configured_for_pack = tuple(provider for provider in preferred if provider in configured or provider in health_by_provider)
        missing = tuple(provider for provider in preferred if provider not in configured_for_pack)
        healthy = tuple(
            provider for provider in configured_for_pack
            if _provider_effective_status(provider, health_by_provider) == "healthy"
        )
        unknown = tuple(
            provider for provider in configured_for_pack
            if _provider_effective_status(provider, health_by_provider) in {"unknown", "not_observed"}
        )
        degraded = tuple(
            provider for provider in configured_for_pack
            if _provider_effective_status(provider, health_by_provider) in {"degraded", "backoff", "unavailable"}
        )
        pack_rows = [row for row in acquisition if str(row.get("source_pack") or "") == pack_name]
        accepted = sum(_accepted_count(row) for row in pack_rows)
        rejected_only = sum(1 for row in pack_rows if _status(row) == "rejected_results_only")
        skipped_budget = sum(1 for row in pack_rows if _status(row) == "skipped_budget")
        unavailable = sum(1 for row in pack_rows if _status(row) in {"provider_unavailable", "provider_backoff", "failed_soft", "skipped_config"})
        article_quality_counts = _article_quality_counts(pack_rows)
        blocked = _coverage_blocked_count(pack_name, pack_rows=pack_rows, core_rows=core_rows)
        absence_meaningful = _evidence_absence_meaningful(pack_name, healthy, degraded)
        coverage_status = _pack_coverage_status(
            configured_for_pack=configured_for_pack,
            missing=missing,
            healthy=healthy,
            unknown=unknown,
            degraded=degraded,
            provider_unavailable_count=unavailable,
        )
        coverage_gap_reason = _coverage_gap_reason(
            coverage_status=coverage_status,
            missing=missing,
            unknown=unknown,
            degraded=degraded,
            blocked=blocked,
            skipped_budget=skipped_budget,
            rejected_only=rejected_only,
            provider_unavailable=unavailable,
        )
        role_statuses = _provider_role_statuses_for_pack(
            provider_health_rows or {},
            preferred=preferred,
            unknown=unknown,
            now=observed,
        )
        recommended_actions = _pack_recommended_actions(
            pack_name,
            missing=missing,
            degraded=degraded,
            blocked=blocked,
            skipped_budget=skipped_budget,
            rejected_only=rejected_only,
            provider_unavailable=unavailable,
        )
        packs.append(
            EventAlphaSourceCoveragePack(
                source_pack=pack_name,
                configured_providers=_sorted_tuple(configured_for_pack),
                missing_providers=_sorted_tuple(missing),
                healthy_providers=_sorted_tuple(healthy),
                unknown_or_unobserved_providers=_sorted_tuple(unknown),
                degraded_or_backoff_providers=_sorted_tuple(degraded),
                provider_coverage_status=coverage_status,
                provider_role_statuses=role_statuses,
                evidence_absence_meaningful=absence_meaningful,
                coverage_gap_reason=coverage_gap_reason,
                providers_missing_for_confirmation=_sorted_tuple(missing),
                providers_degraded_for_confirmation=_sorted_tuple(degraded),
                candidates_blocked_by_coverage_gap=blocked,
                accepted_evidence_count=accepted,
                rejected_only_count=rejected_only,
                skipped_budget_count=skipped_budget,
                provider_unavailable_count=unavailable,
                article_quality_counts=article_quality_counts,
                recommended_actions=recommended_actions,
            )
        )
    return EventAlphaSourceCoverageReport(
        profile=profile,
        artifact_namespace=artifact_namespace,
        packs=tuple(packs),
        provider_health_rows=len(provider_health_rows or {}),
        acquisition_rows=len(acquisition),
        core_rows=len(core_rows),
    )


def format_source_coverage_report(report: EventAlphaSourceCoverageReport) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA SOURCE COVERAGE (research-only)",
        "=" * 76,
        f"profile: {report.profile}",
        f"artifact_namespace: {report.artifact_namespace}",
        f"provider_health_rows: {report.provider_health_rows}",
        f"evidence_acquisition_rows: {report.acquisition_rows}",
        f"core_opportunity_rows: {report.core_rows}",
        "note: configured providers with no health row are unknown/not observed; do not infer they are healthy.",
        "",
        "Source-pack coverage:",
    ]
    for pack in report.packs:
        lines.extend(
            [
                f"- {pack.source_pack}",
                f"  configured providers: {_join(pack.configured_providers)}",
                f"  missing providers: {_join(pack.missing_providers)}",
                f"  healthy providers: {_join(pack.healthy_providers)}",
                f"  unknown/not observed providers: {_join(pack.unknown_or_unobserved_providers)}",
                f"  degraded/backoff providers: {_join(pack.degraded_or_backoff_providers)}",
                f"  provider coverage status: {pack.provider_coverage_status}",
                f"  provider role health: {_join(pack.provider_role_statuses)}",
                f"  evidence absence meaningful: {str(pack.evidence_absence_meaningful).lower()}",
                f"  coverage gap reason: {pack.coverage_gap_reason or 'none'}",
                f"  providers missing for confirmation: {_join(pack.providers_missing_for_confirmation)}",
                f"  providers degraded for confirmation: {_join(pack.providers_degraded_for_confirmation)}",
                (
                    "  acquisition outcomes: "
                    f"accepted={pack.accepted_evidence_count} "
                    f"rejected_only={pack.rejected_only_count} "
                    f"skipped_budget={pack.skipped_budget_count} "
                    f"provider_unavailable={pack.provider_unavailable_count}"
                ),
                f"  article quality: {_join(pack.article_quality_counts)}",
                f"  candidates blocked by coverage gap: {pack.candidates_blocked_by_coverage_gap}",
                f"  recommended actions: {_join(pack.recommended_actions)}",
            ]
        )
    recs = _recommendation_lines(report)
    lines.extend(["", "Most useful next data source:"])
    lines.extend(recs)
    lines.append("")
    lines.append("No alerts, sends, trades, paper rows, normal RSI rows, or triggers were changed.")
    return "\n".join(lines)


def _configured_providers(
    provider_status_report: event_provider_status.EventDiscoveryProviderStatus,
    health_by_provider: Mapping[str, str],
) -> set[str]:
    out: set[str] = set(health_by_provider)
    for item in (*provider_status_report.sources, *provider_status_report.enrichment):
        alias = _READY_PROVIDER_ALIASES.get(item.name)
        if alias and item.ready:
            out.add(alias)
    return out


def _health_by_provider(rows: Mapping[str, Mapping[str, Any]], *, now: datetime) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, row in rows.items():
        alias = _provider_alias(row, fallback_key=str(key))
        if not alias:
            continue
        status = event_provider_health.provider_health_status(row, now=now)
        if status == "backoff":
            out[alias] = "backoff"
        elif status == "degraded":
            out.setdefault(alias, "degraded")
        else:
            out.setdefault(alias, "healthy")
    return out


def _provider_alias(row: Mapping[str, Any], *, fallback_key: str) -> str:
    candidates = (
        row.get("provider_service"),
        row.get("provider"),
        row.get("provider_key"),
        fallback_key,
    )
    joined = " ".join(str(item or "").casefold() for item in candidates)
    for token, alias in _HEALTH_PROVIDER_ALIASES.items():
        if token in joined:
            return alias
    return ""


def _provider_effective_status(provider: str, health_by_provider: Mapping[str, str]) -> str:
    return str(health_by_provider.get(provider) or "unknown")


def _provider_role_statuses_for_pack(
    rows: Mapping[str, Mapping[str, Any]],
    *,
    preferred: Iterable[str],
    unknown: Iterable[str] = (),
    now: datetime,
) -> tuple[str, ...]:
    preferred_set = set(preferred)
    out: list[str] = []
    for key, row in sorted(rows.items()):
        alias = _provider_alias(row, fallback_key=str(key))
        if alias not in preferred_set:
            continue
        role = str(row.get("provider_role") or row.get("provider_kind") or "unclassified").strip() or "unclassified"
        status = event_provider_health.provider_health_status(row, now=now)
        out.append(f"{alias}:{role}={status}")
    for alias in sorted(set(unknown) & preferred_set):
        out.append(f"{alias}:not_observed=unknown")
    return tuple(dict.fromkeys(out))


def _status(row: Mapping[str, Any]) -> str:
    return str(row.get("status") or row.get("evidence_acquisition_status") or "").strip()


def _accepted_count(row: Mapping[str, Any]) -> int:
    for key in ("accepted_evidence_count", "evidence_acquisition_accepted_count"):
        try:
            if row.get(key) not in (None, ""):
                return max(0, int(row.get(key) or 0))
        except (TypeError, ValueError):
            pass
    accepted = row.get("accepted_evidence")
    if isinstance(accepted, list):
        return len(accepted)
    if isinstance(accepted, tuple):
        return len(accepted)
    return 1 if accepted else 0


def _article_quality_counts(rows: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    for row in rows:
        for evidence in (*_evidence_items(row.get("accepted_evidence")), *_evidence_items(row.get("rejected_evidence_samples") or row.get("rejected_evidence"))):
            enrichment = evidence.get("source_enrichment") if isinstance(evidence.get("source_enrichment"), Mapping) else {}
            status = str(enrichment.get("article_quality_status") or "").strip()
            if status:
                counts[status] = counts.get(status, 0) + 1
    return tuple(f"{key}={value}" for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _evidence_items(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _coverage_blocked_count(
    pack_name: str,
    *,
    pack_rows: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
) -> int:
    blocked = 0
    for row in pack_rows:
        if _status(row) in _COVERAGE_GAP_STATUSES and _accepted_count(row) <= 0:
            blocked += 1
    for row in core_rows:
        if str(row.get("source_pack") or row.get("evidence_acquisition_source_pack") or "") != pack_name:
            continue
        reason_values = {
            str(row.get("live_confirmation_reason") or ""),
            str(row.get("source_pack_confirmation_status") or ""),
            str(row.get("source_coverage_gap") or ""),
            str(row.get("quality_gate_block_reason") or ""),
            str(row.get("why_not_promoted") or ""),
        }
        if reason_values & _COVERAGE_GAP_REASONS:
            blocked += 1
    return blocked


def _evidence_absence_meaningful(
    pack_name: str,
    healthy: Iterable[str],
    degraded: Iterable[str],
) -> bool:
    healthy_set = set(healthy)
    degraded_set = set(degraded)
    if not healthy_set:
        return False
    if healthy_set <= _BROAD_CONTEXT_PROVIDERS and degraded_set:
        return False
    pack = event_source_packs.get_source_pack(pack_name)
    preferred = set(pack.preferred_providers)
    return bool((healthy_set & preferred) & _HIGH_SPECIFICITY_PROVIDERS)


def _pack_coverage_status(
    *,
    configured_for_pack: Iterable[str],
    missing: Iterable[str],
    healthy: Iterable[str],
    unknown: Iterable[str],
    degraded: Iterable[str],
    provider_unavailable_count: int,
) -> str:
    configured_set = set(configured_for_pack)
    missing_set = set(missing)
    healthy_set = set(healthy)
    unknown_set = set(unknown)
    degraded_set = set(degraded)
    if provider_unavailable_count and not healthy_set:
        return "unavailable"
    if not configured_set:
        return "not_configured"
    if unknown_set and not healthy_set and not degraded_set:
        return "unknown"
    if degraded_set and not healthy_set:
        return "degraded"
    if healthy_set and not missing_set and not degraded_set and not provider_unavailable_count:
        return "partial" if unknown_set else "complete"
    if healthy_set:
        return "partial"
    return "unknown" if unknown_set else "unavailable"


def _coverage_gap_reason(
    *,
    coverage_status: str,
    missing: Iterable[str],
    unknown: Iterable[str],
    degraded: Iterable[str],
    blocked: int,
    skipped_budget: int,
    rejected_only: int,
    provider_unavailable: int,
) -> str | None:
    reasons: list[str] = []
    if coverage_status in {"not_configured", "degraded", "unavailable", "partial", "unknown"}:
        reasons.append(f"source_pack_coverage_{coverage_status}")
    missing_values = _sorted_tuple(missing)
    unknown_values = _sorted_tuple(unknown)
    degraded_values = _sorted_tuple(degraded)
    if missing_values:
        reasons.append("missing:" + ",".join(missing_values))
    if unknown_values:
        reasons.append("not_observed:" + ",".join(unknown_values))
    if degraded_values:
        reasons.append("degraded:" + ",".join(degraded_values))
    if skipped_budget:
        reasons.append("skipped_budget_not_confirmation")
    if rejected_only:
        reasons.append("rejected_results_only_not_confirmation")
    if provider_unavailable:
        reasons.append("provider_unavailable_not_confirmation")
    if blocked:
        reasons.append("candidates_blocked_by_coverage_gap")
    return ";".join(reasons) if reasons else None


def _recommendation_lines(report: EventAlphaSourceCoverageReport) -> list[str]:
    provider_missing_counts: dict[str, int] = {}
    provider_gap_counts: dict[str, int] = {}
    for pack in report.packs:
        gap_weight = max(1, pack.candidates_blocked_by_coverage_gap)
        for provider in pack.missing_providers:
            provider_missing_counts[provider] = provider_missing_counts.get(provider, 0) + gap_weight
        for provider in pack.degraded_or_backoff_providers:
            provider_gap_counts[provider] = provider_gap_counts.get(provider, 0) + gap_weight
    if not provider_missing_counts and not provider_gap_counts:
        return ["- coverage is currently sufficient for the tracked source packs"]
    combined = {
        provider: provider_missing_counts.get(provider, 0) + provider_gap_counts.get(provider, 0)
        for provider in set(provider_missing_counts) | set(provider_gap_counts)
    }
    top = sorted(combined, key=lambda item: (-combined[item], item))[:5]
    lines: list[str] = []
    for provider in top:
        reason = []
        if provider_missing_counts.get(provider):
            reason.append(f"missing_in_packs={provider_missing_counts[provider]}")
        if provider_gap_counts.get(provider):
            reason.append(f"degraded_or_backoff_in_packs={provider_gap_counts[provider]}")
        lines.append(f"- {provider}: " + ", ".join(reason))
    return lines


def _pack_recommended_actions(
    pack_name: str,
    *,
    missing: Iterable[str],
    degraded: Iterable[str],
    blocked: int,
    skipped_budget: int,
    rejected_only: int,
    provider_unavailable: int,
) -> tuple[str, ...]:
    actions: list[str] = []
    missing_set = set(missing)
    degraded_set = set(degraded)
    if blocked or missing_set or degraded_set:
        for provider in sorted(missing_set):
            actions.append(_provider_setup_action(provider, status="missing"))
        for provider in sorted(degraded_set):
            actions.append(_provider_setup_action(provider, status="degraded"))
    if skipped_budget:
        actions.append("raise evidence-acquisition query/candidate budget for this source pack")
    if rejected_only:
        actions.append("inspect rejected evidence samples and add stricter query terms before trusting absence")
    if provider_unavailable:
        actions.append("run provider health report/reset before treating missing evidence as meaningful")
    if pack_name == "market_anomaly_pack" and "defillama" in missing_set:
        actions.append("add or enable DefiLlama-style protocol metrics before relying on market-anomaly confirmation")
    return tuple(dict.fromkeys(action for action in actions if action))


def _provider_setup_action(provider: str, *, status: str) -> str:
    prefix = "configure" if status == "missing" else "restore"
    guidance = {
        "cryptopanic": "CryptoPanic token/news coverage with CRYPTOPANIC_API_KEY",
        "gdelt": "GDELT broad-news coverage and provider backoff health",
        "project_blog_rss": "project/blog RSS feeds; quarantine feed-level 403s instead of the whole RSS provider",
        "binance_announcements": "official Binance announcement coverage for listing/perp events",
        "bybit_announcements": "official Bybit announcement coverage for listing/perp events",
        "coinmarketcal": "structured event calendar coverage",
        "tokenomist": "Tokenomist unlock/supply coverage",
        "sports_fixtures": "sports fixture coverage for fan-token packs",
        "polymarket": "Polymarket context coverage for external catalysts",
        "coinalyze": "Coinalyze derivatives/OI/funding coverage",
        "coingecko": "CoinGecko market/universe coverage",
        "defillama": "DefiLlama protocol TVL/revenue/context coverage",
        "etherscan": "Etherscan token-flow/supply coverage",
        "arkham": "Arkham labeled-wallet coverage",
        "dune": "Dune curated on-chain query coverage",
        "okx_announcements": "OKX official announcement coverage",
        "coinbase": "Coinbase official listing coverage",
    }
    detail = guidance.get(provider, f"{provider} coverage")
    return f"{prefix} {detail}"


def _sorted_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(str(value) for value in values if str(value))))


def _join(values: Iterable[str]) -> str:
    items = _sorted_tuple(values)
    return ", ".join(items) if items else "none"
