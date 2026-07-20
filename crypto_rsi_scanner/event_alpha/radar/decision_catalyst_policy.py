"""Causal catalyst policy for the trader-facing Decision model.

Historical rows without a closed attribution retain the v2 compatibility
heuristic. Once a row supplies the newer attribution contract, malformed,
retrospective, and context-only evidence fails closed for causal confidence.
"""

from __future__ import annotations

import math
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


def catalyst_status(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...],
) -> str:
    explicit = _typed_text(data.get("catalyst_status")).casefold()
    source_url, _source_title = catalyst_source_fields(data)
    text = _row_text(data, sources)
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
        term in text
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
    official = any(
        _valid_structured_source_event(row.get("official_exchange_event"))
        or _typed_text(row.get("source_class"))
        in {
            "official_exchange",
            "official_project",
            "structured_calendar",
            "structured_unlock",
        }
        or _typed_text(row.get("source_strength")) == "official_structured"
        for row in evidence_rows
    )
    accepted = sum(
        _count(row.get("accepted_evidence_count")) or 0
        for row in evidence_rows
    )
    source_lane_text = " ".join(
        (
            *_texts(data.get("source_origin")),
            *_texts(data.get("source_origins")),
            *_texts(data.get("source_class")),
            *_texts(data.get("source_pack")),
            *(str(row.get("_source_origin") or "") for row in sources),
            *(str(row.get("source_class") or "") for row in sources),
            *(str(row.get("source_pack") or "") for row in sources),
        )
    ).casefold()
    catalyst_specific_source = any(
        token in source_lane_text
        for token in (
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
    )
    if official and (
        accepted > 0
        or any(
            _valid_structured_source_event(row.get("official_exchange_event"))
            for row in evidence_rows
        )
    ):
        return CatalystStatus.CONFIRMED.value
    if (accepted > 0 and catalyst_specific_source) or (
        source_url and catalyst_specific_source
    ):
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


def _catalyst_attribution_values(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...],
) -> tuple[tuple[Mapping[str, Any], ...], bool, bool]:
    supplied = False
    invalid = False
    values: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    candidate_anomaly_ids = _candidate_anomaly_ids(data)
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


def _row_text(
    data: Mapping[str, Any],
    sources: tuple[Mapping[str, Any], ...],
) -> str:
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
    return " ".join(values).casefold()


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
)
