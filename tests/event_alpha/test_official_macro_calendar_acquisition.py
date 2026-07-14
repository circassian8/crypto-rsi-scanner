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
    assert result.provider_call_attempted is False
    assert result.latest_attempt_status == "none"
    assert result.latest_success_status == "none"
    assert set(result.reason_codes) == {
        "live_calendar_authorization_missing",
        "bls_contact_missing_or_invalid",
    }
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


@pytest.mark.parametrize(
    "environ,reason",
    (
        ({OFFICIAL_MACRO_CONTACT_ENV: "calendar-operator@example.com"}, "live_calendar_authorization_missing"),
        ({OFFICIAL_MACRO_LIVE_AUTH_ENV: "1"}, "bls_contact_missing_or_invalid"),
    ),
)
def test_live_acquisition_blocks_before_artifacts_or_calls_without_full_gate(
    tmp_path: Path, environ: dict[str, str], reason: str
) -> None:
    base = tmp_path.resolve() / "calendar"
    calls: list[tuple[str, str]] = []

    result = acquire_official_macro_calendar(
        environ=environ,
        output_base=base,
        observed_at=OBSERVED_AT,
        fetcher=_successful_fetcher(calls),
    )

    assert result.status == "blocked"
    assert result.reason_code == reason
    assert result.provider_call_count == 0
    assert calls == []
    assert not base.exists()


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

    assert failure.status == "failed"
    assert failure.failure_source == "bls"
    assert failure.reason_code == "source_http_status"
    assert failure.provider_call_count == 1
    assert failure.provider_request_succeeded_count == 0
    assert failed_calls == ["bls"]
    assert success_pointer.read_bytes() == preserved
    latest_attempt = json.loads(
        (state / OFFICIAL_MACRO_LATEST_ATTEMPT_FILENAME).read_text(encoding="utf-8")
    )
    assert latest_attempt["status"] == "failed"
    assert latest_attempt["snapshot_path"] is None
    assert failure.receipt_path is not None
    receipt = json.loads(failure.receipt_path.read_text(encoding="utf-8"))
    assert receipt["failure_source"] == "bls"
    assert receipt["source_results"][0]["http_status"] == 403


def test_parse_failure_keeps_immutable_source_digest_and_does_not_publish(
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

    assert result.status == "failed"
    assert result.failure_source == "bls"
    assert result.reason_code is not None and result.reason_code.startswith("parse_")
    assert calls == ["bls"]
    assert result.snapshot_path is None
    assert result.attempt_dir is not None
    raw_path = result.attempt_dir / "bls_release_calendar.ics"
    assert raw_path.is_file()
    assert result.receipt_path is not None
    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    source = receipt["source_results"][0]
    assert source["status"] == "failed"
    assert source["raw_filename"] == raw_path.name
    assert source["sha256"]
    assert not (base / OFFICIAL_MACRO_STATE_DIRNAME / OFFICIAL_MACRO_LATEST_SUCCESS_FILENAME).exists()


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
    assert symlink_result.status == "failed"
    assert symlink_result.failure_source == "federal_reserve"
    assert symlink_result.reason_code == "local_source_unavailable"
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
    assert oversized_result.status == "failed"
    assert oversized_result.failure_source == "bls"
    assert oversized_result.reason_code == "source_body_size_invalid"
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
    assert result.status == "failed"
    assert result.reason_code == "source_redirect_rejected"
    assert result.provider_call_count == 1
    assert calls == ["bls"]


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

    assert "official_macro_calendar readiness" in readiness
    assert "official_macro_calendar acquire" in acquisition
    assert "--observed-at" not in acquisition
    assert missing_time.returncode != 0
    assert "OFFICIAL_MACRO_OBSERVED_AT is required" in missing_time.stderr
    assert "official_macro_calendar import-local" in imported
    assert f'--observed-at "{OBSERVED_AT}"' in imported
    assert "--federal-reserve-html \"/operator/fed.html\"" in imported
    assert "--bls-ics \"/operator/bls.ics\"" in imported
    assert "--bea-json \"/operator/bea.json\"" in imported
