---
source: Orderly official docs (webfetch)
library: Orderly Network
package: orderly-network
topic: /v1/tv/history rate limits, 429 behavior, retry strategy, and startup burst reduction
fetched: 2026-02-07T00:00:00Z
official_docs:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-tradingview-history-bars
  - https://orderly.network/docs/build-on-omnichain/evm-api/introduction
  - https://orderly.network/docs/build-on-omnichain/evm-api/error-codes
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/introduction
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-kline-history
---

# Relevant extracted docs (filtered)

## /v1/tv/history documented limit

- Endpoint: `GET /v1/tv/history?symbol={}&resolution={}&from={}&to={}`
- Documented limit: **10 requests per 1 second per IP address**.

## Nearby chart endpoint limit for comparison

- Endpoint: `GET /v1/tv/kline_history`
- Documented limit: **5 requests per 10 seconds per IP address**.

## General rate-limit behavior

- Introduction states rate limit is counted using the **Orderly key**.
- If limit is reached for an endpoint, server returns HTTP **429**.
- Guidance text: client should wait until next time horizon.

## 429 / error payload details

- Error code mapping page documents:
  - `code: -1003`
  - `status: 429`
  - description: `Rate limit exceed.`
- Generic error response shape in docs:
  - `success: false`
  - `code: <int>`
  - `message: <string>`
- No explicit documentation found for `Retry-After` header or dedicated retry fields in body.

## WebSocket alternative for burst reduction

- WebSocket public topics include kline streams:
  - `kline_1m`, `kline_5m`, `kline_15m`, `kline_30m`, `kline_1h`, `kline_1d`, `kline_1w`, `kline_1M`.
- Practical pattern: REST for initial backfill, WebSocket for incremental updates.

## Practical implementation notes for Python async clients

- Use one shared `httpx.AsyncClient` with connection limits and timeout config.
- Add a per-endpoint limiter bucket for `/v1/tv/history` at 10 rps and per-IP scope assumptions.
- On `429` (or `code=-1003`): back off with jitter; when no `Retry-After` exists, wait at least one full endpoint window, then retry.
- Coalesce duplicate in-flight history requests by key `(symbol,resolution,from,to)`.
- Cache history responses (short TTL for recent windows, longer for historical windows).
- Debounce UI-triggered chart reloads (symbol/timeframe/date-range changes).
- Stagger startup requests and cap concurrent history calls to avoid cold-start bursts.
