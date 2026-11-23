# ADR-002: asyncio.Semaphore for Rate Limiting

## Status
Accepted

## Context
The original implementation scraped pages sequentially (one at a time). For a matrix of 100 keywords × 3 pages × 5 regions = 1500 pages @ 5s each = 125 minutes.

Playwright's async API enables concurrent page scraping, but unbounded parallelism would:
- Overwhelm the target site (triggering rate limits / blocks)
- Exhaust local resources (memory, file descriptors)

## Decision
Use **`asyncio.Semaphore(max_concurrent)`** to limit concurrent page scraping.

## Rationale
- **Controlled concurrency**: Semaphore enforces max N tasks executing simultaneously
- **House pattern**: `asyncio.gather() + Semaphore` is the standard from adaptive-fetch
- **Backpressure**: Tasks queue when semaphore is full, preventing runaway resource usage

## Consequences
**Positive**:
- 5-10x speedup over sequential (8 concurrent pages @ 5s each → 1500 pages in ~16 minutes)
- Tunable: `SH_MAX_CONCURRENT` env var adjusts limit
- Resource-safe: Bounded memory/network usage

**Negative**:
- Slightly more complex than `await asyncio.gather(*tasks)` (add `async with sem:`)
- Doesn't handle per-target rate limiting (would need token bucket or leaky bucket for finer control)

**Alternative considered**: Sequential (no semaphore). Rejected due to unacceptable duration for large datasets.

## Implementation
```python
sem = asyncio.Semaphore(settings.max_concurrent)

async def scrape_keyword(...):
    async with sem:
        page = await context.new_page()
        # ... scraping logic ...

tasks = [scrape_keyword(...) for ... in keywords]
await asyncio.gather(*tasks)
```

Default: `max_concurrent=8` (empirically chosen balance between speed and politeness).
