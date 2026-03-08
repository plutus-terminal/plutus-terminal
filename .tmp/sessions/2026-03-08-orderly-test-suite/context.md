# Task Context: Orderly Test Suite

Session ID: 2026-03-08-orderly-test-suite
Created: 2026-03-08T00:00:00Z
Status: in_progress

## Current Request
Write a full test suite for the Orderly implementation in plutus-terminal using the official Orderly JS SDK and Python EVM connector only as behavior references. Identify whether any code changes are needed to comply with the official expected behavior. Do not use the Python SDK in the current code.

User-approved constraint: auth/signing differences related to WebUI-generated API tokens are intentional and must be preserved. Do not change auth just to match the Python connector.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/core/standards/code-quality.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/core/workflows/task-delegation-basics.md
- AGENTS.md

## Reference Files (Source Material)
- plutus_terminal/core/exchange/orderly/auth.py
- plutus_terminal/core/exchange/orderly/rest_client.py
- plutus_terminal/core/exchange/orderly/markets.py
- plutus_terminal/core/exchange/orderly/constraints.py
- plutus_terminal/core/exchange/orderly/trader.py
- plutus_terminal/core/exchange/orderly/fetcher.py
- plutus_terminal/core/exchange/orderly/websocket.py
- plutus_terminal/core/exchange/orderly/exchange.py
- tests/orderly/test_orderly_trader_builder_parity.py
- tests/orderly/test_orderly_fetcher_parser_parity.py
- tests/orderly/test_orderly_websocket_parity.py

## External Context Fetched
- .tmp/external-context/orderly-network/orderly-native-integration-test-surface.md - Current Orderly API and SDK-derived behavior/test surface.

## Components
- Orderly auth helpers - REST and websocket signing/header helpers
- Orderly REST client - signed requests, query construction, error classification
- Orderly market registry - symbol metadata refresh and rule parsing
- Orderly constraints - price/size/notional validation
- Orderly trader - payload generation and lifecycle calls
- Orderly websocket manager - auth, subscriptions, ack handling, reconnect behavior
- Orderly exchange - orchestration, leverage, user-message handling, fetch refreshes

## Constraints
- Python 3.12 only.
- Use pytest/unittest style already present in tests/orderly.
- Preserve current WebUI-token auth model.
- Use the official JS SDK and Python EVM connector as references only.
- Prefer behavior tests over implementation-detail tests.

## Exit Criteria
- [ ] Missing Orderly modules have focused test coverage added under tests/orderly.
- [ ] Tests document and preserve intentional auth behavior differences.
- [ ] Any likely implementation gaps are identified clearly.
- [ ] Targeted Orderly tests are runnable.

## Progress
- [x] Context initialized
- [ ] Task breakdown created
- [ ] Test implementation complete
- [ ] Validation complete
