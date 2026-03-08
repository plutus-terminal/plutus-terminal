---
source: Official Orderly docs + referenced SDK repos
library: Orderly Network
package: orderly-network
topic: native integration test surface for plutus-terminal
fetched: 2026-03-08T00:00:00Z
official_docs: https://orderly.network/docs/build-on-omnichain/evm-api/introduction
references:
  - https://orderly.network/docs/build-on-omnichain/evm-api/api-authentication
  - https://orderly.network/docs/build-on-omnichain/evm-api/error-codes
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/introduction
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/authentication
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/ping-pong
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/error-response
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/execution-report
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/create-order
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/edit-order
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/cancel-order
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-order-rules-per-symbol
  - https://github.com/OrderlyNetwork/orderly-sdk-js
  - https://github.com/OrderlyNetwork/orderly-evm-connector-python
---

# REST order behavior to cover

- `POST /v1/order`: immediate create response; execution lifecycle comes from websocket.
- `PUT /v1/order`: requires `order_id`, `symbol`, `order_type`, `side`; docs say only price/quantity are amendable; success payload returns `EDIT_SENT`.
- `DELETE /v1/order?order_id={id}&symbol={symbol}`: success payload returns `CANCEL_SENT`.
- Additional connector-covered patterns worth parity tests even if app wraps them differently:
  - `DELETE /v1/client/order?client_order_id={id}&symbol={symbol}`
  - `DELETE /v1/orders[?symbol=...]`
  - `DELETE /v1/batch-order?order_ids=...`
  - `DELETE /v1/client/batch-order?client_order_ids=...`
  - `GET /v1/order/{order_id}` / `GET /v1/client/order/{client_order_id}`
  - `GET /v1/orders` with filters and pagination
- Documented order-type semantics to test at integration boundary:
  - `MARKET`: fills until book exhausted or price limit breached; remainder cancels.
  - `IOC`: partial fill allowed, remainder cancels.
  - `FOK`: all-or-nothing at price.
  - `POST_ONLY`: cancels if it would cross immediately.
  - `ASK` / `BID`: server assigns best ask/bid at acceptance.
- `client_order_id` must be unique among open orders; reused ID should reject until prior order completes.
- `visible_quantity`: default equals `order_quantity`; `0` hides order; negative or `> order_quantity` invalid; not meaningful for immediate-or-cancel style orders.

# Auth and signing behaviors to cover

- Preserve current WebUI-token flow if it works; official docs explicitly note Orderly keys can come from frontend builders such as WOOFi Pro.
- Signed REST headers to test: `orderly-account-id`, `orderly-key`, `orderly-signature`, `orderly-timestamp`, plus method-dependent `Content-Type`.
- Signing normalization to test exactly:
  - `timestamp + UPPERCASE_METHOD + path_with_query`
  - append JSON body only for requests with bodies
  - no base URL in signed string
- Timestamp skew beyond 300 seconds should be rejected.
- Key/account validity failures should surface as auth errors, not generic network errors.
- Private websocket auth signs only the timestamp (blank method/path/body).
- Official docs say signature is base64 url-safe; referenced Python connector uses standard base64. Tests should pin the codebase's current server-compatible encoding and separately verify normalized preimage construction.

# Websocket semantics to cover

- Endpoints:
  - Public: `wss://ws-evm.orderly.org/ws/stream/{account_id}`
  - Private: `wss://ws-private-evm.orderly.org/v2/ws/private/stream/{account_id}`
- Public topics include `orderbook`, `orderbookupdate`, `trade`, `ticker`, `tickers`, `bbo`, `bbos`, `estfundingrate`, `indexprice`, `indexprices`, `liquidation`, `markprice`, `markprices`, `openinterest`, and kline variants.
- Private topics include `account`, `balance`, `executionreport`, `liquidationsaccount`, `liquidatorliquidations`, `notifications`, `settle`, `position`, `wallet`.
- Auth:
  - private WS requires auth before subscribing
  - failed auth disconnects client
  - auth may be sent as `event: auth` frame or embedded as query params in connection URL
- Ack/error behavior:
  - subscribe/auth responses carry request `id`
  - success ack includes `success: true`
  - error ack includes `success: false` and `errorMsg`
