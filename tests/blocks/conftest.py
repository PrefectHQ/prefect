"""
Fixtures for tests/blocks/ module.

Provides utilities for generating unique block type slugs to prevent
conflicts when running tests in parallel with modules excluded from clear_db.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest


@pytest.fixture
def unique_slug_prefix() -> str:
    """Returns a unique prefix for this test's block slugs."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
def unique_block_slug(unique_slug_prefix: str) -> Callable[[str], str]:
    """
    Returns a function that generates unique block type slugs.

    Usage:
        def test_something(unique_block_slug):
            class MyBlock(Block):
                _block_type_slug = unique_block_slug("myblock")
                ...
    """

    def _make_slug(base_name: str) -> str:
        return f"{base_name}-{unique_slug_prefix}"

    return _make_slug
