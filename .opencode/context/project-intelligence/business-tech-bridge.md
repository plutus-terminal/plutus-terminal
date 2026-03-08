<!-- Context: project-intelligence/bridge | Priority: high | Version: 1.1 | Updated: 2026-02-07 -->

# Business <-> Tech Bridge

**Purpose**: Map business outcomes in Plutus Terminal to concrete technical implementation choices.
**Last Updated**: 2026-02-07

## Core Concept

Plutus Terminal delivers business value only when real-time news signals convert into safe, fast trading actions. Technical design decisions are therefore judged by two outcomes: reaction speed and user trust. This bridge keeps both domains aligned.

## Key Points

- News-to-action latency is a business metric, not only a technical metric.
- Local-first credential handling is a trust and adoption requirement.
- Filter accuracy and reliability directly impact retention and user confidence.
- `Decimal`-based monetary logic protects users from precision-related trading errors.
- Controller and message-bus architecture exists to preserve responsive UX under async workloads.

## Core Mapping

| Business Need | Technical Solution | Why This Mapping | Business Value |
|------|------|------|------|
| React immediately to market-moving news | Async news ingestion + event pipeline (`NewsManager`, Qt signals, async slots) | Reduces decision and action delay in critical moments | Faster execution opportunities and better user outcomes |
| Keep users in control of keys and secrets | Password guard + OS keyring boundary | Removes custody risk from central services | Higher trust and stronger local-first positioning |
| Scale to more exchanges without breaking UX | Contract-first exchange abstraction (`ExchangeBase` + fetcher/trader protocols) | Keeps integrations consistent behind one interface | Faster expansion with lower regression risk |
| Avoid costly execution mistakes | Validation, typed models, and `Decimal` monetary handling | Limits precision and input-related failures | Reduced risk of user-loss events |
| Keep workflows configurable for advanced users | Persisted filters/settings with local DB models | Supports user-specific strategy tuning | Better retention for power users |

## Feature Mapping Examples

### Feature: Real-Time News to Trade Action

- **Business context**: Users need to turn breaking news into actionable trades quickly.
- **Technical implementation**: `NewsManager` ingests sources and emits processed items; controller layer updates UI and exchange interactions asynchronously.
- **Connection**: Without this pipeline, users context-switch across tools and lose timing edge.

### Feature: Local Credential Safety

- **Business context**: Users require confidence that private credentials remain under their control.
- **Technical implementation**: Sensitive values are guarded through password/keyring components rather than plain storage or logs.
- **Connection**: Trust collapses if credential safety is weak, regardless of feature richness.

### Feature: Precision-Safe Trading Calculations

- **Business context**: Small calculation errors can become direct financial losses.
- **Technical implementation**: Monetary operations use `Decimal`; strict coding standards enforce safer data handling.
- **Connection**: Precision integrity supports safer execution and long-term credibility.

## Trade-Off Decisions

| Situation | Business Priority | Technical Priority | Decision Made | Rationale |
|------|------|------|------|------|
| Speed vs safety checks | Fast action | Strong validation | Keep validation at boundaries while preserving async flow | Prevents bad orders without collapsing UX responsiveness |
| Feature breadth vs reliability | More exchanges/features | Stable core loops | Prioritize reliability in news/filter/trade core | Core trust is prerequisite for expansion |
| Rich persistence vs privacy | More stored context | Minimize sensitive footprint | Store only necessary local state, keep secrets guarded | Balances convenience with security posture |

## Quick Example

```text
Business request: "Faster reaction to breaking news."
-> Technical change: optimize async news pipeline + UI signaling path.
Business request: "Safer account handling."
-> Technical change: enforce keyring/password guard boundary and no-secret logging.
Business request: "Fewer execution mistakes."
-> Technical change: keep Decimal-only monetary calculations and validation rules.
```

## Reference

- Business context: `business-domain.md`
- Technical context: `technical-domain.md`

## 📂 Codebase References

- `plutus_terminal/core/news/news_manager.py`: real-time ingestion and processing pipeline.
- `plutus_terminal/controller/ui_controller.py`: async UI orchestration and exchange switching.
- `plutus_terminal/controller/plutus_controller.py`: top-level controller composition.
- `plutus_terminal/core/exchange/base.py`: exchange abstraction boundary used by controllers/widgets and implementations.
- `plutus_terminal/core/password_guard.py`: credential protection boundary.
- `plutus_terminal/core/db/models.py`: persisted settings/filter models for user workflows.
- `pyproject.toml`: runtime/tooling constraints enforcing quality baseline.

## Related Files

- `business-domain.md`
- `technical-domain.md`
- `decisions-log.md`
- `living-notes.md`
