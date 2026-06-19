"""Artifact context and filtering helpers for Event Alpha research outputs."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


RUN_MODES = ("test", "fixture", "replay", "burn_in", "operational")
NON_OPERATIONAL_RUN_MODES = {"test", "fixture", "replay"}
LIVE_BURN_IN_PROFILES = {"no_key_live", "no_key_llm", "api_live", "full_llm_live"}
OPERATIONAL_PROFILES = {"research_send"}


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
    watchlist_state_path: Path
    feedback_path: Path
    missed_path: Path
    priors_path: Path
    provider_health_path: Path
    daily_brief_path: Path
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
    """Resolve profile/run-mode artifact paths while honoring explicit env paths."""
    from . import config

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
    raw_base = os.getenv("RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR") or base_dir or getattr(
        config,
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        getattr(config, "EVENT_DISCOVERY_CACHE_DIR", Path("event_fade_cache")),
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
) -> list[dict[str, Any]]:
    """Filter local rows to one profile/namespace and exclude test rows by default."""
    profile_key = _clean_optional(profile)
    namespace_key = _clean_optional(artifact_namespace)
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        data = dict(row)
        if not include_test_artifacts and is_non_operational_row(data):
            continue
        if profile_key is not None and _clean_optional(data.get("profile")) not in (None, profile_key):
            continue
        if namespace_key is not None:
            row_ns = _clean_optional(data.get("artifact_namespace") or data.get("namespace"))
            if row_ns not in (None, namespace_key):
                continue
        out.append(data)
    return out


def is_non_operational_row(row: Mapping[str, Any]) -> bool:
    mode = _clean_optional(row.get("run_mode"))
    if mode in NON_OPERATIONAL_RUN_MODES:
        return True
    namespace = _clean_optional(row.get("artifact_namespace") or row.get("namespace"))
    return bool(namespace and namespace in NON_OPERATIONAL_RUN_MODES)


def row_namespace(row: Mapping[str, Any]) -> str:
    return _clean_optional(row.get("artifact_namespace") or row.get("namespace")) or "legacy"


def row_profile(row: Mapping[str, Any]) -> str:
    return _clean_optional(row.get("profile")) or "default"


def _default_run_mode(profile: str) -> str:
    if profile == "fixture":
        return "fixture"
    if profile == "replay":
        return "replay"
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
