"""Operator Experience V1 health, learning, and campaign-history pages."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from .campaign_page import render_campaign_page
from .components import (
    HtmlFragment,
    badge,
    data_table,
    definition_list,
    disclosure,
    empty_state,
    escape_html,
    time_element,
)
from .layer_coverage import (
    DashboardLayerCoverage,
    dashboard_layer_coverage,
    dashboard_layer_coverage_by_key,
)
from .models import DashboardSnapshot
from .presentation import (
    UNAVAILABLE,
    format_duration,
    format_number,
    humanize_enum,
    humanize_reason,
    present_time,
    semantic_status,
)
from .system_page_support import (
    as_mapping as _mapping,
    as_number as _number,
    display_count as _count,
    render_metric_grid as _metric_grid,
    render_page_intro as _page_intro,
    render_panel as _panel,
    summarize_market_quality as _quality_summary,
)


_MATURED_OUTCOME_STATES = {
    "complete",
    "completed",
    "filled",
    "graded",
    "mature",
    "matured",
    "resolved",
}
_PENDING_OUTCOME_STATES = {
    "",
    "awaiting_data",
    "awaiting_horizon",
    "open",
    "pending",
    "scheduled",
}


def render_health_page(snapshot: DashboardSnapshot) -> str:
    """Render exact trust, provider, acquisition, and quality state."""

    providers = _provider_items(snapshot.provider_readiness)
    assessments = tuple(_provider_assessment(item) for item in providers)
    failures = sum(1 for item in assessments if item[1] == "danger")
    disabled = sum(1 for item in assessments if item[0] == "Disabled / not selected")
    missing = sum(
        1
        for item in assessments
        if item[0] in {"Authorization missing", "Not configured"}
    )
    rows = snapshot.current_market_observations
    quality = _quality_summary(rows, snapshot.market_generation)
    coverage = dashboard_layer_coverage(snapshot)
    coverage_by_key = {row.key: row for row in coverage}
    layer_gaps = sum(1 for row in coverage if row.action_required)
    status_tone = "positive" if snapshot.generation_authoritative else "danger"
    metrics = (
        ("Current authority", humanize_enum(snapshot.generation_authority_status), status_tone),
        ("Strict doctor", humanize_enum(snapshot.doctor_status), _status_tone(snapshot.doctor_status)),
        ("Layer gaps", str(layer_gaps), "warning" if layer_gaps else "positive"),
        ("Actual failures", str(failures), "danger" if failures else "positive"),
        ("Disabled / not selected", str(disabled), "muted"),
        ("Missing setup", str(missing), "warning" if missing else "positive"),
        (
            "Market observations",
            str(len(rows)) if snapshot.generation_authoritative else "Suppressed",
            "info" if snapshot.generation_authoritative else "danger",
        ),
    )
    return (
        _page_intro(
            "System Health",
            "Exact run trust, provider state, acquisition evidence, and data-quality constraints.",
            "Current-generation evidence",
        )
        + _metric_grid(metrics)
        + _health_action_summary(
            snapshot,
            failures=failures,
            disabled=disabled,
            missing=missing,
            quality=quality,
            coverage=coverage,
        )
        + _current_contract(snapshot)
        + _layer_coverage_section(coverage)
        + _provider_readiness_section(providers)
        + _request_ledger_section(snapshot, coverage_by_key["request_ledger"])
        + _market_quality_section(snapshot, quality)
        + _source_coverage_section(snapshot)
        + _historical_provider_health(snapshot)
        + _technical_health_details(snapshot)
    )


def render_outcomes_page(
    snapshot: DashboardSnapshot,
    query: Mapping[str, str] | None,
) -> str:
    """Render exact outcome placeholders separately from historical learning."""

    filters = _outcome_filters(query)
    current = tuple(snapshot.current_outcomes)
    historical = _historical_outcomes(snapshot)
    filtered_current = _filter_outcomes(current, filters)
    filtered_history = _filter_outcomes(
        tuple(row for row, _source in historical),
        filters,
    )
    history_sources = {
        _outcome_key(row): source for row, source in historical
    }
    current_counts = _outcome_counts(current)
    historical_counts = _outcome_counts(tuple(row for row, _source in historical))
    current_matured = current_counts["matured"]
    history_matured = historical_counts["matured"]
    outcome_layer = dashboard_layer_coverage_by_key(snapshot)["outcomes"]
    outcome_authority = str(snapshot.current_outcomes_metadata.get("authority") or "").strip()
    outcome_authority_label = (
        humanize_enum(outcome_authority)
        if outcome_authority
        else humanize_enum(outcome_layer.status)
    )
    current_value = str(len(current)) if snapshot.generation_authoritative else "Suppressed"
    metrics = (
        ("Current ideas tracked", current_value, "info" if snapshot.generation_authoritative else "danger"),
        (
            "Current outcome coverage",
            humanize_enum(outcome_layer.status),
            _coverage_tone(outcome_layer.status),
        ),
        (
            "Current pending",
            str(current_counts["pending"]) if snapshot.generation_authoritative else "Suppressed",
            "warning" if snapshot.generation_authoritative else "danger",
        ),
        (
            "Current matured",
            str(current_matured) if snapshot.generation_authoritative else "Suppressed",
            "positive" if current_matured and snapshot.generation_authoritative else "muted",
        ),
        ("Historical rows", str(len(historical)), "neutral"),
        ("Historical matured", str(history_matured), "positive" if history_matured else "muted"),
        ("Optional feedback", str(len(snapshot.cumulative_feedback)), "info"),
    )
    sections: list[str] = [
        _page_intro(
            "Outcomes & Learning",
            "Pending ideas, matured observations, and score cohorts. Evidence confidence is not win probability.",
            "Research-only learning loop",
        ),
        _metric_grid(metrics),
        _outcome_filter_form(filters),
    ]
    if not snapshot.generation_authoritative:
        sections.append(
            _panel(
                "Current outcome rows suppressed",
                (
                    "Current outcome rows are unavailable because generation authority "
                    "did not pass. Historical campaign rows remain separately labeled context."
                ),
                eyebrow="Fail-closed authority",
            )
        )
    else:
        sections.append(_sample_warning(current_matured, scope="exact current generation"))
    if snapshot.generation_authoritative and filters["scope"] in {"all", "current"}:
        sections.append(
            _outcome_section(
                "Exact current-generation outcomes",
                (
                    "Fingerprint-verified placeholders and outcomes for this run only; the coverage badge still reports count or contract gaps."
                    if outcome_authority == "current_generation_fingerprint_verified"
                    and snapshot.current_outcomes_metadata.get("sha256")
                    else "Exact current-generation outcome coverage; unavailable or rejected data is never presented as verified."
                ),
                filtered_current,
                source_labels=None,
                empty_message=_current_outcome_empty_message(
                    current=current,
                    filtered_current=filtered_current,
                    layer=outcome_layer,
                ),
                authority=outcome_authority_label,
            )
        )
    if filters["scope"] in {"all", "historical"}:
        sections.extend(
            (
                _sample_warning(history_matured, scope="historical campaign"),
                _outcome_section(
                    "Historical campaign outcomes",
                    (
                        "Historical / non-authoritative for the current generation. These rows "
                        "support learning but never alter current visibility or thresholds."
                    ),
                    filtered_history,
                    source_labels=history_sources,
                    empty_message="No historical outcome rows match these filters.",
                    authority="Historical / non-authoritative",
                ),
            )
        )
    sections.extend((_cohort_summary(current, historical), _feedback_summary(snapshot)))
    return "".join(sections)


def _health_action_summary(
    snapshot: DashboardSnapshot,
    *,
    failures: int,
    disabled: int,
    missing: int,
    quality: Mapping[str, int],
    coverage: tuple[DashboardLayerCoverage, ...],
) -> str:
    items: list[tuple[str, str, str]] = []
    if not snapshot.generation_authoritative:
        items.append((
            "Current generation is not authoritative",
            "Pointer, manifest, exact-artifact, or strict-doctor authority checks did not pass.",
            "danger",
        ))
    if snapshot.doctor_status.casefold() != "ok":
        items.append((
            "Strict doctor requires attention",
            f"The exact strict-doctor state is {humanize_enum(snapshot.doctor_status)}.",
            "danger" if snapshot.doctor_status.casefold() not in {"warn", "warning"} else "warning",
        ))
    if failures:
        items.append((
            "Actual provider failures need review",
            f"{failures} provider state{'s' if failures != 1 else ''} record a failure, degraded response, or backoff.",
            "danger",
        ))
    if missing:
        items.append((
            "Configuration or authorization is missing",
            f"{missing} provider state{'s' if missing != 1 else ''} cannot be selected until explicit setup exists.",
            "warning",
        ))
    if disabled:
        items.append((
            "Disabled providers are not failures",
            f"{disabled} provider state{'s' if disabled != 1 else ''} were disabled or not selected; no request was expected.",
            "muted",
        ))
    if quality["warming"] or quality["cold"]:
        items.append((
            "Temporal evidence is still warming",
            f"{quality['warming']} warming and {quality['cold']} cold assets are retained without being presented as mature.",
            "warning",
        ))
    if snapshot.current_market_observations and not quality["spread"]:
        items.append((
            "Spread evidence is unavailable",
            "No current asset has verified execution spread, so actionable execution-quality claims remain capped.",
            "warning",
        ))
    for layer in coverage:
        if not layer.action_required:
            continue
        items.append((
            _coverage_action_title(layer),
            layer.detail,
            _coverage_tone(layer.status),
        ))
    if not items:
        items.append((
            "No action-required health constraint",
            "Authority, strict doctor, provider acquisition, current quality, and every expected product layer are healthy or explicitly not applicable.",
            "positive",
        ))
    body = "".join(
        '<article class="health-action">'
        f"{badge(title, tone=tone)}<p>{escape_html(detail)}</p></article>"
        for title, detail, tone in items
    )
    return _panel("Operator action summary", body, eyebrow="What needs attention")


def _current_contract(snapshot: DashboardSnapshot) -> str:
    state = snapshot.operator_state
    checked = time_element(present_time(snapshot.generation_authority_checked_at))
    generated = time_element(
        present_time(state.get("generated_at") or state.get("run_started_at"))
    )
    doctor_revision = (
        snapshot.doctor_verified_revision
        if snapshot.doctor_verified_revision is not None
        else UNAVAILABLE
    )
    values = (
        ("Pointer / publication authority", badge(snapshot.generation_authority_status)),
        ("Namespace", snapshot.artifact_namespace),
        ("Run", snapshot.run_id),
        ("Revision", snapshot.revision),
        ("Strict doctor", badge(snapshot.doctor_status)),
        ("Doctor verified revision", doctor_revision),
        ("Manifest", badge(snapshot.manifest_status)),
        ("Authority checked", checked),
        ("Generation started", generated),
        ("Research only", badge(state.get("research_only") is True)),
        ("No-send enforced", badge(state.get("send_attempted") is False)),
    )
    reasons = ""
    if snapshot.generation_authority_reasons:
        reasons = (
            '<div class="alert alert-danger"><strong>Authority blockers</strong><ul>'
            + "".join(
                f"<li>{escape_html(humanize_reason(reason))}</li>"
                for reason in snapshot.generation_authority_reasons
            )
            + "</ul></div>"
        )
    return _panel(
        "Exact operator generation",
        str(definition_list(values, css_class="definition-grid")) + reasons,
        eyebrow="Pointer-bound truth",
    )


def _layer_coverage_section(
    coverage: tuple[DashboardLayerCoverage, ...],
) -> str:
    rows = [
        (
            layer.label,
            badge(layer.status, tone=_coverage_tone(layer.status)),
            "Expected" if layer.expected else "Not applicable",
            layer.row_count,
            layer.detail,
        )
        for layer in coverage
    ]
    return _panel(
        "Product-layer coverage",
        str(
            data_table(
                ("Layer", "State", "Contract", "Rows", "Meaning"),
                rows,
                caption="Canonical exact-generation layer coverage",
                empty="No product-layer coverage projection is available.",
            )
        )
        + (
            '<p class="muted">Healthy empty means the configured exact layer was observed and '
            "returned zero rows. Missing, unavailable, stale, or rejected coverage never means "
            "nothing exists.</p>"
        ),
        eyebrow="One coverage contract",
    )


def _coverage_action_title(layer: DashboardLayerCoverage) -> str:
    if layer.key == "request_ledger":
        return f"Provider request ledger {humanize_enum(layer.status).casefold()}"
    if layer.key == "calendar" and layer.status == "not_configured":
        return "Calendar acquisition not configured"
    return f"{layer.label} {humanize_enum(layer.status).casefold()}"


def _coverage_tone(status: str) -> str:
    if status in {"healthy_nonempty", "healthy_empty"}:
        return "positive"
    if status == "not_applicable":
        return "muted"
    if status in {"rejected", "stale"}:
        return "danger"
    return "warning"


def _provider_readiness_section(
    providers: tuple[Mapping[str, Any], ...],
) -> str:
    rows: list[tuple[object, ...]] = []
    for item in providers:
        label, tone, detail = _provider_assessment(item)
        provider = item.get("provider") or item.get("provider_name") or item.get("name")
        last = present_time(
            item.get("last_success_at")
            or item.get("last_success")
            or item.get("latest_rehearsal_generated_at")
        )
        last_label: object = time_element(last, primary="relative") if last.available else UNAVAILABLE
        rows.append((
            humanize_enum(provider),
            badge(label, tone=tone),
            detail,
            last_label,
        ))
    table = data_table(
        ("Provider", "State", "What it means", "Last evidence"),
        rows,
        caption="Exact-generation provider readiness",
        empty="No provider-readiness rows are attached to this exact generation.",
    )
    return _panel(
        "Provider readiness",
        str(table)
        + '<p class="muted">Disabled, not selected, and missing authorization are setup states—not request failures.</p>',
        eyebrow="Expected vs failed",
    )


def _request_ledger_section(
    snapshot: DashboardSnapshot,
    coverage: DashboardLayerCoverage,
) -> str:
    ledger = snapshot.current_request_ledger
    if not ledger:
        error = snapshot.current_request_ledger_metadata.get("error")
        detail = coverage.detail
        if error not in (None, ""):
            detail += f" Read issue: {humanize_reason(error)}"
        body = empty_state(
            f"Exact request ledger {humanize_enum(coverage.status).casefold()}",
            detail,
        )
        return _panel(
            "Provider request",
            str(badge(coverage.status, tone=_coverage_tone(coverage.status))) + str(body),
            eyebrow="Exact acquisition evidence",
        )
    start = time_element(present_time(ledger.get("request_started_at")))
    end = time_element(present_time(ledger.get("request_ended_at")))
    duration = format_duration(
        _duration_seconds(ledger.get("duration_ms"), milliseconds=True)
    )
    http = ledger.get("http_status")
    http_label = f"HTTP {http}" if http not in (None, "") else UNAVAILABLE
    values = (
        ("Provider", humanize_enum(ledger.get("provider"))),
        ("Authorization present", badge(ledger.get("live_provider_authorized") is True)),
        ("Provider call attempted", badge(ledger.get("provider_call_attempted") is True)),
        ("Request succeeded", badge(ledger.get("provider_request_succeeded") is True)),
        ("Response", http_label),
        ("Request started", start),
        ("Request ended", end),
        ("Duration", duration),
        ("Rows returned / selected", f"{_count(ledger.get('result_count'))} / {_count(ledger.get('selected_market_row_count'))}"),
        ("Retries", _count(ledger.get("retry_count"))),
        ("Cache behavior", humanize_enum(ledger.get("cache_behavior") or ledger.get("cache_status"))),
        ("Data mode", humanize_enum(ledger.get("candidate_source_mode") or ledger.get("data_mode"))),
        ("No-send", badge(ledger.get("no_send") is True)),
        ("Side effects", _side_effect_summary(ledger)),
    )
    failure = ""
    if ledger.get("error_class"):
        failure = (
            '<div class="alert alert-danger"><strong>Actual request failure:</strong> '
            f"{escape_html(humanize_reason(ledger.get('error_class')))}</div>"
        )
    return _panel(
        "Provider request",
        str(badge(coverage.status, tone=_coverage_tone(coverage.status)))
        + str(definition_list(values, css_class="definition-grid"))
        + failure,
        eyebrow="Exact acquisition evidence",
    )


def _market_quality_section(
    snapshot: DashboardSnapshot,
    summary: Mapping[str, int],
) -> str:
    generation = snapshot.market_generation
    provenance = _mapping(generation.get("market_provenance"))
    data_quality = _mapping(provenance.get("data_quality"))
    feature_basis = _mapping(provenance.get("feature_basis"))
    freshness = _freshness_counts(snapshot.current_market_observations)
    values = (
        ("Fresh / warming / stale / unknown", _ordered_counts(freshness, ("fresh", "warming", "stale", "unknown"))),
        ("Warm / warming / cold baselines", f"{summary['warm']} / {summary['warming']} / {summary['cold']}"),
        ("Spread verified", f"{summary['spread']} / {len(snapshot.current_market_observations)}"),
        ("Direct feature evidence", _count(data_quality.get("direct_feature_count") or generation.get("direct_feature_count"))),
        ("Proxy feature evidence", _count(data_quality.get("proxy_feature_count") or generation.get("proxy_feature_count"))),
        ("Return basis", humanize_enum(feature_basis.get("returns"))),
        ("Volume basis", humanize_enum(feature_basis.get("volume_zscore_24h") or feature_basis.get("volume_zscore"))),
        ("Liquidity basis", humanize_enum(feature_basis.get("liquidity"))),
        ("Spread basis", humanize_enum(feature_basis.get("spread"))),
        ("Campaign cadence", humanize_enum(generation.get("cadence_status") or "not_recorded")),
        ("Next eligible observation", time_element(present_time(generation.get("next_eligible_observation_at")))),
    )
    return _panel(
        "Market data quality",
        str(definition_list(values, css_class="definition-grid"))
        + '<p class="muted">Direct observations and proxy features remain visibly separate. Warming is evidence progress, not failure.</p>',
        eyebrow="Freshness, baseline, spread",
    )


def _source_coverage_section(snapshot: DashboardSnapshot) -> str:
    raw = snapshot.source_coverage.get("packs")
    packs = (
        tuple(item for item in raw if isinstance(item, Mapping))
        if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping))
        else ()
    )
    rows = []
    for item in packs:
        status = item.get("provider_coverage_status") or item.get("source_pack_coverage_status")
        missing = _joined(item.get("missing_providers"))
        gap = item.get("coverage_gap_reason") or item.get("source_coverage_gap_reason")
        detail = (
            humanize_reason(gap)
            if gap not in (None, "")
            else "No coverage gap recorded."
        )
        if missing != UNAVAILABLE:
            detail = f"{detail} Missing: {missing}."
        rows.append((
            humanize_enum(item.get("source_pack")),
            badge(status),
            _count(item.get("accepted_evidence_count")),
            _joined(item.get("healthy_providers")),
            detail,
        ))
    return _panel(
        "Source-pack coverage",
        str(data_table(
            ("Source pack", "State", "Accepted", "Healthy providers", "Coverage meaning"),
            rows,
            caption="Exact-generation source coverage",
            empty="No source-pack coverage assessment is attached.",
        )),
        eyebrow="Coverage is not absence",
    )


def _historical_provider_health(snapshot: DashboardSnapshot) -> str:
    providers = _provider_items(snapshot.provider_health)
    rows = []
    for item in providers:
        label, tone, detail = _provider_assessment(item)
        rows.append((
            humanize_enum(item.get("provider") or item.get("name") or item.get("provider_key")),
            badge(label, tone=tone),
            detail,
        ))
    body: object = data_table(
        ("Provider", "Historical state", "Meaning"),
        rows,
        caption="Cumulative provider health · non-authoritative",
        empty="No cumulative provider-health rows are available.",
    )
    metadata = (
        f"Read {time_element(present_time(snapshot.provider_health_read_at))}. "
        "This cumulative file is context only and cannot override exact current readiness."
    )
    return str(disclosure(
        "Cumulative provider health",
        HtmlFragment(str(body) + f'<p class="muted">{metadata}</p>'),
        summary="Historical / non-authoritative",
        css_class="technical-details",
    ))


def _technical_health_details(snapshot: DashboardSnapshot) -> str:
    artifacts = _mapping(snapshot.operator_state.get("artifacts"))
    artifact_paths = []
    for name, value in sorted(artifacts.items()):
        item = _mapping(value)
        if item.get("path"):
            artifact_paths.append((humanize_enum(name), item.get("path")))
    values: list[tuple[object, object]] = [
        ("Artifact namespace", snapshot.artifact_namespace),
        ("Operator-state SHA-256", snapshot.operator_state_sha256),
        ("Current outcomes SHA-256", snapshot.current_outcomes_metadata.get("sha256") or UNAVAILABLE),
        ("Request ledger SHA-256", snapshot.current_request_ledger_metadata.get("sha256") or UNAVAILABLE),
        ("Market history SHA-256", snapshot.exact_market_history_metadata.get("sha256") or UNAVAILABLE),
        ("Provider-health SHA-256", snapshot.provider_health_sha256 or UNAVAILABLE),
        *artifact_paths,
    ]
    return str(disclosure(
        "Technical evidence",
        definition_list(values, css_class="technical-grid"),
        summary="Paths and fingerprints",
        css_class="technical-details",
    ))


def _outcome_section(
    title: str,
    description: str,
    rows: tuple[Mapping[str, Any], ...],
    *,
    source_labels: Mapping[tuple[str, ...], str] | None,
    empty_message: str,
    authority: str,
) -> str:
    table_rows = []
    for row in rows:
        state = _outcome_state(row)
        source = source_labels.get(_outcome_key(row), UNAVAILABLE) if source_labels else "Exact generation"
        table_rows.append((
            row.get("symbol") or row.get("coin_id") or row.get("candidate_id") or "Idea",
            badge(state),
            humanize_enum(row.get("radar_route") or row.get("route")),
            _outcome_time(row),
            humanize_enum(row.get("primary_horizon") or row.get("preferred_horizon")),
            _cohort_label(row.get("actionability_score_cohort"), row.get("actionability_score")),
            _cohort_label(row.get("evidence_confidence_score_cohort"), row.get("evidence_confidence_score")),
            _cohort_label(row.get("risk_score_cohort"), row.get("risk_score")),
            humanize_enum(row.get("outcome_label") or row.get("validation_label")),
            source,
        ))
    table = data_table(
        (
            "Idea", "State", "Route", "Observed / evaluated", "Horizon",
            "Actionability cohort", "Evidence cohort", "Risk cohort", "Result", "Scope",
        ),
        table_rows,
        caption=title,
        empty=empty_message,
    )
    return _panel(
        title,
        f'<p>{escape_html(description)}</p>'
        + str(badge(authority, tone="info" if "historical" in authority.casefold() else None))
        + str(table),
        eyebrow="Pending and matured",
    )


def _current_outcome_empty_message(
    *,
    current: tuple[Mapping[str, Any], ...],
    filtered_current: tuple[Mapping[str, Any], ...],
    layer: DashboardLayerCoverage,
) -> str:
    if current and not filtered_current:
        return (
            "Exact current outcome rows exist, but none match the selected filters. "
            "Clear or adjust the filters to see them."
        )
    if layer.status == "healthy_empty":
        return (
            "The fingerprint-verified outcome artifact is empty for this zero-idea generation. "
            "That is a verified empty result, not a missing artifact."
        )
    if layer.status == "not_applicable":
        return (
            "This generation has no canonical current ideas, so no outcome placeholder is required. "
            "No fingerprint-verification claim is made for an absent artifact."
        )
    if layer.status == "rejected":
        return (
            "The exact outcome artifact was rejected and no current rows were admitted. "
            "Zero rows is not a verified empty result."
        )
    if layer.status == "stale":
        return (
            "The exact outcome artifact is stale and cannot be presented as current. "
            "Zero rows is not a verified empty result."
        )
    return (
        "No fingerprint-verified exact outcome artifact is available for the current ideas. "
        "Zero rows is not a verified empty result."
    )


def _cohort_summary(
    current: tuple[Mapping[str, Any], ...],
    historical: tuple[tuple[Mapping[str, Any], str], ...],
) -> str:
    matured = [
        row
        for row in (*current, *(row for row, _source in historical))
        if _outcome_bucket(row) == "matured"
    ]
    route_counts = Counter(
        humanize_enum(row.get("radar_route") or row.get("route"))
        for row in matured
    )
    rows = [
        (route, count, "Descriptive only · no automatic threshold")
        for route, count in route_counts.most_common()
    ]
    return _panel(
        "Matured route cohorts",
        str(data_table(
            ("Route cohort", "Matured rows", "Use"),
            rows,
            caption="Matured sample by Decision route",
            empty="No matured outcome cohort is available yet.",
        ))
        + '<p class="muted">Cohort summaries need adequate sample size and diversity before supporting any human policy review.</p>',
        eyebrow="Learning, not auto-calibration",
    )


def _feedback_summary(snapshot: DashboardSnapshot) -> str:
    counts = Counter(
        humanize_enum(
            row.get("feedback_label")
            or row.get("label")
            or row.get("human_label")
            or "unclassified"
        )
        for row in snapshot.cumulative_feedback
    )
    rows = [(label, count) for label, count in counts.most_common()]
    return _panel(
        "Optional human feedback",
        str(data_table(
            ("Preference label", "Rows"),
            rows,
            caption="Cumulative optional feedback",
            empty="No optional human preference feedback has been recorded.",
        ))
        + (
            '<p class="muted">Feedback is preference data only. It does not automatically change scores, routes, gates, or visibility.</p>'
        ),
        eyebrow="Human input",
    )


def _provider_items(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = payload.get("providers") if isinstance(payload, Mapping) else None
    if isinstance(raw, Mapping):
        return tuple(
            dict(value, provider=value.get("provider") or key)
            if isinstance(value, Mapping)
            else {"provider": key, "status": value}
            for key, value in raw.items()
        )
    if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
        return tuple(item for item in raw if isinstance(item, Mapping))
    if isinstance(payload, Mapping) and payload:
        candidates = []
        for key, value in payload.items():
            if isinstance(value, Mapping) and (
                "status" in value
                or "configured" in value
                or "provider" in value
                or "health_status" in value
            ):
                candidates.append(dict(value, provider=value.get("provider") or key))
        return tuple(candidates)
    return ()


def _provider_assessment(item: Mapping[str, Any]) -> tuple[str, str, str]:
    status = str(
        item.get("status")
        or item.get("readiness_status")
        or item.get("health_status")
        or item.get("latest_provider_health_status")
        or item.get("activation_phase")
        or item.get("preflight_status")
        or ""
    ).strip().casefold()
    reason = str(
        item.get("reason")
        or item.get("status_detail")
        or item.get("skip_reason")
        or item.get("error_class")
        or item.get("last_error_safe")
        or ""
    ).strip()
    combined = f"{status} {reason}".casefold()
    failures = _number(item.get("consecutive_failures"))
    http = _number(item.get("request_http_status") or item.get("http_status"))
    if (
        (failures is not None and failures > 0)
        or (http is not None and http >= 400)
        or any(token in combined for token in ("failed", "failure", "degraded", "backoff", "rate_limit", "unavailable", "timeout"))
    ):
        detail = (
            f"Actual provider failure. {humanize_reason(reason, fallback=humanize_enum(status))}"
        )
        if http is not None:
            detail += f" Last response: HTTP {int(http)}."
        return "Provider failure", "danger", detail
    if any(token in combined for token in ("auth", "credential", "api_key", "missing_key", "token_missing")):
        return (
            "Authorization missing",
            "warning",
            "No request was expected because explicit provider authorization or credentials are missing.",
        )
    configured = item.get("configured")
    if configured is False or status in {"not_configured", "missing_config"}:
        return (
            "Not configured",
            "warning",
            "No request was expected because required provider configuration is absent.",
        )
    if (
        item.get("enabled_by_default") is False
        or item.get("live_call_allowed") is False
        or status in {"disabled", "not_selected", "skipped_live_calls_disabled", "config_ready_no_live"}
    ):
        return (
            "Disabled / not selected",
            "muted",
            "This provider was not selected for a live call; that is not a request failure.",
        )
    if any(token in combined for token in ("warming", "cold", "insufficient_history")):
        return (
            "Warming",
            "warning",
            "Acquisition is available, but the temporal evidence window is not mature yet.",
        )
    if (
        item.get("last_success_at")
        or item.get("last_success")
        or status in {"healthy", "observed_healthy", "complete", "ready", "success"}
        or (http is not None and 200 <= http < 300)
    ):
        return (
            "Observed healthy",
            "positive",
            "The provider has current successful evidence for its configured role.",
        )
    return (
        "Not observed",
        "neutral",
        "No current success or failure evidence was recorded for this provider.",
    )


def _freshness_counts(rows: Iterable[Mapping[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        token = str(
            row.get("freshness_status")
            or row.get("market_data_freshness")
            or "unknown"
        ).strip().casefold()
        counts[token] += 1
    return counts


def _outcome_filters(query: Mapping[str, str] | None) -> dict[str, str]:
    raw = query or {}
    scope = str(raw.get("scope") or "all").casefold()
    status = str(raw.get("status") or "all").casefold()
    return {
        "scope": scope if scope in {"all", "current", "historical"} else "all",
        "status": status if status in {"all", "pending", "matured"} else "all",
        "route": str(raw.get("route") or "").strip().casefold(),
        "search": str(raw.get("search") or "").strip().casefold(),
    }


def _filter_outcomes(
    rows: tuple[Mapping[str, Any], ...],
    filters: Mapping[str, str],
) -> tuple[Mapping[str, Any], ...]:
    selected = []
    for row in rows:
        if filters["status"] != "all" and _outcome_bucket(row) != filters["status"]:
            continue
        route = str(row.get("radar_route") or row.get("route") or "").casefold()
        if filters["route"] and route != filters["route"]:
            continue
        search_text = " ".join(
            str(row.get(field) or "")
            for field in ("symbol", "coin_id", "candidate_id", "core_opportunity_id")
        ).casefold()
        if filters["search"] and filters["search"] not in search_text:
            continue
        selected.append(row)
    return tuple(selected)


def _historical_outcomes(
    snapshot: DashboardSnapshot,
) -> tuple[tuple[Mapping[str, Any], str], ...]:
    rows: list[tuple[Mapping[str, Any], str]] = []
    seen: set[tuple[str, ...]] = set()
    for values, source in (
        (snapshot.campaign_outcomes, "Decision campaign"),
        (snapshot.cumulative_outcomes, "Namespace history"),
    ):
        for row in values:
            key = _outcome_key(row)
            if key in seen:
                continue
            seen.add(key)
            rows.append((row, source))
    return tuple(rows)


def _outcome_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("artifact_namespace") or ""),
        str(row.get("candidate_id") or row.get("core_opportunity_id") or ""),
        str(row.get("observed_at") or row.get("decision_evaluated_at") or ""),
    )


def _outcome_state(row: Mapping[str, Any]) -> str:
    return str(
        row.get("outcome_status")
        or row.get("maturation_state")
        or "pending"
    ).strip().casefold()


def _outcome_bucket(row: Mapping[str, Any]) -> str:
    state = _outcome_state(row)
    if state in _MATURED_OUTCOME_STATES or row.get("outcome_evaluated_at"):
        return "matured"
    if state in _PENDING_OUTCOME_STATES:
        return "pending"
    return "matured" if row.get("outcome_label") else "pending"


def _outcome_counts(rows: tuple[Mapping[str, Any], ...]) -> Counter[str]:
    return Counter(_outcome_bucket(row) for row in rows)


def _outcome_time(row: Mapping[str, Any]) -> HtmlFragment:
    value = (
        row.get("outcome_evaluated_at")
        or row.get("observed_at")
        or row.get("decision_evaluated_at")
    )
    return time_element(present_time(value))


def _cohort_label(value: object, score: object) -> str:
    text = str(value or "").strip()
    if text:
        parts = text.split("_")
        if len(parts) == 2 and all(part.replace(".", "", 1).isdigit() for part in parts):
            return f"{parts[0]}–{parts[1]}"
        return humanize_enum(text)
    number = _number(score)
    return format_number(number, decimals=1) if number is not None else UNAVAILABLE


def _sample_warning(matured: int, *, scope: str) -> str:
    if matured >= 30:
        return (
            '<div class="alert alert-positive"><strong>Sample-size checkpoint:</strong> '
            f"{matured} matured rows in the {escape_html(scope)}. Cohort diversity still matters.</div>"
        )
    return (
        '<div class="alert alert-warning"><strong>Small-sample warning:</strong> '
        f"Only {matured} matured row{'s' if matured != 1 else ''} in the {escape_html(scope)}. "
        "Do not infer edge or change thresholds from this sample.</div>"
    )


def _outcome_filter_form(filters: Mapping[str, str]) -> str:
    return (
        '<form class="filter-panel" method="get" action="/outcomes"><div class="filter-grid">'
        f'<label><span>Scope</span><select name="scope">{_options(filters["scope"], (("all", "Current + historical"), ("current", "Exact current"), ("historical", "Historical")))}</select></label>'
        f'<label><span>State</span><select name="status">{_options(filters["status"], (("all", "Pending + matured"), ("pending", "Pending"), ("matured", "Matured")))}</select></label>'
        f'<label><span>Route</span><input name="route" value="{escape_html(filters["route"])}" placeholder="Risk watch"></label>'
        f'<label><span>Search idea</span><input type="search" name="search" value="{escape_html(filters["search"])}" placeholder="BTC, DEXE…"></label>'
        '</div><div class="filter-actions"><button class="button button-primary" type="submit">Apply</button>'
        '<a class="button button-quiet" href="/outcomes">Clear</a></div></form>'
    )


def _options(selected: str, values: tuple[tuple[str, str], ...]) -> str:
    return "".join(
        f'<option value="{escape_html(value)}"{" selected" if selected == value else ""}>{escape_html(label)}</option>'
        for value, label in values
    )


def _technical_code(value: object) -> HtmlFragment:
    return HtmlFragment(f"<code>{escape_html(value)}</code>")


def _duration_seconds(value: object, *, milliseconds: bool = False) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return number / 1000.0 if milliseconds else number


def _joined(value: object) -> str:
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        items = [humanize_enum(item) for item in value if item not in (None, "")]
        return ", ".join(items) if items else UNAVAILABLE
    return humanize_enum(value)


def _ordered_counts(counts: Mapping[str, int], order: tuple[str, ...]) -> str:
    return " / ".join(str(counts.get(key, 0)) for key in order)


def _side_effect_summary(ledger: Mapping[str, Any]) -> str:
    fields = (
        ("Telegram sends", "telegram_sends"),
        ("Trades", "trades_created"),
        ("Paper trades", "paper_trades_created"),
        ("RSI writes", "normal_rsi_signal_rows_written"),
        ("Triggered fade", "triggered_fade_created"),
    )
    return " · ".join(f"{label} {_count(ledger.get(field))}" for label, field in fields)


def _status_tone(value: object) -> str:
    return semantic_status(value).tone


__all__ = (
    "render_campaign_page",
    "render_health_page",
    "render_outcomes_page",
)
