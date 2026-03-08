# Task Context: Orderly PnL Stability and Hover Details

Session ID: 2026-02-07-orderly-pnl-stability
Created: 2026-02-07T00:00:00Z
Status: in_progress

## Current Request
The way position are being fecthed in Orderly is problematic because the position table keeps blinking around the Pnl column. Improve it so they Pnl column stays consistent and fix the mouse hover on the Pnl to show the details of the Pnl.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/project-intelligence/business-tech-bridge.md
- .opencode/context/project-intelligence/decisions-log.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- plutus_terminal/core/exchange/orderly/fetcher.py
- plutus_terminal/ui/widgets/positions_table.py
- plutus_terminal/ui/widgets/pnl_breakdown.py
- plutus_terminal/core/exchange/base.py

## External Docs Fetched
- None.

## Components
- Orderly position refresh emission stability
- Positions table PnL widget update stability
- PnL hover tooltip behavior

## Constraints
- Preserve existing Qt signal/message bus architecture.
- Keep Decimal-based calculations unchanged.
- Avoid aggressive table model resets when positions did not materially change.

## Exit Criteria
- [ ] Position table no longer visibly blinks around the PnL column during normal refresh cycles.
- [ ] Hovering over PnL displays the PnL details tooltip consistently.
- [ ] Ruff lint/format and targeted checks pass for touched code.
