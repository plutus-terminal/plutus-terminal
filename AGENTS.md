# AGENTS.md

Guidance for autonomous coding agents working in `plutus-terminal`.

## Project Snapshot

- Language: Python 3.12 only (`>=3.12,<3.13`).
- Packaging: Poetry (`pyproject.toml`, `poetry.lock`).
- App type: PySide6 desktop app with async/event-loop integration via `qasync`.
- Main package: `plutus_terminal/`.
- Entry point: `plutus_terminal.run:run` (CLI command `plutus-terminal`).
- Lint/format: Ruff + Ruff formatter.
- Type checking: mypy (configured via dependency + overrides in `pyproject.toml`).
- Pre-commit: enabled (`.pre-commit-config.yaml`).

## Environment Setup

1. Install Poetry (if missing): `pipx install poetry`.
2. Install deps: `poetry install`.
3. Activate shell (optional): `poetry shell`.
4. Run commands using `poetry run ...` to ensure virtualenv consistency.

## Build / Run Commands

- Install dependencies: `poetry install`
- Run app: `poetry run plutus-terminal`
- Alternate run: `poetry run python -m plutus_terminal.run`
- Build package artifact: `poetry build`
- Check package version: `poetry version -s`

## Lint / Format Commands

- Lint only: `poetry run ruff check .`
- Lint and auto-fix: `poetry run ruff check . --fix`
- Format code: `poetry run ruff format .`
- Run all pre-commit hooks: `poetry run pre-commit run --all-files`

## Type Checking Commands

- Run mypy on package: `poetry run mypy plutus_terminal`
- If mypy complains about missing stubs, sync deps with: `poetry install`

## Test Commands

Current state: repository has `tests/__init__.py` only (no committed test modules yet).

When tests are added, use:

- Run all tests: `poetry run pytest`
- Run a file: `poetry run pytest tests/path/test_file.py`
- Run a single test: `poetry run pytest tests/path/test_file.py::test_name`
- Run single parametrized case: `poetry run pytest tests/path/test_file.py::test_name[param]`
- Run by keyword: `poetry run pytest -k "keyword"`
- Stop early on first failure: `poetry run pytest -x`
- Quiet output: `poetry run pytest -q`

If `pytest` is not installed in the active environment, add it to dev deps first.

## CI / Release Notes Relevant to Agents

- GitHub workflow in `.github/workflows/release.yml` builds and publishes on pushes to `main`/`unstable`.
- Workflow installs via `poetry install` and publishes with `poetry publish --build`.
- PyApp binaries are also produced for Linux/Windows in release workflow.
- Do not alter release automation unless task explicitly requires it.

## Required Style Rules (from tooling)

- Line length target: 100.
- Ruff lint is strict (`extend-select = ["ALL"]`) with explicit ignores in `pyproject.toml`.
- Ruff pydocstyle convention: Google-style docstrings.
- Ruff isort behavior:
  - `combine-as-imports = true`
  - `force-wrap-aliases = true`
  - `force-sort-within-sections = true`
- Per-file lint exceptions exist (notably `plutus_terminal/ui/resources.py` is ignored).

## Code Organization Conventions

- Keep domain logic under `plutus_terminal/core/`.
- Keep UI widgets under `plutus_terminal/ui/widgets/`.
- Controllers orchestrate UI/core interactions in `plutus_terminal/controller/`.
- Use `MessageBus` signals for cross-component communication instead of ad-hoc coupling.
- Prefer extending existing service/manager classes over introducing parallel abstractions.

## Import Conventions

- Prefer absolute imports rooted at `plutus_terminal`.
- Use `TYPE_CHECKING` blocks for type-only imports to avoid runtime cycles.
- Keep imports grouped and sorted by Ruff/isort (stdlib, third-party, local).
- Avoid wildcard imports.

## Typing Conventions

- Use modern Python typing syntax (`X | Y`, `list[str]`, `dict[str, Any]`).
- Add explicit annotations for public functions/methods.
- Use `Self` where appropriate for class constructors/factories.
- Use Protocols/ABCs for interface contracts (already used in exchange layer).
- Use dataclasses with `frozen=True, slots=True` for immutable message payloads when suitable.

## Naming Conventions

- Modules/functions/variables: `snake_case`.
- Classes/enums: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE` (e.g., `LOGGER`, class-level defaults).
- Internal/private attributes: prefix with `_`.
- Qt signals: descriptive names with `_changed`/action semantics.

## Async / Concurrency Conventions

- Use async methods for network/exchange operations.
- For Qt-triggered async handlers, use `@asyncSlot()`.
- Track long-running tasks and cancel them during shutdown (`stop_async`).
- Avoid blocking calls in UI paths unless intentionally wrapped/controlled.

## Error Handling Conventions

- Raise specific domain exceptions (e.g., `TransactionFailedError`, `InvalidOrderSizeError`).
- Catch specific exceptions at integration boundaries and emit user-facing messages.
- Route user-visible status/errors through `UserMessage` + `MessageBus.send_message`.
- Avoid silent `except` blocks; include actionable context in messages/logs.
- Prefer validation before side effects (e.g., leverage/order-size checks).

## Logging Conventions

- Define module logger as `LOGGER = logging.getLogger(__name__)`.
- Use structured log messages with context instead of print statements.
- Keep noisy logs at debug level unless they indicate user-impacting events.

## Data / Precision Conventions

- Use `Decimal` for monetary values and trading size calculations.
- Avoid float arithmetic for balances, order sizes, pnl, and fees.
- Keep serialization/deserialization consistent with `orjson` where already used.

## Agent Change Checklist

Before finishing a change, agents should:

1. Run formatter: `poetry run ruff format .`
2. Run lint: `poetry run ruff check .`
3. Run types where relevant: `poetry run mypy plutus_terminal`
4. Run targeted tests (or add tests if behavior changed materially).
5. Update docs/config comments when behavior or workflow changes.

## Cursor / Copilot Rule Files

Checked paths:

- `.cursor/rules/`
- `.cursorrules`
- `.github/copilot-instructions.md`

Result at time of writing: none of these rule files are present in this repository.

If any are later added, treat them as higher-priority repository instructions and update this file.
