from __future__ import annotations

import sys

import pytest

from prefect import flow


@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires python 3.10 or higher")
def test_class_destringify():
    class Test:
        pass

    @flow
    def foo(x: Test):
        print(x)

    assert foo
