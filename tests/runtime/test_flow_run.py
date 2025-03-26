import dataclasses
import datetime
from typing import Any

import pytest

from prefect import flow, states, tags, task
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import FlowRun, TaskRun
from prefect.context import FlowRunContext, TaskRunContext
from prefect.flows import Flow
from prefect.runtime import flow_run
from prefect.settings import PREFECT_API_URL, PREFECT_UI_URL
from prefect.types._datetime import DateTime, Timezone, now


class TestAttributeAccessPatterns:
    async def test_access_unknown_attribute_fails(self):
        with pytest.raises(AttributeError, match="beep"):
            flow_run.beep

    async def test_import_unknown_attribute_fails(self):
        with pytest.raises(ImportError, match="boop"):
            from prefect.runtime.flow_run import boop  # noqa # type: ignore

    async def test_known_attributes_autocomplete(self):
        assert "id" in dir(flow_run)
        assert "foo" not in dir(flow_run)

    async def test_new_attribute_via_env_var(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(name="PREFECT__RUNTIME__FLOW_RUN__NEW_KEY", value="foobar")
        assert flow_run.new_key == "foobar"

    @pytest.mark.parametrize(
        "attribute_name, attribute_value, env_value, expected_value",
        [
            # check allowed types for existing attributes
            ("bool_attribute", True, "False", False),
            ("int_attribute", 10, "20", 20),
            ("float_attribute", 10.5, "20.5", 20.5),
            ("str_attribute", "foo", "bar", "bar"),
            (
                "datetime_attribute",
                DateTime(2022, 1, 1, 0, tzinfo=Timezone("UTC")),
                "2023-05-13 20:00:00",
                DateTime(2023, 5, 13, 20, tzinfo=Timezone("UTC")),
            ),
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
        monkeypatch.setitem(flow_run.FIELDS, attribute_name, lambda: attribute_value)

        monkeypatch.setenv(
            name=f"PREFECT__RUNTIME__FLOW_RUN__{attribute_name.upper()}",
            value=env_value,
        )
        flow_run_attr = getattr(flow_run, attribute_name)
        # check the type of the flow_run attribute
        assert isinstance(flow_run_attr, type(expected_value))
        # check the flow_run attribute value is expected_value
        assert flow_run_attr == expected_value

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
        monkeypatch.setitem(flow_run.FIELDS, attribute_name, lambda: attribute_value)

        monkeypatch.setenv(
            name=f"PREFECT__RUNTIME__FLOW_RUN__{attribute_name.upper()}", value="foo"
        )
        with pytest.raises(ValueError, match="cannot be mocked"):
            getattr(flow_run, attribute_name)


class TestID:
    """
    This class may appear to reproduce some tests from the AttributeAccessPatterns tests
    but is intended to be copy / pastable for other new attributes to ensure full coverage of
    feature set for each attribute.
    """

    async def test_id_is_attribute(self):
        assert "id" in dir(flow_run)

    async def test_id_is_none_when_not_set(self):
        assert flow_run.id is None

    async def test_id_uses_env_var_when_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value="foo")
        assert flow_run.id == "foo"

    async def test_id_prioritizes_context_info_over_env_var_dynamically(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value="foo")

        assert flow_run.id == "foo"

        @flow
        def flow_with_new_id():
            return flow_run.id

        new_id = flow_with_new_id()
        assert isinstance(new_id, str)
        assert flow_with_new_id() != "foo"
        assert flow_run.id == "foo"

    async def test_id_can_be_retrieved_from_task_run_context(self):
        with TaskRunContext.model_construct(
            task_run=TaskRun.model_construct(flow_run_id="foo")
        ):
            assert flow_run.id == "foo"


class TestTags:
    async def test_tags_is_attribute(self):
        assert "tags" in dir(flow_run)

    async def test_tags_is_empty_when_not_set(self):
        assert flow_run.tags == []

    async def test_tags_returns_tags_when_present_dynamically(self):
        assert flow_run.tags == []

        @flow
        def run_with_tags():
            return flow_run.tags

        with tags("foo", "bar"):
            assert set(run_with_tags()) == {"foo", "bar"}

        assert flow_run.tags == []

    async def test_tags_pulls_from_api_when_needed(
        self, monkeypatch: pytest.MonkeyPatch, prefect_client: PrefectClient
    ):
        run = await prefect_client.create_flow_run(
            flow=flow(lambda: None, name="test"), tags=["red", "green"]
        )
        assert flow_run.tags == []

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert set(flow_run.tags) == {"red", "green"}


class TestRunCount:
    async def test_run_count_is_attribute(self):
        assert "run_count" in dir(flow_run)

    async def test_run_count_is_zero_when_not_set(self):
        assert flow_run.run_count == 0

    async def test_run_count_returns_run_count_when_present_dynamically(self):
        assert flow_run.run_count == 0

        with FlowRunContext.model_construct(
            flow_run=FlowRun.model_construct(id="foo", run_count=10)
        ):
            assert flow_run.run_count == 10

        assert flow_run.run_count == 0

    async def test_run_count_from_api(
        self, monkeypatch: pytest.MonkeyPatch, prefect_client: PrefectClient
    ):
        run = await prefect_client.create_flow_run(
            flow=flow(lambda: None, name="test", retries=5)
        )
        assert flow_run.run_count == 0

        await prefect_client.set_flow_run_state(
            flow_run_id=run.id, state=states.Retrying()
        )

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert flow_run.run_count == 1


class TestStartTime:
    async def test_scheduled_start_time_is_attribute(self):
        assert "scheduled_start_time" in dir(flow_run)

    async def test_scheduled_start_time_is_timestamp_when_not_set(self):
        assert isinstance(flow_run.scheduled_start_time, datetime.datetime)

    async def test_scheduled_start_time_pulls_from_api_when_needed(
        self, monkeypatch: pytest.MonkeyPatch, prefect_client: PrefectClient
    ):
        TIMESTAMP = now("UTC") + datetime.timedelta(days=7)
        run = await prefect_client.create_flow_run(
            flow=flow(lambda: None, name="test"),
            state=states.Scheduled(scheduled_time=TIMESTAMP),
        )
        assert flow_run.scheduled_start_time != TIMESTAMP

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert flow_run.scheduled_start_time == TIMESTAMP


class TestName:
    async def test_name_is_attribute(self):
        assert "name" in dir(flow_run)

    async def test_name_is_empty_when_not_set(self):
        assert flow_run.name is None

    async def test_name_returns_name_when_present_dynamically(self):
        assert flow_run.name is None

        with FlowRunContext.model_construct(
            flow_run=FlowRun.model_construct(name="foo")
        ):
            assert flow_run.name == "foo"

        assert flow_run.name is None

    async def test_name_pulls_from_api_when_needed(
        self, monkeypatch: pytest.MonkeyPatch, prefect_client: PrefectClient
    ):
        run = await prefect_client.create_flow_run(
            flow=flow(lambda: None, name="test"), name="foo"
        )
        assert flow_run.name is None

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert flow_run.name == "foo"


class TestFlowName:
    async def test_flow_name_is_attribute(self):
        assert "flow_name" in dir(flow_run)

    async def test_flow_name_is_empty_when_not_set(self):
        assert flow_run.flow_name is None

    async def test_flow_name_returns_flow_name_when_present_dynamically(self):
        assert flow_run.flow_name is None

        with FlowRunContext.model_construct(
            flow_run=FlowRun.model_construct(), flow=Flow(fn=lambda: None, name="foo")
        ):
            assert flow_run.flow_name == "foo"

        assert flow_run.flow_name is None

    async def test_flow_name_pulls_from_api_when_needed(
        self, monkeypatch: pytest.MonkeyPatch, prefect_client: PrefectClient
    ):
        run = await prefect_client.create_flow_run(
            flow=flow(lambda: None, name="foo"), name="bar"
        )
        assert flow_run.flow_name is None

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert flow_run.flow_name == "foo"


class TestParameters:
    async def test_parameters_is_attribute(self):
        assert "parameters" in dir(flow_run)

    async def test_parameters_is_dict_when_not_set(self):
        assert flow_run.parameters == {}

    async def test_parameters_from_context(self):
        with FlowRunContext.model_construct(
            flow_run=FlowRun.model_construct(id="foo"),
            parameters={"x": "foo", "y": "bar"},
        ):
            assert flow_run.parameters == {"x": "foo", "y": "bar"}

    async def test_parameters_from_api(
        self, monkeypatch: pytest.MonkeyPatch, prefect_client: PrefectClient
    ):
        run = await prefect_client.create_flow_run(
            flow=flow(lambda: None, name="foo"), parameters={"x": "foo", "y": "bar"}
        )

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))
        assert flow_run.parameters == {"x": "foo", "y": "bar"}

    async def test_within_flow_run_uses_unserialized_parameters(self):
        @dataclasses.dataclass
        class Foo:
            y: int

        foo = Foo(y=1)

        @flow
        def my_flow(x):
            return flow_run.parameters

        assert my_flow(foo) == {"x": foo}

    async def test_outside_flow_run_uses_serialized_parameters(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        @dataclasses.dataclass
        class Foo:
            y: int

        foo = Foo(y=1)

        @flow
        def my_flow(x):
            return flow_run.get_id()

        flow_run_id = my_flow(foo)

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=flow_run_id)
        assert flow_run.parameters == {"x": {"y": 1}}


