---
source: Orderly official docs (webfetch)
library: Orderly Network
package: orderly-network
topic: python exchange client websocket-first implementation
fetched: 2026-02-07T00:00:00Z
official_docs: https://orderly.network/docs/build-on-omnichain/building-on-omnichain
---

# Environment and Base URLs

- REST mainnet: `https://api.orderly.org/`
- REST testnet: `https://testnet-api.orderly.org`
- WS public mainnet: `wss://ws-evm.orderly.org/ws/stream/{account_id}`
- WS public testnet: `wss://testnet-ws-evm.orderly.org/ws/stream/{account_id}`
- WS private mainnet: `wss://ws-private-evm.orderly.org/v2/ws/private/stream/{account_id}`
- WS private testnet: `wss://testnet-ws-private-evm.orderly.org/v2/ws/private/stream/{account_id}`

# Authentication and Signatures (REST)

- Required headers: `Content-Type`, `orderly-account-id`, `orderly-key`, `orderly-signature`, `orderly-timestamp`
- Signature algorithm: `ed25519`, encoded base64 url-safe
- Signing string format:
  1. timestamp in ms
  2. HTTP method uppercase
  3. request path including query string
  4. JSON body string (only for methods with body)
- Timestamp skew requirement: requests are rejected when `orderly-timestamp` differs by 300+ seconds

# Authentication (Private WebSocket)

- Auth event signs only the timestamp (method/path/body are blank)
- Legacy auth message:
  - `{"id":"...","event":"auth","params":{"orderly_key":"...","sign":"...","timestamp":...}}`
- New connection-time auth query string is supported:
  - `?orderly_key=...&timestamp=...&sign=...`

# Core REST Endpoints for Python Exchange Client

- Markets/instruments:
  - `GET /v1/public/info` (all symbols + rules)
  - `GET /v1/public/info/{symbol}` (rule checks for one symbol)
- Balances:
  - `GET /v1/client/holding`
- Positions:
  - `GET /v1/positions`
- Open orders:
  - `GET /v1/orders` (use `status=INCOMPLETE` for open)
- Place order:
  - `POST /v1/order`
- Cancel order:
  - `DELETE /v1/order?order_id={order_id}&symbol={symbol}`
- Leverage/margin related:
  - `GET /v1/client/info` (account_mode, max_leverage, fee rates)
  - `POST /v1/client/leverage` (symbol or futures mode leverage update)

# WebSocket Streams to Use (WebSocket-first)

- Public market data:
  - `{symbol}@orderbook` (depth 100, 1s)
  - `{symbol}@trade` (real-time)
  - `{symbol}@markprice` (1s)
  - `markprices` (1s, all symbols)
  - `{symbol}@indexprice` (1s, use SPOT symbol)
  - `indexprices` (1s, all symbols)
  - `{symbol}@bbo` (10ms)
  - `bbos` (1s)
  - `{symbol}@openinterest` (change-driven, max 10s force update)
- Private account data:
  - `account`
  - `balance`
  - `executionreport`
  - `position` (listed in WS intro topic list)
  - also listed: `wallet`, `settle`, `notifications`, `liquidationsaccount`, `liquidatorliquidations`

# Keepalive and Reconnect Notes

- Server sends `ping` every 10s
- Client must answer with `pong`
- If no pong within 10s for 10 consecutive checks, server disconnects
- Client may also send `ping` every 10s proactively

# Rate Limits and Constraints Relevant to Fast Clients

- Limit accounting is keyed by Orderly key
- On limit breach, API returns HTTP `429`
- Typical limits in the required flow:
  - `GET /v1/public/info`: 10 req/s/IP
  - `GET /v1/client/holding`: 10 req/s
  - `GET /v1/positions`: 30 req/10s/user
  - `GET /v1/orders`: 10 req/s
  - `POST /v1/order`: 10 req/s
  - `DELETE /v1/order`: 10 req/s
  - `POST /v1/client/leverage`: 5 req/60s/user

# Symbol and Precision Rules

- Perp symbols use `PERP_<BASE>_USDC` (example: `PERP_ETH_USDC`)
- Index price stream uses `SPOT_<BASE>_USDC`
- Size and price validity are enforced by `base_min`, `base_max`, `base_tick`, `quote_min`, `quote_max`, `quote_tick`, `min_notional`, and `price_range`
- Create order notes: `order_quantity` precision should be within 8 digits
- `client_order_id` must be unique among open orders
