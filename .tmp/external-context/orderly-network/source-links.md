---
source: Orderly official docs (webfetch)
library: Orderly Network
package: orderly-network
topic: source links for websocket-first exchange client
fetched: 2026-02-07T00:00:00Z
official_docs: https://orderly.network/docs/build-on-omnichain/building-on-omnichain
---

- System overview start page:
  - https://orderly.network/docs/build-on-omnichain/building-on-omnichain
- EVM API introduction (REST + WS base URLs, symbol format, rate-limit behavior):
  - https://orderly.network/docs/build-on-omnichain/evm-api/introduction
- API authentication (ed25519 signing, required headers, timestamp window):
  - https://orderly.network/docs/build-on-omnichain/evm-api/api-authentication

## Required REST endpoint docs

- Markets/instruments:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-available-symbols
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-order-rules-per-symbol
- Balances:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-current-holding
- Positions:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-all-positions-info
- Open orders:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-orders
- Place order:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/create-order
- Cancel order:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/cancel-order
- Leverage/margin:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-account-information
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/update-leverage-setting

## WebSocket docs

- WS intro (base endpoints + private topic list):
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/introduction
- WS private auth:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/authentication
- Keepalive:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/ping-pong

### Public topics

- Orderbook:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/orderbook
- Trade:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/trade
- Mark price:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/mark-price
- Mark prices:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/mark-prices
- Index price:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/index-price
- Index prices:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/index-prices
- BBO:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/bbo
- BBOS:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/bbos
- Open interest:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/open-interest

### Private topics

- Account:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/account
- Balance:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/balance
- Execution report:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/execution-report
- Notifications:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/notifications
