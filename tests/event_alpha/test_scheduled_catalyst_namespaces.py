"""Structured catalyst, unlock preflight, source-coverage, narrative, and research-card regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.namespace import lifecycle

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


@pytest.mark.parametrize(
    "filename",
    (
        "event_scheduled_catalysts.jsonl",
        "event_unlock_candidates.jsonl",
        "event_scheduled_catalyst_report.md",
        "event_unlock_risk_report.md",
    ),
)
def test_scheduled_catalyst_outputs_refuse_symlink_leaves(tmp_path, filename):
    import crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts as scheduled

    namespace_dir = tmp_path / "artifacts" / "scheduled_symlink_leaf"
    namespace_dir.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    marker = b"outside-must-not-change\n"
    outside.write_bytes(marker)
    (namespace_dir / filename).symlink_to(outside)

    with pytest.raises(RuntimeError, match="artifact_not_regular"):
        scheduled.run_scheduled_catalyst_scan(
            namespace_dir=namespace_dir,
            provider_paths={},
            profile="fixture",
            artifact_namespace=namespace_dir.name,
            run_mode="fixture",
            run_id="run-symlink-leaf",
            observed_at="2026-07-14T00:00:00Z",
            calendar_rows=(),
        )

    assert outside.read_bytes() == marker


def test_scheduled_catalyst_outputs_refuse_symlink_namespace(tmp_path):
    import crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts as scheduled

    base = tmp_path / "artifacts"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    namespace_dir = base / "scheduled_symlink_namespace"
    namespace_dir.symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeError, match="namespace_not_directory"):
        scheduled.run_scheduled_catalyst_scan(
            namespace_dir=namespace_dir,
            provider_paths={},
            profile="fixture",
            artifact_namespace=namespace_dir.name,
            run_mode="fixture",
            run_id="run-symlink-namespace",
            observed_at="2026-07-14T00:00:00Z",
            calendar_rows=(),
        )

    assert tuple(outside.iterdir()) == ()


def test_scheduled_catalyst_can_omit_empty_unlock_artifacts_without_deletion(
    tmp_path,
):
    import crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts as scheduled

    namespace_dir = tmp_path / "artifacts" / "scheduled_without_unlocks"
    result = scheduled.run_scheduled_catalyst_scan(
        namespace_dir=namespace_dir,
        provider_paths={},
        profile="fixture",
        artifact_namespace=namespace_dir.name,
        run_mode="fixture",
        run_id="run-without-empty-unlocks",
        observed_at="2026-07-14T00:00:00Z",
        calendar_rows=(),
        include_empty_unlock_artifacts=False,
    )

    assert result.unlock_count == 0
    assert result.scheduled_path.is_file()
    assert result.scheduled_report_path.is_file()
    assert not result.unlock_path.exists()
    assert not result.unlock_report_path.exists()
    assert {path.name for path in namespace_dir.iterdir()} == {
        scheduled.SCHEDULED_CATALYSTS_FILENAME,
        scheduled.SCHEDULED_CATALYST_REPORT_FILENAME,
    }


def test_scheduled_catalyst_bundle_rejects_namespace_replacement_between_renames(
    tmp_path,
    monkeypatch,
):
    import crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts as scheduled

    base = tmp_path / "artifacts"
    namespace_dir = base / "scheduled_bundle_swap"
    namespace_dir.mkdir(parents=True)
    displaced = base / "scheduled_bundle_swap.displaced"
    replacement = base / "scheduled_bundle_swap.replacement"
    replacement.mkdir()
    outside = tmp_path / "outside.txt"
    marker = b"outside-must-not-change\n"
    outside.write_bytes(marker)
    for filename in (
        scheduled.SCHEDULED_CATALYSTS_FILENAME,
        scheduled.UNLOCK_CANDIDATES_FILENAME,
        scheduled.SCHEDULED_CATALYST_REPORT_FILENAME,
        scheduled.UNLOCK_RISK_REPORT_FILENAME,
    ):
        (replacement / filename).symlink_to(outside)
    original_rename = scheduled.market_anomaly_receipt.os.rename
    original_noreplace = scheduled.market_anomaly_receipt._rename_noreplace
    swapped = False

    def swapping_noreplace(namespace_fd, source, target):
        nonlocal swapped
        result = original_noreplace(namespace_fd, source, target)
        if not swapped:
            original_rename(namespace_dir, displaced)
            original_rename(replacement, namespace_dir)
            swapped = True
        return result

    monkeypatch.setattr(
        scheduled.market_anomaly_receipt,
        "_rename_noreplace",
        swapping_noreplace,
    )

    with pytest.raises(RuntimeError, match="namespace_identity"):
        scheduled.run_scheduled_catalyst_scan(
            namespace_dir=namespace_dir,
            provider_paths={},
            profile="fixture",
            artifact_namespace=namespace_dir.name,
            run_mode="fixture",
            run_id="run-bundle-swap",
            observed_at="2026-07-14T00:00:00Z",
            calendar_rows=(),
        )

    assert swapped is True
    assert outside.read_bytes() == marker


def test_market_reaction_unlock_structured_source_risk_or_fade_depends_on_market():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction

    no_reaction = event_market_reaction.evaluate_market_reaction({
        "source_class": "structured_unlock",
        "source_pack": "unlock_supply_pack",
        "impact_path_type": "unlock_supply_event",
        "evidence_quality_score": 90,
        "accepted_evidence_count": 1,
        "market_snapshot": {
            "return_24h": 0.0,
            "volume_zscore_24h": 0.2,
            "event_age_hours": -12,
            "market_context_freshness_status": "fresh",
        },
    })
    crowded = event_market_reaction.evaluate_market_reaction({
        "source_class": "structured_unlock",
        "source_pack": "unlock_supply_pack",
        "impact_path_type": "unlock_supply_event",
        "evidence_quality_score": 90,
        "accepted_evidence_count": 1,
        "market_snapshot": {
            "return_24h": 0.46,
            "volume_zscore_24h": 4.5,
            "event_age_hours": 4,
            "market_context_freshness_status": "fresh",
        },
        "derivatives_snapshot": {
            "open_interest_24h_change_pct": 0.36,
            "funding_rate_8h": 0.001,
        },
    })

    assert no_reaction.opportunity_type == "RISK_ONLY"
    assert crowded.opportunity_type == "FADE_SHORT_REVIEW"


def test_scheduled_catalyst_fixture_lanes_and_unlock_artifacts():
    import crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts as event_scheduled_catalysts

    with TemporaryDirectory() as tmp:
        result = event_scheduled_catalysts.run_scheduled_catalyst_scan(
            namespace_dir=tmp,
            provider_paths={
                "tokenomist": "fixtures/event_discovery/scheduled_tokenomist_unlocks.json",
                "coinmarketcal": "fixtures/event_discovery/scheduled_coinmarketcal_events.json",
            },
            profile="fixture",
            artifact_namespace="scheduled_catalyst_smoke",
            run_mode="fixture",
            run_id="run-scheduled-fixture",
            observed_at="2026-06-15T16:00:00Z",
        )
        scheduled = event_scheduled_catalysts.load_scheduled_catalysts(tmp)
        unlocks = event_scheduled_catalysts.load_unlock_candidates(tmp)

    by_symbol = {str(row.get("symbol") or ""): row for row in scheduled}
    unlock_by_symbol = {str(row.get("symbol") or ""): row for row in unlocks}

    assert result.scheduled_count == 6
    assert result.unlock_count == 2
    assert by_symbol["TESTUP"]["opportunity_type"] == "EARLY_LONG_RESEARCH"
    assert by_symbol["TESTBREAK"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
    assert by_symbol["TESTRUMOR"]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
    assert by_symbol["TESTCANCEL"]["opportunity_type"] == "DIAGNOSTIC"
    assert unlock_by_symbol["TESTUNLOCK"]["opportunity_type"] == "RISK_ONLY"
    assert unlock_by_symbol["TESTRALLY"]["opportunity_type"] == "FADE_SHORT_REVIEW"
    assert all(row["created_alert"] is False for row in [*scheduled, *unlocks])
    assert all(row["research_only"] is True for row in [*scheduled, *unlocks])


def test_unlock_calendar_preflight_provider_rows_and_doctor_conflicts():
    import json
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight as event_unlock_calendar_preflight

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        report = event_unlock_calendar_preflight.build_preflight_report(
            namespace_dir=base,
            profile="fixture",
            artifact_namespace="unlock_calendar_preflight",
            tokenomist_path="fixtures/event_discovery/scheduled_tokenomist_unlocks.json",
            messari_path="fixtures/event_discovery/scheduled_messari_unlocks.json",
            coinmarketcal_path="fixtures/event_discovery/scheduled_coinmarketcal_events.json",
            smoke_mode=True,
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        )
        json_path, _md_path = event_unlock_calendar_preflight.write_preflight_artifacts(report, base)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        by_provider = {row["provider"]: row for row in payload["providers"]}
        clean = event_unlock_calendar_preflight.artifact_conflicts(base)

        assert payload["preflight_status"] == "fixture_ready"
        assert payload["live_call_allowed"] is False
        assert payload["research_only"] is True
        assert set(by_provider) == {"tokenomist", "messari_unlocks", "coinmarketcal"}
        assert by_provider["tokenomist"]["fixture_parser_status"] == "pass"
        assert by_provider["messari_unlocks"]["fixture_parser_status"] == "pass"
        assert by_provider["coinmarketcal"]["fixture_parser_status"] == "pass"
        assert by_provider["messari_unlocks"]["env_vars_required"] == [
            "RSI_EVENT_ALPHA_SCHEDULED_CATALYST_MESSARI_PATH",
            "MESSARI_API_KEY",
        ]
        assert all(row["live_call_allowed"] is False for row in by_provider.values())
        assert all(row["telegram_sends"] == 0 for row in by_provider.values())
        assert clean["unlock_calendar_preflight_secret_leak"] == 0
        assert clean["unlock_calendar_preflight_live_without_ledger"] == 0
        assert clean["unlock_calendar_preflight_forbidden_side_effect_claim"] == 0

        payload["live_call_allowed"] = True
        payload["providers"][0]["live_call_allowed"] = True
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        unsafe = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=base / "event_alpha_source_coverage.md",
            profile="fixture",
            artifact_namespace="unlock_calendar_preflight",
            include_test_artifacts=True,
            strict=True,
        )

    assert unsafe.unlock_calendar_preflight_live_without_ledger >= 1
    assert unsafe.status == "BLOCKED"


def test_source_coverage_links_unlock_calendar_preflight_artifacts():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.radar.source_coverage as event_alpha_source_coverage
    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status
    import crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight as event_unlock_calendar_preflight

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        preflight = event_unlock_calendar_preflight.build_preflight_report(
            namespace_dir=base,
            profile="fixture",
            artifact_namespace="scheduled_catalyst_smoke",
            tokenomist_path="fixtures/event_discovery/scheduled_tokenomist_unlocks.json",
            messari_path="fixtures/event_discovery/scheduled_messari_unlocks.json",
            coinmarketcal_path="fixtures/event_discovery/scheduled_coinmarketcal_events.json",
            smoke_mode=True,
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        )
        event_unlock_calendar_preflight.write_preflight_artifacts(preflight, base)
        provider_status = event_provider_status.build_event_discovery_provider_status(_event_provider_status_cfg())
        report = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=provider_status,
            profile="fixture",
            artifact_namespace="scheduled_catalyst_smoke",
            artifact_namespace_dir=base,
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        )
        text = event_alpha_source_coverage.format_source_coverage_report(report)

    assert report.unlock_calendar_preflight_status == "fixture_ready"
    assert report.unlock_calendar_preflight_report_path.endswith("event_unlock_calendar_preflight.md")
    assert "Unlock/calendar preflight: fixture_ready" in text
    assert "event_unlock_calendar_preflight.md" in text
    assert "messari_unlocks configured=true fixture_parser_status=pass" in text


def test_cryptopanic_fan_narrative_is_not_structured_unlock_proof():
    import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction
    import crypto_rsi_scanner.event_alpha.providers.source_packs as event_source_packs

    row = {
        "provider": "cryptopanic",
        "source_class": "cryptopanic_tagged",
        "source_pack": "unlock_supply_pack",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "title": "CHZ fan token narrative before World Cup",
        "currency_tags": ["CHZ"],
        "source_url": "https://cryptopanic.com/news/chz-world-cup",
        "event_time": "2026-06-16T16:00:00Z",
        "unlock_pct_circulating": 0.10,
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
        "market_snapshot": {
            "return_24h": 0.20,
            "volume_zscore_24h": 3.0,
            "market_context_freshness_status": "fresh",
        },
    }
    pack_result = event_source_packs.evaluate_pack_evidence(row, pack=event_source_packs.get_source_pack("unlock_supply_pack"))
    reaction = event_market_reaction.evaluate_market_reaction({
        **row,
        "impact_path_type": "unlock_supply_event",
        "evidence_quality_score": 86,
        "accepted_evidence_count": 1,
    })

    assert pack_result["source_pack_validated_digest_sufficient"] is False
    assert "structured_unlock_source_required" in pack_result["source_pack_missing_evidence"]
    assert reaction.opportunity_type == "UNCONFIRMED_RESEARCH"
    assert "structured_unlock_source_required" in reaction.why_not_alertable


def test_research_card_renders_scheduled_unlock_details():
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts as event_scheduled_catalysts

    with TemporaryDirectory() as tmp:
        result = event_scheduled_catalysts.run_scheduled_catalyst_scan(
            namespace_dir=tmp,
            provider_paths={
                "tokenomist": "fixtures/event_discovery/scheduled_tokenomist_unlocks.json",
                "coinmarketcal": "fixtures/event_discovery/scheduled_coinmarketcal_events.json",
            },
            profile="fixture",
            artifact_namespace="unlock_risk_smoke",
            run_mode="fixture",
            run_id="run-scheduled-fixture",
            observed_at="2026-06-15T16:00:00Z",
        )
    row = next(item for item in result.unlock_candidates if item["symbol"] == "TESTUNLOCK")
    row = {**row, "alert_id": "TESTUNLOCK", "tier": "STORE_ONLY"}
    card = event_research_cards.render_research_card("TESTUNLOCK", alert_rows=[row])

    assert card.found is True
    assert "## Scheduled Catalyst / Unlock Details" in card.markdown
    assert "- Unlock time: 2026-06-16T08:00:00+00:00" in card.markdown
    assert "- Structured unlock proof: true" in card.markdown
