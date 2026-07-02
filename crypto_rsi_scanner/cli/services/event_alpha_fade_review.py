"""Event Alpha Fade Review.

Behavior-preserving split from ``crypto_rsi_scanner.cli.services.event_alpha``.
Functions bind scanner globals at runtime so historical helper/config lookups
remain compatible during the refactor.
"""

from __future__ import annotations

from types import ModuleType
from typing import MutableMapping


_SERVICE_FUNCTION_NAMES = ('bind_scanner_globals', '_write_event_fade_review_bundle', '_event_fade_review_bundle_manifest', '_event_fade_review_bundle_readme', '_event_fade_review_guide')


def bind_scanner_globals(target: MutableMapping[str, object], scanner_module: ModuleType | None = None) -> ModuleType:
    if scanner_module is None:
        from ... import scanner as scanner_module
    for name, value in vars(scanner_module).items():
        if not name.startswith("__") and name not in _SERVICE_FUNCTION_NAMES:
            target[name] = value
    return scanner_module

def _write_event_fade_review_bundle(
    *,
    source_rows: list[dict[str, Any]],
    sample_path: str,
    out_dir: str,
    limit: int | None,
    prices_path: str | None,
    auto_export_prices: bool,
    price_days: int | None,
    price_fixture_dir: str | None,
    price_interval: str,
    refresh_price_cache: bool,
    reviewed_path: str | None,
    review_merge: event_validation.ValidationSampleMergeResult | None,
    overwrite_outcomes: bool,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    bind_scanner_globals(globals())
    bundle_dir = Path(out_dir).expanduser()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    copied_sample = event_discovery.write_validation_sample(
        source_rows,
        bundle_dir / "validation_sample.jsonl",
    )
    review_rows = source_rows
    effective_prices_path = prices_path
    price_export_result: event_price_history.EventFadeOutcomePriceExportResult | None = None
    if auto_export_prices and not effective_prices_path:
        price_export_result = event_price_history.export_outcome_price_fixture(
            source_rows,
            bundle_dir / "outcome_prices.json",
            days=price_days,
            fixture_dir=price_fixture_dir,
            cache_dir=config.BACKTEST_CACHE_DIR,
            refresh_cache=refresh_price_cache,
            interval=price_interval,
        )
        effective_prices_path = str(price_export_result.out_path)

    fill_summary = "No price fixture supplied; outcome fields were not filled."
    fill_result: event_validation.ValidationOutcomeFillResult | None = None
    outcome_sample: Path | None = None
    if effective_prices_path:
        prices = event_validation.load_outcome_price_fixture(effective_prices_path)
        fill_result = event_validation.fill_validation_outcomes(
            source_rows,
            prices,
            overwrite=overwrite_outcomes,
        )
        review_rows = fill_result.rows
        outcome_sample = event_discovery.write_validation_sample(
            review_rows,
            bundle_dir / "validation_sample_with_outcomes.jsonl",
        )
        fill_summary = (
            f"Filled {fill_result.filled_rows}/{fill_result.triggered_rows} triggered row(s); "
            f"missing_history={fill_result.missing_history_rows}, "
            f"insufficient_history={fill_result.insufficient_history_rows}, "
            f"skipped_existing={fill_result.skipped_existing_rows}."
        )

    queue = event_validation.build_labeling_queue(review_rows, limit=limit)
    review = event_validation.review_validation_sample(review_rows)
    sample_summary = _event_fade_review_sample_summary(review_rows)
    template_rows = event_validation.build_review_template_rows(review_rows, limit=limit)
    balanced_template_rows = event_validation.build_balanced_review_template_rows(review_rows)
    bundle_warnings = tuple([_empty_review_bundle_message(sample_path)] if not review_rows else [])

    queue_path = bundle_dir / "labeling_queue.txt"
    packet_path = bundle_dir / "review_packet.md"
    balanced_packet_path = bundle_dir / "review_packet_balanced.md"
    template_path = bundle_dir / "review_template.csv"
    balanced_template_path = bundle_dir / "review_template_balanced.csv"
    report_path = bundle_dir / "review_report.txt"
    guide_path = bundle_dir / "review_guide.md"
    manifest_path = bundle_dir / "manifest.json"
    readme_path = bundle_dir / "README.md"

    queue_path.write_text(event_validation.format_labeling_queue(queue) + "\n", encoding="utf-8")
    packet_path.write_text(event_validation.format_review_packet(review_rows, limit=limit) + "\n", encoding="utf-8")
    balanced_packet_path.write_text(
        event_validation.format_balanced_review_packet(review_rows) + "\n",
        encoding="utf-8",
    )
    template_path.write_text(event_validation.format_review_template_csv(template_rows), encoding="utf-8")
    balanced_template_path.write_text(
        event_validation.format_review_template_csv(balanced_template_rows),
        encoding="utf-8",
    )
    report_path.write_text(event_validation.format_validation_review(review) + "\n", encoding="utf-8")
    guide_path.write_text(_event_fade_review_guide(), encoding="utf-8")
    manifest = _event_fade_review_bundle_manifest(
        sample_path=sample_path,
        prices_path=prices_path,
        overwrite_outcomes=overwrite_outcomes,
        copied_sample=copied_sample,
        price_export=price_export_result,
        outcome_sample=outcome_sample,
        queue_path=queue_path,
        packet_path=packet_path,
        balanced_packet_path=balanced_packet_path,
        template_path=template_path,
        balanced_template_path=balanced_template_path,
        balanced_template_rows=len(balanced_template_rows),
        report_path=report_path,
        guide_path=guide_path,
        readme_path=readme_path,
        source_rows=len(source_rows),
        review_rows=len(review_rows),
        queue=queue,
        review=review,
        sample_summary=sample_summary,
        limit=limit,
        fill_summary=fill_summary,
        fill_result=fill_result,
        effective_prices_path=effective_prices_path,
        auto_export_prices=auto_export_prices,
        price_days=price_days,
        price_fixture_dir=price_fixture_dir,
        price_interval=price_interval,
        refresh_price_cache=refresh_price_cache,
        reviewed_path=reviewed_path,
        review_merge=review_merge,
        warnings=bundle_warnings,
        generated_at=generated_at,
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    readme_path.write_text(
        _event_fade_review_bundle_readme(
            sample_path=sample_path,
            copied_sample=copied_sample,
            price_export=price_export_result,
            outcome_sample=outcome_sample,
            queue_path=queue_path,
            packet_path=packet_path,
            balanced_packet_path=balanced_packet_path,
            template_path=template_path,
            balanced_template_path=balanced_template_path,
            report_path=report_path,
            guide_path=guide_path,
            manifest_path=manifest_path,
            rows=len(review_rows),
            queue=queue,
            review=review,
            sample_summary=sample_summary,
            fill_summary=fill_summary,
            auto_export_prices=auto_export_prices,
            reviewed_path=reviewed_path,
            review_merge=review_merge,
            warnings=bundle_warnings,
        ),
        encoding="utf-8",
    )
    return {
        "bundle_dir": bundle_dir,
        "price_export": price_export_result,
        "outcome_sample": outcome_sample,
        "queue": queue,
        "rows": len(review_rows),
    }


def _event_fade_review_bundle_manifest(
    *,
    sample_path: str,
    prices_path: str | None,
    overwrite_outcomes: bool,
    copied_sample: Path,
    price_export: event_price_history.EventFadeOutcomePriceExportResult | None,
    outcome_sample: Path | None,
    queue_path: Path,
    packet_path: Path,
    balanced_packet_path: Path,
    template_path: Path,
    balanced_template_path: Path,
    balanced_template_rows: int,
    report_path: Path,
    guide_path: Path,
    readme_path: Path,
    source_rows: int,
    review_rows: int,
    queue: event_validation.ValidationLabelingQueue,
    review: event_validation.EventFadeValidationReview,
    sample_summary: dict[str, Any],
    limit: int | None,
    fill_summary: str,
    fill_result: event_validation.ValidationOutcomeFillResult | None,
    effective_prices_path: str | None,
    auto_export_prices: bool,
    price_days: int | None,
    price_fixture_dir: str | None,
    price_interval: str,
    refresh_price_cache: bool,
    reviewed_path: str | None,
    review_merge: event_validation.ValidationSampleMergeResult | None,
    warnings: tuple[str, ...] = (),
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    bind_scanner_globals(globals())
    files = {
        "readme": readme_path.name,
        "validation_sample": copied_sample.name,
        "labeling_queue": queue_path.name,
        "review_packet": packet_path.name,
        "review_packet_balanced": balanced_packet_path.name,
        "review_template": template_path.name,
        "review_template_balanced": balanced_template_path.name,
        "review_report": report_path.name,
        "review_guide": guide_path.name,
    }
    if price_export is not None:
        files["outcome_prices"] = price_export.out_path.name
    if outcome_sample is not None:
        files["validation_sample_with_outcomes"] = outcome_sample.name
    outcome_fill: dict[str, Any] = {
        "enabled": effective_prices_path is not None,
        "prices_path": effective_prices_path,
        "overwrite_outcomes": overwrite_outcomes,
        "summary": fill_summary,
    }
    if fill_result is not None:
        outcome_fill.update({
            "sample_rows": fill_result.sample_rows,
            "triggered_rows": fill_result.triggered_rows,
            "filled_rows": fill_result.filled_rows,
            "missing_history_rows": fill_result.missing_history_rows,
            "insufficient_history_rows": fill_result.insufficient_history_rows,
            "skipped_existing_rows": fill_result.skipped_existing_rows,
        })

    return {
        "bundle_version": 1,
        "generated_at": (generated_at or datetime.now(timezone.utc)).isoformat(),
        "source": {
            "sample_path": sample_path,
            "source_rows": source_rows,
            "review_rows": review_rows,
        },
        "warnings": list(warnings),
        "sample_summary": sample_summary,
        "files": files,
        "queue": {
            "limit": limit,
            "needed_rows": queue.needed_rows,
            "shown_rows": queue.shown_rows,
            "total_rows": queue.total_rows,
        },
        "balanced_review_template": {
            "rows": balanced_template_rows,
            "proxy_limit": event_validation.DEFAULT_BALANCED_PROXY_REVIEW_ROWS,
            "control_limit": event_validation.DEFAULT_BALANCED_CONTROL_REVIEW_ROWS,
        },
        "review": {
            "promotion_ready": review.promotion_ready,
            "promotion_blockers": list(review.promotion_blockers),
            "reviewed_rows": review.reviewed_rows,
            "reviewed_proxy_candidates": review.reviewed_proxy_candidates,
            "reviewed_negative_controls": review.reviewed_negative_controls,
            "reviewed_proxy_event_types": review.reviewed_proxy_event_types,
            "min_proxy_event_types": review.min_proxy_event_types,
            "reviewed_proxy_source_providers": review.reviewed_proxy_source_providers,
            "min_proxy_source_providers": review.min_proxy_source_providers,
            "reviewed_proxy_source_origins": review.reviewed_proxy_source_origins,
            "triggered_reviewed": review.triggered_reviewed,
            "triggered_btc_risk_buckets": review.triggered_btc_risk_buckets,
            "min_trigger_btc_risk_buckets": review.min_trigger_btc_risk_buckets,
            "low_confidence_trigger_event_time_rows": review.low_confidence_trigger_event_time_rows,
            "missing_trigger_outcome_rows": review.missing_trigger_outcome_rows,
            "missing_event_time_baseline_rows": review.missing_event_time_baseline_rows,
            "missing_review_provenance_rows": review.missing_review_provenance_rows,
            "point_in_time_violation_rows": review.point_in_time_violation_rows,
            "post_decision_source_rows": review.post_decision_source_rows,
            "missing_source_timing_rows": review.missing_source_timing_rows,
            "next_sample_work": list(event_validation.validation_review_next_steps(review)),
        },
        "price_export": _event_fade_review_price_export_manifest(
            auto_export_prices=auto_export_prices,
            explicit_prices_path=prices_path,
            price_days=price_days,
            price_fixture_dir=price_fixture_dir,
            price_interval=price_interval,
            refresh_price_cache=refresh_price_cache,
            result=price_export,
        ),
        "outcome_fill": outcome_fill,
        "review_merge": _event_fade_review_merge_manifest(reviewed_path, review_merge),
    }


def _event_fade_review_bundle_readme(
    *,
    sample_path: str,
    copied_sample: Path,
    price_export: event_price_history.EventFadeOutcomePriceExportResult | None,
    outcome_sample: Path | None,
    queue_path: Path,
    packet_path: Path,
    balanced_packet_path: Path,
    template_path: Path,
    balanced_template_path: Path,
    report_path: Path,
    guide_path: Path,
    manifest_path: Path,
    rows: int,
    queue: event_validation.ValidationLabelingQueue,
    review: event_validation.EventFadeValidationReview,
    sample_summary: dict[str, Any],
    fill_summary: str,
    auto_export_prices: bool,
    reviewed_path: str | None,
    review_merge: event_validation.ValidationSampleMergeResult | None,
    warnings: tuple[str, ...] = (),
) -> str:
    bind_scanner_globals(globals())
    price_line = (
        f"- `{price_export.out_path.name}`: bundle-local OHLCV price fixture"
        if price_export is not None
        else "- No bundle-local price fixture was exported."
    )
    outcome_line = (
        f"- `{outcome_sample.name}`: sample with locally filled trigger/baseline outcomes"
        if outcome_sample is not None
        else "- No outcome-filled sample was written."
    )
    if review_merge is None:
        merge_line = "- No prior reviewed sample was merged."
    else:
        merge_line = (
            f"- Prior reviewed sample `{reviewed_path}` merged: "
            f"{review_merge.matched_rows} matched, "
            f"{review_merge.evidence_changed_rows} evidence-changed, "
            f"{review_merge.copied_fields} copied field(s)."
        )
    warning_lines = ["Warnings:", *(f"- {warning}" for warning in warnings), ""] if warnings else []
    return "\n".join([
        "# Event-Fade Validation Review Bundle",
        "",
        "Research-only: no alerts, live DB writes, paper trades, or orders.",
        "",
        f"Input sample: `{sample_path}`",
        f"Rows: {rows}",
        f"Rows needing labels/status/outcomes: {queue.needed_rows}",
        f"Rows shown in queue/template/packet: {queue.shown_rows}",
        "",
        "Sample summary:",
        *_event_fade_review_bundle_summary_lines(sample_summary),
        "",
        "Review gates:",
        *_event_fade_review_gate_lines(review),
        *warning_lines,
        f"Auto price export: {'yes' if auto_export_prices else 'no'}",
        f"Outcome fill: {fill_summary}",
        "Review merge:",
        merge_line,
        "",
        "Files:",
        f"- `{copied_sample.name}`: copied source validation sample",
        price_line,
        outcome_line,
        f"- `{queue_path.name}`: prioritized queue for missing labels/status/outcomes",
        f"- `{packet_path.name}`: human-readable evidence packet",
        f"- `{balanced_packet_path.name}`: human-readable evidence packet matching the balanced sidecar",
        f"- `{template_path.name}`: compact editable CSV sidecar",
        f"- `{balanced_template_path.name}`: gate-balanced editable CSV sidecar with proxy candidates and negative controls",
        f"- `{guide_path.name}`: label taxonomy, review provenance, and event-time review rules",
        f"- `{report_path.name}`: current review metrics and promotion blockers",
        f"- `{manifest_path.name}`: machine-readable bundle provenance and counts",
        "",
        "Suggested workflow:",
        "1. Read `review_guide.md` for label and timing rules.",
        "2. Read `review_packet_balanced.md` for evidence matching `review_template_balanced.csv`; use `review_packet.md` for strict priority rows.",
        "3. For fastest promotion-gate coverage, edit `review_template_balanced.csv`; for strict priority order, edit `review_template.csv`.",
        "4. Fill `review_status`, `reviewed_by`, `reviewed_at`, `human_label`, `human_notes`, any human event-time confirmation, and any missing outcomes. Use `external_asset`, `primary_source_url`, `source_search_url`, `source_date_hint`, `source_providers`, `primary_raw_title`, `review_prompt`, and `event_time_review_hint` as reviewer aids only.",
        "5. Dry-check the edited sidecar with `main.py --event-fade-check-review-template SAMPLE TEMPLATE`.",
        "6. Apply the checked sidecar with `main.py --event-fade-apply-review-template SAMPLE TEMPLATE OUT`.",
        "7. Run `main.py --event-fade-review-sample OUT` to inspect coverage and blockers.",
        "",
    ])


def _event_fade_review_guide() -> str:
    bind_scanner_globals(globals())
    return "\n".join([
        "# Event-Fade Review Guide",
        "",
        "Research-only: this guide is for labeling validation artifacts. It does not promote alerts, paper trades, or execution.",
        "",
        "## Label Rules",
        "",
        "Use exactly one `human_label` value per reviewed row:",
        "",
        "- `valid_proxy_fade`: the crypto asset is a true proxy instrument for a dated external catalyst, not the direct beneficiary, and the evidence would have been knowable before the decision time.",
        "- `false_positive`: the row looked proxy-like to the system but manual review says it is not a valid proxy-fade setup.",
        "- `direct_event`: the catalyst directly changes the asset's own listing, supply, emissions, protocol, utility, or structural demand.",
        "- `ambiguous`: the evidence is too weak, ticker-only, generic market chatter, or cannot be resolved to a clear proxy/direct relationship.",
        "",
        "Set `review_status=reviewed` only after checking the source evidence. Rows with labels but without `review_status=reviewed` do not count as reviewed evidence.",
        "",
        "Fill `reviewed_by` with the reviewer name or handle and `reviewed_at` with an ISO timestamp. These fields make copied labels auditable across refreshed samples, and missing provenance blocks promotion.",
        "",
        "## Proxy Criteria",
        "",
        "A valid proxy-fade candidate should have all of these:",
        "",
        "- a dated external catalyst or expiry",
        "- a crypto asset used as synthetic exposure, attention exposure, fan exposure, or prediction-market-style proxy",
        "- `is_direct_beneficiary=false`",
        "- source evidence available before the decision time",
        "",
        "Examples that should usually be `direct_event`: BTC/BTC ETF, ETH/ETH ETF, token unlocks, exchange listings, airdrops, TGEs, mainnet launches, and protocol upgrades.",
        "",
        "## Event-Time Confirmation",
        "",
        "If the machine `event_time` is blank, weak, or inferred from text, fill the separate human fields instead of editing `event_time`:",
        "",
        "- `human_event_time`: ISO timestamp for the catalyst, preferably UTC with an offset, for example `2026-06-20T13:30:00+00:00`",
        "- `human_event_time_source`: URL or title proving that timestamp",
        "- `human_event_time_confidence`: reviewer confidence from `0.0` to `1.0`; use `0.80` or higher only for explicit source evidence",
        "- `human_event_time_notes`: short note explaining how the timestamp was confirmed",
        "",
        "Validation metrics may use high-confidence `human_event_time` for review-only timing checks and event-time baselines, but it remains separate from the machine-discovered `event_time`.",
        "",
        "## Review Template Helper Columns",
        "",
        "`review_template.csv` and `review_template_balanced.csv` include reviewer-only helper columns:",
        "",
        "- `external_asset`: machine-extracted external catalyst identity; verify it against the source before using `valid_proxy_fade`",
        "- `primary_source_url`: first source URL to open for the row",
        "- `primary_source_origin`: first normalized publisher/origin",
        "- `primary_raw_title`: first raw source title",
        "- `source_search_url`: title/publisher search link for finding the canonical article when the primary source is a feed or Google News wrapper",
        "- `source_date_hint`: date-like phrases found in the source title or event name, such as a date range, event year, `today`, or `tonight`; use it only as a cue to verify explicit source timing",
        "- `source_providers`: discovery provider(s) that supplied the row, such as `project_blog_rss`, `gdelt`, or `prediction_market_events`",
        "- `review_prompt`: compact instruction for the queued review category",
        "- `event_time_review_hint`: whether the event time is missing, inferred/weak, or explicit/high-confidence",
        "",
        "These helper columns are not copied back into validation samples and do not affect evidence matching. The fields that count are still `review_status`, `reviewed_by`, `reviewed_at`, `human_label`, `human_notes`, `human_event_time*`, and required outcome fields.",
        "",
        "`review_template.csv` follows strict labeling-queue priority. `review_template_balanced.csv` is better for building the validation sample because it includes triggered rows, proxy candidates, and direct/ambiguous negative controls in one sidecar.",
        "Run `main.py --event-fade-check-review-template SAMPLE TEMPLATE` before applying an edited sidecar; it catches changed evidence, unmatched rows, missing provenance, unknown labels, missing outcomes, and valid proxy labels without explicit catalyst timing.",
        "",
        "## Outcome Fields",
        "",
        "For reviewed `SHORT_TRIGGERED` rows, fill or verify:",
        "",
        "- `max_adverse_excursion`",
        "- `max_favorable_excursion`",
        "- `post_event_return_72h`",
        "- `event_time_post_event_return_72h`",
        "",
        "Prefer locally filled 1h outcomes when available; daily outcomes are coarse and can hide intraday squeeze risk.",
        "",
        "## Promotion Reminder",
        "",
        "Do not promote event fade beyond local reports until the review report clears the proxy/control/trigger sample-size, source-diversity, timing, and outcome-quality gates.",
        "",
    ])


__all__ = tuple(name for name in _SERVICE_FUNCTION_NAMES if name != 'bind_scanner_globals')
