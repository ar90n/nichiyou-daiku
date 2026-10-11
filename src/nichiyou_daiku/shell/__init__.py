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

# build123d_export imports build123d lazily, so it is always importable;
# only advertise its functions when build123d is installed.
from .build123d_export import HAS_BUILD123D

if HAS_BUILD123D:
    from .build123d_export import (  # noqa: F401
        assembly_to_build123d,
        check_overlap,
        find_joint_mismatches,
    )

    __all__ += ["assembly_to_build123d", "check_overlap", "find_joint_mismatches"]
