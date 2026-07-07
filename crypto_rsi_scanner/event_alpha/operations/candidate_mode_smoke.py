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
    run_id = f"{generated}|candidate_mode_fixture_smoke|{artifact_namespace}"
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
        row["run_id"] = run_id
        row["run_mode"] = "fixture"
    _write_jsonl(context.namespace_dir / "event_integrated_radar_candidates.jsonl", candidates)
    card_rows = _write_research_cards(context=context, candidates=candidates, generated=generated, profile=profile, artifact_namespace=artifact_namespace, run_id=run_id)
    _write_jsonl(
        context.namespace_dir / "event_core_opportunities.jsonl",
        [
            {
                "row_type": "event_core_opportunity",
                "core_opportunity_id": card_row["core_opportunity_id"],
                "candidate_id": row["candidate_id"],
                "symbol": row["symbol"],
                "coin_id": row["coin_id"],
                "profile": profile,
                "artifact_namespace": artifact_namespace,
                "run_id": run_id,
                "run_mode": "fixture",
                "opportunity_type": row["opportunity_type"],
                "opportunity_score": row["opportunity_score_final"],
                "source_origin": row["source_origin"],
                "source_pack": row["source_pack"],
                "candidate_provenance": "core_opportunity",
                "candidate_source_mode": "mocked_fixture",
                "contract_counted_candidate": False,
                "research_only": True,
                "no_send_rehearsal": True,
                "card_path": card_row["card_path"],
                "research_card_path": card_row["card_path"],
                "feedback_target": card_row["feedback_target"],
                "feedback_target_type": "core_opportunity_id",
                "strict_alerts_created": 0,
                "telegram_sends": 0,
                "trades_created": 0,
                "paper_trades_created": 0,
                "normal_rsi_signal_rows_written": 0,
                "triggered_fade_created": 0,
                "generated_at": generated,
            }
            for row, card_row in zip(candidates, card_rows, strict=True)
        ],
    )
    _write_support_artifacts(context=context, generated=generated, profile=profile, artifact_namespace=artifact_namespace)
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
            "research_cards_written": len(card_rows),
            "source_coverage_marker_written": True,
            "readiness_marker_written": True,
            "notification_preview_marker_written": True,
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


def _write_research_cards(
    *,
    context: Any,
    candidates: list[dict[str, Any]],
    generated: str,
    profile: str,
    artifact_namespace: str,
    run_id: str,
) -> list[dict[str, str]]:
    cards_dir = context.research_cards_dir
    cards_dir.mkdir(parents=True, exist_ok=True)
    for old_card in cards_dir.glob("*.md"):
        old_card.unlink()
    card_rows: list[dict[str, str]] = []
    grouped_links: dict[str, list[str]] = {"Unconfirmed Research Cards": []}
    index_lines = [
        "# Event Alpha Candidate-Mode Fixture Cards",
        "",
        "Research-only fixture cards. Not trade signals.",
        "",
    ]
    for row in candidates:
        core_id = row["candidate_id"].replace("mock:", "core:")
        filename = f"{core_id.replace(':', '_')}.md"
        path = cards_dir / filename
        rel = common.rel_path(path)
        feedback_target = core_id
        lines = [
            f"# {row['symbol']} {row['opportunity_type']}",
            "",
            "Research-only / unvalidated. Not a trade signal.",
            "",
            "## Fixture Candidate",
            "",
            f"- opportunity_type: {row['opportunity_type']}",
            "- candidate_source_mode: mocked_fixture",
            "- contract_counted_candidate: false",
            "- no_send_rehearsal: true",
            "- strict_alerts_created: 0",
            "- telegram_sends: 0",
            "- trades_created: 0",
            "- paper_trades_created: 0",
            "- normal_rsi_signal_rows_written: 0",
            "- triggered_fade_created: 0",
            "",
            "## Artifact Lineage",
            "",
            f"- Generated at: {generated}",
            "- Lineage status: current",
            "- legacy_lineage_missing: false",
            f"- Run ID: {run_id}",
            f"- Profile: {profile}",
            f"- Namespace: {artifact_namespace}",
            "- Incident ID: none",
            "- Hypothesis ID: none",
            f"- Watchlist key: {row['candidate_id']}",
            f"- Core opportunity ID: {core_id}",
            "- Alert ID: none",
            "- Snapshot ID: none",
            "- Source row type: event_integrated_radar_candidate",
            f"- Integrated candidate ID: {row['candidate_id']}",
            "- Source raw/event IDs: raw=none events=none",
            f"- Card path: {rel}",
            f"- Feedback target: {feedback_target}",
            "- Feedback target type: core_opportunity_id",
            f"- Feedback command useful: make event-feedback-useful PROFILE={profile} FEEDBACK_TARGET='{feedback_target}'",
            f"- Feedback command junk: make event-feedback-junk PROFILE={profile} FEEDBACK_TARGET='{feedback_target}'",
            f"- Feedback command watch: make event-feedback-watch PROFILE={profile} FEEDBACK_TARGET='{feedback_target}'",
            f"- Cluster ID: {row['symbol'].lower()}:candidate-mode-fixture",
        ]
        common.write_text(path, "\n".join(lines))
        grouped_links["Unconfirmed Research Cards"].append(f"- [{filename}]({filename})")
        card_rows.append({"core_opportunity_id": core_id, "card_path": rel, "feedback_target": feedback_target})
    for group, links in grouped_links.items():
        index_lines.extend([f"## {group}", ""])
        index_lines.extend(links or ["- none"])
        index_lines.append("")
    common.write_text(cards_dir / "index.md", "\n".join(index_lines))
    return card_rows


