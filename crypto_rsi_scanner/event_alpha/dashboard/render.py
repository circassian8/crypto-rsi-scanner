"""Escaped server-rendered HTML for the local radar dashboard."""

from __future__ import annotations

import html
import math
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import quote, urlsplit

from ..operations import market_provenance
from .loader import candidate_identifier
from .models import DashboardResponse, DashboardSnapshot


_NAV = (
    ("/", "Today"),
    ("/anomalies", "Market Anomalies"),
    ("/catalysts", "Catalyst Ideas"),
    ("/fade-risk", "Fade / Risk"),
    ("/calendar", "Calendar"),
    ("/health", "Provider / System Health"),
    ("/feedback-outcomes", "Feedback / Outcomes"),
)
_ACTIONABLE_ROUTES = {"actionable_watch", "high_confidence_watch"}


def render_dashboard_page(
    snapshot: DashboardSnapshot,
    path: str,
    *,
    include_diagnostics: bool = False,
    query: Mapping[str, str] | None = None,
) -> DashboardResponse:
    dashboard_query = _dashboard_query(query)
    current_generation_page = path in {"/", "/anomalies", "/catalysts", "/fade-risk", "/calendar"}
    if current_generation_page and not snapshot.generation_authoritative:
        title = {
            "/": "Today",
            "/anomalies": "Market Anomalies",
            "/catalysts": "Catalyst Ideas",
            "/fade-risk": "Fade / Risk",
            "/calendar": "Calendar",
        }[path]
        return _ok(snapshot, title, _authority_unavailable(snapshot))
    if path == "/":
        body = _today(
            snapshot,
            include_diagnostics=include_diagnostics,
            query=dashboard_query,
        )
        return _ok(snapshot, "Today", body)
    if path == "/anomalies":
        return _ok(
            snapshot,
            "Market Anomalies",
            _anomalies(
                snapshot,
                include_diagnostics=include_diagnostics,
                query=dashboard_query,
            ),
        )
    if path == "/catalysts":
        return _ok(
            snapshot,
            "Catalyst Ideas",
            _catalysts(
                snapshot,
                include_diagnostics=include_diagnostics,
                query=dashboard_query,
            ),
        )
    if path == "/fade-risk":
        return _ok(
            snapshot,
            "Fade / Risk",
            _fade_risk(
                snapshot,
                include_diagnostics=include_diagnostics,
                query=dashboard_query,
            ),
        )
    if path == "/calendar":
        return _ok(snapshot, "Calendar", _calendar(snapshot))
    if path == "/health":
        return _ok(snapshot, "Provider / System Health", _health(snapshot))
    if path == "/feedback-outcomes":
        return _ok(snapshot, "Feedback / Outcomes", _feedback_outcomes(snapshot))
    if path.startswith("/candidate/"):
        identifier = path.removeprefix("/candidate/")
        return _candidate_detail(snapshot, identifier, include_diagnostics=include_diagnostics)
    return DashboardResponse(404, "Not Found", _standalone_error("Not Found", "Unknown dashboard page."))


def _today(
    snapshot: DashboardSnapshot,
    *,
    include_diagnostics: bool,
    query: Mapping[str, str],
) -> str:
    rows = tuple(
        row
        for row in snapshot.visible_current_candidates
        if row.get("_dashboard_route") in _ACTIONABLE_ROUTES
        and row.get("radar_actionable") is True
    )
    sections = [
        _section("Actionable research ideas", _candidate_table(rows, query=query)),
        _section(
            "Dashboard watch",
            _candidate_table(
                (
                    row
                    for row in snapshot.visible_current_candidates
                    if row.get("_dashboard_route") == "dashboard_watch"
                ),
                query=query,
            ),
        ),
        _section(
            "Rapid anomalies",
            _candidate_table(
                (
                    row
                    for row in snapshot.visible_current_candidates
                    if row.get("_dashboard_route") == "rapid_market_anomaly"
                ),
                query=query,
            ),
        ),
        _section(
            "Review queues",
            _candidate_table(
                (
                    row
                    for row in snapshot.visible_current_candidates
                    if row.get("_dashboard_route") in {
                        "fade_exhaustion_review",
                        "risk_watch",
                        "calendar_risk",
                    }
                ),
                query=query,
            ),
        ),
    ]
    if snapshot.expired_current_candidates:
        sections.append(
            _section(
                "Expired ideas (not currently actionable)",
                '<p class="scope">Canonical research history is preserved, but these ideas are '
                "suppressed from current actionability because their recorded expiry is at or before "
                "the dashboard read time.</p>"
                + _candidate_table(
                    snapshot.expired_current_candidates,
                    query=query,
                ),
            )
        )
    if include_diagnostics:
        sections.append(
            _section(
                "Diagnostics",
                _candidate_table(snapshot.diagnostic_candidates, query=query),
            )
        )
    else:
        sections.append(
            '<p class="muted">Diagnostics are hidden by default. '
            '<a href="/?include_diagnostics=1">Show current-generation diagnostics</a>.</p>'
        )
    return _candidate_controls(query) + "".join(sections)


