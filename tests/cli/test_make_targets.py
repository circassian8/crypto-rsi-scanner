"""Makefile, export, CI, and architecture-baseline static tests."""

from __future__ import annotations

from tests.rsi import _api_helpers as _api

globals().update({name: getattr(_api, name) for name in dir(_api) if not name.startswith("__")})

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---

def test_makefile_has_clean_export_and_bootstrap_targets():
    import importlib.util
    import os
    import subprocess
    import time
    import zipfile
    from datetime import datetime
    from pathlib import Path

    root = REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    requirements = (root / "requirements.in").read_text(encoding="utf-8")
    assert "PYTHON ?= .venv/bin/python" in makefile
    assert "PYTEST_PATHS ?= tests/event_alpha tests/rsi tests/cli tests/test_indicators.py" in makefile
    assert "PYTEST_SAFE_ENV = PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in makefile
    assert "PYTEST_DURATIONS ?= 50" in makefile
    assert "PYTEST_WORKERS ?= auto" in makefile
    assert "test-rsi:" in makefile
    assert "$(PYTEST_SAFE_ENV) $(PYTHON) -m pytest tests/rsi" in makefile
    assert "test-cli:" in makefile
    assert "$(PYTEST_SAFE_ENV) $(PYTHON) -m pytest tests/cli" in makefile
    assert "pytest-xdist is not installed; skipping parallel pytest run." in makefile
    assert "pytest-xdist>=3.6" in requirements
    assert "verify-fast: check-python test-full smoke-alerts backtest-fixture score" in makefile
    assert "test-pytest-durations:" in makefile
    assert "--durations=$(PYTEST_DURATIONS)" in makefile
    assert "-p xdist.plugin" in makefile
    assert "-n $(PYTEST_WORKERS)" in makefile
    assert "--dist=$(PYTEST_XDIST_MODE)" in makefile
    assert "EVENT_FIXTURE_NOW ?= 2026-06-15T16:00:00Z" in makefile
    assert "EVENT_RESEARCH_NOW ?=" in makefile
    assert "EVENT_FIXTURE_NOW_ENV = RSI_EVENT_RESEARCH_NOW=$(EVENT_FIXTURE_NOW)" in makefile
    assert "EVENT_RESEARCH_NOW_ENV = $(if $(strip $(EVENT_RESEARCH_NOW)),RSI_EVENT_RESEARCH_NOW=$(EVENT_RESEARCH_NOW),)" in makefile
    assert "event-incidents-report:" in makefile
    assert "--event-incidents-report" in makefile
    assert "radar-dashboard:" in makefile
    assert "radar-dashboard-smoke:" in makefile
    assert "radar-calendar-preview:" in makefile
    assert "crypto_rsi_scanner.event_alpha.radar.calendar" in makefile
    assert "crypto_rsi_scanner.event_alpha.dashboard" in makefile
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
    assert "export-src-with-artifacts-smoke:" in makefile
    assert "$(PYTHON) scripts/export_source_with_artifacts.py" in makefile
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
        changed = export_module._normalize_input_timestamps([future_file], safe_export_timestamp=now_ts)
        assert changed == 1
        assert future_file.stat().st_mtime <= now_ts + 2
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
        os.environ["SOURCE_DATE_EPOCH"] = str(int(now_ts + 86400))
        try:
            future_epoch_safe_ts = export_module._safe_export_timestamp(now_ts=now_ts)
        finally:
            if original_epoch is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = original_epoch
        assert future_epoch_safe_ts <= now_ts - export_module.DEFAULT_EXPORT_MTIME_SAFETY_MARGIN_SECONDS + 1

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


def test_event_alpha_architecture_docs_capture_v1_guardrails():
    root = REPO_ROOT
    doc_paths = [
        root / "research" / "EVENT_ALPHA_ARCHITECTURE_V1.md",
        root / "research" / "EVENT_ALPHA_ARTIFACT_SCHEMA_V1.md",
        root / "research" / "EVENT_ALPHA_NAMESPACE_LIFECYCLE.md",
        root / "research" / "EVENT_ALPHA_CONSOLIDATION_PLAN.md",
        root / "research" / "EVENT_ALPHA_RUNBOOK.md",
        root / "AGENTS.md",
        root / "DECISIONS.md",
        root / "ROADMAP.md",
        root / "DEVLOG.md",
    ]
    for path in doc_paths:
        assert path.exists(), path
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in doc_paths).casefold()
    normalized = " ".join(corpus.split())
    required = (
        "event_alpha/providers",
        "event_alpha/radar",
        "event_alpha/artifacts",
        "event_alpha/notifications",
        "event_alpha/outcomes",
        "event_alpha/doctor",
        "event_alpha/namespace",
        "cli/",
        "old import",
        "compatibility shims",
        "new code should import",
        "must not recreate",
        "cli/parser.py",
        "cli/dispatch.py",
        "cli/commands_*.py",
        "tests/event_alpha",
        "tests/rsi",
        "tests/cli",
        "tests/test_indicators.py",
        "compatibility umbrella",
        "new artifact field",
        "schema v1",
        "new doctor check",
        "schema dependencies",
        "schema-first",
        "namespace lifecycle",
        "safe_for_send_readiness",
        "retention policy",
        "research-only/no-trading/no-paper/no-send guards",
        "no live trading",
        "no live provider calls",
        "no live telegram sends",
        "triggered_fade",
        "how to add a provider",
        "how to add a radar artifact",
        "how to add a notification lane",
        "how to add an outcome",
    )
    for item in required:
        assert item in normalized, item


def test_architecture_baseline_generation_writes_reports_without_behavior_invocation():
    from crypto_rsi_scanner.project_health import baseline as architecture_baseline

    root = REPO_ROOT
    with TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "research"
        paths = architecture_baseline.write_architecture_baseline(root=root, out_dir=out_dir)
        assert paths["json"].exists()
        assert paths["markdown"].exists()
        payload = json.loads(paths["json"].read_text(encoding="utf-8"))
        markdown = paths["markdown"].read_text(encoding="utf-8")

    assert payload["schema_version"] == "architecture_baseline_v1"
    assert payload["static_inventory_only"] is True
    assert payload["behavior_changing_code_invoked"] is False
    assert payload["live_provider_calls_allowed"] is False
    assert payload["telegram_sends"] == 0
    assert payload["trades_created"] == 0
    assert payload["paper_trades_created"] == 0
    assert payload["normal_rsi_signal_rows_written"] == 0
    assert payload["triggered_fade_created"] == 0
    assert "Behavior Freeze Contract" in markdown
    assert "Architecture Success Gates" in markdown


