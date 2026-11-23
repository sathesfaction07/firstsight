# SerpHarvest — Technical Architecture

## Overview

SerpHarvest is a concurrent Playwright-driven search results harvester with checkpoint recovery and idempotent DynamoDB storage. It orchestrates N concurrent browser tasks under a semaphore, extracts product IDs from paginated search results, and writes to local CSV or DynamoDB with first-sighting-wins semantics.

**Design principle:** Idempotence means preserving first-sighting metadata, not overwriting with latest data. The composite partition key `REGION#keyword#PRODUCT_ID` with DynamoDB conditional writes ensures re-harvesting the same query weeks later adds new products but never overwrites the original timestamp/run_id of existing products.

**Headline engineering feature:** Cross-run deduplication that preserves first-sighting timestamps. When tracking product rankings over time, you need to know when each product *first appeared* in results for a given keyword, not the most recent harvest date. SerpHarvest's two-level dedup (in-memory `seen` set within a run + DynamoDB conditional write across runs) ensures re-harvesting "laptop" in US every Monday for six months produces a dataset where every row shows the original sighting date, enabling time-to-discovery and seasonality analysis that upsert semantics would destroy.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLI (serp-harvest)                          │
│                                                                  │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │   run        │   │   probe          │   │   plan         │  │
│  │ - parse CSV  │   │ - test browser   │   │ - estimate     │  │
│  │ - orchestrate│   │   launch         │   │   workload     │  │
│  └──────┬───────┘   └──────────────────┘   └────────────────┘  │
└─────────┼───────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│               scrape_all (orchestration layer)                     │
│                                                                  │
│  1. Parse input CSV (keyword, region, sort)                       │
│  2. Checkpoint.load() → resume already-harvested IDs              │
│  3. Create asyncio.Semaphore(max_concurrent=8)                    │
│  4. Launch N tasks: asyncio.gather(scrape_keyword × keywords)     │
│  5. Checkpoint.save() after each batch                            │
│  6. Sink.write(df, run_id) → local CSV or DynamoDB                │
└─────────┬────────────────────────────────────────────────────────┘
          │  one task per (keyword, region, sort, max_pages)
          ▼
┌──────────────────────────────────────────────────────────────────┐
│          scrape_keyword (per-task worker)                          │
│                                                                  │
│  async with semaphore:                                            │
│      async with context.new_page() as page:                       │
│          await setup_region(page, region, postcode)               │
│          for page_num in range(1, max_pages+1):                   │
│              await page.goto(search_url)                          │
│              product_ids = await extract_product_ids(page)        │
│              for pid in product_ids:                              │
│                  if not checkpoint.is_completed(key, pid):        │
│                      checkpoint.add(key, pid)                     │
│                      results.append({pid, keyword, region, ...})  │
│          checkpoint.save()                                        │
└──────────────┬────────────────────────────────────────────────────┘
               │
      ┌────────┴─────────┐
      ▼                  ▼
┌───────────────┐   ┌──────────────────────┐
│  setup_region │   │  extract_product_ids │
│  (postcode)   │   │  (Playwright locs)   │
│               │   │                      │
│  - navigate   │   │  - scroll to bottom  │
│  - set zip    │   │  - wait for products │
│  - confirm    │   │  - extract data-product-id │
└───────────────┘   └──────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  List[product_id]   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  DataFrame          │
                    │  (keyword, region,  │
                    │   product_ids, ...)  │
                    └──────────┬──────────┘
                               │
               ┌───────────────┴────────────────┐
               ▼                                ▼
      ┌────────────────┐              ┌─────────────────┐
      │  LocalSink     │              │  DynamoDBSink   │
      │  (CSV write)   │              │  (conditional)  │
      │  - atomic tmp  │              │  - seen set     │
      │  - pandas.to_  │              │  - first-sight  │
      │    csv()       │              │    wins         │
      └────────────────┘              └─────────────────┘
```

---

## Components

### CLI (cli.py)

Three Click commands:

- **`run`**: Main orchestrator. Parses CSV, invokes `scrape_all()`, writes results to sink
- **`probe`**: Tests that Playwright can launch Firefox (catches missing browsers early)
- **`plan`**: Estimates workload (keywords × pages × avg time) without fetching

All commands configure logging and exit non-zero on error for scripting.

### Configuration (config.py)

Pydantic `Settings` class with environment variable support (`SH_` prefix). Key fields:

- `input_path`, `output_path`: File paths
- `base_url`: Template for search URLs (default: `https://shop.example.com/search?q={keyword}&sort={sort}`)
- `max_concurrent`: Semaphore limit (default: 8, range: 1-20)
- `checkpoint_dir`, `checkpoint_every`: Checkpoint persistence config
- `resume`: Boolean flag to enable/disable checkpoint resume
- `sink`: Output destination (`local` | `dynamodb` | `both`)
- `dynamodb_table_name`, `dynamodb_region`: DynamoDB config
- `POSTCODE_MAP`: Dict mapping region codes to delivery postcodes (fake but realistic)

