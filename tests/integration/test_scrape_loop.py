"""Integration tests for the full scrape loop."""

import pandas as pd
import pytest

from serp_harvest.core.checkpoint import Checkpoint
from serp_harvest.sinks.local import LocalSink


def test_checkpoint_integration(tmp_path):
    cp = Checkpoint(checkpoint_dir=str(tmp_path))

    cp.add("laptop_us_featured", "P-0001")
    cp.add("laptop_us_featured", "P-0002")
    cp.add("mouse_ca_newest", "P-0003")
    cp.save()

    assert cp.is_completed("laptop_us_featured", "P-0001")
    assert not cp.is_completed("laptop_us_featured", "P-9999")

    cp2 = Checkpoint(checkpoint_dir=str(tmp_path))
    cp2.load()

    assert cp2.is_completed("laptop_us_featured", "P-0001")
    assert cp2.is_completed("mouse_ca_newest", "P-0003")


def test_sink_write_integration(tmp_path):
    sink = LocalSink(output_path=str(tmp_path / "harvest.csv"))

    df = pd.DataFrame([
        {"product_ids": "P-0001", "keyword": "laptop", "region": "US", "sort_by": "featured"},
        {"product_ids": "P-0002", "keyword": "mouse", "region": "CA", "sort_by": "newest"},
    ])

    written, skipped = sink.write(df, "run_12345678")

    assert written == 2
    assert skipped == 0

    csv_path = tmp_path / "harvest.csv"
    assert csv_path.exists()

    df_read = pd.read_csv(csv_path)
    assert len(df_read) == 2
    assert df_read["product_ids"].tolist() == ["P-0001", "P-0002"]


@pytest.mark.asyncio
async def test_extraction_integration(page, mock_html):
    from serp_harvest.core.extraction import extract_product_ids

    await page.set_content(mock_html)
    product_ids = await extract_product_ids(page)

    assert len(product_ids) == 3
    assert "P-0001" in product_ids
    assert "P-0002" in product_ids
    assert "P-0003" in product_ids
