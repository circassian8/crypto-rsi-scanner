from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() not in ("0", "false", "no", "off")


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no dependency). Existing env vars win."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # An empty value means "unset" — skip it so code defaults still apply
        # (e.g. `CG_CALLS_PER_MINUTE=` must not shadow the int default).
        if key and value:
            os.environ.setdefault(key, value)


_load_dotenv(Path(__file__).resolve().parent.parent / ".env")

TOP_N = int(os.getenv("RSI_TOP_N", "100"))
RSI_PERIOD = 14
RSI_OB = float(os.getenv("RSI_OB", "70"))
RSI_OS = float(os.getenv("RSI_OS", "30"))
LOOKBACK_DAYS_DAILY = 250  # >= REGIME_LONG_MA so the 200-day MA is available
LOOKBACK_DAYS_4H = 90
RSI_Z_WINDOW = 90
MIN_ANNUAL_VOL = 0.20

ADAPTIVE_OB_PERCENTILE = 95
ADAPTIVE_OS_PERCENTILE = 5

SEVERITY_TIERS = {
    "OB": [(90.0, "EXTREME"), (80.0, "ALERT"), (70.0, "WATCH")],
    "OS": [(10.0, "EXTREME"), (20.0, "ALERT"), (30.0, "WATCH")],
}

COOLDOWN_HOURS = float(os.getenv("RSI_COOLDOWN_HOURS", "48"))
MIN_CONVICTION_ALERT = int(os.getenv("RSI_MIN_CONVICTION", "0"))  # 0 = nothing dropped

# --- Approaching-threshold pre-alerts -------------------------------------
# A coin that hasn't crossed yet but is within APPROACH_MARGIN RSI points of
# its (effective) threshold AND moving toward it by at least APPROACH_MIN_DELTA
# over the delta window. Surfaces setups *before* they trigger.
APPROACH_MARGIN = float(os.getenv("RSI_APPROACH_MARGIN", "5"))
APPROACH_MIN_DELTA = float(os.getenv("RSI_APPROACH_MIN_DELTA", "3"))

# --- Tiered notification routing ------------------------------------------
# Nothing worth a look is dropped; tiering decides *how loud* it is.
#   INSTANT: sent immediately, prominent. Edge-triggered (newly crossed).
#   DIGEST:  batched watch-list snapshot, sent at most once per interval.
# A real OB/OS crossing is INSTANT if its severity is in INSTANT_SEVERITIES
# or its conviction >= INSTANT_CONVICTION; otherwise DIGEST. Pre-alerts are
# always DIGEST.
INSTANT_CONVICTION = int(os.getenv("RSI_INSTANT_CONVICTION", "65"))
INSTANT_SEVERITIES = {"EXTREME", "ALERT"}
DIGEST_INTERVAL_HOURS = float(os.getenv("RSI_DIGEST_INTERVAL_HOURS", "24"))

_CG_DEFAULT_CPM = "25" if os.getenv("COINGECKO_API_KEY") else "8"
CALLS_PER_MINUTE = int(os.getenv("CG_CALLS_PER_MINUTE", _CG_DEFAULT_CPM))
MAX_RETRIES = 5

VOLUME_AVG_WINDOW = 20
VOLUME_SPIKE_THRESHOLD = 1.5

BTC_CORR_WINDOW = 30
RSI_DELTA_WINDOW = 3
DIVERGENCE_LOOKBACK = 30
DIVERGENCE_ORDER = 5

# Trend regime (moving-average structure, close-only).
REGIME_SHORT_MA = 50
REGIME_LONG_MA = 200
REGIME_SLOPE_LOOKBACK = 20

# Signal outcome tracking: forward return measured N days after each crossing,
# computed from price history already fetched each scan (no extra API calls).
OUTCOME_HORIZONS = [1, 3, 7, 14]
OUTCOME_PRIMARY_HORIZON = 7  # horizon used for regime / conviction breakdowns

# Self-tuning conviction: let each (flag, regime) bucket's historical hit-rate
# nudge the conviction score. Needs enough matured samples to be trustworthy.
SELFTUNE_ENABLED = (os.getenv("RSI_SELFTUNE", "1").lower() not in ("0", "false", "no"))
SELFTUNE_MIN_SAMPLES = int(os.getenv("RSI_SELFTUNE_MIN_SAMPLES", "8"))
SELFTUNE_MAX_SWING = int(os.getenv("RSI_SELFTUNE_MAX_SWING", "15"))

# Market-regime gating: each setup only has edge in specific BTC market regimes
# defined in signal_registry.py. The registry now seeds conviction from measured
# edge priors; this flag controls whether the current market regime is used for
# alignment/routing. MARKET_ALIGN_SWING is retained for the legacy helper/tests.
MARKET_GATING_ENABLED = (os.getenv("RSI_MARKET_GATING", "1").lower() not in ("0", "false", "no"))
MARKET_ALIGN_SWING = int(os.getenv("RSI_MARKET_ALIGN_SWING", "12"))

