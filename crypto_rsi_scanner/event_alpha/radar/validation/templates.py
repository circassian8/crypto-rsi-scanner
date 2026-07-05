"""Validation review template helpers."""

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
from .models import *  # noqa: F403 - split modules share historical model names


def merge_review_fields(
    fresh_rows: Iterable[Mapping[str, Any]],
    reviewed_rows: Iterable[Mapping[str, Any]],
) -> ValidationSampleMergeResult:
    """Copy human review fields only when the row's evidence fingerprint is unchanged."""
    return _merge_review_fields(fresh_rows, reviewed_rows, evidence_fields=REVIEW_EVIDENCE_FIELDS)


def _merge_review_fields(
    fresh_rows: Iterable[Mapping[str, Any]],
    reviewed_rows: Iterable[Mapping[str, Any]],
    *,
    evidence_fields: Iterable[str],
) -> ValidationSampleMergeResult:
    fresh = [dict(row) for row in fresh_rows]
    reviewed = [dict(row) for row in reviewed_rows]
    evidence_field_tuple = tuple(evidence_fields)
    reviewed_by_key = {
        key: row
        for row in reviewed
        if (key := _sample_key(row)) is not None and _has_review_data(row)
    }
    matched_keys: set[tuple[str, str, str]] = set()
    evidence_changes: list[ValidationSampleEvidenceChange] = []
    copied_fields = 0
    merged: list[dict[str, Any]] = []
    for row in fresh:
        out = dict(row)
        key = _sample_key(row)
        source = reviewed_by_key.get(key) if key is not None else None
        if source is not None:
            matched_keys.add(key)
            changed_fields = _changed_evidence_fields(out, source, evidence_field_tuple)
            if changed_fields:
                evidence_changes.append(_evidence_change_item(out, changed_fields))
                merged.append(out)
                continue
            for field in REVIEW_FIELDS:
                value = source.get(field)
                if _has_value(value):
                    out[field] = value
                    copied_fields += 1
        merged.append(out)
    return ValidationSampleMergeResult(
        rows=merged,
        fresh_rows=len(fresh),
        reviewed_rows=len(reviewed),
        matched_rows=len(matched_keys),
        evidence_changed_rows=len(evidence_changes),
        evidence_changes=tuple(evidence_changes),
        unmatched_reviewed_rows=max(0, len(reviewed_by_key) - len(matched_keys)),
        copied_fields=copied_fields,
    )


def build_review_template_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int | None = 20,
) -> list[dict[str, Any]]:
    """Build compact, editable sidecar rows for human validation review."""
    data = [dict(row) for row in rows]
    pairs = _review_packet_items(data, limit=limit)
    return [_review_template_row(item, row) for item, row in pairs]


def build_balanced_review_template_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    proxy_limit: int | None = DEFAULT_BALANCED_PROXY_REVIEW_ROWS,
    control_limit: int | None = DEFAULT_BALANCED_CONTROL_REVIEW_ROWS,
    triggered_limit: int | None = None,
) -> list[dict[str, Any]]:
    """Build a review sidecar that samples the validation gates, not just priority order."""
    return [
        {
            **_review_template_row(item, row),
            "review_slice": review_slice,
        }
        for review_slice, item, row in _balanced_review_packet_items(
            rows,
            proxy_limit=proxy_limit,
            control_limit=control_limit,
            triggered_limit=triggered_limit,
        )
    ]


def format_review_template_jsonl(rows: Iterable[Mapping[str, Any]]) -> str:
    return "\n".join(
        json.dumps(_review_template_json_ready(row), sort_keys=True, separators=(",", ":"))
        for row in rows
    )


def format_review_template_csv(rows: Iterable[Mapping[str, Any]]) -> str:
    from io import StringIO

    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=list(REVIEW_TEMPLATE_FIELDS), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({
            field: _review_template_csv_cell(row.get(field))
            for field in REVIEW_TEMPLATE_FIELDS
        })
    return out.getvalue()


