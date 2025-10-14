"""Shell layer for nichiyou-daiku - handles external integrations and I/O.

This package contains modules that interact with external systems,
following the functional core, imperative shell pattern.
"""

# Always available report generation and resource extraction
from .report_generator import generate_markdown_report  # noqa: F401
from .resources import (  # noqa: F401
    PieceResource,
    ResourceSummary,
    AnchorInfo,
    extract_resources,
)

__all__ = [
    "generate_markdown_report",
    "extract_resources",
    "PieceResource",
    "ResourceSummary",
    "AnchorInfo",
]

# Only expose assembly_to_build123d if build123d is available
try:
    from .build123d_export import HAS_BUILD123D

    if HAS_BUILD123D:
        from .build123d_export import assembly_to_build123d  # noqa: F401

        __all__.append("assembly_to_build123d")
except ImportError:
    pass
