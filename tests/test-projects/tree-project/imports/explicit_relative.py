from ..shared_libs.bar import bar
from ..shared_libs.foo import foo


def foobar():
    return foo() + bar()
