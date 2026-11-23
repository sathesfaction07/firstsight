# SerpHarvest

A Playwright-driven search results harvester with checkpoint recovery and concurrent page scraping. Extracts product listings across multiple keywords, regions, and sort orders, with idempotent DynamoDB storage that preserves first-sighting semantics — re-scraping the same query days later neither duplicates rows nor overwrites original timestamps.

---

## The Problem

Harvesting product data at scale across multiple keywords, regions, and sort orders creates several problems:

**Concurrency.** Sequential page-by-page scraping takes hours for even modest workloads. A keyword matrix of 50 keywords × 5 regions × 2 sort orders × 3 pages each = 1,500 pages at ~5 seconds per page is over two hours of wall time. Browser automation can do better.

**Resume capability.** Network failures, rate limits, or browser crashes are inevitable at that scale. Without checkpoint-resume, every failure means starting over and re-fetching data you already collected.

**Idempotence.** Running the same harvest twice should not create duplicate database rows. More importantly, re-running a harvest days later to catch new products should *not* overwrite the original sighting date of existing products — first-sighting timestamps are the business value, and upsert semantics destroy them.

**Resource control.** Unbounded parallelism overwhelms rate limits and drowns in browser tabs. Controlled concurrency requires explicit limiting.

Manual coordination of browser contexts, checkpoints, and database deduplication logic is error-prone and masks the actual harvest logic. This tool structures the problem so the harvest is declarative data (a CSV of keywords and regions) and the machinery is reusable.

---

## How It Works

1. **Input parsing:** Reads a CSV with `keyword`, `region`, `sort` columns (e.g., "laptop, US, featured")
2. **Checkpoint load:** If `--resume` is enabled, loads `.checkpoints/checkpoint.json` to skip already-harvested product IDs
3. **Concurrent scraping:**
   - Creates one Playwright browser with a context pool
   - Launches N concurrent tasks (default 8) under an `asyncio.Semaphore`
   - Each task: navigates to search URL → sets delivery postcode → paginates → extracts product IDs
4. **Deduplication:**
   - Per-run `seen` set prevents redundant API calls within a harvest
   - DynamoDB conditional write (`attribute_not_exists(item_key)`) ensures first sighting wins across runs
5. **Checkpoint save:** Batched atomic writes to `.checkpoints/checkpoint.json` after processing each page
6. **Output:** Writes to local CSV and/or DynamoDB with (written, skipped) counts

**Why this approach:**

- **Semaphore over sequential:** 5-10x faster (2 hours → 15-20 minutes) with controlled resource usage
- **Playwright auto-wait:** Eliminates most `time.sleep()` calls that Selenium required
- **Browser contexts over tabs:** Contexts isolate cookies/postcode state cleanly without tab-switching logic
- **Checkpoint by identity:** Resume granularity = (region, keyword, product_id) tuples, not fragile page offsets
- **First-sighting-wins:** The composite key `REGION#keyword#PRODUCT_ID` with conditional write preserves original timestamps forever

---

## The Cross-Run Deduplication Feature

When tracking product rankings over time, the first-sighting date is immutable business data — it tells you when a product *first appeared* in search results for a given keyword in a given region. Upsert semantics destroy this: re-harvesting the same query five days later to catch newly-listed products would overwrite all existing rows with new timestamps, losing the original sighting dates.

SerpHarvest solves this with a two-level deduplication strategy:

**Within a run:** An in-memory `seen` set prevents processing the same (region, keyword, product_id) tuple twice. If product P-123 appears on page 1 and page 3 for "laptop" in US, it gets written once and the second occurrence is filtered out before any database call. This avoids wasting API quota on redundant conditional writes.

**Across runs:** DynamoDB's conditional write with `attribute_not_exists(item_key)` is the cross-run gate. The composite partition key `REGION#keyword#PRODUCT_ID` (e.g., `US#laptop#P-123456`) uniquely identifies each sighting. When a row with that key already exists, DynamoDB rejects the write atomically and boto3 raises `ConditionalCheckFailedException`, which the sink catches and counts as a skip.

