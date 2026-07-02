"""Parser and command classification helpers for the CLI consolidation layer.

``build_parser`` owns argparse construction for the compatibility CLI without
calling ``parse_args`` or executing any command branch.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CommandSnapshot:
    command_name: str
    flag: str
    command_group: str

    @property
    def dispatch_key(self) -> str:
        return self.command_name


COMMAND_FLAG_TO_SNAPSHOT: dict[str, CommandSnapshot] = {
    "--dry-run": CommandSnapshot("dry_run", "--dry-run", "rsi"),
    "--report": CommandSnapshot("report", "--report", "rsi"),
    "--score": CommandSnapshot("score", "--score", "paper"),
    "--refresh-paper": CommandSnapshot("refresh_paper", "--refresh-paper", "paper"),
    "--backup-db": CommandSnapshot("backup_db", "--backup-db", "maintenance"),
    "--maintenance": CommandSnapshot("maintenance", "--maintenance", "maintenance"),
    "--status": CommandSnapshot("status", "--status", "maintenance"),
    "--export-src": CommandSnapshot("export_src", "--export-src", "export"),
    "--export-src-with-artifacts": CommandSnapshot(
        "export_src_with_artifacts",
        "--export-src-with-artifacts",
        "export",
    ),
    "--event-alpha-integrated-radar-smoke": CommandSnapshot(
        "event_alpha_integrated_radar_smoke",
        "--event-alpha-integrated-radar-smoke",
        "event_alpha",
    ),
    "--event-alpha-integrated-radar-cycle": CommandSnapshot(
        "event_alpha_integrated_radar_cycle",
        "--event-alpha-integrated-radar-cycle",
        "event_alpha_integrated_radar",
    ),
    "--event-alpha-integrated-radar-doctor": CommandSnapshot(
        "event_alpha_integrated_radar_doctor",
        "--event-alpha-integrated-radar-doctor",
        "event_alpha_artifact_doctor",
    ),
    "--event-alpha-integrated-radar-fill-outcomes": CommandSnapshot(
        "event_alpha_integrated_radar_fill_outcomes",
        "--event-alpha-integrated-radar-fill-outcomes",
        "event_alpha_integrated_radar",
    ),
    "--event-alpha-integrated-radar-outcome-report": CommandSnapshot(
        "event_alpha_integrated_radar_outcome_report",
        "--event-alpha-integrated-radar-outcome-report",
        "event_alpha_integrated_radar",
    ),
    "--event-alpha-integrated-radar-calibration-report": CommandSnapshot(
        "event_alpha_integrated_radar_calibration_report",
        "--event-alpha-integrated-radar-calibration-report",
        "event_alpha_integrated_radar",
    ),
    "--event-alpha-artifact-doctor": CommandSnapshot(
        "event_alpha_artifact_doctor",
        "--event-alpha-artifact-doctor",
        "event_alpha_artifact_doctor",
    ),
    "--event-alpha-notify-preview": CommandSnapshot(
        "event_alpha_notify_preview",
        "--event-alpha-notify-preview",
        "event_alpha_notification",
    ),
    "--event-alpha-notify-preview-from-artifacts": CommandSnapshot(
        "event_alpha_notify_preview_from_artifacts",
        "--event-alpha-notify-preview-from-artifacts",
        "event_alpha_notification",
    ),
    "--event-alpha-notify-go-no-go": CommandSnapshot(
        "event_alpha_notify_go_no_go",
        "--event-alpha-notify-go-no-go",
        "event_alpha_notification",
    ),
    "--event-alpha-live-provider-readiness": CommandSnapshot(
        "event_alpha_live_provider_readiness",
        "--event-alpha-live-provider-readiness",
        "event_alpha_provider_readiness",
    ),
    "--event-alpha-live-provider-readiness-smoke": CommandSnapshot(
        "event_alpha_live_provider_readiness_smoke",
        "--event-alpha-live-provider-readiness-smoke",
        "event_alpha_provider_readiness",
    ),
    "--event-alpha-coinalyze-preflight": CommandSnapshot(
        "event_alpha_coinalyze_preflight",
        "--event-alpha-coinalyze-preflight",
        "event_alpha_coinalyze",
    ),
    "--event-alpha-coinalyze-preflight-smoke": CommandSnapshot(
        "event_alpha_coinalyze_preflight_smoke",
        "--event-alpha-coinalyze-preflight-smoke",
        "event_alpha_coinalyze",
    ),
    "--event-alpha-coinalyze-no-send-rehearsal": CommandSnapshot(
        "event_alpha_coinalyze_no_send_rehearsal",
        "--event-alpha-coinalyze-no-send-rehearsal",
        "event_alpha_coinalyze",
    ),
    "--event-alpha-bybit-announcements-preflight": CommandSnapshot(
        "event_alpha_bybit_announcements_preflight",
        "--event-alpha-bybit-announcements-preflight",
        "event_alpha_official_exchange",
    ),
    "--event-alpha-bybit-announcements-preflight-smoke": CommandSnapshot(
        "event_alpha_bybit_announcements_preflight_smoke",
        "--event-alpha-bybit-announcements-preflight-smoke",
        "event_alpha_official_exchange",
    ),
    "--event-alpha-bybit-announcements-no-send-rehearsal": CommandSnapshot(
        "event_alpha_bybit_announcements_no_send_rehearsal",
        "--event-alpha-bybit-announcements-no-send-rehearsal",
        "event_alpha_official_exchange",
    ),
    "--event-alpha-official-exchange-report": CommandSnapshot(
        "event_alpha_official_exchange_report",
        "--event-alpha-official-exchange-report",
        "event_alpha_official_exchange",
    ),
    "--event-alpha-namespace-lifecycle-report": CommandSnapshot(
        "event_alpha_namespace_lifecycle_report",
        "--event-alpha-namespace-lifecycle-report",
        "event_alpha",
    ),
}

COMMAND_ALIAS_TO_SNAPSHOT: dict[str, CommandSnapshot] = {
    "backtest": CommandSnapshot("backtest", "backtest", "backtest"),
    "crypto_rsi_scanner.backtest": CommandSnapshot(
        "backtest",
        "crypto_rsi_scanner.backtest",
        "backtest",
    ),
}


def build_parser() -> argparse.ArgumentParser:
    """Build the scanner CLI parser without executing command dispatch."""

    import argparse
    from .. import event_alpha_profiles, event_feedback

    parser = argparse.ArgumentParser(
        description="Top-N crypto multi-timeframe RSI overextension scanner."
    )
    parser.add_argument("--top-n", type=int, default=None, help="Number of coins to scan.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and print, but send no notifications and don't update state.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print signal-outcome stats (hit-rates, forward returns) and exit.",
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="Print the paper-trade scoreboard (realized P&L by book/setup) and exit.",
    )
    parser.add_argument(
        "--refresh-paper",
        action="store_true",
        help="Fetch open paper-trade histories, close matured positions, and print the scoreboard without alerts.",
    )
    parser.add_argument(
        "--event-fade-report",
        action="store_true",
        help="Score local event-fade JSON fixtures and print an alert-only report.",
    )
    parser.add_argument(
        "--event-discovery-report",
        action="store_true",
        help="Print research-only event radar from local discovery fixtures.",
    )
    parser.add_argument(
        "--event-alert-report",
        action="store_true",
        help="Print ranked research-only event-alert candidates from discovery fixtures.",
    )
    parser.add_argument(
        "--event-alpha-radar-report",
        action="store_true",
        help="Print research-only event alpha radar with opt-in market enrichment/anomaly inputs.",
    )
    parser.add_argument(
        "--event-alpha-cycle",
        action="store_true",
        help="Run one unified research-only Event Alpha cycle (alerts, watchlist, router summary).",
    )
    parser.add_argument(
        "--event-alpha-notify-cycle",
        action="store_true",
        help="Run a day-1 Event Alpha notification burn-in cycle with lane-specific guarded sends.",
    )
    parser.add_argument(
        "--event-alpha-scheduled-catalyst-report",
        action="store_true",
        help="Normalize scheduled catalyst/unlock fixtures into research-only Event Alpha artifacts.",
    )
    parser.add_argument(
        "--event-alpha-unlock-calendar-preflight",
        action="store_true",
        help="Write structured unlock/calendar provider preflight artifacts without live calls.",
    )
    parser.add_argument(
        "--event-alpha-tokenomist-preflight",
        action="store_true",
        help="Write Tokenomist unlock provider preflight artifacts without live calls.",
    )
    parser.add_argument(
        "--event-alpha-messari-unlocks-preflight",
        action="store_true",
        help="Write Messari unlock provider preflight artifacts without live calls.",
    )
    parser.add_argument(
        "--event-alpha-coinmarketcal-preflight",
        action="store_true",
        help="Write CoinMarketCal provider preflight artifacts without live calls.",
    )
    parser.add_argument(
        "--event-alpha-dex-onchain-readiness",
        action="store_true",
        help="Write DEX/on-chain/protocol fundamentals readiness artifacts from fixtures without live calls.",
    )
    parser.add_argument(
        "--event-alpha-dex-onchain-readiness-smoke",
        action="store_true",
        help="Write fixture-only DEX/on-chain/protocol fundamentals readiness smoke artifacts; no network or keys required.",
    )
    parser.add_argument(
        "--event-alpha-derivatives-report",
        action="store_true",
        help="Normalize derivatives crowding fixtures into research-only fade/short-review artifacts.",
    )
    parser.add_argument(
        "--ignore-provider-backoff",
        action="store_true",
        help="With --event-alpha-notify-cycle, attempt providers even if local provider health is in backoff for this run only.",
    )
    parser.add_argument(
        "--event-alpha-notify-preview",
        action="store_true",
        help="Preview Event Alpha notification readiness, would-send counts, and lane cooldowns.",
    )
    parser.add_argument(
        "--event-alpha-notify-preview-from-artifacts",
        action="store_true",
        help="Regenerate Event Alpha notification preview and structured preview delivery telemetry from local artifacts only.",
    )
    parser.add_argument(
        "--event-alpha-notify-go-no-go",
        action="store_true",
        help="Print Event Alpha notification preview/send go-no-go readiness.",
    )
    parser.add_argument(
        "--event-alpha-environment-doctor",
        action="store_true",
        help="Print scheduled Event Alpha notification environment readiness.",
    )
    parser.add_argument(
        "--event-alpha-pause-notifications",
        action="store_true",
        help="Write a namespace-scoped Event Alpha notification pause file.",
    )
    parser.add_argument(
        "--event-alpha-resume-notifications",
        action="store_true",
        help="Clear the namespace-scoped Event Alpha notification pause file. Requires --confirm.",
    )
    parser.add_argument(
        "--event-alpha-scheduler-status",
        action="store_true",
        help="Print Event Alpha scheduled notification run freshness and lock status.",
    )
    parser.add_argument(
        "--event-alpha-generate-launchd",
        action="store_true",
        help="Print or write a launchd plist template for scheduled Event Alpha notifications.",
    )
    parser.add_argument(
        "--event-alpha-notification-slo-report",
        action="store_true",
        help="Print Event Alpha notification SLO/freshness status.",
    )
    parser.add_argument(
        "--event-alpha-export-notification-pack",
        action="store_true",
        help="Write a redacted zip of notification artifacts and operator reports. Use --out OUT.zip.",
    )
    parser.add_argument(
        "--event-alpha-notification-checklist",
        action="store_true",
        help="Print day-1 Event Alpha notification startup checklist.",
    )
    parser.add_argument(
        "--event-alpha-send-readiness",
        action="store_true",
        help="Check latest notification rehearsal artifacts before enabling real Event Alpha Telegram sends.",
    )
    parser.add_argument(
        "--event-alpha-telegram-final-check",
        action="store_true",
        help="Print compact final Event Alpha Telegram no-send/readiness result from existing artifacts.",
    )
    parser.add_argument(
        "--event-alpha-send-test",
        action="store_true",
        help="Send one guarded research-only Event Alpha heartbeat without running providers.",
    )
    parser.add_argument(
        "--event-alpha-telegram-recipient-check",
        action="store_true",
        help="Send a guarded research-only Telegram diagnostic to each configured Event Alpha recipient.",
    )
    parser.add_argument(
        "--ignore-notification-pause",
        action="store_true",
        help="Allow --event-alpha-send-test to bypass the local notification pause file.",
    )
    parser.add_argument(
        "--event-alpha-notification-runs-report",
        action="store_true",
        help="Print recent Event Alpha notification-cycle summary rows.",
    )
    parser.add_argument(
        "--event-alpha-notification-inbox",
        action="store_true",
        help="Print unreviewed Event Alpha notification/card follow-up queues.",
    )
    parser.add_argument(
        "--event-alpha-burn-in-review",
        action="store_true",
        help="Print a compact burn-in notification review inbox instead of the full row-level inbox.",
    )
    parser.add_argument(
        "--event-alpha-notification-deliveries-report",
        action="store_true",
        help="Print the research-only Event Alpha notification delivery ledger for a profile/namespace.",
    )
    parser.add_argument(
        "--event-alpha-notification-retry-failed",
        action="store_true",
        help="List failed Event Alpha notification deliveries (dry-run scaffold; --confirm required to proceed).",
    )
    parser.add_argument(
        "--event-alpha-provider-health-report",
        action="store_true",
        help="Print profile-scoped Event Alpha provider health/backoff rows.",
    )
    parser.add_argument(
        "--event-alpha-cryptopanic-preflight",
        action="store_true",
        help="Print redacted CryptoPanic readiness/backoff/source-pack preflight for Event Alpha.",
    )
    parser.add_argument(
        "--event-alpha-source-coverage-report",
        action="store_true",
        help="Print source-pack provider/evidence coverage for Event Alpha research artifacts.",
    )
    parser.add_argument(
        "--event-alpha-live-provider-readiness",
        action="store_true",
        help="Write live-provider activation readiness artifacts without live provider calls.",
    )
    parser.add_argument(
        "--event-alpha-live-provider-readiness-smoke",
        action="store_true",
        help="Write fixture/config-only live-provider readiness artifacts; no network, keys, or sends required.",
    )
    parser.add_argument(
        "--event-alpha-coinalyze-preflight",
        action="store_true",
        help="Write Coinalyze derivatives/OI/funding no-call preflight artifacts.",
    )
    parser.add_argument(
        "--event-alpha-coinalyze-preflight-smoke",
        action="store_true",
        help="Write fixture-only Coinalyze preflight artifacts; no key or network required.",
    )
    parser.add_argument(
        "--event-alpha-coinalyze-no-send-rehearsal",
        action="store_true",
        help="Run guarded Coinalyze no-send rehearsal stub; no live calls unless explicitly allowed.",
    )
    parser.add_argument(
        "--event-alpha-coinalyze-allow-live-preflight",
        action="store_true",
        help="Allow future bounded Coinalyze live preflight path. Tests and smokes must leave this off.",
    )
    parser.add_argument(
        "--event-alpha-bybit-announcements-preflight",
        action="store_true",
        help="Write Bybit official-announcements no-call preflight artifacts.",
    )
    parser.add_argument(
        "--event-alpha-bybit-announcements-preflight-smoke",
        action="store_true",
        help="Write fixture/parser-only Bybit announcement preflight artifacts; no network or key required.",
    )
    parser.add_argument(
        "--event-alpha-bybit-announcements-no-send-rehearsal",
        action="store_true",
        help="Run guarded Bybit announcements no-send rehearsal; no live calls unless explicitly allowed.",
    )
    parser.add_argument(
        "--event-alpha-bybit-announcements-allow-live-preflight",
        action="store_true",
        help="Allow bounded Bybit announcements live preflight/no-send rehearsal. Tests and smokes must leave this off.",
    )
    parser.add_argument(
        "--event-alpha-mark-namespace-stale",
        action="store_true",
        help="Mark the selected Event Alpha artifact namespace stale/deprecated so default reports skip it.",
    )
    parser.add_argument(
        "--event-alpha-mark-known-stale-namespaces",
        action="store_true",
        help="Mark known pre-canonical Event Alpha artifact namespaces stale/deprecated.",
    )
    parser.add_argument(
        "--event-alpha-prune-or-archive-stale-namespace",
        action="store_true",
        help="Print a dry-run prune/archive plan for a stale Event Alpha artifact namespace.",
    )
    parser.add_argument(
        "--event-alpha-namespace-lifecycle-report",
        action="store_true",
        help="Write and print the Event Alpha namespace lifecycle inventory report.",
    )
    parser.add_argument(
        "--event-alpha-list-active-namespaces",
        action="store_true",
        help="Print active Event Alpha artifact namespaces from lifecycle inventory.",
    )
    parser.add_argument(
        "--event-alpha-archive-stale-namespaces",
        action="store_true",
        help="Print a dry-run archive plan for stale Event Alpha artifact namespaces.",
    )
    parser.add_argument(
        "--event-alpha-stale-superseded-by",
        default=None,
        help="Optional replacement namespace for --event-alpha-mark-namespace-stale.",
    )
    parser.add_argument(
        "--event-alpha-stale-archive",
        action="store_true",
        help="For stale namespace prune/archive plan, mark archive intent; output remains dry-run only.",
    )
    parser.add_argument(
        "--event-alpha-provider-health-reset",
        action="store_true",
        help="Clear selected profile-scoped provider health backoff state. Requires --confirm.",
    )
    parser.add_argument(
        "--event-alpha-notify-fixture-smoke",
        action="store_true",
        help="Run a local fake-sender Event Alpha notification smoke under a fixture namespace.",
    )
    parser.add_argument(
        "--event-alpha-notification-runs-path",
        default=None,
        help="Optional Event Alpha notification summary JSONL path.",
    )
    parser.add_argument(
        "--event-alpha-runs-report",
        action="store_true",
        help="Print recent research-only Event Alpha cycle run ledger rows.",
    )
    parser.add_argument(
        "--event-impact-hypotheses-report",
        action="store_true",
        help="Print stored research-only Event Impact Hypothesis rows for a profile/namespace.",
    )
    parser.add_argument(
        "--event-impact-hypotheses-inbox",
        action="store_true",
        help="Print stored Event Impact Hypothesis rows needing operator review for a profile/namespace.",
    )
    parser.add_argument(
        "--event-incidents-report",
        action="store_true",
        help="Print stored canonical Event Alpha incident rows for a profile/namespace.",
    )
    parser.add_argument(
        "--event-impact-hypothesis-smoke",
        action="store_true",
        help="Run offline Event Impact Hypothesis smoke: SpaceX sector hypothesis validates VELVET RADAR only.",
    )
    parser.add_argument(
        "--event-impact-hypothesis-store-path",
        default=None,
        help="Optional Event Impact Hypothesis JSONL path for --event-impact-hypotheses-report.",
    )
    parser.add_argument(
        "--event-incident-store-path",
        default=None,
        help="Optional canonical incident JSONL path for --event-incidents-report.",
    )
    parser.add_argument(
        "--include-diagnostic-incidents",
        action="store_true",
        help="For --event-incidents-report, include diagnostic/raw/external-context incidents that are hidden by default.",
    )
    parser.add_argument(
        "--include-raw-incidents",
        action="store_true",
        help="For --event-incidents-report, include raw-observation incidents hidden by default.",
    )
    parser.add_argument(
        "--include-external-context-incidents",
        action="store_true",
        help="For --event-incidents-report, include external-context-only incidents hidden by default.",
    )
    parser.add_argument(
        "--latest-run",
        action="store_true",
        help="For impact-hypothesis reports, show only rows from the latest stored run_id. This is the default unless --all-history, --run-id, or --since is used.",
    )
    parser.add_argument(
        "--all-history",
        action="store_true",
        help="For impact-hypothesis reports, include all historical rows instead of defaulting to the latest run.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="For impact-hypothesis reports, show only rows from this stored run_id.",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="For impact-hypothesis reports, show rows observed at or after this ISO timestamp.",
    )
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="For impact-hypothesis reports, include legacy/missing-schema rows in filtered output.",
    )
    parser.add_argument(
        "--event-alpha-run-ledger-path",
        default=None,
        help="Optional Event Alpha run ledger JSONL path for --event-alpha-runs-report.",
    )
    parser.add_argument(
        "--event-alpha-run-limit",
        type=int,
        default=20,
        help="Maximum rows to show for --event-alpha-runs-report.",
    )
    parser.add_argument(
        "--event-alpha-status",
        action="store_true",
        help="Print profile-aware Event Alpha source, artifact, send, and LLM budget status.",
    )
    parser.add_argument(
        "--event-alpha-preflight",
        action="store_true",
        help="Preflight profile-scoped Event Alpha artifact paths, providers, LLM budget, and send guards.",
    )
    parser.add_argument(
        "--event-alpha-feedback-readiness",
        action="store_true",
        help="Check Event Alpha card lineage, inbox feedback targets, and calibration fields without sending or mutating tiers.",
    )
    parser.add_argument(
        "--event-watchlist-refresh",
        action="store_true",
        help="Refresh research-only event alpha watchlist state from current alert candidates.",
    )
    parser.add_argument(
        "--event-watchlist-report",
        action="store_true",
        help="Print latest research-only event alpha watchlist state.",
    )
    parser.add_argument(
        "--event-watchlist-monitor",
        action="store_true",
        help="Monitor active event alpha watchlist rows without requiring new source evidence.",
    )
    parser.add_argument(
        "--event-alpha-router-report",
        action="store_true",
        help="Print research-only Event Alpha Radar route decisions from watchlist state.",
    )
    parser.add_argument(
        "--event-alpha-signal-quality-eval",
        action="store_true",
        help="Run the offline curated Event Alpha signal-quality benchmark.",
    )
    parser.add_argument(
        "--event-alpha-signal-quality-cases-path",
        default=None,
        help="Optional JSON fixture path for --event-alpha-signal-quality-eval.",
    )
    parser.add_argument(
        "--event-opportunity-audit",
        metavar="TARGET",
        help="Explain one Event Alpha opportunity decision path from local artifacts.",
    )
    parser.add_argument(
        "--event-alpha-quality-review",
        action="store_true",
        help="Print latest Event Alpha signal-quality review from local artifacts.",
    )
    parser.add_argument(
        "--event-alpha-quality-coverage-report",
        action="store_true",
        help="Strictly check latest-run Event Alpha artifact rows for top-level signal-quality fields.",
    )
    parser.add_argument(
        "--event-alpha-policy-simulate",
        action="store_true",
        help="Simulate Event Alpha quality threshold policies from local artifacts without writing state.",
    )
    parser.add_argument(
        "--event-alpha-export-signal-quality-cases",
        action="store_true",
        help="Export proposed signal-quality benchmark cases from local artifacts.",
    )
    parser.add_argument(
        "--event-alpha-signal-quality-export-path",
        default=None,
        help="Optional output path for --event-alpha-export-signal-quality-cases.",
    )
    parser.add_argument(
        "--event-alpha-missed-report",
        action="store_true",
        help="Print missed-opportunity diagnostics from market rows and Event Alpha artifacts.",
    )
    parser.add_argument(
        "--event-alpha-near-miss-report",
        action="store_true",
        help="Print near-promotion Event Alpha candidates and targeted refresh diagnostics.",
    )
    parser.add_argument(
        "--event-alpha-calibration-report",
        action="store_true",
        help="Print research-only calibration summaries from alert, feedback, outcome, and missed artifacts.",
    )
    parser.add_argument(
        "--event-source-reliability-report",
        action="store_true",
        help="Print source/provider reliability summaries from Event Alpha artifacts.",
    )
    parser.add_argument(
        "--event-alpha-burn-in-scorecard",
        action="store_true",
        help="Print Event Alpha burn-in scorecard from run/alert/feedback/missed/provider artifacts.",
    )
    parser.add_argument(
        "--event-alpha-burn-in-checklist",
        action="store_true",
        help="Print Event Alpha burn-in acceptance checklist for research-send readiness.",
    )
    parser.add_argument(
        "--event-alpha-burn-in-readiness",
        action="store_true",
        help="Print live-style no-send Event Alpha burn-in readiness from local artifacts.",
    )
    parser.add_argument(
        "--event-alpha-v1-readiness",
        action="store_true",
        help="Print v1 promotion readiness flags for Event Alpha burn-in artifacts.",
    )
    parser.add_argument(
        "--event-alpha-health-guard",
        action="store_true",
        help="Print Event Alpha run freshness/safety guard status.",
    )
    parser.add_argument(
        "--event-alpha-artifact-doctor",
        action="store_true",
        help="Diagnose Event Alpha artifact lineage, namespace, and snapshot consistency.",
    )
    parser.add_argument(
        "--event-alpha-tuning-worksheet",
        action="store_true",
        help="Print weekly Event Alpha tuning suggestions without applying changes.",
    )
    parser.add_argument(
        "--event-alpha-export-burn-in-pack",
        metavar="OUT_ZIP",
        help="Write a clean Event Alpha burn-in review pack zip.",
    )
    parser.add_argument(
        "--event-alpha-burn-in-days",
        "--days",
        type=int,
        default=7,
        dest="event_alpha_burn_in_days",
        help="Lookback window for --event-alpha-burn-in-scorecard.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path for commands that write one artifact, such as --event-alpha-generate-launchd.",
    )
    parser.add_argument(
        "--event-alpha-calibration-export-priors",
        nargs="?",
        const="",
        metavar="OUT",
        help="Export reviewable Event Alpha calibration priors JSON; defaults to RSI_EVENT_ALPHA_PRIORS_PATH.",
    )
    parser.add_argument(
        "--event-alpha-export-eval-cases-from-feedback",
        nargs="?",
        const="",
        metavar="OUT_DIR",
        help="Export proposed eval cases from feedback artifacts without modifying canonical fixtures.",
    )
    parser.add_argument(
        "--event-alpha-export-eval-cases-from-missed",
        nargs="?",
        const="",
        metavar="OUT_DIR",
        help="Export proposed eval cases from missed-opportunity artifacts.",
    )
    parser.add_argument(
        "--event-alpha-explain-last-run",
        action="store_true",
        help="Explain why the latest Event Alpha cycle did or did not alert.",
    )
    parser.add_argument(
        "--event-alpha-daily-brief",
        action="store_true",
        help="Write and print a daily Event Alpha research brief from local artifacts.",
    )
    parser.add_argument(
        "--event-alpha-market-anomaly-scan",
        action="store_true",
        help="Write research-only market-state/anomaly artifacts from cached or fixture market rows.",
    )
    parser.add_argument(
        "--event-alpha-integrated-radar-cycle",
        action="store_true",
        help="Run the research-only integrated Event Alpha radar cycle and write local artifacts.",
    )
    parser.add_argument(
        "--event-alpha-integrated-radar-fixture",
        action="store_true",
        help="Use deterministic fixture sidecar inputs for --event-alpha-integrated-radar-cycle.",
    )
    parser.add_argument(
        "--event-alpha-integrated-radar-auto",
        action="store_true",
        help="Let --event-alpha-integrated-radar-cycle choose fixture/run/load sidecar behavior automatically.",
    )
    parser.add_argument(
        "--event-alpha-integrated-radar-run-sidecars",
        action="store_true",
        help="Run integrated radar sidecar producers when available before building integrated candidates.",
    )
    parser.add_argument(
        "--event-alpha-integrated-radar-load-existing",
        action="store_true",
        help="Build integrated radar candidates from existing local sidecar artifacts.",
    )
    parser.add_argument(
        "--event-alpha-integrated-radar-coinalyze-namespace",
        default=None,
        help="Optional Coinalyze artifact namespace to load into integrated radar enrichment; auto-checks readiness/default rehearsal when omitted.",
    )
    parser.add_argument(
        "--event-alpha-integrated-radar-fill-outcomes",
        action="store_true",
        help="Fill research-only integrated radar outcome artifacts from local fixture/cache rows.",
    )
    parser.add_argument(
        "--event-alpha-integrated-radar-outcome-report",
        action="store_true",
        help="Print the research-only integrated radar outcome report.",
    )
    parser.add_argument(
        "--event-alpha-integrated-radar-calibration-report",
        action="store_true",
        help="Print the recommendation-only integrated radar calibration report.",
    )
    parser.add_argument(
        "--event-alpha-integrated-radar-calibration-export-priors",
        action="store_true",
        help="Write recommendation-only integrated radar calibration priors JSON.",
    )
    parser.add_argument(
        "--event-alpha-market-anomaly-rows",
        default=None,
        help="Optional JSON/JSONL market rows path for --event-alpha-market-anomaly-scan.",
    )
    parser.add_argument(
        "--event-alpha-market-anomaly-asset-registry",
        default=None,
        help="Optional canonical asset registry JSON path for --event-alpha-market-anomaly-scan.",
    )
    parser.add_argument(
        "--event-alpha-market-anomaly-universe",
        default=None,
        help="Optional cached CoinGecko universe rows path for --event-alpha-market-anomaly-scan.",
    )
    parser.add_argument(
        "--event-alpha-official-exchange-report",
        action="store_true",
        help="Write research-only official exchange announcement artifacts from configured fixtures.",
    )
    parser.add_argument(
        "--event-alpha-official-exchange-binance",
        default=None,
        help="Optional Binance announcement fixture path for --event-alpha-official-exchange-report.",
    )
    parser.add_argument(
        "--event-alpha-official-exchange-bybit",
        default=None,
        help="Optional Bybit announcement fixture path for --event-alpha-official-exchange-report.",
    )
    parser.add_argument(
        "--event-alpha-scheduled-catalyst-tokenomist",
        default=None,
        help="Optional Tokenomist unlock fixture path for --event-alpha-scheduled-catalyst-report.",
    )
    parser.add_argument(
        "--event-alpha-scheduled-catalyst-messari",
        default=None,
        help="Optional Messari unlock fixture path for --event-alpha-scheduled-catalyst-report.",
    )
    parser.add_argument(
        "--event-alpha-scheduled-catalyst-coinmarketcal",
        default=None,
        help="Optional CoinMarketCal/event-calendar fixture path for --event-alpha-scheduled-catalyst-report.",
    )
    parser.add_argument(
        "--event-alpha-unlock-calendar-provider",
        default=None,
        choices=("tokenomist", "messari_unlocks", "coinmarketcal"),
        help="Optional provider filter for --event-alpha-unlock-calendar-preflight.",
    )
    parser.add_argument(
        "--event-alpha-derivatives-crowding-path",
        default=None,
        help="Optional derivatives crowding fixture path for --event-alpha-derivatives-report.",
    )
    parser.add_argument(
        "--event-alpha-replay",
        action="store_true",
        help="Replay Event Alpha local artifacts without provider calls or sends.",
    )
    parser.add_argument(
        "--event-alpha-replay-raw-events",
        default=None,
        help="Optional raw event JSONL/cache path for true local Event Alpha replay.",
    )
    parser.add_argument(
        "--event-alpha-replay-market-rows",
        default=None,
        help="Optional CoinGecko-style market rows path for --event-alpha-replay-raw-events.",
    )
    parser.add_argument(
        "--event-alpha-replay-priors",
        action="store_true",
        help="With --event-alpha-replay, show priors before/after score fields when present.",
    )
    parser.add_argument(
        "--event-alpha-replay-llm-advisory",
        action="store_true",
        help="With --event-alpha-replay, annotate the replay as LLM-advisory comparison mode.",
    )
    parser.add_argument(
        "--event-alpha-replay-compare",
        default=None,
        help="With --event-alpha-replay and raw events, compare policies such as baseline,llm,priors.",
    )
    parser.add_argument(
        "--event-alpha-replay-profile",
        default=None,
        help="Apply a profile before replaying local raw-event evidence.",
    )
    parser.add_argument(
        "--event-alpha-replay-profile-alt",
        default=None,
        help="Profile used for the profile_variant replay comparison row.",
    )
    parser.add_argument(
        "--event-alpha-prune-artifacts",
        action="store_true",
        help="Dry-run retention pruning for old Event Alpha research artifacts.",
    )
    parser.add_argument(
        "--event-alpha-priors-shadow-report",
        action="store_true",
        help="Compare current Event Alpha alert tiers/scores before and after priors without writing artifacts.",
    )
    parser.add_argument(
        "--event-opportunity-audit-include-diagnostics",
        action="store_true",
        help="With --event-opportunity-audit, include hidden diagnostic/source-noise/control rows in core opportunity audits.",
    )
    parser.add_argument(
        "--event-research-card",
        nargs="?",
        const="",
        metavar="ALERT_KEY",
        help="Print a Markdown Event Alpha research card for ALERT_KEY, or selected local cards when omitted.",
    )
    parser.add_argument(
        "--event-research-cards-write",
        action="store_true",
        help="Write selected Event Alpha research cards plus index.md under RSI_EVENT_RESEARCH_CARDS_DIR.",
    )
    parser.add_argument(
        "--event-alpha-alerts-report",
        action="store_true",
        help="Print research-only Event Alpha alert snapshot cohorts and filled outcomes.",
    )
    parser.add_argument(
        "--event-alpha-alert-store-path",
        default=None,
        help="Optional Event Alpha alert snapshot JSONL path for report/outcome commands.",
    )
    parser.add_argument(
        "--event-alpha-fill-outcomes",
        nargs=2,
        metavar=("PRICES", "OUT"),
        help="Fill Event Alpha alert snapshot outcomes from local OHLCV price fixture PRICES and write OUT.",
    )
    parser.add_argument(
        "--event-feedback-mark",
        metavar="TARGET",
        help=(
            "Append lightweight Event Alpha feedback for a watchlist key, event id, symbol, "
            "coin id, or missed opportunity target."
        ),
    )
    parser.add_argument(
        "--event-feedback-label",
        choices=event_feedback.valid_labels(),
        help="Feedback label to use with --event-feedback-mark.",
    )
    parser.add_argument(
        "--event-feedback-notes",
        default=None,
        help="Optional notes to append with --event-feedback-mark.",
    )
    parser.add_argument(
        "--event-feedback-by",
        default="human",
        help="Reviewer name to append with --event-feedback-mark.",
    )
    parser.add_argument(
        "--event-feedback-path",
        default=None,
        help="Optional feedback JSONL artifact path for mark/report commands.",
    )
    parser.add_argument(
        "--event-feedback-report",
        action="store_true",
        help="Print lightweight Event Alpha feedback artifact rows.",
    )
    parser.add_argument("--event-feedback-useful", metavar="TARGET", help="Shortcut: mark TARGET as useful.")
    parser.add_argument("--event-feedback-junk", metavar="TARGET", help="Shortcut: mark TARGET as junk.")
    parser.add_argument("--event-feedback-watch", metavar="TARGET", help="Shortcut: mark TARGET as watch.")
    parser.add_argument("--event-feedback-traded", metavar="TARGET", help="Shortcut: mark TARGET as traded elsewhere.")
    parser.add_argument("--event-feedback-ignore", metavar="TARGET", help="Shortcut: mark TARGET as ignored.")
    parser.add_argument("--event-feedback-missed", metavar="SYMBOL_OR_COIN_ID", help="Shortcut: record a missed opportunity.")
    parser.add_argument(
        "--event-llm-shadow-report",
        action="store_true",
        help="Print research-only shadow LLM relationship analysis for event candidates.",
    )
    parser.add_argument(
        "--event-llm-extract-report",
        action="store_true",
        help="Print research-only shadow LLM raw-event extraction for discovery evidence.",
    )
    parser.add_argument(
        "--event-catalyst-search-report",
        action="store_true",
        help="Print research-only market-anomaly catalyst-search diagnostics.",
    )
    parser.add_argument(
        "--event-alpha-profile",
        default=None,
        help=(
            "Apply an Event Alpha operational research profile "
            f"({', '.join(event_alpha_profiles.profile_names())})."
        ),
    )
    parser.add_argument(
        "--event-alpha-artifact-namespace",
        default=None,
        help="Restrict Event Alpha artifact reports to this namespace/profile artifact directory.",
    )
    parser.add_argument(
        "--provider-key",
        default=None,
        help="Provider health key selector for --event-alpha-provider-health-reset, such as gdelt:event_source.",
    )
    parser.add_argument(
        "--service",
        default=None,
        help="Provider health service selector for --event-alpha-provider-health-reset, such as gdelt.",
    )
    parser.add_argument(
        "--role",
        default=None,
        help="Provider health role selector for --event-alpha-provider-health-reset, such as event_source.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="With --event-alpha-provider-health-reset, clear all provider backoffs in the selected profile namespace.",
    )
    parser.add_argument(
        "--reason",
        default=None,
        help="Operator reason for --event-alpha-pause-notifications.",
    )
    parser.add_argument(
        "--event-alpha-include-test-artifacts",
        action="store_true",
        help="Include Event Alpha rows marked test/fixture/replay in artifact reports.",
    )
    parser.add_argument(
        "--event-alpha-include-legacy-artifacts",
        action="store_true",
        help="Include legacy/default Event Alpha artifact rows in artifact reports for migration review.",
    )
    parser.add_argument(
        "--event-alpha-include-stale-artifacts",
        action="store_true",
        help="Include namespaces explicitly marked stale/deprecated in artifact doctor checks.",
    )
    parser.add_argument(
        "--event-alpha-artifact-doctor-strict",
        action="store_true",
        help="Escalate fresh/current artifact mismatches, mixed namespaces, and unknown IDs to artifact-doctor blockers.",
    )
    parser.add_argument(
        "--event-alpha-artifact-doctor-strict-legacy",
        action="store_true",
        help="With strict artifact doctor, also escalate legacy quality-route conflicts to blockers.",
    )
    parser.add_argument(
        "--event-alpha-artifact-doctor-delivery-scope",
        choices=("latest_run", "all_rows", "legacy_included"),
        default=None,
        help="Scope strict notification-delivery identity checks; default checks the latest run when available.",
    )
    parser.add_argument(
        "--event-alpha-profile-report",
        metavar="PROFILE",
        help="Print an Event Alpha operational profile without running the cycle.",
    )
    parser.add_argument(
        "--event-alert-send",
        action="store_true",
        help=(
            "With --event-alert-report, send an opt-in Telegram research digest. "
            "Requires RSI_EVENT_ALERTS_ENABLED=1."
        ),
    )
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help=(
            "With --event-alert-report, run event LLM analysis. "
            "Advisory tier changes require RSI_EVENT_LLM_MODE=advisory."
        ),
    )
    parser.add_argument(
        "--event-now",
        default=None,
        help=(
            "Override the event research clock for deterministic reports "
            "(ISO-8601, e.g. 2026-06-15T16:00:00Z)."
        ),
    )
    parser.add_argument(
        "--event-discovery-refresh",
        action="store_true",
        help="Fetch configured event-discovery sources and append research-only JSONL cache artifacts.",
    )
    parser.add_argument(
        "--event-discovery-status",
        action="store_true",
        help="Print redacted readiness for research-only event-discovery providers.",
    )
    parser.add_argument(
        "--event-discovery-runs",
        action="store_true",
        help="Print recent research-cache event-discovery run diagnostics.",
    )
    parser.add_argument(
        "--event-discovery-run-limit",
        type=int,
        default=10,
        help="Maximum recent run rows to show for --event-discovery-runs.",
    )
    parser.add_argument(
        "--event-discovery-binance-listen",
        action="store_true",
        help="Listen briefly to live Binance announcements and append raw research JSONL cache artifacts.",
    )
    parser.add_argument(
        "--event-fade-auto-report",
        action="store_true",
        help="Print grouped research-only event-fade candidates from discovery fixtures.",
    )
    parser.add_argument(
        "--event-fade-export-sample",
        metavar="PATH",
        help="Export a research-only event-fade validation sample from discovery fixtures (.jsonl/.csv or '-' for JSONL stdout).",
    )
    parser.add_argument(
        "--event-fade-export-cache-sample",
        metavar="PATH",
        help="Export latest research-cache candidate snapshots as a validation sample (.jsonl/.csv or '-' for JSONL stdout).",
    )
    parser.add_argument(
        "--event-fade-review-sample",
        metavar="PATH",
        help="Review status/labels/outcomes and next sample work in a research-only event-fade validation sample export.",
    )
    parser.add_argument(
        "--event-fade-labeling-queue",
        metavar="PATH",
        help="Print prioritized validation sample rows that need human review status, labels, or outcomes.",
    )
    parser.add_argument(
        "--event-fade-review-packet",
        nargs=2,
        metavar=("SAMPLE", "OUT"),
        help="Write a Markdown manual-review packet for prioritized validation rows.",
    )
    parser.add_argument(
        "--event-fade-export-review-template",
        nargs=2,
        metavar=("SAMPLE", "OUT"),
        help="Write compact editable review sidecar rows for prioritized validation rows.",
    )
    parser.add_argument(
        "--event-fade-apply-review-template",
        nargs=3,
        metavar=("SAMPLE", "TEMPLATE", "OUT"),
        help="Apply edited compact review sidecar rows to SAMPLE and write OUT.",
    )
    parser.add_argument(
        "--event-fade-check-review-template",
        nargs=2,
        metavar=("SAMPLE", "TEMPLATE"),
        help="Dry-check edited compact review sidecar rows before applying them.",
    )
    parser.add_argument(
        "--event-fade-review-bundle",
        nargs=2,
        metavar=("SAMPLE", "OUT_DIR"),
        help="Write a local manual-review workspace for an event-fade validation sample.",
    )
    parser.add_argument(
        "--event-fade-cache-review-bundle",
        metavar="OUT_DIR",
        help="Write a local manual-review workspace from latest cached event-discovery snapshots.",
    )
    parser.add_argument(
        "--event-fade-review-bundle-prices",
        metavar="PRICES",
        help="Optional local OHLCV price fixture for review-bundle outcome filling.",
    )
    parser.add_argument(
        "--event-fade-review-bundle-export-prices",
        action="store_true",
        help=(
            "With review-bundle commands, export a bundle-local outcome price fixture "
            "when --event-fade-review-bundle-prices is not supplied."
        ),
    )
    parser.add_argument(
        "--event-fade-review-bundle-reviewed",
        metavar="REVIEWED_SAMPLE",
        help="Optional prior reviewed sample to merge into review-bundle rows before writing artifacts.",
    )
    parser.add_argument(
        "--event-fade-queue-limit",
        type=int,
        default=20,
        help=(
            "Maximum rows to show for --event-fade-labeling-queue, "
            "--event-fade-review-packet, --event-fade-export-review-template, "
            "or --event-fade-review-bundle."
        ),
    )
    parser.add_argument(
        "--event-fade-merge-sample",
        nargs=3,
        metavar=("FRESH", "REVIEWED", "OUT"),
        help="Merge human review status, labels, and outcomes from REVIEWED into FRESH and write OUT.",
    )
    parser.add_argument(
        "--event-fade-fill-outcomes",
        nargs=3,
        metavar=("SAMPLE", "PRICES", "OUT"),
        help="Fill SHORT_TRIGGERED validation outcome fields from local price fixture PRICES and write OUT.",
    )
    parser.add_argument(
        "--event-fade-overwrite-outcomes",
        action="store_true",
        help="With --event-fade-fill-outcomes, replace existing outcome fields instead of only filling blanks.",
    )
    parser.add_argument(
        "--event-fade-export-outcome-prices",
        nargs=2,
        metavar=("SAMPLE", "OUT"),
        help="Export local OHLCV price fixture for SHORT_TRIGGERED validation sample rows.",
    )
    parser.add_argument(
        "--event-fade-price-days",
        type=int,
        default=None,
        help="Days of daily kline history for --event-fade-export-outcome-prices; auto-sized when omitted.",
    )
    parser.add_argument(
        "--event-fade-price-fixture-dir",
        default=None,
        help="Offline Binance-style kline fixture directory for --event-fade-export-outcome-prices.",
    )
    parser.add_argument(
        "--event-fade-price-interval",
        choices=("1d", "1h"),
        default="1d",
        help="Kline interval for --event-fade-export-outcome-prices.",
    )
    parser.add_argument(
        "--event-fade-refresh-price-cache",
        action="store_true",
        help="Refetch Binance klines for --event-fade-export-outcome-prices instead of using cache.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON for commands that support it.",
    )
    parser.add_argument(
        "--cohorts",
        action="store_true",
        help="For --score, include live paper-trade cohort breakdowns.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print operational scan/listener health and exit.",
    )
    parser.add_argument(
        "--backup-db",
        action="store_true",
        help="Create and verify a safe SQLite backup, then prune old backups.",
    )
    parser.add_argument(
        "--verify-restore",
        nargs="?",
        const="",
        metavar="BACKUP",
        help="Restore-check a backup path, or the newest retained backup when omitted.",
    )
    parser.add_argument(
        "--maintenance",
        action="store_true",
        help="Run DB backup, restore drill, and log rotation.",
    )
    parser.add_argument(
        "--rotate-logs",
        action="store_true",
        help="Rotate oversized local scan/listener logs and prune old rotations.",
    )
    parser.add_argument(
        "--launchd-status",
        action="store_true",
        help="Print launchd status for the scan and bot agents.",
    )
    parser.add_argument(
        "--install-maintenance-agent",
        action="store_true",
        help="Install/load the daily launchd maintenance agent for this checkout.",
    )
    parser.add_argument(
        "--restart-listener",
        action="store_true",
        help="Restart the always-on bot listener launchd agent.",
    )
    parser.add_argument(
        "--universe-audit",
        action="store_true",
        help="Print the most recent universe hygiene audit.",
    )
    parser.add_argument(
        "--refresh-universe-audit",
        action="store_true",
        help="Fetch, persist, and print a fresh universe hygiene audit without a full RSI scan.",
    )
    parser.add_argument(
        "--listen",
        action="store_true",
        help="Run the bot listener loop so commands (/top, /detail, /stats) "
             "are answered in real time. Runs until stopped.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm commands that are dry-run by default, such as --event-alpha-prune-artifacts.",
    )

    parser.add_argument(
        "--export-src",
        action="store_true",
        help="Write a clean source zip using git archive and exit.",
    )
    parser.add_argument(
        "--export-src-with-artifacts",
        action="store_true",
        help="Overwrite crypto_rsi_scanner_source_with_artifacts.zip with source plus local research artifacts.",
    )
    return parser

def classify_command(argv: Sequence[str]) -> CommandSnapshot:
    for item in argv:
        if item in COMMAND_FLAG_TO_SNAPSHOT:
            return COMMAND_FLAG_TO_SNAPSHOT[item]
        if item in COMMAND_ALIAS_TO_SNAPSHOT:
            return COMMAND_ALIAS_TO_SNAPSHOT[item]
    return CommandSnapshot("run_scan", "default", "rsi")


def command_group(argv: Sequence[str]) -> str:
    return classify_command(argv).command_group


def _dest_from_flag(flag: str) -> str:
    return flag.lstrip("-").replace("-", "_")


def dispatch_key_from_args(args: argparse.Namespace) -> str:
    for flag, snapshot in COMMAND_FLAG_TO_SNAPSHOT.items():
        dest = _dest_from_flag(flag)
        if not hasattr(args, dest):
            continue
        value = getattr(args, dest)
        if isinstance(value, bool):
            if value:
                return snapshot.dispatch_key
            continue
        if value not in (None, "", False):
            return snapshot.dispatch_key
    return "run_scan"


def parse_command_snapshot(argv: Sequence[str]) -> dict[str, str]:
    snapshot = classify_command(argv)
    return {
        "command_name": snapshot.command_name,
        "flag": snapshot.flag,
        "command_group": snapshot.command_group,
    }


__all__ = (
    "CommandSnapshot",
    "build_parser",
    "classify_command",
    "command_group",
    "dispatch_key_from_args",
    "parse_command_snapshot",
)
