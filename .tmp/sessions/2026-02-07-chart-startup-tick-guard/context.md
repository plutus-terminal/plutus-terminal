# Task Context: Startup Chart Tick Guard

Session ID: 2026-02-07-chart-startup-tick-guard
Created: 2026-02-07T15:10:00Z
Status: in_progress

## Current Request
Fix startup error: `TypeError: 'NoneType' object is not subscriptable` raised from `TradingChart.update_chart_tick` when calling `lightweight_charts.update_from_tick` before chart bar initialization.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/core/workflows/code-review.md

## Reference Files (Source Material to Look At)
- plutus_terminal/ui/widgets/trading_chart.py
- AGENTS.md

## External Docs Fetched
- None

## Components
- Trading chart tick-update guard during startup initialization
- Startup/runtime validation for first live tick handling

## Constraints
- Do not crash when tick arrives before initial OHLCV data is set
- Preserve existing chart update behavior after initialization
- Keep fix minimal and localized to chart widget flow

## Exit Criteria
- [ ] Startup no longer crashes when early price tick arrives
- [ ] Tick updates continue to render once history has been loaded
- [ ] Formatting/lint/type checks pass for changed code
