from __future__ import annotations
import sys

import pytest

from prefect import flow

pytestmark = pytest.mark.skipif(sys.version_info < (3, 9))

def test_destringify_class():
    class Test:
        pass

    @flow
    def foo(x: Test):
        print(x)
