"""Markdown report rendering for Coinalyze preflight/rehearsal."""

from __future__ import annotations

from typing import Mapping, Any

from ..radar import derivatives_crowding as event_derivatives_crowding

ENV_API_KEY = "RSI_EVENT_DISCOVERY_COINALYZE_API_KEY"
ENV_ALLOW_LIVE_PREFLIGHT = "RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT"
ENV_PREFLIGHT_MAX_REQUESTS = "RSI_EVENT_ALPHA_COINALYZE_PREFLIGHT_MAX_REQUESTS"

SUPPORTED_METRICS = (
    "open_interest",
    "funding_rate",
    "predicted_funding",
    "liquidations",
    "long_short_ratio",
    "basis",
    "perp_volume",
)

def format_preflight_report(report: CoinalyzePreflightReport) -> str:
    lines = [
        "=" * 76,
        "COINALYZE DERIVATIVES PREFLIGHT (research-only, no-call by default)",
        "=" * 76,
        f"provider: {report.provider}",
        f"category: {report.category}",
        f"generated_at: {report.generated_at}",
        f"configured: {str(report.configured).lower()}",
        f"preflight_status: {report.preflight_status}",
        f"smoke_mode: {str(report.smoke_mode).lower()}",
        f"live_call_allowed: {str(report.live_call_allowed).lower()}",
        f"env_vars_required: {', '.join(report.env_vars_required)}",
        f"provider_health_key: {report.provider_health_key}",
        f"request_ledger_path: {report.request_ledger_path}",
        f"request_budget: {report.request_budget}",
        f"max_requests_per_run: {report.max_requests_per_run}",
        f"timeout_seconds: {report.timeout_seconds:g}",
        f"cache_ttl_seconds: {report.cache_ttl_seconds}",
        f"fixture_parser_status: {report.fixture_parser_status}",
        f"fixture_symbol_mapping_status: {report.fixture_symbol_mapping_status}",
        f"fixture_symbols_observed: {', '.join(report.fixture_symbols_observed) or 'none'}",
        f"supported_metrics: {', '.join(report.supported_metrics)}",
        f"supported_metric_status: {_format_metric_status(report.supported_metric_status)}",
        f"implemented_metrics: {_metrics_by_report_status(report.supported_metric_status, event_derivatives_crowding.METRIC_STATUS_IMPLEMENTED)}",
        f"fixture_only_metrics: {_metrics_by_report_status(report.supported_metric_status, event_derivatives_crowding.METRIC_STATUS_FIXTURE_ONLY)}",
        f"missing_or_planned_metrics: {_metrics_by_report_status(report.supported_metric_status, event_derivatives_crowding.METRIC_STATUS_MISSING_FROM_RESPONSE, event_derivatives_crowding.METRIC_STATUS_NOT_IMPLEMENTED, event_derivatives_crowding.METRIC_STATUS_PROVIDER_UNAVAILABLE)}",
        f"lanes_enabled_if_healthy: {', '.join(report.lanes_enabled_if_healthy)}",
        f"source_packs_enabled: {', '.join(report.source_packs_enabled)}",
        "",
        "Safety notes:",
    ]
    lines.extend(f"- {item}" for item in report.safety_notes)
    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in report.warnings)
    lines.append("")
    lines.append("No provider network calls were performed by this preflight.")
    return "\n".join(lines)


