"""Main scraping orchestration with concurrent page processing."""

import asyncio
import logging
from typing import List, Tuple

import pandas as pd
from playwright.async_api import Browser, BrowserContext, async_playwright

from ..config import POSTCODE_MAP, Settings
from .checkpoint import Checkpoint
from .extraction import extract_product_ids
from .postcode import build_composite_key, setup_region

logger = logging.getLogger(__name__)


async def scrape_keyword(
    context: BrowserContext,
    keyword: str,
    region: str,
    sort: str,
    max_pages: int,
    checkpoint: Checkpoint,
    sem: asyncio.Semaphore,
) -> List[Tuple[str, str, str, str]]:
    """Scrape a single keyword/region/sort combination.

    Args:
        context: Playwright browser context
        keyword: Search keyword
        region: Region code
        sort: Sort type (featured/newest)
        max_pages: Maximum pages to scrape
        checkpoint: Checkpoint instance
        sem: Semaphore for concurrency control

    Returns:
        List of (product_id, keyword, region, sort) tuples
    """
    async with sem:
        page = await context.new_page()
        results = []
        key = build_composite_key(keyword, region, sort)

        try:
            postcode = POSTCODE_MAP.get(region, "")
            base_url = f"https://shop.example.com/search?q={keyword}&sort={sort}"

            await page.goto(base_url, wait_until="domcontentloaded")

            if postcode:
                await setup_region(page, region, postcode)

            for page_num in range(1, max_pages + 1):
                page_url = f"{base_url}&page={page_num}"
                await page.goto(page_url, wait_until="domcontentloaded")

                product_ids = await extract_product_ids(page)

                for product_id in product_ids:
                    if not checkpoint.is_completed(key, product_id):
                        results.append((product_id, keyword, region, sort))
                        checkpoint.add(key, product_id)

                logger.info(
                    f"Region {region} Page {page_num} for '{keyword}' (sort: {sort}): "
                    f"{len(product_ids)} products"
                )

        except Exception as e:
            logger.error(f"Error scraping {keyword}/{region}/{sort}: {e}")
        finally:
            await page.close()

        return results


async def scrape_all(
    keywords: List[Tuple[str, str, str, int]], settings: Settings
) -> pd.DataFrame:
    """Orchestrate concurrent scraping of all keyword/region/sort combinations.

    Args:
        keywords: List of (keyword, region, sort, max_pages) tuples
        settings: Application settings

    Returns:
        DataFrame with harvested data
    """
    checkpoint = Checkpoint(settings.checkpoint_dir)
    if settings.resume:
        checkpoint.load()

    all_results = []
    sem = asyncio.Semaphore(settings.max_concurrent)

    async with async_playwright() as p:
        browser: Browser = await p.firefox.launch(headless=settings.headless)
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )

        tasks = [
            scrape_keyword(context, kw, region, sort, max_pages, checkpoint, sem)
            for kw, region, sort, max_pages in keywords
        ]

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        for results in results_list:
            if isinstance(results, Exception):
                logger.error(f"Task failed: {results}")
                continue
            all_results.extend(results)

        await context.close()
        await browser.close()

    checkpoint.save()

    if not all_results:
        return pd.DataFrame()

    df = pd.DataFrame(all_results, columns=["product_ids", "keyword", "region", "sort_by"])
    return df