# Paper-trading scoreboard: auto-open a virtual trade on each new OB/OS crossing
# (long if the setup expects up, short if down), close it after PAPER_HOLD_DAYS
# at that day's close, and track realized P&L — the live proof of whether the
# gated signals make money. No real orders; uses prices already fetched.
PAPER_TRADING_ENABLED = (os.getenv("RSI_PAPER", "1").lower() not in ("0", "false", "no"))
PAPER_HOLD_DAYS = int(os.getenv("RSI_PAPER_HOLD_DAYS", str(OUTCOME_PRIMARY_HORIZON)))

# Sell-the-news / proxy-catalyst event fade research sleeve. Disabled by
# default and alert-only when enabled; no live order execution exists.
EVENT_FADE_ENABLED = _env_bool("RSI_EVENT_FADE_ENABLED", False)
EVENT_FADE_MODE = os.getenv("RSI_EVENT_FADE_MODE", "alert_only")
_EVENT_FADE_EVENTS_PATH_RAW = os.getenv("RSI_EVENT_FADE_EVENTS_PATH", "")
EVENT_FADE_MIN_WATCHLIST_SCORE = int(os.getenv("RSI_EVENT_FADE_MIN_WATCHLIST_SCORE", "60"))
EVENT_FADE_MIN_ARMED_SCORE = int(os.getenv("RSI_EVENT_FADE_MIN_ARMED_SCORE", "75"))
EVENT_FADE_MIN_TRIGGER_SCORE = int(os.getenv("RSI_EVENT_FADE_MIN_TRIGGER_SCORE", "80"))
EVENT_FADE_MIN_EVENT_CONFIDENCE = float(os.getenv("RSI_EVENT_FADE_MIN_EVENT_CONFIDENCE", "0.80"))
EVENT_FADE_MAX_DAYS_TO_EVENT = float(os.getenv("RSI_EVENT_FADE_MAX_DAYS_TO_EVENT", "7"))
EVENT_FADE_EXPIRE_HOURS_AFTER_EVENT = float(os.getenv("RSI_EVENT_FADE_EXPIRE_HOURS_AFTER_EVENT", "72"))
EVENT_FADE_MIN_RETURN_24H = float(os.getenv("RSI_EVENT_FADE_MIN_RETURN_24H", "0.75"))
EVENT_FADE_MIN_RETURN_7D = float(os.getenv("RSI_EVENT_FADE_MIN_RETURN_7D", "1.50"))
EVENT_FADE_EXTREME_RETURN_7D = float(os.getenv("RSI_EVENT_FADE_EXTREME_RETURN_7D", "5.00"))
EVENT_FADE_MIN_VOLUME_Z = float(os.getenv("RSI_EVENT_FADE_MIN_VOLUME_Z", "3.0"))
EVENT_FADE_MIN_OI_CHANGE_24H = float(os.getenv("RSI_EVENT_FADE_MIN_OI_CHANGE_24H", "0.30"))
EVENT_FADE_HOT_FUNDING_8H = float(os.getenv("RSI_EVENT_FADE_HOT_FUNDING_8H", "0.0005"))
EVENT_FADE_EXTREME_FUNDING_8H = float(os.getenv("RSI_EVENT_FADE_EXTREME_FUNDING_8H", "0.0010"))
EVENT_FADE_MIN_PERP_SPOT_VOLUME_RATIO = float(os.getenv("RSI_EVENT_FADE_MIN_PERP_SPOT_VOLUME_RATIO", "5.0"))
EVENT_FADE_MIN_RSI_OVERBOUGHT_SCORE = float(os.getenv("RSI_EVENT_FADE_MIN_RSI_OVERBOUGHT_SCORE", "60"))
EVENT_FADE_BLOCK_BTC_STRONG_RISK_ON = _env_bool("RSI_EVENT_FADE_BLOCK_BTC_STRONG_RISK_ON", True)
EVENT_FADE_MAX_SPREAD_BPS = float(os.getenv("RSI_EVENT_FADE_MAX_SPREAD_BPS", "100"))
EVENT_FADE_MIN_DEPTH_2PCT_USD = float(os.getenv("RSI_EVENT_FADE_MIN_DEPTH_2PCT_USD", "10000"))
EVENT_FADE_DEFAULT_RISK_PCT = float(os.getenv("RSI_EVENT_FADE_DEFAULT_RISK_PCT", "0.005"))
EVENT_FADE_MAX_RISK_PCT = float(os.getenv("RSI_EVENT_FADE_MAX_RISK_PCT", "0.01"))
EVENT_FADE_MAX_LEVERAGE_HINT = float(os.getenv("RSI_EVENT_FADE_MAX_LEVERAGE_HINT", "2.0"))
EVENT_FADE_MIN_FAILURE_CHECKS = int(os.getenv("RSI_EVENT_FADE_MIN_FAILURE_CHECKS", "2"))

