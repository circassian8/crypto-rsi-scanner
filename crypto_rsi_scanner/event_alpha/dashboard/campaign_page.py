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
from .presentation import (
    UNAVAILABLE,
    format_duration,
    format_number,
    format_percent,
    humanize_enum,
    humanize_reason,
    present_time,
)
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
        + _control_regime_generation_history(snapshot)
        + _shadow_surprise_distributions(snapshot)
        + _protocol_v2_episode_coverage(snapshot)
        + history
        + _maintenance_cycle_table(snapshot)
        + _campaign_metadata_disclosure(snapshot)
        + _maintenance_metadata_disclosure(snapshot)
    )


def _shadow_surprise_distributions(snapshot: DashboardSnapshot) -> str:
    state = snapshot.campaign_operator_actions
    raw = state.get("shadow_temporal_surprise")
    if state.get("status") != "ready" or not isinstance(raw, Mapping) or not raw:
        return ""
    feature_coverage = raw.get("feature_coverage")
    if not isinstance(feature_coverage, Mapping) or not feature_coverage:
        return ""
    rows = []
    for feature, value in sorted(feature_coverage.items()):
        if not isinstance(value, Mapping):
            continue
        minimum_sample = value.get("minimum_eligible_sample_count")
        maximum_sample = value.get("maximum_eligible_sample_count")
        sample_range = (
            f"{display_count(minimum_sample)}–{display_count(maximum_sample)}"
            if minimum_sample is not None and maximum_sample is not None
            else UNAVAILABLE
        )
        rows.append((
            humanize_enum(feature),
            humanize_enum(value.get("family")),
            (
                f"{display_count(value.get('ready_count'))} / "
                f"{display_count(value.get('evaluated_observation_count'))}"
            ),
            sample_range,
            _distribution_triplet(
                value,
                ("robust_z_p05", "robust_z_median", "robust_z_p95"),
                decimals=3,
                signed=True,
            ),
            humanize_enum(value.get("descriptive_tail_rank_kind")),
            _distribution_triplet(
                value,
                (
                    "descriptive_tail_rank_minimum",
                    "descriptive_tail_rank_median",
                    "descriptive_tail_rank_p95",
                ),
                decimals=4,
            ),
            _shadow_extreme_observation(
                value.get("minimum_tail_observation"),
                now=snapshot.generation_authority_checked_at,
            ),
        ))
    statuses = raw.get("projection_status_counts")
    statuses = statuses if isinstance(statuses, Mapping) else {}
    values = (
        ("Audit status", badge(humanize_enum(raw.get("status")), tone="info")),
        ("Evaluated observations", display_count(raw.get("evaluated_observation_count"))),
        ("Assets replayed", display_count(raw.get("asset_count"))),
        ("Complete projections", display_count(statuses.get("ready"))),
        ("Partial projections", display_count(statuses.get("partial"))),
        ("Unavailable projections", display_count(statuses.get("unavailable"))),
    )
    body = (
        '<div class="alert alert-info"><strong>Descriptive shadow evidence only.</strong> '
        "Robust-z magnitude and empirical rank answer different questions. The ranks are not "
        "p-values, overlapping samples are not independent, and reference-set variation is not "
        "an effective-sample-size estimate. None of these values changes routes, scores, "
        "thresholds, or current authority.</div>"
        + str(definition_list(values, css_class="definition-grid"))
        + str(data_table(
            (
                "Feature",
                "Family",
                "Ready / evaluated",
                "Sample range",
                "Robust z p05 / med / p95",
                "Rank family",
                "Rank min / med / p95",
                "Rarest-rank observation",
            ),
            rows,
            caption="Canonical causal shadow replay distributions",
            empty="No ready shadow distributions are available.",
            compact=True,
        ))
        + _shadow_variation_table(feature_coverage, snapshot=snapshot)
        + _shadow_projection_scope_notice(raw)
        + _shadow_asset_variation_table(raw, snapshot=snapshot)
        + _shadow_interval_overlap_table(raw, snapshot=snapshot)
    )
    return render_panel(
        "Shadow anomaly distributions",
        body,
        eyebrow="Causal replay · copied from canonical campaign truth",
    )