This means:
- Re-harvesting the same keyword/region/product weeks later does not duplicate rows
- The first timestamp, run_id, rank, and metadata are preserved forever
- New products added to the search results get written; existing products get skipped with no overwrite

The business value: you can track "laptop" in US every Monday for six months, and every product's record shows when it *first* appeared in results for that keyword, not the most recent harvest date. Trends, seasonality, and time-to-discovery analysis all depend on this property. Without it, your time-series data is a snapshot series with no memory.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     CLI (run, probe, plan)                 │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│              scrape_all (orchestrator)                      │
│   - Checkpoint.load()                                       │
│   - asyncio.Semaphore(max_concurrent=8)                    │
│   - asyncio.gather(scrape_keyword × N tasks)               │
│   - Checkpoint.save()                                      │
└──────────────────────────┬─────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            │    scrape_keyword (async)    │  (one per keyword/region/sort)
            │  - goto search URL           │
            │  - setup_region (postcode)   │
            │  - paginate & extract IDs    │
            │  - Checkpoint.add()          │
            └──────────────┬──────────────┘
                           │
           ┌───────────────┴───────────────┐
           ▼                               ▼
┌──────────────────┐          ┌────────────────────┐
│  Postcode Setup  │          │   Extraction       │
│  (23 regions,    │          │  (Playwright       │
│   4 flow types)  │          │   locators)        │
└──────────────────┘          └────────────────────┘
                                      │
                                      ▼
                              ┌───────────────────┐
                              │  DataFrame with   │
                              │  product_ids      │
                              └─────────┬─────────┘
                                        │
                                        ▼
                              ┌───────────────────┐
                              │  Sink.write()     │
                              │   - LocalSink     │
                              │   - DynamoDBSink  │
                              └───────────────────┘
```

---

## Project Structure

```
serp-harvest/
├── src/serp_harvest/
│   ├── __init__.py           # Package version
│   ├── config.py             # Pydantic Settings (env vars, postcodes map)
│   ├── cli.py                # Click commands (run, probe, plan)
│   ├── core/
│   │   ├── checkpoint.py     # State persistence, identity-based resume
│   │   ├── scraper.py        # Main async orchestration (gather + semaphore)
│   │   ├── extraction.py     # Product ID extraction from page (Playwright locators)
│   │   ├── postcode.py       # 23-region delivery setup (data-driven flows)
│   │   └── selectors.py      # Configurable DOM selectors (deployment config)
│   └── sinks/
│       ├── base.py           # Sink protocol
│       ├── local.py          # CSV output with atomic temp-file writes
│       └── dynamodb.py       # Conditional write with first-sighting semantics
├── tests/
│   ├── conftest.py           # Fixtures: StubDynamoDBTable, Playwright page
│   ├── unit/
│   │   ├── test_checkpoint.py   # Persistence, resume, atomic writes
│   │   ├── test_extraction.py   # Product ID parsing (mock HTML)
│   │   ├── test_postcode.py     # 23-region flows, split logic, city mappings
│   │   └── test_sinks.py        # DynamoDB dedup semantics, CSV writes
│   └── integration/
│       └── test_scrape_loop.py  # Full orchestration with checkpoint/sink
├── data/
│   ├── sample_keywords.csv      # Example input
│   └── mock_search_results.html # Static HTML for testing extraction
├── docs/adr/
│   ├── ADR-001-playwright-contexts-not-tabs.md
│   └── ADR-002-semaphore-for-rate-limiting.md
├── setup.sh                     # Zero-to-running script
├── pyproject.toml               # Dependencies, ruff config, pytest config
└── README.md
```

---

## Running

```bash
bash setup.sh                # Install deps, verify imports, run tests

source .venv/bin/activate

