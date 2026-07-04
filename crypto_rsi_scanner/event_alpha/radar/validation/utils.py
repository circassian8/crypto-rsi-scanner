"""Validation review utility helpers."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote_plus, urlparse

from ..discovery import VALIDATION_SAMPLE_FIELDS, VALIDATION_SAMPLE_SCHEMA_VERSION
from .models import *  # noqa: F403 - split modules share legacy model names


def _label(row: Mapping[str, Any]) -> str:
    return str(row.get("human_label") or "").strip()


def _review_status(row: Mapping[str, Any]) -> str:
    return str(row.get("review_status") or "").strip().casefold()


def _signal_type(row: Mapping[str, Any]) -> str:
    return str(row.get("signal_type") or "").strip()


def _asset_role(row: Mapping[str, Any]) -> str:
    return str(row.get("asset_role") or "").strip().casefold()


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    return text in {"true", "1", "yes", "y"}


def _btc_risk_bucket(row: Mapping[str, Any]) -> str:
    score = _num(row.get("btc_risk_on_score"))
    if score is None:
        return "btc_risk_unknown"
    if score >= 80:
        return "btc_risk_on_high"
    if score >= 60:
        return "btc_risk_on_elevated"
    if score <= 30:
        return "btc_risk_off"
    return "btc_risk_neutral"


def _changed_evidence_fields(
    fresh: Mapping[str, Any],
    reviewed: Mapping[str, Any],
    evidence_fields: Iterable[str],
) -> tuple[str, ...]:
    return tuple(
        field
        for field in evidence_fields
        if _fingerprint_value(fresh.get(field)) != _fingerprint_value(reviewed.get(field))
    )


def _cohort(name: str, rows: list[Mapping[str, Any]]) -> ValidationCohort:
    reviewed = [row for row in rows if _is_reviewed_evidence(row)]
    reviewed_proxy = [row for row in reviewed if _is_proxy_candidate(row)]
    negative_controls = [
        row
        for row in reviewed
        if _label(row) in CONTROL_LABELS or _is_direct_or_ambiguous(row)
    ]
    triggered_reviewed = [row for row in reviewed if _signal_type(row) == "SHORT_TRIGGERED"]
    triggered_valid = [row for row in triggered_reviewed if _label(row) == POSITIVE_LABEL]
    trigger_precision = (
        len(triggered_valid) / len(triggered_reviewed)
        if triggered_reviewed
        else None
    )
    mfe_values = _nums(row.get("max_favorable_excursion") for row in triggered_reviewed)
    mae_values = _nums(row.get("max_adverse_excursion") for row in triggered_reviewed)
    avg_mfe = _mean(mfe_values)
    avg_mae = _mean(mae_values)
    mfe_mae_ratio = (
        abs(avg_mfe) / abs(avg_mae)
        if avg_mfe is not None and avg_mae not in (None, 0)
        else None
    )
    avg_72h = _mean(_nums(row.get("post_event_return_72h") for row in triggered_reviewed))
    return ValidationCohort(
        name=name,
        total_rows=len(rows),
        reviewed_rows=len(reviewed),
        reviewed_proxy_candidates=len(reviewed_proxy),
        reviewed_negative_controls=len(negative_controls),
        triggered_reviewed=len(triggered_reviewed),
        triggered_valid=len(triggered_valid),
        trigger_precision=trigger_precision,
        avg_mfe=avg_mfe,
        avg_mae=avg_mae,
        mfe_mae_ratio=mfe_mae_ratio,
        avg_post_event_return_72h=avg_72h,
    )


def _cohorts(
    rows: Iterable[Mapping[str, Any]],
    key_fn,
) -> tuple[ValidationCohort, ...]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        key = str(key_fn(row) or "unknown").strip() or "unknown"
        groups.setdefault(key, []).append(row)
    cohorts = [_cohort(name, group) for name, group in groups.items()]
    return tuple(sorted(cohorts, key=lambda item: (-item.reviewed_rows, -item.total_rows, item.name)))


def _decision_time(row: Mapping[str, Any]) -> datetime | None:
    signal_type = _signal_type(row)
    if signal_type == "SHORT_TRIGGERED":
        return _dt(row.get("trigger_observed_at"))
    return _review_event_time(row)


def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _event_time_source_bucket(row: Mapping[str, Any]) -> str:
    if _review_human_event_time(row) is not None:
        return "human_confirmed"
    source = str(row.get("event_time_source") or "").strip()
    if source:
        return source
    if not row.get("event_time"):
        return "missing_event_time"
    return "unknown_event_time_source"


def _event_types(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        value = str(row.get("event_type") or "").strip()
        if value:
            out.add(value)
    return out


def _evidence_change_item(
    row: Mapping[str, Any],
    changed_fields: tuple[str, ...],
) -> ValidationSampleEvidenceChange:
    return ValidationSampleEvidenceChange(
        event_id=str(row.get("event_id") or ""),
        asset_symbol=str(row.get("asset_symbol") or ""),
        asset_coin_id=str(row.get("asset_coin_id") or ""),
        relationship_type=str(row.get("relationship_type") or ""),
        changed_fields=changed_fields,
    )


def _fingerprint_normalized(value: object) -> object:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        raw = value.strip()
        if raw == "":
            return None
        if raw in {"True", "true"}:
            return True
        if raw in {"False", "false"}:
            return False
        if raw.startswith(("{", "[")):
            try:
                return _fingerprint_normalized(json.loads(raw))
            except json.JSONDecodeError:
                return raw
        return raw
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, ".12g")
    if isinstance(value, Mapping):
        return {
            str(key): _fingerprint_normalized(nested)
            for key, nested in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple, set)):
        normalized = [_fingerprint_normalized(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    return str(value).strip()


def _fingerprint_value(value: object) -> str:
    normalized = _fingerprint_normalized(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def _float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_hours(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}h"


def _fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _fmt_pp(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:+.1f}pp"


def _has_value(value: object) -> bool:
    return value is not None and value != ""


def _is_direct_or_ambiguous(row: Mapping[str, Any]) -> bool:
    relation = str(row.get("relationship_type") or "").strip()
    return _bool(row.get("is_direct_beneficiary")) or relation == "ambiguous" or not _is_proxy_candidate(row)


def _is_proxy_candidate(row: Mapping[str, Any]) -> bool:
    return _bool(row.get("is_proxy_narrative")) and not _bool(row.get("is_direct_beneficiary"))


def _is_reviewed_evidence(row: Mapping[str, Any]) -> bool:
    return _review_status(row) == "reviewed" and _label(row) in KNOWN_LABELS


def _known_btc_risk_buckets(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        bucket
        for row in rows
        if (bucket := _btc_risk_bucket(row)) != "btc_risk_unknown"
    }


def _label_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = _label(row)
        counts[label] = counts.get(label, 0) + 1
    return counts


def _list_values(value: object) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return [value]
            return parsed if isinstance(parsed, list) else [value]
        return [value]
    return [value]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _missing_source_timing(row: Mapping[str, Any]) -> bool:
    return not _source_known_times(row, include_max=True)


def _num(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nums(values: Iterable[object]) -> list[float]:
    out: list[float] = []
    for value in values:
        n = _num(value)
        if n is not None:
            out.append(n)
    return out


def _point_in_time_violation(row: Mapping[str, Any]) -> bool:
    decision_time = _decision_time(row)
    if decision_time is None:
        return _signal_type(row) in {"WATCHLIST", "SHORT_TRIGGERED"}
    known_times = _source_known_times(row, include_max=False)
    return bool(known_times) and min(known_times) > decision_time


def _post_decision_source(row: Mapping[str, Any]) -> bool:
    decision_time = _decision_time(row)
    if decision_time is None:
        return False
    return any(value > decision_time for value in _source_known_times(row, include_max=True))


def _publisher_from_title(title: str) -> str | None:
    if " - " not in title:
        return None
    publisher = title.rsplit(" - ", 1)[-1].strip()
    if not publisher:
        return None
    publisher = publisher.removeprefix("www.").casefold()
    publisher = " ".join(publisher.split())
    return publisher or None


def _publishers_from_titles(titles: Iterable[str]) -> tuple[str, ...]:
    publishers: set[str] = set()
    for title in titles:
        publisher = _publisher_from_title(title)
        if publisher:
            publishers.add(publisher)
    return tuple(sorted(publishers))


def _review_event_time(row: Mapping[str, Any]) -> datetime | None:
    human = _review_human_event_time(row)
    if human is not None:
        return human
    return _dt(row.get("event_time"))


def _review_event_time_confidence(row: Mapping[str, Any]) -> float | None:
    if _review_human_event_time(row) is not None:
        return _num(row.get("human_event_time_confidence"))
    return _num(row.get("event_time_confidence"))


def _review_human_event_time(row: Mapping[str, Any]) -> datetime | None:
    human = _dt(row.get("human_event_time"))
    if human is None:
        return None
    confidence = _num(row.get("human_event_time_confidence")) or 0.0
    return human if confidence >= DEFAULT_MIN_TRIGGER_EVENT_TIME_CONFIDENCE else None


def _source_domain(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = (parsed.netloc or "").casefold()
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    host = host.split(":", 1)[0].removeprefix("www.")
    return host or None


def _source_known_times(row: Mapping[str, Any], *, include_max: bool) -> list[datetime]:
    known_times = [
        _dt(row.get("first_seen_time")),
        _dt(row.get("fetched_at_min")),
        _dt(row.get("published_at_min")),
    ]
    if include_max:
        known_times.extend([
            _dt(row.get("fetched_at_max")),
            _dt(row.get("published_at_max")),
        ])
        known_times.extend(_dt(value) for value in _list_values(row.get("raw_fetched_at")))
        known_times.extend(_dt(value) for value in _list_values(row.get("raw_published_at")))
    return [value for value in known_times if value is not None]


def _source_origin_cohorts(rows: Iterable[Mapping[str, Any]]) -> tuple[ValidationCohort, ...]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        for origin in source_origin_values(row):
            groups.setdefault(origin, []).append(row)
    cohorts = [_cohort(name, group) for name, group in groups.items()]
    return tuple(sorted(cohorts, key=lambda item: (-item.reviewed_rows, -item.total_rows, item.name)))


def _source_origins(rows: Iterable[Mapping[str, Any]]) -> frozenset[str]:
    origins: set[str] = set()
    for row in rows:
        origins.update(source_origin_values(row))
    origins.discard("unknown_source_origin")
    return frozenset(origins)


def _source_provider_cohorts(rows: Iterable[Mapping[str, Any]]) -> tuple[ValidationCohort, ...]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        for provider in _source_provider_values(row):
            groups.setdefault(provider, []).append(row)
    cohorts = [_cohort(name, group) for name, group in groups.items()]
    return tuple(sorted(cohorts, key=lambda item: (-item.reviewed_rows, -item.total_rows, item.name)))


def _source_provider_values(row: Mapping[str, Any]) -> tuple[str, ...]:
    values = _list_values(row.get("raw_providers"))
    if not values:
        values = _list_values(row.get("source_provider"))
    if not values:
        values = _list_values(row.get("source"))
    providers = {
        str(value).strip() or "unknown_source_provider"
        for value in values
        if value is not None
    }
    if not providers:
        providers.add("unknown_source_provider")
    return tuple(sorted(providers))


def _source_providers(rows: Iterable[Mapping[str, Any]]) -> frozenset[str]:
    providers: set[str] = set()
    for row in rows:
        providers.update(_source_provider_values(row))
    providers.discard("unknown_source_provider")
    return frozenset(providers)


def _string_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _trigger_latencies_hours(rows: Iterable[Mapping[str, Any]]) -> list[float]:
    out: list[float] = []
    for row in rows:
        event_time = _review_event_time(row)
        trigger_time = _dt(row.get("trigger_observed_at"))
        if event_time is None or trigger_time is None:
            continue
        out.append((trigger_time - event_time).total_seconds() / 3600.0)
    return out


def _trigger_vs_event_time_72h_edges(rows: Iterable[Mapping[str, Any]]) -> list[float]:
    out: list[float] = []
    for row in rows:
        trigger_return = _num(row.get("post_event_return_72h"))
        event_time_return = _num(row.get("event_time_post_event_return_72h"))
        if trigger_return is None or event_time_return is None:
            continue
        # Lower post-entry returns are better for a short, so positive means
        # the confirmed trigger beat a naive short at the event timestamp.
        out.append(event_time_return - trigger_return)
    return out


def source_origin_values(row: Mapping[str, Any]) -> tuple[str, ...]:
    """Return independent source origins from validation row evidence."""
    urls = [str(value) for value in _list_values(row.get("source_urls")) if value not in (None, "")]
    titles = [str(value) for value in _list_values(row.get("raw_titles")) if value not in (None, "")]
    origins: set[str] = set()
    for url in urls:
        domain = _source_domain(url)
        if domain in {"news.google.com"}:
            publishers = _publishers_from_titles(titles)
            origins.update(publishers or (domain,))
        elif domain:
            origins.add(domain)
    if not origins:
        origins.update(_source_provider_values(row))
    if not origins:
        origins.add("unknown_source_origin")
    return tuple(sorted(origins))
