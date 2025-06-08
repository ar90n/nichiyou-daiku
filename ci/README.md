# CI/CD Pipeline

This directory contains the CI/CD pipeline configuration for nichiyou-daiku.

## Structure

- `dagger_pipeline.py` - Main Dagger pipeline implementation
- `requirements.txt` - CI-specific dependencies

## Running the Pipeline

### Local Development

```bash
# Quick test (Python 3.11 only)
python ci/dagger_pipeline.py

# Test multiple Python versions
python ci/dagger_pipeline.py "3.11,3.12"
```

### GitHub Actions

The pipeline is automatically triggered by GitHub Actions on:
- Push to main branch
- Pull requests
- Manual workflow dispatch

## Pipeline Stages

1. **Test Pipeline**
   - Runs docstring tests
   - Runs pytest with coverage
   - Enforces 90% minimum coverage

2. **Lint Pipeline**
   - Code formatting check with black
   - Linting with ruff
   - Type checking with mypy

3. **Build Pipeline**
   - Builds distribution packages
   - Exports artifacts

## Configuration

The pipeline supports multiple Python versions and can be configured by passing a comma-separated list of versions.