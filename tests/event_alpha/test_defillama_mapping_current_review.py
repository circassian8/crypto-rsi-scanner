from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    defillama_mapping_current_review as current_review,
)
from crypto_rsi_scanner.event_providers import defillama_mapping_registry


def _snapshot() -> SimpleNamespace:
    namespace = "radar_market_no_send_20260718t194216z_example"
    run_id = "2026-07-18T19:42:16+00:00|no_key_live"
    profile = "no_key_live"
    names = (
        ("aave", "AAVE", "Aave"),
        ("uniswap", "UNI", "Uniswap"),
    )
    observations = tuple(
        {
            "artifact_namespace": namespace,
            "run_id": run_id,
            "profile": profile,
            "canonical_asset_id": coin_id,
            "coin_id": coin_id,
            "symbol": symbol,
        }
        for coin_id, symbol, _name in names
    )
    generation = {
        "data_mode": "live",
        "provider": "coingecko",
        "provider_request_succeeded": True,
        "decision_radar_campaign_counted": True,
        "no_send": True,
        "research_only": True,
        "selected_market_row_count": len(observations),
        "universe_audit": {
            "kept": [
                {"id": coin_id, "symbol": symbol.lower(), "name": name}
                for coin_id, symbol, name in names
            ]
        },
    }
    return SimpleNamespace(
        generation_authority_status="authoritative",
        artifact_namespace=namespace,
        run_id=run_id,
        profile=profile,
        revision=12,
        operator_state_sha256="a" * 64,
        generation_authority_checked_at="2026-07-18T19:43:00+00:00",
        current_market_observations=observations,
        market_generation=generation,
    )


def _operator_registry(packet: dict[str, object]) -> dict[str, object]:
    template = deepcopy(packet["operator_registry_template"])
    assert isinstance(template, dict)
    template.update(
        {
            "registry_id": "defillama-map-v1:owner-july-review",
            "reviewed_at": "2026-07-18T20:00:00+00:00",
            "reviewed_by": "owner",
        }
    )
    mappings = template["mappings"]
    assert isinstance(mappings, list)
    for row in mappings:
        row.update(
            {
                "mapping_status": "not_applicable",
                "review_note": "No matching protocol after explicit review.",
                "reviewer_confirmed": True,
            }
        )
    return defillama_mapping_registry.normalize_mapping_registry(
        (json.dumps(template, sort_keys=True) + "\n").encode()
    )


def test_current_review_binds_exact_authority_and_emits_invalid_pending_template() -> None:
    packet = current_review.build_current_mapping_review(_snapshot())

    assert packet["status"] == "operator_action_required"
    assert packet["authority_binding"]["namespace_source"] == (
        "current_dashboard_pointer"
    )
    assert packet["mapping_review"]["asset_count"] == 2
    assert [row["name"] for row in packet["mapping_review"]["assets"]] == [
        "Aave",
        "Uniswap",
    ]
    assert packet["coverage"]["coverage_counts"]["unreviewed"] == 2
    assert packet["coverage"]["live_capture_mapping_eligible"] is False
    assert packet["provider_calls"] == 0
    assert packet["writes"] == 0
    assert packet["automatic_identity_inference"] is False
    assert packet["protocol_v2_evidence_eligible"] is False
    template = packet["operator_registry_template"]
    assert all(row["mapping_status"] == "pending" for row in template["mappings"])
    assert all(row["reviewer_confirmed"] is False for row in template["mappings"])
    assert template["market_universe_sha256"] == packet["mapping_review"][
        "market_universe_sha256"
    ]
    with pytest.raises(
        defillama_mapping_registry.DefiLlamaMappingRegistryError,
        match="registry_id_invalid",
    ):
        defillama_mapping_registry.normalize_mapping_registry(
            (json.dumps(template, sort_keys=True) + "\n").encode()
        )


def test_exact_completed_registry_closes_only_mapping_prerequisite() -> None:
    initial = current_review.build_current_mapping_review(_snapshot())
    registry = _operator_registry(initial)

    packet = current_review.build_current_mapping_review(
        _snapshot(), registry=registry
    )

    assert packet["status"] == "mapping_review_complete"
    assert packet["coverage"]["coverage_complete"] is True
    assert packet["coverage"]["live_capture_mapping_eligible"] is True
    assert packet["human_decision_required"] is False
    assert packet["mapping_eligibility_grants_provider_authorization"] is False
    assert packet["protocol_v2_evidence_eligible"] is False
    assert packet["automatic_policy_effect"] == "none"


