"""Secret-leak checks for Event Alpha artifact doctor plugins."""

from __future__ import annotations

import re
from typing import Iterable, Mapping

SECRET_FIELD_NAMES = {
    "api_key",
    "api_secret",
    "authorization",
    "headers",
    "telegram_token",
    "token",
}

SECRET_VALUE_RE = re.compile(
    r"(?:bearer\s+[a-z0-9._-]{12,}|x-api-key|api[_-]?secret|telegram[_-]?token)",
    re.IGNORECASE,
)


def row_has_secret_field(row: Mapping[str, object]) -> bool:
    return any(str(key).lower() in SECRET_FIELD_NAMES for key in row)


def text_has_secret_like_value(text: object) -> bool:
    return bool(SECRET_VALUE_RE.search(str(text or "")))


def secret_leak_count(rows: Iterable[Mapping[str, object]]) -> int:
    count = 0
    for row in rows:
        if row_has_secret_field(row) or any(text_has_secret_like_value(value) for value in row.values()):
            count += 1
    return count