# Macro context header in the digest (Fear & Greed + BTC trend + breadth).
MACRO_ENABLED = (os.getenv("RSI_MACRO", "1").lower() not in ("0", "false", "no"))

# Heartbeat / dead-man's-switch: alert if a run breaks or degrades silently.
HEARTBEAT_ENABLED = (os.getenv("RSI_HEARTBEAT", "1").lower() not in ("0", "false", "no"))
# Warn if more than this fraction of coins fail to fetch (silent degradation).
HEARTBEAT_MAX_FETCH_FAIL_RATIO = float(os.getenv("RSI_HEARTBEAT_MAX_FAIL", "0.30"))

# Stale-scan watchdog: the always-on listener alerts (once) if no successful scan
# has landed in STALE_SCAN_HOURS — catches a Mac asleep through the 03:10 schedule,
# an unloaded launchd job, or a silently-failing scan. Default 36h tolerates normal
# overnight sleep; lower it for a tighter watch. Gated by HEARTBEAT_ENABLED.
STALE_SCAN_HOURS = float(os.getenv("RSI_STALE_SCAN_HOURS", "36"))
STALE_CHECK_INTERVAL_SEC = int(os.getenv("RSI_STALE_CHECK_INTERVAL_SEC", "1800"))

RSI_4H_FETCH_UPPER = 60.0
RSI_4H_FETCH_LOWER = 40.0

# Universe hygiene. The live scan/backtest request a larger CoinGecko candidate
# pool, then filter stablecoins, wrapped/staked receipts, stale/suspicious
# listings, and illiquid assets before taking the requested top-N.
UNIVERSE_FETCH_MULTIPLIER = int(os.getenv("RSI_UNIVERSE_FETCH_MULTIPLIER", "2"))
UNIVERSE_EXTRA_CANDIDATES = int(os.getenv("RSI_UNIVERSE_EXTRA_CANDIDATES", "50"))
UNIVERSE_MAX_CANDIDATES = int(os.getenv("RSI_UNIVERSE_MAX_CANDIDATES", "250"))
UNIVERSE_MIN_VOLUME_TO_MCAP = float(os.getenv("RSI_MIN_VOLUME_TO_MCAP", "0.001"))
UNIVERSE_MIN_MARKET_CAP_USD = float(os.getenv("RSI_MIN_MARKET_CAP_USD", "0"))
UNIVERSE_MAX_ABS_24H_CHANGE = float(os.getenv("RSI_MAX_ABS_24H_CHANGE", "500"))

EXCLUDE_SYMBOLS = {
    "usdt", "usdc", "dai", "usde", "fdusd", "tusd", "usdd", "pyusd", "usds",
    "busd", "gusd", "frax", "lusd", "usd0", "usdb", "crvusd", "usdx",
    "usd1", "usdg", "usdtb", "gho", "ylds", "usx", "usyc", "xaut", "paxg",
    "wbtc", "weth", "weeth", "wsteth", "steth", "reth", "cbbtc", "cbeth",
    "solvbtc", "lbtc", "wbeth", "meth", "ezeth", "rseth", "bnsol", "jitosol",
    "wbnb",
}

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
COINGECKO_KEY_TYPE = (os.getenv("COINGECKO_KEY_TYPE") or "demo").lower()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# One or more recipient chat IDs, comma-separated (e.g. "133428954,987654321").
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_CHAT_IDS = [
    cid.strip() for cid in (TELEGRAM_CHAT_ID or "").split(",") if cid.strip()
]
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

DATA_DIR = Path(__file__).resolve().parent.parent
DB_PATH = DATA_DIR / "rsi_scanner.db"
CSV_OUT = DATA_DIR / "rsi_scan_latest.csv"

EVENT_FADE_EVENTS_PATH = Path(_EVENT_FADE_EVENTS_PATH_RAW).expanduser() if _EVENT_FADE_EVENTS_PATH_RAW else None
if EVENT_FADE_EVENTS_PATH is not None and not EVENT_FADE_EVENTS_PATH.is_absolute():
    EVENT_FADE_EVENTS_PATH = DATA_DIR / EVENT_FADE_EVENTS_PATH

_BACKUP_DIR_RAW = os.getenv("RSI_BACKUP_DIR", "backups")
BACKUP_DIR = Path(_BACKUP_DIR_RAW).expanduser()
if not BACKUP_DIR.is_absolute():
    BACKUP_DIR = DATA_DIR / BACKUP_DIR
