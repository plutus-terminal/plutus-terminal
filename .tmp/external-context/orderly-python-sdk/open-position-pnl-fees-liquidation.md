---
source: Official Orderly docs + official Orderly Python SDK repository
library: Orderly Python SDK
package: orderly-evm-connector-python
topic: open position pnl fees funding liquidation
fetched: 2026-03-08T00:00:00Z
official_docs: https://orderly.network/docs/llms.txt
---

# Official findings

## Python SDK endpoints / files

- `orderly_evm_connector/rest/_trade.py`
  - `get_all_positions_info()` -> `GET /v1/positions`
  - `get_one_position_info(symbol)` -> `GET /v1/position/{symbol}`
  - `get_funding_fee_history(symbol, **kwargs)` -> `GET /v1/funding_fee/history`
- `orderly_evm_connector/rest/_account.py`
  - `get_account_information()` -> `GET /v1/client/info`
  - `get_position_history(symbol=None, limit=None)` -> `GET /v1/position_history`
- `orderly_evm_connector/rest/_settlement.py`
  - `get_settle_pnl_nonce()` -> `GET /v1/settle_nonce`
  - `request_pnl_settlement(...)` -> `POST /v1/settle_pnl`

The SDK is a thin wrapper around Orderly APIs. It does not implement local PnL/funding/liquidation calculations itself.

## Position fields exposed by official API

From `GET /v1/position/{symbol}` and `GET /v1/positions`, the official position payload includes:

- `average_open_price`
- `mark_price`
- `position_qty`
- `unsettled_pnl`
- `est_liq_price`
- `last_sum_unitary_funding`
- `fee_24_h`

Official docs formula:

- Unrealized PnL = `position_qty * (mark_price - avg_open)`
- Liquidation price = `max(Mark Price + (total_collateral_value - total_notional * MMR) / (|Qi| * MMRi - Qi), 0)`

Official docs also explicitly say: `Unsettled PnL is retrieved from the API and cannot be calculated`.

## Funding fee guidance

- Official history source: `GET /v1/funding_fee/history`
  - returns `funding_rate`, `mark_price`, `funding_fee`, `payment_type` (`Receive`/`Pay`), and `status` (`Accrued`/`Settled`).
- Official product docs define accrued funding at each funding timestamp as:
  - `Accrued Funding(dt) = Position Size * Mark Price * Funding Rate`
- Official docs further state funding is settled when PnL settlement is called.

Practical implication:

- For actual open-position funding amount, use the official API/history as source of truth.
- Do not try to fully reconstruct cumulative funding locally from current position data alone.
- `last_sum_unitary_funding` exists in the position payload, but the public docs fetched here do not document a client-side formula using it.

## Estimated PnL after fees guidance

- If you want the authoritative current position PnL state, prefer API `unsettled_pnl` over locally computed unrealized PnL.
- Why:
  - docs distinguish unrealized PnL from unsettled PnL;
  - docs say unsettled PnL cannot be calculated locally;
  - settled/unsettled PnL is what matters for settlement and withdrawability.

## Opening + closing fees + funding fee

- Official trading-fees docs say perpetual trading fees are charged after every trade in USDC and are **factored into the position's average entry price**.
- Therefore:
  - opening fee is already reflected if you use `average_open_price` and compute unrealized PnL from it;
  - opening fee should not be subtracted again;
  - estimated close fee should be added separately for an open position estimate;
  - funding should be added/subtracted from API funding records or included via authoritative `unsettled_pnl`.

Safe display rule:

- `estimated_pnl_after_fees ~= unsettled_pnl - expected_close_fee`

If you cannot rely on `unsettled_pnl`, fallback approximation is:

- `position_qty * (mark_price - average_open_price) - expected_close_fee +/- funding_adjustment`

but this is less authoritative than `unsettled_pnl`.

## Liquidation price display guidance

- Official position APIs already return `est_liq_price`.
- Official docs publish a formula, but it depends on account-level values such as `total_collateral_value`, `total_notional`, `MMR`, and symbol-specific `MMRi`.
- Because Orderly also states unsettled PnL cannot be calculated locally, the API value is the safer display source.

Recommendation:

- Use native API `est_liq_price` for UI display.
- Use local derivation only for sanity checks or fallback, not as the primary displayed number.

## Key official links

- SDK repo: https://github.com/OrderlyNetwork/orderly-evm-connector-python
- Position endpoint docs: https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-one-position-info
- All positions docs: https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-all-positions-info
- Funding fee history docs: https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-funding-fee-history
- PnL settlement docs: https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/request-pnl-settlement
- Margin / PnL docs: https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/margin-leverage-and-pnl
- Formulas docs: https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/formulas-definitions
- Funding docs: https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/funding-rate
- Liquidation docs: https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/liquidations
- Trading fees docs: https://orderly.network/docs/introduction/trade-on-orderly/trading-basics/trading-fees