def _anomalies(
    snapshot: DashboardSnapshot,
    *,
    include_diagnostics: bool,
    query: Mapping[str, str],
) -> str:
    raw_by_asset = {
        _asset_key(row): row
        for row in snapshot.current_market_anomalies
        if _asset_key(row)
    }
    market_led = []
    for candidate in snapshot.current_candidates:
        if candidate.get("_decision_model_status") != "v2":
            continue
        if not (
            "market_led" in _origin_tokens(candidate)
            or candidate.get("anomaly_type")
            or candidate.get("market_anomaly_type")
        ):
            continue
        row = dict(candidate)
        raw = raw_by_asset.get(_asset_key(candidate), {})
        if isinstance(raw, Mapping):
            for field in ("anomaly_type", "market_anomaly_type", "market_state_class", "market_state_snapshot"):
                if row.get(field) in (None, "", {}, ()) and raw.get(field) not in (None, "", {}, ()):
                    row[field] = raw.get(field)
        if include_diagnostics or row.get("_dashboard_route") != "diagnostic":
            market_led.append(row)
    if include_diagnostics:
        market_led.extend(
            row
            for row in snapshot.current_market_anomalies
            if row.get("_decision_model_status") != "v2" or row.get("_dashboard_route") == "diagnostic"
        )
    rows = tuple(market_led)
    text = (
        "Market-led rows may be actionable without a known catalyst when identity, freshness, liquidity, "
        "spread, turnover, and manipulation-risk gates pass. Unknown catalyst remains a warning, not a trade instruction."
    )
    return _candidate_controls(query) + f"<p>{_h(text)}</p>" + _candidate_table(rows, query=query)


def _catalysts(
    snapshot: DashboardSnapshot,
    *,
    include_diagnostics: bool,
    query: Mapping[str, str],
) -> str:
    rows = tuple(
        row
        for row in snapshot.current_candidates
        if "catalyst_led" in _origin_tokens(row)
        and str(row.get("catalyst_status") or "") in {"confirmed", "plausible"}
        and (include_diagnostics or row.get("_dashboard_route") != "diagnostic")
        and row.get("_decision_model_status") == "v2"
    )
    return _candidate_controls(query) + _candidate_table(rows, query=query)


def _fade_risk(
    snapshot: DashboardSnapshot,
    *,
    include_diagnostics: bool,
    query: Mapping[str, str],
) -> str:
    rows = tuple(
        row
        for row in snapshot.current_candidates
        if (
            str(row.get("directional_bias") or "") in {"fade_short_review", "risk"}
            or row.get("_dashboard_route") in {
                "fade_exhaustion_review",
                "risk_watch",
                "calendar_risk",
            }
        )
        and (include_diagnostics or row.get("_dashboard_route") != "diagnostic")
        and row.get("_decision_model_status") == "v2"
    )
    return (
        "<p>Fade and risk rows are manual research reviews after a completed or scheduled risk condition. "
        "They never create <code>TRIGGERED_FADE</code>.</p>"
        + _candidate_controls(query)
        + _candidate_table(rows, query=query)
    )


def _calendar(snapshot: DashboardSnapshot) -> str:
    headers = (
        "Event",
        "When",
        "Timezone",
        "Date window",
        "Kind",
        "Importance",
        "Previous / forecast / actual / surprise",
        "Impact window",
        "Assets",
        "Tracking",
        "Source",
    )
    body_rows = []
    for row in sorted(
        snapshot.current_calendar_events,
        key=lambda item: str(item.get("scheduled_at") or item.get("window_start") or "~"),
    ):
        scheduled = _h(row.get("scheduled_at") or "date window")
        window = _h(_window_label(row))
        body_rows.append(
            (
                _h(row.get("title") or "Untitled event"),
                scheduled,
                _h(row.get("timezone") or "UTC"),
                window,
                _h(row.get("event_kind") or "unknown"),
                _h(row.get("importance") or "unknown"),
                _h(_economic_context_label(row)),
                _h(_impact_window_label(row)),
                _h(", ".join(str(item) for item in row.get("affected_assets") or ()) or "market-wide"),
                _h(row.get("post_event_tracking_status") or "unknown"),
                _source_link(row),
            )
        )
    intro = (
        "<p>Fixture-first unified calendar. Dates may be exact, estimated, or bounded windows; "
        "reminders are display metadata only and do not send notifications.</p>"
    )
    return intro + _table(headers, body_rows, empty="No current-generation calendar rows.")


def _health(snapshot: DashboardSnapshot) -> str:
    doctor_verified = snapshot.doctor_verified_revision
    doctor_revision = "none" if doctor_verified is None else str(doctor_verified)
    summary = _definition_list(
        (
            ("Run", snapshot.run_id),
            ("Operator revision", snapshot.revision),
            ("Manifest", snapshot.manifest_status),
            ("Doctor", snapshot.doctor_status),
            ("Doctor verified revision", doctor_revision),
            ("Generation authority", snapshot.generation_authority_status),
            ("Authority checked at", snapshot.generation_authority_checked_at),
            ("Operator-state SHA-256", snapshot.operator_state_sha256),
            (
                "Authority reasons",
                "; ".join(snapshot.generation_authority_reasons) or "none",
            ),
            ("Research only", snapshot.operator_state.get("research_only")),
            ("Send attempted", snapshot.operator_state.get("send_attempted")),
            ("Trades / paper / RSI / triggered fade", "0 / 0 / 0 / 0"),
        )
    )
    artifacts = snapshot.operator_state.get("artifacts")
    artifact_rows = []
    if isinstance(artifacts, Mapping):
        for name, entry in sorted(artifacts.items()):
            if not isinstance(entry, Mapping):
                continue
            artifact_rows.append(
                (
                    _h(name),
                    _h(entry.get("status") or "unknown"),
                    _h(entry.get("path") or "not written"),
                    _h(entry.get("reason") or ""),
                )
            )
    current_providers = _provider_rows(snapshot.provider_readiness)
    cumulative_providers = _provider_rows(snapshot.provider_health)
    cumulative_health_metadata = _definition_list(
        (
            ("Authority", "cumulative / non-authoritative"),
            ("Read at", snapshot.provider_health_read_at or "not read"),
            ("SHA-256", snapshot.provider_health_sha256 or "unavailable"),
            ("Read error", snapshot.provider_health_error or "none"),
        )
    )
    return (
        _section("Current operator generation", summary)
        + _section("Artifact manifest", _table(("Artifact", "Status", "Path", "Reason"), artifact_rows))
        + _section(
            "Exact-generation provider readiness",
            _table(("Provider", "Status", "Detail"), current_providers),
        )
        + _section(
            "Cumulative provider health (non-authoritative)",
            cumulative_health_metadata
            + _table(("Provider", "Status", "Detail"), cumulative_providers),
        )
    )


