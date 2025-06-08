#!/bin/bash
# Run CI pipeline locally using Dagger

set -e

echo "🚀 Running local CI pipeline with Dagger..."

# Check if Dagger CLI dependencies are installed
if ! python -c "import dagger" 2>/dev/null; then
    echo "📦 Installing Dagger dependencies..."
    pip install -r requirements-ci.txt
fi

# Run CI for Python 3.11 only by default (faster for local testing)
PYTHON_VERSIONS="${1:-3.11}"

echo "🐍 Testing with Python version(s): $PYTHON_VERSIONS"

# Run the Dagger CI pipeline
python ci.py "$PYTHON_VERSIONS"

echo "✅ Local CI run completed!"