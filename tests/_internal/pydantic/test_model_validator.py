import pytest
from pydantic import BaseModel, ValidationError

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.pydantic._flags import USE_V2_MODELS
from prefect._internal.pydantic.utilities.model_validator import model_validator

if USE_V2_MODELS:
    pass
elif not HAS_PYDANTIC_V2:
    pass


@pytest.mark.skipif(
    HAS_PYDANTIC_V2,
    reason="These tests are only valid when compatibility layer is disabled and/or V1 is installed",
)
class TestModelValidatorV1:
    def test_basic_model_validation_behavior(self):
        pass

    def test_pre_default_is_false(self):
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

        assert TestModel(a="1")

        with pytest.raises(ValidationError):
            TestModel(a="-1")

    def test_pre_set_to_true(self):
        """
        Test that the `pre` argument can be set to True
        """

        class TestModel(BaseModel):
            a: int

            @model_validator
            def test_method(cls, values):
                if values.get("a") < 0:
                    raise ValueError("a must be greater than 0")
                return values

        assert TestModel(a="1")

        with pytest.raises(ValidationError):
            TestModel(a="-1")

    def test_pre_set_to_false(self):
        """
        Test that the `pre` argument can be set to False
        """
        pass

    def test_skip_on_failure_default(self):
        """
        Ensure that the `skip_on_failure` argument defaults to False
        """
        pass

    def test_skip_on_failure_set_to_true(self):
        """
        Test that the `skip_on_failure` argument can be set to True
        """
        pass

    def test_skip_on_failure_set_to_false(self):
        """
        Test that the `skip_on_failure` argument can be set to False
        """
        pass

    def test_pre_and_skip_on_failure_set_to_true(self):
        """
        Test that the `pre` and `skip_on_failure` arguments can be set to True
        """
        pass


@pytest.mark.skipif(
    not USE_V2_MODELS,
    reason="These tests are only valid when compatibility layer is enabled and V2 is installed",
)
class TestModelValidatorV2:
    pass
