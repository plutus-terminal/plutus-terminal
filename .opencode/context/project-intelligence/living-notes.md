<!-- Context: project-intelligence/notes | Priority: high | Version: 1.2 | Updated: 2026-02-07 -->

# Living Notes

**Purpose**: Track active debt, open questions, and practical guardrails that affect reliability and user trust right now.
**Last Updated**: 2026-02-07

## Core Concept

Plutus Terminal runs in a high-risk domain where reliability and safety directly affect real-money outcomes. This file captures current technical pressure points so they are visible and actionable.

## Key Points

- Trading-path correctness and safety checks are higher priority than feature breadth.
- Exchange integrations must stay contract-first (`ExchangeBase` + protocols).
- Monetary and position calculations should remain `Decimal`-first.
- Missing observability in async/filter paths increases debugging cost.
- Automated test coverage is currently a major quality gap.

## Technical Debt

| Item | Impact | Priority | Status | Mitigation |
|------|------|------|------|------|
| Foxify min order size still hardcoded | Can reject/accept wrong sizes if contract values diverge | high | acknowledged | Pull min size from on-chain/official source |
| Missing filter-key warning logs | Silent filter mismatches reduce operator confidence | medium | acknowledged | Add structured warnings in data filter path |
| Temporary F1 style reload hook in main window | Debug behavior can leak into production UX paths | low | deferred | Remove dev shortcut and helper |
| Near-zero automated tests | Regressions can slip into trading-critical flows | high | acknowledged | Add targeted tests for exchange/news/controller flows |

## Open Questions

| Question | Stakeholders | Status | Next Action |
|------|------|------|------|
| Should min order size be queried on startup per exchange? | exchange + controller maintainers | open | Define contract/source and cache strategy |
| Do we need a contract compliance test suite for `ExchangeBase` implementations? | maintainers | open | Add shared tests for required protocol behavior |
| Which reliability SLO should gate releases for trading core? | maintainers + release owners | open | Define release checklist metrics in CI/docs |

## Known Issues

| Issue | Severity | Workaround | Status |
|------|------|------|------|
| No committed behavior tests in `tests/` | high | Manual verification and lint/type checks | known |
| Filter key mismatch has no explicit warning log | medium | Inspect filter configs manually | known |

## Patterns Worth Preserving

- Controller orchestration with message bus boundaries (`UIController`, `PlutusController`).
- Exchange contract abstraction in `core/exchange/base.py` before concrete exchange wiring.
- Explicit error-to-user-message routing for trading actions.

## Maintainer Gotchas

- Any new exchange must satisfy `ExchangeBase`, `ExchangeFetcher`, and `ExchangeTrader` contracts first.
- Avoid float arithmetic in money/trade paths; use `Decimal` end-to-end.
- Async shutdown paths (`stop_async`) must cancel tasks cleanly to prevent stale loops.

## Quick Example

```text
Symptom: Order-size validation disagrees with exchange UI.
Likely source: hardcoded min size in exchange implementation.
Action: update exchange adapter to source limits dynamically.
Guardrail: keep validation in base contract path and report user-facing errors.
```

## Reference

- Reliability context: `decisions-log.md`
- Business impact context: `business-tech-bridge.md`

## 📂 Codebase References

- `plutus_terminal/core/exchange/base.py`: required abstraction for exchange integrations.
- `plutus_terminal/core/exchange/foxify/exchange.py`: TODO for contract-sourced `min_order_size`.
- `plutus_terminal/core/news/filter/_filters.py`: TODO for missing key warning logs.
- `plutus_terminal/ui/main_window.py`: temporary style reload shortcut marked for removal.
- `tests/__init__.py`: current test package state (no committed test modules).

## Related Files

- `business-domain.md`
- `technical-domain.md`
- `business-tech-bridge.md`
- `decisions-log.md`