class TestParentFlowRunId:
    async def test_parent_flow_run_id_is_attribute(self):
        assert "parent_flow_run_id" in dir(flow_run)

    async def test_parent_flow_run_id_is_empty_when_not_set(self):
        assert flow_run.parent_flow_run_id is None

    async def test_parent_flow_run_id_returns_parent_flow_run_id_when_present_dynamically(
        self, prefect_client: PrefectClient
    ):
        assert flow_run.parent_flow_run_id is None

        with FlowRunContext.model_construct(
            flow_run=FlowRun.model_construct(parent_task_run_id=None),
            flow=Flow(fn=lambda: None, name="foo"),
        ):
            assert flow_run.parent_flow_run_id is None

        parent_flow_run = await prefect_client.create_flow_run(
            flow=Flow(fn=lambda: None, name="foo2"), parameters={"x": "foo", "y": "bar"}
        )

        @task
        def foo():
            return 1

        parent_task_run = await prefect_client.create_task_run(
            task=foo, dynamic_key="1", flow_run_id=parent_flow_run.id
        )

        with FlowRunContext.model_construct(
            flow_run=FlowRun.model_construct(parent_task_run_id=parent_task_run.id),
            flow=Flow(fn=lambda: None, name="foo3"),
        ):
            assert (
                flow_run.parent_flow_run_id
                == str(parent_flow_run.id)
                == str(parent_task_run.flow_run_id)
            )

        assert flow_run.parent_flow_run_id is None

    async def test_parent_flow_run_id_pulls_from_api_when_needed(
        self, monkeypatch: pytest.MonkeyPatch, prefect_client: PrefectClient
    ):
        assert flow_run.parent_flow_run_id is None

        parent_flow_run = await prefect_client.create_flow_run(
            flow=Flow(fn=lambda: None, name="parent"),
            parameters={"x": "foo", "y": "bar"},
        )

        @task
        def foo():
            return 1

        parent_task_run = await prefect_client.create_task_run(
            task=foo, dynamic_key="1", flow_run_id=parent_flow_run.id
        )

        child_flow_run = await prefect_client.create_flow_run(
            flow=Flow(fn=lambda: None, name="child"),
            parameters={"x": "foo", "y": "bar"},
            parent_task_run_id=parent_task_run.id,
        )

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(child_flow_run.id))
        assert (
            flow_run.parent_flow_run_id
            == str(parent_flow_run.id)
            == str(parent_task_run.flow_run_id)
        )

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(parent_flow_run.id))
        assert flow_run.parent_flow_run_id is None