def _feedback_outcomes(snapshot: DashboardSnapshot) -> str:
    feedback_rows = []
    for row in snapshot.cumulative_feedback:
        feedback_rows.append(
            (
                _h(row.get("core_opportunity_id") or row.get("target") or row.get("alert_id") or "unknown"),
                _h(row.get("label") or row.get("feedback_label") or row.get("status") or "unlabeled"),
                _h(_origin_display(row)),
                _h(row.get("catalyst_status") or "unclassified"),
            )
        )
    outcome_rows = []
    for row in snapshot.cumulative_outcomes:
        outcome_rows.append(
            (
                _h(row.get("core_opportunity_id") or row.get("candidate_id") or "unknown"),
                _h(row.get("outcome_status") or row.get("maturation_state") or "unknown"),
                _h(_origin_display(row)),
                _h(row.get("confidence_band") or "unclassified"),
                _h(row.get("actionability_score") if row.get("actionability_score") is not None else "n/a"),
            )
        )
    history_rows = []
    for artifact_name, metadata in sorted(snapshot.cumulative_history_metadata.items()):
        history_rows.append(
            (
                _h(artifact_name),
                _h(metadata.get("authority") or "cumulative_non_authoritative"),
                _h(metadata.get("read_at") or "not read"),
                _h(metadata.get("sha256") or "unavailable"),
                _h(metadata.get("error") or "none"),
            )
        )
    return (
        '<p class="scope"><strong>Cumulative research history.</strong> These rows are intentionally not '
        "presented as current-generation candidate counts.</p>"
        + _section(
            "Cumulative artifact reads (non-authoritative)",
            _table(("Artifact", "Authority", "Read at", "SHA-256", "Read error"), history_rows),
        )
        + _section(
            f"Feedback labels ({len(feedback_rows)})",
            _table(("Target", "Label", "Thesis origin", "Catalyst status"), feedback_rows),
        )
        + _section(
            f"Outcome rows ({len(outcome_rows)})",
            _table(("Target", "State", "Thesis origin", "Confidence", "Actionability"), outcome_rows),
        )
    )


