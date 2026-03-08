---
source: Official Orderly docs
library: Orderly Network
package: orderly
topic: trading-client-parity
fetched: 2026-03-07T00:00:00Z
official_docs: https://orderly.network/docs/llms.txt
---

# Orderly trading client parity notes

Base URLs:
- REST mainnet: `https://api.orderly.org`
- REST testnet: `https://testnet-api.orderly.org`
- WS private mainnet: `wss://ws-private-evm.orderly.org/v2/ws/private/stream/{account_id}`
- WS private testnet: `wss://testnet-ws-private-evm.orderly.org/v2/ws/private/stream/{account_id}`

Auth:
- REST requires `orderly-account-id`, `orderly-key`, `orderly-signature`, `orderly-timestamp`.
- Signature payload is `timestamp + METHOD + path_with_query + json_body_if_any` using ed25519, base64url output.
- GET/DELETE use `application/x-www-form-urlencoded`; POST/PUT use `application/json`.
- Request timestamp older/newer than 300s from server time is rejected.
- WS private auth can be sent as `{event:"auth", params:{orderly_key, sign, timestamp}}` or pre-authenticated in the query string when opening the socket.

Private REST - regular orders:
- `POST /v1/order`: create order. Important request fields: `symbol`, `order_type`, `side`, `order_price`, `order_quantity`, `order_amount`, `client_order_id`, `reduce_only`, `visible_quantity`, `slippage`, `order_tag`, `level`, `post_only_adjust`.
- Supported `order_type`: `LIMIT`, `MARKET`, `IOC`, `FOK`, `POST_ONLY`, `ASK`, `BID`.
- `PUT /v1/order`: edit pending order; docs say only `order_price` or `order_quantity` can be amended.
- `DELETE /v1/order?order_id=&symbol=`: cancel one order; response status is `CANCEL_SENT`.
- `GET /v1/order/{order_id}` / `GET /v1/orders`: order details/list. Core response fields: `order_id`, `client_order_id`, `price`, `quantity`, `amount`, `executed_quantity`, `total_executed_quantity`, `average_executed_price`, `status`, `visible_quantity`, `side`, `symbol`, `total_fee`, `fee_asset`, `realized_pnl`, `created_time`, `updated_time`.
- `GET /v1/trades`: fills/trade history; useful fields: `fee`, `fee_asset`, `executed_price`, `executed_quantity`, `executed_timestamp`, `is_maker`, `realized_pnl`, `match_id`.

Private REST - algo / conditional orders:
- `POST /v1/algo/order`: create conditional/algo order. Docs list `algo_type`: `STOP`, `TP_SL`, `POSITIONAL_TP_SL`, `BRACKET`, `BRACKET + TP_SL`, `TRAILING_STOP`.
- For `STOP`, request uses `type` = `LIMIT` or `MARKET`, plus `trigger_price_type` (docs currently say only `MARK_PRICE`), `trigger_price`, `price` if limit, `quantity`, `side`, `reduce_only`.
- For `TP_SL`, pass `child_orders` with `TAKE_PROFIT` and/or `STOP_LOSS`; child orders can be `MARKET` or `LIMIT` and typically `reduce_only: true`.
- For `POSITIONAL_TP_SL`, parent does not need explicit quantity in the sample; child orders use `type: CLOSE_POSITION` and `algo_type: TAKE_PROFIT` / `STOP_LOSS`.
- For `TRAILING_STOP`, docs require `algo_type: TRAILING_STOP`, `type: MARKET`, plus `callbackRate`; `activatedPrice` and `callbackValue` also appear in schema.
- `GET /v1/algo/orders`: list algo orders. Important fields: `algo_order_id`, `root_algo_order_id`, `parent_algo_order_id`, `algo_type`, `algo_status`, `root_algo_order_status`, `trigger_price`, `trigger_price_type`, `is_triggered`, `quantity`, `executed_quantity`, `total_executed_quantity`, `total_fee`, `fee_asset`, `realized_pnl`, `child_orders`.
- `DELETE /v1/algo/order`, `PUT /v1/algo/order`, and bulk cancel endpoints exist in docs index for lifecycle parity.

Algo caveats from samples/docs:
- `TP_SL` creates three algo orders internally.
- Edit `TP_SL` through the `root_algo_order`; if changing quantity, both child orders must be passed and quantities must match.
- Max untriggered orders: 10 `TP_SL` per user; 1 untriggered `POSITIONAL_TP_SL` per user.
- `BRACKET + POSITIONAL_TP_SL` can cancel previous active positional TP/SL orders so only one active positional TP/SL remains.

