from datetime import timedelta
import pendulum
import pytest
import logging
from uuid import uuid4
from unittest.mock import MagicMock

import prefect
from prefect.client.client import FlowRunInfoResult, ProjectInfo
from prefect.engine import signals, state

from prefect.run_configs import UniversalRun
from prefect.backend.flow_run import FlowRunLog
from prefect.engine.results.local_result import LocalResult


from prefect.tasks.prefect import (
    create_flow_run,
    wait_for_flow_run,
    get_task_run_result,
)


@pytest.fixture
def MockClient(monkeypatch):
    Client = MagicMock()
    monkeypatch.setattr("prefect.tasks.prefect.flow_run.Client", Client)
    return Client


@pytest.fixture
def MockFlowView(monkeypatch):
    FlowView = MagicMock()
    monkeypatch.setattr("prefect.tasks.prefect.flow_run.FlowView", FlowView)
    return FlowView


@pytest.fixture
def MockFlowRunView(monkeypatch):
    FlowRunView = MagicMock()
    monkeypatch.setattr("prefect.backend.flow_run.FlowRunView", FlowRunView)
    monkeypatch.setattr("prefect.tasks.prefect.flow_run.FlowRunView", FlowRunView)
    return FlowRunView


class TestCreateFlowRun:
    def test_does_not_accept_both_id_and_name(self):
        with pytest.raises(ValueError, match="Received both `flow_id` and `flow_name`"):
            create_flow_run.run(flow_id=uuid4(), flow_name="foo")

    def test_requires_id_or_name(self):
        with pytest.raises(ValueError, match="`flow_id` and `flow_name` are null"):
            create_flow_run.run(flow_id=None, flow_name=None)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"flow_id": "flow-id"},
            {"flow_name": "flow-name"},
            {"flow_name": "flow-name", "project_name": "project-name"},
        ],
    )
    def test_lookup_uses_given_identifiers(self, kwargs, MockFlowView, MockClient):
        create_flow_run.run(**kwargs)
        if "flow_id" in kwargs:
            MockFlowView.from_id.assert_called_once_with("flow-id")
        elif "flow_name" in kwargs:
            MockFlowView.from_flow_name.assert_called_once_with(
                "flow-name", project_name=kwargs.get("project_name", "")
            )

    def test_creates_flow_run_with_defaults(self, MockFlowView, MockClient):
        MockFlowView.from_id.return_value.flow_id = "flow-id"
        create_flow_run.run(flow_id="flow-id")
        MockClient().create_flow_run.assert_called_once_with(
            flow_id="flow-id",
            parameters=None,
            run_name=None,
            labels=None,
            context=None,
            run_config=None,
            scheduled_start_time=None,
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"parameters": dict(x=1, y="foo")},
            {"run_name": "run-name"},
            {"labels": ["a", "b"]},
            {"context": {"var": "val"}},
            {"run_config": UniversalRun(env={"x"})},
            {"scheduled_start_time": pendulum.now().add(days=1)},
        ],
    )
    def test_creates_flow_with_given_settings(self, MockFlowView, MockClient, kwargs):
        MockFlowView.from_id.return_value.flow_id = "flow-id"
        create_flow_run.run(flow_id="flow-id", **kwargs)
        MockClient().create_flow_run.assert_called_once_with(
            flow_id="flow-id",
            parameters=kwargs.get("parameters"),
            run_name=kwargs.get("run_name"),
            labels=kwargs.get("labels"),
            context=kwargs.get("context"),
            run_config=kwargs.get("run_config"),
            scheduled_start_time=kwargs.get("scheduled_start_time"),
        )

    def test_generates_run_name_from_parent_and_child(self, MockFlowView, MockClient):
        MockFlowView.from_id.return_value.flow_id = "flow-id"
        MockFlowView.from_id.return_value.name = "child-name"
        with prefect.context(flow_run_name="parent-run"):
            create_flow_run.run(flow_id="flow-id")
        MockClient().create_flow_run.assert_called_once_with(
            flow_id="flow-id",
            parameters=None,
            run_name="parent-run-child-name",
            labels=None,
            context=None,
            run_config=None,
            scheduled_start_time=None,
        )

    def test_returns_flow_run_idl(self, MockFlowView, MockClient):
        MockClient().create_flow_run.return_value = "flow-run-id"
        result = create_flow_run.run(flow_id="flow-id")
        assert result == "flow-run-id"

    def test_displays_flow_run_url(self, MockFlowView, MockClient, caplog):
        MockClient().create_flow_run.return_value = "flow-run-id"
        MockClient().get_cloud_url.return_value = "fake-url"
        create_flow_run.run(flow_id="flow-id")
        MockClient().get_cloud_url.assert_called_once_with(
            "flow-run", "flow-run-id", as_user=False
        )
        assert "Created flow run '<generated-name>': fake-url" in caplog.text


