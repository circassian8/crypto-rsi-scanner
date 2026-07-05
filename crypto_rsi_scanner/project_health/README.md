# Project Health

This package contains permanent architecture and project-health checks. The
tools are static report writers: they inspect repository files, Make targets,
report artifacts, and test organization without importing scanner runtime
paths, calling providers, sending notifications, writing trading state, or
creating Event Alpha `TRIGGERED_FADE` rows.

Canonical Make targets use `architecture-*` names. Deprecated `refactor-*`
targets may remain as hidden compatibility aliases for one cycle, but new code,
docs, and CI should call `crypto_rsi_scanner.project_health.*` modules and
`make architecture-*` targets.
