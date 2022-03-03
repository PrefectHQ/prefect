import warnings

import pytest

from prefect.utilities.testing import assert_does_not_warn


def test_assert_does_not_warn_no_warning():
    with assert_does_not_warn():
        pass


def test_assert_does_not_warn_does_not_capture_exceptions():
    with pytest.raises(ValueError):
        with assert_does_not_warn():
            raise ValueError()


def test_assert_does_not_warn_raises_assertion_error():
    with pytest.raises(AssertionError, match="Warning was raised"):
        with assert_does_not_warn():
            warnings.warn("Test")