class TestParentDeploymentId:
    async def test_parent_deployment_id_is_attribute(self):
        assert "parent_deployment_id" in dir(flow_run)

    async def test_parent_deployment_id_is_empty_when_not_set(self):
        assert flow_run.parent_deployment_id is None

    async def test_parent_deployment_id_returns_parent_deployment_id_when_present_dynamically(
        self, prefect_client: PrefectClient
    ):
        assert flow_run.parent_deployment_id is None

        @flow
        def parent():
            return 1

        @task
        def foo():
            return 1

        parent_flow_id = await prefect_client.create_flow(parent)

        # Parent flow run that does not have a deployment
        parent_flow_run_no_deployment = await prefect_client.create_flow_run(
            flow=parent,
        )
        parent_task_run_no_deployment = await prefect_client.create_task_run(
            task=foo, dynamic_key="1", flow_run_id=parent_flow_run_no_deployment.id
        )
        with FlowRunContext.model_construct(
            flow_run=FlowRun.model_construct(
                parent_task_run_id=parent_task_run_no_deployment.id
            ),
            flow=Flow(fn=lambda: None, name="child-flow-no-deployment"),
        ):
            assert flow_run.parent_deployment_id is None

        # Parent flow run that does have a deployment
        parent_flow_deployment_id = await prefect_client.create_deployment(
            flow_id=parent_flow_id,
            name="example",
        )
        parent_flow_run_with_deployment = (
            await prefect_client.create_flow_run_from_deployment(
                deployment_id=parent_flow_deployment_id,
            )
        )
        parent_task_run_with_deployment = await prefect_client.create_task_run(
            task=foo, dynamic_key="1", flow_run_id=parent_flow_run_with_deployment.id
        )
        with FlowRunContext.model_construct(
            flow_run=FlowRun.model_construct(
                parent_task_run_id=parent_task_run_with_deployment.id
            ),
            flow=Flow(fn=lambda: None, name="child-flow-with-parent-deployment"),
        ):
            assert flow_run.parent_deployment_id == str(parent_flow_deployment_id)

        # No parent flow run
        with FlowRunContext.model_construct(
            flow_run=FlowRun.model_construct(parent_task_run_id=None),
            flow=Flow(fn=lambda: None, name="child-flow-no-parent-task-run"),
        ):
            assert flow_run.parent_deployment_id is None

    async def test_parent_deployment_id_pulls_from_api_when_needed(
        self, monkeypatch: pytest.MonkeyPatch, prefect_client: PrefectClient
    ):
        assert flow_run.parent_deployment_id is None

        @flow
        def parent():
            return 1

        @task
        def foo():
            return 1

        parent_flow_id = await prefect_client.create_flow(parent)

        # Parent flow run that does not have a deployment
        parent_flow_run_no_deployment = await prefect_client.create_flow_run(
            flow=parent,
        )

        parent_task_run_no_deployment = await prefect_client.create_task_run(
            task=foo, dynamic_key="1", flow_run_id=parent_flow_run_no_deployment.id
        )

        child_flow_run_no_deployment = await prefect_client.create_flow_run(
            flow=Flow(fn=lambda: None, name="child-no-deploy"),
            parameters={"x": "foo", "y": "bar"},
            parent_task_run_id=parent_task_run_no_deployment.id,
        )

        monkeypatch.setenv(
            name="PREFECT__FLOW_RUN_ID", value=str(child_flow_run_no_deployment.id)
        )
        assert flow_run.parent_deployment_id is None

        # Parent flow run that does have a deployment
        parent_flow_deployment_id = await prefect_client.create_deployment(
            flow_id=parent_flow_id,
            name="example",
        )

        parent_flow_run_with_deployment = (
            await prefect_client.create_flow_run_from_deployment(
                deployment_id=parent_flow_deployment_id,
            )
        )

        parent_task_run_with_deployment = await prefect_client.create_task_run(
            task=foo, dynamic_key="1", flow_run_id=parent_flow_run_with_deployment.id
        )

        child_flow_run_with_deployment = await prefect_client.create_flow_run(
            flow=Flow(fn=lambda: None, name="child-deploy"),
            parameters={"x": "foo", "y": "bar"},
            parent_task_run_id=parent_task_run_with_deployment.id,
        )

        monkeypatch.setenv(
            name="PREFECT__FLOW_RUN_ID", value=str(child_flow_run_with_deployment.id)
        )
        assert flow_run.parent_deployment_id == str(parent_flow_deployment_id)

        # No parent flow run
        monkeypatch.setenv(
            name="PREFECT__FLOW_RUN_ID", value=str(parent_flow_run_no_deployment.id)
        )
        assert flow_run.parent_deployment_id is None


