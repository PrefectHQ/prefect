from typing import Optional

import pytest
from typing_extensions import Annotated

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.pydantic._compat import BaseModel, Field, ValidationError
from prefect._internal.pydantic._flags import USE_V2_MODELS
from prefect._internal.pydantic.utilities.field_validator import field_validator
from prefect._internal.pydantic.utilities.model_validator import model_validator

if not HAS_PYDANTIC_V2:
    # v1v1
    from pydantic import ConfigError
elif HAS_PYDANTIC_V2 and not USE_V2_MODELS:
    # v2v1
    from pydantic.v1 import ConfigError
else:
    # v2v2
    from pydantic import ValidationInfo  # type: ignore


@pytest.mark.skipif(
    USE_V2_MODELS,
    reason="These tests are only valid when compatibility layer is disabled and/or V1 is installed",
)
class TestFieldValidatorV1:
    def test_basic_field_validation_behavior(self):
        """
        Ensures the `field_validator` correctly applies validation logic to a specified field
        and raises a `ValidationError` when the validation condition is not met.
        """

        class TestModel(BaseModel):
            a: int
            b: str

            @field_validator("b", mode="after")
            def check_b(cls, v):
                if "a" in v:
                    raise ValueError("'a' not allowed in b")
                return v

        model = TestModel(a=1, b="123")
        assert model.b == "123"

        with pytest.raises(ValidationError):
            TestModel(a=1, b="a123")

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

            @field_validator("field2", mode="before")
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

    def test_validation_of_default_values(self):
        """
        Ensures that the `field_validator` applies validation to fields with default values.
        """

        class TestModel(BaseModel):
            a: str = "default"

            @field_validator("a", mode="before")
            def check_a(cls, v):
                if not v.isalpha():
                    raise ValueError(
                        "Default value must only contain alphabetic characters"
                    )
                return v

        model = TestModel()
        assert model.a == "default"

        with pytest.raises(ValidationError):
            TestModel(a="123")

    def test_handling_of_optional_fields(self):
        """
        Tests that the `field_validator` correctly handles optional fields, applying validation
        only when a value is provided.
        """

        class TestModel(BaseModel):
            a: Optional[str] = None

            @field_validator("a", mode="before")
            def check_a(cls, v):
                if v is not None and len(v) < 3:
                    raise ValueError("Field 'a' must be at least 3 characters long")
                return v

        # Test that the validator does not raise an error for a missing optional field
        model = TestModel()
        assert model.a is None

        # Test that providing a valid optional value passes
        model = TestModel(a="valid")
        assert model.a == "valid"

        # Test that an invalid value raises a ValidationError
        with pytest.raises(ValidationError):
            TestModel(a="no")

    def test_reuse_of_validators_across_different_fields(self):
        """
        Tests that validators can be reused across different fields within the same model.
        """

        class TestModel(BaseModel):
            a: str
            b: str

            @field_validator("a", "b")
            def check_length(cls, v):
                if len(v) < 5:
                    raise ValueError(
                        "Fields 'a' and 'b' must be at least 5 characters long"
                    )
                return v

        # Test that both fields pass validation
        model = TestModel(a="valid", b="check")
        assert model.a == "valid" and model.b == "check"

        # Test that an invalid 'a' value raises a ValidationError
        with pytest.raises(ValidationError):
            TestModel(a="no", b="check")

        # Test that an invalid 'b' value also raises a ValidationError
        with pytest.raises(ValidationError):
            TestModel(a="valid", b="no")

    def test_check_fields_default_behavior(self):
        """
        Validate that the `check_fields` parameter is set to `True` by default in Pydantic V1 models
        to ensure that unless specified otherwise, the fields being validated are checked for existence.
        """

        with pytest.raises(ConfigError) as exc_info:

            class TestModel(BaseModel):
                existing_field: int

                @field_validator("non_existent_field")
                def dummy_validator(cls, value):
                    return value

        assert "Validators defined with incorrect fields: dummy_validator" in str(
            exc_info.value
        )

    def test_validator_not_reusable_across_models_by_default(self):
        """
        Validate `allow_reuse` parameter set to False by default in V1 models, ensuring that
        a validator function cannot be reused across different models unless explicitly allowed.
        """

        def normalize(small_name: str) -> str:
            return " ".join((word.capitalize()) for word in small_name.split(" "))

        class Producer(BaseModel):
            name: str

            _normalize_name = field_validator(
                "name",
            )(normalize)

        with pytest.raises(ConfigError) as exc_info:

            class Consumer(BaseModel):
                name: str

                _normalize_name = field_validator(
                    "name",
                )(normalize)

        assert "duplicate validator function" in str(exc_info.value)

    def test_pre_parameter_defaults_to_false(self):
        """
        Tests the `pre` parameter to ensure post-validation logic is applied by default in V1.
        """

        class TestModel(BaseModel):
            a: int

            @field_validator("a")
            def ensure_positive(cls, v):
                if v <= 0:
                    raise ValueError("Field 'a' must be positive")
                return v

        TestModel(a="1")  # type: ignore

        with pytest.raises(ValidationError) as exc_info:
            TestModel(a="-1")  # type: ignore
        assert "Field 'a' must be positive" in str(exc_info.value)

    def test_pre_parameter_set_to_true(self):
        """
        Tests the `pre` parameter to ensure pre-validation logic is applied in V1.
        """

        class TestModel(BaseModel):
            a: int

            @field_validator("a", mode="before")
            def ensure_positive(cls, v):
                if v <= 0:
                    raise ValueError("Field 'a' must be positive")
                return v

        # Test that a positive value passes pre-validation
        TestModel(a=1)

        # Test that a non-positive value raises a ValidationError at pre-validation stage
        with pytest.raises(ValidationError) as exc_info:
            TestModel(a=-1)
        assert "Field 'a' must be positive" in str(exc_info.value)

    def test_always_parameter_in_v1_defaults_to_false(self):
        """
        Test that the `always` parameter in Pydantic V1 models defaults to `False`,
        """

        class TestModel(BaseModel):
            a: int = -1

            @field_validator("a")
            def ensure_positive(cls, v):
                # This logic should not be invoked if 'a' is not explicitly set
                # because always is set to False by default
                if v <= 0:
                    raise ValueError("Field 'a' must be positive")
                return v

        # The validator should not be called, and no error should be raised
        model = TestModel()
        assert model.a == -1, "Default value for 'a' should be untouched"

        # The validator should be called, and an error should be raised
        with pytest.raises(ValidationError) as exc_info:
            TestModel(a=-1)
        assert "Field 'a' must be positive" in str(exc_info.value)

    def test_always_parameter_in_v1_set_to_true_behavior(self):
        """
        The `always` parameter is not available in Pydantic V2 models.
        In order to achieve the same behavior, without exposing an `always` parameter in the @field_validator decorator,
        we can use @model_validator with `mode='before'` and check that the field is not None, if necessary.
        """

        class TestModel(BaseModel):
            a: int = -1

            @model_validator(mode="before")
            def ensure_positive(cls, data):
                if "a" not in data:
                    raise ValueError("Field 'a' must be present")
                if data["a"] <= 0:
                    raise ValueError("Field 'a' must be positive")
                return data

        with pytest.raises(ValidationError) as exc_info:
            TestModel()
        assert "Field 'a' must be present" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            TestModel(a=-2)
        assert "Field 'a' must be positive" in str(exc_info.value)

        TestModel(a=1)


