"""Tests for product ID extraction."""

import pytest

from serp_harvest.core.extraction import extract_product_ids


@pytest.mark.asyncio
async def test_extract_product_ids_from_mock_html(page, mock_html):
    await page.set_content(mock_html)
    product_ids = await extract_product_ids(page)

    assert len(product_ids) == 3
    assert "P-0001" in product_ids
    assert "P-0002" in product_ids
    assert "P-0003" in product_ids


@pytest.mark.asyncio
async def test_extract_handles_empty_data_product_id_attr(page):
    html = """<html><body>
    <div data-component-type="s-search-result" data-product-id="P-0001"></div>
    <div data-component-type="s-search-result" data-product-id=""></div>
    <div data-component-type="s-search-result" data-product-id="P-0002"></div>
    </body></html>"""

    await page.set_content(html)
    product_ids = await extract_product_ids(page)

    assert len(product_ids) == 2
    assert "P-0001" in product_ids
    assert "P-0002" in product_ids
    assert "" not in product_ids


@pytest.mark.asyncio
async def test_extract_handles_missing_elements(page):
    html = """<html><body>
    <p>No product elements here</p>
    </body></html>"""

    await page.set_content(html)
    product_ids = await extract_product_ids(page)

    assert len(product_ids) == 0


@pytest.mark.asyncio
async def test_extract_deduplicates_within_page(page):
    html = """<html><body>
    <div data-component-type="s-search-result" data-product-id="P-0001"></div>
    <div data-component-type="s-search-result" data-product-id="P-0001"></div>
    <div data-component-type="s-search-result" data-product-id="P-0002"></div>
    </body></html>"""

    await page.set_content(html)
    product_ids = await extract_product_ids(page)

    assert product_ids.count("P-0001") == 2
    assert product_ids.count("P-0002") == 1
