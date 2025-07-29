"""DSL (Domain Specific Language) module for nichiyou-daiku.

This module provides a Cypher-like graph definition language for
defining furniture models in a more concise and readable way.
"""

from nichiyou_daiku.dsl.exceptions import (
    DSLError,
    DSLSemanticError,
    DSLSyntaxError,
    DSLValidationError,
)
from nichiyou_daiku.dsl.parser import parse_dsl

__all__ = [
    "parse_dsl",
    "DSLError",
    "DSLSyntaxError",
    "DSLSemanticError",
    "DSLValidationError",
]
