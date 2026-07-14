"""Bounded Decision Radar campaign-history dashboard surface."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .components import (
    badge,
    data_table,
    definition_list,
    disclosure,
    empty_state,
    escape_html,
    time_element,
)
from .models import DashboardSnapshot
from .presentation import UNAVAILABLE, humanize_enum, humanize_reason, present_time
from .system_page_support import (
    as_mapping,
    display_count,
    render_metric_grid,
    render_page_intro,
    render_panel,
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
    succeeded = sum(
        1 for row in snapshot.campaign_attempts if row.get("provider_request_succeeded") is True
    )
    counted = sum(
        1 for row in snapshot.campaign_attempts if row.get("decision_radar_campaign_counted") is True
    )
    current_value = (
        str(len(snapshot.current_market_observations))
        if snapshot.generation_authoritative
        else "Suppressed"
    )
    metrics = (
        ("Bounded attempts loaded", str(len(snapshot.campaign_attempts)), "neutral"),
        ("Provider successes", str(succeeded), "positive" if succeeded else "muted"),
        ("Campaign-counted", str(counted), "info"),
        ("Current observations", current_value, "info" if snapshot.generation_authoritative else "danger"),
        (
            "Current ideas",
            str(len(snapshot.current_candidates)) if snapshot.generation_authoritative else "Suppressed",
            "positive" if snapshot.generation_authoritative and snapshot.current_candidates else "muted",
        ),
        (
            "Warm assets",
            str(quality["warm"]) if snapshot.generation_authoritative else "Suppressed",
            "positive" if snapshot.generation_authoritative and quality["warm"] else "warning",
        ),
    )
    current_authority = (
        _campaign_current_authority(snapshot, ledger, generation, quality)
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
    return (
        render_page_intro(
            "Campaign History",
            (
                "Bounded no-send observation attempts and the exact current authority. "
                "Historical rows are context, never current truth."
            ),
            "Decision Radar observation campaign",
        )
        + render_metric_grid(metrics)
        + current_authority
        + _campaign_latest(snapshot)
        + _campaign_filter_form(filters)
        + _campaign_attempt_table(attempts)
        + _campaign_reservation(reservation)
        + _campaign_metadata_disclosure(snapshot)
    )


def _campaign_current_authority(
    snapshot: DashboardSnapshot,
    ledger: Mapping[str, Any],
    generation: Mapping[str, Any],
    quality: Mapping[str, int],
) -> str:
    provenance = as_mapping(generation.get("market_provenance"))
    data_quality = as_mapping(provenance.get("data_quality"))
    values = (
        ("Current pointer", badge(snapshot.generation_authority_status)),
        ("Namespace", snapshot.artifact_namespace),
        ("Run", snapshot.run_id),
        ("Revision", snapshot.revision),
        ("Provider", humanize_enum(ledger.get("provider") or generation.get("provider"))),
        ("Authorization present", badge((ledger.get("live_provider_authorized") if ledger else generation.get("live_provider_authorized")) is True)),
        ("Data mode", humanize_enum(ledger.get("candidate_source_mode") or generation.get("candidate_source_mode") or generation.get("data_mode"))),
        ("Observed", time_element(present_time(ledger.get("observed_at") or generation.get("observed_at")))),
        ("Provider request", badge((ledger.get("provider_request_succeeded") if ledger else generation.get("provider_request_succeeded")) is True)),
        ("Raw / selected rows", f"{display_count(ledger.get('raw_market_row_count') or generation.get('raw_market_row_count'))} / {display_count(ledger.get('selected_market_row_count') or generation.get('selected_market_row_count'))}"),
        ("Observations / anomalies / ideas", f"{len(snapshot.current_market_observations)} / {len(snapshot.current_market_anomalies)} / {len(snapshot.current_candidates)}"),
        ("Core / cards", f"{display_count(generation.get('core_row_count'))} / {display_count(generation.get('card_count'))}"),
        ("Baseline", f"{quality['warm']} warm · {quality['warming']} warming · {quality['cold']} cold"),
        ("Direct / proxy features", f"{display_count(data_quality.get('direct_feature_count') or generation.get('direct_feature_count'))} / {display_count(data_quality.get('proxy_feature_count') or generation.get('proxy_feature_count'))}"),
        ("Spread verified", f"{quality['spread']} / {len(snapshot.current_market_observations)}"),
        ("Strict doctor", badge(snapshot.doctor_status)),
        ("Publication", badge(generation.get("status") or snapshot.generation_authority_status)),
        ("Campaign counted", badge(generation.get("decision_radar_campaign_counted") is True)),
    )
    return render_panel(
        "Current authoritative generation",
        str(definition_list(values, css_class="definition-grid"))
        + '<p class="muted">This is the only section on this page allowed to describe current authority.</p>',
        eyebrow="Exact pointer binding",
    )


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
    failure = (
        humanize_reason(latest.get("failure_class"))
        if latest.get("failure_class")
        else "No failure recorded."
    )
    values = (
        ("Attempt", latest.get("attempt_id") or UNAVAILABLE),
        ("Recorded", time_element(present_time(latest.get("recorded_at")))),
        ("Observed", time_element(present_time(latest.get("observed_at")))),
        ("Provider", humanize_enum(latest.get("provider"))),
        ("Status", badge(latest.get("status"))),
        ("Provider call attempted", badge(latest.get("provider_call_attempted") is True)),
        ("Request succeeded", badge(latest.get("provider_request_succeeded") is True)),
        ("Campaign counted", badge(latest.get("decision_radar_campaign_counted") is True)),
        ("Namespace", latest.get("artifact_namespace") or UNAVAILABLE),
        ("Run", latest.get("run_id") or UNAVAILABLE),
        ("Failure", failure),
    )
    return render_panel(
        "Latest attempt receipt",
        str(definition_list(values, css_class="definition-grid"))
        + str(badge("Historical / non-authoritative", tone="info")),
        eyebrow="Last bounded attempt",
    )


def _campaign_attempt_table(
    attempts: tuple[Mapping[str, Any], ...],
) -> str:
    rows = []
    for item in reversed(attempts):
        failure = (
            humanize_reason(item.get("failure_class"))
            if item.get("failure_class")
            else "No failure recorded."
        )
        rows.append((
            time_element(present_time(item.get("recorded_at")), primary="combined"),
            humanize_enum(item.get("provider")),
            badge(item.get("status")),
            badge(item.get("provider_call_attempted") is True),
            badge(item.get("provider_request_succeeded") is True),
            badge(item.get("decision_radar_campaign_counted") is True),
            humanize_enum(item.get("candidate_source_mode") or item.get("data_mode")),
            item.get("artifact_namespace") or UNAVAILABLE,
            item.get("run_id") or UNAVAILABLE,
            failure,
        ))
    return render_panel(
        "Bounded attempt ledger",
        '<div class="alert alert-info"><strong>Historical / non-authoritative.</strong> '
        "These receipts cannot replace the exact current pointer.</div>"
        + str(data_table(
            (
                "Recorded", "Provider", "Result", "Call attempted", "Request succeeded",
                "Campaign counted", "Data mode", "Namespace", "Run", "Failure",
            ),
            rows,
            caption="Bounded historical no-send attempts",
            empty="No historical attempt receipts match these filters.",
        )),
        eyebrow="Observation history",
    )


def _campaign_reservation(reservation: Mapping[str, Any]) -> str:
    if not reservation:
        return render_panel(
            "Cadence and reservation",
            str(empty_state(
                "Reservation evidence unavailable",
                "No valid campaign reservation receipt was loaded.",
            )),
            eyebrow="Next eligibility",
        )
    next_at = present_time(reservation.get("next_provider_call_at"))
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
        ("Acquired", time_element(present_time(reservation.get("acquired_at")))),
        ("Provider call reserved", time_element(present_time(reservation.get("provider_call_reserved_at")))),
        ("Released", time_element(present_time(reservation.get("released_at")))),
        ("Reservation expiry", time_element(present_time(reservation.get("expires_at")))),
        ("Next provider-call eligibility", time_element(next_at)),
        ("Eligibility summary", now_status),
        ("No-send", badge(reservation.get("no_send") is True)),
    )
    return render_panel(
        "Cadence and reservation",
        str(definition_list(values, css_class="definition-grid")),
        eyebrow="Next eligibility",
    )


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


def _campaign_filter_form(filters: Mapping[str, str]) -> str:
    return (
        '<form class="filter-panel" method="get" action="/campaign-history"><div class="filter-grid">'
        f'<label><span>Result</span><input name="status" value="{escape_html(filters["status"])}" placeholder="Complete"></label>'
        f'<label><span>Provider</span><input name="provider" value="{escape_html(filters["provider"])}" placeholder="CoinGecko"></label>'
        f'<label><span>Search identity</span><input type="search" name="search" value="{escape_html(filters["search"])}" placeholder="Namespace, run, attempt…"></label>'
        '</div><div class="filter-actions"><button class="button button-primary" type="submit">Apply</button>'
        '<a class="button button-quiet" href="/campaign-history">Clear</a></div></form>'
    )


__all__ = ("render_campaign_page",)
