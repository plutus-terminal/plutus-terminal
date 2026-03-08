---
source: Context7 API + HTTPX official docs
library: HTTPX
package: httpx
topic: async client timeout handling and startup retry/degradation
tech_stack: Python async app startup
fetched: 2026-02-07T00:00:00Z
official_docs: https://www.python-httpx.org/advanced/timeouts/
---

# HTTPX async timeout handling (relevant excerpts)

- HTTPX enforces timeouts by default and raises `TimeoutException` after 5 seconds of network inactivity.
- Timeout configuration can be per request (`timeout=...`) or client default (`AsyncClient(timeout=...)`).
- Fine-grained timeouts are available with `httpx.Timeout(connect=..., read=..., write=..., pool=...)`.
- `ConnectTimeout` is raised when connection establishment exceeds the connect timeout.

```python
import asyncio
import random
import httpx

STARTUP_TIMEOUT = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=2.0)


async def fetch_bootstrap(url: str) -> dict:
    async with httpx.AsyncClient(timeout=STARTUP_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def fetch_with_backoff(url: str, retries: int = 4, base_delay: float = 0.25) -> dict | None:
    for attempt in range(retries):
        try:
            return await fetch_bootstrap(url)
        except httpx.ConnectTimeout:
            # Fast-fail network path not ready yet.
            pass
        except httpx.TimeoutException:
            # Read/write/pool timeout.
            pass
        except httpx.RequestError:
            # DNS, connection reset, protocol, etc.
            pass

        if attempt < retries - 1:
            jitter = random.uniform(0, base_delay)
            await asyncio.sleep((base_delay * (2**attempt)) + jitter)

    # Graceful degradation path for startup
    return None
```

Practical startup behavior:
- Keep connect timeout short at startup (2-3s) to avoid boot hangs.
- Retry only transient failures (`ConnectTimeout`, `TimeoutException`, `RequestError`).
- Cap retries and switch to degraded mode (`None`, cached config, disabled remote-dependent features).
- Log exception type and endpoint for diagnostics.
