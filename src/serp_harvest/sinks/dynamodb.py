"""DynamoDB sink with idempotent conditional writes.

Preserves the first sighting of each REGION#keyword#PRODUCT_ID combination.
The conditional write ensures that re-scraping the same combination preserves
the original timestamp, user, and run_id rather than overwriting.
"""

import logging
from typing import Optional, Tuple

import boto3
import pandas as pd
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_dynamodb_table = None


def get_dynamodb_table(table_name: str, region: str):
    """Get or create the DynamoDB table resource.

    Returns a cached table resource using the standard boto3 credential chain.
    """
    global _dynamodb_table
    if _dynamodb_table is None:
        _dynamodb_table = boto3.resource("dynamodb", region_name=region).Table(table_name)
    return _dynamodb_table


def build_item_key(product_id: str, keyword: str, region: str) -> str:
    """Identity of a scraped row: one product ID, under one keyword, in one marketplace.

    Normalised so 'laptop' and 'Laptop', or ' ca ' and 'CA', collapse to the same key.
    This is the partition key, and it is what makes re-scraping idempotent.

    Args:
        product_id: Product identifier
        keyword: Search keyword used
        region: Marketplace region code

    Returns:
        Formatted partition key string: REGION#keyword#PRODUCT_ID
    """
    product_id = str(product_id).strip().upper()
    keyword = " ".join(str(keyword).split()).lower()
    region = str(region).strip().upper()
    return f"{region}#{keyword}#{product_id}"


class DynamoDBSink:
    """Writes harvested data to DynamoDB with idempotent deduplication."""

    def __init__(self, table_name: str, region: str):
        self.table_name = table_name
        self.region = region

    def write(self, df: Optional[pd.DataFrame], run_id: str) -> Tuple[int, int]:
        """Store rows in the table, skipping REGION+keyword+PRODUCT_ID combinations already
        recorded.

        The conditional write means the first sighting wins: a combination scraped five days
        ago keeps its original timestamp, user and run_id, and today's re-scrape is skipped
        rather than overwriting it. Returns (written, skipped).

        Values are stored as trimmed strings. Empty and NaN values are omitted rather than
        written as empty attributes.

        Args:
            df: DataFrame containing scraped data with columns: product_ids, keyword, region
            run_id: Unique identifier for this scraping run

        Returns:
            Tuple of (written_count, skipped_count)
        """
        if df is None or df.empty:
            return 0, 0

        table = get_dynamodb_table(self.table_name, self.region)
        written = 0
        skipped = 0
        seen = set()

        for row in df.to_dict("records"):
            item_key = build_item_key(
                row.get("product_ids"), row.get("keyword"), row.get("region")
            )
            if item_key in seen:
                skipped += 1
                continue
            seen.add(item_key)

            item = {"item_key": item_key, "run_id": str(run_id)}
            for column, value in row.items():
                if value is None:
                    continue
                if isinstance(value, float) and value.is_integer():
                    text = str(int(value))
                else:
                    text = str(value).strip()
                if text == "" or text.lower() == "nan":
                    continue
                item[str(column)] = text

            try:
                table.put_item(Item=item, ConditionExpression="attribute_not_exists(item_key)")
                written += 1
            except ClientError as error:
                if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    skipped += 1
                else:
                    raise

        return written, skipped
