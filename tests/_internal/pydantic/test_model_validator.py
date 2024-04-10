import json
from typing import Any, List

import pytest

from prefect._internal.pydantic._compat import BaseModel, ValidationError
from prefect._internal.pydantic._flags import USE_V2_MODELS
from prefect._internal.pydantic.utilities.model_validator import model_validator

if USE_V2_MODELS:
    from pydantic import (
        ValidationInfo,
        ValidatorFunctionWrapHandler,
    )
    from pydantic.functional_validators import WrapValidator
from typing_extensions import Annotated


@pytest.mark.skipif(
    USE_V2_MODELS,
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

            @model_validator(skip_on_failure=True)
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

        assert (
            "Field 'b' must be positive" in errors
        )  # This check verifies that the pre-validation ran
        assert "Field 'a' must be positive" not in errors


@pytest.mark.skipif(
    not USE_V2_MODELS,
    reason="These tests are only valid when compatibility layer is enabled and V2 is installed",
)
class TestModelValidatorV2:
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

        assert TestModel(a=1)

        with pytest.raises(ValidationError) as e:
            TestModel(a=-1)
        assert "a must be greater than 0" in str(e)

    def test_mode_param_before_after(self):
        """
        Example from:
        https://docs.pydantic.dev/latest/concepts/validators/#model-validators
        """

        class UserModel(BaseModel):
            username: str
            password1: str
            password2: str

            @model_validator(mode="before")
            @classmethod
            def check_card_number_omitted(cls, data: Any) -> Any:
                if isinstance(data, dict):
                    assert (
                        "card_number" not in data
                    ), "card_number should not be included"
                return data

            @model_validator(mode="after")
            def check_passwords_match(self) -> "UserModel":
                pw1 = self.password1
                pw2 = self.password2
                if pw1 is not None and pw2 is not None and pw1 != pw2:
                    raise ValueError("passwords do not match")
                return self

        print(UserModel(username="scolvin", password1="zxcvbn", password2="zxcvbn"))
        # > username='scolvin' password1='zxcvbn' password2='zxcvbn'
        with pytest.raises(ValidationError) as e:
            UserModel(username="scolvin", password1="zxcvbn", password2="zxcvbn2")
        assert "passwords do not match" in str(e)

        with pytest.raises(ValidationError) as e:
            UserModel(
                username="scolvin",
                password1="zxcvbn",
                password2="zxcvbn",
                card_number="1234",  # type: ignore
            )
        assert "card_number should not be included" in str(e)

    def test_mode_param_wrap_succeeds(self):
        """
        Example from:
        https://docs.pydantic.dev/latest/concepts/validators/#before-after-wrap-and-plain-validators
        """

        def maybe_strip_whitespace(
            v: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo
        ) -> int:
            if info.mode == "json":
                assert isinstance(v, str), "In JSON mode the input must be a string!"
                # you can call the handler multiple times
                try:
                    return handler(v)
                except ValidationError:
                    return handler(v.strip())
            assert info.mode == "python"
            assert isinstance(v, int), "In Python mode the input must be an int!"
            # do no further validation
            return v

        MyNumber = Annotated[int, WrapValidator(maybe_strip_whitespace)]

        class DemoModel(BaseModel):
            number: List[MyNumber]

        print(DemoModel(number=[2, 8]))
        # > number=[2, 8]
        print(DemoModel.model_validate_json(json.dumps({"number": [" 2 ", "8"]})))
        # > number=[2, 8]
        try:
            DemoModel(number=["2"])
        except ValidationError as e:
            print(e)
            """
            1 validation error for DemoModel
            number.0
            Assertion failed, In Python mode the input must be an int!
            assert False
            +  where False = isinstance('2', int) [type=assertion_error, input_value='2', input_type=str]
            """