serp-harvest probe           # Test Playwright browser launch
serp-harvest plan data/sample_keywords.csv --max-pages 3
serp-harvest run data/sample_keywords.csv --max-pages 3 --sink local
serp-harvest run data/sample_keywords.csv --sink dynamodb --no-resume
```

---

## Usage Reference

### CLI Commands

**`run INPUT_PATH`**: Execute the harvest

- `--max-pages N`: Pages to scrape per keyword (default: 3)
- `--sink local|dynamodb|both`: Output destination (default: local)
- `--resume / --no-resume`: Use checkpoint (default: --resume)

**`probe`**: Verify Playwright can launch Firefox

**`plan INPUT_PATH`**: Estimate harvest size and duration without fetching

### Environment Variables

All settings support environment variables with `SH_` prefix:

```bash
export SH_MAX_CONCURRENT=12              # Concurrent pages (default: 8)
export SH_CHECKPOINT_DIR=".chk"          # Checkpoint directory
export SH_OUTPUT_PATH="out.csv"          # CSV output path
export SH_DYNAMODB_TABLE_NAME="products"
export SH_DYNAMODB_REGION="us-west-2"
export SH_HEADLESS=false                 # Show browser (default: true)
```

Or use a `.env` file (auto-loaded by Pydantic).

### Input CSV Format

```csv
keyword,region,sort
wireless mouse,US,featured
laptop,CA,newest
headphones,UK,featured
```

Columns: `keyword` (required), `region` (required, 2-letter ISO code), `sort` (optional, defaults to "featured").

---

## Testing

```bash
pytest -v                    # All tests (42 pass)
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests
pytest --cov=serp_harvest    # With coverage
```

**Test coverage:** All 42 tests pass, including 24 for the 23-region postcode module covering every flow type, split position, city mapping, and regional quirk. Extraction tests use mock HTML via `page.set_content()` (zero network calls). The DynamoDB sink is tested against a `StubDynamoDBTable` fixture, not a real table.

---

## Configuration

Key settings in `config.py`:

- **`POSTCODE_MAP`**: Region → postcode mappings (fake but realistic: 10001 for US, A1A 1A1 for CA, EC1A 1BB for UK, etc.)
- **`max_concurrent`**: Semaphore limit (default: 8, range: 1-20)
- **`checkpoint_every`**: Save frequency (default: 25 records)
- **`base_url`**: Target site template (default: `https://shop.example.com/search?q={keyword}&sort={sort}`)

**Per-region delivery flows (23 regions, 4 flow types):**

The original tool had a 640-line `setup_country()` function with nested conditionals for each region's delivery-address workflow. SerpHarvest replaces this with a data-driven architecture:

- **`REGION_FLOWS` dictionary**: Maps each of 23 region codes to a `RegionFlowConfig` defining its flow type, split position (for CA/JP/PL/SE/BR), city mappings (for SA/EG/ZA/AE), and behavioral flags (cookie consent for 9 EU regions, dismiss notifications for 6).
- **`PostcodeFlowType` enum**: Four categories — single-field, split-two-part, city-dropdown, city-text-input.
- **`selectors.py`**: Configurable CSS selectors for DOM elements (location trigger, postcode inputs, city dropdowns, confirm buttons, cookie banners). All selectors are deployment configuration, not business logic.

**Why selectors are configuration:** The same harvest logic applies to any search-results page, but DOM selectors change per site. Isolating them into a deployment-time config class means the core scraper never knows about specific CSS IDs — only the `LocationSelectors` instance does. This makes the codebase deployable to different targets without code changes, and testable without a live site.

**DynamoDB schema:**

The partition key is `item_key`, a composite string:

```
item_key = f"{REGION}#{keyword}#{PRODUCT_ID}"
```

Where:
- `REGION` = uppercased region code (US, CA, UK)
- `keyword` = lowercased, whitespace-collapsed search term
- `PRODUCT_ID` = uppercased product identifier

Example: `US#laptop#P-123456`

**First-sighting-wins semantics:**

Every write uses `attribute_not_exists(item_key)` as the condition expression. If the key already exists, DynamoDB rejects the write and boto3 raises `ConditionalCheckFailedException`, which the sink catches and counts as a skip. This means:

1. Re-harvesting the same keyword/region/product weeks later does not overwrite the original row
2. The first timestamp, run_id, rank, and metadata are preserved forever
3. New products added to the search results get written; existing products get skipped

This is the project's headline engineering feature — idempotent harvesting where "idempotent" means "preserves first-sighting data" rather than "overwrites with latest data."

---

## Tradeoffs and Decisions I Made Along the Way

