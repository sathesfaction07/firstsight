"""Sink factory for data output destinations."""

from typing import Union

from .dynamodb import DynamoDBSink
from .local import LocalSink


def get_sink(sink_type: str, **kwargs) -> Union[LocalSink, DynamoDBSink]:
    """Factory function to create the appropriate sink instance.

    Args:
        sink_type: Type of sink to create ('local' or 'dynamodb')
        **kwargs: Sink-specific configuration

    Returns:
        Configured sink instance

    Raises:
        ValueError: If sink_type is not recognized
    """
    if sink_type == "local":
        return LocalSink(output_path=kwargs.get("output_path", "output/harvest.csv"))
    elif sink_type == "dynamodb":
        return DynamoDBSink(
            table_name=kwargs.get("table_name", "product-harvest"),
            region=kwargs.get("region", "us-east-1"),
        )
    else:
        raise ValueError(f"Unknown sink type: {sink_type}")