def _write_support_artifacts(*, context: Any, generated: str, profile: str, artifact_namespace: str) -> None:
    readiness = common.with_safety(
        {
            "schema_version": "event_alpha_live_provider_activation_readiness_v1",
            "row_type": "event_alpha_live_provider_activation_readiness",
            "generated_at": generated,
            "profile": profile,
            "artifact_namespace": artifact_namespace,
            "smoke_mode": True,
            "candidate_source_mode": "mocked_fixture",
            "fixture_smoke_marker": True,
            "live_calls_allowed": False,
            "providers": [
                {"provider": "coinalyze", "configured": False, "live_call_allowed": False, "preflight_status": "fixture_smoke_marker"},
                {"provider": "bybit_announcements", "configured": False, "live_call_allowed": False, "preflight_status": "fixture_smoke_marker"},
            ],
        }
    )
    common.write_json(context.namespace_dir / "event_live_provider_activation_readiness.json", readiness)
    common.write_text(
        context.namespace_dir / "event_live_provider_activation_readiness.md",
        "\n".join(
            [
                "# Event Alpha Live-Provider Activation Readiness",
                "",
                "- fixture_smoke_marker: true",
                "- candidate_source_mode: mocked_fixture",
                "- live_calls_allowed: false",
                "- Coinalyze: fixture marker only",
                "- Bybit announcements: fixture marker only",
            ]
        ),
    )
    source_coverage = common.with_safety(
        {
            "schema_version": "event_alpha_source_coverage_v1",
            "row_type": "event_alpha_source_coverage",
            "generated_at": generated,
            "profile": profile,
            "artifact_namespace": artifact_namespace,
            "fixture_smoke_marker": True,
            "candidate_source_mode": "mocked_fixture",
            "source_pack_coverage_status": "fixture_smoke_marker",
            "live_provider_readiness_path": common.rel_path(context.namespace_dir / "event_live_provider_activation_readiness.json"),
        }
    )
    common.write_json(context.namespace_dir / "event_alpha_source_coverage.json", source_coverage)
    common.write_text(
        context.namespace_dir / "event_alpha_source_coverage.md",
        "\n".join(
            [
                "# Event Alpha Source Coverage",
                "",
                "Live-provider activation readiness: event_live_provider_activation_readiness.md / event_live_provider_activation_readiness.json",
                "",
                "Most useful next data source categories:",
                "- derivatives/OI/funding: fixture smoke marker",
                "- official exchange announcements: fixture smoke marker",
                "- structured unlock/calendar: fixture smoke marker",
                "",
                "Recommended next activation order",
                "- Coinalyze derivatives/OI/funding",
                "- Bybit/Binance official announcements",
                "- Structured unlock/calendar",
            ]
        ),
    )
    common.write_text(
        context.namespace_dir / "event_alpha_notification_preview.md",
        "\n".join(
            [
                "# Event Alpha Notification Preview",
                "",
                "No Telegram send was attempted.",
                "",
                "- candidate_source_mode: mocked_fixture",
                "- skipped_reason: fixture candidate-mode smoke",
                "- strict_alerts_created: 0",
                "- telegram_sends: 0",
                "- trades_created: 0",
                "- paper_trades_created: 0",
                "- normal_rsi_signal_rows_written: 0",
                "- triggered_fade_created: 0",
            ]
        ),
    )
