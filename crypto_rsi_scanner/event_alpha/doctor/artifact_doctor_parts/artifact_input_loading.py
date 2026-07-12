"""Canonical path and raw-file loading helpers for the artifact doctor."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Mapping

from ...artifacts import json_lines as artifact_json_lines
from .runtime import *  # noqa: F403 - doctor split modules share runtime bindings.


def _default_doctor_artifact_dir(options: Mapping[str, Any]) -> Path | None:
    if options["artifact_namespace_dir"] is not None:
        return Path(options["artifact_namespace_dir"]).expanduser()
    if options["inspected_alert_store_path"] is not None:
        return Path(options["inspected_alert_store_path"]).parent
    if options["source_coverage_report_path"] is not None:
        return Path(options["source_coverage_report_path"]).parent
    return None


def _load_raw_doctor_artifacts(options: Mapping[str, Any]) -> SimpleNamespace:
    default_dir = _default_doctor_artifact_dir(options)
    integrated_path = _canonical_doctor_artifact_path(
        options["integrated_candidate_path"],
        default_dir,
        "event_integrated_radar_candidates.jsonl",
    )
    integrated_dir = default_dir
    integrated_candidate_read = artifact_json_lines.read_jsonl(integrated_path)
    core_path = _canonical_doctor_artifact_path(
        options["core_opportunity_store_path"],
        default_dir,
        "event_core_opportunities.jsonl",
    )
    core_read = artifact_json_lines.read_jsonl(core_path)
    integrated_outcomes_path = _canonical_doctor_artifact_path(
        options["integrated_outcomes_path"],
        default_dir,
        event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME,  # noqa: F405
    )
    integrated_outcome_read = artifact_json_lines.read_jsonl(integrated_outcomes_path)
    alpha_outcomes_path = _canonical_doctor_artifact_path(
        options["outcomes_path"],
        default_dir,
        "event_alpha_outcomes.jsonl",
    )
    alpha_outcome_read = artifact_json_lines.read_jsonl(alpha_outcomes_path)
    feedback_path = _canonical_doctor_artifact_path(
        options["feedback_path"],
        default_dir,
        "event_alpha_feedback.jsonl",
    )
    feedback_read = artifact_json_lines.read_jsonl(feedback_path)
    explicit_feedback = [
        dict(row) for row in options["feedback_rows"] if isinstance(row, Mapping)
    ]
    raw_feedback = (
        list(feedback_read.rows)
        if options["feedback_path"] is not None
        or (feedback_path is not None and feedback_path.exists())
        else explicit_feedback
    )
    explicit_core_rows = [_row(row) for row in options["core_opportunity_rows"]]
    raw_canonical_core_rows = (
        list(core_read.rows)
        if options["core_opportunity_store_path"] is not None
        or (core_path is not None and core_path.exists())
        else explicit_core_rows
    )
    explicit_outcomes = [
        dict(row) for row in options["outcome_rows"] if isinstance(row, Mapping)
    ]
    canonical_outcome_files_present = (
        options["integrated_outcomes_path"] is not None
        or options["outcomes_path"] is not None
        or any(
            path is not None and path.exists()
            for path in (integrated_outcomes_path, alpha_outcomes_path)
        )
    )
    raw_outcomes = (
        [*integrated_outcome_read.rows, *alpha_outcome_read.rows]
        if canonical_outcome_files_present
        else explicit_outcomes
    )
    outcome_evidence_jsonl_diagnostics = _outcome_evidence_jsonl_diagnostics(
        candidate_diagnostics=integrated_candidate_read.diagnostics,
        core_diagnostics=core_read.diagnostics,
        integrated_outcome_diagnostics=integrated_outcome_read.diagnostics,
        alpha_outcome_diagnostics=alpha_outcome_read.diagnostics,
    )
    return SimpleNamespace(
        raw_runs=[dict(row) for row in options["run_rows"] if isinstance(row, Mapping)],
        raw_alerts=[dict(row) for row in options["alert_rows"] if isinstance(row, Mapping)],
        raw_feedback=raw_feedback,
        raw_outcomes=raw_outcomes,
        raw_hypotheses=[_row(row) for row in options["hypothesis_rows"]],
        raw_core_rows=explicit_core_rows,
        raw_canonical_core_rows=raw_canonical_core_rows,
        raw_watchlist=[_row(row) for row in options["watchlist_rows"]],
        raw_incidents=[_row(row) for row in options["incident_rows"]],
        raw_acquisition_rows=[
            dict(row)
            for row in options["evidence_acquisition_rows"]
            if isinstance(row, Mapping)
        ],
        **_load_raw_namespace_sidecars(options, default_dir),
        raw_integrated_candidates=list(integrated_candidate_read.rows),
        outcome_evidence_jsonl_diagnostics=outcome_evidence_jsonl_diagnostics,
        feedback_jsonl_diagnostics=feedback_read.diagnostics,
        integrated_manifest_path=(
            integrated_dir / "event_integrated_radar_input_manifest.json"
            if integrated_dir is not None
            else None
        ),
        integrated_source_coverage_json_path=(
            integrated_dir / "event_alpha_source_coverage.json"
            if integrated_dir is not None
            else None
        ),
        integrated_delivery_path=(
            integrated_dir / event_integrated_radar.INTEGRATED_DELIVERIES_FILENAME  # noqa: F405
            if integrated_dir is not None
            else None
        ),
        integrated_outcomes_path=integrated_outcomes_path,
    )


def _load_raw_namespace_sidecars(
    options: Mapping[str, Any],
    default_dir: Path | None,
) -> dict[str, Any]:
    def artifact_json(filename: str) -> dict[str, Any]:
        return _read_json(default_dir / filename if default_dir is not None else None)

    return {
        "raw_market_anomalies": _load_optional_rows(
            options["market_anomaly_rows"],
            lambda: event_market_anomaly_scanner.load_market_anomaly_rows(default_dir),  # noqa: F405
        ),
        "raw_official_exchange_candidates": _load_optional_rows(
            options["official_exchange_candidate_rows"],
            lambda: event_official_exchange.load_official_listing_candidates(default_dir),  # noqa: F405
        ),
        "raw_scheduled_catalysts": _load_optional_rows(
            options["scheduled_catalyst_rows"],
            lambda: event_scheduled_catalysts.load_scheduled_catalysts(default_dir),  # noqa: F405
        ),
        "raw_unlock_candidates": _load_optional_rows(
            options["unlock_candidate_rows"],
            lambda: event_scheduled_catalysts.load_unlock_candidates(default_dir),  # noqa: F405
        ),
        "raw_derivatives_state": _load_optional_rows(
            options["derivatives_state_rows"],
            lambda: event_derivatives_crowding.load_derivatives_state(default_dir),  # noqa: F405
        ),
        "raw_fade_review_candidates": _load_raw_fade_review_candidates(
            options,
            default_dir,
        ),
        "raw_dex_pool_state": list(
            event_dex_onchain_readiness.load_dex_pool_state(default_dir)  # noqa: F405
        ),
        "raw_dex_pool_anomalies": list(
            event_dex_onchain_readiness.load_dex_pool_anomalies(default_dir)  # noqa: F405
        ),
        "raw_protocol_fundamentals": list(
            event_dex_onchain_readiness.load_protocol_fundamentals(default_dir)  # noqa: F405
        ),
        "raw_burn_in_scorecard": artifact_json("event_alpha_burn_in_scorecard.json"),
        "raw_source_yield_report": artifact_json("event_alpha_source_yield_report.json"),
        "raw_daily_review_inbox": artifact_json("event_alpha_daily_review_inbox.json"),
        "raw_daily_burn_in_run": artifact_json("event_alpha_daily_burn_in_run.json"),
        "raw_candidate_mode_manifest": artifact_json("event_alpha_candidate_mode_manifest.json"),
        "raw_burn_in_namespace_policy": artifact_json("event_alpha_burn_in_namespace_policy.json"),
        "raw_burn_in_archive_manifest": artifact_json("event_alpha_burn_in_archive_manifest.json"),
    }


def _canonical_doctor_artifact_path(
    explicit_path: str | Path | None,
    default_dir: Path | None,
    filename: str,
) -> Path | None:
    if explicit_path is not None:
        return Path(explicit_path).expanduser()
    if default_dir is None:
        return None
    return default_dir / filename


def _load_optional_rows(
    rows: Iterable[Mapping[str, Any]] | None,
    loader: Callable[[], Iterable[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    if rows is None:
        return [dict(row) for row in loader() if isinstance(row, Mapping)]
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _outcome_evidence_jsonl_diagnostics(
    default_dir: Path | None = None,
    *,
    candidate_diagnostics: Any,
    core_diagnostics: Any = None,
    integrated_outcome_diagnostics: Any = None,
    alpha_outcome_diagnostics: Any = None,
) -> dict[str, Any]:
    if core_diagnostics is None:
        core_diagnostics = artifact_json_lines.read_jsonl(
            default_dir / "event_core_opportunities.jsonl"
            if default_dir is not None
            else None
        ).diagnostics
    if integrated_outcome_diagnostics is None:
        integrated_outcome_diagnostics = artifact_json_lines.read_jsonl(
            default_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME  # noqa: F405
            if default_dir is not None
            else None
        ).diagnostics
    if alpha_outcome_diagnostics is None:
        alpha_outcome_diagnostics = artifact_json_lines.read_jsonl(
            default_dir / "event_alpha_outcomes.jsonl"
            if default_dir is not None
            else None
        ).diagnostics
    return {
        "candidates": candidate_diagnostics,
        "core": core_diagnostics,
        "integrated_outcomes": integrated_outcome_diagnostics,
        "alpha_outcomes": alpha_outcome_diagnostics,
    }


def _attach_outcome_evidence_jsonl_diagnostics(ctx: SimpleNamespace) -> None:
    diagnostics = ctx.outcome_evidence_jsonl_diagnostics
    duplicate_counts = {
        name: len(item.duplicate_key_lines)
        for name, item in diagnostics.items()
        if item.duplicate_key_lines
    }
    malformed_counts = {
        name: len(item.invalid_json_lines) + len(item.non_object_lines)
        for name, item in diagnostics.items()
        if item.invalid_json_lines or item.non_object_lines
    }
    read_errors = tuple(
        sorted(name for name, item in diagnostics.items() if item.read_error)
    )
    messages: list[str] = []
    if duplicate_counts:
        messages.append(
            "outcome_evidence_duplicate_json_keys="
            + ",".join(
                f"{name}:{duplicate_counts[name]}" for name in sorted(duplicate_counts)
            )
        )
    if malformed_counts:
        messages.append(
            "outcome_evidence_invalid_jsonl="
            + ",".join(
                f"{name}:{malformed_counts[name]}" for name in sorted(malformed_counts)
            )
        )
    if read_errors:
        messages.append("outcome_evidence_jsonl_read_errors=" + ",".join(read_errors))
    target = ctx.blockers if ctx.strict else ctx.warnings
    target.extend(
        check_registry.format_check_message("outcomes.eligibility_firewall", message)  # noqa: F405
        for message in messages
    )


def _load_raw_fade_review_candidates(
    options: Mapping[str, Any],
    default_dir: Path | None,
) -> list[dict[str, Any]]:
    rows = options["fade_review_candidate_rows"]
    if rows is not None:
        return [dict(row) for row in rows if isinstance(row, Mapping)]
    candidates = list(event_derivatives_crowding.load_derivatives_candidates(default_dir))  # noqa: F405
    if not candidates:
        candidates = list(event_derivatives_crowding.load_fade_review_candidates(default_dir))  # noqa: F405
    return [dict(row) for row in candidates if isinstance(row, Mapping)]


def _row(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(getattr(value, "__dict__", {}) or {})


def _read_jsonl(path: str | Path | None) -> list[dict[str, Any]]:
    return list(artifact_json_lines.read_jsonl(path).rows)


def _read_json(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


__all__ = (
    "_attach_outcome_evidence_jsonl_diagnostics",
    "_canonical_doctor_artifact_path",
    "_default_doctor_artifact_dir",
    "_load_optional_rows",
    "_load_raw_doctor_artifacts",
    "_load_raw_fade_review_candidates",
    "_outcome_evidence_jsonl_diagnostics",
    "_read_json",
    "_read_jsonl",
    "_row",
)
