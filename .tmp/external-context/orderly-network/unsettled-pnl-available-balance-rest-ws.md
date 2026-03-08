---
source: Orderly official docs
library: Orderly Network
package: orderly-network
topic: unsettled PnL fields and balance-calculation guidance in REST and WebSocket account/balance endpoints
fetched: 2026-02-07T00:00:00Z
official_docs:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-current-holding
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-all-positions-info
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-one-position-info
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/public/get-tvl-by-builder
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/balance
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/account
---

# What the current docs show

## REST account/balance style endpoints

### `GET /v1/client/holding` (Get Current Holding)

- Payload location: `data.holding[]`
- Documented balance fields per token: `holding`, `frozen`, `pending_short`
- Unsettled PnL field: **not documented in this endpoint**

### `GET /v1/positions` (Get All Positions Info)

- Payload location: `data.rows[].unsettled_pnl`
- This is the documented per-position unsettled PnL field.
- Same payload also includes account-level risk/collateral fields such as `free_collateral` and `total_collateral_value`.

### `GET /v1/position/{symbol}` (Get One Position Info)

- Payload location: `data.unsettled_pnl`
- This is the single-position unsettled PnL value.

## WebSocket account/balance endpoints

### Topic `balance`

- Payload location: `data.balances.<TOKEN>`
- Documented token fields include `holding`, `frozen`, `interest`, `pendingShortQty`, `pendingExposure`, `pendingLongQty`, `pendingLongExposure`, `pnl24H`, `fee24H`, `markPrice`.
- Unsettled PnL field: **not documented in the `balance` topic payload**.

### Topic `account`

- Payload location: `accountDetail`
- Documented fields are account configuration/fee/leverage settings (for example `marginMode`, `futuresLeverage`, fee rates, `symbolLeverage`).
- Unsettled PnL field: **not documented in the `account` topic payload**.

# Formula guidance explicitly documented

## Public builder TVL endpoint

For `GET /v1/public/balance/stats` (Get TVL by Builder), docs explicitly state:

- `TVL = Total Balance + Unsettled PnL`
- Payload fields:
  - `data.total_holding`
  - `data.total_unsettled_balance`

This is the only explicit formula text found in the fetched docs set.

# Practical implication for account available-balance calculations

- In current docs, unsettled PnL is explicitly available from position endpoints (`unsettled_pnl`) rather than account/balance payloads.
- If you need unsettled-PnL-aware available balance at account level, docs do not provide a direct `available_including_unsettled_pnl` field in `GET /v1/client/holding` or WS `balance`/`account`.
- You must derive from position unsettled PnL plus your balance/collateral model, or use account-level fields like `free_collateral` where appropriate for margin availability.
