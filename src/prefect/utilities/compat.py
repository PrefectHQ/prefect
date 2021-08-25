"""
Utilities for Python version compatibility
"""
import sys

if sys.version_info < (3, 8):
    from mock import AsyncMock
else:
    from unittest.mock import AsyncMock
