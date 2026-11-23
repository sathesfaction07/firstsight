"""Product ID extraction from search result pages."""

import logging
from typing import List

from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def extract_product_ids(page: Page) -> List[str]:
    """Extract product IDs from the current search results page.

    Scrolls to the bottom to load all products, then extracts identifiers
    from product elements.

    Args:
        page: Playwright Page instance

    Returns:
        List of product ID strings found on the page
    """
    product_ids = []
    try:
        await page.wait_for_load_state("domcontentloaded")

        await page.evaluate("document.body.style.zoom = '50%'")

        last_height = await page.evaluate("document.body.scrollHeight")
        max_scrolls = 50
        scroll_count = 0
        while scroll_count < max_scrolls:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scroll_count += 1

        try:
            await page.wait_for_selector(
                "div[data-component-type='s-search-result']", state="attached", timeout=15000
            )
            products = await page.locator("div[data-component-type='s-search-result']").all()

            for product in products:
                product_id = await product.get_attribute("data-product-id")
                if product_id:
                    product_ids.append(product_id)
        except Exception as e:
            logger.info(f"Product elements not found: {e}")

    except Exception as e:
        logger.error(f"Error extracting product IDs: {e}")

    return product_ids
