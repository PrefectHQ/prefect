"""
Fixture to ignore our own deprecation warnings.

Deprecations should be specifically tested to ensure they are emitted as expected.
"""

import warnings

import pytest

from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning


@pytest.fixture(autouse=True)
def ignore_prefect_deprecation_warnings():
    """
    Ignore deprecation warnings from the agent module to avoid
    test failures.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=PrefectDeprecationWarning)
        yield
