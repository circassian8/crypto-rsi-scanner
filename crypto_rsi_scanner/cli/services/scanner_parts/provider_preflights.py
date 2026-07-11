"""Provider Preflights commands from the scanner service."""

from __future__ import annotations

from .runtime import *
from .config_reports import _event_alpha_context_block


def _run_provider_artifact_mutation(
    context: Any,
    command: str,
    skip_label: str,
    action: Callable[[], None],
) -> None:
    with event_alpha_run_lock.artifact_mutation_guard(
        context,
        profile=context.profile,
        namespace=context.artifact_namespace,
        command=command,
    ) as mutation_lock:
        if not mutation_lock.owned:
            print(_event_alpha_context_block(context))
            print(f"{skip_label}: {mutation_lock.status.message}")
            return
        action()

def event_alpha_notification_runs_report(
    path: str | None = None,
    limit: int = 20,
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print recent Event Alpha notification-cycle summary rows."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    cfg = event_alpha_notification_runs.EventAlphaNotificationRunsConfig(
        path=_event_alpha_report_path(path, context.notification_runs_path)
    )
    result = event_alpha_notification_runs.load_notification_runs(cfg.path, limit=limit)
    print(_event_alpha_context_block(context))
    print(event_alpha_notification_runs.format_notification_runs_report(result))

def event_alpha_notification_deliveries_report(
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    verbose: bool = False,
) -> None:
    """Print the research-only notification delivery ledger for one profile/namespace."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    rows = event_alpha_notification_delivery.load_delivery_records(path)
    print(_event_alpha_context_block(context))
    print("")
    print(
        event_alpha_notification_delivery.format_delivery_report(
            rows,
            path=path,
            profile=context.profile,
            namespace=context.artifact_namespace,
        )
    )

def event_alpha_notification_retry_failed(
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    confirm: bool = False,
    verbose: bool = False,
) -> None:
    """List failed notification deliveries; resend is a guarded TODO scaffold.

    The delivery ledger keeps redacted metadata only (no full message body), so
    automated resend is intentionally not wired yet. This stays dry-run unless
    ``--confirm`` is passed, and even then it only points back at the notify
    cycle. It never trades, paper trades, or routes RSI rows.
    """
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    path = event_alpha_notification_delivery.deliveries_path_for_context(context)
    rows = event_alpha_notification_delivery.load_delivery_records(path)
    failed = event_alpha_notification_delivery.failed_deliveries(rows)
    print("=" * 76)
    print("EVENT ALPHA NOTIFICATION RETRY (research-only; dry-run scaffold)")
    print("=" * 76)
    print(f"profile: {context.profile} · namespace: {context.artifact_namespace}")
    print(f"path: {event_artifact_paths.artifact_display_path(path)}")
    print(f"failed deliveries: {len(failed)}")
    for row in failed[:20]:
        print(
            f"- {row.get('attempted_at') or 'unknown'} lane={row.get('lane') or 'unknown'} "
            f"alert_id={row.get('alert_id') or 'n/a'} error={row.get('error_message_safe') or 'unknown'}"
        )
    if not failed:
        print("No failed deliveries to retry.")
        return
    if not confirm:
        print("")
        print("Dry-run only. Re-run with --confirm to proceed (still requires RSI_EVENT_ALERTS_ENABLED=1 to send).")
        return
    print("")
    print(
        "Automated resend is not implemented yet (TODO): the deliveries ledger stores redacted "
        "metadata only, not message bodies. Re-run `make event-alpha-notify-no-key-scheduled` "
        "(or notify_llm) to regenerate and resend due notifications under the run lock."
    )

def event_alpha_provider_health_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print profile-scoped provider health/backoff rows."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    rows = event_provider_health.load_provider_health(context.provider_health_path)
    print(_event_alpha_context_block(context))
    print(f"provider_health_path: {context.provider_health_path}")
    print(event_provider_health.format_provider_health_report(rows))

def event_alpha_cryptopanic_preflight(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
) -> None:
    """Print a redacted CryptoPanic readiness report for Event Alpha runs."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_llm_deep", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    provider_report = event_provider_status.build_event_discovery_provider_status(config)
    provider_rows = event_provider_health.load_provider_health(context.provider_health_path)
    report = event_alpha_cryptopanic.build_cryptopanic_preflight(
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        provider_status_report=provider_report,
        provider_health_rows=provider_rows,
        provider_health_path=context.provider_health_path,
        request_ledger_path=context.provider_health_path.with_name("cryptopanic_request_ledger.jsonl"),
        token_configured=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN),
        live_enabled=bool(config.EVENT_DISCOVERY_CRYPTOPANIC_LIVE or config.EVENT_DISCOVERY_CRYPTOPANIC_PATH),
        endpoint_url=config.EVENT_DISCOVERY_CRYPTOPANIC_BASE_URL,
        plan=config.EVENT_DISCOVERY_CRYPTOPANIC_PLAN,
        weekly_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_WEEKLY_REQUEST_LIMIT,
        daily_soft_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_DAY_SOFT_LIMIT,
        per_run_limit=config.EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT,
        catalyst_search_providers=tuple(str(item) for item in config.EVENT_CATALYST_SEARCH_PROVIDERS),
        no_send=not bool(config.EVENT_ALERTS_ENABLED),
    )
    print(_event_alpha_context_block(context))
    print(event_alpha_cryptopanic.format_cryptopanic_preflight(report))

