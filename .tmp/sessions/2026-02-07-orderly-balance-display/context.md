# Task Context: Fix Orderly Available Balance Display

Session ID: 2026-02-07-orderly-balance-display
Created: 2026-02-07T00:00:00Z
Status: in_progress

## Current Request
The current balance displayed on orderly is incorrect.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/code-analysis.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/project-intelligence/decisions-log.md
- .opencode/context/project-intelligence/business-tech-bridge.md
- .opencode/context/core/standards/test-coverage.md

## Reference Files (Source Material to Look At)
- plutus_terminal/core/exchange/orderly/fetcher.py
- plutus_terminal/core/exchange/orderly/ws_topics.py
- plutus_terminal/ui/widgets/account_info.py
- plutus_terminal/message_bus.py

## External Docs Fetched
- Orderly REST `/v1/client/holding`: uses `holding` (total), `frozen`, `pending_short`.
- Orderly private websocket `balance` topic: uses `data.balances.<TOKEN>` map with `holding`, `frozen`, `pendingShortQty` and related fields.
- Orderly private websocket `account` topic: account details only, not token balances.
- Local reference: `.tmp/external-context/orderly-network/balance-fields-rest-holding-ws-balance-account.md`

## Components
- Balance value extraction from REST holding payload
- Balance value extraction from websocket balance event payload
- Consistent available-balance calculation and UI signal emission

## Constraints
- Use `Decimal` for all monetary calculations.
- Keep compatibility with snake_case REST and camelCase websocket fields.
- Avoid broad refactors; fix should stay localized and low-risk.

## Exit Criteria
- [ ] Orderly available balance derives from available funds (not raw holding total).
- [ ] Websocket balance updates are parsed correctly for documented payload shape.
- [ ] Existing UI receives corrected value via `MessageBus.balance_fetched`.
