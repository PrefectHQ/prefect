""""
Internal utilities for tests.
"""
import os
import sys
from contextlib import contextmanager

import prefect.context
import prefect.settings


def exceptions_equal(a, b):
    """
    Exceptions cannot be compared by `==`. They can be compared using `is` but this
    will fail if the exception is serialized/deserialized so this utility does its
    best to assert equality using the type and args used to initialize the exception
    """
    if a == b:
        return True
    return type(a) == type(b) and getattr(a, "args", None) == getattr(b, "args", None)


# AsyncMock has a new import path in Python 3.8+

if sys.version_info < (3, 8):
    # https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock
    from mock import AsyncMock
else:
    from unittest.mock import AsyncMock


@contextmanager
def temporary_settings(**kwargs):
    """
    Temporarily override setting values.

    This will _not_ mutate values that have been already been accessed at module
    load time.

    This function should only be used for testing.

    Example:
        >>> import prefect.settings
        >>> with temporary_settings(PREFECT_ORION_HOST="foo"):
        >>>    assert prefect.settings.from_env().orion_host == "foo"
        >>> assert prefect.settings.from_env().orion_host is None
    """
    old_env = os.environ.copy()
    old_settings = prefect.settings.from_env()

    try:
        for setting in kwargs:
            os.environ[setting] = str(kwargs[setting])

        assert old_env != os.environ, "Environment did not change"
        new_settings = prefect.settings.from_env()
        assert new_settings != old_settings, "Temporary settings did not change values"
        yield new_settings

    finally:
        for setting in kwargs:
            if old_env.get(setting):
                os.environ[setting] = old_env[setting]
            else:
                os.environ.pop(setting, None)