def test_architecture_baseline_json_contains_file_counts_and_inventory():
    from crypto_rsi_scanner.project_health import baseline as architecture_baseline

    root = REPO_ROOT
    payload = architecture_baseline.build_architecture_baseline(root=root)
    counts = payload["line_counts"]
    umbrella_lines = len((root / "tests" / "test_indicators.py").read_text(encoding="utf-8").splitlines())
    assert counts["crypto_rsi_scanner/scanner.py"] < 2000
    assert counts["tests/test_indicators.py"] == umbrella_lines
    assert counts["tests/test_indicators.py"] < 2000
    assert counts["crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py"] < 300
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


def test_architecture_final_report_generation_writes_size_and_shim_gates():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crypto_rsi_scanner.project_health import architecture_report as architecture_final_report
    from crypto_rsi_scanner.project_health import architecture_contract as architecture_v3_contract

    root = REPO_ROOT
    with TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        paths = architecture_final_report.write_architecture_final_report(
            root=root,
            out_dir=out_dir,
            pytest_runtime_seconds=12.34,
            standalone_runner_runtime_seconds=56.78,
        )
        assert paths["json"].exists()
        assert paths["markdown"].exists()
        assert (out_dir / architecture_v3_contract.CONTRACT_JSON).exists()
        assert (out_dir / architecture_v3_contract.CONTRACT_MD).exists()
        assert (out_dir / architecture_final_report.V3_RELEASE_CANDIDATE_JSON).exists()
        assert (out_dir / architecture_final_report.V4_FINAL_JSON).exists()
        assert (out_dir / architecture_final_report.V4_FINAL_MD).exists()
        payload = json.loads(paths["json"].read_text(encoding="utf-8"))
        contract = json.loads((out_dir / architecture_v3_contract.CONTRACT_JSON).read_text(encoding="utf-8"))
        v4_report = json.loads((out_dir / architecture_final_report.V4_FINAL_JSON).read_text(encoding="utf-8"))
        markdown = paths["markdown"].read_text(encoding="utf-8")

    assert payload["schema_version"] == "architecture_final_report_v1"
    assert payload["research_only"] is True
    assert payload["live_provider_calls_allowed"] is False
    assert payload["telegram_sends"] == 0
    assert payload["trades_created"] == 0
    assert payload["paper_trades_created"] == 0
    assert payload["normal_rsi_signal_rows_written"] == 0
    assert payload["triggered_fade_created"] == 0
    assert payload["old_module_paths_removed"] == payload["deleted_shims"]
    assert payload["deleted_shims"] >= 1
    assert payload["removed_shims_count"] == payload["deleted_shims"]
    assert payload["retained_public_shims_count"] == 0
    assert payload["retained_shims_with_reason"] == []
    assert payload["shim_dependency_include_runtime_artifacts"] is False
    assert payload["shim_dependency_report_cache_status"] in {
        "hit",
        "miss",
        "miss_due_future_mtime",
        "force_rescan",
        "disabled",
    }
    assert payload["shim_dependency_scanned_source_files"] >= 1
    assert payload["shim_dependency_skipped_artifact_files"] >= 0
    assert isinstance(payload["shim_dependency_scan_accounting"], dict)
    assert payload["dead_duplicate_code_removed"] is False
    assert payload["pytest_runtime_seconds"] == 12.34
    assert payload["standalone_runner_runtime_seconds"] == 56.78
    assert payload["line_counts"]["tests/test_indicators.py"] < 2000
    assert payload["line_counts"]["crypto_rsi_scanner/scanner.py"] < 2000
    assert payload["line_counts"]["crypto_rsi_scanner/cli/services/scanner_api.py"] < 3000
    assert "crypto_rsi_scanner/event_alpha_artifact_doctor.py" not in payload["line_counts"]
    assert payload["line_counts"]["crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py"] < 1500
    assert payload["line_counts"]["crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_core.py"] < 3000
    assert payload["api_artifact_doctor_core_lines"] == payload["line_counts"]["crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_core.py"]
    assert payload["line_counts"]["crypto_rsi_scanner/cli/services/event_alpha.py"] < 1500
    assert payload["active_shims"] == 0
    assert payload["partial_shims"] == 0
    assert payload["unmigrated_modules"] >= 1
    assert payload["unmigrated_modules"] <= 15
    assert payload["active_shim_modules_with_implementation_logic"] == 0
    assert payload["cli_event_alpha_service_lines"] == payload["line_counts"]["crypto_rsi_scanner/cli/services/event_alpha.py"]
    assert payload["cli_service_bind_scanner_globals_call_sites"] >= 1
    assert "crypto_rsi_scanner.event_fade" in payload["intentionally_outside_event_alpha_modules"]
    assert contract["schema_version"] == "architecture_contract_v1"
    assert any(
        row["path"] == "crypto_rsi_scanner/event_fade.py"
        for row in contract["intentional_exceptions"]
    )
    assert any(
        row["path"] == "crypto_rsi_scanner/scanner.py"
        for row in contract["public_compatibility_entrypoints"]
    )
    assert payload["v3_contract_path"] == "research/ARCHITECTURE_CONTRACT.md"
    assert payload["v3_gate_status"] == "accepted_with_documented_exceptions"
    assert payload["v3_auto_accept_ready"] is False
    assert payload["v3_blockers"] == []
    assert payload["v3_auto_accept_blockers"] == []
    assert set(payload["v3_accepted_exceptions"]) == {
        "production_files_over_1200_lines",
        "class_exceptions_remaining",
    }
    assert payload["v3_accepted_exceptions"]["production_files_over_1200_lines"]["count"] == payload["accepted_production_files_over_1200_lines"]
    assert payload["v3_accepted_exceptions"]["class_exceptions_remaining"]["count"] == 3
    for gate_name in architecture_v3_contract.V3_GATE_NAMES:
        assert gate_name in payload["v3_gates"]
    assert payload["nonessential_shims_remaining"] == payload["v3_gates"]["nonessential_shims_remaining"]
    assert payload["public_compatibility_shims"] == payload["v3_gates"]["public_compatibility_shims"]
    assert payload["public_compatibility_shims"] == 0
    assert payload["transitional_file_status"] == "OK"
    assert payload["transitional_file_report"]["schema_version"] == "architecture_transitional_file_report_v1"
    assert payload["transitional_file_report"]["transitional_named_files_count"] == 0
    assert payload["transitional_file_report"]["transitional_named_files_remaining"] == 0
    assert payload["transitional_named_files_count"] == 0
    assert payload["transitional_named_files_remaining"] == 0
    assert payload["transitional_named_files_with_implementation"] == 0
    assert payload["transitional_named_dirs_count"] == 0
    assert payload["compatibility_named_files_remaining"] == 0
    assert payload["transitional_top_level_event_modules_count"] == 0
    assert payload["transitional_retained_public_shims_count"] == 0
    assert payload["retained_public_entrypoints"] == 0
    assert payload["event_fade_safety_exception_present"] is True
    assert payload["scanner_entrypoint_exception_present"] is True
    assert payload["public_compatibility_entrypoints_path"] == "research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.json"
    assert v4_report["schema_version"] == "architecture_acceptance_report_v1"
    assert v4_report["architecture_status"] == "accepted"
    assert v4_report["critical_gates"]["transitional_named_files_zero"] == "pass"
    assert v4_report["critical_gates"]["compatibility_named_files_zero"] == "pass"
    assert v4_report["critical_gates"]["retained_public_entrypoints_zero"] == "pass"
    assert v4_report["critical_gates"]["event_fade_safety_exception_present"] == "pass"
    assert v4_report["critical_gates"]["scanner_entrypoint_exception_present"] == "pass"
    assert v4_report["public_compatibility_entrypoints_manifest"] == "research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.json"
    assert payload["nonessential_shims_remaining"] == 0
    assert "nonessential_shims_remaining" not in payload["v3_auto_accept_blockers"]
    assert payload["remaining_implementation_modules_by_package_target"] == {}
    assert payload["remaining_module_classification"]["path"] == "research/REMAINING_EVENT_MODULE_CLASSIFICATION.json"
    assert payload["class_ownership_report"]["path"] == "research/ARCHITECTURE_CLASS_OWNERSHIP_REPORT.json"
    assert not any(row["path"] == "crypto_rsi_scanner/scanner.py" for row in payload["blockers"])
    assert not any(
        row["path"] == "crypto_rsi_scanner/cli/services/event_alpha.py"
        and "bind_scanner_globals" in row["blocker_reason"]
        for row in payload["blockers"]
    )
    assert not any(
        row["path"] == "crypto_rsi_scanner/cli/services/event_alpha.py"
        and "above the requested <1500 split target" in row["blocker_reason"]
        for row in payload["blockers"]
    )
    assert not any(row["path"] == "crypto_rsi_scanner/event_alpha_artifact_doctor.py" for row in payload["blockers"])
    assert not any(row["path"] == "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py" for row in payload["blockers"])
    assert not any(row["path"] == "crypto_rsi_scanner/cli/services/scanner_api.py" for row in payload["blockers"])
    assert not any(
        row["path"] == "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_core.py"
        for row in payload["blockers"]
    )
    assert not any(
        row["path"] == "crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/api.py"
        for row in payload["blockers"]
    )
    phases = {row["phase"]: row["policy"] for row in payload["deprecation_plan"]}
    assert "v3_public_compatibility" in phases and "No flat Event Alpha public compatibility shims remain" in phases["v3_public_compatibility"]
    assert "deleted_import_tombstones" in phases and "allowed to fail" in phases["deleted_import_tombstones"]
    assert "v4_dev_warning" in phases and "warn in development mode only" in phases["v4_dev_warning"]
    assert "v4_removal" in phases and "removed" in phases["v4_removal"]
    assert "Architecture Final Report" in markdown
    assert "Architecture V3 Finalization Gates" in markdown
    assert "Newly Migrated Modules" in markdown
    assert "Blockers" in markdown
    assert "Deprecation Plan" in markdown
    rc_payload = json.loads((REPO_ROOT / "research" / "ARCHITECTURE_RELEASE_REPORT.json").read_text(encoding="utf-8"))
    assert rc_payload["acceptance_status"] == "accepted"
    assert rc_payload["critical_gate_status"] == "pass"
    assert payload["v3_gate_status"] != "pending"


