---
source: HTTPX official docs
library: HTTPX
package: httpx
topic: exception classes ConnectTimeout TimeoutException RequestError
tech_stack: Python async networking
fetched: 2026-02-07T00:00:00Z
official_docs: https://www.python-httpx.org/exceptions/
---

# HTTPX exception relationships (relevant excerpts)

Hierarchy slice from docs:

- `HTTPError`
  - `RequestError`
    - `TransportError`
      - `TimeoutException`
        - `ConnectTimeout`
        - `ReadTimeout`
        - `WriteTimeout`
        - `PoolTimeout`

Key meanings:

- `RequestError`: base class for exceptions while issuing a request.
- `TimeoutException`: base class for timeout errors.
- `ConnectTimeout`: timeout while connecting to host.

Handling strategy at startup:

```python
try:
    data = await client.get(url)
    data.raise_for_status()
except httpx.ConnectTimeout:
    # Network not reachable yet; retry with backoff.
    ...
except httpx.TimeoutException:
    # Any timeout class; retry if idempotent startup read.
    ...
except httpx.RequestError:
    # Other transport/request failures; degrade gracefully.
    ...
```

Guideline:
- Catch `ConnectTimeout` first for targeted behavior.
- Catch `TimeoutException` next for all timeout variants.
- Catch `RequestError` after that for broader transient request failures.
