"""Deterministic mocked candidate-mode smoke artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import common


def write_candidate_mode_fixture_artifacts(
    *,
    profile: str,
    artifact_namespace: str,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    context = common.context_for(profile=profile, artifact_namespace=artifact_namespace, base_dir=base_dir)
    context.namespace_dir.mkdir(parents=True, exist_ok=True)
    generated = common.utc_now().isoformat()
    candidates = [
        _fixture_candidate("mock:early", "TESTLIST", "testlist", "EARLY_LONG_RESEARCH", "bybit_announcements", "official_exchange_listing_pack", "official_listing_no_reaction", 72),
        _fixture_candidate("mock:confirmed", "TESTPERP", "testperp", "CONFIRMED_LONG_RESEARCH", "bybit_announcements", "official_exchange_listing_pack", "official_listing_market_breakout", 84, market_state="breakout_confirmed"),
        _fixture_candidate("mock:fade", "TESTFADE", "testfade", "FADE_SHORT_REVIEW", "coinalyze", "derivatives_crowding", "crowding_exhaustion_review", 88, market_state="completed_move", crowding_class="extreme"),
        _fixture_candidate("mock:risk", "TESTRISK", "testrisk", "RISK_ONLY", "bybit_announcements", "official_exchange_risk_pack", "delisting_or_unlock_risk", 69),
        _fixture_candidate("mock:unconfirmed", "TESTUNC", "testunc", "UNCONFIRMED_RESEARCH", "cryptopanic_context", "cryptopanic_context", "context_without_confirmation", 41),
    ]
    for row in candidates:
        row["generated_at"] = generated
        row["profile"] = profile
        row["artifact_namespace"] = artifact_namespace
    _write_jsonl(context.namespace_dir / "event_integrated_radar_candidates.jsonl", candidates)
    _write_jsonl(
        context.namespace_dir / "event_core_opportunities.jsonl",
        [
            {
                "row_type": "event_core_opportunity",
                "core_opportunity_id": row["candidate_id"].replace("mock:", "core:"),
                "candidate_id": row["candidate_id"],
                "symbol": row["symbol"],
                "coin_id": row["coin_id"],
                "opportunity_type": row["opportunity_type"],
                "candidate_source_mode": "mocked_fixture",
                "contract_counted_candidate": False,
                "research_only": True,
                "no_send_rehearsal": True,
                "generated_at": generated,
            }
            for row in candidates
        ],
    )
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_candidate_mode_fixture_smoke_v1",
            "row_type": "event_alpha_candidate_mode_fixture_smoke",
            "generated_at": generated,
            "profile": profile,
            "artifact_namespace": artifact_namespace,
            "candidate_source_mode": "mocked_fixture",
            "candidate_count": len(candidates),
            "lanes": sorted({row["opportunity_type"] for row in candidates}),
            "contract_counted_candidate_count": 0,
            "live_calls_attempted": 0,
        }
    )
    common.write_json(context.namespace_dir / "event_alpha_candidate_mode_fixture_smoke.json", payload)
    return payload


def _fixture_candidate(
    candidate_id: str,
    symbol: str,
    coin_id: str,
    lane: str,
    provider: str,
    source_pack: str,
    evidence_status: str,
    score: int,
    *,
    market_state: str = "pending_confirmation",
    crowding_class: str = "",
) -> dict[str, Any]:
    return {
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": candidate_id,
        "symbol": symbol,
        "coin_id": coin_id,
        "opportunity_type": lane,
        "opportunity_score_final": score,
        "provider": provider,
        "source_origin": provider,
        "source_pack": source_pack,
        "source_artifact": "event_alpha_candidate_mode_fixture_smoke.json",
        "candidate_provenance": "integrated_candidate",
        "candidate_source_mode": "mocked_fixture",
        "contract_counted_candidate": False,
        "fixture_only": True,
        "test_fixture": True,
        "research_only": True,
        "no_send_rehearsal": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "evidence_status": evidence_status,
        "market_state_class": market_state,
        "crowding_class": crowding_class,
        "what_confirms": "mocked fixture confirmation only; not contract counted",
        "what_invalidates": "fixture smoke rows are diagnostic and never authorize sends or trades",
        "why_not_alertable": "mocked fixture candidate-mode smoke",
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
