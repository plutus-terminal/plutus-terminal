---
source: Official Orderly docs
library: Orderly Network
package: orderly
topic: ui-order-display-fields
fetched: 2026-03-07T00:00:00Z
official_docs: https://orderly.network/docs/llms.txt
---

# Orderly fields relevant to display-only UI updates

## 1) App-level `order_kind` vs documented Orderly fields

- Orderly docs do **not** define an `order_kind` enum with `REGULAR`, `STOP`, or `ALGO_TP_SL`.
- The documented split is:
  - regular orders via `/v1/order`, `/v1/orders`, and private WS topic `executionreport`
  - algo orders via `/v1/algo/order`, `/v1/algo/orders`, and private WS topic `algoexecutionreport`
- Safe UI mapping if your parser already uses these app-level values:
  - `REGULAR` -> standard order endpoints / `executionreport`
  - `STOP` -> algo orders where `algo_type = STOP`
  - `ALGO_TP_SL` -> algo orders involving `TP_SL` or `POSITIONAL_TP_SL` trees
- Do not present `REGULAR`, `STOP`, or `ALGO_TP_SL` as official Orderly API values; they are only safe as internal UI categories.

Sources:
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/create-order
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/create-algo-order
- https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/execution-report
- https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/algo-execution-report

## 2) STOP / trigger / price semantics

- `algo_type = STOP` is an algo order that places a new order only after a trigger condition is met.
- `trigger_price` is the stop/trigger threshold.
- `trigger_price_type`: docs say **only `MARK_PRICE` is available for now**.
- `type` on STOP is the post-trigger order type and is documented as `LIMIT` or `MARKET`.
- `price` is relevant for triggered `LIMIT` stops; it is not needed for triggered `MARKET` stops.
- Orderly prose says a stop becomes a market order once the stop price is reached, but the API schema and examples explicitly support both `LIMIT` and `MARKET` STOP orders. For UI, show the actual `type` and `price` from payload instead of assuming all stops become market orders.
- Docs do not expose a separate official `trigger_condition` enum such as "gte", "lte", "cross_above", or "cross_below".
- Safe display wording: `MARK_PRICE reaches trigger_price` or `Triggers on MARK_PRICE at <trigger_price>`.
- Do **not** invent unsupported trigger-condition labels unless your parser derives them from other verified business rules.

Sources:
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/create-algo-order
- https://orderly.network/docs/build-on-omnichain/user-flows/algo-order-samples

## 3) Paired TP/SL child orders

- `TP_SL` is an algo order family with child orders for `TAKE_PROFIT` and/or `STOP_LOSS`.
- Docs say each placed `TP_SL` creates **three algo orders** in the system: the root plus child orders.
- Child orders are carried in `child_orders`.
- For non-positional `TP_SL`, child orders may use `MARKET` or `LIMIT` and can carry `price` plus `trigger_price`.
- `POSITIONAL_TP_SL` is specifically position-closing logic:
  - child `type` should be `CLOSE_POSITION`
  - quantity is position-sized at trigger time rather than taken from the root quantity field in the same way as plain `TP_SL`
- Docs also say there can be at most 10 untriggered `TP_SL` orders per user and at most 1 untriggered `POSITIONAL_TP_SL` order.
- For editing, docs say edits are made on the `root_algo_order`; if editing quantity on `TP_SL`, both child orders must be passed and quantities must match.
- Safe display implication: treat TP and SL legs as linked by `root_algo_order_id` / parent-child relationships, not by guessing from side or trigger price alone.

Sources:
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/create-algo-order
- https://orderly.network/docs/build-on-omnichain/user-flows/algo-order-samples
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-algo-orders

## 4) WebSocket/private-stream fields that affect display

### `executionreport` (regular orders)

- Topic: `executionreport`
- Relevant fields in example payload:
  - `type`, `side`, `quantity`, `price`
  - `executedPrice`, `executedQuantity`, `totalExecutedQuantity`, `avgExecutedPrice`
  - `status`, `reason`
  - `fee`, `totalFee`, `feeAsset`
  - `visibleQuantity`
  - `maker`
  - `timestamp`, `seq`
- Safe display distinction:
  - `fee` looks per execution update
  - `totalFee` is the accumulated fee on the order
  - `avgExecutedPrice` is the running average across fills

### `algoexecutionreport` (algo orders)

- Topic: `algoexecutionreport`
- Example payload `data` is an **array** of algo-order objects.
- Relevant identity/linking fields:
  - `rootAlgoOrderId`
  - `parentAlgoOrderId`
  - `algoOrderId`
  - `clientOrderId`
  - `orderTag`
- Relevant state fields:
  - `algoType`
  - `status`, `algoStatus`, `rootAlgoStatus`
  - `triggerStatus`
  - `triggered`, `isActivated`
  - `triggerTime`, `createdTime`, `timestamp`
- Relevant price/size/fee fields:
  - `triggerPrice`, `triggerPriceType`
  - `price`, `type`
  - `triggerTradePrice`
  - `quantity`, `executedQuantity`, `totalExecutedQuantity`
  - `executedPrice`, `averageExecutedPrice`
  - `fee`, `totalFee`, `feeAsset`
  - `visibleQuantity`
  - `reduceOnly`
- Relevant trailing-stop-only fields in schema/example:
  - `callbackRate`, `callbackValue`, `extremePrice`, `activatedPrice`, `activated`
