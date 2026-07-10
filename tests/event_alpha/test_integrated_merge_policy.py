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
    "AAVE": "ccd9e11dc6630354e754deef10e18c15336d2304aca4f6ed1cdff9900a672379",
    "BTC": "925cb96543407afa9c9c0063fa6f62931b0b24bb6d5a6a91a9b326edee0997a2",
    "SECTOR": "aae11ab8df651a744f94a627510fb257c9cefe1a65cf18b962ed1c95d2d9e0de",
    "TESTFADE": "899853d28d0eacab564dc26fa25a7b5aeb1423c2c16528c06fd68f84b57fc4d4",
    "TESTPERP": "e938f1fe1fc21f91a70bfddfc57f4883d8bb5fb38114a5cab85864bd2e80855b",
    "TKNC": "96dd2bf43440040e00051b6ad40492c952435d5cfadc93a70a12346a0671d795",
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
