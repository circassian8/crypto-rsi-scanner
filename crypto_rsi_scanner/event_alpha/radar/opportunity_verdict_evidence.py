"""Evidence-semantics predicates for opportunity verdict policy."""

from __future__ import annotations

from typing import Any, Mapping

from .opportunity_verdict_values import _lower_text_blob, _lower_values, _score


def _narrative_source_pack(data: Mapping[str, Any]) -> bool:
    if str(data.get("source_pack") or "").strip().casefold() in {
        "fan_sports_pack",
        "proxy_preipo_rwa_pack",
        "political_meme_pack",
    }:
        return True
    return _has_narrative_or_proxy_semantics(data)


def _has_narrative_or_proxy_semantics(data: Mapping[str, Any]) -> bool:
    values = _lower_values(
        data,
        "supporting_categories",
        "supporting_impact_paths",
        "impact_category",
        "impact_path_type",
        "primary_impact_path",
        "impact_path_reason",
        "playbook_type",
        "effective_playbook_type",
        "latest_playbook_type",
        "relationship_type",
        "candidate_role",
    )
    narrative_tokens = {
        "sports_fan_proxy",
        "fan_sports_proxy",
        "fan_token_attention",
        "fan_token_event",
        "fan_token",
        "sports_proxy",
        "proxy_attention",
        "proxy_exposure",
        "proxy_instrument",
        "proxy_venue",
        "venue_value_capture",
        "rwa_preipo_proxy",
        "rwa_preipo",
        "preipo_proxy",
        "pre_ipo_proxy",
        "tokenized_stock_venue",
        "political_meme",
        "political_meme_proxy",
        "meme_attention",
    }
    if values.intersection(narrative_tokens):
        return True
    text = _lower_text_blob(
        data,
        "canonical_incident_name",
        "incident_canonical_name",
        "latest_event_name",
        "event_name",
        "latest_source_title",
        "source_title",
        "why_opportunity_visible",
        "final_verdict_reason",
    )
    return any(
        term in text
        for term in (
            "fan token",
            "world cup",
            "champions league",
            "proxy narrative",
            "pre-ipo",
            "pre ipo",
            "tokenized stock",
            "synthetic exposure",
            "political meme",
            "election meme",
        )
    )


def _has_official_or_structured_evidence(data: Mapping[str, Any]) -> bool:
    source_classes = _lower_values(data, "source_class", "source_classes")
    reason_codes = _lower_values(
        data,
        "accepted_evidence_reason_codes",
        "accepted_reason_codes",
        "source_registry_reasons",
        "reason_codes",
    )
    provider_counts = {
        str(key or "").strip().casefold()
        for key in (
            data.get("accepted_provider_counts").keys()
            if isinstance(data.get("accepted_provider_counts"), Mapping)
            else ()
        )
    }
    official_or_structured = {
        "official_project",
        "official_exchange",
        "structured_calendar",
        "structured_unlock",
        "exchange_announcement",
    }
    if source_classes.intersection(official_or_structured):
        return True
    if provider_counts.intersection({"tokenomist", "coinmarketcal", "binance_announcements", "bybit_announcements"}):
        return True
    return bool(
        reason_codes.intersection(
            {
                "official_project_source",
                "official_exchange_announcement",
                "official_exchange_identity_match",
                "structured_unlock_evidence",
                "structured_calendar_evidence",
                "tokenomist_unlock_match",
                "unlock_schedule_match",
                "direct_token_unlock_fact",
            }
        )
    )


def _cryptopanic_tag_only_cannot_confirm_direct_path(data: Mapping[str, Any]) -> bool:
    source_classes = _lower_values(data, "source_class", "source_classes")
    reason_codes = _lower_values(
        data,
        "accepted_evidence_reason_codes",
        "accepted_reason_codes",
        "source_registry_reasons",
        "reason_codes",
    )
    cryptopanic_tagged = "cryptopanic_tagged" in source_classes or "cryptopanic_currency_tag_match" in reason_codes
    if not cryptopanic_tagged:
        return False
    if _has_narrative_or_proxy_semantics(data):
        return True
    impact_path = str(data.get("impact_path_type") or data.get("primary_impact_path") or "").strip().casefold()
    if impact_path == "unlock_supply_event" and not _has_official_or_structured_evidence(data):
        return True
    return False