def write_review_template(
    rows: Iterable[Mapping[str, Any]],
    path: str | Path,
    *,
    limit: int | None = 20,
) -> Path:
    out = Path(path).expanduser()
    template_rows = build_review_template_rows(rows, limit=limit)
    if out.suffix.casefold() == ".csv":
        text = format_review_template_csv(template_rows)
    else:
        text = format_review_template_jsonl(template_rows)
        if text:
            text += "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def apply_review_template(
    sample_rows: Iterable[Mapping[str, Any]],
    reviewed_template_rows: Iterable[Mapping[str, Any]],
) -> ValidationSampleMergeResult:
    """Copy human review fields from a compact sidecar into validation rows."""
    return _merge_review_fields(
        sample_rows,
        reviewed_template_rows,
        evidence_fields=REVIEW_TEMPLATE_EVIDENCE_FIELDS,
    )


def check_review_template(
    sample_rows: Iterable[Mapping[str, Any]],
    reviewed_template_rows: Iterable[Mapping[str, Any]],
) -> ValidationReviewTemplateCheck:
    """Dry-check an edited review sidecar before applying it to a sample."""
    fresh = [dict(row) for row in sample_rows]
    template = [dict(row) for row in reviewed_template_rows]
    result = apply_review_template(fresh, template)

    fresh_by_key = {
        key: row
        for row in fresh
        if (key := _sample_key(row)) is not None
    }
    merged_by_key = {
        key: row
        for row in result.rows
        if (key := _sample_key(row)) is not None
    }

    issues: list[ValidationReviewTemplateIssue] = []
    edited_rows = 0
    for idx, row in enumerate(template, 1):
        if not _has_review_data(row):
            continue
        edited_rows += 1
        key = _sample_key(row)
        if key is None:
            issues.append(_review_template_issue(
                row,
                idx,
                category="missing_identity",
                message="Template row has review data but lacks event/asset/relationship identity.",
            ))
            continue
        fresh_row = fresh_by_key.get(key)
        if fresh_row is None:
            issues.append(_review_template_issue(
                row,
                idx,
                category="unmatched_row",
                message="Template row has review data but does not match any sample row.",
            ))
            continue
        changed = _changed_evidence_fields(fresh_row, row, REVIEW_TEMPLATE_EVIDENCE_FIELDS)
        if changed:
            issues.append(_review_template_issue(
                row,
                idx,
                category="evidence_changed",
                message="Evidence fields changed; review fields will not be copied.",
                changed_fields=changed,
            ))
            continue
        merged_row = merged_by_key.get(key, fresh_row)
        queue_item = _labeling_queue_item(merged_row)
        if queue_item is not None:
            issues.append(_review_template_issue(
                merged_row,
                idx,
                category=queue_item.category,
                message="Edited row still needs required review fields before it is complete.",
                missing_fields=queue_item.missing_fields,
            ))

    if edited_rows == 0:
        issues.append(ValidationReviewTemplateIssue(
            row_index=0,
            category="no_review_data",
            event_id="",
            asset_symbol="",
            asset_coin_id="",
            relationship_type="",
            message="No sidecar row contains nonblank review fields.",
        ))

    return ValidationReviewTemplateCheck(
        template_rows=len(template),
        edited_rows=edited_rows,
        matched_rows=result.matched_rows,
        evidence_changed_rows=result.evidence_changed_rows,
        unmatched_reviewed_rows=result.unmatched_reviewed_rows,
        copied_fields=result.copied_fields,
        issues=tuple(issues),
    )


