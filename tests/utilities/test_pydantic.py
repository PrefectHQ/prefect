import json

import pydantic
import pytest

from prefect.utilities.pydantic import (
    PartialModel,
    add_type_dispatch,
    register_dispatch_type,
)


class SimplePydantic(pydantic.BaseModel):
    x: int
    y: int


class TestPartialModel:
    def test_init(self):
        p = PartialModel(SimplePydantic)
        assert p.model_cls == SimplePydantic
        assert p.fields == {}

    def test_init_with_fields(self):
        p = PartialModel(SimplePydantic, x=1, y=2)
        assert p.fields == {"x": 1, "y": 2}
        m = p.finalize()
        assert isinstance(m, SimplePydantic)
        assert m == SimplePydantic(x=1, y=2)

    def test_init_with_invalid_field(self):
        with pytest.raises(ValueError, match="Field 'z' is not present in the model"):
            PartialModel(SimplePydantic, x=1, z=2)

    def test_set_attribute(self):
        p = PartialModel(SimplePydantic)
        p.x = 1
        p.y = 2
        assert p.finalize() == SimplePydantic(x=1, y=2)

    def test_set_invalid_attribute(self):
        p = PartialModel(SimplePydantic)
        with pytest.raises(ValueError, match="Field 'z' is not present in the model"):
            p.z = 1

    def test_set_already_set_attribute(self):
        p = PartialModel(SimplePydantic, x=1)
        with pytest.raises(ValueError, match="Field 'x' has already been set"):
            p.x = 2

    def test_finalize_with_fields(self):
        p = PartialModel(SimplePydantic)
        m = p.finalize(x=1, y=2)
        assert isinstance(m, SimplePydantic)
        assert m == SimplePydantic(x=1, y=2)

    def test_finalize_with_invalid_field(self):
        p = PartialModel(SimplePydantic)
        with pytest.raises(ValueError, match="Field 'z' is not present in the model"):
            p.finalize(z=1)

    def test_finalize_with_already_set_field(self):
        p = PartialModel(SimplePydantic, x=1)
        with pytest.raises(ValueError, match="Field 'x' has already been set"):
            p.finalize(x=1)

    def test_finalize_with_missing_field(self):
        p = PartialModel(SimplePydantic, x=1)
        with pytest.raises(ValueError, match="validation error"):
            p.finalize()


# Capture exceptions during the declarion of these types and reraise as test setup
# errors rather than crashing the test suite on collection. These types must remain
# top-level so they are importable on dispatch.

TYPE_DISPATCH_EXCEPTION = None

try:

    @add_type_dispatch
    class Base(pydantic.BaseModel):
        pass

    class Foo(Base):
        pass

    class Bar(Base):
        pass

    @add_type_dispatch
    class BaseNamed(pydantic.BaseModel):
        __typename__: str

    @register_dispatch_type
    class FooNamed(BaseNamed):
        __typename__ = "foo"

    @register_dispatch_type
    class BarNamed(BaseNamed):
        __typename__ = "bar"

    class UnregisteredNamed(BaseNamed):
        pass  # Does not define a typename, is not registered

    @add_type_dispatch
    class SecondBaseNamed(pydantic.BaseModel):
        __typename__: str

    @register_dispatch_type
    class SecondFooNamed(SecondBaseNamed):
        __typename__ = "foo"

except Exception as exc:
    TYPE_DISPATCH_EXCEPTION = exc


@pytest.fixture
def check_base_for_dispatch_decoration():
    if TYPE_DISPATCH_EXCEPTION:
        raise RuntimeError(
            "Failed to create models for type dispatch tests"
        ) from TYPE_DISPATCH_EXCEPTION


