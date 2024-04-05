import pytest

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.pydantic._flags import USE_V2_MODELS

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

    def test_pre_default(self):
        """
        Ensure that the `pre` argument defaults to False
        """

    def test_pre_set_to_true(self):
        """
        Test that the `pre` argument can be set to True
        """
        pass

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
