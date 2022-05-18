import datetime
from uuid import UUID, uuid4

import pendulum
import pydantic
import pytest

from prefect.orion.utilities.schemas import (
    IDBaseModel,
    ORMBaseModel,
    PrefectBaseModel,
    pydantic_subclass,
)
from prefect.testing.utilities import assert_does_not_warn


class TestExtraForbidden:
    def test_extra_attributes_are_forbidden_during_unit_tests(self):
        class Model(PrefectBaseModel):
            x: int

        with pytest.raises(pydantic.ValidationError):
            Model(x=1, y=2)


class TestPydanticSubclass:
    class Parent(pydantic.BaseModel):
        class Config:
            extra = "forbid"

        x: int
        y: int = 2

    def test_subclass_is_a_subclass(self):
        Child = pydantic_subclass(self.Parent)
        assert issubclass(Child, self.Parent)

    def test_parent_is_unchanged(self):
        original_fields = self.Parent.__fields__.copy()
        Child = pydantic_subclass(self.Parent)
        assert self.Parent.__fields__ == original_fields

    def test_default_subclass_name(self):
        Child = pydantic_subclass(self.Parent)
        assert Child.__name__ == "Parent"

    def test_pydantic_does_not_issue_warning_when_creating_subclass(self):
        with assert_does_not_warn():
            pydantic_subclass(self.Parent)

    def test_subclass_name(self):
        Child = pydantic_subclass(self.Parent, name="Child")
        assert Child.__name__ == "Child"

    def test_subclass_fields(self):
        Child = pydantic_subclass(self.Parent, name="Child")
        c = Child(x=1)
        assert c.x == 1
        assert c.y == 2

    def test_subclass_include_fields(self):
        Child = pydantic_subclass(self.Parent, name="Child", include_fields=["y"])
        c = Child(y=1)
        assert c.y == 1
        assert not hasattr(c, "x")

    def test_subclass_exclude_fields(self):
        Child = pydantic_subclass(self.Parent, name="Child", exclude_fields=["x"])
        c = Child(y=1)
        assert c.y == 1
        assert not hasattr(c, "x")

    def test_subclass_include_invalid_fields(self):
        with pytest.raises(ValueError, match="(fields not found on base class)"):
            pydantic_subclass(self.Parent, name="Child", include_fields=["z"])

    def test_subclass_exclude_invalid_fields(self):
        with pytest.raises(ValueError, match="(fields not found on base class)"):
            pydantic_subclass(self.Parent, name="Child", exclude_fields=["z"])

    def test_extend_subclass(self):
        class Child(pydantic_subclass(self.Parent, include_fields=["y"])):
            z: int

        c = Child(y=5, z=10)
        assert c.y == 5
        assert c.z == 10

    def test_extend_subclass_respects_config(self):
        class Child(pydantic_subclass(self.Parent, include_fields=["y"])):
            z: int

        with pytest.raises(
            pydantic.ValidationError, match="(extra fields not permitted)"
        ):
            Child(y=5, z=10, q=17)

    def test_validators_for_missing_fields_are_ok(self):
        class Parent2(pydantic.BaseModel):

            x: int
            y: int = 2

            @pydantic.validator("x")
            def x_greater_10(cls, v):
                if v <= 10:
                    raise ValueError()
                return v

        # child has a validator for a field that it doesn't include
        # and no error is raised during creation
        child = pydantic_subclass(Parent2, include_fields=["y"])
        with pytest.raises(ValueError):
            child.x_greater_10(5)


class TestClassmethodSubclass:
    class Parent(PrefectBaseModel):
        x: int
        y: int

    def test_classmethod_creates_subclass(self):
        Child = self.Parent.subclass("Child", include_fields=["x"])
        assert Child.__name__ == "Child"
        assert Child(x=1)
        assert not hasattr(Child(x=1), "y")


