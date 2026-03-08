# Orderly Runtime Coverage Gaps

Context standards require behavior-first, deterministic coverage with happy, edge, and error cases (`.opencode/context/core/standards/test-coverage.md:25`, `.opencode/context/core/standards/test-coverage.md:48`, `.tmp/external-context/orderly-network/orderly-native-integration-test-surface.md:115`). Existing Orderly tests cover fetcher parsing, selected websocket ack paths, and trader payload builders, but not the main runtime orchestration surfaces in `plutus_terminal/core/exchange/orderly/markets.py`, `plutus_terminal/core/exchange/orderly/constraints.py`, `plutus_terminal/core/exchange/orderly/fetcher.py`, `plutus_terminal/core/exchange/orderly/websocket.py`, and `plutus_terminal/core/exchange/orderly/exchange.py`.

## Gap List By Module

### Markets
- Covered now: none directly; current tests only consume fallback registry data from `tests/orderly/test_orderly_fetcher_parser_parity.py:29` and `tests/orderly/test_orderly_trader_builder_parity.py:22`.
- Gap: `OrderlyMarketRegistry.refresh()` is untested for filtering non-PERP rows and replacing stale rule maps from `/v1/public/info` (`plutus_terminal/core/exchange/orderly/markets.py:57`).
- Gap: dynamic rule parsing misses coverage for defaulted fields and per-symbol leverage extraction in `_build_market_rule()` / `_extract_max_leverage()` (`plutus_terminal/core/exchange/orderly/markets.py:116`, `plutus_terminal/core/exchange/orderly/markets.py:126`).
- Gap: fallback bootstrap behavior is only exercised indirectly; no test proves `load_fallback_symbols()` ignores non-PERP entries and leaves prior state intact when nothing valid is supplied (`plutus_terminal/core/exchange/orderly/markets.py:79`).

### Constraints
- Covered now: only indirectly through trader builder quantity normalization (`tests/orderly/test_orderly_trader_builder_parity.py:123`).
- Gap: no direct positive/negative tests for `quantize_price()` and `quantize_base_size()` step rounding (`plutus_terminal/core/exchange/orderly/constraints.py:14`, `plutus_terminal/core/exchange/orderly/constraints.py:19`).
- Gap: `validate_order_size()` lacks failure coverage for non-positive size, below-min size, above-max size, and below-min-notional (`plutus_terminal/core/exchange/orderly/constraints.py:24`).
- Likely mismatch to pin: external surface expects dynamic server rule enforcement including price-range checks; current local constraints only enforce base min/max and min notional, not quote bounds, tick alignment validation, or mark-price range checks (`.tmp/external-context/orderly-network/orderly-native-integration-test-surface.md:85`, `plutus_terminal/core/exchange/orderly/constraints.py:24`).

### Trader Lifecycle
- Covered now: regular create, paired TP/SL create, and single-child reduce TP/SL payloads (`tests/orderly/test_orderly_trader_builder_parity.py:54`, `tests/orderly/test_orderly_trader_builder_parity.py:123`).
- Gap: `_submit_order_request()` has no direct lifecycle coverage for stop orders routing to `/v1/algo/order` vs regular orders routing to `/v1/order` (`plutus_terminal/core/exchange/orderly/trader.py:137`).
- Gap: `cancel_order()` and `edit_order()` are untested, including regular-vs-algo cancel path selection and current edit behavior of cancel-then-create instead of native `PUT /v1/order` (`plutus_terminal/core/exchange/orderly/trader.py:93`, `plutus_terminal/core/exchange/orderly/trader.py:113`).
- Gap: no runtime assertion preserves protocol status markers like `CANCEL_SENT` / `EDIT_SENT`, which the external surface calls out as important response semantics (`.tmp/external-context/orderly-network/orderly-native-integration-test-surface.md:27`, `.tmp/external-context/orderly-network/orderly-native-integration-test-surface.md:28`).
- Likely mismatch: official behavior exposes native edit via `PUT /v1/order`, while current implementation replaces by cancel+create; that is a code-level divergence worth isolating before any behavior change (`.tmp/external-context/orderly-network/orderly-native-integration-test-surface.md:27`, `plutus_terminal/core/exchange/orderly/trader.py:113`).

