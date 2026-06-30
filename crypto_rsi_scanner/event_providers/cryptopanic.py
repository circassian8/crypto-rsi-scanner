"""CryptoPanic-style news provider for event discovery.

The default path is fixture-only for deterministic tests. Live HTTP ingestion is
explicit opt-in and research-only.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from ..event_models import RawDiscoveredEvent
from ._news_common import _news_items, fetch_news_events, news_events_from_items

log = logging.getLogger(__name__)

UrlOpen = Callable[[Request, float], Any]
DEFAULT_CRYPTOPANIC_API_BASE_URL = "https://cryptopanic.com/api/growth_weekly/v2"
GROWTH_WEEKLY_PLAN = "growth_weekly"
GROWTH_WEEKLY_ALLOWED_FILTERS = {"rising", "hot", "bullish", "bearish", "important", "saved", "lol"}
GROWTH_WEEKLY_ALLOWED_KINDS = {"news", "media", "all"}
GROWTH_WEEKLY_UNSUPPORTED_PARAMS = {
    "last_pull",
    "panic_period",
    "panic_sort",
    "search",
    "size",
    "with_content",
}


@dataclass(frozen=True)
class CryptoPanicUsageSummary:
    ledger_path: Path | None
    weekly_limit: int
    daily_soft_limit: int
    rolling_7d_requests: int
    today_requests: int
    remaining_weekly: int | None
    remaining_daily_soft: int | None
    last_request_at: datetime | None = None
    last_status_code: int | None = None
    last_error_class: str | None = None


def _urlopen_with_timeout(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)


class CryptoPanicProvider:
    name = "cryptopanic"

    def __init__(
        self,
        path: str | Path | None,
        *,
        required: bool = False,
        live_enabled: bool = False,
        api_token: str = "",
        base_url: str = DEFAULT_CRYPTOPANIC_API_BASE_URL,
        plan: str = GROWTH_WEEKLY_PLAN,
        public: bool = True,
        following: bool = False,
        filter_name: str = "",
        currencies: str = "",
        regions: str = "en",
        kind: str = "news",
        page: int = 1,
        search: str = "",
        timeout: float = 10.0,
        opener: UrlOpen | None = None,
        fetched_at: datetime | None = None,
        request_ledger_path: str | Path | None = None,
        profile: str = "",
        artifact_namespace: str = "",
        weekly_request_limit: int = 600,
        requests_per_run_limit: int = 20,
        requests_per_day_soft_limit: int = 80,
        min_seconds_between_requests: float = 1.0,
        max_pages_per_query: int = 1,
        max_currencies_per_request: int = 10,
    ) -> None:
        self.path = path
        self.required = required
        self.live_enabled = live_enabled
        self.api_token = api_token
        self.base_url = base_url
        self.plan = plan or GROWTH_WEEKLY_PLAN
        self.public = public
        self.following = following
        self.filter_name = filter_name
        self.currencies = currencies
        self.regions = regions
        self.kind = kind
        self.page = max(1, int(page or 1))
        self.search = search
        self.timeout = timeout
        self.opener = opener or _urlopen_with_timeout
        self.fetched_at = fetched_at
        self.request_ledger_path = Path(request_ledger_path).expanduser() if request_ledger_path else None
        self.profile = profile
        self.artifact_namespace = artifact_namespace
        self.weekly_request_limit = int(weekly_request_limit)
        self.requests_per_run_limit = int(requests_per_run_limit)
        self.requests_per_day_soft_limit = int(requests_per_day_soft_limit)
        self.min_seconds_between_requests = float(min_seconds_between_requests)
        self.max_pages_per_query = max(1, int(max_pages_per_query or 1))
        self.max_currencies_per_request = max(1, int(max_currencies_per_request or 1))
        self.last_warnings: tuple[str, ...] = ()
        self.last_skip_reason: str | None = None
        self.last_request_url_redacted: str | None = None
        self.last_status_code: int | None = None
        self.last_result_count: int = 0
        self.requests_attempted: int = 0

    def fetch_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        self.last_warnings = ()
        if self.path is None and self.live_enabled:
            return self._fetch_live_events(start, end)
        return fetch_news_events(
            self.path,
            provider=self.name,
            start=start,
            end=end,
            required=self.required,
        )

    def _fetch_live_events(self, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
        observed = self.fetched_at or datetime.now(timezone.utc)
        self.last_skip_reason = None
        self.last_status_code = None
        self.last_result_count = 0
        self.requests_attempted = 0
        token = self.api_token.strip()
        if not token:
            warning = "CryptoPanic live news fetch skipped: missing API token"
            self.last_warnings = (warning,)
            self.last_skip_reason = "missing_api_key"
            if self.required:
                raise ValueError("CryptoPanic live fetch requires RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN")
            log.warning(warning)
            return []

        rows: list[Mapping[str, Any]] = []
        warnings: list[str] = []
        seen_ids: set[str] = set()
        for currencies in _currency_batches(self.currencies, max_size=self.max_currencies_per_request):
            for page in range(self.page, self.page + self.max_pages_per_query):
                decision = self._quota_skip_reason(now=observed)
                if decision:
                    self.last_skip_reason = decision
                    if decision in {"quota_exhausted", "run_budget_exhausted", "daily_soft_limit_exceeded"}:
                        warnings.append(f"CryptoPanic live news fetch skipped: {decision}")
                    continue
                url = self._request_url(token, currencies=currencies, page=page)
                redacted_url = redact_cryptopanic_url(url)
                self.last_request_url_redacted = redacted_url
                status_code: int | None = None
                result_count = 0
                error_class: str | None = None
                try:
                    self._respect_min_interval(now=observed)
                    request = Request(url, headers={"Accept": "application/json", "User-Agent": "crypto-rsi-scanner/1.0"})
                    with self.opener(request, self.timeout) as response:
                        status_code = int(getattr(response, "status", getattr(response, "code", 200)))
                        if status_code >= 400:
                            raise RuntimeError(f"HTTP {status_code}")
                        raw = json.loads(response.read().decode("utf-8"))
                    fetched = [_normalize_cryptopanic_item(item) for item in _news_items(raw, allow_empty=True)]
                    result_count = len(fetched)
                    self.last_result_count += result_count
                    for item in fetched:
                        key = str(item.get("cryptopanic_id") or item.get("id") or item.get("url") or "")
                        if key and key in seen_ids:
                            continue
                        if key:
                            seen_ids.add(key)
                        rows.append(item)
                except Exception as exc:  # noqa: BLE001
                    status_code = _status_code_from_exception(exc)
                    error_class = _error_class_from_exception(exc)
                    warning = _safe_fetch_warning(exc)
                    warnings.append(warning)
                    if self.required:
                        raise
                finally:
                    if redacted_url:
                        self.requests_attempted += 1
                        self.last_status_code = status_code
                        self._record_request(
                            observed_at=observed,
                            endpoint="posts",
                            request_url_redacted=redacted_url,
                            currencies=currencies,
                            page=page,
                            status_code=status_code,
                            result_count=result_count,
                            error_class=error_class,
                        )

        if warnings:
            self.last_warnings = tuple(dict.fromkeys(warnings))
            for warning in self.last_warnings:
                log.warning(warning)
            if not rows:
                return []
        else:
            self.last_warnings = ()
        return news_events_from_items(
            rows,
            provider=self.name,
            start=start,
            end=end,
            fetched_at=observed,
        )

    def _request_url(self, token: str, *, currencies: str | None = None, page: int | None = None) -> str:
        query: dict[str, str] = {"auth_token": token}
        plan = self.plan.strip().lower() or GROWTH_WEEKLY_PLAN
        if self.following:
            query["following"] = "true"
        else:
            query["public"] = "true" if self.public else "false"
        if currencies:
            query["currencies"] = currencies
        if self.regions:
            query["regions"] = self.regions
        kind = self.kind.strip().lower()
        if kind in GROWTH_WEEKLY_ALLOWED_KINDS:
            query["kind"] = kind
        filter_name = self.filter_name.strip().lower()
        if filter_name in GROWTH_WEEKLY_ALLOWED_FILTERS:
            query["filter"] = filter_name
        if page:
            query["page"] = str(page)
        if plan == "enterprise" and self.search:
            query["search"] = self.search
        return _append_query(_posts_endpoint(self.base_url), query)

    def _quota_skip_reason(self, *, now: datetime) -> str | None:
        if self.request_ledger_path is None:
            return None
        summary = cryptopanic_usage_summary(
            self.request_ledger_path,
            now=now,
            weekly_limit=self.weekly_request_limit,
            daily_soft_limit=self.requests_per_day_soft_limit,
        )
        if self.weekly_request_limit > 0 and summary.rolling_7d_requests >= self.weekly_request_limit:
            return "quota_exhausted"
        if self.requests_per_run_limit > 0 and self.requests_attempted >= self.requests_per_run_limit:
            return "run_budget_exhausted"
        if self.requests_per_day_soft_limit > 0 and summary.today_requests >= self.requests_per_day_soft_limit:
            return "daily_soft_limit_exceeded"
        return None

    def _respect_min_interval(self, *, now: datetime) -> None:
        if self.request_ledger_path is None or self.min_seconds_between_requests <= 0:
            return
        summary = cryptopanic_usage_summary(
            self.request_ledger_path,
            now=now,
            weekly_limit=self.weekly_request_limit,
            daily_soft_limit=self.requests_per_day_soft_limit,
        )
        if summary.last_request_at is None:
            return
        elapsed = max(0.0, (now - summary.last_request_at).total_seconds())
        delay = self.min_seconds_between_requests - elapsed
        if delay > 0:
            time.sleep(min(delay, 5.0))

    def _record_request(
        self,
        *,
        observed_at: datetime,
        endpoint: str,
        request_url_redacted: str,
        currencies: str,
        page: int,
        status_code: int | None,
        result_count: int,
        error_class: str | None,
    ) -> None:
        if self.request_ledger_path is None:
            return
        row = {
            "timestamp": _as_utc(observed_at).isoformat(),
            "profile": self.profile,
            "artifact_namespace": self.artifact_namespace,
            "provider": self.name,
            "endpoint": endpoint,
            "request_kind": "live_posts",
            "request_url_redacted": request_url_redacted,
            "plan": self.plan or GROWTH_WEEKLY_PLAN,
            "currencies": currencies,
            "filter": self.filter_name if self.filter_name in GROWTH_WEEKLY_ALLOWED_FILTERS else "",
            "kind": self.kind if self.kind in GROWTH_WEEKLY_ALLOWED_KINDS else "",
            "page": page,
            "status_code": status_code,
            "result_count": result_count,
            "error_class": error_class,
        }
        try:
            self.request_ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with self.request_ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
        except OSError as exc:
            log.warning("CryptoPanic request ledger write failed: %s", type(exc).__name__)


def _safe_fetch_warning(exc: BaseException) -> str:
    """Return a warning that cannot echo the request URL or auth token."""
    if isinstance(exc, HTTPError):
        return f"CryptoPanic live news fetch failed: HTTPError status={exc.code}"
    status = getattr(exc, "status", None) or getattr(exc, "code", None)
    if status:
        return f"CryptoPanic live news fetch failed: {type(exc).__name__} status={status}"
    return f"CryptoPanic live news fetch failed: {type(exc).__name__}"


def cryptopanic_usage_summary(
    ledger_path: str | Path | None,
    *,
    now: datetime | None = None,
    weekly_limit: int = 600,
    daily_soft_limit: int = 80,
) -> CryptoPanicUsageSummary:
    path = Path(ledger_path).expanduser() if ledger_path else None
    observed = _as_utc(now or datetime.now(timezone.utc))
    week_start = observed.timestamp() - 7 * 24 * 60 * 60
    day_key = observed.date()
    rolling = 0
    today = 0
    last_request_at: datetime | None = None
    last_status_code: int | None = None
    last_error_class: str | None = None
    for row in _read_ledger_rows(path):
        ts = _parse_datetime(row.get("timestamp"))
        if ts is None:
            continue
        if ts.timestamp() >= week_start:
            rolling += 1
        if ts.date() == day_key:
            today += 1
        if last_request_at is None or ts > last_request_at:
            last_request_at = ts
            try:
                last_status_code = int(row.get("status_code")) if row.get("status_code") not in (None, "") else None
            except (TypeError, ValueError):
                last_status_code = None
            last_error_class = str(row.get("error_class") or "") or None
    return CryptoPanicUsageSummary(
        ledger_path=path,
        weekly_limit=int(weekly_limit),
        daily_soft_limit=int(daily_soft_limit),
        rolling_7d_requests=rolling,
        today_requests=today,
        remaining_weekly=max(0, int(weekly_limit) - rolling) if weekly_limit > 0 else None,
        remaining_daily_soft=max(0, int(daily_soft_limit) - today) if daily_soft_limit > 0 else None,
        last_request_at=last_request_at,
        last_status_code=last_status_code,
        last_error_class=last_error_class,
    )


def redact_cryptopanic_url(url: str) -> str:
    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "auth_token":
            query.append((key, "<redacted>"))
        else:
            query.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _posts_endpoint(base_url: str) -> str:
    clean = str(base_url or DEFAULT_CRYPTOPANIC_API_BASE_URL).strip().rstrip("/")
    if clean.endswith("/posts"):
        return clean + "/"
    return clean + "/posts/"


def _append_query(url: str, query: Mapping[str, str]) -> str:
    separator = "&" if "?" in url else "?"
    return url + separator + urlencode({key: value for key, value in query.items() if value not in (None, "")})


def _currency_batches(raw: str, *, max_size: int) -> tuple[str, ...]:
    values = [part.strip() for part in str(raw or "").replace(";", ",").split(",") if part.strip()]
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    if not deduped:
        return ("",)
    size = max(1, int(max_size or 1))
    return tuple(",".join(deduped[index:index + size]) for index in range(0, len(deduped), size))


def _normalize_cryptopanic_item(item: Mapping[str, Any]) -> Mapping[str, Any]:
    row = dict(item)
    source = row.get("source") if isinstance(row.get("source"), Mapping) else {}
    instruments = tuple(dict(inst) for inst in row.get("instruments") or () if isinstance(inst, Mapping))
    instrument_codes = tuple(
        str(inst.get("code") or "").strip().upper()
        for inst in instruments
        if str(inst.get("code") or "").strip()
    )
    content = row.get("content") if isinstance(row.get("content"), Mapping) else {}
    clean_content = content.get("clean") if isinstance(content, Mapping) else None
    original_content = content.get("original") if isinstance(content, Mapping) else None
    description = row.get("description")
    if not description and clean_content:
        description = clean_content
    normalized = {
        **row,
        "raw_id": f"cryptopanic:{row.get('id') or row.get('slug') or row.get('url') or row.get('original_url')}",
        "cryptopanic_id": row.get("id"),
        "description": description or "",
        "body": description or clean_content or "",
        "published_at": row.get("published_at") or row.get("created_at"),
        "created_at": row.get("created_at"),
        "kind": row.get("kind"),
        "source_title": source.get("title"),
        "source_domain": source.get("domain"),
        "source_type": source.get("type"),
        "source_origin": source.get("domain") or source.get("title") or "CryptoPanic",
        "original_url": row.get("original_url"),
        "cryptopanic_url": row.get("url"),
        "url": row.get("original_url") or row.get("url"),
        "source_url": row.get("original_url") or row.get("url"),
        "instruments": instruments,
        "instrument_codes": instrument_codes,
        "currency_tags": instrument_codes,
        "currencies": instruments or tuple({"code": code} for code in instrument_codes),
        "votes": row.get("votes"),
        "panic_score": row.get("panic_score"),
        "content_clean": clean_content or "",
        "content_original_present": bool(original_content),
        "source_provider": "cryptopanic",
        "provider": "cryptopanic",
        "source_class": "cryptopanic_tagged" if instrument_codes else "crypto_news",
    }
    return normalized


def _read_ledger_rows(path: Path | None) -> tuple[Mapping[str, Any], ...]:
    if path is None or not path.exists():
        return ()
    rows: list[Mapping[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, Mapping):
                rows.append(row)
    except (OSError, json.JSONDecodeError):
        return tuple(rows)
    return tuple(rows)


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _as_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _status_code_from_exception(exc: BaseException) -> int | None:
    if isinstance(exc, HTTPError):
        return int(exc.code)
    status = getattr(exc, "status", None) or getattr(exc, "code", None)
    try:
        return int(status) if status not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _error_class_from_exception(exc: BaseException) -> str:
    status = _status_code_from_exception(exc)
    if status in {403, 429}:
        return "rate_limit_or_forbidden"
    return type(exc).__name__