def test_architecture_v3_gate_snapshot_statuses_for_blockers_and_exceptions():
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crypto_rsi_scanner.project_health import architecture_contract as architecture_v3_contract

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = root / "crypto_rsi_scanner"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "stable.py").write_text("\n".join(["VALUE = 1"] * 1301) + "\n", encoding="utf-8")
        accepted = architecture_v3_contract.build_v3_gate_snapshot(
            root=root,
            size_gate_report={
                "production_files_over_1500_lines": 0,
                "production_files_over_1200_lines": 1,
                "accepted_production_files_over_1200_lines": 1,
                "unresolved_production_files_over_1200_lines": 0,
                "accepted_production_files_over_1200_line_rows": [
                    {"path": "crypto_rsi_scanner/stable.py", "line_count": 1301}
                ],
                "accepted_class_exceptions_count": 1,
                "remaining_class_ownership_debt_count": 0,
                "accepted_class_exceptions": [{"class_name": "SignalsMixin", "line_count": 100}],
            },
            class_ownership_report={
                "accepted_class_exceptions_count": 1,
                "remaining_class_ownership_debt_count": 0,
                "accepted_class_exceptions": [{"class_name": "SignalsMixin", "line_count": 100}],
            },
            shim_dependency_report={
                "entries": [],
                "old_path_internal_imports": 0,
                "old_path_test_imports": 0,
                "old_path_docs_references": 0,
                "old_path_import_allowed_exceptions": 0,
                "deleted_shims": 0,
                "removal_candidate_counts": {"keep_public_compatibility": 0},
            },
        )
    assert accepted["status"] == "accepted_with_documented_exceptions"
    assert accepted["v3_blockers"] == []
    assert accepted["v3_auto_accept_ready"] is False

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = root / "crypto_rsi_scanner"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "small.py").write_text("VALUE = 1\n", encoding="utf-8")
        unaccepted_class = architecture_v3_contract.build_v3_gate_snapshot(
            root=root,
            size_gate_report={"production_files_over_1500_lines": 0},
            class_ownership_report={
                "accepted_class_exceptions_count": 1,
                "remaining_class_ownership_debt_count": 1,
                "accepted_class_exceptions": [{"class_name": "Unaccepted", "line_count": 100}],
            },
            shim_dependency_report={
                "entries": [],
                "old_path_internal_imports": 0,
                "old_path_test_imports": 0,
                "old_path_docs_references": 0,
                "old_path_import_allowed_exceptions": 0,
                "deleted_shims": 0,
                "removal_candidate_counts": {"keep_public_compatibility": 0},
            },
        )
    assert unaccepted_class["status"] == "pending"
    assert unaccepted_class["v3_pending_exceptions"] == ["class_exceptions_remaining"]


