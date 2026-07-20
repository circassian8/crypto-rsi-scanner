"""Source Coverage Checks for the artifact doctor."""

from __future__ import annotations

from .runtime import *
from .integrated_radar_checks import _raw_int_value
from .notification_checks import _read_card_text
from .notification_delivery_checks import _as_int, _latest_run_id

def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)

def _source_coverage_metadata_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "source_pack_provider_status_missing": 0,
        "missing_provider_recommendations_missing": 0,
        "degraded_provider_absence_marked_meaningful": 0,
    }
    for row in rows:
        source_pack = str(row.get("source_pack") or row.get("evidence_acquisition_source_pack") or "").strip()
        if not source_pack:
            continue
        status = str(row.get("source_pack_coverage_status") or row.get("provider_coverage_status") or "").strip()
        has_source_coverage_metadata = any(
            key in row
            for key in (
                "source_pack_coverage_status",
                "provider_coverage_status",
                "providers_missing_for_confirmation",
                "providers_degraded_for_confirmation",
                "source_coverage_recommended_actions",
                "recommended_actions",
            )
        )
        if has_source_coverage_metadata and not status:
            out["source_pack_provider_status_missing"] += 1
        missing = _tuple_value(row.get("providers_missing_for_confirmation"))
        degraded = _tuple_value(row.get("providers_degraded_for_confirmation"))
        recs = _tuple_value(row.get("source_coverage_recommended_actions") or row.get("recommended_actions"))
        if (missing or degraded) and not recs:
            out["missing_provider_recommendations_missing"] += 1
        absence = _truthy(row.get("evidence_absence_is_meaningful")) or _truthy(
            row.get("evidence_absence_meaningful")
        )
        if status in {"degraded", "unavailable", "not_configured"} and absence:
            out["degraded_provider_absence_marked_meaningful"] += 1
    return out

def _source_coverage_report_conflicts(path: str | Path | None) -> dict[str, int]:
    out = {
        "source_coverage_report_missing": 0,
        "source_coverage_provider_status_unknown": 0,
        "source_coverage_provider_marked_healthy_without_observation": 0,
        "source_coverage_category_priority_missing": 0,
        "source_coverage_readiness_link_missing": 0,
        "source_coverage_context_provider_ranked_above_lane_critical": 0,
        "source_coverage_coinalyze_missing_linked_artifact": 0,
        "source_coverage_bybit_announcements_missing_linked_artifact": 0,
        "source_coverage_unlock_calendar_missing_linked_artifact": 0,
        "source_coverage_dex_onchain_missing_linked_artifact": 0,
    }
    if path is None:
        return out
    report_path = Path(path)
    if not report_path.exists():
        if _source_coverage_report_required(report_path.parent):
            out["source_coverage_report_missing"] = 1
        return out
    try:
        text = report_path.read_text(encoding="utf-8")
    except OSError:
        out["source_coverage_report_missing"] = 1
        return out
    out["source_coverage_provider_status_unknown"] = text.count("provider coverage status: unknown")
    unknown_provider_lines = [
        line for line in text.splitlines()
        if line.strip().startswith("unknown/not observed providers:")
        and line.rsplit(":", 1)[-1].strip() not in {"", "none"}
    ]
    out["source_coverage_provider_status_unknown"] += len(unknown_provider_lines)
    blocks = text.split("\n- ")
    for block in blocks:
        healthy_line = next(
            (line for line in block.splitlines() if line.strip().startswith("healthy providers:")),
            "",
        )
        not_observed_line = next(
            (
                line
                for line in block.splitlines()
                if line.strip().startswith(("unknown/not observed providers:", "skipped/not observed providers:"))
            ),
            "",
        )
        healthy = set(_split_provider_line(healthy_line))
        not_observed = set(_split_provider_line(not_observed_line))
        if healthy & not_observed:
            out["source_coverage_provider_marked_healthy_without_observation"] += len(healthy & not_observed)
    if "Most useful next data source categories:" not in text:
        out["source_coverage_category_priority_missing"] = 1
    for artifact_name in (
        event_coinalyze_preflight.PREFLIGHT_JSON,
        event_coinalyze_preflight.PREFLIGHT_MD,
        event_coinalyze_preflight.REHEARSAL_JSON,
        event_coinalyze_preflight.REHEARSAL_MD,
        event_coinalyze_preflight.REQUEST_LEDGER,
    ):
        if artifact_name in text and not (report_path.parent / artifact_name).exists():
            out["source_coverage_coinalyze_missing_linked_artifact"] += 1
    for artifact_name in (
        event_bybit_announcements_preflight.PREFLIGHT_JSON,
        event_bybit_announcements_preflight.PREFLIGHT_MD,
        event_bybit_announcements_preflight.REHEARSAL_JSON,
        event_bybit_announcements_preflight.REHEARSAL_MD,
        event_bybit_announcements_preflight.REQUEST_LEDGER,
    ):
        if artifact_name in text and not (report_path.parent / artifact_name).exists():
            out["source_coverage_bybit_announcements_missing_linked_artifact"] += 1
    for artifact_name in (
        event_unlock_calendar_preflight.PREFLIGHT_JSON,
        event_unlock_calendar_preflight.PREFLIGHT_MD,
        event_unlock_calendar_preflight.REQUEST_LEDGER,
    ):
        if artifact_name in text and not (report_path.parent / artifact_name).exists():
            out["source_coverage_unlock_calendar_missing_linked_artifact"] += 1
    for artifact_name in (
        event_dex_onchain_readiness.READINESS_JSON,
        event_dex_onchain_readiness.READINESS_MD,
        event_dex_onchain_readiness.DEX_POOL_STATE_FILENAME,
        event_dex_onchain_readiness.DEX_POOL_ANOMALIES_FILENAME,
        event_dex_onchain_readiness.PROTOCOL_FUNDAMENTALS_FILENAME,
    ):
        if artifact_name in text and not (report_path.parent / artifact_name).exists():
            out["source_coverage_dex_onchain_missing_linked_artifact"] += 1
    readiness_present = "Live-provider activation readiness:" in text
    readiness_md_path = report_path.parent / event_alpha_source_coverage.LIVE_PROVIDER_READINESS_MD
    readiness_json_path = report_path.parent / event_alpha_source_coverage.LIVE_PROVIDER_READINESS_JSON
    readiness_artifact_exists = readiness_md_path.exists() or readiness_json_path.exists()
    readiness_command_present = "event-alpha-live-provider-readiness" in text
    if readiness_artifact_exists:
        if not readiness_present or (
            event_alpha_source_coverage.LIVE_PROVIDER_READINESS_MD not in text
            and event_alpha_source_coverage.LIVE_PROVIDER_READINESS_JSON not in text
        ):
            out["source_coverage_readiness_link_missing"] = 1
    elif not readiness_present or not readiness_command_present:
        out["source_coverage_readiness_link_missing"] = 1
    if "Recommended next activation order" not in text and "Most useful next data source categories:" not in text:
        out["source_coverage_readiness_link_missing"] = 1
    if "Most useful next data source categories:" in text:
        category_section = text.split("Most useful next data source categories:", 1)[1]
        category_section = category_section.split("Most useful next data source:", 1)[0]
        category_lower = category_section.casefold()
        context_pos = min(
            (pos for token in ("context/news", "cryptopanic", "rss", "gdelt") if (pos := category_lower.find(token)) >= 0),
            default=-1,
        )
        critical_pos = min(
            (
                pos
                for token in ("derivatives/oi/funding", "official exchange announcements", "structured unlock/calendar")
                if (pos := category_lower.find(token)) >= 0
            ),
            default=-1,
        )
        if context_pos >= 0 and critical_pos >= 0 and context_pos < critical_pos:
            out["source_coverage_context_provider_ranked_above_lane_critical"] = 1
    if "Most useful next data source:" in text:
        top_section = text.split("Most useful next data source:", 1)[1]
        ranked = [line.strip() for line in top_section.splitlines() if line.strip().startswith("- ")][:5]
        full_ranked_section = "\n".join(
            line.strip() for line in top_section.splitlines() if line.strip().startswith("- ")
        )
        broad_idx = [
            idx for idx, line in enumerate(ranked)
            if any(token in line.casefold() for token in ("gdelt", "rss", "project_blog"))
        ]
        critical_idx = [
            idx for idx, line in enumerate(ranked)
            if any(token in line.casefold() for token in ("coinalyze", "tokenomist", "binance", "bybit", "coinbase", "kucoin", "okx"))
        ]
        if broad_idx and critical_idx and min(broad_idx) < min(critical_idx):
            out["source_coverage_context_provider_ranked_above_lane_critical"] = 1
        coinalyze_gap = bool(
            re.search(
                r"(missing|degraded|backoff|not configured|not_configured)[^\n]{0,120}coinalyze"
                r"|coinalyze[^\n]{0,120}(missing|degraded|backoff|not configured|not_configured)",
                text,
                re.IGNORECASE,
            )
        )
        if coinalyze_gap and "coinalyze" not in full_ranked_section.casefold():
            out["source_coverage_context_provider_ranked_above_lane_critical"] = 1
    return out