class TestWaitForFlowRun:
    @pytest.fixture
    def mock_watch_flow_run(self, monkeypatch):
        watch_flow_run = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.prefect.flow_run.watch_flow_run", watch_flow_run
        )
        return watch_flow_run

    def test_logs_include_flow_run_name_and_level(
        self, MockFlowRunView, mock_watch_flow_run, caplog
    ):
        MockFlowRunView.from_flow_run_id.return_value.name = "fake-run-name"
        run_logs = [
            FlowRunLog(
                timestamp=pendulum.now(), level=logging.INFO, message="Log message"
            ),
            FlowRunLog(
                timestamp=pendulum.now(), level=logging.ERROR, message="Another log"
            ),
        ]
        mock_watch_flow_run.return_value = run_logs
        wait_for_flow_run.run("flow-run-id")
        for record, run_log in zip(caplog.records, run_logs):
            assert record.levelno == run_log.level
            assert record.msg == f"Flow 'fake-run-name': {run_log.message}"

    @pytest.mark.parametrize("stream_logs", [True, False])
    @pytest.mark.parametrize("stream_states", [True, False])
    def test_passes_args_to_watch_flow_run(
        self, mock_watch_flow_run, stream_logs, stream_states, MockFlowRunView
    ):
        wait_for_flow_run.run(
            "flow-run-id", stream_states=stream_states, stream_logs=stream_logs
        )
        mock_watch_flow_run.assert_called_once_with(
            "flow-run-id", stream_states=stream_states, stream_logs=stream_logs
        )

    def test_returns_latest_flow_run_view(self, mock_watch_flow_run, MockFlowRunView):
        MockFlowRunView.from_flow_run_id().get_latest.return_value = "fake-return-value"
        result = wait_for_flow_run.run("flow-run-id")
        assert result == "fake-return-value"


class TestGetTaskRunResult:
    def test_requires_task_slug(self):
        with pytest.raises(ValueError, match="`task_slug` is empty"):
            get_task_run_result.run(flow_run_id="id", task_slug="")

    def test_does_not_allow_current_flow_run(self):
        with prefect.context(flow_run_id="id"):
            with pytest.raises(
                ValueError,
                match="`flow_run_id` is the same as the currently running flow",
            ):
                get_task_run_result.run(flow_run_id="id", task_slug="foo")

    def test_waits_for_flow_run_to_finish(self, MockFlowRunView, monkeypatch):
        # Create a fake flow run that is 'Running' then 'Finished'
        flow_run = MagicMock()
        flow_run.state = prefect.engine.state.Running()

        def mark_flow_run_as_finished():
            flow_run.state = prefect.engine.state.Finished()
            return flow_run

        flow_run.get_latest.side_effect = mark_flow_run_as_finished

        # Return the fake flow run during retrieval
        MockFlowRunView.from_flow_run_id.return_value = flow_run

        # Mock sleep so the test is not slow
        mock_sleep = MagicMock()
        monkeypatch.setattr("prefect.tasks.prefect.flow_run.time.sleep", mock_sleep)

        get_task_run_result.run(flow_run_id="id", task_slug="slug", poll_time=1)

        # Should have slept once for the given poll time
        mock_sleep.assert_called_once_with(1)

    @pytest.mark.parametrize("kwargs", [{}, {"map_index": 5}])
    def test_gets_task_run_result(self, MockFlowRunView, monkeypatch, kwargs, caplog):
        task_run = MagicMock()
        task_run.get_result.return_value = "fake-result"
        # Provide a Result class so we can assert it is logged
        task_run.state._result = LocalResult()

        flow_run = MagicMock()
        flow_run.state = prefect.engine.state.Finished()
        flow_run.get_task_run.return_value = task_run
        MockFlowRunView.from_flow_run_id.return_value = flow_run

        # Ensure we aren't sleeping on already finished runs
        mock_sleep = MagicMock(
            side_effect=RuntimeError(
                "Sleep should not be called for a fnished flow run."
            )
        )
        monkeypatch.setattr("prefect.tasks.prefect.flow_run.time.sleep", mock_sleep)

        result = get_task_run_result.run(flow_run_id="id", task_slug="slug", **kwargs)

        mock_sleep.assert_not_called()

        # Task pulled from the flow run, map_index passed through if given
        flow_run.get_task_run.assert_called_once_with(
            task_slug="slug", map_index=kwargs.get("map_index", -1)
        )

        # Result loaded from storage
        task_run.get_result.assert_called_once()
        assert result == "fake-result"

        # Result type logged
        assert "Loading task run result from LocalResult..." in caplog.text


