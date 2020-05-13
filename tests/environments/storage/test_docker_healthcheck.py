import datetime
import os
import sys
import tempfile
from unittest.mock import MagicMock

import cloudpickle
import pytest

from prefect import Flow, Task, task
from prefect.engine.results import LocalResult
from prefect.environments import Environment, RemoteEnvironment
from prefect.environments.storage import _healthcheck as healthchecks


pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="These checks only run within UNIX machines"
)


class TestSerialization:
    def test_cloudpickle_deserialization_check_raises_on_bad_imports(self):
        bad_bytes = b"\x80\x04\x95\x18\x00\x00\x00\x00\x00\x00\x00\x8c\x0bfoo_machine\x94\x8c\x04func\x94\x93\x94."
        with tempfile.NamedTemporaryFile() as f:
            f.write(bad_bytes)
            f.seek(0)
            with pytest.raises(ImportError, match="foo_machine"):
                objs = healthchecks.cloudpickle_deserialization_check(
                    "['{}']".format(f.name)
                )

    def test_cloudpickle_deserialization_check_passes_and_returns_objs(self):
        good_bytes = cloudpickle.dumps(Flow("empty"))
        with tempfile.NamedTemporaryFile() as f:
            f.write(good_bytes)
            f.seek(0)
            objs = healthchecks.cloudpickle_deserialization_check(
                "['{}']".format(f.name)
            )

        assert len(objs) == 1

        flow = objs.pop()
        assert isinstance(flow, Flow)
        assert flow.name == "empty"
        assert flow.tasks == set()

    def test_cloudpickle_deserialization_check_passes_and_returns_multiple_objs(self):
        flow_one = cloudpickle.dumps(Flow("one"))
        flow_two = cloudpickle.dumps(Flow("two"))
        with tempfile.TemporaryDirectory() as tmpdir:
            file_one = os.path.join(tmpdir, "one.flow")
            with open(file_one, "wb") as f:
                f.write(flow_one)

            file_two = os.path.join(tmpdir, "two.flow")
            with open(file_two, "wb") as f:
                f.write(flow_two)

            paths = "['{0}', '{1}']".format(file_one, file_two)
            objs = healthchecks.cloudpickle_deserialization_check(paths)

        assert len(objs) == 2


class TestSystemCheck:
    def test_system_check_just_warns(self):
        with pytest.warns(UserWarning, match="unexpected errors"):
            healthchecks.system_check("(3, 4)")

    def test_system_check_doesnt_warn(self):
        sys_info = "({0}, {1})".format(sys.version_info.major, sys.version_info.minor)
        with pytest.warns(None) as records:
            healthchecks.system_check(sys_info)
        assert len(records) == 0