def event_alpha_coinalyze_preflight_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    smoke_mode: bool = False,
    allow_live_preflight: bool = False,
) -> None:
    """Write Coinalyze no-call preflight artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_llm_deep", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    if _coinalyze_namespace_write_blocked(context, suggested_namespace=event_coinalyze_preflight.DEFAULT_PREFLIGHT_NAMESPACE):
        return
    _run_provider_artifact_mutation(
        context,
        "coinalyze-preflight-report",
        "coinalyze_preflight_skipped",
        lambda: _event_alpha_coinalyze_preflight_report_locked(
            context,
            smoke_mode=smoke_mode,
            allow_live_preflight=allow_live_preflight,
        ),
    )


def _event_alpha_coinalyze_preflight_report_locked(
    context: Any,
    *,
    smoke_mode: bool,
    allow_live_preflight: bool,
) -> None:
    if _coinalyze_namespace_write_blocked(
        context,
        suggested_namespace=event_coinalyze_preflight.DEFAULT_PREFLIGHT_NAMESPACE,
    ):
        return
    report = event_coinalyze_preflight.build_preflight_report(
        namespace_dir=context.namespace_dir,
        smoke_mode=smoke_mode,
        allow_live_preflight=allow_live_preflight,
        now=_event_research_now(),
    )
    json_path, md_path = event_coinalyze_preflight.write_preflight_artifacts(report, context.namespace_dir)
    print(_event_alpha_context_block(context))
    print(f"coinalyze_preflight_json: {event_artifact_paths.artifact_display_path(json_path)}")
    print(f"coinalyze_preflight_report: {event_artifact_paths.artifact_display_path(md_path)}")
    print(event_coinalyze_preflight.format_preflight_report(report))

def event_alpha_coinalyze_no_send_rehearsal(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    allow_live_preflight: bool = False,
) -> None:
    """Guarded Coinalyze no-send rehearsal stub; no live calls by default."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_llm_deep", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    if _coinalyze_namespace_write_blocked(context, suggested_namespace=event_coinalyze_preflight.DEFAULT_REHEARSAL_NAMESPACE):
        return
    _run_provider_artifact_mutation(
        context,
        "coinalyze-no-send-rehearsal",
        "coinalyze_rehearsal_skipped",
        lambda: _event_alpha_coinalyze_no_send_rehearsal_locked(
            context,
            allow_live_preflight=allow_live_preflight,
        ),
    )


def _event_alpha_coinalyze_no_send_rehearsal_locked(
    context: Any,
    *,
    allow_live_preflight: bool,
) -> None:
    if _coinalyze_namespace_write_blocked(
        context,
        suggested_namespace=event_coinalyze_preflight.DEFAULT_REHEARSAL_NAMESPACE,
    ):
        return
    preflight, report, paths = event_coinalyze_preflight.run_no_send_rehearsal(
        namespace_dir=context.namespace_dir,
        provider_health_path=context.provider_health_path,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        allow_live_preflight=allow_live_preflight,
        no_send_rehearsal=True,
        now=_event_research_now(),
    )
    json_path, md_path, rehearsal_json_path, rehearsal_path = paths
    print(_event_alpha_context_block(context))
    print(f"coinalyze_preflight_json: {event_artifact_paths.artifact_display_path(json_path)}")
    print(f"coinalyze_preflight_report: {event_artifact_paths.artifact_display_path(md_path)}")
    print(f"coinalyze_rehearsal_json: {event_artifact_paths.artifact_display_path(rehearsal_json_path)}")
    print(f"coinalyze_rehearsal_report: {event_artifact_paths.artifact_display_path(rehearsal_path)}")
    print(f"coinalyze_no_send_rehearsal_status: {report.status}")
    print(event_coinalyze_preflight.format_rehearsal_report(report))

