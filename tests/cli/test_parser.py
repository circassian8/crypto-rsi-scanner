"""Focused pytest checks for CLI parser snapshots."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from crypto_rsi_scanner.cli.parser import (
    build_parser,
    classify_command,
    command_group,
    dispatch_key_from_args,
)


ROOT = Path(__file__).resolve().parents[2]


def test_build_parser_preserves_core_defaults():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.top_n is None
    assert args.dry_run is False
    assert args.report is False
    assert args.score is False
    assert args.event_alpha_profile is None
    assert args.event_alpha_artifact_namespace is None
    assert args.event_alpha_run_limit == 20
    assert args.event_discovery_run_limit == 10
    assert args.event_fade_queue_limit == 20
    assert args.event_alpha_coinalyze_allow_live_preflight is False
    assert args.event_alpha_bybit_announcements_allow_live_preflight is False
    assert dispatch_key_from_args(args) == "run_scan"


def test_build_parser_preserves_default_rsi_scan_options():
    parser = build_parser()
    args = parser.parse_args(["--dry-run", "--top-n", "30", "--verbose"])
    assert args.dry_run is True
    assert args.top_n == 30
    assert args.verbose is True
    assert dispatch_key_from_args(args) == "dry_run"
    assert classify_command(["--top-n", "30"]).command_name == "run_scan"
    assert command_group(["--top-n", "30"]) == "rsi"


def test_build_parser_preserves_paper_and_maintenance_flags():
    parser = build_parser()
    paper = parser.parse_args(["--score", "--json", "--cohorts"])
    assert paper.score is True
    assert paper.json is True
    assert paper.cohorts is True
    assert dispatch_key_from_args(paper) == "score"

    refresh = parser.parse_args(["--refresh-paper"])
    assert refresh.refresh_paper is True
    assert dispatch_key_from_args(refresh) == "refresh_paper"

    backup = parser.parse_args(["--backup-db"])
    assert backup.backup_db is True
    assert dispatch_key_from_args(backup) == "backup_db"

    maintenance = parser.parse_args(["--maintenance"])
    assert maintenance.maintenance is True
    assert dispatch_key_from_args(maintenance) == "maintenance"


def test_build_parser_preserves_integrated_radar_flags():
    parser = build_parser()
    args = parser.parse_args([
        "--event-alpha-integrated-radar-cycle",
        "--event-alpha-integrated-radar-load-existing",
        "--event-alpha-integrated-radar-coinalyze-namespace",
        "coinalyze_no_send_rehearsal",
        "--event-alpha-profile",
        "fixture",
    ])
    assert args.event_alpha_integrated_radar_cycle is True
    assert args.event_alpha_integrated_radar_load_existing is True
    assert args.event_alpha_integrated_radar_coinalyze_namespace == "coinalyze_no_send_rehearsal"
    assert args.event_alpha_profile == "fixture"
    assert dispatch_key_from_args(args) == "event_alpha_integrated_radar_cycle"


def test_build_parser_preserves_artifact_doctor_and_notification_flags():
    parser = build_parser()
    doctor = parser.parse_args([
        "--event-alpha-artifact-doctor",
        "--event-alpha-artifact-doctor-strict",
        "--event-alpha-artifact-doctor-delivery-scope",
        "latest_run",
    ])
    assert doctor.event_alpha_artifact_doctor is True
    assert doctor.event_alpha_artifact_doctor_strict is True
    assert doctor.event_alpha_artifact_doctor_delivery_scope == "latest_run"
    assert dispatch_key_from_args(doctor) == "event_alpha_artifact_doctor"

    preview = parser.parse_args([
        "--event-alpha-notify-preview",
        "--event-alpha-profile",
        "notify_no_key",
    ])
    assert preview.event_alpha_notify_preview is True
    assert preview.event_alpha_profile == "notify_no_key"
    assert dispatch_key_from_args(preview) == "event_alpha_notify_preview"


def test_build_parser_preserves_provider_preflight_flags():
    parser = build_parser()
    readiness = parser.parse_args(["--event-alpha-live-provider-readiness"])
    assert readiness.event_alpha_live_provider_readiness is True
    assert dispatch_key_from_args(readiness) == "event_alpha_live_provider_readiness"

    coinalyze = parser.parse_args([
        "--event-alpha-coinalyze-no-send-rehearsal",
        "--event-alpha-coinalyze-allow-live-preflight",
    ])
    assert coinalyze.event_alpha_coinalyze_no_send_rehearsal is True
    assert coinalyze.event_alpha_coinalyze_allow_live_preflight is True
    assert dispatch_key_from_args(coinalyze) == "event_alpha_coinalyze_no_send_rehearsal"

    bybit = parser.parse_args([
        "--event-alpha-bybit-announcements-preflight",
        "--event-alpha-bybit-announcements-allow-live-preflight",
    ])
    assert bybit.event_alpha_bybit_announcements_preflight is True
    assert bybit.event_alpha_bybit_announcements_allow_live_preflight is True
    assert dispatch_key_from_args(bybit) == "event_alpha_bybit_announcements_preflight"

    official = parser.parse_args([
        "--event-alpha-official-exchange-report",
        "--event-alpha-official-exchange-binance",
        "binance.json",
        "--event-alpha-official-exchange-bybit",
        "bybit.json",
    ])
    assert official.event_alpha_official_exchange_report is True
    assert official.event_alpha_official_exchange_binance == "binance.json"
    assert official.event_alpha_official_exchange_bybit == "bybit.json"
    assert dispatch_key_from_args(official) == "event_alpha_official_exchange_report"


def test_classify_command_groups_cover_representative_paths():
    cases = [
        ([], "run_scan", "rsi"),
        (["--dry-run"], "dry_run", "rsi"),
        (["-m", "crypto_rsi_scanner.backtest", "--fixture-dir", "fixtures/backtest_smoke"], "backtest", "backtest"),
        (["--score"], "score", "paper"),
        (["--backup-db"], "backup_db", "maintenance"),
        (["--export-src"], "export_src", "export"),
        (["--event-alpha-integrated-radar-cycle"], "event_alpha_integrated_radar_cycle", "event_alpha_integrated_radar"),
        (["--event-alpha-artifact-doctor"], "event_alpha_artifact_doctor", "event_alpha_artifact_doctor"),
        (["--event-alpha-notify-preview"], "event_alpha_notify_preview", "event_alpha_notification"),
        (["--event-alpha-live-provider-readiness"], "event_alpha_live_provider_readiness", "event_alpha_provider_readiness"),
        (["--event-alpha-coinalyze-preflight"], "event_alpha_coinalyze_preflight", "event_alpha_coinalyze"),
        (
            ["--event-alpha-bybit-announcements-preflight"],
            "event_alpha_bybit_announcements_preflight",
            "event_alpha_official_exchange",
        ),
    ]
    for argv, command_name, group in cases:
        snapshot = classify_command(argv)
        assert snapshot.command_name == command_name
        assert snapshot.command_group == group
        assert command_group(argv) == group


def test_scanner_and_cli_main_help_smoke():
    for module in ("crypto_rsi_scanner.scanner", "crypto_rsi_scanner.cli.main"):
        result = subprocess.run(
            [sys.executable, "-m", module, "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "RuntimeWarning" not in result.stderr
        assert "Top-N crypto multi-timeframe RSI overextension scanner" in result.stdout
        assert "--event-alpha-integrated-radar-cycle" in result.stdout
        assert "--event-alpha-artifact-doctor" in result.stdout
        assert "--event-alpha-coinalyze-preflight" in result.stdout
        assert "--event-alpha-bybit-announcements-preflight" in result.stdout