def format_review_template_check(
    check: ValidationReviewTemplateCheck,
    *,
    limit: int = 20,
) -> str:
    rows = [
        "=" * 78,
        "EVENT FADE REVIEW TEMPLATE CHECK (research-only; no writes, alerts, paper trades, or orders)",
        "=" * 78,
        (
            f"Template rows: {check.template_rows} · edited rows: {check.edited_rows} · "
            f"matched edited rows: {check.matched_rows} · copied fields if applied: {check.copied_fields}"
        ),
        (
            f"Evidence-changed rows: {check.evidence_changed_rows} · "
            f"unmatched edited rows: {check.unmatched_reviewed_rows} · issues: {check.issue_rows}"
        ),
        "",
        "Status: ready to apply." if check.ready_to_apply else "Status: not ready to apply.",
    ]
    if not check.issues:
        return "\n".join(rows)

    rows.extend(["", "Issues:"])
    shown = check.issues[: max(0, limit)]
    for issue in shown:
        label = issue.asset_symbol or issue.asset_coin_id or "unknown-asset"
        event = issue.event_id or "unknown-event"
        rows.append(
            f"- row {issue.row_index}: {issue.category} · {label} · "
            f"{event} · rel={issue.relationship_type or 'unknown'}"
        )
        rows.append(f"  {issue.message}")
        if issue.missing_fields:
            rows.append("  missing: " + ", ".join(issue.missing_fields))
        if issue.changed_fields:
            fields = ", ".join(issue.changed_fields[:8])
            if len(issue.changed_fields) > 8:
                fields += f", +{len(issue.changed_fields) - 8} more"
            rows.append("  changed evidence: " + fields)
    remaining = len(check.issues) - len(shown)
    if remaining > 0:
        rows.append(f"- ... {remaining} more issue(s)")
    return "\n".join(rows)


def format_merge_evidence_changes(
    result: ValidationSampleMergeResult,
    *,
    limit: int = 10,
) -> str:
    """Format rows whose prior review was skipped because evidence changed."""
    if not result.evidence_changes:
        return ""
    shown = result.evidence_changes[:limit]
    rows = ["Evidence-changed rows (review fields were not copied):"]
    for item in shown:
        label = item.asset_symbol or item.asset_coin_id or "unknown-asset"
        event_id = item.event_id or "unknown-event"
        relationship = item.relationship_type or "unknown"
        fields = ", ".join(item.changed_fields[:8])
        if len(item.changed_fields) > 8:
            fields += f", +{len(item.changed_fields) - 8} more"
        rows.append(f"- {label} {event_id} `{relationship}` changed: {fields}")
    remaining = len(result.evidence_changes) - len(shown)
    if remaining > 0:
        rows.append(f"- ... {remaining} more evidence-changed row(s)")
    return "\n".join(rows)


