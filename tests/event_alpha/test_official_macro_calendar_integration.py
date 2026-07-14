"""Official macro producer to authoritative dashboard composition proof."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from crypto_rsi_scanner.event_alpha.dashboard.calendar_page import (
    render_calendar_page,
)
from crypto_rsi_scanner.event_alpha.dashboard.loader import load_dashboard_snapshot
from crypto_rsi_scanner.event_alpha.operations import market_no_send
from crypto_rsi_scanner.event_alpha.operations import market_no_send_calendar
from crypto_rsi_scanner.event_alpha.operations import (
    market_no_send_calendar_publication,
)
from crypto_rsi_scanner.event_alpha.operations.official_macro_calendar import (
    OFFICIAL_MACRO_CONTACT_ENV,
    OFFICIAL_MACRO_LIVE_AUTH_ENV,
    OfficialMacroHTTPResponse,
    OfficialMacroSourceSpec,
    acquire_official_macro_calendar,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "fixtures" / "event_alpha" / "official_macro_calendar"


def _official_response(spec: OfficialMacroSourceSpec) -> OfficialMacroHTTPResponse:
    filename, content_type = {
        "bls": ("bls_release_calendar.ics", "text/calendar"),
        "federal_reserve": ("federal_reserve_fomc.html", "text/html; charset=utf-8"),
        "bea": ("bea_release_dates.json", "application/json"),
    }[spec.name]
    return OfficialMacroHTTPResponse(
        body=(_FIXTURES / filename).read_bytes(),
        status=200,
        content_type=content_type,
        final_url=spec.url,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_official_macro_pack_reaches_fingerprinted_live_generation_and_dashboard(
    tmp_path: Path,
    monkeypatch,
) -> None:
    observed = datetime.now(timezone.utc).replace(microsecond=0)
    calendar_calls: list[str] = []

    def calendar_fetcher(
        spec: OfficialMacroSourceSpec,
        _user_agent: str,
    ) -> OfficialMacroHTTPResponse:
        calendar_calls.append(spec.name)
        return _official_response(spec)

    pack = acquire_official_macro_calendar(
        environ={
            OFFICIAL_MACRO_LIVE_AUTH_ENV: "1",
            OFFICIAL_MACRO_CONTACT_ENV: "calendar-operator@example.com",
        },
        output_base=tmp_path / "official_macro_acquisition",
        observed_at=observed,
        fetcher=calendar_fetcher,
    )
    assert pack.complete is True
    assert pack.snapshot_path is not None
    assert calendar_calls == ["bls", "federal_reserve", "bea"]

    artifact_base = tmp_path / "radar_artifacts"
    artifact_base.mkdir()
    monkeypatch.setenv(market_no_send.LIVE_AUTH_ENV, "1")
    monkeypatch.setattr(market_no_send.config, "FIXTURE_DIR", None)
    monkeypatch.setattr(
        market_no_send.config,
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        artifact_base,
    )
    market_calls = 0

    def market_provider(_limit: int):
        nonlocal market_calls
        market_calls += 1
        return market_no_send._smoke_rows()

    monkeypatch.setattr(
        market_no_send,
        "_fetch_live_coingecko_rows",
        market_provider,
    )
    namespace = "official_macro_live_composition"
    result = market_no_send.run_market_no_send_generation(
        artifact_base_dir=artifact_base,
        artifact_namespace=namespace,
        top_n=5,
        observed_at=observed,
        environ={
            market_no_send.LIVE_AUTH_ENV: "1",
            market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV: str(
                pack.snapshot_path
            ),
        },
        fixture_dir=None,
    )

    assert result.complete is True
    assert result.candidate_source_mode == "live_no_send"
    assert result.decision_radar_campaign_counted is True
    assert market_calls == 1
    namespace_dir = artifact_base / namespace
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    metadata = manifest["calendar_snapshot"]
    assert metadata["status"] == "healthy_nonempty"
    assert metadata["source_provider"] == "official_us_macro"
    assert metadata["upstream_source_mode"] == "live_provider_snapshot"
    assert metadata["upstream_acquisition_mode"] == "live_provider"
    assert metadata["retained_row_count"] > 0
    assert metadata["unified_calendar_artifact_row_count"] == metadata[
        "retained_row_count"
    ]

    source_copy = namespace_dir / metadata["copy_artifact"]
    scheduled = namespace_dir / metadata["scheduled_catalyst_artifact"]
    unified = namespace_dir / metadata["unified_calendar_artifact"]
    assert metadata["copy_artifact_sha256"] == _sha256(source_copy)
    assert metadata["scheduled_catalyst_artifact_sha256"] == _sha256(scheduled)
    assert metadata["unified_calendar_artifact_sha256"] == _sha256(unified)
    candidates = tuple(
        json.loads(line)
        for line in (namespace_dir / "event_integrated_radar_candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )
    assert candidates
    assert all(row.get("symbol") != "UNKNOWN" for row in candidates)
    assert all(row.get("market_provenance") for row in candidates)
    market_no_send_calendar_publication.validate_optional_calendar_snapshot(
        manifest,
        namespace_dir=namespace_dir,
        run_id=result.run_id,
        safety_counters=market_no_send._SAFETY_COUNTERS,
    )

    operator_state = json.loads(
        (namespace_dir / "event_alpha_operator_state.json").read_text(
            encoding="utf-8"
        )
    )
    for artifact_name in ("market_no_send_calendar_source", "unified_calendar"):
        artifact = operator_state["artifacts"][artifact_name]
        assert artifact["status"] == "current"
        assert artifact["sha256"]

    doctor_env = os.environ.copy()
    doctor_env.update(
        {
            "RSI_EVENT_ALERTS_ENABLED": "0",
            "RSI_EVENT_ALPHA_TARGETED_MARKET_REFRESH_ENABLED": "0",
            "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR": str(artifact_base),
            "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE": namespace,
            "RSI_EVENT_ALPHA_RUN_MODE": "operational",
            "RSI_EVENT_RESEARCH_NOW": result.observed_at,
        }
    )
    doctor = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "main.py"),
            "--event-alpha-artifact-doctor",
            "--event-alpha-profile",
            "no_key_live",
            "--event-alpha-artifact-namespace",
            namespace,
            "--event-alpha-artifact-doctor-strict",
        ],
        cwd=namespace_dir,
        env=doctor_env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr

    checked_at = datetime.now(timezone.utc)
    published = market_no_send.publish_market_no_send_generation(
        artifact_base,
        namespace,
        now=checked_at,
    )
    loaded = load_dashboard_snapshot(artifact_base, namespace, now=checked_at)
    assert published.snapshot.generation_authoritative is True
    assert loaded.generation_authoritative is True
    assert len(loaded.current_calendar_events) == metadata["retained_row_count"]
    assert "Federal Open Market Committee" in render_calendar_page(loaded, {})
    result_values = result.to_dict()
    assert result_values["telegram_sends"] == 0
    assert result_values["trades_created"] == 0
    assert result_values["paper_trades_created"] == 0
    assert result_values["normal_rsi_signal_rows_written"] == 0
    assert result_values["triggered_fade_created"] == 0
