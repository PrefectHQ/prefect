import dataclasses
import datetime

import pendulum
import pytest

from prefect import flow, states, tags
from prefect.client.schemas import FlowRun, TaskRun
from prefect.context import FlowRunContext, TaskRunContext
from prefect.flows import Flow
from prefect.runtime import flow_run


class TestAttributeAccessPatterns:
    async def test_access_unknown_attribute_fails(self):
        with pytest.raises(AttributeError, match="beep"):
            flow_run.beep

    async def test_import_unknown_attribute_fails(self):
        with pytest.raises(ImportError, match="boop"):
            from prefect.runtime.flow_run import boop  # noqa

    async def test_known_attributes_autocomplete(self):
        assert "id" in dir(flow_run)
        assert "foo" not in dir(flow_run)

    async def test_attribute_override_via_env_var(self, monkeypatch):
        monkeypatch.setenv(name="PREFECT__RUNTIME__FLOW_RUN__NEW_KEY", value="foobar")
        assert flow_run.new_key == "foobar"


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

    async def test_id_uses_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value="foo")
        assert flow_run.id == "foo"

    async def test_id_prioritizes_context_info_over_env_var_dynamically(
        self, monkeypatch
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
        with TaskRunContext.construct(task_run=TaskRun.construct(flow_run_id="foo")):
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

    async def test_tags_pulls_from_api_when_needed(self, monkeypatch, orion_client):
        run = await orion_client.create_flow_run(
            flow=flow(lambda: None, name="test"), tags=["red", "green"]
        )
        assert flow_run.tags == []

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert set(flow_run.tags) == {"red", "green"}


class TestStartTime:
    async def test_scheduled_start_time_is_attribute(self):
        assert "scheduled_start_time" in dir(flow_run)

    async def test_scheduled_start_time_is_timestamp_when_not_set(self):
        assert isinstance(flow_run.scheduled_start_time, datetime.datetime)

    async def test_scheduled_start_time_pulls_from_api_when_needed(
        self, monkeypatch, orion_client
    ):
        TIMESTAMP = pendulum.now("utc").add(days=7)
        run = await orion_client.create_flow_run(
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

        with FlowRunContext.construct(flow_run=FlowRun.construct(name="foo")):
            assert flow_run.name == "foo"

        assert flow_run.name is None

    async def test_name_pulls_from_api_when_needed(self, monkeypatch, orion_client):
        run = await orion_client.create_flow_run(
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

        with FlowRunContext.construct(
            flow_run=FlowRun.construct(), flow=Flow(fn=lambda: None, name="foo")
        ):
            assert flow_run.flow_name == "foo"

        assert flow_run.flow_name is None

    async def test_flow_name_pulls_from_api_when_needed(
        self, monkeypatch, orion_client
    ):
        run = await orion_client.create_flow_run(
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
        with FlowRunContext.construct(
            flow_run=FlowRun.construct(id="foo"), parameters={"x": "foo", "y": "bar"}
        ):
            assert flow_run.parameters == {"x": "foo", "y": "bar"}

    async def test_parameters_from_api(self, monkeypatch, orion_client):
        run = await orion_client.create_flow_run(
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

    async def test_outside_flow_run_uses_serialized_parameters(self, monkeypatch):
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
