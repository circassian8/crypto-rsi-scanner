"""Event Alpha compatibility-shim registry tests."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import importlib

from crypto_rsi_scanner.event_alpha import shims


def test_known_active_shims_are_minimal_compatibility_modules():
    report = shims.audit_registry()

    assert report["registry_entry_count"] >= 50
    assert report["shim_status_counts"][shims.STATUS_ACTIVE_SHIM] >= 40
    assert report["active_shim_modules_with_implementation_logic"] == 0
    assert not report["active_shim_violations"]
    assert any(
        row["old_module"] == "crypto_rsi_scanner.event_alpha_artifact_doctor"
        and row["shim_status"] == shims.STATUS_ACTIVE_SHIM
        for row in report["entries"]
    )


def test_partial_shim_with_implementation_logic_is_not_active_shim_violation():
    entry = shims.ShimRegistryEntry(
        old_module="crypto_rsi_scanner.event_alpha_fixture_partial",
        new_module="crypto_rsi_scanner.event_alpha.new_home",
        shim_status=shims.STATUS_PARTIAL_SHIM,
        allowed_exports=("*",),
        notes="fixture partial migration bridge",
    )
    report = shims.audit_entries(
        (entry,),
        source_loader=lambda _entry: '"""partial shim fixture."""\n\ndef still_migrating():\n    return 1\n',
    )

    assert report["status"] == "OK"
    assert report["active_shim_modules_with_implementation_logic"] == 0
    assert report["partial_shim_modules_with_implementation_logic"] == 1
    assert report["active_shim_violations"] == []


def test_active_shim_fixture_with_new_logic_fails_audit():
    entry = shims.ShimRegistryEntry(
        old_module="crypto_rsi_scanner.event_alpha_fixture_active",
        new_module="crypto_rsi_scanner.event_alpha.new_home",
        shim_status=shims.STATUS_ACTIVE_SHIM,
        allowed_exports=("*",),
    )
    report = shims.audit_entries(
        (entry,),
        source_loader=lambda _entry: '"""active shim fixture."""\n\ndef new_logic():\n    return 1\n',
    )

    assert report["status"] == "WARN"
    assert report["active_shim_modules_with_implementation_logic"] == 1
    assert "FunctionDef" in "; ".join(report["active_shim_violations"][0]["violations"])


def test_shim_report_writer_outputs_json_and_markdown():
    with TemporaryDirectory() as tmp:
        json_path, md_path, report = shims.write_shim_report(out_dir=tmp)

        assert json_path == Path(tmp) / shims.REPORT_JSON
        assert md_path == Path(tmp) / shims.REPORT_MD
        assert report["active_shim_modules_with_implementation_logic"] == 0
        assert json_path.exists()
        assert md_path.exists()
        text = md_path.read_text(encoding="utf-8")
        assert "Event Alpha Shim Report" in text
        assert "active_shim" in text


def test_artifact_doctor_warns_when_active_shim_contains_logic():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    original = event_alpha_artifact_doctor.event_alpha_shims.active_shim_violation_summary
    event_alpha_artifact_doctor.event_alpha_shims.active_shim_violation_summary = (
        lambda: (1, ("crypto_rsi_scanner.event_alpha_fixture_active",))
    )
    try:
        result = event_alpha_artifact_doctor.diagnose_artifacts()
    finally:
        event_alpha_artifact_doctor.event_alpha_shims.active_shim_violation_summary = original

    assert any("paths.active_shim_contains_logic" in warning for warning in result.warnings)


def test_recently_migrated_old_and_new_import_paths_share_key_callables():
    pairs = (
        ("crypto_rsi_scanner.event_research_cards", "crypto_rsi_scanner.event_alpha.artifacts.research_cards", "render_research_card"),
        ("crypto_rsi_scanner.event_alpha_daily_brief", "crypto_rsi_scanner.event_alpha.artifacts.daily_brief", "build_daily_brief"),
        ("crypto_rsi_scanner.event_derivatives_crowding", "crypto_rsi_scanner.event_alpha.radar.derivatives_crowding", "run_derivatives_crowding_scan"),
        ("crypto_rsi_scanner.event_scheduled_catalysts", "crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts", "run_scheduled_catalyst_scan"),
        ("crypto_rsi_scanner.event_asset_registry", "crypto_rsi_scanner.event_alpha.radar.asset_registry", "build_asset_registry"),
        ("crypto_rsi_scanner.event_instrument_resolver", "crypto_rsi_scanner.event_alpha.radar.instrument_resolver", "resolve_rows"),
        ("crypto_rsi_scanner.event_market_confirmation", "crypto_rsi_scanner.event_alpha.radar.market_confirmation", "evaluate_market_confirmation"),
        ("crypto_rsi_scanner.event_catalyst_search", "crypto_rsi_scanner.event_alpha.radar.catalyst_search", "run_catalyst_search"),
        ("crypto_rsi_scanner.event_source_enrichment", "crypto_rsi_scanner.event_alpha.radar.source_enrichment", "enrich_source_text"),
        ("crypto_rsi_scanner.event_opportunity_audit", "crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit", "format_opportunity_audit"),
    )
    for old_name, new_name, attr in pairs:
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        assert getattr(old_module, attr) is getattr(new_module, attr)