class TestResultCheck:
    def test_no_raise_on_normal_flow(self):
        @task
        def up():
            pass

        @task
        def down(x):
            pass

        with Flow("THIS IS A TEST") as flow:
            result = down(x=up, upstream_tasks=[Task(), Task()])

        assert healthchecks.result_check([flow]) is None

    @pytest.mark.parametrize(
        "kwargs", [dict(checkpoint=True), dict(cache_for=datetime.timedelta(minutes=1))]
    )
    def test_doesnt_raise_for_checkpointed_tasks_if_flow_has_result_handler(
        self, kwargs
    ):
        @task(**kwargs)
        def up():
            pass

        f = Flow("foo-test", tasks=[up], result_handler=42)
        assert healthchecks.result_check([f]) is None

    @pytest.mark.parametrize(
        "kwargs",
        [
            dict(max_retries=2, retry_delay=datetime.timedelta(minutes=1)),
            dict(cache_for=datetime.timedelta(minutes=1)),
        ],
    )
    def test_raises_for_tasks_with_upstream_dependencies_with_no_result_configured(
        self, kwargs
    ):
        @task
        def up():
            pass

        @task(**kwargs, result=42)
        def down(x):
            pass

        with Flow("upstream-test") as f:
            result = down(x=up)

        with pytest.raises(
            ValueError, match="upstream dependencies do not have result types."
        ):
            healthchecks.result_check([f])

    @pytest.mark.parametrize("location", [None, "{filename}.txt"])
    def test_doesnt_raise_for_mapped_tasks_with_correctly_specified_result_location(
        self, location, tmpdir
    ):
        @task(result=LocalResult(dir=tmpdir, location=location))
        def down(x):
            pass

        with Flow("upstream-test") as f:
            result = down.map(x=[1, 2, 3])

        assert healthchecks.result_check([f]) is None

    @pytest.mark.parametrize("location", [None, "{filename}.txt"])
    def test_doesnt_raise_for_mapped_tasks_with_correctly_specified_result_location_on_flow(
        self, location, tmpdir
    ):
        @task
        def down(x):
            pass

        with Flow(
            "upstream-test", result=LocalResult(dir=tmpdir, location=location)
        ) as f:
            result = down.map(x=[1, 2, 3])

        assert healthchecks.result_check([f]) is None

    def test_doesnt_raise_for_tasks_with_no_result(self, tmpdir):
        @task
        def down(x):
            pass

        with Flow("upstream-test") as f:
            result = down.map(x=[1, 2, 3])

        assert healthchecks.result_check([f]) is None

    def test_raises_for_mapped_tasks_with_poorly_specified_result_location(
        self, tmpdir
    ):
        @task(result=LocalResult(dir=tmpdir, location="{task_name}.txt"))
        def down(x):
            pass

        with Flow("upstream-test") as f:
            result = down.map(x=[1, 2, 3])

        with pytest.raises(ValueError, match="filename"):
            healthchecks.result_check([f])

    def test_raises_for_mapped_tasks_with_poorly_specified_result_location_on_flow(
        self, tmpdir
    ):
        @task
        def down(x):
            pass

        with Flow(
            "upstream-test", result=LocalResult(dir=tmpdir, location="my_path.txt")
        ) as f:
            result = down.map(x=[1, 2, 3])

        with pytest.raises(ValueError, match="filename"):
            healthchecks.result_check([f])

    @pytest.mark.parametrize(
        "kwargs",
        [
            dict(max_retries=2, retry_delay=datetime.timedelta(minutes=1)),
            dict(cache_for=datetime.timedelta(minutes=1)),
        ],
    )
    def test_doesnt_raise_for_tasks_with_non_keyed_edges(self, kwargs):
        @task
        def up():
            pass

        @task(**kwargs, result_handler=42)
        def down():
            pass

        with Flow("non-keyed-test") as f:
            result = down(upstream_tasks=[up])

        assert healthchecks.result_check([f]) is None


class TestEnvironmentDependencyCheck:
    def test_no_raise_on_normal_flow(self):
        flow = Flow("THIS IS A TEST")

        assert healthchecks.environment_dependency_check([flow]) is None

    def test_no_raise_on_remote_env(self):
        flow = Flow("THIS IS A TEST", environment=RemoteEnvironment())

        assert healthchecks.environment_dependency_check([flow]) is None

    def test_no_raise_on_proper_imports(self):
        class NewEnvironment(Environment):
            @property
            def dependencies(self) -> list:
                return ["prefect"]

        flow = Flow("THIS IS A TEST", environment=NewEnvironment())

        assert healthchecks.environment_dependency_check([flow]) is None

    def test_no_raise_on_missing_dependencies_property(self):
        class NewEnvironment(Environment):
            pass

        flow = Flow("THIS IS A TEST", environment=NewEnvironment())

        assert healthchecks.environment_dependency_check([flow]) is None

    def test_raise_on_missing_imports(self, monkeypatch):
        class NewEnvironment(Environment):
            @property
            def dependencies(self) -> list:
                return ["TEST"]

        flow = Flow("THIS IS A TEST", environment=NewEnvironment())

        with pytest.raises(ModuleNotFoundError):
            healthchecks.environment_dependency_check([flow])
