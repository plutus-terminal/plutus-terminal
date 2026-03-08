# Task Context: Orderly Parity Implementation

Session ID: 2026-03-07-orderly-parity
Created: 2026-03-07T00:00:00Z
Status: in_progress

## Current Request
Investigate Foxify's use of Orderly, compare it with the local Orderly implementation in plutus-terminal, and implement Orderly parity improvements. Keep scope to Orderly parity only. TP/SL should support single-order-at-a-time by default, but also allow users to submit both TP and SL if they want.

## Context Files (Standards to Follow)
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/core/workflows/task-delegation-basics.md
- .opencode/context/core/workflows/task-delegation-specialists.md

## Reference Files (Source Material)
- AGENTS.md
- plutus_terminal/core/exchange/types.py
- plutus_terminal/core/exchange/orderly/exchange.py
- plutus_terminal/core/exchange/orderly/trader.py
- plutus_terminal/core/exchange/orderly/fetcher.py
- plutus_terminal/core/exchange/orderly/websocket.py
- plutus_terminal/core/exchange/orderly/rest_client.py
- plutus_terminal/core/exchange/orderly/auth.py
- plutus_terminal/core/exchange/orderly/markets.py
- plutus_terminal/ui/widgets/manage_order.py
- plutus_terminal/ui/widgets/orders_table.py
- plutus_terminal/ui/widgets/positions_table_action_cell.py
- plutus_terminal/ui/widgets/trading_chart.py
- plutus_terminal/ui/widgets/account_info.py
- plutus_terminal/controller/ui_controller.py

## External Context Fetched
- .tmp/external-context/orderly/trading-client-parity.md - Current Orderly docs for regular orders, algo orders, websocket acknowledgements, positions, balances, fees, and liquidation fields.

## Components
- OrderlyExchange - exchange adapter and UI-facing operations.
- OrderlyTrader - request building for regular and algo order lifecycle.
- OrderlyFetcher - REST/WS synchronization, parsing, and account math.
- OrderlyWebsocketManager - private/public WS auth and subscription lifecycle.
- Orderly UI widgets - TP/SL, order table, chart overlays, account info.
- Tests - new behavior coverage for request builders and parsers.

## Constraints
- Python 3.12 only.
- Use Decimal end-to-end for trade math.
- Preserve ExchangeBase and MessageBus architecture.
- Keep TP/SL UX single-order-first, but allow submitting both TP and SL together.
- Do not implement Foxify funded/broker product features.
- Prefer native Orderly fields over local estimates when available.

## Exit Criteria
- [ ] Regular and algo Orderly orders are represented distinctly in models and parsing.
- [ ] Stop, TP, and SL requests are sent with native Orderly payloads.
- [ ] UI allows single TP or SL and optional paired TP+SL submission.
- [ ] Websocket auth/subscription handling is more robust and algo events are consumed.
- [ ] Funding/liquidation/fee data uses Orderly-native fields where practical.
- [ ] Targeted tests cover request building and order parsing.
- [ ] Formatting, lint, types, and targeted tests run successfully.

## Progress
- [x] Session initialized
- [ ] Tasks created
- [ ] Implementation complete