def _live_provider_readiness_conflicts(namespace_dir: str | Path | None) -> dict[str, int]:
    out = {
        "live_provider_readiness_missing": 0,
        "live_provider_readiness_secret_leak": 0,
        "live_provider_readiness_live_calls_allowed_in_smoke": 0,
        "live_provider_readiness_configured_missing_env": 0,
        "live_provider_readiness_fixture_live_state_conflict": 0,
    }
    if namespace_dir is None:
        return out
    base = Path(namespace_dir)
    json_path = base / event_live_provider_readiness.READINESS_JSON
    md_path = base / event_live_provider_readiness.READINESS_MD
    if not json_path.exists() and not md_path.exists():
        if _live_provider_readiness_required(base):
            out["live_provider_readiness_missing"] = 1
        return out
    texts: list[str] = []
    for path in (json_path, md_path):
        if not path.exists():
            continue
        try:
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            out["live_provider_readiness_missing"] = 1
    joined = "\n".join(texts)
    if _text_has_secret_like_value(joined):
        out["live_provider_readiness_secret_leak"] = 1
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, Mapping):
            smoke = bool(data.get("smoke_mode"))
            if smoke and bool(data.get("live_calls_allowed")):
                out["live_provider_readiness_live_calls_allowed_in_smoke"] += 1
            for provider in data.get("providers") or ():
                if not isinstance(provider, Mapping):
                    continue
                if smoke and bool(provider.get("live_call_allowed")):
                    out["live_provider_readiness_live_calls_allowed_in_smoke"] += 1
                if bool(provider.get("configured")) and str(provider.get("preflight_status") or "") == "missing_config":
                    out["live_provider_readiness_configured_missing_env"] += 1
                if str(provider.get("configuration_scope") or "") == "fixture_input_only" and (
                    bool(provider.get("configured"))
                    or bool(provider.get("live_call_allowed"))
                    or bool(provider.get("live_rehearsal_eligible"))
                    or str(provider.get("live_transport_status") or "") != "not_implemented"
                ):
                    out["live_provider_readiness_fixture_live_state_conflict"] += 1
    return out