class TestRootFlowRunId:
    async def test_root_flow_run_id_is_attribute(self):
        assert "root_flow_run_id" in dir(flow_run)

    async def test_root_flow_run_id_is_empty_when_not_set(self):
        assert flow_run.root_flow_run_id is None

    async def test_root_flow_run_id_pulls_from_api_when_needed(
        self, monkeypatch: pytest.MonkeyPatch, prefect_client: PrefectClient
    ):
        assert flow_run.root_flow_run_id is None

        root_flow_run = await prefect_client.create_flow_run(
            flow=Flow(fn=lambda: None, name="root"),
            parameters={"x": "foo", "y": "bar"},
            parent_task_run_id=None,
        )

        @task
        def root_task():
            return 1

        root_task_run = await prefect_client.create_task_run(
            task=root_task,
            dynamic_key="1",
            flow_run_id=root_flow_run.id,
        )

        child_flow_run = await prefect_client.create_flow_run(
            flow=Flow(fn=lambda: None, name="child"),
            parameters={"x": "foo", "y": "bar"},
            parent_task_run_id=root_task_run.id,
        )

        @task
        def child_task():
            return 1

        child_task_run = await prefect_client.create_task_run(
            task=child_task,
            dynamic_key="1",
            flow_run_id=child_flow_run.id,
        )

        deep_flow_run = await prefect_client.create_flow_run(
            flow=Flow(fn=lambda: None, name="deep"),
            parameters={"x": "foo", "y": "bar"},
            parent_task_run_id=child_task_run.id,
        )

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(deep_flow_run.id))
        assert (
            flow_run.root_flow_run_id
            == str(root_flow_run.id)
            == str(root_task_run.flow_run_id)
        )

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(root_flow_run.id))
        assert flow_run.root_flow_run_id == str(root_flow_run.id)


