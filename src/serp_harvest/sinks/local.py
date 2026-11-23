"""Local filesystem sink for CSV/JSON output."""

import logging
import os
import shutil
import tempfile
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class LocalSink:
    """Writes harvested data to local CSV files."""

    def __init__(self, output_path: str):
        self.output_path = output_path

    def write(self, df: pd.DataFrame, run_id: str) -> Tuple[int, int]:
        """Write DataFrame to local CSV using atomic temp file pattern.

        Args:
            df: DataFrame to save
            run_id: Unique identifier for this harvest run

        Returns:
            Tuple of (written_count, 0) - local sink doesn't skip duplicates
        """
        if df is None or df.empty:
            return 0, 0

        os.makedirs(os.path.dirname(self.output_path) or ".", exist_ok=True)

        temp_dir = tempfile.mkdtemp()
        try:
            temp_path = os.path.join(temp_dir, "temp.csv")
            df.to_csv(temp_path, encoding="utf-8-sig", index=False)
            shutil.copy2(temp_path, self.output_path)
            logger.info(f"Wrote {len(df)} records to {self.output_path}")
            return len(df), 0
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return 0, 0
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
