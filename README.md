# crypto-rsi-scanner

Research-oriented crypto RSI scanner and Event Alpha artifact pipeline.

## CI safety

GitHub Actions is configured for safe verification only. Push and pull-request
CI runs compile/static architecture checks plus one canonical `make verify`
(standalone compatibility, pytest, alert render, fixture backtest, and paper
scoreboard) with `RSI_EVENT_ALERTS_ENABLED=0`. The manual Event Alpha smoke
workflow runs fixture and no-call smoke targets only. CI does not load `.env`, provider API keys,
Telegram tokens, live-provider allow flags, live-send targets, trading, paper
trading, execution, normal RSI signal writes, or Event Alpha `TRIGGERED_FADE`
creation.
