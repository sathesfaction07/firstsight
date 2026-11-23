"""Tests for sinks (local and DynamoDB)."""

import pandas as pd
import pytest
from botocore.exceptions import ClientError

from serp_harvest.sinks.dynamodb import DynamoDBSink, build_item_key
from serp_harvest.sinks.local import LocalSink


def test_build_item_key_normalization():
    key1 = build_item_key("p-0001", "laptop", "us")
    key2 = build_item_key("P-0001", "Laptop", "US")
    assert key1 == key2

    key3 = build_item_key(" P-0001 ", " multi   space  keyword  ", " ca ")
    expected = "CA#multi space keyword#P-0001"
    assert key3 == expected

    key_us = build_item_key("P-0001", "laptop", "US")
    key_uk = build_item_key("P-0001", "laptop", "UK")
    assert key_us != key_uk
    assert "US#" in key_us
    assert "UK#" in key_uk


def test_write_none_dataframe(stub_table):
    sink = DynamoDBSink(table_name="test-table", region="us-east-1")
    written, skipped = sink.write(None, "test-run-123")
    assert written == 0
    assert skipped == 0
    assert stub_table.put_item_calls == 0


def test_write_empty_dataframe(stub_table):
    sink = DynamoDBSink(table_name="test-table", region="us-east-1")
    df = pd.DataFrame(columns=["product_ids", "keyword", "region"])
    written, skipped = sink.write(df, "test-run-123")
    assert written == 0
    assert skipped == 0
    assert stub_table.put_item_calls == 0


def test_write_new_items(stub_table):
    sink = DynamoDBSink(table_name="test-table", region="us-east-1")
    df = pd.DataFrame([
        {"product_ids": "P-0001", "keyword": "laptop", "region": "US", "rank": 1},
        {"product_ids": "P-0002", "keyword": "mouse", "region": "CA", "rank": 2},
    ])

    written, skipped = sink.write(df, "test-run-123")

    assert written == 2
    assert skipped == 0
    assert stub_table.put_item_calls == 2
    assert len(stub_table.items) == 2


def test_skip_existing_items(stub_table):
    sink = DynamoDBSink(table_name="test-table", region="us-east-1")

    df1 = pd.DataFrame([
        {
            "product_ids": "P-0001",
            "keyword": "laptop",
            "region": "US",
            "rank": 1,
            "title": "Original",
        }
    ])
    sink.write(df1, "run-1")

    item_key = build_item_key("P-0001", "laptop", "US")

    df2 = pd.DataFrame([
        {
            "product_ids": "P-0001",
            "keyword": "laptop",
            "region": "US",
            "rank": 5,
            "title": "Updated",
        }
    ])
    written, skipped = sink.write(df2, "run-2")

    assert written == 0
    assert skipped == 1
    assert stub_table.items[item_key]["title"] == "Original"
    assert stub_table.items[item_key]["rank"] == "1"
    assert stub_table.items[item_key]["run_id"] == "run-1"


def test_duplicates_within_run_no_extra_calls(stub_table):
    sink = DynamoDBSink(table_name="test-table", region="us-east-1")
    df = pd.DataFrame([
        {"product_ids": "P-0001", "keyword": "laptop", "region": "US", "rank": 1},
        {"product_ids": "P-0001", "keyword": "laptop", "region": "US", "rank": 2},
    ])

    written, skipped = sink.write(df, "test-run-123")

    assert written == 1
    assert skipped == 1
    assert stub_table.put_item_calls == 1
    assert len(stub_table.items) == 1


def test_same_product_different_region_both_written(stub_table):
    sink = DynamoDBSink(table_name="test-table", region="us-east-1")
    df = pd.DataFrame([
        {"product_ids": "P-0001", "keyword": "laptop", "region": "US", "rank": 1},
        {"product_ids": "P-0001", "keyword": "laptop", "region": "CA", "rank": 2},
    ])

    written, skipped = sink.write(df, "test-run-123")

    assert written == 2
    assert skipped == 0
    assert len(stub_table.items) == 2


def test_idempotent_rewrite(stub_table):
    sink = DynamoDBSink(table_name="test-table", region="us-east-1")
    df = pd.DataFrame([
        {"product_ids": "P-0001", "keyword": "laptop", "region": "US", "rank": 1}
    ])

    written1, skipped1 = sink.write(df, "test-run-1")
    assert written1 == 1
    assert skipped1 == 0

    written2, skipped2 = sink.write(df, "test-run-2")
    assert written2 == 0
    assert skipped2 == 1


def test_nan_values_omitted(stub_table):
    sink = DynamoDBSink(table_name="test-table", region="us-east-1")
    df = pd.DataFrame([
        {
            "product_ids": "P-0001",
            "keyword": "laptop",
            "region": "US",
            "valid_column": "valid_value",
            "nan_column": float("nan"),
            "none_column": None,
            "empty_column": "",
        }
    ])

    written, skipped = sink.write(df, "test-run-123")

    assert written == 1
    item_key = build_item_key("P-0001", "laptop", "US")
    item = stub_table.items[item_key]

    assert "valid_column" in item
    assert item["valid_column"] == "valid_value"

    assert "nan_column" not in item
    assert "none_column" not in item
    assert "empty_column" not in item


def test_whole_float_stored_as_int(stub_table):
    sink = DynamoDBSink(table_name="test-table", region="us-east-1")
    df = pd.DataFrame([
        {
            "product_ids": "P-0001",
            "keyword": "laptop",
            "region": "US",
            "whole_float": 1.0,
            "decimal_float": 19.99,
        }
    ])

    written, skipped = sink.write(df, "test-run-123")

    assert written == 1
    item_key = build_item_key("P-0001", "laptop", "US")
    item = stub_table.items[item_key]

    assert item["whole_float"] == "1"
    assert item["decimal_float"] == "19.99"


def test_non_conditional_error_propagates(stub_table, monkeypatch):
    sink = DynamoDBSink(table_name="test-table", region="us-east-1")
    df = pd.DataFrame([{"product_ids": "P-0001", "keyword": "laptop", "region": "US"}])

    def failing_put_item(Item, ConditionExpression=None):  # noqa: N803
        stub_table.put_item_calls += 1
        error_response = {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Rate exceeded",
            }
        }
        raise ClientError(error_response, "PutItem")

    monkeypatch.setattr(stub_table, "put_item", failing_put_item)

    with pytest.raises(ClientError) as exc_info:
        sink.write(df, "test-run-123")

    assert exc_info.value.response["Error"]["Code"] == "ProvisionedThroughputExceededException"


def test_save_csv_safely_success(tmp_path):
    sink = LocalSink(output_path=str(tmp_path / "test.csv"))
    df = pd.DataFrame([
        {"product_ids": "P-0001", "keyword": "laptop", "region": "US"}
    ])

    written, skipped = sink.write(df, "test-run-123")

    assert written == 1
    assert skipped == 0
    assert (tmp_path / "test.csv").exists()

    df_read = pd.read_csv(tmp_path / "test.csv")
    assert len(df_read) == 1
    assert df_read["product_ids"][0] == "P-0001"


def test_save_csv_empty_dataframe(tmp_path):
    sink = LocalSink(output_path=str(tmp_path / "empty.csv"))
    df = pd.DataFrame()

    written, skipped = sink.write(df, "test-run-123")

    assert written == 0
    assert skipped == 0
