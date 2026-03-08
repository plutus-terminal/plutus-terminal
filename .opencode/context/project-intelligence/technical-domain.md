<!-- Context: project-intelligence/technical | Priority: critical | Version: 1.2 | Updated: 2026-02-08 -->

# Technical Domain

**Purpose**: Define the technical stack and coding patterns agents must preserve when implementing this project.
**Last Updated**: 2026-02-08

## Core Concept

Plutus Terminal is a Python 3.12 desktop application using PySide6 with `qasync` for async Qt integration. The architecture centers on controller orchestration and message-driven UI updates. Precision and safety rules are strict for trading and monetary data.

## Key Points

- Python-only codebase (`>=3.12,<3.13`) with Poetry-managed dependencies.
- UI orchestration uses controller classes and Qt signals (`Signal`, `@asyncSlot`).
- Exchange integrations follow shared contracts in `core/exchange/base.py`.
- Database layer is local SQLite with Peewee ORM models and snake_case fields.
- Tooling baseline: Ruff (lint + format), mypy, pytest, pre-commit.
- Monetary logic must use `Decimal` (no float arithmetic for balances, pnl, sizing, fees).

## Primary Stack

| Layer | Technology | Version | Rationale |
|------|------|------|------|
| Language | Python | 3.12+ | Required runtime and typing model for the project.
| UI Framework | PySide6 + qasync | 6.9.0 + 0.27.1 | Qt desktop UI with async event-loop integration.
| Database | SQLite + Peewee | Local file + 3.17.9 | Lightweight local persistence with typed model layer.
| Quality Tooling | Ruff + mypy + pytest | 0.11.6 + 1.15.0 + project env | Enforces style, typing, and behavior checks.
| Packaging | Poetry | lockfile-managed | Reproducible dependency and build workflow.

## Code Patterns

### API Endpoint Pattern

No HTTP API endpoint pattern is currently primary in this project. Prefer message bus and controller interactions for internal flows.

### Component Pattern

```python
class UIController(QObject):
    exchange_changed = Signal()

    @asyncSlot()
    async def change_current_exchange(self) -> None:
        await self.current_exchange.stop_async()
        self.current_exchange = await VALID_EXCHANGES[name].create(...)
        self.exchange_changed.emit()
```

## Naming Conventions

| Type | Convention | Example |
|------|------|------|
| Files | `snake_case.py` | `news_manager.py`, `ui_controller.py` |
| Classes | `PascalCase` | `NewsManager`, `UIController`, `PlutusController` |
| Functions/Methods | `snake_case` | `fetch_news`, `process_news`, `change_current_pair` |
| Constants | `UPPER_SNAKE_CASE` | `LOGGER`, `_SEEN_CACHE_MAX` |
| Database Fields | `snake_case` | `exchange_name`, `trade_value_low`, `rpc_urls` |

## Code Standards

- Run Ruff formatter and Ruff lint; line length target is 100.
- Keep Google-style docstrings where docstrings are present.
- Use explicit typing for public interfaces and async boundaries.
- Prefer absolute imports from `plutus_terminal`.
- Use `@asyncSlot()` for Qt-triggered async handlers.

## Security Requirements

- Never log secrets or credentials.
- Store sensitive credentials only via keyring/password guard.
- Encrypt sensitive local data when applicable.
- Always use `Decimal` for monetary values and trade calculations.

## Quick Example

```python
from decimal import Decimal

order_value = Decimal("250")
entry_price = Decimal("43210.5")
size = order_value / entry_price
assert size > Decimal("0")
```

## Reference

- Project guide: `AGENTS.md`
- Stack and tooling config: `pyproject.toml`
- Orderly trade intro: `https://orderly.network/docs/introduction/trade-on-orderly/`
- Orderly perp formulas and definitions: `https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/formulas-definitions`
- Orderly margin, leverage, and PnL: `https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/margin-leverage-and-pnl`
- Orderly mark/index/last price: `https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/mark-price-index-price-and-last-price`
- Orderly orders and price limits: `https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/orders-price-limits`
- Orderly funding rate: `https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/funding-rate`
- Orderly liquidations: `https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/liquidations`
- Orderly insurance fund and ADL: `https://orderly.network/docs/introduction/trade-on-orderly/perpetual-futures/insurance-fund-and-adl`

## 📂 Codebase References

- `pyproject.toml`: Python version, dependencies, Ruff/mypy settings.
- `plutus_terminal/controller/ui_controller.py`: Qt signal + `@asyncSlot` controller orchestration.
- `plutus_terminal/controller/plutus_controller.py`: top-level composition of UI controller and main window.
- `plutus_terminal/core/exchange/base.py`: exchange contract layer (`ExchangeBase`, `ExchangeFetcher`, `ExchangeTrader`).
- `plutus_terminal/core/news/news_manager.py`: naming and async service patterns.
- `plutus_terminal/core/db/models.py`: SQLite + Peewee model conventions.

## Related Files

- `business-domain.md`
- `business-tech-bridge.md`
- `decisions-log.md`
