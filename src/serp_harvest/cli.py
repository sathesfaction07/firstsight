"""Command-line interface for SerpHarvest."""

import asyncio
import logging
import sys
import uuid

import click
import pandas as pd
from playwright.async_api import async_playwright

from .config import Settings
from .core import scrape_all
from .sinks import get_sink


def setup_logging(level: str = "INFO"):
    """Configure logging for the application."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


@click.group()
def main():
    """SerpHarvest: Playwright-driven search results harvester."""
    pass


@main.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--max-pages", default=3, help="Maximum pages to scrape per keyword")
@click.option("--sink", default="local", type=click.Choice(["local", "dynamodb", "both"]))
@click.option("--resume/--no-resume", default=True, help="Resume from checkpoint")
def run(input_path: str, max_pages: int, sink: str, resume: bool):
    """Run the harvest using keywords from INPUT_PATH CSV.

    INPUT_PATH should be a CSV with columns: keyword, region, sort
    """
    settings = Settings(input_path=input_path, sink=sink, resume=resume)
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    logger.info(f"Starting harvest from {input_path}")

    try:
        df_input = pd.read_csv(input_path)
        required_cols = {"keyword", "region"}
        if not required_cols.issubset(df_input.columns):
            logger.error(f"CSV must have columns: {required_cols}")
            sys.exit(1)

        if "sort" not in df_input.columns:
            df_input["sort"] = "featured"

        keywords = [
            (row["keyword"], row["region"], row.get("sort", "featured"), max_pages)
            for _, row in df_input.iterrows()
        ]

        df_results = asyncio.run(scrape_all(keywords, settings))

        if df_results.empty:
            logger.warning("No results harvested")
            return

        run_id = f"run_{uuid.uuid4().hex[:8]}"

        if sink in ("local", "both"):
            local_sink = get_sink("local", output_path=settings.output_path)
            written, skipped = local_sink.write(df_results, run_id)
            logger.info(f"Local: {written} written, {skipped} skipped")

        if sink in ("dynamodb", "both"):
            try:
                dynamodb_sink = get_sink(
                    "dynamodb",
                    table_name=settings.dynamodb_table_name,
                    region=settings.dynamodb_region,
                )
                written, skipped = dynamodb_sink.write(df_results, run_id)
                logger.info(f"DynamoDB: {written} written, {skipped} skipped")
            except Exception as e:
                logger.error(f"DynamoDB write failed: {e}")

        logger.info("Harvest complete")

    except Exception as e:
        logger.error(f"Harvest failed: {e}", exc_info=True)
        sys.exit(1)


@main.command()
def probe():
    """Test that Playwright can launch a browser."""
    setup_logging()
    logger = logging.getLogger(__name__)

    async def test_launch():
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto("https://example.com")
            title = await page.title()
            await browser.close()
            return title

    try:
        title = asyncio.run(test_launch())
        logger.info(f"✓ Browser launched successfully (page title: {title})")
    except Exception as e:
        logger.error(f"✗ Browser launch failed: {e}")
        sys.exit(1)


@main.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--max-pages", default=3, help="Maximum pages to scrape per keyword")
def plan(input_path: str, max_pages: int):
    """Estimate harvest size and duration from INPUT_PATH CSV."""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        df_input = pd.read_csv(input_path)
        required_cols = {"keyword", "region"}
        if not required_cols.issubset(df_input.columns):
            logger.error(f"CSV must have columns: {required_cols}")
            sys.exit(1)

        total_keywords = len(df_input)
        total_pages = total_keywords * max_pages
        estimated_products = total_pages * 48

        logger.info(f"Keywords: {total_keywords}")
        logger.info(f"Total pages: {total_pages}")
        logger.info(f"Estimated products: {estimated_products}")
        logger.info(f"Estimated duration: {total_pages * 5 / 60:.1f} minutes (@ 5s/page)")

    except Exception as e:
        logger.error(f"Plan failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
