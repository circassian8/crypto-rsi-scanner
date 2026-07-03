"""Additive storage migrations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


class MigrationsMixin:
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
            ("market_aligned", "TEXT"),
            ("state_json", "TEXT"),
        ):
            if name not in cols:
                self.conn.execute(f"ALTER TABLE signals ADD COLUMN {name} {decl}")

        paper_cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(paper_trades)")}
        if "state_json" not in paper_cols:
            self.conn.execute("ALTER TABLE paper_trades ADD COLUMN state_json TEXT")
        self._backfill_setups_once()
        self._backfill_market_alignment_once()

    def _backfill_setups_once(self) -> None:
        """Stamp historical setups once and re-grade stored outcomes."""
        if self.get_meta("setup_regrade_v1"):
            return
        from ..signal_registry import setup_for
        from ..outcomes import favorable

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

    def _backfill_market_alignment_once(self) -> None:
        if self.get_meta("market_alignment_backfill_v1"):
            return
        from ..signal_registry import market_alignment, setup_for

        rows = self.conn.execute(
            "SELECT id, flag, regime, setup_type, market_regime FROM signals "
            "WHERE market_aligned IS NULL"
        ).fetchall()
        updated = 0
        for r in rows:
            setup = r["setup_type"] or setup_for(r["flag"] or "", r["regime"] or "")[0]
            aligned = market_alignment(setup, r["market_regime"])
            self.conn.execute(
                "UPDATE signals SET market_aligned = ? WHERE id = ?",
                (aligned, r["id"]),
            )
            updated += 1
        self.conn.commit()
        self.set_meta("market_alignment_backfill_v1", datetime.now(timezone.utc).isoformat())
        if updated:
            log.info("Market-alignment migration: stamped %d signal(s)", updated)
