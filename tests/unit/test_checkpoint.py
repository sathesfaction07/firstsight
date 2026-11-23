"""Tests for checkpoint and resume logic."""

import json

from serp_harvest.core.checkpoint import Checkpoint


def test_persistence(tmp_path):
    cp = Checkpoint(checkpoint_dir=str(tmp_path))
    cp.add("key1", "P-0001")
    cp.add("key1", "P-0002")
    cp.add("key2", "P-0003")
    cp.save()

    assert (tmp_path / "checkpoint.json").exists()

    cp2 = Checkpoint(checkpoint_dir=str(tmp_path))
    cp2.load()

    assert cp2.is_completed("key1", "P-0001")
    assert cp2.is_completed("key1", "P-0002")
    assert cp2.is_completed("key2", "P-0003")
    assert not cp2.is_completed("key1", "P-9999")


def test_resume(tmp_path):
    cp = Checkpoint(checkpoint_dir=str(tmp_path))
    cp.add("laptop_us_featured", "P-0001")
    cp.add("laptop_us_featured", "P-0002")
    cp.save()

    cp2 = Checkpoint(checkpoint_dir=str(tmp_path))
    cp2.load()

    completed = cp2.get_completed("laptop_us_featured")
    assert "P-0001" in completed
    assert "P-0002" in completed
    assert "P-9999" not in completed


def test_get_completed(tmp_path):
    cp = Checkpoint(checkpoint_dir=str(tmp_path))
    cp.add("key1", "P-0001")
    cp.add("key1", "P-0002")

    completed = cp.get_completed("key1")
    assert len(completed) == 2
    assert "P-0001" in completed
    assert "P-0002" in completed

    empty = cp.get_completed("nonexistent_key")
    assert len(empty) == 0


def test_clear(tmp_path):
    cp = Checkpoint(checkpoint_dir=str(tmp_path))
    cp.add("key1", "P-0001")
    cp.save()

    assert (tmp_path / "checkpoint.json").exists()

    cp.clear()

    assert len(cp.records) == 0
    assert not (tmp_path / "checkpoint.json").exists()


def test_atomic_write(tmp_path):
    cp = Checkpoint(checkpoint_dir=str(tmp_path))
    cp.add("key1", "P-0001")
    cp.save()

    checkpoint_path = tmp_path / "checkpoint.json"
    assert checkpoint_path.exists()

    with open(checkpoint_path) as f:
        data = json.load(f)
    assert "key1" in data
    assert "P-0001" in data["key1"]
