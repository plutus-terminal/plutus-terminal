---
source: Context7 API + Orderly official docs
library: Orderly Network
package: orderly-network
topic: GET /v1/tv/history vs /v1/tv/kline_history query params response shape and charting differences
fetched: 2026-02-07T00:00:00Z
official_docs:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-tradingview-history-bars
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-kline-history
---

# Endpoint confirmation (charting-focused)

## GET /v1/tv/history

- Query params: `symbol` (required), `resolution` (required), `from` (required), `to` (required).
- Response shape: TradingView-style parallel arrays: `s`, `t`, `o`, `h`, `l`, `c`, `v`.
- Rate limit: documented as `10 req/s` per IP.

## GET /v1/tv/kline_history

- Query params: `symbol` (required), `resolution` (required), `from` (optional), `to` (optional), `limit` (optional, max 1000).
- Response shape: TradingView-style parallel arrays: `s`, `o`, `c`, `h`, `l`, `v`, `a`, `t` (`a` = amount/notional).
- Rate limit: documented as `5 req/10s` per IP.

## Practical differences for charting use

- Prefer `/v1/tv/history` for strict TradingView-compatible history requests where `from/to` are always sent.
- Prefer `/v1/tv/kline_history` when you need pagination/window control via `limit` and optional `from/to`, plus `a` (amount).
- Both are array-based OHLCV payloads; normalize once into bar objects for your chart adapter.
- Docs contain timestamp/auth inconsistencies across pages (string vs integer, seconds-vs-ms examples, public endpoint with auth headers in one spec block), so validate with one live call per environment and lock behavior in adapter tests.
