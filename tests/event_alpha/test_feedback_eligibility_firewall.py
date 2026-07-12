"""Adversarial tests for the exact research-feedback calibration firewall."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone


def _feedback_row(
    *,
    core_id: str = "core:btc:listing",
    run_id: str = "run-1",
    profile: str = "fixture",
    namespace: str = "feedback_firewall",
    feedback_id: str = "feedback-1",
    label: str = "watch",
    marked_at: str = "2026-07-12T01:00:00+00:00",
    **overrides,
):
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    row = {
        "run_id": run_id,
        "profile": profile,
        "artifact_namespace": namespace,
        "core_opportunity_id": core_id,
        "feedback_id": feedback_id,
        "feedback_target_type": "core_opportunity_id",
        "feedback_target": core_id,
        "target": core_id,
        "label": label,
        "marked_at": marked_at,
        "marked_by": "human-reviewer",
        "source": "manual_cli",
        "research_only": True,
        "notes": "research annotation",
    }
    row.update(overrides)
    row.update(firewall.build_feedback_eligibility_fields(row))
    return row


def _core_row(
    *,
    core_id: str = "core:btc:listing",
    run_id: str = "run-1",
    profile: str = "fixture",
    namespace: str = "feedback_firewall",
    **overrides,
):
    row = {
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "row_type": "event_core_opportunity",
        "run_id": run_id,
        "profile": profile,
        "artifact_namespace": namespace,
        "core_opportunity_id": core_id,
        "feedback_target": core_id,
        "feedback_target_type": "core_opportunity_id",
        "generated_at": "2026-07-12T00:00:00+00:00",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "source_provider": "core-provider",
        "source_provider_domain": "core.example",
        "source_domain": "core.example",
        "source_pack": "core-pack",
        "source_class": "official_exchange",
        "lane": "listing",
        "playbook_type": "listing",
        "effective_playbook_type": "listing",
        "impact_path_type": "listing",
        "opportunity_level": "watchlist",
        "final_opportunity_level": "watchlist",
        "final_route_after_quality_gate": "WATCHLIST",
        "thesis_origin": "catalyst_led",
        "directional_bias": "long",
        "catalyst_status": "confirmed",
        "confidence_band": "exploratory",
        "timing_state": "early",
        "tradability_status": "acceptable",
        "radar_route": "diagnostic",
        "actionability_score_cohort": "70_79",
        "anomaly_type": "none",
    }
    row.update(overrides)
    return row


def test_feedback_contract_uses_exact_identity_hash_and_row_local_effective_state():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    base = {
        "run_id": "run-1",
        "profile": "fixture",
        "artifact_namespace": "feedback_firewall",
        "core_opportunity_id": "core:btc:listing",
        "feedback_id": "feedback-1",
        "feedback_target_type": "core_opportunity_id",
        "feedback_target": "core:btc:listing",
        "target": "core:btc:listing",
        "label": "useful",
        "marked_at": "2026-07-12T01:00:00+00:00",
        "marked_by": "reviewer",
        "source": "manual_cli",
        "research_only": True,
    }
    before = copy.deepcopy(base)
    fields = firewall.build_feedback_eligibility_fields(base)
    row = {**base, **fields}

    expected_identity = {
        "run_id": "run-1",
        "profile": "fixture",
        "artifact_namespace": "feedback_firewall",
        "core_opportunity_id": "core:btc:listing",
    }
    expected_payload = json.dumps(
        expected_identity,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert base == before
    assert fields["feedback_identity"] == expected_identity
    assert fields["feedback_identity_key"] == hashlib.sha256(
        expected_payload.encode("utf-8")
    ).hexdigest()
    assert fields["calibration_eligible"] is True
    assert fields["calibration_ineligible_reasons"] == []
    assert firewall.effective_feedback_state(row) == (True, ())
    assert firewall.validate_contract(row) == []

    legacy = dict(base)
    eligible, reasons = firewall.effective_feedback_state(legacy)
    assert eligible is False
    assert "legacy_feedback_contract" in reasons
    assert firewall.validate_contract(legacy) == []

    partial = dict(row)
    partial.pop("feedback_identity_key")
    eligible, reasons = firewall.effective_feedback_state(partial)
    assert eligible is False
    assert "partial_feedback_contract" in reasons
    assert "feedback_identity_key_mismatch" in reasons


def test_feedback_contract_rejects_loose_targets_unsafe_source_and_bad_values():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    bad_overrides = (
        ({"target": "BTC"}, "feedback_target_mismatch"),
        ({"feedback_target": "bitcoin"}, "feedback_target_mismatch"),
        ({"feedback_target_type": "symbol"}, "invalid_feedback_target_type"),
        ({"source": "manual_cli_unmatched"}, "invalid_feedback_source"),
        ({"label": "great"}, "invalid_feedback_label"),
        ({"marked_by": ""}, "missing_marked_by"),
        ({"feedback_id": " feedback-1"}, "missing_feedback_id"),
        ({"research_only": 1}, "non_research_feedback"),
    )
    for overrides, expected_reason in bad_overrides:
        row = _feedback_row(**overrides)
        eligible, reasons = firewall.effective_feedback_state(row)
        assert eligible is False
        assert expected_reason in reasons

    for value in (
        "NaN",
        "inf",
        "-inf",
        float("nan"),
        float("inf"),
        "2026-07-12T01:00:00",
        "999999999999-01-01T00:00:00+00:00",
        " 2026-07-12T01:00:00+00:00",
    ):
        row = _feedback_row(marked_at=value)
        eligible, reasons = firewall.effective_feedback_state(row)
        assert eligible is False
        assert "invalid_feedback_marked_at" in reasons

    tampered = _feedback_row()
    tampered["feedback_identity_key"] = "0" * 64
    eligible, reasons = firewall.effective_feedback_state(tampered)
    assert eligible is False
    assert "feedback_identity_key_mismatch" in reasons


def test_joined_projection_uses_only_exact_core_attribution_and_has_no_side_effects():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    feedback = _feedback_row(
        source_provider="poison-provider",
        source_pack="poison-pack",
        lane="poison-lane",
        playbook_type="poison-playbook",
        thesis_origin="poison-origin",
        primary_horizon_return=999.0,
        direction_hit=True,
    )
    core = _core_row(primary_horizon_return=-999.0, feedback_label="poison-label")
    feedback_before = copy.deepcopy(feedback)
    core_before = copy.deepcopy(core)

    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [feedback],
        [core],
    )

    assert feedback == feedback_before
    assert core == core_before
    assert excluded == ()
    assert counts == {}
    assert len(eligible) == 1
    projection = eligible[0]
    assert projection["feedback_label"] == "watch"
    assert projection["source_provider"] == "core-provider"
    assert projection["source_pack"] == "core-pack"
    assert projection["lane"] == "listing"
    assert projection["playbook_type"] == "listing"
    assert projection["thesis_origin"] == "catalyst_led"
    assert projection["core_attribution"]["source_provider"] == "core-provider"
    assert "primary_horizon_return" not in projection
    assert "direction_hit" not in projection
    assert "feedback_label" not in projection["core_attribution"]

    projection["core_attribution"]["source_provider"] = "changed"
    assert core["source_provider"] == "core-provider"


def test_latest_feedback_is_order_invariant_and_older_rows_are_superseded():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    older = _feedback_row(
        feedback_id="feedback-old",
        label="watch",
        marked_at="2026-07-12T01:00:00+00:00",
    )
    latest = _feedback_row(
        feedback_id="feedback-latest",
        label="useful",
        marked_at="2026-07-12T02:00:00+00:00",
    )
    core = _core_row()

    forward = firewall.partition_joined_calibration_feedback([older, latest], [core])
    reverse = firewall.partition_joined_calibration_feedback([latest, older], [core])

    assert forward == reverse
    eligible, excluded, counts = forward
    assert [row["feedback_id"] for row in eligible] == ["feedback-latest"]
    assert eligible[0]["feedback_label"] == "useful"
    assert len(excluded) == 1
    assert excluded[0]["feedback_id"] == "feedback-old"
    assert excluded[0]["calibration_ineligible_reasons"] == ["superseded_feedback"]
    assert counts == {"superseded_feedback": 1}


def test_same_timestamp_conflicts_and_duplicate_rows_fail_closed():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    first = _feedback_row(feedback_id="feedback-a", label="useful")
    conflicting = _feedback_row(feedback_id="feedback-b", label="junk")
    core = _core_row()

    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [conflicting, first],
        [core],
    )
    assert eligible == ()
    assert len(excluded) == 2
    assert all(
        "ambiguous_feedback_timestamp" in row["calibration_ineligible_reasons"]
        for row in excluded
    )
    assert all(
        "ambiguous_feedback_history" in row["calibration_ineligible_reasons"]
        for row in excluded
    )
    assert counts["ambiguous_feedback_timestamp"] == 2

    same_label = _feedback_row(feedback_id="feedback-c", label="watch")
    other_id = _feedback_row(feedback_id="feedback-d", label="watch")
    eligible, excluded, _counts = firewall.partition_joined_calibration_feedback(
        [same_label, other_id],
        [core],
    )
    assert eligible == ()
    assert all(
        "ambiguous_feedback_timestamp" in row["calibration_ineligible_reasons"]
        for row in excluded
    )

    same_id = _feedback_row(feedback_id="feedback-e", label="watch")
    other_label = _feedback_row(feedback_id="feedback-e", label="junk")
    eligible, excluded, _counts = firewall.partition_joined_calibration_feedback(
        [same_id, other_label],
        [core],
    )
    assert eligible == ()
    assert all(
        "ambiguous_feedback_timestamp" in row["calibration_ineligible_reasons"]
        for row in excluded
    )
    assert all(
        "duplicate_feedback_id" in row["calibration_ineligible_reasons"]
        for row in excluded
    )

    duplicate = _feedback_row()
    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [duplicate, copy.deepcopy(duplicate)],
        [core],
    )
    assert eligible == ()
    assert len(excluded) == 2
    assert counts["duplicate_feedback_row"] == 2
    assert counts["duplicate_feedback_id"] == 2
    assert counts["ambiguous_feedback_history"] == 2


def test_duplicate_feedback_ids_across_identities_block_both_histories():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    btc = _feedback_row(feedback_id="reused-feedback-id")
    eth = _feedback_row(
        core_id="core:eth:unlock",
        feedback_id="reused-feedback-id",
    )
    cores = [_core_row(), _core_row(core_id="core:eth:unlock", symbol="ETH", coin_id="ethereum")]

    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [eth, btc],
        list(reversed(cores)),
    )
    assert eligible == ()
    assert len(excluded) == 2
    assert counts["duplicate_feedback_id"] == 2
    assert counts["ambiguous_feedback_history"] == 2


def test_core_authority_must_be_one_exact_run_profile_namespace_identity():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    feedback = _feedback_row()
    for mismatched_core in (
        _core_row(run_id="run-2"),
        _core_row(profile="other-profile"),
        _core_row(namespace="other-namespace"),
    ):
        eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
            [feedback],
            [mismatched_core],
        )
        assert eligible == ()
        assert "core_authority_identity_mismatch" in excluded[0][
            "calibration_ineligible_reasons"
        ]
        assert counts["core_authority_identity_mismatch"] == 1

    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [feedback],
        [],
    )
    assert eligible == ()
    assert counts["missing_core_authority"] == 1

    core = _core_row()
    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [feedback],
        [core, copy.deepcopy(core)],
    )
    assert eligible == ()
    assert counts["duplicate_core_authority"] == 1


def test_invalid_timestamp_in_one_exact_history_blocks_order_fallback():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    valid = _feedback_row(feedback_id="valid-feedback")
    unorderable = _feedback_row(
        feedback_id="unorderable-feedback",
        marked_at="NaN",
        label="useful",
    )
    core = _core_row()

    forward = firewall.partition_joined_calibration_feedback([valid, unorderable], [core])
    reverse = firewall.partition_joined_calibration_feedback([unorderable, valid], [core])
    assert forward == reverse
    eligible, excluded, counts = forward
    assert eligible == ()
    assert len(excluded) == 2
    assert counts["ambiguous_feedback_history"] == 2
    invalid = next(row for row in excluded if row["feedback_id"] == "unorderable-feedback")
    assert "invalid_feedback_marked_at" in invalid["calibration_ineligible_reasons"]


def test_core_authority_uses_canonical_store_schema_and_rejects_forged_attribution():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    now = datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc)
    core = _core_row()
    assert firewall.core_authority_ineligibility_reasons(core, now=now) == ()

    forged = {
        "run_id": "run-1",
        "profile": "fixture",
        "artifact_namespace": "feedback_firewall",
        "core_opportunity_id": "core:btc:listing",
        "feedback_target": "core:btc:listing",
        "feedback_target_type": "core_opportunity_id",
        "source_provider": "attacker",
        "source_pack": "poison",
    }
    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [_feedback_row()],
        [forged],
        now=now,
    )
    assert eligible == ()
    assert len(excluded) == 1
    assert counts["invalid_core_authority_contract"] == 1

    poisoned = _core_row(source_provider={"provider": "attacker"})
    reasons = firewall.core_authority_ineligibility_reasons(poisoned, now=now)
    assert "invalid_core_authority_attribution" in reasons

    unsafe = _core_row(sent=True)
    reasons = firewall.core_authority_ineligibility_reasons(unsafe, now=now)
    assert "core_authority_safety_contract_invalid" in reasons


def test_future_feedback_contaminates_exact_history_using_one_external_clock():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    now = datetime(2026, 7, 12, 3, 0, tzinfo=timezone.utc)
    current = _feedback_row(
        feedback_id="feedback-current",
        label="useful",
        marked_at="2026-07-12T02:00:00+00:00",
    )
    future = _feedback_row(
        feedback_id="feedback-future",
        label="junk",
        marked_at="2999-01-01T00:00:00+00:00",
    )
    core = _core_row()

    forward = firewall.partition_joined_calibration_feedback(
        [current, future], [core], now=now
    )
    reverse = firewall.partition_joined_calibration_feedback(
        [future, current], [core], now=now
    )
    assert forward == reverse
    eligible, excluded, counts = forward
    assert eligible == ()
    assert len(excluded) == 2
    assert counts["ambiguous_feedback_history"] == 2
    future_row = next(row for row in excluded if row["feedback_id"] == "feedback-future")
    assert "feedback_marked_in_future" in future_row["calibration_ineligible_reasons"]

    try:
        firewall.partition_joined_calibration_feedback(
            [current], [core], now=datetime(2026, 7, 12, 3, 0)
        )
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:  # pragma: no cover - explicit fail-closed assertion for standalone runner.
        raise AssertionError("naive external clock must fail closed")


def test_feedback_safety_contract_and_notes_are_closed_before_projection():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    unsafe_values = (
        {"trade_created": True},
        {"paper_trade_created": True},
        {"normal_rsi_signal_written": True},
        {"triggered_fade_created": True},
        {"sent": True},
        {"decision_source_secret_safety_failed": True},
        {"safety_failure_count": 1},
        {"telegram_sends": 1},
    )
    for overrides in unsafe_values:
        row = _feedback_row(**overrides)
        eligible, reasons = firewall.effective_feedback_state(row)
        assert eligible is False
        assert "feedback_safety_contract_invalid" in reasons

    for notes in (
        {"api_key": "SECRET"},
        ["not", "text"],
        "x" * 4_097,
        "unsafe\u202etext",
        "api_key=actual-secret-value",
        "Authorization: Bearer abcdefghijklmnop",
        "copied token=xoxb_1234567890abcdefghijkl",
        "provider key sk-proj-abcdefghijklmnop",
        "Telegram 123456789:abcdefghijklmnopqrstuvwxyz",
    ):
        row = _feedback_row(notes=notes)
        eligible, reasons = firewall.effective_feedback_state(row)
        assert eligible is False
        assert "invalid_feedback_notes" in reasons

    safe = _feedback_row(
        notes="human research note; api_key=<redacted>; token=missing",
        trade_created=False,
        triggered_fade_created=0,
        telegram_sends=0,
    )
    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [safe],
        [_core_row()],
        now=datetime(2026, 7, 12, 3, 0, tzinfo=timezone.utc),
    )
    assert excluded == ()
    assert counts == {}
    assert eligible[0]["feedback_notes"] == (
        "human research note; api_key=<redacted>; token=missing"
    )


def test_malformed_overlapping_core_authority_contaminates_exact_join_only():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    now = datetime(2026, 7, 12, 3, 0, tzinfo=timezone.utc)
    feedback = _feedback_row()
    exact = _core_row()
    malformed_overlap = _core_row(run_id="")

    forward = firewall.partition_joined_calibration_feedback(
        [feedback], [exact, malformed_overlap], now=now
    )
    reverse = firewall.partition_joined_calibration_feedback(
        [feedback], [malformed_overlap, exact], now=now
    )
    assert forward == reverse
    eligible, excluded, counts = forward
    assert eligible == ()
    assert len(excluded) == 1
    assert counts["ambiguous_core_authority"] == 1
    assert counts["invalid_core_authority_contract"] == 1

    other_run = _core_row(run_id="run-2")
    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [feedback], [exact, other_run], now=now
    )
    assert len(eligible) == 1
    assert excluded == ()
    assert counts == {}


def test_feedback_before_core_generation_contaminates_exact_history():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    now = datetime(2026, 7, 12, 5, 0, tzinfo=timezone.utc)
    impossible = _feedback_row(
        feedback_id="feedback-before-core",
        marked_at="2026-07-12T01:00:00+00:00",
    )
    valid_later = _feedback_row(
        feedback_id="feedback-after-core",
        marked_at="2026-07-12T03:00:00+00:00",
        label="useful",
    )
    core = _core_row(generated_at="2026-07-12T02:00:00+00:00")

    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [valid_later, impossible], [core], now=now
    )
    assert eligible == ()
    assert len(excluded) == 2
    assert counts["ambiguous_feedback_history"] == 2
    impossible_row = next(
        row for row in excluded if row["feedback_id"] == "feedback-before-core"
    )
    assert "feedback_before_core_generation" in impossible_row[
        "calibration_ineligible_reasons"
    ]

    future_core = _core_row(generated_at="2026-07-13T00:00:00+00:00")
    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [_feedback_row()], [future_core], now=now
    )
    assert eligible == ()
    assert counts["core_authority_generated_in_future"] == 1


def test_feedback_and_core_identity_require_nfc_without_invisible_controls():
    import crypto_rsi_scanner.event_alpha.outcomes.feedback_eligibility as firewall

    now = datetime(2026, 7, 12, 3, 0, tzinfo=timezone.utc)
    nfc_run = "run-\u00e9"
    nfd_run = "run-e\u0301"
    valid = _feedback_row(run_id=nfc_run)
    valid_core = _core_row(run_id=nfc_run)
    eligible, excluded, _counts = firewall.partition_joined_calibration_feedback(
        [valid], [valid_core], now=now
    )
    assert len(eligible) == 1
    assert excluded == ()

    for invalid_run in (nfd_run, "run-\u202e1", " run-1"):
        row = _feedback_row(run_id=invalid_run)
        eligible, reasons = firewall.effective_feedback_state(row)
        assert eligible is False
        assert "missing_exact_feedback_identity" in reasons

    malformed_alias = _core_row(run_id=nfd_run)
    eligible, excluded, counts = firewall.partition_joined_calibration_feedback(
        [valid], [valid_core, malformed_alias], now=now
    )
    assert eligible == ()
    assert counts["ambiguous_core_authority"] == 1
