"""Human-facing text helpers for Event Alpha reason/action codes."""

from __future__ import annotations

from typing import Iterable


REASON_TEXT = {
    "quality_context_missing": "missing enough validated context",
    "needs_direct_token_mechanism": "needs proof that this event directly affects the token",
    "explained_token_impact_path": "needs an explained catalyst-to-token impact path",
    "needs_market_confirmation": "no convincing price/volume confirmation yet",
    "market_confirmation": "no convincing price/volume confirmation yet",
    "needs_strong_market_confirmation": "needs stronger price/volume confirmation",
    "market_confirmation_level": "needs clearer market confirmation",
    "cause_unknown_market_dislocation": "token moved, but the cause is still unknown",
    "generic_cooccurrence_only": "token and event appeared together, but no impact mechanism was proven",
    "impact_path_type_insufficient_data": "not enough evidence to establish the impact mechanism",
    "impact_path_not_strong_enough": "impact path is too weak for alerting",
    "impact_path_not_validated": "impact path has not been validated",
    "weak_impact_path_despite_market_confirmation": "market moved, but the impact path is still weak",
    "missing_direct_impact_path": "missing a direct catalyst-to-token impact path",
    "needs_impact_path_validation": "needs validated catalyst-to-token impact path",
    "needs_identity_validation": "needs deterministic asset identity validation",
    "candidate_discovery_pending": "candidate still needs resolver-confirmed asset identity",
    "no_value_capture_explained": "no token value-capture mechanism was explained",
    "no_value_capture": "no token value-capture mechanism is visible",
    "weak_cooccurrence_only": "weak token/catalyst co-occurrence only",
    "generic_policy_only": "generic policy context only",
    "source_low_quality": "needs a stronger independent source",
    "needs_higher_quality_source": "needs a stronger independent source",
    "blocked_by_low_score": "research score is still too low",
    "score_below_promotion_threshold": "research score is below the promotion threshold",
    "blocked_by_source_noise": "source/noise risk is still too high",
    "source_noise": "likely source/noise artifact",
    "source_noise_control": "source/noise control row",
    "ticker_collision": "ticker/common-word collision risk",
    "ticker_word_collision": "ticker/common-word collision risk",
    "common_phrase_not_asset_identity": "common phrase is not asset identity",
    "common_word_or_title_not_asset_identity": "common word or title is not asset identity",
    "generic_symbol_without_project_identity": "generic ticker word without project identity",
    "publisher_source_name_not_asset_identity": "publisher/source name is not asset identity",
    "source_origin_only_identity": "publisher/source origin does not prove asset identity",
    "identity_low_confidence": "asset identity confidence is too low",
    "rejected_candidate_asset": "candidate asset evidence was rejected",
    "invalid_subject": "source subject does not match the candidate asset",
    "diagnostic_only": "diagnostic/control row only",
    "quality_state_capped": "quality verdict capped the lifecycle state",
    "quality_gate_blocked": "quality gate blocked promotion",
}


ACTION_TEXT = {
    "targeted_market_refresh": "refresh market/volume context",
    "targeted_derivatives_refresh": "check OI/funding/derivatives crowding",
    "targeted_supply_refresh": "check unlock/supply pressure",
    "targeted_evidence_refresh": "find independent catalyst evidence",
    "operator_review": "manual analyst review",
}


def humanize_event_alpha_reason(reason: object) -> str:
    """Translate a stable Event Alpha reason code into concise operator text."""
    text = str(reason or "").strip()
    if not text:
        return ""
    return REASON_TEXT.get(text, text.replace("_", " "))


def humanize_event_alpha_reasons(reasons: Iterable[object], *, limit: int = 5) -> str:
    """Translate and dedupe a sequence of Event Alpha reason codes."""
    translated = [humanize_event_alpha_reason(reason) for reason in reasons]
    translated = [reason for reason in translated if reason]
    return "; ".join(dict.fromkeys(translated[: max(1, limit)]))


def humanize_event_alpha_action(action: object) -> str:
    text = str(action or "").strip()
    if not text:
        return ""
    return ACTION_TEXT.get(text, text.replace("_", " "))


def humanize_event_alpha_actions(actions: Iterable[object], *, limit: int = 5) -> str:
    translated = [humanize_event_alpha_action(action) for action in actions]
    translated = [action for action in translated if action]
    return "; ".join(dict.fromkeys(translated[: max(1, limit)]))