def test_architecture_v3_contract_generation_lists_final_exceptions():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crypto_rsi_scanner.project_health import architecture_contract as architecture_v3_contract

    with TemporaryDirectory() as tmp:
        json_path, md_path, contract = architecture_v3_contract.write_architecture_v3_contract(out_dir=tmp)
        payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
        markdown = Path(md_path).read_text(encoding="utf-8")

    assert payload == contract
    assert payload["schema_version"] == architecture_v3_contract.CONTRACT_SCHEMA_VERSION
    assert payload["research_only"] is True
    assert payload["no_live_provider_calls"] is True
    assert payload["no_sends_trades_paper_rsi_or_triggered_fade"] is True
    assert set(architecture_v3_contract.V3_GATE_NAMES).issubset(set(payload["v3_gate_names"]))
    assert any(row["path"] == "crypto_rsi_scanner/event_fade.py" for row in payload["intentional_exceptions"])
    assert any(row["path"] == "crypto_rsi_scanner/scanner.py" for row in payload["public_compatibility_entrypoints"])
    assert "old Event Alpha shim paths are temporary" in markdown or "Temporary compatibility paths" in markdown


def test_event_alpha_radar_north_star_generation_writes_contract():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crypto_rsi_scanner.project_health import radar_north_star

    with TemporaryDirectory() as tmp:
        json_path, md_path, payload = radar_north_star.write_north_star(out_dir=tmp)
        disk_payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
        markdown = Path(md_path).read_text(encoding="utf-8")

    assert disk_payload == payload
    assert payload["schema_version"] == radar_north_star.REPORT_SCHEMA_VERSION
    assert set(payload["opportunity_lanes"]) == set(radar_north_star.LANE_NAMES)
    assert payload["burn_in_contract"]["min_live_no_send_cycles"] == 20
    assert payload["burn_in_contract"]["min_real_candidates"] == 300
    assert payload["burn_in_contract"]["min_human_labels"] == 150
    assert payload["burn_in_contract"]["min_labeled_near_misses"] == 50
    assert payload["burn_in_contract"]["min_outcome_rows"] == 100
    assert payload["burn_in_contract"]["auto_apply_thresholds"] is False
    assert payload["burn_in_contract"]["no_auto_threshold_changes"] is True
    assert payload["burn_in_contract"]["mock_fixture_replay_cache_or_preflight_counted"] is False
    assert "decision_radar_live_observation_campaign_v2 rows are excluded" in payload["burn_in_contract"]["candidate_count_authority"]
    market_generation = payload["market_no_send_generation"]
    assert market_generation["provenance_contract"]["schema_version"] == "crypto_radar_market_provenance_v2"
    assert market_generation["provenance_contract"]["contract_version"] == 2
    assert market_generation["provenance_contract"]["mock_or_fixture_decision_campaign_counted"] is False
    assert market_generation["provenance_contract"]["event_alpha_catalyst_burn_in_counted"] is False
    assert "live_provider" in market_generation["provenance_contract"]["data_acquisition_modes"]
    assert "live_no_send" in market_generation["provenance_contract"]["candidate_source_modes"]
    assert market_generation["authorization"]["inferred_from_cache"] is False
    assert "no provider call" in market_generation["authorization"]["absent_behavior"]
    assert market_generation["temporal_baseline"]["baseline_excludes_current_observation"] is True
    assert market_generation["temporal_baseline"]["default_limits"]["min_baseline_observations"] == 8
    assert market_generation["outcome_policy"]["pending_placeholder_per_canonical_decision_candidate"] is True
    assert payload["decision_model_v2"]["market_data_quality_caps"]["proxy_only_can_be_actionable_or_rapid"] is False
    assert payload["decision_model_v2"]["market_data_quality_caps"]["missing_or_stale_spread_urgency_max"] == 55
    assert payload["source_activation_order"] == list(radar_north_star.SOURCE_ACTIVATION_ORDER)
    assert payload["telegram_sends"] == 0
    assert payload["trades_created"] == 0
    assert payload["paper_trades_created"] == 0
    assert payload["normal_rsi_signal_rows_written"] == 0
    assert payload["triggered_fade_created"] == 0
    assert "Event Alpha Radar North Star" in markdown
    assert "30-Day Burn-In Contract" in markdown
    assert "auto_apply_thresholds: `False`" in markdown
    assert "crypto_radar_market_provenance_v2" in markdown
    assert "event_market_history.jsonl" in markdown
    assert "market_data_quality_caps" in markdown


