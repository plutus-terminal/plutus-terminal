# Task Context: Orderly Open Position Widget Refresh

Session ID: 2026-02-07-orderly-position-widget-sync
Created: 2026-02-07T00:00:00Z
Status: in_progress

## Current Request
When a position from orderly is open it's not being identified in the open position widget, it will only show after a restart of the app. Fix that.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/business-tech-bridge.md
- .opencode/context/project-intelligence/decisions-log.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/project-intelligence/navigation.md
- .opencode/context/core/standards/project-intelligence.md
- .opencode/context/core/workflows/component-planning.md

## Reference Files (Source Material to Look At)
- plutus_terminal/core/exchange/orderly/fetcher.py
- plutus_terminal/core/exchange/orderly/exchange.py
- plutus_terminal/core/exchange/base.py
- plutus_terminal/ui/widgets/trade_table.py
- plutus_terminal/ui/widgets/positions_table.py

## External Docs Fetched
None.

## Components
- Orderly position refresh loop
- Position update signal emission to UI widgets

## Constraints
- Keep behavior aligned with existing message-bus update patterns.
- Avoid changing unrelated exchange implementations.
- Keep polling interval semantics intact.

## Exit Criteria
- [ ] Open positions from Orderly appear in the positions widget without app restart.
- [ ] Existing Orderly polling and position update flow remains stable.
- [ ] Lint passes for modified files.
