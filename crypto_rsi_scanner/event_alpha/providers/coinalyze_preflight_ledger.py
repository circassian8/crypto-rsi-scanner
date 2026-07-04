"""Request ledger helpers for Coinalyze preflight/rehearsal."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request

from ..artifacts import schema_v1

class _LedgeredCoinalyzeOpener:
    def __init__(
        self,
        *,
        ledger_path: Path,
        api_key: str,
        max_requests: int,
        opener: Callable[[Request, float], Any] | None,
        now: datetime,
    ) -> None:
        self.ledger_path = ledger_path
        self.api_key = api_key
        self.max_requests = max_requests
        self.opener = opener
        self.started_now = now
        self.used = 0

    def __call__(self, request: Request, timeout: float) -> Any:
        before = self.max_requests - self.used
        if before <= 0:
            exc = RequestBudgetExceeded("coinalyze request budget exceeded")
            self._append_row(request, started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc), before=before, after=before, exc=exc)
            raise exc
        self.used += 1
        started = datetime.now(timezone.utc)
        try:
            response = (self.opener or _default_urlopen)(request, timeout)
        except Exception as exc:  # noqa: BLE001
            finished = datetime.now(timezone.utc)
            self._append_row(request, started_at=started, finished_at=finished, before=before, after=before - 1, exc=exc)
            raise
        return _LedgeredCoinalyzeResponse(
            response=response,
            request=request,
            ledger_path=self.ledger_path,
            started_at=started,
            budget_before=before,
            budget_after=before - 1,
            api_key=self.api_key,
        )

    def _append_row(
        self,
        request: Request,
        *,
        started_at: datetime,
        finished_at: datetime,
        before: int,
        after: int,
        exc: Exception,
    ) -> None:
        _append_ledger_row(
            self.ledger_path,
            _ledger_row(
                request,
                started_at=started_at,
                finished_at=finished_at,
                budget_before=before,
                budget_after=after,
                success=False,
                api_key=self.api_key,
                error=exc,
            ),
        )


class _LedgeredCoinalyzeResponse:
    def __init__(
        self,
        *,
        response: Any,
        request: Request,
        ledger_path: Path,
        started_at: datetime,
        budget_before: int,
        budget_after: int,
        api_key: str,
    ) -> None:
        self.response = response
        self.request = request
        self.ledger_path = ledger_path
        self.started_at = started_at
        self.budget_before = budget_before
        self.budget_after = budget_after
        self.api_key = api_key
        self.payload: bytes | None = None
        self.entered: Any = None

    def __enter__(self) -> "_LedgeredCoinalyzeResponse":
        if hasattr(self.response, "__enter__"):
            self.entered = self.response.__enter__()
        else:
            self.entered = self.response
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        finished = datetime.now(timezone.utc)
        success = exc is None
        row = _ledger_row(
            self.request,
            started_at=self.started_at,
            finished_at=finished,
            budget_before=self.budget_before,
            budget_after=self.budget_after,
            success=success,
            api_key=self.api_key,
            response=self.entered or self.response,
            payload=self.payload,
            error=exc if isinstance(exc, Exception) else None,
        )
        _append_ledger_row(self.ledger_path, row)
        if hasattr(self.response, "__exit__"):
            return bool(self.response.__exit__(exc_type, exc, tb))
        return False

    def read(self) -> bytes:
        target = self.entered or self.response
        raw = target.read()
        self.payload = raw
        return raw


class RequestBudgetExceeded(RuntimeError):
    pass


def _default_urlopen(request: Request, timeout: float) -> Any:
    from urllib.request import urlopen

    return urlopen(request, timeout=timeout)


def _ledger_row(
    request: Request,
    *,
    started_at: datetime,
    finished_at: datetime,
    budget_before: int,
    budget_after: int,
    success: bool,
    api_key: str,
    response: Any | None = None,
    payload: bytes | None = None,
    error: Exception | None = None,
) -> dict[str, Any]:
    status_code = _status_code(response, error)
    safe_error = _safe_error_message(error, api_key) if error else None
    return {
        "schema_version": "event_coinalyze_request_ledger_v1",
        "provider": "coinalyze",
        "endpoint": _endpoint(request.full_url),
        "sanitized_url": _sanitized_url(request.full_url),
        "method": getattr(request, "method", None) or request.get_method(),
        "started_at": started_at.astimezone(timezone.utc).isoformat(),
        "finished_at": finished_at.astimezone(timezone.utc).isoformat(),
        "duration_ms": max(0, int((finished_at - started_at).total_seconds() * 1000)),
        "status_code": status_code,
        "success": bool(success),
        "result_count": _result_count(payload),
        "error_class": type(error).__name__ if error else None,
        "error_message_safe": safe_error,
        "request_budget_before": budget_before,
        "request_budget_after": budget_after,
        "live_call_allowed": True,
        "token_redacted": True,
        "no_send_rehearsal": True,
    }


def _append_ledger_row(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        stamped = schema_v1.stamp_artifact_row(row, path=path)
        fh.write(json.dumps(stamped, sort_keys=True) + "\n")


def _endpoint(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path.rstrip("/").rsplit("/", 1)[-1]


def _sanitized_url(url: str) -> str:
    parsed = urlparse(url)
    query = urlencode(
        [
            (key, "<redacted>" if _secret_param(key) else value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        ]
    )
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, ""))


def _secret_param(key: str) -> bool:
    lowered = key.casefold()
    return "key" in lowered or "token" in lowered or "secret" in lowered


def _status_code(response: Any | None, error: Exception | None) -> int | None:
    if isinstance(error, HTTPError):
        return int(error.code)
    for obj in (response,):
        if obj is None:
            continue
        for attr in ("status", "code"):
            value = getattr(obj, attr, None)
            if value not in (None, ""):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass
        getcode = getattr(obj, "getcode", None)
        if callable(getcode):
            try:
                return int(getcode())
            except (TypeError, ValueError):
                pass
    return None


def _result_count(payload: bytes | None) -> int | None:
    if payload is None:
        return None
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(parsed, list):
        return len(parsed)
    if isinstance(parsed, Mapping):
        for key in ("data", "result", "results", "snapshots"):
            value = parsed.get(key)
            if isinstance(value, list):
                return len(value)
        return 1
    return None


def _safe_error_message(error: Exception | None, api_key: str) -> str | None:
    if error is None:
        return None
    text = str(error)
    if isinstance(error, HTTPError):
        text = f"HTTP {error.code}: {error.reason}"
    elif isinstance(error, URLError):
        text = f"URL error: {error.reason}"
    if api_key:
        text = text.replace(api_key, "<coinalyze-api-key>")
    return text[:240]
