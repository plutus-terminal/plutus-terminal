# Task Context: Fix Orderly Estimated Liquidation Price

Session ID: 2026-02-08-orderly-liquidation-price
Created: 2026-02-08T00:00:00Z
Status: in_progress

## Current Request
The calculation for the estimated liquidation price displayed on the position table is wrong. For example a short position on bitcoin with a collateral of 9.868 and 5x leverage and available balance around 24.3 is displayed as ~116,692 but should be ~104,425. Review Orderly documentation and fix the function that calculates liquidation price.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/business-tech-bridge.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/core/workflows/code-review.md
- .opencode/context/core/workflows/external-libraries-workflow.md

## Reference Files (Source Material to Look At)
- plutus_terminal/core/exchange/orderly/fetcher.py
- plutus_terminal/core/exchange/types.py
- plutus_terminal/ui/widgets/positions_table.py
- plutus_terminal/ui/widgets/manage_order.py
- plutus_terminal/ui/widgets/perps_trade.py

## External Docs Fetched
- IMPORTANT: https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/liquidations
- https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/formulas-definitions
- https://orderly.network/docs/build-on-omnichain/evm-api/restful-api/private/get-one-position-info

## Components
- Orderly liquidation calculation path in fetcher
- Position table liquidation display refresh
- Fallback liquidation estimator for non-exchange preview values

## Constraints
- Keep Decimal-only arithmetic for money and price values.
- Follow existing exchange and UI contracts.
- Prefer authoritative exchange liquidation value when available.

## Exit Criteria
- [ ] Position table uses correct liquidation price for live Orderly positions.
- [ ] No regression for UI preview liquidation values when exchange value is unavailable.
- [ ] Lint/type checks pass for touched code.
