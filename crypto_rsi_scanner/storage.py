from __future__ import annotations

import logging
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


def _clean(value: object) -> object:
    """Coerce pandas/NumPy NaN to None so SQLite stores NULL, not a NaN float."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    coin_count INTEGER,
    ob_count INTEGER,
    os_count INTEGER
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER REFERENCES scans(id),
    symbol TEXT NOT NULL,
    coin_id TEXT NOT NULL,
    flag TEXT NOT NULL,
    severity TEXT NOT NULL,
    rsi_daily REAL,
    rsi_4h REAL,
    rsi_weekly REAL,
    rsi_z REAL,
    rsi_delta REAL,
    xrank INTEGER,
    volume_ratio REAL,
    btc_corr REAL,
    divergence TEXT,
    conviction INTEGER,
    tier TEXT,
    regime TEXT,
    regime_note TEXT,
    setup_type TEXT,
    expected_dir TEXT,
    market_regime TEXT,
    price REAL,
    mcap_rank INTEGER,
    is_new INTEGER DEFAULT 0,
    run_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prev_flags (
    symbol TEXT PRIMARY KEY,
    flag TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_log (
    symbol TEXT NOT NULL,
    flag TEXT NOT NULL,
    alerted_at TEXT NOT NULL,
    PRIMARY KEY (symbol, flag)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscribers (
    chat_id TEXT PRIMARY KEY,
    name TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    subscribed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcomes (
    signal_id INTEGER NOT NULL REFERENCES signals(id),
    horizon_days INTEGER NOT NULL,
    entry_price REAL,
    exit_price REAL,
    ret_pct REAL,
    favorable INTEGER,
    evaluated_at TEXT NOT NULL,
    PRIMARY KEY (signal_id, horizon_days)
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    coin_id TEXT NOT NULL,
    setup_type TEXT,
    market_regime TEXT,
    market_aligned TEXT,
    direction TEXT NOT NULL,
    conviction INTEGER,
    entry_price REAL NOT NULL,
    entry_at TEXT NOT NULL,
    hold_days INTEGER NOT NULL,
    exit_price REAL,
    exit_at TEXT,
    ret_pct REAL,
    status TEXT NOT NULL DEFAULT 'open'
);
"""