def _has_fresh_market_confirmation(data: Mapping[str, Any]) -> bool:
    market_score = _score(
        data.get("market_confirmation_score"),
        data.get("market_confirmation_after"),
        data.get("market_move_volume"),
    )
    market_level = str(
        data.get("market_confirmation_level")
        or data.get("market_confirmation")
        or data.get("market_reaction_confirmation")
        or ""
    ).strip().casefold()
    freshness = str(
        data.get("market_context_freshness_status")
        or data.get("market_data_freshness")
        or data.get("market_freshness_status")
        or ""
    ).strip().casefold()
    fresh_context = freshness in {"fresh", "fixture_allowed_stale"}
    return fresh_context and (market_score >= 40 or market_level in {"moderate", "strong", "confirmed", "fresh"})


def _strategic_broad_asset_context_only(data: Mapping[str, Any]) -> bool:
    """Return true for broad-asset treasury/valuation context, not token impact.

    A crypto-news article about Strategy/MSTR, ETF/company equity valuation,
    market structure, or treasury discounts can mention BTC/ETH/SOL directly
    without proving that the asset itself is the affected subject. Accepted
    source-pack evidence or fresh market confirmation can still validate those
    rows through the normal live-confirmation paths.
    """
    symbol = str(data.get("symbol") or data.get("validated_symbol") or "").strip().upper()
    coin_id = str(data.get("coin_id") or data.get("validated_coin_id") or "").strip().casefold()
    broad_asset = symbol in {"BTC", "ETH", "SOL"} or coin_id in {"bitcoin", "ethereum", "solana"}
    if not broad_asset:
        return False
    impact_path = str(data.get("impact_path_type") or data.get("primary_impact_path") or "").strip().casefold()
    impact_reason = str(data.get("impact_path_reason") or data.get("primary_impact_path_reason") or "").strip().casefold()
    event_archetype = str(data.get("event_archetype") or data.get("main_frame_type") or "").strip().casefold()
    strategic = any(
        token in {impact_path, impact_reason, event_archetype}
        for token in {
            "strategic_investment",
            "strategic_investment_or_valuation",
            "valuation_event",
            "treasury_context",
            "external_equity_proxy_context",
        }
    )
    if not strategic:
        return False
    text = " ".join(
        str(value or "")
        for value in (
            data.get("canonical_incident_name"),
            data.get("incident_canonical_name"),
            data.get("latest_event_name"),
            data.get("event_name"),
            data.get("latest_source_title"),
            data.get("source_title"),
            data.get("latest_source"),
            data.get("source"),
            data.get("why_opportunity_visible"),
            data.get("final_verdict_reason"),
        )
    ).casefold()
    context_terms = (
        "strategy",
        "microstrategy",
        "mstr",
        "treasury",
        "holdings",
        "valuation",
        "discount",
        "premium",
        "public company",
        "equity valuation",
        "shares",
        "stock",
        "cme",
        "sec",
        "cftc",
        "market structure",
    )
    if not any(term in text for term in context_terms):
        return False
    direct_terms = (
        "protocol upgrade",
        "network upgrade",
        "bitcoin etf approved",
        "ethereum etf approved",
        "solana etf approved",
        "spot bitcoin etf",
        "spot ethereum etf",
        "spot solana etf",
        "listing",
        "unlock",
        "exploit",
    )
    return not any(term in text for term in direct_terms)


def _is_sector_only_row(data: Mapping[str, Any]) -> bool:
    symbol = str(data.get("symbol") or data.get("validated_symbol") or "").strip().upper()
    coin_id = str(data.get("coin_id") or data.get("validated_coin_id") or "").strip().casefold()
    if symbol == "SECTOR":
        return True
    return coin_id in {
        "sports_fan_proxy",
        "political_meme_proxy",
        "ai_ipo_proxy",
        "rwa_preipo_proxy",
        "market_anomaly",
        "sector",
    }
