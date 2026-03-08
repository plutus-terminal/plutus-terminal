# Task Context: Orders Table Refactor

Session ID: 2026-03-07-orders-table-refactor
Created: 2026-03-07T16:20:00
Status: in_progress

## Current Request
Apply the same behavior on `orders_table` as the refactored positions table.

## Context Files (Standards to Follow)
- `.opencode/context/project-intelligence/technical-domain.md`
- `.opencode/context/project-intelligence/decisions-log.md`
- `.opencode/context/project-intelligence/living-notes.md`
- `.opencode/context/core/standards/code-quality.md`
- `.opencode/context/core/essential-patterns.md`
- `.opencode/context/core/workflows/component-planning.md`

## Reference Files (Source Material to Look At)
- `plutus_terminal/ui/widgets/orders_table.py`
- `plutus_terminal/ui/widgets/positions_table_model.py`
- `plutus_terminal/ui/widgets/positions_table_view.py`
- `plutus_terminal/ui/widgets/trade_table.py`
- `plutus_terminal/ui/widgets/manage_order.py`

## External Docs Fetched
- None.

## Components
- Order table state helpers
- Order table column definitions
- Order action cell widget
- Order table model
- Order table view
- Thin public export module

## Constraints
- Preserve `TradeTable` as the composition boundary.
- Match the positions-table split and per-row update behavior.
- Keep exchange actions in widgets, not the generic model.
- Keep behavior unchanged aside from architecture and more targeted updates.

## Exit Criteria
- [ ] `orders_table` follows the same split model/view/cell structure as `positions_table`
- [ ] order action cells are cached and updated per row instead of recreated on every reset
- [ ] order model supports row-key-based updates when row identity is unchanged
- [ ] Ruff, mypy, and formatting pass for touched files
