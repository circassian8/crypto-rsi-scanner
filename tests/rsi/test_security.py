"""Focused privacy and runtime-permission regression coverage."""

from __future__ import annotations

import os
import stat
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_config_redacts_all_configured_credentials_and_recipients():
    from crypto_rsi_scanner import config

    names = (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_IDS",
        "COINGECKO_API_KEY",
        "OPENAI_API_KEY",
        "DISCORD_WEBHOOK_URL",
        "SMTP_PASS",
        "SMTP_USER",
        "EMAIL_TO",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET",
        "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN",
        "EVENT_DISCOVERY_COINALYZE_API_KEY",
    )
    original = {name: getattr(config, name) for name in names}
    values = {
        "TELEGRAM_BOT_TOKEN": "123456789:telegram-secret",
        "TELEGRAM_CHAT_IDS": ["1122334455"],
        "COINGECKO_API_KEY": "coingecko-secret",
        "OPENAI_API_KEY": "openai-secret",
        "DISCORD_WEBHOOK_URL": "https://discord.test/webhook-secret",
        "SMTP_PASS": "smtp-secret",
        "SMTP_USER": "sender@example.test",
        "EMAIL_TO": "recipient@example.test",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY": "binance-key-secret",
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET": "binance-api-secret",
        "EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN": "cryptopanic-secret",
        "EVENT_DISCOVERY_COINALYZE_API_KEY": "coinalyze-secret",
    }
    try:
        for name, value in values.items():
            setattr(config, name, value)
        raw_values = [
            *(str(value) for name, value in values.items() if name != "TELEGRAM_CHAT_IDS"),
            *values["TELEGRAM_CHAT_IDS"],
        ]
        redacted = config.redact_token(" | ".join(raw_values))
        assert all(value not in redacted for value in raw_values)
        assert "<bot-token>" in redacted
        assert "<telegram-chat-id>" in redacted
    finally:
        for name, value in original.items():
            setattr(config, name, value)


def test_notification_failures_do_not_log_credentials_or_recipient_ids():
    from crypto_rsi_scanner import config, notifications

    messages: list[str] = []

    class CaptureLog:
        def error(self, message, *args):
            messages.append(message % args)

        def info(self, message, *args):
            messages.append(message % args)

    class FailingSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            raise RuntimeError(f"login failed for {user} with {password}")

    token = "123456789:telegram-secret"
    chat_id = "1122334455"
    webhook = "https://discord.test/webhook-secret"
    smtp_user = "sender@example.test"
    smtp_pass = "smtp-secret"
    email_to = "recipient@example.test"
    originals = {
        "log": notifications.log,
        "post": notifications.requests.post,
        "smtp": notifications.smtplib.SMTP,
        "TELEGRAM_BOT_TOKEN": config.TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_IDS": config.TELEGRAM_CHAT_IDS,
        "DISCORD_WEBHOOK_URL": config.DISCORD_WEBHOOK_URL,
        "SMTP_HOST": config.SMTP_HOST,
        "SMTP_USER": config.SMTP_USER,
        "SMTP_PASS": config.SMTP_PASS,
        "EMAIL_TO": config.EMAIL_TO,
    }
    try:
        notifications.log = CaptureLog()
        notifications.requests.post = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError(f"request failed {token} {chat_id} {webhook}")
        )
        notifications.smtplib.SMTP = FailingSMTP
        config.TELEGRAM_BOT_TOKEN = token
        config.TELEGRAM_CHAT_IDS = [chat_id]
        config.DISCORD_WEBHOOK_URL = webhook
        config.SMTP_HOST = "smtp.example.test"
        config.SMTP_USER = smtp_user
        config.SMTP_PASS = smtp_pass
        config.EMAIL_TO = email_to

        notifications.send_telegram_structured("hello")
        notifications.send_discord("hello")
        notifications.send_email("subject", "body")

        logged = "\n".join(messages)
        for value in (token, chat_id, webhook, smtp_user, smtp_pass, email_to):
            assert value not in logged
        assert "recipient 1/1" in logged
    finally:
        notifications.log = originals["log"]
        notifications.requests.post = originals["post"]
        notifications.smtplib.SMTP = originals["smtp"]
        for name in (
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_IDS",
            "DISCORD_WEBHOOK_URL",
            "SMTP_HOST",
            "SMTP_USER",
            "SMTP_PASS",
            "EMAIL_TO",
        ):
            setattr(config, name, originals[name])


def test_heartbeat_redacts_and_escapes_exception_text():
    from crypto_rsi_scanner import config, heartbeat

    sent: list[str] = []
    token = "123456789:telegram-secret"
    original_token = config.TELEGRAM_BOT_TOKEN
    original_enabled = config.HEARTBEAT_ENABLED
    original_send = heartbeat.send_telegram
    try:
        config.TELEGRAM_BOT_TOKEN = token
        config.HEARTBEAT_ENABLED = True
        heartbeat.send_telegram = lambda text, **kwargs: sent.append(text) or True
        heartbeat.alert_failure(RuntimeError(f"provider URL had {token} <unsafe>"))
        assert len(sent) == 1
        assert token not in sent[0]
        assert "<unsafe>" not in sent[0]
        assert "&lt;unsafe&gt;" in sent[0]
    finally:
        config.TELEGRAM_BOT_TOKEN = original_token
        config.HEARTBEAT_ENABLED = original_enabled
        heartbeat.send_telegram = original_send


def test_runtime_database_backup_and_log_files_are_owner_only(tmp_path: Path):
    from crypto_rsi_scanner.backups import backup_database
    from crypto_rsi_scanner.ops import rotate_logs
    from crypto_rsi_scanner.storage import Storage

    db_path = tmp_path / "runtime.db"
    storage = Storage(db_path)
    try:
        assert _mode(db_path) == 0o600
        for sidecar in (Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
            if sidecar.exists():
                assert _mode(sidecar) == 0o600
    finally:
        storage.close()

    source = tmp_path / "source.db"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    backup_dir = tmp_path / "backups"
    backup = backup_database(
        source,
        backup_dir,
        now=datetime(2026, 7, 9, tzinfo=timezone.utc),
    )
    assert _mode(backup_dir) == 0o700
    assert _mode(backup.path) == 0o600

    log_path = tmp_path / "scan.log"
    log_path.write_text("sensitive runtime text\n", encoding="utf-8")
    log_path.chmod(0o644)
    rotation = rotate_logs([log_path], max_bytes=1, keep=1)[0]
    assert rotation.rotated_to is not None
    assert _mode(log_path) == 0o600
    assert _mode(rotation.rotated_to) == 0o600


def test_launchd_templates_apply_owner_only_umask():
    from crypto_rsi_scanner.event_alpha.config.scheduler import generate_launchd_plist
    from crypto_rsi_scanner.ops import maintenance_agent_plist

    plist = maintenance_agent_plist(
        label="com.example.maint",
        python_path=Path("/repo/.venv/bin/python"),
        main_path=Path("/repo/main.py"),
        working_dir=Path("/repo"),
        log_path=Path("/repo/maintenance.log"),
        hour=3,
        minute=45,
    )
    assert plist["Umask"] == 0o077
    event_alpha_plist = generate_launchd_plist(profile="notify_no_key", repo_path="/repo")
    assert "<key>Umask</key><integer>63</integer>" in event_alpha_plist
