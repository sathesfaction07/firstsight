"""Sink abstraction for writing harvested data."""

from typing import Protocol, Tuple

import pandas as pd


class Sink(Protocol):
    """Protocol for data output destinations."""

    def write(self, df: pd.DataFrame, run_id: str) -> Tuple[int, int]:
        """Write DataFrame to the destination.

        Args:
            df: DataFrame containing harvested data
            run_id: Unique identifier for this harvest run

        Returns:
            Tuple of (written_count, skipped_count)
        """
        ...
