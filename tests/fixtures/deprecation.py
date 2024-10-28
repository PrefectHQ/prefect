"""
Fixture to ignore our own deprecation warnings.

Deprecations should be specifically tested to ensure they are emitted as expected.
"""

import warnings
from datetime import datetime

import pytest

from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning


def should_reraise_warning(warning):
    """
    Determine if a deprecation warning should be reraised based on the date.

    Deprecation warnings that have passed the date threshold should be reraised to
    ensure the deprecated code paths are removed.
    """
    message = str(warning.message)
    try:
        # Extract the date from the new message format
        date_str = message.split("not be available in new releases after ")[1].strip(
            "."
        )
        # Parse the date
        deprecation_date = datetime.strptime(date_str, "%b %Y").date().replace(day=1)

        # Check if the current date is after the start of the month following the deprecation date
        current_date = datetime.now().date().replace(day=1)
        return current_date > deprecation_date
    except Exception:
        # Reraise in cases of failure
        return True


@pytest.fixture
def ignore_prefect_deprecation_warnings():
    """
    Ignore deprecation warnings from the agent module to avoid
    test failures.
    """
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("ignore", category=PrefectDeprecationWarning)
        yield
        for warning in w:
            if isinstance(warning.message, PrefectDeprecationWarning):
                if should_reraise_warning(warning):
                    warnings.warn(warning.message, warning.category, stacklevel=2)