class TestURL:
    @pytest.mark.parametrize("url_type", ["api_url", "ui_url"])
    async def test_url_is_attribute(self, url_type: str):
        assert url_type in dir(flow_run)

    @pytest.mark.parametrize("url_type", ["api_url", "ui_url"])
    async def test_url_is_none_when_id_not_set(self, url_type: str):
        assert getattr(flow_run, url_type) is None

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

        expected_url = f"{base_url_value}/flow-runs/flow-run/{test_id}"

        with FlowRunContext.model_construct(
            flow_run=FlowRun.model_construct(id=test_id)
        ):
            assert getattr(flow_run, url_type) == expected_url

        assert not getattr(flow_run, url_type)

    @pytest.mark.parametrize(
        "url_type,",
        ["api_url", "ui_url"],
    )
    async def test_url_pulls_from_api_when_needed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        prefect_client: PrefectClient,
        url_type: str,
    ):
        run = await prefect_client.create_flow_run(flow=flow(lambda: None, name="test"))

        assert not getattr(flow_run, url_type)

        if url_type == "api_url":
            base_url_value = PREFECT_API_URL.value()
        elif url_type == "ui_url":
            base_url_value = PREFECT_UI_URL.value()
        else:
            raise ValueError(f"Invalid url_type: {url_type}")

        expected_url = f"{base_url_value}/flow-runs/flow-run/{str(run.id)}"

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert getattr(flow_run, url_type) == expected_url


class TestJobVariables:
    async def test_job_variables_is_attribute(self):
        assert "job_variables" in dir(flow_run)

    async def test_job_variables_is_none_when_not_set(self):
        assert flow_run.job_variables is None

    async def test_job_variables_returns_variables_when_present_dynamically(self):
        assert flow_run.job_variables is None

        with FlowRunContext.model_construct(
            flow_run=FlowRun.model_construct(job_variables={"foo": "bar"})
        ):
            assert flow_run.job_variables == {"foo": "bar"}

        assert flow_run.job_variables is None