def _shadow_projection_scope_notice(raw: Mapping[str, Any]) -> str:
    if raw.get("asset_variation_projection_status") != (
        "summary_only_full_evidence_in_source_report"
    ):
        return ""
    return (
        '<div class="alert alert-info"><strong>Bounded dashboard projection.</strong> '
        f"Aggregate shadow evidence is current; {escape_html(display_count(raw.get('asset_variation_summary_count')))} "
        "asset-level trace summaries remain fingerprint-bound in the full campaign report "
        "and are intentionally omitted from this read-only page.</div>"
    )


def _distribution_triplet(
    value: Mapping[str, Any],
    fields: tuple[str, str, str],
    *,
    decimals: int,
    signed: bool = False,
) -> str:
    return " / ".join(
        format_number(value.get(field), decimals=decimals, signed=signed)
        for field in fields
    )


def _shadow_variation_table(
    feature_coverage: Mapping[str, Any],
    *,
    snapshot: DashboardSnapshot,
) -> str:
    rows = []
    for feature, value in sorted(feature_coverage.items()):
        if not isinstance(value, Mapping) or value.get("variation_available") is not True:
            continue
        rows.append((
            humanize_enum(feature),
            (
                f"{display_count(value.get('variation_observation_count'))} / "
                f"{display_count(value.get('evaluated_observation_count'))}"
            ),
            _ratio_distribution_triplet(
                value,
                (
                    "distinct_baseline_value_ratio_minimum",
                    "distinct_baseline_value_ratio_median",
                    "distinct_baseline_value_ratio_p95",
                ),
            ),
            _ratio_distribution_triplet(
                value,
                (
                    "maximum_baseline_value_tie_ratio_median",
                    "maximum_baseline_value_tie_ratio_p95",
                    "maximum_baseline_value_tie_ratio_maximum",
                ),
            ),
            _shadow_variation_extreme(
                value.get("minimum_distinct_ratio_observation"),
                now=snapshot.generation_authority_checked_at,
            ),
        ))
    if not rows:
        return ""
    return str(data_table(
        (
            "Feature",
            "Eligible variation rows / evaluated",
            "Distinct share min / med / p95",
            "Largest-tie share med / p95 / max",
            "Least-diverse reference set",
        ),
        rows,
        caption=(
            "Reference-set variation at the existing nominal sample minimum; "
            "descriptive only"
        ),
        empty="No sample-eligible variation diagnostics are available.",
        compact=True,
    ))


def _ratio_distribution_triplet(
    value: Mapping[str, Any],
    fields: tuple[str, str, str],
) -> str:
    return _ratio_distribution_values(value, fields)


def _ratio_distribution_values(
    value: Mapping[str, Any],
    fields: tuple[str, ...],
) -> str:
    return " / ".join(
        format_percent(value.get(field), unit="fraction", decimals=1)
        for field in fields
    )


def _shadow_variation_extreme(value: Any, *, now: Any) -> HtmlFragment | str:
    if not isinstance(value, Mapping):
        return UNAVAILABLE
    asset_id = value.get("canonical_asset_id")
    observed_at = value.get("observed_at")
    sample_count = value.get("sample_count")
    distinct_count = value.get("distinct_baseline_value_count")
    maximum_tie_count = value.get("maximum_baseline_value_tie_count")
    if (
        asset_id in (None, "")
        or observed_at in (None, "")
        or sample_count in (None, "")
        or distinct_count in (None, "")
        or maximum_tie_count in (None, "")
    ):
        return UNAVAILABLE
    return HtmlFragment(
        f"{escape_html(humanize_enum(asset_id))}<br>"
        f"{escape_html(display_count(distinct_count))}/{escape_html(display_count(sample_count))} "
        f"distinct · largest tie {escape_html(display_count(maximum_tie_count))}/"
        f"{escape_html(display_count(sample_count))}<br>"
        f'{time_element(present_time(observed_at, now=now), primary="utc")}'
    )


