import pytest

from prefect.client.schemas import TaskRun
from prefect.context import TaskRunContext
from prefect.runtime import task_run
from prefect.tasks import Task


class TestAttributeAccessPatterns:
    async def test_access_unknown_attribute_fails(self):
        with pytest.raises(AttributeError, match="beep"):
            task_run.beep

    async def test_import_unknown_attribute_fails(self):
        with pytest.raises(ImportError, match="boop"):
            from prefect.runtime.task_run import boop  # noqa

    async def test_known_attributes_autocomplete(self):
        assert "id" in dir(task_run)
        assert "foo" not in dir(task_run)

    @pytest.mark.parametrize(
        "env_name, env_value, expected_value",
        [
            # new user defined env var
            ("new_key", "foobar", "foobar"),
            # KNOWN FIELDS
            # id is of type str
            ("id", "fake-id", "fake-id"),
            # name is of type str
            ("name", "fake-name", "fake-name"),
            # flow_name is of type str
            ("task_name", "fake-task-name", "fake-task-name"),
        ],
    )
    async def test_attribute_override_via_env_var(
        self, monkeypatch, env_name, env_value, expected_value
    ):
        monkeypatch.setenv(
            name=f"PREFECT__RUNTIME__TASK_RUN__{env_name.upper()}", value=env_value
        )
        tasks_run_attr = getattr(task_run, env_name)
        # check the type of the flow_run attribute
        assert isinstance(tasks_run_attr, type(expected_value))
        # check the flow_run attribute value is expected_value
        assert tasks_run_attr == expected_value

    @pytest.mark.parametrize(
        "env_name",
        [
            # complex types (list and dict) not allowed to be mocked using environment variables
            "tags",
            "parameters",
        ],
    )
    async def test_attribute_override_via_env_var_not_allowed(
        self, monkeypatch, env_name
    ):
        monkeypatch.setenv(
            name=f"PREFECT__RUNTIME__TASK_RUN__{env_name.upper()}", value="foo"
        )
        with pytest.raises(ValueError, match="cannot be mocked"):
            getattr(task_run, env_name)


class TestID:
    async def test_id_is_attribute(self):
        assert "id" in dir(task_run)

    async def test_id_is_none_when_not_set(self):
        assert task_run.id is None

    async def test_id_from_context(self):
        with TaskRunContext.construct(task_run=TaskRun.construct(id="foo")):
            assert task_run.id == "foo"


class TestTags:
    async def test_tags_is_attribute(self):
        assert "tags" in dir(task_run)

    async def test_tags_is_empty_when_not_set(self):
        assert task_run.tags == []

    async def test_tags_returns_tags_when_present_dynamically(self):
        with TaskRunContext.construct(task_run=TaskRun.construct(tags=["foo", "bar"])):
            assert task_run.tags == ["foo", "bar"]


class TestParameters:
    async def test_parameters_is_attribute(self):
        assert "parameters" in dir(task_run)

    async def test_parameters_is_dict_when_not_set(self):
        assert task_run.parameters == {}

    async def test_parameters_from_context(self):
        with TaskRunContext.construct(parameters={"x": "foo", "y": "bar"}):
            assert task_run.parameters == {"x": "foo", "y": "bar"}


class TestName:
    async def test_name_is_attribute(self):
        assert "name" in dir(task_run)

    async def test_name_is_none_when_not_set(self):
        assert task_run.name is None

    async def test_name_from_context(self):
        with TaskRunContext.construct(task_run=TaskRun.construct(name="foo")):
            assert task_run.name == "foo"


class TestTaskName:
    async def test_task_name_is_attribute(self):
        assert "task_name" in dir(task_run)

    async def test_task_name_is_none_when_not_set(self):
        assert task_run.task_name is None

    async def test_task_name_from_context(self):
        with TaskRunContext.construct(task=Task(fn=lambda: None, name="foo")):
            assert task_run.task_name == "foo"
