"""Evidence acquisition scoring and verdict helpers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from .... import (
    event_evidence_quality,
    event_llm_evidence_planner,
)
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ....event_resolver import clean_text
from ...providers import source_packs as event_source_packs
from ...providers import source_registry as event_source_registry
from .. import catalyst_search as event_catalyst_search
from .. import core_opportunities as event_core_opportunities
from .. import impact_hypotheses as event_impact_hypotheses
from .. import source_enrichment as event_source_enrichment
from .models import *  # noqa: F403 - split modules share legacy model names


def _apply_final_verdict_metadata(components: dict[str, Any], result: EvidenceAcquisitionResult) -> None:
    fields = {
        "initial_opportunity_score": result.initial_opportunity_score,
        "initial_opportunity_level": result.initial_opportunity_level,
        "post_refresh_opportunity_score": result.post_refresh_opportunity_score,
        "post_refresh_opportunity_level": result.post_refresh_opportunity_level,
        "post_refresh_market_confirmation_score": result.post_refresh_market_confirmation_score,
        "post_refresh_market_confirmation_level": result.post_refresh_market_confirmation_level,
        "post_refresh_evidence_quality_score": result.post_refresh_evidence_quality_score,
        "final_opportunity_score": result.final_opportunity_score,
        "final_opportunity_level": result.final_opportunity_level,
        "final_verdict_source": result.final_verdict_source,
        "final_verdict_reason": result.final_verdict_reason,
        "market_data_freshness": result.market_data_freshness,
        "market_reaction_confirmation": result.market_reaction_confirmation,
        "final_upgrade_status": result.final_upgrade_status,
        "acquisition_evidence_status": result.acquisition_evidence_status,
        "evidence_quality_delta": result.evidence_quality_delta,
        "opportunity_score_delta": result.opportunity_score_delta,
        "opportunity_level_delta": result.opportunity_level_delta,
        "evidence_quality_upgraded": result.evidence_quality_upgraded,
        "impact_path_validation_upgraded": result.impact_path_validation_upgraded,
        "market_confirmation_upgraded": result.market_confirmation_upgraded,
    }
    for key, value in fields.items():
        if value not in (None, "", [], {}, ()):
            components[key] = value
    if result.final_opportunity_score is not None:
        components["opportunity_score_final"] = result.final_opportunity_score
    if result.final_opportunity_level:
        components["opportunity_level"] = result.final_opportunity_level
    if result.post_refresh_market_confirmation_score is not None:
        components["market_confirmation_score"] = result.post_refresh_market_confirmation_score
        components["post_refresh_market_confirmation_score"] = result.post_refresh_market_confirmation_score
    if result.post_refresh_market_confirmation_level:
        components["market_confirmation_level"] = result.post_refresh_market_confirmation_level
        components["post_refresh_market_confirmation_level"] = result.post_refresh_market_confirmation_level
    if result.post_refresh_market_confirmation_level:
        components["market_reaction_confirmation"] = result.post_refresh_market_confirmation_level
    if result.market_reaction_confirmation:
        components["market_reaction_confirmation"] = result.market_reaction_confirmation
    if result.market_data_freshness:
        components["market_data_freshness"] = result.market_data_freshness
        components.setdefault("market_context_freshness_status", result.market_data_freshness)
    elif components.get("market_context_freshness_status"):
        components["market_data_freshness"] = components.get("market_context_freshness_status")