def test_event_alpha_radar_north_star_project_health_status_and_blocker(tmp_path):
    import json

    from crypto_rsi_scanner.project_health import radar_north_star
    from crypto_rsi_scanner.project_health import terminology_check

    status = radar_north_star.north_star_status(root=REPO_ROOT)
    assert status["document_present"] is True
    assert status["burn_in_contract_present"] is True
    assert status["all_lanes_present"] is True
    assert status["auto_apply_thresholds"] is False
    report = terminology_check.build_report(root=REPO_ROOT)
    assert report["north_star_document_present"] is True
    assert report["north_star_burn_in_contract_present"] is True
    assert report["north_star_auto_apply_thresholds"] is False
    assert report["validation_loop_status"]["status"] == "pass"
    assert report["validation_loop_missing_module_count"] == 0
    assert report["validation_loop_missing_make_target_count"] == 0
    assert report["validation_loop_review_dispatch_artifact_only"] is True
    assert not any(row.get("check") == "north_star_document_missing" for row in report["warnings"])

    research = tmp_path / "research"
    research.mkdir()
    payload = radar_north_star.build_north_star()
    payload["burn_in_contract"]["auto_apply_thresholds"] = True
    (research / radar_north_star.REPORT_JSON).write_text(json.dumps(payload), encoding="utf-8")
    (research / radar_north_star.REPORT_MD).write_text("# North Star\n", encoding="utf-8")
    blocked = radar_north_star.north_star_status(root=tmp_path)
    assert blocked["blockers"] == [
        {"check": "auto_apply_thresholds_true", "path": "research/EVENT_ALPHA_RADAR_NORTH_STAR.json"}
    ]


def test_project_health_validation_loop_blocks_missing_modules_and_review_fallthrough(tmp_path):
    from crypto_rsi_scanner.project_health import terminology_check

    (tmp_path / "Makefile").write_text(
        "\n".join(
            [
                "event-alpha-burn-in-scorecard:",
                "\tRSI_EVENT_ALERTS_ENABLED=0 \\",
                "\tpython3 -m crypto_rsi_scanner.event_alpha.operations.scorecard",
            ]
        ),
        encoding="utf-8",
    )
    dispatch = tmp_path / "crypto_rsi_scanner" / "cli" / "event_alpha_command_registry" / "dispatch.py"
    dispatch.parent.mkdir(parents=True)
    dispatch.write_text("def dispatch_event_alpha_command(args):\n    return False\n", encoding="utf-8")

    status = terminology_check._validation_loop_status(tmp_path)
    checks = {row["check"] for row in status["blockers"]}
    assert "validation_loop_make_target_missing_module" in checks
    assert "validation_loop_make_target_missing" in checks
    assert "validation_loop_burn_in_review_can_fall_through_to_scan" in checks
    assert status["review_dispatch_artifact_only"] is False


def test_architecture_final_report_make_target_is_available():
    root = REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    module_text = (root / "crypto_rsi_scanner" / "project_health" / "architecture_report.py").read_text(encoding="utf-8").casefold()

    assert "architecture-final-report:" in makefile
    assert "architecture-transitional-file-check:" in makefile
    assert "architecture-naming-check:" in makefile or "architecture-terminology-check architecture-naming-check:" in makefile
    assert "architecture-class-ownership-report:" in makefile
    assert "event-alpha-radar-north-star:" in makefile
    assert "$(PYTHON) -m crypto_rsi_scanner.project_health.radar_north_star" in makefile
    assert "INCLUDE_HISTORICAL ?= $(INCLUDE_LEGACY)" in makefile
    assert "STRICT_HISTORICAL ?= $(STRICT_LEGACY)" in makefile
    assert "EVENT_ALPHA_INCLUDE_HISTORICAL_ARG" in makefile
    assert "EVENT_ALPHA_INCLUDE_LEGACY_ARG" not in makefile
    assert "EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT_HISTORICAL_ARG" in makefile
    assert "EVENT_ALPHA_ARTIFACT_DOCTOR_STRICT_LEGACY_ARG" not in makefile
    assert "$(python) -m crypto_rsi_scanner.project_health.class_ownership" in makefile.casefold()
    assert "$(python) -m crypto_rsi_scanner.project_health.transitional_file_check" in makefile.casefold()
    assert "$(python) -m crypto_rsi_scanner.project_health.terminology_check" in makefile.casefold()
    assert "$(python) -m crypto_rsi_scanner.project_health.architecture_report" in makefile.casefold()
    assert "PYTEST_RUNTIME_SECONDS" in makefile
    assert "STANDALONE_RUNTIME_SECONDS" in makefile
    assert "event_alpha import shims" in module_text
    assert "subprocess" not in module_text
    assert "urlopen" not in module_text
    assert "requests." not in module_text


def test_event_alpha_shim_dependency_report_make_target_is_available():
    root = REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    policy = root / "research" / "EVENT_ALPHA_SHIM_RETIREMENT_POLICY.md"

    assert "event-alpha-shim-dependency-report:" in makefile
    assert "event-alpha-old-import-check:" in makefile
    assert "--dependency-report --out-dir research" in makefile
    assert "--old-import-check --out-dir research" in makefile
    assert "RSI_EVENT_ALERTS_ENABLED=0" in makefile
    assert policy.exists()
    policy_text = policy.read_text(encoding="utf-8")
    assert "No old top-level Event Alpha public compatibility shims remain" in policy_text
    assert "Deleted old Event Alpha imports are tombstoned" in policy_text
    assert "must not create\n`TRIGGERED_FADE`" in policy_text
    assert "event_fade.py" in policy_text


def test_architecture_transitional_and_terminology_reports_are_static():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crypto_rsi_scanner.project_health import terminology_check as architecture_naming_check
    from crypto_rsi_scanner.project_health import transitional_file_check as architecture_transitional_file_check

    with TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        trans_json, trans_md, trans = architecture_transitional_file_check.write_report(
            root=REPO_ROOT,
            out_dir=out_dir,
        )
        term_json, term_md, term = architecture_naming_check.write_report(
            root=REPO_ROOT,
            out_dir=out_dir,
        )

        assert trans_json.exists()
        assert trans_md.exists()
        assert term_json.exists()
        assert term_md.exists()
        assert json.loads(trans_json.read_text(encoding="utf-8")) == trans
        assert json.loads(term_json.read_text(encoding="utf-8")) == term
        retired_report_prefix = "FINAL_" + "RE" + "FACTOR_"
        assert not any(path.name.startswith(retired_report_prefix) for path in out_dir.iterdir())

    assert trans["schema_version"] == "architecture_transitional_file_report_v1"
    assert trans["status"] == "OK"
    assert trans["transitional_named_files_remaining"] == 0
    assert trans["transitional_named_files_with_implementation"] == 0
    assert term["schema_version"] == "project_health_naming_cleanup_report_v1"
    assert term["status"] == "OK"
    assert term["transitional_named_files_remaining"] == 0
    assert term["classification_counts"]["CLI_backwards_compatibility_alias"] >= 1
    assert term["classification_counts"]["historical_artifact_semantics"] >= 1
    assert term["blockers"] == []


