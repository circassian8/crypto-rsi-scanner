# crypto-rsi-scanner

Research-oriented crypto RSI scanner and Event Alpha artifact pipeline.

## CI safety

GitHub Actions is configured for safe verification only. Push and pull-request
CI first checks the universal hash-pinned dependency lock and audits it for
known vulnerabilities, then runs the canonical `make verify` on Python 3.11 and
3.13 (standalone compatibility, pytest, alert render, fixture backtest, and
paper scoreboard) with `RSI_EVENT_ALERTS_ENABLED=0`. Static architecture reports
run once on 3.13. The manual Event Alpha smoke workflow runs the fixture/no-call
targets on both supported Python versions. CI does not load `.env`, provider API
keys, Telegram tokens, live-provider allow flags, live-send targets, trading,
paper trading, execution, normal RSI signal writes, or Event Alpha
`TRIGGERED_FADE` creation.

All third-party workflow actions are pinned to immutable full release commit
SHAs with readable version comments. The current checkout/setup actions use
their supported Node 24 releases; weekly Dependabot proposes reviewed SHA
updates instead of silently following mutable major tags.

`requirements.in` records direct dependency intent; `requirements.txt` is the
cross-platform, Python 3.11+-compatible hash-pinned environment used by
bootstrap and CI. Install the pinned dependency tools with
`make dependency-tools`, update the lock with
`make lock-dependencies UPGRADE=1`, and run
`make dependency-verify` before accepting dependency changes.