def _shadow_asset_variation_table(
    raw: Mapping[str, Any],
    *,
    snapshot: DashboardSnapshot,
) -> str:
    summaries = raw.get("asset_variation_summaries")
    if (
        raw.get("asset_variation_diagnostics_available") is not True
        or not isinstance(summaries, (list, tuple))
    ):
        return ""
    input_trace_available = raw.get("input_trace_diagnostics_available") is True
    return_timing_available = (
        raw.get("return_sampling_timing_diagnostics_available") is True
    )
    repeated_rows: list[tuple[float, float, str, str, Mapping[str, Any], Mapping[str, Any]]] = []
    for asset in summaries:
        if not isinstance(asset, Mapping):
            continue
        features = asset.get("feature_variation")
        if not isinstance(features, Mapping):
            continue
        for feature, variation in features.items():
            if (
                not isinstance(variation, Mapping)
                or not isinstance(
                    variation.get("repeated_baseline_value_observation_count"),
                    int,
                )
                or variation.get("repeated_baseline_value_observation_count") <= 0
            ):
                continue
            minimum_distinct = variation.get(
                "distinct_baseline_value_ratio_minimum"
            )
            maximum_tie = variation.get(
                "maximum_baseline_value_tie_ratio_maximum"
            )
            if not isinstance(minimum_distinct, (int, float)) or not isinstance(
                maximum_tie, (int, float)
            ):
                continue
            repeated_rows.append((
                float(minimum_distinct),
                -float(maximum_tie),
                str(asset.get("canonical_asset_id") or ""),
                str(feature),
                asset,
                variation,
            ))
    repeated_rows.sort(key=lambda row: row[:4])
    limit = 24
    table_rows = []
    for _, _, asset_id, feature, asset, variation in repeated_rows[:limit]:
        variation_count = variation.get("variation_observation_count")
        repeated_count = variation.get(
            "repeated_baseline_value_observation_count"
        )
        row_values = [
            _shadow_asset_identity(asset_id, asset),
            humanize_enum(feature),
            f"{display_count(repeated_count)} / {display_count(variation_count)}",
            _ratio_distribution_values(
                variation,
                (
                    "distinct_baseline_value_ratio_minimum",
                    "distinct_baseline_value_ratio_median",
                ),
            ),
            _ratio_distribution_values(
                variation,
                (
                    "maximum_baseline_value_tie_ratio_median",
                    "maximum_baseline_value_tie_ratio_maximum",
                ),
            ),
        ]
        if input_trace_available:
            row_values.append(_shadow_input_trace_summary(variation))
        if return_timing_available:
            row_values.append(_shadow_return_sampling_timing_summary(variation))
        row_values.extend((
            _shadow_asset_source_basis(asset, feature=feature),
            _shadow_variation_extreme(
                variation.get("latest_variation_observation"),
                now=snapshot.generation_authority_checked_at,
            ),
        ))
        table_rows.append(tuple(row_values))
    if not table_rows:
        return ""
    count_note = (
        f"Showing all {len(repeated_rows)} exact asset-feature pairs with at least one "
        "repeated baseline value."
        if len(repeated_rows) <= limit
        else (
            f"Showing the {limit} least-diverse of {len(repeated_rows)} exact "
            "asset-feature pairs with repeated baseline values."
        )
    )
    headers = [
        "Asset",
        "Feature",
        "Repeated / eligible",
        "Distinct share min / med",
        "Largest-tie share med / max",
    ]
    if input_trace_available:
        headers.append("Source-repeat / transform / mixed · max run source / derived")
    if return_timing_available:
        headers.append(
            "Reuse observations asset-anchor / benchmark-end / benchmark-anchor "
            "· max timing error asset / benchmark / alignment (s)"
        )
    headers.extend((
        "Retained provider · mode · basis",
        "Latest reference set",
    ))
    trace_note = (
        " Source repetition means the exact value-only source tuple repeated; "
        "transform collision means distinct source tuples produced the same rounded "
        "derived value. Neither result attributes provider fault."
        if input_trace_available
        else ""
    )
    timing_note = (
        " Return sampling uses exact observation identities: reuse counts show "
        "whether an anchor or benchmark endpoint served more than one sample, "
        "while timing errors show realized distance from the nominal horizon and "
        "asset/benchmark endpoint alignment. These diagnostics do not change policy."
        if return_timing_available
        else ""
    )
    return (
        '<div class="alert alert-info"><strong>Attribution required.</strong> '
        + escape_html(count_note)
        + " Repetition can reflect legitimate low-motion behavior, provider refresh cadence, "
        "or upstream quantization. This ranking is outcome-blind and applies no exclusion."
        + escape_html(trace_note)
        + escape_html(timing_note)
        + "</div>"
        + str(data_table(
            tuple(headers),
            table_rows,
            caption="Repeated reference sets by canonical asset and feature",
            empty="No repeated sample-eligible reference sets were recorded.",
            compact=True,
        ))
    )


