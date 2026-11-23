# ADR-001: Playwright Browser Contexts Instead of Tabs

## Status
Accepted

## Context
The original Selenium implementation used `window.open()` to create multiple tabs within a single browser window, then juggled `window_handles` and `switch_to.window(handle)` to navigate between them. Each tab represented a different marketplace/postcode configuration.

Playwright offers two primitives for managing multiple pages:
1. **Pages within one context**: Shared cookies/session state
2. **Multiple contexts**: Isolated cookies/session state per context

## Decision
Use **one browser context per marketplace**, with multiple pages within each context.

## Rationale
- **State isolation**: Each marketplace has different postcode/delivery settings. Contexts isolate this state cleanly.
- **Cleaner API**: No handle juggling. Pages are addressable objects: `page = await context.new_page()`
- **Parallel-ready**: Contexts naturally map to the semaphore pattern (one task per keyword × region × sort)

## Consequences
**Positive**:
- Eliminates `switch_to.window()` logic
- Each context's postcode setup runs once, pages inherit it
- Clear ownership: one context = one region

**Negative**:
- Slightly more memory (multiple browser contexts vs. one browser with tabs)
- Context creation overhead (~100ms per context)

**Alternative considered**: One context with N pages (all sharing state). Rejected because postcode leakage between regions would require defensive re-setup on every page.

## Implementation
```python
async with async_playwright() as p:
    browser = await p.firefox.launch()
    context = await browser.new_context()  # One per marketplace
    page1 = await context.new_page()
    page2 = await context.new_page()
```
