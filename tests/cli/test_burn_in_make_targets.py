"""Event Alpha burn-in Make target static tests."""

from __future__ import annotations

import subprocess

from tests.rsi import _api_helpers as _api

globals().update({name: getattr(_api, name) for name in dir(_api) if not name.startswith("__")})


def test_event_alpha_burn_in_operating_targets_are_no_send_and_artifact_only():
    root = REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    for target in (
        "event-alpha-burn-in-contract",
        "event-alpha-daily-live-no-send-burn-in",
        "event-alpha-daily-live-no-send-burn-in-plan",
        "event-alpha-daily-live-no-send-burn-in-smoke",
        "event-alpha-daily-review-inbox",
        "event-alpha-feedback-progress",
        "event-alpha-burn-in-weekly-measurement",
        "event-alpha-source-yield-report",
        "conviction-priors-shadow-report",
        "paper-risk-research",
        "event-alpha-archive-burn-in-evidence",
        "event-feedback-source-noise",
        "event-feedback-needs-confirmation",
        "event-feedback-promising-source-type",
    ):
        assert f"{target}:" in makefile
    daily_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-daily-live-no-send-burn-in", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "RSI_EVENT_ALERTS_ENABLED=0" in daily_dry
    assert "operations.daily_burn_in" in daily_dry
    assert "event-alpha-telegram-send-one-cycle" not in daily_dry
    assert "RSI_EVENT_ALERTS_ENABLED=1" not in daily_dry
    plan_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-daily-live-no-send-burn-in-plan", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "operations.daily_burn_in" in plan_dry
    assert "--dry-run-plan" in plan_dry
    assert "RSI_EVENT_ALERTS_ENABLED=1" not in plan_dry
    smoke_dry = subprocess.check_output(
        ["make", "-n", "event-alpha-daily-live-no-send-burn-in-smoke", "PYTHON=python3"],
        cwd=root,
        text=True,
    )
    assert "operations.daily_burn_in" in smoke_dry
    assert "--smoke" in smoke_dry
    assert "RSI_EVENT_ALERTS_ENABLED=1" not in smoke_dry
    progress_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-feedback-progress",
            "PROFILE=notify_llm_deep",
            "ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "operations.feedback_progress" in progress_dry
    assert "--artifact-namespace notify_llm_deep_cryptopanic_rehearsal" in progress_dry
    scorecard_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-burn-in-scorecard",
            "INCLUDE_NOTIFICATION_REHEARSALS=1",
            "INCLUDE_NO_KEY_NAMESPACES=1",
            "INCLUDE_PROVIDER_REHEARSALS=1",
            "INCLUDE_FIXTURE_NAMESPACES=1",
            "INCLUDE_STALE_NAMESPACES=1",
            "COUNT_EXPLICIT_NAMESPACE_FOR_BURN_IN=1",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "--include-notification-rehearsals" in scorecard_dry
    assert "--include-no-key-namespaces" in scorecard_dry
    assert "--include-provider-rehearsals" in scorecard_dry
    assert "--include-fixture-namespaces" in scorecard_dry
    assert "--include-stale-namespaces" in scorecard_dry
    assert "--count-explicit-namespace-for-burn-in" in scorecard_dry
    explicit_scorecard_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-alpha-burn-in-scorecard",
            "PROFILE=notify_llm_deep",
            "ARTIFACT_NAMESPACE=notify_llm_deep_cryptopanic_rehearsal",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "--profile notify_llm_deep" in explicit_scorecard_dry
    assert "--artifact-namespace notify_llm_deep_cryptopanic_rehearsal" in explicit_scorecard_dry
    source_noise_dry = subprocess.check_output(
        [
            "make",
            "-n",
            "event-feedback-source-noise",
            "PROFILE=notify_llm_deep",
            "FEEDBACK_TARGET=ea:test",
            "PYTHON=python3",
        ],
        cwd=root,
        text=True,
    )
    assert "--event-feedback-source-noise" in source_noise_dry
    assert "--event-alpha-profile notify_llm_deep" in source_noise_dry
