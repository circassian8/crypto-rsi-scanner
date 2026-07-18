"""Pure text rendering for the Bybit announcements preflight surfaces."""

from __future__ import annotations

from typing import Any


def format_preflight_report(report: Any) -> str:
    lines = [
        "=" * 76,
        "BYBIT OFFICIAL ANNOUNCEMENTS PREFLIGHT (research-only, no-call by default)",
        "=" * 76,
        f"provider: {report.provider}",
        f"category: {report.category}",
        f"generated_at: {report.generated_at}",
        f"configured: {str(report.configured).lower()}",
        f"preflight_status: {report.preflight_status}",
        f"smoke_mode: {str(report.smoke_mode).lower()}",
        f"live_call_allowed: {str(report.live_call_allowed).lower()}",
        f"env_vars_required: {', '.join(report.env_vars_required) or 'none'}",
        f"provider_health_key: {report.provider_health_key}",
        f"request_ledger_path: {report.request_ledger_path}",
        f"request_budget: {report.request_budget}",
        f"max_pages: {report.max_pages}",
        f"limit: {report.limit}",
        f"timeout_seconds: {report.timeout_seconds:g}",
        f"cache_ttl_seconds: {report.cache_ttl_seconds}",
        f"fixture_parser_status: {report.fixture_parser_status}",
        f"fixture_rows_observed: {report.fixture_rows_observed}",
        f"supported_params: {', '.join(report.supported_params)}",
        f"lanes_enabled_if_healthy: {', '.join(report.lanes_enabled_if_healthy)}",
        f"source_packs_enabled: {', '.join(report.source_packs_enabled)}",
        "",
        "Safety notes:",
    ]
    lines.extend(f"- {item}" for item in report.safety_notes)
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.append("")
    lines.append("No provider network calls were performed by this preflight.")
    return "\n".join(lines)


def format_rehearsal_report(
    report: Any,
    *,
    env_allow_live_preflight: str,
    env_preflight_max_pages: str,
    env_preflight_limit: str,
) -> str:
    lines = [
        "# Bybit Official Announcements Bounded No-Send Rehearsal",
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
        f"http_successes: {report.http_successes}",
        f"accepted_source_response_count: {report.accepted_source_response_count}",
        f"accepted_source_artifacts: {', '.join(report.accepted_source_artifacts) or 'none'}",
        f"max_pages: {report.max_pages}",
        f"limit: {report.limit}",
        f"supported_params: {', '.join(report.supported_params)}",
        f"announcements_inspected: {report.announcements_inspected}",
        f"exchange_announcements_written: {report.exchange_announcements_written}",
        f"official_events_written: {report.official_events_written}",
        f"official_listing_candidates_written: {report.official_listing_candidates_written}",
        f"provider_health_status: {report.provider_health_status}",
        f"request_ledger_path: {report.request_ledger_path}",
        f"exchange_announcements_path: {report.exchange_announcements_path}",
        f"official_exchange_events_path: {report.official_exchange_events_path}",
        f"official_listing_candidates_path: {report.official_listing_candidates_path}",
        f"official_exchange_report_path: {report.official_exchange_report_path}",
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
    if report.status == "skipped_live_calls_disabled":
        lines.append(
            f"next_step: set {env_allow_live_preflight}=1 manually after review, then rerun; "
            "the CLI allow flag may only accompany that provider-specific environment gate"
        )
    elif report.status == "blocked_request_budget":
        lines.append(
            f"next_step: keep {env_preflight_max_pages} <= 3 and "
            f"{env_preflight_limit} <= 50"
        )
    else:
        lines.append(
            "next_step: regenerate source coverage/daily brief and run artifact "
            "doctor before any further activation."
        )
    return "\n".join(lines)


__all__ = ("format_preflight_report", "format_rehearsal_report")
