"""Pure exact-generation coverage projection for dashboard product layers.

The dashboard must not infer a healthy empty result from a missing artifact.
This module closes the small collection of exact read-model inputs already
loaded into :class:`DashboardSnapshot` into one operator-facing coverage
contract.  It performs no discovery, provider calls, or writes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from .models import DashboardSnapshot


HEALTHY_STATUSES = frozenset(
    {"healthy_nonempty", "healthy_empty", "not_applicable"}
)
LAYER_ORDER = (
    "market",
    "catalyst",
    "calendar",
    "derivatives",
    "rsi",
    "outcomes",
    "request_ledger",
)

_CATALYST_SIDECARS = frozenset(
    {"official_exchange", "scheduled_catalyst", "unlock"}
)
_DERIVATIVES_SIDECARS = frozenset(
    {
        "derivatives",
        "coinalyze",
        "coinalyze_derivatives_state",
        "coinalyze_derivatives_crowding",
    }
)
_RSI_SIDECARS = frozenset({"rsi_signal_context"})
_CATALYST_PACK_MARKERS = (
    "exchange",
    "listing",
    "perp",
    "preipo",
    "investment",
    "security_shock",
    "fan_sports",
    "unlock_supply",
)
_EXPLICIT_HEALTHY_EMPTY = frozenset(
    {
        "complete",
        "completed_empty",
        "healthy_empty",
        "loaded_existing_empty",
        "loaded_local_read_only_empty",
        "observed_healthy",
        "observed_no_results",
    }
)
_EXPLICIT_HEALTHY_NONEMPTY = frozenset(
    {
        "healthy_nonempty",
        "loaded_existing",
        "loaded_local_read_only",
        "observed",
        "usable",
    }
)


@dataclass(frozen=True)
class DashboardLayerCoverage:
    """One closed operator-facing layer assessment."""

    key: str
    label: str
    status: str
    expected: bool
    row_count: int
    detail: str
    reasons: tuple[str, ...] = ()

    @property
    def action_required(self) -> bool:
        return self.expected and self.status not in HEALTHY_STATUSES


def dashboard_layer_coverage(
    snapshot: DashboardSnapshot,
) -> tuple[DashboardLayerCoverage, ...]:
    """Project every dashboard product layer from one exact snapshot."""

    rows = (
        _market_coverage(snapshot),
        _catalyst_coverage(snapshot),
        _calendar_coverage(snapshot),
        _sidecar_coverage(
            snapshot,
            key="derivatives",
            label="Derivatives context",
            names=_DERIVATIVES_SIDECARS,
            candidate_context_fields=("derivatives_snapshot", "derivatives_state_snapshot"),
        ),
        _sidecar_coverage(
            snapshot,
            key="rsi",
            label="RSI context",
            names=_RSI_SIDECARS,
            candidate_context_fields=("rsi_context",),
        ),
        _outcome_coverage(snapshot),
        _request_ledger_coverage(snapshot),
    )
    if not snapshot.generation_authoritative:
        reasons = (
            *snapshot.generation_authority_reasons,
            "generation_authority_failed",
        )
        rows = tuple(
            DashboardLayerCoverage(
                key=row.key,
                label=row.label,
                status="rejected",
                expected=True,
                row_count=0,
                detail=(
                    "Current layer data is suppressed because the exact generation is not "
                    "authoritative; no underlying row count or healthy-state claim is exposed."
                ),
                reasons=tuple(dict.fromkeys(reasons)),
            )
            for row in rows
        )
    return tuple(sorted(rows, key=lambda row: LAYER_ORDER.index(row.key)))


def dashboard_layer_coverage_by_key(
    snapshot: DashboardSnapshot,
) -> dict[str, DashboardLayerCoverage]:
    """Return the canonical projection keyed by stable layer identifier."""

    return {row.key: row for row in dashboard_layer_coverage(snapshot)}


def _market_coverage(snapshot: DashboardSnapshot) -> DashboardLayerCoverage:
    rows = tuple(snapshot.current_market_observations)
    if rows:
        freshness = {_token(row.get("freshness_status")) or "unknown" for row in rows}
        if freshness and freshness <= {"stale", "expired"}:
            return _layer(
                "market",
                "Market observations",
                "stale",
                len(rows),
                "All exact market observations are stale; current market coverage is not usable.",
                reasons=tuple(sorted(freshness)),
            )
        if freshness & {"stale", "expired", "unknown"}:
            return _layer(
                "market",
                "Market observations",
                "degraded",
                len(rows),
                "Exact market observations are present, but freshness coverage is mixed or unknown.",
                reasons=tuple(sorted(freshness)),
            )
        return _layer(
            "market",
            "Market observations",
            "healthy_nonempty",
            len(rows),
            "Exact fingerprint-bound market observations are present for this generation.",
        )

    generation = snapshot.market_generation
    ledger = snapshot.current_request_ledger
    tokens = _tokens(
        generation.get("status"),
        generation.get("cadence_status"),
        ledger.get("status"),
        ledger.get("error_class"),
    )
    mode = _token(
        generation.get("candidate_source_mode") or generation.get("data_mode")
    )
    selected = _count(
        generation.get("selected_market_row_count")
        if generation.get("selected_market_row_count") is not None
        else ledger.get("selected_market_row_count")
    )
    succeeded = (
        ledger.get("provider_request_succeeded") is True
        or generation.get("provider_request_succeeded") is True
    )
    if _contains(tokens, "reject", "invalid"):
        return _layer(
            "market",
            "Market observations",
            "rejected",
            0,
            "Market acquisition evidence was rejected; zero observations is not a healthy empty result.",
            reasons=tokens,
        )
    if _contains(tokens, "stale", "expired"):
        return _layer(
            "market",
            "Market observations",
            "stale",
            0,
            "Market acquisition evidence is stale; zero observations cannot be treated as current coverage.",
            reasons=tokens,
        )
    if selected == 0 and (
        succeeded
        or (
            _token(generation.get("status")) in {"complete", "completed"}
            and mode in {"fixture", "mock", "mock_fixture", "artifact_replay"}
        )
    ):
        return _layer(
            "market",
            "Market observations",
            "healthy_empty",
            0,
            "The exact provider request completed successfully and selected zero in-scope market rows.",
        )
    if _contains(tokens, "degraded", "partial", "backoff", "rate_limit"):
        return _layer(
            "market",
            "Market observations",
            "degraded",
            0,
            "Market acquisition was partial or degraded; zero rows does not prove an empty market layer.",
            reasons=tokens,
        )
    if generation.get("live_provider_authorized") is False:
        return _layer(
            "market",
            "Market observations",
            "not_configured",
            0,
            "Live-safe market acquisition is not authorized for this generation.",
        )
    return _layer(
        "market",
        "Market observations",
        "unavailable",
        0,
        "No exact market observations or complete healthy-empty acquisition receipt is attached.",
        reasons=tokens,
    )


def _catalyst_coverage(snapshot: DashboardSnapshot) -> DashboardLayerCoverage:
    packs = tuple(
        row
        for row in _source_pack_rows(snapshot)
        if any(marker in _token(row.get("source_pack")) for marker in _CATALYST_PACK_MARKERS)
    )
    sidecars = _manifest_rows(snapshot, _CATALYST_SIDECARS)
    assessments = [*(_pack_assessment(row) for row in packs), *(_manifest_assessment(row) for row in sidecars)]
    row_count = sum(_accepted_count(row) for row in packs)
    candidate_count = sum(
        1
        for row in snapshot.current_candidates
        if "catalyst_led" in _origin_tokens(row)
    )
    row_count = max(row_count, candidate_count)
    return _combined_coverage(
        key="catalyst",
        label="Catalyst context",
        assessments=assessments,
        row_count=row_count,
        absent_detail=(
            "No exact source-pack or input-manifest assessment is attached for catalyst coverage."
        ),
    )


def _calendar_coverage(snapshot: DashboardSnapshot) -> DashboardLayerCoverage:
    rows = tuple(snapshot.current_calendar_events)
    raw = snapshot.market_generation.get("calendar_snapshot")
    metadata = raw if isinstance(raw, Mapping) else {}
    rejected = _count(metadata.get("normalization_rejected_count")) or 0
    tokens = _tokens(
        metadata.get("normalization_status"),
        metadata.get("status"),
        metadata.get("error_class"),
        metadata.get("error"),
    )
    if rows and rejected:
        return _layer(
            "calendar",
            "Calendar coverage",
            "degraded",
            len(rows),
            "Exact calendar rows are present, but some source rows were rejected during normalization.",
            reasons=(*tokens, f"normalization_rejected_count={rejected}"),
        )
    if rows and _contains(tokens, "reject", "invalid", "stale", "expired", "unavailable", "failed"):
        return _layer(
            "calendar",
            "Calendar coverage",
            "degraded",
            len(rows),
            "Exact calendar rows are present, but the attached acquisition state is not fully healthy.",
            reasons=tokens,
        )
    if rows:
        return _layer(
            "calendar",
            "Calendar coverage",
            "healthy_nonempty",
            len(rows),
            "Exact normalized calendar rows are present for this generation.",
        )
    if rejected or _contains(tokens, "reject", "invalid", "fixture_rejected"):
        return _layer(
            "calendar",
            "Calendar coverage",
            "rejected",
            0,
            "Calendar input failed admission or normalization; zero rows is not evidence of no events.",
            reasons=(*tokens, *((f"normalization_rejected_count={rejected}",) if rejected else ())),
        )
    if _contains(tokens, "stale", "too_old", "expired"):
        return _layer(
            "calendar",
            "Calendar coverage",
            "stale",
            0,
            "The configured calendar snapshot is stale and was not admitted.",
            reasons=tokens,
        )
    if metadata.get("configured") is False or _contains(tokens, "not_configured", "missing_config"):
        return _layer(
            "calendar",
            "Calendar coverage",
            "not_configured",
            0,
            "Calendar acquisition was not configured; zero rows does not mean no events exist.",
            reasons=tokens,
        )
    if _contains(tokens, "healthy_empty", "observed_no_results"):
        return _layer(
            "calendar",
            "Calendar coverage",
            "healthy_empty",
            0,
            "The exact configured calendar snapshot was observed and retained zero events.",
        )
    if _contains(tokens, "healthy_nonempty"):
        return _layer(
            "calendar",
            "Calendar coverage",
            "degraded",
            0,
            "The calendar receipt reports nonempty coverage, but no exact calendar rows are attached.",
            reasons=tokens,
        )
    if _contains(tokens, "unavailable", "failed", "error"):
        return _layer(
            "calendar",
            "Calendar coverage",
            "unavailable",
            0,
            "Calendar acquisition failed or was unavailable; treat the schedule as unknown.",
            reasons=tokens,
        )

    fallback = tuple(
        _pack_assessment(row)
        for row in _source_pack_rows(snapshot)
        if _token(row.get("source_pack")) in {"unified_calendar_pack", "unlock_supply_pack"}
    )
    return _combined_coverage(
        key="calendar",
        label="Calendar coverage",
        assessments=fallback,
        row_count=0,
        absent_detail=(
            "No exact calendar rows or complete calendar acquisition assessment is attached."
        ),
    )


def _sidecar_coverage(
    snapshot: DashboardSnapshot,
    *,
    key: str,
    label: str,
    names: frozenset[str],
    candidate_context_fields: tuple[str, ...],
) -> DashboardLayerCoverage:
    manifest = _manifest_rows(snapshot, names)
    context_count = sum(
        1
        for row in snapshot.current_candidates
        if any(isinstance(row.get(field), Mapping) for field in candidate_context_fields)
    )
    manifest_count = sum(_manifest_row_count(row) for row in manifest)
    assessments = [_manifest_assessment(row) for row in manifest]
    if context_count and not assessments:
        assessments.append("healthy_nonempty")
    return _combined_coverage(
        key=key,
        label=label,
        assessments=assessments,
        row_count=max(context_count, manifest_count),
        absent_detail=f"No exact {label.casefold()} input-manifest assessment is attached.",
    )


def _outcome_coverage(snapshot: DashboardSnapshot) -> DashboardLayerCoverage:
    rows = tuple(snapshot.current_outcomes)
    candidates = tuple(snapshot.current_candidates)
    metadata = snapshot.current_outcomes_metadata
    entry = _artifact_entry(snapshot, "integrated_outcomes")
    error = _token(metadata.get("error"))
    entry_status = _token(entry.get("status"))
    authority = _token(metadata.get("authority"))
    digest = str(metadata.get("sha256") or "").strip()
    reasons = _tokens(error, entry_status, entry.get("reason"), authority)
    if error:
        status = "rejected" if _contains((error,), "invalid", "schema", "contract", "lineage", "row_type", "research_only") else "unavailable"
        return _layer(
            "outcomes",
            "Outcome tracking",
            status,
            0,
            "The exact outcome artifact failed validation and no outcome rows were admitted.",
            reasons=reasons,
        )
    if entry_status in {"stale"}:
        return _layer(
            "outcomes",
            "Outcome tracking",
            "stale",
            0,
            "The exact outcome artifact is stale.",
            reasons=reasons,
        )
    if authority == "current_generation_fingerprint_verified" and digest:
        if candidates and len(rows) != len(candidates):
            return _layer(
                "outcomes",
                "Outcome tracking",
                "degraded",
                len(rows),
                "The fingerprint-verified outcome count does not cover every canonical current idea.",
                reasons=(f"candidates={len(candidates)}", f"outcomes={len(rows)}"),
            )
        return _layer(
            "outcomes",
            "Outcome tracking",
            "healthy_nonempty" if rows else "healthy_empty",
            len(rows),
            (
                "Fingerprint-verified outcome rows cover the canonical current ideas."
                if rows
                else "The fingerprint-verified outcome artifact is empty for this zero-idea generation."
            ),
        )
    if not candidates and not rows and entry_status in {"", "skipped"}:
        return DashboardLayerCoverage(
            key="outcomes",
            label="Outcome tracking",
            status="not_applicable",
            expected=False,
            row_count=0,
            detail="No canonical current ideas exist, so an outcome placeholder is not required.",
            reasons=reasons,
        )
    return _layer(
        "outcomes",
        "Outcome tracking",
        "unavailable",
        len(rows),
        "No fingerprint-verified exact outcome artifact is available for the current ideas.",
        reasons=reasons,
    )


def _request_ledger_coverage(snapshot: DashboardSnapshot) -> DashboardLayerCoverage:
    ledger = snapshot.current_request_ledger
    metadata = snapshot.current_request_ledger_metadata
    entry = _artifact_entry(snapshot, "market_no_send_request_ledger")
    mode = _token(
        ledger.get("candidate_source_mode")
        or snapshot.market_generation.get("candidate_source_mode")
        or snapshot.market_generation.get("data_mode")
    )
    expected = bool(
        mode in {"live", "live_no_send", "live_provider"}
        or snapshot.market_generation.get("provider_call_attempted") is True
        or snapshot.market_generation.get("provider_request_succeeded") is not None
        or snapshot.market_generation.get("live_provider_authorized") is not None
        or _token(entry.get("status")) == "current"
    )
    error = _token(metadata.get("error"))
    entry_status = _token(entry.get("status"))
    reasons = _tokens(error, entry_status, entry.get("reason"), metadata.get("authority"))
    if error:
        status = "rejected" if _contains((error,), "invalid", "schema", "contract", "lineage", "mismatch", "safety") else "unavailable"
        return _layer(
            "request_ledger",
            "Provider request ledger",
            status,
            0,
            "The exact provider request ledger failed validation and was not admitted.",
            expected=expected,
            reasons=reasons,
        )
    if entry_status == "stale":
        return _layer(
            "request_ledger",
            "Provider request ledger",
            "stale",
            0,
            "The exact provider request ledger is stale.",
            expected=expected,
            reasons=reasons,
        )
    authority = _token(metadata.get("authority"))
    digest = str(metadata.get("sha256") or "").strip()
    if ledger and authority == "current_generation_fingerprint_verified" and digest:
        return _layer(
            "request_ledger",
            "Provider request ledger",
            "healthy_nonempty",
            1,
            "A fingerprint-verified provider request ledger is attached to this generation.",
            expected=expected,
        )
    if ledger:
        return _layer(
            "request_ledger",
            "Provider request ledger",
            "unavailable",
            0,
            "Provider request values exist, but fingerprint-verified exact-ledger metadata is unavailable.",
            expected=True,
            reasons=reasons,
        )
    if not expected:
        return DashboardLayerCoverage(
            key="request_ledger",
            label="Provider request ledger",
            status="not_applicable",
            expected=False,
            row_count=0,
            detail="This non-live generation did not require a provider request ledger.",
            reasons=reasons,
        )
    return _layer(
        "request_ledger",
        "Provider request ledger",
        "unavailable",
        0,
        "A live/provider-backed generation is missing its fingerprint-verified request ledger.",
        expected=True,
        reasons=reasons,
    )


def _combined_coverage(
    *,
    key: str,
    label: str,
    assessments: Iterable[str],
    row_count: int,
    absent_detail: str,
) -> DashboardLayerCoverage:
    states = tuple(state for state in assessments if state)
    if not states:
        return _layer(key, label, "unavailable", row_count, absent_detail)
    unique = set(states)
    nonhealthy = unique - HEALTHY_STATUSES
    healthy = unique & {"healthy_nonempty", "healthy_empty"}
    if healthy and nonhealthy:
        status = "degraded"
    elif "rejected" in unique:
        status = "rejected"
    elif "stale" in unique:
        status = "stale"
    elif "unavailable" in unique:
        status = "unavailable"
    elif "degraded" in unique:
        status = "degraded"
    elif unique <= {"not_configured", "not_applicable"}:
        status = "not_configured" if "not_configured" in unique else "not_applicable"
    elif row_count or "healthy_nonempty" in unique:
        status = "healthy_nonempty"
    elif unique <= {"healthy_empty", "not_applicable"}:
        status = "healthy_empty"
    else:
        status = "unavailable"
    detail = {
        "healthy_nonempty": f"Exact {label.casefold()} evidence is present for this generation.",
        "healthy_empty": f"Configured {label.casefold()} inputs were observed and produced a healthy empty result.",
        "not_configured": f"{label} was not configured for this generation; zero rows is not proof of no relevant evidence.",
        "not_applicable": f"{label} is explicitly not applicable to this generation.",
        "unavailable": f"{label} was configured or expected but exact coverage is unavailable.",
        "degraded": f"{label} coverage is partial or degraded; do not interpret zero rows as confirmed absence.",
        "stale": f"{label} coverage is stale and is not current evidence.",
        "rejected": f"{label} evidence was rejected by validation or admission checks.",
    }[status]
    return _layer(
        key,
        label,
        status,
        row_count,
        detail,
        expected=status != "not_applicable",
        reasons=tuple(sorted(unique)),
    )


def _manifest_assessment(row: Mapping[str, Any]) -> str:
    count = _manifest_row_count(row)
    configured = row.get("configured")
    tokens = _tokens(
        row.get("coverage_status"),
        row.get("mode"),
        row.get("provider_status"),
        row.get("freshness_status"),
        *_iter_values(row.get("warnings")),
        *_iter_values(row.get("errors")),
    )
    if _contains(tokens, "reject", "invalid", "schema", "contract"):
        return "rejected"
    if _contains(tokens, "stale", "expired"):
        return "stale"
    if _contains(tokens, "read_error", "unavailable", "failed", "missing_artifact", "unreadable"):
        return "unavailable" if configured is not False else "not_configured"
    if _contains(tokens, "degraded", "partial", "unverified", "backoff", "rate_limit"):
        return "degraded"
    if _contains(tokens, "not_applicable"):
        return "not_applicable"
    if configured is False or _contains(tokens, "not_configured", "skipped_missing_config", "missing_config"):
        return "not_configured"
    if count:
        return "healthy_nonempty"
    if any(token in _EXPLICIT_HEALTHY_EMPTY for token in tokens):
        return "healthy_empty"
    if any(token in _EXPLICIT_HEALTHY_NONEMPTY for token in tokens):
        return "healthy_nonempty" if count else "healthy_empty"
    return "unavailable"


def _pack_assessment(row: Mapping[str, Any]) -> str:
    status = _token(
        row.get("provider_coverage_status") or row.get("source_pack_coverage_status")
    )
    accepted = _accepted_count(row)
    if _contains((status,), "reject", "invalid"):
        return "rejected"
    if _contains((status,), "stale", "expired"):
        return "stale"
    if status in {"partial", "degraded", "backoff", "rate_limited"}:
        return "degraded"
    if status in {"unavailable", "provider_unavailable", "failed"}:
        return "unavailable"
    if status in {"not_configured", "missing_config", "skipped_live_calls_disabled"}:
        return "not_configured"
    if accepted:
        return "healthy_nonempty"
    if status in {"complete", "observed_healthy", "observed_no_results", "healthy_empty"}:
        return "healthy_empty"
    return "unavailable"


def _source_pack_rows(snapshot: DashboardSnapshot) -> tuple[Mapping[str, Any], ...]:
    raw = snapshot.source_coverage.get("packs")
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
        return ()
    return tuple(row for row in raw if isinstance(row, Mapping))


def _manifest_rows(
    snapshot: DashboardSnapshot,
    names: frozenset[str],
) -> tuple[Mapping[str, Any], ...]:
    raw = snapshot.source_coverage.get("input_manifest")
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
        return ()
    return tuple(
        row
        for row in raw
        if isinstance(row, Mapping) and _token(row.get("sidecar_name")) in names
    )


def _artifact_entry(snapshot: DashboardSnapshot, name: str) -> Mapping[str, Any]:
    artifacts = snapshot.operator_state.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return {}
    entry = artifacts.get(name)
    return entry if isinstance(entry, Mapping) else {}


def _layer(
    key: str,
    label: str,
    status: str,
    row_count: int,
    detail: str,
    *,
    expected: bool = True,
    reasons: Iterable[str] = (),
) -> DashboardLayerCoverage:
    return DashboardLayerCoverage(
        key=key,
        label=label,
        status=status,
        expected=expected,
        row_count=max(0, int(row_count)),
        detail=detail,
        reasons=tuple(dict.fromkeys(str(reason) for reason in reasons if str(reason))),
    )


def _tokens(*values: object) -> tuple[str, ...]:
    return tuple(dict.fromkeys(token for value in values if (token := _token(value))))


def _token(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _contains(tokens: Iterable[str], *parts: str) -> bool:
    return any(part in token for token in tokens for part in parts)


def _count(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _manifest_row_count(row: Mapping[str, Any]) -> int:
    raw = row.get("row_counts")
    if isinstance(raw, Mapping):
        return _count(raw.get("rows")) or 0
    return _count(row.get("row_count")) or 0


def _accepted_count(row: Mapping[str, Any]) -> int:
    return _count(row.get("accepted_evidence_count")) or 0


def _iter_values(value: object) -> tuple[object, ...]:
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return tuple(value)
    return (value,) if value not in (None, "") else ()


def _origin_tokens(row: Mapping[str, Any]) -> set[str]:
    raw = row.get("thesis_origins") or row.get("source_origins") or ()
    if isinstance(raw, str):
        values = (raw,)
    elif isinstance(raw, Iterable) and not isinstance(raw, (bytes, Mapping)):
        values = raw
    else:
        values = ()
    primary = row.get("primary_thesis_origin") or row.get("thesis_origin")
    return {_token(value) for value in (*tuple(values), primary) if _token(value)}


__all__ = (
    "DashboardLayerCoverage",
    "HEALTHY_STATUSES",
    "LAYER_ORDER",
    "dashboard_layer_coverage",
    "dashboard_layer_coverage_by_key",
)
