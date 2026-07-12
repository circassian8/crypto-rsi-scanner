"""Strict preview-first operator for one exact observed-outcome build.

This boundary is deliberately narrower than the general Event Alpha artifact
loaders.  It reads only explicit local inputs, rejects partial or ambiguous
authority, and can create only a new isolated JSONL file after confirmation.
It never appends canonical artifacts or calls providers, notifications, paper
trading, normal RSI routing, execution, or ``TRIGGERED_FADE`` paths.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import tempfile
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from ..artifacts import context as artifact_context
from ..artifacts import fingerprints as artifact_fingerprints
from ..artifacts import json_lines as artifact_json_lines
from ..artifacts import locks as artifact_locks
from ..artifacts import paths as artifact_paths
from ..artifacts import schema_v1
from ..doctor.checks import secrets as secret_checks
from . import observed_outcome_builder
from . import outcome_eligibility


OPERATOR_CONTRACT_VERSION = 1
SYNTHETIC_CLOSES_SCHEMA_VERSION = "event_alpha_observed_ohlcv_fixture_v1"
OBSERVED_CLOSES_SCHEMA_VERSION = "event_alpha_observed_ohlcv_v1"
_PRICE_KIND_BY_SCHEMA_VERSION = {
    SYNTHETIC_CLOSES_SCHEMA_VERSION: "synthetic_fixture",
    OBSERVED_CLOSES_SCHEMA_VERSION: "observed_market_prices",
}
_CLOSE_DOCUMENT_FIELDS = frozenset(
    {
        "schema_version",
        "symbol",
        "coin_id",
        "interval_policy",
        "candidate_observed_at",
        "rows",
    }
)
_CLOSE_ROW_FIELDS = frozenset(
    {
        "symbol",
        "coin_id",
        "close_observed_at",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source",
        "observation_id",
    }
)
_CANONICAL_ARTIFACT_BASENAMES = frozenset(
    name.casefold() for name in schema_v1.FILENAME_TO_SCHEMA_ID
)
_MAX_AUTHORITY_BYTES = 32 * 1024 * 1024
_MAX_CLOSE_BYTES = 128 * 1024 * 1024
_MAX_AUTHORITY_ROWS = 250_000
_MAX_CLOSE_ROWS = 1_000_000
_SYNTHETIC_LINEAGE_RE = re.compile(
    r"(?:^|[:_./-])(?:fixture|synthetic|test|mock)(?:$|[:_./-])",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(?:\bbearer\s+[a-z0-9._-]{12,}\b|\bsk-(?:proj-)?[a-z0-9_-]{12,}\b|"
    r"\b(?:ghp|gho|ghu|github_pat|xoxb|xoxp)_[a-z0-9_]{16,}\b|"
    r"\b\d{6,12}:[a-z0-9_-]{20,}\b)",
    re.IGNORECASE,
)
_SAFE_SECRET_VALUES = frozenset(
    {"", "***", "<redacted>", "[redacted]", "false", "missing", "none", "redacted"}
)


@dataclass(frozen=True)
class ObservedOutcomeOperatorResult:
    """Stable payload-free operator result used by CLI and tests."""

    ok: bool
    mode: str
    errors: tuple[str, ...]
    outcome: dict[str, Any] | None
    candidate_rows_supplied: int
    core_rows_supplied: int
    observations_supplied: int
    observations_accepted: int
    written: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": OPERATOR_CONTRACT_VERSION,
            "ok": self.ok,
            "mode": self.mode,
            "errors": list(self.errors),
            "candidate_rows_supplied": self.candidate_rows_supplied,
            "core_rows_supplied": self.core_rows_supplied,
            "observations_supplied": self.observations_supplied,
            "observations_accepted": self.observations_accepted,
            "written": self.written,
            "outcome": dict(self.outcome) if self.outcome is not None else None,
            "research_only": True,
            "no_send_rehearsal": True,
            "send_requested": False,
            "notifications_sent": 0,
            "trades_created": 0,
            "paper_trades_created": 0,
            "normal_rsi_signal_rows_written": 0,
            "triggered_fades_created": 0,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass(frozen=True)
class _StrictJsonlResult:
    rows: tuple[dict[str, Any], ...]
    supplied: int
    errors: tuple[str, ...]


@dataclass(frozen=True)
class _CloseDocumentResult:
    rows: tuple[dict[str, Any], ...]
    supplied: int
    price_data_kind: str | None
    errors: tuple[str, ...]


@dataclass(frozen=True)
class _OperatorRequest:
    mode: str
    candidate_path: Path
    core_path: Path
    closes_path: Path
    evaluation: datetime | None
    captured_now: datetime
    errors: tuple[str, ...]


@dataclass(frozen=True)
class _AuthoritySelection:
    candidate: dict[str, Any] | None
    core: dict[str, Any] | None
    candidate_rows_supplied: int
    core_rows_supplied: int
    errors: tuple[str, ...]


@dataclass(frozen=True)
class _OperatorBuild:
    outcome: dict[str, Any] | None
    observations_supplied: int
    observations_accepted: int
    errors: tuple[str, ...]


def run_observed_outcome_operator(
    candidate_path: str | Path,
    core_path: str | Path,
    closes_path: str | Path,
    candidate_id: str,
    core_id: str,
    evaluated_at: Any,
    *,
    profile_assertion: str | None = None,
    artifact_namespace_assertion: str | None = None,
    out_path: str | Path | None = None,
    confirm: bool = False,
) -> ObservedOutcomeOperatorResult:
    """Preview or create one isolated exact-authority outcome artifact."""

    request = _prepare_operator_request(
        candidate_path,
        core_path,
        closes_path,
        candidate_id,
        core_id,
        evaluated_at,
        profile_assertion=profile_assertion,
        artifact_namespace_assertion=artifact_namespace_assertion,
        out_path=out_path,
        confirm=confirm,
    )
    if request.errors:
        return _operator_result(mode=request.mode, errors=request.errors)

    authority = _load_authority_selection(
        request.candidate_path,
        request.core_path,
        candidate_id=candidate_id,
        core_id=core_id,
        profile_assertion=profile_assertion,
        artifact_namespace_assertion=artifact_namespace_assertion,
    )
    if authority.errors or authority.candidate is None or authority.core is None:
        return _operator_result(
            mode=request.mode,
            errors=authority.errors,
            candidate_rows=authority.candidate_rows_supplied,
            core_rows=authority.core_rows_supplied,
        )

    assert request.evaluation is not None
    built = _build_operator_outcome(
        request.closes_path,
        candidate=authority.candidate,
        core=authority.core,
        evaluation=request.evaluation,
    )
    if built.errors or built.outcome is None:
        return _operator_result(
            mode=request.mode,
            errors=built.errors,
            candidate_rows=authority.candidate_rows_supplied,
            core_rows=authority.core_rows_supplied,
            observations=built.observations_supplied,
            accepted=built.observations_accepted,
        )

    written, stage_errors = _stage_operator_outcome(
        built.outcome,
        out_path=out_path,
        request=request,
        candidate=authority.candidate,
    )

    return _operator_result(
        mode=request.mode,
        errors=stage_errors,
        outcome=built.outcome,
        candidate_rows=authority.candidate_rows_supplied,
        core_rows=authority.core_rows_supplied,
        observations=built.observations_supplied,
        accepted=built.observations_accepted,
        written=written,
    )


def _prepare_operator_request(
    candidate_path: Any,
    core_path: Any,
    closes_path: Any,
    candidate_id: Any,
    core_id: Any,
    evaluated_at: Any,
    *,
    profile_assertion: Any,
    artifact_namespace_assertion: Any,
    out_path: Any,
    confirm: bool,
) -> _OperatorRequest:
    mode = "stage" if out_path is not None else "preview"
    errors: set[str] = set()
    candidate_input, candidate_error = _validated_input_path(candidate_path, kind="candidate")
    core_input, core_error = _validated_input_path(core_path, kind="core")
    closes_input, closes_error = _validated_input_path(closes_path, kind="closes")
    errors.update(
        error for error in (candidate_error, core_error, closes_error) if error is not None
    )
    if out_path is None and confirm:
        errors.add("confirmation_without_output")
    if out_path is not None and not confirm:
        errors.add("confirmation_required")
    if not _canonical_text(candidate_id):
        errors.add("candidate_id_invalid")
    if not _canonical_text(core_id):
        errors.add("core_id_invalid")
    for value, reason in (
        (profile_assertion, "profile_assertion_invalid"),
        (artifact_namespace_assertion, "artifact_namespace_assertion_invalid"),
    ):
        if value is not None and not _canonical_text(value):
            errors.add(reason)
    evaluation = outcome_eligibility.parse_aware_time(evaluated_at)
    captured_now = _utc_now()
    if evaluation is None:
        errors.add("evaluated_at_invalid")
    elif evaluation > captured_now:
        errors.add("evaluated_at_in_future")
    return _OperatorRequest(
        mode,
        candidate_input,
        core_input,
        closes_input,
        evaluation,
        captured_now,
        tuple(sorted(errors)),
    )


def _load_authority_selection(
    candidate_path: Path,
    core_path: Path,
    *,
    candidate_id: str,
    core_id: str,
    profile_assertion: str | None,
    artifact_namespace_assertion: str | None,
) -> _AuthoritySelection:
    candidate_read = _read_authority_jsonl(
        candidate_path, kind="candidate", max_bytes=_MAX_AUTHORITY_BYTES
    )
    core_read = _read_authority_jsonl(
        core_path, kind="core", max_bytes=_MAX_AUTHORITY_BYTES
    )
    errors = set((*candidate_read.errors, *core_read.errors))
    if not errors and any(
        not outcome_eligibility.valid_candidate_authority(row)
        for row in candidate_read.rows
    ):
        errors.add("candidate_authority_file_invalid")
    if not errors and any(
        not outcome_eligibility.valid_core_authority(row) for row in core_read.rows
    ):
        errors.add("core_authority_file_invalid")
    selected = [
        row for row in candidate_read.rows if row.get("candidate_id") == candidate_id
    ]
    candidate = selected[0] if len(selected) == 1 else None
    if not errors and candidate is None:
        errors.add("candidate_selection_count_invalid")
    if candidate is not None:
        if candidate.get("core_opportunity_id") != core_id:
            errors.add("candidate_core_id_mismatch")
        if profile_assertion is not None and candidate.get("profile") != profile_assertion:
            errors.add("profile_assertion_mismatch")
        if (
            artifact_namespace_assertion is not None
            and candidate.get("artifact_namespace") != artifact_namespace_assertion
        ):
            errors.add("artifact_namespace_assertion_mismatch")
    core = _select_exact_core(core_read.rows, candidate=candidate, core_id=core_id)
    if candidate is not None and core is None:
        errors.add("core_selection_count_invalid")
    return _AuthoritySelection(
        candidate,
        core,
        candidate_read.supplied,
        core_read.supplied,
        tuple(sorted(errors)),
    )


def _select_exact_core(
    rows: tuple[dict[str, Any], ...],
    *,
    candidate: Mapping[str, Any] | None,
    core_id: str,
) -> dict[str, Any] | None:
    if candidate is None:
        return None
    context = (
        core_id,
        candidate.get("run_id"),
        candidate.get("profile"),
        candidate.get("artifact_namespace"),
    )
    selected = [row for row in rows if _core_context(row) == context]
    return selected[0] if len(selected) == 1 else None


def _build_operator_outcome(
    closes_path: Path,
    *,
    candidate: Mapping[str, Any],
    core: Mapping[str, Any],
    evaluation: datetime,
) -> _OperatorBuild:
    close_read = _read_close_document(closes_path, candidate=candidate)
    if close_read.errors or close_read.price_data_kind is None:
        return _OperatorBuild(None, close_read.supplied, 0, close_read.errors)
    build = observed_outcome_builder.build_observed_outcome(
        (candidate,),
        (core,),
        close_read.rows,
        evaluated_at=evaluation,
        price_data_kind=close_read.price_data_kind,
    )
    errors = {f"builder_{reason}" for reason in build.build_errors}
    outcome = dict(build.outcome) if build.outcome is not None else None
    if outcome is None and not errors:
        errors.add("builder_outcome_missing")
    if outcome is not None:
        errors.update(_outcome_contract_errors(outcome))
    return _OperatorBuild(
        outcome,
        build.observations_supplied,
        build.observations_accepted,
        tuple(sorted(errors)),
    )


def _stage_operator_outcome(
    outcome: Mapping[str, Any],
    *,
    out_path: str | Path | None,
    request: _OperatorRequest,
    candidate: Mapping[str, Any],
) -> tuple[bool, tuple[str, ...]]:
    if out_path is None:
        return False, ()
    target, errors = _validated_output_path(
        out_path,
        candidate_path=request.candidate_path,
        core_path=request.core_path,
        closes_path=request.closes_path,
        candidate=candidate,
    )
    if errors or target is None:
        return False, errors
    write_error = _create_outcome_jsonl(
        target,
        outcome,
        profile=str(candidate.get("profile") or "default"),
        artifact_namespace=str(candidate.get("artifact_namespace") or "default"),
        now=request.captured_now,
    )
    return (write_error is None), ((write_error,) if write_error is not None else ())


def _read_authority_jsonl(
    path: str | Path,
    *,
    kind: str,
    max_bytes: int,
) -> _StrictJsonlResult:
    raw, read_error = _read_exact_bytes(path, kind=kind, max_bytes=max_bytes)
    if read_error is not None:
        return _StrictJsonlResult((), 0, (read_error,))
    assert raw is not None
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        return _StrictJsonlResult((), 0, (f"{kind}_jsonl_invalid",))
    lines = text.splitlines()
    supplied = sum(1 for line in lines if line.strip())
    if not lines or supplied == 0 or supplied > _MAX_AUTHORITY_ROWS:
        return _StrictJsonlResult((), supplied, (f"{kind}_jsonl_invalid",))
    if any(not line.strip() for line in lines):
        return _StrictJsonlResult((), supplied, (f"{kind}_jsonl_invalid",))
    rows: list[dict[str, Any]] = []
    try:
        for line in lines:
            value = artifact_json_lines.loads_no_duplicate_keys(line)
            if not isinstance(value, Mapping) or not _json_value_is_strict(value):
                raise ValueError
            rows.append(dict(value))
    except (json.JSONDecodeError, ValueError):
        return _StrictJsonlResult((), supplied, (f"{kind}_jsonl_invalid",))
    return _StrictJsonlResult(tuple(rows), supplied, ())


def _read_close_document(
    path: str | Path,
    *,
    candidate: Mapping[str, Any],
) -> _CloseDocumentResult:
    raw, read_error = _read_exact_bytes(
        path,
        kind="closes",
        max_bytes=_MAX_CLOSE_BYTES,
    )
    if read_error is not None:
        return _CloseDocumentResult((), 0, None, (read_error,))
    assert raw is not None
    try:
        value = artifact_json_lines.loads_no_duplicate_keys(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, ValueError):
        return _CloseDocumentResult((), 0, None, ("closes_document_invalid",))
    if (
        not isinstance(value, Mapping)
        or not _json_value_is_strict(value)
        or set(value) != _CLOSE_DOCUMENT_FIELDS
    ):
        return _CloseDocumentResult((), 0, None, ("closes_document_invalid",))

    schema_version = value.get("schema_version")
    price_data_kind = _PRICE_KIND_BY_SCHEMA_VERSION.get(schema_version)
    rows_value = value.get("rows")
    supplied = len(rows_value) if isinstance(rows_value, list) else 0
    if price_data_kind is None:
        return _CloseDocumentResult((), supplied, None, ("closes_schema_invalid",))
    if (
        not _canonical_text(value.get("symbol"))
        or not _canonical_text(value.get("coin_id"))
        or not _canonical_text(value.get("interval_policy"))
        or value.get("symbol") != candidate.get("symbol")
        or value.get("coin_id") != candidate.get("coin_id")
        or outcome_eligibility.parse_aware_time(value.get("candidate_observed_at"))
        != outcome_eligibility.parse_aware_time(candidate.get("observed_at"))
    ):
        return _CloseDocumentResult(
            (), supplied, price_data_kind, ("closes_authority_mismatch",)
        )
    if (
        not isinstance(rows_value, list)
        or not rows_value
        or supplied > _MAX_CLOSE_ROWS
    ):
        return _CloseDocumentResult(
            (), supplied, price_data_kind, ("closes_rows_invalid",)
        )

    rows: list[dict[str, Any]] = []
    timestamps: set[datetime] = set()
    observation_ids: set[str] = set()
    for raw_row in rows_value:
        if not isinstance(raw_row, Mapping) or set(raw_row) != _CLOSE_ROW_FIELDS:
            return _CloseDocumentResult(
                (), supplied, price_data_kind, ("closes_rows_invalid",)
            )
        row = dict(raw_row)
        observed_at = outcome_eligibility.parse_aware_time(row.get("close_observed_at"))
        observation_id = row.get("observation_id")
        source = row.get("source")
        open_price = _finite_number(row.get("open"))
        high_price = _finite_number(row.get("high"))
        low_price = _finite_number(row.get("low"))
        close_price = _finite_number(row.get("close"))
        volume = _finite_number(row.get("volume"))
        if (
            row.get("symbol") != value.get("symbol")
            or row.get("coin_id") != value.get("coin_id")
            or observed_at is None
            or not _canonical_text(source)
            or not _canonical_text(observation_id)
            or open_price is None
            or high_price is None
            or low_price is None
            or close_price is None
            or volume is None
            or min(open_price, high_price, low_price, close_price) <= 0
            or volume < 0
            or low_price > min(open_price, close_price)
            or high_price < max(open_price, close_price)
            or low_price > high_price
        ):
            return _CloseDocumentResult(
                (), supplied, price_data_kind, ("closes_rows_invalid",)
            )
        assert isinstance(observation_id, str)
        if observed_at in timestamps or observation_id in observation_ids:
            return _CloseDocumentResult(
                (), supplied, price_data_kind, ("closes_rows_ambiguous",)
            )
        if price_data_kind == "observed_market_prices" and _synthetic_lineage(
            str(source), observation_id
        ):
            return _CloseDocumentResult(
                (), supplied, price_data_kind, ("observed_closes_claim_fixture_lineage",)
            )
        timestamps.add(observed_at)
        observation_ids.add(observation_id)
        rows.append(row)
    return _CloseDocumentResult(tuple(rows), supplied, price_data_kind, ())


def _read_exact_bytes(
    path: str | Path,
    *,
    kind: str,
    max_bytes: int,
) -> tuple[bytes | None, str | None]:
    try:
        raw = artifact_fingerprints.read_regular_file_bytes(Path(path).expanduser())
    except artifact_fingerprints.FingerprintError as exc:
        reason = str(exc)
        if reason == "path_missing":
            return None, f"{kind}_path_missing"
        if "symlink" in reason or "non_regular" in reason:
            return None, f"{kind}_path_unsafe"
        return None, f"{kind}_read_failed"
    if len(raw) > max_bytes:
        return None, f"{kind}_file_too_large"
    return raw, None


def _validated_input_path(
    value: Any,
    *,
    kind: str,
) -> tuple[Path, str | None]:
    if value is None or (type(value) is str and not value.strip()):
        return Path("."), f"{kind}_path_invalid"
    try:
        path = Path(value).expanduser()
    except (OSError, TypeError, ValueError, RuntimeError):
        return Path("."), f"{kind}_path_invalid"
    if "\x00" in str(path):
        return Path("."), f"{kind}_path_invalid"
    return path, None


def _outcome_contract_errors(outcome: Mapping[str, Any]) -> tuple[str, ...]:
    errors: set[str] = set()
    try:
        json.dumps(dict(outcome), allow_nan=False, sort_keys=True)
    except (TypeError, ValueError):
        errors.add("outcome_json_invalid")
    if schema_v1.validate_row_against_schema(outcome, "outcome_row_v1"):
        errors.add("outcome_schema_invalid")
    if outcome_eligibility.validate_contract(outcome):
        errors.add("outcome_eligibility_contract_invalid")
    if artifact_paths.has_operator_absolute_path(outcome) or _contains_absolute_path(
        outcome
    ):
        errors.add("outcome_absolute_path_forbidden")
    if secret_checks.secret_leak_count((dict(outcome),)) or _contains_secret_like_value(
        outcome
    ):
        errors.add("outcome_secret_like_value_forbidden")
    if (
        outcome.get("research_only") is not True
        or outcome.get("no_send_rehearsal") is not True
        or any(
            outcome.get(field) is not False
            for field in (
                "sent",
                "normal_rsi_signal_written",
                "triggered_fade_created",
                "paper_trade_created",
                "trade_created",
            )
        )
    ):
        errors.add("outcome_safety_contract_invalid")
    return tuple(sorted(errors))


def _validated_output_path(
    value: str | Path,
    *,
    candidate_path: Path,
    core_path: Path,
    closes_path: Path,
    candidate: Mapping[str, Any],
) -> tuple[Path | None, tuple[str, ...]]:
    errors: set[str] = set()
    try:
        raw = Path(value).expanduser()
    except (OSError, TypeError, ValueError, RuntimeError):
        return None, ("output_path_invalid",)
    if not raw.is_absolute():
        errors.add("output_path_must_be_absolute")
        return None, tuple(sorted(errors))
    if raw.suffix.casefold() != ".jsonl":
        errors.add("output_path_must_be_jsonl")
    if raw.name.casefold() in _CANONICAL_ARTIFACT_BASENAMES:
        errors.add("output_canonical_name_forbidden")
    try:
        resolved_parent = raw.parent.resolve(strict=True)
        parent_info = resolved_parent.lstat()
        if not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode):
            errors.add("output_parent_unsafe")
        if resolved_parent != raw.parent:
            errors.add("output_parent_unsafe")
    except (FileNotFoundError, OSError):
        errors.add("output_parent_unsafe")
        return None, tuple(sorted(errors))
    target = resolved_parent / raw.name
    if os.path.lexists(target):
        errors.add("output_target_exists")
    input_paths: set[Path] = set()
    for input_path in (candidate_path, core_path, closes_path):
        try:
            input_paths.add(input_path.expanduser().resolve(strict=True))
        except (FileNotFoundError, OSError):
            errors.add("output_input_alias_unverifiable")
    if target in input_paths:
        errors.add("output_input_alias_forbidden")
    roots, exact_paths, configured_error = _configured_artifact_paths(candidate)
    if configured_error:
        errors.add("output_configured_roots_unverifiable")
    if any(_path_is_within(target, root) for root in roots):
        errors.add("output_configured_root_forbidden")
    if target in exact_paths:
        errors.add("output_canonical_path_forbidden")
    return (target if not errors else None), tuple(sorted(errors))


def _configured_artifact_paths(
    candidate: Mapping[str, Any],
) -> tuple[tuple[Path, ...], frozenset[Path], bool]:
    roots: set[Path] = set()
    exact_paths: set[Path] = set()
    try:
        from ... import config

        for name in ("EVENT_ALPHA_ARTIFACT_BASE_DIR", "EVENT_DISCOVERY_CACHE_DIR"):
            value = getattr(config, name, None)
            if value not in (None, ""):
                roots.add(Path(value).expanduser().resolve(strict=False))
        for name in ("EVENT_ALPHA_OUTCOMES_PATH", "EVENT_CORE_OPPORTUNITY_STORE_PATH"):
            value = getattr(config, name, None)
            if value not in (None, ""):
                exact_paths.add(Path(value).expanduser().resolve(strict=False))
        context = artifact_context.context_from_profile(
            str(candidate.get("profile") or "default"),
            artifact_namespace=str(candidate.get("artifact_namespace") or "default"),
        )
        roots.add(context.base_dir.expanduser().resolve(strict=False))
        roots.add(context.namespace_dir.expanduser().resolve(strict=False))
        exact_paths.add(context.outcomes_path.expanduser().resolve(strict=False))
        exact_paths.add(
            (context.namespace_dir / "event_integrated_radar_outcomes.jsonl").resolve(
                strict=False
            )
        )
    except Exception:  # noqa: BLE001 - staging must fail closed on config drift.
        return (), frozenset(), True
    return tuple(sorted(roots, key=str)), frozenset(exact_paths), False


def _create_outcome_jsonl(
    target: Path,
    outcome: Mapping[str, Any],
    *,
    profile: str,
    artifact_namespace: str,
    now: datetime,
) -> str | None:
    digest = hashlib.sha256(str(target).encode("utf-8")).hexdigest()[:16]
    lock_path = target.parent / f".event_alpha_observed_outcome_{digest}.lock"
    context = SimpleNamespace(
        namespace_dir=target.parent,
        base_dir=target.parent,
        profile=profile,
        artifact_namespace=artifact_namespace,
    )
    run_id = f"observed-outcome-{os.getpid()}-{uuid.uuid4().hex}"
    lock = artifact_locks.acquire_run_lock(
        context,
        cfg=artifact_locks.EventAlphaRunLockConfig(
            enabled=True,
            stale_minutes=60.0,
            allow_overlap=False,
        ),
        run_id=run_id,
        profile=profile,
        namespace=artifact_namespace,
        command="observed-outcome-stage",
        lock_name="observed_outcome_stage",
        now=now,
        path_override=lock_path,
    )
    try:
        if not lock.owned:
            return "output_lock_unavailable"
        if os.path.lexists(target):
            return "output_target_exists"
        try:
            payload = (
                json.dumps(
                    dict(outcome),
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
        except (TypeError, UnicodeError, ValueError):
            return "output_serialization_failed"
        temp_path: Path | None = None
        linked = False
        try:
            with tempfile.NamedTemporaryFile(
                "wb",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temp_path.chmod(0o600)
            os.link(temp_path, target, follow_symlinks=False)
            linked = True
            target.chmod(0o600)
            _fsync_directory(target.parent)
            temp_path.unlink()
            temp_path = None
            _fsync_directory(target.parent)
            return None
        except FileExistsError:
            return "output_target_exists"
        except (OSError, TypeError, ValueError):
            if linked:
                try:
                    target.unlink(missing_ok=True)
                except OSError:
                    pass
            return "output_write_failed"
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
    finally:
        artifact_locks.release_run_lock(lock)


def _operator_result(
    *,
    mode: str,
    errors: Any = (),
    outcome: dict[str, Any] | None = None,
    candidate_rows: int = 0,
    core_rows: int = 0,
    observations: int = 0,
    accepted: int = 0,
    written: bool = False,
) -> ObservedOutcomeOperatorResult:
    stable_errors = tuple(sorted({str(error) for error in errors if str(error)}))
    return ObservedOutcomeOperatorResult(
        ok=not stable_errors and outcome is not None,
        mode=mode,
        errors=stable_errors,
        outcome=dict(outcome) if outcome is not None else None,
        candidate_rows_supplied=max(0, int(candidate_rows)),
        core_rows_supplied=max(0, int(core_rows)),
        observations_supplied=max(0, int(observations)),
        observations_accepted=max(0, int(accepted)),
        written=bool(written),
    )


def _core_context(row: Mapping[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (
        row.get("core_opportunity_id"),
        row.get("run_id"),
        row.get("profile"),
        row.get("artifact_namespace"),
    )


def _finite_number(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _synthetic_lineage(source: str, observation_id: str) -> bool:
    return bool(
        _SYNTHETIC_LINEAGE_RE.search(source)
        or _SYNTHETIC_LINEAGE_RE.search(observation_id)
    )


def _canonical_text(value: Any) -> bool:
    if type(value) is not str or not value or value != value.strip():
        return False
    if unicodedata.normalize("NFC", value) != value:
        return False
    return not any(
        unicodedata.category(character).startswith("C")
        or unicodedata.category(character) in {"Zl", "Zp"}
        for character in value
    )


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _contains_absolute_path(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_absolute_path(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_absolute_path(item) for item in value)
    if type(value) is not str or not value:
        return False
    try:
        return Path(value).expanduser().is_absolute()
    except (OSError, RuntimeError, ValueError):
        return True


def _json_value_is_strict(value: Any) -> bool:
    try:
        json.dumps(value, allow_nan=False, sort_keys=True)
        return True
    except (TypeError, UnicodeError, ValueError):
        return False


def _contains_secret_like_value(value: Any) -> bool:
    if isinstance(value, Mapping):
        secret_names = {
            *(str(name).casefold() for name in schema_v1.SECRET_FIELD_NAMES),
            *(str(name).casefold() for name in secret_checks.SECRET_FIELD_NAMES),
        }
        secret_fragments = tuple(
            str(fragment).casefold() for fragment in schema_v1.SECRET_FIELD_FRAGMENTS
        )
        for raw_key, item in value.items():
            key = str(raw_key).casefold()
            safe_value = str(item or "").strip().casefold() in _SAFE_SECRET_VALUES
            if not safe_value and (
                key in secret_names or any(fragment in key for fragment in secret_fragments)
            ):
                return True
            if _contains_secret_like_value(item):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_contains_secret_like_value(item) for item in value)
    return type(value) is str and bool(_SECRET_VALUE_RE.search(value))


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = (
    "OBSERVED_CLOSES_SCHEMA_VERSION",
    "OPERATOR_CONTRACT_VERSION",
    "ObservedOutcomeOperatorResult",
    "SYNTHETIC_CLOSES_SCHEMA_VERSION",
    "run_observed_outcome_operator",
)