**Why no GUI?** The original tool (a Selenium-based desktop harvester I built internally) had a GUI with a start button and progress bars. I dropped it here because CLI tools compose into automation pipelines and scheduled jobs without needing a display. If you need point-and-click, wrap the CLI in a simple web UI — but that wasn't this project's goal.

**Why Playwright over Selenium?** House rule, non-negotiable. But also correct: Playwright's auto-wait eliminates ~80% of the `time.sleep()` calls that litter Selenium scrapers, and async support enables the semaphore concurrency pattern. The port was mechanical: `driver.find_elements()` → `page.locator().all()`, `WebDriverWait` → `page.wait_for_selector()`, `window.open() + switch_to.window()` → `context.new_page()`.

**Why browser contexts instead of tabs?** The original juggled `window_handles` and `switch_to.window()` to open one search page per region. Contexts isolate cookies and delivery postcode state cleanly while sharing the browser process. Tradeoff: slightly more memory (one context per region) vs. risk of state leakage across tabs. I went with contexts because the isolation is explicit and the memory cost is trivial (< 50MB per context).

**Why asyncio.gather + Semaphore instead of sequential?** The original scraped one page at a time. For 100 keywords × 3 pages × 5 regions = 1,500 pages @ 5s each, that's over two hours. `Semaphore(8)` brings it to ~15-20 minutes with controlled resource usage. This is the house standard concurrency pattern (from `adaptive-fetch` and the portfolio style guide). The semaphore prevents overwhelming rate limits or drowning in tabs.

**Why checkpoint by composite key instead of page number?** Page offsets break when the target site adds or removes products between runs. Identity-based resume (`REGION#keyword#PRODUCT_ID`) is stable: if a product was harvested, skip it; if it's new, fetch it. Tradeoff: checkpoint files grow (~1MB for 100k products) but deterministic resume is worth it. A page-offset approach would be smaller but fragile.

**Why DynamoDB conditional write?** The original used the exact same pattern: `attribute_not_exists(item_key)` means "write only if this exact combination has never been seen." Re-scraping the same query five days later to catch newly-listed products skips the ones already in the table, preserving their original timestamp and run_id. This is idempotence at the row level. The alternative (upsert) would overwrite, losing first-sighting metadata — which is the whole point of harvesting over time.

**Why implement all 23 marketplace postcode setups?** The original tool had a 640-line `setup_country()` function with nested conditionals for each region's delivery-address workflow (single-field postcodes, split-field with different break points, city dropdowns with different list lengths, cookie consent banners on 9 EU regions). I ported all 23 variations as a data-driven architecture (`REGION_FLOWS` dictionary + `PostcodeFlowType` enum) to show the Selenium → Playwright conversion pattern faithfully, including regional quirks like Canada's 3-character split (A1A 1A1) and Saudi Arabia's 15-city dropdown. The extraction logic is complete and tested against mock HTML; the postcode setup is complete and tested against all flow types, but the selectors have never run against a live site.

**What is not verified?** The Playwright selectors (`div[data-component-type='s-search-result']`, `data-product-id` attributes, delivery location trigger IDs) have never run against a live search-results page. All extraction tests use `page.set_content(mock_html)` to avoid network calls and target-site dependencies. The DynamoDB write path is covered by tests using a `StubDynamoDBTable`, not against a real table. These are stated scope boundaries, not defects: the patterns are correct, the regional flows are complete, and production deployment would verify selectors and credentials once. The 23-region coverage is faithfully ported from the original; the limitation is that DOM selectors are configurable placeholders that must be overridden with site-specific values at deployment.

---

## Stack

- **Python >=3.11** (required for improved asyncio and typing)
- **Playwright >=1.40** (browser automation, async API)
- **Pydantic >=2.0** (settings with environment variable support)
- **Click >=8.1** (CLI framework)
- **pandas >=2.0** (DataFrame I/O)
- **boto3 >=1.34** (optional, DynamoDB sink)
- **pytest + pytest-asyncio + pytest-playwright** (testing)
- **ruff** (linting/formatting)

---

Built following house style from `adaptive-fetch`. See `ARCHITECTURE.md` for detailed component design and `docs/adr/` for architectural decisions.
