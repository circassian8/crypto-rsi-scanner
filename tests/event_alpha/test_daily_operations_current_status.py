"""Closed current-authorization receipt tests for Daily Operations."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from crypto_rsi_scanner.event_alpha.operations import daily_operations_current_status
from crypto_rsi_scanner.event_alpha.operations import daily_operations_cli
from tests.event_alpha.test_daily_operations import _Boundaries


def _readiness(*, authorized: bool = False, status: str = "blocked") -> SimpleNamespace:
    return SimpleNamespace(
        checked_at="2026-07-15T12:00:00+00:00",
        status=status,
        reason=("eligible" if status == "ready" else "provider_authorization_missing"),
        market=SimpleNamespace(
            live_provider_authorized=authorized,
            cadence_status="eligible",
            next_eligible_observation_at="2026-07-15T12:00:00+00:00",
        ),
        dashboard=SimpleNamespace(owned=True),
        scheduler=SimpleNamespace(enabled=False, loaded=False, healthy=True),
    )


def test_current_status_separates_current_authorization_and_call_eligibility() -> None:
    blocked = daily_operations_current_status.current_status_values(_readiness())
    ready = daily_operations_current_status.current_status_values(
        _readiness(authorized=True, status="ready")
    )

    assert blocked["current_authorization_status"] == "not_authorized"
    assert blocked["current_provider_call_eligibility"] == "blocked_authorization"
    assert ready["current_authorization_status"] == "authorized"
    assert ready["current_provider_call_eligibility"] == "eligible"
    assert blocked["implications"] == (
        "current_authorization_is_absent_and_the_provider_boundary_is_closed"
    )
    assert ready["implications"] == (
        "an_explicit_cycle_may_attempt_one_already_authorized_bounded_request"
    )
    assert blocked["provider_call_attempted"] is False
    assert blocked["safe_manual_readiness_command"] == (
        "make radar-daily-ops-readiness PYTHON=.venv/bin/python"
    )
    assert blocked["installation_requires_confirmation"] is True
    assert all(
        blocked[field] == 0
        for field in (
            "telegram_sends",
            "trades_created",
            "paper_trades_created",
            "normal_rsi_signal_rows_written",
            "triggered_fade_created",
        )
    )


def test_current_status_persists_only_closed_credential_free_values(tmp_path) -> None:
    path = daily_operations_current_status.persist_current_status(
        tmp_path,
        _readiness(),
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, sort_keys=True).casefold()
    assert path.name == daily_operations_current_status.CURRENT_STATUS_FILENAME
    assert payload["row_type"] == "decision_radar_daily_operations_current_status"
    assert "token" not in serialized
    assert "authorization_header" not in serialized
    assert "credential" not in serialized


def test_current_status_write_rejects_symlink_leaf(tmp_path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.json"
    outside.write_text("sentinel\n", encoding="utf-8")
    target = tmp_path / daily_operations_current_status.CURRENT_STATUS_FILENAME
    target.symlink_to(outside)

    with pytest.raises(Exception):
        daily_operations_current_status.persist_current_status(
            tmp_path,
            _readiness(),
        )

    assert outside.read_text(encoding="utf-8") == "sentinel\n"


def test_readiness_cli_persists_current_truth_without_provider_call(
    tmp_path,
    capsys,
) -> None:
    boundaries = _Boundaries(authorized=False, readiness_status="blocked")

    result = daily_operations_cli.run_cli(
        [
            "readiness",
            "--artifact-base",
            str(tmp_path),
            "--top-n",
            "30",
        ],
        dependencies=boundaries.dependencies(),
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    receipt = json.loads(
        (tmp_path / daily_operations_current_status.CURRENT_STATUS_FILENAME).read_text(
            encoding="utf-8"
        )
    )

    assert result == 0
    assert output.err == ""
    assert payload["current_authorization_status"] == "not_authorized"
    assert payload["current_provider_call_eligibility"] == "blocked_authorization"
    assert payload["safe_manual_readiness_command"].startswith(
        "make radar-daily-ops-readiness"
    )
    assert receipt["current_authorization_status"] == "not_authorized"
    assert receipt["provider_call_attempted"] is False
    assert "run" not in boundaries.events