def test_architecture_naming_check_blocks_active_refactor_reports_but_allows_archive():
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crypto_rsi_scanner.project_health import terminology_check as architecture_naming_check

    canonical_reports = (
        "ARCHITECTURE_BASELINE.json",
        "ARCHITECTURE_SIZE_GATES.json",
        "ARCHITECTURE_CLASS_OWNERSHIP_REPORT.json",
        "ARCHITECTURE_FINAL_REPORT.json",
        "ARCHITECTURE_COMPLETION_MAP.json",
        "ARCHITECTURE_CONTRACT.json",
        "ARCHITECTURE_TRANSITIONAL_FILE_REPORT.json",
    )
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        research = root / "research"
        research.mkdir()
        for name in canonical_reports:
            (research / name).write_text("{}\n", encoding="utf-8")
        (research / "REFACTOR_FINAL_REPORT.md").write_text("historical\n", encoding="utf-8")

        active = architecture_naming_check.build_report(root=root)
        assert active["status"] == "BLOCKED"
        assert active["active_refactor_reports_remaining"] == 1
        assert active["blockers"][0]["path"] == "research/REFACTOR_FINAL_REPORT.md"

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        research = root / "research"
        archive = research / "archive" / "refactor_history"
        archive.mkdir(parents=True)
        for name in canonical_reports:
            (research / name).write_text("{}\n", encoding="utf-8")
        (archive / "REFACTOR_FINAL_REPORT.md").write_text("historical refactor report\n", encoding="utf-8")

        archived = architecture_naming_check.build_report(root=root)
        assert archived["status"] == "OK"
        assert archived["active_refactor_reports_remaining"] == 0
        assert archived["blockers"] == []


def test_architecture_completion_map_generation_writes_release_candidate_reports():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crypto_rsi_scanner.project_health import completion_map as architecture_completion_map

    verification = {
        "commands": [
            {
                "command": "python3 tests/test_indicators.py",
                "returncode": 0,
                "status": "pass",
                "elapsed_seconds": 1.0,
            }
        ],
        "total_elapsed_seconds": 1.0,
    }
    with TemporaryDirectory() as tmp:
        paths = architecture_completion_map.write_architecture_completion_map(
            root=REPO_ROOT,
            out_dir=Path(tmp),
            verification_results=verification,
        )
        completion = json.loads(paths["completion_json"].read_text(encoding="utf-8"))
        release = json.loads(paths["release_json"].read_text(encoding="utf-8"))
        markdown = paths["completion_markdown"].read_text(encoding="utf-8")

    assert completion["schema_version"] == "architecture_completion_map_v1"
    assert completion["research_only"] is True
    assert completion["live_provider_calls_allowed"] is False
    assert completion["telegram_sends"] == 0
    assert completion["trades_created"] == 0
    assert completion["paper_trades_created"] == 0
    assert completion["normal_rsi_signal_rows_written"] == 0
    assert completion["triggered_fade_created"] == 0
    assert completion["scanner_facade"]["line_count"] < 2000
    assert completion["cli_architecture"]["scanner_command_body_functions_remaining"] == 0
    assert completion["size_gates"]["gate_status"] == "pass"
    gates = completion["final_architecture_gates"]
    assert gates["transitional_named_files_remaining"] == 0
    assert gates["transitional_named_files_with_implementation"] == 0
    assert gates["compatibility_named_files_remaining"] == 0
    assert gates["old_path_internal_imports"] == 0
    assert gates["old_path_test_imports"] == 0
    assert gates["old_path_docs_references"] == 0
    assert gates["nonessential_shims_remaining"] == 0
    assert gates["retained_public_entrypoints"] == 0
    assert isinstance(gates["deleted_shims_count"], int)
    assert gates["deleted_shims_count"] >= 0
    assert gates["canonical_import_coverage"] == "pass"
    assert gates["event_fade_safety_exception_present"] is True
    assert gates["scanner_entrypoint_exception_present"] is True
    assert completion["verification"]["status"] == "pass"
    assert release["schema_version"] == "architecture_release_candidate_report_v1"
    assert release["status"] in {"accepted", "pending_with_documented_architecture_blockers"}
    assert "Architecture Completion Map" in markdown
    assert "canonical_import_coverage" in markdown


