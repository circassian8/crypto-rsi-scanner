from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from crypto_rsi_scanner.event_alpha.operations.market_no_send_calendar import (
    CALENDAR_SNAPSHOT_PATH_ENV,
    load_market_no_send_calendar_snapshot,
)
from crypto_rsi_scanner.event_alpha.operations.official_macro_calendar import (
    OFFICIAL_MACRO_CONTACT_ENV,
    OFFICIAL_MACRO_LATEST_ATTEMPT_FILENAME,
    OFFICIAL_MACRO_LATEST_SUCCESS_FILENAME,
    OFFICIAL_MACRO_LIVE_AUTH_ENV,
    OFFICIAL_MACRO_RECEIPT_FILENAME,
    OFFICIAL_MACRO_SNAPSHOT_FILENAME,
    OFFICIAL_MACRO_STATE_DIRNAME,
    OfficialMacroAcquisitionError,
    OfficialMacroHTTPResponse,
    OfficialMacroSourceSpec,
    acquire_official_macro_calendar,
    import_official_macro_calendar,
    main as official_macro_main,
    official_macro_calendar_readiness,
    format_official_macro_calendar_readiness_summary,
    resolve_latest_official_macro_snapshot,
)


FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "event_alpha"
    / "official_macro_calendar"
)
REPO_ROOT = Path(__file__).resolve().parents[2]
OBSERVED_AT = "2026-07-15T00:00:00Z"
AUTHORIZED_ENV = {
    OFFICIAL_MACRO_LIVE_AUTH_ENV: "1",
    OFFICIAL_MACRO_CONTACT_ENV: "calendar-operator@example.com",
}


def _body_for(source: str) -> bytes:
    return {
        "bls": (FIXTURES / "bls_release_calendar.ics").read_bytes(),
        "federal_reserve": (FIXTURES / "federal_reserve_fomc.html").read_bytes(),
        "bea": (FIXTURES / "bea_release_dates.json").read_bytes(),
    }[source]


def _content_type(source: str) -> str:
    return {
        "bls": "text/calendar",
        "federal_reserve": "text/html; charset=utf-8",
        "bea": "application/json",
    }[source]


def _successful_fetcher(calls: list[tuple[str, str]]):
    def fetch(
        spec: OfficialMacroSourceSpec, user_agent: str
    ) -> OfficialMacroHTTPResponse:
        calls.append((spec.name, user_agent))
        return OfficialMacroHTTPResponse(
            body=_body_for(spec.name),
            status=200,
            content_type=_content_type(spec.name),
            final_url=spec.url,
        )

    return fetch


def _operator_exports(directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "federal_reserve": directory / "federal_reserve_fomc.html",
        "bls": directory / "bls_release_calendar.ics",
        "bea": directory / "bea_release_dates.json",
    }
    for source, fixture_name in (
        ("federal_reserve", "federal_reserve_fomc.html"),
        ("bls", "bls_release_calendar.ics"),
        ("bea", "bea_release_dates.json"),
    ):
        paths[source].write_bytes((FIXTURES / fixture_name).read_bytes() + b"\n")
    return paths


def _import(base: Path):
    sources = _operator_exports(base.parent / "operator_exports")
    return import_official_macro_calendar(
        federal_reserve_html=sources["federal_reserve"],
        bls_ics=sources["bls"],
        bea_json=sources["bea"],
        output_base=base,
        observed_at=OBSERVED_AT,
    )


