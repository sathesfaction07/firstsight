#!/usr/bin/env bash
set -euo pipefail

echo "=== SerpHarvest Setup Script ==="
echo

OS_TYPE=$(uname -s)
echo "Detected OS: $OS_TYPE"

find_python() {
    for cmd in python3.12 python3.11 python3; do
        if command -v "$cmd" >/dev/null 2>&1; then
            version=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
            major=$(echo "$version" | cut -d. -f1)
            minor=$(echo "$version" | cut -d. -f2)
            if [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

echo "Looking for Python >=3.11..."
if PYTHON_CMD=$(find_python); then
    echo "✓ Found: $PYTHON_CMD ($($PYTHON_CMD --version))"
else
    echo "✗ Python >=3.11 not found"
    echo
    echo "Install instructions:"
    if [ "$OS_TYPE" = "Darwin" ]; then
        echo "  brew install python@3.11"
    elif [ "$OS_TYPE" = "Linux" ]; then
        echo "  sudo apt-get install python3.11 python3.11-venv"
    fi
    exit 1
fi

VENV_DIR=".venv"
if [ -d "$VENV_DIR" ]; then
    echo "✓ Virtual environment exists"
else
    echo "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
fi

echo "Activating virtual environment..."
if [ "$OS_TYPE" = "Darwin" ] || [ "$OS_TYPE" = "Linux" ]; then
    source "$VENV_DIR/bin/activate"
else
    echo "✗ Unsupported OS for auto-activation"
    exit 1
fi

echo "Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -e ".[dev,dynamodb]"
echo "✓ Dependencies installed"

echo "Installing Playwright browsers..."
playwright install firefox
echo "✓ Playwright browsers installed"

echo
echo "=== Verification Tests ==="
echo

echo "1. Verifying imports..."
"$PYTHON_CMD" -c "
from serp_harvest import __version__
from serp_harvest.config import Settings
from serp_harvest.core import Checkpoint, extract_product_ids
from serp_harvest.sinks import get_sink
print('✓ All imports successful')
"

echo "2. Verifying Playwright can launch..."
"$PYTHON_CMD" -c "
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        await browser.close()
    print('✓ Playwright browser launched successfully')

asyncio.run(test())
"

echo "3. Verifying checkpoint persistence..."
"$PYTHON_CMD" -c "
import tempfile
import os
from serp_harvest.core.checkpoint import Checkpoint

with tempfile.TemporaryDirectory() as tmpdir:
    cp = Checkpoint(tmpdir)
    cp.add('test_key', 'P-0001')
    cp.save()
    
    cp2 = Checkpoint(tmpdir)
    cp2.load()
    assert cp2.is_completed('test_key', 'P-0001')
    print('✓ Checkpoint save/load works')
"

echo "4. Verifying local sink..."
"$PYTHON_CMD" -c "
import tempfile
import pandas as pd
from serp_harvest.sinks.local import LocalSink

with tempfile.TemporaryDirectory() as tmpdir:
    sink = LocalSink(output_path=f'{tmpdir}/test.csv')
    df = pd.DataFrame([{'product_ids': 'P-0001', 'keyword': 'test', 'region': 'US'}])
    written, skipped = sink.write(df, 'test_run')
    assert written == 1
    print('✓ Local sink writes CSV')
"

echo
echo "=== Running Test Suite ==="
echo

pytest -q --tb=short

echo
echo "=== Setup Complete ==="
echo
echo "Usage:"
echo "  source .venv/bin/activate"
echo "  serp-harvest probe                         # Test browser launch"
echo "  serp-harvest plan data/sample_keywords.csv # Estimate harvest"
echo "  serp-harvest run data/sample_keywords.csv  # Run harvest"
echo