BACKUP_KEEP = int(os.getenv("RSI_BACKUP_KEEP", "14"))
BACKUP_STALE_HOURS = float(os.getenv("RSI_BACKUP_STALE_HOURS", "72"))
RESTORE_EXPECTED_TABLES = ("scans", "signals", "meta", "paper_trades")

_LOG_FILES_RAW = os.getenv("RSI_LOG_FILES", "scan.log,bot.log")
LOG_FILES: list[Path] = []
for _raw_log_path in (p.strip() for p in _LOG_FILES_RAW.split(",")):
    if not _raw_log_path:
        continue
    _log_path = Path(_raw_log_path).expanduser()
    if not _log_path.is_absolute():
        _log_path = DATA_DIR / _log_path
    LOG_FILES.append(_log_path)
LOG_ROTATE_MAX_BYTES = int(os.getenv("RSI_LOG_ROTATE_MAX_BYTES", str(5 * 1024 * 1024)))
LOG_ROTATE_KEEP = int(os.getenv("RSI_LOG_ROTATE_KEEP", "5"))

LAUNCHD_SCAN_LABEL = os.getenv("RSI_LAUNCHD_SCAN_LABEL", "com.nasrenkaraf.rsiscanner")
LAUNCHD_BOT_LABEL = os.getenv("RSI_LAUNCHD_BOT_LABEL", "com.nasrenkaraf.rsibot")
MAINTENANCE_LABEL = os.getenv("RSI_MAINTENANCE_LABEL", "com.nasrenkaraf.rsimaintenance")
MAINTENANCE_HOUR = int(os.getenv("RSI_MAINTENANCE_HOUR", "3"))
MAINTENANCE_MINUTE = int(os.getenv("RSI_MAINTENANCE_MINUTE", "45"))
_MAINTENANCE_LOG_RAW = os.getenv("RSI_MAINTENANCE_LOG", "maintenance.log")
MAINTENANCE_LOG = Path(_MAINTENANCE_LOG_RAW).expanduser()
if not MAINTENANCE_LOG.is_absolute():
    MAINTENANCE_LOG = DATA_DIR / MAINTENANCE_LOG
if MAINTENANCE_LOG not in LOG_FILES:
    LOG_FILES.append(MAINTENANCE_LOG)

_UNIVERSE_AUDIT_OUT_RAW = os.getenv("RSI_UNIVERSE_AUDIT_OUT", "universe_hygiene_latest.json")
UNIVERSE_AUDIT_OUT = Path(_UNIVERSE_AUDIT_OUT_RAW).expanduser()
if not UNIVERSE_AUDIT_OUT.is_absolute():
    UNIVERSE_AUDIT_OUT = DATA_DIR / UNIVERSE_AUDIT_OUT

_FIXTURE_DIR_RAW = os.getenv("RSI_FIXTURE_DIR", "")
FIXTURE_DIR = Path(_FIXTURE_DIR_RAW).expanduser() if _FIXTURE_DIR_RAW else None
if FIXTURE_DIR is not None and not FIXTURE_DIR.is_absolute():
    FIXTURE_DIR = DATA_DIR / FIXTURE_DIR

_BACKTEST_CACHE_DIR_RAW = os.getenv("RSI_BACKTEST_CACHE_DIR", "backtest_cache")
BACKTEST_CACHE_DIR = Path(_BACKTEST_CACHE_DIR_RAW).expanduser()
if not BACKTEST_CACHE_DIR.is_absolute():
    BACKTEST_CACHE_DIR = DATA_DIR / BACKTEST_CACHE_DIR


def redact_token(text: str) -> str:
    """Strip the Telegram bot token from a string before logging — it rides
    along inside request URLs in exception messages (e.g. getUpdates failures),
    which would otherwise leak the token into the log file."""
    token = TELEGRAM_BOT_TOKEN
    if token and token in text:
        return text.replace(token, "<bot-token>")
    return text


def has_notification_channel() -> bool:
    return bool(
        (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS)
        or DISCORD_WEBHOOK_URL
        or (SMTP_HOST and SMTP_USER and SMTP_PASS and EMAIL_TO)
    )


def validate() -> None:
    """Log warnings about config that will degrade the run. Non-fatal."""
    if not COINGECKO_API_KEY:
        log.warning(
            "No COINGECKO_API_KEY set — free tier is heavily rate-limited; "
            "4H data may be incomplete. A free demo key is strongly recommended."
        )
    if not has_notification_channel():
        log.warning("No notification channel configured — output will be console-only.")
    if RSI_OS >= RSI_OB:
        raise ValueError(f"RSI_OS ({RSI_OS}) must be below RSI_OB ({RSI_OB}).")