def _review_template_row(
    item: ValidationLabelingQueueItem,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    out = {field: row.get(field) for field in REVIEW_TEMPLATE_FIELDS}
    out.update({
        "queue_category": item.category,
        "suggested_label": item.suggested_label,
        "missing_fields": list(item.missing_fields),
        "review_prompt": _review_template_prompt(item, row),
        "event_time_review_hint": _event_time_review_hint(row),
        "source_date_hint": _source_date_hint(row),
        "primary_source_url": _first_list_text(row.get("source_urls")),
        "primary_source_origin": _first_list_text(source_origin_values(row)),
        "primary_raw_title": _first_list_text(row.get("raw_titles")),
        "source_search_url": _source_search_url(row),
        "source_urls": list(item.source_urls),
        "source_providers": list(_source_provider_values(row)),
        "source_origins": list(item.source_origins),
    })
    return out


def _review_template_prompt(
    item: ValidationLabelingQueueItem,
    row: Mapping[str, Any],
) -> str:
    if item.category == "confirm_proxy_event_time":
        return (
            "Open primary_source_url, verify the proxy/direct relationship, and fill "
            "human_event_time* only if explicit catalyst timing is sourced."
        )
    if item.category == "label_triggered_candidate":
        return (
            "Verify source evidence, label the row, and fill any required trigger/event-time "
            "outcomes from local price evidence."
        )
    if item.category == "confirm_trigger_event_time":
        return "Confirm the trigger's event time from source evidence before counting outcomes."
    if item.category == "add_review_provenance":
        return "Add reviewed_by and reviewed_at so the existing label is auditable."
    if item.category == "confirm_source_timing":
        return "Check that source evidence was published/fetched before the decision time."
    if item.category == "confirm_point_in_time":
        return "Check point-in-time evidence timing before keeping this row as reviewed."
    if "human_label" in item.missing_fields:
        return "Open primary_source_url and assign one accepted human_label with evidence notes."
    return "Review the missing fields listed for this row."


def _event_time_review_hint(row: Mapping[str, Any]) -> str:
    source = _string_or_none(row.get("event_time_source")) or "missing"
    confidence = _float_or_none(row.get("event_time_confidence")) or 0.0
    event_time = _string_or_none(row.get("event_time"))
    if not event_time:
        return "No machine event time; fill human_event_time* only from explicit dated catalyst evidence."
    if source == "text_date" or confidence < DEFAULT_MIN_TRIGGER_EVENT_TIME_CONFIDENCE:
        return "Machine event time is inferred or low confidence; confirm with an explicit source before counting it."
    return "Machine event time is explicit/high confidence; confirm only if source evidence contradicts it."


def _source_date_hint(row: Mapping[str, Any]) -> str | None:
    values: list[str] = []
    for value in (row.get("event_name"), row.get("description"), *list(_list_values(row.get("raw_titles")))):
        text = str(value or "").strip()
        if text:
            values.append(text)
    found: list[str] = []
    seen: set[str] = set()
    for text in values:
        for pattern in DATE_HINT_PATTERNS:
            for match in pattern.finditer(text):
                hint = re.sub(r"\s+", " ", match.group(0)).strip(" -–")
                key = hint.casefold()
                if hint and key not in seen:
                    found.append(hint)
                    seen.add(key)
                if len(found) >= 5:
                    return "; ".join(found)
    return "; ".join(found) if found else None


def _first_list_text(value: object) -> str | None:
    for item in _list_values(value):
        text = _packet_text(item)
        if text and text != "n/a":
            return text
    return None


def _source_search_url(row: Mapping[str, Any]) -> str | None:
    title = _first_list_text(row.get("raw_titles")) or _string_or_none(row.get("event_name"))
    if not title:
        return None
    origin = _first_list_text(source_origin_values(row))
    query = f'"{title}"'
    if origin and origin != "unknown_source_origin":
        query = f"{query} {origin}"
    return "https://www.google.com/search?q=" + quote_plus(query)


def _review_template_json_ready(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: _review_template_json_value(row.get(field))
        for field in REVIEW_TEMPLATE_FIELDS
    }


def _review_template_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _review_template_json_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_review_template_json_value(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def _review_template_csv_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(_review_template_json_value(value), sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _parse_csv_row(row: Mapping[str, str]) -> dict[str, Any]:
    return {key: _parse_csv_cell(value) for key, value in row.items()}


def _parse_csv_cell(value: str | None) -> Any:
    if value is None or value == "":
        return None
    raw = value.strip()
    if raw in {"True", "true"}:
        return True
    if raw in {"False", "false"}:
        return False
    if raw.startswith(("{", "[")):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return value
    try:
        if any(ch in raw for ch in (".", "e", "E")):
            return float(raw)
        return int(raw)
    except ValueError:
        return value


def _sample_key(row: Mapping[str, Any]) -> tuple[str, str, str] | None:
    event_id = str(row.get("event_id") or "").strip()
    coin_id = str(row.get("asset_coin_id") or "").strip().casefold()
    relationship = str(row.get("relationship_type") or "").strip().casefold()
    if event_id and coin_id and relationship:
        return (event_id, coin_id, relationship)
    event_name = str(row.get("event_name") or "").strip().casefold()
    symbol = str(row.get("asset_symbol") or "").strip().casefold()
    if event_name and symbol and relationship:
        return (event_name, symbol, relationship)
    return None


def _review_template_issue(
    row: Mapping[str, Any],
    row_index: int,
    *,
    category: str,
    message: str,
    missing_fields: tuple[str, ...] = (),
    changed_fields: tuple[str, ...] = (),
) -> ValidationReviewTemplateIssue:
    return ValidationReviewTemplateIssue(
        row_index=row_index,
        category=category,
        event_id=str(row.get("event_id") or ""),
        asset_symbol=str(row.get("asset_symbol") or ""),
        asset_coin_id=str(row.get("asset_coin_id") or ""),
        relationship_type=str(row.get("relationship_type") or ""),
        message=message,
        missing_fields=missing_fields,
        changed_fields=changed_fields,
    )


def _has_review_data(row: Mapping[str, Any]) -> bool:
    return any(_has_value(row.get(field)) for field in REVIEW_FIELDS)


def _missing_review_provenance_fields(row: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(field for field in REVIEW_PROVENANCE_FIELDS if not _has_value(row.get(field)))
