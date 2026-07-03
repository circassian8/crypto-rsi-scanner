"""Core opportunity path and card linkage helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import (
    config,
    event_alpha_router,
    event_watchlist,
)
from ...artifacts import paths as event_artifact_paths
from .. import core_opportunities as event_core_opportunities
from .. import market_reaction as event_market_reaction
from .. import opportunity_verdict as event_opportunity_verdict
from .models import *  # noqa: F403 - split modules share legacy model names


def _load_alert_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        from .... import event_alpha_alert_store

        return [dict(row) for row in event_alpha_alert_store.load_alert_snapshots(path).rows]
    except Exception:  # noqa: BLE001 - partial artifact views should fail soft.
        return []


def _load_acquisition_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        from .. import evidence_acquisition as event_evidence_acquisition

        return [dict(row) for row in event_evidence_acquisition.load_acquisition_results(path)]
    except Exception:  # noqa: BLE001 - partial artifact views should fail soft.
        return []


def _load_incident_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        from .. import incidents as event_incident_store

        return [
            dict(row)
            for row in event_incident_store.load_incidents(
                path,
                latest_run=False,
                include_legacy=True,
                include_diagnostic=True,
                include_raw=True,
                include_external_context=True,
            ).rows
        ]
    except Exception:  # noqa: BLE001 - partial artifact views should fail soft.
        return []


def _load_feedback_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        from .... import event_feedback

        return [asdict(record) for record in event_feedback.load_feedback(path).records]
    except Exception:  # noqa: BLE001 - partial artifact views should fail soft.
        return []


def _markdown_card_paths(path: str | Path | None) -> tuple[Path, ...]:
    if path is None:
        return ()
    root = Path(path).expanduser()
    if not root.exists():
        return ()
    if root.is_file():
        return (root,) if root.suffix.lower() == ".md" else ()
    try:
        return tuple(path for path in root.glob("*.md") if path.name != "index.md")
    except OSError:
        return ()


def _card_path_by_core_id(paths: Iterable[str | Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from ...artifacts import research_cards as event_research_cards
    except Exception:  # noqa: BLE001 - optional presentation helper.
        return out
    for value in paths:
        path = Path(value)
        core_id = event_research_cards.card_core_opportunity_id(path)
        if core_id:
            out.setdefault(core_id, str(path))
    return out


def _find_core_opportunity(
    target: str,
    opportunities: Iterable[event_core_opportunities.CoreOpportunity],
) -> event_core_opportunities.CoreOpportunity | None:
    clean = target[3:] if target.startswith("ea:") else target
    clean_l = clean.casefold()
    for item in opportunities:
        identifiers = {
            item.core_opportunity_id,
            item.symbol,
            item.coin_id,
            item.incident_id or "",
            item.canonical_incident_name or "",
            str(item.primary_row.get("alert_id") or ""),
            str(item.primary_row.get("card_id") or ""),
            str(item.primary_row.get("snapshot_id") or ""),
            str(item.primary_row.get("key") or ""),
            str(item.primary_row.get("alert_key") or ""),
            str(item.primary_row.get("hypothesis_id") or ""),
        }
        identifiers.update(str(value) for value in item.supporting_hypothesis_ids)
        identifiers.update(_as_list_values(item.primary_row.get("supporting_row_ids")))
        identifiers.update(_as_list_values(item.primary_row.get("diagnostic_row_ids")))
        for row in (*item.supporting_rows, *item.diagnostic_rows):
            identifiers.update(_row_identifier_values(row))
        if clean in identifiers or clean_l in {value.casefold() for value in identifiers if value}:
            return item
    return None


def _target_from_acquisition_rows(target: str, rows: Iterable[Mapping[str, Any]]) -> str | None:
    clean = str(target or "").strip()
    clean_l = clean.casefold()
    for row in rows:
        candidates = {
            str(row.get("original_core_opportunity_id") or ""),
            str(row.get("requested_core_opportunity_id") or ""),
            str(row.get("support_row_id") or ""),
            str(row.get("hypothesis_id") or ""),
        }
        if clean in candidates or clean_l in {item.casefold() for item in candidates if item}:
            resolved = str(row.get("core_opportunity_id") or "").strip()
            if resolved:
                return resolved
    return None


def _canonical_store_row(
    core_id: str,
    core_rows: Iterable[Mapping[str, Any]],
    opportunity: event_core_opportunities.CoreOpportunity,
) -> dict[str, Any]:
    for row in core_rows:
        if str(row.get("core_opportunity_id") or "") == core_id:
            return dict(row)
    row = _row_from_core_opportunity(
        opportunity,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    return dict(row)


def _core_view_identifiers(
    canonical_row: Mapping[str, Any],
    opportunity: event_core_opportunities.CoreOpportunity,
) -> set[str]:
    identifiers = set(_row_identifier_values(canonical_row))
    identifiers.add(opportunity.core_opportunity_id)
    identifiers.add(opportunity.symbol)
    identifiers.add(opportunity.coin_id)
    identifiers.add(opportunity.incident_id or "")
    identifiers.add(opportunity.canonical_incident_name or "")
    identifiers.update(str(value) for value in opportunity.supporting_hypothesis_ids)
    identifiers.update(_as_list_values(canonical_row.get("supporting_row_ids")))
    identifiers.update(_as_list_values(canonical_row.get("diagnostic_row_ids")))
    for row in (*opportunity.supporting_rows, *opportunity.diagnostic_rows):
        identifiers.update(_row_identifier_values(row))
    return {str(value) for value in identifiers if str(value or "").strip()}


def _row_identifier_values(row: Mapping[str, Any]) -> set[str]:
    values = {
        row.get("core_opportunity_id"),
        row.get("diagnostic_support_for_core_opportunity_id"),
        row.get("original_core_opportunity_id"),
        row.get("feedback_target"),
        row.get("target"),
        row.get("alert_id"),
        row.get("alert_key"),
        row.get("card_id"),
        row.get("snapshot_id"),
        row.get("watchlist_key"),
        row.get("key"),
        row.get("event_id"),
        row.get("hypothesis_id"),
        row.get("incident_id"),
        row.get("symbol"),
        row.get("validated_symbol"),
        row.get("coin_id"),
        row.get("validated_coin_id"),
        row.get("asset_symbol"),
        row.get("asset_coin_id"),
    }
    for key in ("supporting_hypothesis_ids", "supporting_row_ids", "diagnostic_row_ids", "source_event_ids", "event_ids"):
        values.update(_as_list_values(row.get(key)))
    return {str(value) for value in values if str(value or "").strip()}


def _row_matches_identifiers(row: Mapping[str, Any], identifiers: set[str]) -> bool:
    direct_values = {
        row.get("core_opportunity_id"),
        row.get("diagnostic_support_for_core_opportunity_id"),
        row.get("original_core_opportunity_id"),
        row.get("feedback_target"),
        row.get("target"),
        row.get("alert_id"),
        row.get("alert_key"),
        row.get("card_id"),
        row.get("snapshot_id"),
        row.get("watchlist_key"),
        row.get("key"),
        row.get("event_id"),
        row.get("hypothesis_id"),
    }
    for key in ("supporting_hypothesis_ids", "supporting_row_ids", "diagnostic_row_ids", "source_event_ids", "event_ids"):
        direct_values.update(_as_list_values(row.get(key)))
    if {str(value) for value in direct_values if str(value or "").strip()}.intersection(identifiers):
        return True
    incident = str(row.get("incident_id") or "").strip()
    asset_values = {
        str(value)
        for value in (
            row.get("symbol"),
            row.get("validated_symbol"),
            row.get("coin_id"),
            row.get("validated_coin_id"),
            row.get("asset_symbol"),
            row.get("asset_coin_id"),
        )
        if str(value or "").strip()
    }
    return bool(incident and incident in identifiers and asset_values.intersection(identifiers))


def _row_is_diagnostic_support(row: Mapping[str, Any], core_id: str, identifiers: set[str]) -> bool:
    if str(row.get("diagnostic_support_for_core_opportunity_id") or "") == core_id:
        return True
    if not _row_matches_identifiers(row, identifiers):
        return False
    return event_core_opportunities.row_is_diagnostic(row)


def _incident_matches_identifiers(row: Mapping[str, Any], identifiers: set[str]) -> bool:
    direct_values = {
        row.get("incident_id"),
        row.get("canonical_name"),
        row.get("canonical_incident_name"),
        row.get("primary_subject"),
        row.get("main_frame_subject"),
    }
    if {str(value) for value in direct_values if str(value or "").strip()}.intersection(identifiers):
        return True
    linked_assets = row.get("linked_assets")
    if isinstance(linked_assets, Iterable) and not isinstance(linked_assets, (str, bytes, Mapping)):
        for item in linked_assets:
            if not isinstance(item, Mapping):
                continue
            values = {
                item.get("symbol"),
                item.get("coin_id"),
                item.get("asset_symbol"),
                item.get("asset_coin_id"),
            }
            if {str(value) for value in values if str(value or "").strip()}.intersection(identifiers):
                return True
    return False


def _best_incident_row(
    rows: Iterable[Mapping[str, Any]],
    canonical_row: Mapping[str, Any],
    opportunity: event_core_opportunities.CoreOpportunity,
) -> dict[str, Any] | None:
    candidates = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not candidates:
        return None
    incident_id = str(canonical_row.get("incident_id") or opportunity.incident_id or "").strip()
    if incident_id:
        exact = [row for row in candidates if str(row.get("incident_id") or "").strip() == incident_id]
        if exact:
            candidates = exact
    status_rank = {
        "active_incident": 5,
        "linked_incident": 4,
        "canonical_incident": 3,
        "incident_candidate": 2,
    }
    return sorted(
        candidates,
        key=lambda row: (
            status_rank.get(str(row.get("incident_relevance_status") or "").strip(), 0),
            float(row.get("incident_relevance_score") or 0.0),
            str(row.get("last_updated_at") or row.get("observed_at") or ""),
        ),
        reverse=True,
    )[0]


def _is_market_refresh_row(row: Mapping[str, Any]) -> bool:
    return _any_truthy(
        [row],
        (
            "market_refresh_attempted",
            "targeted_market_refresh_attempted",
            "market_refresh_success",
            "targeted_market_refresh_success",
        ),
    ) or any(
        key in row
        for key in (
            "market_context_after",
            "market_confirmation_after",
            "market_context_observed_at",
            "market_context_freshness_status",
        )
    )


def _research_card_path(
    canonical_row: Mapping[str, Any],
    core_id: str,
    paths: Iterable[Path],
) -> str | None:
    existing = _first_text([canonical_row], ("research_card_path", "card_path"))
    if existing:
        return existing
    try:
        from ...artifacts import research_cards as event_research_cards
    except Exception:  # noqa: BLE001 - optional presentation helper.
        return None
    for path in paths:
        if event_research_cards.card_core_opportunity_id(path) == core_id:
            return str(path)
    return None


def _feedback_matches(row: Mapping[str, Any], identifiers: set[str], feedback_target: str | None) -> bool:
    explicit_target = str(row.get("target") or "").strip()
    if explicit_target and (explicit_target == feedback_target or explicit_target in identifiers):
        return True
    return _row_matches_identifiers(row, identifiers)


def _unique_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized = dict(row)
        row_type = str(normalized.get("row_type") or "row").strip()
        if row_type == "event_alpha_alert_snapshot":
            id_value = _first_text(
                [normalized],
                (
                    "alert_id",
                    "snapshot_id",
                    "card_id",
                    "alert_key",
                    "core_opportunity_id",
                ),
            )
            snapshot_class = str(normalized.get("snapshot_class") or normalized.get("core_resolution_status") or "").strip()
            if id_value and snapshot_class:
                id_value = f"{id_value}:{snapshot_class}"
        else:
            id_value = _first_text(
                [normalized],
                (
                    "acquisition_id",
                    "core_opportunity_id",
                    "diagnostic_support_for_core_opportunity_id",
                    "original_core_opportunity_id",
                    "alert_id",
                    "snapshot_id",
                    "hypothesis_id",
                    "key",
                    "event_id",
                ),
            )
        dedupe_key = (
            f"{row_type}:{id_value}"
            if id_value
            else json.dumps(_json_ready(normalized), sort_keys=True, separators=(",", ":"))
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(normalized)
    return out


def _row_dict(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(getattr(value, "__dict__", {}) or {})


def _as_list_values(value: Any) -> set[str]:
    if value in (None, "", [], {}, ()):
        return set()
    if isinstance(value, str):
        return {item.strip() for item in value.replace("|", ";").split(";") if item.strip()}
    if isinstance(value, Mapping):
        return {str(item) for item in value.values() if str(item or "").strip()}
    if isinstance(value, Iterable):
        return {str(item) for item in value if str(item or "").strip()}
    return {str(value)}


def _row_ids(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    ids: list[str] = []
    for row in rows:
        value = _first_text([row], ("row_id", "hypothesis_id", "alert_id", "watchlist_key", "key", "event_id"))
        if value:
            ids.append(value)
    return list(dict.fromkeys(ids))


def _any_truthy(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> bool:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            if _truthy(value):
                return True
    return False


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _best_confirmation_context(
    rows: Iterable[Mapping[str, Any]],
    *,
    score_keys: tuple[str, ...],
    level_keys: tuple[str, ...],
    reasons_keys: tuple[str, ...],
    freshness_keys: tuple[str, ...],
) -> dict[str, Any]:
    score = _best_float(rows, score_keys)
    return {
        "score": score,
        "level": _first_text(rows, level_keys) or (_market_level_from_score(score) if score is not None else None),
        "reasons": _first_list(rows, reasons_keys),
        "freshness_status": _first_text(rows, freshness_keys),
    }


def _best_float(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> float | None:
    values = [
        parsed
        for row in rows
        for parsed in (_first_float([row], keys),)
        if parsed is not None
    ]
    return max(values) if values else None


def _best_market_context(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for source in (row, components if isinstance(components, Mapping) else None):
            if not isinstance(source, Mapping):
                continue
            candidates.append(_market_context_from_flat(source))
            for key in ("market_context_after", "market_context", "market_data_context"):
                nested = source.get(key)
                if isinstance(nested, Mapping):
                    candidates.append(_market_context_from_nested(nested))
    candidates = [item for item in candidates if _market_context_has_value(item)]
    if not candidates:
        return {}
    candidates.sort(key=_market_context_rank, reverse=True)
    return candidates[0]


def _best_source_pack(rows: Iterable[Mapping[str, Any]], impact_path: str | None) -> str | None:
    prioritized: list[str] = []
    fallback: list[str] = []
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        values = (
            row.get("evidence_acquisition_source_pack"),
            row.get("source_pack"),
            components.get("evidence_acquisition_source_pack") if isinstance(components, Mapping) else None,
            components.get("source_pack") if isinstance(components, Mapping) else None,
        )
        status = str(
            row.get("evidence_acquisition_status")
            or (components.get("evidence_acquisition_status") if isinstance(components, Mapping) else "")
            or ""
        )
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            if status == "accepted_evidence_found" or text != "market_anomaly_pack":
                prioritized.append(text)
            else:
                fallback.append(text)
    if prioritized:
        return prioritized[0]
    if fallback:
        return fallback[0]
    try:
        from ...providers import source_packs as event_source_packs
        impact = str(impact_path or "")
        pack_impact = "venue_value_capture" if impact.casefold() in {"proxy_attention", "proxy_exposure"} else impact
        return event_source_packs.source_pack_for_playbook(
            "proxy_attention" if pack_impact.casefold() in {"venue_value_capture", "proxy_exposure"} else impact,
            impact_path_type=pack_impact,
        ).name
    except Exception:  # noqa: BLE001 - optional source-pack helper.
        return None


def _first_float(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> float | None:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            parsed = _float_or_none(value)
            if parsed is not None:
                return parsed
    return None


def _first_list(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> list[Any]:
    value = _first_value(rows, keys)
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return list(value)
    return [value]


def _first_text(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> str | None:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            text = str(value or "").strip()
            if text:
                return text
    return None


def _first_value(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> Any:
    for row in rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
        for key in keys:
            value = row.get(key)
            if value in (None, "", [], {}, ()):
                value = components.get(key) if isinstance(components, Mapping) else None
            if value not in (None, "", [], {}, ()):
                return value
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value


def _latest_run_id(rows: Iterable[Mapping[str, Any]]) -> str | None:
    for row in rows:
        value = str(row.get("run_id") or "").strip()
        if value:
            return value
    return None


def _market_context_from_flat(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "market_context_freshness_status": _text_or_none(source.get("market_context_freshness_status")),
        "market_context_source": _text_or_none(source.get("market_context_source")),
        "market_context_observed_at": _text_or_none(source.get("market_context_observed_at")),
        "market_context_age_hours": _float_or_none(source.get("market_context_age_hours")),
        "market_context_freshness_cap_applied": _truthy(source.get("market_context_freshness_cap_applied")),
        "market_context_data_quality": _text_or_none(source.get("market_context_data_quality")),
    }


def _market_context_from_nested(source: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = source.get("market_snapshot") if isinstance(source.get("market_snapshot"), Mapping) else {}
    data_quality = _text_or_none(source.get("data_quality")) or _text_or_none(snapshot.get("data_quality"))
    observed_at = (
        _text_or_none(source.get("timestamp"))
        or _text_or_none(source.get("observed_at"))
        or _text_or_none(snapshot.get("timestamp"))
        or _text_or_none(snapshot.get("observed_at"))
    )
    age_seconds = _float_or_none(source.get("age_seconds"))
    age_hours = _float_or_none(source.get("age_hours"))
    if age_hours is None and age_seconds is not None:
        age_hours = age_seconds / 3600.0
    source_name = _text_or_none(source.get("source")) or _text_or_none(snapshot.get("source"))
    freshness = _text_or_none(source.get("freshness_status")) or _text_or_none(source.get("market_context_freshness_status"))
    if not freshness and data_quality in {"fresh", "fixture_allowed_stale", "stale", "missing", "unknown"}:
        freshness = data_quality
    if not freshness and observed_at:
        freshness = "fresh"
    cap_value = source.get("freshness_cap_applied", source.get("market_context_freshness_cap_applied"))
    return {
        "market_context_freshness_status": freshness,
        "market_context_source": source_name,
        "market_context_observed_at": observed_at,
        "market_context_age_hours": age_hours,
        "market_context_freshness_cap_applied": _truthy(cap_value),
        "market_context_data_quality": data_quality,
    }


def _market_context_has_value(item: Mapping[str, Any]) -> bool:
    return any(value not in (None, "", [], {}, ()) for value in item.values())


def _market_context_rank(item: Mapping[str, Any]) -> tuple[int, int, int, int, int, int]:
    status = str(item.get("market_context_freshness_status") or "").casefold()
    source = str(item.get("market_context_source") or "").casefold()
    data_quality = str(item.get("market_context_data_quality") or "").casefold()
    observed_at = str(item.get("market_context_observed_at") or "").strip()
    age = item.get("market_context_age_hours")
    cap = bool(item.get("market_context_freshness_cap_applied"))
    return (
        3 if status == "fresh" else 2 if status == "fixture_allowed_stale" else 1 if status == "stale" else 0,
        1 if source not in {"", "missing", "unknown"} else 0,
        1 if data_quality not in {"", "missing", "unknown"} else 0,
        1 if observed_at else 0,
        1 if age not in (None, "", "unknown") else 0,
        0 if cap else 1,
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    raw = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(raw, Mapping):
                    rows.append(dict(raw))
    except OSError:
        return []
    return rows


def _text_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)