Positions / balances / client info:
- `GET /v1/positions` and `GET /v1/position/{symbol}` return margin/account rollups plus per-position rows.
- Position fields covering parity needs: `average_open_price`, `cost_position`, `est_liq_price`, `fee_24_h`, `last_sum_unitary_funding`, `mark_price`, `pending_long_qty`, `pending_short_qty`, `pnl_24_h`, `position_qty`, `settle_price`, `unsettled_pnl`, `leverage`, `imr`, `mmr`, `IMR_withdraw_orders`, `MMR_with_orders`.
- `GET /v1/client/holding` returns balances by token with `holding`, `frozen`, `pending_short`, `updated_time`; `all=true` includes zero balances.
- `GET /v1/client/info` returns fee/config data: `account_id`, `account_mode`, `max_leverage`, `maker_fee_rate`, `taker_fee_rate`, `futures_maker_fee_rate`, `futures_taker_fee_rate`, `rwa_*_fee_rate`, `maintenance_cancel_orders`, `imr_factor`, `max_notional`.
- `POST /v1/client/leverage` updates leverage globally or by symbol; response echoes `symbol` and `leverage`.
- `GET /v1/public/config` exposes `available_futures_leverage` values.
- `GET /v1/funding_fee/history` returns `funding_rate`, `mark_price`, `funding_fee`, `payment_type`, `status`, `created_time`, `updated_time`.

Private WS topics and acknowledgements:
- Auth success response shape: `{id, event:"auth", success:true, ts}`.
- Subscription ack shape across private topics is consistently `{id, event:"subscribe", success:true, ts}`.
- `executionreport` payload covers order lifecycle and fills: `orderId`, `clientOrderId`, `type`, `side`, `quantity`, `price`, `tradeId`, `executedPrice`, `executedQuantity`, `fee`, `feeAsset`, `totalExecutedQuantity`, `avgExecutedPrice`, `status`, `reason`, `totalFee`, `visibleQuantity`, `maker` / `isMaker`, `match_id`, `seq`, `timestamp`.
- `algoexecutionreport` adds algo fields: `rootAlgoOrderId`, `parentAlgoOrderId`, `algoOrderId`, `algoType`, `triggerStatus`, `triggerTradePrice`, `triggerTime`, `rootAlgoStatus`, `algoStatus`, `triggerPrice`, `triggerPriceType`, `callbackRate`, `callbackValue`, `activatedPrice`, `triggered`, `isActivated`, `createdTime`.
- `position` push carries `positionQty`, `costPosition`, `lastSumUnitaryFunding`, `pendingLongQty`, `pendingShortQty`, `settlePrice`, `averageOpenPrice`, `unsettledPnl`, `pnl24H`, `fee24H`, `markPrice`, `estLiqPrice`, `imrwithOrders`, `mmrwithOrders`, `mmr`, `imr`, `seq`, `timestamp`, `updated_time`, `leverage`.
- `balance` push carries per-token `holding`, `frozen`, `interest`, `pendingShortQty`, `pendingExposure`, `pendingLongQty`, `pendingLongExposure`, `staked`, `unbonding`, `vault`, `averageOpenPrice`, `pnl24H`, `fee24H`, `markPrice`.
- `account` push carries `marginMode`, `futuresLeverage`, `takerFeeRate`, `makerFeeRate`, `futuresTakerFeeRate`, `futuresMakerFeeRate`, `maintenanceCancelFlag`, and `symbolLeverage`.

Caveats:
- Testnet and mainnet have separate REST/WS hosts; symbol shape remains `PERP_<TOKEN>_USDC`.
- Trading endpoints require an Orderly key with `trading` scope.
- `client_order_id` must be unique among open orders; duplicate open IDs are rejected.
- `visible_quantity` is for iceberg-style visibility, but docs say it does not work for `MARKET` / `IOC` / `FOK` and is not supported for `POST_ONLY`.
- `MARKET` orders can be partially filled then cancel residual size if book depth or price-range protection is exceeded.
- Order list status bundles: `INCOMPLETE = NEW + PARTIAL_FILLED`; `COMPLETED = CANCELLED + FILLED`.
- Builder/broker behavior exists around keys and fees: docs note Orderly keys may come from frontend builders such as WOOFi Pro, and fee rates can be builder-specific via custom fee configuration / builder-only fee endpoints. Do not hardcode one fee schedule.
