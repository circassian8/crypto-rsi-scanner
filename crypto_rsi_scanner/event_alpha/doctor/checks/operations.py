"""Event Alpha burn-in operation artifact checks."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .. import check_registry
from . import market_snapshot_units
from ._utils import Messages, ctx_mapping, ctx_value
from ...artifacts import paths as event_artifact_paths
from ...artifacts import fingerprints as event_alpha_fingerprints
from ...artifacts import operator_state as event_alpha_operator_state
from ...operations import common
from ...operations import daily_operations_publication
from ...operations import market_provenance as event_market_provenance
from ...providers import request_lineage as event_request_lineage
from ...radar import source_independence_store as event_source_independence_store


_PROVIDER_REHEARSAL_REPORTS = {
    "coinalyze": "event_coinalyze_rehearsal_report.json",
    "bybit_announcements": "event_bybit_announcements_rehearsal_report.json",
}
_PROVIDER_SUCCESS_STATUSES = {
    "live_rehearsal_success",
    "live_rehearsal_partial",
    "live_rehearsal_no_results",
}


def apply_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    daily_run = ctx_mapping(ctx, "daily_burn_in_run")
    candidate_mode_manifest = ctx_mapping(ctx, "candidate_mode_manifest")
    scorecard = ctx_mapping(ctx, "burn_in_scorecard")
    source_yield = ctx_mapping(ctx, "source_yield_report")
    review_inbox = ctx_mapping(ctx, "daily_review_inbox")
    archive_manifest = ctx_mapping(ctx, "burn_in_archive_manifest")
    _check_daily_run(ctx, daily_run, blockers, warnings)
    _check_candidate_mode(ctx, daily_run, candidate_mode_manifest, blockers, warnings)
    _check_scorecard(scorecard, blockers)
    _check_source_yield(source_yield, blockers)
    _check_review_inbox(ctx, review_inbox, blockers, warnings)
    _check_archive_manifest(archive_manifest, blockers)
    _check_targeted_market_refresh(ctx, blockers)
    market_snapshot_units.apply_checks(ctx, blockers)
    _check_operator_state(ctx, blockers, warnings)
    _check_source_independence_store(ctx, blockers)
    _check_daily_operations_publication(ctx, blockers)


def _check_source_independence_store(
    ctx: object,
    blockers: Messages,
) -> None:
    """Resolve every bounded persisted reference before strict authority."""

    namespace_dir_value = ctx_value(ctx, "namespace_dir", None)
    if not namespace_dir_value:
        return
    namespace_dir = Path(str(namespace_dir_value)).expanduser()
    references: list[Mapping[str, Any]] = []
    for filename in (
        "event_integrated_radar_candidates.jsonl",
        "event_integrated_radar_outcomes.jsonl",
        "event_core_opportunities.jsonl",
        "event_integrated_radar_notification_deliveries.jsonl",
        "event_alpha_alerts.jsonl",
        "event_evidence_acquisition.jsonl",
        "event_impact_hypotheses.jsonl",
        "event_incidents.jsonl",
        "event_watchlist_state.jsonl",
    ):
        for row in common.read_jsonl(namespace_dir / filename):
            try:
                references.extend(_source_independence_references(row))
            except ValueError as exc:
                blockers.append(
                    check_registry.format_check_message(
                        "namespace.operator_artifact_coherence",
                        f"source_independence_reference_scan_failed={filename}:{exc}",
                    )
                )
                return
    if not references:
        return
    loaded = event_alpha_operator_state.load_operator_state(namespace_dir)
    artifacts = (
        loaded.state.get("artifacts")
        if loaded.valid
        and isinstance(loaded.state, Mapping)
        and isinstance(loaded.state.get("artifacts"), Mapping)
        else {}
    )
    store_entry = artifacts.get("source_independence_contract_store")
    if not isinstance(store_entry, Mapping) or store_entry.get("status") != "current":
        blockers.append(
            check_registry.format_check_message(
                "namespace.operator_artifact_coherence",
                "source_independence_store_not_bound_to_operator_state",
            )
        )
    elif store_entry.get("path") != event_source_independence_store.STORE_DIRECTORY:
        blockers.append(
            check_registry.format_check_message(
                "namespace.operator_artifact_coherence",
                "source_independence_store_operator_path_mismatch",
            )
        )
    seen: set[bytes] = set()
    for reference in references:
        reference_errors = event_source_independence_store.validate_reference(
            reference
        )
        if reference_errors:
            blockers.append(
                check_registry.format_check_message(
                    "namespace.operator_artifact_coherence",
                    "source_independence_reference_invalid="
                    + ",".join(reference_errors)[:240],
                )
            )
            continue
        try:
            key = event_alpha_fingerprints.canonical_json_bytes(dict(reference))
        except event_alpha_fingerprints.FingerprintError:
            blockers.append(
                check_registry.format_check_message(
                    "namespace.operator_artifact_coherence",
                    "source_independence_reference_canonicalization_failed",
                )
            )
            continue
        if key in seen:
            continue
        seen.add(key)
        try:
            event_source_independence_store.resolve(namespace_dir, reference)
        except event_source_independence_store.SourceIndependenceStoreError as exc:
            blockers.append(
                check_registry.format_check_message(
                    "namespace.operator_artifact_coherence",
                    "source_independence_reference_unresolvable="
                    + str(exc)[:240],
                )
            )


def _source_independence_references(
    value: Any,
    *,
    max_nodes: int = 100_000,
) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    stack = [value]
    visited = 0
    while stack:
        current = stack.pop()
        visited += 1
        if visited > max_nodes:
            raise ValueError("node_limit_exceeded")
        if isinstance(current, Mapping):
            if (
                current.get("schema_id")
                == event_source_independence_store.REFERENCE_SCHEMA_ID
            ):
                found.append(current)
                continue
            stack.extend(current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    return found


def _check_daily_operations_publication(
    ctx: object,
    blockers: Messages,
) -> None:
    """Validate v1.1 receipts only after a namespace enters that contract."""

    namespace_dir_value = ctx_value(ctx, "namespace_dir", None)
    if not namespace_dir_value:
        return
    namespace_dir = Path(str(namespace_dir_value)).expanduser()
    managed = False
    for filename in (
        daily_operations_publication.PREPUBLICATION_AUDIT_FILENAME,
        daily_operations_publication.PUBLICATION_RECEIPT_FILENAME,
        daily_operations_publication.OPERATIONS_RECEIPT_FILENAME,
    ):
        try:
            (namespace_dir / filename).lstat()
        except OSError:
            continue
        managed = True
        break
    if not managed:
        try:
            canonically_managed = (
                daily_operations_publication.is_daily_operations_managed_namespace(
                    namespace_dir.parent,
                    namespace_dir.name,
                )
            )
        except Exception:  # noqa: BLE001 - doctor remains fail closed
            canonically_managed = True
        if not canonically_managed:
            return
        probe = daily_operations_publication.validate_final_publication_contract(
            namespace_dir.parent,
            namespace_dir.name,
        )
        # Before publication the new namespace is not current.  Keep that
        # strict-doctor phase valid even though the root cycle ledger already
        # identifies it as Daily Operations managed.
        if not probe.currently_authoritative:
            return
        managed = True
        validation = probe
    else:
        validation = daily_operations_publication.validate_final_publication_contract(
            namespace_dir.parent,
            namespace_dir.name,
        )
    if validation.currently_authoritative:
        validation = daily_operations_publication.validate_final_publication_contract(
            namespace_dir.parent,
            namespace_dir.name,
            require_current=True,
            require_operations=True,
        )
    for error in validation.errors:
        blockers.append(
            check_registry.format_check_message(
                "namespace.daily_operations_publication_contract",
                error,
            )
        )


def _check_targeted_market_refresh(ctx: object, blockers: Messages) -> None:
    namespace_dir_value = ctx_value(ctx, "namespace_dir", None)
    if not namespace_dir_value:
        return
    namespace_dir = Path(str(namespace_dir_value)).expanduser()
    report = common.read_json(namespace_dir / "event_targeted_market_refresh_report.json")
    ledger_rows = common.read_jsonl(namespace_dir / "event_targeted_market_refresh_ledger.jsonl")
    if not report and not ledger_rows:
        return
    if not report:
        _targeted_refresh_block(blockers, "targeted_market_refresh_ledger_without_report")
        return
    refresh_id = str(report.get("refresh_run_id") or "")
    run_id = str(report.get("run_id") or "")
    exact_rows = [
        row for row in ledger_rows
        if str(row.get("targeted_market_refresh_id") or "") == refresh_id
    ]
    request_count = int(report.get("request_count") or 0)
    selected_assets = int(report.get("selected_assets") or 0)
    timeout_seconds = float(report.get("timeout_seconds") or 0.0)
    if not refresh_id or not run_id:
        _targeted_refresh_block(blockers, "targeted_market_refresh_missing_exact_run_lineage")
    if request_count not in {0, 1} or selected_assets > 20 or timeout_seconds <= 0:
        _targeted_refresh_block(
            blockers,
            f"targeted_market_refresh_budget_invalid=requests:{request_count},assets:{selected_assets},timeout:{timeout_seconds}",
            check_id="integrated_radar.targeted_market_refresh_budget",
        )
    if selected_assets != len(exact_rows):
        _targeted_refresh_block(blockers, f"targeted_market_refresh_selected_ledger_mismatch={selected_assets}!={len(exact_rows)}")
    canonical_assets = [str(row.get("canonical_asset_id") or "") for row in exact_rows]
    if len(canonical_assets) != len(set(canonical_assets)):
        _targeted_refresh_block(blockers, "targeted_market_refresh_duplicate_canonical_asset")
    snapshots = [
        row for row in common.read_jsonl(namespace_dir / "event_market_state_snapshots.jsonl")
        if str(row.get("targeted_market_refresh_id") or "") == refresh_id
    ]
    snapshot_assets = {str(row.get("canonical_asset_id") or "") for row in snapshots}
    refreshed_assets = {
        str(row.get("canonical_asset_id") or "")
        for row in exact_rows
        if str(row.get("status") or "") == "refreshed"
    }
    if refreshed_assets != snapshot_assets:
        _targeted_refresh_block(blockers, "targeted_market_refresh_snapshot_ledger_mismatch")
    if int(report.get("refreshed_assets") or 0) != len(refreshed_assets):
        _targeted_refresh_block(blockers, "targeted_market_refresh_report_refreshed_count_mismatch")
    persisted = sum(
        1 for row in common.read_jsonl(namespace_dir / "event_market_state_snapshots.jsonl")
        if str(row.get("run_id") or "") == run_id
    )
    if int(report.get("persisted_snapshot_rows") or 0) != persisted:
        _targeted_refresh_block(blockers, "targeted_market_refresh_persisted_snapshot_count_mismatch")
    for row in exact_rows:
        if str(row.get("run_id") or "") != run_id:
            _targeted_refresh_block(blockers, "targeted_market_refresh_ledger_run_mismatch")
        if row.get("research_only") is not True or row.get("no_send_rehearsal") is not True:
            _targeted_refresh_block(blockers, "targeted_market_refresh_safety_missing")
        if any(int(row.get(field) or 0) != 0 for field in (
            "strict_alerts_created", "telegram_sends", "trades_created",
            "paper_trades_created", "normal_rsi_signal_rows_written", "triggered_fade_created",
        )):
            _targeted_refresh_block(blockers, "targeted_market_refresh_side_effect_claim")
        duration = float(row.get("duration_seconds") or 0.0)
        timeout = float(row.get("timeout_seconds") or 0.0)
        if duration > timeout and str(row.get("status") or "") != "timeout":
            _targeted_refresh_block(
                blockers,
                "targeted_market_refresh_timeout_not_enforced",
                check_id="integrated_radar.targeted_market_refresh_budget",
            )
    integrated_rows = common.read_jsonl(namespace_dir / "event_integrated_radar_candidates.jsonl")
    by_asset = {
        str(row.get("canonical_asset_id") or row.get("coin_id") or "").casefold(): row
        for row in integrated_rows
    }
    for asset in refreshed_assets:
        candidate = by_asset.get(asset.casefold())
        if candidate is not None and (
            candidate.get("market_refresh_success") is not True
            or not str(candidate.get("market_refresh_artifact") or "").strip()
        ):
            _targeted_refresh_block(blockers, f"targeted_market_refresh_candidate_propagation_missing={asset}")


def _targeted_refresh_block(
    blockers: Messages,
    detail: str,
    *,
    check_id: str = "integrated_radar.targeted_market_refresh_lineage",
) -> None:
    blockers.append(check_registry.format_check_message(check_id, detail))


def _check_operator_state(ctx: object, blockers: Messages, warnings: Messages) -> None:
    if not hasattr(ctx, "latest_run_id"):
        return
    namespace_dir_value = ctx_value(ctx, "namespace_dir", None)
    if not namespace_dir_value:
        return
    namespace_dir = Path(str(namespace_dir_value)).expanduser()
    loaded = event_alpha_operator_state.load_operator_state(namespace_dir)
    if not loaded.exists:
        latest_run_id = str(ctx_value(ctx, "latest_run_id", "") or "")
        persisted_latest = bool(
            latest_run_id
            and _run_ledger_contains(
                namespace_dir,
                latest_run_id,
                run_ledger_path=ctx_value(ctx, "run_ledger_path", None),
            )
        )
        target = blockers if persisted_latest else warnings
        target.append(
            check_registry.format_check_message(
                (
                    "namespace.operator_state_missing"
                    if persisted_latest
                    else "namespace.operator_state_missing_legacy"
                ),
                (
                    f"operator_state_missing_for_latest_run={latest_run_id}"
                    if persisted_latest
                    else "operator_state_missing_legacy_namespace"
                ),
            )
        )
        return
    if not loaded.valid or loaded.state is None:
        blockers.append(
            check_registry.format_check_message(
                "namespace.operator_state_invalid",
                f"operator_state_invalid={loaded.error or 'unknown'}",
            )
        )
        return
    state = loaded.state
    latest_run_id = str(ctx_value(ctx, "latest_run_id", "") or "")
    state_run_id = str(state.get("run_id") or "")
    if latest_run_id and state_run_id != latest_run_id:
        blockers.append(
            check_registry.format_check_message(
                "namespace.operator_state_run_mismatch",
                f"operator_state_run_id={state_run_id or 'missing'} latest_run_id={latest_run_id}",
            )
        )
    if str(state.get("artifact_namespace") or "") != str(ctx_value(ctx, "artifact_namespace", "") or ""):
        blockers.append(
            check_registry.format_check_message(
                "namespace.operator_state_run_mismatch",
                "operator_state_artifact_namespace_mismatch",
            )
        )
    expected_profile = str(ctx_value(ctx, "profile", "") or "")
    if expected_profile and str(state.get("profile") or "") != expected_profile:
        blockers.append(
            check_registry.format_check_message(
                "namespace.operator_state_run_mismatch",
                "operator_state_profile_mismatch",
            )
        )
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), Mapping) else {}
    for name, entry_value in artifacts.items():
        if not isinstance(entry_value, Mapping):
            blockers.append(
                check_registry.format_check_message(
                    "namespace.operator_state_invalid",
                    f"operator_artifact_not_object={name}",
                )
            )
            continue
        status = str(entry_value.get("status") or "")
        if str(entry_value.get("run_id") or "") != state_run_id:
            blockers.append(
                check_registry.format_check_message(
                    "namespace.operator_state_run_mismatch",
                    f"operator_artifact_run_mismatch={name}",
                )
            )
        if status != event_alpha_operator_state.STATUS_CURRENT:
            if not str(entry_value.get("reason") or "").strip():
                blockers.append(
                    check_registry.format_check_message(
                        "namespace.operator_artifact_coherence",
                        f"operator_artifact_non_current_missing_reason={name}",
                    )
                )
            continue
        resolved = _resolve_operator_artifact_path(namespace_dir, entry_value.get("path"))
        if resolved is None or not resolved.exists():
            blockers.append(
                check_registry.format_check_message(
                    "namespace.operator_artifact_coherence",
                    f"operator_artifact_current_path_missing={name}",
                )
            )
            continue
        if name == "notification_preview":
            try:
                header = resolved.read_text(encoding="utf-8", errors="replace")[:4096]
            except OSError:
                header = ""
            if not event_alpha_operator_state.text_has_exact_run_id(header, state_run_id):
                blockers.append(
                    check_registry.format_check_message(
                        "namespace.operator_artifact_coherence",
                        "operator_notification_preview_run_mismatch",
                    )
                )
        elif name in {"source_coverage_json", "provider_readiness_json"}:
            try:
                payload = json.loads(resolved.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            if not isinstance(payload, Mapping) or str(payload.get("run_id") or "") != state_run_id:
                blockers.append(
                    check_registry.format_check_message(
                        "namespace.operator_artifact_coherence",
                        f"operator_artifact_embedded_run_mismatch={name}",
                    )
                )
        elif name in {"source_coverage_md", "provider_readiness_md"}:
            try:
                header = resolved.read_text(encoding="utf-8", errors="replace")[:8192]
            except OSError:
                header = ""
            if not re.search(rf"(?m)^-?\s*run_id:\s*{re.escape(state_run_id)}\s*$", header):
                blockers.append(
                    check_registry.format_check_message(
                        "namespace.operator_artifact_coherence",
                        f"operator_artifact_embedded_run_mismatch={name}",
                    )
                )


def _resolve_operator_artifact_path(namespace_dir: Path, value: object) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    raw = Path(text).expanduser()
    if raw.is_absolute():
        return raw
    return namespace_dir / raw


def _run_ledger_contains(
    namespace_dir: Path,
    run_id: str,
    *,
    run_ledger_path: str | Path | None = None,
) -> bool:
    path = (
        Path(run_ledger_path).expanduser()
        if run_ledger_path not in (None, "")
        else namespace_dir / "event_alpha_runs.jsonl"
    )
    if not path.exists():
        return False
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, Mapping) and str(row.get("run_id") or "") == run_id:
                return True
    except OSError:
        return False
    return False


def _check_daily_run(ctx: object, daily_run: Mapping[str, Any], blockers: Messages, warnings: Messages) -> None:
    if not daily_run and _is_burn_in_namespace(ctx):
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_run_missing",
                "daily_burn_in_run_missing",
            )
        )
        return
    if not daily_run:
        return
    steps = [row for row in daily_run.get("steps") or [] if isinstance(row, Mapping)]
    missing_status = sum(1 for row in steps if not str(row.get("status") or "").strip())
    if missing_status:
        warnings.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_run_step_status",
                f"daily_burn_in_run_step_missing_status={missing_status}",
            )
        )
    missing_required = sum(1 for row in steps if row.get("required") is None)
    if missing_required:
        warnings.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_run_step_required",
                f"daily_burn_in_run_step_missing_required={missing_required}",
            )
        )
    executable_steps = [row for row in steps if str(row.get("status") or "").strip() != "skipped" and row.get("command")]
    missing_timeout = sum(1 for row in executable_steps if row.get("timeout_seconds") in (None, ""))
    if missing_timeout:
        warnings.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_run_step_timeout",
                f"daily_burn_in_run_step_missing_timeout={missing_timeout}",
            )
        )
    skipped_without_reason = sum(
        1
        for row in steps
        if str(row.get("status") or "").strip() == "skipped"
        and not str(row.get("skip_reason") or "").strip()
    )
    if skipped_without_reason:
        warnings.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_run_step_skip_reason",
                f"daily_burn_in_run_step_skipped_missing_reason={skipped_without_reason}",
            )
        )
    side_effects = sum(1 for key in _FORBIDDEN_SIDE_EFFECT_FIELDS if _int(daily_run.get(key)) != 0)
    if side_effects:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_run_side_effects",
                f"daily_burn_in_run_forbidden_side_effect_claim={side_effects}",
            )
        )
    integrated_conflicts = ctx_mapping(ctx, "integrated_conflicts")
    if _int(integrated_conflicts.get("integrated_preview_lane_mismatch")):
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_integrated_preview",
                "daily_burn_in_integrated_preview_mismatch",
            )
        )
    _check_step_tails(steps, blockers, warnings)


def _check_candidate_mode(ctx: object, daily_run: Mapping[str, Any], candidate_mode_manifest: Mapping[str, Any], blockers: Messages, warnings: Messages) -> None:
    if daily_run.get("candidate_mode") is True and not candidate_mode_manifest:
        warnings.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_candidate_mode_manifest",
                "daily_burn_in_candidate_mode_manifest_missing",
            )
        )
    candidate_rows = [
        row for row in ctx_value(ctx, "integrated_candidates", []) or []
        if isinstance(row, Mapping)
        and (
            row.get("measurement_program")
            or event_market_provenance.market_provenance_values(row).get("measurement_program")
        )
        != event_market_provenance.DECISION_RADAR_MEASUREMENT_PROGRAM
    ]
    missing_provenance = 0
    missing_ledger = 0
    fixture_counted = 0
    preflight_counted = 0
    for row in candidate_rows:
        if row.get("contract_counted_candidate") is not True:
            continue
        required_fields = (
            "candidate_provenance", "provider", "source_pack", "source_origin",
            "provider_generation_id", "provider_source_artifact",
        )
        if any(not str(row.get(field) or "").strip() for field in required_fields):
            missing_provenance += 1
        source_mode = str(row.get("candidate_source_mode") or "").strip()
        if source_mode == "live_no_send" and not _exact_contract_ledger_valid(ctx, row):
            missing_ledger += 1
        if source_mode in {"mocked_fixture", "fixture"} or row.get("fixture_only") is True or row.get("test_fixture") is True:
            fixture_counted += 1
        if source_mode in {"preflight_only", "readiness_only"}:
            preflight_counted += 1
    if missing_provenance:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_candidate_provenance",
                f"daily_burn_in_contract_candidate_missing_provenance={missing_provenance}",
            )
        )
    if missing_ledger:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_candidate_live_ledger",
                f"daily_burn_in_live_candidate_missing_request_ledger={missing_ledger}",
            )
        )
    if fixture_counted:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_scorecard_fixture_real",
                f"daily_burn_in_fixture_candidate_counted_as_real={fixture_counted}",
            )
        )
    if preflight_counted:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.source_yield_preflight_candidate_yield",
                f"daily_burn_in_preflight_row_counted_as_candidate={preflight_counted}",
            )
        )
    _check_candidate_mode_fixture_cards(ctx, candidate_rows, candidate_mode_manifest, blockers)
    _check_candidate_mode_safety_counters(candidate_mode_manifest, blockers)


def _exact_contract_ledger_valid(ctx: object, row: Mapping[str, Any]) -> bool:
    ledger_label = str(row.get("request_ledger_path") or "").strip()
    generation_id = str(row.get("provider_generation_id") or "").strip()
    provider = _contract_provider(row)
    profile = str(row.get("profile") or "").strip()
    artifact_namespace = str(row.get("artifact_namespace") or "").strip()
    namespace_dir = Path(ctx_value(ctx, "namespace_dir", "."))
    if (
        not ledger_label
        or not generation_id
        or not provider
        or not profile
        or not artifact_namespace
        or row.get("provider_request_succeeded") is not True
    ):
        return False
    ctx_profile = str(ctx_value(ctx, "profile", profile) or profile)
    ctx_namespace = str(ctx_value(ctx, "artifact_namespace", artifact_namespace) or artifact_namespace)
    if profile != ctx_profile or artifact_namespace != ctx_namespace:
        return False
    if provider == "coingecko":
        return _market_no_send_contract_ledger_valid(
            namespace_dir,
            row,
            generation_id=generation_id,
            profile=profile,
            artifact_namespace=artifact_namespace,
        )
    report_name = _PROVIDER_REHEARSAL_REPORTS.get(provider)
    if not report_name:
        return False
    report = common.read_json(namespace_dir / report_name)
    provider_run_id = str(report.get("run_id") or "").strip()
    if (
        str(report.get("provider") or "").strip() != provider
        or str(report.get("provider_generation_id") or "").strip() != generation_id
        or not provider_run_id
        or str(report.get("status") or "") not in _PROVIDER_SUCCESS_STATUSES
        or report.get("live_call_allowed") is not True
        or report.get("no_send") is not True
        or report.get("research_only") is not True
    ):
        return False
    ledger_path = _contract_artifact_path(namespace_dir, ledger_label)
    source_path = _contract_artifact_path(
        namespace_dir,
        str(row.get("provider_source_artifact") or "").strip(),
    )
    if ledger_path is None or source_path is None:
        return False
    ledger_rows = event_request_lineage.generation_rows(
        common.read_jsonl(ledger_path),
        generation_id,
        provider=provider,
        run_id=provider_run_id,
        profile=profile,
        artifact_namespace=artifact_namespace,
    )
    source_rows = event_request_lineage.generation_rows(
        common.read_jsonl(source_path),
        generation_id,
        provider=provider,
        run_id=provider_run_id,
        profile=profile,
        artifact_namespace=artifact_namespace,
    )
    if provider == "bybit_announcements" and not _contract_bybit_source_fields_complete(row):
        return False
    return bool(source_rows) and any(
        item.get("success") is True and item.get("no_send_rehearsal") is True
        for item in ledger_rows
    )


def _market_no_send_contract_ledger_valid(
    namespace_dir: Path,
    row: Mapping[str, Any],
    *,
    generation_id: str,
    profile: str,
    artifact_namespace: str,
) -> bool:
    provenance = event_market_provenance.market_provenance_values(row)
    if not provenance or provenance.get("provenance_contract_valid") is not True:
        return False
    if (
        provenance.get("candidate_source_mode") != "live_no_send"
        or provenance.get("data_acquisition_mode") != "live_provider"
        or provenance.get("provider") != "coingecko"
        or provenance.get("provider_generation_id") != generation_id
        or provenance.get("live_provider_authorized") is not True
        or provenance.get("provider_call_attempted") is not True
        or provenance.get("provider_call_succeeded") is not True
        or provenance.get("burn_in_counted") is not True
        or provenance.get("cache_status") != "write_through"
    ):
        return False
    ledger_path = _contract_artifact_path(
        namespace_dir,
        str(provenance.get("request_ledger_path") or ""),
    )
    source_path = _contract_artifact_path(
        namespace_dir,
        str(provenance.get("provider_source_artifact") or ""),
    )
    if ledger_path is None or source_path is None or ledger_path == source_path:
        return False
    if (
        _sha256_file(ledger_path) != provenance.get("request_ledger_sha256")
        or _sha256_file(source_path)
        != provenance.get("provider_source_artifact_sha256")
    ):
        return False
    ledger = common.read_json(ledger_path)
    source = common.read_json(source_path)
    identity = {
        "run_id": generation_id,
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "provider": "coingecko",
    }
    if any(ledger.get(field) != value for field, value in identity.items()):
        return False
    if any(source.get(field) != value for field, value in identity.items()):
        return False
    ledger_contract = {
        "row_type": "event_market_no_send_request_ledger",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "live_provider_authorized": True,
        "fixture_mode": False,
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "provider_source_artifact": source_path.name,
        "provider_source_artifact_sha256": _sha256_file(source_path),
        "provenance_contract_valid": True,
        "burn_in_counted": True,
        "no_send": True,
        "research_only": True,
    }
    source_contract = {
        "row_type": "event_market_no_send_source_cache",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "provenance_contract_valid": True,
        "burn_in_counted": True,
        "no_send": True,
        "research_only": True,
    }
    return (
        all(ledger.get(field) == value for field, value in ledger_contract.items())
        and all(source.get(field) == value for field, value in source_contract.items())
        and all(int(ledger.get(field) or 0) == 0 for field in _FORBIDDEN_SIDE_EFFECT_FIELDS)
        and all(int(source.get(field) or 0) == 0 for field in _FORBIDDEN_SIDE_EFFECT_FIELDS)
    )


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _contract_provider(row: Mapping[str, Any]) -> str:
    provider = str(row.get("provider") or row.get("source_provider") or "").strip()
    return "bybit_announcements" if "bybit" in provider.casefold() else provider


def _contract_artifact_path(namespace_dir: Path, label: str) -> Path | None:
    candidate = Path(label)
    if not label:
        return None
    namespace_dir = namespace_dir.resolve()
    if candidate.is_absolute():
        resolved = candidate.resolve()
        return resolved if resolved.parent == namespace_dir and resolved.is_file() else None
    if ".." in candidate.parts:
        return None
    path = namespace_dir / candidate.name
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return None
    return resolved if resolved.parent == namespace_dir and resolved.is_file() else None


def _contract_bybit_source_fields_complete(row: Mapping[str, Any]) -> bool:
    event = row.get("official_exchange_event") if isinstance(row.get("official_exchange_event"), Mapping) else {}
    return all(
        str(row.get(key) or event.get(key) or "").strip()
        for key in ("source_url", "title", "published_at")
    )


def _check_scorecard(scorecard: Mapping[str, Any], blockers: Messages) -> None:
    if not scorecard:
        return
    contract_counted = _int(scorecard.get("contract_counted_candidate_count"))
    real_candidates = _int(scorecard.get("real_burn_in_candidate_count"))
    if contract_counted > real_candidates:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.burn_in_scorecard_contract_count",
                "burn_in_scorecard_contract_count_exceeds_real_candidates",
            )
        )
    if scorecard.get("evidence_scope") == "real_burn_in_evidence" and contract_counted == 0:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.burn_in_scorecard_real_scope",
                "burn_in_scorecard_real_scope_without_contract_candidates",
            )
        )
    support_rows = (
        _int(scorecard.get("fixture_candidates"))
        + _int(scorecard.get("fixture_candidate_count"))
        + _int(scorecard.get("preflight_diagnostic_rows"))
        + _int(scorecard.get("readiness_rows"))
        + _int(scorecard.get("source_coverage_rows"))
    )
    if support_rows and contract_counted and contract_counted > real_candidates:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.burn_in_scorecard_contract_count",
                "burn_in_scorecard_counts_support_rows_as_real_candidates",
            )
        )
    if _int(scorecard.get("fixture_candidate_count")) and contract_counted > real_candidates:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_scorecard_fixture_real",
                "daily_burn_in_scorecard_counts_fixture_as_real_candidate",
            )
        )


def _check_source_yield(source_yield: Mapping[str, Any], blockers: Messages) -> None:
    if not source_yield:
        return
    if "real_candidate_rows" not in source_yield:
        return
    real_rows = _int(source_yield.get("real_candidate_rows"))
    provider_candidate_rows = sum(
        _int(row.get("candidate_count"))
        for row in (source_yield.get("providers") or {}).values()
        if isinstance(row, Mapping)
    )
    if provider_candidate_rows > real_rows:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.source_yield_real_candidate_rows",
                "source_yield_counts_non_real_rows_as_candidate_yield",
            )
        )
    if (_int(source_yield.get("provider_readiness_rows")) or _int(source_yield.get("preflight_diagnostic_rows"))) and real_rows == 0 and provider_candidate_rows:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.source_yield_preflight_candidate_yield",
                "source_yield_counts_readiness_or_preflight_as_candidate_yield",
            )
        )


def _check_review_inbox(ctx: object, review_inbox: Mapping[str, Any], blockers: Messages, warnings: Messages) -> None:
    if not review_inbox:
        return
    items = [row for row in review_inbox.get("items") or [] if isinstance(row, Mapping)]
    inbox_blockers = [str(item) for item in review_inbox.get("blockers") or [] if str(item or "").strip()]
    if inbox_blockers:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.review_inbox_blockers",
                f"daily_review_inbox_blockers={len(inbox_blockers)}",
            )
        )
    absolute_card_paths = _count_absolute_card_path_fields(review_inbox)
    if absolute_card_paths:
        blockers.append(
            check_registry.format_check_message(
                "paths.review_inbox_card_path_absolute",
                f"review_inbox_operator_card_paths_absolute={absolute_card_paths}",
            )
        )
    markdown = _review_inbox_markdown(ctx)
    if markdown and event_artifact_paths.has_operator_absolute_path(markdown):
        blockers.append(
            check_registry.format_check_message(
                "paths.review_inbox_markdown_absolute_path",
                "review_inbox_markdown_contains_local_absolute_path",
            )
        )
    missing_card_or_reason = sum(
        1
        for row in items
        if not str(row.get("card_path") or "").strip()
        and not str(row.get("card_not_available_reason") or "").strip()
    )
    if missing_card_or_reason:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.review_inbox_missing_card_or_reason",
                f"review_inbox_selected_items_missing_card_path_or_reason={missing_card_or_reason}",
            )
        )
    missing_provenance = sum(1 for row in items if not row.get("candidate_provenance") or not row.get("source_artifact"))
    if missing_provenance:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.review_inbox_selected_provenance",
                f"review_inbox_selected_items_missing_provenance={missing_provenance}",
            )
        )
    hidden_selected = sum(1 for row in items if row.get("diagnostic_only") is True or row.get("preflight_only") is True)
    if hidden_selected:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.review_inbox_hidden_default",
                f"review_inbox_selected_diagnostic_or_preflight_only={hidden_selected}",
            )
        )
    if items and "generic_context_source_downranked" in (items[0].get("downrank_reason_codes") or []):
        accepted_below = any(
            "accepted_evidence_no_market_confirmation" in (row.get("review_value_reason_codes") or [])
            or "accepted_evidence_found" in (row.get("review_value_reason_codes") or [])
            for row in items[1:]
        )
        if accepted_below:
            warnings.append(
                check_registry.format_check_message(
                    "outcomes.review_inbox_generic_context_priority",
                    "review_inbox_generic_context_outranks_accepted_evidence",
                )
            )


def _count_absolute_card_path_fields(value: Any) -> int:
    if isinstance(value, Mapping):
        count = 0
        for key, item in value.items():
            key_text = str(key)
            if key_text.endswith("_abs_debug"):
                continue
            if "card_path" in key_text.casefold() and event_artifact_paths.has_operator_absolute_path(item):
                count += 1
            count += _count_absolute_card_path_fields(item)
        return count
    if isinstance(value, (list, tuple, set)):
        return sum(_count_absolute_card_path_fields(item) for item in value)
    return 0


def _review_inbox_markdown(ctx: object) -> str:
    explicit = str(ctx_value(ctx, "daily_review_inbox_markdown", "") or "")
    if explicit:
        return explicit
    namespace_dir = ctx_value(ctx, "namespace_dir", None)
    if not namespace_dir:
        return ""
    path = Path(str(namespace_dir)) / "event_alpha_daily_review_inbox.md"
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return ""


def _check_archive_manifest(archive_manifest: Mapping[str, Any], blockers: Messages) -> None:
    if not archive_manifest:
        return
    secret_blockers = _int(archive_manifest.get("secret_blocker_count"))
    if not secret_blockers and "secret_blocker_count" not in archive_manifest:
        secret_blockers = _int(archive_manifest.get("secret_hit_count"))
    if secret_blockers:
        blockers.append(
            check_registry.format_check_message(
                "secrets.daily_burn_in_archive_secret_blocker",
                f"daily_burn_in_archive_secret_blocker_count={secret_blockers}",
            )
        )
    if str(archive_manifest.get("archive_scope") or "") != "active_burn_in_namespaces":
        return
    non_burn_in = (
        _int(archive_manifest.get("included_without_burn_in_run_count"))
        + _int(archive_manifest.get("notification_rehearsal_included_count"))
        + _int(archive_manifest.get("no_key_included_count"))
        + _int(archive_manifest.get("provider_rehearsal_included_count"))
        + _int(archive_manifest.get("fixture_included_count"))
    )
    if non_burn_in:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_archive_scope",
                "daily_burn_in_archive_includes_non_burn_in_by_default",
            )
        )


def _check_step_tails(steps: list[Mapping[str, Any]], blockers: Messages, warnings: Messages) -> None:
    missing_scrub_flags = 0
    unsanitized_paths = 0
    unsanitized_secrets = 0
    for row in steps:
        for field, scrubbed_field in (("stdout_tail", "stdout_tail_scrubbed"), ("stderr_tail", "stderr_tail_scrubbed")):
            text = str(row.get(field) or "")
            if text and row.get(scrubbed_field) is not True:
                missing_scrub_flags += 1
            if _contains_unsanitized_absolute_path(text):
                unsanitized_paths += 1
            if any(detail.get("status") == "blocker" for detail in common.classify_secret_hits_in_text(text)):
                unsanitized_secrets += 1
    if missing_scrub_flags:
        warnings.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_tail_scrub_flags",
                f"daily_burn_in_step_tail_missing_scrub_flags={missing_scrub_flags}",
            )
        )
    if unsanitized_paths:
        blockers.append(
            check_registry.format_check_message(
                "paths.daily_burn_in_unsanitized_tail_path",
                f"daily_burn_in_step_tail_unsanitized_absolute_paths={unsanitized_paths}",
            )
        )
    if unsanitized_secrets:
        blockers.append(
            check_registry.format_check_message(
                "secrets.daily_burn_in_unsanitized_tail_secret",
                f"daily_burn_in_step_tail_unsanitized_secret_values={unsanitized_secrets}",
            )
        )


def _check_candidate_mode_fixture_cards(
    ctx: object,
    candidate_rows: list[Mapping[str, Any]],
    candidate_mode_manifest: Mapping[str, Any],
    blockers: Messages,
) -> None:
    fixture_count = _int(candidate_mode_manifest.get("fixture_candidate_count")) or sum(1 for row in candidate_rows if _is_fixture_candidate(row))
    if fixture_count <= 0:
        return
    review_inbox = ctx_mapping(ctx, "daily_review_inbox")
    review_items = [row for row in review_inbox.get("items") or [] if isinstance(row, Mapping)]
    core_rows = [row for row in ctx_value(ctx, "core_rows", []) or [] if isinstance(row, Mapping)]
    cards_from_inbox = sum(1 for row in review_items if str(row.get("card_path") or "").strip() and str(row.get("card_path") or "").strip().lower() != "none")
    cards_from_core = sum(1 for row in core_rows if str(row.get("card_path") or row.get("research_card_path") or "").strip())
    cards_from_manifest = _int(candidate_mode_manifest.get("research_cards_written"))
    if max(cards_from_inbox, cards_from_core, cards_from_manifest) <= 0:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_candidate_mode_fixture_cards",
                "daily_burn_in_candidate_mode_fixture_candidates_without_cards",
            )
        )
    missing_feedback_targets = sum(1 for row in review_items if not str(row.get("feedback_target") or "").strip())
    if review_items and missing_feedback_targets:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_candidate_mode_fixture_cards",
                f"daily_burn_in_candidate_mode_review_items_missing_feedback_target={missing_feedback_targets}",
            )
        )


def _check_candidate_mode_safety_counters(candidate_mode_manifest: Mapping[str, Any], blockers: Messages) -> None:
    if not candidate_mode_manifest:
        return
    missing = [key for key in common.SAFETY_FIELDS if key not in candidate_mode_manifest]
    nonzero = [
        key
        for key, value in common.SAFETY_FIELDS.items()
        if isinstance(value, int)
        and not isinstance(value, bool)
        and _int(candidate_mode_manifest.get(key)) != 0
    ]
    if missing or nonzero:
        blockers.append(
            check_registry.format_check_message(
                "outcomes.daily_burn_in_candidate_mode_safety",
                f"daily_burn_in_candidate_mode_safety_counters_missing={len(missing)} nonzero={len(nonzero)}",
            )
        )


def _contains_unsanitized_absolute_path(text: str) -> bool:
    if not text:
        return False
    return bool(
        re.search(r"(/Users/[^\s`'\"<>]+/|/mnt/data/[^\s`'\"<>]+|/tmp/[^\s`'\"<>]*event_fade_cache/|/private/tmp/[^\s`'\"<>]*event_fade_cache/)", text)
    )


def _is_fixture_candidate(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(row.get(field) or "") for field in ("run_mode", "profile", "artifact_namespace", "source_origin", "source_pack", "candidate_source_mode")).casefold()
    return bool(row.get("fixture_only") is True or row.get("test_fixture") is True or "fixture" in text or "smoke" in text or "mocked_fixture" in text)


def _is_burn_in_namespace(ctx: object) -> bool:
    namespace = str(ctx_value(ctx, "artifact_namespace", "") or "")
    profile = str(ctx_value(ctx, "profile", "") or "")
    status_obj = ctx_value(ctx, "namespace_status", None)
    safe_for_burn = bool(getattr(status_obj, "safe_for_burn_in_measurement", False))
    return (
        namespace.startswith("live_burn_in_")
        or profile.startswith("live_burn_in")
        or safe_for_burn
    )


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


_FORBIDDEN_SIDE_EFFECT_FIELDS = (
    "strict_alerts_created",
    "telegram_sends",
    "trades_created",
    "paper_trades_created",
    "normal_rsi_signal_rows_written",
    "triggered_fade_created",
)