def _text_has_secret_like_value(text: str) -> bool:
    patterns = (
        r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        r"\bghp_[A-Za-z0-9_]{20,}",
        r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9._-]{20,}['\"]",
        r"(?i)(api[_-]?key|secret|token)\s+[A-Za-z0-9._-]{24,}",
    )
    return any(re.search(pattern, text) for pattern in patterns)

def _source_coverage_report_required(namespace_dir: Path) -> bool:
    """Return true for namespaces that claim source/evidence/provider coverage."""

    required_markers = (
        "event_integrated_radar_candidates.jsonl",
        "event_evidence_acquisition.jsonl",
        "event_live_provider_activation_readiness.json",
        "event_live_provider_activation_readiness.md",
        "event_coinalyze_preflight.json",
        "event_coinalyze_preflight.md",
        "event_coinalyze_rehearsal_report.json",
        "event_coinalyze_rehearsal_report.md",
        "event_coinalyze_request_ledger.jsonl",
        "event_bybit_announcements_preflight.json",
        "event_bybit_announcements_preflight.md",
        "event_bybit_announcements_rehearsal_report.json",
        "event_bybit_announcements_rehearsal_report.md",
        "event_bybit_announcements_request_ledger.jsonl",
        "event_unlock_calendar_preflight.json",
        "event_unlock_calendar_preflight.md",
        "event_unlock_calendar_request_ledger.jsonl",
        event_dex_onchain_readiness.READINESS_JSON,
        event_dex_onchain_readiness.READINESS_MD,
        event_dex_onchain_readiness.DEX_POOL_STATE_FILENAME,
        event_dex_onchain_readiness.DEX_POOL_ANOMALIES_FILENAME,
        event_dex_onchain_readiness.PROTOCOL_FUNDAMENTALS_FILENAME,
        "event_official_exchange_activation.json",
        "event_official_exchange_activation.md",
        "cryptopanic_request_ledger.jsonl",
    )
    return any((namespace_dir / name).exists() for name in required_markers)

def _live_provider_readiness_required(namespace_dir: Path) -> bool:
    """Pure notification-format smoke namespaces do not claim live-provider readiness."""

    if (namespace_dir / "event_live_provider_activation_readiness.json").exists():
        return True
    if (namespace_dir / "event_live_provider_activation_readiness.md").exists():
        return True
    required_markers = (
        "event_alpha_source_coverage.json",
        "event_integrated_radar_candidates.jsonl",
        "event_coinalyze_preflight.json",
        "event_coinalyze_preflight.md",
        "event_coinalyze_rehearsal_report.json",
        "event_coinalyze_rehearsal_report.md",
        "event_bybit_announcements_preflight.json",
        "event_bybit_announcements_preflight.md",
        "event_bybit_announcements_rehearsal_report.json",
        "event_bybit_announcements_rehearsal_report.md",
        "event_unlock_calendar_preflight.json",
        "event_unlock_calendar_preflight.md",
        event_dex_onchain_readiness.READINESS_JSON,
        event_dex_onchain_readiness.READINESS_MD,
        "event_official_exchange_activation.json",
        "event_official_exchange_activation.md",
    )
    return any((namespace_dir / name).exists() for name in required_markers)

def _cryptopanic_artifact_conflicts(
    *,
    acquisition_rows: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    research_card_paths: Iterable[Path],
    source_coverage_report_path: str | Path | None,
    run_rows: Iterable[Mapping[str, Any]] = (),
) -> dict[str, int]:
    out = _empty_cryptopanic_artifact_conflicts()
    source_path = Path(source_coverage_report_path) if source_coverage_report_path is not None else None
    source_text, source_payload, exact_run, readiness_row = _cryptopanic_source_context(
        source_path,
        run_rows=run_rows,
    )
    _add_source_conflict_counts(
        out,
        _cryptopanic_source_state_conflicts(
            source_text=source_text,
            source_payload=source_payload,
            exact_run=exact_run,
            readiness_row=readiness_row,
            core_rows=core_rows,
        ),
    )
    acquisition = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    cryptopanic_used = any(_row_mentions_cryptopanic(row) for row in acquisition)
    _add_source_conflict_counts(
        out,
        _cryptopanic_evidence_conflicts(
            acquisition=acquisition,
            core_rows=core_rows,
            research_card_paths=research_card_paths,
            source_text=source_text,
            cryptopanic_used=cryptopanic_used,
        ),
    )
    ledger_path = source_path.with_name("cryptopanic_request_ledger.jsonl") if source_path is not None else None
    ledger_rows = _load_jsonl_rows(ledger_path) if ledger_path is not None else ()
    if cryptopanic_used and ledger_path is not None and not ledger_path.exists():
        out["cryptopanic_request_ledger_missing_when_used"] = 1
    _add_source_conflict_counts(out, _cryptopanic_ledger_conflicts(ledger_rows, source_text=source_text))
    combined_text = source_text + "\n" + "\n".join(_read_card_text(path) for path in research_card_paths)
    if _contains_unredacted_cryptopanic_secret(combined_text):
        out["cryptopanic_token_printed_or_unredacted"] = 1
    return out


