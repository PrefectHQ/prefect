import os
import json
import sys
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
    ResourceResult,
)
from prefect.engine.serializers import JSONSerializer, PickleSerializer
from prefect.tasks.core.constants import Constant
from prefect.tasks.resources.base import ResourceHandle
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

    def test_cant_pass_serializer_to_secret_result(self):
        with pytest.raises(ValueError, match="Can't pass a serializer"):
            SecretResult(PrefectSecret("foo"), serializer=None)


class TestResourceResult:
    def test_initialize_empty(self):
        result = ResourceResult()
        assert result.handle is None
        assert result.location is None

    def test_from_value_and_value_property(self):
        result = ResourceResult()

        with pytest.raises(ValueError, match="No value found for this resource result"):
            result.value

        with pytest.raises(TypeError, match="value must be a ResourceHandle"):
            result.from_value(123)

        # from_value works with a resource handle
        handle = ResourceHandle(lambda x, y=1: x + y, (1, 2), {})
        result2 = result.from_value(handle)
        assert result2.handle is handle
        assert result2.location is None

        # Value attribute recreates resource
        assert result2.value == 3

        # Value attribute setter is a no-op
        result2.value = None
        assert result2.value == 3

        # After resource is cleared, `value` attribute raises
        handle.clear()

        with pytest.raises(ValueError, match="Cannot access value of `Resource`"):
            result2.value

    def test_read_returns_self(self):
        result = ResourceResult()
        assert result.read("unused") is result

    def test_write_raises(self):
        result = ResourceResult()

        with pytest.raises(ValueError):
            result.write("unused")

    def test_exists(self):
        result = ResourceResult()
        assert result.exists("unused")

    def test_cant_pass_serializer_to_resource_result(self):
        with pytest.raises(ValueError, match="Can't pass a serializer"):
            ResourceResult(serializer=JSONSerializer())


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

    def test_cant_pass_serializer_to_constant_result(self):
        with pytest.raises(ValueError, match="Can't pass a serializer"):
            ConstantResult(serializer=None)


class TestPrefectResult:
    def test_serializer_not_configurable(self):
        # By default creates own JSONSerializer
        result = PrefectResult()
        assert isinstance(result.serializer, JSONSerializer)

        # Can specify one manually as well
        serializer = JSONSerializer()
        result = PrefectResult(serializer=serializer)
        assert result.serializer is serializer

        # Can set if it's a JSONSerializer
        serializer2 = JSONSerializer()
        result.serializer = serializer2
        assert result.serializer is serializer2

        # Type errors for other serializer types
        with pytest.raises(TypeError):
            result.serializer = PickleSerializer()
        with pytest.raises(TypeError):
            result = PrefectResult(serializer=PickleSerializer())

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
        assert new_result.location.endswith("42.txt")
        assert new_result.value == "so-much-data"

    def test_local_result_creates_necessary_dirs(self, tmp_dir):
        os_independent_template = os.path.join("mydir", "mysubdir", "{thing}.txt")
        result = LocalResult(dir=tmp_dir, location=os_independent_template)
        new_result = result.write("so-much-data", thing=42)
        assert new_result.location.endswith(os.path.join("mydir", "mysubdir", "42.txt"))
        assert new_result.value == "so-much-data"

    def test_local_result_cleverly_redirects_prefect_defaults(self):
        result = LocalResult(dir=config.home_dir)
        assert result.dir == os.path.join(config.home_dir, "results")

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_result_writes_to_dir(self, tmp_dir, res):
        result = LocalResult(dir=tmp_dir, location="test.txt")
        fpath = result.write(res).location
        assert isinstance(fpath, str)
        assert fpath.endswith("test.txt")

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

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows specific test")
    def test_local_init_with_different_drive_works_on_windows(self):
        result = LocalResult(dir="E:/location", validate_dir=False)
        assert result.dir == "E:/location"


class TestResultFormatting:
    def test_result_accepts_callable_for_location(self, tmpdir):
        result = LocalResult(dir=tmpdir, location=lambda **kwargs: "special_val")
        assert result.location is None
        new_result = result.format()
        assert new_result.location.endswith("special_val")

    def test_result_callable_accepts_kwargs(self, tmpdir):
        result = LocalResult(dir=tmpdir, location=lambda **kwargs: kwargs["key"])
        assert result.location is None
        new_result = result.format(key="42")
        assert new_result.location.endswith("42")
