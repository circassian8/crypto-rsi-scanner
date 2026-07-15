"""Compatibility exports for dashboard health, outcomes, and campaign pages."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
import math
from typing import Any

from ... import config
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
)
from .maintenance_guidance import maintenance_expiry_guidance
from .models import DashboardSnapshot
from .outcomes_page import render_outcomes_page
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
    render_validation_badge as _validation_badge,
    summarize_market_quality as _quality_summary,
)

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
    integrity_status = (
        "Passed"
        if snapshot.doctor_status.casefold() == "ok"
        else humanize_enum(snapshot.doctor_status)
    )
    metrics = (
        ("Current authority", humanize_enum(snapshot.generation_authority_status), status_tone),
        ("Integrity checks", integrity_status, _status_tone(snapshot.doctor_status)),
        ("Provider failures", str(failures), "danger" if failures else "positive"),
        ("Coverage gaps", str(layer_gaps), "warning" if layer_gaps else "positive"),
    )
    return (
        _page_intro(
            "Trust and evidence status",
            "Exact run trust, provider state, acquisition evidence, and data-quality constraints.",
            "Current-generation evidence",
        )
        + '<div class="health-metrics">'
        + _metric_grid(metrics)
        + '</div>'
        + _health_action_summary(
            snapshot,
            failures=failures,
            disabled=disabled,
            missing=missing,
            quality=quality,
            coverage=coverage,
        )
        + _current_contract(snapshot)
        + _maintenance_status_section(snapshot)
        + _layer_coverage_section(coverage)
        + _provider_readiness_section(
            providers,
            now=snapshot.generation_authority_checked_at,
        )
        + _request_ledger_section(snapshot, coverage_by_key["request_ledger"])
        + _source_coverage_section(snapshot)
        + _market_quality_section(snapshot, quality)
        + _historical_provider_health(snapshot)
        + _technical_health_details(snapshot)
    )




def _operator_coverage_label(value: object) -> str:
    token = str(value or "").strip().casefold()
    return {
        "healthy_nonempty": "Complete",
        "healthy_empty": "Complete · empty",
        "degraded": "Incomplete",
        "not_configured": "Not configured",
        "not_applicable": "Not applicable",
    }.get(token, humanize_enum(value))


def _boolean_badge(
    value: object,
    *,
    false_tone: str = "muted",
) -> HtmlFragment:
    if value is True:
        return badge("Yes", tone="positive")
    if value is False:
        return badge("No", tone=false_tone)
    return badge("Not recorded", tone="neutral")


def _no_send_enforced_badge(send_attempted: object) -> HtmlFragment:
    if send_attempted is False:
        return badge("Yes", tone="positive")
    if send_attempted is True:
        return badge("No", tone="danger")
    return badge("Not recorded", tone="neutral")


def _health_action_summary(
    snapshot: DashboardSnapshot,
    *,
    failures: int,
    disabled: int,
    missing: int,
    quality: Mapping[str, int],
    coverage: tuple[DashboardLayerCoverage, ...],
) -> str:
    items: list[tuple[str, str, str, str]] = []
    if not snapshot.generation_authoritative:
        items.append((
            "Current generation is not authoritative",
            "Pointer, manifest, exact-artifact, or strict-doctor authority checks did not pass.",
            "danger",
            "#exact-generation",
        ))
    if snapshot.doctor_status.casefold() != "ok":
        items.append((
            "Integrity checks require attention",
            f"The exact run-integrity state is {humanize_enum(snapshot.doctor_status)}.",
            "danger" if snapshot.doctor_status.casefold() not in {"warn", "warning"} else "warning",
            "#exact-generation",
        ))
    if failures:
        items.append((
            "Actual provider failures need review",
            f"{failures} provider state{'s' if failures != 1 else ''} record a failure, degraded response, or backoff.",
            "danger",
            "#provider-readiness",
        ))
    if missing:
        items.append((
            "Configuration or authorization is missing",
            f"{missing} provider state{'s' if missing != 1 else ''} cannot be selected until explicit setup exists.",
            "warning",
            "#provider-readiness",
        ))
    if disabled:
        items.append((
            "Disabled providers are not failures",
            f"{disabled} provider state{'s' if disabled != 1 else ''} were disabled or not selected; no request was expected.",
            "muted",
            "#provider-readiness",
        ))
    if quality["warming"] or quality["cold"]:
        items.append((
            "Temporal evidence is still warming",
            f"{quality['warming']} warming and {quality['cold']} cold assets are retained without being presented as mature.",
            "warning",
            "#market-quality",
        ))
    if snapshot.current_market_observations and not quality["spread"]:
        items.append((
            "Spread evidence is unavailable",
            "No current asset has verified execution spread, so actionable execution-quality claims remain capped.",
            "warning",
            "#market-quality",
        ))
    coverage_items: list[tuple[str, str, str, str]] = []
    for layer in coverage:
        if not layer.action_required:
            continue
        coverage_items.append((
            _coverage_action_title(layer),
            layer.detail,
            _coverage_tone(layer.status),
            _coverage_action_href(layer),
        ))
    items.extend(coverage_items)
    if not items:
        items.append((
            "No action-required health constraint",
            "Authority, strict doctor, provider acquisition, current quality, and every expected product layer are healthy or explicitly not applicable.",
            "positive",
            "#exact-generation",
        ))
    groups = (
        ("blocking", "Blocking issues", {"danger"}),
        ("attention", "Constraints and setup", {"warning"}),
        ("context", "Expected or informational", {"muted"}),
        ("clear", "All clear", {"positive"}),
    )
    grouped = []
    for key, label, tones in groups:
        group_items = tuple(item for item in items if item[2] in tones)
        if not group_items:
            continue
        visible_limit = 3 if key == "attention" else len(group_items)
        visible_items = group_items[:visible_limit]
        remaining_items = group_items[visible_limit:]
        content = "".join(_health_action_link(*item) for item in visible_items)
        if remaining_items:
            remainder = "".join(_health_action_link(*item) for item in remaining_items)
            count = len(remaining_items)
            remaining_are_coverage = all(item in coverage_items for item in remaining_items)
            overflow_label = (
                f"Show all {count} product-layer gap{'s' if count != 1 else ''}"
                if remaining_are_coverage
                else f"Show {count} additional check{'s' if count != 1 else ''}"
            )
            content += (
                '<details class="disclosure health-action-overflow"><summary>'
                f'{escape_html(overflow_label)}'
                f'</summary><div class="disclosure__body">{remainder}</div></details>'
            )
        grouped.append(
            f'<div class="health-action-group health-action-group--{key}" role="group" '
            f'aria-labelledby="health-action-{key}"><h3 id="health-action-{key}">'
            f'{escape_html(label)}</h3>{content}</div>'
        )
    body = '<div class="health-action-groups">' + "".join(grouped) + "</div>"
    return _health_detail_panel(
        "Operator action summary",
        body,
        eyebrow="What needs attention",
        anchor="operator-action-summary",
    )


def _health_action_link(title: str, detail: str, tone: str, href: str) -> str:
    symbol = {"positive": "✓", "muted": "i"}.get(tone, "!")
    return (
        f'<a class="health-action" href="{escape_html(href)}" '
        f'data-tone="{escape_html(tone)}">'
        f'<span class="health-action__icon" aria-hidden="true">{symbol}</span>'
        '<span class="health-action__copy">'
        f'<strong>{escape_html(title)}</strong><p>{escape_html(detail)}</p></span>'
        '<b class="health-action__arrow" aria-hidden="true">→</b></a>'
    )


def _health_detail_panel(
    title: str,
    body: str,
    *,
    eyebrow: str,
    anchor: str | None = None,
) -> str:
    anchor_attr = f' id="{escape_html(anchor)}"' if anchor else ""
    return (
        f'<section class="panel health-detail-panel"{anchor_attr}>'
        '<div class="section-heading"><div>'
        f'<p class="eyebrow">{escape_html(eyebrow)}</p>'
        f'<h2>{escape_html(title)}</h2></div></div>{body}</section>'
    )


def _health_disclosure(
    label: str,
    body: str,
    *,
    summary: str,
) -> str:
    return str(disclosure(
        label,
        HtmlFragment(body),
        summary=summary,
        css_class="health-detail-disclosure",
    ))


def _current_contract(snapshot: DashboardSnapshot) -> str:
    state = snapshot.operator_state
    clock = snapshot.generation_authority_checked_at
    checked = time_element(present_time(clock, now=clock))
    generated = time_element(
        present_time(
            state.get("generated_at") or state.get("run_started_at"),
            now=clock,
        )
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
        ("Research only", _boolean_badge(state.get("research_only"), false_tone="danger")),
        ("No-send enforced", _no_send_enforced_badge(state.get("send_attempted"))),
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
    summary = (
        f"{humanize_enum(snapshot.generation_authority_status)} · "
        f"doctor {humanize_enum(snapshot.doctor_status).casefold()}"
    )
    overview = (
        '<div class="chip-row" aria-label="Generation trust summary">'
        f'{badge(snapshot.generation_authority_status)}{_validation_badge(snapshot.doctor_status)}</div>'
    )
    return _health_detail_panel(
        "Exact operator generation",
        overview
        + reasons
        + _health_disclosure(
            "View exact generation contract",
            str(definition_list(values, css_class="definition-grid")),
            summary=summary,
        ),
        eyebrow="Pointer-bound truth",
        anchor="exact-generation",
    )


def _maintenance_status_section(snapshot: DashboardSnapshot) -> str:
    context = _maintenance_status_context(snapshot)
    values = _maintenance_status_values(snapshot, context)
    maintenance_label = str(context["maintenance_label"])
    maintenance_tone = str(context["maintenance_tone"])
    scheduler_healthy = context["scheduler_healthy"]
    scheduler_label = (
        "Healthy"
        if scheduler_healthy is True
        else "Needs attention"
        if scheduler_healthy is False
        else "Not recorded"
    )
    overview = (
        '<div class="chip-row" aria-label="Daily maintenance summary">'
        + str(badge(maintenance_label, tone=maintenance_tone))
        + str(
            badge(
                scheduler_label,
                tone=(
                    "positive"
                    if scheduler_healthy is True
                    else "danger"
                    if scheduler_healthy is False
                    else "neutral"
                ),
            )
        )
        + '</div><p class="health-detail-summary">'
        + escape_html(
            "Daily Operations uses persisted maintenance telemetry only; this page does not inspect launchd or call a provider."
        )
        + "</p>"
    )
    return _health_detail_panel(
        "Daily Operations maintenance",
        overview
        + _maintenance_expiry_action(snapshot)
        + _health_disclosure(
            "View maintenance schedule and evidence",
            str(definition_list(values, css_class="definition-grid")),
            summary=(
                f"{maintenance_label} · scheduler {scheduler_label.casefold()}"
            ),
        ),
        eyebrow="Artifact-backed automation status",
        anchor="daily-operations-maintenance",
    )


def _maintenance_status_context(snapshot: DashboardSnapshot) -> dict[str, object]:
    service = snapshot.maintenance_service
    state = snapshot.maintenance_state
    current = snapshot.maintenance_current_status
    latest_constraint = next(
        (
            row
            for row in reversed(snapshot.maintenance_cycles)
            if row.get("status") in {"skipped", "blocked"}
        ),
        {},
    )
    enabled = service.get("enabled")
    prepared = service.get("prepared")
    if enabled is True:
        maintenance_label = "Enabled"
        maintenance_tone = "positive"
    elif prepared is True:
        maintenance_label = "Prepared / disabled"
        maintenance_tone = "muted"
    else:
        maintenance_label = "Unavailable"
        maintenance_tone = "warning"
    scheduler_healthy = (
        state.get("scheduler_healthy")
        if state.get("scheduler_healthy") in {True, False}
        else service.get("healthy")
    )
    scheduler_loaded = (
        state.get("scheduler_loaded")
        if state.get("scheduler_loaded") in {True, False}
        else service.get("loaded")
    )
    scheduler_reason = (
        state.get("scheduler_reason")
        or service.get("scheduler_reason")
        or service.get("reason")
    )
    authority_expiry = _generation_authority_expiry(snapshot)
    clock = snapshot.generation_authority_checked_at
    historical_authorization = state.get("authorization_at_last_cycle")
    if not isinstance(historical_authorization, bool):
        historical_authorization = state.get("live_provider_authorized")
    current_freshness = str(current.get("current_status_freshness") or "missing")
    current_authorization = str(
        current.get("current_authorization_status") or "not_recorded"
    )
    if current_freshness == "stale":
        current_authorization = "unknown_stale_receipt"
    return {
        "service": service,
        "state": state,
        "current": current,
        "latest_constraint": latest_constraint,
        "maintenance_label": maintenance_label,
        "maintenance_tone": maintenance_tone,
        "scheduler_healthy": scheduler_healthy,
        "scheduler_loaded": scheduler_loaded,
        "scheduler_reason": scheduler_reason,
        "authority_expiry": authority_expiry,
        "clock": clock,
        "historical_authorization": historical_authorization,
        "current_authorization": current_authorization,
        "current_freshness": current_freshness,
    }


def _maintenance_status_values(
    snapshot: DashboardSnapshot,
    context: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    service = snapshot.maintenance_service
    state = snapshot.maintenance_state
    current = snapshot.maintenance_current_status
    latest_constraint = context["latest_constraint"]
    assert isinstance(latest_constraint, Mapping)
    clock = context["clock"]
    maintenance_label = str(context["maintenance_label"])
    maintenance_tone = str(context["maintenance_tone"])
    return (
        ("Maintenance", badge(maintenance_label, tone=maintenance_tone)),
        ("Scheduler loaded", _boolean_badge(context["scheduler_loaded"])),
        (
            "Scheduler health",
            _boolean_badge(context["scheduler_healthy"], false_tone="danger"),
        ),
        ("Scheduler detail", humanize_reason(context["scheduler_reason"])),
        (
            "Service receipt updated",
            time_element(present_time(service.get("updated_at"), now=clock)),
        ),
        (
            "Last readiness check",
            time_element(present_time(state.get("last_readiness_check"), now=clock)),
        ),
        (
            "Last attempted observation",
            time_element(
                present_time(state.get("last_attempted_observation"), now=clock)
            ),
        ),
        (
            "Last successful publication",
            time_element(
                present_time(state.get("last_successful_publication"), now=clock)
            ),
        ),
        (
            "Next eligible observation",
            time_element(
                present_time(state.get("next_eligible_observation_at"), now=clock)
            ),
        ),
        (
            "Generation authority expiry",
            time_element(present_time(context["authority_expiry"], now=clock)),
        ),
        (
            "Authorization at last cycle",
            _boolean_badge(
                context["historical_authorization"], false_tone="warning"
            ),
        ),
        (
            "Authorization checked at last cycle",
            time_element(
                present_time(
                    state.get("authorization_checked_at_last_cycle")
                    or state.get("last_readiness_check"),
                    now=clock,
                )
            ),
        ),
        (
            "Current authorization status",
            badge(
                humanize_enum(context["current_authorization"]),
                tone=(
                    "positive"
                    if context["current_authorization"] == "authorized"
                    else "warning"
                ),
            ),
        ),
        (
            "Current authorization checked",
            time_element(
                present_time(
                    current.get("current_authorization_checked_at"),
                    now=clock,
                )
            ),
        ),
        (
            "Current provider-call eligibility",
            humanize_reason(
                "unknown_stale_receipt"
                if context["current_freshness"] == "stale"
                else current.get("current_provider_call_eligibility")
            ),
        ),
        ("Last cycle", badge(state.get("last_cycle_status"))),
        (
            "Last cycle reason",
            humanize_reason(state.get("last_cycle_reason")),
        ),
        (
            "Latest skip / block reason",
            humanize_reason(latest_constraint.get("reason")),
        ),
        (
            "Latest skip / block recorded",
            time_element(
                present_time(latest_constraint.get("recorded_at"), now=clock)
            ),
        ),
        ("No-send", _boolean_badge(state.get("no_send"), false_tone="danger")),
        (
            "Research only",
            _boolean_badge(state.get("research_only"), false_tone="danger"),
        ),
    )


def _maintenance_expiry_action(snapshot: DashboardSnapshot) -> str:
    guidance = maintenance_expiry_guidance(snapshot)
    if guidance.get("active") is not True:
        return ""
    remaining = format_duration(guidance.get("time_until_expiry_seconds"))
    readiness = str(guidance.get("safe_manual_readiness_command") or "")
    install = str(guidance.get("installation_command") or "")
    disable = str(guidance.get("rollback_disable_command") or "")
    return (
        '<div class="alert alert-warning maintenance-expiry-action"><div '
        'class="alert-icon" aria-hidden="true">!</div><div>'
        '<h3>Manual freshness check approaching</h3><p>Generation authority '
        f'expires in approximately {escape_html(remaining)} and maintenance is disabled. '
        'Run the no-provider readiness check before deciding whether to start a cycle.</p>'
        f'<p><code>{escape_html(readiness)}</code></p>'
        '<details class="disclosure"><summary>Optional recurring maintenance</summary>'
        '<div class="disclosure__body"><p>This changes local scheduler state and requires '
        'explicit confirmation. It does not create provider authorization.</p>'
        f'<p><code>{escape_html(install)}</code></p>'
        f'<p>Rollback: <code>{escape_html(disable)}</code></p>'
        f'<p>{escape_html(guidance.get("provider_activity"))}</p></div></details>'
        '</div></div>'
    )


def _generation_authority_expiry(snapshot: DashboardSnapshot) -> str | None:
    state = snapshot.operator_state
    raw = state.get("run_started_at") or state.get("generated_at")
    try:
        started = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if started.tzinfo is None or started.utcoffset() is None:
        return None
    try:
        max_age_hours = float(config.EVENT_ALPHA_MAX_RUN_AGE_HOURS)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(max_age_hours) or max_age_hours <= 0:
        return None
    return (
        started.astimezone(timezone.utc) + timedelta(hours=max_age_hours)
    ).isoformat()


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
    gaps = sum(1 for layer in coverage if layer.action_required)
    overview = (
        f"{gaps} of {len(coverage)} expected product layers require attention."
        if gaps
        else f"All {len(coverage)} expected product layers are healthy or explicitly not applicable."
    )
    table = (
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
        )
    )
    return _health_detail_panel(
        "Product-layer coverage",
        f'<p class="health-detail-summary">{escape_html(overview)}</p>'
        + _health_disclosure(
            "View product-layer coverage table",
            table,
            summary=f"{len(coverage)} layers · {gaps} gaps",
        ),
        eyebrow="One coverage contract",
        anchor="product-layer-coverage",
    )


def _coverage_action_title(layer: DashboardLayerCoverage) -> str:
    if layer.key == "request_ledger":
        return f"Provider request ledger {humanize_enum(layer.status).casefold()}"
    if layer.key == "calendar" and layer.status == "not_configured":
        return "Calendar acquisition not configured"
    return f"{layer.label} {humanize_enum(layer.status).casefold()}"


def _coverage_action_href(layer: DashboardLayerCoverage) -> str:
    if layer.key == "request_ledger":
        return "#provider-request"
    if layer.key == "market":
        return "#market-quality"
    return "#product-layer-coverage"


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
    *,
    now: object = None,
) -> str:
    rows: list[tuple[object, ...]] = []
    for item in providers:
        label, tone, detail = _provider_assessment(item)
        provider = item.get("provider") or item.get("provider_name") or item.get("name")
        last = present_time(
            item.get("last_success_at")
            or item.get("last_success")
            or item.get("latest_rehearsal_generated_at"),
            now=now,
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
    assessments = tuple(_provider_assessment(item) for item in providers)
    failures = sum(1 for _label, tone, _detail in assessments if tone == "danger")
    setup_gaps = sum(
        1
        for label, _tone, _detail in assessments
        if label in {"Authorization missing", "Not configured"}
    )
    disabled = sum(1 for label, _tone, _detail in assessments if label == "Disabled / not selected")
    overview = (
        f"{len(providers)} provider states: {failures} failures, "
        f"{setup_gaps} setup gaps, {disabled} disabled or not selected."
    )
    detail = str(table) + (
        '<p class="muted">Disabled, not selected, and missing authorization are setup states—not request failures.</p>'
    )
    return _health_detail_panel(
        "Provider readiness",
        f'<p class="health-detail-summary">{escape_html(overview)}</p>'
        + _health_disclosure(
            "View provider readiness table",
            detail,
            summary=f"{len(providers)} providers · {failures} failures",
        ),
        eyebrow="Expected vs failed",
        anchor="provider-readiness",
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
        return _health_detail_panel(
            "Provider request",
            str(badge(coverage.status, tone=_coverage_tone(coverage.status))) + str(body),
            eyebrow="Exact acquisition evidence",
            anchor="provider-request",
        )
    clock = snapshot.generation_authority_checked_at
    start = time_element(
        present_time(ledger.get("request_started_at"), now=clock)
    )
    end = time_element(present_time(ledger.get("request_ended_at"), now=clock))
    duration = format_duration(
        _duration_seconds(ledger.get("duration_ms"), milliseconds=True)
    )
    http = ledger.get("http_status")
    http_label = f"HTTP {http}" if http not in (None, "") else UNAVAILABLE
    values = (
        ("Provider", humanize_enum(ledger.get("provider"))),
        (
            "Authorization at request",
            _boolean_badge(ledger.get("live_provider_authorized"), false_tone="warning"),
        ),
        ("Provider call attempted", _boolean_badge(ledger.get("provider_call_attempted"))),
        (
            "Request succeeded",
            _boolean_badge(ledger.get("provider_request_succeeded"), false_tone="danger"),
        ),
        ("Response", http_label),
        ("Request started", start),
        ("Request ended", end),
        ("Duration", duration),
        ("Rows returned / selected", f"{_count(ledger.get('result_count'))} / {_count(ledger.get('selected_market_row_count'))}"),
        ("Retries", _count(ledger.get("retry_count"))),
        ("Cache behavior", humanize_enum(ledger.get("cache_behavior") or ledger.get("cache_status"))),
        ("Data mode", humanize_enum(ledger.get("candidate_source_mode") or ledger.get("data_mode"))),
        ("No-send", _boolean_badge(ledger.get("no_send"), false_tone="danger")),
        ("Side effects", _side_effect_summary(ledger)),
    )
    failure = ""
    if ledger.get("error_class"):
        failure = (
            '<div class="alert alert-danger"><strong>Actual request failure:</strong> '
            f"{escape_html(humanize_reason(ledger.get('error_class')))}</div>"
        )
    provider = humanize_enum(ledger.get("provider"))
    request_state = _request_state_label(ledger)
    overview = (
        f"{provider} request {request_state}; {http_label}; "
        f"{_count(ledger.get('selected_market_row_count'))} selected rows."
    )
    detail = str(definition_list(values, css_class="definition-grid"))
    return _health_detail_panel(
        "Provider request",
        str(badge(coverage.status, tone=_coverage_tone(coverage.status)))
        + f'<p class="health-detail-summary">{escape_html(overview)}</p>'
        + failure
        + _health_disclosure(
            "View exact provider request receipt",
            detail,
            summary=f"{provider} · {http_label}",
        ),
        eyebrow="Exact acquisition evidence",
        anchor="provider-request",
    )


def _request_state_label(ledger: Mapping[str, Any]) -> str:
    attempted = ledger.get("provider_call_attempted")
    succeeded = ledger.get("provider_request_succeeded")
    if succeeded is True:
        return "succeeded"
    if attempted is True and succeeded is False:
        return "failed"
    if attempted is True:
        return "has no recorded result"
    if attempted is False:
        return "was not attempted"
    return "state was not recorded"


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
        (
            "Next eligible observation",
            time_element(
                present_time(
                    generation.get("next_eligible_observation_at"),
                    now=snapshot.generation_authority_checked_at,
                )
            ),
        ),
    )
    observation_count = len(snapshot.current_market_observations)
    overview = (
        f"{observation_count} exact observations; {summary['spread']} spread verified; "
        f"{summary['warm']} warm baselines."
    )
    detail = (
        str(definition_list(values, css_class="definition-grid"))
        + '<p class="muted">Direct observations and proxy features remain visibly separate. '
        "Warming is evidence progress, not failure.</p>"
    )
    return _health_detail_panel(
        "Market data quality",
        f'<p class="health-detail-summary">{escape_html(overview)}</p>'
        + _health_disclosure(
            "View market data-quality evidence",
            detail,
            summary=f"{observation_count} observations · {summary['spread']} spread verified",
        ),
        eyebrow="Freshness, baseline, spread",
        anchor="market-quality",
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
        detail = _source_gap_detail(gap, missing=missing)
        rows.append((
            humanize_enum(item.get("source_pack")),
            badge(status),
            _count(item.get("accepted_evidence_count")),
            _joined(item.get("healthy_providers")),
            detail,
        ))
    accepted = sum(
        max(0, int(value))
        for item in packs
        if (value := _number(item.get("accepted_evidence_count"))) is not None
    )
    overview = f"{len(packs)} source packs; {accepted} accepted evidence rows."
    table = str(data_table(
        ("Source pack", "State", "Accepted", "Healthy providers", "Coverage meaning"),
        rows,
        caption="Exact-generation source coverage",
        empty="No source-pack coverage assessment is attached.",
    ))
    return _health_detail_panel(
        "Source-pack coverage",
        f'<p class="health-detail-summary">{escape_html(overview)}</p>'
        + _health_disclosure(
            "View source-pack coverage table",
            table,
            summary=f"{len(packs)} packs · {accepted} accepted rows",
        ),
        eyebrow="Coverage is not absence",
        anchor="source-pack-coverage",
    )


def _source_gap_detail(gap: object, *, missing: str) -> str:
    token = str(gap or "").strip().casefold()
    detail = {
        "missing_provider_configuration": "Provider configuration is missing.",
        "missing_provider_authorization": "Provider authorization is missing.",
        "provider_not_selected": "No provider was selected for this source pack.",
        "no_healthy_provider": "No healthy provider evidence was recorded.",
    }.get(
        token,
        humanize_reason(gap)
        if gap not in (None, "")
        else "No coverage gap recorded.",
    )
    if missing == UNAVAILABLE:
        return detail
    return f"{detail} Affected providers: {missing}."


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
        "Read "
        f"{time_element(present_time(snapshot.provider_health_read_at, now=snapshot.generation_authority_checked_at))}. "
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
