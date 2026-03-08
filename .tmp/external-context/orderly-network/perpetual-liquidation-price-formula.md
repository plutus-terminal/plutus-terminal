---
source: Orderly official docs (live fetch)
library: Orderly
package: orderly-network
topic: perpetual estimated liquidation price calculation
fetched: 2026-02-08T00:00:00Z
official_docs: https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/formulas-definitions
---

# Core liquidation trigger and formula

- Liquidation trigger: account is liquidated when `Account Margin Ratio < Maintenance Margin Ratio`.
- Account Margin Ratio: `total_collateral_value / sum(abs(position_notional_i))`.
- Estimated liquidation price (position-level estimate):

```text
Qi = position_qty
liquidation_price = max(
  mark_price + (total_collateral_value - total_notional * MMR) / (abs(Qi) * MMRi - Qi),
  0
)
```

Source pages:
- https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/formulas-definitions
- https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/liquidations

# Margin terms used by the formula

- `total_collateral_value = total_balance + upnl + pending_short_USDC`
- `position_notional_i = abs(mark_price_i * position_qty_i)`
- `total_notional = sum(abs(position_notional_i))`
- Maintenance ratio per symbol:

```text
MMR_i = max(
  Base_MMR_i,
  (Base_MMR_i / Base_IMR_i) * IMR_Factor_i * abs(position_notional_i)^(4/5)
)
```

- Portfolio/account maintenance ratio:

```text
weighted_maintenance_margin_ratio_i = abs(position_notional_i / total_notional) * MMR_i
maintenance_margin_ratio (MMR) = sum(weighted_maintenance_margin_ratio_i)
```

Source pages:
- https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/formulas-definitions
- https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/margin-leverage-and-pnl

# With open orders variant

Orderly also provides the with-orders form:

```text
Qi = position_qty + order_qty
liquidation_price = max(
  mark_price + (total_collateral_value - total_notional_with_order * MMR_with_order) / (abs(Qi) * MMR_with_order_i - Qi),
  0
)
```

Source page:
- https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/formulas-definitions

# Fees and caveats

- Trading fees: charged in USDC after every trade and added to position cost basis.
- Liquidation fees: charged when liquidation happens; split between insurance fund and liquidator based on account state.
- Mark price (not last trade price) is used for liquidation checks and formula inputs.
- API fields include `est_liq_price`, `mmr`, `imr`, and account-level collateral/margin fields.

Relevant docs:
- https://orderly.network/docs/introduction/trade-on-orderly/trading-basics/trading-fees
- https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/liquidations
- https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/mark-price-index-price-and-last-price
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-one-position-info
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-all-positions-info