def event_alpha_bybit_announcements_preflight_report(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    smoke_mode: bool = False,
    allow_live_preflight: bool = False,
) -> None:
    """Write Bybit official-announcements no-call preflight artifacts."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_llm_deep", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    if _event_alpha_namespace_write_blocked(
        context,
        suggested_namespace=event_bybit_announcements_preflight.DEFAULT_PREFLIGHT_NAMESPACE,
        artifact_label="Bybit announcements preflight/rehearsal",
    ):
        return
    _run_provider_artifact_mutation(
        context,
        "bybit-announcements-preflight-report",
        "bybit_announcements_preflight_skipped",
        lambda: _event_alpha_bybit_announcements_preflight_report_locked(
            context,
            smoke_mode=smoke_mode,
            allow_live_preflight=allow_live_preflight,
        ),
    )


def _event_alpha_bybit_announcements_preflight_report_locked(
    context: Any,
    *,
    smoke_mode: bool,
    allow_live_preflight: bool,
) -> None:
    if _event_alpha_namespace_write_blocked(
        context,
        suggested_namespace=event_bybit_announcements_preflight.DEFAULT_PREFLIGHT_NAMESPACE,
        artifact_label="Bybit announcements preflight/rehearsal",
    ):
        return
    report = event_bybit_announcements_preflight.build_preflight_report(
        namespace_dir=context.namespace_dir,
        smoke_mode=smoke_mode,
        allow_live_preflight=allow_live_preflight,
        now=_event_research_now(),
    )
    json_path, md_path = event_bybit_announcements_preflight.write_preflight_artifacts(report, context.namespace_dir)
    print(_event_alpha_context_block(context))
    print(f"bybit_announcements_preflight_json: {event_artifact_paths.artifact_display_path(json_path)}")
    print(f"bybit_announcements_preflight_report: {event_artifact_paths.artifact_display_path(md_path)}")
    print(event_bybit_announcements_preflight.format_preflight_report(report))

def event_alpha_bybit_announcements_no_send_rehearsal(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    allow_live_preflight: bool = False,
) -> None:
    """Run guarded Bybit official-announcements no-send rehearsal; no live calls by default."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_llm_deep", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    if _event_alpha_namespace_write_blocked(
        context,
        suggested_namespace=event_bybit_announcements_preflight.DEFAULT_REHEARSAL_NAMESPACE,
        artifact_label="Bybit announcements preflight/rehearsal",
    ):
        return
    _run_provider_artifact_mutation(
        context,
        "bybit-announcements-no-send-rehearsal",
        "bybit_announcements_rehearsal_skipped",
        lambda: _event_alpha_bybit_announcements_no_send_rehearsal_locked(
            context,
            allow_live_preflight=allow_live_preflight,
        ),
    )


def _event_alpha_bybit_announcements_no_send_rehearsal_locked(
    context: Any,
    *,
    allow_live_preflight: bool,
) -> None:
    if _event_alpha_namespace_write_blocked(
        context,
        suggested_namespace=event_bybit_announcements_preflight.DEFAULT_REHEARSAL_NAMESPACE,
        artifact_label="Bybit announcements preflight/rehearsal",
    ):
        return
    _preflight, report, paths = event_bybit_announcements_preflight.run_no_send_rehearsal(
        namespace_dir=context.namespace_dir,
        provider_health_path=context.provider_health_path,
        profile=context.profile,
        artifact_namespace=context.artifact_namespace,
        allow_live_preflight=allow_live_preflight,
        no_send_rehearsal=True,
        now=_event_research_now(),
    )
    preflight_json, preflight_md, rehearsal_json, rehearsal_md = paths
    print(_event_alpha_context_block(context))
    print(f"bybit_announcements_preflight_json: {event_artifact_paths.artifact_display_path(preflight_json)}")
    print(f"bybit_announcements_preflight_report: {event_artifact_paths.artifact_display_path(preflight_md)}")
    print(f"bybit_announcements_rehearsal_json: {event_artifact_paths.artifact_display_path(rehearsal_json)}")
    print(f"bybit_announcements_rehearsal_report: {event_artifact_paths.artifact_display_path(rehearsal_md)}")
    print(f"bybit_announcements_no_send_rehearsal_status: {report.status}")
    print(event_bybit_announcements_preflight.format_rehearsal_report(report))

