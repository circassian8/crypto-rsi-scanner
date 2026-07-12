"""Card, feedback, and target matching for opportunity audits."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as event_feedback_eligibility
import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities

from . import research_cards as event_research_cards
from .opportunity_audit_values import _row


def _audit_feedback_target(
    row: Mapping[str, Any],
    fallback: str,
    core: event_core_opportunities.CoreOpportunity | None = None,
    card_paths: Iterable[Path] = (),
) -> str:
    for path in card_paths:
        card_target = event_research_cards.card_feedback_target(path)
        if card_target:
            return card_target
    if core is not None:
        for candidate in (core.core_opportunity_id, row.get("card_id"), row.get("alert_id"), row.get("key"), row.get("hypothesis_id")):
            if candidate:
                return str(candidate)
    return str(row.get("card_id") or row.get("alert_id") or row.get("key") or row.get("hypothesis_id") or fallback)


def _matching_card_paths(
    target: str,
    row: Mapping[str, Any],
    core: event_core_opportunities.CoreOpportunity | None,
    card_paths: Iterable[str | Path],
) -> tuple[Path, ...]:
    identifiers = {
        target,
        str(row.get("alert_id") or ""),
        str(row.get("card_id") or ""),
        str(row.get("snapshot_id") or ""),
        str(row.get("key") or ""),
        str(row.get("event_id") or ""),
        str(row.get("hypothesis_id") or ""),
        str(row.get("incident_id") or ""),
        str(row.get("symbol") or ""),
        str(row.get("coin_id") or ""),
        str(row.get("validated_symbol") or ""),
        str(row.get("validated_coin_id") or ""),
    }
    if core is not None:
        identifiers.add(core.core_opportunity_id)
        identifiers.add(core.incident_id or "")
        identifiers.update(str(value) for value in core.supporting_hypothesis_ids)
        identifiers.update(str(support.get("key") or "") for support in core.supporting_rows)
        identifiers.update(str(support.get("card_id") or "") for support in core.supporting_rows)
        identifiers.update(str(support.get("alert_id") or "") for support in core.supporting_rows)
    identifiers = {item for item in identifiers if item}
    identifiers_l = {item.lower() for item in identifiers}
    out: list[Path] = []
    for raw_path in card_paths:
        path = Path(raw_path)
        if path.name == "index.md" or not path.exists():
            continue
        path_targets = {
            str(path),
            path.name,
            path.stem,
            event_research_cards.card_feedback_target(path) or "",
        }
        if identifiers_l.intersection(value.lower() for value in path_targets if value):
            out.append(path)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(identifier in text for identifier in identifiers):
            out.append(path)
    return tuple(dict.fromkeys(out))


def _matching_feedback_rows(
    feedback_target: str,
    row: Mapping[str, Any],
    feedback_rows: Iterable[Mapping[str, Any] | object],
    *,
    core_rows: Iterable[Mapping[str, Any] | object] = (),
    now: datetime | None = None,
) -> tuple[dict[str, Any], ...]:
    del feedback_target
    authorities = [_row(item) for item in core_rows]
    if now is None or not authorities:
        return ()
    exact_identity = event_feedback_eligibility.canonical_feedback_join_identity(row)
    if exact_identity is None:
        return ()
    eligible, _excluded, _reason_counts = (
        event_feedback_eligibility.partition_joined_calibration_feedback(
            (_row(item) for item in feedback_rows),
            authorities,
            now=now,
        )
    )
    return tuple(
        dict(feedback)
        for feedback in eligible
        if event_feedback_eligibility.canonical_feedback_join_identity(feedback)
        == exact_identity
    )


def _target_from_card_path(target: str, card_paths: Iterable[str | Path]) -> str | None:
    target_l = target.lower()
    for raw_path in card_paths:
        path = Path(raw_path)
        if path.name == "index.md" or not path.exists():
            continue
        if target_l in {str(path).lower(), path.name.lower(), path.stem.lower()}:
            return event_research_cards.card_feedback_target(path)
    return None
