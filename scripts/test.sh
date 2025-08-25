#!/bin/bash

# Test script for Python backend with correct PYTHONPATH

set -e

echo "🧪 Running Python tests..."

# Navigate to backend directory
cd backend

# Set PYTHONPATH to include src and src/services directories
export PYTHONPATH="src:src/services:$PYTHONPATH"

# Run pytest with verbose output
echo "Running pytest with PYTHONPATH: $PYTHONPATH"
python -m pytest -v

echo "✅ All tests passed!"
