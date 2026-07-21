"""Read-only DefiLlama mapping review for the exact dashboard authority.

The command resolves the persisted dashboard pointer through the normal strict
authority contract, derives the exact selected CoinGecko universe, and emits a
deliberately incomplete operator-registry template.  It performs no provider
call or write and never infers a protocol identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...event_providers import defillama_mapping_registry as mapping_registry
from ..dashboard import readiness as dashboard_readiness


SCHEMA_ID = "decision_radar.defillama_current_mapping_review"
SCHEMA_VERSION = 1
MAX_UNIVERSE_ROWS = 100
MAX_AUDIT_ROWS = 500
OUTPUT_JSON = "json"
OUTPUT_SUMMARY = "summary"
OUTPUT_TEMPLATE = "template"
OUTPUT_CHOICES = (OUTPUT_JSON, OUTPUT_SUMMARY, OUTPUT_TEMPLATE)
FULL_JSON_COMMAND = (
    "make -s radar-fundamentals-defillama-mapping-review "
    "RADAR_DEFILLAMA_MAPPING_OUTPUT=json PYTHON=.venv/bin/python"
)
TEMPLATE_COMMAND = (
    "make -s radar-fundamentals-defillama-mapping-review "
    "RADAR_DEFILLAMA_MAPPING_OUTPUT=template PYTHON=.venv/bin/python"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")


class DefiLlamaCurrentMappingReviewError(ValueError):
    """Raised when the current authority cannot yield an exact mapping review."""


def build_current_mapping_review(
    snapshot: object,
    *,
    registry: Mapping[str, object] | None = None,
    namespace_source: str = "pointer",
) -> dict[str, Any]:
    """Build one human-action packet from a prevalidated dashboard snapshot."""

    binding = _authority_binding(snapshot, namespace_source=namespace_source)
    market_rows = _exact_market_rows(snapshot, binding=binding)
    review = mapping_registry.build_mapping_review(market_rows)
    coverage = mapping_registry.assess_mapping_coverage(review, registry)
    template = mapping_registry.build_operator_registry_template(review)
    eligible = coverage["live_capture_mapping_eligible"] is True
    supplied = registry is not None
    status = (
        "mapping_review_complete"
        if eligible
        else "operator_registry_not_current"
        if supplied
        else "operator_action_required"
    )
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "authority_binding": binding,
        "mapping_review_sha256": _digest(review),
        "mapping_review": review,
        "coverage": coverage,
        "operator_registry_template": template,
        "template_status": "intentionally_invalid_until_human_completed",
        "template_required": not eligible,
        "registry_supplied": supplied,
        "registry_id": coverage.get("registry_id"),
        "registry_mode": coverage.get("registry_mode"),
        "human_decision_required": not eligible,
        "human_steps": [
            "Save only operator_registry_template as an operator-owned JSON file.",
            "Replace the registry ID, UTC review time, and reviewer alias placeholders.",
            "For every row choose mapped or not_applicable; never infer from name or symbol.",
            "For mapped rows enter exact DefiLlama list ID, slug, and protocol name.",
            "For every row add a review note and set reviewer_confirmed to true.",
            "Re-run the validation command against the completed JSON file.",
        ],
        "validation_make_command": (
            "make radar-fundamentals-defillama-mapping-review "
            "DEFILLAMA_MAPPING_REGISTRY=/absolute/path/operator-registry.json "
            "PYTHON=.venv/bin/python"
        ),
        "expected_provider_activity": "none",
        "provider_calls": 0,
        "writes": 0,
        "automatic_identity_inference": False,
        "template_is_evidence_authority": False,
        "mapping_eligibility_grants_provider_authorization": False,
        "protocol_v2_evidence_eligible": False,
        "automatic_policy_effect": "none",
        "research_only": True,
        "safety": {
            "telegram_sends": 0,
            "trades_created": 0,
            "paper_trades_created": 0,
            "normal_rsi_signal_rows_written": 0,
            "triggered_fade_created": 0,
        },
    }


def load_current_mapping_review(
    artifact_base_dir: str | Path,
    *,
    registry: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Resolve only the exact current pointer and build its review packet."""

    resolved = dashboard_readiness.resolve_authoritative_dashboard(artifact_base_dir)
    if resolved.namespace_source != "pointer":
        raise DefiLlamaCurrentMappingReviewError(
            "current_mapping_review_pointer_required"
        )
    return build_current_mapping_review(
        resolved.snapshot,
        registry=registry,
        namespace_source=resolved.namespace_source,
    )