def _event_alpha_namespace_write_blocked(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    suggested_namespace: str,
    artifact_label: str,
) -> bool:
    status = event_alpha_namespace_status.load_namespace_status(context.namespace_dir)
    allow = str(os.getenv("ALLOW_STALE_NAMESPACE_WRITE", "")).strip().casefold() in {"1", "true", "yes", "on"} or str(
        os.getenv("RSI_EVENT_ALPHA_ALLOW_STALE_NAMESPACE_WRITE", "")
    ).strip().casefold() in {"1", "true", "yes", "on"}
    if not event_alpha_namespace_status.is_stale_deprecated(status) or allow:
        return False
    suggested = status.superseded_by or suggested_namespace
    print(_event_alpha_context_block(context))
    print("status=blocked_stale_namespace")
    print(f"active_suggested_namespace={suggested}")
    print(event_alpha_namespace_status.format_namespace_status(status))
    print(f"No {artifact_label} artifacts were written to the stale namespace.")
    return True

def _coinalyze_namespace_write_blocked(
    context: event_alpha_artifacts.EventAlphaArtifactContext,
    *,
    suggested_namespace: str,
) -> bool:
    return _event_alpha_namespace_write_blocked(
        context,
        suggested_namespace=suggested_namespace,
        artifact_label="Coinalyze preflight/rehearsal",
    )

def event_alpha_mark_namespace_stale(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    reason: str | None = None,
    superseded_by: str | None = None,
) -> None:
    """Write an explicit stale/deprecated marker for one artifact namespace."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_llm_deep", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    _run_provider_artifact_mutation(
        context,
        "mark-namespace-stale",
        "mark_namespace_stale_skipped",
        lambda: _event_alpha_mark_namespace_stale_locked(
            context,
            reason=reason,
            superseded_by=superseded_by,
        ),
    )


def _event_alpha_mark_namespace_stale_locked(
    context: Any,
    *,
    reason: str | None,
    superseded_by: str | None,
) -> None:
    marker = event_alpha_namespace_status.mark_namespace_stale(
        context.namespace_dir,
        namespace=context.artifact_namespace,
        reason=reason or "operator marked stale/deprecated",
        superseded_by=superseded_by,
        safe_for_send_readiness=False,
        now=_event_research_now(),
    )
    status = event_alpha_namespace_status.load_namespace_status(context.namespace_dir)
    print(_event_alpha_context_block(context))
    print(f"namespace_status_marker: {event_artifact_paths.artifact_display_path(marker)}")
    print(event_alpha_namespace_status.format_namespace_status(status))

def event_alpha_mark_known_stale_namespaces(verbose: bool = False) -> None:
    """Idempotently mark known pre-canonical namespaces stale/deprecated."""
    _setup_event_discovery_logging(verbose)
    known = (
        {
            "profile": "notify_llm_deep",
            "namespace": "notify_llm_deep",
            "reason": "pre-canonical notify_llm_deep artifacts; superseded by current rehearsal namespaces",
            "superseded_by": "notify_llm_deep_cryptopanic_rehearsal, notify_llm_deep_fixture_rehearsal, integrated_radar_smoke",
        },
    )
    for item in known:
        context = resolve_event_alpha_artifact_context_for_report(
            str(item["profile"]),
            str(item["namespace"]),
        )
        _run_provider_artifact_mutation(
            context,
            "mark-known-stale-namespace",
            "mark_known_stale_namespace_skipped",
            lambda context=context, item=item: _event_alpha_mark_known_stale_namespace_locked(
                context,
                item,
            ),
        )


def _event_alpha_mark_known_stale_namespace_locked(context: Any, item: Mapping[str, Any]) -> None:
    marker = event_alpha_namespace_status.mark_namespace_stale(
        context.namespace_dir,
        namespace=context.artifact_namespace,
        reason=str(item["reason"]),
        superseded_by=str(item["superseded_by"]),
        safe_for_send_readiness=False,
        now=_event_research_now(),
    )
    print(_event_alpha_context_block(context))
    print(f"namespace_status_marker: {event_artifact_paths.artifact_display_path(marker)}")
    print(event_alpha_namespace_status.format_namespace_status(event_alpha_namespace_status.load_namespace_status(context.namespace_dir)))

def event_alpha_prune_or_archive_stale_namespace(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    archive: bool = False,
) -> None:
    """Print a dry-run stale namespace prune/archive plan."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name or "notify_llm_deep", artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    status = event_alpha_namespace_status.load_namespace_status(context.namespace_dir)
    plan = event_alpha_namespace_status.stale_namespace_plan(context.namespace_dir, archive=archive)
    print(_event_alpha_context_block(context))
    print(event_alpha_namespace_status.format_namespace_status(status))
    print("stale_namespace_prune_archive_plan:")
    print(json.dumps(plan, indent=2, sort_keys=True))
    print("dry_run_only: true")

