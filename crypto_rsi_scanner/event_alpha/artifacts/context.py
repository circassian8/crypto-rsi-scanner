"""Artifact context and filtering helpers for Event Alpha research outputs."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


RUN_MODES = ("test", "fixture", "replay", "burn_in", "notification_burn_in", "operational")
NON_OPERATIONAL_RUN_MODES = {"test", "fixture", "replay"}
LIVE_BURN_IN_PROFILES = {"no_key_live", "no_key_llm", "api_live", "full_llm_live", "full_llm_deep"}
NOTIFICATION_BURN_IN_PROFILES = {
    "notify_no_key",
    "notify_llm",
    "notify_llm_deep",
    "notify_llm_quality",
    "notify_llm_quality_fresh",
    "live_burn_in_no_send",
}
OPERATIONAL_PROFILES = {"research_send"}
LEGACY_NAMESPACE = "legacy"
SNAPSHOT_AVAILABLE = "available"
SNAPSHOT_MISSING = "missing"
SNAPSHOT_EXTERNAL_PATH = "external_path"
SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL = "test_or_fixture_external"
SNAPSHOT_UNKNOWN_LEGACY = "unknown_api"


@dataclass(frozen=True)
class EventAlphaArtifactContext:
    """Resolved local research-artifact namespace for one Event Alpha run/report."""

    profile: str
    run_mode: str
    artifact_namespace: str
    base_dir: Path
    namespace_dir: Path
    run_ledger_path: Path
    alert_store_path: Path
    notification_runs_path: Path
    watchlist_state_path: Path
    feedback_path: Path
    missed_path: Path
    priors_path: Path
    provider_health_path: Path
    daily_brief_path: Path
    impact_hypothesis_store_path: Path
    core_opportunity_store_path: Path
    incident_store_path: Path
    evidence_acquisition_path: Path
    proposed_eval_cases_dir: Path
    research_cards_dir: Path
    llm_budget_ledger_path: Path
    outcomes_path: Path


def context_from_profile(
    profile: str | None,
    *,
    run_mode: str | None = None,
    base_dir: str | Path | None = None,
    artifact_namespace: str | None = None,
) -> EventAlphaArtifactContext:
    """Resolve artifact paths, with an explicit call-site base taking priority."""
    from ... import config

    profile_key = _clean_token(profile or "default", default="default")
    mode = _clean_token(
        os.getenv("RSI_EVENT_ALPHA_RUN_MODE") or run_mode or _default_run_mode(profile_key),
        default=_default_run_mode(profile_key),
    )
    if mode not in RUN_MODES:
        mode = "test"
    namespace = _clean_token(
        os.getenv("RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE")
        or artifact_namespace
        or _default_namespace(profile_key, mode),
        default=_default_namespace(profile_key, mode),
    )
    raw_base = (
        base_dir
        if base_dir is not None
        else os.getenv("RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR")
        or getattr(
            config,
            "EVENT_ALPHA_ARTIFACT_BASE_DIR",
            getattr(config, "EVENT_DISCOVERY_CACHE_DIR", Path("event_fade_cache")),
        )
    )
    resolved_base = _resolve_path(raw_base, data_dir=config.DATA_DIR)
    namespace_dir = resolved_base / namespace
    return EventAlphaArtifactContext(
        profile=profile_key,
        run_mode=mode,
        artifact_namespace=namespace,
        base_dir=resolved_base,
        namespace_dir=namespace_dir,
        run_ledger_path=_path_override(
            "RSI_EVENT_ALPHA_RUN_LEDGER_PATH",
            namespace_dir / "event_alpha_runs.jsonl",
            data_dir=config.DATA_DIR,
        ),
        alert_store_path=_path_override(
            "RSI_EVENT_ALPHA_ALERT_STORE_PATH",
            namespace_dir / "event_alpha_alerts.jsonl",
            data_dir=config.DATA_DIR,
        ),
        notification_runs_path=_path_override(
            "RSI_EVENT_ALPHA_NOTIFICATION_RUNS_PATH",
            namespace_dir / "event_alpha_notification_runs.jsonl",
            data_dir=config.DATA_DIR,
        ),
        watchlist_state_path=_path_override(
            "RSI_EVENT_WATCHLIST_STATE_PATH",
            namespace_dir / "event_watchlist_state.jsonl",
            data_dir=config.DATA_DIR,
        ),
        feedback_path=_path_override(
            "RSI_EVENT_ALPHA_FEEDBACK_PATH",
            namespace_dir / "event_alpha_feedback.jsonl",
            data_dir=config.DATA_DIR,
        ),
        missed_path=_path_override(
            "RSI_EVENT_ALPHA_MISSED_PATH",
            namespace_dir / "event_alpha_missed.jsonl",
            data_dir=config.DATA_DIR,
        ),
        priors_path=_path_override(
            "RSI_EVENT_ALPHA_PRIORS_PATH",
            namespace_dir / "event_alpha_priors.json",
            data_dir=config.DATA_DIR,
        ),
        provider_health_path=_path_override(
            "RSI_EVENT_PROVIDER_HEALTH_PATH",
            namespace_dir / "event_provider_health.json",
            data_dir=config.DATA_DIR,
        ),
        daily_brief_path=_path_override(
            "RSI_EVENT_ALPHA_DAILY_BRIEF_PATH",
            namespace_dir / "event_alpha_daily_brief.md",
            data_dir=config.DATA_DIR,
        ),
        impact_hypothesis_store_path=_path_override(
            "RSI_EVENT_IMPACT_HYPOTHESIS_STORE_PATH",
            namespace_dir / "event_impact_hypotheses.jsonl",
            data_dir=config.DATA_DIR,
        ),
        core_opportunity_store_path=_path_override(
            "RSI_EVENT_CORE_OPPORTUNITY_STORE_PATH",
            namespace_dir / "event_core_opportunities.jsonl",
            data_dir=config.DATA_DIR,
        ),
        incident_store_path=_path_override(
            "RSI_EVENT_INCIDENT_STORE_PATH",
            namespace_dir / "event_incidents.jsonl",
            data_dir=config.DATA_DIR,
        ),
        evidence_acquisition_path=_path_override(
            "RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH",
            namespace_dir / "event_evidence_acquisition.jsonl",
            data_dir=config.DATA_DIR,
        ),
        proposed_eval_cases_dir=_path_override(
            "RSI_EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR",
            namespace_dir / "proposed_eval_cases",
            data_dir=config.DATA_DIR,
        ),
        research_cards_dir=_path_override(
            "RSI_EVENT_RESEARCH_CARDS_DIR",
            namespace_dir / "research_cards",
            data_dir=config.DATA_DIR,
        ),
        llm_budget_ledger_path=_path_override(
            "RSI_EVENT_LLM_BUDGET_LEDGER_PATH",
            namespace_dir / "event_llm_budget.json",
            data_dir=config.DATA_DIR,
        ),
        outcomes_path=_path_override(
            "RSI_EVENT_ALPHA_OUTCOMES_PATH",
            namespace_dir / "event_alpha_outcomes.jsonl",
            data_dir=config.DATA_DIR,
        ),
    )


def filter_artifact_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
) -> list[dict[str, Any]]:
    """Filter local rows to one profile/namespace and exclude test/legacy rows by default."""
    profile_key = _clean_optional(profile)
    namespace_key = _clean_optional(artifact_namespace)
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        data = dict(row)
        if not include_test_artifacts and is_non_operational_row(data):
            continue
        if not include_api_artifacts and is_api_row(data):
            continue
        if profile_key is not None and _clean_optional(data.get("profile")) not in (None, profile_key):
            continue
        if namespace_key is not None:
            row_ns = _clean_optional(data.get("artifact_namespace") or data.get("namespace"))
            if row_ns != namespace_key:
                continue
        out.append(data)
    return out


def is_non_operational_row(row: Mapping[str, Any]) -> bool:
    mode = _clean_optional(row.get("run_mode"))
    if mode in NON_OPERATIONAL_RUN_MODES:
        return True
    namespace = _clean_optional(row.get("artifact_namespace") or row.get("namespace"))
    return bool(namespace and namespace in NON_OPERATIONAL_RUN_MODES)


def is_api_row(row: Mapping[str, Any]) -> bool:
    mode = _clean_optional(row.get("run_mode"))
    namespace = _clean_optional(row.get("artifact_namespace") or row.get("namespace"))
    if mode in (None, LEGACY_NAMESPACE):
        return True
    return namespace in (None, LEGACY_NAMESPACE)


def classify_snapshot_availability(
    run_row: Mapping[str, Any],
    inspected_alert_store_path: str | Path | None,
    matching_alert_count: int,
) -> str:
    """Classify whether a run's claimed snapshots are present in the inspected store."""
    if matching_alert_count > 0:
        return SNAPSHOT_AVAILABLE
    if is_api_row(run_row) or not str(run_row.get("run_id") or "").strip():
        return SNAPSHOT_UNKNOWN_LEGACY
    run_mode = _clean_optional(run_row.get("run_mode"))
    external = snapshot_path_is_external(run_row, inspected_alert_store_path)
    if external and run_mode in NON_OPERATIONAL_RUN_MODES:
        return SNAPSHOT_TEST_OR_FIXTURE_EXTERNAL
    if external:
        return SNAPSHOT_EXTERNAL_PATH
    return SNAPSHOT_MISSING


