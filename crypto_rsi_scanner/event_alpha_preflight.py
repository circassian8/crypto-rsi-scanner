"""Preflight checks for profile-scoped Event Alpha research runs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import event_alpha_artifacts, event_alpha_profiles, event_provider_status


@dataclass(frozen=True)
class EventAlphaPreflightResult:
    ready: bool
    profile: str
    artifact_namespace: str
    run_mode: str
    paths: dict[str, Path]
    provider_ready_event_sources: int
    provider_ready_enrichment_sources: int
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommended_next_command: str = "make event-alpha-cycle-profile PROFILE=no_key_live"


def run_preflight(
    *,
    profile_name: str | None,
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    cfg: Any,
    provider_status: event_provider_status.EventDiscoveryProviderStatus | None = None,
    send_requested: bool = False,
) -> EventAlphaPreflightResult:
    """Check whether a profile-scoped Event Alpha run can write clean artifacts."""
    profile_key = str(profile_name or context.profile or "default").strip() or "default"
    blockers: list[str] = []
    warnings: list[str] = []
    profile = None
    if profile_name:
        try:
            profile = event_alpha_profiles.get_profile(profile_name)
        except ValueError as exc:
            blockers.append(str(exc))

    paths = {
        "run_ledger_path": context.run_ledger_path,
        "alert_store_path": context.alert_store_path,
        "watchlist_state_path": context.watchlist_state_path,
        "feedback_path": context.feedback_path,
        "missed_path": context.missed_path,
        "provider_health_path": context.provider_health_path,
        "llm_budget_ledger_path": context.llm_budget_ledger_path,
        "daily_brief_path": context.daily_brief_path,
        "research_cards_dir": context.research_cards_dir,
    }
    namespace_dir = _resolved(context.namespace_dir)
    for label, path in paths.items():
        _check_path(
            label,
            path,
            namespace_dir=namespace_dir,
            strict_namespace=_is_operational_mode(context.run_mode),
            blockers=blockers,
            warnings=warnings,
        )

    if _is_operational_mode(context.run_mode) and context.artifact_namespace in event_alpha_artifacts.NON_OPERATIONAL_RUN_MODES:
        blockers.append(
            f"operational profile {profile_key!r} would write to non-operational namespace "
            f"{context.artifact_namespace!r}"
        )
    if profile_key in event_alpha_artifacts.OPERATIONAL_PROFILES | event_alpha_artifacts.LIVE_BURN_IN_PROFILES:
        if context.artifact_namespace in {"default", event_alpha_artifacts.LEGACY_NAMESPACE, ""}:
            blockers.append(f"profile {profile_key!r} must use an isolated artifact namespace")

    status = provider_status or event_provider_status.build_event_discovery_provider_status(cfg)
    if status.ready_event_source_count <= 0:
        warnings.append("no configured event source is ready; run may produce zero raw events")
    if status.ready_enrichment_count <= 0:
        warnings.append("no enrichment source is ready; resolver/market evidence may be weak")

    _check_llm(profile_key, cfg, blockers=blockers, warnings=warnings)
    profile_send = bool(profile and (profile.send or profile.notification_burn_in))
    if send_requested or profile_send:
        if not bool(getattr(cfg, "EVENT_ALERTS_ENABLED", False)):
            blockers.append("send requested/profile requires RSI_EVENT_ALERTS_ENABLED=1")
        if not _telegram_ready(cfg):
            blockers.append("send requested/profile requires Telegram token and chat id configuration")

    recommended = _recommended_next_command(profile_key, bool(blockers), bool(warnings))
    return EventAlphaPreflightResult(
        ready=not blockers,
        profile=profile_key,
        artifact_namespace=context.artifact_namespace,
        run_mode=context.run_mode,
        paths=paths,
        provider_ready_event_sources=status.ready_event_source_count,
        provider_ready_enrichment_sources=status.ready_enrichment_count,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        recommended_next_command=recommended,
    )


def format_preflight_report(result: EventAlphaPreflightResult) -> str:
    """Render a redacted, operator-facing preflight report."""
    lines = [
        "=" * 76,
        "EVENT ALPHA PREFLIGHT (research-only)",
        "=" * 76,
        f"READY_TO_RUN: {'yes' if result.ready else 'no'}",
        f"profile: {result.profile}",
        f"artifact_namespace: {result.artifact_namespace}",
        f"run_mode: {result.run_mode}",
        (
            "provider_ready: "
            f"event_sources={result.provider_ready_event_sources} "
            f"enrichment_sources={result.provider_ready_enrichment_sources}"
        ),
        "",
        "paths:",
    ]
    for label, path in result.paths.items():
        lines.append(f"- {label}: {event_alpha_artifacts.safe_path_label(path, max_len=140)}")
    lines.extend(["", "blockers:"])
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.extend(["", "warnings:"])
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.extend([
        "",
        f"recommended_next_command: {result.recommended_next_command}",
        "Preflight checks local research readiness only; it does not send, trade, paper trade, write normal RSI signals, or alter tiers.",
    ])
    return "\n".join(lines).rstrip()


def _check_path(
    label: str,
    path: Path,
    *,
    namespace_dir: Path,
    strict_namespace: bool,
    blockers: list[str],
    warnings: list[str],
) -> None:
    resolved = _resolved(path)
    if strict_namespace and not _is_relative_to(resolved, namespace_dir):
        warnings.append(f"{label} is outside namespace_dir: {event_alpha_artifacts.safe_path_label(resolved)}")
    target_dir = resolved if _looks_like_dir(label, resolved) else resolved.parent
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        probe = target_dir / ".event_alpha_preflight_write_test"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        blockers.append(f"{label} is not writable/creatable: {event_alpha_artifacts.safe_path_label(resolved)} ({exc})")


def _check_llm(profile_key: str, cfg: Any, *, blockers: list[str], warnings: list[str]) -> None:
    relationship_provider = str(getattr(cfg, "EVENT_LLM_PROVIDER", "fixture") or "fixture").lower()
    extractor_provider = str(getattr(cfg, "EVENT_LLM_EXTRACTOR_PROVIDER", relationship_provider) or "fixture").lower()
    llm_enabled = bool(getattr(cfg, "EVENT_LLM_ENABLED", False))
    extractor_enabled = bool(getattr(cfg, "EVENT_LLM_EXTRACTOR_ENABLED", False))
    wants_openai = (
        (llm_enabled and relationship_provider == "openai")
        or (extractor_enabled and extractor_provider == "openai")
        or profile_key in {"full_llm_live", "notify_llm"}
    )
    max_run = int(getattr(cfg, "EVENT_LLM_MAX_CALLS_PER_RUN", 0) or 0)
    max_day = int(getattr(cfg, "EVENT_LLM_MAX_CALLS_PER_DAY", 0) or 0)
    max_cost = float(getattr(cfg, "EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY", 0.0) or 0.0)
    if profile_key in {"full_llm_live", "no_key_llm", "notify_llm"} and (max_run <= 0 or max_day <= 0 or max_cost <= 0):
        warnings.append("LLM profile has no positive per-run/day/cost budget caps")
    if wants_openai and not os.getenv("OPENAI_API_KEY"):
        blockers.append("OpenAI LLM profile/provider requires OPENAI_API_KEY")
    if not wants_openai and relationship_provider not in {"fixture", "none", "off", "disabled"}:
        warnings.append(f"relationship LLM provider {relationship_provider!r} is not a known offline provider")
    if not wants_openai and extractor_provider not in {"fixture", "none", "off", "disabled"}:
        warnings.append(f"extractor LLM provider {extractor_provider!r} is not a known offline provider")


def _telegram_ready(cfg: Any) -> bool:
    return bool(getattr(cfg, "TELEGRAM_BOT_TOKEN", None) and getattr(cfg, "TELEGRAM_CHAT_IDS", None))


def _recommended_next_command(profile: str, blocked: bool, warned: bool) -> str:
    if blocked:
        return f"make event-alpha-status PROFILE={profile}"
    if warned:
        return f"make event-alpha-artifact-doctor PROFILE={profile} STRICT=1"
    return f"make event-alpha-cycle-profile PROFILE={profile}"


def _is_operational_mode(mode: str) -> bool:
    return str(mode or "") not in event_alpha_artifacts.NON_OPERATIONAL_RUN_MODES


def _looks_like_dir(label: str, path: Path) -> bool:
    return label.endswith("_dir") or (not path.suffix and str(path).endswith(("/", "\\")))


def _resolved(path: Path | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
