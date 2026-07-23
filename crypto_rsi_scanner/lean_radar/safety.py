"""Shared zero-side-effect counters for every Lean Radar operator surface."""

SAFETY_COUNTERS = {
    "telegram_sends": 0,
    "trades_created": 0,
    "orders_created": 0,
    "paper_trades_created": 0,
    "normal_rsi_signal_rows_written": 0,
    "triggered_fade_created": 0,
}


__all__ = ("SAFETY_COUNTERS",)