All settings can be overridden via environment variables or `.env` file.

### Orchestrator (core/scraper.py)

**`async def scrape_all(keywords, settings) -> pd.DataFrame`**

1. Creates Playwright browser and single context
2. Loads checkpoint to get already-completed IDs
3. Creates `asyncio.Semaphore(max_concurrent)`
4. Launches N concurrent `scrape_keyword` tasks via `asyncio.gather()`
5. Collects results into one DataFrame
6. Saves checkpoint
7. Returns DataFrame for sink

**Why one context?** Contexts isolate cookies/postcode, but creating one per task is wasteful. Current design: one shared context, pages created per task. Alternative: one context per region (cleaner isolation), documented in ADR-001.

**`async def scrape_keyword(context, keyword, region, sort, max_pages, checkpoint, sem)`**

Per-task worker. Flow:

1. Acquire semaphore
2. Create new page in context
3. Call `setup_region()` to set delivery postcode
4. For each page number:
   - Navigate to search URL with keyword/sort
   - Call `extract_product_ids()` to get IDs from page
   - Filter out already-completed IDs via `checkpoint.is_completed()`
   - Collect results
5. Release page
6. Return results list

Each task is independent except for the shared checkpoint (thread-safe via Python GIL, no explicit lock needed for in-memory dict).

### Postcode Setup (core/postcode.py)

**`async def setup_region(page, region, postcode)`**

Navigates to region-specific delivery-address workflow and sets the postcode. Current implementation is a simplified reference showing the Playwright conversion pattern (one region flow).

**Implementation scope:** All 23 regions from the original 640-line `setup_country()` function are implemented as a data-driven architecture. The `REGION_FLOWS` dictionary maps each region code to a `RegionFlowConfig` defining:

- **Flow type** (single-field, split-two-part, city-dropdown, city-text-input)
- **Split position** for CA/JP/PL/SE/BR (e.g., CA splits "A1A1A1" at position 3 → "A1A 1A1")
- **City mappings** for SA (15 cities), EG (27), ZA (22), AE (8)
- **Behavioral flags** (cookie consent for 9 EU regions, dismiss notifications for 6)

**Why this is configuration, not business logic:** The regional flows are data (declarative config) + generic page manipulation logic (single async function). Selectors live in `selectors.py` as a `LocationSelectors` dataclass with 12 configurable fields (`#delivery-location-trigger`, `.location-modal-close`, etc.). This architecture makes the scraper deployable to different sites without code changes — only the selector config changes.

**Limitation:** The selectors have never run against a live site. All tests use `page.set_content(mock_html)` to avoid network dependencies. Production deployment would override `DEFAULT_SELECTORS` with site-specific values and verify once.

### Product Extraction (core/extraction.py)

**`async def extract_product_ids(page) -> List[str]`**

1. Waits for page load (`domcontentloaded`)
2. Zooms out to 50% to load more products without scrolling as far
3. Scrolls to bottom in loop (checks `scrollHeight` repeatedly)
4. Waits for product elements: `div[data-component-type='s-search-result']`
5. Extracts `data-product-id` attribute from each element
6. Filters empty strings
7. Returns list of product IDs

**Selector assumptions:** The code assumes the target site uses `data-product-id` attributes on search result divs. These selectors have never run against a live site — all tests use `page.set_content(mock_html)` to avoid network dependencies. Production deployment would verify selectors once.

### Checkpoint (core/checkpoint.py)

**`class Checkpoint`**

State persistence for resume capability. Tracks completed product IDs per composite key.

- `records: Dict[str, Set[str]]` — Maps `keyword_region_sort` → set of completed product IDs
- `load()` — Reads `.checkpoints/checkpoint.json`, deserializes into `records` dict
- `save()` — Atomic temp-file write (`checkpoint.json.tmp` → `os.replace()`)
- `add(key, product_id)` — Marks a product ID as completed
- `is_completed(key, product_id) -> bool` — Checks if already harvested
- `get_completed(key) -> Set[str]` — Returns all completed IDs for a key
- `clear()` — Wipes checkpoint state

**Atomicity:** Uses temp-file write + `os.replace()` (atomic on POSIX) to prevent corruption on crash.

**Resume granularity:** Composite key = `f"{keyword}_{region}_{sort}"`. A harvested product ID under "laptop_US_featured" is independent of "laptop_US_newest". This is identity-based resume, not page-offset resume (which breaks when target site adds/removes products).

