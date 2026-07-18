from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_providers import defillama_mapping_registry


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "event_dex_onchain"
MARKET_ROWS = FIXTURE_DIR / "defillama_mapping_market_rows.json"
REGISTRY = FIXTURE_DIR / "defillama_mapping_registry.json"


def _market_rows() -> list[dict[str, object]]:
    return json.loads(MARKET_ROWS.read_text(encoding="utf-8"))["rows"]


def _registry() -> dict[str, object]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _raw(value: dict[str, object]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def test_review_is_deterministic_and_never_infers_protocol_identity() -> None:
    first = defillama_mapping_registry.build_mapping_review(_market_rows())
    second = defillama_mapping_registry.build_mapping_review(_market_rows())

    assert first == second
    assert first["asset_count"] == 2
    assert first["automatic_identity_inference"] is False
    assert first["provider_calls"] == 0
    assert all(row["mapping_status"] == "pending" for row in first["assets"])
    assert all(row["protocol_list_id"] is None for row in first["assets"])


def test_fixture_registry_requires_explicit_test_allowance() -> None:
    with pytest.raises(
        defillama_mapping_registry.DefiLlamaMappingRegistryError,
        match="fixture_registry_not_allowed",
    ):
        defillama_mapping_registry.normalize_mapping_registry(REGISTRY.read_bytes())

    registry = defillama_mapping_registry.normalize_mapping_registry(
        REGISTRY.read_bytes(),
        allow_fixture=True,
    )
    review = defillama_mapping_registry.build_mapping_review(_market_rows())
    coverage = defillama_mapping_registry.assess_mapping_coverage(review, registry)

    assert registry["mapping_count"] == 2
    assert registry["provider_calls"] == 0
    assert registry["mappings"][0]["mapping_authority"] == "operator_confirmed_fixture"
    assert coverage["coverage_complete"] is True
    assert coverage["coverage_counts"] == {
        "mapped": 1,
        "not_applicable": 1,
        "unreviewed": 0,
        "identity_conflict": 0,
    }
    assert coverage["live_capture_mapping_eligible"] is False
    assert coverage["live_capture_mapping_blockers"] == ["operator_registry_required"]


def test_exact_operator_registry_can_close_mapping_coverage_without_provider_call() -> None:
    value = _registry()
    value.update(
        {
            "registry_id": "defillama-map-v1:operator-review-1",
            "registry_mode": "operator",
            "reviewed_by": "human-owner",
        }
    )
    registry = defillama_mapping_registry.normalize_mapping_registry(_raw(value))
    review = defillama_mapping_registry.build_mapping_review(_market_rows())
    coverage = defillama_mapping_registry.assess_mapping_coverage(review, registry)

    assert registry["registry_mode"] == "operator"
    assert all(
        row["mapping_authority"] == "operator_confirmed_registry"
        for row in registry["mappings"]
    )
    assert coverage["coverage_complete"] is True
    assert coverage["live_capture_mapping_eligible"] is True
    assert coverage["live_capture_mapping_blockers"] == []
    assert coverage["provider_calls"] == 0


def test_missing_or_conflicting_review_never_becomes_complete() -> None:
    review = defillama_mapping_registry.build_mapping_review(_market_rows())
    value = _registry()
    value["mappings"] = value["mappings"][:1]
    partial = defillama_mapping_registry.normalize_mapping_registry(
        _raw(value),
        allow_fixture=True,
    )
    partial_coverage = defillama_mapping_registry.assess_mapping_coverage(review, partial)
    assert partial_coverage["coverage_complete"] is False
    assert partial_coverage["coverage_counts"]["unreviewed"] == 1

    value = _registry()
    value["mappings"][1]["coingecko_asset_id"] = "aave-v2"
    conflict = defillama_mapping_registry.normalize_mapping_registry(
        _raw(value),
        allow_fixture=True,
    )
    conflict_coverage = defillama_mapping_registry.assess_mapping_coverage(review, conflict)
    assert conflict_coverage["coverage_complete"] is False
    assert conflict_coverage["coverage_counts"]["identity_conflict"] == 1

    value = _registry()
    value["mappings"][1]["symbol"] = "AAVEV2"
    symbol_conflict = defillama_mapping_registry.normalize_mapping_registry(
        _raw(value),
        allow_fixture=True,
    )
    symbol_coverage = defillama_mapping_registry.assess_mapping_coverage(
        review,
        symbol_conflict,
    )
    assert symbol_coverage["coverage_complete"] is False
    assert symbol_coverage["coverage_counts"]["identity_conflict"] == 1


def test_coverage_rejects_noncanonical_registry_and_review_objects() -> None:
    review = defillama_mapping_registry.build_mapping_review(_market_rows())
    registry = defillama_mapping_registry.normalize_mapping_registry(
        REGISTRY.read_bytes(),
        allow_fixture=True,
    )

    malformed_registry = deepcopy(registry)
    malformed_registry["mappings"][1]["mapping_status"] = "pending"
    with pytest.raises(
        defillama_mapping_registry.DefiLlamaMappingRegistryError,
        match="status_invalid",
    ):
        defillama_mapping_registry.assess_mapping_coverage(review, malformed_registry)

    malformed_review = deepcopy(review)
    malformed_review["provider_calls"] = 1
    with pytest.raises(
        defillama_mapping_registry.DefiLlamaMappingRegistryError,
        match="review_schema_invalid",
    ):
        defillama_mapping_registry.assess_mapping_coverage(malformed_review, registry)


def test_missing_registry_exposes_exact_live_mapping_blockers() -> None:
    review = defillama_mapping_registry.build_mapping_review(_market_rows())

    coverage = defillama_mapping_registry.assess_mapping_coverage(review, None)

    assert coverage["coverage_complete"] is False
    assert coverage["coverage_counts"]["unreviewed"] == 2
    assert coverage["live_capture_mapping_eligible"] is False
    assert coverage["live_capture_mapping_blockers"] == [
        "operator_registry_missing",
        "registry_universe_digest_mismatch",
        "mapping_cardinality_mismatch",
        "unreviewed_assets_present",
    ]


@pytest.mark.parametrize(
    ("mutate", "error"),
    (
        (
            lambda value: value["mappings"][1].update(protocol_list_id=None),
            "protocol_identity_missing",
        ),
        (
            lambda value: value["mappings"][0].update(protocol_slug="bitcoin"),
            "not_applicable_has_protocol",
        ),
        (
            lambda value: value["mappings"].append(deepcopy(value["mappings"][0])),
            "mapping_canonical_asset_id_duplicate",
        ),
        (
            lambda value: value.update(api_key="forbidden"),
            "sensitive_key_forbidden",
        ),
        (
            lambda value: value.update(market_universe_sha256="bad"),
            "market_universe_sha256_invalid",
        ),
    ),
)
def test_registry_rejects_ambiguous_or_unsafe_decisions(mutate, error: str) -> None:
    value = _registry()
    mutate(value)

    with pytest.raises(
        defillama_mapping_registry.DefiLlamaMappingRegistryError,
        match=error,
    ):
        defillama_mapping_registry.normalize_mapping_registry(
            _raw(value),
            allow_fixture=True,
        )


def test_cli_reports_fixture_coverage_without_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    before = tuple(tmp_path.iterdir())
    result = defillama_mapping_registry.main(
        [
            str(MARKET_ROWS),
            "--registry",
            str(REGISTRY),
            "--allow-fixture-registry",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["coverage_complete"] is True
    assert payload["live_capture_mapping_eligible"] is False
    assert tuple(tmp_path.iterdir()) == before
