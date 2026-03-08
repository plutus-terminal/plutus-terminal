# Task Context: Orderly Dynamic Liquidation Price Display

Session ID: 2026-02-08-orderly-liquidation-dynamic
Created: 2026-02-08T00:00:00Z
Status: in_progress

## Current Request
Update the displayed data for orderly exchange. Using the formulas and definitions on this page https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/formulas-definitions also make sure that the estimated liquidation price to be dynamic in accordance to this values and that this value is displayed correclty on the open positions table. Use the existent archtecure on the table so the liquidation price cells updates indivudually from the other cells.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/project-intelligence/business-tech-bridge.md
- .opencode/context/core/standards/security-patterns.md
- .opencode/context/project-intelligence/decisions-log.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/project-intelligence/navigation.md
- .opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- plutus_terminal/core/exchange/orderly/fetcher.py
- plutus_terminal/ui/widgets/positions_table.py
- plutus_terminal/ui/widgets/trade_table.py
- plutus_terminal/ui/widgets/perps_trade.py
- plutus_terminal/core/exchange/orderly/exchange.py
- plutus_terminal/core/exchange/types.py

## External Docs Fetched
- Orderly formulas and definitions page with liquidation formula and margin definitions.
- Orderly private API Get All Positions Info docs for `/v1/positions`, including fields:
  `total_collateral_value`, `maintenance_margin_ratio`, `rows[].mmr`, `rows[].mark_price`,
  `rows[].position_qty`, and `rows[].est_liq_price`.

## Components
- Orderly position/risk data ingestion and caching.
- Liquidation price calculation aligned with Orderly formulas.
- Open positions table liquidation cell updates and refresh triggers.

## Constraints
- Preserve existing per-cell table widget architecture for liquidation updates.
- Keep monetary/risk calculations in `Decimal`.
- Prefer exchange-provided liquidation estimate when present and valid.

## Exit Criteria
- [ ] Open positions table shows correctly computed dynamic liquidation values for Orderly.
- [ ] Liquidation values refresh independently of other table columns.
- [ ] Liquidation computation uses Orderly formula inputs where exchange estimate is unavailable.
