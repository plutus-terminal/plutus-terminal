# Task Context: Orderly Leverage Validation Fix

Session ID: 2026-02-07-leverage-validation-fix
Created: 2026-02-07T00:00:00Z
Status: in_progress

## Current Request
When setting leverage I am getting an insufficient margin error. Max leverage limits are not being respected; Orderly allows 100x leverage on BTC.

## Context Files (Standards to Follow)
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/project-intelligence/decisions-log.md
- .opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- plutus_terminal/core/exchange/base.py
- plutus_terminal/core/exchange/orderly/exchange.py
- plutus_terminal/core/exchange/orderly/markets.py
- plutus_terminal/core/exchange/orderly/trader.py
- plutus_terminal/core/exchange/orderly/rest_client.py
- plutus_terminal/controller/ui_controller.py
- plutus_terminal/ui/widgets/perps_trade.py
- plutus_terminal/ui/widgets/config/perps_config.py

## External Docs Fetched
None.

## Components
- Orderly leverage boundary computation (account-level and symbol-level).
- Leverage set flow correctness (only persist config after successful API call).
- UI enforcement and messaging for applied leverage values.

## Constraints
- Use ExchangeBase contract and existing controller/message patterns.
- Preserve Decimal-first monetary behavior.
- Do not introduce broad architectural changes.

## Exit Criteria
- [ ] Setting leverage respects per-symbol max leverage (BTC cap is not bypassed).
- [ ] Failed leverage API calls do not leave stale app leverage values.
- [ ] UI reflects effective leverage after clamping and shows accurate warnings.
