"""Event discovery validation sample exporters."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .... import event_fade
import crypto_rsi_scanner.event_alpha.radar.anomaly_scanner as event_anomaly_scanner
import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
import crypto_rsi_scanner.event_alpha.providers.provider_health as event_provider_health
from ....derivatives_providers.coinalyze import CoinalyzeDerivativesProvider
from ..classification import classify_event_asset
from crypto_rsi_scanner.event_core.models import (
    DiscoveredAsset,
    DiscoveredEventFadeCandidate,
    EventAssetLink,
    EventClassification,
    EventDiscoveryResult,
    NormalizedEvent,
    RawDiscoveredEvent,
)
from ....event_providers.binance_announcements import BinanceAnnouncementProvider
from ....event_providers.bybit_announcements import BybitAnnouncementProvider
from ....event_providers.coinmarketcal import CoinMarketCalProvider
from ....event_providers.coingecko_universe import CoinGeckoUniverseProvider
from ....event_providers.cryptopanic import CryptoPanicProvider
from ....event_providers.external_ipo import ExternalIpoProvider
from ....event_providers.gdelt import DEFAULT_GDELT_QUERY, GdeltProvider
from ....event_providers.manual_json import ManualJsonEventProvider, parse_datetime
from ....event_providers.prediction_market_events import PredictionMarketEventsProvider
from ....event_providers.project_blog_rss import ProjectBlogRssProvider
from ....event_providers.sports_fixtures import SportsFixturesProvider
from ....event_providers.tokenomist import TokenomistProvider
from ..resolver import clean_text, load_asset_aliases, resolve_event_assets
from ....supply_providers.arkham import ArkhamSupplyProvider
from ....supply_providers.dune import DuneSupplyProvider
from ....supply_providers.etherscan import EtherscanSupplyProvider
from ....supply_providers.tokenomist import TokenomistSupplyProvider
from .models import *  # noqa: F403 - split modules share historical model names


def event_fade_validation_sample_rows(
    result: EventDiscoveryResult,
    *,
    exported_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Build point-in-time review rows for the event-fade validation sample."""
    exported = _as_utc(exported_at or datetime.now(timezone.utc))
    raw_by_id = {raw.raw_id: raw for raw in result.raw_events}
    rows: list[dict[str, Any]] = []
    for candidate in result.candidates:
        rows.append(_validation_sample_row(candidate, raw_by_id, exported))
    return rows


def format_validation_sample_jsonl(rows: Iterable[Mapping[str, Any]]) -> str:
    return "\n".join(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")) for row in rows)


def format_validation_sample_csv(rows: Iterable[Mapping[str, Any]]) -> str:
    from io import StringIO

    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=list(VALIDATION_SAMPLE_FIELDS), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_cell(row.get(field)) for field in VALIDATION_SAMPLE_FIELDS})
    return out.getvalue()


