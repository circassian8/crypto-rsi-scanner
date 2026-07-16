"""Evidence-reality presentation helpers for the Decision Radar dashboard."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from ..radar import catalyst_attribution as event_catalyst_attribution
from ..radar import source_independence as event_source_independence
from .presentation import humanize_enum, humanize_reason


DefinitionGrid = Callable[[Iterable[tuple[str, object]]], str]
StatusBadge = Callable[[object], str]


def render_evidence_verdict(
    row: Mapping[str, Any],
    *,
    definition_grid: DefinitionGrid,
    status_badge: StatusBadge,
) -> str:
    """Render the compact operator verdict without exposing full contracts."""

    independence = validated_source_independence(row)
    attribution = validated_catalyst_attribution(row)
    raw_count = _count_value(independence.get("raw_document_count"))
    if raw_count is None:
        raw_count = _first_count(row, "source_update_count", "source_count")
    accepted_count = _first_count(
        row,
        "evidence_acquisition_accepted_count",
        "accepted_evidence_count",
    )
    assessed = bool(independence)
    metrics = (
        ("Raw sources", _count_label(raw_count, unavailable="Unavailable")),
        (
            "Accepted evidence rows (not corroboration)",
            _count_label(accepted_count),
        ),
        (
            "Content clusters",
            _count_label(
                _count_value(independence.get("content_cluster_count"))
                if assessed
                else None
            ),
        ),
        (
            "Independent evidence units",
            _count_label(
                _count_value(independence.get("independent_evidence_count"))
                if assessed
                else None
            ),
        ),
        (
            "Additional independent corroborations",
            _count_label(
                _count_value(independence.get("independent_corroboration_count"))
                if assessed
                else None
            ),
        ),
        (
            "Syndicated copies collapsed",
            _count_label(_collapsed_copy_count(independence) if assessed else None),
        ),
        ("Catalyst timing", _catalyst_timing_label(attribution)),
        ("Causal eligibility", _causal_eligibility_label(attribution)),
        ("Source authority", _source_authority_label(attribution)),
        (
            "Evidence errors",
            _bounded_evidence_errors(
                row,
                source_independence=independence,
                attribution=attribution,
            ),
        ),
    )
    return (
        '<section class="panel evidence-verdict"><div class="section-heading"><div>'
        '<p class="eyebrow">Evidence reality</p><h2>Evidence verdict</h2></div>'
        f'{status_badge("assessed" if assessed else "unassessed")}</div>'
        '<p>Accepted evidence is a validation count, not independent corroboration. '
        'Only validated content-and-origin units raise the corroboration count.</p>'
        + definition_grid(metrics)
        + '</section>'
    )


def validated_source_independence(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the validated source-independence contract, if supplied."""

    return event_source_independence.validated_source_independence_container(row)


def validated_catalyst_attribution(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the first valid catalyst-attribution contract, if supplied."""

    if (
        row.get("catalyst_attribution_rejected") is True
        or _values(row, "catalyst_attribution_rejection_reasons")
    ):
        return {}
    supplied: list[Mapping[str, Any]] = []
    single = row.get("catalyst_attribution")
    if single not in (None, "", {}, []):
        if not isinstance(single, Mapping):
            return {}
        supplied.append(single)
    multiple = row.get("catalyst_attributions")
    if multiple not in (None, "", {}, []):
        if not isinstance(multiple, Iterable) or isinstance(
            multiple, (str, bytes, Mapping)
        ):
            return {}
        for value in multiple:
            if not isinstance(value, Mapping):
                return {}
            supplied.append(value)
    if not supplied or any(
        event_catalyst_attribution.validate_contract(value) for value in supplied
    ):
        return {}
    return dict(supplied[0])


def _collapsed_copy_count(contract: Mapping[str, Any]) -> int:
    documents = contract.get("documents")
    if not isinstance(documents, list):
        return 0
    return sum(
        1
        for document in documents
        if isinstance(document, Mapping)
        and document.get("match_kind") in {"exact", "near_duplicate"}
    )


def _catalyst_timing_label(attribution: Mapping[str, Any]) -> str:
    return humanize_enum(attribution.get("temporal_relation") or "not_assessed")


def _causal_eligibility_label(attribution: Mapping[str, Any]) -> str:
    if not attribution:
        return "Not assessed"
    if attribution.get("causal_eligible") is True:
        return "Eligible"
    if attribution.get("evidence_use") == "disproof":
        return "Disproof"
    return "Context only"


def _source_authority_label(attribution: Mapping[str, Any]) -> str:
    if not attribution:
        return "Unassessed"
    source_class = str(attribution.get("source_class") or "").casefold()
    if attribution.get("source_authority_verified") is True:
        if source_class.startswith("official_"):
            return "Official"
        if source_class.startswith("structured_"):
            return "Structured"
    return "Context"


def _bounded_evidence_errors(
    row: Mapping[str, Any],
    *,
    source_independence: Mapping[str, Any],
    attribution: Mapping[str, Any],
) -> str:
    values = [
        *_values(row, "source_independence_errors"),
        *_values(row, "catalyst_attribution_rejection_reasons"),
    ]
    if (
        not source_independence
        and row.get("source_independence") not in (None, "", {}, [])
        and not _values(row, "source_independence_errors")
        and "source_independence_invalid" not in values
    ):
        values.append("source_independence_invalid")
    if (
        not attribution
        and (
            row.get("catalyst_attribution") not in (None, "", {}, [])
            or row.get("catalyst_attributions") not in (None, "", {}, [])
        )
        and "catalyst_attribution_invalid" not in values
    ):
        values.append("catalyst_attribution_invalid")
    clean = [humanize_reason(" ".join(value.split())[:160]) for value in values]
    if not clean:
        return "No errors recorded"
    visible = clean[:4]
    hidden = len(clean) - len(visible)
    return "; ".join(visible) + (f"; +{hidden} more" if hidden else "")


def _count_value(value: object) -> int | None:
    if type(value) is int and value >= 0:
        return value
    return None


def _first_count(row: Mapping[str, Any], *fields: str) -> int | None:
    for field in fields:
        value = _count_value(row.get(field))
        if value is not None:
            return value
    return None


def _count_label(value: int | None, *, unavailable: str = "Not assessed") -> str:
    return str(value) if value is not None else unavailable


def _values(row: Mapping[str, Any], *fields: str) -> tuple[str, ...]:
    out: list[str] = []
    for field in fields:
        value = row.get(field)
        if isinstance(value, str):
            if value.strip():
                out.append(value.strip())
        elif isinstance(value, Iterable) and not isinstance(
            value, (str, bytes, Mapping)
        ):
            out.extend(str(item).strip() for item in value if str(item).strip())
    return tuple(dict.fromkeys(out))
