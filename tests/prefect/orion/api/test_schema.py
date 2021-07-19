import pendulum
import pytest
from pydantic import ValidationError

from prefect.orion.api import schemas


class TestParameterSchema:
    async def test_create_parameter_with_valid_type(self):
        assert schemas.Parameter(name="x", type=schemas.ParameterType.STRING)

    async def test_create_parameter_with_invalid_type(self):
        with pytest.raises(
            ValidationError, match="(value is not a valid enumeration member)"
        ):
            schemas.Parameter(name="x", type="ABC")

    async def test_required_parameter(self):
        assert schemas.Parameter(name="x", is_required=True)

    async def test_json_default(self):
        assert schemas.Parameter(name="x", default="y")

    async def test_non_json_default(self):
        with pytest.raises(
            ValidationError, match="(Default values must be JSON-compatible)"
        ):
            schemas.Parameter(name="x", default=pendulum.now())
