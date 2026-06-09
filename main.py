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
  RSI_BACKUP_STALE_HOURS  Backup freshness threshold for --status (default 72).
  RSI_LOG_FILES        Comma-separated logs for --status/--rotate-logs.
  RSI_LOG_ROTATE_MAX_BYTES  Rotate logs larger than this (default 5 MiB).
  RSI_LOG_ROTATE_KEEP  Number of rotated logs to retain (default 5).
  RSI_FIXTURE_DIR      Optional CoinGecko fixture directory for offline smoke.

Secrets can also be placed in a .env file at the project root.

Usage:
  pip install -r requirements.txt
  python main.py                 # full scan + notify
  python main.py --dry-run       # scan + print, no notifications, no state change
  python main.py --top-n 20 -v   # smaller universe, debug logging
  python main.py --report        # print signal-outcome stats (hit-rates) and exit
  python main.py --status        # print scan/listener/backup/log health
  python main.py --backup-db     # safe SQLite backup + integrity check
  python main.py --verify-restore # restore-check latest SQLite backup
  python main.py --maintenance   # backup + restore drill + log rotation
  python main.py --rotate-logs   # rotate oversized scan/listener logs
  python main.py --launchd-status # print launchd service status
  python main.py --score --json  # structured paper scoreboard
  python main.py --refresh-universe-audit # refresh hygiene audit only

Cron (daily at 00:05 UTC):
  5 0 * * *  cd /path/to/project && python main.py >> scan.log 2>&1
"""

from crypto_rsi_scanner.scanner import cli

if __name__ == "__main__":
    cli()
