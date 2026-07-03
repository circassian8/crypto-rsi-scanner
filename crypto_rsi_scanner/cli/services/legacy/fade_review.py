"""Fade Review commands from the legacy scanner service."""

from __future__ import annotations

from .runtime import *

def event_fade_auto_report(verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Print grouped research-only event-fade candidates from discovery fixtures."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    print(event_discovery.format_event_fade_auto_report(result))

def event_fade_export_sample(path: str, verbose: bool = False, event_now: str | datetime | None = None) -> None:
    """Export discovery-fed event-fade validation sample rows."""
    _setup_event_discovery_logging(verbose)
    if not _event_discovery_paths_configured():
        print(
            "No event-discovery sources ready. Set RSI_EVENT_DISCOVERY_EVENTS_PATH, "
            "another event-discovery fixture path, or opt into a live research provider. "
            "Run --event-discovery-status for a redacted readiness report."
        )
        return
    now = _event_research_now(event_now)
    result = _event_discovery_result_from_config(now=now)
    rows = event_discovery.event_fade_validation_sample_rows(result, exported_at=now)
    if path == "-":
        print(event_discovery.format_validation_sample_jsonl(rows))
        return
    out = event_discovery.write_validation_sample(rows, path)
    print(f"Event-fade validation sample: wrote {len(rows)} row(s) to {out}")

def event_fade_export_cache_sample(
    path: str,
    verbose: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Export latest cached event-discovery snapshots as validation sample rows."""
    _setup_event_discovery_logging(verbose)
    _event_research_now(event_now)
    read = event_cache.load_cached_validation_sample(config.EVENT_DISCOVERY_CACHE_DIR)
    if path == "-":
        print(event_discovery.format_validation_sample_jsonl(read.rows))
        return
    out = event_discovery.write_validation_sample(read.rows, path)
    print(
        "Event-fade cached validation sample: "
        f"read {read.snapshots_read} snapshot(s), "
        f"exported {len(read.rows)} latest row(s) to {out}"
    )

def event_fade_review_sample(path: str, verbose: bool = False) -> None:
    """Review status/labels/outcomes and next sample work for an event-fade validation export."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(path)
    review = event_validation.review_validation_sample(rows)
    print(event_validation.format_validation_review(review))

def event_fade_labeling_queue(path: str, limit: int | None = 20, verbose: bool = False) -> None:
    """Print prioritized rows that still need event-fade validation review."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(path)
    queue = event_validation.build_labeling_queue(rows, limit=limit)
    print(event_validation.format_labeling_queue(queue))

def event_fade_review_packet(
    sample_path: str,
    out_path: str,
    *,
    limit: int | None = 20,
    verbose: bool = False,
) -> None:
    """Write a Markdown packet for manual event-fade validation review."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(sample_path)
    queue = event_validation.build_labeling_queue(rows, limit=limit)
    packet = event_validation.format_review_packet(rows, limit=limit)
    if out_path == "-":
        print(packet)
        return
    out = Path(out_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(packet + "\n", encoding="utf-8")
    print(
        "Event-fade review packet: "
        f"wrote {queue.shown_rows}/{queue.needed_rows} row(s) needing review to {out}"
    )

def event_fade_export_review_template(
    sample_path: str,
    out_path: str,
    *,
    limit: int | None = 20,
    verbose: bool = False,
) -> None:
    """Export compact editable sidecar rows for event-fade validation review."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(sample_path)
    queue = event_validation.build_labeling_queue(rows, limit=limit)
    if out_path == "-":
        template_rows = event_validation.build_review_template_rows(rows, limit=limit)
        print(event_validation.format_review_template_jsonl(template_rows))
        return
    out = event_validation.write_review_template(rows, out_path, limit=limit)
    print(
        "Event-fade review template: "
        f"wrote {queue.shown_rows}/{queue.needed_rows} row(s) needing review to {out}"
    )

def event_fade_apply_review_template(
    sample_path: str,
    template_path: str,
    out_path: str,
    *,
    verbose: bool = False,
) -> None:
    """Apply edited compact review sidecar rows to a validation sample artifact."""
    _setup_event_discovery_logging(verbose)
    sample_rows = event_validation.load_validation_sample(sample_path)
    template_rows = event_validation.load_validation_sample(template_path)
    result = event_validation.apply_review_template(sample_rows, template_rows)
    out = event_discovery.write_validation_sample(result.rows, out_path)
    review = event_validation.review_validation_sample(result.rows)
    print(
        "Event-fade review template apply: "
        f"{result.matched_rows} matched row(s), "
        f"{result.evidence_changed_rows} evidence-changed row(s), "
        f"{result.unmatched_reviewed_rows} unmatched reviewed row(s), "
        f"{result.copied_fields} copied field(s), wrote {len(result.rows)} row(s) to {out}"
    )
    evidence_changes = event_validation.format_merge_evidence_changes(result)
    if evidence_changes:
        print(evidence_changes)
    print("")
    print(event_validation.format_validation_review(review))

def event_fade_check_review_template(
    sample_path: str,
    template_path: str,
    *,
    verbose: bool = False,
) -> None:
    """Dry-check an edited compact review sidecar before applying it."""
    _setup_event_discovery_logging(verbose)
    sample_rows = event_validation.load_validation_sample(sample_path)
    template_rows = event_validation.load_validation_sample(template_path)
    check = event_validation.check_review_template(sample_rows, template_rows)
    print(event_validation.format_review_template_check(check))
    if not check.ready_to_apply:
        raise SystemExit(1)

def event_fade_review_bundle(
    sample_path: str,
    out_dir: str,
    *,
    limit: int | None = 20,
    prices_path: str | None = None,
    auto_export_prices: bool = False,
    price_days: int | None = None,
    price_fixture_dir: str | None = None,
    price_interval: str = "1d",
    refresh_price_cache: bool = False,
    reviewed_path: str | None = None,
    overwrite_outcomes: bool = False,
    verbose: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Write a local event-fade validation review workspace."""
    _setup_event_discovery_logging(verbose)
    source_rows = event_validation.load_validation_sample(sample_path)
    bundle_rows, review_merge = _merge_review_rows_for_bundle(source_rows, reviewed_path)
    generated_at = _event_research_now(event_now)
    result = _write_event_fade_review_bundle(
        source_rows=bundle_rows,
        sample_path=sample_path,
        out_dir=out_dir,
        limit=limit,
        prices_path=prices_path,
        auto_export_prices=auto_export_prices,
        price_days=price_days,
        price_fixture_dir=price_fixture_dir,
        price_interval=price_interval,
        refresh_price_cache=refresh_price_cache,
        reviewed_path=reviewed_path,
        review_merge=review_merge,
        overwrite_outcomes=overwrite_outcomes,
        generated_at=generated_at,
    )
    print(
        "Event-fade review bundle: "
        f"rows={result['rows']}, "
        f"needing_review={result['queue'].needed_rows}, "
        f"showing={result['queue'].shown_rows}, "
        f"dir={result['bundle_dir']}"
    )
    if result["rows"] == 0:
        print(_empty_review_bundle_message(sample_path))
    _print_review_merge_summary(review_merge)
    if result["price_export"] is not None:
        price_export = result["price_export"]
        print(
            "Outcome price fixture: "
            f"assets={price_export.assets_written}/{price_export.assets_requested}, "
            f"price_rows={price_export.price_rows_written}, "
            f"interval={price_export.interval}, source={price_export.source}, wrote {price_export.out_path}"
        )
    if result["outcome_sample"] is not None:
        print(f"Outcome-filled sample: {result['outcome_sample']}")

def event_fade_cache_review_bundle(
    out_dir: str,
    *,
    limit: int | None = 20,
    prices_path: str | None = None,
    auto_export_prices: bool = False,
    price_days: int | None = None,
    price_fixture_dir: str | None = None,
    price_interval: str = "1d",
    refresh_price_cache: bool = False,
    reviewed_path: str | None = None,
    overwrite_outcomes: bool = False,
    verbose: bool = False,
    event_now: str | datetime | None = None,
) -> None:
    """Write a local review workspace from latest cached event-discovery snapshots."""
    _setup_event_discovery_logging(verbose)
    read = event_cache.load_cached_validation_sample(config.EVENT_DISCOVERY_CACHE_DIR)
    bundle_rows, review_merge = _merge_review_rows_for_bundle(read.rows, reviewed_path)
    generated_at = _event_research_now(event_now)
    result = _write_event_fade_review_bundle(
        source_rows=bundle_rows,
        sample_path=f"cache:{read.cache_dir}",
        out_dir=out_dir,
        limit=limit,
        prices_path=prices_path,
        auto_export_prices=auto_export_prices,
        price_days=price_days,
        price_fixture_dir=price_fixture_dir,
        price_interval=price_interval,
        refresh_price_cache=refresh_price_cache,
        reviewed_path=reviewed_path,
        review_merge=review_merge,
        overwrite_outcomes=overwrite_outcomes,
        generated_at=generated_at,
    )
    print(
        "Event-fade cached review bundle: "
        f"snapshots_read={read.snapshots_read}, "
        f"rows={result['rows']}, "
        f"needing_review={result['queue'].needed_rows}, "
        f"showing={result['queue'].shown_rows}, "
        f"dir={result['bundle_dir']}"
    )
    if result["rows"] == 0:
        print(_empty_review_bundle_message(f"cache:{read.cache_dir}"))
    _print_review_merge_summary(review_merge)
    if result["price_export"] is not None:
        price_export = result["price_export"]
        print(
            "Outcome price fixture: "
            f"assets={price_export.assets_written}/{price_export.assets_requested}, "
            f"price_rows={price_export.price_rows_written}, "
            f"interval={price_export.interval}, source={price_export.source}, wrote {price_export.out_path}"
        )
    if result["outcome_sample"] is not None:
        print(f"Outcome-filled sample: {result['outcome_sample']}")

def _merge_review_rows_for_bundle(
    source_rows: list[dict[str, Any]],
    reviewed_path: str | None,
) -> tuple[list[dict[str, Any]], event_validation.ValidationSampleMergeResult | None]:
    if not reviewed_path:
        return source_rows, None
    reviewed_rows = event_validation.load_validation_sample(reviewed_path)
    result = event_validation.merge_review_fields(source_rows, reviewed_rows)
    return result.rows, result

def _print_review_merge_summary(
    review_merge: event_validation.ValidationSampleMergeResult | None,
) -> None:
    if review_merge is None:
        return
    print(
        "Review merge: "
        f"{review_merge.matched_rows} matched row(s), "
        f"{review_merge.evidence_changed_rows} evidence-changed row(s), "
        f"{review_merge.unmatched_reviewed_rows} unmatched reviewed row(s), "
        f"{review_merge.copied_fields} copied field(s)"
    )
    evidence_changes = event_validation.format_merge_evidence_changes(review_merge)
    if evidence_changes:
        print(evidence_changes)

def _empty_review_bundle_message(sample_path: str) -> str:
    return (
        "No validation rows were available for this review bundle. "
        f"Source={sample_path}. Run `main.py --event-discovery-status`, check live provider "
        "warnings/rate limits, then refresh event-discovery cache with at least one working event source."
    )

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
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service._write_event_fade_review_bundle(source_rows=source_rows, sample_path=sample_path, out_dir=out_dir, limit=limit, prices_path=prices_path, auto_export_prices=auto_export_prices, price_days=price_days, price_fixture_dir=price_fixture_dir, price_interval=price_interval, refresh_price_cache=refresh_price_cache, reviewed_path=reviewed_path, review_merge=review_merge, overwrite_outcomes=overwrite_outcomes, generated_at=generated_at)

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
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service._event_fade_review_bundle_manifest(sample_path=sample_path, prices_path=prices_path, overwrite_outcomes=overwrite_outcomes, copied_sample=copied_sample, price_export=price_export, outcome_sample=outcome_sample, queue_path=queue_path, packet_path=packet_path, balanced_packet_path=balanced_packet_path, template_path=template_path, balanced_template_path=balanced_template_path, balanced_template_rows=balanced_template_rows, report_path=report_path, guide_path=guide_path, readme_path=readme_path, source_rows=source_rows, review_rows=review_rows, queue=queue, review=review, sample_summary=sample_summary, limit=limit, fill_summary=fill_summary, fill_result=fill_result, effective_prices_path=effective_prices_path, auto_export_prices=auto_export_prices, price_days=price_days, price_fixture_dir=price_fixture_dir, price_interval=price_interval, refresh_price_cache=refresh_price_cache, reviewed_path=reviewed_path, review_merge=review_merge, warnings=warnings, generated_at=generated_at)

def _event_fade_review_price_export_manifest(
    *,
    auto_export_prices: bool,
    explicit_prices_path: str | None,
    price_days: int | None,
    price_fixture_dir: str | None,
    price_interval: str,
    refresh_price_cache: bool,
    result: event_price_history.EventFadeOutcomePriceExportResult | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "enabled": auto_export_prices,
        "exported": result is not None,
        "explicit_prices_path": explicit_prices_path,
        "requested_days": price_days,
        "requested_interval": price_interval,
        "fixture_dir": price_fixture_dir,
        "refresh_cache": refresh_price_cache,
    }
    if result is not None:
        payload.update({
            "out_path": str(result.out_path),
            "assets_requested": result.assets_requested,
            "assets_written": result.assets_written,
            "price_rows_written": result.price_rows_written,
            "missing_assets": list(result.missing_assets),
            "days": result.days,
            "interval": result.interval,
            "source": result.source,
        })
    return payload

def _event_fade_review_merge_manifest(
    reviewed_path: str | None,
    review_merge: event_validation.ValidationSampleMergeResult | None,
) -> dict[str, Any]:
    if review_merge is None:
        return {
            "enabled": False,
            "reviewed_path": reviewed_path,
        }
    return {
        "enabled": True,
        "reviewed_path": reviewed_path,
        "fresh_rows": review_merge.fresh_rows,
        "reviewed_rows": review_merge.reviewed_rows,
        "matched_rows": review_merge.matched_rows,
        "evidence_changed_rows": review_merge.evidence_changed_rows,
        "unmatched_reviewed_rows": review_merge.unmatched_reviewed_rows,
        "copied_fields": review_merge.copied_fields,
        "evidence_changes": [
            {
                "event_id": item.event_id,
                "asset_symbol": item.asset_symbol,
                "asset_coin_id": item.asset_coin_id,
                "relationship_type": item.relationship_type,
                "changed_fields": list(item.changed_fields),
            }
            for item in review_merge.evidence_changes
        ],
    }

def _event_fade_review_sample_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build compact sample-quality counts for review bundle manifests/READMEs."""
    source_provider_summary = _event_fade_review_source_provider_summary(rows)
    source_origin_summary = _event_fade_review_source_origin_summary(rows)
    return {
        "rows": len(rows),
        "review_status": _count_values(row.get("review_status") or "missing" for row in rows),
        "human_labels": _count_values(row.get("human_label") or "unlabeled" for row in rows),
        "event_types": _count_values(row.get("event_type") or "unknown" for row in rows),
        "relationship_types": _count_values(row.get("relationship_type") or "unknown" for row in rows),
        "asset_roles": _count_values(row.get("asset_role") or "unknown" for row in rows),
        "signal_types": _count_values(row.get("signal_type") or "NO_TRADE" for row in rows),
        "source_providers": _count_values(
            provider
            for row in rows
            for provider in _bundle_list_values(row.get("raw_providers"))
        ),
        "source_origins": _count_values(
            origin
            for row in rows
            for origin in event_validation.source_origin_values(row)
        ),
        "proxy_candidates": sum(1 for row in rows if _bundle_bool(row.get("is_proxy_narrative"))),
        "proxy_context_controls": sum(1 for row in rows if row.get("relationship_type") == "proxy_context"),
        "direct_beneficiaries": sum(1 for row in rows if _bundle_bool(row.get("is_direct_beneficiary"))),
        "eligible_rows": sum(1 for row in rows if _bundle_bool(row.get("eligible"))),
        "short_triggered_rows": sum(1 for row in rows if row.get("signal_type") == "SHORT_TRIGGERED"),
        "missing_event_time_rows": sum(1 for row in rows if not row.get("event_time")),
        "source_provider_summary": source_provider_summary,
        "source_origin_summary": source_origin_summary,
    }

def _event_fade_review_source_provider_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        providers = _bundle_list_values(row.get("raw_providers")) or _bundle_list_values(row.get("source")) or ["unknown"]
        for provider in providers:
            bucket = summary.setdefault(provider, {
                "rows": 0,
                "proxy_candidates": 0,
                "proxy_context_controls": 0,
                "direct_beneficiaries": 0,
                "eligible_rows": 0,
                "short_triggered_rows": 0,
                "missing_event_time_rows": 0,
            })
            bucket["rows"] += 1
            if _bundle_bool(row.get("is_proxy_narrative")):
                bucket["proxy_candidates"] += 1
            if row.get("relationship_type") == "proxy_context":
                bucket["proxy_context_controls"] += 1
            if _bundle_bool(row.get("is_direct_beneficiary")):
                bucket["direct_beneficiaries"] += 1
            if _bundle_bool(row.get("eligible")):
                bucket["eligible_rows"] += 1
            if row.get("signal_type") == "SHORT_TRIGGERED":
                bucket["short_triggered_rows"] += 1
            if not row.get("event_time"):
                bucket["missing_event_time_rows"] += 1
    return dict(sorted(
        summary.items(),
        key=lambda item: (-item[1]["rows"], item[0]),
    ))

def _event_fade_review_source_origin_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        origins = event_validation.source_origin_values(row)
        for origin in origins:
            bucket = summary.setdefault(origin, {
                "rows": 0,
                "proxy_candidates": 0,
                "proxy_context_controls": 0,
                "direct_beneficiaries": 0,
                "eligible_rows": 0,
                "short_triggered_rows": 0,
                "missing_event_time_rows": 0,
            })
            bucket["rows"] += 1
            if _bundle_bool(row.get("is_proxy_narrative")):
                bucket["proxy_candidates"] += 1
            if row.get("relationship_type") == "proxy_context":
                bucket["proxy_context_controls"] += 1
            if _bundle_bool(row.get("is_direct_beneficiary")):
                bucket["direct_beneficiaries"] += 1
            if _bundle_bool(row.get("eligible")):
                bucket["eligible_rows"] += 1
            if row.get("signal_type") == "SHORT_TRIGGERED":
                bucket["short_triggered_rows"] += 1
            if not row.get("event_time"):
                bucket["missing_event_time_rows"] += 1
    return dict(sorted(
        summary.items(),
        key=lambda item: (-item[1]["rows"], item[0]),
    ))

def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

def _bundle_list_values(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, tuple):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return [raw]
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item not in (None, "")]
        return [raw]
    return [str(value)]

def _bundle_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return False

def event_fade_merge_sample(fresh_path: str, reviewed_path: str, out_path: str, verbose: bool = False) -> None:
    """Merge manual review status, labels, and outcomes into a fresh export."""
    _setup_event_discovery_logging(verbose)
    fresh = event_validation.load_validation_sample(fresh_path)
    reviewed = event_validation.load_validation_sample(reviewed_path)
    result = event_validation.merge_review_fields(fresh, reviewed)
    out = event_discovery.write_validation_sample(result.rows, out_path)
    print(
        "Event-fade validation sample merge: "
        f"{result.matched_rows} matched row(s), "
        f"{result.evidence_changed_rows} evidence-changed row(s), "
        f"{result.unmatched_reviewed_rows} unmatched reviewed row(s), "
        f"{result.copied_fields} copied field(s), wrote {len(result.rows)} row(s) to {out}"
    )
    evidence_changes = event_validation.format_merge_evidence_changes(result)
    if evidence_changes:
        print(evidence_changes)

def event_fade_fill_outcomes(
    sample_path: str,
    prices_path: str,
    out_path: str,
    *,
    overwrite: bool = False,
    verbose: bool = False,
) -> None:
    """Fill validation-sample outcome fields from local OHLCV fixtures."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(sample_path)
    prices = event_validation.load_outcome_price_fixture(prices_path)
    result = event_validation.fill_validation_outcomes(rows, prices, overwrite=overwrite)
    out = event_discovery.write_validation_sample(result.rows, out_path)
    print(
        "Event-fade validation outcome fill: "
        f"{result.filled_rows}/{result.triggered_rows} triggered row(s) filled, "
        f"missing_history={result.missing_history_rows}, "
        f"insufficient_history={result.insufficient_history_rows}, "
        f"skipped_existing={result.skipped_existing_rows}, "
        f"wrote {len(result.rows)} row(s) to {out}"
    )

def event_fade_export_outcome_prices(
    sample_path: str,
    out_path: str,
    *,
    days: int | None = None,
    fixture_dir: str | None = None,
    interval: str = "1d",
    refresh_cache: bool = False,
    verbose: bool = False,
) -> None:
    """Export local OHLCV prices for event-fade validation outcome filling."""
    _setup_event_discovery_logging(verbose)
    rows = event_validation.load_validation_sample(sample_path)
    result = event_price_history.export_outcome_price_fixture(
        rows,
        out_path,
        days=days,
        fixture_dir=fixture_dir,
        cache_dir=config.BACKTEST_CACHE_DIR,
        refresh_cache=refresh_cache,
        interval=interval,
    )
    missing = ", ".join(result.missing_assets) if result.missing_assets else "none"
    print(
        "Event-fade outcome price export: "
        f"assets={result.assets_written}/{result.assets_requested}, "
        f"price_rows={result.price_rows_written}, "
        f"days={result.days}, interval={result.interval}, source={result.source}, "
        f"missing={missing}, wrote {result.out_path}"
    )

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
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service._event_fade_review_bundle_readme(sample_path=sample_path, copied_sample=copied_sample, price_export=price_export, outcome_sample=outcome_sample, queue_path=queue_path, packet_path=packet_path, balanced_packet_path=balanced_packet_path, template_path=template_path, balanced_template_path=balanced_template_path, report_path=report_path, guide_path=guide_path, manifest_path=manifest_path, rows=rows, queue=queue, review=review, sample_summary=sample_summary, fill_summary=fill_summary, auto_export_prices=auto_export_prices, reviewed_path=reviewed_path, review_merge=review_merge, warnings=warnings)

def _event_fade_review_guide() -> str:
    from .. import event_alpha as _event_alpha_service
    return _event_alpha_service._event_fade_review_guide()

def _event_fade_review_bundle_summary_lines(sample_summary: dict[str, Any]) -> list[str]:
    return [
        f"- Proxy candidates: {sample_summary.get('proxy_candidates', 0)}",
        f"- Proxy-context controls: {sample_summary.get('proxy_context_controls', 0)}",
        f"- Direct beneficiaries: {sample_summary.get('direct_beneficiaries', 0)}",
        f"- SHORT_TRIGGERED rows: {sample_summary.get('short_triggered_rows', 0)}",
        f"- Missing event time rows: {sample_summary.get('missing_event_time_rows', 0)}",
        "- Asset roles: " + _summary_count_line(sample_summary.get("asset_roles")),
        "- Relationships: " + _summary_count_line(sample_summary.get("relationship_types")),
        "- Source providers: " + _summary_count_line(sample_summary.get("source_providers")),
        "- Source provider detail: " + _source_provider_summary_line(sample_summary.get("source_provider_summary")),
        "- Source origins: " + _summary_count_line(sample_summary.get("source_origins")),
        "- Source origin detail: " + _source_provider_summary_line(sample_summary.get("source_origin_summary")),
        "",
    ]

def _event_fade_review_gate_lines(review: event_validation.EventFadeValidationReview) -> list[str]:
    return [
        f"- Promotion ready: {'yes' if review.promotion_ready else 'no'}",
        (
            f"- Reviewed coverage: proxy={review.reviewed_proxy_candidates}/{review.min_proxy_candidates}, "
            f"controls={review.reviewed_negative_controls}/{review.min_negative_controls}, "
            f"triggers={review.triggered_reviewed}/{review.min_triggered_reviewed}"
        ),
        (
            f"- Proxy diversity: event_types={review.reviewed_proxy_event_types}/{review.min_proxy_event_types}, "
            f"source_providers={review.reviewed_proxy_source_providers}/{review.min_proxy_source_providers}, "
            f"source_origins={review.reviewed_proxy_source_origins}"
        ),
        (
            f"- Trigger diversity: btc_risk_buckets={review.triggered_btc_risk_buckets}/"
            f"{review.min_trigger_btc_risk_buckets}"
        ),
        (
            f"- Timing blockers: low_confidence_trigger_times={review.low_confidence_trigger_event_time_rows}, "
            f"missing_source_timing={review.missing_source_timing_rows}, "
            f"point_in_time_violations={review.point_in_time_violation_rows}, "
            f"post_decision_source_rows={review.post_decision_source_rows}"
        ),
        f"- Review provenance missing: {review.missing_review_provenance_rows}",
        "",
    ]

def _summary_count_line(counts: object, *, limit: int = 6) -> str:
    if not isinstance(counts, dict) or not counts:
        return "none"
    parts = [f"{key}={value}" for key, value in list(counts.items())[:limit]]
    remaining = len(counts) - len(parts)
    if remaining > 0:
        parts.append(f"+{remaining} more")
    return ", ".join(parts)

def _source_provider_summary_line(summary: object, *, limit: int = 4) -> str:
    if not isinstance(summary, dict) or not summary:
        return "none"
    parts: list[str] = []
    for provider, raw_counts in list(summary.items())[:limit]:
        if not isinstance(raw_counts, dict):
            continue
        parts.append(
            f"{provider}: rows={raw_counts.get('rows', 0)}, "
            f"proxy={raw_counts.get('proxy_candidates', 0)}, "
            f"direct={raw_counts.get('direct_beneficiaries', 0)}, "
            f"triggered={raw_counts.get('short_triggered_rows', 0)}, "
            f"missing_time={raw_counts.get('missing_event_time_rows', 0)}"
        )
    remaining = len(summary) - len(parts)
    if remaining > 0:
        parts.append(f"+{remaining} more")
    return "; ".join(parts) if parts else "none"

__all__ = (
    'event_fade_auto_report',
    'event_fade_export_sample',
    'event_fade_export_cache_sample',
    'event_fade_review_sample',
    'event_fade_labeling_queue',
    'event_fade_review_packet',
    'event_fade_export_review_template',
    'event_fade_apply_review_template',
    'event_fade_check_review_template',
    'event_fade_review_bundle',
    'event_fade_cache_review_bundle',
    '_merge_review_rows_for_bundle',
    '_print_review_merge_summary',
    '_empty_review_bundle_message',
    '_write_event_fade_review_bundle',
    '_event_fade_review_bundle_manifest',
    '_event_fade_review_price_export_manifest',
    '_event_fade_review_merge_manifest',
    '_event_fade_review_sample_summary',
    '_event_fade_review_source_provider_summary',
    '_event_fade_review_source_origin_summary',
    '_count_values',
    '_bundle_list_values',
    '_bundle_bool',
    'event_fade_merge_sample',
    'event_fade_fill_outcomes',
    'event_fade_export_outcome_prices',
    '_event_fade_review_bundle_readme',
    '_event_fade_review_guide',
    '_event_fade_review_bundle_summary_lines',
    '_event_fade_review_gate_lines',
    '_summary_count_line',
    '_source_provider_summary_line',
)
