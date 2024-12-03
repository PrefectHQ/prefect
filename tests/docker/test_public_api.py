from unittest import TestCase
from warnings import warn

from prefect import flow


def function_that_warns():
    warn("Test warning!")


@flow
def my_flow():
    function_that_warns()


class TestWarnings(TestCase):
    """this is a regression test for https://github.com/PrefectHQ/prefect/issues/16171"""

    def test_warning(self):
        with self.assertWarns(UserWarning):
            function_that_warns()