def write_validation_sample(rows: Iterable[Mapping[str, Any]], path: str | Path) -> Path:
    out = Path(path).expanduser()
    data = list(rows)
    if out.suffix.casefold() == ".csv":
        text = format_validation_sample_csv(data)
    else:
        text = format_validation_sample_jsonl(data)
        if text:
            text += "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def _validation_sample_row(
    candidate: DiscoveredEventFadeCandidate,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
    exported_at: datetime,
) -> dict[str, Any]:
    raw_events = [raw_by_id[raw_id] for raw_id in candidate.event.raw_ids if raw_id in raw_by_id]
    signal = candidate.fade_signal
    fade_candidate = candidate.fade_candidate
    market = fade_candidate.market if fade_candidate else None
    derivatives = fade_candidate.derivatives if fade_candidate else None
    supply = fade_candidate.supply if fade_candidate else None
    rsi = fade_candidate.rsi if fade_candidate else None
    technical = fade_candidate.technical if fade_candidate else None
    vector = (
        event_fade.event_fade_feature_vector(fade_candidate, now=signal.timestamp if signal else None)
        if fade_candidate
        else {}
    )
    row = {
        "schema_version": VALIDATION_SAMPLE_SCHEMA_VERSION,
        "exported_at": _iso(exported_at),
        "row_type": "candidate",
        "event_id": candidate.event.event_id,
        "raw_ids": list(candidate.event.raw_ids),
        "raw_providers": _unique(raw.provider for raw in raw_events),
        "raw_titles": [raw.title for raw in raw_events],
        "raw_content_hashes": [raw.content_hash for raw in raw_events],
        "event_name": candidate.event.event_name,
        "event_type": candidate.event.event_type,
        "external_asset": candidate.event.external_asset,
        "event_time": _iso(candidate.event.event_time),
        "event_time_confidence": candidate.event.event_time_confidence,
        "event_time_source": candidate.event.event_time_source,
        "first_seen_time": _iso(candidate.event.first_seen_time),
        "raw_published_at": [_iso(raw.published_at) for raw in raw_events],
        "raw_fetched_at": [_iso(raw.fetched_at) for raw in raw_events],
        "published_at_min": _iso(_min_dt(raw.published_at for raw in raw_events)),
        "published_at_max": _iso(_max_dt(raw.published_at for raw in raw_events)),
        "fetched_at_min": _iso(_min_dt(raw.fetched_at for raw in raw_events)),
        "fetched_at_max": _iso(_max_dt(raw.fetched_at for raw in raw_events)),
        "source": candidate.event.source,
        "source_urls": list(candidate.event.source_urls),
        "source_count": candidate.data_quality.get("source_count"),
        "asset_coin_id": candidate.asset.coin_id,
        "asset_symbol": candidate.asset.symbol,
        "asset_name": candidate.asset.name,
        "asset_role": candidate.classification.asset_role,
        "asset_role_confidence": candidate.classification.asset_role_confidence,
        "asset_role_reason": candidate.classification.asset_role_reason,
        "asset_role_evidence": list(candidate.classification.asset_role_evidence),
        "link_confidence": candidate.link.link_confidence,
        "match_reason": candidate.link.match_reason,
        "link_evidence": list(candidate.link.evidence),
        "relationship_type": candidate.classification.relationship_type,
        "is_proxy_narrative": candidate.classification.is_proxy_narrative,
        "is_direct_beneficiary": candidate.classification.is_direct_beneficiary,
        "classifier_confidence": candidate.classification.confidence,
        "classifier_version": candidate.classification.classifier_version,
        "classification_reason": candidate.classification.reason,
        "classification_evidence": list(candidate.classification.evidence),
        "fade_state": signal.state.value if signal else None,
        "signal_type": signal.signal_type.value if signal else event_fade.FadeSignalType.NO_TRADE.value,
        "fade_score": signal.fade_score if signal else (fade_candidate.fade_score if fade_candidate else None),
        "signal_confidence": signal.confidence if signal else None,
        "eligible": vector.get("eligible"),
        "reason_codes": list(signal.reason_codes) if signal else [],
        "warnings": list(signal.warnings) if signal else [],
        "component_scores": dict(fade_candidate.component_scores) if fade_candidate else {},
        "data_quality": dict(candidate.data_quality),
        "missing_data": _missing_data(candidate),
        "price": market.price if market else None,
        "market_cap": market.market_cap if market else None,
        "volume_24h": market.volume_24h if market else None,
        "spot_volume_24h": market.spot_volume_24h if market else None,
        "return_24h": market.return_24h if market else None,
        "return_72h": market.return_72h if market else None,
        "return_7d": market.return_7d if market else None,
        "volume_zscore_24h": market.volume_zscore_24h if market else None,
        "spread_bps": market.spread_bps if market else None,
        "order_book_depth_2pct": market.order_book_depth_2pct if market else None,
        "perp_available": derivatives.perp_available if derivatives else None,
        "open_interest": derivatives.open_interest if derivatives else None,
        "open_interest_24h_change_pct": derivatives.open_interest_24h_change_pct if derivatives else None,
        "open_interest_to_market_cap": derivatives.open_interest_to_market_cap if derivatives else None,
        "funding_rate_8h": derivatives.funding_rate_8h if derivatives else None,
        "funding_rate_percentile": derivatives.funding_rate_percentile if derivatives else None,
        "futures_volume_24h": derivatives.futures_volume_24h if derivatives else None,
        "perp_spot_volume_ratio": derivatives.perp_spot_volume_ratio if derivatives else None,
        "liquidations_24h": derivatives.liquidations_24h if derivatives else None,
        "long_short_ratio": derivatives.long_short_ratio if derivatives else None,
        "basis": derivatives.basis if derivatives else None,
        "large_holder_exchange_inflow": supply.large_holder_exchange_inflow if supply else None,
        "cex_inflow_amount": supply.cex_inflow_amount if supply else None,
        "cex_inflow_pct_supply": supply.cex_inflow_pct_supply if supply else None,
        "unlock_amount": supply.unlock_amount if supply else None,
        "unlock_pct_circulating": supply.unlock_pct_circulating if supply else None,
        "top_holder_concentration": supply.top_holder_concentration if supply else None,
        "team_or_mm_wallet_activity": supply.team_or_mm_wallet_activity if supply else None,
        "admin_or_mint_risk": supply.admin_or_mint_risk if supply else None,
        "rsi_daily": rsi.rsi_daily if rsi else None,
        "rsi_4h": rsi.rsi_4h if rsi else None,
        "rsi_weekly": rsi.rsi_weekly if rsi else None,
        "target_overbought_score": rsi.target_overbought_score if rsi else None,
        "btc_risk_on_score": rsi.btc_risk_on_score if rsi else None,
        "rsi_rollover_confirmed": rsi.rsi_rollover_confirmed if rsi else None,
        "bearish_rsi_divergence": rsi.bearish_rsi_divergence if rsi else None,
        "event_vwap": technical.event_vwap if technical else None,
        "price_below_event_vwap": technical.price_below_event_vwap if technical else None,
        "failed_reclaim_event_vwap": technical.failed_reclaim_event_vwap if technical else None,
        "lower_high_confirmed": technical.lower_high_confirmed if technical else None,
        "first_support_broken": technical.first_support_broken if technical else None,
        "post_event_high": technical.post_event_high if technical else None,
        "post_event_lower_high": technical.post_event_lower_high if technical else None,
        "entry_reference_price": signal.entry_reference_price if signal else (technical.entry_reference_price if technical else None),
        "invalidation_level": signal.invalidation_level if signal else (technical.invalidation_level if technical else None),
        "trigger_observed_at": _iso(signal.timestamp) if signal and signal.signal_type == event_fade.FadeSignalType.SHORT_TRIGGERED else None,
        "first_seen_at": None,
        "first_watchlisted_at": None,
        "first_armed_at": None,
        "first_triggered_at": _iso(signal.timestamp) if signal and signal.signal_type == event_fade.FadeSignalType.SHORT_TRIGGERED else None,
        "last_seen_at": None,
        "max_adverse_excursion": None,
        "max_favorable_excursion": None,
        "post_event_return_24h": None,
        "post_event_return_72h": None,
        "post_event_return_7d": None,
        "event_time_entry_price": None,
        "event_time_max_adverse_excursion": None,
        "event_time_max_favorable_excursion": None,
        "event_time_post_event_return_24h": None,
        "event_time_post_event_return_72h": None,
        "event_time_post_event_return_7d": None,
        "outcome_price_interval": None,
        "outcome_price_source": None,
        "review_status": "",
        "reviewed_by": "",
        "reviewed_at": "",
        "human_label": "",
        "human_notes": "",
    }
    return {field: row.get(field) for field in VALIDATION_SAMPLE_FIELDS}


def _min_dt(values: Iterable[datetime | None]) -> datetime | None:
    present = [_as_utc(value) for value in values if value is not None]
    return min(present) if present else None


def _max_dt(values: Iterable[datetime | None]) -> datetime | None:
    present = [_as_utc(value) for value in values if value is not None]
    return max(present) if present else None


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    return str(value)


def _json_ready(value: object) -> object:
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, Mapping):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    return value


def _csv_cell(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(_json_ready(value), sort_keys=True, separators=(",", ":"))
    if isinstance(value, datetime):
        return _iso(value)
    return value