def test_architecture_completion_map_make_target_is_static_and_no_live_runtime_path():
    root = REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    module_text = (root / "crypto_rsi_scanner" / "project_health" / "completion_map.py").read_text(encoding="utf-8").casefold()
    assert "architecture-completion-map:" in makefile
    assert "$(python) -m crypto_rsi_scanner.project_health.completion_map" in makefile.casefold()
    forbidden = (
        "subprocess",
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


def test_architecture_size_gates_static_baseline_and_new_violation_detection():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crypto_rsi_scanner.project_health import size_gates as architecture_size_gates

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = root / "crypto_rsi_scanner"
        tests_dir = root / "tests"
        package.mkdir()
        tests_dir.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "small.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
        (tests_dir / "test_small.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

        baseline_path, baseline = architecture_size_gates.write_baseline(root=root)
        assert baseline_path.name == "ARCHITECTURE_SIZE_BASELINE.json"
        assert baseline["schema_version"] == "architecture_size_baseline_v1"
        assert baseline["violation_ids"] == []

        report_path, markdown_path, report = architecture_size_gates.write_gate_report(root=root)
        assert report_path.name == "ARCHITECTURE_SIZE_GATES.json"
        assert markdown_path.name == "ARCHITECTURE_SIZE_GATES.md"
        assert report["gate_status"] == "pass"
        assert report["new_violation_count"] == 0

        (package / "new_large.py").write_text("\n".join(["VALUE = 1"] * 1502) + "\n", encoding="utf-8")
        blocked = architecture_size_gates.build_gate_report(root=root)
        assert blocked["gate_status"] == "blocked"
        assert any(row["category"] == "file_over_1500_lines" for row in blocked["new_violations"])
        assert blocked["production_size_gate_status"] == "blocked"
        assert blocked["production_files_over_1200_lines"] == 1
        assert blocked["accepted_production_files_over_1200_lines"] == 0
        assert blocked["unresolved_production_files_over_1200_lines"] == 1
        assert blocked["v3_gates"]["production_files_over_1200_lines"] == 1
        assert blocked["v3_gates"]["production_files_over_1500_lines"] == 1
        assert blocked["v3_gate_status"] == "blocked"
        assert "production_files_over_1500_lines" in blocked["v3_blockers"]
        assert blocked["v3_auto_accept_ready"] is False
        assert json.loads(baseline_path.read_text(encoding="utf-8"))["violation_ids"] == []

        (package / "giant_production.py").write_text("\n".join(["VALUE = 1"] * 2002) + "\n", encoding="utf-8")
        production_blocked = architecture_size_gates.build_gate_report(root=root)
        assert production_blocked["production_size_gate_status"] == "blocked"
        assert production_blocked["production_files_over_2000_lines"] == 1
        assert any(row["path"] == "crypto_rsi_scanner/giant_production.py" for row in production_blocked["largest_production_files"])

        (tests_dir / "test_giant.py").write_text("\n".join(["VALUE = 1"] * 2002) + "\n", encoding="utf-8")
        test_tracked = architecture_size_gates.build_gate_report(root=root)
        assert test_tracked["test_size_gate_status"] == "warning"
        assert test_tracked["test_files_over_1500_lines"] == 1
        assert any(row["path"] == "tests/test_giant.py" for row in test_tracked["largest_test_files"])

        (package / "feature_legacy.py").write_text("\n".join(["VALUE = 1"] * 3001) + "\n", encoding="utf-8")
        legacy_blocked = architecture_size_gates.build_gate_report(root=root)
        assert legacy_blocked["api_decomposition_gate_status"] == "blocked"
        assert legacy_blocked["api_files_over_3000_lines"] == 1
        assert legacy_blocked["largest_api_files"][0]["path"] == "crypto_rsi_scanner/feature_legacy.py"


def test_architecture_size_gates_make_target_is_static_and_no_live_runtime_path():
    root = REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    module_text = (root / "crypto_rsi_scanner" / "project_health" / "size_gates.py").read_text(encoding="utf-8").casefold()
    assert "architecture-size-baseline-update:" in makefile
    assert "architecture-size-gates:" in makefile
    assert "$(python) -m crypto_rsi_scanner.project_health.size_gates --update-baseline" in makefile.casefold()
    assert "$(python) -m crypto_rsi_scanner.project_health.size_gates" in makefile.casefold()
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


def test_architecture_reports_list_large_api_implementation_cores():
    from crypto_rsi_scanner.project_health import architecture_report as architecture_final_report
    from crypto_rsi_scanner.project_health import size_gates as architecture_size_gates

    size_report = architecture_size_gates.build_gate_report(root=REPO_ROOT)
    final_report = architecture_final_report.build_architecture_final_report(root=REPO_ROOT)
    assert size_report["api_decomposition_gate_status"] == "pass"
    assert final_report["api_decomposition_gate_status"] == "pass"
    assert size_report["api_files_over_1500_lines"] == 0
    assert final_report["api_files_over_1500_lines"] == 0
    assert size_report["production_size_gate_status"] == "warning"
    assert final_report["production_size_gate_status"] == "warning"
    assert size_report["production_files_over_1200_lines"] == size_report["accepted_production_files_over_1200_lines"]
    assert size_report["unresolved_production_files_over_1200_lines"] == 0
    assert final_report["production_files_over_1200_lines"] == final_report["accepted_production_files_over_1200_lines"]
    assert final_report["unresolved_production_files_over_1200_lines"] == 0
    assert size_report["production_files_over_1500_lines"] == 0
    assert final_report["production_files_over_1500_lines"] == 0
    assert size_report["production_files_over_2000_lines"] == 0
    assert not any(
        blocker["path"] == "crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/api.py"
        for blocker in final_report["blockers"]
    )


def test_shared_architecture_facades_preserve_import_paths():
    from crypto_rsi_scanner.storage import Storage
    from crypto_rsi_scanner.storage_parts.signals import SignalsMixin
    from crypto_rsi_scanner import backtest
    from crypto_rsi_scanner.backtest_parts import data as backtest_data
    from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
    from crypto_rsi_scanner.event_alpha.artifacts.schema import validators

    assert issubclass(Storage, SignalsMixin)
    assert backtest.fixture_symbols is backtest_data.fixture_symbols
    assert backtest._filter_usdt_bases([
        {"baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},
        {"baseAsset": "USDT", "quoteAsset": "USDT", "status": "TRADING"},
    ]) == ["BTC"]
    assert schema_v1.validate_artifact_file is validators.validate_artifact_file
    assert schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION == "event_alpha_schema_v1"


def test_test_runtime_report_writes_json_and_markdown_without_live_side_effects():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from crypto_rsi_scanner import test_runtime_report

    results = (
        test_runtime_report.RuntimeCommandResult(
            name="standalone_runner",
            command=("python3", "tests/test_indicators.py"),
            returncode=0,
            runtime_seconds=1.25,
        ),
        test_runtime_report.RuntimeCommandResult(
            name="pytest_safe",
            command=("python3", "-m", "pytest"),
            returncode=0,
            runtime_seconds=2.5,
        ),
    )
    with TemporaryDirectory() as tmp:
        paths = test_runtime_report.write_runtime_report(
            root=REPO_ROOT,
            out_dir=Path(tmp),
            results=results,
        )
        payload = json.loads(paths["json"].read_text(encoding="utf-8"))
        markdown = paths["markdown"].read_text(encoding="utf-8")

    assert payload["schema_version"] == "test_runtime_report_v1"
    assert payload["research_only"] is True
    assert payload["live_provider_calls_allowed"] is False
    assert payload["telegram_sends"] == 0
    assert payload["trades_created"] == 0
    assert payload["paper_trades_created"] == 0
    assert payload["normal_rsi_signal_rows_written"] == 0
    assert payload["triggered_fade_created"] == 0
    assert payload["standalone_runner_runtime_seconds"] == 1.25
    assert payload["pytest_runtime_seconds"] == 2.5
    assert "Test Runtime Report" in markdown


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


def test_architecture_baseline_make_target_is_static_and_no_live_runtime_path():
    root = REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    module_text = (root / "crypto_rsi_scanner" / "project_health" / "baseline.py").read_text(encoding="utf-8").casefold()
    assert "architecture-baseline:" in makefile
    assert "$(python) -m crypto_rsi_scanner.project_health.baseline" in makefile.casefold()
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
    import subprocess
    import time
    import zipfile
    from datetime import datetime, timedelta, timezone

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
        makefile = tree / "Makefile"
        makefile.write_text("verify:\n\t@true\n", encoding="utf-8")
        (tree / "crypto_rsi_scanner").mkdir()
        (tree / "crypto_rsi_scanner" / "unit.py").write_text("VALUE = 1\n", encoding="utf-8")
        (tree / ".env").write_text("SECRET=1\n", encoding="utf-8")
        (tree / "local.db").write_text("db\n", encoding="utf-8")
        (tree / "backtest_cache").mkdir()
        (tree / "backtest_cache" / "cached.json").write_text("{}\n", encoding="utf-8")
        outside = Path(tmp) / "outside-private-material.txt"
        outside.write_text("unconfigured private material\n", encoding="utf-8")
        outside_future_ts = time.time() + 172800
        os.utime(outside, (outside_future_ts, outside_future_ts))
        outside_mtime_ns = outside.stat().st_mtime_ns
        artifact_dir = tree / "event_fade_cache" / "unit"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "linked-evidence.txt").symlink_to(outside)
        future_ts = time.time() + 86400
        os.utime(makefile, (future_ts, future_ts))
        out = Path(tmp) / "out.zip"
        assert export_module.main(root=tree, out=out) == 0
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
            makefile_ts = datetime(*zf.getinfo("Makefile").date_time).timestamp()
        assert "Makefile" in names
        assert "crypto_rsi_scanner/unit.py" in names
        assert ".env" not in names
        assert "local.db" not in names
        assert "backtest_cache/cached.json" not in names
        assert "event_fade_cache/unit/linked-evidence.txt" not in names
        assert outside.stat().st_mtime_ns == outside_mtime_ns
        assert outside.read_text(encoding="utf-8") == "unconfigured private material\n"
        assert makefile_ts <= time.time()
        safe_archive = out.read_bytes()

        configured_secret = "123456789:configured-secret"
        (tree / ".env").write_text(
            f"TELEGRAM_BOT_TOKEN={configured_secret}\n",
            encoding="utf-8",
        )
        (tree / "crypto_rsi_scanner" / "unit.py").write_text(
            f"VALUE = {configured_secret!r}\n",
            encoding="utf-8",
        )
        assert export_module.main(root=tree, out=out) == 1
        assert out.read_bytes() == safe_archive
        assert not out.with_name(f"{out.name}.tmp").exists()

        extract_dir = Path(tmp) / "extract"
        with zipfile.ZipFile(out) as zf:
            zf.extractall(extract_dir)
        make_dry = subprocess.run(
            ["make", "-n", "verify"],
            cwd=extract_dir,
            text=True,
            capture_output=True,
            check=True,
        )
        make_output = make_dry.stdout + make_dry.stderr
        assert "Clock skew detected" not in make_output
        assert "modification time" not in make_output

        future_zip = Path(tmp) / "future.zip"
        now_ts = time.time()
        future = datetime.fromtimestamp(now_ts + 86400).timetuple()[:6]
        with zipfile.ZipFile(future_zip, "w") as zf:
            info = zipfile.ZipInfo("Makefile", future)
            zf.writestr(info, "all:\n\t@true\n")
        bad = export_module._validate_archive_entries(future_zip, safe_export_timestamp=now_ts)
        assert any(item.startswith("future_mtime:Makefile") for item in bad)


def test_export_source_with_artifacts_parent_symlink_swap_fails_closed():
    import importlib.util
    import os
    import zipfile
    root = REPO_ROOT
    spec = importlib.util.spec_from_file_location(
        "export_source_with_artifacts_race",
        root / "scripts" / "export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    export_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export_module)
    with TemporaryDirectory() as tmp:
        trusted_root = Path(tmp) / "trusted"
        artifact_root = trusted_root / "event_fade_cache"
        safe_file = artifact_root / "unit" / "evidence.txt"
        safe_file.parent.mkdir(parents=True)
        safe_file.write_text("safe evidence\n", encoding="utf-8")
        outside_root = Path(tmp) / "outside"
        outside_file = outside_root / "unit" / "evidence.txt"
        outside_file.parent.mkdir(parents=True)
        outside_file.write_text("outside private material\n", encoding="utf-8")
        displaced = trusted_root / "event_fade_cache.checked"
        archive = Path(tmp) / "race.zip"
        original_open = export_module.os.open
        swapped = False
        def racing_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if path == "event_fade_cache" and dir_fd is not None and not swapped:
                artifact_root.rename(displaced)
                artifact_root.symlink_to(outside_root, target_is_directory=True)
                swapped = True
            return original_open(path, flags, mode, dir_fd=dir_fd)

        export_module.os.open = racing_open
        try:
            try:
                with zipfile.ZipFile(archive, "w") as zf:
                    export_module._write_file_to_zip(
                        zf,
                        safe_file,
                        "event_fade_cache/unit/evidence.txt",
                        now_ts=__import__("time").time(),
                        root=trusted_root,
                    )
            except OSError:
                pass
            else:
                raise AssertionError("parent symlink swap must fail closed")
        finally:
            export_module.os.open = original_open

        assert swapped is True
        assert outside_file.read_text(encoding="utf-8") == "outside private material\n"
        with zipfile.ZipFile(archive) as zf:
            assert "event_fade_cache/unit/evidence.txt" not in zf.namelist()