### Fetcher Runtime
- Covered now: parsing of orders/positions plus one unsubscribe and one public-loop idle case (`tests/orderly/test_orderly_fetcher_parser_parity.py:72`, `tests/orderly/test_orderly_fetcher_parser_parity.py:171`, `tests/orderly/test_orderly_fetcher_parser_parity.py:185`).
- Gap: start-up sequencing is untested: `start()` must ensure connections, subscribe private topics, refresh account config, and create exactly one consumer task (`plutus_terminal/core/exchange/orderly/fetcher.py:156`).
- Gap: chart-history runtime behavior is untested for duplicate in-flight coalescing, local pacing, 429 cooldown propagation, Retry-After parsing, and timestamp normalization (`plutus_terminal/core/exchange/orderly/fetcher.py:219`, `plutus_terminal/core/exchange/orderly/fetcher.py:281`, `plutus_terminal/core/exchange/orderly/fetcher.py:293`, `plutus_terminal/core/exchange/orderly/fetcher.py:761`).
- Gap: public reconnect flow is untested for `receive_subscribed_prices()` reconnecting and resubscribing after unexpected errors (`plutus_terminal/core/exchange/orderly/fetcher.py:343`).
- Gap: private event handling is untested for balance, positions, and execution/order topics triggering cache refreshes and message-bus emissions (`plutus_terminal/core/exchange/orderly/fetcher.py:570`).
- Likely mismatch: `_is_open_algo_row()` hides statuses listed in `_TERMINAL_ORDER_STATUSES`, but no test pins protocol markers like `TRIGGERED` / `DEACTIVATED` / `FAILED` against external execution-report semantics (`plutus_terminal/core/exchange/orderly/fetcher.py:62`, `plutus_terminal/core/exchange/orderly/fetcher.py:1183`, `.tmp/external-context/orderly-network/orderly-native-integration-test-surface.md:81`).

### Websocket Runtime
- Covered now: subscribe/unsubscribe ack handling, buffering one push event before subscribe ack, and topic list parity (`tests/orderly/test_orderly_websocket_parity.py:54`, `tests/orderly/test_orderly_websocket_parity.py:94`, `tests/orderly/test_orderly_websocket_parity.py:149`).
- Gap: `connect_private()` auth sequencing is not tested end-to-end; it should authenticate before replaying private topics on reconnect (`plutus_terminal/core/exchange/orderly/websocket.py:97`, `plutus_terminal/core/exchange/orderly/websocket.py:257`).
- Gap: heartbeat handling is only implicit; no test proves `_normalize_event()` answers server `ping` with `pong` and suppresses the heartbeat frame from consumers (`plutus_terminal/core/exchange/orderly/websocket.py:398`).
- Gap: reconnect restoration is partial in current tests; there is no explicit coverage that stored topics are resubscribed after `connect_public()` / `connect_private()` recreate sockets (`plutus_terminal/core/exchange/orderly/websocket.py:74`, `plutus_terminal/core/exchange/orderly/websocket.py:97`).
- Gap: ack validation lacks direct negative tests for missing `success`, mismatched `id`, and unsolicited failed acks being buffered vs logged (`plutus_terminal/core/exchange/orderly/websocket.py:353`, `plutus_terminal/core/exchange/orderly/websocket.py:445`).
- Likely mismatch: external docs prioritize auth-before-subscribe and reconnect-with-resubscribe semantics; current parity tests do not yet prove those race boundaries (`.tmp/external-context/orderly-network/orderly-native-integration-test-surface.md:66`, `.tmp/external-context/orderly-network/orderly-native-integration-test-surface.md:78`).

