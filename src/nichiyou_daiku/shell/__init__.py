"""Shell layer for nichiyou-daiku - handles external integrations and I/O.

This package contains modules that interact with external systems,
following the functional core, imperative shell pattern.
"""

from .build123d_export import assembly_to_build123d

__all__ = ["assembly_to_build123d"]