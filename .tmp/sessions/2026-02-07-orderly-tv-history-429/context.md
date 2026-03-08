# Task Context: Reduce Orderly TV History 429s

Session ID: 2026-02-07-orderly-tv-history-429
Created: 2026-02-07T00:00:00Z
Status: in_progress

## Current Request
When opening the UI, Orderly `/v1/tv/history` returns 429 too many requests, likely from the amount of news that triggers price-history fetches. Improve this with exponential backoff and higher retry limit, and suggest other improvements.

## Context Files (Standards to Follow)
- .opencode/context/core/standards/code-quality.md
- .opencode/context/core/standards/test-coverage.md
- .opencode/context/project-intelligence/technical-domain.md
- .opencode/context/project-intelligence/living-notes.md
- .opencode/context/development/principles/api-design.md
- .opencode/context/core/workflows/external-libraries-workflow.md
- .opencode/context/project-intelligence/decisions-log.md
- .opencode/context/development/principles/clean-code.md
- .opencode/context/core/workflows/external-libraries-scenarios.md

## Reference Files (Source Material to Look At)
- plutus_terminal/core/exchange/orderly/fetcher.py
- plutus_terminal/ui/widgets/news_widget.py
- plutus_terminal/ui/widgets/news_list.py
- plutus_terminal/controller/ui_controller.py

## External Docs Fetched
- Orderly `/v1/tv/history` documented limit: 10 requests per second per IP.
- 429 maps to code `-1003` (Rate limit exceed).
- No guaranteed documented `Retry-After` header; use safe fallback backoff windows.
- Public websocket supports kline topics for live updates after backfill.

## Components
- Orderly history request retry policy (429-aware exponential backoff + jitter)
- Local request burst protection for history endpoint (pacing + duplicate suppression)
- News-triggered initial price lookups burst mitigation

## Constraints
- Preserve async Qt behavior and cancellation safety.
- Keep changes scoped and maintainable.
- Do not alter unrelated exchange behavior.

## Exit Criteria
- [ ] Opening UI no longer triggers frequent 429 storms for Orderly history requests.
- [ ] History requests use explicit 429-aware retry/backoff with increased retry attempts.
- [ ] Startup/news history requests are paced/coalesced to respect endpoint limits.
- [ ] Ruff checks pass for touched files.