def format_current_mapping_review_summary(result: Mapping[str, object]) -> str:
    """Render one bounded operator summary without duplicating the template."""

    binding = _mapping(result.get("authority_binding"), "authority_binding")
    coverage = _mapping(result.get("coverage"), "coverage")
    counts = _mapping(coverage.get("coverage_counts"), "coverage_counts")
    blockers = _text_sequence(
        coverage.get("live_capture_mapping_blockers"),
        "live_capture_mapping_blockers",
    )
    status = _text(result.get("status"), "status", 96)
    namespace = _text(
        binding.get("artifact_namespace"), "artifact_namespace", 192
    )
    revision = _nonnegative_int(binding.get("revision"), "revision")
    asset_count = _nonnegative_int(coverage.get("asset_count"), "asset_count")
    mapped = _nonnegative_int(counts.get("mapped"), "mapped")
    not_applicable = _nonnegative_int(
        counts.get("not_applicable"), "not_applicable"
    )
    unreviewed = _nonnegative_int(counts.get("unreviewed"), "unreviewed")
    identity_conflict = _nonnegative_int(
        counts.get("identity_conflict"), "identity_conflict"
    )
    if mapped + not_applicable + unreviewed + identity_conflict != asset_count:
        raise DefiLlamaCurrentMappingReviewError("coverage_count_mismatch")
    mapping_eligible = _boolean(
        coverage.get("live_capture_mapping_eligible"),
        "live_capture_mapping_eligible",
    )
    registry_supplied = _boolean(
        result.get("registry_supplied"), "registry_supplied"
    )
    human_required = _boolean(
        result.get("human_decision_required"), "human_decision_required"
    )
    automatic_inference = _boolean(
        result.get("automatic_identity_inference"),
        "automatic_identity_inference",
    )
    provider_calls = _nonnegative_int(
        result.get("provider_calls"), "provider_calls"
    )
    writes = _nonnegative_int(result.get("writes"), "writes")
    authorization_granted = _boolean(
        result.get("mapping_eligibility_grants_provider_authorization"),
        "mapping_eligibility_grants_provider_authorization",
    )
    protocol_eligible = _boolean(
        result.get("protocol_v2_evidence_eligible"),
        "protocol_v2_evidence_eligible",
    )
    expected_activity = _text(
        result.get("expected_provider_activity"),
        "expected_provider_activity",
        96,
    )
    validation_command = _text(
        result.get("validation_make_command"),
        "validation_make_command",
        512,
    )
    registry_mode = result.get("registry_mode")
    if registry_mode is None:
        registry_mode_text = "missing"
    else:
        registry_mode_text = _text(registry_mode, "registry_mode", 96)
    next_action = (
        "mapping prerequisite complete; preserve the reviewed registry and "
        "revalidate it after any universe change"
        if mapping_eligible
        else TEMPLATE_COMMAND
    )
    return "\n".join(
        (
            "report=decision_radar_defillama_mapping_review",
            f"status={status}",
            f"authority_namespace={namespace}",
            f"authority_revision={revision}",
            f"asset_count={asset_count}",
            (
                "coverage="
                f"mapped:{mapped},not_applicable:{not_applicable},"
                f"unreviewed:{unreviewed},identity_conflict:{identity_conflict}"
            ),
            f"registry_supplied={str(registry_supplied).lower()}",
            f"registry_mode={registry_mode_text}",
            f"mapping_eligible={str(mapping_eligible).lower()}",
            f"blockers={','.join(blockers) if blockers else 'none'}",
            f"human_decision_required={str(human_required).lower()}",
            f"automatic_identity_inference={str(automatic_inference).lower()}",
            f"expected_provider_activity={expected_activity}",
            f"provider_calls={provider_calls}",
            f"writes={writes}",
            f"provider_authorization_granted={str(authorization_granted).lower()}",
            f"protocol_v2_evidence_eligible={str(protocol_eligible).lower()}",
            f"next_safe_action={next_action}",
            f"validation_command={validation_command}",
            f"full_json_command={FULL_JSON_COMMAND}",
        )
    )


