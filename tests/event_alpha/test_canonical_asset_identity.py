from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.radar import asset_registry
from crypto_rsi_scanner.event_alpha.radar import instrument_resolver
from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner
from crypto_rsi_scanner.event_alpha.radar.canonical_asset import CanonicalAsset


def _bitcoin() -> CanonicalAsset:
    return CanonicalAsset(
        canonical_asset_id="bitcoin",
        symbol="BTC",
        coin_id="bitcoin",
        aliases=("BTC", "bitcoin"),
        is_tradable_asset=True,
        source="fixture_registry",
    )


def test_projection_rejects_non_text_identity_and_collection_members() -> None:
    asset = CanonicalAsset.from_mapping(
        {
            "canonical_asset_id": True,
            "coin_id": "safe-token",
            "symbol": {"forged": "symbol"},
            "aliases": {"TRUE": "forged"},
            "contracts_by_chain": {True: [False, {"x": 1}]},
        }
    )

    assert asset.canonical_asset_id == ""
    assert asset.coin_id == "safe-token"
    assert asset.symbol == ""
    assert asset.aliases == ()
    assert asset.contracts_by_chain == {}
    assert asset_registry.registry_index_keys(asset) == ()


def test_projection_keeps_absent_identity_fallback_and_typed_members() -> None:
    asset = CanonicalAsset.from_mapping(
        {
            "base_symbol": "safe",
            "coin_id": "safe-token",
            "aliases": ["safe", True, None, {"x": 1}],
            "contracts_by_chain": {
                "ethereum": ["0xabc", False, {"x": 1}],
                False: ["0xforged"],
            },
        }
    )

    assert asset.canonical_asset_id == "safe-token"
    assert asset.symbol == "SAFE"
    assert asset.aliases == ("safe",)
    assert asset.contracts_by_chain == {"ethereum": ("0xabc",)}


def test_registry_load_and_merge_drop_malformed_canonical_identity(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "canonical_asset_id": False,
                        "coin_id": "forged-fallback",
                        "symbol": "FORGED",
                    },
                    {
                        "canonical_asset_id": "safe-token",
                        "coin_id": "safe-token",
                        "symbol": "SAFE",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    malformed_direct = CanonicalAsset(  # type: ignore[arg-type]
        canonical_asset_id=True,
        symbol="FORGED",
        coin_id="forged-fallback",
    )

    assert [asset.canonical_asset_id for asset in asset_registry.load_asset_registry(path)] == [
        "safe-token"
    ]
    assert asset_registry._merge_assets((malformed_direct,)) == ()


def test_registry_writer_rejects_malformed_direct_identity(tmp_path: Path) -> None:
    malformed = CanonicalAsset(  # type: ignore[arg-type]
        canonical_asset_id=True,
        symbol="FORGED",
        coin_id="forged",
    )

    with pytest.raises(ValueError, match="malformed canonical identity"):
        asset_registry.write_asset_registry_artifact((malformed,), tmp_path)

    assert not (tmp_path / asset_registry.ASSET_REGISTRY_JSON).exists()


def test_coingecko_registry_does_not_borrow_beneath_invalid_provider_id(tmp_path: Path) -> None:
    path = tmp_path / "universe.json"
    path.write_text(
        json.dumps(
            {
                "coins": [
                    {"id": True, "coin_id": "forged-fallback", "symbol": "BAD"},
                    {"id": "safe-token", "symbol": "safe", "name": "Safe Token"},
                ]
            }
        ),
        encoding="utf-8",
    )

    assets = asset_registry.assets_from_coingecko_universe(path)

    assert [(asset.canonical_asset_id, asset.symbol) for asset in assets] == [
        ("safe-token", "SAFE")
    ]


def test_resolver_fails_closed_on_explicit_invalid_or_conflicting_canonical_id() -> None:
    registry = (_bitcoin(),)

    invalid_rows, invalid_resolutions = instrument_resolver.resolve_rows(
        [{"canonical_asset_id": True, "coin_id": "bitcoin", "symbol": "BTC"}],
        registry,
    )
    conflicting_rows, conflicting_resolutions = instrument_resolver.resolve_rows(
        [{"canonical_asset_id": "not-bitcoin", "coin_id": "bitcoin", "symbol": "BTC"}],
        registry,
    )
    fallback_rows, fallback_resolutions = instrument_resolver.resolve_rows(
        [{"canonical_asset_id": "", "coin_id": "bitcoin", "symbol": "BTC"}],
        registry,
    )

    assert invalid_rows[0]["canonical_asset_id"] is None
    assert invalid_rows[0]["instrument_resolver_status"] == "unresolved"
    assert invalid_rows[0]["instrument_resolver_match_reason"] == "invalid_canonical_asset_id"
    assert "canonical_asset_identity_invalid" in invalid_rows[0]["instrument_resolver_warnings"]
    assert invalid_resolutions[0]["canonical_asset_id"] is None

    assert conflicting_rows[0]["canonical_asset_id"] == "not-bitcoin"
    assert conflicting_rows[0]["instrument_resolver_status"] == "unresolved"
    assert conflicting_rows[0]["instrument_resolver_match_reason"] == "canonical_asset_id_unresolved"
    assert conflicting_resolutions[0]["instrument_identity_trusted"] is False

    assert fallback_rows[0]["canonical_asset_id"] == "bitcoin"
    assert fallback_rows[0]["instrument_resolver_status"] == "resolved"
    assert fallback_resolutions[0]["resolver_match_reason"] == "coin_id_exact"


def test_resolver_and_market_enrichment_reproject_direct_registry_values() -> None:
    malformed_alias = CanonicalAsset(  # type: ignore[arg-type]
        canonical_asset_id="safe-token",
        symbol="SAFE",
        coin_id="safe-token",
        aliases={"bitcoin": "forged"},
    )

    rows, resolutions = instrument_resolver.resolve_rows(
        [{"coin_id": "bitcoin", "symbol": "OTHER"}],
        (malformed_alias,),
    )

    assert rows[0]["instrument_resolver_status"] == "unresolved"
    assert resolutions[0]["resolver_match_reason"] == "unresolved"
    assert market_anomaly_scanner._asset_rows((malformed_alias,))[0].aliases == ()

