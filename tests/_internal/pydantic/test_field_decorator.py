import pytest
from pydantic import BaseModel, Field, ValidationError
from typing_extensions import Annotated

from prefect._internal.pydantic._flags import USE_V2_MODELS
from prefect._internal.pydantic.utilities.field_decorator import field_validator

if USE_V2_MODELS:
    from pydantic import ValidationInfo


class TestFieldValidator:
    def test_basic_field_validation_behavior(self):
        """
        Ensures the `field_validator` correctly applies validation logic to a specified field
        and raises a `ValidationError` when the validation condition is not met.
        """

        class TestModel(BaseModel):
            a: int
            b: str

            @field_validator("b", mode="after", allow_reuse=True)
            def check_b(cls, v):
                if "a" in v:
                    raise ValueError("'a' not allowed in b")
                return v

        model = TestModel(a=1, b="123")
        assert model.b == "123"

        with pytest.raises(ValidationError):
            TestModel(a=1, b="a123")

    @pytest.mark.skipif(
        USE_V2_MODELS,
        reason="These tests are only valid when compatibility layer is disabled and/or V1 is installed",
    )
    def test_cross_field_dependency_in_v1(self):
        """
        Validates that `field_validator` properly enables cross-field dependencies in Pydantic V1 models,
        allowing `fieldd`'s validation to depend on `fieldc`'s value. Specifically tests that `fieldd` must
        be 'allowed' when `fieldc` is 'special'.
        """

        class TestModel4(BaseModel):
            fieldc: str
            fieldd: str

            @field_validator("fieldd")
            def fieldd_depends_on_fieldc(cls, v, values):
                if (
                    "fieldc" in values
                    and values["fieldc"] == "special"
                    and v != "allowed"
                ):
                    raise ValueError(
                        "fieldd must be 'allowed' when fieldc is 'special'"
                    )
                return v

        with pytest.raises(ValidationError):
            TestModel4(fieldc="special", fieldd="not_allowed")

        model = TestModel4(fieldc="special", fieldd="allowed")
        assert model.fieldd == "allowed"

    @pytest.mark.skipif(
        USE_V2_MODELS,
        reason="These tests are only valid when compatibility layer is disabled and/or V1 is installed",
    )
    def test_cross_field_validation_in_v1_using_values(self):
        """
        Verifies cross-field validation in Pydantic V1 by using the `values` dictionary
        to access other fields within the same model. It checks that `field2`'s validation
        depends on `field1`'s value, ensuring `field2` contains 'special' when `field1` is greater than 10.

        !!! note
            This test is only valid for Pydantic V1 models.
            In Pydantic V2, the `info` parameter is used to access other fields.
        """

        class TestModel2(BaseModel):
            field1: int
            field2: str

            @field_validator("field2", pre=True)
            def validate_field2(cls, v, values):
                if values["field1"] > 10 and "special" not in v:
                    raise ValueError("field2 must contain 'special' when field1 > 10")
                return v

        model = TestModel2(field1=5, field2="normal")
        assert model.field2 == "normal"

        model = TestModel2(field1=15, field2="special value")
        assert model.field2 == "special value"

        with pytest.raises(ValidationError) as exc_info:
            TestModel2(field1=15, field2="normal")
        assert "field2 must contain 'special' when field1 > 10" in str(exc_info.value)

    @pytest.mark.skipif(
        not USE_V2_MODELS,
        reason="These tests are only valid when compatibility layer is enabled and V2 is installed",
    )
    def test_cross_field_validation_in_v2_using_info(self):
        """
        Tests the ability to perform cross-field validation in Pydantic V2 using the `info` parameter.
        Ensures `field4` is correctly validated based on `field3`'s value, with `field4` required to be 'allowed'
        if `field3` is 'special'.

        !!! note
            This test is only valid for Pydantic V2 models.
            In Pydantic V1, the `info` parameter is not available, and cross-field validation is performed using `values`.
        """

        class TestModel3(BaseModel):
            field3: str
            field4: str

            @field_validator("field4")
            def field4_depends_on_field3_info(cls, v, info):
                if (
                    "field3" in info.data
                    and info.data["field3"] == "special"
                    and v != "allowed"
                ):
                    raise ValueError(
                        "field4 must be 'allowed' when field3 is 'special'"
                    )
                return v

        with pytest.raises(ValidationError):
            TestModel3(field3="special", field4="not_allowed")

        model = TestModel3(field3="special", field4="allowed")
        assert model.field4 == "allowed"

    @pytest.mark.skipif(
        not USE_V2_MODELS,
        reason="These tests are only valid when compatibility layer is enabled and V2 is installed",
    )
    def test_multiple_field_validation_in_v2_with_default_values(self):
        """
        Example taken from: https://docs.pydantic.dev/latest/concepts/validators/#validation-of-default-values

        """

        class Model(BaseModel):
            x: str = "abc"
            y: Annotated[str, Field(validate_default=True)] = "xyz"

            @field_validator("x", "y")
            @classmethod
            def double(cls, v: str) -> str:
                return v * 2

        assert Model().model_dump() == {"x": "abc", "y": "xyzxyz"}
        assert Model(x="foo").model_dump() == {"x": "foofoo", "y": "xyzxyz"}
        assert Model(x="foo", y="bar").model_dump() == {"x": "foofoo", "y": "barbar"}
        assert Model(y="bar").model_dump() == {"x": "abc", "y": "barbar"}

    @pytest.mark.skipif(
        not USE_V2_MODELS,
        reason="These tests are only valid when compatibility layer is enabled and V2 is installed",
    )
    def test_multiple_field_validation_in_v2(self):
        """
        https://docs.pydantic.dev/latest/concepts/validators/#field-validators
        """

        class UserModel(BaseModel):
            name: str
            id: int

            @field_validator("name")
            @classmethod
            def name_must_contain_space(cls, v: str) -> str:
                if " " not in v:
                    raise ValueError("must contain a space")
                return v.title()

            # you can select multiple fields, or use '*' to select all fields
            @field_validator("id", "name")
            @classmethod
            def check_alphanumeric(cls, v: str, info: "ValidationInfo") -> str:
                if isinstance(v, str):
                    # info.field_name is the name of the field being validated
                    is_alphanumeric = v.replace(" ", "").isalnum()
                    assert is_alphanumeric, f"{info.field_name} must be alphanumeric"
                return v

        assert UserModel(name="John Doe", id=1).model_dump() == {
            "name": "John Doe",
            "id": 1,
        }

        with pytest.raises(ValidationError) as exc_info:
            UserModel(name="samuel", id=1)
        assert "must contain a space" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            UserModel(name="John Doe!", id=1)

        assert "name must be alphanumeric" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            UserModel(name="John Doe!", id=1)

        assert "name must be alphanumeric" in str(exc_info.value)
