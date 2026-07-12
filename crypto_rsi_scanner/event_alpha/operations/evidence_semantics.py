"""Shared burn-in evidence classification for Event Alpha operating reports."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import common
from .daily_burn_in import CANDIDATE_MODE_MANIFEST_JSON, RUN_JSON


INTEGRATED_CANDIDATES = "event_integrated_radar_candidates.jsonl"
CORE_OPPORTUNITIES = "event_core_opportunities.jsonl"
NOTIFICATION_ALERTS = "event_alpha_alerts.jsonl"
MARKET_ANOMALIES = "event_market_anomalies.jsonl"
FADE_REVIEW_CANDIDATES = "event_fade_short_review_candidates.jsonl"
SOURCE_COVERAGE_JSON = "event_alpha_source_coverage.json"
REVIEW_INBOX_JSON = "event_alpha_daily_review_inbox.json"
FEEDBACK_JSONL = "event_alpha_feedback.jsonl"

READINESS_ARTIFACTS = {
    "event_alpha_live_provider_readiness.json",
    "event_dex_onchain_readiness.json",
    "event_provider_health.json",
}
PREFLIGHT_ARTIFACTS = {
    "event_coinalyze_preflight.json",
    "event_coinalyze_rehearsal_report.json",
    "event_bybit_announcements_preflight.json",
    "event_bybit_announcements_rehearsal_report.json",
    "event_unlock_calendar_preflight.json",
}
CANDIDATE_ARTIFACTS = {
    INTEGRATED_CANDIDATES,
    CORE_OPPORTUNITIES,
    NOTIFICATION_ALERTS,
    MARKET_ANOMALIES,
    FADE_REVIEW_CANDIDATES,
}
NON_CONTRACT_NAMESPACE_CATEGORIES = {
    "notification_rehearsal",
    "provider_rehearsal",
    "fixture",
    "stale",
    "no_key",
    "active_live_rehearsal",
}


def policy_categories(policy: Mapping[str, Any], namespace: str) -> set[str]:
    for section in ("included_namespace_details", "excluded_namespace_details"):
        for row in policy.get(section) or []:
            if isinstance(row, Mapping) and str(row.get("namespace") or "") == namespace:
                return {str(item) for item in row.get("categories") or []}
    return set()


def namespace_summaries(
    base: Path,
    namespaces: list[str] | tuple[str, ...],
    *,
    cutoff: datetime,
    policy: Mapping[str, Any],
    evaluated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    evaluation_now = _evaluation_now(evaluated_at)
    return [
        namespace_summary(
            base,
            namespace,
            cutoff=cutoff,
            categories=policy_categories(policy, namespace),
            evaluated_at=evaluation_now,
        )
        for namespace in namespaces
    ]


def namespace_summary(
    base: Path,
    namespace: str,
    *,
    cutoff: datetime,
    categories: set[str] | None = None,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    evaluation_now = _evaluation_now(evaluated_at)
    categories = set(categories or set())
    namespace_dir = base / namespace
    daily_run = _current_json_doc(
        namespace_dir / RUN_JSON,
        cutoff=cutoff,
        evaluated_at=evaluation_now,
    )
    candidate_manifest = _current_json_doc(
        namespace_dir / CANDIDATE_MODE_MANIFEST_JSON,
        cutoff=cutoff,
        evaluated_at=evaluation_now,
    )
    candidate_mode = bool(daily_run.get("candidate_mode") or candidate_manifest.get("candidate_mode"))
    burn_in_run_count = _json_doc_count(
        namespace_dir / RUN_JSON,
        cutoff=cutoff,
        evaluated_at=evaluation_now,
    )
    integrated_rows = _rows(
        namespace_dir / INTEGRATED_CANDIDATES,
        cutoff=cutoff,
        evaluated_at=evaluation_now,
    )
    core_rows = _rows(
        namespace_dir / CORE_OPPORTUNITIES,
        cutoff=cutoff,
        evaluated_at=evaluation_now,
    )
    alert_rows = _rows(
        namespace_dir / NOTIFICATION_ALERTS,
        cutoff=cutoff,
        evaluated_at=evaluation_now,
    )
    market_rows = _rows(
        namespace_dir / MARKET_ANOMALIES,
        cutoff=cutoff,
        evaluated_at=evaluation_now,
    )
    fade_rows = _rows(
        namespace_dir / FADE_REVIEW_CANDIDATES,
        cutoff=cutoff,
        evaluated_at=evaluation_now,
    )
    candidate_rows = [*integrated_rows, *core_rows, *alert_rows, *market_rows, *fade_rows]
    fixture_candidate_count = sum(1 for row in integrated_rows if _is_fixture_row(row) or "fixture" in categories)
    diagnostic_count = sum(1 for row in candidate_rows if is_diagnostic_row(row))
    real_rows = [
        row
        for row in integrated_rows
        if is_contract_counted_candidate(row, namespace_categories=categories, has_burn_in_run=burn_in_run_count > 0)
    ]
    readiness_rows = sum(
        _json_doc_count(
            namespace_dir / name,
            cutoff=cutoff,
            evaluated_at=evaluation_now,
        )
        for name in READINESS_ARTIFACTS
    )
    preflight_rows = sum(
        _json_doc_count(
            namespace_dir / name,
            cutoff=cutoff,
            evaluated_at=evaluation_now,
        )
        for name in PREFLIGHT_ARTIFACTS
    )
    source_coverage_rows = _json_doc_count(
        namespace_dir / SOURCE_COVERAGE_JSON,
        cutoff=cutoff,
        evaluated_at=evaluation_now,
    )
    preview_only = int((namespace_dir / "event_alpha_notification_preview.md").exists() and not candidate_rows)
    no_candidate_artifacts = not any((namespace_dir / name).exists() for name in CANDIDATE_ARTIFACTS)
    return {
        "namespace": namespace,
        "categories": sorted(categories),
        "burn_in_run_count": burn_in_run_count,
        "has_burn_in_run": burn_in_run_count > 0,
        "candidate_mode": candidate_mode,
        "has_candidate_mode_manifest": bool(candidate_manifest),
        "integrated_candidate_count": len(integrated_rows),
        "core_opportunity_count": len(core_rows),
        "notification_rehearsal_rows": len(alert_rows),
        "market_anomaly_rows": len(market_rows),
        "fade_review_candidate_rows": len(fade_rows),
        "candidate_artifact_rows": len(candidate_rows),
        "real_burn_in_candidate_count": len(real_rows),
        "fixture_candidate_count": fixture_candidate_count,
        "integrated_fixture_rows": fixture_candidate_count,
        "diagnostic_candidate_count": diagnostic_count,
        "preflight_diagnostic_rows": preflight_rows,
        "source_coverage_rows": source_coverage_rows,
        "readiness_rows": readiness_rows,
        "notification_preview_only": preview_only,
        "stale_rows": len(integrated_rows) if "stale" in categories else 0,
        "no_key_rows": len(integrated_rows) if "no_key" in categories else 0,
        "has_candidate_artifacts": not no_candidate_artifacts,
        "has_support_artifacts": bool(preflight_rows or readiness_rows or source_coverage_rows or preview_only),
        "has_only_preflight_rows": bool(not real_rows and not candidate_rows and (preflight_rows or readiness_rows or source_coverage_rows)),
        "has_only_fixture_rows": bool(not real_rows and fixture_candidate_count and fixture_candidate_count == len(integrated_rows)),
        "has_only_diagnostics": bool(not real_rows and candidate_rows and diagnostic_count == len(candidate_rows)),
        "has_integrated_candidates": bool(integrated_rows),
        "has_real_candidates": bool(real_rows),
        "has_notification_preview_only": bool(preview_only),
        "has_no_candidate_artifacts": bool(no_candidate_artifacts),
        "real_candidate_rows": real_rows,
    }


def aggregate_namespace_summaries(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    real_rows = [row for summary in summaries for row in summary.get("real_candidate_rows", [])]
    return {
        "burn_in_run_namespaces": _names_where(summaries, "has_burn_in_run"),
        "burn_in_run_count": sum(int(item.get("burn_in_run_count") or 0) for item in summaries),
        "namespaces_with_real_candidates": _names_where(summaries, "has_real_candidates"),
        "namespaces_with_only_preflight_rows": _names_where(summaries, "has_only_preflight_rows"),
        "namespaces_with_only_fixture_rows": _names_where(summaries, "has_only_fixture_rows"),
        "namespaces_with_only_diagnostics": _names_where(summaries, "has_only_diagnostics"),
        "namespaces_with_integrated_candidates": _names_where(summaries, "has_integrated_candidates"),
        "namespaces_with_notification_preview_only": _names_where(summaries, "has_notification_preview_only"),
        "namespaces_with_no_candidate_artifacts": _names_where(summaries, "has_no_candidate_artifacts"),
        "candidate_mode_namespaces": _names_where(summaries, "candidate_mode"),
        "candidate_mode_manifest_namespaces": _names_where(summaries, "has_candidate_mode_manifest"),
        "real_burn_in_candidates": len(real_rows),
        "fixture_candidates": sum(int(item.get("fixture_candidate_count") or 0) for item in summaries),
        "preflight_diagnostic_rows": sum(int(item.get("preflight_diagnostic_rows") or 0) for item in summaries),
        "source_coverage_rows": sum(int(item.get("source_coverage_rows") or 0) for item in summaries),
        "readiness_rows": sum(int(item.get("readiness_rows") or 0) for item in summaries),
        "notification_rehearsal_rows": sum(int(item.get("notification_rehearsal_rows") or 0) for item in summaries),
        "integrated_fixture_rows": sum(int(item.get("integrated_fixture_rows") or 0) for item in summaries),
        "stale_rows": sum(int(item.get("stale_rows") or 0) for item in summaries),
        "no_key_rows": sum(int(item.get("no_key_rows") or 0) for item in summaries),
        "real_candidate_rows": real_rows,
        "namespace_evidence_details": [
            {key: value for key, value in item.items() if key != "real_candidate_rows"}
            for item in summaries
        ],
    }


def payload_fields(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "burn_in_run_namespaces",
        "burn_in_run_count",
        "namespaces_with_real_candidates",
        "namespaces_with_only_preflight_rows",
        "namespaces_with_only_fixture_rows",
        "namespaces_with_only_diagnostics",
        "namespaces_with_integrated_candidates",
        "namespaces_with_notification_preview_only",
        "namespaces_with_no_candidate_artifacts",
        "candidate_mode_namespaces",
        "candidate_mode_manifest_namespaces",
        "real_burn_in_candidates",
        "fixture_candidates",
        "preflight_diagnostic_rows",
        "source_coverage_rows",
        "readiness_rows",
        "notification_rehearsal_rows",
        "integrated_fixture_rows",
        "stale_rows",
        "no_key_rows",
        "namespace_evidence_details",
    )
    return {field: aggregate.get(field) for field in fields}


def evidence_scope_from_summary(
    *,
    explicit_scope: bool,
    contract_countable: bool,
    included_namespaces: list[str],
    aggregate: Mapping[str, Any],
) -> tuple[str, str]:
    if explicit_scope and not contract_countable:
        return "explicit_single_namespace_diagnostic", "explicit namespace is diagnostic unless counted intentionally"
    if not included_namespaces:
        return "no_active_burn_in_namespaces", "no active burn-in namespaces selected by policy"
    real_count = int(aggregate.get("real_burn_in_candidates") or 0)
    if real_count > 0:
        return "real_burn_in_evidence", "burn-in run produced contract-counted candidate artifacts"
    fixture_count = int(aggregate.get("fixture_candidates") or 0) + int(aggregate.get("integrated_fixture_rows") or 0)
    if aggregate.get("candidate_mode_namespaces") and fixture_count > 0:
        return "fixture_candidate_mode_smoke", "candidate-mode smoke produced mocked fixture candidates that are not contract-counted"
    if aggregate.get("candidate_mode_namespaces"):
        return "active_burn_in_candidate_mode_no_candidates", "candidate mode ran but no contract-counted candidate artifacts were produced"
    support_rows = (
        int(aggregate.get("preflight_diagnostic_rows") or 0)
        + int(aggregate.get("readiness_rows") or 0)
        + int(aggregate.get("source_coverage_rows") or 0)
        + fixture_count
    )
    if support_rows > 0:
        return "active_burn_in_preflight_only", "burn-in run completed but only fixture/preflight/readiness/support rows were found"
    return "active_burn_in_no_candidate_evidence", "burn-in run completed but no real candidate artifacts were produced"


def is_contract_counted_candidate(row: Mapping[str, Any], *, namespace_categories: set[str], has_burn_in_run: bool) -> bool:
    if not has_burn_in_run:
        return False
    if namespace_categories & NON_CONTRACT_NAMESPACE_CATEGORIES:
        return False
    if is_diagnostic_row(row) or _is_fixture_row(row):
        return False
    source_mode = str(row.get("candidate_source_mode") or "").strip().casefold()
    if source_mode in {"mocked_fixture", "fixture", "preflight_only", "readiness_only", "artifact_replay"}:
        return False
    if row.get("contract_counted_candidate") is not True:
        return False
    return bool(
        source_mode == "live_no_send"
        and str(row.get("request_ledger_path") or "").strip()
        and str(row.get("provider_generation_id") or "").strip()
        and str(row.get("provider_source_artifact") or "").strip()
        and row.get("provider_request_succeeded") is True
    )


def is_diagnostic_row(row: Mapping[str, Any]) -> bool:
    lane = common.row_lane(row).upper()
    if lane == "DIAGNOSTIC":
        return True
    return bool(row.get("diagnostic_only") is True or row.get("is_diagnostic") is True)


def row_provenance(row: Mapping[str, Any]) -> dict[str, Any]:
    source_file = str(row.get("_source_file") or "")
    record_type = {
        INTEGRATED_CANDIDATES: "integrated_candidate",
        CORE_OPPORTUNITIES: "core_opportunity",
        NOTIFICATION_ALERTS: "notification_skipped_candidate" if row.get("skipped") is True or row.get("skip_reason") else "notification_candidate",
        MARKET_ANOMALIES: "market_anomaly",
        FADE_REVIEW_CANDIDATES: "fade_review_candidate",
    }.get(source_file, "candidate")
    fixture_only = _is_fixture_row(row)
    diagnostic_only = is_diagnostic_row(row)
    preflight_only = record_type in {"preflight", "readiness"}
    source_mode = str(row.get("candidate_source_mode") or "").strip()
    requested_contract_count = row.get("contract_counted_candidate")
    real_evidence = record_type == "integrated_candidate" and not fixture_only and not diagnostic_only
    if requested_contract_count is False:
        real_evidence = False
    if source_mode in {"mocked_fixture", "preflight_only", "readiness_only", "artifact_replay"}:
        real_evidence = False
    if requested_contract_count is True and source_mode == "live_no_send" and row.get("request_ledger_path"):
        real_evidence = True
    return {
        "candidate_record_type": record_type,
        "candidate_provenance": record_type,
        "source_artifact": source_file,
        "source_artifact_row_type": str(row.get("row_type") or record_type),
        "real_candidate_evidence": real_evidence,
        "diagnostic_only": diagnostic_only,
        "fixture_only": fixture_only,
        "preflight_only": preflight_only,
        "candidate_source_mode": source_mode,
        "provider": str(row.get("provider") or row.get("source_provider") or row.get("source_origin") or ""),
        "source_pack": str(row.get("source_pack") or row.get("source_pack_id") or row.get("source_class") or ""),
        "source_origin": str(row.get("source_origin") or row.get("provider") or row.get("source_provider") or ""),
        "request_ledger_path": str(row.get("request_ledger_path") or ""),
        "contract_counted_candidate": bool(real_evidence if requested_contract_count is None else requested_contract_count and real_evidence),
    }


def archive_artifact_categories(rel_path: str) -> dict[str, bool]:
    name = Path(rel_path).name
    return {
        "burn_in_run_artifacts": name == RUN_JSON,
        "candidate_artifacts": name in CANDIDATE_ARTIFACTS,
        "readiness_artifacts": name in READINESS_ARTIFACTS or name in PREFLIGHT_ARTIFACTS or "readiness" in name or "preflight" in name,
        "source_coverage_artifacts": name.startswith("event_alpha_source_coverage."),
        "review_inbox_artifacts": name.startswith("event_alpha_daily_review_inbox."),
        "feedback_artifacts": name == FEEDBACK_JSONL,
    }


def _evaluation_now(value: datetime | None) -> datetime:
    evaluation_now = common.utc_now() if value is None else value
    if (
        not isinstance(evaluation_now, datetime)
        or evaluation_now.tzinfo is None
        or evaluation_now.utcoffset() is None
    ):
        raise ValueError("evidence semantics evaluated_at must be timezone-aware")
    return evaluation_now.astimezone(timezone.utc)


def _rows(
    path: Path,
    *,
    cutoff: datetime,
    evaluated_at: datetime,
) -> list[dict[str, Any]]:
    return [
        row
        for row in common.read_jsonl(path)
        if common.row_in_evidence_window(
            row,
            cutoff=cutoff,
            evaluated_at=evaluated_at,
        )
    ]


def _json_doc_count(
    path: Path,
    *,
    cutoff: datetime,
    evaluated_at: datetime,
) -> int:
    return int(
        bool(
            _current_json_doc(
                path,
                cutoff=cutoff,
                evaluated_at=evaluated_at,
            )
        )
    )


def _current_json_doc(
    path: Path,
    *,
    cutoff: datetime,
    evaluated_at: datetime,
) -> dict[str, Any]:
    row = common.read_json(path)
    if not row or not common.row_in_evidence_window(
        row,
        cutoff=cutoff,
        evaluated_at=evaluated_at,
    ):
        return {}
    return row


def _is_fixture_row(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(row.get(field) or "") for field in ("run_mode", "profile", "artifact_namespace", "source_origin", "source_pack")).casefold()
    return bool(row.get("fixture_only") is True or row.get("test_fixture") is True or "fixture" in text or "smoke" in text)


def _names_where(summaries: list[dict[str, Any]], field: str) -> list[str]:
    return [str(item.get("namespace")) for item in summaries if item.get(field)]
