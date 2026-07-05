"""Core opportunity evidence acquisition view helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import (
    config,
)
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ...artifacts import paths as event_artifact_paths
from .. import core_opportunities as event_core_opportunities
from .. import market_reaction as event_market_reaction
from .. import opportunity_verdict as event_opportunity_verdict
from .models import *  # noqa: F403 - split modules share historical model names


def _acquisition_candidate_rows(rows: Iterable[Mapping[str, Any] | object]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in rows:
        row = _row_dict(item)
        merged = _row_with_score_components(row)
        if _row_has_acquisition_metadata(merged):
            out.append(merged)
    return out


def _build_core_evidence_acquisition_view(
    core_opportunity_id: str,
    rows: Iterable[Mapping[str, Any]],
) -> CoreEvidenceAcquisitionView:
    clean_core = str(core_opportunity_id or "").strip()
    primary: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for raw in rows:
        row = _row_with_score_components(raw)
        if not _row_has_acquisition_metadata(row):
            continue
        if _is_diagnostic_acquisition_row(row, clean_core):
            diagnostics.append(dict(row))
        else:
            primary.append(dict(row))
    if not primary:
        return CoreEvidenceAcquisitionView(
            core_opportunity_id=clean_core,
            diagnostic_rows=tuple(_unique_rows(diagnostics)),
        )

    accepted_samples = _unique_evidence_samples(
        sample
        for row in primary
        for sample in _evidence_samples(row, ("evidence_acquisition_accepted_evidence", "accepted_evidence"))
    )
    rejected_samples = _unique_evidence_samples(
        sample
        for row in primary
        for sample in _evidence_samples(row, ("evidence_acquisition_rejected_samples", "rejected_evidence_samples", "rejected_evidence"))
    )
    accepted_count = max(
        len(accepted_samples),
        *(_int_or_zero(_nested_result_value(row, "accepted")) for row in primary),
        *(_int_or_zero(_first_value([row], ("evidence_acquisition_accepted_count", "accepted_evidence_count"))) for row in primary),
    )
    rejected_count = max(
        len(rejected_samples),
        *(_int_or_zero(_nested_result_value(row, "rejected")) for row in primary),
        *(_int_or_zero(_first_value([row], ("evidence_acquisition_rejected_count", "rejected_evidence_count"))) for row in primary),
    )
    accepted_reasons = _unique_strings(
        [
            *(
                str(reason)
                for row in primary
                for reason in _first_list([row], ("accepted_evidence_reason_codes",))
                if str(reason or "").strip()
            ),
            *(
                str(reason)
                for sample in accepted_samples
                for reason in _as_list_values(sample.get("reason_codes"))
                if str(reason or "").strip()
            ),
        ]
    )
    rejected_reasons = _unique_strings(
        [
            *(
                str(reason)
                for row in primary
                for reason in _first_list([row], ("rejected_evidence_reason_codes",))
                if str(reason or "").strip()
            ),
            *(
                str(reason)
                for sample in rejected_samples
                for reason in _as_list_values(sample.get("reason_codes"))
                if str(reason or "").strip()
            ),
        ]
    )
    accepted_provider_counts = _merge_count_maps(row.get("accepted_provider_counts") for row in primary)
    rejected_provider_counts = _merge_count_maps(row.get("rejected_provider_counts") for row in primary)
    accepted_reason_code_counts = _merge_count_maps(row.get("accepted_reason_code_counts") for row in primary)
    provider_failures = _unique_strings(
        failure
        for row in primary
        for failure in (
            *tuple(_first_list([row], ("evidence_acquisition_provider_failures", "provider_failures", "provider_coverage_gaps"))),
            *tuple(_query_provider_failures(row)),
        )
        if str(failure or "").strip()
    )
    status = _best_acquisition_status(primary, accepted_count=accepted_count, rejected_count=rejected_count)
    source_pack = _best_source_pack(primary, _first_text(primary, ("impact_path_type", "primary_impact_path")))
    return CoreEvidenceAcquisitionView(
        core_opportunity_id=clean_core,
        acquisition_attempted=_any_truthy(primary, ("evidence_acquisition_attempted", "source_acquisition_attempted")) or status != "not_executed",
        acquisition_status=status,
        source_pack=source_pack,
        accepted_evidence_count=accepted_count,
        rejected_evidence_count=rejected_count,
        accepted_reason_codes=tuple(accepted_reasons),
        rejected_reason_codes=tuple(rejected_reasons),
        accepted_provider_counts=accepted_provider_counts,
        rejected_provider_counts=rejected_provider_counts,
        accepted_reason_code_counts=accepted_reason_code_counts,
        accepted_evidence_samples=tuple(accepted_samples[:5]),
        rejected_evidence_samples=tuple(rejected_samples[:5]),
        provider_failures=tuple(provider_failures),
        evidence_quality_before=_first_float(primary, ("evidence_quality_before", "evidence_acquisition_score_before", "evidence_quality_score_before")),
        evidence_quality_after=_best_float(primary, ("evidence_quality_after", "evidence_acquisition_score_after", "evidence_quality_score_after", "post_refresh_evidence_quality_score")),
        opportunity_score_before=_first_float(primary, ("opportunity_score_before", "opportunity_score_before_acquisition", "initial_opportunity_score")),
        opportunity_score_after=_best_float(primary, ("opportunity_score_after", "opportunity_score_after_acquisition", "post_refresh_opportunity_score", "final_opportunity_score", "opportunity_score_final")),
        opportunity_level_before=_first_text(primary, ("opportunity_level_before", "opportunity_level_before_acquisition", "initial_opportunity_level")),
        opportunity_level_after=_first_text(primary, ("opportunity_level_after", "opportunity_level_after_acquisition", "post_refresh_opportunity_level", "final_opportunity_level", "opportunity_level")),
        final_upgrade_status=_first_text(primary, ("final_upgrade_status", "acquisition_upgrade_status")),
        no_upgrade_reason=_first_text(primary, ("no_upgrade_reason",)),
        diagnostic_rows=tuple(_unique_rows(diagnostics)),
    )