def _shadow_input_trace_summary(value: Mapping[str, Any]) -> str:
    source = display_count(
        value.get("source_tuple_repetition_observation_count")
    )
    transform = display_count(
        value.get("transform_collision_observation_count")
    )
    mixed = display_count(
        value.get("mixed_source_and_transform_observation_count")
    )
    source_run = display_count(
        value.get("maximum_consecutive_source_value_tuple_count")
    )
    derived_run = display_count(
        value.get("maximum_consecutive_derived_value_count")
    )
    return f"{source} / {transform} / {mixed} · {source_run} / {derived_run}"


def _shadow_interval_overlap_table(
    raw: Mapping[str, Any],
    *,
    snapshot: DashboardSnapshot,
) -> str:
    summaries = raw.get("asset_variation_summaries")
    if (
        raw.get("return_sampling_overlap_diagnostics_available") is not True
        or not isinstance(summaries, (list, tuple))
    ):
        return ""
    rows: list[
        tuple[float, str, str, Mapping[str, Any], Mapping[str, Any] | None]
    ] = []
    for asset in summaries:
        if not isinstance(asset, Mapping):
            continue
        features = asset.get("feature_variation")
        if not isinstance(features, Mapping):
            continue
        asset_id = str(asset.get("canonical_asset_id") or "")
        for feature, variation in features.items():
            if not isinstance(variation, Mapping):
                continue
            timing = variation.get("return_sampling_timing_summary")
            if not isinstance(timing, Mapping):
                continue
            asset_overlap = timing.get("asset_interval_overlap_summary")
            benchmark_overlap = timing.get("benchmark_interval_overlap_summary")
            if not isinstance(asset_overlap, Mapping):
                continue
            minimum = asset_overlap.get("unique_clock_coverage_ratio_minimum")
            if not isinstance(minimum, (int, float)) or isinstance(minimum, bool):
                continue
            rows.append((
                float(minimum),
                asset_id,
                str(feature),
                asset_overlap,
                benchmark_overlap if isinstance(benchmark_overlap, Mapping) else None,
            ))
    rows.sort(key=lambda row: row[:3])
    if not rows:
        return ""
    limit = 36
    table_rows = []
    for _, asset_id, feature, asset_overlap, benchmark_overlap in rows[:limit]:
        asset_counts = (
            f"{display_count(asset_overlap.get('adjacent_overlap_observation_count'))} / "
            f"{display_count(asset_overlap.get('interval_reuse_observation_count'))}"
        )
        benchmark_counts = (
            f"{display_count(benchmark_overlap.get('adjacent_overlap_observation_count'))} / "
            f"{display_count(benchmark_overlap.get('interval_reuse_observation_count'))}"
            if benchmark_overlap is not None
            else UNAVAILABLE
        )
        table_rows.append((
            humanize_enum(asset_id),
            humanize_enum(feature),
            display_count(asset_overlap.get("observation_count")),
            asset_counts,
            _ratio_distribution_values(
                asset_overlap,
                (
                    "unique_clock_coverage_ratio_minimum",
                    "unique_clock_coverage_ratio_median",
                    "unique_clock_coverage_ratio_maximum",
                ),
            ),
            (
                f"{format_number(asset_overlap.get('maximum_adjacent_overlap_seconds'), decimals=0)} / "
                f"{format_number(asset_overlap.get('maximum_overlap_excess_seconds'), decimals=0)}"
            ),
            benchmark_counts,
            (
                _ratio_distribution_values(
                    benchmark_overlap,
                    (
                        "unique_clock_coverage_ratio_minimum",
                        "unique_clock_coverage_ratio_median",
                        "unique_clock_coverage_ratio_maximum",
                    ),
                )
                if benchmark_overlap is not None
                else UNAVAILABLE
            ),
            _shadow_interval_overlap_extreme(
                asset_overlap.get("minimum_unique_clock_coverage_observation"),
                now=snapshot.generation_authority_checked_at,
            ),
        ))
    count_note = (
        f"Showing all {len(rows)} sample-eligible asset-return pairs."
        if len(rows) <= limit
        else f"Showing the {limit} lowest-coverage of {len(rows)} pairs."
    )
    return (
        '<div class="alert alert-info"><strong>Dependent rolling windows.</strong> '
        + escape_html(count_note)
        + " Coverage is the exact union of half-open anchor-to-endpoint intervals. "
        "Adjacent overlap, exact interval reuse, and unique clock coverage remain "
        "descriptive: they do not estimate effective sample size, change sample "
        "weights, exclude assets, or alter routes and scores.</div>"
        + str(data_table(
            (
                "Asset",
                "Return feature",
                "Eligible sets",
                "Asset overlap / exact reuse sets",
                "Asset unique clock min / med / max",
                "Asset max adjacent / total excess (s)",
                "Benchmark overlap / exact reuse sets",
                "Benchmark unique clock min / med / max",
                "Lowest asset coverage reference",
            ),
            table_rows,
            caption="Rolling return-window dependence by canonical asset and family",
            empty="No sample-eligible interval-overlap evidence is available.",
            compact=True,
        ))
    )