def _empty_cryptopanic_artifact_conflicts() -> dict[str, int]:
    return {
        "cryptopanic_configured_but_not_observed": 0,
        "cryptopanic_used_but_no_source_coverage_entry": 0,
        "cryptopanic_accepted_evidence_missing_from_card": 0,
        "cryptopanic_rejected_only_promoted": 0,
        "cryptopanic_token_printed_or_unredacted": 0,
        "cryptopanic_growth_unsupported_param_used": 0,
        "cryptopanic_duplicate_request_key": 0,
        "cryptopanic_invalid_currency_code": 0,
        "cryptopanic_empty_currency_request": 0,
        "cryptopanic_coin_id_sent_as_currency": 0,
        "cryptopanic_all_requests_failed": 0,
        "cryptopanic_json_parse_errors": 0,
        "cryptopanic_configured_but_unusable": 0,
        "cryptopanic_status_code_missing_on_http_failure": 0,
        "cryptopanic_body_excerpt_unredacted_token": 0,
        "cryptopanic_quota_exceeded": 0,
        "cryptopanic_request_ledger_missing_when_used": 0,
        "cryptopanic_success_with_backoff_status": 0,
        "cryptopanic_restore_token_recommendation_when_configured": 0,
        "cryptopanic_run_coverage_config_mismatch": 0,
        "cryptopanic_profile_disabled_coverage_mismatch": 0,
        "cryptopanic_profile_disabled_credential_recommendation": 0,
        "source_coverage_blocker_summary_inconsistent": 0,
    }


def _add_source_conflict_counts(out: dict[str, int], increments: Mapping[str, int]) -> None:
    for key, value in increments.items():
        out[key] += value


def _cryptopanic_source_context(
    source_path: Path | None,
    *,
    run_rows: Iterable[Mapping[str, Any]],
) -> tuple[str, Mapping[str, Any], Mapping[str, Any] | None, Mapping[str, Any]]:
    source_text = ""
    if source_path is not None and source_path.exists():
        try:
            source_text = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            source_text = ""
    source_payload: Mapping[str, Any] = {}
    if source_path is not None:
        source_json_path = source_path if source_path.suffix == ".json" else source_path.with_suffix(".json")
        source_payload = _load_json_mapping(source_json_path)
    run_list = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    source_run_id = str(source_payload.get("run_id") or "").strip()
    exact_run = next(
        (row for row in run_list if source_run_id and str(row.get("run_id") or "") == source_run_id),
        None,
    )
    if exact_run is None and run_list:
        latest_id = _latest_run_id(run_list)
        exact_run = next(
            (row for row in run_list if str(row.get("run_id") or "") == str(latest_id or "")),
            run_list[-1],
        )
    readiness_payload: Mapping[str, Any] = {}
    readiness_row: Mapping[str, Any] = {}
    if source_path is not None:
        candidate = _load_json_mapping(source_path.parent / event_alpha_source_coverage.LIVE_PROVIDER_READINESS_JSON)
        readiness_run_id = str(candidate.get("run_id") or "").strip()
        exact_run_id = str((exact_run or {}).get("run_id") or "").strip()
        if candidate and (not exact_run_id or readiness_run_id == exact_run_id):
            readiness_payload = candidate
            readiness_row = _cryptopanic_readiness_row(readiness_payload)
    return source_text, source_payload, exact_run, readiness_row