def snapshot_path_is_external(
    run_row: Mapping[str, Any],
    inspected_alert_store_path: str | Path | None,
) -> bool:
    row_path = _clean_path(run_row.get("alert_store_path"))
    inspected = _clean_path(inspected_alert_store_path)
    return bool(row_path and inspected and row_path != inspected)


def safe_path_label(value: object, *, max_len: int = 96) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if not text:
        return "unknown"
    home = str(Path.home())
    if home and text.startswith(home):
        text = "~" + text[len(home):]
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password)=([^&\\s]+)", r"\1=[redacted]", text)
    if len(text) > max_len:
        return "..." + text[-max(8, max_len - 3):]
    return text


def row_namespace(row: Mapping[str, Any]) -> str:
    return _clean_optional(row.get("artifact_namespace") or row.get("namespace")) or LEGACY_NAMESPACE


def row_profile(row: Mapping[str, Any]) -> str:
    return _clean_optional(row.get("profile")) or "default"


def _default_run_mode(profile: str) -> str:
    if profile == "fixture":
        return "fixture"
    if profile == "replay":
        return "replay"
    if profile in NOTIFICATION_BURN_IN_PROFILES:
        return "notification_burn_in"
    if profile in OPERATIONAL_PROFILES:
        return "operational"
    if profile in LIVE_BURN_IN_PROFILES:
        return "burn_in"
    return "test"


def _default_namespace(profile: str, run_mode: str) -> str:
    if profile and profile != "default":
        return profile
    return run_mode if run_mode in NON_OPERATIONAL_RUN_MODES else "default"


def _path_override(env_name: str, default: Path, *, data_dir: Path) -> Path:
    raw = os.getenv(env_name, "")
    return _resolve_path(raw, data_dir=data_dir) if raw else default


def _resolve_path(value: str | Path, *, data_dir: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else data_dir / path


def _clean_path(value: object) -> str | None:
    if value in (None, ""):
        return None
    try:
        return str(Path(str(value)).expanduser().resolve(strict=False))
    except (OSError, RuntimeError, ValueError):
        return str(value)


def _clean_optional(value: object) -> str | None:
    text = _clean_token(value, default="")
    return text or None


def _clean_token(value: object, *, default: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return default
    text = re.sub(r"[^a-z0-9_.-]+", "_", text)
    text = text.strip("._-")
    return text or default