def _authority_binding(snapshot: object, *, namespace_source: str) -> dict[str, Any]:
    if namespace_source != "pointer":
        raise DefiLlamaCurrentMappingReviewError(
            "current_mapping_review_pointer_required"
        )
    if getattr(snapshot, "generation_authority_status", None) != "authoritative":
        raise DefiLlamaCurrentMappingReviewError(
            "current_mapping_review_authority_required"
        )
    namespace = _text(
        getattr(snapshot, "artifact_namespace", None), "artifact_namespace", 192
    )
    if not _NAMESPACE_RE.fullmatch(namespace):
        raise DefiLlamaCurrentMappingReviewError("artifact_namespace_invalid")
    run_id = _text(getattr(snapshot, "run_id", None), "run_id", 256)
    profile = _text(getattr(snapshot, "profile", None), "profile", 96)
    revision = getattr(snapshot, "revision", None)
    if type(revision) is not int or revision < 1:
        raise DefiLlamaCurrentMappingReviewError("revision_invalid")
    operator_digest = getattr(snapshot, "operator_state_sha256", None)
    if not isinstance(operator_digest, str) or not _SHA256_RE.fullmatch(
        operator_digest
    ):
        raise DefiLlamaCurrentMappingReviewError("operator_state_sha256_invalid")
    checked_at = _utc(
        getattr(snapshot, "generation_authority_checked_at", None),
        "authority_checked_at",
    )
    return {
        "namespace_source": "current_dashboard_pointer",
        "artifact_namespace": namespace,
        "run_id": run_id,
        "profile": profile,
        "revision": revision,
        "operator_state_sha256": operator_digest,
        "generation_authority_status": "authoritative",
        "authority_checked_at": checked_at,
    }