def format_rehearsal_report(report: CoinalyzeRehearsalReport) -> str:
    lines = [
        "# Coinalyze Bounded No-Send Rehearsal",
        "",
        "Research-only. Not a trade signal. No Telegram sends, trades, paper trades, normal RSI rows, or Event Alpha TRIGGERED_FADE.",
        f"status: {report.status}",
        f"provider: {report.provider}",
        f"configured: {str(report.configured).lower()}",
        f"allow_live_preflight: {str(report.allow_live_preflight).lower()}",
        f"live_call_allowed: {str(report.live_call_allowed).lower()}",
        f"no_send: {str(report.no_send).lower()}",
        f"research_only: {str(report.research_only).lower()}",
        f"provider_generation_id: {report.provider_generation_id}",
        f"run_id: {report.run_id}",
        f"requests_used: {report.requests_used}",
        f"max_requests_per_run: {report.max_requests_per_run}",
        f"symbols_requested: {', '.join(report.symbols_requested) or 'none'}",
        f"symbols_resolved: {', '.join(report.symbols_resolved) or 'none'}",
        f"supported_metric_status: {_format_metric_status(report.supported_metric_status)}",
        f"implemented_metrics: {_metrics_by_report_status(report.supported_metric_status, event_derivatives_crowding.METRIC_STATUS_IMPLEMENTED)}",
        f"fixture_only_metrics: {_metrics_by_report_status(report.supported_metric_status, event_derivatives_crowding.METRIC_STATUS_FIXTURE_ONLY)}",
        f"missing_or_planned_metrics: {_metrics_by_report_status(report.supported_metric_status, event_derivatives_crowding.METRIC_STATUS_MISSING_FROM_RESPONSE, event_derivatives_crowding.METRIC_STATUS_NOT_IMPLEMENTED, event_derivatives_crowding.METRIC_STATUS_PROVIDER_UNAVAILABLE)}",
        f"snapshots_written: {report.snapshots_written}",
        f"crowding_candidates_written: {report.crowding_candidates_written}",
        f"fade_review_candidates_written: {report.fade_review_candidates_written}",
        f"crowding_class_counts: {_format_counts(report.crowding_class_counts)}",
        f"fade_readiness_counts: {_format_counts(report.fade_readiness_counts)}",
        "symbols_with_extreme_crowding: "
        + (", ".join(report.symbols_with_extreme_crowding) or "none"),
        "symbols_with_confirmed_long_crowding_warning: "
        + (", ".join(report.symbols_with_confirmed_long_crowding_warning) or "none"),
        f"provider_health_status: {report.provider_health_status}",
        f"request_ledger_path: {report.request_ledger_path}",
        f"derivatives_state_path: {report.derivatives_state_path}",
        f"derivatives_crowding_candidates_path: {report.derivatives_candidates_path}",
        f"fade_review_candidates_path: {report.fade_review_candidates_path}",
        f"strict_alerts_created: {report.strict_alerts_created}",
        f"telegram_sends: {report.telegram_sends}",
        f"trades_created: {report.trades_created}",
        f"paper_trades_created: {report.paper_trades_created}",
        f"normal_rsi_signal_rows_written: {report.normal_rsi_signal_rows_written}",
        f"triggered_fade_created: {report.triggered_fade_created}",
    ]
    if report.error_class:
        lines.append(f"error_class: {report.error_class}")
    if report.error_message_safe:
        lines.append(f"error_message_safe: {report.error_message_safe}")
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    if report.status == "missing_config":
        lines.append(f"next_step: configure {ENV_API_KEY}, then rerun without live calls first")
    elif report.status == "live_call_blocked_by_default":
        lines.append(
            f"next_step: set {ENV_ALLOW_LIVE_PREFLIGHT}=1 manually after review, then rerun; "
            "the CLI allow flag may only accompany that provider-specific environment gate"
        )
    elif report.status == "blocked_request_budget":
        lines.append(f"next_step: keep {ENV_PREFLIGHT_MAX_REQUESTS} small and at least the required endpoint count for this symbol mode")
    else:
        lines.append("next_step: regenerate source coverage/daily brief and run artifact doctor before any further activation.")
    return "\n".join(lines)



def _format_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def _format_metric_status(status: Mapping[str, str]) -> str:
    return ", ".join(
        f"{metric}={status.get(metric)}"
        for metric in SUPPORTED_METRICS
        if status.get(metric)
    ) or "none"


def _metrics_by_report_status(status: Mapping[str, str], *wanted: str) -> str:
    wanted_set = {str(item) for item in wanted}
    metrics = [metric for metric in SUPPORTED_METRICS if str(status.get(metric) or "") in wanted_set]
    return ", ".join(metrics) if metrics else "none"