# Legacy tests -------------------------------------------------------------------------

from prefect.tasks.prefect.flow_run import StartFlowRun


@pytest.fixture()
def client(monkeypatch):
    cloud_client = MagicMock(
        graphql=MagicMock(
            return_value=MagicMock(
                data=MagicMock(flow=[MagicMock(id="abc123"), MagicMock(id="def456")])
            )
        ),
        create_flow_run=MagicMock(return_value="xyz890"),
        get_cloud_url=MagicMock(return_value="https://api.prefect.io/flow/run/url"),
        create_task_run_artifact=MagicMock(return_value="id"),
        get_flow_run_info=MagicMock(
            return_value=FlowRunInfoResult(
                id="my-flow-run-id",
                name="test-run",
                flow_id="xyz890",
                version=1,
                task_runs=[],
                state=state.Success(),
                scheduled_start_time=None,
                project=ProjectInfo(id="my-project-id", name="Test Project"),
                parameters={"test": "ing"},
                context={},
            )
        ),
    )
    monkeypatch.setattr(
        "prefect.tasks.prefect.flow_run.Client", MagicMock(return_value=cloud_client)
    )
    monkeypatch.setattr(
        "prefect.artifacts.Client", MagicMock(return_value=cloud_client)
    )
    yield cloud_client


class TestStartFlowRunCloud:
    def test_initialization(self, cloud_api):
        now = pendulum.now()
        run_config = UniversalRun()

        # verify that the task is initialized as expected
        task = StartFlowRun(
            name="My Flow Run Task",
            checkpoint=False,
            project_name="Test Project",
            flow_name="Test Flow",
            new_flow_context={"foo": "bar"},
            parameters={"test": "ing"},
            run_config=run_config,
            run_name="test-run",
            scheduled_start_time=now,
        )
        assert task.name == "My Flow Run Task"
        assert task.checkpoint is False
        assert task.project_name == "Test Project"
        assert task.flow_name == "Test Flow"
        assert task.new_flow_context == {"foo": "bar"}
        assert task.parameters == {"test": "ing"}
        assert task.run_config == run_config
        assert task.run_name == "test-run"
        assert task.scheduled_start_time == now

    def test_init_errors_if_tasks_passed_to_parameters(self, cloud_api):
        with pytest.raises(TypeError, match="An instance of `Task` was passed"):
            StartFlowRun(
                name="testing", parameters={"a": 1, "b": prefect.Parameter("b")}
            )

    @pytest.mark.parametrize("idempotency_key", [None, "my-key"])
    @pytest.mark.parametrize("task_run_id", [None, "test-id"])
    def test_flow_run_task_submit_args(
        self, client, cloud_api, idempotency_key, task_run_id
    ):
        run_config = UniversalRun()

        # verify that create_flow_run was called
        task = StartFlowRun(
            project_name="Test Project",
            flow_name="Test Flow",
            parameters={"test": "ing"},
            run_config=run_config,
            run_name="test-run",
        )
        # verify that run returns the new flow run ID
        with prefect.context(task_run_id=task_run_id):
            assert task.run(idempotency_key=idempotency_key) == "xyz890"
        # verify the GraphQL query was called with the correct arguments
        query_args = list(client.graphql.call_args_list[0][0][0]["query"].keys())[0]
        assert "Test Project" in query_args
        assert "Test Flow" in query_args

        # verify create_flow_run was called with the correct arguments
        assert client.create_flow_run.call_args[1] == dict(
            flow_id="abc123",
            parameters={"test": "ing"},
            run_config=run_config,
            idempotency_key=idempotency_key or task_run_id,
            context=None,
            run_name="test-run",
            scheduled_start_time=None,
        )

    def test_flow_run_task_uses_scheduled_start_time(self, client, cloud_api):
        in_one_hour = pendulum.now().add(hours=1)
        # verify that create_flow_run was called
        task = StartFlowRun(
            project_name="Test Project",
            flow_name="Test Flow",
            scheduled_start_time=in_one_hour,
        )
        # verify that run returns the new flow run ID
        assert task.run() == "xyz890"

        # verify create_flow_run was called with the correct arguments
        client.create_flow_run.assert_called_once_with(
            flow_id="abc123",
            parameters=None,
            idempotency_key=None,
            context=None,
            run_name=None,
            scheduled_start_time=in_one_hour,
            run_config=None,
        )

    def test_flow_run_task_without_flow_name(self, cloud_api):
        # verify that a ValueError is raised without a flow name
        task = StartFlowRun(project_name="Test Project")
        with pytest.raises(ValueError, match="Must provide a flow name."):
            task.run()

    def test_flow_run_task_without_project_name(self, cloud_api):
        # verify that a ValueError is raised without a project name
        task = StartFlowRun(flow_name="Test Flow")
        with pytest.raises(ValueError, match="Must provide a project name."):
            task.run()

    def test_flow_run_task_with_no_matching_flow(self, client, cloud_api):
        # verify a ValueError is raised if the client returns no flows
        task = StartFlowRun(flow_name="Test Flow", project_name="Test Project")
        client.graphql = MagicMock(return_value=MagicMock(data=MagicMock(flow=[])))
        with pytest.raises(ValueError, match="Flow 'Test Flow' not found."):
            task.run()

    def test_flow_run_link_artifact(self, client, cloud_api):
        task = StartFlowRun(
            project_name="Test Project",
            flow_name="Test Flow",
            parameters={"test": "ing"},
            run_name="test-run",
        )
        with prefect.context(running_with_backend=True, task_run_id="trid"):
            task.run()

            client.create_task_run_artifact.assert_called_once_with(
                data={"link": "/flow/run/url"}, kind="link", task_run_id="trid"
            )


