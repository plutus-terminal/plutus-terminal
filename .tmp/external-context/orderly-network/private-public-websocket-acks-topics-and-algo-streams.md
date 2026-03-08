---
source: Orderly official docs (webfetch)
library: Orderly Network
package: orderly-network
topic: private websocket auth ack, subscribe/unsubscribe acks and errors, topic naming rules, executionreport and algoexecutionreport payloads
fetched: 2026-03-07T00:00:00Z
official_docs: https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/introduction
---

# Orderly WebSocket details for Python client implementation

## Scope and sources

- Source pages used:
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/introduction
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/authentication
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/error-response
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/execution-report
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/algo-execution-report
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/orderbook
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/k-line
  - https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/public/24-hour-tickers

## 1) Private WS auth acknowledgement

- Private endpoints:
  - Mainnet: `wss://ws-private-evm.orderly.org/v2/ws/private/stream/{account_id}`
  - Testnet: `wss://testnet-ws-private-evm.orderly.org/v2/ws/private/stream/{account_id}`
- Auth is required before subscribing to private topics.
- Current docs say the message to sign is only the timestamp because method/path/body are blank for WS auth.
- You can authenticate either:
  - by sending an `auth` frame after connect, or
  - by putting `orderly_key`, `timestamp`, and `sign` in the connection query string.
- Docs explicitly say the socket is disconnected if authentication fails.

Auth request shape:

```json
{
  "id": "123r",
  "event": "auth",
  "params": {
    "orderly_key": "ed25519:CUS69ZJOXwSV38xo...",
    "sign": "4180da84117fc9753b...",
    "timestamp": 1621910107900
  }
}
```

Documented success ack:

```json
{
  "id": "123r",
  "event": "auth",
  "success": true,
  "ts": 1621910107315
}
```

Implementation notes:

- The docs do not show an explicit auth-failure payload.
- The only documented failure behavior is disconnect-on-auth-failure, so client code should treat close-before-auth-success as auth failure unless another close reason is available.
- `id` is echoed back and should be used to correlate auth/subscription responses.

## 2) Subscribe/unsubscribe acknowledgement and error shape

- Topic pages consistently document request fields as:
  - `id: string`
  - `event: "subscribe" | "unsubscribe"`
  - `topic: string`
  - `params: object` when required by the topic
- Topic pages show the same success ack shape for subscription requests.
- Orderly's generic WS error page shows the failure shape.
- The docs do not provide a dedicated unsubscribe success example, but the request schema implies the same ack envelope with `event` matching the request.

Documented success ack example:

```json
{
  "id": "clientID3",
  "event": "subscribe",
  "success": true,
  "ts": 1609924478533
}
```

Documented failure example:

```json
{
  "id": "clientID7",
  "event": "subscribe",
  "success": false,
  "ts": 1614141150601,
  "errorMsg": "invalid symbol SPOT_WOO_USDC.e"
}
```

Implementation notes:

- `id` is the correlation key for both success and failure.
- `event` in responses uses the original request type (`subscribe`; likely `unsubscribe` for unsubscribe acks/errors).
- `errorMsg` is the documented error field; no structured error code is shown on the WS error page.
- A reasonable Python parser shape is `id`, `event`, `success`, `ts`, optional `errorMsg`.

## 3) Topic naming rules relevant to this subtask

Private topics from the WS introduction page:

- `account`
- `balance`
- `executionreport`
- `liquidationsaccount`
- `liquidatorliquidations`
- `notifications`
- `settle`
- `position`
- `wallet`

Additional private topic with a dedicated page:

- `algoexecutionreport`

Important doc discrepancy:

- The introduction page's private-topic list does not include `algoexecutionreport`.
- The docs index and dedicated private page do include `algoexecutionreport`, with a documented subscribe request and payload example.
- For implementation, treat `algoexecutionreport` as current/valid but worth feature-flagging or logging if the server rejects it.

Public topic naming patterns shown in current docs:

- Aggregate topics with no symbol in the name: `tickers`.
- Symbol-scoped topics: `{symbol}@orderbook`.
- Interval-scoped kline topics: `{symbol}@kline_{time}` where `{time}` is one of `1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1w`, `1M`.

Private topic naming patterns shown in current docs:

- Bare topic name only: `algoexecutionreport`.
- Bare topic name plus optional `params.symbol` filter: `executionreport` with comma-separated symbols like `PERP_BTC_USDC,PERP_ETH_USDC`.

Implementation guidance:

- Public streams are not uniform; some topics encode symbol/interval in `topic`, while others are plain names.
- Private streams are closer to RPC-style topics: a plain topic string plus optional filters in `params`.
- Symbols in examples use `PERP_<BASE>_USDC` naming.

## 4) `executionreport` event stream payload

Subscribe example:

```json
{
  "id": "clientID3",
  "topic": "executionreport",
  "event": "subscribe",
  "params": {
    "symbol": "PERP_BTC_USDC,PERP_ETH_USDC"
  }
}
```