def _cryptopanic_source_state_conflicts(
    *,
    source_text: str,
    source_payload: Mapping[str, Any],
    exact_run: Mapping[str, Any] | None,
    readiness_row: Mapping[str, Any],
    core_rows: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    out = {
        "cryptopanic_configured_but_not_observed": 0,
        "cryptopanic_run_coverage_config_mismatch": 0,
        "cryptopanic_profile_disabled_coverage_mismatch": 0,
        "cryptopanic_profile_disabled_credential_recommendation": 0,
        "source_coverage_blocker_summary_inconsistent": 0,
    }
    selected_for_run = (
        source_payload.get("cryptopanic_selected_for_run") is True
        or (exact_run or {}).get("cryptopanic_selected_for_run") is True
    )
    if "CryptoPanic:" in source_text and selected_for_run:
        if "- configured: true" in source_text and "- observed this run: false" in source_text:
            out["cryptopanic_configured_but_not_observed"] = 1
    run_configured = bool((exact_run or {}).get("cryptopanic_configured"))
    readiness_configured = bool(readiness_row.get("configured"))
    coverage_configured = bool(source_payload.get("cryptopanic_configured"))
    if source_payload and (run_configured or readiness_configured) and not coverage_configured:
        out["cryptopanic_run_coverage_config_mismatch"] = 1
    profile_disabled = str((exact_run or {}).get("cryptopanic_skip_reason") or "") == "profile_disabled"
    coverage_status = str(source_payload.get("cryptopanic_coverage_status") or "")
    not_used_reason = str(source_payload.get("cryptopanic_not_used_reason") or "")
    if source_payload and profile_disabled and (
        coverage_status != "configured_profile_disabled" or not_used_reason != "profile_disabled"
    ):
        out["cryptopanic_profile_disabled_coverage_mismatch"] = 1
    recommendation = str(source_payload.get("cryptopanic_recommendation") or "").casefold()
    credential_advice = any(token in recommendation for token in ("configure", "restore", "credential", "api key", "api token"))
    if source_payload and profile_disabled and (run_configured or readiness_configured) and credential_advice:
        out["cryptopanic_profile_disabled_credential_recommendation"] = 1
    explicit_source_blocker = any(
        row.get("source_requirements_met") is False
        or row.get("opportunity_type_source_requirements_met") is False
        or any(
            token in str(row.get("why_not_alertable") or "").casefold()
            for token in ("strong_source_missing", "official_exchange_source_required", "structured_unlock_source_required")
        )
        for row in core_rows
        if isinstance(row, Mapping)
    )
    if source_payload and explicit_source_blocker and int(source_payload.get("candidates_blocked_by_source_coverage") or 0) <= 0:
        out["source_coverage_blocker_summary_inconsistent"] = 1
    return out


def _cryptopanic_evidence_conflicts(
    *,
    acquisition: list[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    research_card_paths: Iterable[Path],
    source_text: str,
    cryptopanic_used: bool,
) -> dict[str, int]:
    out = {
        "cryptopanic_used_but_no_source_coverage_entry": 0,
        "cryptopanic_accepted_evidence_missing_from_card": 0,
        "cryptopanic_rejected_only_promoted": 0,
    }
    if cryptopanic_used and "CryptoPanic:" not in source_text:
        out["cryptopanic_used_but_no_source_coverage_entry"] = 1
    accepted_core_ids = {
        str(row.get("core_opportunity_id") or "")
        for row in acquisition
        if _accepted_cryptopanic_count(row) > 0
    }
    if accepted_core_ids:
        card_text_by_core = _card_text_by_core(research_card_paths)
        for core_id in accepted_core_ids:
            if not core_id:
                continue
            text = card_text_by_core.get(core_id, "")
            if text and "cryptopanic" not in text.casefold():
                out["cryptopanic_accepted_evidence_missing_from_card"] += 1
    rejected_only_core_ids = {
        str(row.get("core_opportunity_id") or "")
        for row in acquisition
        if _row_mentions_cryptopanic(row)
        and _accepted_cryptopanic_count(row) <= 0
        and (
            str(row.get("status") or row.get("evidence_acquisition_status") or "") == "rejected_results_only"
            or _rejected_cryptopanic_count(row) > 0
        )
    }
    for row in core_rows:
        core_id = str(row.get("core_opportunity_id") or "")
        if core_id not in rejected_only_core_ids:
            continue
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "")
        level = str(row.get("opportunity_level") or row.get("final_opportunity_level") or "")
        alertable = bool(row.get("alertable_after_quality_gate") or row.get("route_alertable"))
        if alertable or route in {"RESEARCH_DIGEST", "WATCHLIST", "HIGH_PRIORITY_RESEARCH"} or level in {"validated_digest", "watchlist", "high_priority"}:
            out["cryptopanic_rejected_only_promoted"] += 1
    return out


def _cryptopanic_ledger_conflicts(
    ledger_rows: Iterable[Mapping[str, Any]],
    *,
    source_text: str,
) -> dict[str, int]:
    out = {
        "cryptopanic_growth_unsupported_param_used": 0,
        "cryptopanic_duplicate_request_key": 0,
        "cryptopanic_invalid_currency_code": 0,
        "cryptopanic_empty_currency_request": 0,
        "cryptopanic_coin_id_sent_as_currency": 0,
        "cryptopanic_all_requests_failed": 0,
        "cryptopanic_json_parse_errors": 0,
        "cryptopanic_configured_but_unusable": 0,
        "cryptopanic_status_code_missing_on_http_failure": 0,
        "cryptopanic_body_excerpt_unredacted_token": 0,
        "cryptopanic_token_printed_or_unredacted": 0,
        "cryptopanic_quota_exceeded": 0,
        "cryptopanic_success_with_backoff_status": 0,
        "cryptopanic_restore_token_recommendation_when_configured": 0,
    }
    materialized = [row for row in ledger_rows if isinstance(row, Mapping)]
    for row in materialized:
        _add_source_conflict_counts(out, _cryptopanic_request_row_conflicts(row))
    if out["cryptopanic_token_printed_or_unredacted"]:
        out["cryptopanic_token_printed_or_unredacted"] = 1
    request_keys = [
        str(row.get("normalized_request_key") or row.get("request_url_redacted") or "").strip()
        for row in materialized
        if str(row.get("normalized_request_key") or row.get("request_url_redacted") or "").strip()
    ]
    out["cryptopanic_duplicate_request_key"] = max(0, len(request_keys) - len(set(request_keys)))
    attempted_rows = [row for row in materialized if row.get("quota_counted") is not False]
    successful_rows = [
        row
        for row in attempted_rows
        if not str(row.get("error_class") or "").strip()
        and ((_int_or_none(row.get("status_code"), 0) or 0) in range(200, 400))
    ]
    if attempted_rows:
        successes = sum(1 for row in attempted_rows if int(row.get("result_count") or 0) > 0 and not str(row.get("error_class") or ""))
        failures = sum(1 for row in attempted_rows if str(row.get("error_class") or "") or _int_or_none(row.get("status_code"), 0) >= 400)
        if failures and successes == 0 and failures == len(attempted_rows):
            out["cryptopanic_all_requests_failed"] = 1
    unusable_markers = (
        "coverage status: observed_parse_error",
        "coverage status: observed_rate_limited",
        "coverage status: observed_backoff_without_success",
        "coverage status: quota_exhausted",
    )
    if any(marker in source_text for marker in unusable_markers):
        out["cryptopanic_configured_but_unusable"] = 1
    if successful_rows and (
        "health status: backoff" in source_text
        or "coverage status: observed_backoff_without_success" in source_text
        or "coverage status: configured_but_backoff" in source_text
    ):
        out["cryptopanic_success_with_backoff_status"] = 1
    if successful_rows and (
        "configure CryptoPanic token" in source_text
        or "restore CryptoPanic token" in source_text
        or "verify the CryptoPanic token" in source_text
    ):
        out["cryptopanic_restore_token_recommendation_when_configured"] = 1
    if sum(1 for _ in materialized) > 600:
        out["cryptopanic_quota_exceeded"] = 1
    return out


def _cryptopanic_request_row_conflicts(row: Mapping[str, Any]) -> dict[str, int]:
    out = {
        "cryptopanic_growth_unsupported_param_used": 0,
        "cryptopanic_invalid_currency_code": 0,
        "cryptopanic_empty_currency_request": 0,
        "cryptopanic_coin_id_sent_as_currency": 0,
        "cryptopanic_json_parse_errors": 0,
        "cryptopanic_status_code_missing_on_http_failure": 0,
        "cryptopanic_body_excerpt_unredacted_token": 0,
        "cryptopanic_token_printed_or_unredacted": 0,
    }
    redacted_url = str(row.get("request_url_redacted") or "")
    plan = str(row.get("plan") or "growth").strip().lower()
    if plan != "enterprise" and _growth_unsupported_params(redacted_url):
        out["cryptopanic_growth_unsupported_param_used"] += 1
    currencies = str(row.get("currencies") or "").strip()
    if not currencies:
        out["cryptopanic_empty_currency_request"] += 1
    for currency in [part.strip() for part in currencies.split(",") if part.strip()]:
        if currency != currency.upper() or not re.match(r"^[A-Z][A-Z0-9]{1,9}$", currency):
            out["cryptopanic_invalid_currency_code"] += 1
        if "-" in currency or "_" in currency or currency.casefold() in {"fetch-ai", "synapse-2", "chiliz"}:
            out["cryptopanic_coin_id_sent_as_currency"] += 1
    if "auth_token=" in redacted_url and "auth_token=%3Credacted%3E" not in redacted_url and "auth_token=<redacted>" not in redacted_url:
        out["cryptopanic_token_printed_or_unredacted"] = 1
    error_class = str(row.get("error_class") or "").strip()
    status_code = row.get("status_code")
    try:
        status_int = int(status_code) if status_code not in (None, "") else None
    except (TypeError, ValueError):
        status_int = None
    if error_class in {"json_parse_error", "empty_response"}:
        out["cryptopanic_json_parse_errors"] += 1
    if error_class in {"auth_failed", "rate_limited_or_forbidden", "server_error"} and status_int is None:
        out["cryptopanic_status_code_missing_on_http_failure"] += 1
    if _contains_unredacted_cryptopanic_secret(str(row.get("body_excerpt_redacted") or "")):
        out["cryptopanic_body_excerpt_unredacted_token"] += 1
    return out


def _load_json_mapping(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, Mapping) else {}


def _cryptopanic_readiness_row(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    for row in payload.get("providers") or ():
        if not isinstance(row, Mapping):
            continue
        identity = " ".join(
            str(row.get(key) or "")
            for key in ("provider", "provider_name", "provider_health_key")
        ).casefold()
        if "cryptopanic" in identity:
            return row
    return {}

def _evidence_count_mismatches(rows: Iterable[Mapping[str, Any]]) -> int:
    mismatches = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for count_key, list_key in (
            ("accepted_evidence_count", "accepted_evidence"),
            ("rejected_evidence_count", "rejected_evidence"),
        ):
            if count_key not in row:
                continue
            declared = _int_or_none(row.get(count_key))
            if declared is None:
                mismatches += 1
                continue
            if list_key not in row:
                # Legacy acquisition rows persisted only sample arrays; those are
                # intentionally incomplete and should remain readable.
                continue
            observed = len(_mapping_items(row.get(list_key)))
            if declared != observed:
                mismatches += 1
        legacy_accepted = _int_or_none(row.get("evidence_acquisition_accepted_count"))
        accepted = _int_or_none(row.get("accepted_evidence_count"))
        if legacy_accepted is not None and accepted is not None and legacy_accepted != accepted:
            mismatches += 1
        legacy_rejected = _int_or_none(row.get("evidence_acquisition_rejected_count"))
        rejected = _int_or_none(row.get("rejected_evidence_count"))
        if legacy_rejected is not None and rejected is not None and legacy_rejected != rejected:
            mismatches += 1
    return mismatches

def _evidence_acquisition_final_field_conflicts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {"evidence_acquisition_stale_validated_digest": 0}
    unresolved_statuses = {
        "rejected_results_only",
        "no_results",
        "skipped_budget",
        "not_executed",
        "not_configured",
        "provider_unavailable",
        "provider_backoff",
        "skipped_config",
    }
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        accepted = _raw_int_value(row.get("accepted_evidence_count"), row.get("evidence_acquisition_accepted_count"))
        status = str(row.get("status") or row.get("evidence_acquisition_status") or row.get("acquisition_evidence_status") or "").strip()
        final_level = str(row.get("final_opportunity_level") or row.get("opportunity_level_after") or "").strip()
        if accepted <= 0 and status in unresolved_statuses and final_level in {"validated_digest", "watchlist", "high_priority"}:
            out["evidence_acquisition_stale_validated_digest"] += 1
    return out

def _daily_brief_card_names(path: str | Path | None) -> set[str]:
    if path is None:
        return set()
    brief_path = Path(path)
    if not brief_path.exists():
        return set()
    try:
        text = brief_path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {
        match.group(1)
        for match in re.finditer(r"\[(card_[^\]\s]+?\.md)\]", text)
    }

def _visible_sector_core_without_config(rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        symbol = str(row.get("symbol") or row.get("validated_symbol") or "").strip().upper()
        coin_id = str(row.get("coin_id") or row.get("validated_coin_id") or "").strip().casefold()
        if symbol != "SECTOR" and not coin_id.startswith("sector"):
            continue
        route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
        level = str(row.get("opportunity_level") or row.get("final_opportunity_level") or "").strip()
        visible = event_alpha_router.route_value_is_alertable(route) or level in {
            "validated_digest",
            "watchlist",
            "high_priority",
        }
        allowed = str(row.get("sector_review_enabled") or row.get("allow_sector_digest") or "").strip().casefold() in {
            "1",
            "true",
            "yes",
        }
        if visible and not allowed:
            count += 1
    return count

def _duplicate_proxy_core_rows(rows: Iterable[Mapping[str, Any]]) -> int:
    groups: dict[tuple[str, str, str, str], int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if event_core_opportunities.row_is_diagnostic(row):
            continue
        impact = str(row.get("impact_path_type") or row.get("primary_impact_path") or row.get("impact_path_reason") or "").casefold()
        source_pack = str(row.get("source_pack") or "").casefold()
        if not any(token in f"{impact} {source_pack}" for token in ("proxy", "preipo", "pre_ipo", "rwa", "venue")):
            continue
        symbol = str(row.get("symbol") or row.get("validated_symbol") or "").strip().upper()
        coin_id = str(row.get("coin_id") or row.get("validated_coin_id") or "").strip().casefold() or symbol
        if symbol == "SECTOR" or coin_id.startswith("sector"):
            continue
        incident = str(
            row.get("incident_id")
            or row.get("canonical_incident_name")
            or row.get("external_asset")
            or row.get("event_cluster_id")
            or ""
        ).strip().casefold()
        role = str(row.get("candidate_role") or row.get("relationship_type") or "").strip().casefold()
        family = "proxy_value_capture"
        key = (incident, coin_id, role or "proxy", family)
        groups[key] = groups.get(key, 0) + 1
    return sum(max(0, count - 1) for count in groups.values())

def _row_mentions_cryptopanic(row: Mapping[str, Any]) -> bool:
    values = (
        row.get("provider"),
        row.get("provider_hint"),
        row.get("provider_used"),
        row.get("source_class"),
        row.get("source_url"),
        row.get("providers_used"),
        row.get("evidence_acquisition_providers_used"),
        row.get("provider_failures"),
        row.get("reason_codes"),
        row.get("accepted_evidence"),
        row.get("rejected_evidence"),
        row.get("rejected_evidence_samples"),
        row.get("queries"),
    )
    return any("cryptopanic" in str(value).casefold() for value in values)

def _load_jsonl_rows(path: Path | None) -> tuple[Mapping[str, Any], ...]:
    if path is None or not path.exists():
        return ()
    rows: list[Mapping[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            import json

            value = json.loads(line)
            if isinstance(value, Mapping):
                rows.append(value)
    except Exception:  # noqa: BLE001 - doctor must fail soft
        return tuple(rows)
    return tuple(rows)

def _growth_unsupported_params(redacted_url: str) -> tuple[str, ...]:
    unsupported = {"last_pull", "panic_period", "panic_sort", "search", "size", "with_content"}
    try:
        query = parse_qs(urlsplit(redacted_url).query)
    except Exception:  # noqa: BLE001
        return ()
    return tuple(sorted(key for key in query if key in unsupported))

def _contains_unredacted_cryptopanic_secret(text: str) -> bool:
    if "RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN=" in text:
        return True
    for match in re.finditer(r"auth_token=([^&\s]+)", text):
        value = match.group(1)
        if value not in {"<redacted>", "%3Credacted%3E", "[redacted]"}:
            return True
    # Canonical evidence digests are deliberately operator-visible technical
    # metadata, not credentials.  Remove only exact, fully labelled digest
    # lines before retaining the conservative generic hex-secret check.
    secret_scan_text = re.sub(
        r"(?mi)^\s*-?\s*(?:Catalyst-attribution|Source-independence contract) "
        r"digest:\s*[a-f0-9]{64}\s*$",
        "",
        text,
    )
    if re.search(r"\b[A-Fa-f0-9]{32,}\b", secret_scan_text):
        return True
    return False

def _int_or_none(value: object, default: int | None = None) -> int | None:
    try:
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default

def _accepted_cryptopanic_count(row: Mapping[str, Any]) -> int:
    accepted = row.get("accepted_evidence") or row.get("evidence_acquisition_accepted_evidence")
    return sum(1 for item in _mapping_items(accepted) if _row_mentions_cryptopanic(item))

def _rejected_cryptopanic_count(row: Mapping[str, Any]) -> int:
    rejected = row.get("rejected_evidence_samples") or row.get("rejected_evidence") or row.get("evidence_acquisition_rejected_samples")
    return sum(1 for item in _mapping_items(rejected) if _row_mentions_cryptopanic(item))

def _mapping_items(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()

def _card_text_by_core(paths: Iterable[Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in paths:
        text = _read_card_text(path)
        patterns = (
            r"core_opportunity_id:\s*([^\s]+)",
            r"^-\s*Core opportunity ID:\s*(.+?)\s*$",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.MULTILINE):
                core_id = str(match.group(1)).strip()
                if core_id and core_id.lower() != "none":
                    out[core_id] = text
    return out

def _daily_brief_consistency_conflicts(
    path: str | Path | None,
    *,
    runs: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    delivery_rows: Iterable[Mapping[str, Any]],
    source_coverage_report_path: str | Path | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
) -> dict[str, int]:
    out = {
        "daily_brief_missing_selected_run": 0,
        "daily_brief_selected_run_mismatch": 0,
        "daily_brief_core_count_mismatch_store": 0,
        "daily_brief_research_review_lane_missing": 0,
        "daily_brief_source_coverage_path_missing": 0,
        "daily_brief_coinalyze_source_coverage_mismatch": 0,
    }
    if path is None:
        return out
    brief_path = Path(path)
    if not brief_path.exists():
        return out
    try:
        text = brief_path.read_text(encoding="utf-8")
    except OSError:
        return out
    run_list = [dict(row) for row in runs if isinstance(row, Mapping)]
    core_list = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    latest_id = _latest_run_id(run_list)
    latest_run = next((row for row in run_list if str(row.get("run_id") or "") == str(latest_id or "")), None)
    if run_list and "No run ledger rows found" in text:
        out["daily_brief_missing_selected_run"] = 1
    selected_profile = _daily_brief_line_value(text, "Selected run profile")
    selected_namespace = _daily_brief_line_value(text, "Selected run namespace")
    expected_profile = str((latest_run or {}).get("profile") or profile or "default").strip()
    expected_namespace = str((latest_run or {}).get("artifact_namespace") or artifact_namespace or "legacy").strip()
    if latest_run:
        if selected_profile in {"", "none"} or selected_namespace in {"", "none"}:
            out["daily_brief_selected_run_mismatch"] = 1
        elif selected_profile != expected_profile or selected_namespace != expected_namespace:
            out["daily_brief_selected_run_mismatch"] = 1
    rendered_expected_core_count = len(event_core_opportunity_store.core_opportunities_from_rows(core_list)) if core_list else 0
    rendered_core_count = _daily_brief_core_count(text)
    if core_list and rendered_core_count is not None and rendered_core_count != rendered_expected_core_count:
        out["daily_brief_core_count_mismatch_store"] = 1
    elif core_list and "Core opportunities: 0" in text:
        out["daily_brief_core_count_mismatch_store"] = 1
    research_review_expected = False
    if latest_run and (
        _as_int(latest_run.get("research_review_digest_candidates"))
        or _as_int(latest_run.get("research_review_digest_would_send"))
    ):
        research_review_expected = True
    if latest_id:
        research_review_expected = research_review_expected or any(
            str(row.get("run_id") or "") == str(latest_id)
            and str(row.get("lane") or "") == "research_review_digest"
            for row in delivery_rows
            if isinstance(row, Mapping)
        )
    review_section = _daily_brief_section(text, "### Research Review Digest")
    if research_review_expected and (
        not review_section
        or "Lane count sent/due: 0/0" in review_section
    ):
        out["daily_brief_research_review_lane_missing"] = 1
    if source_coverage_report_path is not None and Path(source_coverage_report_path).exists():
        source_text = str(source_coverage_report_path)
        if source_text not in text and Path(source_coverage_report_path).name not in text:
            out["daily_brief_source_coverage_path_missing"] = 1
        try:
            source_body = Path(source_coverage_report_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            source_body = ""
        coverage_links_coinalyze = (
            event_coinalyze_preflight.PREFLIGHT_JSON in source_body
            or event_coinalyze_preflight.PREFLIGHT_MD in source_body
            or event_coinalyze_preflight.REHEARSAL_MD in source_body
        )
        brief_says_missing = "Coinalyze preflight: not generated" in text or "Coinalyze preflight: not written yet" in text
        if coverage_links_coinalyze and brief_says_missing:
            out["daily_brief_coinalyze_source_coverage_mismatch"] = 1
    return out

def _daily_brief_line_value(text: str, label: str) -> str:
    prefix = f"{label}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[-1].strip()
    return ""

def _daily_brief_core_count(text: str) -> int | None:
    match = re.search(r"^- Core opportunities:\s+(\d+)\b", text, flags=re.MULTILINE)
    if not match:
        return None
    return _as_int(match.group(1))

def _daily_brief_section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    next_heading = text.find("\n### ", start + len(heading))
    if next_heading < 0:
        return text[start:]
    return text[start:next_heading]

def _split_provider_line(line: str) -> tuple[str, ...]:
    if ":" not in line:
        return ()
    value = line.rsplit(":", 1)[-1].strip()
    if not value or value == "none":
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())

def _tuple_value(value: Any) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, Mapping):
        return tuple(str(key) for key in value if str(key).strip())
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value if str(item).strip())
    return (str(value),)

__all__ = (
    '_truthy',
    '_source_coverage_metadata_conflicts',
    '_source_coverage_report_conflicts',
    '_live_provider_readiness_conflicts',
    '_text_has_secret_like_value',
    '_source_coverage_report_required',
    '_live_provider_readiness_required',
    '_cryptopanic_artifact_conflicts',
    '_evidence_count_mismatches',
    '_evidence_acquisition_final_field_conflicts',
    '_daily_brief_card_names',
    '_visible_sector_core_without_config',
    '_duplicate_proxy_core_rows',
    '_row_mentions_cryptopanic',
    '_load_jsonl_rows',
    '_growth_unsupported_params',
    '_contains_unredacted_cryptopanic_secret',
    '_int_or_none',
    '_accepted_cryptopanic_count',
    '_rejected_cryptopanic_count',
    '_mapping_items',
    '_card_text_by_core',
    '_daily_brief_consistency_conflicts',
    '_daily_brief_line_value',
    '_daily_brief_core_count',
    '_daily_brief_section',
    '_split_provider_line',
    '_tuple_value',
)
