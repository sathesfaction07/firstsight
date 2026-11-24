"""Checkpoint and resume logic for harvest runs."""

import json
import logging
import os
from typing import Dict, Set

logger = logging.getLogger(__name__)


class Checkpoint:
    """Manages harvest state for resume capability."""

    def __init__(self, checkpoint_dir: str = ".checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_path = os.path.join(checkpoint_dir, "checkpoint.json")
        self.records: Dict[str, Set[str]] = {}
        os.makedirs(checkpoint_dir, exist_ok=True)

    def load(self) -> None:
        """Load checkpoint state from disk."""
        if not os.path.exists(self.checkpoint_path):
            logger.info("No checkpoint found, starting fresh")
            return

        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.records = {k: set(v) for k, v in data.items()}
            total = sum(len(v) for v in self.records.values())
            logger.info(f"Loaded checkpoint with {total} records")
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}, starting fresh")
            self.records = {}

    def save(self) -> None:
        """Save checkpoint state to disk atomically."""
        try:
            data = {k: list(v) for k, v in self.records.items()}
            temp_path = f"{self.checkpoint_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, self.checkpoint_path)
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def add(self, key: str, product_id: str) -> None:
        """Add a completed product ID to the checkpoint.

        Args:
            key: Composite key (keyword_region_sort)
            product_id: Product identifier to mark as completed
        """
        if key not in self.records:
            self.records[key] = set()
        self.records[key].add(product_id)

    def is_completed(self, key: str, product_id: str) -> bool:
        """Check if a product ID has been completed.

        Args:
            key: Composite key (keyword_region_sort)
            product_id: Product identifier to check

        Returns:
            True if already completed
        """
        return key in self.records and product_id in self.records[key]

    def get_completed(self, key: str) -> Set[str]:
        """Get all completed product IDs for a key.

        Args:
            key: Composite key (keyword_region_sort)

        Returns:
            Set of completed product IDs
        """
        return self.records.get(key, set())

    def clear(self) -> None:
        """Clear all checkpoint state."""
        self.records = {}
        if os.path.exists(self.checkpoint_path):
            os.remove(self.checkpoint_path)