class Storage:
    def __init__(self, db_path: Path):
        # timeout: wait (don't immediately error) when another process holds the lock.
        self.conn = sqlite3.connect(str(db_path), timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        # The daily scan (launchd) and the always-on bot listener share this one
        # SQLite file. WAL lets a reader and a writer proceed concurrently without
        # "database is locked"; busy_timeout backs the rarer writer/writer overlap.
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.executescript(_SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Additively bring an older DB up to date (CREATE IF NOT EXISTS won't
        add columns to a pre-existing table)."""
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(signals)")}
        for name, decl in (
            ("conviction", "INTEGER"),
            ("tier", "TEXT"),
            ("regime", "TEXT"),
            ("regime_note", "TEXT"),
            ("setup_type", "TEXT"),
            ("expected_dir", "TEXT"),
            ("market_regime", "TEXT"),
        ):
            if name not in cols:
                self.conn.execute(f"ALTER TABLE signals ADD COLUMN {name} {decl}")
        self._backfill_setups_once()

    def _backfill_setups_once(self) -> None:
        """One-time, on upgrade: stamp setup_type/expected_dir onto historical
        signals and re-grade their outcomes against each setup's *own* expected
        direction. Lossless — only the favorable verdict is recomputed from the
        already-stored ret_pct, so the historical report becomes meaningful
        immediately. Gated by a meta flag so it runs exactly once."""
        if self.get_meta("setup_regrade_v1"):
            return
        from .signal_registry import setup_for
        from .outcomes import favorable

        sig_rows = self.conn.execute(
            "SELECT id, flag, regime FROM signals "
            "WHERE setup_type IS NULL AND flag IS NOT NULL AND flag != ''"
        ).fetchall()
        for r in sig_rows:
            st, ed = setup_for(r["flag"], r["regime"] or "")
            self.conn.execute(
                "UPDATE signals SET setup_type = ?, expected_dir = ? WHERE id = ?",
                (st, ed, r["id"]),
            )

        out_rows = self.conn.execute(
            "SELECT o.signal_id, o.horizon_days, o.ret_pct, o.favorable, s.expected_dir "
            "FROM outcomes o JOIN signals s ON o.signal_id = s.id"
        ).fetchall()
        regraded = 0
        for r in out_rows:
            new_fav = favorable(r["expected_dir"], r["ret_pct"])
            if new_fav != r["favorable"]:
                self.conn.execute(
                    "UPDATE outcomes SET favorable = ? "
                    "WHERE signal_id = ? AND horizon_days = ?",
                    (new_fav, r["signal_id"], r["horizon_days"]),
                )
                regraded += 1

        self.conn.commit()
        self.set_meta("setup_regrade_v1", datetime.now(timezone.utc).isoformat())
        if sig_rows or regraded:
            log.info(
                "Setup migration: stamped %d signal(s), re-graded %d outcome(s)",
                len(sig_rows), regraded,
            )

    def close(self) -> None:
        self.conn.close()

    def save_scan(self, coin_count: int, ob_count: int, os_count: int) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            "INSERT INTO scans (run_at, coin_count, ob_count, os_count) VALUES (?, ?, ?, ?)",
            (now, coin_count, ob_count, os_count),
        )
        self.conn.commit()
        return cur.lastrowid

    def last_scan_counts(self) -> dict | None:
        """OB/OS counts from the most recent scan (for breadth-direction)."""
        row = self.conn.execute(
            "SELECT ob_count, os_count FROM scans ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return {"ob": row["ob_count"], "os": row["os_count"]}

    def save_signal(self, scan_id: int, sig: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO signals
            (scan_id, symbol, coin_id, flag, severity, rsi_daily, rsi_4h, rsi_weekly,
             rsi_z, rsi_delta, xrank, volume_ratio, btc_corr, divergence, conviction,
             tier, regime, regime_note, setup_type, expected_dir, market_regime, price,
             mcap_rank, is_new, run_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                scan_id,
                sig["symbol"],
                sig["coin_id"],
                sig["flag"],
                sig["severity"],
                _clean(sig.get("rsi_daily")),
                _clean(sig.get("rsi_4h")),
                _clean(sig.get("rsi_weekly")),
                _clean(sig.get("rsi_z")),
                _clean(sig.get("rsi_delta")),
                _clean(sig.get("xrank")),
                _clean(sig.get("volume_ratio")),
                _clean(sig.get("btc_corr")),
                _clean(sig.get("divergence")),
                _clean(sig.get("conviction")),
                _clean(sig.get("tier")),
                _clean(sig.get("regime")),
                _clean(sig.get("regime_note")),
                _clean(sig.get("setup_type")),
                _clean(sig.get("expected_dir")),
                _clean(sig.get("market_regime")),
                _clean(sig.get("price")),
                _clean(sig.get("mcap_rank")),
                _clean(sig.get("is_new", 0)),
                now,
            ),
        )
        self.conn.commit()

    # -- prev_flags: tracks what was flagged in the last run (for "new" detection)

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

    # -- alert_log: tracks when we last notified about a coin+flag (for cooldown)

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

    # -- subscribers: chat IDs that opted in via the bot's /start command

    def subscribe(self, chat_id: str, name: str | None = None) -> bool:
        """Add or re-activate a subscriber. Returns True if newly added/reactivated."""
        row = self.conn.execute(
            "SELECT active FROM subscribers WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        now = datetime.now(timezone.utc).isoformat()
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

    # -- meta: small key/value store (digest timing, etc.)

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
        self.set_meta("last_digest_at", datetime.now(timezone.utc).isoformat())

    # -- outcomes: forward returns measured after each crossing

    def signals_for_outcome(self, coin_id: str, since_iso: str) -> list:
        """Crossing events (is_new) for a coin, recent enough to still be maturing."""
        return self.conn.execute(
            "SELECT id, run_at, flag, price, regime, expected_dir FROM signals "
            "WHERE coin_id = ? AND is_new = 1 AND run_at >= ?",
            (coin_id, since_iso),
        ).fetchall()

    def has_outcome(self, signal_id: int, horizon: int) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM outcomes WHERE signal_id = ? AND horizon_days = ?",
                (signal_id, horizon),
            ).fetchone()
            is not None
        )

    def save_outcome(
        self,
        signal_id: int,
        horizon: int,
        entry: float,
        exit_price: float,
        ret_pct: float,
        favorable: int,
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO outcomes "
            "(signal_id, horizon_days, entry_price, exit_price, ret_pct, favorable, evaluated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                signal_id,
                horizon,
                entry,
                exit_price,
                ret_pct,
                favorable,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()

    def outcomes_joined(self) -> list:
        """All recorded outcomes joined with their signal's context for reporting."""
        return self.conn.execute(
            "SELECT o.horizon_days, o.ret_pct, o.favorable, "
            "s.flag, s.regime, s.regime_note, s.setup_type, s.expected_dir, "
            "s.conviction, s.symbol, s.severity "
            "FROM outcomes o JOIN signals s ON o.signal_id = s.id"
        ).fetchall()

    # -- paper_trades: virtual positions opened on crossings, closed at horizon

    def has_open_trade(self, coin_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM paper_trades WHERE coin_id = ? AND status = 'open' LIMIT 1",
            (coin_id,),
        ).fetchone() is not None

    def open_paper_trade(self, **t) -> None:
        self.conn.execute(
            """INSERT INTO paper_trades
            (symbol, coin_id, setup_type, market_regime, market_aligned, direction,
             conviction, entry_price, entry_at, hold_days, status)
            VALUES (?,?,?,?,?,?,?,?,?,?, 'open')""",
            (
                t["symbol"], t["coin_id"], t.get("setup_type"), t.get("market_regime"),
                t.get("market_aligned"), t["direction"], t.get("conviction"),
                t["entry_price"], t["entry_at"], t["hold_days"],
            ),
        )
        self.conn.commit()

    def open_paper_trades(self) -> list:
        return self.conn.execute(
            "SELECT * FROM paper_trades WHERE status = 'open' ORDER BY entry_at"
        ).fetchall()

    def closed_paper_trades(self) -> list:
        return self.conn.execute(
            "SELECT * FROM paper_trades WHERE status = 'closed' ORDER BY exit_at"
        ).fetchall()

    def close_paper_trade(self, trade_id: int, exit_price: float, exit_at: str,
                          ret_pct: float) -> None:
        self.conn.execute(
            "UPDATE paper_trades SET exit_price = ?, exit_at = ?, ret_pct = ?, "
            "status = 'closed' WHERE id = ?",
            (exit_price, exit_at, ret_pct, trade_id),
        )
        self.conn.commit()

    def abandon_paper_trade(self, trade_id: int) -> None:
        """Coin left the scanned universe before the trade could be priced out."""
        self.conn.execute(
            "UPDATE paper_trades SET status = 'abandoned' WHERE id = ?", (trade_id,)
        )
        self.conn.commit()
