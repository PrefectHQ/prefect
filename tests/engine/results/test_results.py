import json
from typing import Union

import pytest

import prefect
from prefect.engine.results import ConstantResult, PrefectResult, SecretResult
from prefect.tasks.core.constants import Constant
from prefect.tasks.secrets import PrefectSecret


class TestSecretResult:
    def test_instantiates_with_task(self):
        task = PrefectSecret("foo")
        result = SecretResult(task)
        assert result.secret_task is task
        assert result.filepath == "foo"

    def test_reads_by_rerunning_task(self):
        task = PrefectSecret("foo")
        task.run = lambda *args, **kwargs: 42
        result = SecretResult(task)
        result.filepath == "foo"

        new_result = result.read("foo")
        assert new_result.value == 42
        new_result.filepath == "foo"

    def test_reads_with_new_name(self):
        task = PrefectSecret("foo")
        result = SecretResult(task)

        with prefect.context(secrets=dict(x=99, foo="bar")):
            res1 = result.read("x")
            res2 = result.read("foo")

        assert res1.value == 99
        assert res1.filepath == "x"

        assert res2.value == "bar"
        assert res2.filepath == "foo"

    def test_cant_write_to_secret_task(self):
        task = PrefectSecret("foo")
        result = SecretResult(task)

        with pytest.raises(ValueError):
            result.write("new")


class TestConstantResult:
    def test_instantiates_with_value(self):
        constant_result = ConstantResult(value=5)
        assert constant_result.value == 5

        constant_result = ConstantResult(value=10)
        assert constant_result.value == 10

    def test_read_returns_self(self):
        constant_result = ConstantResult(value="hello world")
        assert constant_result.read("this param isn't used") is constant_result

    def test_write_raises(self):
        constant_result = ConstantResult("untouchable!")

        with pytest.raises(ValueError):
            constant_result.write("nvm")

        with pytest.raises(ValueError):
            constant_result.write("untouchable!")

    def test_handles_none_as_constant(self):
        constant_result = ConstantResult(value=None)
        assert constant_result.read("still not used") is constant_result

    @pytest.mark.parametrize(
        "constant_value", [3, "text", 5.0, Constant(3), Constant("text"), Constant(5.0)]
    )
    def test_exists(self, constant_value: Union[str, Constant]):

        result = ConstantResult(value=constant_value)
        result_exists = result.exists("")

        assert result_exists is True


class TestPrefectResult:
    def test_instantiates_with_value(self):
        result = PrefectResult(value=5)
        assert result.value == 5
        assert result.location == ""

        result = PrefectResult(value=10)
        assert result.value == 10
        assert result.location == ""

    def test_read_returns_new_result(self):
        result = PrefectResult(value="hello world")
        res = result.read('"bl00p"')

        assert res.location == '"bl00p"'
        assert res.value == "bl00p"
        assert result.value == "hello world"

    def test_write_doesnt_overwrite_value(self):
        result = PrefectResult(value=42)

        new_result = result.write(99)

        assert result.value == 42
        assert result.location == ""

        assert new_result.value == 99
        assert new_result.location == "99"

    @pytest.mark.parametrize(
        "value", [42, [0, 1], "x,y", (9, 10), dict(x=[55], y=None)]
    )
    def test_exists_for_json_objs(self, value):
        result = PrefectResult()
        assert result.exists(json.dumps(value)) is True
        assert result.exists(value) is False
