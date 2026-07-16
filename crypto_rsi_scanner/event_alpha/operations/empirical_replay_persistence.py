"""Bounded immutable persistence projections for empirical replay products.

The replay kernel, outcome engine, analysis, and policy simulator intentionally
operate on their full in-memory values.  This module only closes the persisted
research archive: it removes redundant production-surface aliases, retains one
canonical Decision-v2 projection per idea, replaces duplicated episode
snapshots with digest-bound idea references, and writes deterministic plaintext
JSONL shards.  Plaintext is deliberate so the immutable store's path and secret
scanners continue to inspect every persisted byte.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from ..artifacts.json_lines import loads_no_duplicate_keys
from ..radar.decision_model_surfaces import decision_model_values
from . import empirical_replay_store


PERSISTENCE_SCHEMA_VERSION = 1
DEFAULT_SHARD_TARGET_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_PARTS = 128

IDEA_INDEX_FILENAME = "replay_ideas.index.json"
IDEA_PART_PREFIX = "replay_ideas.part-"
IDEA_ARCHIVE_SCHEMA_ID = "decision_radar.empirical_replay_idea_archive"
IDEA_RECORD_SCHEMA_ID = "decision_radar.empirical_replay_idea_snapshot"

EPISODE_INDEX_FILENAME = "replay_episode_outcomes.index.json"
EPISODE_PART_PREFIX = "replay_episode_outcomes.part-"
EPISODE_ARCHIVE_SCHEMA_ID = "decision_radar.empirical_replay_episode_archive"
EPISODE_RECORD_SCHEMA_ID = "decision_radar.empirical_replay_episode_record"

_IDEA_MARKET_FIELDS = (
    "symbol",
    "coin_id",
    "canonical_asset_id",
    "observed_at",
    "price",
    "return_24h",
    "return_72h",
    "return_7d",
    "relative_return_vs_btc_24h",
    "relative_return_vs_eth_24h",
    "return_unit",
    "return_units",
    "source_return_unit",
    "source_return_units",
    "threshold_unit",
    "volume_24h",
    "volume_zscore_24h",
    "liquidity_usd",
    "liquidity_tier",
    "spread_status",
    "freshness_status",
    "market_context_freshness_status",
    "market_data_source",
    "unit_warnings",
)
_PROGRESSION_FIELDS = (
    "radar_route",
    "actionability_score",
    "evidence_confidence_score",
    "risk_score",
    "urgency_score",
    "chase_risk_score",
    "market_phase",
    "catalyst_status",
    "spread_status",
    "derivatives_status",
    "expires_at",
)
_FALSE_SAFETY_FIELDS = (
    "notification_send_enabled",
    "paper_trade_created",
    "normal_rsi_signal_written",
    "triggered_fade_created",
    "decision_source_side_effect_safety_failed",
    "decision_source_secret_safety_failed",
    "decision_source_path_safety_failed",
)


@dataclass(frozen=True)
class ReplayPersistenceArchives:
    artifacts: dict[str, bytes]
    metrics: dict[str, int]
    idea_index: dict[str, Any]
    episode_index: dict[str, Any]


def compact_idea_snapshot(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return one closed, audit-complete idea without redundant aliases."""

    if not isinstance(raw, Mapping):
        raise ValueError("empirical replay idea invalid")
    projection_raw = raw.get("decision_projection")
    if not isinstance(projection_raw, Mapping):
        raise ValueError("empirical replay idea canonical projection missing")
    projection = _json_safe(projection_raw)
    if decision_model_values(projection) != projection:
        raise ValueError("empirical replay idea canonical projection invalid")
    if raw.get("research_only") is not True or projection.get("research_only") is not True:
        raise ValueError("empirical replay idea research-only contract invalid")
    for field in _FALSE_SAFETY_FIELDS:
        if raw.get(field) is not False:
            raise ValueError(f"empirical replay idea safety field invalid:{field}")

    market_raw = raw.get("market_snapshot")
    if not isinstance(market_raw, Mapping):
        raise ValueError("empirical replay idea market snapshot missing")
    quality_raw = market_raw.get("market_data_quality")
    if not isinstance(quality_raw, Mapping):
        quality_raw = market_raw.get("data_quality")
    market_features = {
        field: _json_safe_value(market_raw.get(field))
        for field in _IDEA_MARKET_FIELDS
    }
    market_features["quality"] = _json_safe_value(
        quality_raw if isinstance(quality_raw, Mapping) else {}
    )

    value: dict[str, Any] = {
        "schema_id": IDEA_RECORD_SCHEMA_ID,
        "schema_version": PERSISTENCE_SCHEMA_VERSION,
        "identity": _selected(
            raw,
            (
                "candidate_id",
                "candidate_family_id",
                "core_opportunity_id",
                "incident_id",
                "market_anomaly_id",
                "market_snapshot_id",
                "symbol",
                "canonical_asset_id",
            ),
        ),
        "replay": _selected(
            raw,
            (
                "observed_at",
                "decision_evaluated_at",
                "replay_partition",
                "replay_mode",
                "replay_protocol_version",
                "replay_protocol_sha256",
            ),
        ),
        "anomaly": _selected(
            raw,
            ("anomaly_type", "anomaly_bucket", "operator_visible"),
        ),
        "point_in_time_context": _selected(
            raw,
            (
                "market_regime",
                "liquidity_tier",
                "liquidity_usd",
                "trailing_quote_volume_usd",
                "point_in_time_volume_rank",
                "point_in_time_universe_member",
                "baseline_status",
                "baseline_maturity",
                "data_quality_mode",
                "replay_data_quality_mode",
            ),
        ),
        "market_features": market_features,
        "feature_quality": _json_safe_value(raw.get("replay_feature_quality") or {}),
        "provenance": _selected(
            raw,
            (
                "artifact_namespace",
                "run_id",
                "run_mode",
                "data_mode",
                "profile",
                "source_origin",
                "source_origins",
                "source_pack",
                "source_packs",
                "source_class",
                "source_provider",
                "provider",
            ),
        ),
        "decision_projection": projection,
        "safety": {
            "research_only": True,
            **{field: False for field in _FALSE_SAFETY_FIELDS},
        },
    }
    candidate_id = str(value["identity"].get("candidate_id") or "")
    observed_at = str(value["replay"].get("observed_at") or "")
    if not candidate_id or not observed_at:
        raise ValueError("empirical replay idea identity invalid")
    value["snapshot_sha256"] = _record_digest(value, "snapshot_sha256")
    return value


