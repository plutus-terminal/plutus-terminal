---
source: Official docs
library: pytest
package: pytest
topic: poetry-unittest-async
fetched: 2026-03-08T00:00:00Z
official_docs: https://docs.pytest.org/en/stable/how-to/unittest.html
---

# Pytest docs relevant to this repository

## Running existing unittest-based tests

- Pytest supports running Python `unittest`-based tests out of the box.
- Pytest automatically collects `unittest.TestCase` subclasses and their `test` methods in `test_*.py` or `*_test.py` files.
- Supported unittest features include `setUp`, `tearDown`, `setUpClass`, `tearDownClass`, module fixtures, skips, and `subTest()`.
- In `unittest.TestCase` subclasses, normal pytest fixtures do not work directly except for `autouse` fixtures and `@pytest.mark.usefixtures(...)` patterns.
- Parametrization does not work inside `unittest.TestCase` subclasses.

Source: https://docs.pytest.org/en/stable/how-to/unittest.html

## Async tests and `unittest.IsolatedAsyncioTestCase`

- `pytest-asyncio` is a pytest plugin for coroutine test functions.
- The plugin docs say standard `unittest` subclasses are not supported by the plugin and advise users to use `unittest.IsolatedAsyncioTestCase` for unittest-style async tests.
- For a suite that already uses `unittest.IsolatedAsyncioTestCase`, pytest can be used as the runner without adding `pytest-asyncio` just to execute those tests.

Source: https://pytest-asyncio.readthedocs.io/en/latest/

## Poetry add command

- Poetry's `add` command adds packages to `pyproject.toml` and installs them.
- `--dev` / `-D` adds the package as a development dependency and is a shortcut for `-G dev`.
- Standard command for this repo: `poetry add --dev pytest`

Source: https://python-poetry.org/docs/cli/#add

## Minimal pytest configuration

- Pytest supports configuration in `pyproject.toml` via `[tool.pytest.ini_options]`.
- A minimal config can set `minversion`, `testpaths`, and optional `addopts`.
- `testpaths = ["tests"]` is a good fit when tests live under `tests/`.
- Register custom markers only if the repository starts using pytest markers.
- Pytest recommends enabling stricter marker checking with `--strict-markers` when custom markers are used.

Useful references:

- https://docs.pytest.org/en/stable/reference/customize.html
- https://docs.pytest.org/en/stable/how-to/mark.html
- https://docs.pytest.org/en/stable/explanation/goodpractices.html