class TestStartFlowRunServer:
    def test_initialization(self, server_api):
        now = pendulum.now()

        # verify that the task is initialized as expected
        task = StartFlowRun(
            name="My Flow Run Task",
            project_name="Demo",
            checkpoint=False,
            flow_name="Test Flow",
            new_flow_context={"foo": "bar"},
            parameters={"test": "ing"},
            run_name="test-run",
            scheduled_start_time=now,
        )
        assert task.name == "My Flow Run Task"
        assert task.checkpoint is False
        assert task.flow_name == "Test Flow"
        assert task.new_flow_context == {"foo": "bar"}
        assert task.parameters == {"test": "ing"}
        assert task.run_name == "test-run"
        assert task.scheduled_start_time == now

    def test_flow_run_task(self, client, server_api):
        # verify that create_flow_run was called
        task = StartFlowRun(
            flow_name="Test Flow",
            project_name="Demo",
            parameters={"test": "ing"},
            run_name="test-run",
        )
        # verify that run returns the new flow run ID
        assert task.run() == "xyz890"
        # verify the GraphQL query was called with the correct arguments
        query_args = list(client.graphql.call_args_list[0][0][0]["query"].keys())[0]
        assert "Test Flow" in query_args

        # verify create_flow_run was called with the correct arguments
        client.create_flow_run.assert_called_once_with(
            flow_id="abc123",
            parameters={"test": "ing"},
            idempotency_key=None,
            context=None,
            run_name="test-run",
            scheduled_start_time=None,
            run_config=None,
        )

    def test_flow_run_task_with_wait(self, client, server_api):
        # verify that create_flow_run was called
        task = StartFlowRun(
            flow_name="Test Flow",
            project_name="Demo",
            parameters={"test": "ing"},
            run_name="test-run",
            wait=True,
            poll_interval=timedelta(seconds=3),
        )
        assert task.poll_interval == timedelta(seconds=3)
        # Run flow, and assert that signals a success
        with pytest.raises(signals.SUCCESS) as exc_info:
            task.run()
        flow_state_signal = exc_info.value
        assert isinstance(flow_state_signal.state, state.Success)
        # Check flow ID
        assert str(flow_state_signal).split(" ")[0] == "xyz890"
        # verify the GraphQL query was called with the correct arguments
        query_args = list(client.graphql.call_args_list[0][0][0]["query"].keys())[0]
        assert "Test Flow" in query_args
        # verify create_flow_run was called with the correct arguments
        client.create_flow_run.assert_called_once_with(
            flow_id="abc123",
            parameters={"test": "ing"},
            idempotency_key=None,
            context=None,
            run_name="test-run",
            scheduled_start_time=None,
            run_config=None,
        )

    def test_flow_run_task_poll_interval_too_short(self):
        with pytest.raises(ValueError):
            task = StartFlowRun(
                flow_name="Test Flow",
                project_name="Demo",
                parameters={"test": "ing"},
                run_name="test-run",
                wait=True,
                poll_interval=timedelta(seconds=2),
            )

    def test_flow_run_task_without_flow_name(self, server_api):
        # verify that a ValueError is raised without a flow name
        task = StartFlowRun()
        with pytest.raises(ValueError, match="Must provide a flow name."):
            task.run()

    def test_flow_run_task_with_no_matching_flow(self, client, server_api):
        # verify a ValueError is raised if the client returns no flows
        task = StartFlowRun(flow_name="Test Flow", project_name="Demo")
        client.graphql = MagicMock(return_value=MagicMock(data=MagicMock(flow=[])))
        with pytest.raises(ValueError, match="Flow 'Test Flow' not found."):
            task.run()
