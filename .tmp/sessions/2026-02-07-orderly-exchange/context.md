# Task Context: Orderly Exchange Integration

Session ID: 2026-02-07-orderly-exchange
Created: 2026-02-07T00:00:00Z
Status: in_progress

## Current Request
Add orderly.network as an exchange to plutus terminal. Use the foxify implementation as a guide. Follow orderly documentation as close as possible. Focus on speed and use websocket where possible. Fetch token list from orderly API instead of static mapping.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/security-patterns.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/project-intelligence/decisions-log.md
- .opencode/context/project-intelligence/business-tech-bridge.md
- .opencode/context/core/workflows/component-planning.md
- .opencode/context/core/workflows/external-libraries-workflow.md

## Reference Files (Source Material to Look At)
- pyproject.toml
- plutus_terminal/core/exchange/base.py
- plutus_terminal/core/exchange/valid_exchanges.py
- plutus_terminal/core/exchange/foxify/exchange.py
- plutus_terminal/core/exchange/foxify/fetcher.py
- plutus_terminal/core/exchange/foxify/trader.py
- plutus_terminal/core/keyring_manager.py
- plutus_terminal/controller/ui_controller.py

## External Docs Fetched
- Orderly main docs: https://orderly.network/docs/build-on-omnichain/building-on-omnichain
- EVM API intro/auth, REST private/public endpoints, and WebSocket pages for auth/topics/ping-pong.
- Consolidated implementation notes: .tmp/external-context/orderly-network/python-exchange-client-ws-first.md
- Doc source list: .tmp/external-context/orderly-network/source-links.md

## Components
- Orderly auth/signature module (REST + WS auth)
- Orderly REST client utilities
- Orderly websocket manager and subscriptions
- Orderly fetcher implementing ExchangeFetcher
- Orderly trader implementing ExchangeTrader
- Orderly exchange class implementing ExchangeBase
- Exchange registration and package exports

## Constraints
- Websocket-first for market/account updates; REST for snapshots and history/fallbacks.
- Fetch symbol/token list dynamically from Orderly API.
- Enforce Orderly precision and min notional constraints before order submit.
- Keep compatibility with existing `ExchangeBase` and UI flows.
- Do not log secrets.

## Exit Criteria
- [ ] `orderly` exchange is selectable in the app and initializes correctly.
- [ ] Available pairs are sourced from Orderly API, not static files.
- [ ] Live prices, positions, orders, and stable balance update through existing message bus signals.
- [ ] Create/edit/cancel/close order flows work through Orderly endpoints.
- [ ] Lint and type checks pass for modified files.
