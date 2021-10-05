"""
Utilities for working with file systems
"""
import os
from contextlib import contextmanager


@contextmanager
def tmpchdir(path: str):
    """
    Change current-working directories for the duration of the context
    """
    if os.path.isfile(path):
        path = os.path.dirname(path)

    owd = os.getcwd()
    os.chdir(path)

    try:
        yield
    finally:
        os.chdir(owd)
