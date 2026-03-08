# Task Context: Fix Positions Liquidation Widget Runtime Error

Session ID: 2026-02-22-fix-positions-liquidation-widget-runtime-error
Created: 2026-02-22T00:00:00Z
Status: in_progress

## Current Request
When a position is open the open positions table is flickering and there is a runtime error: Internal C++ object (PySide6.QtWidgets.QLabel) already deleted during liquidation column refresh.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/project-intelligence/decisions-log.md
- .opencode/context/project-intelligence/living-notes.md

## Reference Files (Source Material to Look At)
- plutus_terminal/ui/widgets/trade_table.py
- plutus_terminal/ui/widgets/positions_table.py
- plutus_terminal/ui/ui_utils.py

## External Docs Fetched
- None

## Components
- Stored widget lifecycle safety in UI widget cache
- Liquidation column widget update path

## Constraints
- Python 3.12 only
- Preserve existing table update behavior and model/view flow
- Avoid introducing broad architectural changes

## Exit Criteria
- [ ] No runtime error from deleted QLabel during liquidation refresh
- [ ] Liquidation column updates without visible flicker regression
- [ ] Ruff lint passes for touched files