def _candidate_detail(
    snapshot: DashboardSnapshot,
    identifier: str,
    *,
    include_diagnostics: bool,
) -> DashboardResponse:
    if not snapshot.generation_authoritative:
        return DashboardResponse(
            409,
            "Conflict",
            _layout(snapshot, "Candidate unavailable", _authority_unavailable(snapshot)),
        )
    row = next(
        (
            item
            for item in (*snapshot.current_candidates, *snapshot.current_market_anomalies)
            if candidate_identifier(item) == identifier
        ),
        None,
    )
    if row is None or (
        not include_diagnostics
        and row.get("_decision_expired_at_read_time") is not True
        and (
            row.get("_decision_model_status") != "v2"
            or row.get("_dashboard_route") == "diagnostic"
        )
    ):
        return DashboardResponse(
            404,
            "Not Found",
            _layout(snapshot, "Candidate not found", "<p>No visible current-generation candidate has that ID.</p>"),
        )
    provenance = _candidate_market_provenance(row)
    data_quality = _candidate_data_quality(row)
    dimensions = _definition_list(
        (
            ("ID", candidate_identifier(row)),
            ("Asset", f"{row.get('symbol') or 'unknown'} / {row.get('coin_id') or 'unknown'}"),
            ("Research route", row.get("_dashboard_route") or "diagnostic"),
            ("Canonical route", row.get("radar_route") or "diagnostic"),
            (
                "Current actionability",
                "suppressed: expired at dashboard read time"
                if row.get("_decision_expired_at_read_time") is True
                else str(bool(row.get("radar_actionable"))).lower(),
            ),
            (
                "Read-time safety reason",
                row.get("_decision_read_time_reason") or "none",
            ),
            ("Legacy opportunity type", row.get("opportunity_type") or "unknown"),
            ("Primary thesis origin", row.get("primary_thesis_origin") or row.get("thesis_origin") or "unclassified"),
            ("Thesis origins", _origin_display(row)),
            ("Directional bias", row.get("directional_bias") or "unclassified"),
            ("Catalyst status", row.get("catalyst_status") or "unclassified"),
            ("Confidence", row.get("confidence_band") or "unclassified"),
            ("Timing", row.get("timing_state") or "unclassified"),
            ("Market phase", row.get("market_phase") or "unclassified"),
            ("Preferred horizon", row.get("preferred_horizon") or "unclassified"),
            ("Expires at", row.get("expires_at") or "not recorded"),
            ("Tradability", row.get("tradability_status") or "unclassified"),
            ("Spread", row.get("spread_status") or "unclassified"),
            ("Actionability", _score(row.get("actionability_score"))),
            ("Urgency", _score(row.get("urgency_score"))),
            ("Evidence confidence", _score(row.get("evidence_confidence_score"))),
            ("Risk", _score(row.get("risk_score"))),
            ("Chase risk", _score(row.get("chase_risk_score"))),
            ("Catalyst warning", "Catalyst unknown" if row.get("catalyst_status") == "unknown" else "none"),
            ("Data acquisition mode", provenance.get("data_acquisition_mode") or "not recorded"),
            ("Candidate source mode", provenance.get("candidate_source_mode") or "not recorded"),
            ("Market provider", provenance.get("provider") or "not recorded"),
            ("Cache status", provenance.get("cache_status") or "not recorded"),
            ("Burn-in eligible", str(provenance.get("burn_in_eligible") is True).lower()),
            ("Burn-in counted", str(provenance.get("burn_in_counted") is True).lower()),
            ("Burn-in reason", provenance.get("burn_in_reason") or "not recorded"),
            ("Provider source artifact", provenance.get("provider_source_artifact") or "not recorded"),
            ("Request ledger", provenance.get("request_ledger_path") or "not recorded"),
            ("Temporal baseline", data_quality.get("baseline_status") or "not evaluated"),
            ("Direct feature count", data_quality.get("direct_feature_count") or 0),
            ("Proxy feature count", data_quality.get("proxy_feature_count") or 0),
            ("Liquidity basis", data_quality.get("liquidity_basis") or "not recorded"),
            ("Volume baseline basis", data_quality.get("volume_zscore_basis") or "not recorded"),
            ("Execution-quality basis", data_quality.get("spread_basis") or "not recorded"),
        )
    )
    source = _source_link(row)
    source_block = f"<p><strong>Source:</strong> {source}</p>" if source else ""
    snapshot_chart = _market_snapshot_sparkline(row)
    snapshot_block = (
        _section("Market snapshot trend", snapshot_chart)
        if snapshot_chart
        else ""
    )
    body = (
        dimensions
        + source_block
        + snapshot_block
        + _text_list(
            "Why still worth reviewing",
            _values(row, "why_still_worth_reviewing", "why_review_worthy", "why_now"),
        )
        + _text_list(
            "Missing data",
            _values(row, "decision_missing_data", "missing_data", "missing_data_fields"),
        )
        + _text_list("Hard blockers", _values(row, "decision_hard_blockers"))
        + _text_list("Soft penalties", _values(row, "decision_soft_penalties"))
        + _text_list("Decision warnings", _values(row, "decision_warnings"))
        + _text_list("What confirms", _values(row, "radar_what_confirms", "what_confirms"))
        + _text_list("What invalidates", _values(row, "radar_what_invalidates", "what_invalidates"))
        + _score_components("Actionability score components", row.get("actionability_score_components"))
        + _score_components("Actionability penalty components", row.get("actionability_penalty_components"))
        + _score_components(
            "Evidence-confidence score components",
            row.get("evidence_confidence_score_components"),
        )
        + _score_components("Risk score components", row.get("risk_score_components"))
    )
    return _ok(snapshot, f"Candidate {row.get('symbol') or identifier}", body)


def filter_sort_candidates(
    rows: Iterable[Mapping[str, Any]],
    query: Mapping[str, str] | None = None,
) -> tuple[Mapping[str, Any], ...]:
    """Apply exact, allowlisted dashboard filters and deterministic score sorts."""

    filters = _dashboard_query(query)
    selected: list[Mapping[str, Any]] = []
    for row in rows:
        if filters.get("route") and _token(row.get("_dashboard_route")) != filters["route"]:
            continue
        if filters.get("origin") and filters["origin"] not in _origin_tokens(row):
            continue
        if filters.get("confidence") and _token(row.get("confidence_band")) != filters["confidence"]:
            continue
        if filters.get("catalyst") and _token(row.get("catalyst_status")) != filters["catalyst"]:
            continue
        if filters.get("timing") and _token(
            row.get("market_phase") or row.get("timing_state")
        ) != filters["timing"]:
            continue
        if filters.get("risk") and _risk_band(row) != filters["risk"]:
            continue
        selected.append(row)
    sort_name = filters.get("sort", "")
    score_field, descending = {
        "actionability_desc": ("actionability_score", True),
        "urgency_desc": ("urgency_score", True),
        "risk_asc": ("risk_score", False),
        "risk_desc": ("risk_score", True),
    }.get(sort_name, ("", False))
    if score_field:
        selected.sort(
            key=lambda row: (
                _missing_sort_value(row.get(score_field), descending=descending),
                candidate_identifier(row),
            ),
        )
    return tuple(selected)


