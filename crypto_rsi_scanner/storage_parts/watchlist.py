"""Scanner state tables for previous flags, alerts, subscribers, and meta."""

from __future__ import annotations

from datetime import datetime, timezone

from .connection import _now_iso


class WatchlistMixin:
    def get_prev_flags(self) -> dict[str, str]:
        rows = self.conn.execute("SELECT symbol, flag FROM prev_flags").fetchall()
        return {r["symbol"]: r["flag"] for r in rows}

    def save_prev_flags(self, flags: dict[str, str]) -> None:
        self.conn.execute("DELETE FROM prev_flags")
        for sym, flag in flags.items():
            self.conn.execute(
                "INSERT INTO prev_flags (symbol, flag) VALUES (?, ?)", (sym, flag)
            )
        self.conn.commit()

    def is_on_cooldown(self, symbol: str, flag: str, cooldown_hours: float) -> bool:
        row = self.conn.execute(
            "SELECT alerted_at FROM alert_log WHERE symbol = ? AND flag = ?",
            (symbol, flag),
        ).fetchone()
        if not row:
            return False
        last = datetime.fromisoformat(row["alerted_at"])
        now = datetime.now(timezone.utc)
        return (now - last).total_seconds() / 3600 < cooldown_hours

    def mark_alerted(self, symbol: str, flag: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO alert_log (symbol, flag, alerted_at) VALUES (?, ?, ?)",
            (symbol, flag, now),
        )
        self.conn.commit()

    def subscribe(self, chat_id: str, name: str | None = None) -> bool:
        """Add or re-activate a subscriber. Returns True if newly added/reactivated."""
        row = self.conn.execute(
            "SELECT active FROM subscribers WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        now = _now_iso()
        if row is None:
            self.conn.execute(
                "INSERT INTO subscribers (chat_id, name, active, subscribed_at) "
                "VALUES (?, ?, 1, ?)",
                (chat_id, name, now),
            )
            self.conn.commit()
            return True
        if row["active"] == 0:
            self.conn.execute(
                "UPDATE subscribers SET active = 1, name = COALESCE(?, name) WHERE chat_id = ?",
                (name, chat_id),
            )
            self.conn.commit()
            return True
        return False  # already active

    def unsubscribe(self, chat_id: str) -> bool:
        """Mark a subscriber inactive. Returns True if they were active."""
        cur = self.conn.execute(
            "UPDATE subscribers SET active = 0 WHERE chat_id = ? AND active = 1",
            (chat_id,),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def active_subscribers(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT chat_id FROM subscribers WHERE active = 1 ORDER BY subscribed_at"
        ).fetchall()
        return [r["chat_id"] for r in rows]

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value)
        )
        self.conn.commit()

    def digest_due(self, interval_hours: float) -> bool:
        last = self.get_meta("last_digest_at")
        if not last:
            return True
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
        return elapsed / 3600 >= interval_hours

    def mark_digest_sent(self) -> None:
        self.set_meta("last_digest_at", _now_iso())
