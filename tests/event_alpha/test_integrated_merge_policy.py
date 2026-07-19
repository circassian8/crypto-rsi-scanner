import hashlib
import json
from tempfile import TemporaryDirectory

from crypto_rsi_scanner.event_alpha.artifacts.context import context_from_profile
from crypto_rsi_scanner.event_alpha.radar.integrated import api as integrated_api
from crypto_rsi_scanner.event_alpha.radar.integrated.pipeline_parts import merge, merge_policy
from crypto_rsi_scanner.event_alpha.radar.integrated_radar import run_integrated_radar_cycle


_MERGE_GOLDEN_FIELDS = (
    "candidate_family_id",
    "symbol",
    "coin_id",
    "canonical_asset_id",
    "instrument_resolver_status",
    "instrument_resolver_confidence",
    "is_tradable_asset",
    "is_theme_or_sector",
    "is_quote_asset",
    "source_origin",
    "source_origins",
    "source_pack",
    "source_packs",
    "source_class",
    "source_strength",
    "opportunity_type",
    "final_opportunity_level",
    "route",
    "state",
    "score",
    "reason_codes",
    "warnings",
    "market_state_class",
    "integrated_market_confirmation_level",
    "integrated_market_confirmation_score",
    "market_state_snapshot",
    "latest_market_snapshot",
    "derivatives_state_snapshot",
    "crowding_class",
    "fade_readiness",
    "crowding_exhaustion_evidence",
    "dex_liquidity_snapshot",
    "dex_liquidity_level",
    "protocol_metrics_snapshot",
    "protocol_metrics_level",
    "official_exchange_event",
    "scheduled_catalyst_event",
    "unlock_event",
    "accepted_evidence_count",
    "evidence_acquisition_status",
    "triggered_fade_created",
    "normal_rsi_signal_written",
    "created_alert",
    "research_only",
    "paper_trade_created",
    "notification_send_enabled",
)

_MERGE_GOLDEN_HASHES = {
    "AAVE": "57371f4ca538058b7ec83ff4fbe56560287d40d49b93a340366da3b333ebda17",
    "BTC": "4d7fd0d99088e7924219b0493642cc18cd0bab85810434f789bd5cc6460f1024",
    "SECTOR": "69f2105bc4197a8e5b998078a9b898754f8a7178a02a0e2e770db2c17ea777fa",
    "TESTFADE": "6a0bcba166548da8043109418b6b6eb87208039e50cc192f99ce103c93a95cda",
    "TESTPERP": "cc591fd01f48694e521286dca1b44b20761d7490ff8408de3976928c2be0b74a",
    "TKNC": "133d9cb81b249386b6a01c717939d61b13f894495a2d1e37325c1037a3cea229",
}


def _merge_golden_digest(row):
    payload = {key: row.get(key) for key in _MERGE_GOLDEN_FIELDS}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_integrated_merge_policy_preserves_compatibility_exports():
    assert set(merge_policy.__all__).issubset(integrated_api.__all__)
    for name in merge_policy.__all__:
        policy_function = getattr(merge_policy, name)
        api_function = getattr(integrated_api, name)
        assert getattr(merge, name) is api_function
        assert api_function.__wrapped__ is policy_function


def test_integrated_merge_identity_source_market_and_derivatives_golden_snapshot():
    with TemporaryDirectory() as tmp:
        context = context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=tmp,
            artifact_namespace="merge_golden",
        )
        result = run_integrated_radar_cycle(
            context=context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
        )
        rows = [
            json.loads(line)
            for line in result.integrated_candidates_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    by_symbol = {row["symbol"]: row for row in rows}
    actual = {
        symbol: _merge_golden_digest(by_symbol[symbol])
        for symbol in _MERGE_GOLDEN_HASHES
    }
    assert actual == _MERGE_GOLDEN_HASHES
    assert all(by_symbol[symbol]["created_alert"] is False for symbol in actual)
    assert all(by_symbol[symbol]["research_only"] is True for symbol in actual)
    assert all(by_symbol[symbol]["paper_trade_created"] is False for symbol in actual)
    assert all(by_symbol[symbol]["notification_send_enabled"] is False for symbol in actual)
    assert all(by_symbol[symbol]["triggered_fade_created"] is False for symbol in actual)
    assert all(by_symbol[symbol]["normal_rsi_signal_written"] is False for symbol in actual)
