"""Scan, signal, and outcome persistence methods."""

from __future__ import annotations

from datetime import datetime, timezone

from .connection import _clean, _now_iso, _parse_iso


class SignalsMixin:
    def save_scan(self, coin_count: int, ob_count: int, os_count: int) -> int:
        now = _now_iso()
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

    def last_scan_at(self) -> datetime | None:
        """UTC timestamp of the most recent completed scan (None if none yet)."""
        row = self.conn.execute(
            "SELECT run_at FROM scans ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row or not row["run_at"]:
            return None
        return _parse_iso(row["run_at"])

    def save_signal(self, scan_id: int, sig: dict) -> None:
        now = _now_iso()
        self.conn.execute(
            """INSERT INTO signals
            (scan_id, symbol, coin_id, flag, severity, rsi_daily, rsi_4h, rsi_weekly,
             rsi_z, rsi_delta, xrank, volume_ratio, btc_corr, divergence, conviction,
             tier, regime, regime_note, setup_type, expected_dir, market_regime, market_aligned, state_json, price,
             mcap_rank, is_new, run_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                _clean(sig.get("market_aligned")),
                _clean(sig.get("state_json")),
                _clean(sig.get("price")),
                _clean(sig.get("mcap_rank")),
                _clean(sig.get("is_new", 0)),
                now,
            ),
        )
        self.conn.commit()

    def signals_for_outcome(self, coin_id: str, since_iso: str) -> list:
        """Crossing events (is_new) for a coin, recent enough to still be maturing."""
        return self.conn.execute(
            "SELECT id, run_at, flag, price, regime, expected_dir FROM signals "
            "WHERE coin_id = ? AND is_new = 1 AND run_at >= ?",
            (coin_id, since_iso),
        ).fetchall()

    def recent_signal_coin_ids(self, since_iso: str) -> list[str]:
        """Coin IDs with recent crossing signals that may still need outcomes."""
        rows = self.conn.execute(
            "SELECT DISTINCT coin_id FROM signals "
            "WHERE is_new = 1 AND run_at >= ? AND coin_id IS NOT NULL AND coin_id != ''",
            (since_iso,),
        ).fetchall()
        return [r["coin_id"] for r in rows]

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
            "s.market_regime, s.market_aligned, s.state_json, "
            "s.conviction, s.symbol, s.severity "
            "FROM outcomes o JOIN signals s ON o.signal_id = s.id"
        ).fetchall()