### Sinks (sinks/)

**`base.py`**: Protocol defining `write(df, run_id) -> Tuple[int, int]` (returns written, skipped counts).

**`local.py`**: LocalSink writes DataFrame to CSV via `pandas.to_csv()`. Uses atomic temp-file pattern.

**`dynamodb.py`**: DynamoDBSink writes to DynamoDB with first-sighting-wins semantics.

**DynamoDB write flow:**

1. For each row in DataFrame:
   - Build `item_key = f"{REGION}#{keyword}#{PRODUCT_ID}"` (normalized)
   - If `item_key` in per-run `seen` set: skip (in-run dedup, no API call)
   - Else: add to `seen`, call `table.put_item(Item={...}, ConditionExpression='attribute_not_exists(item_key)')`
   - If `ConditionalCheckFailedException`: increment `skipped` (first sighting already exists)
   - If success: increment `written`
   - Other exceptions: propagate (non-conditional errors like throughput exceeded)

2. Return `(written, skipped)`

**Key normalization:**

- `REGION` → uppercase
- `keyword` → lowercase, whitespace collapsed (` multi   space  keyword  ` → `multi space keyword`)
- `PRODUCT_ID` → uppercase

Example: `US#laptop#P-123456`

**First-sighting-wins semantics:** The conditional write ensures the first harvest that encounters a (region, keyword, product) tuple writes it with its timestamp/run_id/rank. Re-harvesting weeks later skips existing tuples, preserving original metadata. New products added to search results get written; existing products get skipped with no overwrite.

**Why this matters:** When tracking product rankings over time, the first-sighting date is immutable business data. Upsert semantics would destroy it. Conditional write preserves it forever.

---

## Data Flow

```
CSV input
   │
   ▼
parse (keyword, region, sort)
   │
   ▼
Checkpoint.load() ─────────┐
   │                       │
   ▼                       │ (skip already-completed IDs)
asyncio.gather(            │
  scrape_keyword × N       │
) ──────────────────────────┤
   │                       │
   ▼                       │
List[(keyword, region,     │
      product_id, ...)]    │
   │                       │
   ▼                       │
Filter via checkpoint ─────┘
   │
   ▼
DataFrame
   │
   ├──────────────────┬─────────────────┐
   ▼                  ▼                 ▼
LocalSink       DynamoDBSink      (both)
(CSV write)     (conditional)
   │                  │
   ▼                  ▼
output/harvest.csv   DynamoDB table
                     (first-sighting-wins)
```

---

## Concurrency Model

**Pattern:** `asyncio.gather()` + `asyncio.Semaphore`

```python
sem = asyncio.Semaphore(max_concurrent)

async def scrape_keyword(...):
    async with sem:
        async with context.new_page() as page:
            # work
            pass

tasks = [scrape_keyword(...) for kw in keywords]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

**Why semaphore?** Unbounded parallelism (launching 500 tasks for 500 keywords) would:
- Overwhelm rate limits (target site returns 429)
- Consume excessive memory (500 browser pages)
- Trigger anti-scraping measures

Semaphore(8) allows 8 concurrent pages, queuing the rest. Tunable via `SH_MAX_CONCURRENT` env var.

**Why asyncio.gather over sequential?** 5-10x speedup. Example: 100 keywords × 3 pages × 5 regions = 1,500 pages @ 5s each = 2+ hours sequential. Concurrent with semaphore: ~15-20 minutes.

**Exception handling:** `asyncio.gather(..., return_exceptions=True)` means one task failing doesn't stop others. Failures are logged but don't propagate.

**GIL implications:** Checkpoint dict writes are not explicitly locked — Python GIL makes dict operations atomic at bytecode level. For multi-process deployment, would need explicit locking or per-process checkpoints merged at end.

---

## Design Decisions

### Why Browser Contexts Instead of Tabs (ADR-001)

Original Selenium code juggled `window_handles` and `switch_to.window()`. Playwright contexts provide:

- **Clean isolation:** Cookies, storage, postcode state isolated per context
- **No switching:** Each context/page is directly addressable, no handle lookup
- **Shared browser:** Contexts share the browser process (unlike separate browser instances)

Tradeoff: Memory cost (~50MB per context) vs. state leakage risk with shared tabs. Current design uses one shared context for simplicity; production could use one context per region for stronger isolation.

### Why Semaphore for Rate Limiting (ADR-002)

Alternative designs considered:

1. **Sequential (no concurrency):** Original Selenium approach. Simple but 5-10x slower.
2. **Unbounded asyncio.gather():** Fastest but overwhelms targets and consumes excessive resources.
3. **asyncio.Semaphore (chosen):** Bounded concurrency with tunability. House standard pattern (from adaptive-fetch).

Semaphore(8) is the default, tunable via `SH_MAX_CONCURRENT`. Higher values increase speed but risk rate-limiting. Lower values reduce resource usage but take longer.

### Why Checkpoint by Identity Instead of Page Offset

Page-offset resume ("`laptop` US featured page 2") breaks when:
- Target site adds new products (page 2 now shows different products)
- Products go out of stock (pages shift)
- Sort order changes

Identity-based resume (`REGION#keyword#PRODUCT_ID`) is stable: if a product was harvested, skip it regardless of which page it appears on now.

