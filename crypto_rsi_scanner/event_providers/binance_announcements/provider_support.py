"""Binance announcement provider for event discovery.

The default path is fixture-only for deterministic tests. Live WebSocket
ingestion is explicit opt-in and research-only.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

import aiohttp

from ... import config
from ...event_core.models import RawDiscoveredEvent
from .._announcement_common import (
    _announcement_items,
    _announcement_items_with_acquisition_time,
    _raw_event_from_item,
    fetch_announcement_events,
)

log = logging.getLogger(__name__)

SessionFactory = Callable[..., Any]
Clock = Callable[[], float]
RandomFactory = Callable[[], str]


def initialize_binance_announcement_provider(
    self: Any,
    path: str | Path | None,
    *,
    required: bool = False,
    live_enabled: bool = False,
    api_key: str = "",
    api_secret: str = "",
    ws_url: str = "wss://api.binance.com/sapi/wss",
    topic: str = "com_announcement_en",
    recv_window_ms: int = 30000,
    listen_seconds: float = 5.0,
    max_messages: int = 20,
    ping_interval_seconds: float = 30.0,
    session_factory: SessionFactory | None = None,
    clock: Clock | None = None,
    random_factory: RandomFactory | None = None,
) -> None:
    self.path = path
    self.required = required
    self.live_enabled = live_enabled
    self.api_key = api_key
    self.api_secret = api_secret
    self.ws_url = ws_url
    self.topic = topic
    self.recv_window_ms = recv_window_ms
    self.listen_seconds = listen_seconds
    self.max_messages = max_messages
    self.ping_interval_seconds = ping_interval_seconds
    self.session_factory = session_factory or aiohttp.ClientSession
    self.clock = clock or time.time
    self.random_factory = random_factory or (lambda: secrets.token_hex(16))


def fetch_binance_announcement_events(self: Any, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
    if self.path is None and self.live_enabled:
        return self._fetch_live_events(start, end)
    return fetch_announcement_events(
        self.path,
        provider=self.name,
        start=start,
        end=end,
        required=self.required,
    )


def fetch_binance_live_events(self: Any, start: datetime, end: datetime) -> list[RawDiscoveredEvent]:
    if not self.api_key or not self.api_secret:
        if self.required:
            raise ValueError("Binance live announcement fetch requires API key and secret")
        log.warning("Binance live announcement fetch skipped: missing API key or secret")
        return []
    start_utc = _as_utc(start)
    end_utc = _as_utc(end)
    try:
        items = _run_async(self._fetch_live_items())
    except Exception as exc:  # noqa: BLE001
        if self.required:
            raise
        log.warning("Binance live announcement fetch failed: %s", _safe_error(exc, self.api_key, self.api_secret))
        return []

    events: list[RawDiscoveredEvent] = []
    for item in items:
        event = _raw_event_from_item(item, self.name)
        if event is None:
            continue
        reference = _as_utc(event.published_at or event.fetched_at)
        if start_utc <= reference <= end_utc:
            events.append(event)
    return events


async def fetch_binance_live_items(self: Any) -> list[dict[str, Any]]:
    url = signed_binance_ws_url(
        self.ws_url,
        topic=self.topic,
        recv_window_ms=self.recv_window_ms,
        api_secret=self.api_secret,
        timestamp_ms=int(self.clock() * 1000),
        random_value=self.random_factory(),
    )
    timeout = aiohttp.ClientTimeout(total=max(5.0, self.listen_seconds + 5.0))
    headers = {"X-MBX-APIKEY": self.api_key}
    out: list[dict[str, Any]] = []
    async with self.session_factory(timeout=timeout) as session:
        async with session.ws_connect(url, headers=headers, heartbeat=self.ping_interval_seconds) as ws:
            deadline = asyncio.get_running_loop().time() + max(0.0, self.listen_seconds)
            while len(out) < max(1, self.max_messages):
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                if msg.type == aiohttp.WSMsgType.TEXT:
                    payload = json.loads(msg.data)
                    try:
                        acquired_at = datetime.fromtimestamp(float(self.clock()), tz=timezone.utc)
                        out.extend(
                            _announcement_items_with_acquisition_time(
                                _announcement_items(payload),
                                acquired_at=acquired_at,
                            )
                        )
                    except ValueError:
                        continue
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING):
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    raise RuntimeError("Binance announcement WebSocket returned an error")
    return out[: max(1, self.max_messages)]


def signed_binance_ws_url(
    ws_url: str,
    *,
    topic: str,
    recv_window_ms: int,
    api_secret: str,
    timestamp_ms: int,
    random_value: str,
) -> str:
    params = [
        ("random", random_value),
        ("topic", topic),
        ("recvWindow", str(recv_window_ms)),
        ("timestamp", str(timestamp_ms)),
    ]
    payload = urlencode(params)
    signature = hmac.new(api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    separator = "&" if "?" in ws_url else "?"
    return f"{ws_url}{separator}{payload}&signature={signature}"


def _run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    close = getattr(coro, "close", None)
    if close:
        close()
    raise RuntimeError("Binance live announcement fetch cannot run inside an active event loop")


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _safe_error(exc: Exception, api_key: str, api_secret: str) -> str:
    text = config.redact_token(str(exc))
    for token, label in ((api_key, "<binance-api-key>"), (api_secret, "<binance-api-secret>")):
        if token:
            text = text.replace(token, label)
    if "signature=" in text:
        before, _sep, after = text.partition("signature=")
        suffix = ""
        for sep in ("&", " ", "'"):
            if sep in after:
                suffix = sep + after.split(sep, 1)[1]
                break
        text = before + "signature=<signature>" + suffix
    return text