### Exchange Orchestration
- Covered now: none directly.
- Gap: `init_async()` is untested for retrying market bootstrap, falling back to default symbols on transient failures, wiring fetcher/trader/ws dependencies, and deriving max leverage from account info (`plutus_terminal/core/exchange/orderly/exchange.py:113`, `plutus_terminal/core/exchange/orderly/exchange.py:145`, `plutus_terminal/core/exchange/orderly/exchange.py:450`).
- Gap: UI-facing methods `create_order()`, `edit_order()`, `create_reduce_order()`, `cancel_order()`, and `close_position()` are untested for message-bus side effects, snapshot refreshes, and `TransactionFailedError` to `UserMessage` mapping (`plutus_terminal/core/exchange/orderly/exchange.py:252`, `plutus_terminal/core/exchange/orderly/exchange.py:309`, `plutus_terminal/core/exchange/orderly/exchange.py:343`, `plutus_terminal/core/exchange/orderly/exchange.py:379`, `plutus_terminal/core/exchange/orderly/exchange.py:403`).
- Gap: leverage handling is untested for pair-level max clamping and persisted app-config updates (`plutus_terminal/core/exchange/orderly/exchange.py:237`, `plutus_terminal/core/exchange/orderly/exchange.py:247`).
- Gap: secret validation and key normalization are untested, including intentional `ed25519:` prefix preservation for the WebUI-token model (`plutus_terminal/core/exchange/orderly/exchange.py:552`, `plutus_terminal/core/exchange/orderly/exchange.py:569`).
- Likely mismatch: external guidance expects stable auth/rate-limit/server error classes, but `OrderlyExchange` mostly collapses trader failures into generic user-facing messages; no tests pin code-specific error mapping yet (`.tmp/external-context/orderly-network/orderly-native-integration-test-surface.md:96`, `plutus_terminal/core/exchange/orderly/exchange.py:295`).

## Isolated Test Targets For Later Subtasks

1. `tests/orderly/test_orderly_market_registry_runtime.py`
   - positive: refresh loads only PERP rows and replaces stale maps
   - negative: refresh skips malformed/non-dict/non-PERP rows; fallback load ignores invalid symbols

2. `tests/orderly/test_orderly_constraints_runtime.py`
   - positive: quantization rounds down to market ticks; valid size passes
   - negative: zero/below-min/above-max/below-notional sizes raise `InvalidOrderSizeError`

3. `tests/orderly/test_orderly_trader_lifecycle_runtime.py`
   - positive: stop orders route to `/v1/algo/order`; cancel uses correct regular/algo endpoint
   - negative: submit/cancel/edit exceptions wrap as `TransactionFailedError`; edit divergence from native `PUT` is documented

4. `tests/orderly/test_orderly_fetcher_runtime.py`
   - positive: start sequence, private-event cache updates, reconnect/resubscribe, history coalescing
   - negative: 429 cooldown, retry-after parsing, malformed topic/data payloads, terminal algo statuses filtered

5. `tests/orderly/test_orderly_websocket_runtime.py`
   - positive: private auth occurs before topic replay; ping receives pong; reconnect resubscribes stored topics
   - negative: failed auth/missing-success/mismatched-ack-id/timeouts raise protocol errors

6. `tests/orderly/test_orderly_exchange_runtime.py`
   - positive: init fallback bootstrap, leverage clamping, successful create/edit/cancel/close emit refreshes and info messages
   - negative: transaction failures emit error messages, invalid secrets reject, max leverage fallback stays stable on client-info failure

## Recommended Parallelization

- Parallel track A: market registry + constraints, because both are pure/deterministic and isolated from async wiring.
- Parallel track B: trader lifecycle + websocket runtime, because both use mocked protocol surfaces without UI/message-bus orchestration.
- Parallel track C: fetcher runtime + exchange orchestration after websocket target scaffolding exists, because both depend on async reconnect and event sequencing assumptions.
