<!-- Context: project-intelligence/decisions | Priority: high | Version: 1.1 | Updated: 2026-02-07 -->

# Decisions Log

**Purpose**: Track project-defining choices with rationale so future contributors understand why the system is shaped this way.
**Last Updated**: 2026-02-07

## Core Concept

Plutus Terminal decisions optimize for two outcomes: fast reaction to market-moving news and safe local user control. This log captures the trade-offs made to preserve those outcomes as the product evolves.

## Key Points

- Business impact is required for every major technical choice.
- Safety and trust constraints can override feature speed when risk is high.
- Runtime and architecture decisions are anchored in desktop/local-first behavior.
- Monetary precision (`Decimal`) is a non-negotiable correctness decision.
- Decisions are revisited when reliability, UX, or security signals degrade.

## Decision Index

| ID | Date | Decision | Status | Why It Matters |
|------|------|------|------|------|
| D-001 | 2024-07 | Local-first desktop architecture | accepted | Keeps users in control of credentials and execution context. |
| D-002 | 2024-07 | Python + PySide6 + qasync stack | accepted | Enables desktop UX with async exchange/news workflows. |
| D-003 | 2024-09 | SQLite + Peewee for local persistence | accepted | Stores user config/filter state with low operational overhead. |
| D-004 | 2024-09 | Password encryption/keyring boundary | accepted | Reduces credential exposure risk for real-money workflows. |
| D-005 | 2025-04 | Controller orchestration refactor | accepted | Improves separation of concerns and UI/exchange coordination. |
| D-006 | ongoing | Reliability over breadth for trading core | under-review | Feature expansion must not regress core news/filter/trade loops. |
| D-007 | 2025-04 | Contract-first exchange integration model | accepted | Enables consistent multi-exchange growth behind one interface. |

## Decision Details

### D-001: Local-First Desktop Architecture

- **Context**: Target users need direct control over keys and execution, with minimal trust in hosted middle layers.
- **Decision**: Run as a local desktop app with local persistence and user-side configuration.
- **Rationale**: Aligns product trust model with web3 self-custody expectations.
- **Impact**: Better trust posture; trade-off is platform-specific desktop complexity.

### D-002: Python + PySide6 + qasync

- **Context**: App must combine responsive GUI behavior with concurrent network/news operations.
- **Decision**: Use PySide6 for UI and `qasync` for async integration.
- **Rationale**: Supports event-driven UI and async tasks in a single application model.
- **Impact**: Strong desktop ergonomics; trade-off is tighter coupling to Qt ecosystem.

### D-003: SQLite + Peewee Local State

- **Context**: Users need durable settings, filters, and account-linked preferences without external services.
- **Decision**: Persist local state with SQLite via Peewee models.
- **Rationale**: Simple deployment model and reliable local data access.
- **Impact**: Low ops burden; trade-off is limited multi-device sync by design.

### D-004: Credential Safety Boundary

- **Context**: Real-money trading risks make secret handling a critical trust requirement.
- **Decision**: Keep sensitive credential handling behind password guard/keyring pathways; avoid secret logging.
- **Rationale**: Reduces accidental exposure and aligns with security requirements.
- **Impact**: Higher user trust; trade-off is stricter integration constraints for new features.

### D-005: Controller-Centric Orchestration

- **Context**: UI, exchange, and news responsibilities needed clearer boundaries to improve maintainability.
- **Decision**: Introduce/refine `UIController` and `PlutusController` orchestration model.
- **Rationale**: Improves composability and reduces ad-hoc coupling.
- **Impact**: Better maintainability and testability; trade-off is extra abstraction discipline.

### D-007: Contract-First Exchange Integration

- **Context**: Exchange-specific implementations grew while UI/controller flows needed a stable integration surface.
- **Decision**: Standardize integration around `ExchangeBase` plus fetcher/trader protocols.
- **Rationale**: Preserves behavior consistency across exchanges and reduces coupling in UI layers.
- **Impact**: Easier extension path for new exchanges; trade-off is stricter implementation requirements.

## Quick Example

```text
Business goal: "React faster to breaking news with fewer errors."
Decision: async news pipeline + controller orchestration.
Guardrail: keep credential safety boundary and Decimal monetary logic.
Result: speed improvements without dropping trust/correctness baselines.
```

## Reference

- Release history: `CHANGELOG.md`
- Product context: `business-domain.md`
- Technical context: `technical-domain.md`

## 📂 Codebase References

- `CHANGELOG.md`: chronology of architectural and feature decisions.
- `pyproject.toml`: runtime/tooling decisions (Python 3.12, PySide6, qasync, Ruff, mypy).
- `plutus_terminal/controller/ui_controller.py`: controller orchestration decision evidence.
- `plutus_terminal/controller/plutus_controller.py`: composition boundaries and lifecycle flow.
- `plutus_terminal/core/exchange/base.py`: contract-first exchange abstraction decision evidence.
- `plutus_terminal/core/db/models.py`: local SQLite + Peewee persistence decision.
- `plutus_terminal/core/password_guard.py`: credential protection boundary decision.

## Related Files

- `business-domain.md`
- `technical-domain.md`
- `business-tech-bridge.md`
- `living-notes.md`
