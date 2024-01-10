from __future__ import annotations

import sys

import pytest

from prefect import flow


class Test:
    pass


@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires python 3.10 or higher")
def test_class_destringify():

    @flow
    def foo(x: Test):
        return

    assert foo
