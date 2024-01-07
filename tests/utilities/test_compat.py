from __future__ import annotations
from prefect import flow

def test_destringify_class():
    class Test:
        pass

    @flow
    def foo(x: Test):
        print(x)
