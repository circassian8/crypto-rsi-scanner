"""Read-once campaign adapter tests for the Decision episode scorecard."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from typing import Any, Mapping, Sequence

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    market_observation_campaign_scorecard,
)
from crypto_rsi_scanner.event_alpha.operations.market_no_send_history_cache import (
    LIVE_HISTORY_CACHE_NAMESPACE,
)
from crypto_rsi_scanner.event_alpha.operations.market_no_send_models import (
    MarketNoSendError,
)
from tests.event_alpha.test_decision_episode_scorecard import (
    _START,
    _candidate,
    _core,
    _episode,
    _outcome,
)


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(
            row,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
        for row in rows
    )


def _private_snapshot_fields(
    label: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    artifact: str,
) -> dict[str, Any]:
    raw = _jsonl_bytes(rows)
    return {
        f"_{label}_snapshot_rows": tuple(deepcopy(list(rows))),
        f"_{label}_snapshot_artifact": artifact,
        f"_{label}_snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        f"_{label}_snapshot_size_bytes": len(raw),
        f"_{label}_snapshot_row_count": len(rows),
        f"_{label}_snapshot_binding_source": f"test_exact_{label}_bytes",
        f"_{label}_snapshot_verified": True,
    }


def _generation(
    candidate: Mapping[str, Any],
    core: Mapping[str, Any],
    *,
    integrated_outcomes: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "artifact_namespace": candidate["artifact_namespace"],
        "run_id": candidate["run_id"],
        "campaign_counted": True,
        **_private_snapshot_fields(
            "candidate",
            [candidate],
            artifact="event_integrated_radar_candidates.jsonl",
        ),
        **_private_snapshot_fields(
            "core",
            [core],
            artifact="event_core_opportunities.jsonl",
        ),
        **_private_snapshot_fields(
            "integrated_outcome",
            integrated_outcomes,
            artifact="event_integrated_radar_outcomes.jsonl",
        ),
    }


def _ledger(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    raw = _jsonl_bytes(rows)
    return {
        "rows": tuple(deepcopy(list(rows))),
        "status": "observed" if rows else "observed_empty",
        "artifact": "event_decision_radar_campaign_outcomes.jsonl",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "row_count": len(rows),
        "binding_source": "campaign_outcome_ledger_exact_bytes",
    }


def _valid_case(*, suffix: str = "adapter"):
    candidate = _candidate(suffix, _START, risk=True)
    core = _core(candidate)
    evaluated = _START + timedelta(days=2)
    outcome = _outcome(
        candidate,
        core,
        persisted_evaluated_at=evaluated,
        primary_price=90.0,
    )
    episode = _episode([candidate], evaluated_at=evaluated)
    return candidate, core, outcome, episode, evaluated


def test_adapter_binds_exact_representative_without_rereads():
    candidate, core, outcome, episode, evaluated = _valid_case()
    generation = _generation(candidate, core, integrated_outcomes=[outcome])
    ledger = _ledger([outcome])

    scorecard = (
        market_observation_campaign_scorecard
        .build_campaign_decision_episode_scorecard(
            episode,
            [generation],
            ledger,
            evaluated_at=evaluated,
        )
    )

    representative = scorecard["representatives"][0]
    assert representative["artifact_namespace"] == candidate["artifact_namespace"]
    assert representative["candidate_id"] == candidate["candidate_id"]
    assert representative["outcome_identity_key"] == outcome["outcome_identity_key"]
    assert representative["outcome_state"] == "matured"
    assert representative["direction_alignment"] == "aligned"
    assert scorecard["candidate_rows_supplied"] == 1
    assert scorecard["core_rows_supplied"] == 1
    assert scorecard["outcome_rows_supplied"] == 1
    by_role = {row["source_role"]: row for row in scorecard["source_artifact_bindings"]}
    assert by_role["candidate"]["artifact_sha256"] == generation[
        "_candidate_snapshot_sha256"
    ]
    assert by_role["core"]["artifact_sha256"] == generation[
        "_core_snapshot_sha256"
    ]
    assert by_role["outcome"]["artifact_sha256"] == ledger["sha256"]
    assert by_role["outcome"]["artifact_namespace"] == LIVE_HISTORY_CACHE_NAMESPACE
    assert by_role["outcome"]["run_id"] == (
        "campaign-ledger-snapshot:" + ledger["sha256"]
    )


@pytest.mark.parametrize("case", ("duplicate", "invalid"))
def test_adapter_contract_excludes_duplicate_or_invalid_outcome(case: str):
    candidate, core, outcome, episode, evaluated = _valid_case(suffix=case)
    if case == "duplicate":
        outcomes = [outcome, deepcopy(outcome)]
    else:
        invalid = deepcopy(outcome)
        invalid["sent"] = True
        outcomes = [invalid]
    scorecard = (
        market_observation_campaign_scorecard
        .build_campaign_decision_episode_scorecard(
            episode,
            [_generation(candidate, core)],
            _ledger(outcomes),
            evaluated_at=evaluated,
        )
    )

    representative = scorecard["representatives"][0]
    assert representative["outcome_state"] == "contract_excluded"
    if case == "duplicate":
        assert "outcome_authority_ambiguous" in representative[
            "contract_exclusion_reasons"
        ]
    else:
        assert "campaign_outcome_validation_invalid" in representative[
            "contract_exclusion_reasons"
        ]
        assert scorecard["outcome_validation_bindings"][0]["valid"] is False


def test_adapter_accounts_for_unrelated_full_ledger_row_without_selection():
    candidate, core, outcome, episode, evaluated = _valid_case(suffix="selected")
    other_candidate = _candidate("outside", _START + timedelta(hours=30), risk=True)
    other_core = _core(other_candidate)
    other_outcome = _outcome(
        other_candidate,
        other_core,
        persisted_evaluated_at=evaluated + timedelta(days=2),
        primary_price=95.0,
    )

    scorecard = (
        market_observation_campaign_scorecard
        .build_campaign_decision_episode_scorecard(
            episode,
            [_generation(candidate, core)],
            _ledger([outcome, other_outcome]),
            evaluated_at=evaluated + timedelta(days=2),
        )
    )

    assert scorecard["outcome_rows_supplied"] == 2
    unrelated = next(
        row for row in scorecard["outcome_validation_bindings"]
        if row["candidate_id"] == other_candidate["candidate_id"]
    )
    assert unrelated["valid"] is False
    assert unrelated["score_cohort_status"] == "invalid"
    assert unrelated["canonical_score_cohorts"] == {
        "actionability_score_cohort": "unknown",
        "evidence_confidence_score_cohort": "unknown",
        "risk_score_cohort": "unknown",
    }
    assert scorecard["representatives"][0]["outcome_state"] == "matured"


def test_adapter_fails_closed_on_snapshot_metadata_mismatch():
    candidate, core, outcome, episode, evaluated = _valid_case(suffix="mismatch")
    generation = _generation(candidate, core)
    generation["_candidate_snapshot_row_count"] = 2

    with pytest.raises(MarketNoSendError, match="candidate snapshot metadata invalid"):
        (
            market_observation_campaign_scorecard
            .build_campaign_decision_episode_scorecard(
                episode,
                [generation],
                _ledger([outcome]),
                evaluated_at=evaluated,
            )
        )


def test_adapter_output_never_leaks_private_generation_fields():
    candidate, core, outcome, episode, evaluated = _valid_case(suffix="private")
    scorecard = (
        market_observation_campaign_scorecard
        .build_campaign_decision_episode_scorecard(
            episode,
            [_generation(candidate, core)],
            _ledger([outcome]),
            evaluated_at=evaluated,
        )
    )

    def assert_closed(value: Any) -> None:
        if isinstance(value, Mapping):
            assert not any(
                type(key) is str and key.startswith("_") for key in value
            )
            for nested in value.values():
                assert_closed(nested)
        elif isinstance(value, list):
            for nested in value:
                assert_closed(nested)

    assert_closed(scorecard)


def test_adapter_keeps_empty_episode_closed_without_synthetic_source_claims():
    evaluated = _START + timedelta(days=2)
    scorecard = (
        market_observation_campaign_scorecard
        .build_campaign_decision_episode_scorecard(
            _episode([], evaluated_at=evaluated),
            [],
            _ledger([]),
            evaluated_at=evaluated,
        )
    )

    assert scorecard["status"] == "empty"
    assert scorecard["candidate_rows_supplied"] == 0
    assert scorecard["core_rows_supplied"] == 0
    assert scorecard["outcome_rows_supplied"] == 0
    assert [
        row["source_role"] for row in scorecard["source_artifact_bindings"]
    ] == ["outcome"]
    assert scorecard["source_artifact_bindings"][0]["artifact_sha256"] == (
        hashlib.sha256(b"").hexdigest()
    )
