"""SQLite schema text for the scanner storage facade."""

from __future__ import annotations

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
    market_aligned TEXT,
    state_json TEXT,
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
    state_json TEXT,
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
