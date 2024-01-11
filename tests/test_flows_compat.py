from __future__ import annotations

from typing import TYPE_CHECKING

from prefect import flow

if TYPE_CHECKING:

    class Test2:
        pass


class Test:
    pass


def test_class_arg():
    @flow
    def foo(x: Test):
        return

    assert foo


def test_class_arg2():
    @flow
    def foo(x: Test2):
        return

    assert foo
