import importlib
import os
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Type, Union
from uuid import uuid4

import pendulum
import pydantic
import pytest

from prefect.server.utilities.schemas import (
    IDBaseModel,
    ORMBaseModel,
    PrefectBaseModel,
)


class NestedFunModel(pydantic.BaseModel):
    loser: str = pydantic.Field("drake")
    nested_secret_str: pydantic.SecretStr
    nested_secret_bytes: pydantic.SecretBytes
    nested_secret_int: pydantic.Secret[int]
    all_my_enemies_secrets: List[pydantic.SecretStr]


class FunSecretModel(PrefectBaseModel):
    winner: str = pydantic.Field("kendrick")
    secret_str: pydantic.SecretStr
    secret_str_manual: pydantic.Secret[str]
    secret_bytes: pydantic.SecretBytes
    secret_bytes_manual: pydantic.Secret[bytes]
    secret_int: pydantic.Secret[int]
    nested_model: NestedFunModel
    normal_dictionary: Dict[str, Union[str, Dict[str, Any]]]


@contextmanager
def reload_prefect_base_model(
    test_mode_value,
) -> Generator[Type[PrefectBaseModel], None, None]:
    import prefect.server.utilities.schemas.bases

    original_base_model = prefect.server.utilities.schemas.bases.PrefectBaseModel
    original_environment = os.environ.get("PREFECT_TEST_MODE")
    if test_mode_value is not None:
        os.environ["PREFECT_TEST_MODE"] = test_mode_value
    else:
        os.environ.pop("PREFECT_TEST_MODE")

    try:
        # We must re-execute the module since the setting is configured at base model
        # definition time
        importlib.reload(prefect.server.utilities.schemas.bases)

        from prefect.server.utilities.schemas.bases import PrefectBaseModel

        yield PrefectBaseModel
    finally:
        if original_environment is None:
            os.environ.pop("PREFECT_TEST_MODE")
        else:
            os.environ["PREFECT_TEST_MODE"] = original_environment

        # We must restore this type or `isinstance` checks will fail later
        prefect.server.utilities.schemas.bases.PrefectBaseModel = original_base_model


class TestExtraForbidden:
    def test_extra_attributes_are_forbidden_during_unit_tests(self):
        class Model(PrefectBaseModel):
            x: int

        with pytest.raises(
            pydantic.ValidationError, match="Extra inputs are not permitted"
        ):
            Model(x=1, y=2)

    @pytest.mark.parametrize("falsey_value", ["0", "False", "", None])
    def test_extra_attributes_are_allowed_outside_test_mode(self, falsey_value):
        with reload_prefect_base_model(falsey_value) as PrefectBaseModel:

            class Model(PrefectBaseModel):
                x: int

        Model(x=1, y=2)

    @pytest.mark.parametrize("truthy_value", ["1", "True", "true"])
    def test_extra_attributes_are_not_allowed_with_truthy_test_mode(self, truthy_value):
        with reload_prefect_base_model(truthy_value) as PrefectBaseModel:

            class Model(PrefectBaseModel):
                x: int

        with pytest.raises(
            pydantic.ValidationError, match="Extra inputs are not permitted"
        ):
            Model(x=1, y=2)


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
        assert nested.model_dump() == {"x": 1, "y": {"z": 2}}
        assert isinstance(nested.model_dump()["y"], dict)

    def test_simple_dict(self, nested):
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

        x1 = X(id=uuid4(), created=pendulum.now("UTC"), x=1)
        x2 = X(id=uuid4(), created=pendulum.now("UTC").add(hours=1), x=1)
        x3 = X(id=uuid4(), created=pendulum.now("UTC").subtract(hours=1), x=2)
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


class TestDumpSecrets:
    @pytest.fixture
    def test_secret_data(self):
        return dict(
            secret_str="oooOo very secret",
            secret_str_manual="even more secret",
            secret_bytes=b"dudes be byting my style",
            secret_bytes_manual=b"sneak dissing",
            secret_int=31415,
            nested_model=dict(
                nested_secret_str="call me a bird the way im nesting",
                nested_secret_bytes=b"nesting like a bird",
                nested_secret_int=54321,
                all_my_enemies_secrets=[
                    "culture vulture",
                    "not really a secret",
                    "but still",
                    "you know",
                ],
            ),
            normal_dictionary=dict(
                keys="do not",
                matter="at all",
                because={
                    "they": "are not",
                    "typed": "on the model",
                    "so": ["they", "can be", "anything"],
                },
            ),
        )

    def test_model_dump_with_secrets_left_obscured(self, test_secret_data):
        model = FunSecretModel.model_validate(test_secret_data)
        assert model.model_dump_with_secrets(unmask_secrets=False) == {
            "winner": "kendrick",
            "secret_str": "**********",
            "secret_str_manual": "**********",
            "secret_bytes": "**********",
            "secret_bytes_manual": "**********",
            "secret_int": "**********",
            "nested_model": {
                "loser": "drake",
                "nested_secret_str": "**********",
                "nested_secret_bytes": "**********",
                "nested_secret_int": "**********",
                "all_my_enemies_secrets": [
                    "**********",
                    "**********",
                    "**********",
                    "**********",
                ],
            },
            "normal_dictionary": test_secret_data["normal_dictionary"],
        }

    def test_model_dump_with_secrets_revealed(self, test_secret_data):
        model = FunSecretModel.model_validate(test_secret_data)
        assert model.model_dump_with_secrets() == {
            "winner": "kendrick",
            "secret_str": "oooOo very secret",
            "secret_str_manual": "even more secret",
            "secret_bytes": b"dudes be byting my style",
            "secret_bytes_manual": b"sneak dissing",
            "secret_int": 31415,
            "nested_model": {
                "loser": "drake",
                "nested_secret_str": "call me a bird the way im nesting",
                "nested_secret_bytes": b"nesting like a bird",
                "nested_secret_int": 54321,
                "all_my_enemies_secrets": [
                    "culture vulture",
                    "not really a secret",
                    "but still",
                    "you know",
                ],
            },
            "normal_dictionary": test_secret_data["normal_dictionary"],
        }
