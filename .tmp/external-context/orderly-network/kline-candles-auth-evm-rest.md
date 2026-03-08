---
source: Context7 API + Orderly official docs
library: Orderly Network
package: orderly-network
topic: EVM REST kline/candles endpoints and authentication requirements
fetched: 2026-02-07T00:00:00Z
official_docs: https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-kline-history
---

# Relevant findings

## Endpoint paths

- Public historical candles endpoint is documented as `GET /v1/tv/kline_history` under the **public** REST section:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-kline-history
- Another public candles/bars endpoint is `GET /v1/tv/history`:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-tradingview-history-bars
- Private kline endpoint is `GET /v1/kline` under the **private** REST section:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-kline
- No `/v1/public/kline` path appears in the current docs index (`llms.txt`).

## Auth requirements

- API intro states: "All our private interfaces require signing..."
  - https://orderly.network/docs/build-on-omnichain/evm-api/introduction
- `GET /v1/kline` (private) explicitly requires signed headers:
  - `orderly-timestamp`, `orderly-account-id`, `orderly-key`, `orderly-signature`
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-kline
- `GET /v1/tv/kline_history` is listed in public docs, but its OpenAPI block currently also lists the same auth headers; this appears inconsistent with the private/public rule and should be treated as a docs inconsistency to validate in live calls.

## Required timestamp params and types

- For `GET /v1/tv/kline_history`:
  - `from` query param: type `string`, unix timestamp example `1761926400` (seconds)
  - `to` query param: type `string`, unix timestamp example `1762790400` (seconds)
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-kline-history
- For `GET /v1/tv/history`:
  - `from` and `to` query params are both required and typed as `string`
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-tradingview-history-bars
- For `GET /v1/kline`:
  - request does not include start/end query params; response includes `start_timestamp` and `end_timestamp` as integer milliseconds.
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-kline

## Response shape and 401 causes

- `GET /v1/tv/kline_history` response shape includes `s`, `o`, `c`, `h`, `l`, `v`, `a`, `t` arrays.
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-kline-history
- `GET /v1/kline` response shape is `{ success, data: { rows: [...] } }` with each row containing OHLCV and `start_timestamp`/`end_timestamp`.
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-kline
- Documented 401 causes (error codes):
  - `-1001`: API key/secret wrong format
  - `-1002`: API key/secret invalid, insufficient permission, expired, or revoked
  - https://orderly.network/docs/build-on-omnichain/evm-api/error-codes
- Additional auth failure causes from auth docs:
  - timestamp drift >= 300 seconds,
  - invalid signature generation,
  - invalid/expired/unregistered `orderly-key`
  - https://orderly.network/docs/build-on-omnichain/evm-api/api-authentication