def _exact_market_rows(
    snapshot: object,
    *,
    binding: Mapping[str, object],
) -> list[dict[str, Any]]:
    generation = _mapping(
        getattr(snapshot, "market_generation", None), "market_generation"
    )
    if (
        generation.get("data_mode") != "live"
        or generation.get("provider") != "coingecko"
        or generation.get("provider_request_succeeded") is not True
        or generation.get("decision_radar_campaign_counted") is not True
        or generation.get("no_send") is not True
        or generation.get("research_only") is not True
    ):
        raise DefiLlamaCurrentMappingReviewError(
            "current_mapping_review_live_no_send_generation_required"
        )
    observations = getattr(snapshot, "current_market_observations", None)
    if (
        isinstance(observations, (str, bytes, bytearray))
        or not isinstance(observations, Sequence)
        or not observations
        or len(observations) > MAX_UNIVERSE_ROWS
    ):
        raise DefiLlamaCurrentMappingReviewError("current_market_observations_invalid")
    selected_count = generation.get("selected_market_row_count")
    if type(selected_count) is not int or selected_count != len(observations):
        raise DefiLlamaCurrentMappingReviewError(
            "current_market_observation_count_mismatch"
        )
    audit = _mapping(generation.get("universe_audit"), "universe_audit")
    kept = audit.get("kept")
    if (
        not isinstance(kept, list)
        or not kept
        or len(kept) > MAX_AUDIT_ROWS
        or any(not isinstance(row, Mapping) for row in kept)
    ):
        raise DefiLlamaCurrentMappingReviewError("universe_audit_kept_invalid")
    names: dict[str, tuple[str, str]] = {}
    for row in kept:
        coin_id = _text(row.get("id"), "universe_coin_id", 128)
        name = _text(row.get("name"), "universe_name", 128)
        symbol = _text(row.get("symbol"), "universe_symbol", 32).upper()
        if coin_id in names:
            raise DefiLlamaCurrentMappingReviewError(
                "universe_audit_coin_id_duplicate"
            )
        names[coin_id] = (name, symbol)

    market_rows: list[dict[str, Any]] = []
    expected_lineage = {
        "artifact_namespace": binding["artifact_namespace"],
        "run_id": binding["run_id"],
        "profile": binding["profile"],
    }
    for rank, raw in enumerate(observations, start=1):
        row = _mapping(raw, f"market_observation_{rank}")
        for field, expected in expected_lineage.items():
            if row.get(field) != expected:
                raise DefiLlamaCurrentMappingReviewError(
                    f"current_market_observation_{field}_mismatch"
                )
        coin_id = _text(row.get("coin_id"), "coin_id", 128)
        if coin_id not in names:
            raise DefiLlamaCurrentMappingReviewError(
                "current_market_observation_universe_identity_missing"
            )
        name, audit_symbol = names[coin_id]
        symbol = _text(row.get("symbol"), "symbol", 32).upper()
        if symbol != audit_symbol:
            raise DefiLlamaCurrentMappingReviewError(
                "current_market_observation_universe_symbol_mismatch"
            )
        market_rows.append(
            {
                "canonical_asset_id": row.get("canonical_asset_id"),
                "coin_id": coin_id,
                "symbol": symbol,
                "name": name,
                "liquidity_rank": rank,
            }
        )
    return market_rows


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DefiLlamaCurrentMappingReviewError(f"{field}_invalid")
    return value


def _text(value: object, field: str, limit: int) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text or len(text) > limit or any(ord(char) < 32 for char in text):
        raise DefiLlamaCurrentMappingReviewError(f"{field}_invalid")
    return text


def _text_sequence(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_UNIVERSE_ROWS:
        raise DefiLlamaCurrentMappingReviewError(f"{field}_invalid")
    return tuple(_text(item, field, 192) for item in value)


def _nonnegative_int(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise DefiLlamaCurrentMappingReviewError(f"{field}_invalid")
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise DefiLlamaCurrentMappingReviewError(f"{field}_invalid")
    return value


def _utc(value: object, field: str) -> str:
    text = _text(value, field, 64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DefiLlamaCurrentMappingReviewError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DefiLlamaCurrentMappingReviewError(f"{field}_invalid")
    return parsed.isoformat()


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-base", required=True)
    parser.add_argument(
        "--registry",
        type=Path,
        help="Optional operator-completed registry to validate against current authority",
    )
    parser.add_argument(
        "--output",
        choices=OUTPUT_CHOICES,
        default=OUTPUT_JSON,
        help="json preserves the full packet; summary is concise; template emits only the pending registry",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    registry = None
    if args.registry is not None:
        registry = mapping_registry.normalize_mapping_registry(
            args.registry.read_bytes()
        )
    result = load_current_mapping_review(args.artifact_base, registry=registry)
    if args.output == OUTPUT_SUMMARY:
        print(format_current_mapping_review_summary(result))
    elif args.output == OUTPUT_TEMPLATE:
        print(
            json.dumps(
                result["operator_registry_template"],
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = (
    "DefiLlamaCurrentMappingReviewError",
    "build_current_mapping_review",
    "format_current_mapping_review_summary",
    "load_current_mapping_review",
    "main",
)
