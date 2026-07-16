from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    empirical_replay_outcomes,
    empirical_replay_persistence,
    empirical_replay_store,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_replay_core import (
    run_replay_kernel,
)
from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
    decision_model_values,
)


_START = datetime(2024, 6, 1, tzinfo=timezone.utc)


def _observation(*, observed_at: datetime = _START) -> dict[str, object]:
    return {
        "symbol": "MOVE",
        "canonical_asset_id": "move",
        "observed_at": observed_at.isoformat(),
        "close": 12.0,
        "quote_volume": 20_000_000.0,
        "return_24h": 30.0,
        "return_72h": 35.0,
        "return_7d": 45.0,
        "relative_return_vs_btc_24h": 28.0,
        "relative_return_vs_eth_24h": 25.0,
        "volume_zscore_24h": 3.0,
        "liquidity_usd": 20_000_000.0,
        "liquidity_tier": "large",
        "market_regime": "bull",
        "point_in_time_universe_member": True,
        "point_in_time_volume_rank": 4,
        "baseline_status": "warm",
        "data_quality_mode": "historical_ohlcv",
        "market_data_source": "binance_historical_ohlcv",
        "source_mode": "historical_replay",
        "market_data_basis": "historical_ohlcv",
        "volume_anomaly_basis": "historical_ohlcv_prior_90d",
        "liquidity_basis": "historical_ohlcv_trailing_quote_volume",
        "spread_basis": "unavailable",
        "catalyst_evidence_timing": "missing",
        "calendar_evidence_timing": "missing",
        "rsi_context_timing": "temporal_direct",
        "direct_proxy_class": "temporal_direct",
        "direct_feature_count": 8,
        "proxy_feature_count": 0,
        "feature_basis": {
            "returns": "historical_ohlcv",
            "volume": "historical_ohlcv_prior_90d",
            "spread": "unavailable",
        },
        "missing_features": [
            "return_4h",
            "spread_bps",
            "derivatives",
            "calendar",
            "catalyst",
        ],
    }


def _ideas_and_outcomes() -> tuple[list[dict], dict]:
    ideas = list(
        run_replay_kernel(
            [
                _observation(),
                _observation(observed_at=_START + timedelta(hours=12)),
            ],
            mode="medium",
            artifact_namespace="persistence-test",
            allowed_partitions=("validation",),
        ).ideas
    )
    index = pd.date_range(start=_START, periods=31, freq="12h", tz="UTC")
    prices = pd.DataFrame(
        {
            "open": [100.0] * len(index),
            "high": [102.0] * len(index),
            "low": [98.0] * len(index),
            "close": [100.0] * len(index),
            "volume": [1_000.0] * len(index),
        },
        index=index,
    )
    outcomes = empirical_replay_outcomes.build_empirical_replay_outcomes(
        ideas,
        {"MOVE": prices},
        evaluated_at=_START + timedelta(days=15),
    )
    return ideas, outcomes


def test_compact_idea_preserves_closed_projection_and_point_in_time_basis() -> None:
    ideas, _outcomes = _ideas_and_outcomes()
    source = ideas[0]
    compact = empirical_replay_persistence.compact_idea_snapshot(source)

    assert compact["decision_projection"] == source["decision_projection"]
    assert decision_model_values(compact["decision_projection"]) == compact[
        "decision_projection"
    ]
    assert compact["identity"]["candidate_id"] == source["candidate_id"]
    assert compact["replay"]["observed_at"] == source["observed_at"]
    assert compact["point_in_time_context"]["point_in_time_volume_rank"] == 4.0
    assert compact["market_features"]["return_24h"] == 30.0
    assert compact["market_features"]["spread_status"] == "unavailable"
    assert compact["feature_quality"] == source["replay_feature_quality"]
    assert compact["safety"]["research_only"] is True
    assert all(
        value is False
        for key, value in compact["safety"].items()
        if key != "research_only"
    )
    assert "latest_market_snapshot" not in compact
    assert "market_state_snapshot" not in compact
    assert "radar_route" not in compact
    assert len(empirical_replay_store.canonical_json_bytes(compact)) < len(
        empirical_replay_store.canonical_json_bytes(source)
    )


def test_episode_archive_references_exact_ideas_and_preserves_progression() -> None:
    ideas, outcomes = _ideas_and_outcomes()
    archive = empirical_replay_persistence.build_replay_persistence_archives(
        ideas, outcomes
    )
    idea_rows = empirical_replay_persistence.decode_archive_rows(
        empirical_replay_persistence.IDEA_INDEX_FILENAME,
        archive.artifacts,
    )
    episode_rows = empirical_replay_persistence.decode_archive_rows(
        empirical_replay_persistence.EPISODE_INDEX_FILENAME,
        archive.artifacts,
    )

    assert len(idea_rows) == 2
    assert len(episode_rows) == 1
    episode = episode_rows[0]
    assert episode["member_count"] == 2
    assert episode["dependent_repeat_count"] == 1
    assert [row["progression_index"] for row in episode["members"]] == [0, 1]
    assert [row["is_representative"] for row in episode["members"]] == [True, False]
    digests = {row["snapshot_sha256"] for row in idea_rows}
    assert {row["idea_snapshot_sha256"] for row in episode["members"]} == digests
    assert episode["members"][0]["progression"]["radar_route"] == ideas[0][
        "radar_route"
    ]
    assert episode["representative_outcome"] == outcomes["episodes"][0][
        "representative_outcome"
    ]
    assert "representative" not in episode
    assert "member_progression" not in episode


def test_archives_are_deterministic_plaintext_bounded_and_digest_checked() -> None:
    ideas, outcomes = _ideas_and_outcomes()
    compact_sizes = [
        len(
            empirical_replay_store.canonical_json_bytes(
                empirical_replay_persistence.compact_idea_snapshot(row)
            )
        )
        for row in ideas
    ]
    target = max(compact_sizes) + 64
    first = empirical_replay_persistence.build_replay_persistence_archives(
        ideas,
        outcomes,
        shard_target_bytes=target,
    )
    second = empirical_replay_persistence.build_replay_persistence_archives(
        reversed(ideas),
        outcomes,
        shard_target_bytes=target,
    )

    assert first.artifacts == second.artifacts
    assert first.idea_index["shard_count"] == 2
    assert first.idea_index["record_count"] == 2
    assert first.episode_index["record_count"] == 1
    for descriptor in [
        *first.idea_index["shards"],
        *first.episode_index["shards"],
    ]:
        assert descriptor["size_bytes"] <= target
        assert b'"decision_projection"' in first.artifacts[descriptor["name"]] or descriptor[
            "name"
        ].startswith(empirical_replay_persistence.EPISODE_PART_PREFIX)

    mutated = dict(first.artifacts)
    part_name = first.idea_index["shards"][0]["name"]
    mutated[part_name] += b"\n"
    with pytest.raises(ValueError, match="shard digest mismatch"):
        empirical_replay_persistence.decode_archive_rows(
            empirical_replay_persistence.IDEA_INDEX_FILENAME,
            mutated,
        )


def test_episode_archive_fails_closed_on_missing_idea_reference() -> None:
    ideas, outcomes = _ideas_and_outcomes()
    compact = {
        row["candidate_id"]: empirical_replay_persistence.compact_idea_snapshot(row)
        for row in ideas[:1]
    }
    episode = deepcopy(outcomes["episodes"][0])

    with pytest.raises(ValueError, match="idea reference missing"):
        empirical_replay_persistence.compact_episode_record(episode, compact)

