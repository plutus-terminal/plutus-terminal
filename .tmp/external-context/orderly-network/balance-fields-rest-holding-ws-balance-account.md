---
source: Orderly official docs
library: Orderly Network
package: orderly-network
topic: field names for total/available/frozen in REST /v1/client/holding and private WS balance/account
fetched: 2026-02-07T00:00:00Z
official_docs:
  - https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-current-holding
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/introduction
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/balance
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/account
---

# REST: `GET /v1/client/holding`

From `data.holding[]` items, documented fields include:

- `token`
- `holding` (total token holding)
- `frozen` (frozen amount)
- `pending_short` (pending short amount)
- `updated_time`

No explicit `available`, `free`, `available_balance`, or `free_balance` field is documented in this endpoint schema.

# Private WebSocket topics

## Topic `balance`

Subscribed message shape (relevant subtree):

- `topic`
- `ts`
- `data.balances.<TOKEN>.holding` (total holding)
- `data.balances.<TOKEN>.frozen` (frozen amount)
- `data.balances.<TOKEN>.interest`
- `data.balances.<TOKEN>.pendingShortQty`
- `data.balances.<TOKEN>.pendingExposure`
- `data.balances.<TOKEN>.pendingLongQty`
- `data.balances.<TOKEN>.pendingLongExposure`
- `data.balances.<TOKEN>.version`
- `data.balances.<TOKEN>.staked`
- `data.balances.<TOKEN>.unbonding`
- `data.balances.<TOKEN>.vault`
- `data.balances.<TOKEN>.averageOpenPrice`
- `data.balances.<TOKEN>.pnl24H`
- `data.balances.<TOKEN>.fee24H`
- `data.balances.<TOKEN>.markPrice`

No explicit `available`/`free` field is shown in the documented `balance` topic example.

## Topic `account`

Documented payload uses `accountDetail` and contains account config/fee/leverage fields (e.g., `marginMode`, `futuresLeverage`, `symbolLeverage`), not token balances.

No token balance fields (`holding`, `available`, `free`, `frozen`) are shown in the documented `account` topic payload example.
