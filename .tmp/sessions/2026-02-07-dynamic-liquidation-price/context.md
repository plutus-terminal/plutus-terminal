# Task Context: Dynamic Estimated Liquidation Price

Session ID: 2026-02-07-dynamic-liquidation-price
Created: 2026-02-07T00:00:00Z
Status: in_progress

## Current Request
Make the estimate liquidation price dynamic based on the current available balance, and include unsettled PnL.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/business-tech-bridge.md
- .opencode/context/project-intelligence/living-notes.md
- AGENTS.md
- pyproject.toml

## Reference Files (Source Material to Look At)
- plutus_terminal/ui/widgets/perps_trade.py
- plutus_terminal/core/exchange/orderly/fetcher.py
- plutus_terminal/core/exchange/orderly/exchange.py
- plutus_terminal/core/exchange/base.py

## External Docs Fetched
None.

## Components
- Orderly available balance exposure in exchange layer
- Orderly liquidation estimate logic using dynamic account collateral
- Perps trade widget estimate construction for dynamic collateral input

## Constraints
- Keep monetary calculations in Decimal only.
- Preserve existing exchange contracts and UI behavior outside this estimate update.
- Keep changes small and scoped to liquidation estimate and balance source.

## Exit Criteria
- [ ] Estimated liquidation price changes dynamically when available balance changes.
- [ ] Available balance used for estimate includes unsettled PnL.
- [ ] Ruff and mypy checks pass for touched files.