class TestNestedDict:
    @pytest.fixture()
    def nested(self):
        class Child(pydantic.BaseModel):
            z: int

        class Parent(PrefectBaseModel):
            x: int
            y: Child

        return Parent(x=1, y=Child(z=2))

    def test_full_dict(self, nested):
        assert nested.dict() == {"x": 1, "y": {"z": 2}}
        assert isinstance(nested.dict()["y"], dict)

    def test_simple_dict(self, nested):
        assert dict(nested) == {"x": 1, "y": nested.y}
        assert isinstance(dict(nested)["y"], pydantic.BaseModel)

    def test_shallow_true(self, nested):
        assert dict(nested) == nested.dict(shallow=True)
        assert isinstance(nested.dict(shallow=True)["y"], pydantic.BaseModel)

    def test_kwargs_respected(self, nested):
        deep = nested.dict(include={"y"})
        shallow = nested.dict(include={"y"}, shallow=True)
        assert isinstance(deep["y"], dict)
        assert isinstance(shallow["y"], pydantic.BaseModel)
        assert deep == shallow == {"y": {"z": 2}}


class TestJsonCompatibleDict:
    class Model(PrefectBaseModel):

        x: UUID
        y: datetime.datetime

    @pytest.fixture()
    def nested(self):
        class Child(pydantic.BaseModel):
            z: UUID

        class Parent(PrefectBaseModel):
            x: UUID
            y: Child

        return Parent(x=uuid4(), y=Child(z=uuid4()))

    def test_json_compatible_and_nested_errors(self):
        model = self.Model(x=uuid4(), y=pendulum.now())
        with pytest.raises(ValueError, match="(only be applied to the entire object)"):
            model.dict(json_compatible=True, shallow=True)

    def test_json_compatible(self):
        model = self.Model(x=uuid4(), y=pendulum.now())
        d1 = model.dict()
        d2 = model.dict(json_compatible=True)

        assert isinstance(d1["x"], UUID) and d1["x"] == model.x
        assert isinstance(d2["x"], str) and d2["x"] == str(model.x)

        assert isinstance(d1["y"], datetime.datetime) and d1["y"] == model.y
        assert isinstance(d2["y"], str) and d2["y"] == str(model.y)

    def test_json_applies_to_nested(self, nested):
        d1 = nested.dict(json_compatible=True)
        assert isinstance(d1["x"], str) and d1["x"] == str(nested.x)
        assert isinstance(d1["y"]["z"], str) and d1["y"]["z"] == str(nested.y.z)


class CopyOnValidationChild(ORMBaseModel):
    x: int


class CopyOnValidationParent(ORMBaseModel):
    x: int
    child: CopyOnValidationChild


def test_assignment_preserves_ids():
    child_id = uuid4()
    parent_id = uuid4()
    child = CopyOnValidationChild(id=child_id, x=1)
    parent = CopyOnValidationParent(id=parent_id, x=1, child=child)
    assert child.id == child_id
    assert parent.id == parent_id
    # without the copy_on_model_validation = False flag
    # this test would fail
    assert parent.child.id == child_id


class TestEqualityExcludedFields:
    def test_idbasemodel_equality(self):
        class X(IDBaseModel):
            x: int

        assert X(id=uuid4(), x=1) == X(id=uuid4(), x=1)
        assert X(id=uuid4(), x=1) != X(id=uuid4(), x=2)

    def test_ormbasemodel_equality(self):
        class X(ORMBaseModel):
            x: int

        x1 = X(id=uuid4(), created=pendulum.now(), x=1)
        x2 = X(id=uuid4(), created=pendulum.now().add(hours=1), x=1)
        x3 = X(id=uuid4(), created=pendulum.now().subtract(hours=1), x=2)
        assert x1 == x2
        assert x1.created != x2.created
        assert x1 != x3

    def test_mixed_model_equality(self):
        class X(IDBaseModel):
            val: int

        class Y(ORMBaseModel):
            val: int

        class Z(PrefectBaseModel):
            val: int

        class A(pydantic.BaseModel):
            val: int

        x = X(val=1)
        y = Y(val=1)
        z = Z(val=1)
        a = A(val=1)

        assert x == y == z == a
        assert x.id != y.id

    def test_right_equality_fails(self):
        class X(IDBaseModel):
            val: int

        class Y(pydantic.BaseModel):
            val: int

        assert X(val=1) == Y(val=1)
        # if the PBM is the RH operand, the equality check fails
        # because the Pydantic logic of using every field is applied
        assert Y(val=1) != X(val=1)