def _shadow_interval_overlap_extreme(value: Any, *, now: Any) -> HtmlFragment | str:
    if not isinstance(value, Mapping):
        return UNAVAILABLE
    observed_at = value.get("observed_at")
    interval_count = value.get("interval_count")
    ratio = value.get("unique_clock_coverage_ratio")
    unique = value.get("unique_clock_coverage_seconds")
    total = value.get("total_interval_seconds")
    if any(item in (None, "") for item in (observed_at, interval_count, ratio, unique, total)):
        return UNAVAILABLE
    return HtmlFragment(
        f"{escape_html(format_percent(ratio, unit='fraction', decimals=1))} · "
        f"{escape_html(display_count(interval_count))} intervals<br>"
        f"{escape_html(format_number(unique, decimals=0))}/"
        f"{escape_html(format_number(total, decimals=0))} unique/total s<br>"
        f'{time_element(present_time(observed_at, now=now), primary="utc")}'
    )


def _shadow_return_sampling_timing_summary(value: Mapping[str, Any]) -> str:
    summary = value.get("return_sampling_timing_summary")
    if not isinstance(summary, Mapping):
        return UNAVAILABLE
    reuse = " / ".join(
        display_count(summary.get(field))
        for field in (
            "asset_anchor_reuse_observation_count",
            "benchmark_endpoint_reuse_observation_count",
            "benchmark_anchor_reuse_observation_count",
        )
    )
    timing = " / ".join(
        format_number(summary.get(field), decimals=0)
        for field in (
            "maximum_asset_anchor_selection_error_seconds",
            "maximum_benchmark_anchor_selection_error_seconds",
            "maximum_benchmark_endpoint_alignment_lag_seconds",
        )
    )
    return f"{reuse} · {timing}"


def _shadow_asset_identity(asset_id: str, asset: Mapping[str, Any]) -> HtmlFragment:
    symbols = asset.get("retained_symbol_counts")
    symbol_text = _context_counts_label(symbols) if isinstance(symbols, Mapping) else ""
    suffix = f"<br>{escape_html(symbol_text)}" if symbol_text else ""
    return HtmlFragment(f"{escape_html(humanize_enum(asset_id))}{suffix}")


def _shadow_asset_source_basis(
    asset: Mapping[str, Any],
    *,
    feature: str,
) -> str:
    providers = _context_counts_label(asset.get("retained_provider_counts"))
    modes = _context_counts_label(asset.get("retained_data_mode_counts"))
    basis_container = asset.get("retained_feature_basis_counts")
    basis_key = feature if feature in {"volume_24h", "turnover_24h"} else "price"
    basis = (
        _context_counts_label(basis_container.get(basis_key))
        if isinstance(basis_container, Mapping)
        else ""
    )
    return " · ".join(value for value in (providers, modes, basis) if value) or UNAVAILABLE


