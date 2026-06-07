# CLAUDE.md

This project is co-developed with OpenAI Codex under a shared protocol.

**Read `AGENTS.md` first and follow it** — it is the single source of truth for
architecture, how to run/test/deploy, conventions, and current strategy findings.

**Two musts after a change-making prompt:** (1) prepend a `DEVLOG.md` entry
(template at its top); (2) commit the change to git on `main` with a clear
message. The repo is local git now; `DEVLOG.md` remains the narrative history.

Quick reminders (full detail in `AGENTS.md`):
- Standard verification: `make verify`.
- Tests: `.venv/bin/python tests/test_indicators.py` — all must pass.
- Pending work: `ROADMAP.md`.
- Durable choices/rejections: `DECISIONS.md`.
- Backtest signal-logic changes before shipping live.
- Restart the listener to deploy listener code:
  `launchctl kickstart -k "gui/$(id -u)/com.nasrenkaraf.rsibot"`.
