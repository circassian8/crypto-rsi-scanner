"""Paper-trade persistence methods."""

from __future__ import annotations


class PapersMixin:
    def has_open_trade(self, coin_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM paper_trades WHERE coin_id = ? AND status = 'open' LIMIT 1",
            (coin_id,),
        ).fetchone() is not None

    def open_paper_trade(self, **t) -> None:
        self.conn.execute(
            """INSERT INTO paper_trades
            (symbol, coin_id, setup_type, market_regime, market_aligned, state_json, direction,
             conviction, entry_price, entry_at, hold_days, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?, 'open')""",
            (
                t["symbol"], t["coin_id"], t.get("setup_type"), t.get("market_regime"),
                t.get("market_aligned"), t.get("state_json"), t["direction"], t.get("conviction"),
                t["entry_price"], t["entry_at"], t["hold_days"],
            ),
        )
        self.conn.commit()

    def open_paper_trades(self) -> list:
        return self.conn.execute(
            "SELECT * FROM paper_trades WHERE status = 'open' ORDER BY entry_at"
        ).fetchall()

    def open_paper_coin_ids(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT coin_id FROM paper_trades "
            "WHERE status = 'open' AND coin_id IS NOT NULL AND coin_id != ''"
        ).fetchall()
        return [r["coin_id"] for r in rows]

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