def test_registry_for_different_universe_remains_explicitly_not_current() -> None:
    initial = current_review.build_current_mapping_review(_snapshot())
    registry = _operator_registry(initial)
    drifted = deepcopy(registry)
    drifted["market_universe_sha256"] = "b" * 64
    drifted.pop("registry_sha256")
    drifted["registry_sha256"] = defillama_mapping_registry._digest(drifted)

    packet = current_review.build_current_mapping_review(
        _snapshot(), registry=drifted
    )

    assert packet["status"] == "operator_registry_not_current"
    assert packet["coverage"]["registry_digest_matches_universe"] is False
    assert "registry_universe_digest_mismatch" in packet["coverage"][
        "live_capture_mapping_blockers"
    ]


@pytest.mark.parametrize(
    ("mutate", "error"),
    (
        (
            lambda snapshot: setattr(
                snapshot, "generation_authority_status", "untrusted"
            ),
            "current_mapping_review_authority_required",
        ),
        (
            lambda snapshot: snapshot.market_generation.update(
                selected_market_row_count=1
            ),
            "current_market_observation_count_mismatch",
        ),
        (
            lambda snapshot: snapshot.market_generation["universe_audit"]["kept"][
                0
            ].update(symbol="wrong"),
            "current_market_observation_universe_symbol_mismatch",
        ),
        (
            lambda snapshot: snapshot.current_market_observations[0].update(
                run_id="other-run"
            ),
            "current_market_observation_run_id_mismatch",
        ),
    ),
)
def test_current_review_fails_closed_on_authority_or_identity_drift(
    mutate, error: str
) -> None:
    snapshot = _snapshot()
    mutate(snapshot)

    with pytest.raises(
        current_review.DefiLlamaCurrentMappingReviewError,
        match=error,
    ):
        current_review.build_current_mapping_review(snapshot)


def test_loader_resolves_pointer_without_explicit_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def resolve(base: str | Path):
        calls.append(Path(base))
        return SimpleNamespace(namespace_source="pointer", snapshot=_snapshot())

    monkeypatch.setattr(
        current_review.dashboard_readiness,
        "resolve_authoritative_dashboard",
        resolve,
    )

    packet = current_review.load_current_mapping_review("/tmp/artifacts")

    assert calls == [Path("/tmp/artifacts")]
    assert packet["authority_binding"]["namespace_source"] == (
        "current_dashboard_pointer"
    )


def test_cli_prints_review_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    packet = current_review.build_current_mapping_review(_snapshot())
    monkeypatch.setattr(
        current_review,
        "load_current_mapping_review",
        lambda artifact_base, registry=None: packet,
    )
    before = tuple(tmp_path.iterdir())

    result = current_review.main(["--artifact-base", str(tmp_path)])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["status"] == "operator_action_required"
    assert output["provider_calls"] == 0
    assert output["writes"] == 0
    assert tuple(tmp_path.iterdir()) == before


def test_cli_summary_is_bounded_and_template_mode_is_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    packet = current_review.build_current_mapping_review(_snapshot())
    monkeypatch.setattr(
        current_review,
        "load_current_mapping_review",
        lambda artifact_base, registry=None: packet,
    )
    before = tuple(tmp_path.iterdir())

    assert current_review.main(
        ["--artifact-base", str(tmp_path), "--output", "summary"]
    ) == 0
    summary = capsys.readouterr().out
    assert "report=decision_radar_defillama_mapping_review" in summary
    assert "status=operator_action_required" in summary
    assert "asset_count=2" in summary
    assert "coverage=mapped:0,not_applicable:0,unreviewed:2" in summary
    assert "mapping_eligible=false" in summary
    assert "automatic_identity_inference=false" in summary
    assert "expected_provider_activity=none" in summary
    assert "provider_calls=0" in summary
    assert "writes=0" in summary
    assert "RADAR_DEFILLAMA_MAPPING_OUTPUT=template" in summary
    assert "RADAR_DEFILLAMA_MAPPING_OUTPUT=json" in summary
    assert "operator_registry_template" not in summary

    assert current_review.main(
        ["--artifact-base", str(tmp_path), "--output", "template"]
    ) == 0
    template = json.loads(capsys.readouterr().out)
    assert template == packet["operator_registry_template"]
    assert all(row["mapping_status"] == "pending" for row in template["mappings"])
    assert tuple(tmp_path.iterdir()) == before


def test_summary_fails_closed_on_coverage_drift() -> None:
    packet = current_review.build_current_mapping_review(_snapshot())
    packet["coverage"]["coverage_counts"]["mapped"] = 1

    with pytest.raises(
        current_review.DefiLlamaCurrentMappingReviewError,
        match="coverage_count_mismatch",
    ):
        current_review.format_current_mapping_review_summary(packet)
