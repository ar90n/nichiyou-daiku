"""Shell layer for nichiyou-daiku - handles external integrations and I/O.

This package contains modules that interact with external systems,
following the functional core, imperative shell pattern.
"""

# Only expose assembly_to_build123d if build123d is available
__all__ = []

try:
    from .build123d_export import assembly_to_build123d, HAS_BUILD123D
    if HAS_BUILD123D:
        __all__.append("assembly_to_build123d")
except ImportError:
    pass