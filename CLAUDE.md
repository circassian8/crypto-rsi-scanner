# CLAUDE.md

This project is co-developed with OpenAI Codex under a shared protocol.

**Read `AGENTS.md` first and follow it** — it is the single source of truth for
architecture, how to run/test/deploy, conventions, and current strategy findings.

**Three musts after a change-making prompt:** (1) prepend a `DEVLOG.md` entry
(template at its top); (2) commit the change to git on `main` with a clear
message; (3) push `main` to `origin` after the commit. The human gave standing
approval on 2026-06-16 to push after every commit. `DEVLOG.md` remains the
narrative history.

Quick reminders (full detail in `AGENTS.md`):
- Standard verification: `make verify`.
- Offline scanner smoke without network: `make dry-run-fixture`.
- Tests: `make test-full` (full pytest suite; part of `make verify`) — all must pass.
- Pending work: `ROADMAP.md`.
- Durable choices/rejections: `DECISIONS.md`.
- Backtest signal-logic changes before shipping live.
- Restart the listener to deploy listener code:
  `make restart-listener`.