def _candidate_table(
    rows: Iterable[Mapping[str, Any]],
    *,
    query: Mapping[str, str] | None = None,
) -> str:
    body_rows = []
    seen = set()
    for row in filter_sort_candidates(rows, query):
        identifier = candidate_identifier(row)
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        link = f'<a href="/candidate/{quote(identifier, safe="")}">{_h(row.get("symbol") or identifier)}</a>'
        warning = "Catalyst unknown" if row.get("catalyst_status") == "unknown" else ""
        if row.get("_decision_expired_at_read_time") is True:
            warning = (
                (warning + "; ") if warning else ""
            ) + "Expired; current actionability suppressed"
        if _higher_manipulation_risk(row):
            warning = (warning + "; " if warning else "") + "Higher manipulation/tradability risk"
        body_rows.append(
            (
                link,
                _h(row.get("_dashboard_route") or "diagnostic"),
                _h(_origin_display(row)),
                _h(row.get("directional_bias") or "unclassified"),
                _h(row.get("confidence_band") or "unclassified"),
                _h(row.get("market_phase") or row.get("timing_state") or "unclassified"),
                _h(_score(row.get("actionability_score"))),
                _h(_score(row.get("urgency_score"))),
                _h(_score(row.get("evidence_confidence_score"))),
                _h(_score(row.get("risk_score"))),
                _h(row.get("preferred_horizon") or "unclassified"),
                _h(row.get("expires_at") or "not recorded"),
                _h(row.get("spread_status") or "unclassified"),
                _h(_candidate_quality_label(row)),
                _h(_score(row.get("chase_risk_score"))),
                _market_snapshot_sparkline(row) or '<span class="muted">n/a</span>',
                _h(warning),
            )
        )
    return _table(
        (
            "Asset",
            "Route",
            "Thesis",
            "Bias",
            "Confidence",
            "Timing",
            "Actionability",
            "Urgency",
            "Evidence",
            "Risk",
            "Horizon",
            "Expires",
            "Spread",
            "Data quality",
            "Chase risk",
            "Snapshot",
            "Warning",
        ),
        body_rows,
        empty="No rows in this current-generation lane.",
    )


def _candidate_controls(query: Mapping[str, str]) -> str:
    inputs = "".join(
        f'<label>{_h(label)} <input name="{_h(name)}" value="{_h(query.get(name, ""))}" '
        'autocomplete="off"></label>'
        for name, label in (
            ("route", "Route"),
            ("origin", "Origin"),
            ("confidence", "Confidence"),
            ("catalyst", "Catalyst"),
            ("risk", "Risk band"),
            ("timing", "Timing"),
        )
    )
    selected = query.get("sort", "")
    options = "".join(
        f'<option value="{_h(value)}"{(" selected" if selected == value else "")}>{_h(label)}</option>'
        for value, label in (
            ("", "Artifact order"),
            ("actionability_desc", "Actionability high to low"),
            ("urgency_desc", "Urgency high to low"),
            ("risk_asc", "Risk low to high"),
            ("risk_desc", "Risk high to low"),
        )
    )
    return (
        '<form class="candidate-filters" method="get">'
        + inputs
        + f'<label>Sort <select name="sort">{options}</select></label>'
        + '<button type="submit">Apply</button></form>'
    )


def _dashboard_query(query: Mapping[str, str] | None) -> dict[str, str]:
    if not isinstance(query, Mapping):
        return {}
    out: dict[str, str] = {}
    for field in ("route", "origin", "confidence", "catalyst", "risk", "timing", "sort"):
        value = query.get(field)
        text = value.strip() if isinstance(value, str) else ""
        if text and len(text) <= 80:
            out[field] = text.casefold()
    return out


def _origin_tokens(row: Mapping[str, Any]) -> set[str]:
    tokens = {
        _token(row.get("primary_thesis_origin") or row.get("thesis_origin")),
    }
    origins = row.get("thesis_origins")
    if isinstance(origins, Iterable) and not isinstance(origins, (str, bytes, Mapping)):
        tokens.update(_token(value) for value in origins)
    return {token for token in tokens if token}


def _candidate_market_provenance(row: Mapping[str, Any]) -> Mapping[str, Any]:
    canonical = market_provenance.market_provenance_values(row)
    if canonical:
        return canonical
    projection = row.get("decision_projection")
    projection = projection if isinstance(projection, Mapping) else {}
    lineage = projection.get("source_provider_lineage")
    lineage = lineage if isinstance(lineage, Mapping) else {}
    containers = (
        projection.get("market_provenance"),
        row.get("market_provenance"),
        lineage.get("market_provenance"),
        row.get("market_state_snapshot"),
        row.get("market_snapshot"),
        lineage,
    )
    merged: dict[str, Any] = {}
    fields = (
        "data_mode", "data_acquisition_mode", "candidate_source_mode", "provider",
        "cache_status", "burn_in_eligible", "burn_in_counted", "burn_in_reason",
        "provider_source_artifact", "provider_source_sha256", "request_ledger_path",
        "request_ledger_sha256", "provenance_contract_valid",
    )
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for field in fields:
            if field not in merged and container.get(field) not in (None, "", [], {}):
                merged[field] = container.get(field)
    return merged


def _candidate_data_quality(row: Mapping[str, Any]) -> Mapping[str, Any]:
    projection = row.get("decision_projection")
    projection = projection if isinstance(projection, Mapping) else {}
    for container in (
        row.get("market_state_snapshot"),
        row.get("market_snapshot"),
        projection.get("market_data_quality"),
        row.get("market_data_quality"),
        row.get("data_quality"),
    ):
        if not isinstance(container, Mapping):
            continue
        nested = container.get("market_data_quality")
        if isinstance(nested, Mapping):
            return nested
        if any(
            field in container
            for field in (
                "baseline_status", "direct_feature_count", "proxy_feature_count",
                "liquidity_basis", "volume_zscore_basis", "spread_basis",
            )
        ):
            return container
    return {}


def _candidate_quality_label(row: Mapping[str, Any]) -> str:
    provenance = _candidate_market_provenance(row)
    quality = _candidate_data_quality(row)
    mode = str(provenance.get("candidate_source_mode") or "unclassified")
    baseline = str(quality.get("baseline_status") or "not_evaluated")
    spread = str(quality.get("spread_basis") or row.get("spread_status") or "unknown")
    return f"{mode}; baseline={baseline}; spread={spread}"


