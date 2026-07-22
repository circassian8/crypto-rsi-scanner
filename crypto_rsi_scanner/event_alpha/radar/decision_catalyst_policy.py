"""Causal catalyst policy for the trader-facing Decision model.

Historical rows without a closed attribution retain the v2 compatibility
heuristic. Once a row supplies the newer attribution contract, malformed,
retrospective, and context-only evidence fails closed for causal confidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from . import catalyst_attribution as event_catalyst_attribution
from .decision_models import CatalystStatus


_SOURCE_URL_FIELDS = ("latest_source_url", "source_url", "url")
_SOURCE_TITLE_FIELDS = (
    "latest_source_title",
    "source_title",
    "title",
    "event_name",
)
_ATTRIBUTION_SOURCE_ID_FIELDS = (
    "raw_id",
    "source_event_id",
    "official_exchange_event_id",
    "event_id",
)
_STRUCTURED_SOURCE_FIELDS = (
    "official_exchange_event",
    "scheduled_catalyst_event",
    "unlock_event",
)
_CATALYST_BOOLEAN_FIELDS = (
    "catalyst_disproven",
    "catalyst_not_required",
    "catalyst_attribution_rejected",
)
_SOURCE_LANE_SPLIT = re.compile(r"[^a-z0-9]+")
_CATALYST_SOURCE_LANE_TOKENS = (
    "official_exchange",
    "official_project",
    "scheduled_catalyst",
    "structured_calendar",
    "structured_unlock",
    "unlock",
    "news",
    "cryptopanic",
    "gdelt",
    "rss",
    "project_blog",
    "regulatory",
    "external_catalyst",
    "prediction_market",
)


def catalyst_status(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...],
) -> str:
    explicit = _typed_text(data.get("catalyst_status")).casefold()
    text_values = _row_text_values(data, sources)
    attributions, attribution_invalid, attribution_supplied = (
        _catalyst_attribution_values(data, sources)
    )
    structured_disproof = explicit == CatalystStatus.DISPROVEN.value or any(
        _truthy(row.get("catalyst_disproven"))
        or str(row.get("cause_status") or "").strip().casefold() == "ruled_out"
        for row in (data, *sources)
    ) or any(
        str(row.get("evidence_use") or "").strip().casefold() == "disproof"
        for row in attributions
    )
    if structured_disproof or any(
        _text_has_unnegated_components(value, term)
        for value in text_values
        for term in ("source correction", "official denial", "catalyst_disproven")
    ):
        return CatalystStatus.DISPROVEN.value
    if attribution_supplied and (
        attribution_invalid
        or not any(row.get("causal_eligible") is True for row in attributions)
    ):
        return (
            CatalystStatus.NOT_REQUIRED.value
            if explicit == CatalystStatus.NOT_REQUIRED.value
            else CatalystStatus.UNKNOWN.value
        )
    if explicit in {item.value for item in CatalystStatus}:
        return explicit
    evidence_rows = (data, *sources)
    source_evidence = _source_evidence_rows(data, sources)
    official_with_evidence = any(
        _row_is_official_source(row)
        and (
            (_count(row.get("accepted_evidence_count")) or 0) > 0
            or _valid_structured_source_event(row.get("official_exchange_event"))
        )
        for row in evidence_rows
    )
    catalyst_specific_with_evidence = any(
        _has_catalyst_source_lane(lane_values)
        and (
            (_count(row.get("accepted_evidence_count")) or 0) > 0
            or bool(catalyst_source_fields(row)[0])
        )
        for row, lane_values in source_evidence
    )
    if official_with_evidence:
        return CatalystStatus.CONFIRMED.value
    if catalyst_specific_with_evidence:
        return CatalystStatus.PLAUSIBLE.value
    if _truthy(data.get("catalyst_not_required")):
        return CatalystStatus.NOT_REQUIRED.value
    return CatalystStatus.UNKNOWN.value


def catalyst_source_fields(data: Mapping[str, Any]) -> tuple[str, str]:
    """Return typed, public source URL/title evidence with fixed precedence."""

    owners: list[Mapping[str, Any]] = [data]
    owners.extend(
        value
        for field in _STRUCTURED_SOURCE_FIELDS
        if isinstance((value := data.get(field)), Mapping) and value
    )
    url = _first_valid_source_url(owners)
    title = _first_source_title(owners)
    return url, title


def catalyst_source_evidence_invalid(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...] = (),
) -> bool:
    """Detect malformed explicit source URL/title or structured-event claims."""

    for row in (data, *sources):
        if _row_source_fields_invalid(row):
            return True
        for field in _STRUCTURED_SOURCE_FIELDS:
            if field not in row or row.get(field) in (None, ""):
                continue
            nested = row.get(field)
            if not isinstance(nested, Mapping) or not nested:
                return True
            if _row_source_fields_invalid(nested):
                return True
    return False


def catalyst_state_claims_invalid(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...] = (),
) -> bool:
    """Detect malformed explicit catalyst status, count, and control claims."""

    allowed_statuses = {item.value for item in CatalystStatus}
    for row in (data, *sources):
        if "catalyst_status" in row and row.get("catalyst_status") not in (None, ""):
            status = _typed_text(row.get("catalyst_status")).casefold()
            if status not in allowed_statuses:
                return True
        for field in ("cause_status", "source_strength"):
            if (
                field in row
                and row.get(field) not in (None, "")
                and not _typed_text(row.get(field))
            ):
                return True
        if (
            "accepted_evidence_count" in row
            and row.get("accepted_evidence_count") not in (None, "")
            and _count(row.get("accepted_evidence_count")) is None
        ):
            return True
        for field in _CATALYST_BOOLEAN_FIELDS:
            if field not in row or row.get(field) in (None, ""):
                continue
            if _semantic_boolean(row.get(field)) is None:
                return True
    return False


def attribution_warning(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...],
) -> str | None:
    values, invalid, supplied = _catalyst_attribution_values(data, sources)
    if invalid:
        return (
            "Catalyst attribution evidence failed its closed contract; it was "
            "excluded from causal catalyst confidence."
        )
    if supplied and values and not any(
        row.get("causal_eligible") is True for row in values
    ):
        return (
            "Catalyst evidence is retrospective or contextual, not antecedent "
            "causal confirmation for this market observation."
        )
    return None


def attribution_values(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...] = (),
) -> tuple[dict[str, Any], ...]:
    """Expose the validated, deduplicated copy set for canonical projection."""

    values, invalid, supplied = _catalyst_attribution_values(data, sources)
    if invalid or not supplied:
        return ()
    return tuple(dict(row) for row in values)


def evidence_owner_rows(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...] = (),
) -> tuple[tuple[dict[str, Any], ...], bool]:
    """Return source-owned catalyst evidence and closed-contract authority.

    The boolean is true when a supplied catalyst-attribution contract controls
    the result.  In that case invalid or non-causal attributions deliberately
    return no owners instead of falling back to historical flattened hints.
    """

    attributions, attribution_invalid, attribution_supplied = (
        _catalyst_attribution_values(data, sources)
    )
    source_rows = (data, *sources)
    if attribution_supplied:
        if attribution_invalid:
            return (), True
        return (
            tuple(
                _attribution_evidence_owner(row, source_rows)
                for row in attributions
                if row.get("causal_eligible") is True
            ),
            True,
        )

    owners: list[dict[str, Any]] = []
    for row, lane_values in _source_evidence_rows(data, sources):
        accepted = (_count(row.get("accepted_evidence_count")) or 0) > 0
        structured = _valid_structured_source_event(
            row.get("official_exchange_event")
        )
        has_public_url = bool(catalyst_source_fields(row)[0])
        if (
            (_row_is_official_source(row) and (accepted or structured))
            or (
                _has_catalyst_source_lane(lane_values)
                and (accepted or has_public_url)
            )
        ):
            owners.append(dict(row))
    return tuple(owners), False


def evidence_owner_catalyst_status(row: Mapping[str, Any]) -> str:
    """Return the positive catalyst status this source row proves by itself."""

    accepted = (_count(row.get("accepted_evidence_count")) or 0) > 0
    structured = _valid_structured_source_event(
        row.get("official_exchange_event")
    )
    if _row_is_official_source(row) and (accepted or structured):
        return CatalystStatus.CONFIRMED.value
    lane_values = (
        *_texts(row.get("_source_origin")),
        *_texts(row.get("source_origin")),
        *_texts(row.get("source_origins")),
        *_texts(row.get("source_class")),
        *_texts(row.get("source_pack")),
    )
    if _has_catalyst_source_lane(lane_values) and (
        accepted or bool(catalyst_source_fields(row)[0])
    ):
        return CatalystStatus.PLAUSIBLE.value
    return CatalystStatus.UNKNOWN.value


def _catalyst_attribution_values(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...],
) -> tuple[tuple[Mapping[str, Any], ...], bool, bool]:
    supplied = False
    invalid = False
    values: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    candidate_anomaly_ids = _candidate_anomaly_ids(data)
    candidate_anomaly_observed_at = _candidate_anomaly_observed_at(data)
    for source in (data, *sources):
        if _truthy(source.get("catalyst_attribution_rejected")):
            supplied = True
            invalid = True
        containers: list[object] = []
        for owner in (source, _mapping(source.get("decision_projection"))):
            for field in ("catalyst_attribution", "catalyst_attributions"):
                if field not in owner:
                    continue
                raw = owner.get(field)
                if field == "catalyst_attribution":
                    supplied = True
                    containers.append(raw)
                elif isinstance(raw, (list, tuple)):
                    if not raw:
                        continue
                    supplied = True
                    containers.extend(raw)
                else:
                    supplied = True
                    invalid = True
        for raw in containers:
            if not isinstance(raw, Mapping):
                invalid = True
                continue
            row = dict(raw)
            if event_catalyst_attribution.validate_contract(row):
                invalid = True
                continue
            if (
                not candidate_anomaly_ids
                or str(row.get("anomaly_id") or "") not in candidate_anomaly_ids
            ):
                invalid = True
                continue
            if row.get("causal_eligible") is True and not _causal_clock_matches(
                row,
                candidate_anomaly_observed_at,
            ):
                invalid = True
                continue
            identity = str(row.get("attribution_digest") or row.get("digest") or "")
            if not identity:
                invalid = True
                continue
            if identity in seen:
                continue
            seen.add(identity)
            values.append(row)
    return tuple(values), invalid, supplied


def _candidate_anomaly_ids(data: Mapping[str, Any]) -> set[str]:
    explicit = {
        str(value).strip()
        for field in ("market_anomaly_id", "anomaly_raw_id")
        for value in (data.get(field),)
        if str(value or "").strip()
    }
    if explicit:
        return explicit
    projection = _mapping(data.get("decision_projection"))
    values = (
        *_texts(data.get("observation_ids")),
        *_texts(projection.get("observation_ids")),
        str(data.get("candidate_id") or ""),
        str(data.get("observation_id") or ""),
    )
    return {value.strip() for value in values if value.strip()}


def _candidate_anomaly_observed_at(
    data: Mapping[str, Any],
) -> datetime | None:
    """Resolve the exact candidate clock used by the attribution builder."""

    for owner, fields in (
        (
            data,
            (
                "observed_at",
                "market_context_observed_at",
                "published_at",
                "fetched_at",
                "anomaly_observed_at",
            ),
        ),
        (
            _mapping(data.get("market_state_snapshot")),
            ("observed_at", "timestamp"),
        ),
    ):
        for field in fields:
            parsed = _parse_aware_time(owner.get(field))
            if parsed is not None:
                return parsed
    return _closed_projection_causal_clock(data)


def _closed_projection_causal_clock(
    data: Mapping[str, Any],
) -> datetime | None:
    """Recover the clock from an older closed projection for idempotence.

    Current projections persist ``anomaly_observed_at`` explicitly.  Earlier
    closed projections already contain a digest-validated attribution but no
    top-level copy of that clock; only those schema-marked projections may use
    the unique causal attribution clock as their self-validating fallback.
    """

    for owner in (data, _mapping(data.get("decision_projection"))):
        if (
            not _typed_text(owner.get("decision_projection_schema_version"))
            or not isinstance(owner.get("observation_ids"), (list, tuple))
            or not owner.get("observation_ids")
            or _parse_aware_time(owner.get("decision_evaluated_at")) is None
            or not isinstance(owner.get("decision_safety_invariants"), Mapping)
        ):
            continue
        raw_values: list[object] = []
        single = owner.get("catalyst_attribution")
        if single is not None:
            raw_values.append(single)
        multiple = owner.get("catalyst_attributions")
        if isinstance(multiple, (list, tuple)):
            raw_values.extend(multiple)
        clocks = {
            parsed
            for value in raw_values
            if isinstance(value, Mapping)
            and value.get("causal_eligible") is True
            and (parsed := _parse_aware_time(value.get("anomaly_observed_at")))
            is not None
        }
        if len(clocks) == 1:
            return next(iter(clocks))
    return None


def _causal_clock_matches(
    attribution: Mapping[str, Any],
    candidate_observed_at: datetime | None,
) -> bool:
    """Keep causal confidence bound to one point-in-time anomaly episode."""

    attribution_observed_at = _parse_aware_time(
        attribution.get("anomaly_observed_at")
    )
    return bool(
        attribution_observed_at is not None
        and candidate_observed_at is not None
        and attribution_observed_at == candidate_observed_at
    )


def _source_evidence_rows(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...],
) -> tuple[tuple[Mapping[str, Any], tuple[str, ...]], ...]:
    return (
        (
            data,
            (
                *_texts(data.get("source_origin")),
                *_texts(data.get("source_origins")),
                *_texts(data.get("source_class")),
                *_texts(data.get("source_pack")),
            ),
        ),
        *(
            (
                row,
                (
                    str(row.get("_source_origin") or ""),
                    str(row.get("source_class") or ""),
                    str(row.get("source_pack") or ""),
                ),
            )
            for row in sources
        ),
    )


def _attribution_evidence_owner(
    attribution: Mapping[str, Any],
    source_rows: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    attribution_values = {
        key: value
        for key, value in attribution.items()
        if value not in (None, "")
    }
    attribution_url = catalyst_source_fields(attribution)[0]
    if attribution_url:
        url_matches = tuple(
            source
            for source in source_rows
            if catalyst_source_fields(source)[0] == attribution_url
        )
        identity_matches = tuple(
            source
            for source in url_matches
            if _source_row_attribution_identity_match(source, attribution) is True
        )
        if len(identity_matches) == 1:
            return {**dict(identity_matches[0]), **attribution_values}
        if not identity_matches:
            compatibility_matches = tuple(
                source
                for source in url_matches
                if _source_row_attribution_identity_match(source, attribution) is None
            )
            if len(compatibility_matches) == 1:
                return {**dict(compatibility_matches[0]), **attribution_values}
    return dict(attribution_values)


def _source_row_attribution_identity_match(
    source: Mapping[str, Any],
    attribution: Mapping[str, Any],
) -> bool | None:
    """Return exact match, mismatch, or legacy-unavailable identity state."""

    if any(
        field in source
        and source.get(field) not in (None, "")
        and not _typed_text(source.get(field))
        for field in (*_ATTRIBUTION_SOURCE_ID_FIELDS, "source_content_hash")
    ):
        return False
    source_ids = {
        value
        for field in _ATTRIBUTION_SOURCE_ID_FIELDS
        if (value := _typed_text(source.get(field)))
    }
    source_hashes = {
        value.casefold()
        for value in (_typed_text(source.get("source_content_hash")),)
        if value
    }
    source_row_typed = bool(
        source_ids
        or _typed_text(source.get("row_type"))
        or _typed_text(source.get("_source_origin"))
    )
    if source_row_typed:
        if (
            "content_hash" in source
            and source.get("content_hash") not in (None, "")
            and not _typed_text(source.get("content_hash"))
        ):
            return False
        if content_hash := _typed_text(source.get("content_hash")):
            source_hashes.add(content_hash.casefold())
    attribution_id = _typed_text(attribution.get("source_id"))
    attribution_hash = _typed_text(attribution.get("source_content_hash")).casefold()
    compared = False
    if source_ids:
        compared = True
        if attribution_id not in source_ids:
            return False
    if source_hashes:
        compared = True
        if attribution_hash not in source_hashes:
            return False
    return True if compared else None


def _row_text_values(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...],
) -> tuple[str, ...]:
    values: list[str] = []
    for row in (data, *sources):
        for key in (
            "source_class",
            "source_pack",
            "source_strength",
            "event_type",
            "title",
            "event_name",
            "reason_codes",
            "warnings",
        ):
            values.extend(_texts(row.get(key)))
    return tuple(values)


def _source_lane_has_token(value: str, token: str) -> bool:
    """Match a canonical lane token on normalized component boundaries."""

    value_parts = _component_parts(value)
    token_parts = _component_parts(token)
    width = len(token_parts)
    return bool(
        width
        and any(
            value_parts[index : index + width] == token_parts
            for index in range(len(value_parts) - width + 1)
        )
    )


def _text_has_unnegated_components(value: str, phrase: str) -> bool:
    value_parts = _component_parts(value)
    phrase_parts = _component_parts(phrase)
    width = len(phrase_parts)
    if not width:
        return False
    for index in range(len(value_parts) - width + 1):
        if value_parts[index : index + width] != phrase_parts:
            continue
        if index and value_parts[index - 1] in {"no", "non", "not", "without"}:
            continue
        return True
    return False


def _component_parts(value: str) -> tuple[str, ...]:
    return tuple(
        part for part in _SOURCE_LANE_SPLIT.split(value.casefold()) if part
    )


def _has_catalyst_source_lane(values: tuple[str, ...]) -> bool:
    return any(
        _source_lane_has_token(value, token)
        for value in values
        for token in _CATALYST_SOURCE_LANE_TOKENS
    )


def _row_is_official_source(row: Mapping[str, Any]) -> bool:
    return bool(
        _valid_structured_source_event(row.get("official_exchange_event"))
        or _typed_text(row.get("source_class")).casefold()
        in {
            "official_exchange",
            "official_project",
            "structured_calendar",
            "structured_unlock",
        }
        or _typed_text(row.get("source_strength")).casefold() == "official_structured"
    )


def _count(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        parsed = int(value)
        return parsed if parsed >= 0 else None
    return None


def _row_source_fields_invalid(row: Mapping[str, Any]) -> bool:
    for field in _SOURCE_URL_FIELDS:
        if field not in row or row.get(field) in (None, ""):
            continue
        if not _valid_public_source_url(row.get(field)):
            return True
    for field in _SOURCE_TITLE_FIELDS:
        if field not in row or row.get(field) in (None, ""):
            continue
        if not _typed_text(row.get(field)):
            return True
    return False


def _valid_structured_source_event(value: object) -> bool:
    if not isinstance(value, Mapping) or not value:
        return False
    return bool(_first_valid_source_url((value,)))


def _first_valid_source_url(owners: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]]) -> str:
    for owner in owners:
        for field in _SOURCE_URL_FIELDS:
            if field not in owner or owner.get(field) in (None, ""):
                continue
            value = owner.get(field)
            return value.strip() if _valid_public_source_url(value) else ""
    return ""


def _first_source_title(owners: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]]) -> str:
    for owner in owners:
        for field in _SOURCE_TITLE_FIELDS:
            if field not in owner or owner.get(field) in (None, ""):
                continue
            return _typed_text(owner.get(field))
    return ""


def _valid_public_source_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or any(character.isspace() for character in text):
        return False
    try:
        parsed = urlsplit(text)
        hostname = parsed.hostname
    except ValueError:
        return False
    return bool(
        parsed.scheme.casefold() in {"http", "https"}
        and parsed.netloc
        and hostname
        and parsed.username is None
        and parsed.password is None
    )


def _typed_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _parse_aware_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _truthy(value: object) -> bool:
    return _semantic_boolean(value) is True


def _semantic_boolean(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        if float(value) == 1.0:
            return True
        if float(value) == 0.0:
            return False
        return None
    if isinstance(value, str):
        text = value.strip().casefold()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
    return None


def _texts(value: object) -> list[str]:
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [str(key) for key, enabled in value.items() if enabled]
    try:
        return [str(item) for item in value if str(item or "")]  # type: ignore[union-attr]
    except TypeError:
        return [str(value)]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


__all__ = (
    "attribution_values",
    "attribution_warning",
    "catalyst_state_claims_invalid",
    "catalyst_source_evidence_invalid",
    "catalyst_source_fields",
    "catalyst_status",
    "evidence_owner_catalyst_status",
    "evidence_owner_rows",
)
