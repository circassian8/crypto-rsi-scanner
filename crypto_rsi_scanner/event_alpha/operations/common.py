"""Shared helpers for Event Alpha burn-in operating reports."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import context as artifact_context
from ..artifacts import json_lines as artifact_json_lines


SECRET_RE = re.compile(
    r"(api[_-]?key\b|auth[_-]?token\b|bearer\s+[a-z0-9._-]{12,}|sk-[a-z0-9_-]{12,}|"
    r"x-api-key\b|telegram[_-]?bot[_-]?token\b|provider[_-]?token\b)",
    re.IGNORECASE,
)
SAFE_SECRET_STATUS_PHRASES = (
    "missing_api_key",
    "missing_config",
    "api_key_missing",
    "token configured: no",
    "token configured: no (redacted)",
    "api key configured: no",
    "api key values are never printed",
    "no api token value is printed",
    "redacted",
    "[redacted]",
    "configured=false",
    "configured: false",
)
SECRET_ENV_VAR_NAMES = {"API_KEY", "AUTH_TOKEN", "X-API-KEY", "TELEGRAM_BOT_TOKEN"}
SECRET_VALUE_RE = re.compile(
    r"(?P<label>\b(?:api[_-]?key|api\s+key|auth[_-]?token|api[_-]?token|telegram[_-]?bot[_-]?token|"
    r"provider[_-]?token)\b)\s*[\"']?\s*[:=]\s*[\"']?(?P<value>[^\"'\s,}]+)",
    re.IGNORECASE,
)
AUTH_BEARER_RE = re.compile(r"\bAuthorization\s*:\s*Bearer\s+(?P<value>[A-Za-z0-9._-]+)", re.IGNORECASE)
X_API_KEY_RE = re.compile(r"\bX-API-Key\s*:\s*(?P<value>[A-Za-z0-9._-]+)", re.IGNORECASE)
OPENAI_KEY_RE = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b")
PROVIDER_TOKEN_VALUE_RE = re.compile(r"\b(?:ghp|gho|ghu|github_pat|xoxb|xoxp)_[A-Za-z0-9_]{16,}\b", re.IGNORECASE)
TELEGRAM_BOT_TOKEN_VALUE_RE = re.compile(
    r"(?<![A-Za-z0-9])\d{6,12}:[A-Za-z0-9_-]{30,64}(?![A-Za-z0-9_-])"
)
ABSOLUTE_ARTIFACT_PATH_RE = re.compile(
    r"(?P<prefix>(?:/mnt/data|/tmp|/private/tmp)/[^\s`'\"<>]*|/Users/[^\s`'\"<>]+/[^\s`'\"<>]*)"
    r"(?P<artifact>event_fade_cache/[^\s`'\"<>]*)"
)
SAFETY_FIELDS: dict[str, Any] = {
    "research_only": True,
    "no_send_rehearsal": True,
    "strict_alerts_created": 0,
    "telegram_sends": 0,
    "trades_created": 0,
    "paper_trades_created": 0,
    "normal_rsi_signal_rows_written": 0,
    "triggered_fade_created": 0,
}
EVIDENCE_TIMESTAMP_FIELDS = (
    "observed_at",
    "created_at",
    "started_at",
    "run_started_at",
    "attempted_at",
    "marked_at",
    "feedback_marked_at",
    "published_at",
    "generated_at",
)
BURN_IN_CONTRACT_COUNT_FIELDS = (
    ("min_live_no_send_cycles", "live_no_send_cycles"),
    ("min_real_candidates", "real_candidates"),
    ("min_human_labels", "human_labels"),
    ("min_labeled_near_misses", "labeled_near_misses"),
    ("min_outcome_rows", "outcome_rows"),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def parse_aware_utc(value: Any) -> datetime | None:
    """Parse an explicitly timezone-aware timestamp and normalize it to UTC."""

    if value in (None, ""):
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value).strip()
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def date_window(days: int, *, now: datetime | None = None) -> datetime:
    return (now or utc_now()).astimezone(timezone.utc) - timedelta(days=max(1, int(days or 1)))


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[3]


def context_for(
    *,
    profile: str | None,
    artifact_namespace: str | None,
    base_dir: str | Path | None = None,
) -> artifact_context.EventAlphaArtifactContext:
    return artifact_context.context_from_profile(
        profile or "live_burn_in_no_send",
        run_mode="burn_in",
        base_dir=base_dir,
        artifact_namespace=artifact_namespace,
    )


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return list(artifact_json_lines.read_jsonl(path).rows)


def read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.exists():
        return {}
    try:
        loaded = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def write_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def write_text(path: str | Path, text: str) -> Path:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.rstrip() + "\n", encoding="utf-8")
    return p


def append_jsonl(path: str | Path, row: Mapping[str, Any]) -> Path:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(json_ready(row), sort_keys=True) + "\n")
    return p


def json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_ready(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def rel_path(path: str | Path, *, root: str | Path | None = None) -> str:
    p = Path(path).expanduser()
    base = Path(root).expanduser() if root is not None else repo_root_from_module()
    try:
        return p.resolve().relative_to(base.resolve()).as_posix()
    except (OSError, ValueError):
        return p.as_posix()


def count_by(rows: Iterable[Mapping[str, Any]], *fields: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        key = next((str(row.get(field) or "").strip() for field in fields if str(row.get(field) or "").strip()), "unknown")
        counts[key] += 1
    return dict(sorted(counts.items()))


def int_value(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def float_value(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def item_family(row: Mapping[str, Any]) -> str:
    return str(
        row.get("canonical_asset_id")
        or row.get("core_opportunity_id")
        or row.get("coin_id")
        or row.get("asset_coin_id")
        or row.get("symbol")
        or row.get("asset_symbol")
        or row.get("feedback_target")
        or row.get("alert_key")
        or row.get("id")
        or "unknown"
    )


def row_score(row: Mapping[str, Any]) -> int:
    for field in ("opportunity_score", "score", "latest_score", "priority"):
        if field in row:
            return int_value(row.get(field))
    return 0


def row_lane(row: Mapping[str, Any]) -> str:
    return str(row.get("opportunity_type") or row.get("lane") or row.get("tier") or "unknown")


def timestamp_for_row(row: Mapping[str, Any]) -> datetime | None:
    for field in EVIDENCE_TIMESTAMP_FIELDS:
        parsed = parse_utc(row.get(field))
        if parsed is not None:
            return parsed
    return None


def row_in_evidence_window(
    row: Mapping[str, Any],
    *,
    cutoff: datetime,
    evaluated_at: datetime,
) -> bool:
    """Return whether a row has an aware timestamp inside the closed evidence window."""

    window_start = parse_aware_utc(cutoff)
    window_end = parse_aware_utc(evaluated_at)
    if window_start is None or window_end is None or window_start > window_end:
        raise ValueError("evidence window requires ordered timezone-aware bounds")
    timestamp = _aware_timestamp_for_row(row)
    return bool(timestamp is not None and window_start <= timestamp <= window_end)


def _aware_timestamp_for_row(row: Mapping[str, Any]) -> datetime | None:
    for field in EVIDENCE_TIMESTAMP_FIELDS:
        value = row.get(field)
        if value not in (None, ""):
            return parse_aware_utc(value)
    return None


def table_line(label: str, counts: Mapping[str, int]) -> str:
    if not counts:
        return f"- {label}: none"
    return f"- {label}: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def secret_hits_in_text(text: str) -> list[str]:
    hits: list[str] = []
    for match in SECRET_RE.finditer(text or ""):
        token = match.group(0)
        if _natural_language_sk_phrase(token):
            continue
        if token and token not in hits:
            hits.append(token[:80])
    return hits


def classify_secret_hits_in_text(text: str) -> Iterable[dict[str, Any]]:
    """Classify secret-like text without treating safe operator status as leakage."""

    details: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for line_no, line in enumerate((text or "").splitlines() or [text or ""], start=1):
        stripped = line.strip()
        if not stripped:
            continue
        line_lower = stripped.casefold()
        safe_status = _safe_secret_status_line(stripped)
        for label, value, match_text in _secret_value_matches(stripped):
            status = "allowed_status" if _safe_secret_value(value) else "blocker"
            reason = "redacted_or_missing_value" if status == "allowed_status" else "secret_value"
            details.append(
                _secret_detail(
                    status=status,
                    reason=reason,
                    line_no=line_no,
                    token=label,
                    excerpt=_redacted_secret_excerpt(match_text),
                )
            )
        if any(detail["line_number"] == line_no and detail["status"] == "blocker" for detail in details):
            continue
        if safe_status:
            hits = secret_hits_in_text(stripped)
            if hits or any(phrase in line_lower for phrase in SAFE_SECRET_STATUS_PHRASES):
                details.append(
                    _secret_detail(
                        status="allowed_status",
                        reason="safe_status_phrase",
                        line_no=line_no,
                        token=hits[0] if hits else "status_phrase",
                        excerpt=stripped[:160],
                    )
                )
            continue
        for token in secret_hits_in_text(stripped):
            if token in SECRET_ENV_VAR_NAMES:
                details.append(
                    _secret_detail(
                        status="false_positive",
                        reason="env_var_name_only",
                        line_no=line_no,
                        token=token,
                        excerpt=stripped[:160],
                    )
                )
            else:
                details.append(
                    _secret_detail(
                        status="blocker",
                        reason="secret_like_token",
                        line_no=line_no,
                        token=token,
                        excerpt=_redacted_secret_excerpt(stripped[:160]),
                    )
                )
    for detail in details:
        key = (str(detail.get("status")), str(detail.get("reason")), str(detail.get("line_number")) + str(detail.get("token")))
        if key in seen:
            continue
        seen.add(key)
        yield_detail = detail
        yield_detail["token"] = str(yield_detail.get("token") or "")[:80]
        yield_detail["excerpt"] = str(yield_detail.get("excerpt") or "")[:200]
        yield yield_detail


def scrub_operator_text(text: str, *, root: str | Path | None = None) -> tuple[str, int]:
    """Redact operator-captured stdout/stderr text before persisting artifacts."""

    clean = str(text or "")
    redactions = 0

    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    try:
        repo_root_text = repo_root.resolve().as_posix()
    except OSError:
        repo_root_text = repo_root.as_posix()
    if repo_root_text and repo_root_text in clean:
        clean, count = re.subn(re.escape(repo_root_text) + r"/?", "", clean)
        redactions += count

    def _artifact_path_repl(match: re.Match[str]) -> str:
        return match.group("artifact")

    clean, count = ABSOLUTE_ARTIFACT_PATH_RE.subn(_artifact_path_repl, clean)
    redactions += count

    def _secret_value_repl(match: re.Match[str]) -> str:
        nonlocal redactions
        label = match.group("label")
        value = match.group("value")
        if _safe_secret_value(value):
            return match.group(0)
        redactions += 1
        return f"{label}=<redacted>"

    clean = SECRET_VALUE_RE.sub(_secret_value_repl, clean)
    for pattern, repl in (
        (AUTH_BEARER_RE, "Authorization: Bearer <redacted>"),
        (X_API_KEY_RE, "X-API-Key: <redacted>"),
        (OPENAI_KEY_RE, "sk-<redacted>"),
        (PROVIDER_TOKEN_VALUE_RE, "<redacted-provider-token>"),
        (TELEGRAM_BOT_TOKEN_VALUE_RE, "<redacted-telegram-bot-token>"),
    ):
        clean, count = pattern.subn(repl, clean)
        redactions += count
    return clean, redactions


def _natural_language_sk_phrase(token: str) -> bool:
    if not token.lower().startswith("sk-"):
        return False
    rest = token[3:]
    slug_part = rest.split("_", 1)[0]
    if "_" in rest and slug_part.count("-") >= 3 and slug_part == slug_part.lower() and all(char.isalnum() or char == "-" for char in slug_part):
        return True
    if not rest or rest != rest.lower() or "_" in rest or not any(char == "-" for char in rest):
        return False
    if not any(char.isdigit() for char in rest):
        return True
    return rest.count("-") >= 3 and all(char.isalnum() or char == "-" for char in rest)


def _safe_secret_status_line(line: str) -> bool:
    lower = line.casefold()
    return any(phrase in lower for phrase in SAFE_SECRET_STATUS_PHRASES)


def _safe_secret_value(value: str) -> bool:
    clean = str(value or "").strip().strip("\"'").casefold()
    return clean in {"", "no", "none", "false", "0", "missing", "missing_config", "missing_api_key", "api_key_missing", "redacted", "[redacted]", "***", "<redacted>"}


def _secret_value_matches(line: str) -> list[tuple[str, str, str]]:
    matches: list[tuple[str, str, str]] = []
    for pattern in (SECRET_VALUE_RE, AUTH_BEARER_RE, X_API_KEY_RE):
        for match in pattern.finditer(line):
            if pattern is SECRET_VALUE_RE and match.start() > 0 and line[match.start() - 1] == "-":
                continue
            label = match.groupdict().get("label") or ("authorization" if pattern is AUTH_BEARER_RE else "x-api-key")
            value = match.groupdict().get("value") or ""
            matches.append((label, value, match.group(0)))
    for pattern, label in (
        (OPENAI_KEY_RE, "openai_key"),
        (PROVIDER_TOKEN_VALUE_RE, "provider_token"),
        (TELEGRAM_BOT_TOKEN_VALUE_RE, "telegram_bot_token"),
    ):
        for match in pattern.finditer(line):
            token = match.group(0)
            if _natural_language_sk_phrase(token):
                continue
            matches.append((label, token, token))
    return matches


def _secret_detail(*, status: str, reason: str, line_no: int, token: str, excerpt: str) -> dict[str, Any]:
    return {
        "status": status,
        "classification": status,
        "reason": reason,
        "line_number": line_no,
        "token": token,
        "excerpt": excerpt,
    }


def _redacted_secret_excerpt(text: str) -> str:
    clean = SECRET_VALUE_RE.sub(lambda match: f"{match.group('label')}=<redacted>", str(text or ""))
    clean = AUTH_BEARER_RE.sub("Authorization: Bearer <redacted>", clean)
    clean = X_API_KEY_RE.sub("X-API-Key: <redacted>", clean)
    clean = OPENAI_KEY_RE.sub("sk-<redacted>", clean)
    clean = PROVIDER_TOKEN_VALUE_RE.sub("<redacted-provider-token>", clean)
    clean = TELEGRAM_BOT_TOKEN_VALUE_RE.sub(
        "<redacted-telegram-bot-token>", clean
    )
    return clean


def load_contract(root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root).expanduser() if root is not None else repo_root_from_module()
    contract = read_json(base / "research" / "event_alpha_burn_in_contract.json")
    if contract:
        return contract
    north_star = read_json(base / "research" / "EVENT_ALPHA_RADAR_NORTH_STAR.json")
    embedded = north_star.get("burn_in_contract")
    return dict(embedded) if isinstance(embedded, Mapping) else {}


def contract_threshold(contract: Mapping[str, Any], key: str) -> int:
    return int_value(contract.get(key))


def burn_in_contract_count_reasons(
    contract: Mapping[str, Any],
    *,
    included_namespaces: Iterable[str],
    live_no_send_cycles: int,
    real_candidates: int,
    human_labels: int,
    labeled_near_misses: int,
    outcome_rows: int,
) -> list[str]:
    """Return every unmet North Star burn-in evidence-count threshold."""

    reasons: list[str] = []
    if not any(str(namespace).strip() for namespace in included_namespaces):
        reasons.append("no_active_burn_in_namespaces")
    observed_counts = {
        "live_no_send_cycles": max(0, int_value(live_no_send_cycles)),
        "real_candidates": max(0, int_value(real_candidates)),
        "human_labels": max(0, int_value(human_labels)),
        "labeled_near_misses": max(0, int_value(labeled_near_misses)),
        "outcome_rows": max(0, int_value(outcome_rows)),
    }
    if observed_counts["live_no_send_cycles"] == 0:
        reasons.append("no_live_no_send_cycles")
    for threshold_key, count_key in BURN_IN_CONTRACT_COUNT_FIELDS:
        threshold = contract_threshold(contract, threshold_key)
        observed = observed_counts[count_key]
        if threshold and observed < threshold:
            reasons.append(f"{threshold_key}:{observed}/{threshold}")
    return reasons


def with_safety(payload: dict[str, Any]) -> dict[str, Any]:
    return {**SAFETY_FIELDS, **payload}
