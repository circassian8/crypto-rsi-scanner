"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/catalyst_search.py` (report)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol
from urllib.parse import urlparse
import crypto_rsi_scanner.event_alpha.radar.identity as event_identity
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ....event_providers.cryptopanic import CryptoPanicProvider, normalize_cryptopanic_currency_code
from ....event_providers.gdelt import GdeltProvider
from ....event_providers.prediction_market_events import PredictionMarketEventsProvider
from ....event_providers.project_blog_rss import ProjectBlogRssProvider
from ..resolver import clean_text
from .models import *  # noqa: F403

def format_catalyst_search_report(result: CatalystSearchRunResult | None) -> str:
    rows = [
        "=" * 76,
        "EVENT CATALYST SEARCH REPORT (research-only; no alerts, DB writes, paper trades, or orders)",
        "=" * 76,
    ]
    if result is None:
        rows.append("No catalyst search run.")
        return "\n".join(rows)
    rows.append(
        f"provider={result.provider} · queries={len(result.queries)} · "
        f"accepted_results={len(result.result_events)} · rejected_results={len(result.rejected_result_events)} · "
        f"attached_raw_events={len(result.attached_raw_events)}"
    )
    rows.append(
        f"provider_fetches={result.provider_fetch_count} · cache_hits={result.provider_cache_hits} · "
        f"cache_misses={result.provider_cache_misses} · query_count={result.query_count or len(result.queries)} · "
        f"result_count={result.result_count or len(result.result_events)} · "
        f"rejected_count={result.rejected_count or len(result.rejected_result_events)}"
    )
    if result.skip_reasons:
        rows.append(
            "skip_reasons: "
            + ", ".join(f"{key}={value}" for key, value in sorted(result.skip_reasons.items()))
        )
    if result.warnings:
        rows.append("warnings: " + "; ".join(result.warnings))
    if result.queries:
        rows.append("")
        rows.append("Queries:")
        for query in result.queries[:20]:
            reason_text = f" ({', '.join(query.score_reasons)})" if query.score_reasons else ""
            rows.append(f"- {query.symbol} #{query.rank} {query.query_type}: score={query.score} {query.query}{reason_text}")
    if result.result_events:
        rows.append("")
        rows.append("Accepted result evidence:")
        for event in result.result_events[:20]:
            reason_text = f" ({', '.join(event.result_score_reasons)})" if event.result_score_reasons else ""
            rows.append(
                f"- {event.query.symbol} {event.query.query_type}: score={event.result_score} "
                f"{event.raw_event.title} [{event.raw_event.provider}]{reason_text}"
            )
    if result.rejected_result_events:
        rows.append("")
        rows.append("Rejected result evidence:")
        for event in result.rejected_result_events[:20]:
            reason_text = f" ({', '.join(event.result_score_reasons)})" if event.result_score_reasons else ""
            rows.append(
                f"- {event.query.symbol} {event.query.query_type}: score={event.result_score} "
                f"{event.raw_event.title} [{event.raw_event.provider}]{reason_text}"
            )
    return "\n".join(rows).rstrip()