def compact_episode_record(
    raw_episode: Mapping[str, Any],
    compact_ideas_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Close one episode through immutable idea references and full outcomes."""

    if not isinstance(raw_episode, Mapping):
        raise ValueError("empirical replay episode invalid")
    episode_id = str(raw_episode.get("episode_id") or "")
    representative_id = str(raw_episode.get("representative_idea_id") or "")
    raw_members = raw_episode.get("member_progression")
    raw_progression_fields = raw_episode.get("progression_fields")
    if (
        not episode_id
        or not representative_id
        or not isinstance(raw_members, Sequence)
        or isinstance(raw_members, (str, bytes, bytearray))
        or not raw_members
        or tuple(raw_progression_fields or ()) != _PROGRESSION_FIELDS
        or raw_episode.get("research_only") is not True
    ):
        raise ValueError("empirical replay episode contract invalid")

    members: list[dict[str, Any]] = []
    representative_count = 0
    for index, raw_member in enumerate(raw_members):
        if not isinstance(raw_member, Mapping):
            raise ValueError("empirical replay episode member invalid")
        idea_id = str(raw_member.get("idea_id") or raw_member.get("candidate_id") or "")
        candidate_id = str(raw_member.get("candidate_id") or idea_id)
        compact = compact_ideas_by_id.get(idea_id) or compact_ideas_by_id.get(candidate_id)
        if compact is None:
            raise ValueError("empirical replay episode idea reference missing")
        identity = compact.get("identity")
        replay = compact.get("replay")
        if not isinstance(identity, Mapping) or not isinstance(replay, Mapping):
            raise ValueError("empirical replay episode idea reference invalid")
        if str(identity.get("candidate_id") or "") != candidate_id:
            raise ValueError("empirical replay episode candidate reference mismatch")
        member_projection = raw_member.get("decision_projection")
        if not isinstance(member_projection, Mapping) or _json_safe(member_projection) != compact.get(
            "decision_projection"
        ):
            raise ValueError("empirical replay episode projection reference mismatch")
        observed_at = str(raw_member.get("observed_at") or "")
        if observed_at != str(replay.get("observed_at") or ""):
            raise ValueError("empirical replay episode timestamp reference mismatch")
        is_representative = idea_id == representative_id
        representative_count += int(is_representative)
        members.append(
            {
                "idea_id": idea_id,
                "candidate_id": candidate_id,
                "observed_at": observed_at,
                "idea_snapshot_sha256": compact.get("snapshot_sha256"),
                "is_representative": is_representative,
                "progression": {
                    field: _json_safe_value(raw_member.get(field))
                    for field in _PROGRESSION_FIELDS
                },
                "progression_index": index,
            }
        )
    if representative_count != 1 or members[0]["is_representative"] is not True:
        raise ValueError("empirical replay episode representative reference invalid")
    raw_member_count = raw_episode.get("member_count")
    raw_dependent_count = raw_episode.get("dependent_repeat_count")
    if type(raw_member_count) is not int or raw_member_count != len(members):
        raise ValueError("empirical replay episode member count mismatch")
    if type(raw_dependent_count) is not int or raw_dependent_count != len(members) - 1:
        raise ValueError("empirical replay episode dependent count mismatch")

    outcome_raw = raw_episode.get("representative_outcome")
    if not isinstance(outcome_raw, Mapping):
        raise ValueError("empirical replay representative outcome missing")
    outcome = _json_safe(outcome_raw)
    if (
        str(outcome.get("idea_id") or "") != representative_id
        or str(outcome.get("episode_id") or "") != episode_id
        or outcome.get("research_only") is not True
        or outcome.get("auto_apply") is not False
    ):
        raise ValueError("empirical replay representative outcome reference invalid")

    value: dict[str, Any] = {
        "schema_id": EPISODE_RECORD_SCHEMA_ID,
        "schema_version": PERSISTENCE_SCHEMA_VERSION,
        "episode_id": episode_id,
        "episode_identity": _json_safe_value(raw_episode.get("episode_identity") or {}),
        "canonical_asset_id": _json_safe_value(raw_episode.get("canonical_asset_id")),
        "directional_bias": _json_safe_value(raw_episode.get("directional_bias")),
        "anomaly_family": _json_safe_value(raw_episode.get("anomaly_family")),
        "episode_start_at": _json_safe_value(raw_episode.get("episode_start_at")),
        "window_end_inclusive_at": _json_safe_value(
            raw_episode.get("window_end_inclusive_at")
        ),
        "representative_rule": _json_safe_value(raw_episode.get("representative_rule")),
        "representative_idea_id": representative_id,
        "member_count": len(members),
        "dependent_repeat_count": len(members) - 1,
        "members": members,
        "progression_fields": list(_PROGRESSION_FIELDS),
        "representative_outcome": outcome,
        "dependent_repeats_counted_as_independent": False,
        "representative_reselected": False,
        "source_episode_digest": _json_safe_value(raw_episode.get("episode_digest")),
        "research_only": True,
        "auto_apply": False,
    }
    value["archive_episode_sha256"] = _record_digest(
        value, "archive_episode_sha256"
    )
    return value


def build_replay_persistence_archives(
    ideas: Iterable[Mapping[str, Any]],
    outcome_bundle: Mapping[str, Any],
    *,
    shard_target_bytes: int = DEFAULT_SHARD_TARGET_BYTES,
) -> ReplayPersistenceArchives:
    """Build deterministic bounded idea and episode archive artifacts."""

    _validate_shard_target(shard_target_bytes)
    compact_ideas = [compact_idea_snapshot(row) for row in ideas]
    compact_ideas.sort(key=_idea_sort_key)
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in compact_ideas:
        candidate_id = str(row["identity"]["candidate_id"])
        if candidate_id in by_id:
            raise ValueError("empirical replay idea identity duplicated")
        by_id[candidate_id] = row

    if not isinstance(outcome_bundle, Mapping):
        raise ValueError("empirical replay outcome bundle invalid")
    raw_episodes = outcome_bundle.get("episodes")
    if not isinstance(raw_episodes, Sequence) or isinstance(
        raw_episodes, (str, bytes, bytearray)
    ):
        raise ValueError("empirical replay outcome episodes invalid")
    if int(outcome_bundle.get("episode_count") or 0) != len(raw_episodes):
        raise ValueError("empirical replay outcome episode count mismatch")
    episodes = [compact_episode_record(row, by_id) for row in raw_episodes]
    episodes.sort(key=_episode_sort_key)

    idea_artifacts, idea_index = _archive_artifacts(
        compact_ideas,
        index_filename=IDEA_INDEX_FILENAME,
        part_prefix=IDEA_PART_PREFIX,
        archive_schema_id=IDEA_ARCHIVE_SCHEMA_ID,
        record_schema_id=IDEA_RECORD_SCHEMA_ID,
        ordering=("replay.observed_at", "identity.candidate_id"),
        record_id=_idea_record_id,
        shard_target_bytes=shard_target_bytes,
        extra_index={
            "canonical_decision_projection_embedded": True,
            "normalized_market_feature_snapshot_embedded": True,
        },
    )
    outcome_metadata = {
        key: _json_safe_value(value)
        for key, value in outcome_bundle.items()
        if key not in {"episodes", "contract_digest"}
    }
    episode_artifacts, episode_index = _archive_artifacts(
        episodes,
        index_filename=EPISODE_INDEX_FILENAME,
        part_prefix=EPISODE_PART_PREFIX,
        archive_schema_id=EPISODE_ARCHIVE_SCHEMA_ID,
        record_schema_id=EPISODE_RECORD_SCHEMA_ID,
        ordering=("episode_start_at", "episode_id"),
        record_id=_episode_record_id,
        shard_target_bytes=shard_target_bytes,
        extra_index={
            "bundle_metadata": outcome_metadata,
            "source_contract_digest": _json_safe_value(
                outcome_bundle.get("contract_digest")
            ),
            "representative_ideas_resolve_through": IDEA_INDEX_FILENAME,
            "representative_outcomes_embedded": True,
        },
    )
    artifacts = {**idea_artifacts, **episode_artifacts}
    metrics = {
        "persistence_schema_version": PERSISTENCE_SCHEMA_VERSION,
        "artifact_shard_target_bytes": shard_target_bytes,
        "persisted_idea_count": len(compact_ideas),
        "persisted_episode_count": len(episodes),
        "idea_shard_count": len(idea_index["shards"]),
        "episode_shard_count": len(episode_index["shards"]),
        "persistence_artifact_count": len(artifacts),
        "persistence_artifact_bytes": sum(len(payload) for payload in artifacts.values()),
    }
    return ReplayPersistenceArchives(artifacts, metrics, idea_index, episode_index)


def decode_archive_rows(
    index_filename: str,
    artifacts: Mapping[str, bytes],
) -> tuple[dict[str, Any], ...]:
    """Verify and decode an in-memory archive artifact mapping."""

    index_payload = artifacts.get(index_filename)
    if not isinstance(index_payload, bytes):
        raise ValueError("empirical replay archive index missing")
    try:
        decoded = loads_no_duplicate_keys(index_payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("empirical replay archive index invalid") from exc
    if not isinstance(decoded, Mapping):
        raise ValueError("empirical replay archive index invalid")
    index = dict(decoded)
    expected_digest = index.pop("archive_digest", None)
    if expected_digest != _sha256(empirical_replay_store.canonical_json_bytes(index)):
        raise ValueError("empirical replay archive index digest mismatch")
    expected_index = {
        IDEA_INDEX_FILENAME: (IDEA_ARCHIVE_SCHEMA_ID, IDEA_RECORD_SCHEMA_ID, IDEA_PART_PREFIX),
        EPISODE_INDEX_FILENAME: (
            EPISODE_ARCHIVE_SCHEMA_ID,
            EPISODE_RECORD_SCHEMA_ID,
            EPISODE_PART_PREFIX,
        ),
    }.get(index_filename)
    if (
        expected_index is None
        or index.get("schema_id") != expected_index[0]
        or index.get("record_schema_id") != expected_index[1]
        or index.get("schema_version") != PERSISTENCE_SCHEMA_VERSION
        or index.get("research_only") is not True
        or index.get("auto_apply") is not False
    ):
        raise ValueError("empirical replay archive index contract invalid")
    _validate_shard_target(index.get("shard_target_bytes"))
    shards = index.get("shards")
    if (
        not isinstance(shards, list)
        or len(shards) > MAX_ARCHIVE_PARTS
        or index.get("shard_count") != len(shards)
    ):
        raise ValueError("empirical replay archive shard index invalid")
    rows: list[dict[str, Any]] = []
    part_names: set[str] = set()
    for descriptor in shards:
        if not isinstance(descriptor, Mapping):
            raise ValueError("empirical replay archive shard descriptor invalid")
        name = str(descriptor.get("name") or "")
        if (
            not name.startswith(expected_index[2])
            or not name.endswith(".jsonl")
            or name in part_names
        ):
            raise ValueError("empirical replay archive shard name invalid")
        part_names.add(name)
        payload = artifacts.get(name)
        if not isinstance(payload, bytes):
            raise ValueError("empirical replay archive shard missing")
        if (
            len(payload) != descriptor.get("size_bytes")
            or len(payload) > index["shard_target_bytes"]
            or _sha256(payload) != descriptor.get("sha256")
        ):
            raise ValueError("empirical replay archive shard digest mismatch")
        shard_rows: list[dict[str, Any]] = []
        for line in payload.splitlines():
            try:
                value = loads_no_duplicate_keys(line.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
                raise ValueError("empirical replay archive row invalid") from exc
            if not isinstance(value, Mapping):
                raise ValueError("empirical replay archive row invalid")
            shard_rows.append(dict(value))
        if len(shard_rows) != descriptor.get("record_count"):
            raise ValueError("empirical replay archive shard count mismatch")
        if shard_rows and (
            _record_id_for_schema(expected_index[1], shard_rows[0])
            != descriptor.get("first_record_id")
            or _record_id_for_schema(expected_index[1], shard_rows[-1])
            != descriptor.get("last_record_id")
        ):
            raise ValueError("empirical replay archive shard boundary mismatch")
        rows.extend(shard_rows)
    if len(rows) != index.get("record_count"):
        raise ValueError("empirical replay archive record count mismatch")
    _validate_decoded_rows(index, rows)
    return tuple(rows)


def _archive_artifacts(
    rows: Sequence[Mapping[str, Any]],
    *,
    index_filename: str,
    part_prefix: str,
    archive_schema_id: str,
    record_schema_id: str,
    ordering: tuple[str, ...],
    record_id,
    shard_target_bytes: int,
    extra_index: Mapping[str, Any],
) -> tuple[dict[str, bytes], dict[str, Any]]:
    parts: list[tuple[str, bytes, list[Mapping[str, Any]]]] = []
    current_rows: list[Mapping[str, Any]] = []
    current_payload = bytearray()
    for row in rows:
        line = empirical_replay_store.canonical_json_bytes(row)
        if len(line) > shard_target_bytes:
            raise ValueError("empirical replay archive row exceeds shard target")
        if current_rows and len(current_payload) + len(line) > shard_target_bytes:
            name = f"{part_prefix}{len(parts):05d}.jsonl"
            parts.append((name, bytes(current_payload), current_rows))
            current_rows = []
            current_payload = bytearray()
        current_rows.append(row)
        current_payload.extend(line)
    if current_rows:
        name = f"{part_prefix}{len(parts):05d}.jsonl"
        parts.append((name, bytes(current_payload), current_rows))
    if len(parts) > MAX_ARCHIVE_PARTS:
        raise ValueError("empirical replay archive part count exceeds bound")

    artifacts: dict[str, bytes] = {}
    descriptors: list[dict[str, Any]] = []
    for name, payload, part_rows in parts:
        artifacts[name] = payload
        descriptors.append(
            {
                "name": name,
                "record_count": len(part_rows),
                "size_bytes": len(payload),
                "sha256": _sha256(payload),
                "first_record_id": record_id(part_rows[0]),
                "last_record_id": record_id(part_rows[-1]),
            }
        )
    index: dict[str, Any] = {
        "schema_id": archive_schema_id,
        "schema_version": PERSISTENCE_SCHEMA_VERSION,
        "record_schema_id": record_schema_id,
        "record_count": len(rows),
        "ordering": list(ordering),
        "shard_target_bytes": shard_target_bytes,
        "shard_count": len(parts),
        "shards": descriptors,
        "research_only": True,
        "auto_apply": False,
        **_json_safe(extra_index),
    }
    index["archive_digest"] = _sha256(
        empirical_replay_store.canonical_json_bytes(index)
    )
    artifacts[index_filename] = empirical_replay_store.canonical_json_bytes(index)
    return artifacts, index


def _validate_decoded_rows(index: Mapping[str, Any], rows: list[dict[str, Any]]) -> None:
    schema_id = index.get("record_schema_id")
    if schema_id == IDEA_RECORD_SCHEMA_ID:
        if rows != sorted(rows, key=_idea_sort_key):
            raise ValueError("empirical replay idea archive ordering invalid")
        identifiers: set[str] = set()
        for row in rows:
            if row.get("schema_id") != IDEA_RECORD_SCHEMA_ID or row.get(
                "snapshot_sha256"
            ) != _record_digest(row, "snapshot_sha256"):
                raise ValueError("empirical replay idea archive record invalid")
            identity = row.get("identity")
            candidate_id = str(identity.get("candidate_id") or "") if isinstance(identity, Mapping) else ""
            if not candidate_id or candidate_id in identifiers:
                raise ValueError("empirical replay idea archive identity invalid")
            identifiers.add(candidate_id)
    elif schema_id == EPISODE_RECORD_SCHEMA_ID:
        if rows != sorted(rows, key=_episode_sort_key):
            raise ValueError("empirical replay episode archive ordering invalid")
        identifiers = set()
        for row in rows:
            if row.get("schema_id") != EPISODE_RECORD_SCHEMA_ID or row.get(
                "archive_episode_sha256"
            ) != _record_digest(row, "archive_episode_sha256"):
                raise ValueError("empirical replay episode archive record invalid")
            episode_id = str(row.get("episode_id") or "")
            if not episode_id or episode_id in identifiers:
                raise ValueError("empirical replay episode archive identity invalid")
            identifiers.add(episode_id)
    else:
        raise ValueError("empirical replay archive record schema invalid")


def _validate_shard_target(value: int) -> None:
    if (
        type(value) is not int
        or value < 1024
        or value > empirical_replay_store.MAX_ARTIFACT_BYTES
    ):
        raise ValueError("empirical replay archive shard target invalid")


def _selected(source: Mapping[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: _json_safe_value(source.get(field)) for field in fields}


def _json_safe(value: Mapping[str, Any]) -> dict[str, Any]:
    decoded = _json_safe_value(dict(value))
    if not isinstance(decoded, dict):
        raise ValueError("empirical replay persistence mapping invalid")
    return decoded


def _json_safe_value(value: Any) -> Any:
    try:
        return json.loads(empirical_replay_store.canonical_json_bytes(value))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("empirical replay persistence value invalid") from exc


def _record_digest(row: Mapping[str, Any], digest_field: str) -> str:
    payload = {key: value for key, value in row.items() if key != digest_field}
    return _sha256(empirical_replay_store.canonical_json_bytes(payload))


def _idea_sort_key(row: Mapping[str, Any]) -> tuple[str, str]:
    replay = row.get("replay")
    identity = row.get("identity")
    return (
        str(replay.get("observed_at") or "") if isinstance(replay, Mapping) else "",
        str(identity.get("candidate_id") or "") if isinstance(identity, Mapping) else "",
    )


def _episode_sort_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("episode_start_at") or ""), str(row.get("episode_id") or ""))


def _idea_record_id(row: Mapping[str, Any]) -> str:
    identity = row.get("identity")
    return str(identity.get("candidate_id") or "") if isinstance(identity, Mapping) else ""


def _episode_record_id(row: Mapping[str, Any]) -> str:
    return str(row.get("episode_id") or "")


def _record_id_for_schema(schema_id: str, row: Mapping[str, Any]) -> str:
    if schema_id == IDEA_RECORD_SCHEMA_ID:
        return _idea_record_id(row)
    if schema_id == EPISODE_RECORD_SCHEMA_ID:
        return _episode_record_id(row)
    raise ValueError("empirical replay archive record schema invalid")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "DEFAULT_SHARD_TARGET_BYTES",
    "EPISODE_INDEX_FILENAME",
    "EPISODE_PART_PREFIX",
    "IDEA_INDEX_FILENAME",
    "IDEA_PART_PREFIX",
    "PERSISTENCE_SCHEMA_VERSION",
    "ReplayPersistenceArchives",
    "build_replay_persistence_archives",
    "compact_episode_record",
    "compact_idea_snapshot",
    "decode_archive_rows",
]