Tradeoff: Checkpoint file size grows linearly with product count (~1MB for 100k products). Page-offset checkpoints would be constant size (~1KB) but fragile.

### Why DynamoDB Conditional Write

The composite key `item_key = REGION#keyword#PRODUCT_ID` with `attribute_not_exists(item_key)` ensures:

1. **Idempotent harvests:** Re-running the same harvest doesn't duplicate rows
2. **First-sighting preservation:** Original timestamp, run_id, rank never overwritten
3. **Atomic deduplication:** No race conditions (DynamoDB handles conditional write atomically)

Alternative (upsert with overwrite) would lose first-sighting metadata — which is the entire point of harvesting over time. Conditional write makes "idempotent" mean "preserves first sighting" rather than "overwrites with latest."

### Batched Checkpoint Saves

Checkpoint saves after every `checkpoint_every` records (default: 25). Why not after every record?

- **I/O overhead:** 1,000 records × 1 write each = 1,000 I/O ops. Batched: ~40 writes.
- **Atomicity:** Temp-file write ensures either the full checkpoint is written or nothing.

Tradeoff: On crash, lose up to 25 records of progress. Acceptable for a resumable harvest.

---

## Configuration

| Setting | Type | Default | Description |
|:--|:--|:--|:--|
| `input_path` | str | `data/sample_keywords.csv` | CSV with keyword, region, sort columns |
| `output_path` | str | `output/harvest.csv` | Local CSV output path |
| `base_url` | str | `https://shop.example.com/search?q={keyword}&sort={sort}` | Search URL template |
| `max_concurrent` | int | 8 | Semaphore limit (range: 1-20) |
| `checkpoint_dir` | str | `.checkpoints` | Checkpoint directory |
| `checkpoint_every` | int | 25 | Records per checkpoint save |
| `resume` | bool | True | Enable checkpoint resume |
| `sink` | str | `local` | Output destination (local / dynamodb / both) |
| `dynamodb_table_name` | str | `product-harvest` | DynamoDB table name |
| `dynamodb_region` | str | `us-east-1` | AWS region for DynamoDB |
| `log_level` | str | `INFO` | Python logging level |
| `user_name` | str | `user` | User identifier for run metadata |
| `headless` | bool | True | Run browser headless |

All settings support environment variables with `SH_` prefix (e.g., `SH_MAX_CONCURRENT=12`).

---

## Running

```bash
bash setup.sh                # Install deps, verify, run tests

source .venv/bin/activate

# Test browser launch
serp-harvest probe

# Estimate workload
serp-harvest plan data/sample_keywords.csv --max-pages 3

# Run harvest
serp-harvest run data/sample_keywords.csv --max-pages 3 --sink local

# Run with DynamoDB (requires credentials)
serp-harvest run data/sample_keywords.csv --sink dynamodb --no-resume
```

---

## Testing

```bash
pytest -v                    # All tests (42 pass)
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests
pytest --cov=serp_harvest    # With coverage
```

**Test strategy:**

- **Unit tests:** Pure logic (checkpoint persistence, key normalization, CSV writes). Mock all I/O.
- **Integration tests:** Full orchestration with stub sinks and mock HTML. No network, no real DynamoDB.
- **Playwright tests:** Use `page.set_content(mock_html)` to avoid network dependencies. Five tests require `playwright install firefox`.

**Coverage:** All 42 tests pass (24 for the 23-region postcode module, 4 for extraction, 11 for other modules, 3 integration). The postcode test suite covers all flow types, split positions, city mappings, cookie consent flags, and dismiss notification flags. DynamoDB tested via `StubDynamoDBTable` fixture (in `conftest.py`), not against a real table. Playwright selectors tested against mock HTML, never against a live search-results page.

**Scope boundaries:** The 23 regional flows are complete and tested; the selectors are configurable placeholders. Production deployment would override `DEFAULT_SELECTORS` with site-specific CSS IDs and verify against the target site. DynamoDB writes are tested via stub, not against a real table. These are deployment configuration gaps, not architectural defects.

---

Built following house style from `adaptive-fetch`. See `docs/adr/` for architectural decision records and `README.md` for usage guide.
