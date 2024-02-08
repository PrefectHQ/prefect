from .shared_libs import get_bar, get_foo


def foobar():
    assert callable(get_foo), f"Expected callable, got {get_foo!r}"
    assert callable(get_bar), f"Expected callable, got {get_bar!r}"
    return get_foo() + get_bar()
