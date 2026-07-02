"""Makefile, export, CI, and refactor-baseline static tests."""

from __future__ import annotations

from tests.rsi import _legacy_helpers as _legacy

globals().update({name: getattr(_legacy, name) for name in dir(_legacy) if not name.startswith("__")})

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---

def test_makefile_has_clean_export_and_bootstrap_targets():
    import importlib.util
    import subprocess
    import time
    import zipfile
    from datetime import datetime
    from pathlib import Path

    root = REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert "PYTHON ?= .venv/bin/python" in makefile
    assert "test-rsi:" in makefile
    assert "$(PYTHON) -m pytest tests/rsi" in makefile
    assert "test-cli:" in makefile
    assert "$(PYTHON) -m pytest tests/cli" in makefile
    assert "pytest-xdist is not installed; skipping parallel pytest run." in makefile
    assert "EVENT_FIXTURE_NOW ?= 2026-06-15T16:00:00Z" in makefile
    assert "EVENT_RESEARCH_NOW ?=" in makefile
    assert "EVENT_FIXTURE_NOW_ENV = RSI_EVENT_RESEARCH_NOW=$(EVENT_FIXTURE_NOW)" in makefile
    assert "EVENT_RESEARCH_NOW_ENV = $(if $(strip $(EVENT_RESEARCH_NOW)),RSI_EVENT_RESEARCH_NOW=$(EVENT_RESEARCH_NOW),)" in makefile
    assert "event-incidents-report:" in makefile
    assert "--event-incidents-report" in makefile
    assert "RSI_EVENT_RESEARCH_NOW=$(EVENT_RESEARCH_NOW) \\" not in makefile
    notify_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-no-key", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_RESEARCH_NOW=" not in notify_dry
    notify_fixed_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-notify-no-key",
            "PYTHON=python3",
            "EVENT_RESEARCH_NOW=2026-06-20T12:00:00Z",
        ],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_RESEARCH_NOW=2026-06-20T12:00:00Z" in notify_fixed_dry
    notify_ignore_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-no-key", "PYTHON=python3", "IGNORE_BACKOFF=1"],
        cwd=root,
        text=True,
    )
    assert "--ignore-provider-backoff" in notify_ignore_dry
    day1_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-day1-start", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "event-alpha-preflight PROFILE=notify_no_key" in day1_dry
    assert "event-alpha-notification-checklist PROFILE=notify_no_key" in day1_dry
    assert "event-alpha-notify-preview PROFILE=notify_no_key" in day1_dry
    assert "main.py --event-alpha-send-test" not in day1_dry
    assert "main.py --event-alpha-notify-cycle" not in day1_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=notify_no_key" in day1_dry
    fixture_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-cycle", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_RESEARCH_NOW=2026-06-15T16:00:00Z" in fixture_dry
    notify_report_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-notification-runs-report",
            "PROFILE=notify_no_key",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=notify_no_key" in notify_report_dry
    assert "--event-alpha-notification-runs-report --event-alpha-profile notify_no_key" in notify_report_dry
    assert "RSI_EVENT_ALPHA_NOTIFICATION_RUNS_PATH=" not in notify_report_dry
    inbox_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notification-inbox", "PROFILE=notify_no_key", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-notification-inbox --event-alpha-profile notify_no_key" in inbox_dry
    fixture_smoke_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-fixture-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-notify-fixture-smoke" in fixture_smoke_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=fixture_notify_smoke" in fixture_smoke_dry
    deep_no_send_smoke_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-llm-deep-no-send-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-notify-fixture-smoke" in deep_no_send_smoke_dry
    assert "RSI_EVENT_ALPHA_NOTIFY_FIXTURE_NO_SEND=1" in deep_no_send_smoke_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=notify_llm_deep_no_send_smoke" in deep_no_send_smoke_dry
    deep_research_review_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-llm-deep-research-review-no-send-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_ALPHA_NOTIFY_FIXTURE_PROFILE=notify_llm_deep" in deep_research_review_dry
    assert "RSI_EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED=1" in deep_research_review_dry
    assert "research_review_digest_candidates" in deep_research_review_dry
    assert "notify_llm_deep_research_review_smoke" in deep_research_review_dry
    assert "--event-alpha-source-coverage-report --event-alpha-profile notify_llm_deep --event-alpha-artifact-namespace notify_llm_deep_research_review_smoke" in deep_research_review_dry
    assert "event_alpha_source_coverage.md" in deep_research_review_dry
    assert "--event-alpha-daily-brief --event-alpha-profile notify_llm_deep --event-alpha-artifact-namespace notify_llm_deep_research_review_smoke --event-alpha-include-test-artifacts" in deep_research_review_dry
    assert "event_alpha_daily_brief.md" in deep_research_review_dry
    assert "--event-alpha-artifact-doctor-delivery-scope latest_run" in deep_research_review_dry
    daily_brief_namespace_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-daily-brief",
            "PROFILE=notify_llm_deep",
            "ARTIFACT_NAMESPACE=notify_llm_deep_research_review_smoke",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-profile notify_llm_deep --event-alpha-artifact-namespace notify_llm_deep_research_review_smoke --event-alpha-include-test-artifacts" in daily_brief_namespace_dry
    source_coverage_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-source-coverage-report",
            "PROFILE=notify_llm_deep",
            "ARTIFACT_NAMESPACE=notify_llm_deep_research_review_smoke",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=notify_llm_deep_research_review_smoke" in source_coverage_dry
    assert "--event-alpha-profile notify_llm_deep --event-alpha-artifact-namespace notify_llm_deep_research_review_smoke" in source_coverage_dry
    doctor_namespace_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-artifact-doctor",
            "PROFILE=notify_llm_deep_research_review_smoke",
            "STRICT=1",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-profile notify_llm_deep --event-alpha-artifact-namespace notify_llm_deep_research_review_smoke" in doctor_namespace_dry
    deep_rehearsal_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-llm-deep-real-no-send-rehearsal", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-notify-cycle --event-alpha-profile notify_llm_deep --event-alert-send" in deep_rehearsal_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in deep_rehearsal_dry
    assert "RSI_EVENT_ALERTS_ENABLED=1" not in deep_rehearsal_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=notify_llm_deep_rehearsal" in deep_rehearsal_dry
    assert "RSI_EVENT_RESEARCH_CARDS_WRITE_LIMIT=250" in deep_rehearsal_dry
    assert "--event-alpha-artifact-doctor-delivery-scope latest_run" in deep_rehearsal_dry
    cryptopanic_preflight_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-cryptopanic-preflight", "PROFILE=notify_llm_deep", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-cryptopanic-preflight --event-alpha-profile notify_llm_deep" in cryptopanic_preflight_dry
    cryptopanic_rehearsal_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-notify-llm-deep-cryptopanic-no-send-rehearsal", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "notify_llm_deep_cryptopanic_rehearsal" in cryptopanic_rehearsal_dry
    assert "--event-alpha-cryptopanic-preflight --event-alpha-profile notify_llm_deep" in cryptopanic_rehearsal_dry
    assert "--event-alpha-notify-cycle --event-alpha-profile notify_llm_deep --event-alert-send" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_CATALYST_SEARCH_MAX_ANOMALIES=2" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES=2" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_QUERIES=4" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_DISCOVERY_CRYPTOPANIC_TIMEOUT=3" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_DISCOVERY_CRYPTOPANIC_REQUESTS_PER_RUN_LIMIT=8" in cryptopanic_rehearsal_dry
    assert "RSI_EVENT_DISCOVERY_CRYPTOPANIC_MAX_PAGES_PER_QUERY=1" in cryptopanic_rehearsal_dry
    assert "event-alpha-telegram-send-one-cycle" not in cryptopanic_rehearsal_dry
    coinalyze_preflight_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-coinalyze-preflight", "PROFILE=notify_llm_deep", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-coinalyze-preflight --event-alpha-profile notify_llm_deep" in coinalyze_preflight_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=coinalyze_preflight" in coinalyze_preflight_dry
    assert "--event-alpha-artifact-namespace coinalyze_preflight" in coinalyze_preflight_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in coinalyze_preflight_dry
    assert "--event-alpha-coinalyze-allow-live-preflight" not in coinalyze_preflight_dry
    coinalyze_smoke_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-coinalyze-preflight-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-coinalyze-preflight-smoke --event-alpha-profile fixture" in coinalyze_smoke_dry
    assert "RSI_EVENT_DISCOVERY_COINALYZE_API_KEY=" in coinalyze_smoke_dry
    assert "--event-alpha-coinalyze-allow-live-preflight" not in coinalyze_smoke_dry
    coinalyze_rehearsal_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-coinalyze-no-send-rehearsal", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=coinalyze_no_send_rehearsal" in coinalyze_rehearsal_dry
    assert "--event-alpha-artifact-namespace coinalyze_no_send_rehearsal" in coinalyze_rehearsal_dry
    assert "--event-alpha-coinalyze-allow-live-preflight" not in coinalyze_rehearsal_dry
    dex_onchain_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-dex-onchain-readiness-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-dex-onchain-readiness-smoke --event-alpha-profile fixture" in dex_onchain_dry
    assert "RSI_EVENT_ALPHA_DEX_GECKOTERMINAL_PATH=fixtures/event_dex_onchain/geckoterminal_pools.json" in dex_onchain_dry
    assert "RSI_EVENT_ALPHA_DEX_COINGECKO_PATH=fixtures/event_dex_onchain/coingecko_dex_pools.json" in dex_onchain_dry
    assert "RSI_EVENT_ALPHA_PROTOCOL_DEFILLAMA_PATH=fixtures/event_dex_onchain/defillama_protocol_fundamentals.json" in dex_onchain_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in dex_onchain_dry
    bybit_preflight_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-bybit-announcements-preflight", "PROFILE=notify_llm_deep", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-bybit-announcements-preflight --event-alpha-profile notify_llm_deep" in bybit_preflight_dry
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=bybit_announcements_preflight" in bybit_preflight_dry
    assert "--event-alpha-artifact-namespace bybit_announcements_preflight" in bybit_preflight_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in bybit_preflight_dry
    assert "--event-alpha-bybit-announcements-allow-live-preflight" not in bybit_preflight_dry
    bybit_smoke_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-bybit-announcements-preflight-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-bybit-announcements-preflight-smoke --event-alpha-profile fixture" in bybit_smoke_dry
    assert "RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH=fixtures/event_discovery/official_exchange_bybit_announcements.json" in bybit_smoke_dry
    assert "--event-alpha-bybit-announcements-allow-live-preflight" not in bybit_smoke_dry
    bybit_rehearsal_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-bybit-announcements-no-send-rehearsal", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE=bybit_announcements_no_send_rehearsal" in bybit_rehearsal_dry
    assert "--event-alpha-artifact-namespace bybit_announcements_no_send_rehearsal" in bybit_rehearsal_dry
    assert "--event-alpha-bybit-announcements-allow-live-preflight" not in bybit_rehearsal_dry
    notify_preview_from_artifacts_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-notify-preview-from-artifacts",
            "PROFILE=notify_llm_deep",
            "ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-notify-preview-from-artifacts --event-alpha-profile notify_llm_deep" in notify_preview_from_artifacts_dry
    assert "RSI_EVENT_ALERTS_ENABLED=0" in notify_preview_from_artifacts_dry
    known_stale_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-mark-known-stale-namespaces", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "--event-alpha-mark-known-stale-namespaces" in known_stale_dry
    assert "check-python:" in makefile
    assert "bootstrap:" in makefile
    assert "python3 -m venv .venv" in makefile
    assert "export-src:" in makefile
    assert "git archive --format=zip -o crypto-rsi-scanner-source.zip HEAD" in makefile
    assert "export-src-with-artifacts:" in makefile
    assert "python3 scripts/export_source_with_artifacts.py" in makefile
    assert "event-fade-check-review-template:" in makefile
    assert "--event-fade-check-review-template $(EVENT_FADE_SAMPLE_IN) $(EVENT_FADE_REVIEW_TEMPLATE)" in makefile
    assert "event-fade-check-review-bundle:" in makefile
    assert "--event-fade-check-review-template $(EVENT_FADE_REVIEW_BUNDLE_SAMPLE) $(EVENT_FADE_REVIEW_BUNDLE_TEMPLATE)" in makefile
    assert "event-fade-apply-review-bundle:" in makefile
    assert "--event-fade-apply-review-template $(EVENT_FADE_REVIEW_BUNDLE_SAMPLE) $(EVENT_FADE_REVIEW_BUNDLE_TEMPLATE) $(EVENT_FADE_REVIEW_BUNDLE_APPLIED)" in makefile
    assert "event-fade-review-applied-bundle:" in makefile
    assert "--event-fade-review-sample $(EVENT_FADE_REVIEW_BUNDLE_APPLIED)" in makefile
    assert "event-fade-fill-review-bundle-outcomes:" in makefile
    assert "--event-fade-fill-outcomes $(EVENT_FADE_REVIEW_BUNDLE_APPLIED) $(EVENT_FADE_REVIEW_BUNDLE_OUTCOME_PRICES) $(EVENT_FADE_REVIEW_BUNDLE_OUTCOMES)" in makefile
    assert "Run 'make bootstrap' or override with 'make verify PYTHON=python3'." in makefile

    export_dry = subprocess.run(
        ["make", "-n", "export-src"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "git archive --format=zip -o crypto-rsi-scanner-source.zip HEAD" in export_dry.stdout

    export_artifacts_dry = subprocess.run(
        ["make", "-n", "export-src-with-artifacts"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "python3 scripts/export_source_with_artifacts.py" in export_artifacts_dry.stdout

    spec = importlib.util.spec_from_file_location(
        "export_source_with_artifacts",
        root / "scripts" / "export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    export_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export_module)
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        future_file = tmp_path / "Makefile"
        future_file.write_text("all:\n\t@true\n", encoding="utf-8")
        now_ts = time.time()
        future_ts = now_ts + 86400
        os.utime(future_file, (future_ts, future_ts))
        out_zip = tmp_path / "out.zip"
        with zipfile.ZipFile(out_zip, "w") as zf:
            export_module._write_file_to_zip(zf, future_file, "Makefile", now_ts=now_ts)
        with zipfile.ZipFile(out_zip) as zf:
            zipped_ts = datetime(*zf.getinfo("Makefile").date_time).timestamp()
        assert zipped_ts <= now_ts + 2
        assert zipped_ts < future_ts - 3600
        original_epoch = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "315619200"
        try:
            safe_ts = export_module._safe_export_timestamp(now_ts=now_ts)
        finally:
            if original_epoch is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = original_epoch
        assert safe_ts == 315619200

    verify_dry = subprocess.run(
        ["make", "-n", "verify", "PYTHON=python3"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "python3 tests/test_indicators.py" in verify_dry.stdout
    assert ".venv/bin/python tests/test_indicators.py" not in verify_dry.stdout

    bundle_check_dry = subprocess.run(
        [
            "make",
            "-n",
            "event-fade-check-review-bundle",
            "PYTHON=python3",
            "EVENT_FADE_REVIEW_BUNDLE_DIR=/tmp/review_bundle",
        ],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert (
        "python3 main.py --event-fade-check-review-template "
        "/tmp/review_bundle/validation_sample.jsonl "
        "/tmp/review_bundle/review_template_balanced.csv"
    ) in bundle_check_dry.stdout

    bundle_outcomes_dry = subprocess.run(
        [
            "make",
            "-n",
            "event-fade-fill-review-bundle-outcomes",
            "PYTHON=python3",
            "EVENT_FADE_REVIEW_BUNDLE_DIR=/tmp/review_bundle",
        ],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert (
        "python3 main.py --event-fade-fill-outcomes "
        "/tmp/review_bundle/validation_sample_reviewed.jsonl "
        "/tmp/review_bundle/outcome_prices.json "
        "/tmp/review_bundle/validation_sample_reviewed_with_outcomes.jsonl"
    ) in bundle_outcomes_dry.stdout


def test_normalize_export_timestamps_clamps_future_mtimes():
    import os
    from scripts import normalize_export_timestamps

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        future = root / "future.txt"
        future.write_text("future\n", encoding="utf-8")
        old = root / "old.txt"
        old.write_text("old\n", encoding="utf-8")
        now_ts = 1_800_000_000.0
        os.utime(future, (now_ts + 500, now_ts + 500))
        os.utime(old, (now_ts - 500, now_ts - 500))
        changed = normalize_export_timestamps.normalize_path_timestamps(root, now_ts=now_ts)
        assert changed == 1
        assert future.stat().st_mtime <= now_ts
        assert old.stat().st_mtime == now_ts - 500


def test_github_actions_are_safe_fixture_verification_only():
    root = REPO_ROOT
    verify = root / ".github" / "workflows" / "verify.yml"
    smoke = root / ".github" / "workflows" / "event-alpha-smoke.yml"
    assert verify.exists()
    assert smoke.exists()
    verify_text = verify.read_text(encoding="utf-8")
    smoke_text = smoke.read_text(encoding="utf-8")
    text = (verify_text + "\n" + smoke_text).casefold()

    assert "on:\n  push:\n  pull_request:" in verify_text
    assert "workflow_dispatch" not in verify_text
    assert "on:\n  workflow_dispatch:" in smoke_text
    assert "\n  push:" not in smoke_text
    assert "\n  pull_request:" not in smoke_text
    assert "permissions:\n  contents: read" in verify_text
    assert "permissions:\n  contents: read" in smoke_text
    assert 'RSI_EVENT_ALERTS_ENABLED: "0"' in verify_text
    assert 'RSI_EVENT_ALERTS_ENABLED: "0"' in smoke_text
    assert 'RSI_EVENT_RESEARCH_NOW: "2026-06-15T16:00:00Z"' in verify_text
    assert 'RSI_EVENT_RESEARCH_NOW: "2026-06-15T16:00:00Z"' in smoke_text

    verify_runs = [line.split("run:", 1)[1].strip() for line in verify_text.splitlines() if line.strip().startswith("run:")]
    assert verify_runs == [
        "python3 -m pip install --disable-pip-version-check -r requirements.txt pytest",
        "python3 tests/test_indicators.py",
        "python3 -m pytest",
        "python3 -m compileall -q crypto_rsi_scanner tests",
        "make verify PYTHON=python3",
    ]
    smoke_runs = [line.split("run:", 1)[1].strip() for line in smoke_text.splitlines() if line.strip().startswith("run:")]
    assert smoke_runs == [
        "python3 -m pip install --disable-pip-version-check -r requirements.txt pytest",
        "make event-alpha-integrated-radar-smoke PYTHON=python3",
        "make event-alpha-integrated-radar-doctor PYTHON=python3",
        "make event-alpha-live-provider-readiness-smoke PYTHON=python3",
        "make event-alpha-coinalyze-preflight-smoke PYTHON=python3",
    ]

    forbidden = (
        "allow_live",
        "allow-live",
        "_allow_live",
        "allow_live_preflight",
        "allow-live-preflight",
        "rsi_event_alpha_coinalyze_allow_live_preflight",
        "rsi_event_alpha_bybit_announcements_allow_live_preflight",
        "rsi_event_alerts_enabled=1",
        'rsi_event_alerts_enabled: "1"',
        "secrets.",
        "telegram",
        "api_key",
        "api-secret",
        "api_secret",
        "bot_token",
        "event-alert-send",
        "event-alert-no-key-send",
        "event-alpha-cycle-send",
        "event-alpha-cycle-profile-send",
        "event-alpha-daily-send",
        "event-alpha-notify-cycle",
        "event-alpha-telegram-send-one-cycle",
        "telegram_bot_token",
        "coinalyze_api_key",
        "--event-alert-send",
    )
    for item in forbidden:
        assert item not in text
    assert "make verify python=python3" in text
    assert "event-alpha-integrated-radar-smoke" in text
    assert "--upgrade pip" not in text


def test_refactor_baseline_generation_writes_reports_without_behavior_invocation():
    from crypto_rsi_scanner import refactor_baseline

    root = REPO_ROOT
    with TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "research"
        paths = refactor_baseline.write_refactor_baseline(root=root, out_dir=out_dir)
        assert paths["json"].exists()
        assert paths["markdown"].exists()
        payload = json.loads(paths["json"].read_text(encoding="utf-8"))
        markdown = paths["markdown"].read_text(encoding="utf-8")

    assert payload["schema_version"] == "refactor_baseline_v1"
    assert payload["static_inventory_only"] is True
    assert payload["behavior_changing_code_invoked"] is False
    assert payload["live_provider_calls_allowed"] is False
    assert payload["telegram_sends"] == 0
    assert payload["trades_created"] == 0
    assert payload["paper_trades_created"] == 0
    assert payload["normal_rsi_signal_rows_written"] == 0
    assert payload["triggered_fade_created"] == 0
    assert "Behavior Freeze Contract" in markdown
    assert "Refactor Success Gates" in markdown


def test_refactor_baseline_json_contains_file_counts_and_inventory():
    from crypto_rsi_scanner import refactor_baseline

    root = REPO_ROOT
    payload = refactor_baseline.build_refactor_baseline(root=root)
    counts = payload["line_counts"]
    umbrella_lines = len((root / "tests" / "test_indicators.py").read_text(encoding="utf-8").splitlines())
    assert counts["crypto_rsi_scanner/scanner.py"] > 4000
    assert counts["tests/test_indicators.py"] == umbrella_lines
    assert counts["tests/test_indicators.py"] < 2000
    assert counts["crypto_rsi_scanner/event_alpha_artifact_doctor.py"] > 1500
    assert payload["top_level_event_module_count"] == len(payload["top_level_event_modules"])
    assert payload["top_level_event_module_count"] > 0
    assert "crypto_rsi_scanner/event_alpha/artifacts/schema_v1.py" in payload["event_alpha_package_files"]
    assert "crypto_rsi_scanner/cli/parser.py" in payload["cli_package_files"]
    assert "tests/test_indicators.py" in payload["tests_package_files"]
    assert "tests/rsi/test_indicators_core.py" in payload["tests_package_files"]
    assert "tests/rsi/test_backtest.py" in payload["tests_package_files"]
    assert "tests/rsi/test_paper_risk.py" in payload["tests_package_files"]
    assert "tests/cli/test_parser.py" in payload["tests_package_files"]
    assert "tests/cli/test_make_targets.py" in payload["tests_package_files"]
    assert ".github/workflows/verify.yml" in payload["github_actions_workflows"]
    assert "event-alpha-integrated-radar-smoke" in payload["makefile_event_targets"]
    assert payload["namespace_inventory"]["base_dir"] == "event_fade_cache"


def test_split_rsi_cli_runner_and_make_targets_are_wired():
    import subprocess
    import sys

    root = REPO_ROOT
    output = subprocess.check_output(
        [sys.executable, str(root / "tests" / "test_indicators.py"), "--list-tests"],
        cwd=root,
        text=True,
    )
    counts = {
        key: int(value)
        for line in output.splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }
    assert counts["standalone_tests"] > 650
    assert counts["event_alpha_tests"] > 500
    assert counts["rsi_tests"] >= 95
    assert counts["cli_tests"] >= 15
    assert counts["umbrella_tests"] < 60

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert "test-rsi:" in makefile
    assert "$(PYTHON) -m pytest tests/rsi" in makefile
    assert "test-cli:" in makefile
    assert "$(PYTHON) -m pytest tests/cli" in makefile


def test_refactor_baseline_make_target_is_static_and_no_live_runtime_path():
    root = REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    module_text = (root / "crypto_rsi_scanner" / "refactor_baseline.py").read_text(encoding="utf-8").casefold()
    assert "refactor-baseline:" in makefile
    assert "$(python) -m crypto_rsi_scanner.refactor_baseline" in makefile.casefold()
    forbidden = (
        "urlopen",
        "requests.",
        "aiohttp",
        "from crypto_rsi_scanner.scanner import",
        "import crypto_rsi_scanner.scanner",
        "main.py --",
        "event_alert_send",
    )
    for item in forbidden:
        assert item not in module_text


def test_export_source_with_artifacts_fallback_and_archive_validation():
    import importlib.util
    import time
    import zipfile
    from datetime import datetime

    root = REPO_ROOT
    spec = importlib.util.spec_from_file_location(
        "export_source_with_artifacts",
        root / "scripts" / "export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    export_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export_module)
    with TemporaryDirectory() as tmp:
        tree = Path(tmp) / "tree"
        tree.mkdir()
        (tree / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
        (tree / "crypto_rsi_scanner").mkdir()
        (tree / "crypto_rsi_scanner" / "unit.py").write_text("VALUE = 1\n", encoding="utf-8")
        (tree / ".env").write_text("SECRET=1\n", encoding="utf-8")
        (tree / "local.db").write_text("db\n", encoding="utf-8")
        out = Path(tmp) / "out.zip"
        assert export_module.main(root=tree, out=out) == 0
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
        assert "Makefile" in names
        assert "crypto_rsi_scanner/unit.py" in names
        assert ".env" not in names
        assert "local.db" not in names

        future_zip = Path(tmp) / "future.zip"
        now_ts = time.time()
        future = datetime.fromtimestamp(now_ts + 86400).timetuple()[:6]
        with zipfile.ZipFile(future_zip, "w") as zf:
            info = zipfile.ZipInfo("Makefile", future)
            zf.writestr(info, "all:\n\t@true\n")
        bad = export_module._validate_archive_entries(future_zip, safe_export_timestamp=now_ts)
        assert any(item.startswith("future_mtime:Makefile") for item in bad)