- Safe display implication:
  - use IDs to group root and child algo rows
  - show trigger metadata only when present
  - do not assume all algo orders have trailing-stop fields

### `position` push

- Topic: `position`
- Relevant fields for chart/account display:
  - `markPrice`
  - `averageOpenPrice`
  - `unsettledPnl`
  - `fee24H`
  - `estLiqPrice`
  - `imr`, `mmr`, `imrwithOrders`, `mmrwithOrders`
  - `positionQty`, `pendingLongQty`, `pendingShortQty`
- `fee24H` is a rolling 24h fee aggregate on the position push, not the same thing as per-fill `fee` or cumulative order `totalFee`.

### `account` push

- Topic: `account`
- Relevant fields for account-level fee/rate display:
  - `takerFeeRate`, `makerFeeRate`
  - `futuresTakerFeeRate`, `futuresMakerFeeRate`
  - `rwaFuturesTakerFeeRate`, `rwaFuturesMakerFeeRate`
  - `maintenanceCancelFlag`
  - `marginMode`, `futuresLeverage`, `symbolLeverage`
- These are account-config/rate fields, not charged trade amounts.

### `liquidationsaccount` push

- Relevant liquidation-only fields:
  - `transferAmountToInsuranceFund`
  - per-position `transferPrice`, `liquidatorFee`, `insuranceFundFee`, `absLiquidationFee`
- These should be displayed only in liquidation contexts, not mixed with regular trading fees.

Sources:
- https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/execution-report
- https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/algo-execution-report
- https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/position-push
- https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/account
- https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/liquidation-account-push

## 5) Liquidation price semantics

- REST positions and position push expose estimated liquidation price as `est_liq_price` / `estLiqPrice`.
- Orderly's formulas docs define liquidation price using mark price, total collateral, total notional, per-position MMR, and position quantity.
- The liquidation docs say liquidation is triggered when **Account Margin Ratio falls below Maintenance Margin Ratio**, and Orderly uses **Mark Price** for liquidation logic rather than Last Price.
- Safe display wording: `Estimated liquidation price`.
- Do not present it as a guaranteed execution/liquidation price or as a trigger based on last-traded price.
- Docs do not define a special semantic meaning for `0` beyond examples that may show `0.0`; safest UI treatment is to render the server value as-is or treat non-positive values as unavailable, rather than inventing a stronger interpretation.

Sources:
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-all-positions-info
- https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/formulas-definitions
- https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/liquidations

## 6) Funding fee / trading fee / account-level fee distinctions

### Trading-fee rate fields (account-level)

- REST `GET /v1/client/info` exposes current fee-rate fields such as:
  - `taker_fee_rate`, `maker_fee_rate`
  - `futures_taker_fee_rate`, `futures_maker_fee_rate`
  - `rwa_taker_fee_rate`, `rwa_maker_fee_rate`
- WS `account` push exposes camelCase variants:
  - `takerFeeRate`, `makerFeeRate`
  - `futuresTakerFeeRate`, `futuresMakerFeeRate`
  - `rwaFuturesTakerFeeRate`, `rwaFuturesMakerFeeRate`
- These are fee **rates**, not realized fee amounts.

### Trading-fee amount fields (execution/order/trade level)

- `executionreport`: `fee` and `totalFee`
- `algoexecutionreport`: `fee` and `totalFee`
- `GET /v1/orders`: `total_fee`
- `GET /v1/trades`: `fee`
- `GET /v1/trades` also includes `realized_pnl`, which should remain distinct from fee.
- Safe display distinction:
  - `fee` = per trade/fill fee amount
  - `total_fee` / `totalFee` = cumulative fee across fills for that order/algo order
  - account fee-rate fields = configured rates, not charged amounts

### Funding-fee amount fields

- `GET /v1/funding_fee/history` exposes:
  - `funding_rate`
  - `mark_price`
  - `funding_fee`
  - `payment_type` (`Receive` / `Pay`)
  - `status` (`Accrued` / `Settled`)
- Safe display distinction:
  - funding fee is a periodic funding transfer, not a trading fee
  - `payment_type` tells direction of cash flow
  - `status` tells whether it is accrued but unsettled vs settled

### Important fee caveat from docs

- Orderly trading-fees docs say **perpetual futures trading fees are charged after every trade in USDC** and are factored into the position's average entry price.
- Some endpoint schemas/examples use a generic `fee_asset` field and older examples may show non-USDC assets; for current perp UI, prefer rendering the server-provided `fee_asset`, but do not invent other perp fee assets if they are absent.

Sources:
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-account-information
- https://orderly.network/docs/build-on-omnichain/evm-api/websocket-api/private/account
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-trades
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-funding-fee-history
- https://orderly.network/docs/introduction/trade-on-orderly/trading-basics/trading-fees

## 7) Conservative UI rules supported by docs

- Show official API fields exactly when present; avoid creating unsupported enums for trigger direction or algo subtype.
- For app-level `order_kind`, keep it explicitly internal and derive it from whether payloads come from regular or algo order channels.
- Label liquidation price as estimated and mark-price-based.
- Separate three fee concepts in UI:
  - configured fee rate
  - realized trading fee amount
  - funding fee amount
- For TP/SL trees, group by root/parent IDs and display child-leg type (`TAKE_PROFIT`, `STOP_LOSS`) directly from payload when available.