def _origin_display(row: Mapping[str, Any]) -> str:
    primary = _token(row.get("primary_thesis_origin") or row.get("thesis_origin"))
    origins = row.get("thesis_origins")
    ordered = (
        [_token(value) for value in origins]
        if isinstance(origins, Iterable) and not isinstance(origins, (str, bytes, Mapping))
        else []
    )
    values = [value for value in (primary, *ordered) if value]
    return ", ".join(dict.fromkeys(values)) or "legacy unclassified"


def _risk_band(row: Mapping[str, Any]) -> str:
    explicit = _token(row.get("risk_band"))
    if explicit in {"low", "medium", "high"}:
        return explicit
    value = _finite_number(row.get("risk_score"))
    if value is None:
        return "unknown"
    if value < 40:
        return "low"
    if value < 70:
        return "medium"
    return "high"


def _missing_sort_value(value: object, *, descending: bool) -> tuple[int, float]:
    number = _finite_number(value)
    if number is None:
        return (1, 0.0)
    return (0, -number if descending else number)


def _market_snapshot_sparkline(row: Mapping[str, Any]) -> str:
    values = _market_snapshot_series(row)
    if len(values) < 2:
        return ""
    width = 108.0
    height = 30.0
    padding = 2.0
    low = min(values)
    high = max(values)
    span = high - low
    points = []
    for index, value in enumerate(values):
        x = padding + (width - 2 * padding) * index / (len(values) - 1)
        y = height / 2 if span == 0 else padding + (height - 2 * padding) * (high - value) / span
        points.append(f"{x:.1f},{y:.1f}")
    return (
        '<svg class="sparkline" viewBox="0 0 108 30" role="img" '
        'aria-label="Existing market snapshot trend">'
        f'<polyline points="{" ".join(points)}" fill="none" stroke="currentColor" '
        'stroke-width="2" vector-effect="non-scaling-stroke"></polyline></svg>'
    )


def _market_snapshot_series(row: Mapping[str, Any]) -> tuple[float, ...]:
    for container_name in ("market_state_snapshot", "market_snapshot"):
        container = row.get(container_name)
        if not isinstance(container, Mapping):
            continue
        for field in ("price_series", "close_series", "return_series", "sparkline_values"):
            values = _finite_series(container.get(field))
            if len(values) >= 2:
                return values
    for field in ("market_state_snapshots", "market_snapshots"):
        snapshots = row.get(field)
        if not isinstance(snapshots, Iterable) or isinstance(snapshots, (str, bytes, Mapping)):
            continue
        values: list[float] = []
        for snapshot in snapshots:
            if not isinstance(snapshot, Mapping):
                continue
            value = None
            for name in ("price", "close", "return", "return_1h"):
                value = _finite_number(snapshot.get(name))
                if value is not None:
                    break
            if value is not None:
                values.append(value)
        if len(values) >= 2:
            return tuple(values)
    return ()


def _finite_series(value: object) -> tuple[float, ...]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return ()
    out = tuple(number for item in value if (number := _finite_number(item)) is not None)
    return out[:64]


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _token(value: object) -> str:
    return str(value or "").strip().casefold()


def _higher_manipulation_risk(row: Mapping[str, Any]) -> bool:
    components = row.get("risk_score_components")
    try:
        manipulation = float(components.get("manipulation_risk") or 0.0) if isinstance(components, Mapping) else 0.0
    except (TypeError, ValueError):
        manipulation = 0.0
    warnings = " ".join(str(item) for item in row.get("decision_warnings") or ())
    return bool(
        row.get("tradability_status") in {"poor", "blocked"}
        or manipulation >= 50.0
        or "manipulation" in warnings.casefold()
    )


