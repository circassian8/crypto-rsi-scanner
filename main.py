#!/usr/bin/env python3
"""
Top-100 crypto RSI overextension scanner.

Scans the top coins by market cap, computes multi-timeframe RSI (daily, 4H,
weekly), and alerts when coins reach stretched levels. Adds context via
z-scores, volume confirmation, BTC correlation, divergence detection,
adaptive thresholds, and severity tiers.

Notifications: Telegram, Discord webhook, and/or email (all optional).
State is persisted in SQLite for cooldown logic and historical tracking.

ENV VARS:
  COINGECKO_API_KEY    CoinGecko demo or pro key (recommended).
  COINGECKO_KEY_TYPE   "demo" (default) or "pro".
  CG_CALLS_PER_MINUTE  Rate limit (default 25, raise for pro keys).
  TELEGRAM_BOT_TOKEN   Telegram bot token.
  TELEGRAM_CHAT_ID     Your Telegram chat ID.
  DISCORD_WEBHOOK_URL  Discord webhook URL.
  SMTP_HOST/PORT/USER/PASS  Email SMTP settings.
  EMAIL_TO             Recipient email address.
  RSI_OB / RSI_OS      Override overbought/oversold thresholds (default 70/30).
  RSI_COOLDOWN_HOURS   Alert cooldown per coin (default 48).
  RSI_TOP_N            Number of coins to scan (default 100).
  RSI_BACKUP_DIR       Backup directory for --backup-db (default ./backups).
  RSI_BACKUP_KEEP      Number of DB backups to retain (default 14).

Secrets can also be placed in a .env file at the project root.

Usage:
  pip install -r requirements.txt
  python main.py                 # full scan + notify
  python main.py --dry-run       # scan + print, no notifications, no state change
  python main.py --top-n 20 -v   # smaller universe, debug logging
  python main.py --report        # print signal-outcome stats (hit-rates) and exit
  python main.py --backup-db     # safe SQLite backup + integrity check

Cron (daily at 00:05 UTC):
  5 0 * * *  cd /path/to/project && python main.py >> scan.log 2>&1
"""

from crypto_rsi_scanner.scanner import cli

if __name__ == "__main__":
    cli()
