"""Closed artifact-conflict checks for the Bybit announcement rehearsal."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Pattern

from ..operations.market_no_send_io import read_regular_bytes
from . import official_exchange as event_official_exchange
from . import request_lineage as event_request_lineage


JsonlReader = Callable[[Path], tuple[dict[str, Any], ...]]


def artifact_conflicts(
    namespace_dir: str | Path | None,
    *,
    preflight_json: str,
    preflight_md: str,
    rehearsal_json: str,
    rehearsal_md: str,
    request_ledger: str,
    accepted_source_prefix: str,
    accepted_source_suffix: str,
    accepted_source_name_re: Pattern[str],
    sha256_re: Pattern[str],
    read_jsonl: JsonlReader,
) -> dict[str, int]:
    out = {
        "bybit_announcements_preflight_secret_leak": 0,
        "bybit_announcements_preflight_live_call_allowed_in_smoke": 0,
        "bybit_announcements_preflight_missing_fixture_parser_status": 0,
        "bybit_announcements_rehearsal_secret_leak": 0,
        "bybit_announcements_rehearsal_live_without_ledger": 0,
        "bybit_announcements_rehearsal_live_without_explicit_allow": 0,
        "bybit_announcements_rehearsal_unsupported_params": 0,
        "bybit_announcements_rehearsal_accepted_source_invalid": 0,
        "bybit_announcements_rehearsal_forbidden_side_effect_claim": 0,
    }
    if namespace_dir is None:
        return out
    base = Path(namespace_dir)
    paths = [
        base / preflight_json,
        base / preflight_md,
        base / rehearsal_json,
        base / rehearsal_md,
        base / request_ledger,
    ]
    existing = [path for path in paths if path.exists()]
    if not existing:
        return out
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace") for path in existing
    )
    if _secret_like(text):
        out["bybit_announcements_preflight_secret_leak"] = 1
        out["bybit_announcements_rehearsal_secret_leak"] = 1
    preflight = _read_json(base / preflight_json)
    if preflight:
        if bool(preflight.get("smoke_mode")) and bool(
            preflight.get("live_call_allowed")
        ):
            out["bybit_announcements_preflight_live_call_allowed_in_smoke"] = 1
        if not str(preflight.get("fixture_parser_status") or "").strip():
            out["bybit_announcements_preflight_missing_fixture_parser_status"] = 1
    rehearsal = _read_json(base / rehearsal_json)
    ledger_rows = read_jsonl(base / request_ledger)
    if rehearsal:
        generation_id = str(rehearsal.get("provider_generation_id") or "")
        if generation_id:
            ledger_rows = event_request_lineage.generation_rows(
                ledger_rows,
                generation_id,
            )
        live_allowed = bool(rehearsal.get("live_call_allowed"))
        if live_allowed and not ledger_rows:
            out["bybit_announcements_rehearsal_live_without_ledger"] = 1
        if live_allowed and not bool(rehearsal.get("allow_live_preflight")):
            out["bybit_announcements_rehearsal_live_without_explicit_allow"] = 1
        for key in (
            "strict_alerts_created",
            "telegram_sends",
            "trades_created",
            "paper_trades_created",
            "normal_rsi_signal_rows_written",
            "triggered_fade_created",
        ):
            if int(rehearsal.get(key) or 0) != 0:
                out[
                    "bybit_announcements_rehearsal_forbidden_side_effect_claim"
                ] = 1
    for row in ledger_rows:
        unsupported = row.get("unsupported_query_params")
        if unsupported:
            out["bybit_announcements_rehearsal_unsupported_params"] += (
                len(unsupported) if isinstance(unsupported, list) else 1
            )
    out["bybit_announcements_rehearsal_accepted_source_invalid"] = (
        _accepted_source_conflict_count(
            base,
            ledger_rows=ledger_rows,
            rehearsal=rehearsal,
            accepted_source_prefix=accepted_source_prefix,
            accepted_source_suffix=accepted_source_suffix,
            accepted_source_name_re=accepted_source_name_re,
            sha256_re=sha256_re,
            read_jsonl=read_jsonl,
        )
    )
    if re.search(
        r"(?i)\b(send telegram|paper trade|live trade|execute order|triggered_fade created)\b",
        text,
    ):
        out["bybit_announcements_rehearsal_forbidden_side_effect_claim"] = 1
    return out


def _accepted_source_conflict_count(
    base: Path,
    *,
    ledger_rows: Iterable[Mapping[str, Any]],
    rehearsal: Mapping[str, Any],
    accepted_source_prefix: str,
    accepted_source_suffix: str,
    accepted_source_name_re: Pattern[str],
    sha256_re: Pattern[str],
    read_jsonl: JsonlReader,
) -> int:
    conflicts = 0
    expected: dict[str, tuple[str, int]] = {}
    successful_result_count = 0
    for row in ledger_rows:
        artifact = str(row.get("accepted_source_artifact") or "")
        digest = str(row.get("accepted_source_sha256") or "")
        try:
            size = int(row.get("accepted_source_size_bytes"))
        except (TypeError, ValueError):
            size = -1
        success = bool(row.get("success"))
        immutable = bool(row.get("accepted_source_immutable"))
        if not success:
            if artifact or digest or size >= 0 or immutable:
                conflicts += 1
            continue
        if (
            not accepted_source_name_re.fullmatch(artifact)
            or not sha256_re.fullmatch(digest)
            or size <= 0
            or not immutable
            or artifact in expected
        ):
            conflicts += 1
            continue
        expected[artifact] = (digest, size)
        try:
            successful_result_count += int(row.get("result_count") or 0)
        except (TypeError, ValueError):
            conflicts += 1

    try:
        observed_names = {
            entry.name
            for entry in base.iterdir()
            if entry.name.startswith(accepted_source_prefix)
            and entry.name.endswith(accepted_source_suffix)
        }
    except OSError:
        return conflicts + max(1, len(expected))
    conflicts += len(observed_names.symmetric_difference(expected))

    valid_sources: dict[str, str] = {}
    for artifact, (digest, size) in expected.items():
        try:
            raw = read_regular_bytes(base / artifact)
        except Exception:  # noqa: BLE001 - any unsafe/missing leaf is a conflict
            conflicts += 1
            continue
        if (
            raw is None
            or len(raw) != size
            or hashlib.sha256(raw).hexdigest() != digest
        ):
            conflicts += 1
            continue
        if _secret_like(raw.decode("utf-8", errors="replace")):
            conflicts += 1
        valid_sources[artifact] = digest

    report_artifacts = rehearsal.get("accepted_source_artifacts")
    report_count = rehearsal.get("accepted_source_response_count")
    if expected and not rehearsal:
        conflicts += 1
    elif rehearsal:
        if (
            not isinstance(report_artifacts, list)
            or report_artifacts != list(expected)
            or report_count != len(expected)
            or rehearsal.get("announcements_inspected")
            != successful_result_count
        ):
            conflicts += 1

    announcement_rows = read_jsonl(
        base / event_official_exchange.EXCHANGE_ANNOUNCEMENTS_FILENAME
    )
    sourced_rows = [
        row
        for row in announcement_rows
        if bool(row.get("provider_request_succeeded"))
    ]
    if len(sourced_rows) != successful_result_count:
        conflicts += 1
    for row in sourced_rows:
        payload = row.get("raw_payload_redacted")
        if not isinstance(payload, Mapping):
            conflicts += 1
            continue
        artifact = str(payload.get("provider_source_artifact") or "")
        digest = str(payload.get("provider_source_sha256") or "")
        if (
            valid_sources.get(artifact) != digest
            or not bool(payload.get("provider_source_immutable"))
            or row.get("provider_source_artifact") != artifact
        ):
            conflicts += 1
    return conflicts


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def _secret_like(text: str) -> bool:
    return bool(
        re.search(
            r"(?i)(api[_-]?key|secret|token|authorization|bearer)\s*[=:]\s*['\"][A-Za-z0-9._-]{20,}['\"]",
            text,
        )
    )


__all__ = ("artifact_conflicts",)
