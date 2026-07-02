"""Focused pytest checks for extracted CLI dispatch routing."""

from __future__ import annotations

import importlib

import pytest

from crypto_rsi_scanner import scanner
from crypto_rsi_scanner.cli.dispatch import dispatch_args
from crypto_rsi_scanner.cli.parser import build_parser
from crypto_rsi_scanner.cli.services import (
    event_alpha_integrated,
    event_alpha_notifications,
    event_alpha_provider_preflights,
    event_alpha_reports,
)


def _args(argv: list[str]):
    return build_parser().parse_args(argv)


def test_dispatch_integrated_radar_fixture_cycle(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_integrated(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(event_alpha_integrated, "event_alpha_integrated_radar_cycle_report", fake_integrated)
    monkeypatch.setattr(
        scanner,
        "event_alpha_integrated_radar_cycle_report",
        lambda **kwargs: pytest.fail("dispatch should call event_alpha_integrated service directly"),
    )
    dispatch_args(_args([
        "--event-alpha-integrated-radar-cycle",
        "--event-alpha-integrated-radar-fixture",
        "--event-alpha-profile",
        "fixture",
        "--event-alpha-artifact-namespace",
        "integrated_radar_smoke",
    ]))
    assert calls == [{
        "verbose": False,
        "profile_name": "fixture",
        "artifact_namespace": "integrated_radar_smoke",
        "fixture": True,
        "input_mode": scanner.event_integrated_radar.INPUT_MODE_AUTO,
        "coinalyze_namespace": None,
    }]


def test_dispatch_artifact_doctor(monkeypatch):
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(event_alpha_reports, "event_alpha_artifact_doctor_report", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(
        scanner,
        "event_alpha_artifact_doctor_report",
        lambda **kwargs: pytest.fail("dispatch should call event_alpha_reports service directly"),
    )
    dispatch_args(_args([
        "--event-alpha-artifact-doctor",
        "--event-alpha-artifact-doctor-strict",
        "--event-alpha-profile",
        "notify_llm_deep",
        "--event-alpha-artifact-namespace",
        "notify_llm_deep_cryptopanic_rehearsal",
    ]))
    assert calls[0]["profile_name"] == "notify_llm_deep"
    assert calls[0]["artifact_namespace"] == "notify_llm_deep_cryptopanic_rehearsal"
    assert calls[0]["strict"] is True
    assert calls[0]["include_test_artifacts"] is False


def test_dispatch_coinalyze_preflight(monkeypatch):
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        event_alpha_provider_preflights,
        "event_alpha_coinalyze_preflight_report",
        lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(
        scanner,
        "event_alpha_coinalyze_preflight_report",
        lambda **kwargs: pytest.fail("dispatch should call event_alpha_provider_preflights service directly"),
    )
    dispatch_args(_args(["--event-alpha-coinalyze-preflight", "--event-alpha-profile", "fixture"]))
    assert calls == [{
        "verbose": False,
        "profile_name": "fixture",
        "artifact_namespace": None,
        "smoke_mode": False,
        "allow_live_preflight": False,
    }]


def test_dispatch_notify_preview(monkeypatch):
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(event_alpha_notifications, "event_alpha_notify_preview", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(
        scanner,
        "event_alpha_notify_preview",
        lambda **kwargs: pytest.fail("dispatch should call event_alpha_notifications service directly"),
    )
    dispatch_args(_args(["--event-alpha-notify-preview", "--event-alpha-profile", "notify_no_key"]))
    assert calls == [{"verbose": False, "profile_name": "notify_no_key"}]


def test_dispatch_normal_rsi_dry_run(monkeypatch):
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(scanner, "run", lambda **kwargs: calls.append(kwargs))
    dispatch_args(_args(["--dry-run", "--top-n", "5", "--verbose"]))
    assert calls == [{"top_n": 5, "dry_run": True, "verbose": True}]


def test_dispatch_export_source_with_artifacts(monkeypatch):
    export_module = importlib.import_module("scripts.export_source_with_artifacts")
    calls: list[str] = []

    def fake_export_main():
        calls.append("export")
        return 0

    monkeypatch.setattr(export_module, "main", fake_export_main)
    with pytest.raises(SystemExit) as exc:
        dispatch_args(_args(["--export-src-with-artifacts"]))
    assert exc.value.code == 0
    assert calls == ["export"]
