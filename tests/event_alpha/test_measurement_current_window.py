"""Current-window truth checks for the Event Alpha measurement dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.namespace import status as namespace_status
from crypto_rsi_scanner.event_alpha.operations import candidate_semantics, measurement


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_measurement_interpretation_uses_only_selected_current_window(tmp_path):
    fixed_now = datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc)
    selected = tmp_path / "selected"
    _write_jsonl(
        selected / "event_integrated_radar_candidates.jsonl",
        [
            {
                "candidate_id": "current-1",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "review_state": "near_miss",
                "generated_at": (fixed_now - timedelta(days=1)).isoformat(),
            },
            {
                "candidate_id": "current-2",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "review_state": "quality_capped",
                "generated_at": (fixed_now - timedelta(days=1)).isoformat(),
            },
            {
                "candidate_id": "current-3",
                "opportunity_type": "DIAGNOSTIC",
                "generated_at": (fixed_now - timedelta(days=1)).isoformat(),
            },
        ],
    )
    historical = tmp_path / "notify_llm_deep_cryptopanic_rehearsal"
    _write_jsonl(
        historical / "event_integrated_radar_candidates.jsonl",
        [
            {
                "candidate_id": f"historical-{index}",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "provider": "historical-provider",
                "generated_at": (fixed_now - timedelta(days=10)).isoformat(),
            }
            for index in range(59)
        ],
    )

    payload = measurement.build_measurement_dashboard(
        profile="live_burn_in_no_send",
        artifact_namespace="selected",
        base_dir=tmp_path,
        now=fixed_now,
    )
    current = payload["current_window_interpretation"]
    assert "first_real_run_interpretation" not in payload
    assert current["source"] == "selected_filtered_namespaces"
    assert current["included_namespace_count"] == 1
    assert current["real_burn_in_candidate_count"] == 0
    assert current["non_burn_in_candidate_count"] == 3
    assert current["near_miss_count"] == 0
    assert current["quality_capped_count"] == 0
    assert current["feedback_rows_eligible"] == 0
    assert current["outcome_rows_eligible"] == 0
    assert payload["auto_apply_thresholds"] is False

    rendered = measurement.format_measurement_dashboard(payload)
    assert "## Current Window Interpretation" in rendered
    assert "insufficient exact current-window evidence for threshold changes" in rendered
    assert "Interpretation remains inconclusive" not in rendered
    assert "notify_llm_deep_cryptopanic_rehearsal" not in rendered
    assert "real_candidates: `59`" not in rendered
    assert "historical-provider" not in json.dumps(payload, sort_keys=True)


def test_measurement_default_clock_is_captured_once_while_invalid_times_fail_closed(
    tmp_path,
    monkeypatch,
):
    fixed_now = datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc)
    namespace = tmp_path / "single-clock"
    _write_jsonl(
        namespace / "event_integrated_radar_candidates.jsonl",
        [
            {
                "candidate_id": "current-aware",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "generated_at": (fixed_now - timedelta(days=1)).isoformat(),
            },
            {
                "candidate_id": "timestamp-less",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
            },
            {
                "candidate_id": "naive-timestamp",
                "opportunity_type": "DIAGNOSTIC",
                "generated_at": "2026-07-11T04:00:00",
            },
        ],
    )
    (namespace / "event_alpha_daily_burn_in_run.json").write_text(
        json.dumps(
            {"generated_at": (fixed_now - timedelta(days=30)).isoformat()}
        )
        + "\n",
        encoding="utf-8",
    )
    (namespace / "event_alpha_source_coverage.json").write_text(
        json.dumps({"generated_at": fixed_now.isoformat()}) + "\n",
        encoding="utf-8",
    )
    (namespace / "event_provider_health.json").write_text(
        json.dumps(
            {
                "generated_at": (fixed_now + timedelta(seconds=1)).isoformat(),
                "provider": {"status": "degraded"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (namespace / "event_alpha_candidate_mode_manifest.json").write_text(
        json.dumps({"candidate_mode": True}) + "\n",
        encoding="utf-8",
    )
    clock_calls: list[datetime] = []

    def changing_utc_now() -> datetime:
        value = fixed_now + timedelta(days=100 * len(clock_calls))
        clock_calls.append(value)
        return value

    monkeypatch.setattr(measurement.common, "utc_now", changing_utc_now)

    payload = measurement.build_measurement_dashboard(
        profile="live_burn_in_no_send",
        artifact_namespace="single-clock",
        base_dir=tmp_path,
        days=30,
    )

    assert clock_calls == [fixed_now]
    assert payload["generated_at"] == fixed_now.isoformat()
    assert payload["non_burn_in_candidate_count"] == 1
    current = payload["current_window_interpretation"]
    assert current["window_end"] == payload["generated_at"]
    assert current["window_start"] == (fixed_now - timedelta(days=30)).isoformat()
    namespace_policy = json.loads(
        (namespace / "event_alpha_burn_in_namespace_policy.json").read_text(
            encoding="utf-8"
        )
    )
    assert namespace_policy["generated_at"] == payload["generated_at"]
    assert payload["live_cycles"] == 1
    assert payload["source_coverage_docs"] == 1
    assert payload["provider_degraded_backoff_rate"] == 0.0
    assert payload["candidate_mode_manifest_namespaces"] == []


def test_measurement_explicit_clock_controls_strict_inclusive_window(
    tmp_path,
    monkeypatch,
):
    fixed_now = datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc)
    namespace = tmp_path / "fixed-window"
    _write_jsonl(
        namespace / "event_integrated_radar_candidates.jsonl",
        [
            {
                "candidate_id": "inside-window",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "generated_at": (fixed_now - timedelta(days=29)).isoformat(),
            },
            {
                "candidate_id": "outside-window",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "generated_at": (fixed_now - timedelta(days=31)).isoformat(),
            },
            {
                "candidate_id": "at-cutoff",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "generated_at": (fixed_now - timedelta(days=30)).isoformat(),
            },
            {
                "candidate_id": "at-window-end",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "generated_at": fixed_now.isoformat(),
            },
            {
                "candidate_id": "timestamp-less",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
            },
            {
                "candidate_id": "naive-timestamp",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "generated_at": "2026-07-11T04:00:00",
            },
            {
                "candidate_id": "invalid-timestamp",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "generated_at": "not-a-timestamp",
            },
            {
                "candidate_id": "future-timestamp",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "generated_at": (fixed_now + timedelta(seconds=1)).isoformat(),
            },
            {
                "candidate_id": "invalid-primary-does-not-fall-through",
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "observed_at": "2026-07-11T04:00:00",
                "generated_at": fixed_now.isoformat(),
            },
        ],
    )
    _write_jsonl(
        namespace / "event_alpha_notification_deliveries.jsonl",
        [
            {
                "delivery_id": "at-cutoff",
                "attempted_at": (fixed_now - timedelta(days=30)).isoformat(),
                "state": "rendered",
            },
            {
                "delivery_id": "future",
                "attempted_at": (fixed_now + timedelta(seconds=1)).isoformat(),
                "state": "rendered",
            },
            {
                "delivery_id": "naive-primary",
                "attempted_at": "2026-07-11T04:00:00",
                "generated_at": fixed_now.isoformat(),
                "state": "rendered",
            },
        ],
    )

    def unexpected_wall_clock() -> datetime:
        raise AssertionError("explicit measurement clock must own all fallbacks")

    monkeypatch.setattr(measurement.common, "utc_now", unexpected_wall_clock)

    payload = measurement.build_measurement_dashboard(
        profile="live_burn_in_no_send",
        artifact_namespace="fixed-window",
        base_dir=tmp_path,
        days=30,
        now=fixed_now,
    )

    assert payload["generated_at"] == fixed_now.isoformat()
    assert payload["non_burn_in_candidate_count"] == 3
    assert payload["candidates_by_opportunity_type"] == {
        "UNCONFIRMED_RESEARCH": 3
    }
    assert payload["rendered_vs_skipped_counts"] == {
        "rendered": 1,
        "skipped": 0,
    }
    assert payload["current_window_interpretation"]["window_end"] == fixed_now.isoformat()
    assert payload["telegram_sends"] == 0
    assert payload["trades_created"] == 0
    assert payload["paper_trades_created"] == 0
    assert payload["auto_apply_thresholds"] is False


def test_measurement_review_cohorts_use_explicit_deduplicated_identity(
    tmp_path,
):
    fixed_now = datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc)
    namespace = tmp_path / "explicit-cohorts"
    shared = {
        "core_opportunity_id": "core-shared",
        "generated_at": fixed_now.isoformat(),
        "opportunity_type": "UNCONFIRMED_RESEARCH",
    }
    _write_jsonl(
        namespace / "event_integrated_radar_candidates.jsonl",
        [
            {
                **shared,
                "candidate_id": "candidate-shared",
                "review_state": "near_miss",
                "provider": "provider-name-says-quality-capped",
            },
            {
                "candidate_id": "prose-only-noise",
                "generated_at": fixed_now.isoformat(),
                "opportunity_type": "UNCONFIRMED_RESEARCH",
                "provider": "near_miss quality_capped",
                "source_url": "https://example.test/near-miss/quality-capped",
                "requested_state_after_quality_gate": "QUALITY_BLOCKED",
            },
        ],
    )
    _write_jsonl(
        namespace / "event_core_opportunities.jsonl",
        [
            {
                **shared,
                "row_type": "event_core_opportunity",
                "run_id": "run-explicit-cohorts",
                "profile": "live_burn_in_no_send",
                "artifact_namespace": "explicit-cohorts",
                "symbol": "EXPLICIT",
                "coin_id": "explicit",
                "opportunity_score_final": 60,
                "final_opportunity_score": 60,
                "opportunity_level": "local_only",
                "final_opportunity_level": "local_only",
                "final_route_after_quality_gate": "STORE_ONLY",
                "impact_path_type": "direct_token_event",
                "candidate_role": "candidate_asset",
                "source_class": "crypto_news",
                "evidence_specificity": "specific",
                "final_state_after_quality_gate": "QUALITY_BLOCKED",
            },
            {
                **shared,
                "row_type": "event_core_opportunity",
                "run_id": "run-explicit-cohorts",
                "profile": "live_burn_in_no_send",
                "artifact_namespace": "explicit-cohorts",
                "symbol": "EXPLICIT",
                "coin_id": "explicit",
                "opportunity_score_final": 60,
                "final_opportunity_score": 60,
                "opportunity_level": "local_only",
                "final_opportunity_level": "local_only",
                "final_route_after_quality_gate": "STORE_ONLY",
                "impact_path_type": "direct_token_event",
                "candidate_role": "candidate_asset",
                "source_class": "crypto_news",
                "evidence_specificity": "specific",
                "final_state_after_quality_gate": "QUALITY_BLOCKED",
            },
        ],
    )

    payload = measurement.build_measurement_dashboard(
        profile="live_burn_in_no_send",
        artifact_namespace="explicit-cohorts",
        base_dir=tmp_path,
        now=fixed_now,
    )

    assert payload["near_miss_count"] == 1
    assert payload["quality_capped_count"] == 1
    current = payload["current_window_interpretation"]
    assert current["near_miss_count"] == 1
    assert current["quality_capped_count"] == 1


def test_measurement_rejects_naive_explicit_clock(tmp_path):
    with pytest.raises(ValueError, match="timezone-aware"):
        measurement.build_measurement_dashboard(
            profile="live_burn_in_no_send",
            artifact_namespace="naive-clock",
            base_dir=tmp_path,
            now=datetime(2026, 7, 12, 4, 0),
        )


def test_measurement_normalizes_non_positive_window_days(tmp_path):
    fixed_now = datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc)

    payload = measurement.build_measurement_dashboard(
        profile="live_burn_in_no_send",
        artifact_namespace="normalized-window",
        base_dir=tmp_path,
        days=0,
        now=fixed_now,
    )

    assert payload["window_days"] == 1
    current = payload["current_window_interpretation"]
    assert current["window_days"] == 1
    assert current["window_end"] == fixed_now.isoformat()
    assert current["window_start"] == (fixed_now - timedelta(days=1)).isoformat()
    assert schema_v1.validate_row_against_schema(
        {**payload, "namespace_dir": "event_fade_cache/normalized-window"},
        "event_alpha_burn_in_measurement_dashboard_v1",
    ) == []


def test_measurement_provider_health_uses_nested_exact_state_timestamps(tmp_path):
    fixed_now = datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc)
    cutoff = fixed_now - timedelta(days=30)
    namespace = tmp_path / "provider-health"
    namespace.mkdir()
    (namespace / "event_provider_health.json").write_text(
        json.dumps(
            {
                "schema_version": "event_provider_health_v1",
                "providers": {
                    "healthy:cutoff": {
                        "provider": "healthy",
                        "provider_key": "healthy:cutoff",
                        "consecutive_failures": 0,
                        "last_success_at": cutoff.isoformat(),
                    },
                    "degraded:window-end": {
                        "provider": "degraded",
                        "provider_key": "degraded:window-end",
                        "consecutive_failures": 1,
                        "last_failure_at": fixed_now.isoformat(),
                    },
                    "stale:healthy": {
                        "provider": "stale",
                        "provider_key": "stale:healthy",
                        "consecutive_failures": 0,
                        "last_success_at": (
                            cutoff - timedelta(microseconds=1)
                        ).isoformat(),
                    },
                    "future:healthy": {
                        "provider": "future",
                        "provider_key": "future:healthy",
                        "consecutive_failures": 0,
                        "last_success_at": (
                            fixed_now + timedelta(microseconds=1)
                        ).isoformat(),
                    },
                    "naive:failure": {
                        "provider": "naive",
                        "provider_key": "naive:failure",
                        "consecutive_failures": 1,
                        "last_failure_at": fixed_now.replace(tzinfo=None).isoformat(),
                        # A valid secondary timestamp must not rescue the invalid
                        # current failure-state authority.
                        "last_success_at": fixed_now.isoformat(),
                    },
                    "missing:healthy": {
                        "provider": "missing",
                        "provider_key": "missing:healthy",
                        "consecutive_failures": 0,
                    },
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = measurement.build_measurement_dashboard(
        profile="live_burn_in_no_send",
        artifact_namespace="provider-health",
        base_dir=tmp_path,
        days=30,
        now=fixed_now,
    )

    assert payload["provider_degraded_backoff_rate"] == 50.0
    rows = measurement._provider_health_rows(  # noqa: SLF001 - exact store-shape regression
        tmp_path,
        cutoff=cutoff,
        namespaces=["provider-health"],
        evaluated_at=fixed_now,
    )
    assert [row["provider_key"] for row in rows] == [
        "degraded:window-end",
        "healthy:cutoff",
    ]


def test_core_cohort_keeps_runs_distinct_but_deduplicates_same_run_revisions():
    base = {
        "row_type": "event_core_opportunity",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "cohort",
        "core_opportunity_id": "core-shared",
    }
    rows = [
        {
            **base,
            "run_id": "run-one",
            "generated_at": "2026-07-12T01:00:00+00:00",
            "revision": "older",
        },
        {
            **base,
            "run_id": "run-one",
            "generated_at": "2026-07-12T02:00:00+00:00",
            "revision": "latest",
        },
        {
            **base,
            "run_id": "run-two",
            "generated_at": "2026-07-12T03:00:00+00:00",
            "revision": "different-run",
        },
        {
            **base,
            "run_id": "",
            "generated_at": "2026-07-12T04:00:00+00:00",
            "revision": "missing-authority",
        },
    ]

    selected = candidate_semantics.latest_authoritative_core_rows(rows)

    assert len(selected) == 2
    assert {row["run_id"] for row in selected} == {"run-one", "run-two"}
    assert next(row for row in selected if row["run_id"] == "run-one")["revision"] == "latest"
    assert len(
        {
            candidate_semantics.core_observation_identity(row)
            for row in selected
        }
    ) == 2


def test_core_quality_cap_requires_final_quality_authority():
    for nonfinal_field in (
        {"review_state": "quality_capped"},
        {"quality_capped": True},
        {"quality_state_block_reason": "insufficient_evidence"},
    ):
        row = {
            "row_type": "event_core_opportunity",
            "run_id": "run-quality-authority",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "cohort",
            "core_opportunity_id": "core-quality-authority",
            "generated_at": "2026-07-12T03:00:00+00:00",
            "final_state_after_quality_gate": "RADAR",
            **nonfinal_field,
        }

        assert candidate_semantics.is_authoritative_core_quality_cap(row) is False


def test_core_identity_is_exact_and_delimiter_safe():
    base = {
        "row_type": "event_core_opportunity",
        "profile": "profile",
        "artifact_namespace": "namespace",
        "core_opportunity_id": "core",
    }
    padded = {**base, "run_id": " run"}
    left_delimiter = {**base, "run_id": "run|profile"}
    right_delimiter = {
        **base,
        "run_id": "run",
        "profile": "profile|namespace",
    }

    assert candidate_semantics.core_observation_identity(padded) == ""
    assert (
        candidate_semantics.core_observation_identity(left_delimiter)
        != candidate_semantics.core_observation_identity(right_delimiter)
    )


def test_equal_clock_conflicting_core_revisions_fail_closed_independent_of_order():
    base = {
        "row_type": "event_core_opportunity",
        "run_id": "run-conflict",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "cohort",
        "core_opportunity_id": "core-conflict",
        "generated_at": "2026-07-12T03:00:00+00:00",
    }
    first = {**base, "final_state_after_quality_gate": "RADAR"}
    second = {**base, "final_state_after_quality_gate": "QUALITY_BLOCKED"}

    assert candidate_semantics.latest_authoritative_core_rows([first, second]) == []
    assert candidate_semantics.latest_authoritative_core_rows([second, first]) == []

    later = {
        **second,
        "generated_at": "2026-07-12T03:01:00+00:00",
    }
    assert candidate_semantics.latest_authoritative_core_rows(
        [first, second, later]
    ) == [later]


def test_measurement_refuses_immutable_output_before_any_write(tmp_path):
    fixed_now = datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc)
    frozen = tmp_path / "frozen-history"
    namespace_status.write_namespace_status(
        frozen,
        {
            "namespace": frozen.name,
            "status": namespace_status.STATUS_ARCHIVED,
            "safe_for_send_readiness": False,
            "safe_for_burn_in_measurement": False,
            "safe_for_calibration": False,
        },
        now=fixed_now,
    )
    evidence = frozen / "historical-evidence.json"
    evidence.write_bytes(b'{"immutable":true}\n')
    before = {
        path.relative_to(frozen).as_posix(): path.read_bytes()
        for path in frozen.rglob("*")
        if path.is_file()
    }

    with pytest.raises(ValueError, match="output namespace is immutable"):
        measurement.build_measurement_dashboard(
            profile="live_burn_in_no_send",
            artifact_namespace=frozen.name,
            base_dir=tmp_path,
            now=fixed_now,
        )

    after = {
        path.relative_to(frozen).as_posix(): path.read_bytes()
        for path in frozen.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_measurement_refuses_checksum_archived_output_before_any_write(
    tmp_path,
    monkeypatch,
):
    fixed_now = datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc)
    base = tmp_path / "event_fade_cache"
    frozen = base / "live_burn_in_20260707"
    evidence = frozen / "historical-evidence.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_bytes(b'{"immutable":true}\n')
    checksums = tmp_path / "research" / "event_alpha_burn_in_archive_checksums.json"
    checksums.parent.mkdir(parents=True)
    checksums.write_text(
        json.dumps(
            {
                "files": {
                    "live_burn_in_20260707/historical-evidence.json": "sealed"
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(measurement.common, "repo_root_from_module", lambda: tmp_path)
    before = evidence.read_bytes()

    with pytest.raises(ValueError, match="archived_checksum_snapshot"):
        measurement.build_measurement_dashboard(
            profile="live_burn_in_no_send",
            artifact_namespace=frozen.name,
            base_dir=base,
            now=fixed_now,
        )

    assert evidence.read_bytes() == before
    assert sorted(path.name for path in frozen.iterdir()) == [evidence.name]
