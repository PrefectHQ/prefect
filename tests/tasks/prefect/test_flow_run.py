from datetime import timedelta
import pendulum
import pytest
from unittest.mock import MagicMock

import prefect
from prefect.client.client import FlowRunInfoResult, ProjectInfo
from prefect.engine import signals, state

from prefect.run_configs import UniversalRun
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


def test_deprecated_old_name():
    from prefect.tasks.prefect import FlowRunTask

    with pytest.warns(UserWarning, match="StartFlowRun"):
        task = FlowRunTask(name="My flow run")

    assert isinstance(task, StartFlowRun)
    assert task.name == "My flow run"


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