def _context_counts_label(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    return ", ".join(
        f"{humanize_enum(identity)} {display_count(count)}"
        for identity, count in sorted(value.items())
    )


def _shadow_extreme_observation(value: Any, *, now: Any) -> HtmlFragment | str:
    if not isinstance(value, Mapping):
        return UNAVAILABLE
    asset_id = value.get("canonical_asset_id")
    observed_at = value.get("observed_at")
    if asset_id in (None, "") or observed_at in (None, ""):
        return UNAVAILABLE
    return HtmlFragment(
        f"{escape_html(humanize_enum(asset_id))}<br>"
        f'{time_element(present_time(observed_at, now=now), primary="utc")}'
    )


def _control_regime_generation_history(snapshot: DashboardSnapshot) -> str:
    state = snapshot.campaign_operator_actions
    baseline = state.get("temporal_baseline")
    raw = (
        baseline.get("control_market_regime_generation_audit")
        if state.get("status") == "ready" and isinstance(baseline, Mapping)
        else None
    )
    if not isinstance(raw, Mapping):
        return ""
    latest = raw.get("latest_complete_generation")
    latest = latest if isinstance(latest, Mapping) else {}
    verified = display_count(raw.get("verified_source_generation_count"))
    total = display_count(raw.get("input_generation_count"))
    complete = display_count(raw.get("complete_universe_generation_count"))
    ready = display_count(raw.get("ready_generation_count"))
    incomplete = display_count(raw.get("incomplete_generation_count"))
    transitions = display_count(raw.get("transition_count"))
    changes = display_count(raw.get("universe_change_transition_count"))
    recent = display_count(raw.get("incomplete_with_recent_entry_count"))
    without_recent = display_count(
        raw.get("incomplete_without_recent_entry_count")
    )
    latest_eligible = display_count(latest.get("eligible_input_count"))
    latest_expected = display_count(latest.get("universe_expected_count"))
    latest_missing = ", ".join(
        str(item) for item in latest.get("missing_asset_ids") or ()
    ) or "None"
    latest_recent = ", ".join(
        str(item)
        for item in latest.get("recent_entry_missing_asset_ids") or ()
    ) or "None"
    membership_context = _regime_membership_context_label(
        latest.get("missing_input_membership_context")
    )
    anchor_context = _regime_anchor_context_label(
        raw.get("latest_missing_input_anchor_audit")
    )
    cadence_context = _regime_cadence_context_label(
        raw.get("observation_cadence_gap_audit")
    )
    values = (
        ("Verified source envelopes", f"{verified} / {total}"),
        ("Complete universes", complete),
        ("Ready / incomplete", f"{ready} / {incomplete}"),
        ("Comparable transitions", transitions),
        ("Membership changes", changes),
        ("Incomplete + recent entry", recent),
        ("Incomplete without recent entry", without_recent),
        ("Latest causal inputs", f"{latest_eligible} / {latest_expected}"),
        ("Latest missing", latest_missing),
        ("Latest recent-entry overlap", latest_recent),
        ("Latest continuous membership", membership_context),
        ("Latest anchor-window replay", anchor_context),
        ("Complete-generation cadence", cadence_context),
    )
    missing_counts = raw.get("missing_asset_generation_counts")
    missing_rows = []
    if isinstance(missing_counts, Mapping):
        missing_rows = sorted(
            (
                (str(asset_id), count)
                for asset_id, count in missing_counts.items()
                if type(count) is int and count > 0
            ),
            key=lambda item: (-item[1], item[0]),
        )[:8]
    missing_table = (
        str(disclosure(
            "Recurring missing inputs",
            data_table(
                ("Asset", "Incomplete generations"),
                [
                    (humanize_enum(asset_id), display_count(count))
                    for asset_id, count in missing_rows
                ],
                caption="Bounded exact-generation missing-input frequency",
                compact=True,
            ),
            summary=f"{len(missing_rows)} recurring asset{'s' if len(missing_rows) != 1 else ''}",
            css_class="campaign-technical-disclosure",
        ))
        if missing_rows
        else ""
    )
    body = (
        '<div class="alert alert-info"><strong>Observed history, not a policy input.</strong> '
        "This compares immutable generation envelopes. Recent membership entry is overlap, "
        "not proof of causation or anchor eligibility; pre-contract rows do not enter the "
        "prospective membership clock.</div>"
        + str(definition_list(values, css_class="definition-grid"))
        + missing_table
    )
    return render_panel(
        "Causal 24-hour input history",
        body,
        eyebrow="Exact generation evidence · no backfill",
    )


def _regime_membership_context_label(value: Any) -> str:
    rows = [dict(row) for row in value or () if isinstance(row, Mapping)]
    if not rows:
        return "None"
    values = []
    for row in rows:
        asset_id = humanize_enum(row.get("canonical_asset_id"))
        if row.get("membership_start_known") is True:
            values.append(
                f"{asset_id}: {format_duration(row.get('continuous_membership_age_seconds'))} "
                f"since {row.get('continuous_membership_started_at')}"
            )
        else:
            values.append(f"{asset_id}: start predates audited prospective window")
    return "; ".join(values)


def _regime_anchor_context_label(value: Any) -> str:
    if not isinstance(value, Mapping):
        return UNAVAILABLE
    diagnostics = [
        dict(row)
        for row in value.get("diagnostics") or ()
        if isinstance(row, Mapping)
    ]
    if not diagnostics:
        return humanize_enum(value.get("reason"))
    grouped: dict[tuple[Any, ...], list[str]] = {}
    for row in diagnostics:
        asset_id = humanize_enum(row.get("canonical_asset_id"))
        if row.get("status") == "ready":
            selected = row.get("selected_anchor")
            selected_at = (
                selected.get("observed_at")
                if isinstance(selected, Mapping)
                else UNAVAILABLE
            )
            grouped.setdefault(("ready", selected_at), []).append(asset_id)
            continue
        before = row.get("nearest_causal_before_window")
        after = row.get("nearest_post_target_observation")
        grouped.setdefault((
            "unavailable",
            row.get("anchor_window_start_at"),
            row.get("anchor_window_end_at"),
            before.get("distance_seconds") if isinstance(before, Mapping) else None,
            after.get("distance_seconds") if isinstance(after, Mapping) else None,
        ), []).append(asset_id)
    values = []
    for key, assets in grouped.items():
        identity = _campaign_asset_group_label(assets)
        if key[0] == "ready":
            values.append(f"{identity}: selected {key[1]}")
            continue
        _, window_start, window_end, before_seconds, after_seconds = key
        before_text = (
            f"; prior row {format_duration(before_seconds)} before window"
            if before_seconds is not None
            else ""
        )
        after_text = (
            f"; next row {format_duration(after_seconds)} after target"
            if after_seconds is not None
            else ""
        )
        values.append(
            f"{identity}: no anchor in {window_start} to "
            f"{window_end}{before_text}{after_text}"
        )
    visible = values[:8]
    if len(values) > 8:
        visible.append(f"+{len(values) - 8} exact groups in the source report")
    return "; ".join(visible)


def _campaign_asset_group_label(assets: list[str]) -> str:
    if len(assets) == 1:
        return assets[0]
    visible = ", ".join(assets[:4])
    suffix = f", +{len(assets) - 4} more" if len(assets) > 4 else ""
    return f"{len(assets)} assets ({visible}{suffix})"


def _regime_cadence_context_label(value: Any) -> str:
    if not isinstance(value, Mapping):
        return UNAVAILABLE
    adjacent = value.get("adjacent_interval_count")
    gaps = value.get("exceeding_anchor_tolerance_interval_count")
    tolerance = value.get("anchor_tolerance_seconds")
    if not all(type(item) is int and item >= 0 for item in (adjacent, gaps, tolerance)):
        return UNAVAILABLE
    if adjacent == 0:
        return "No adjacent complete-generation interval yet"
    maximum = value.get("maximum_interval")
    maximum_text = (
        f"; longest {format_duration(maximum.get('interval_seconds'))} from "
        f"{maximum.get('start_observed_at')} to {maximum.get('end_observed_at')}"
        if isinstance(maximum, Mapping)
        else ""
    )
    return (
        f"{gaps}/{adjacent} intervals exceed the {format_duration(tolerance)} "
        f"24-hour-anchor tolerance{maximum_text}; continuity risk only"
    )


def _protocol_v2_episode_coverage(snapshot: DashboardSnapshot) -> str:
    state = snapshot.campaign_operator_actions
    raw = state.get("episode_coverage")
    if state.get("status") != "ready" or not isinstance(raw, Mapping):
        return ""
    route_rows = [
        row for row in raw.get("route_coverage") or () if isinstance(row, Mapping)
    ]
    origin_rows = [
        row
        for row in raw.get("primary_origin_coverage") or ()
        if isinstance(row, Mapping)
    ]
    if not route_rows or not origin_rows:
        return ""
    route_table = data_table(
        (
            "Route",
            "Coverage",
            "Episodes",
            "Matured",
            "Not due",
            "Missing price",
            "Scoreable",
            "Aligned",
        ),
        [
            (
                humanize_enum(row.get("name")),
                badge(
                    "Observed"
                    if row.get("coverage_status") == "observed"
                    else "No episode",
                    tone=(
                        "info"
                        if row.get("coverage_status") == "observed"
                        else "muted"
                    ),
                ),
                display_count(row.get("episode_count")),
                display_count(row.get("matured_episode_count")),
                display_count(row.get("not_due_episode_count")),
                display_count(row.get("due_missing_price_episode_count")),
                display_count(row.get("scoreable_directional_episode_count")),
                display_count(row.get("aligned_episode_count")),
            )
            for row in route_rows
        ],
        caption="Canonical Decision-route episode coverage",
        compact=True,
    )
    origin_table = data_table(
        (
            "Primary origin",
            "Coverage",
            "Episodes",
            "Matured",
            "Not due",
            "Missing price",
            "Scoreable",
            "Aligned",
        ),
        [
            (
                humanize_enum(row.get("name")),
                badge(
                    "Observed"
                    if row.get("coverage_status") == "observed"
                    else "No episode",
                    tone=(
                        "info"
                        if row.get("coverage_status") == "observed"
                        else "muted"
                    ),
                ),
                display_count(row.get("episode_count")),
                display_count(row.get("matured_episode_count")),
                display_count(row.get("not_due_episode_count")),
                display_count(row.get("due_missing_price_episode_count")),
                display_count(row.get("scoreable_directional_episode_count")),
                display_count(row.get("aligned_episode_count")),
            )
            for row in origin_rows
        ],
        caption="Canonical primary-origin episode coverage",
        compact=True,
    )
    observed_routes = display_count(raw.get("observed_route_count"))
    route_total = display_count(raw.get("route_population_count"))
    observed_origins = display_count(raw.get("observed_primary_origin_count"))
    origin_total = display_count(raw.get("primary_origin_population_count"))
    summary = (
        '<div class="alert alert-info"><strong>Descriptive evidence frontier.</strong> '
        f'Frozen episodes cover {escape_html(observed_routes)}/{escape_html(route_total)} '
        f'routes and {escape_html(observed_origins)}/{escape_html(origin_total)} primary '
        'origins. Zero rows are missing evidence, not healthy-empty proof. Minimum samples, '
        'statistical independence, matched controls, and Protocol-v2 eligibility remain '
        'unsealed.</div>'
    )
    body = (
        summary
        + '<div class="campaign-desktop-table">'
        + str(route_table)
        + '</div>'
        + str(disclosure(
            "Primary-origin coverage",
            origin_table,
            summary=(
                f"{observed_origins}/{origin_total} primary origins observed"
            ),
            css_class="campaign-technical-disclosure",
        ))
    )
    return render_panel(
        "Protocol-v2 episode coverage",
        body,
        eyebrow="Frozen Decision episodes · no policy conclusion",
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
        ("Authorization at generation", _boolean_badge(authorized)),
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
            _maintenance_operations_summary(item),
            _maintenance_current_authority(snapshot, item),
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
                "Attempt status",
                "Provider request",
                "Publication",
                "Operations",
                "Current authority",
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
    if item.get("pointer_published") is True:
        return badge("Published", tone="positive")
    return badge("Not published", tone="muted")


def _maintenance_operations_summary(item: Mapping[str, Any]) -> HtmlFragment:
    if item.get("dashboard_restarted") is True:
        return badge("Dashboard restarted", tone="positive")
    if item.get("pointer_published") is True:
        return badge("Restart not completed", tone="danger")
    return badge("Not applicable", tone="muted")


def _maintenance_current_authority(
    snapshot: DashboardSnapshot,
    item: Mapping[str, Any],
) -> HtmlFragment:
    current = bool(
        snapshot.generation_authoritative
        and item.get("artifact_namespace") == snapshot.artifact_namespace
        and item.get("pointer_published") is True
    )
    return badge(
        "Current exact authority" if current else "Historical / not current",
        tone="positive" if current else "muted",
    )


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
