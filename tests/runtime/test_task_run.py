from typing import Any

import pytest

from prefect.client.schemas import TaskRun
from prefect.context import TaskRunContext
from prefect.runtime import task_run
from prefect.settings import PREFECT_API_URL, PREFECT_UI_URL
from prefect.tasks import Task


class TestAttributeAccessPatterns:
    async def test_access_unknown_attribute_fails(self):
        with pytest.raises(AttributeError, match="beep"):
            task_run.beep

    async def test_import_unknown_attribute_fails(self):
        with pytest.raises(ImportError, match="boop"):
            from prefect.runtime.task_run import boop  # noqa # type: ignore

    async def test_known_attributes_autocomplete(self):
        assert "id" in dir(task_run)
        assert "foo" not in dir(task_run)

    async def test_new_attribute_via_env_var(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(name="PREFECT__RUNTIME__TASK_RUN__NEW_KEY", value="foobar")
        assert task_run.new_key == "foobar"

    @pytest.mark.parametrize(
        "attribute_name, attribute_value, env_value, expected_value",
        [
            # check allowed types for existing attributes
            ("bool_attribute", True, "False", False),
            ("int_attribute", 10, "20", 20),
            ("float_attribute", 10.5, "20.5", 20.5),
            ("str_attribute", "foo", "bar", "bar"),
        ],
    )
    async def test_attribute_override_via_env_var(
        self,
        monkeypatch: pytest.MonkeyPatch,
        attribute_name: str,
        attribute_value: Any,
        env_value: str,
        expected_value: Any,
    ):
        # mock attribute_name to be a function that generates attribute_value
        monkeypatch.setitem(task_run.FIELDS, attribute_name, lambda: attribute_value)

        monkeypatch.setenv(
            name=f"PREFECT__RUNTIME__TASK_RUN__{attribute_name.upper()}",
            value=env_value,
        )
        tasks_run_attr = getattr(task_run, attribute_name)
        # check the type of the task_run attribute
        assert isinstance(tasks_run_attr, type(expected_value))
        # check the task_run attribute value is expected_value
        assert tasks_run_attr == expected_value

    @pytest.mark.parametrize(
        "attribute_name, attribute_value",
        [
            # complex types (list and dict) not allowed to be mocked using environment variables
            ("list_of_values", [1, 2, 3]),
            ("dict_of_values", {"foo": "bar"}),
        ],
    )
    async def test_attribute_override_via_env_var_not_allowed(
        self, monkeypatch: pytest.MonkeyPatch, attribute_name: str, attribute_value: Any
    ):
        # mock attribute_name to be a function that generates attribute_value
        monkeypatch.setitem(task_run.FIELDS, attribute_name, lambda: attribute_value)

        monkeypatch.setenv(
            name=f"PREFECT__RUNTIME__TASK_RUN__{attribute_name.upper()}", value="foo"
        )
        with pytest.raises(ValueError, match="cannot be mocked"):
            getattr(task_run, attribute_name)


class TestID:
    async def test_id_is_attribute(self):
        assert "id" in dir(task_run)

    async def test_id_is_none_when_not_set(self):
        assert task_run.id is None

    async def test_id_from_context(self):
        with TaskRunContext.model_construct(task_run=TaskRun.model_construct(id="foo")):
            assert task_run.id == "foo"


class TestTags:
    async def test_tags_is_attribute(self):
        assert "tags" in dir(task_run)

    async def test_tags_is_empty_when_not_set(self):
        assert task_run.tags == []

    async def test_tags_returns_tags_when_present_dynamically(self):
        with TaskRunContext.model_construct(
            task_run=TaskRun.model_construct(tags=["foo", "bar"])
        ):
            assert task_run.tags == ["foo", "bar"]


class TestRunCount:
    async def test_run_count_is_attribute(self):
        assert "run_count" in dir(task_run)

    async def test_run_count_is_zero_when_not_set(self):
        assert task_run.run_count == 0

    async def test_run_count_returns_run_count_when_present_dynamically(self):
        assert task_run.run_count == 0

        with TaskRunContext.model_construct(
            task_run=TaskRun.model_construct(id="foo", run_count=10)
        ):
            assert task_run.run_count == 10

        assert task_run.run_count == 0


class TestParameters:
    async def test_parameters_is_attribute(self):
        assert "parameters" in dir(task_run)

    async def test_parameters_is_dict_when_not_set(self):
        assert task_run.parameters == {}

    async def test_parameters_from_context(self):
        with TaskRunContext.model_construct(parameters={"x": "foo", "y": "bar"}):
            assert task_run.parameters == {"x": "foo", "y": "bar"}


class TestName:
    async def test_name_is_attribute(self):
        assert "name" in dir(task_run)

    async def test_name_is_none_when_not_set(self):
        assert task_run.name is None

    async def test_name_from_context(self):
        with TaskRunContext.model_construct(
            task_run=TaskRun.model_construct(name="foo")
        ):
            assert task_run.name == "foo"


class TestTaskName:
    async def test_task_name_is_attribute(self):
        assert "task_name" in dir(task_run)

    async def test_task_name_is_none_when_not_set(self):
        assert task_run.task_name is None

    async def test_task_name_from_context(self):
        with TaskRunContext.model_construct(task=Task(fn=lambda: None, name="foo")):
            assert task_run.task_name == "foo"


class TestURL:
    @pytest.mark.parametrize("url_type", ["api_url", "ui_url"])
    async def test_url_is_attribute(self, url_type: str):
        assert url_type in dir(task_run)

    @pytest.mark.parametrize("url_type", ["api_url", "ui_url"])
    async def test_url_is_none_when_id_not_set(self, url_type: str):
        assert getattr(task_run, url_type) is None

    @pytest.mark.parametrize(
        "url_type,",
        ["api_url", "ui_url"],
    )
    async def test_url_returns_correct_url_when_id_present(
        self,
        url_type: str,
    ):
        test_id = "12345"
        if url_type == "api_url":
            base_url_value = PREFECT_API_URL.value()
        elif url_type == "ui_url":
            base_url_value = PREFECT_UI_URL.value()
        else:
            raise ValueError(f"Invalid url_type: {url_type}")

        expected_url = f"{base_url_value}/runs/task-run/{test_id}"

        with TaskRunContext.model_construct(
            task_run=TaskRun.model_construct(id=test_id)
        ):
            assert getattr(task_run, url_type) == expected_url

        assert not getattr(task_run, url_type)
