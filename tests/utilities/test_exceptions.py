import sys

import pytest

from prefect.exceptions import _collapse_excgroups

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="`BaseExceptionGroup` is available in Python 3.11+",
)


class TestExceptionGroup:
    def test_no_exception(self):
        with _collapse_excgroups():
            pass

    def test_regular_exception(self):
        with pytest.raises(ValueError):
            with _collapse_excgroups():
                raise ValueError("A regular exception")

    def test_single_exception_group(self):
        with pytest.raises(ValueError):
            with _collapse_excgroups():
                raise BaseExceptionGroup("Single", [ValueError("Wrapped exception")])

    def test_multi_exception_group(self):
        with pytest.raises(BaseExceptionGroup) as excinfo:
            with _collapse_excgroups():
                raise BaseExceptionGroup(
                    "Multiple", [ValueError("First"), TypeError("Second")]
                )

        assert len(excinfo.value.exceptions) == 2
