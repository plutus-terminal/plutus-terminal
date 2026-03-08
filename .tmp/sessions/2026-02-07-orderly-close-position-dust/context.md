# Task Context: Orderly Full Position Close Fix

Session ID: 2026-02-07-orderly-close-position-dust
Created: 2026-02-07T00:00:00Z
Status: in_progress

## Current Request
When closing the position on orderly, it's not closing the full position it's keeping a small part of it open.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/project-intelligence/decisions-log.md
- .opencode/context/project-intelligence/business-tech-bridge.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- plutus_terminal/core/exchange/orderly/exchange.py
- plutus_terminal/core/exchange/orderly/trader.py
- plutus_terminal/core/exchange/orderly/fetcher.py
- plutus_terminal/core/exchange/orderly/constraints.py
- plutus_terminal/core/exchange/types.py

## External Docs Fetched
- None

## Components
- Orderly close-position argument shaping in exchange layer
- Orderly order quantity derivation in trader layer
- Local validation and formatting checks

## Constraints
- Use Decimal-safe sizing logic only
- Preserve existing exchange contract behavior for non-close flows
- Keep changes minimal and targeted

## Exit Criteria
- [ ] Closing an Orderly position uses exact position base quantity when available
- [ ] Reduce-only market close no longer leaves dust caused by notional-to-quantity rounding drift
- [ ] Changed files pass Ruff format and Ruff lint checks
