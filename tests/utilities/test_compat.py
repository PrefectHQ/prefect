from __future__ import annotations
import sys

import pytest

from prefect import flow

@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires python 3.10 or higher")
def test_destringify_class():
    class Test:
        pass

    @flow
    def foo(x: Test):
        print(x)

    assert foo

@pytest.mark.skipif(sys.version_info >= (3, 10), reason="requires python 3.9 or lower")
def test_destringify_class_old():
    with pytest.raises(ValueError):
        class Test:
            pass
    
        @flow
        def foo(x: Test):
            print(x)
    
        assert foo
