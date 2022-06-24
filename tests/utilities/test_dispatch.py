import pytest

from prefect.utilities.dispatch import (
    _TYPE_REGISTRIES,
    get_dispatch_key,
    lookup_type,
    register_base_type,
    register_type,
)


@pytest.fixture(autouse=True)
def reset_dispatch_registry():
    yield

    _TYPE_REGISTRIES.clear()


def test_register_base_type():
    @register_base_type
    class Foo:
        pass

    assert Foo in _TYPE_REGISTRIES


def test_register_base_type_with_key():
    @register_base_type
    class Foo:
        __dispatch_key__ = "foo"

    assert lookup_type(Foo, "foo") is Foo
    assert Foo in _TYPE_REGISTRIES


def test_register_base_type_can_be_called_more_than_once():
    @register_base_type
    class Foo:
        pass

    assert Foo in _TYPE_REGISTRIES
    _TYPE_REGISTRIES[Foo] = "test"

    register_base_type(Foo)

    assert _TYPE_REGISTRIES[Foo] == "test"


def test_register_base_type_with_invalid_dispatch_key():
    with pytest.raises(
        TypeError,
        match="Type 'Parent' has a '__dispatch_key__' of type int but a type of 'str' is required.",
    ):

        @register_base_type
        class Parent:
            __dispatch_key__ = 1


def test_register_type():
    @register_base_type
    class Parent:
        pass

    @register_type
    class Child(Parent):
        __dispatch_key__ = "child"

    assert lookup_type(Parent, "child") is Child


def test_register_type_with_invalid_dispatch_key():
    @register_base_type
    class Parent:
        pass

    with pytest.raises(
        TypeError,
        match="Type 'Child' has a '__dispatch_key__' of type int but a type of 'str' is required.",
    ):

        @register_type
        class Child(Parent):
            __dispatch_key__ = 1


def test_register_type_with_dispatch_key_collission():
    @register_base_type
    class Parent:
        pass

    @register_type
    class Child(Parent):
        __dispatch_key__ = "a"

    with pytest.warns(
        UserWarning,
        match="Type 'OtherChild' has key 'a' that matches existing registered type 'Child'. The existing type will be overridden.",
    ):

        @register_type
        class OtherChild(Parent):
            __dispatch_key__ = "a"

    assert lookup_type(Parent, "a") == OtherChild


def test_register_type_with_unregistered_parent():
    class Parent:
        pass

    with pytest.raises(
        ValueError, match="No registry found for type 'Child' with bases 'Parent'."
    ):

        @register_type
        class Child(Parent):
            __dispatch_key__ = "child"


def test_register_type_with_unregistered_parent_shows_known_bases():
    class Parent:
        pass

    @register_base_type
    class RegisteredBase:
        pass

    with pytest.raises(
        ValueError,
        match="Did you mean to inherit from one of the following known types: 'RegisteredBase'.",
    ):

        @register_type
        class Child(Parent):
            __dispatch_key__ = "child"


def test_register_type_with_registered_grandparent():
    @register_base_type
    class Grandparent:
        pass

    class Parent(Grandparent):
        pass

    @register_type
    class Child(Parent):
        __dispatch_key__ = "child"

    assert lookup_type(Grandparent, "child") is Child
    assert lookup_type(Parent, "child") is Child


def test_lookup_type_with_unknown_dispatch_key():
    @register_base_type
    class Parent:
        pass

    @register_type
    class Child(Parent):
        __dispatch_key__ = "child"

    with pytest.raises(
        KeyError, match="No class found in registry for dispatch key 'foo'"
    ):
        lookup_type(Parent, "foo")


def test_get_dispatch_key_on_class():
    class Foo:
        __dispatch_key__ = "foo"

    assert get_dispatch_key(Foo) == "foo"


def test_get_dispatch_key_on_instance():
    class Foo:
        __dispatch_key__ = "foo"

    assert get_dispatch_key(Foo()) == "foo"


def test_get_dispatch_key_callable():
    class Foo:
        @classmethod
        def __dispatch_key__(cls):
            return "foo"

    assert get_dispatch_key(Foo) == "foo"


def test_get_dispatch_key_not_found_on_class():
    class Foo:
        pass

    with pytest.raises(
        ValueError,
        match="Type 'Foo' does not define a value for '__dispatch_key__' which is required for registry lookup.",
    ):
        get_dispatch_key(Foo)


def test_get_dispatch_key_not_found_on_instance():
    class Foo:
        pass

    with pytest.raises(
        ValueError,
        match="Type 'Foo' does not define a value for '__dispatch_key__' which is required for registry lookup.",
    ):
        get_dispatch_key(Foo())


def test_get_dispatch_key_not_a_string():
    class Foo:
        __dispatch_key__ = 1

    with pytest.raises(
        TypeError,
        match="Type 'Foo' has a '__dispatch_key__' of type int but a type of 'str' is required.",
    ):
        get_dispatch_key(Foo)


def test_get_dispatch_key_not_a_string_from_callable():
    class Foo:
        @classmethod
        def __dispatch_key__(cls):
            return 1

    with pytest.raises(
        TypeError,
        match="Type 'Foo' has a '__dispatch_key__' of type int but a type of 'str' is required.",
    ):
        get_dispatch_key(Foo)
