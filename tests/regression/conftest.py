"""Pytest configuration for regression tests."""


def pytest_configure(config):
    """Register custom markers for regression tests."""
    config.addinivalue_line(
        "markers",
        "regression: Visual regression tests (requires viz and test-visual extras)",
    )
