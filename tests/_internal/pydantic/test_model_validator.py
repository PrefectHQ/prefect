import pytest
from pydantic import BaseModel, ValidationError

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.pydantic._flags import USE_V2_MODELS
from prefect._internal.pydantic.utilities.model_validator import model_validator

# if USE_V2_MODELS:
#     from pydantic import ValidationInfo
# elif not HAS_PYDANTIC_V2:
#     from pydantic.errors import ConfigError


@pytest.mark.skipif(
    HAS_PYDANTIC_V2,
    reason="These tests are only valid when compatibility layer is disabled and/or V1 is installed",
)
class TestModelValidatorV1:
    def test_basic_model_validation_behavior(self):
        """
        Ensure that the `pre` argument defaults to False
        """

        class TestModel(BaseModel):
            a: int

            @model_validator
            def test_method(cls, values):
                if values.get("a") < 0:
                    raise ValueError("a must be greater than 0")
                return values

        assert TestModel(a="1")  # type: ignore

        with pytest.raises(ValidationError):
            TestModel(a="-1")  # type: ignore

    def test_pre_set_to_true(self):
        class TestModel(BaseModel):
            a: int

            @model_validator(
                pre=True
            )  # Setting pre to True to run before Pydantic validations
            def test_method(cls, values):
                # Example pre-validation logic: Transforming 'a' from string to int if possible, before Pydantic's type check
                if (
                    "a" in values
                    and isinstance(values["a"], str)
                    and values["a"].isdigit()
                ):
                    values["a"] = int(
                        values["a"]
                    )  # Transforming 'a' to int if it's a digit string
                return values

        assert TestModel(a="1")  # type: ignore

        try:
            TestModel(a="foo")  # type: ignore
        except ValidationError as e:
            # Pydantic error message
            assert "value is not a valid integer" in str(e)

    def test_skip_on_failure_default(self):
        class TestModel(BaseModel):
            a: int
            b: int = 0  # Default to ensure `b` is always present for validation

            @model_validator
            def check_a_positive(cls, values):
                if values.get("a", 0) <= 0:
                    raise ValueError("Field 'a' must be positive")
                return values

            @model_validator
            def check_b_positive(cls, values):
                # This validator should run even if 'check_a_positive' fails
                if values.get("b", 0) <= 0:
                    raise ValueError("Field 'b' must be positive")
                return values

        # Test where both validators should fail; both error messages should be present
        with pytest.raises(ValidationError) as exc_info:
            TestModel(a=-1, b=-1)
        errors = str(exc_info.value)
        assert "Field 'a' must be positive" in errors
        assert "Field 'b' must be positive" in errors

    def test_skip_on_failure_set_to_true(self):
        """
        Test that the `skip_on_failure` argument can be set to True
        """

        class TestModel(BaseModel):
            a: int
            b: int = 0  # Default to ensure `b` is present for validation

            @model_validator
            def check_a_positive(cls, values):
                if values.get("a", 0) <= 0:
                    raise ValueError("Field 'a' must be positive")
                return values

            @model_validator(skip_on_failure=True)
            def check_b_positive(cls, values):
                # This validator should be skipped if 'check_a_positive' fails
                if values.get("b", 0) <= 0:
                    raise ValueError("Field 'b' must be positive")
                return values

        # Test where the first validator fails; expect only the first error message
        with pytest.raises(ValidationError) as exc_info:
            TestModel(a=-1, b=-1)
        errors = str(exc_info.value)
        assert "Field 'a' must be positive" in errors
        assert (
            "Field 'b' must be positive" not in errors
        )  # This check verifies that the second validator was skipped

    def test_skip_on_failure_set_to_false(self):
        """
        Test that the `skip_on_failure` argument can be set to False
        """

        class TestModel(BaseModel):
            a: int
            b: int = 0  # Default to ensure `b` is always present for validation

            @model_validator
            def check_a_positive(cls, values):
                if values.get("a", 0) <= 0:
                    raise ValueError("Field 'a' must be positive")
                return values

            @model_validator
            def check_b_positive(cls, values):
                # This validator should run even if 'check_a_positive' fails
                if values.get("b", 0) <= 0:
                    raise ValueError("Field 'b' must be positive")
                return values

        # Test where both validators should fail; both error messages should be present
        with pytest.raises(ValidationError) as exc_info:
            TestModel(a=-1, b=-1)
        errors = str(exc_info.value)
        assert "Field 'a' must be positive" in errors
        assert "Field 'b' must be positive" in errors

    def test_pre_and_skip_on_failure_set_to_true(self):
        """
        Test that the `pre` and `skip_on_failure` arguments can be set to True
        """

        class TestModel(BaseModel):
            a: int
            b: int = 0

            @model_validator(pre=True, skip_on_failure=True)
            def check_a_positive(cls, values):
                if values.get("a", 0) <= 0:
                    raise ValueError("Field 'a' must be positive")
                return values

            @model_validator(pre=True, skip_on_failure=True)
            def check_b_positive(cls, values):
                if values.get("b", 0) <= 0:
                    raise ValueError("Field 'b' must be positive")
                return values

        with pytest.raises(ValidationError) as exc_info:
            TestModel(a=-1, b=-1)
        errors = str(exc_info.value)

        assert "Field 'a' must be positive" in errors
        assert "Field 'b' must be positive" not in errors


@pytest.mark.skipif(
    not USE_V2_MODELS,
    reason="These tests are only valid when compatibility layer is enabled and V2 is installed",
)
class TestModelValidatorV2:
    pass