@pytest.mark.skipif(
    not USE_V2_MODELS,
    reason="These tests are only valid when compatibility layer is enabled and V2 is installed",
)
class TestFieldValidatorV2:
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

    def test_multiple_field_validation_in_v2(self):
        """
        Tests that multiple fields can be validated using a single validator in Pydantic V2.

        Example taken from:
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

            @field_validator("id", "name")
            @classmethod
            def check_alphanumeric(cls, v: str, info: "ValidationInfo") -> str:
                if isinstance(v, str):
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

    def test_multiple_field_validation_in_v2_with_default_values(self):
        """
        Test that multiple fields can be validated using a single validator in Pydantic V2.
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

    def test_nested_model_validation(self):
        """
        Test that field validation can be applied to nested models.
        """

        class ChildModel(BaseModel):
            child_field: int

            @field_validator("child_field")
            def child_field_must_be_even(cls, v):
                if v % 2 != 0:
                    raise ValueError("child_field must be even")
                return v

        class ParentModel(BaseModel):
            nested: ChildModel

        valid_child = ChildModel(child_field=2)
        ParentModel(nested=valid_child)

        with pytest.raises(ValidationError) as exc_info:
            ChildModel(child_field=3)
        assert "child_field must be even" in str(exc_info.value)

    def test_dynamic_default_validation(self):
        """
        Test that field validation can be applied to fields with default_factory.
        """

        def default_name():
            return "Default Name"

        class DynamicDefaultModel(BaseModel):
            name: str = Field(default_factory=default_name)

            @field_validator("name")
            def name_must_include_space(cls, v):
                if " " not in v:
                    raise ValueError("name must include a space")
                return v

        model = DynamicDefaultModel()
        assert model.name == "Default Name"

        DynamicDefaultModel(name="Valid Name")

        with pytest.raises(ValidationError) as exc_info:
            DynamicDefaultModel(name="InvalidName")
        assert "name must include a space" in str(exc_info.value)

    def test_field_validator_with_before_mode(self):
        """
        Tests that field validation can be applied before the default validation logic.
        """

        class Model(BaseModel):
            a: str

            @field_validator("a", mode="before")
            @classmethod
            def ensure_foobar(cls, v: str) -> str:
                if "foobar" not in v:
                    raise ValueError('"foobar" not found in a')
                return v

        assert Model(a="this is foobar good").model_dump() == {
            "a": "this is foobar good"
        }

        with pytest.raises(ValidationError) as exc_info:
            Model(a="snap")
        assert '"foobar" not found in a' in str(exc_info.value)

    def test_alias_field_validation(self):
        """
        Tests that field validation can be applied to fields with aliases.
        """

        class AliasModel(BaseModel):
            real_name: str = Field(..., alias="alias_name")

            @field_validator("real_name")
            def real_name_must_be_capitalized(cls, v):
                if not v.istitle():
                    raise ValueError("real_name must be capitalized")
                return v

        AliasModel(alias_name="Valid Name")

        AliasModel(alias_name="Another Valid Name")

        with pytest.raises(ValidationError) as exc_info:
            AliasModel(alias_name="invalid")
        assert "real_name must be capitalized" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            AliasModel(alias_name="also invalid")
        assert "real_name must be capitalized" in str(exc_info.value)
