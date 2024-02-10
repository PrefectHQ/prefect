from shared_libs.bar import get_bar
from shared_libs.foo import get_foo

import prefect


@prefect.flow
def foobar():
    assert callable(get_foo), f"Expected callable, got {get_foo!r}"
    assert callable(get_bar), f"Expected callable, got {get_bar!r}"
    return get_foo() + get_bar()
