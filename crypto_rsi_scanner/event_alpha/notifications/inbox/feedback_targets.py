"""Split implementation for `crypto_rsi_scanner/event_alpha/notifications/inbox.py` (feedback_targets)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping
from .... import (
    event_alpha_alert_store,
    event_alpha_quality_fields,
    event_alpha_router,
    event_core_opportunities,
    event_watchlist,
)
from ...artifacts import research_cards as event_research_cards
from ...radar import core_opportunity_store as event_core_opportunity_store
from .. import delivery
from .. import pipeline as event_alpha_notifications
from .models import *  # noqa: F403

def _card_paths_by_core_id(cards_dir: Path) -> dict[str, Path]:
    if not cards_dir or not cards_dir.exists():
        return {}
    out: dict[str, Path] = {}
    for path in cards_dir.glob("*.md"):
        if path.name == "index.md":
            continue
        core_id = event_research_cards.card_core_opportunity_id(path)
        if core_id:
            out.setdefault(core_id, path)
    return out
def _card_path_for_core(
    core_id: str,
    row: Mapping[str, Any],
    paths_by_core: Mapping[str, Path],
) -> Path | None:
    for key in ("research_card_path", "card_path"):
        value = str(row.get(key) or "").strip()
        if value:
            return Path(value)
    return paths_by_core.get(core_id)
def _reviewed_ids(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        for field in ("target", "key", "event_id", "coin_id", "symbol", "card_id", "alert_id"):
            value = str(row.get(field) or "").strip()
            if value:
                ids.add(value)
                if value.startswith("ea:"):
                    ids.add(value[3:])
                else:
                    ids.add(f"ea:{value}")
    return ids
def _alert_ids(alert: Mapping[str, Any], alert_id: str, alert_key: str, card_id: str) -> set[str]:
    ids = {value for value in (alert_id, alert_key, card_id) if value}
    for field in ("event_id", "coin_id", "symbol", "asset_coin_id", "asset_symbol", "validated_coin_id", "validated_symbol", "snapshot_id"):
        value = str(alert.get(field) or "").strip()
        if value:
            ids.add(value)
    ids.update(f"ea:{value}" for value in list(ids) if value and not value.startswith("ea:"))
    ids.update(value[3:] for value in list(ids) if value.startswith("ea:"))
    return ids
def _card_paths(cards_dir: Path) -> dict[str, Path]:
    if not cards_dir.exists():
        return {}
    paths = {
        path.stem: path
        for path in cards_dir.glob("*.md")
        if path.name != "index.md"
    }
    return paths
def _path_for_card(
    alert_id: str,
    alert_key: str,
    card_id: str,
    paths: Mapping[str, Path],
) -> Path | None:
    for key in (card_id, alert_id.replace("ea:", "card_"), f"card_{alert_key}"):
        clean = _card_key(key)
        if clean in paths:
            return paths[clean]
    return None
def _card_key(value: str) -> str:
    text = str(value or "").strip()
    if text.endswith(".md"):
        text = text[:-3]
    return text