class TestTypeDispatch:
    def test_add_type_dispatch(self):
        class Model(pydantic.BaseModel):
            pass

        add_type_dispatch(Model)

    def test_add_type_dispatch_fails_if_field_is_in_use(self):
        class Model(pydantic.BaseModel):
            type: str

        with pytest.raises(
            ValueError,
            match="Model class 'Model' includes reserved field 'type' used for dispatch",
        ):
            add_type_dispatch(Model)

    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_base_can_be_resolved_to_self(self):
        instance = Base()
        post_instance = Base.parse_raw(instance.json())
        assert type(post_instance) == Base

    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_subtype_can_be_resolved_with_base_parse(self):
        instance = Foo()
        post_instance = Base.parse_raw(instance.json())
        assert type(post_instance) == Foo
        assert isinstance(post_instance, Foo)
        assert isinstance(post_instance, Base)

    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_subtype_can_be_resolved_with_subtype_parse(self):
        instance = Foo()
        post_instance = Foo.parse_raw(instance.json())
        assert type(post_instance) == Foo
        assert isinstance(post_instance, Foo)
        assert isinstance(post_instance, Base)

    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_subtypes_are_unique(self):
        foo = Foo()
        bar = Bar()
        post_foo = Base.parse_raw(foo.json())
        post_bar = Base.parse_raw(bar.json())
        assert type(post_foo) != type(post_bar)


class TestNamedTypeDispatch:
    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_base_can_be_resolved_to_self(self):
        instance = BaseNamed()
        post_instance = BaseNamed.parse_raw(instance.json())
        assert type(post_instance) == BaseNamed

    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_subtype_dict_contains_type_name(self):
        assert FooNamed().dict().get("type") == "foo"

    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_subtype_json_contains_type_name(self):
        assert json.loads(FooNamed().json()).get("type") == "foo"

    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_subtype_can_be_resolved_with_base_parse(self):
        instance = FooNamed()
        post_instance = BaseNamed.parse_raw(instance.json())
        assert type(post_instance) == FooNamed
        assert isinstance(post_instance, FooNamed)
        assert isinstance(post_instance, BaseNamed)

    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_subtype_can_be_resolved_with_subtype_parse(self):
        instance = FooNamed()
        post_instance = FooNamed.parse_raw(instance.json())
        assert type(post_instance) == FooNamed
        assert isinstance(post_instance, FooNamed)
        assert isinstance(post_instance, BaseNamed)

    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_subtypes_are_unique(self):
        foo = FooNamed()
        bar = BarNamed()
        post_foo = BaseNamed.parse_raw(foo.json())
        post_bar = BaseNamed.parse_raw(bar.json())
        assert type(post_foo) != type(post_bar)

    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_registries_are_unique_per_base(self):
        foo = FooNamed()
        second_foo = SecondFooNamed()
        post_foo = BaseNamed.parse_raw(foo.json())
        post_second_foo = SecondBaseNamed.parse_raw(second_foo.json())
        assert type(post_foo) != type(post_second_foo)
        assert isinstance(post_foo, FooNamed)
        assert isinstance(post_second_foo, SecondFooNamed)

    @pytest.mark.usefixtures("check_base_for_dispatch_decoration")
    def test_unregistered_subtype_can_be_resolved_with_base_parse(self):
        """
        Falls back to using imports
        """
        instance = UnregisteredNamed()
        post_instance = BaseNamed.parse_raw(instance.json())
        assert type(post_instance) == UnregisteredNamed
        assert isinstance(post_instance, UnregisteredNamed)
        assert isinstance(post_instance, BaseNamed)

    def test_register_type_without_known_base(self):
        class DispatchlessBase(pydantic.BaseModel):
            pass

        with pytest.raises(
            KeyError,
            match="Base type 'DispatchlessBase' for model 'Foo' not found in registry",
        ):

            @register_dispatch_type
            class Foo(DispatchlessBase):
                pass

    def test_register_type_without_typename(self):
        with pytest.raises(
            ValueError,
            match="Model 'Foobar' does not define a value for '__typename__' which is requried for registry lookup",
        ):

            @register_dispatch_type
            class Foobar(BaseNamed):
                pass
