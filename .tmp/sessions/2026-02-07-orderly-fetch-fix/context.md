# Task Context: Orderly Fetch And Pair Mapping Fix

Session ID: 2026-02-07-orderly-fetch-fix
Created: 2026-02-07T00:00:00Z
Status: in_progress

## Current Request
I'm currently getting errors when fetching data for orderly, here is the log.

## Context Files (Standards to Follow)
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/project-intelligence/decisions-log.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- plutus_terminal/controller/ui_controller.py
- plutus_terminal/core/exchange/base.py
- plutus_terminal/core/exchange/orderly/exchange.py
- plutus_terminal/core/exchange/orderly/fetcher.py
- plutus_terminal/core/exchange/orderly/markets.py
- plutus_terminal/core/exchange/orderly/rest_client.py

## External Docs Fetched
- Orderly docs confirm `GET /v1/kline` is a private endpoint requiring signed headers.
- Public candle history endpoints are under `/v1/tv/...` (including `/v1/tv/kline_history`).
- Public kline history uses `from`/`to` in seconds, and returns TradingView-style arrays.

## Components
- Pair formatting and leverage path correctness
- Public market data endpoint usage for chart history
- Orderly history response parsing compatibility

## Constraints
- Keep existing exchange abstraction contract intact.
- Avoid changing credential/signature behavior for private requests.
- Minimize blast radius: only adjust Orderly fetching and leverage path wiring.

## Exit Criteria
- [ ] Changing pair no longer triggers `Crypto.Crypto.../USDC` KeyError.
- [ ] Price history fetch no longer calls private `/v1/kline` as public.
- [ ] Orderly chart history works with public endpoint response shape.
