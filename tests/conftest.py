"""Shared test fixtures for SerpHarvest tests."""


import os

import pytest


class StubDynamoDBTable:
    """Stub DynamoDB table for testing without network access."""

    def __init__(self):
        self.items = {}
        self.put_item_calls = 0

    def put_item(self, Item, ConditionExpression=None):  # noqa: N803
        self.put_item_calls += 1
        item_key = Item["item_key"]

        if ConditionExpression and "attribute_not_exists" in ConditionExpression:
            if item_key in self.items:
                from botocore.exceptions import ClientError

                error_response = {
                    "Error": {
                        "Code": "ConditionalCheckFailedException",
                        "Message": "The conditional request failed",
                    }
                }
                raise ClientError(error_response, "PutItem")

        self.items[item_key] = Item.copy()

    def get_item(self, Key):  # noqa: N803
        item_key = Key["item_key"]
        if item_key in self.items:
            return {"Item": self.items[item_key]}
        return {}


@pytest.fixture
def stub_table(monkeypatch):
    """Provide a stub DynamoDB table for testing."""
    stub = StubDynamoDBTable()

    def mock_get_table(table_name, region):
        return stub

    monkeypatch.setattr("serp_harvest.sinks.dynamodb.get_dynamodb_table", mock_get_table)
    return stub


@pytest.fixture
def mock_html():
    """Provide mock HTML for testing extraction."""
    return """<!DOCTYPE html>
<html>
<body>
    <div data-component-type="s-search-result" data-product-id="P-0001"></div>
    <div data-component-type="s-search-result" data-product-id="P-0002"></div>
    <div data-component-type="s-search-result" data-product-id=""></div>
    <div data-component-type="s-search-result" data-product-id="P-0003"></div>
</body>
</html>"""


@pytest.fixture
def mock_html_file(tmp_path, mock_html):
    """Create a temporary mock HTML file."""
    html_path = tmp_path / "mock_page.html"
    html_path.write_text(mock_html)
    return html_path


@pytest.fixture
async def page():
    """Provide a Playwright page for async tests."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        if not os.path.exists(p.firefox.executable_path):
            # The pip package does not include browsers; CI runs `playwright install firefox`.
            # Without it these tests would ERROR with a banner; say what to run instead.
            pytest.skip("Firefox for Playwright is not installed: run `playwright install firefox`")
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        yield page
        await context.close()
        await browser.close()
