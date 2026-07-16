"""Offline orchestration for immutable Decision Radar empirical replay runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts.json_lines import loads_no_duplicate_keys
from . import (
    empirical_policy_lab,
    empirical_replay_analysis,
    empirical_replay_controls,
    empirical_replay_core,
    empirical_replay_data,
    empirical_replay_outcomes,
    empirical_replay_persistence,
    empirical_replay_store,
    empirical_review,
    empirical_validation_protocol,
)


RUN_SCHEMA_ID = "decision_radar.empirical_replay_execution"
RUN_SCHEMA_VERSION = 1
CHUNK_SIZE = 2_048
TRACE_EXAMPLE_LIMIT = 256
_SELECTION_PARTITIONS = ("development", "validation")
_SAFETY = {
    "research_only": True,
    "auto_apply": False,
    "provider_calls": 0,
    "authorization_mutations": 0,
    "telegram_sends": 0,
    "trades": 0,
    "orders": 0,
    "event_alpha_paper_trades": 0,
    "normal_rsi_writes": 0,
    "event_alpha_triggered_fade": 0,
    "dashboard_authority_mutations": 0,
}


@dataclass(frozen=True)
class EmpiricalReplayExecution:
    mode: str
    run_dir: Path
    run_fingerprint: str
    manifest: dict[str, Any]
    resumed: bool
    summary: dict[str, Any]


@dataclass(frozen=True)
class _PreparedReplay:
    run_mode: str
    protocol: dict[str, Any]
    dataset: empirical_replay_data.ReplayDataset
    partitions: tuple[str, ...]
    core_mode: str
    partition_ranges: dict[str, tuple[str, str]] | None
    bootstrap_resamples: int
    catalog: dict[str, Any]
    evaluated_at: str
    code_sha256: str
    configuration: dict[str, Any]
    fingerprint: str
    output: Path
    seal: dict[str, Any] | None
    load_seconds: float


@dataclass(frozen=True)
class _ReplayProducts:
    ideas: list[dict[str, Any]]
    trace_summary: dict[str, Any]
    trace_examples: list[dict[str, Any]]
    outcomes: dict[str, Any]
    analyses: dict[str, dict[str, Any]]
    controls: dict[str, Any]
    review_queue: dict[str, Any]
    policy_artifacts: dict[str, Any]
    stage_times: dict[str, float]


def execute_empirical_replay(
    *,
    mode: str,
    input_dir: str | Path,
    output_root: str | Path,
    recommendation_seal_path: str | Path | None = None,
) -> EmpiricalReplayExecution:
    """Run or resume one offline, research-only replay configuration."""

    prepared = _prepare_replay(
        mode=mode,
        input_dir=input_dir,
        output_root=output_root,
        recommendation_seal_path=recommendation_seal_path,
    )
    resumed = _resume_existing(prepared)
    if resumed is not None:
        return resumed
    products = _produce_replay(prepared)
    return _store_replay(prepared, products)


def _prepare_replay(
    *,
    mode: str,
    input_dir: str | Path,
    output_root: str | Path,
    recommendation_seal_path: str | Path | None,
) -> _PreparedReplay:
    run_mode = _normalize_mode(mode)
    protocol = empirical_validation_protocol.protocol_values()
    errors = empirical_validation_protocol.validate_protocol(protocol)
    if errors:
        raise ValueError("empirical protocol invalid:" + ";".join(errors))
    seal = _load_recommendation_seal(recommendation_seal_path) if run_mode == "final_test" else None
    if run_mode != "final_test" and recommendation_seal_path is not None:
        raise ValueError("recommendation seal is accepted only for final_test")

    stage_started = time.perf_counter()
    if run_mode == "fixture_smoke":
        dataset = empirical_replay_data.load_fixture_dataset(input_dir, mode="smoke")
        partitions = ("fixture",)
        core_mode = "fixture"
        partition_ranges = None
        bootstrap_resamples = int(protocol["statistics"]["bootstrap_resamples_smoke"])
    else:
        data_mode = "medium" if run_mode == "medium" else "full"
        dataset = empirical_replay_data.load_binance_cache_dataset(input_dir, mode=data_mode)
        partitions = ("final_test",) if run_mode == "final_test" else _SELECTION_PARTITIONS
        core_mode = "final_test" if run_mode == "final_test" else run_mode
        partition_ranges = None if run_mode == "final_test" else _partition_ranges(protocol, partitions)
        bootstrap_resamples = int(
            protocol["statistics"][
                "bootstrap_resamples_medium" if run_mode == "medium" else "bootstrap_resamples_full"
            ]
        )
    catalog = empirical_replay_data.build_replay_catalog(dataset)
    load_seconds = time.perf_counter() - stage_started

    evaluated_at = _evaluated_at(dataset, protocol, run_mode)
    code_sha256 = empirical_replay_store.code_fingerprint(_code_paths())
    if seal is not None:
        binding = seal["selection_run_binding"]
        if str(catalog["catalog_digest"]) != binding["input_sha256"]:
            raise ValueError("final_test input differs from sealed selection run")
        if code_sha256 != binding["code_sha256"]:
            raise ValueError("final_test code differs from sealed selection run")
    configuration = {
        "schema_id": RUN_SCHEMA_ID,
        "schema_version": RUN_SCHEMA_VERSION,
        "mode": run_mode,
        "data_mode": dataset.mode.name,
        "source_kind": dataset.source_kind,
        "partitions": list(partitions),
        "universe_top_n": dataset.mode.universe_top_n,
        "evaluated_at": evaluated_at,
        "chunk_size": CHUNK_SIZE,
        "trace_example_limit": TRACE_EXAMPLE_LIMIT,
        "bootstrap_resamples": bootstrap_resamples,
        "persistence_schema_version": empirical_replay_persistence.PERSISTENCE_SCHEMA_VERSION,
        "artifact_shard_target_bytes": empirical_replay_persistence.DEFAULT_SHARD_TARGET_BYTES,
        "recommendation_seal_sha256": seal.get("seal_sha256") if seal else None,
        "research_only": True,
        "auto_apply": False,
    }
    fingerprint = empirical_replay_store.run_fingerprint(
        protocol_sha256=empirical_validation_protocol.protocol_sha256(protocol),
        input_sha256=str(catalog["catalog_digest"]),
        code_sha256=code_sha256,
        configuration=configuration,
    )
    output = Path(output_root).expanduser()
    if output.is_symlink():
        raise RuntimeError("empirical_replay_output_root_unsafe")
    return _PreparedReplay(
        run_mode=run_mode,
        protocol=protocol,
        dataset=dataset,
        partitions=partitions,
        core_mode=core_mode,
        partition_ranges=partition_ranges,
        bootstrap_resamples=bootstrap_resamples,
        catalog=catalog,
        evaluated_at=evaluated_at,
        code_sha256=code_sha256,
        configuration=configuration,
        fingerprint=fingerprint,
        output=output,
        seal=seal,
        load_seconds=load_seconds,
    )


def _resume_existing(prepared: _PreparedReplay) -> EmpiricalReplayExecution | None:
    existing = prepared.output / "runs" / prepared.fingerprint
    if existing.exists() or existing.is_symlink():
        manifest = empirical_replay_store.load_manifest(existing)
        return EmpiricalReplayExecution(
            prepared.run_mode,
            existing,
            prepared.fingerprint,
            manifest,
            True,
            _resume_summary(manifest),
        )
    return None


def _produce_replay(prepared: _PreparedReplay) -> _ReplayProducts:
    observations = empirical_replay_data.iter_point_in_time_observations(
        prepared.dataset,
        partitions=prepared.partition_ranges,
    )
    if prepared.run_mode == "final_test":
        observations = (
            row
            for row in observations
            if empirical_replay_core.partition_for_timestamp(
                row["observed_at"], prepared.protocol
            )
            == "final_test"
        )
    kernel_started = time.perf_counter()
    ideas, trace_summary, trace_examples, control_observations, control_traces = (
        _run_kernel_chunked(
        observations,
        mode=prepared.core_mode,
        artifact_namespace=f"empirical_replay_{prepared.fingerprint[:20]}",
        allowed_partitions=prepared.partitions,
        protocol=prepared.protocol,
        )
    )
    kernel_seconds = time.perf_counter() - kernel_started

    outcome_started = time.perf_counter()
    outcome_symbols = {str(row.get("symbol") or "").upper() for row in ideas}
    outcome_symbols.update(
        str(row.get("symbol") or "").upper() for row in control_observations
    )
    outcome_symbols.update({"BTCUSDT", "ETHUSDT"})
    price_frames = prepared.dataset.price_frames(outcome_symbols)
    outcomes = empirical_replay_outcomes.build_empirical_replay_outcomes(
        ideas,
        price_frames,
        evaluated_at=prepared.evaluated_at,
    )
    outcome_seconds = time.perf_counter() - outcome_started

    analysis_started = time.perf_counter()
    selected_days_by_partition = _selected_observation_days_by_partition(
        control_observations,
        partitions=prepared.partitions,
    )
    _bind_selected_observation_day_summary(
        trace_summary,
        selected_days_by_partition,
    )
    analyses = {
        partition: empirical_replay_analysis.build_empirical_replay_analysis_from_episodes(
            {"episodes": _episodes_for_partition(outcomes, partition)},
            partition=partition,
            evidence_mode="fixture_mechanics_only" if partition == "fixture" else "historical_replay",
            bootstrap_resamples=prepared.bootstrap_resamples,
            selected_observation_days=selected_days_by_partition[partition],
        )
        for partition in prepared.partitions
    }
    episode_ideas, representative_outcomes = _episode_policy_rows(ideas, outcomes)
    policy_artifacts = _build_policy_artifacts(
        prepared,
        episode_ideas,
        representative_outcomes,
        selected_days_by_partition=selected_days_by_partition,
    )
    analysis_seconds = time.perf_counter() - analysis_started

    controls_started = time.perf_counter()
    controls = empirical_replay_controls.build_empirical_replay_controls(
        control_observations,
        control_traces,
        ideas,
        price_frames,
        evaluated_at=prepared.evaluated_at,
        evidence_mode=(
            "fixture_mechanics_only"
            if prepared.run_mode == "fixture_smoke"
            else "historical_replay"
        ),
    )
    controls_seconds = time.perf_counter() - controls_started

    review_started = time.perf_counter()
    review_queue = empirical_review.build_targeted_review_queue(
        ideas,
        outcomes,
        analyses,
        controls,
        run_fingerprint=prepared.fingerprint,
    )
    review_seconds = time.perf_counter() - review_started
    return _ReplayProducts(
        ideas=ideas,
        trace_summary=trace_summary,
        trace_examples=trace_examples,
        outcomes=outcomes,
        analyses=analyses,
        controls=controls,
        review_queue=review_queue,
        policy_artifacts=policy_artifacts,
        stage_times={
        "input_load_and_catalog": round(prepared.load_seconds, 6),
        "decision_replay": round(kernel_seconds, 6),
        "episode_outcomes": round(outcome_seconds, 6),
        "analysis_and_policy": round(analysis_seconds, 6),
        "controls_benchmarks_and_missed_moves": round(controls_seconds, 6),
        "targeted_review_selection": round(review_seconds, 6),
        },
    )


def _build_policy_artifacts(
    prepared: _PreparedReplay,
    episode_ideas: list[dict[str, Any]],
    representative_outcomes: list[dict[str, Any]],
    *,
    selected_days_by_partition: Mapping[str, set[str]],
) -> dict[str, Any]:
    if prepared.run_mode in {"medium", "full"}:
        simulation = empirical_policy_lab.simulate_shadow_policies(
            episode_ideas,
            representative_outcomes,
            partitions=_SELECTION_PARTITIONS,
            protocol=prepared.protocol,
            selected_observation_days_by_partition=(
                selected_days_by_partition
            ),
        )
        return {
            "shadow_policy_simulation.json": simulation,
            "recommendation_seal.json": empirical_policy_lab.freeze_recommendation_set(
                simulation,
                selection_run_binding={
                    "selection_run_fingerprint": prepared.fingerprint,
                    "input_sha256": str(prepared.catalog["catalog_digest"]),
                    "code_sha256": prepared.code_sha256,
                    "configuration_sha256": hashlib.sha256(
                        empirical_replay_store.canonical_json_bytes(
                            prepared.configuration
                        )
                    ).hexdigest(),
                    "mode": prepared.run_mode,
                    "simulation_artifact": "shadow_policy_simulation.json",
                },
            ),
            "walk_forward.json": empirical_policy_lab.walk_forward_evaluation(
                episode_ideas,
                representative_outcomes,
                protocol=prepared.protocol,
                selected_observation_days_by_partition=(
                    selected_days_by_partition
                ),
            ),
        }
    if prepared.run_mode == "final_test":
        assert prepared.seal is not None
        return {
            "recommendation_seal.json": prepared.seal,
            "final_test_confirmation.json": empirical_policy_lab.evaluate_sealed_final_test(
                episode_ideas,
                representative_outcomes,
                seal=prepared.seal,
                protocol=prepared.protocol,
                selected_observation_days_by_partition=(
                    selected_days_by_partition
                ),
            ),
        }
    return {}


def _store_replay(
    prepared: _PreparedReplay,
    products: _ReplayProducts,
) -> EmpiricalReplayExecution:
    persistence_started = time.perf_counter()
    persistence = empirical_replay_persistence.build_replay_persistence_archives(
        products.ideas,
        products.outcomes,
    )
    persistence_seconds = time.perf_counter() - persistence_started
    stage_times = {
        **products.stage_times,
        "archive_projection_and_sharding": round(persistence_seconds, 6),
    }
    runtime = {
        "schema_id": "decision_radar.empirical_replay_runtime",
        "schema_version": 1,
        "stage_seconds": stage_times,
        "total_seconds": round(sum(stage_times.values()), 6),
        "bottleneck_stage": max(stage_times, key=stage_times.get),
        "observation_count": products.trace_summary["observation_count"],
        "idea_count": len(products.ideas),
        "episode_count": products.outcomes["episode_count"],
        "candidate_pool_symbol_count": prepared.catalog["selected_symbol_count"],
        "point_in_time_universe_top_n": prepared.configuration["universe_top_n"],
        "selected_symbol_count": prepared.catalog["selected_symbol_count"],
        "selected_symbol_count_semantics": (
            "legacy_alias_candidate_pool_symbol_count"
        ),
        "row_count": prepared.catalog["row_count"],
        "persistence": dict(persistence.metrics),
        "resumed": False,
        "research_only": True,
    }
    execution_summary = _execution_summary(
        run_mode=prepared.run_mode,
        fingerprint=prepared.fingerprint,
        catalog=prepared.catalog,
        configuration=prepared.configuration,
        trace_summary=products.trace_summary,
        outcomes=products.outcomes,
        analyses=products.analyses,
        controls=products.controls,
        runtime=runtime,
    )
    artifacts: dict[str, bytes] = {
        "input_catalog.json": empirical_replay_store.canonical_json_bytes(prepared.catalog),
        "replay_trace_summary.json": empirical_replay_store.canonical_json_bytes(products.trace_summary),
        "replay_trace_examples.jsonl": _jsonl_bytes(products.trace_examples),
        "replay_controls.json": empirical_replay_store.canonical_json_bytes(products.controls),
        "targeted_review_queue.json": empirical_replay_store.canonical_json_bytes(
            products.review_queue
        ),
        "replay_analysis.json": empirical_replay_store.canonical_json_bytes({
            "schema_id": "decision_radar.empirical_partition_analyses",
            "schema_version": 1,
            "partitions": products.analyses,
            "research_only": True,
            "auto_apply": False,
        }),
        "runtime_report.json": empirical_replay_store.canonical_json_bytes(runtime),
        "execution_summary.json": empirical_replay_store.canonical_json_bytes(execution_summary),
        "execution_summary.md": _summary_markdown(execution_summary).encode("utf-8"),
    }
    artifacts.update(persistence.artifacts)
    artifacts.update({
        name: empirical_replay_store.canonical_json_bytes(value)
        for name, value in products.policy_artifacts.items()
    })
    stored = empirical_replay_store.write_immutable_run(
        prepared.output,
        protocol_version=prepared.protocol["protocol_version"],
        protocol_sha256=empirical_validation_protocol.protocol_sha256(prepared.protocol),
        input_sha256=str(prepared.catalog["catalog_digest"]),
        code_sha256=prepared.code_sha256,
        configuration=prepared.configuration,
        artifacts=artifacts,
        metrics={
            "observation_count": products.trace_summary["observation_count"],
            "idea_count": len(products.ideas),
            "episode_count": products.outcomes["episode_count"],
            "matched_control_count": products.controls["matched_non_signal_controls"]["selected_control_count"],
            "missed_opportunity_count": products.controls["missed_move_evaluation"]["missed_opportunity_count"],
            "targeted_review_item_count": products.review_queue["item_count"],
            "matured_episode_count": sum(
                row["matured_episode_count"] for row in products.analyses.values()
            ),
            "runtime_seconds": runtime["total_seconds"],
            "bottleneck_stage": runtime["bottleneck_stage"],
            **persistence.metrics,
        },
        safety=_SAFETY,
    )
    return EmpiricalReplayExecution(
        prepared.run_mode,
        stored.run_dir,
        stored.run_fingerprint,
        stored.manifest,
        stored.resumed,
        execution_summary,
    )


def _run_kernel_chunked(
    observations: Iterable[Mapping[str, Any]],
    *,
    mode: str,
    artifact_namespace: str,
    allowed_partitions: tuple[str, ...],
    protocol: Mapping[str, Any],
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    iterator = iter(observations)
    ideas: list[dict[str, Any]] = []
    control_observations: list[dict[str, Any]] = []
    control_traces: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    route_counts: Counter[str] = Counter()
    partition_counts: Counter[str] = Counter()
    selected_observation_days: set[str] = set()
    idea_observation_days: set[str] = set()
    selected_observation_start_at: str | None = None
    selected_observation_end_at: str | None = None
    observation_count = 0
    operator_visible = 0
    example_by_stage: dict[str, dict[str, Any]] = {}
    hashed_examples: dict[str, dict[str, Any]] = {}
    template: dict[str, Any] | None = None
    while chunk := list(islice(iterator, CHUNK_SIZE)):
        ordered_chunk = sorted(
            chunk,
            key=lambda row: (
                str(row.get("observed_at") or ""),
                str(row.get("symbol") or ""),
            ),
        )
        result = empirical_replay_core.run_replay_kernel(
            ordered_chunk,
            mode=mode,
            artifact_namespace=artifact_namespace,
            allowed_partitions=allowed_partitions,
            protocol=protocol,
        )
        template = template or dict(result.trace_summary)
        observation_count += result.trace_summary["observation_count"]
        operator_visible += result.trace_summary["operator_visible_idea_count"]
        status_counts.update(result.trace_summary["trace_status_counts"])
        failure_counts.update(result.trace_summary["failure_stage_counts"])
        route_counts.update(result.trace_summary["route_counts"])
        partition_counts.update(result.trace_summary["partition_counts"])
        ideas.extend(dict(row) for row in result.ideas)
        for idea in result.ideas:
            observed_at = str(idea.get("observed_at") or "")
            if observed_at:
                idea_observation_days.add(observed_at[:10])
        if len(result.trace_rows) != len(ordered_chunk):
            raise RuntimeError("empirical_replay_trace_observation_count_mismatch")
        for raw, trace in zip(ordered_chunk, result.trace_rows, strict=True):
            if str(trace.get("partition") or "") not in allowed_partitions:
                continue
            observed_at = str(trace.get("observed_at") or "")
            if observed_at:
                selected_observation_days.add(observed_at[:10])
                if (
                    selected_observation_start_at is None
                    or observed_at < selected_observation_start_at
                ):
                    selected_observation_start_at = observed_at
                if (
                    selected_observation_end_at is None
                    or observed_at > selected_observation_end_at
                ):
                    selected_observation_end_at = observed_at
            control_observations.append(_control_observation_projection(raw, trace))
            control_traces.append(_control_trace_projection(trace))
        for trace in result.trace_rows:
            stage = str(trace.get("failure_stage") or trace.get("radar_route") or "unknown")
            example_by_stage.setdefault(stage, dict(trace))
            digest = hashlib.sha256(empirical_replay_store.canonical_json_bytes(trace)).hexdigest()
            hashed_examples[digest] = dict(trace)
        if len(hashed_examples) > TRACE_EXAMPLE_LIMIT * 3:
            hashed_examples = dict(sorted(hashed_examples.items())[: TRACE_EXAMPLE_LIMIT * 2])
    if template is None:
        empty = empirical_replay_core.run_replay_kernel(
            (),
            mode=mode,
            artifact_namespace=artifact_namespace,
            allowed_partitions=allowed_partitions,
            protocol=protocol,
        )
        template = dict(empty.trace_summary)
    ideas.sort(key=lambda row: (str(row.get("observed_at") or ""), str(row.get("candidate_id") or "")))
    template.update({
        "observation_count": observation_count,
        "observation_counting_unit": "input_observation_rows",
        "selected_partition_observation_count": len(control_traces),
        "selected_partition_observed_day_count": len(selected_observation_days),
        "selected_partition_observation_start_at": selected_observation_start_at,
        "selected_partition_observation_end_at": selected_observation_end_at,
        "idea_count": len(ideas),
        "idea_counting_unit": "canonical_idea_rows",
        "idea_observed_day_count": len(idea_observation_days),
        "idea_count_per_selected_observed_day": (
            len(ideas) / len(selected_observation_days)
            if selected_observation_days
            else None
        ),
        "operator_visible_idea_count": operator_visible,
        "trace_status_counts": dict(sorted(status_counts.items())),
        "failure_stage_counts": dict(sorted(failure_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "route_counting_unit": "canonical_idea_rows",
        "partition_counts": dict(sorted(partition_counts.items())),
        "trace_rows_persisted": False,
        "trace_examples_bounded": True,
        "trace_example_limit": TRACE_EXAMPLE_LIMIT,
    })
    chosen: dict[str, dict[str, Any]] = {}
    for row in example_by_stage.values():
        chosen[_trace_identity(row)] = row
    for _digest_value, row in sorted(hashed_examples.items()):
        if len(chosen) >= TRACE_EXAMPLE_LIMIT:
            break
        chosen.setdefault(_trace_identity(row), row)
    examples = sorted(
        chosen.values(),
        key=lambda row: (str(row.get("observed_at") or ""), str(row.get("symbol") or ""), str(row.get("failure_stage") or "")),
    )
    return ideas, template, examples, control_observations, control_traces


def _control_observation_projection(
    raw: Mapping[str, Any],
    trace: Mapping[str, Any],
) -> dict[str, Any]:
    fields = (
        "market_regime",
        "liquidity_tier",
        "liquidity_usd",
        "trailing_quote_volume",
        "point_in_time_universe_member",
        "baseline_status",
        "data_quality_mode",
        "return_unit",
        "return_units",
        "return_24h",
        "return_72h",
        "return_7d",
        "relative_return_vs_btc_24h",
        "volume_zscore_24h",
        "rsi",
    )
    return {
        "canonical_asset_id": trace.get("canonical_asset_id"),
        "symbol": trace.get("symbol"),
        "observed_at": trace.get("observed_at"),
        "partition": trace.get("partition"),
        **{field: raw.get(field) for field in fields},
    }


def _selected_observation_days_by_partition(
    observations: Iterable[Mapping[str, Any]],
    *,
    partitions: Iterable[str],
) -> dict[str, set[str]]:
    output = {str(partition): set() for partition in partitions}
    for row in observations:
        partition = str(row.get("partition") or "")
        if partition not in output:
            raise RuntimeError("selected_observation_partition_mismatch")
        output[partition].add(_utc_day(row.get("observed_at")))
    return output


def _bind_selected_observation_day_summary(
    trace_summary: dict[str, Any],
    day_sets: Mapping[str, set[str]],
) -> None:
    union = set().union(*day_sets.values()) if day_sets else set()
    trace_summary["selected_partition_observed_day_count"] = len(union)
    trace_summary["idea_count_per_selected_observed_day"] = (
        int(trace_summary.get("idea_count") or 0) / len(union)
        if union
        else None
    )
    trace_summary["selected_partition_observed_day_count_by_partition"] = {
        partition: len(days) for partition, days in sorted(day_sets.items())
    }
    trace_summary["selected_partition_observed_days_sha256_by_partition"] = {
        partition: empirical_validation_protocol.selected_observation_days_sha256(days)
        for partition, days in sorted(day_sets.items())
    }
    trace_summary["selected_partition_observed_days_sha256"] = (
        empirical_validation_protocol.selected_observation_days_sha256(union)
    )
    trace_summary["selected_partition_observed_day_basis"] = (
        "exact_selected_observation_utc_days"
    )


def _utc_day(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("selected_observation_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError("selected_observation_timestamp_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("selected_observation_timestamp_timezone_required")
    return parsed.astimezone(timezone.utc).date().isoformat()


def _control_trace_projection(trace: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "canonical_asset_id",
        "symbol",
        "observed_at",
        "trace_status",
        "failure_stage",
        "operator_visible",
        "radar_route",
        "hard_blockers",
        "warnings",
        "actionability_score",
        "evidence_confidence_score",
        "risk_score",
        "urgency_score",
        "chase_risk_score",
        "catalyst_status",
        "spread_status",
        "rsi_context_present",
    )
    return {field: trace.get(field) for field in fields}


def _episode_policy_rows(
    ideas: Iterable[Mapping[str, Any]],
    outcome_bundle: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id = {str(row.get("candidate_id") or ""): dict(row) for row in ideas}
    representatives: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for episode in outcome_bundle.get("episodes", []):
        if not isinstance(episode, Mapping):
            continue
        idea_id = str(episode.get("representative_idea_id") or "")
        raw = by_id.get(idea_id)
        outcome = episode.get("representative_outcome")
        if raw is None or not isinstance(outcome, Mapping):
            continue
        representatives.append({
            **raw,
            "episode_id": str(episode.get("episode_id") or ""),
            "episode_member_count": int(episode.get("member_count") or 0),
            "dependent_repeat_count": int(episode.get("dependent_repeat_count") or 0),
        })
        outcomes.append(dict(outcome))
    return representatives, outcomes


def _episodes_for_partition(outcomes: Mapping[str, Any], partition: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in outcomes.get("episodes", [])
        if isinstance(row, Mapping)
        and isinstance(row.get("representative"), Mapping)
        and str(row["representative"].get("replay_partition") or row["representative"].get("partition") or "") == partition
    ]


def _partition_ranges(protocol: Mapping[str, Any], names: Iterable[str]) -> dict[str, tuple[str, str]]:
    wanted = set(names)
    return {
        str(row["name"]): (str(row["start_inclusive"]), str(row["end_exclusive"]))
        for row in protocol["partitions"]
        if row["name"] in wanted
    }


def _evaluated_at(dataset: empirical_replay_data.ReplayDataset, protocol: Mapping[str, Any], mode: str) -> str:
    if mode == "fixture_smoke":
        return max(bar.observed_at for series in dataset.series for bar in series.bars).isoformat()
    return str(protocol["analysis_window"]["outcome_data_end_exclusive"])


def _load_recommendation_seal(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        raise ValueError("final_test requires a recommendation seal")
    supplied = Path(path).expanduser()
    if (
        supplied.name != "recommendation_seal.json"
        or supplied.is_symlink()
        or supplied.parent.is_symlink()
    ):
        raise ValueError("recommendation seal path invalid")
    try:
        manifest, payloads = empirical_replay_store.load_verified_run(
            supplied.parent
        )
        raw = payloads.get("recommendation_seal.json")
        if raw is None or len(raw) > 2 * 1024 * 1024:
            raise ValueError("recommendation seal missing from immutable run")
        value = loads_no_duplicate_keys(raw.decode("utf-8"))
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise ValueError("recommendation seal unreadable") from exc
    if not isinstance(value, Mapping):
        raise ValueError("recommendation seal invalid")
    seal = dict(value)
    if raw != empirical_replay_store.canonical_json_bytes(seal):
        raise ValueError("recommendation seal invalid:noncanonical_json")
    errors = empirical_policy_lab.validate_recommendation_seal(seal)
    if errors:
        raise ValueError("recommendation seal invalid:" + ";".join(errors))
    binding = seal["selection_run_binding"]
    configuration = manifest.get("configuration")
    simulation_name = str(binding["simulation_artifact"])
    simulation = payloads.get(simulation_name)
    if (
        binding["mode"] != "full"
        or manifest.get("run_fingerprint")
        != binding["selection_run_fingerprint"]
        or manifest.get("input_sha256") != binding["input_sha256"]
        or manifest.get("code_sha256") != binding["code_sha256"]
        or not isinstance(configuration, Mapping)
        or configuration.get("mode") != "full"
        or configuration.get("partitions") != ["development", "validation"]
        or configuration.get("universe_top_n") != 100
        or hashlib.sha256(
            empirical_replay_store.canonical_json_bytes(configuration)
        ).hexdigest()
        != binding["configuration_sha256"]
        or not isinstance(simulation, bytes)
        or hashlib.sha256(simulation).hexdigest() != seal["simulation_sha256"]
        or manifest.get("protocol_sha256") != seal["protocol_sha256"]
    ):
        raise ValueError("recommendation seal selection run binding invalid")
    return seal


def _code_paths() -> dict[str, Path]:
    operations = Path(__file__).resolve().parent
    radar = operations.parent / "radar"
    package = operations.parent.parent
    return {
        "empirical_replay_run.py": Path(__file__),
        "empirical_validation_protocol.py": operations / "empirical_validation_protocol.py",
        "empirical_replay_observations.py": operations / "_empirical_replay_observations.py",
        "empirical_replay_data.py": operations / "empirical_replay_data.py",
        "empirical_replay_data_bar.py": operations / "empirical_replay_data_bar.py",
        "empirical_replay_data_dataset.py": operations / "empirical_replay_data_dataset.py",
        "empirical_replay_data_error.py": operations / "empirical_replay_data_error.py",
        "empirical_replay_data_mode.py": operations / "empirical_replay_data_mode.py",
        "empirical_replay_data_series.py": operations / "empirical_replay_data_series.py",
        "empirical_replay_core.py": operations / "empirical_replay_core.py",
        "empirical_replay_outcomes.py": operations / "empirical_replay_outcomes.py",
        "empirical_replay_outcome_join.py": operations / "empirical_replay_outcome_join.py",
        "empirical_replay_persistence.py": operations / "empirical_replay_persistence.py",
        "empirical_replay_analysis.py": operations / "empirical_replay_analysis.py",
        "empirical_replay_dimensions.py": operations / "empirical_replay_dimensions.py",
        "empirical_operator_burden.py": operations / "empirical_operator_burden.py",
        "empirical_survivability.py": operations / "empirical_survivability.py",
        "empirical_replay_statistics.py": operations / "empirical_replay_statistics.py",
        "empirical_replay_controls.py": operations / "empirical_replay_controls.py",
        "empirical_missed_attribution.py": operations / "empirical_missed_attribution.py",
        "empirical_replay_benchmark_metrics.py": operations / "empirical_replay_benchmark_metrics.py",
        "empirical_review.py": operations / "empirical_review.py",
        "empirical_policy_lab.py": operations / "empirical_policy_lab.py",
        "empirical_policy_metrics.py": operations / "empirical_policy_metrics.py",
        "empirical_replay_store.py": operations / "empirical_replay_store.py",
        "market_provenance.py": operations / "market_provenance.py",
        "decision_model.py": radar / "decision_model.py",
        "decision_model_surfaces.py": radar / "decision_model_surfaces.py",
        "decision_models.py": radar / "decision_models.py",
        "decision_policy.py": radar / "decision_policy.py",
        "decision_catalyst_policy.py": radar / "decision_catalyst_policy.py",
        "decision_market_quality.py": radar / "decision_market_quality.py",
        "decision_safety.py": radar / "decision_safety.py",
        "decision_results.py": radar / "decision_results.py",
        "market_units.py": radar / "market_units.py",
        "rsi_technical_context.py": radar / "rsi_technical_context.py",
        "catalyst_attribution.py": radar / "catalyst_attribution.py",
        "source_independence.py": radar / "source_independence.py",
        "source_independence_store.py": radar / "source_independence_store.py",
        "market_anomaly_scanner.py": radar / "market_anomaly_scanner.py",
        "market_anomaly_receipt.py": radar / "market_anomaly_receipt.py",
        "asset_registry.py": radar / "asset_registry.py",
        "market_state.py": radar / "market_state.py",
        "decision_projection_schema.py": operations.parent / "artifacts" / "schema" / "decision_model.py",
        "artifact_json_lines.py": operations.parent / "artifacts" / "json_lines.py",
        "config.py": package / "config.py",
        "state_features.py": package / "state_features.py",
        "indicators.py": package / "indicators.py",
        "signal_registry.py": package / "signal_registry.py",
    }


def _execution_summary(
    *,
    run_mode: str,
    fingerprint: str,
    catalog: Mapping[str, Any],
    configuration: Mapping[str, Any],
    trace_summary: Mapping[str, Any],
    outcomes: Mapping[str, Any],
    analyses: Mapping[str, Mapping[str, Any]],
    controls: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    matched = controls["matched_non_signal_controls"]
    missed = controls["missed_move_evaluation"]
    benchmark_status_counts = Counter(
        str(row.get("status") or "unknown") for row in controls["benchmark_rows"]
    )
    return {
        "schema_id": RUN_SCHEMA_ID,
        "schema_version": RUN_SCHEMA_VERSION,
        "mode": run_mode,
        "run_fingerprint": fingerprint,
        "input_data_window_semantics": "completed_daily_bar_cache_window_inclusive",
        "data_start_at": catalog["data_start_at"],
        "data_end_at": catalog["data_end_at"],
        "candidate_pool_symbol_count": catalog["selected_symbol_count"],
        "point_in_time_universe_top_n": configuration["universe_top_n"],
        "selected_symbol_count": catalog["selected_symbol_count"],
        "selected_symbol_count_semantics": (
            "legacy_alias_candidate_pool_symbol_count"
        ),
        "input_row_count": catalog["row_count"],
        "partial_bar_count": catalog["partial_bar_count"],
        "observation_count": trace_summary["observation_count"],
        "observation_counting_unit": trace_summary["observation_counting_unit"],
        "selected_partition_observation_count": trace_summary[
            "selected_partition_observation_count"
        ],
        "selected_partition_observed_day_count": trace_summary[
            "selected_partition_observed_day_count"
        ],
        "selected_partition_observed_day_count_by_partition": dict(
            trace_summary[
                "selected_partition_observed_day_count_by_partition"
            ]
        ),
        "selected_partition_observed_day_basis": trace_summary[
            "selected_partition_observed_day_basis"
        ],
        "selected_partition_observation_start_at": trace_summary[
            "selected_partition_observation_start_at"
        ],
        "selected_partition_observation_end_at": trace_summary[
            "selected_partition_observation_end_at"
        ],
        "idea_count": trace_summary["idea_count"],
        "idea_counting_unit": trace_summary["idea_counting_unit"],
        "idea_observed_day_count": trace_summary["idea_observed_day_count"],
        "idea_count_per_selected_observed_day": trace_summary[
            "idea_count_per_selected_observed_day"
        ],
        "route_counts": dict(trace_summary["route_counts"]),
        "route_counting_unit": trace_summary["route_counting_unit"],
        "episode_count": outcomes["episode_count"],
        "dependent_repeat_count": outcomes["dependent_repeat_count"],
        "matched_control_count": matched["selected_control_count"],
        "matched_control_unavailable_count": matched["unavailable_control_count"],
        "missed_opportunity_count": missed["missed_opportunity_count"],
        "missed_endpoint_candidate_count": missed["endpoint_candidate_count"],
        "benchmark_status_counts": dict(sorted(benchmark_status_counts.items())),
        "matured_episode_count_by_partition": {
            name: analysis["matured_episode_count"] for name, analysis in analyses.items()
        },
        "evidence_strength_by_partition": {
            name: _strongest_evidence(
                row["evidence_strength"] for row in analysis["route_cohorts"]
            )
            for name, analysis in analyses.items()
        },
        "residual_survivorship_present": catalog["residual_survivorship_present"],
        "historical_spread_observed": False,
        "intraday_validation_available": False,
        "runtime": dict(runtime),
        "research_only": True,
        "auto_apply": False,
        "policy_mutations": 0,
        "provider_calls": 0,
        "dashboard_authority_mutations": 0,
    }


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    route_counts = ", ".join(f"{key}={value}" for key, value in sorted(summary["route_counts"].items())) or "none"
    return "\n".join([
        "# Decision Radar empirical replay execution",
        "",
        f"- Mode: `{summary['mode']}`",
        f"- Fingerprint: `{summary['run_fingerprint']}`",
        f"- Input cache: `{summary['data_start_at']}` through `{summary['data_end_at']}` (inclusive completed daily bars)",
        f"- Selected partitions: `{summary['selected_partition_observation_start_at']}` through `{summary['selected_partition_observation_end_at']}` / {summary['selected_partition_observation_count']} observation rows / {summary['selected_partition_observed_day_count']} observed UTC days",
        f"- Candidate-pool inputs: {summary['candidate_pool_symbol_count']} cached symbols / {summary['input_row_count']} bars / {summary['partial_bar_count']} partial bars",
        f"- Point-in-time universe: top {summary['point_in_time_universe_top_n']} assets per observation (the candidate-pool symbol count is not the daily universe size)",
        f"- Replay: {summary['observation_count']} input observation rows / {summary['idea_count']} canonical idea rows / {summary['episode_count']} independent episodes",
        f"- Idea burden: {summary['idea_observed_day_count']} active idea days / {summary['idea_count_per_selected_observed_day'] or 0.0:.4f} ideas per selected observed day",
        f"- Routes (canonical idea rows): {route_counts}",
        f"- Controls: {summary['matched_control_count']} matched / {summary['matched_control_unavailable_count']} unavailable",
        f"- Missed opportunities: {summary['missed_opportunity_count']} of {summary['missed_endpoint_candidate_count']} frozen endpoint candidates",
        f"- Runtime: {summary['runtime']['total_seconds']:.3f}s; bottleneck `{summary['runtime']['bottleneck_stage']}`",
        "- Historical spread and intraday validation remain unavailable.",
        "- Research only; no policy auto-apply, provider call, send, trade, paper trade, RSI write, fade trigger, or dashboard authority mutation.",
        "",
    ])


def _strongest_evidence(values: Iterable[str]) -> str:
    order = {
        "no_evidence": 0,
        "insufficient": 1,
        "descriptive_only": 2,
        "exploratory": 3,
        "stronger_exploratory": 4,
    }
    return max((str(value) for value in values), key=lambda value: order.get(value, -1), default="no_evidence")


def _resume_summary(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": RUN_SCHEMA_ID,
        "schema_version": RUN_SCHEMA_VERSION,
        "mode": manifest.get("configuration", {}).get("mode"),
        "run_fingerprint": manifest.get("run_fingerprint"),
        "resumed": True,
        "metrics": dict(manifest.get("metrics") or {}),
        "research_only": True,
        "auto_apply": False,
    }


def _jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(empirical_replay_store.canonical_json_bytes(row) for row in rows)


def _trace_identity(row: Mapping[str, Any]) -> str:
    return "|".join(str(row.get(field) or "") for field in ("observed_at", "symbol", "failure_stage", "candidate_id"))


def _normalize_mode(value: str) -> str:
    normalized = str(value or "").strip().casefold().replace("-", "_")
    if normalized not in {"fixture_smoke", "medium", "full", "final_test"}:
        raise ValueError("empirical replay mode invalid")
    return normalized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run offline Decision Radar empirical replay.")
    parser.add_argument("--mode", choices=("fixture-smoke", "medium", "full", "final-test"), required=True)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--recommendation-seal")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = execute_empirical_replay(
        mode=args.mode,
        input_dir=args.input_dir,
        output_root=args.output_root,
        recommendation_seal_path=args.recommendation_seal,
    )
    payload = {
        "mode": result.mode,
        "run_dir": str(result.run_dir),
        "run_fingerprint": result.run_fingerprint,
        "resumed": result.resumed,
        "summary": result.summary,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"mode={result.mode}")
        print(f"run_fingerprint={result.run_fingerprint}")
        print(f"run_dir={result.run_dir}")
        print(f"resumed={str(result.resumed).lower()}")
        metrics = result.manifest.get("metrics") or {}
        print("metrics=" + ",".join(f"{key}={value}" for key, value in sorted(metrics.items())))
        print("research_only=true auto_apply=false provider_calls=0 dashboard_authority_mutations=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["EmpiricalReplayExecution", "execute_empirical_replay", "main"]
