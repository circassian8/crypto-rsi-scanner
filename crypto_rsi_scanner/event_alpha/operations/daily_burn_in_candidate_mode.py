"""Candidate-mode provider lineage and manifests for daily burn-in."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ... import config
from ..artifacts import research_cards as event_research_cards
from ..providers import request_lineage as event_request_lineage
from ..radar import core_opportunity_store as event_core_opportunity_store
from . import common


CANDIDATE_MODE_MANIFEST_JSON = "event_alpha_candidate_mode_manifest.json"
COINALYZE_REQUEST_LEDGER = "event_coinalyze_request_ledger.jsonl"
BYBIT_REQUEST_LEDGER = "event_bybit_announcements_request_ledger.jsonl"
_PROVIDER_REHEARSAL_REPORTS = {
    "coinalyze": "event_coinalyze_rehearsal_report.json",
    "bybit_announcements": "event_bybit_announcements_rehearsal_report.json",
}
_PROVIDER_CANDIDATE_SUCCESS_STATUSES = {
    "live_rehearsal_success",
    "live_rehearsal_partial",
    "live_rehearsal_no_results",
}
_TRUTHY = {"1", "true", "yes", "on"}


def _request_ledger_row_total(context: Any) -> int:
    return sum(
        len(common.read_jsonl(context.namespace_dir / name))
        for name in (COINALYZE_REQUEST_LEDGER, BYBIT_REQUEST_LEDGER)
    )


def _candidate_provider_status(context: Any) -> dict[str, dict[str, Any]]:
    coinalyze_key_present = bool(
        _configured_value(
            "RSI_EVENT_DISCOVERY_COINALYZE_API_KEY",
            config.EVENT_DISCOVERY_COINALYZE_API_KEY,
        )
    )
    coinalyze_allow = _env_truthy("RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT")
    coinalyze_budget = _int_env("RSI_EVENT_ALPHA_COINALYZE_PREFLIGHT_MAX_REQUESTS", 8)
    coinalyze_symbols = tuple(
        _env_csv("RSI_EVENT_DISCOVERY_COINALYZE_SYMBOLS")
        or config.EVENT_DISCOVERY_COINALYZE_SYMBOLS
        or ()
    )
    if not coinalyze_key_present:
        coinalyze_status = "skipped_missing_config"
        coinalyze_skip = "missing RSI_EVENT_DISCOVERY_COINALYZE_API_KEY"
        coinalyze_live = False
    elif not coinalyze_allow:
        coinalyze_status = "live_call_blocked_by_default"
        coinalyze_skip = (
            "set RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT=1 "
            "for guarded no-send candidate mode"
        )
        coinalyze_live = False
    elif coinalyze_budget <= 0 or coinalyze_budget > 10:
        coinalyze_status = "request_budget_not_small"
        coinalyze_skip = "set RSI_EVENT_ALPHA_COINALYZE_PREFLIGHT_MAX_REQUESTS to 1..10"
        coinalyze_live = False
    else:
        coinalyze_status = "ready_live_no_send"
        coinalyze_skip = ""
        coinalyze_live = True

    bybit_allow = _env_truthy("RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT")
    bybit_limit = _int_env(
        "RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_PREFLIGHT_LIMIT",
        int(config.EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIMIT or 20),
    )
    if not bybit_allow:
        bybit_status = "skipped_live_calls_disabled"
        bybit_skip = (
            "set RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT=1 "
            "for guarded no-send candidate mode"
        )
        bybit_live = False
    elif bybit_limit <= 0 or bybit_limit > 50:
        bybit_status = "request_budget_not_small"
        bybit_skip = "set RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_PREFLIGHT_LIMIT to 1..50"
        bybit_live = False
    else:
        bybit_status = "ready_live_no_send"
        bybit_skip = ""
        bybit_live = True

    return {
        "coinalyze": {
            "provider": "coinalyze",
            "configured": coinalyze_key_present,
            "allow_flag_set": coinalyze_allow,
            "live_call_allowed": coinalyze_live,
            "status": coinalyze_status,
            "skip_reason": coinalyze_skip,
            "request_budget": coinalyze_budget,
            "symbols_configured": len(coinalyze_symbols),
            "request_ledger_path": common.rel_path(context.namespace_dir / COINALYZE_REQUEST_LEDGER),
            "source_pack": "derivatives_crowding",
        },
        "bybit_announcements": {
            "provider": "bybit_announcements",
            "configured": True,
            "allow_flag_set": bybit_allow,
            "live_call_allowed": bybit_live,
            "status": bybit_status,
            "skip_reason": bybit_skip,
            "request_budget": bybit_limit,
            "request_ledger_path": common.rel_path(context.namespace_dir / BYBIT_REQUEST_LEDGER),
            "source_pack": "official_exchange_listing_pack",
        },
    }


def _write_candidate_mode_manifest(
    *,
    context: Any,
    generated: datetime,
    profile: str,
    namespace: str,
    candidate_mode: bool,
    provider_status: Mapping[str, Mapping[str, Any]],
    completed: bool,
    doctor_status: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not candidate_mode:
        return None
    counts = _candidate_mode_counts(context, provider_status)
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_candidate_mode_manifest_v2",
            "row_type": "event_alpha_candidate_mode_manifest",
            "generated_at": generated.isoformat(),
            "last_updated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "candidate_mode": True,
            "completed": bool(completed),
            "status": _candidate_manifest_status(counts, provider_status, completed=completed),
            "no_send": True,
            "no_send_rehearsal": True,
            "live_provider_calls_allowed": any(
                bool(row.get("live_call_allowed")) for row in provider_status.values()
            ),
            "providers": {key: dict(value) for key, value in provider_status.items()},
            "skipped_missing_config": _providers_with_status(
                provider_status,
                "skipped_missing_config",
            ),
            "skipped_live_calls_disabled": _providers_with_status(
                provider_status,
                "skipped_live_calls_disabled",
                "live_call_blocked_by_default",
            ),
            "skipped_request_budget": _providers_with_status(
                provider_status,
                "request_budget_not_small",
            ),
            "skipped_not_required_for_profile": [],
            "next_steps": _candidate_mode_next_steps(provider_status),
            "doctor_status": doctor_status or {},
            **counts,
        }
    )
    common.write_json(context.namespace_dir / CANDIDATE_MODE_MANIFEST_JSON, payload)
    return payload


def _postprocess_candidate_mode_artifacts(
    *,
    context: Any,
    provider_status: Mapping[str, Mapping[str, Any]],
) -> None:
    candidates_path = context.namespace_dir / "event_integrated_radar_candidates.jsonl"
    rows = common.read_jsonl(candidates_path)
    if not rows:
        return
    changed = False
    annotated: list[dict[str, Any]] = []
    for row in rows:
        out = dict(row)
        before = dict(out)
        _annotate_candidate_row(out, context=context, provider_status=provider_status)
        annotated.append(out)
        changed = changed or out != before
    if changed:
        _write_jsonl(candidates_path, annotated)
    if _propagate_candidate_lineage_to_core(context, annotated):
        _regenerate_lineage_cards(context, annotated)


def _annotate_candidate_row(
    row: dict[str, Any],
    *,
    context: Any,
    provider_status: Mapping[str, Mapping[str, Any]],
) -> None:
    provider = _infer_candidate_provider(row)
    ledger_path = _request_ledger_for_provider(provider, context)
    generation_id = str(row.get("provider_generation_id") or "").strip()
    attempt = _current_provider_attempt(
        context=context,
        row=row,
        provider=provider,
        ledger_path=ledger_path,
        generation_id=generation_id,
    )
    ledger_success = bool(attempt)
    provider_ready = bool(provider_status.get(provider, {}).get("live_call_allowed"))
    provider_specific_source_ok = _provider_source_provenance_complete(row, provider)
    exact_lineage = bool(
        generation_id
        and ledger_success
        and provider_ready
        and provider_specific_source_ok
    )
    fixture = _is_fixture_candidate(row)
    diagnostic = (
        str(row.get("opportunity_type") or row.get("lane") or "").upper() == "DIAGNOSTIC"
        or row.get("diagnostic_only") is True
    )
    source_mode = "mocked_fixture" if fixture else ("live_no_send" if exact_lineage else "artifact_replay")
    row.setdefault("candidate_provenance", "integrated_candidate")
    row.setdefault("provider", provider or "unknown")
    row.setdefault(
        "source_origin",
        row.get("provider") or provider or row.get("source_origin") or "unknown",
    )
    row.setdefault("source_pack", row.get("source_pack") or _source_pack_for_provider(provider))
    row["candidate_source_mode"] = source_mode
    if ledger_path:
        row["request_ledger_path"] = ledger_path
    row["provider_request_succeeded"] = ledger_success
    row["no_send_rehearsal"] = True
    row["research_only"] = True
    row["strict_alerts_created"] = 0
    row["telegram_sends"] = 0
    row["trades_created"] = 0
    row["paper_trades_created"] = 0
    row["normal_rsi_signal_rows_written"] = 0
    row["triggered_fade_created"] = 0
    row["contract_counted_candidate"] = bool(
        source_mode == "live_no_send"
        and exact_lineage
        and not fixture
        and not diagnostic
        and provider in provider_status
    )


def _namespace_artifact_path(context: Any, label: str) -> Path | None:
    if not label:
        return None
    candidate = Path(label)
    namespace_dir = Path(context.namespace_dir).resolve()
    if candidate.is_absolute():
        resolved = candidate.resolve()
        return resolved if resolved.parent == namespace_dir and resolved.is_file() else None
    if ".." in candidate.parts:
        return None
    path = namespace_dir / candidate.name
    return path if path.is_file() else None


def _current_provider_attempt(
    *,
    context: Any,
    row: Mapping[str, Any],
    provider: str,
    ledger_path: str,
    generation_id: str,
) -> dict[str, Any] | None:
    """Return exact current-attempt evidence or fail closed.

    A successful row anywhere in an append-only provider ledger is not enough.
    The candidate, latest rehearsal report, ledger row, and provider source row
    must all name the same unique attempt, profile, and artifact namespace.
    """
    expected_profile = str(row.get("profile") or "").strip()
    expected_namespace = str(row.get("artifact_namespace") or "").strip()
    if expected_profile != str(context.profile) or expected_namespace != str(context.artifact_namespace):
        return None
    report, exact_ledger_rows = _current_provider_report_ledger_rows(
        context=context,
        provider=provider,
        ledger_path=ledger_path,
    )
    provider_run_id = str(report.get("run_id") or "").strip()
    if (
        not report
        or str(report.get("provider_generation_id") or "").strip() != generation_id
    ):
        return None
    if not any(
        item.get("success") is True and item.get("no_send_rehearsal") is True
        for item in exact_ledger_rows
    ):
        return None
    source_file = _namespace_artifact_path(
        context,
        str(row.get("provider_source_artifact") or "").strip(),
    )
    if source_file is None:
        return None
    exact_source_rows = event_request_lineage.generation_rows(
        common.read_jsonl(source_file),
        generation_id,
        provider=provider,
        run_id=provider_run_id,
        profile=expected_profile,
        artifact_namespace=expected_namespace,
    )
    if not exact_source_rows:
        return None
    return {
        "report": report,
        "provider_run_id": provider_run_id,
        "ledger_rows": exact_ledger_rows,
        "source_rows": exact_source_rows,
    }


def _current_provider_report_ledger_rows(
    *,
    context: Any,
    provider: str,
    ledger_path: str,
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    report_name = _PROVIDER_REHEARSAL_REPORTS.get(provider)
    if not report_name or not ledger_path:
        return {}, ()
    report = common.read_json(context.namespace_dir / report_name)
    generation_id = str(report.get("provider_generation_id") or "").strip()
    provider_run_id = str(report.get("run_id") or "").strip()
    if (
        str(report.get("provider") or "").strip() != provider
        or not generation_id
        or not provider_run_id
        or str(report.get("status") or "") not in _PROVIDER_CANDIDATE_SUCCESS_STATUSES
        or report.get("live_call_allowed") is not True
        or report.get("no_send") is not True
        or report.get("research_only") is not True
    ):
        return {}, ()
    ledger_file = _namespace_artifact_path(context, ledger_path)
    if ledger_file is None:
        return {}, ()
    rows = event_request_lineage.generation_rows(
        common.read_jsonl(ledger_file),
        generation_id,
        provider=provider,
        run_id=provider_run_id,
        profile=str(context.profile),
        artifact_namespace=str(context.artifact_namespace),
    )
    return report, rows


def _provider_source_provenance_complete(row: Mapping[str, Any], provider: str) -> bool:
    if provider != "bybit_announcements":
        return True
    event = row.get("official_exchange_event") if isinstance(row.get("official_exchange_event"), Mapping) else {}
    return all(
        str(row.get(key) or event.get(key) or "").strip()
        for key in ("source_url", "title", "published_at")
    )


def _propagate_candidate_lineage_to_core(context: Any, candidates: list[dict[str, Any]]) -> bool:
    core_path = context.namespace_dir / "event_core_opportunities.jsonl"
    core_rows = common.read_jsonl(core_path)
    if not core_rows:
        return False
    by_core = {
        (
            str(row.get("core_opportunity_id") or ""),
            str(row.get("run_id") or ""),
            str(row.get("profile") or ""),
            str(row.get("artifact_namespace") or ""),
        ): row
        for row in candidates
        if all(
            str(row.get(field) or "")
            for field in ("core_opportunity_id", "run_id", "profile", "artifact_namespace")
        )
    }
    fields = (
        "candidate_provenance",
        "candidate_source_mode",
        "contract_counted_candidate",
        "provider",
        "provider_generation_id",
        "provider_request_succeeded",
        "provider_source_artifact",
        "request_ledger_path",
        "market_refresh_artifact",
    )
    changed = False
    updated: list[dict[str, Any]] = []
    for core in core_rows:
        out = dict(core)
        candidate = by_core.get(
            (
                str(out.get("core_opportunity_id") or ""),
                str(out.get("run_id") or ""),
                str(out.get("profile") or ""),
                str(out.get("artifact_namespace") or ""),
            )
        )
        if candidate:
            before = dict(out)
            for field in fields:
                if candidate.get(field) not in (None, ""):
                    out[field] = candidate.get(field)
            changed = changed or out != before
        updated.append(out)
    if changed:
        _write_jsonl(core_path, updated)
    return changed


def _regenerate_lineage_cards(context: Any, candidates: list[dict[str, Any]]) -> None:
    core_read = event_core_opportunity_store.load_core_opportunities(
        context.core_opportunity_store_path,
        latest_run=True,
        include_api=True,
    )
    core_rows = tuple(core_read.rows)
    if not core_rows:
        return
    run_id = str(core_rows[0].get("run_id") or candidates[0].get("run_id") or "") if candidates else ""
    result = event_research_cards.write_research_cards(
        context.research_cards_dir,
        watchlist_entries=(),
        alert_rows=core_rows,
        include_all_alertable=True,
        limit=max(25, len(core_rows)),
        now=common.utc_now(),
        lineage_context={
            "run_id": run_id,
            "profile": context.profile,
            "artifact_namespace": context.artifact_namespace,
            "run_mode": "burn_in",
        },
    )
    event_core_opportunity_store.update_core_opportunity_card_links(
        context.core_opportunity_store_path,
        result.card_paths,
        run_id=run_id or None,
    )


def _candidate_mode_counts(
    context: Any,
    provider_status: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    rows = common.read_jsonl(context.namespace_dir / "event_integrated_radar_candidates.jsonl")
    ledger_counts: dict[str, int] = {}
    ledger_successes: dict[str, int] = {}
    for key, value in provider_status.items():
        ledger_path = str(value.get("request_ledger_path") or "")
        _report, exact_rows = _current_provider_report_ledger_rows(
            context=context,
            provider=key,
            ledger_path=ledger_path,
        )
        ledger_counts[key] = len(exact_rows)
        ledger_successes[key] = sum(
            1
            for item in exact_rows
            if item.get("success") is True and item.get("no_send_rehearsal") is True
        )
    existing_ledgers = [
        str(value.get("request_ledger_path"))
        for key, value in provider_status.items()
        if int(ledger_counts.get(key) or 0) > 0
        and str(value.get("request_ledger_path") or "").strip()
    ]
    source_artifacts = _existing_artifacts(
        context,
        (
            "event_alpha_live_provider_readiness.json",
            "event_coinalyze_preflight.json",
            "event_coinalyze_rehearsal_report.json",
            "event_bybit_announcements_preflight.json",
            "event_bybit_announcements_rehearsal_report.json",
            "event_exchange_announcements.jsonl",
            "event_official_exchange_events.jsonl",
            "event_derivatives_state.jsonl",
            "event_derivatives_crowding_candidates.jsonl",
            "event_alpha_source_coverage.json",
        ),
    )
    candidate_artifacts = _existing_artifacts(
        context,
        (
            "event_integrated_radar_candidates.jsonl",
            "event_core_opportunities.jsonl",
            "event_official_listing_candidates.jsonl",
            "event_fade_short_review_candidates.jsonl",
            "event_alpha_alerts.jsonl",
        ),
    )
    return {
        "candidate_rows": len(rows),
        "integrated_candidate_rows": len(rows),
        "notification_preview_rows": int(
            (context.namespace_dir / "event_alpha_notification_preview.md").exists()
        ),
        "preflight_diagnostic_rows": (
            _json_doc_count(context.namespace_dir / "event_coinalyze_preflight.json")
            + _json_doc_count(context.namespace_dir / "event_bybit_announcements_preflight.json")
        ),
        "readiness_rows": _json_doc_count(
            context.namespace_dir / "event_alpha_live_provider_readiness.json"
        ),
        "source_coverage_rows": _json_doc_count(
            context.namespace_dir / "event_alpha_source_coverage.json"
        ),
        "real_burn_in_candidate_count": sum(
            1 for row in rows if row.get("contract_counted_candidate") is True
        ),
        "contract_counted_candidate_count": sum(
            1 for row in rows if row.get("contract_counted_candidate") is True
        ),
        "fixture_candidate_count": sum(1 for row in rows if _is_fixture_candidate(row)),
        "provider_attempts": sum(
            1 for row in provider_status.values() if row.get("live_call_allowed")
        ),
        "provider_skips": sum(
            1
            for row in provider_status.values()
            if str(row.get("status") or "") != "ready_live_no_send"
        ),
        "provider_successes": sum(
            1 for key in provider_status if int(ledger_successes.get(key) or 0) > 0
        ),
        "request_ledger_rows": ledger_counts,
        "successful_request_ledger_rows": ledger_successes,
        "request_ledgers": sorted(existing_ledgers),
        "source_artifacts": source_artifacts,
        "candidate_artifacts": candidate_artifacts,
        "research_cards_written": len(
            [path for path in context.research_cards_dir.glob("*.md") if path.name != "index.md"]
        )
        if context.research_cards_dir.exists()
        else 0,
        "source_coverage_marker_written": bool(
            (context.namespace_dir / "event_alpha_source_coverage.json").exists()
            or (context.namespace_dir / "event_alpha_source_coverage.md").exists()
        ),
        "readiness_marker_written": bool(
            (context.namespace_dir / "event_live_provider_activation_readiness.json").exists()
            or (context.namespace_dir / "event_live_provider_activation_readiness.md").exists()
        ),
        "notification_preview_marker_written": bool(
            (context.namespace_dir / "event_alpha_notification_preview.md").exists()
        ),
        "review_inbox_path": common.rel_path(
            context.namespace_dir / "event_alpha_daily_review_inbox.json"
        )
        if (context.namespace_dir / "event_alpha_daily_review_inbox.json").exists()
        else "",
        "scorecard_path": common.rel_path(
            context.namespace_dir / "event_alpha_burn_in_scorecard.json"
        )
        if (context.namespace_dir / "event_alpha_burn_in_scorecard.json").exists()
        else "",
        "providers_with_candidates": sorted(
            {
                _infer_candidate_provider(row)
                for row in rows
                if _infer_candidate_provider(row) in provider_status
            }
        ),
    }


def _json_doc_count(path: Path) -> int:
    return 1 if common.read_json(path) else 0


def _existing_artifacts(context: Any, names: tuple[str, ...]) -> list[str]:
    return [
        common.rel_path(context.namespace_dir / name)
        for name in names
        if (context.namespace_dir / name).exists()
    ]


def _candidate_manifest_status(
    counts: Mapping[str, Any],
    provider_status: Mapping[str, Mapping[str, Any]],
    *,
    completed: bool,
) -> str:
    if not completed:
        return "running"
    if int(counts.get("contract_counted_candidate_count") or 0) > 0:
        return "completed_with_contract_candidates"
    if int(counts.get("fixture_candidate_count") or 0) > 0:
        return "completed_fixture_candidates_only"
    if not any(bool(row.get("live_call_allowed")) for row in provider_status.values()):
        return "completed_no_candidate_providers"
    return "completed_no_candidates"


def _request_ledger_for_provider(provider: str, context: Any) -> str:
    if provider == "coinalyze":
        return common.rel_path(context.namespace_dir / COINALYZE_REQUEST_LEDGER)
    if provider in {"bybit", "bybit_announcements"}:
        return common.rel_path(context.namespace_dir / BYBIT_REQUEST_LEDGER)
    return ""


def _infer_candidate_provider(row: Mapping[str, Any]) -> str:
    explicit = " ".join(
        str(row.get(field) or "")
        for field in ("provider", "source_provider")
    ).casefold()
    if "bybit" in explicit:
        return "bybit_announcements"
    if "coinalyze" in explicit:
        return "coinalyze"
    text = " ".join(
        str(row.get(field) or "")
        for field in (
            "provider",
            "source_provider",
            "source_origin",
            "source_pack",
            "source_pack_id",
        )
    ).casefold()
    if "coinalyze" in text or "derivative" in text or "funding" in text:
        return "coinalyze"
    if "bybit" in text:
        return "bybit_announcements"
    return str(
        row.get("provider")
        or row.get("source_provider")
        or row.get("source_origin")
        or "unknown"
    )


def _source_pack_for_provider(provider: str) -> str:
    if provider == "coinalyze":
        return "derivatives_crowding"
    if provider in {"bybit", "bybit_announcements"}:
        return "official_exchange_listing_pack"
    return "unknown"


def _providers_with_status(
    provider_status: Mapping[str, Mapping[str, Any]],
    *statuses: str,
) -> list[str]:
    wanted = set(statuses)
    return sorted(
        key
        for key, row in provider_status.items()
        if str(row.get("status") or "") in wanted
    )


def _candidate_mode_next_steps(
    provider_status: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    steps: list[str] = []
    for key, row in sorted(provider_status.items()):
        status = str(row.get("status") or "")
        if status == "skipped_missing_config":
            steps.append(f"configure {key} credentials/settings before candidate-mode sampling")
        elif status in {"skipped_live_calls_disabled", "live_call_blocked_by_default"}:
            steps.append(
                f"set explicit allow flag for {key} to run guarded no-send candidate sampling"
            )
        elif status == "request_budget_not_small":
            steps.append(f"set a small request budget for {key}")
    return steps or ["review candidate artifacts and labels; no thresholds auto-apply"]


def _is_fixture_candidate(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(row.get(field) or "")
        for field in (
            "run_mode",
            "profile",
            "artifact_namespace",
            "source_origin",
            "source_pack",
            "candidate_source_mode",
        )
    ).casefold()
    return bool(
        row.get("fixture_only") is True
        or row.get("test_fixture") is True
        or "fixture" in text
        or "smoke" in text
        or "mocked_fixture" in text
    )


def _configured_value(env_name: str, config_value: Any) -> str:
    return str(os.getenv(env_name, "") or config_value or "").strip()


def _env_truthy(name: str) -> bool:
    return str(os.getenv(name) or "").strip().casefold() in _TRUTHY


def _env_csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except ValueError:
        return 0


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
