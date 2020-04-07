from typing import Union

import pytest

from prefect.engine.results import ConstantResult
from prefect.tasks.core.constants import Constant


class TestConstantResult:
    def test_instantiates_with_value(self):
        constant_result = ConstantResult(5)
        assert constant_result.value == 5

        constant_result = ConstantResult(value=10)
        assert constant_result.value == 10

    def test_read_returns_value(self):
        constant_result = ConstantResult("hello world")
        assert constant_result.read("this param isn't used") is constant_result

    def test_write_doesnt_overwrite_value(self):
        constant_result = ConstantResult("untouchable!")

        constant_result.write()
        assert constant_result.value == "untouchable!"
        assert constant_result.read("still unused") is constant_result

    def test_write_returns_value(self):
        constant_result = ConstantResult("constant value")

        output = constant_result.write()
        assert output is output

    def test_handles_none_as_constant(self):

        constant_result = ConstantResult(None)
        assert constant_result.read("still not used") is constant_result
        output = constant_result.write()
        assert output is output

    @pytest.mark.parametrize(
        "constant_value", [3, "text", 5.0, Constant(3), Constant("text"), Constant(5.0)]
    )
    def test_exists(self, constant_value: Union[str, Constant]):

        result = ConstantResult(constant_value)
        result_exists = result.exists()

        assert result_exists is True
