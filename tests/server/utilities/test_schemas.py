import datetime
import importlib
import os
from contextlib import contextmanager
from typing import Any, Generator, Optional, Union
from uuid import uuid4

import pydantic
import pytest

from prefect.server.utilities.schemas import (
    IDBaseModel,
    ORMBaseModel,
    PrefectBaseModel,
    PrefectDescriptorBase,
)
from prefect.types._datetime import now


@contextmanager
def reload_prefect_base_model(
    test_mode_value: Optional[str],
) -> Generator[type[PrefectBaseModel], None, None]:
    import prefect.server.utilities.schemas.bases

    original_base_model = prefect.server.utilities.schemas.bases.PrefectBaseModel
    original_environment = os.environ.get("PREFECT_TESTING_TEST_MODE")
    if test_mode_value is not None:
        os.environ["PREFECT_TESTING_TEST_MODE"] = test_mode_value
    else:
        os.environ.pop("PREFECT_TESTING_TEST_MODE")

    try:
        # We must re-execute the module since the setting is configured at base model
        # definition time
        importlib.reload(prefect.server.utilities.schemas.bases)

        from prefect.server.utilities.schemas.bases import PrefectBaseModel

        yield PrefectBaseModel
    finally:
        if original_environment is None:
            os.environ.pop("PREFECT_TESTING_TEST_MODE")
        else:
            os.environ["PREFECT_TESTING_TEST_MODE"] = original_environment

        # We must restore this type or `isinstance` checks will fail later
        prefect.server.utilities.schemas.bases.PrefectBaseModel = original_base_model


class TestExtraForbidden:
    def test_extra_attributes_are_allowed_during_unit_tests(self):
        class Model(PrefectBaseModel):
            x: int

        Model(x=1, y=2)

    @pytest.mark.parametrize("falsey_value", ["0", "False", "", None])
    def test_extra_attributes_are_allowed_outside_test_mode(
        self, falsey_value: Optional[str]
    ):
        with reload_prefect_base_model(falsey_value) as PrefectBaseModel:

            class Model(PrefectBaseModel):
                x: int

        Model(x=1, y=2)

    @pytest.mark.parametrize("truthy_value", ["1", "True", "true"])
    def test_extra_attributes_are_allowed_with_truthy_test_mode(
        self, truthy_value: Optional[str]
    ):
        with reload_prefect_base_model(truthy_value) as PrefectBaseModel:

            class Model(PrefectBaseModel):
                x: int

        Model(x=1, y=2)


class TestNestedDict:
    @pytest.fixture()
    def nested(self) -> pydantic.BaseModel:
        class Child(pydantic.BaseModel):
            z: int

        class Parent(PrefectBaseModel):
            x: int
            y: Child

        return Parent(x=1, y=Child(z=2))

    def test_full_dict(self, nested: PrefectBaseModel):
        assert nested.model_dump() == {"x": 1, "y": {"z": 2}}
        assert isinstance(nested.model_dump()["y"], dict)

    def test_simple_dict(self, nested: PrefectBaseModel):
        assert dict(nested) == {"x": 1, "y": nested.y}
        assert isinstance(dict(nested)["y"], pydantic.BaseModel)

    def test_custom_dump_methods_respected(self, nested: PrefectBaseModel):
        deep = nested.model_dump(include={"y"})
        shallow = nested.model_dump_for_orm(include={"y"})
        assert isinstance(deep["y"], dict)
        assert isinstance(shallow["y"], pydantic.BaseModel)


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

        now_dt = now()
        x1 = X(id=uuid4(), created=now_dt, x=1)
        x2 = X(id=uuid4(), created=now_dt + datetime.timedelta(hours=1), x=1)
        x3 = X(id=uuid4(), created=now_dt - datetime.timedelta(hours=1), x=2)
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


class ConcreteDescriptor(PrefectDescriptorBase):
    def __get__(self, *args: Any) -> Any:
        return super().__get__(*args)


class PlainOwner:
    descr = ConcreteDescriptor()


class ModelOwner(PrefectBaseModel):
    descr = ConcreteDescriptor()
    _private_descr = ConcreteDescriptor()


class TestPrefectDescriptorBase:
    @pytest.mark.parametrize("type_", (PlainOwner, ModelOwner))
    def test_class_access(self, type_: Union[PlainOwner, ModelOwner]):
        assert type_.descr is type_.__dict__["descr"]

    def test_base_implementation(self):
        instance = PlainOwner()
        with pytest.raises(AttributeError):
            instance.descr

    def test_pydantic_ignored_types(self):
        assert "descr" not in ModelOwner.model_fields
        assert "descr" in dir(ModelOwner)
        assert not ModelOwner.__private_attributes__

    @pytest.mark.parametrize("attr_name", ("descr", "_private_descr"))
    def test_pydantic_model_access(self, attr_name: str):
        instance = ModelOwner()
        with pytest.raises(AttributeError):
            getattr(instance, attr_name)
