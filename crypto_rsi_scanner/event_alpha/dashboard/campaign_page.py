"""Bounded Decision Radar campaign-history dashboard surface."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
from .layer_coverage import DashboardLayerCoverage, dashboard_layer_coverage_by_key
from .models import DashboardSnapshot
from .presentation import UNAVAILABLE, humanize_enum, humanize_reason, present_time
from .system_page_support import (
    as_mapping,
    display_count,
    first_recorded,
    render_metric_grid,
    render_page_intro,
    render_panel,
    render_validation_badge,
    summarize_market_quality,
)


def render_campaign_page(
    snapshot: DashboardSnapshot,
    query: Mapping[str, str] | None,
) -> str:
    """Render bounded campaign attempts without granting them current authority."""

    filters = _campaign_filters(query)
    attempts = _filter_attempts(snapshot.campaign_attempts, filters)
    ledger = snapshot.current_request_ledger
    generation = snapshot.market_generation
    reservation = snapshot.campaign_reservation
    quality = summarize_market_quality(snapshot.current_market_observations, generation)
    market_coverage = dashboard_layer_coverage_by_key(snapshot)["market"]
    fixture_generation = _is_fixture_generation(snapshot)
    succeeded, succeeded_tone = _recorded_true_count(
        snapshot.campaign_attempts,
        "provider_request_succeeded",
        positive_tone="positive",
    )
    counted, counted_tone = _recorded_true_count(
        snapshot.campaign_attempts,
        "decision_radar_campaign_counted",
        positive_tone="info",
    )
    fixture_current_value = (
        _admitted_count(market_coverage)
        if snapshot.generation_authoritative
        else "Suppressed"
    )
    fixture_idea_value = (
        str(len(snapshot.visible_current_candidates))
        if snapshot.generation_authoritative
        else "Suppressed"
    )
    fixture_observation_tone = (
        "info"
        if snapshot.generation_authoritative and _market_admitted(market_coverage)
        else "warning"
        if snapshot.generation_authoritative
        else "danger"
    )
    fixture_campaign_label, fixture_campaign_tone = _campaign_counted_state(
        {
            "decision_radar_campaign_counted": _generation_campaign_counted(
                generation
            ),
        }
    )
    metrics = (
        (
            "Fixture observations",
            fixture_current_value,
            fixture_observation_tone,
        ),
        (
            "Fixture ideas",
            fixture_idea_value,
            (
                "positive"
                if snapshot.generation_authoritative
                and snapshot.visible_current_candidates
                else "muted"
                if snapshot.generation_authoritative
                else "danger"
            ),
        ),
        ("Campaign status", fixture_campaign_label, fixture_campaign_tone),
        ("Live receipts", "Separate context", "neutral"),
    ) if fixture_generation else (
        ("Recent attempts", str(len(snapshot.campaign_attempts)), "neutral"),
        ("Successful data fetches", succeeded, succeeded_tone),
        ("Pilot runs counted", counted, counted_tone),
        (
            "Current ideas",
            str(len(snapshot.visible_current_candidates)) if snapshot.generation_authoritative else "Suppressed",
            "positive" if snapshot.generation_authoritative and snapshot.visible_current_candidates else "muted",
        ),
    )
    current_authority = (
        _campaign_current_authority(
            snapshot,
            ledger,
            generation,
            quality,
            market_coverage,
        )
        if snapshot.generation_authoritative
        else render_panel(
            "Current campaign authority suppressed",
            (
                "Current request, observation, baseline, and idea fields are quarantined because "
                "generation authority did not pass. Bounded historical attempts remain visible below."
            ),
            eyebrow="Fail-closed authority",
        )
    )
    history = (
        _fixture_campaign_context(snapshot, filters, attempts, reservation)
        if fixture_generation
        else (
            _campaign_latest(snapshot)
            + _campaign_filter_form(filters, snapshot.campaign_attempts)
            + _campaign_attempt_table(
                attempts,
                now=snapshot.generation_authority_checked_at,
            )
            + _campaign_reservation(
                reservation,
                now=snapshot.generation_authority_checked_at,
            )
        )
    )
    return (
        render_page_intro(
            "No-send run history",
            (
                "Exact fixture authority with separately scoped live campaign context."
                if fixture_generation
                else "Bounded no-send observation attempts and the exact current authority. Historical rows are context, never current truth."
            ),
            "Decision Radar observation campaign",
        )
        + current_authority
        + render_metric_grid(metrics)
        + history
        + _maintenance_cycle_table(snapshot)
        + _campaign_metadata_disclosure(snapshot)
        + _maintenance_metadata_disclosure(snapshot)
    )


def _is_fixture_generation(snapshot: DashboardSnapshot) -> bool:
    mode = str(snapshot.operator_state.get("run_mode") or "").strip().casefold()
    return mode in {"fixture", "mock", "mocked", "test"}


def _fixture_campaign_context(
    snapshot: DashboardSnapshot,
    filters: Mapping[str, str],
    attempts: tuple[Mapping[str, Any], ...],
    reservation: Mapping[str, Any],
) -> str:
    body = (
        '<div class="alert alert-info"><strong>Different authority scope.</strong> '
        'These live CoinGecko campaign receipts are machine-level history and do not describe '
        'this fixture generation.</div>'
        + _campaign_latest(snapshot)
        + _campaign_filter_form(filters, snapshot.campaign_attempts)
        + _campaign_attempt_table(
            attempts,
            now=snapshot.generation_authority_checked_at,
        )
        + _campaign_reservation(
            reservation,
            now=snapshot.generation_authority_checked_at,
        )
    )
    return render_panel(
        "Live campaign context — not this fixture",
        str(disclosure(
            "Review separately scoped live receipts",
            HtmlFragment(body),
            summary=f"{len(snapshot.campaign_attempts)} machine-level receipt{'s' if len(snapshot.campaign_attempts) != 1 else ''}",
            css_class="campaign-scope-disclosure",
        )),
        eyebrow="Historical context only",
    )


def _campaign_current_authority(
    snapshot: DashboardSnapshot,
    ledger: Mapping[str, Any],
    generation: Mapping[str, Any],
    quality: Mapping[str, int],
    market_coverage: DashboardLayerCoverage,
) -> str:
    provenance = as_mapping(generation.get("market_provenance"))
    data_quality = as_mapping(provenance.get("data_quality"))
    market_admitted = _market_admitted(market_coverage)
    observation_count = _admitted_count(market_coverage)
    anomaly_count = (
        str(len(snapshot.current_market_anomalies)) if market_admitted else UNAVAILABLE
    )
    raw_count = first_recorded(
        ledger.get("raw_market_row_count"),
        generation.get("raw_market_row_count"),
    )
    selected_count = first_recorded(
        ledger.get("selected_market_row_count"),
        generation.get("selected_market_row_count"),
    )
    direct_count = first_recorded(
        data_quality.get("direct_feature_count"),
        generation.get("direct_feature_count"),
    )
    proxy_count = first_recorded(
        data_quality.get("proxy_feature_count"),
        generation.get("proxy_feature_count"),
    )
    authorized = first_recorded(
        ledger.get("live_provider_authorized"),
        generation.get("live_provider_authorized"),
    )
    request_succeeded = first_recorded(
        ledger.get("provider_request_succeeded"),
        generation.get("provider_request_succeeded"),
    )
    baseline_value = (
        f"{quality['warm']} warm · {quality['warming']} warming · {quality['cold']} cold"
        if market_admitted
        else UNAVAILABLE
    )
    spread_value = (
        f"{quality['spread']} / {len(snapshot.current_market_observations)}"
        if market_admitted
        else UNAVAILABLE
    )
    provider_value = ledger.get("provider") or generation.get("provider")
    provider_summary = (
        badge(humanize_enum(provider_value), tone="info")
        if provider_value not in (None, "")
        else badge("Provider not recorded", tone="neutral")
    )
    values = (
        ("Current pointer", badge(snapshot.generation_authority_status)),
        ("Namespace", snapshot.artifact_namespace),
        ("Run", snapshot.run_id),
        ("Revision", snapshot.revision),
        ("Provider", humanize_enum(ledger.get("provider") or generation.get("provider"))),
        ("Authorization present", _boolean_badge(authorized)),
        ("Data mode", humanize_enum(ledger.get("candidate_source_mode") or generation.get("candidate_source_mode") or generation.get("data_mode"))),
        (
            "Observed",
            time_element(
                present_time(
                    ledger.get("observed_at") or generation.get("observed_at"),
                    now=snapshot.generation_authority_checked_at,
                )
            ),
        ),
        ("Provider request", _boolean_badge(request_succeeded)),
        (
            "Raw / selected rows",
            f"{display_count(raw_count)} / {display_count(selected_count)}",
        ),
        (
            "Observations / anomalies / canonical candidates / current ideas",
            f"{observation_count} / {anomaly_count} / "
            f"{len(snapshot.current_candidates)} / {len(snapshot.visible_current_candidates)}",
        ),
        ("Core / cards", f"{display_count(generation.get('core_row_count'))} / {display_count(generation.get('card_count'))}"),
        ("Baseline", baseline_value),
        (
            "Direct / proxy features",
            f"{display_count(direct_count)} / {display_count(proxy_count)}",
        ),
        ("Spread verified", spread_value),
        ("Strict doctor", badge(snapshot.doctor_status)),
        ("Publication", badge(generation.get("status") or snapshot.generation_authority_status)),
        (
            "Campaign counted",
            _campaign_counted_badge(_generation_campaign_counted(generation)),
        ),
    )
    overview = (
        '<div class="chip-row">'
        + str(badge(snapshot.generation_authority_status))
        + str(render_validation_badge(snapshot.doctor_status))
        + str(provider_summary)
        + '</div><p class="health-detail-summary">'
        f'{_layer_count_summary(observation_count, "observation")} · '
        f'{_layer_count_summary(anomaly_count, "anomaly", plural="anomalies")} · '
        f'{_counted(len(snapshot.current_candidates), "canonical candidate row")} · '
        f'{_counted(len(snapshot.visible_current_candidates), "current idea")} · '
        + (
            f'{quality["warm"]} warm baselines.</p>'
            if market_admitted
            else 'baseline maturity unavailable.</p>'
        )
    )
    return render_panel(
        "Current authoritative generation",
        overview
        + str(disclosure(
            "View exact current-run contract",
            definition_list(values, css_class="definition-grid"),
            summary=f"Revision {snapshot.revision} · exact pointer binding",
            css_class="campaign-technical-disclosure",
        ))
        + '<p class="muted">Use this exact run and revision as the reference point; the receipts below are historical context.</p>',
        eyebrow="Exact pointer binding",
    )


def _counted(count: int, singular: str, *, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


def _recorded_true_count(
    rows: tuple[Mapping[str, Any], ...],
    field: str,
    *,
    positive_tone: str,
) -> tuple[str, str]:
    values = tuple(row.get(field) for row in rows)
    if any(value is not True and value is not False for value in values):
        return "Not recorded", "neutral"
    count = sum(value is True for value in values)
    return str(count), positive_tone if count else "muted"


def _generation_campaign_counted(generation: Mapping[str, Any]) -> object:
    provenance = as_mapping(generation.get("market_provenance"))
    return first_recorded(
        generation.get("decision_radar_campaign_counted"),
        provenance.get("decision_radar_campaign_counted"),
    )


def _market_admitted(coverage: DashboardLayerCoverage) -> bool:
    return coverage.status in {"healthy_nonempty", "healthy_empty"}


def _admitted_count(coverage: DashboardLayerCoverage) -> str:
    return str(coverage.row_count) if _market_admitted(coverage) else UNAVAILABLE


def _layer_count_summary(
    value: str,
    singular: str,
    *,
    plural: str | None = None,
) -> str:
    if value == UNAVAILABLE:
        return f"{plural or singular + 's'} unavailable"
    return _counted(int(value), singular, plural=plural)


def _attempt_outcome_summary(item: Mapping[str, Any]) -> str:
    if item.get("failure_class"):
        return humanize_reason(item.get("failure_class"))
    attempted = item.get("provider_call_attempted")
    succeeded = item.get("provider_request_succeeded")
    if succeeded is True:
        return "Request succeeded"
    if attempted is True and succeeded is False:
        return "Request failed"
    if attempted is True:
        return "Request result not recorded"
    if attempted is False:
        return "No provider call attempted"
    status = str(item.get("status") or "").strip()
    if status:
        return f"{humanize_enum(status)} result"
    return "Result not recorded"


def _campaign_latest(snapshot: DashboardSnapshot) -> str:
    latest = snapshot.campaign_latest_attempt
    if not latest:
        return render_panel(
            "Latest attempt receipt",
            str(empty_state(
                "Latest receipt unavailable",
                "No valid bounded latest-attempt receipt was loaded.",
            )),
            eyebrow="Historical / non-authoritative",
        )
    failure: object = (
        humanize_reason(latest.get("failure_class"))
        if latest.get("failure_class")
        else UNAVAILABLE
    )
    outcome_summary = _attempt_outcome_summary(latest)
    values = (
        ("Attempt", latest.get("attempt_id") or UNAVAILABLE),
        (
            "Recorded",
            time_element(
                present_time(
                    latest.get("recorded_at"),
                    now=snapshot.generation_authority_checked_at,
                )
            ),
        ),
        (
            "Observed",
            time_element(
                present_time(
                    latest.get("observed_at"),
                    now=snapshot.generation_authority_checked_at,
                )
            ),
        ),
        ("Provider", humanize_enum(latest.get("provider"))),
        ("Status", badge(latest.get("status"))),
        ("Provider call attempted", _boolean_badge(latest.get("provider_call_attempted"))),
        ("Request succeeded", _boolean_badge(latest.get("provider_request_succeeded"))),
        (
            "Campaign counted",
            _campaign_counted_badge(latest.get("decision_radar_campaign_counted")),
        ),
        ("Namespace", latest.get("artifact_namespace") or UNAVAILABLE),
        ("Run", latest.get("run_id") or UNAVAILABLE),
        ("Failure", failure),
    )
    counted_label, counted_tone = _campaign_counted_state(latest)
    overview = (
        '<div class="chip-row">'
        + str(badge(latest.get("status")))
        + str(badge(counted_label, tone=counted_tone))
        + '</div><p class="health-detail-summary">'
        f'{escape_html(humanize_enum(latest.get("provider")))} · '
        f'{time_element(present_time(latest.get("recorded_at"), now=snapshot.generation_authority_checked_at))} · '
        f'{escape_html(outcome_summary)}</p>'
    )
    return render_panel(
        "Latest attempt receipt",
        overview
        + str(disclosure(
            "View full attempt receipt",
            definition_list(values, css_class="definition-grid"),
            summary="Historical receipt · non-authoritative",
            css_class="campaign-technical-disclosure",
        ))
        + str(badge("Historical / non-authoritative", tone="info")),
        eyebrow="Last bounded attempt",
    )


def _campaign_attempt_table(
    attempts: tuple[Mapping[str, Any], ...],
    *,
    now: object = None,
) -> str:
    rows = []
    mobile_rows: list[str] = []
    for item in reversed(attempts):
        failure: object = (
            humanize_reason(item.get("failure_class"))
            if item.get("failure_class")
            else UNAVAILABLE
        )
        outcome_summary = _attempt_outcome_summary(item)
        rows.append((
            time_element(
                present_time(item.get("recorded_at"), now=now),
                primary="combined",
            ),
            _campaign_provider_cell(item),
            badge(item.get("status")),
            _campaign_request_cell(item),
            _campaign_counted_cell(item),
            _campaign_identity_cell(item),
            outcome_summary,
        ))
        provider = humanize_enum(item.get("provider"))
        status = humanize_enum(item.get("status"))
        counted_label, _counted_tone = _campaign_counted_state(item)
        request_label, _request_tone, _request_detail = _campaign_request_state(item)
        mobile_rows.append(
            '<article class="campaign-attempt-record">'
            '<header class="campaign-attempt-record__header"><div>'
            '<p class="eyebrow">Historical attempt</p>'
            f'<h3>{escape_html(provider)}</h3></div>{badge(status)}</header>'
            f'<p class="campaign-attempt-record__summary">{time_element(present_time(item.get("recorded_at"), now=now), primary="combined")} · {escape_html(outcome_summary)}</p>'
            '<div class="campaign-attempt-record__facts">'
            f'<span><small>Campaign</small><strong>{escape_html(counted_label)}</strong></span>'
            f'<span><small>Request</small><strong>{escape_html(request_label)}</strong></span>'
            '</div>'
            + str(disclosure(
                "Attempt identity and evidence",
                definition_list((
                    ("Attempt", item.get("attempt_id") or UNAVAILABLE),
                    ("Provider call attempted", _boolean_badge(item.get("provider_call_attempted"))),
                    ("Request succeeded", _boolean_badge(item.get("provider_request_succeeded"))),
                    (
                        "Campaign counted",
                        _campaign_counted_badge(item.get("decision_radar_campaign_counted")),
                    ),
                    ("Data mode", humanize_enum(item.get("candidate_source_mode") or item.get("data_mode"))),
                    ("Namespace", item.get("artifact_namespace") or UNAVAILABLE),
                    ("Run", item.get("run_id") or UNAVAILABLE),
                    ("Failure", failure),
                ), css_class="definition-grid"),
                summary="Historical receipt · non-authoritative",
                css_class="campaign-attempt-record__details",
            ))
            + '</article>'
        )
    mobile = (
        "".join(mobile_rows)
        if mobile_rows
        else str(empty_state(
            "No matching attempts",
            "No historical attempt receipts match these filters.",
        ))
    )
    return render_panel(
        "Bounded attempt ledger",
        '<div class="alert alert-info"><strong>Historical / non-authoritative.</strong> '
        "These receipts cannot replace the exact current pointer.</div>"
        + '<div class="campaign-desktop-table">' + str(data_table(
            (
                "Recorded", "Provider / mode", "Result", "Request",
                "Campaign", "Generation", "Outcome",
            ),
            rows,
            caption="Bounded historical no-send attempts",
            empty="No historical attempt receipts match these filters.",
            compact=True,
        )) + '</div><div class="campaign-mobile-list">' + mobile + '</div>',
        eyebrow="Observation history",
    )


def _campaign_provider_cell(item: Mapping[str, Any]) -> HtmlFragment:
    provider = humanize_enum(item.get("provider"))
    data_mode = humanize_enum(
        item.get("candidate_source_mode") or item.get("data_mode")
    )
    accessible = f"Provider {provider}; data mode {data_mode}."
    return HtmlFragment(
        f'<span class="table-stack-cell" aria-label="{escape_html(accessible)}">'
        f'<strong>{escape_html(provider)}</strong>'
        f'<small>{escape_html(data_mode)}</small>'
        '</span>'
    )


def _campaign_request_cell(item: Mapping[str, Any]) -> HtmlFragment:
    attempted_value = item.get("provider_call_attempted")
    succeeded_value = item.get("provider_request_succeeded")
    label, tone, detail = _campaign_request_state(item)
    accessible = (
        f"Provider call attempted: {_boolean_label(attempted_value)}; "
        f"provider request succeeded: {_boolean_label(succeeded_value)}."
    )
    return HtmlFragment(
        f'<span class="table-stack-cell" title="{escape_html(accessible)}">'
        f'{badge(label, tone=tone)}<small>{escape_html(detail)}</small>'
        f'<span class="sr-only">{escape_html(accessible)}</span>'
        '</span>'
    )


def _campaign_counted_cell(item: Mapping[str, Any]) -> HtmlFragment:
    counted_value = item.get("decision_radar_campaign_counted")
    label, tone = _campaign_counted_state(item)
    accessible = (
        f"Decision Radar campaign counted: {_boolean_label(counted_value)}."
    )
    return HtmlFragment(
        f'<span title="{escape_html(accessible)}">'
        f'{badge(label, tone=tone)}'
        f'<span class="sr-only">{escape_html(accessible)}</span>'
        '</span>'
    )


def _campaign_identity_cell(item: Mapping[str, Any]) -> HtmlFragment:
    namespace = str(item.get("artifact_namespace") or UNAVAILABLE)
    run_id = str(item.get("run_id") or UNAVAILABLE)
    attempt_id = str(item.get("attempt_id") or UNAVAILABLE)
    exact = f"Namespace {namespace}; run {run_id}; attempt {attempt_id}."
    namespace_label = _compact_identity_value(namespace, maximum=24)
    run_label = _compact_identity_value(run_id, maximum=12)
    attempt_label = _compact_identity_value(attempt_id, maximum=18)
    return HtmlFragment(
        f'<span class="table-identity-cell" title="{escape_html(exact)}">'
        f'<strong>{escape_html(namespace_label)}</strong>'
        f'<small>{escape_html(run_label)} · {escape_html(attempt_label)}</small>'
        f'<span class="sr-only">{escape_html(exact)}</span>'
        '</span>'
    )


def _compact_identity_value(value: str, *, maximum: int) -> str:
    return value if len(value) <= maximum else value[: maximum - 1] + "…"


def _campaign_request_state(item: Mapping[str, Any]) -> tuple[str, str, str]:
    attempted = item.get("provider_call_attempted")
    succeeded = item.get("provider_request_succeeded")
    if succeeded is True and attempted is not True:
        return "Inconsistent", "danger", "Success without attempted flag"
    if succeeded is True:
        return "Succeeded", "positive", "Call attempted"
    if attempted is True and succeeded is False:
        return "Failed", "danger", "Call attempted"
    if attempted is True:
        return "Result unavailable", "warning", "Call attempted"
    if attempted is False:
        return "Not attempted", "muted", "No provider call"
    return "Not recorded", "neutral", "Request evidence unavailable"


def _campaign_counted_state(item: Mapping[str, Any]) -> tuple[str, str]:
    counted = item.get("decision_radar_campaign_counted")
    if counted is True:
        return "Counted", "positive"
    if counted is False:
        return "Excluded", "warning"
    return "Not recorded", "neutral"


def _boolean_label(value: object) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "not recorded"


def _boolean_badge(value: object) -> HtmlFragment:
    if value is True:
        return badge("Yes", tone="positive")
    if value is False:
        return badge("No", tone="muted")
    return badge("Not recorded", tone="neutral")


def _campaign_counted_badge(value: object) -> HtmlFragment:
    label, tone = _campaign_counted_state(
        {"decision_radar_campaign_counted": value}
    )
    return badge(label, tone=tone)


def _campaign_reservation(
    reservation: Mapping[str, Any],
    *,
    now: object = None,
) -> str:
    if not reservation:
        return render_panel(
            "Cadence and reservation",
            str(empty_state(
                "Reservation evidence unavailable",
                "No valid campaign reservation receipt was loaded.",
            )),
            eyebrow="Next eligibility",
        )
    next_at = present_time(reservation.get("next_provider_call_at"), now=now)
    now_status = (
        "Eligible now"
        if next_at.available and next_at.relative_label.endswith("ago")
        else f"Next eligible {next_at.primary_label}"
        if next_at.available
        else UNAVAILABLE
    )
    values = (
        ("Reservation state", badge(reservation.get("status"))),
        ("Namespace", reservation.get("artifact_namespace") or UNAVAILABLE),
        (
            "Acquired",
            time_element(present_time(reservation.get("acquired_at"), now=now)),
        ),
        (
            "Provider call reserved",
            time_element(
                present_time(
                    reservation.get("provider_call_reserved_at"),
                    now=now,
                )
            ),
        ),
        (
            "Released",
            time_element(present_time(reservation.get("released_at"), now=now)),
        ),
        (
            "Reservation expiry",
            time_element(present_time(reservation.get("expires_at"), now=now)),
        ),
        ("Next provider-call eligibility", time_element(next_at)),
        ("Eligibility summary", now_status),
        ("No-send", _boolean_badge(reservation.get("no_send"))),
    )
    return render_panel(
        "Cadence and reservation",
        '<div class="chip-row">'
        + str(badge(reservation.get("status")))
        + str(_no_send_badge(reservation.get("no_send")))
        + '</div><p class="health-detail-summary"><strong>'
        + escape_html(now_status)
        + '</strong> · bounded provider-call cadence.</p>'
        + '<p><a class="button button-primary" href="/health#provider-readiness">Review provider readiness</a></p>'
        + str(disclosure(
            "View reservation receipt",
            definition_list(values, css_class="definition-grid"),
            summary="Timestamps, namespace, and safety evidence",
            css_class="campaign-technical-disclosure",
        )),
        eyebrow="Next eligibility",
    )


def _no_send_badge(value: object) -> HtmlFragment:
    if value is True:
        return badge("No-send", tone="info")
    if value is False:
        return badge("No-send: no", tone="danger")
    return badge("No-send not recorded", tone="neutral")


def _campaign_metadata_disclosure(snapshot: DashboardSnapshot) -> str:
    rows = []
    for name, metadata in sorted(snapshot.campaign_history_metadata.items()):
        rows.append((
            name,
            humanize_enum(metadata.get("authority")),
            display_count(metadata.get("source_row_count")),
            display_count(metadata.get("returned_row_count")),
            humanize_reason(metadata.get("error"), fallback="None recorded."),
            metadata.get("sha256") or UNAVAILABLE,
        ))
    table = data_table(
        ("Artifact", "Authority", "Source rows", "Loaded rows", "Read issue", "SHA-256"),
        rows,
        caption="Campaign history read metadata",
        empty="No campaign-history metadata was loaded.",
    )
    return str(disclosure(
        "Campaign artifact evidence",
        table,
        summary="Historical bounds, errors, and fingerprints",
        css_class="technical-details",
    ))


def _maintenance_cycle_table(snapshot: DashboardSnapshot) -> str:
    rows = []
    for item in reversed(snapshot.maintenance_cycles):
        rows.append((
            time_element(
                present_time(
                    item.get("recorded_at"),
                    now=snapshot.generation_authority_checked_at,
                ),
                primary="combined",
            ),
            badge(item.get("status")),
            _maintenance_request_summary(item),
            _maintenance_publication_summary(item),
            _compact_identity_value(
                str(item.get("artifact_namespace") or UNAVAILABLE),
                maximum=30,
            ),
            humanize_reason(item.get("reason")),
        ))
    body = (
        '<div class="alert alert-info"><strong>Maintenance telemetry / non-authoritative.</strong> '
        "These bounded receipts explain automatic upkeep but never replace the exact current pointer.</div>"
        + str(data_table(
            (
                "Recorded",
                "Cycle result",
                "Provider request",
                "Publication",
                "Namespace",
                "Reason",
            ),
            rows,
            caption="Bounded Daily Operations maintenance cycles",
            empty="No valid Daily Operations cycle receipts are available.",
            compact=True,
        ))
    )
    return render_panel(
        "Daily maintenance cycle ledger",
        body,
        eyebrow="Daily Operations history",
    )


def _maintenance_request_summary(item: Mapping[str, Any]) -> HtmlFragment:
    attempted = item.get("provider_call_attempted")
    succeeded = item.get("provider_request_succeeded")
    if succeeded is True:
        return badge("Succeeded", tone="positive")
    if attempted is True:
        return badge("Failed", tone="danger")
    return badge("Not attempted", tone="muted")


def _maintenance_publication_summary(item: Mapping[str, Any]) -> HtmlFragment:
    if item.get("pointer_invalidated") is True:
        return badge("Authority invalidated", tone="danger")
    if item.get("pointer_rolled_back") is True:
        return badge("Rolled back", tone="warning")
    if (
        item.get("pointer_published") is True
        and item.get("dashboard_restarted") is True
    ):
        return badge("Published / restarted", tone="positive")
    if item.get("pointer_published") is True:
        return badge("Published / restart failed", tone="danger")
    return badge("Not published", tone="muted")


def _maintenance_metadata_disclosure(snapshot: DashboardSnapshot) -> str:
    rows = []
    for name, metadata in sorted(snapshot.maintenance_history_metadata.items()):
        rows.append((
            name,
            humanize_enum(metadata.get("authority")),
            display_count(metadata.get("source_row_count")),
            display_count(metadata.get("returned_row_count")),
            humanize_reason(metadata.get("error"), fallback="None recorded."),
            metadata.get("sha256") or UNAVAILABLE,
        ))
    table = data_table(
        ("Artifact", "Authority", "Source rows", "Loaded rows", "Read issue", "SHA-256"),
        rows,
        caption="Daily Operations telemetry read metadata",
        empty="No Daily Operations telemetry metadata was loaded.",
    )
    return str(disclosure(
        "Daily Operations artifact evidence",
        table,
        summary="Read-only bounds, errors, and fingerprints",
        css_class="technical-details",
    ))


def _campaign_filters(query: Mapping[str, str] | None) -> dict[str, str]:
    raw = query or {}
    return {
        "status": str(raw.get("status") or "").strip().casefold(),
        "provider": str(raw.get("provider") or "").strip().casefold(),
        "search": str(raw.get("search") or "").strip().casefold(),
    }


def _filter_attempts(
    rows: tuple[dict[str, Any], ...],
    filters: Mapping[str, str],
) -> tuple[Mapping[str, Any], ...]:
    selected = []
    for row in rows:
        if filters["status"] and str(row.get("status") or "").casefold() != filters["status"]:
            continue
        if filters["provider"] and str(row.get("provider") or "").casefold() != filters["provider"]:
            continue
        text = " ".join(
            str(row.get(field) or "")
            for field in ("artifact_namespace", "run_id", "attempt_id", "failure_class")
        ).casefold()
        if filters["search"] and filters["search"] not in text:
            continue
        selected.append(row)
    return tuple(selected)


def _campaign_filter_form(
    filters: Mapping[str, str],
    attempts: tuple[Mapping[str, Any], ...],
) -> str:
    statuses = tuple(sorted({
        str(row.get("status") or "").strip().casefold()
        for row in attempts
        if str(row.get("status") or "").strip()
    }))
    providers = tuple(sorted({
        str(row.get("provider") or "").strip().casefold()
        for row in attempts
        if str(row.get("provider") or "").strip()
    }))
    status_options = '<option value="">All results</option>' + "".join(
        f'<option value="{escape_html(value)}"{" selected" if filters["status"] == value else ""}>{escape_html(humanize_enum(value))}</option>'
        for value in statuses
    )
    provider_options = '<option value="">All providers</option>' + "".join(
        f'<option value="{escape_html(value)}"{" selected" if filters["provider"] == value else ""}>{escape_html(humanize_enum(value))}</option>'
        for value in providers
    )
    active_count = sum(bool(filters[name]) for name in ("status", "provider", "search"))
    form = (
        '<form class="filter-panel embedded-filter-panel" method="get" action="/campaign-history"><div class="filter-grid">'
        f'<label><span>Result</span><select name="status">{status_options}</select></label>'
        f'<label><span>Provider</span><select name="provider">{provider_options}</select></label>'
        f'<label><span>Search identity</span><input type="search" name="search" value="{escape_html(filters["search"])}" placeholder="Namespace, run, attempt…"></label>'
        '</div><div class="filter-actions"><button class="button button-primary" type="submit">Apply</button>'
        '<a class="button button-quiet" href="/campaign-history">Clear</a></div></form>'
    )
    return str(disclosure(
        "Filter run history",
        HtmlFragment(form),
        summary=f"{active_count} active",
        open=bool(active_count),
        css_class="filter-disclosure campaign-filter-disclosure",
    ))


__all__ = ("render_campaign_page",)