def _provider_rows(*payloads: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for payload in payloads:
        raw = payload.get("providers") if isinstance(payload, Mapping) else None
        if isinstance(raw, Mapping):
            values = [dict(value, provider=key) if isinstance(value, Mapping) else {"provider": key, "status": value} for key, value in raw.items()]
        elif isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
            values = [item for item in raw if isinstance(item, Mapping)]
        else:
            values = []
        for item in values:
            out.append(
                (
                    _h(item.get("provider") or item.get("name") or item.get("provider_key") or "unknown"),
                    _h(item.get("status") or item.get("readiness_status") or item.get("health_status") or "unknown"),
                    _h(item.get("reason") or item.get("status_detail") or item.get("skip_reason") or ""),
                )
            )
    return out


def _ok(snapshot: DashboardSnapshot, title: str, body: str) -> DashboardResponse:
    return DashboardResponse(200, "OK", _layout(snapshot, title, body))


def _layout(snapshot: DashboardSnapshot, title: str, body: str) -> str:
    nav = "".join(f'<a href="{path}">{_h(label)}</a>' for path, label in _NAV)
    current_count = (
        str(snapshot.current_generation_count)
        if snapshot.generation_authoritative
        else "suppressed (untrusted)"
    )
    cumulative_count = (
        str(snapshot.cumulative_store_count)
        if snapshot.generation_authoritative
        else "see Feedback / Outcomes"
    )
    scope = (
        f"Current generation: {_h(snapshot.run_id)} · revision {snapshot.revision} · "
        f"current candidates {current_count} · cumulative core history {cumulative_count}"
    )
    badges = _generation_badges(snapshot)
    authority_banner = ""
    if not snapshot.generation_authoritative:
        reasons = "".join(f"<li>{_h(reason)}</li>" for reason in snapshot.generation_authority_reasons)
        authority_banner = (
            '<div class="authority-untrusted"><strong>UNTRUSTED CURRENT GENERATION.</strong> '
            "Current actionable, anomaly, catalyst, fade/risk, calendar, diagnostic, and candidate-detail "
            f"content is suppressed.<ul>{reasons}</ul></div>"
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_h(title)} · Crypto Radar</title><style>
:root{{--bg:#0b1020;--panel:#151d31;--ink:#eef3ff;--muted:#a9b6d3;--line:#2d3956;--accent:#7dd3fc;--warn:#fbbf24;--danger:#f87171}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}
header,main{{max-width:1280px;margin:auto;padding:18px}}nav{{display:flex;gap:14px;flex-wrap:wrap}}a{{color:var(--accent)}}
.banner,.scope,.authority-untrusted,section{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:14px 0}}
.badge{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:2px 8px;margin:0 5px 4px 0;font-size:.86em}}.badge-current{{border-color:#22c55e;color:#bbf7d0}}.badge-live{{border-color:#38bdf8;color:#bae6fd}}.badge-fixture{{border-color:#a78bfa;color:#ddd6fe}}.badge-stale{{border-color:var(--danger);color:#fecaca}}
.banner{{border-color:#725b16;color:#fde68a}}.muted{{color:var(--muted)}}table{{width:100%;border-collapse:collapse;overflow:auto}}
.authority-untrusted{{border:3px solid var(--danger);color:#fecaca;background:#3f1219}}.authority-untrusted strong{{font-size:1.08em}}
.candidate-filters{{display:flex;gap:10px;flex-wrap:wrap;align-items:end;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:14px 0}}
.candidate-filters label{{display:grid;gap:3px;color:var(--muted)}}.candidate-filters input,.candidate-filters select,.candidate-filters button{{background:#0d1528;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:6px 8px}}
.sparkline{{width:108px;height:30px;color:var(--accent);vertical-align:middle}}
th,td{{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}}th{{color:var(--muted)}}
dl{{display:grid;grid-template-columns:minmax(150px,260px) 1fr;gap:6px 14px}}dt{{color:var(--muted)}}dd{{margin:0;overflow-wrap:anywhere}}
code{{color:#bae6fd}}@media(max-width:760px){{table{{display:block;overflow-x:auto}}dl{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>Crypto Radar</h1><nav>{nav}</nav></header><main>
<div class="banner"><strong>Research idea, not a trade instruction.</strong> No execution, Event Alpha paper trading, normal RSI writes, or Event Alpha <code>TRIGGERED_FADE</code> creation.</div>
{authority_banner}
<div class="scope">{badges}<br>{scope}<br>Doctor: {_h(snapshot.doctor_status)} at revision {_h(snapshot.doctor_verified_revision if snapshot.doctor_verified_revision is not None else 'not verified')}</div>
<h2>{_h(title)}</h2>{body}</main></body></html>"""


def _generation_badges(snapshot: DashboardSnapshot) -> str:
    state = snapshot.operator_state
    provenance = _canonical_generation_market_provenance(state)
    claimed_mode = str(
        state.get("data_mode")
        or next(
            (
                row.get("data_mode")
                or (
                    row.get("decision_projection", {}).get("source_provider_lineage", {}).get("data_mode")
                    if isinstance(row.get("decision_projection"), Mapping)
                    and isinstance(row.get("decision_projection", {}).get("source_provider_lineage"), Mapping)
                    else None
                )
                for row in snapshot.current_candidates
                if isinstance(row, Mapping)
                and (
                    row.get("data_mode")
                    or isinstance(row.get("decision_projection"), Mapping)
                )
            ),
            None,
        )
        or state.get("run_mode")
        or "unknown"
    ).strip().casefold()
    source_mode = str(
        provenance.get("candidate_source_mode")
        or provenance.get("data_acquisition_mode")
        or claimed_mode
    ).strip().casefold()
    if not provenance and source_mode in {"live_no_send", "live_provider", "live"}:
        source_mode = "unverified_live_claim"
    stale = any(
        "stale" in str(reason).casefold() or "age" in str(reason).casefold()
        for reason in snapshot.generation_authority_reasons
    )
    status_label = "STALE" if stale else (
        "CURRENT" if snapshot.generation_authoritative else "UNTRUSTED"
    )
    status_class = "stale" if stale or not snapshot.generation_authoritative else "current"
    exact_modes = {
        "live_no_send": ("LIVE / REAL DATA", "live"),
        "live_provider": ("LIVE / REAL DATA", "live"),
        "live": ("LIVE / REAL DATA", "live"),
        "mocked_fixture": ("MOCKED FIXTURE", "fixture"),
        "mock_fixture": ("MOCKED FIXTURE", "fixture"),
        "mock": ("MOCKED FIXTURE", "fixture"),
        "artifact_replay": ("ARTIFACT REPLAY", "fixture"),
        "cached": ("CACHED DATA", "fixture"),
        "preflight_only": ("PREFLIGHT ONLY", "stale"),
        "unverified_live_claim": ("UNVERIFIED LIVE CLAIM", "stale"),
        "untrusted_provenance": ("UNTRUSTED PROVENANCE", "stale"),
        "fixture": ("FIXTURE", "fixture"),
    }
    mode_label, mode_class = exact_modes.get(
        source_mode,
        (source_mode.upper() or "UNKNOWN MODE", "stale"),
    )
    is_live = bool(provenance) and source_mode in {
        "live_no_send", "live_provider", "live",
    }
    no_send = state.get("send_attempted") is False
    burn_in_counted = bool(
        provenance.get("provenance_contract_valid") is True
        and provenance.get("burn_in_counted") is True
        and is_live
    )
    values = (
        (status_label, status_class),
        (mode_label or "UNKNOWN MODE", mode_class),
        ("NO-SEND" if no_send else "SEND STATE UNKNOWN", "current" if no_send else "stale"),
        (
            "BURN-IN COUNTED" if burn_in_counted else "BURN-IN EXCLUDED",
            "current" if burn_in_counted and is_live else "fixture",
        ),
    )
    return "".join(
        f'<span class="badge badge-{_h(css)}">{_h(label)}</span>'
        for label, css in values
    )


def _canonical_generation_market_provenance(
    state: Mapping[str, Any],
) -> Mapping[str, Any]:
    raw = state.get("market_no_send_provenance")
    if not isinstance(raw, Mapping):
        raw = state.get("market_data_provenance")
    if not isinstance(raw, Mapping) or not raw:
        return {}
    normalized = market_provenance.normalize_market_provenance(raw)
    if (
        normalized.get("provenance_contract_valid") is True
        and dict(raw) == normalized
    ):
        return normalized
    return {
        "candidate_source_mode": "untrusted_provenance",
        "provenance_contract_valid": False,
        "burn_in_eligible": False,
        "burn_in_counted": False,
    }


def _standalone_error(title: str, detail: str) -> str:
    return f"<!doctype html><html><head><meta charset=\"utf-8\"><title>{_h(title)}</title></head><body><h1>{_h(title)}</h1><p>{_h(detail)}</p></body></html>"


def _authority_unavailable(snapshot: DashboardSnapshot) -> str:
    reasons = _text_list("Authority failures", snapshot.generation_authority_reasons)
    return (
        "<p><strong>Current-generation research content is unavailable because generation authority "
        "did not pass.</strong> Provider/system health and explicitly cumulative feedback/outcomes remain visible.</p>"
        + reasons
    )


def _section(title: str, body: str) -> str:
    return f"<section><h3>{_h(title)}</h3>{body}</section>"


def _table(headers: Iterable[str], rows: Iterable[Iterable[str]], *, empty: str = "No rows.") -> str:
    materialized = [tuple(row) for row in rows]
    if not materialized:
        return f'<p class="muted">{_h(empty)}</p>'
    head = "".join(f"<th>{_h(value)}</th>" for value in headers)
    body = "".join("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>" for row in materialized)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _definition_list(items: Iterable[tuple[str, object]]) -> str:
    return "<dl>" + "".join(f"<dt>{_h(key)}</dt><dd>{_h(value)}</dd>" for key, value in items) + "</dl>"


def _text_list(title: str, values: Iterable[str]) -> str:
    materialized = tuple(str(value) for value in values if str(value).strip())
    if not materialized:
        return f"<h3>{_h(title)}</h3><p class=\"muted\">None recorded.</p>"
    return f"<h3>{_h(title)}</h3><ul>" + "".join(f"<li>{_h(value)}</li>" for value in materialized) + "</ul>"


def _score_components(title: str, value: object) -> str:
    if not isinstance(value, Mapping) or not value:
        return f'<h3>{_h(title)}</h3><p class="muted">No component detail recorded.</p>'
    rows = [(_h(key), _h(component)) for key, component in sorted(value.items()) if not isinstance(component, (Mapping, list, tuple, set))]
    return f"<h3>{_h(title)}</h3>" + _table(("Component", "Value"), rows)


def _values(row: Mapping[str, Any], *fields: str) -> tuple[str, ...]:
    out = []
    for field in fields:
        value = row.get(field)
        if isinstance(value, str):
            if value.strip():
                out.append(value.strip())
        elif isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
            out.extend(str(item).strip() for item in value if str(item).strip())
    return tuple(dict.fromkeys(out))


def _window_label(row: Mapping[str, Any]) -> str:
    start = str(row.get("window_start") or "").strip()
    end = str(row.get("window_end") or "").strip()
    certainty = str(row.get("time_certainty") or "unknown")
    if start or end:
        return f"{start or 'unknown'} → {end or 'unknown'} ({certainty})"
    return certainty


def _economic_context_label(row: Mapping[str, Any]) -> str:
    values = (
        _display_number(row.get("previous_value")),
        _display_number(row.get("forecast_value")),
        _display_number(row.get("actual_value")),
        _display_number(row.get("surprise_value")),
    )
    return " / ".join(values)


def _impact_window_label(row: Mapping[str, Any]) -> str:
    before = str(row.get("impact_window_before") or "unknown").strip()
    after = str(row.get("impact_window_after") or "unknown").strip()
    return f"-{before} / +{after}"


def _display_number(value: object) -> str:
    number = _finite_number(value)
    if number is None:
        return "—"
    return f"{number:g}"


def _asset_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("symbol") or row.get("validated_symbol") or "").strip().upper(),
        str(row.get("coin_id") or row.get("validated_coin_id") or "").strip().casefold(),
    )


def _source_link(row: Mapping[str, Any]) -> str:
    raw = str(row.get("source_url") or row.get("latest_source_url") or row.get("url") or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return '<span class="muted">unsafe or unavailable source URL</span>'
    label = str(row.get("source") or row.get("latest_source") or parsed.netloc)
    return f'<a href="{_h(raw)}" rel="noreferrer" target="_blank">{_h(label)}</a>'


def _score(value: object) -> str:
    try:
        return f"{float(value):.0f}/100"
    except (TypeError, ValueError):
        return "n/a"


def _h(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


__all__ = ("filter_sort_candidates", "render_dashboard_page")
