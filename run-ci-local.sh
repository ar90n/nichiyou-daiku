#!/bin/bash
# Run CI pipeline locally using Dagger

set -e

echo "🚀 Running local Quality Assurance pipeline with Dagger..."

# Check if Dagger CLI dependencies are installed
if ! python -c "import dagger" 2>/dev/null; then
    echo "📦 Installing Dagger dependencies..."
    pip install -r ci/requirements.txt
fi

# Run CI for Python 3.13 only by default (faster for local testing)
PYTHON_VERSIONS="${1:-3.13}"

echo "🐍 Testing with Python version(s): $PYTHON_VERSIONS"

# Run the Dagger CI pipeline
python ci/dagger_pipeline.py "$PYTHON_VERSIONS"

echo "✅ Local QA pipeline completed!"