def test_readiness_is_read_only_and_reports_missing_explicit_authorization(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"

    result = official_macro_calendar_readiness(environ={}, output_base=base)

    assert result.status == "blocked"
    assert result.current_status == "blocked_missing_live_authorization"
    assert result.read_only is True
    assert result.provider_call_count == 0
    assert result.provider_call_attempted is False
    assert result.writes_performed is False
    assert result.latest_attempt_status == "none"
    assert result.latest_success_status == "none"
    assert set(result.reason_codes) == {
        "live_calendar_authorization_missing",
        "bls_contact_missing_or_invalid",
    }
    assert result.next_safe_command == (
        "make radar-calendar-official-readiness PYTHON=python3"
    )
    assert "readiness_never_calls" in result.authorization_boundary
    assert "never_creates_or_mutates_authorization" in result.authorization_boundary
    assert "at_most_one_request_per_configured_source" in (
        result.expected_provider_activity
    )
    assert result.rollback_disable_command == (
        "none_required_program_never_mutates_authorization_or_installs_a_service"
    )
    assert result.implications[0].startswith("readiness_is_read_only")
    source_rows = {row.source: row for row in result.source_readiness}
    assert tuple(source_rows) == ("federal_reserve", "bea", "bls")
    assert source_rows["federal_reserve"].official_endpoint_configured is True
    assert source_rows["federal_reserve"].availability == (
        "configured_waiting_for_live_authorization"
    )
    assert source_rows["bea"].availability == (
        "configured_waiting_for_live_authorization"
    )
    assert source_rows["bls"].availability == (
        "blocked_missing_live_authorization_and_contact"
    )
    assert source_rows["bls"].contact_required is True
    assert source_rows["bls"].contact_configured is False
    assert not any(row.request_eligible for row in source_rows.values())
    assert not any(
        row.provider_calls_during_readiness for row in source_rows.values()
    )
    assert result.live_partial_snapshot_eligible is False
    assert result.local_import_partial_snapshot_supported is True
    assert "local_import_can_publish_partial" in result.partial_snapshot_eligibility
    assert "make radar-calendar-official-import-local" in result.local_import_command
    assert str(base) in result.local_import_command
    assert '"$OFFICIAL_MACRO_OBSERVED_AT"' in result.local_import_command
    assert '"$FED_FOMC_HTML"' in result.local_import_command
    assert '"$BLS_CALENDAR_ICS"' in result.local_import_command
    assert '"$BEA_RELEASE_DATES_JSON"' in result.local_import_command
    assert any(
        "BLS_CALENDAR_ICS_is_optional" in item
        for item in result.local_import_requirements
    )
    assert not base.exists()


def test_readiness_summary_leads_with_exact_operator_actions(tmp_path: Path) -> None:
    result = official_macro_calendar_readiness(
        environ={},
        output_base=tmp_path.resolve() / "calendar",
    )

    rendered = format_official_macro_calendar_readiness_summary(result)

    assert "report=decision_radar_official_macro_calendar_readiness" in rendered
    assert "status=blocked" in rendered
    assert "live_acquisition_authorized=false" in rendered
    assert "bls_contact_configured=false" in rendered
    assert "source[federal_reserve].request_eligible=false" in rendered
    assert "source[bea].request_eligible=false" in rendered
    assert "source[bls].reason=live_authorization_and_bls_contact_missing" in rendered
    assert "next_safe_command=make radar-calendar-official-readiness" in rendered
    assert "local_import_command=" in rendered
    assert "readiness_never_calls" in rendered
    assert "provider_call_attempted=false" in rendered
    assert "provider_call_count=0" in rendered
    assert "writes_performed=false" in rendered
    assert "RADAR_OFFICIAL_MACRO_READINESS_OUTPUT=json" in rendered


def test_readiness_cli_keeps_json_default_and_supports_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = tmp_path.resolve() / "calendar"
    monkeypatch.delenv(OFFICIAL_MACRO_LIVE_AUTH_ENV, raising=False)
    monkeypatch.delenv(OFFICIAL_MACRO_CONTACT_ENV, raising=False)

    assert official_macro_main([
        "readiness",
        "--output-base",
        str(base),
    ]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked"
    assert payload["provider_call_count"] == 0
    assert payload["writes_performed"] is False

    assert official_macro_main([
        "readiness",
        "--output-base",
        str(base),
        "--output",
        "summary",
    ]) == 2
    summary = capsys.readouterr().out
    assert "status=blocked" in summary
    assert "provider_call_count=0" in summary
    assert "writes_performed=false" in summary
    assert not base.exists()


def test_readiness_explains_partial_bls_configuration_without_calling(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"

    result = official_macro_calendar_readiness(
        environ={OFFICIAL_MACRO_LIVE_AUTH_ENV: "1"},
        output_base=base,
    )

    assert result.status == "ready"
    assert result.current_status == "ready_partial_bls_missing_configuration"
    assert result.read_only is True
    assert result.provider_call_count == 0
    assert result.provider_call_attempted is False
    assert result.writes_performed is False
    assert result.next_safe_command == (
        "make radar-calendar-official-acquire PYTHON=python3"
    )
    assert any("must_skip_bls" in item for item in result.implications)
    source_rows = {row.source: row for row in result.source_readiness}
    assert source_rows["federal_reserve"].availability == (
        "available_for_authorized_acquisition"
    )
    assert source_rows["bea"].availability == (
        "available_for_authorized_acquisition"
    )
    assert source_rows["bls"].availability == "missing_configuration"
    assert source_rows["federal_reserve"].request_eligible is True
    assert source_rows["bea"].request_eligible is True
    assert source_rows["bls"].request_eligible is False
    assert source_rows["federal_reserve"].maximum_provider_calls_if_acquire == 1
    assert source_rows["bea"].maximum_provider_calls_if_acquire == 1
    assert source_rows["bls"].maximum_provider_calls_if_acquire == 0
    assert result.live_partial_snapshot_eligible is True
    assert "live_acquisition_can_publish_partial" in (
        result.partial_snapshot_eligibility
    )
    assert not base.exists()


def test_readiness_all_configured_sources_are_individually_visible_without_calling(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"

    result = official_macro_calendar_readiness(
        environ=AUTHORIZED_ENV,
        output_base=base,
    )

    assert result.status == "ready"
    assert result.current_status == "ready_all_official_sources_configured"
    assert result.provider_call_count == 0
    assert result.provider_call_attempted is False
    assert result.writes_performed is False
    assert [row.source for row in result.source_readiness] == [
        "federal_reserve",
        "bea",
        "bls",
    ]
    assert all(row.request_eligible for row in result.source_readiness)
    assert all(
        row.availability == "available_for_authorized_acquisition"
        for row in result.source_readiness
    )
    assert sum(
        row.maximum_provider_calls_if_acquire
        for row in result.source_readiness
    ) == 3
    assert not base.exists()


def test_local_import_requires_explicit_observed_at_before_artifact_writes(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    base = root / "calendar"
    sources = _operator_exports(root / "operator_exports")

    result = import_official_macro_calendar(
        federal_reserve_html=sources["federal_reserve"],
        bls_ics=sources["bls"],
        bea_json=sources["bea"],
        output_base=base,
    )

    assert result.status == "blocked"
    assert result.reason_code == "local_import_observed_at_required"
    assert result.provider_call_count == 0
    assert not base.exists()


def test_local_import_rejects_direct_checked_in_fixture_paths_before_writes(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"

    result = import_official_macro_calendar(
        federal_reserve_html=FIXTURES / "federal_reserve_fomc.html",
        bls_ics=FIXTURES / "bls_release_calendar.ics",
        bea_json=FIXTURES / "bea_release_dates.json",
        output_base=base,
        observed_at=OBSERVED_AT,
    )

    assert result.status == "blocked"
    assert result.reason_code == "local_import_nonlive_path_rejected"
    assert result.failure_source == "federal_reserve"
    assert result.provider_call_count == 0
    assert not base.exists()


def test_local_import_rejects_copied_fixture_bytes_before_writes(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    base = root / "calendar"
    sources = _operator_exports(root / "renamed_operator_downloads")
    shutil.copyfile(
        FIXTURES / "federal_reserve_fomc.html",
        sources["federal_reserve"],
    )

    result = import_official_macro_calendar(
        federal_reserve_html=sources["federal_reserve"],
        bls_ics=sources["bls"],
        bea_json=sources["bea"],
        output_base=base,
        observed_at=OBSERVED_AT,
    )

    assert result.status == "blocked"
    assert result.reason_code == "local_import_nonlive_content_rejected"
    assert result.failure_source == "federal_reserve"
    assert result.provider_call_count == 0
    assert not base.exists()


def test_live_cli_does_not_accept_observed_at_override() -> None:
    with pytest.raises(SystemExit) as raised:
        official_macro_main(
            ["acquire", "--observed-at", "2026-07-15T00:00:00Z"]
        )
    assert raised.value.code == 2


def test_import_cli_requires_observed_at() -> None:
    with pytest.raises(SystemExit) as raised:
        official_macro_main(
            [
                "import-local",
                "--federal-reserve-html",
                "fed.html",
                "--bls-ics",
                "bls.ics",
                "--bea-json",
                "bea.json",
            ]
        )
    assert raised.value.code == 2


def test_live_acquisition_blocks_before_artifacts_or_calls_without_authorization(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"
    calls: list[tuple[str, str]] = []

    result = acquire_official_macro_calendar(
        environ={OFFICIAL_MACRO_CONTACT_ENV: "calendar-operator@example.com"},
        output_base=base,
        observed_at=OBSERVED_AT,
        fetcher=_successful_fetcher(calls),
    )

    assert result.status == "blocked"
    assert result.reason_code == "live_calendar_authorization_missing"
    assert result.provider_call_count == 0
    assert [row["status"] for row in result.source_results] == [
        "missing_configuration",
        "missing_configuration",
        "missing_configuration",
    ]
    assert calls == []
    assert not base.exists()


def test_missing_bls_contact_yields_partial_fed_and_bea_coverage(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"
    calls: list[tuple[str, str]] = []

    result = acquire_official_macro_calendar(
        environ={OFFICIAL_MACRO_LIVE_AUTH_ENV: "1"},
        output_base=base,
        observed_at=OBSERVED_AT,
        fetcher=_successful_fetcher(calls),
    )

    assert result.status == "partial"
    assert result.usable is True
    assert result.provider_call_count == 2
    assert [name for name, _agent in calls] == ["federal_reserve", "bea"]
    by_source = {row["source"]: row for row in result.source_results}
    assert by_source["bls"]["status"] == "missing_configuration"
    assert by_source["bls"]["request_attempted"] is False
    assert by_source["federal_reserve"]["status"] == "observed"
    assert by_source["bea"]["status"] == "observed"
    assert resolve_latest_official_macro_snapshot(base) == result.snapshot_path
    assert result.snapshot_path is not None
    loaded = load_market_no_send_calendar_snapshot(
        environ={CALENDAR_SNAPSHOT_PATH_ENV: str(result.snapshot_path)},
        now=OBSERVED_AT,
        data_mode="live",
        run_mode="operational",
    )
    assert loaded.usable is True
    assert loaded.snapshot_status == "partial"
    assert [row["status"] for row in loaded.source_coverage] == [
        "missing_configuration",
        "observed",
        "observed",
    ]


def test_live_acquisition_calls_each_required_source_once_and_emits_compatible_snapshot(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"
    calls: list[tuple[str, str]] = []

    result = acquire_official_macro_calendar(
        environ=AUTHORIZED_ENV,
        output_base=base,
        observed_at=OBSERVED_AT,
        fetcher=_successful_fetcher(calls),
    )

    assert result.complete
    assert result.provider_call_count == 3
    assert result.provider_request_succeeded_count == 3
    assert [name for name, _ in calls] == ["bls", "federal_reserve", "bea"]
    assert all("calendar-operator@example.com" in agent for _, agent in calls)
    assert result.event_count == 11
    assert result.snapshot_path is not None
    assert result.snapshot_path.name == OFFICIAL_MACRO_SNAPSHOT_FILENAME
    assert result.receipt_path is not None
    loaded = load_market_no_send_calendar_snapshot(
        environ={CALENDAR_SNAPSHOT_PATH_ENV: str(result.snapshot_path)},
        now=OBSERVED_AT,
        data_mode="live",
        run_mode="operational",
    )
    assert loaded.usable
    assert loaded.upstream_source_mode == "live_provider_snapshot"
    assert loaded.upstream_acquisition_mode == "live_provider"
    assert loaded.source_provider == "official_us_macro"
    assert loaded.retained_row_count > 0
    assert all(row.get("research_only") is True for row in loaded.raw_rows)

    receipt_text = result.receipt_path.read_text(encoding="utf-8")
    assert "calendar-operator@example.com" not in receipt_text
    receipt = json.loads(receipt_text)
    assert receipt["all_required_sources_accepted"] is True
    assert receipt["provider_call_count"] == 3
    assert [row["source"] for row in receipt["source_results"]] == [
        "bls",
        "federal_reserve",
        "bea",
    ]
    assert all(len(row["sha256"]) == 64 for row in receipt["source_results"])


def test_rate_limited_source_is_explicit_without_discarding_observed_sources(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def fetch(spec: OfficialMacroSourceSpec, _user_agent: str):
        calls.append(spec.name)
        if spec.name == "bls":
            return OfficialMacroHTTPResponse(
                body=b"rate limited",
                status=429,
                content_type="text/plain",
                final_url=spec.url,
            )
        return OfficialMacroHTTPResponse(
            body=_body_for(spec.name),
            status=200,
            content_type=_content_type(spec.name),
            final_url=spec.url,
        )

    result = acquire_official_macro_calendar(
        environ=AUTHORIZED_ENV,
        output_base=tmp_path.resolve() / "calendar",
        observed_at=OBSERVED_AT,
        fetcher=fetch,
    )

    assert result.status == "partial"
    assert calls == ["bls", "federal_reserve", "bea"]
    by_source = {row["source"]: row for row in result.source_results}
    assert by_source["bls"]["status"] == "rate_limited"
    assert by_source["bls"]["http_status"] == 429
    assert by_source["federal_reserve"]["status"] == "observed"
    assert by_source["bea"]["status"] == "observed"


def test_valid_source_with_no_relevant_rows_is_not_missing_coverage(
    tmp_path: Path,
) -> None:
    def fetch(spec: OfficialMacroSourceSpec, _user_agent: str):
        body = (
            b"BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"
            if spec.name == "bls"
            else _body_for(spec.name)
        )
        return OfficialMacroHTTPResponse(
            body=body,
            status=200,
            content_type=_content_type(spec.name),
            final_url=spec.url,
        )

    result = acquire_official_macro_calendar(
        environ=AUTHORIZED_ENV,
        output_base=tmp_path.resolve() / "calendar",
        observed_at=OBSERVED_AT,
        fetcher=fetch,
    )

    assert result.complete
    assert result.event_count == 7
    assert result.source_results[0]["status"] == "no_results"
    assert result.source_results[0]["sha256"]


def test_complete_all_source_no_results_snapshot_is_a_healthy_empty_observation(
    tmp_path: Path,
) -> None:
    bodies = {
        "bls": b"BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n",
        "federal_reserve": b"<html><h3>2026 FOMC Meetings</h3></html>",
        "bea": json.dumps(
            {
                "Gross Domestic Product": {"release_dates": []},
                "Personal Income and Outlays": {"release_dates": []},
            }
        ).encode("utf-8"),
    }

    def fetch(spec: OfficialMacroSourceSpec, _user_agent: str):
        return OfficialMacroHTTPResponse(
            body=bodies[spec.name],
            status=200,
            content_type=_content_type(spec.name),
            final_url=spec.url,
        )

    result = acquire_official_macro_calendar(
        environ=AUTHORIZED_ENV,
        output_base=tmp_path.resolve() / "calendar",
        observed_at=OBSERVED_AT,
        fetcher=fetch,
    )

    assert result.complete
    assert result.event_count == 0
    assert [row["status"] for row in result.source_results] == [
        "no_results",
        "no_results",
        "no_results",
    ]
    assert result.snapshot_path is not None
    loaded = load_market_no_send_calendar_snapshot(
        environ={CALENDAR_SNAPSHOT_PATH_ENV: str(result.snapshot_path)},
        now=OBSERVED_AT,
        data_mode="live",
        run_mode="operational",
    )
    assert loaded.status == "healthy_empty"
    assert loaded.snapshot_status == "complete"


def test_explicit_local_import_never_calls_a_provider_and_uses_operator_provenance(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"

    first = _import(base)
    second = _import(base)

    assert first.complete and second.complete
    assert first.provider_call_count == second.provider_call_count == 0
    assert first.attempt_id != second.attempt_id
    assert first.attempt_dir != second.attempt_dir
    assert first.snapshot_path is not None
    snapshot = json.loads(first.snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["source_mode"] == "operator_verified_calendar_snapshot"
    assert snapshot["data_acquisition_mode"] == "operator_verified_export"
    assert snapshot["snapshot_observed_at"] == "2026-07-15T00:00:00+00:00"
    assert len(snapshot["events"]) == 11
    assert all("forecast_value" not in row for row in snapshot["events"])
    assert len(list(base.glob("official_macro_*"))) == 2


def test_local_import_can_attest_partial_coverage_without_network(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    sources = _operator_exports(root / "operator_exports")

    result = import_official_macro_calendar(
        federal_reserve_html=sources["federal_reserve"],
        bls_ics=None,
        bea_json=sources["bea"],
        output_base=root / "calendar",
        observed_at=OBSERVED_AT,
    )

    assert result.status == "partial"
    assert result.provider_call_count == 0
    assert result.source_results[0]["status"] == "missing_configuration"
    assert result.snapshot_path is not None
    snapshot = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["snapshot_status"] == "partial"
    assert [row["status"] for row in snapshot["source_coverage"]] == [
        "missing_configuration",
        "observed",
        "observed",
    ]


def test_latest_success_resolver_attests_pointer_receipt_snapshot_and_sources(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"
    result = _import(base)

    assert result.complete
    assert resolve_latest_official_macro_snapshot(base) == result.snapshot_path
    readiness = official_macro_calendar_readiness(environ={}, output_base=base)
    assert readiness.latest_success_status == "complete"

    assert result.snapshot_path is not None
    result.snapshot_path.write_bytes(result.snapshot_path.read_bytes() + b" ")
    with pytest.raises(
        OfficialMacroAcquisitionError,
        match="latest_success_snapshot_digest_mismatch",
    ):
        resolve_latest_official_macro_snapshot(base)
    assert official_macro_calendar_readiness(
        environ={}, output_base=base
    ).latest_success_status == "invalid"


def test_latest_success_resolver_rejects_replaced_source_artifact(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"
    result = _import(base)
    assert result.complete and result.attempt_dir is not None
    raw = result.attempt_dir / "bls_release_calendar.ics"
    raw.write_bytes(raw.read_bytes() + b"\n")

    with pytest.raises(
        OfficialMacroAcquisitionError,
        match="latest_success_source_digest_mismatch",
    ):
        resolve_latest_official_macro_snapshot(base)


def test_local_import_preserves_london_bls_and_bea_timezones_end_to_end(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    base = root / "calendar"
    sources = _operator_exports(root / "operator_exports")
    sources["bls"].write_text(
        "\n".join(
            (
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "X-WR-TIMEZONE:Europe/London",
                "BEGIN:VEVENT",
                "UID:cpi-london@bls.gov",
                "DTSTART;TZID=Europe/London:20260812T083000",
                "SUMMARY:Consumer Price Index",
                "STATUS:CONFIRMED",
                "END:VEVENT",
                "BEGIN:VEVENT",
                "UID:jobs-london@bls.gov",
                "DTSTART;TZID=Europe/London:20260807T083000",
                "SUMMARY:Employment Situation",
                "STATUS:CONFIRMED",
                "END:VEVENT",
                "END:VCALENDAR",
            )
        ),
        encoding="utf-8",
    )
    sources["bea"].write_text(
        json.dumps(
            {
                "Gross Domestic Product": {
                    "release_dates": ["2026-07-30T08:30:00+01:00"]
                },
                "Personal Income and Outlays": {
                    "release_dates": ["2026-07-31T08:30:00+01:00"]
                },
            }
        ),
        encoding="utf-8",
    )

    result = import_official_macro_calendar(
        federal_reserve_html=sources["federal_reserve"],
        bls_ics=sources["bls"],
        bea_json=sources["bea"],
        output_base=base,
        observed_at=OBSERVED_AT,
    )

    assert result.complete
    assert result.snapshot_path is not None
    snapshot = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
    bls_rows = [row for row in snapshot["events"] if row["source"].startswith("US Bureau of Labor")]
    bea_rows = [row for row in snapshot["events"] if row["source"].startswith("US Bureau of Economic")]
    assert {row["timezone"] for row in bls_rows} == {"Europe/London"}
    assert {row["timezone"] for row in bea_rows} == {"UTC+01:00"}
    loaded = load_market_no_send_calendar_snapshot(
        environ={CALENDAR_SNAPSHOT_PATH_ENV: str(result.snapshot_path)},
        now=OBSERVED_AT,
        data_mode="live",
        run_mode="operational",
    )
    assert loaded.usable
    assert {row["timezone"] for row in loaded.raw_rows}.issuperset(
        {"Europe/London", "UTC+01:00"}
    )


def test_failed_live_pack_is_not_retried_and_preserves_last_success_pointer(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"
    successful_calls: list[tuple[str, str]] = []
    success = acquire_official_macro_calendar(
        environ=AUTHORIZED_ENV,
        output_base=base,
        observed_at=OBSERVED_AT,
        fetcher=_successful_fetcher(successful_calls),
    )
    assert success.complete
    state = base / OFFICIAL_MACRO_STATE_DIRNAME
    success_pointer = state / OFFICIAL_MACRO_LATEST_SUCCESS_FILENAME
    preserved = success_pointer.read_bytes()
    failed_calls: list[str] = []

    def forbidden_bls(spec: OfficialMacroSourceSpec, user_agent: str):
        del user_agent
        failed_calls.append(spec.name)
        return OfficialMacroHTTPResponse(
            body=b"forbidden",
            status=403,
            content_type="text/html",
            final_url=spec.url,
        )

    failure = acquire_official_macro_calendar(
        environ=AUTHORIZED_ENV,
        output_base=base,
        observed_at="2026-07-15T01:00:00Z",
        fetcher=forbidden_bls,
    )

    assert failure.status == "unavailable"
    assert failure.failure_source == "bls"
    assert failure.reason_code is None
    assert failure.provider_call_count == 3
    assert failure.provider_request_succeeded_count == 0
    assert failed_calls == ["bls", "federal_reserve", "bea"]
    assert success_pointer.read_bytes() == preserved
    latest_attempt = json.loads(
        (state / OFFICIAL_MACRO_LATEST_ATTEMPT_FILENAME).read_text(encoding="utf-8")
    )
    assert latest_attempt["status"] == "unavailable"
    assert latest_attempt["snapshot_status"] == "unavailable"
    assert latest_attempt["snapshot_path"] is not None
    assert failure.receipt_path is not None
    receipt = json.loads(failure.receipt_path.read_text(encoding="utf-8"))
    assert receipt["failure_source"] == "bls"
    assert receipt["source_results"][0]["http_status"] == 403
    assert failure.snapshot_path is not None
    unavailable = load_market_no_send_calendar_snapshot(
        environ={CALENDAR_SNAPSHOT_PATH_ENV: str(failure.snapshot_path)},
        now="2026-07-15T01:00:00Z",
        data_mode="live",
        run_mode="operational",
    )
    assert unavailable.status == "unavailable"
    assert unavailable.usable is False
    assert unavailable.snapshot_status == "unavailable"
    assert unavailable.raw_rows == ()


def test_partial_snapshot_rejects_source_coverage_digest_drift(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"
    result = acquire_official_macro_calendar(
        environ={OFFICIAL_MACRO_LIVE_AUTH_ENV: "1"},
        output_base=base,
        observed_at=OBSERVED_AT,
        fetcher=_successful_fetcher([]),
    )
    assert result.status == "partial" and result.snapshot_path is not None
    payload = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
    payload["source_coverage"][0]["status"] = "observed"
    result.snapshot_path.write_text(json.dumps(payload), encoding="utf-8")

    rejected = load_market_no_send_calendar_snapshot(
        environ={CALENDAR_SNAPSHOT_PATH_ENV: str(result.snapshot_path)},
        now=OBSERVED_AT,
        data_mode="live",
        run_mode="operational",
    )

    assert rejected.status == "unavailable"
    assert rejected.error_class == "live_snapshot_official_source_coverage_invalid"
    assert rejected.raw_rows == ()


def test_parse_failure_keeps_immutable_digest_and_publishes_only_partial_coverage(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"
    calls: list[str] = []

    def malformed(spec: OfficialMacroSourceSpec, user_agent: str):
        del user_agent
        calls.append(spec.name)
        body = (
            b"BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Consumer Price Index\n"
            b"END:VEVENT\nEND:VCALENDAR\n"
            if spec.name == "bls"
            else _body_for(spec.name)
        )
        return OfficialMacroHTTPResponse(
            body=body,
            status=200,
            content_type=_content_type(spec.name),
            final_url=spec.url,
        )

    result = acquire_official_macro_calendar(
        environ=AUTHORIZED_ENV,
        output_base=base,
        observed_at=OBSERVED_AT,
        fetcher=malformed,
    )

    assert result.status == "partial"
    assert result.failure_source == "bls"
    assert result.reason_code is None
    assert calls == ["bls", "federal_reserve", "bea"]
    assert result.snapshot_path is not None
    assert result.attempt_dir is not None
    raw_path = result.attempt_dir / "bls_release_calendar.ics"
    assert raw_path.is_file()
    assert result.receipt_path is not None
    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    source = receipt["source_results"][0]
    assert source["status"] == "parse_error"
    assert source["raw_filename"] == raw_path.name
    assert source["sha256"]
    assert (base / OFFICIAL_MACRO_STATE_DIRNAME / OFFICIAL_MACRO_LATEST_SUCCESS_FILENAME).exists()


def test_local_import_rejects_symlink_and_oversized_sources_with_failed_receipts(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    sources = _operator_exports(root / "operator_exports")
    symlink = root / "fed-link.html"
    symlink.symlink_to(sources["federal_reserve"])
    symlink_result = import_official_macro_calendar(
        federal_reserve_html=symlink,
        bls_ics=sources["bls"],
        bea_json=sources["bea"],
        output_base=root / "calendar-symlink",
        observed_at=OBSERVED_AT,
    )
    assert symlink_result.status == "partial"
    assert symlink_result.failure_source == "federal_reserve"
    assert symlink_result.reason_code is None
    assert symlink_result.provider_call_count == 0
    assert symlink_result.receipt_path is not None
    assert symlink_result.receipt_path.name == OFFICIAL_MACRO_RECEIPT_FILENAME

    oversized = root / "oversized.ics"
    oversized.write_bytes(b"x" * (512 * 1024 + 1))
    oversized_result = import_official_macro_calendar(
        federal_reserve_html=sources["federal_reserve"],
        bls_ics=oversized,
        bea_json=sources["bea"],
        output_base=root / "calendar-oversized",
        observed_at=OBSERVED_AT,
    )
    assert oversized_result.status == "partial"
    assert oversized_result.failure_source == "bls"
    assert oversized_result.reason_code is None
    assert oversized_result.provider_call_count == 0


def test_live_response_redirect_or_wrong_content_type_fails_closed(
    tmp_path: Path,
) -> None:
    base = tmp_path.resolve() / "calendar"
    calls: list[str] = []

    def redirected(spec: OfficialMacroSourceSpec, user_agent: str):
        del user_agent
        calls.append(spec.name)
        return OfficialMacroHTTPResponse(
            body=_body_for(spec.name),
            status=200,
            content_type=_content_type(spec.name),
            final_url=spec.url + "?redirected=1",
        )

    result = acquire_official_macro_calendar(
        environ=AUTHORIZED_ENV,
        output_base=base,
        observed_at=OBSERVED_AT,
        fetcher=redirected,
    )
    assert result.status == "unavailable"
    assert result.reason_code is None
    assert result.provider_call_count == 3
    assert calls == ["bls", "federal_reserve", "bea"]


def test_operation_results_keep_all_safety_counters_zero(tmp_path: Path) -> None:
    result = _import(tmp_path.resolve() / "calendar")
    payload: dict[str, Any] = result.to_dict()
    assert payload["research_only"] is True
    assert payload["no_send"] is True
    for name in (
        "strict_alerts_created",
        "telegram_sends",
        "trades_created",
        "paper_trades_created",
        "normal_rsi_signal_rows_written",
        "triggered_fade_created",
    ):
        assert payload[name] == 0


def test_official_calendar_make_targets_preserve_explicit_import_contract() -> None:
    def dry_run(target: str, *assignments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["make", "-n", target, "PYTHON=python3", *assignments],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=check,
        )

    readiness = dry_run("radar-calendar-official-readiness").stdout
    acquisition = dry_run("radar-calendar-official-acquire").stdout
    missing_time = subprocess.run(
        [
            "make",
            "radar-calendar-official-import-local",
            "PYTHON=python3",
            "FED_FOMC_HTML=/operator/fed.html",
            "BLS_CALENDAR_ICS=/operator/bls.ics",
            "BEA_RELEASE_DATES_JSON=/operator/bea.json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    imported = dry_run(
        "radar-calendar-official-import-local",
        "FED_FOMC_HTML=/operator/fed.html",
        "BLS_CALENDAR_ICS=/operator/bls.ics",
        "BEA_RELEASE_DATES_JSON=/operator/bea.json",
        f"OFFICIAL_MACRO_OBSERVED_AT={OBSERVED_AT}",
    ).stdout
    partial_import = dry_run(
        "radar-calendar-official-import-local",
        "FED_FOMC_HTML=/operator/fed.html",
        f"OFFICIAL_MACRO_OBSERVED_AT={OBSERVED_AT}",
    ).stdout
    missing_sources = subprocess.run(
        [
            "make",
            "radar-calendar-official-import-local",
            "PYTHON=python3",
            f"OFFICIAL_MACRO_OBSERVED_AT={OBSERVED_AT}",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert "official_macro_calendar readiness" in readiness
    assert "--output summary" in readiness
    assert "official_macro_calendar acquire" in acquisition
    assert "--observed-at" not in acquisition
    assert missing_time.returncode != 0
    assert "OFFICIAL_MACRO_OBSERVED_AT is required" in missing_time.stderr
    assert "official_macro_calendar import-local" in imported
    assert f'--observed-at "{OBSERVED_AT}"' in imported
    assert "--federal-reserve-html \"/operator/fed.html\"" in imported
    assert "--bls-ics \"/operator/bls.ics\"" in imported
    assert "--bea-json \"/operator/bea.json\"" in imported
    assert "--federal-reserve-html \"/operator/fed.html\"" in partial_import
    assert "--bls-ics" not in partial_import
    assert "--bea-json" not in partial_import
    assert missing_sources.returncode != 0
    assert "At least one of FED_FOMC_HTML" in missing_sources.stderr