def event_alpha_namespace_lifecycle_report(verbose: bool = False) -> None:
    """Write and print the Event Alpha namespace lifecycle inventory."""
    _setup_event_discovery_logging(verbose)
    report = event_alpha_namespace_lifecycle.write_namespace_lifecycle_report()
    print("event_alpha_namespace_lifecycle_report:")
    print(f"registry_path: {report.get('registry_path')}")
    print(f"report_path: {report.get('report_path')}")
    print(event_alpha_namespace_lifecycle.format_namespace_lifecycle_report(report))

def event_alpha_list_active_namespaces(verbose: bool = False) -> None:
    """Print active Event Alpha artifact namespaces from lifecycle inventory."""
    _setup_event_discovery_logging(verbose)
    rows = event_alpha_namespace_lifecycle.list_active_namespaces()
    print("event_alpha_active_namespaces:")
    print(json.dumps(list(rows), indent=2, sort_keys=True))

def event_alpha_archive_stale_namespaces(verbose: bool = False) -> None:
    """Print a dry-run archive plan for stale Event Alpha namespaces."""
    _setup_event_discovery_logging(verbose)
    dry_run = str(os.getenv("RSI_EVENT_ALPHA_ARCHIVE_DRY_RUN", "1")).strip().casefold() not in {"0", "false", "no", "off"}
    plan = event_alpha_namespace_lifecycle.archive_stale_namespaces_plan(dry_run=dry_run)
    print("event_alpha_archive_stale_namespaces_plan:")
    print(json.dumps(plan, indent=2, sort_keys=True))
    print("dry_run_only: true")

def event_alpha_provider_health_reset(
    verbose: bool = False,
    *,
    profile_name: str | None = None,
    artifact_namespace: str | None = None,
    provider_key: str | None = None,
    service: str | None = None,
    role: str | None = None,
    reset_all: bool = False,
    confirm: bool = False,
) -> None:
    """Clear selected provider health backoff state without calling providers."""
    _setup_event_discovery_logging(verbose)
    try:
        context = _event_alpha_report_context(profile_name, artifact_namespace)
    except ValueError as exc:
        print(str(exc))
        return
    if not confirm:
        print("Provider health reset refused: pass --confirm to clear local backoff state.")
        return
    rows = event_provider_health.load_provider_health(context.provider_health_path)
    try:
        updated, result = event_provider_health.reset_provider_health_rows(
            rows,
            provider_key=provider_key,
            service=service,
            role=role,
            reset_all=reset_all,
        )
    except ValueError as exc:
        print(f"Provider health reset failed: {exc}")
        return
    event_provider_health.write_provider_health(context.provider_health_path, updated)
    print(_event_alpha_context_block(context))
    print(event_provider_health.format_provider_health_reset_result(result, path=context.provider_health_path))

__all__ = (
    'event_alpha_notification_runs_report',
    'event_alpha_notification_deliveries_report',
    'event_alpha_notification_retry_failed',
    'event_alpha_provider_health_report',
    'event_alpha_cryptopanic_preflight',
    'event_alpha_coinalyze_preflight_report',
    'event_alpha_coinalyze_no_send_rehearsal',
    'event_alpha_bybit_announcements_preflight_report',
    'event_alpha_bybit_announcements_no_send_rehearsal',
    '_event_alpha_namespace_write_blocked',
    '_coinalyze_namespace_write_blocked',
    'event_alpha_mark_namespace_stale',
    'event_alpha_mark_known_stale_namespaces',
    'event_alpha_prune_or_archive_stale_namespace',
    'event_alpha_namespace_lifecycle_report',
    'event_alpha_list_active_namespaces',
    'event_alpha_archive_stale_namespaces',
    'event_alpha_provider_health_reset',
)
