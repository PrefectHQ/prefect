from typing import Optional

import pydantic
import pytest

from prefect._internal.compatibility.deprecated import (
    PrefectDeprecationWarning,
    deprecated_callable,
    deprecated_class,
    deprecated_field,
    deprecated_parameter,
    generate_deprecation_message,
)


def test_generate_deprecation_message():
    assert (
        generate_deprecation_message(
            "test name", start_date="Jan 2022", help="test help"
        )
        == "test name has been deprecated. It will not be available in new releases after Jul 2022."
        " test help"
    )


def test_generate_deprecation_message_when():
    assert (
        generate_deprecation_message(
            "test name", start_date="Jan 2022", help="test help", when="testing"
        )
        == "test name has been deprecated when testing. It will not be available in new releases after"
        " Jul 2022. test help"
    )


def test_generate_deprecation_message_invalid_start_date():
    with pytest.raises(ValueError, match="String does not match format MMM YYYY"):
        generate_deprecation_message("test name", start_date="2022")


def test_generate_deprecation_message_end_date():
    assert (
        generate_deprecation_message("test name", end_date="Dec 2023")
        == "test name has been deprecated. It will not be available in new releases after Dec 2023."
    )


def test_generate_deprecation_message_invalid_end_date():
    with pytest.raises(ValueError, match="String does not match format MMM YYYY"):
        generate_deprecation_message("test name", end_date="Foobar")


def test_generate_deprecation_message_no_start_or_end_date():
    with pytest.raises(
        ValueError, match="A start date is required if an end date is not provided"
    ):
        generate_deprecation_message("test name")


def test_deprecated_callable():
    @deprecated_callable(start_date="Jan 2022", help="test help")
    def foo():
        pass

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "test_deprecated.test_deprecated_callable.<locals>.foo has been deprecated."
            " It will not be available in new releases after Jul 2022. test help"
        ),
    ):
        foo()


def test_deprecated_parameter():
    @deprecated_parameter(name="y", start_date="Jan 2022", help="test help")
    def foo(
        x=None,
        y=None,
    ):
        pass

    # Does not warn
    foo(x=0)
    foo()

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "The parameter 'y' for 'foo' has been deprecated. It will not be available in new releases"
            " after Jul 2022. test help"
        ),
    ):
        foo(y=10)

    # positional
    with pytest.warns(PrefectDeprecationWarning):
        foo(0, 10)


def test_deprecated_parameter_when():
    @deprecated_parameter(
        name="x", when=lambda x: x > 5, start_date="Jan 2022", help="test help"
    )
    def foo(x: int = 0):
        pass

    # Does not warn
    foo(x=0)
    foo()

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "The parameter 'x' for 'foo' has been deprecated. It will not be available in new releases"
            " after Jul 2022. test help"
        ),
    ):
        foo(10)

    # positional
    with pytest.warns(PrefectDeprecationWarning):
        foo(10)

    # kwarg
    with pytest.warns(PrefectDeprecationWarning):
        foo(x=10)


def test_deprecated_field():
    @deprecated_field(name="y", start_date="Jan 2022", help="test help")
    class Foo(pydantic.BaseModel):
        x: Optional[int] = None
        y: Optional[int] = None

    # Does not warn
    Foo(x=0)
    Foo()

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "The field 'y' in 'Foo' has been deprecated. It will not be available in new releases after"
            " Jul 2022. test help"
        ),
    ):
        Foo(y=10)

    assert Foo.model_fields["y"].json_schema_extra["deprecated"] is True


def test_deprecated_field_when():
    @deprecated_field(
        name="x", when=lambda x: x > 5, start_date="Jan 2022", help="test help"
    )
    class Foo(pydantic.BaseModel):
        x: Optional[int] = None

    # Does not warn
    Foo(x=0)
    Foo()

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "The field 'x' in 'Foo' has been deprecated. It will not be available in new releases after"
            " Jul 2022. test help"
        ),
    ):
        Foo(x=10)

    assert Foo.model_fields["x"].json_schema_extra["deprecated"] is True


def test_deprecated_class():
    @deprecated_class(start_date="Jan 2022", help="test help")
    class MyClass:
        def __init__(self):
            pass

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "MyClass has been deprecated. It will not be available in new releases after Jul 2022."
            " test help"
        ),
    ):
        obj = MyClass()
        assert isinstance(obj, MyClass)