- Heartbeat:
  - server sends ping every 10s
  - client should answer pong
  - server disconnects if no pong within 10s for 10 consecutive times
  - connector README also claims auto-pong and allows client-side keepalive ping every 10s
- Reconnect:
  - Python connector retries every 5s, max 30 tries, then resubscribes after reconnect
  - project tests should verify your native client restores auth state and subscriptions after reconnect, not just raw socket reopening
- Private stream payloads to validate from execution reports: `status`, `reason`, `orderId`, `clientOrderId`, `executedQuantity`, `totalExecutedQuantity`, `avgExecutedPrice`, `fee`, `maker`, `seq`, `timestamp`

# Market metadata / leverage / symbol rules to cover

- `GET /v1/public/info/{symbol}` rule fields should drive constraints tests: `quote_min`, `quote_max`, `quote_tick`, `base_min`, `base_max`, `base_tick`, `min_notional`, `price_range`, `price_scope`, `base_imr`, `base_mmr`, `liquidation_tier`, `global_max_oi_cap`.
- Enforce filters in tests:
  - price min/max and tick alignment
  - quantity min/max and step alignment
  - min notional
  - buy/sell price-range checks against mark price
  - exposure/risk checks informed by account info / leverage settings
- Cover available-symbols registry refresh via `GET /v1/public/info` and one-symbol lookup parity via `GET /v1/public/info/{symbol}`.
- Cover leverage config surfaces from public config plus account leverage updates/settings if your exchange layer applies them.
- Per-symbol market rules should be treated as dynamic server metadata, not hardcoded assumptions.

# Error handling patterns to shape tests

- Auth/rate-limit/server classes from official refs:
  - `-1001` malformed key/secret
  - `-1002` invalid / expired / insufficient-permission key
  - `-1003` rate limit exceeded (`429`)
  - `5xx` unknown/server errors
- Trading validation classes worth explicit assertions:
  - `-1101` exposure too high / insufficient margin after order
  - `-1102` notional too small
  - `-1103` price bounds or tick mismatch
  - `-1104` quantity / visible quantity bounds or step mismatch
  - `-1105` price too far from mark/mid limit
  - `-1006` order/data not found, including canceling already-cancelled order
  - `-1007` duplicate data/request
  - `-1011` / `-1012` temporary internal rejection paths
- Websocket errors should preserve request `id`, `event`, and `errorMsg` so orchestration can attribute failures to the initiating action.
- Connector splits 4xx into client errors and 5xx into server errors; native tests should expect similarly stable classification even if exception types differ.

# Test priorities for plutus-terminal

1. Signing preimage/header construction for REST and private websocket auth.
2. Order constraint validation from live symbol metadata: tick/step/min_notional/price_range.
3. Place-edit-cancel happy paths with correct endpoint/method/query-body shapes.
4. `client_order_id` handling: lookup/cancel by client ID and duplicate-open-order rejection.
5. Websocket private auth ack, subscription ack, and execution report lifecycle mapping to local order state.
6. Ping/pong timeout behavior and reconnect-with-resubscribe semantics.
7. Exchange-layer handling of Orderly error codes into user-visible/domain errors.
8. Market registry refresh and leverage/symbol rule updates flowing into constraints/trader logic.
9. Batch cancel / cancel-all behavior if exposed by the app.
10. Temporary server/rate-limit failures and retry/non-retry policy boundaries.

# Likely mismatches to inspect in plutus-terminal

- If your code signs `path + body + query` in the wrong order, auth will be flaky; official order is `timestamp + method + path_with_query + body`.
- If private websocket auth sends subscriptions before auth success is confirmed, reconnect races are likely.
- If websocket keepalive only sends client `pong` on a local timer, also verify it responds to actual server `ping` frames/events.
- If constraints are cached statically, they may drift from `public/info` updates.
- If REST/client tests only assert request success and not returned order status markers like `EDIT_SENT` / `CANCEL_SENT`, they may miss protocol regressions.
- If current code assumes connector-style wallet-secret auth everywhere, that would conflict with your stated WebUI-token usage; keep tests focused on server-accepted headers/signatures rather than connector-specific onboarding flows.