Documented push example:

```json
{
  "topic": "executionreport",
  "ts": 1704679472455,
  "data": {
    "symbol": "PERP_MATIC_USDC",
    "clientOrderId": "",
    "orderId": 292820969,
    "type": "LIMIT",
    "side": "BUY",
    "quantity": 7029.0,
    "price": 0.7699,
    "tradeId": 0,
    "executedPrice": 0.0,
    "executedQuantity": 0.0,
    "fee": 0.0,
    "feeAsset": "USDC",
    "totalExecutedQuantity": 0.0,
    "avgExecutedPrice": 0,
    "status": "NEW",
    "reason": "",
    "totalFee": 0.0,
    "visibleQuantity": 7029.0,
    "timestamp": 1704679472448,
    "maker": false,
    "match_id": "1707119522287540609",
    "seq": 1730181536341943600
  }
}
```

Implementation notes:

- `data` is a single object for `executionreport`, not an array.
- `tradeId` can be `0` for non-fill state updates.
- The example includes both order-entry fields (`type`, `side`, `quantity`, `price`) and execution-state fields (`executedPrice`, `executedQuantity`, `totalExecutedQuantity`, `avgExecutedPrice`, `status`, `reason`).
- Sequence/tracing fields present in the example: `timestamp`, `match_id`, `seq`.
- Numeric fields are shown as JSON numbers; for a trading client, parse monetary/size values into `Decimal` instead of `float`.

## 5) `algoexecutionreport` event stream payload

Subscribe example:

```json
{
  "id": "clientID3",
  "topic": "algoexecutionreport",
  "event": "subscribe"
}
```

Documented push example:

```json
{
  "topic": "algoexecutionreport",
  "ts": 1750997326998,
  "data": [
    {
      "symbol": "PERP_NEAR_USDC",
      "rootAlgoOrderId": 654400003,
      "parentAlgoOrderId": 0,
      "algoOrderId": 654400003,
      "clientOrderId": "clientOrderId123",
      "orderTag": "tag1",
      "status": "FILLED",
      "algoType": "STOP",
      "side": "SELL",
      "quantity": 3,
      "triggerStatus": "SUCCESS",
      "price": 1.25,
      "type": "MARKET",
      "triggerTradePrice": 1.3,
      "triggerTime": 1750997326000,
      "tradeId": 10001,
      "executedPrice": 1.3,
      "executedQuantity": 3,
      "fee": 1.2,
      "feeAsset": "USDC",
      "totalExecutedQuantity": 3,
      "averageExecutedPrice": 1.3,
      "totalFee": 1.2,
      "timestamp": 1750997326991,
      "visibleQuantity": 3,
      "reduceOnly": true,
      "callbackRate": null,
      "callbackValue": null,
      "extremePrice": null,
      "activatedPrice": null,
      "triggered": true,
      "activated": null,
      "maker": true,
      "isMaker": true,
      "rootAlgoStatus": "FILLED",
      "algoStatus": "FILLED",
      "isActivated": true,
      "triggerPrice": 1.25,
      "triggerPriceType": "MARK_PRICE",
      "createdTime": 1750997261728
    }
  ]
}
```

Implementation notes:

- `data` is an array for `algoexecutionreport`, unlike the single-object `executionreport` example.
- Algo-specific identity fields: `rootAlgoOrderId`, `parentAlgoOrderId`, `algoOrderId`.
- Trigger lifecycle fields: `triggerStatus`, `triggerTradePrice`, `triggerTime`, `triggerPrice`, `triggerPriceType`, `triggered`, `isActivated`, `activated`, `activatedPrice`.
- Trailing-stop style placeholders can be `null`: `callbackRate`, `callbackValue`, `extremePrice`, `activatedPrice`.
- The example contains both `maker` and `isMaker`, plus both `status` and `algoStatus`; do not collapse them unless you have observed server behavior confirming equivalence.
- The regular execution report uses `avgExecutedPrice`, while the algo execution example uses `averageExecutedPrice`; code should support both spellings.

## 6) Failure cases actually documented vs not documented

Documented now:

- Auth success payload.
- Generic subscribe success payload.
- Generic subscribe failure payload with `errorMsg`.
- `executionreport` push shape.
- `algoexecutionreport` push shape.

Not documented on the current pages fetched:

- Explicit auth failure payload.
- Explicit unsubscribe success example.
- Explicit unsubscribe failure example.
- Exhaustive enum lists for `status`, `reason`, `algoType`, or `triggerStatus` on these WS pages.

Recommended client behavior:

- Correlate request/response with `id`.
- Time out auth and subscriptions waiting for `{success:true}`.
- Treat `{success:false, errorMsg}` as a recoverable request failure.
- Treat socket close during auth as auth failure.
- Parse `executionreport.data` as object and `algoexecutionreport.data` as list.
