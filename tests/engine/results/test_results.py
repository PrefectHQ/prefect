import os
import json
import tempfile
from typing import Union

import cloudpickle
import pytest

import prefect
from prefect import config
from prefect.engine.results import (
    ConstantResult,
    LocalResult,
    PrefectResult,
    SecretResult,
)
from prefect.tasks.core.constants import Constant
from prefect.tasks.secrets import PrefectSecret


class TestSecretResult:
    def test_instantiates_with_task(self):
        task = PrefectSecret("foo")
        result = SecretResult(task)
        assert result.secret_task is task
        assert result.location == "foo"

    def test_reads_by_rerunning_task(self):
        task = PrefectSecret("foo")
        task.run = lambda *args, **kwargs: 42
        result = SecretResult(task)
        result.location == "foo"

        new_result = result.read("foo")
        assert new_result.value == 42
        new_result.location == "foo"

    def test_reads_with_new_name(self):
        task = PrefectSecret("foo")
        result = SecretResult(task)

        with prefect.context(secrets=dict(x=99, foo="bar")):
            res1 = result.read("x")
            res2 = result.read("foo")

        assert res1.value == 99
        assert res1.location == "x"

        assert res2.value == "bar"
        assert res2.location == "foo"

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
        constant_result = ConstantResult(value="untouchable!")

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
        assert result.location is None

        result = PrefectResult(value=10)
        assert result.value == 10
        assert result.location is None

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
        assert result.location is None

        assert new_result.value == 99
        assert new_result.location == "99"

    @pytest.mark.parametrize(
        "value", [42, [0, 1], "x,y", (9, 10), dict(x=[55], y=None)]
    )
    def test_exists_for_json_objs(self, value):
        result = PrefectResult()
        assert result.exists(json.dumps(value)) is True
        assert result.exists(value) is False


class TestLocalResult:
    @pytest.fixture(scope="class")
    def tmp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_local_result_initializes_with_no_args(self):
        result = LocalResult()
        assert result.dir == os.path.join(config.home_dir, "results")
        assert result.value is None

    def test_local_result_initializes_with_dir(self):
        root_dir = os.path.abspath(os.sep)
        result = LocalResult(dir=root_dir)
        assert result.dir == root_dir

    def test_local_result_writes_using_rendered_template_name(self, tmp_dir):
        result = LocalResult(dir=tmp_dir, location="{thing}.txt")
        new_result = result.write("so-much-data", thing=42)
        assert new_result.location == "42.txt"
        assert new_result.value == "so-much-data"

    def test_local_result_creates_necessary_dirs(self, tmp_dir):
        os_independent_template = os.path.join("mydir", "mysubdir", "{thing}.txt")
        result = LocalResult(dir=tmp_dir, location=os_independent_template)
        new_result = result.write("so-much-data", thing=42)
        assert new_result.location == os.path.join("mydir", "mysubdir", "42.txt")
        assert new_result.value == "so-much-data"

    def test_local_result_cleverly_redirects_prefect_defaults(self):
        result = LocalResult(dir=config.home_dir)
        assert result.dir == os.path.join(config.home_dir, "results")

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_result_writes_to_dir(self, tmp_dir, res):
        result = LocalResult(dir=tmp_dir, location="test.txt")
        fpath = result.write(res).location
        assert isinstance(fpath, str)
        assert fpath == "test.txt"

        with open(os.path.join(tmp_dir, fpath), "rb") as f:
            val = f.read()
        assert isinstance(val, bytes)

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_result_writes_and_reads(self, tmp_dir, res):
        result = LocalResult(dir=tmp_dir, location="test.txt")
        final = result.read(result.write(res).location)
        assert final.value == res

    def test_local_result_is_pickleable(self):
        result = LocalResult(dir="root")
        new = cloudpickle.loads(cloudpickle.dumps(result))
        assert isinstance(new, LocalResult)

    def test_local_result_writes_and_exists(self, tmp_dir):
        result = LocalResult(dir=tmp_dir, location="{thing}.txt")
        assert result.exists("43.txt") is False
        new_result = result.write("so-much-data", thing=43)
        assert result.exists("43.txt") is True

    def test_local_exists_full_path(self, tmp_dir):
        result = LocalResult(dir=tmp_dir, location="{thing}.txt")
        assert result.exists("44.txt") is False
        new_result = result.write("so-much-data", thing=44)
        assert result.exists("44.txt") is True
        assert result.exists(os.path.join(tmp_dir, "44.txt")) is True
