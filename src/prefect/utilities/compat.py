"""
Utilities for Python version compatibility
"""
import sys

if sys.version_info < (3, 8):
    from asyncmock import AsyncMock
else:
    from unittest.mock import AsyncMock
