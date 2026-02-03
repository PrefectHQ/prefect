"""
Core types for SDK generation.

This module contains the data classes and exceptions used across the SDK
generation modules.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversionContext:
    """Context for schema conversion, tracking definitions and visited refs."""

    definitions: dict[str, Any] = field(default_factory=dict)
    """Schema definitions (from 'definitions' or '$defs' key)."""

    visited_refs: set[str] = field(default_factory=set)
    """Set of $ref paths currently being resolved (for circular detection)."""

    conversion_warnings: list[str] = field(default_factory=list)
    """Warnings accumulated during conversion."""


class CircularReferenceError(Exception):
    """Raised when a circular $ref is detected in the schema."""

    pass


@dataclass
class FieldInfo:
    """Information about a TypedDict field."""

    name: str
    """The field name."""

    python_type: str
    """The Python type annotation string."""

    required: bool
    """Whether the field is required."""

    default: Any | None = None
    """The default value, if any."""

    has_default: bool = False
    """Whether a default value is present."""

    description: str | None = None
    """Field description from schema."""
