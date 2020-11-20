import pendulum
import pytest
from unittest.mock import MagicMock

import prefect
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

        # verify that the task is initialized as expected
        task = StartFlowRun(
            name="My Flow Run Task",
            checkpoint=False,
            project_name="Test Project",
            flow_name="Test Flow",
            new_flow_context={"foo": "bar"},
            parameters={"test": "ing"},
            run_name="test-run",
            scheduled_start_time=now,
        )
        assert task.name == "My Flow Run Task"
        assert task.checkpoint is False
        assert task.project_name == "Test Project"
        assert task.flow_name == "Test Flow"
        assert task.new_flow_context == {"foo": "bar"}
        assert task.parameters == {"test": "ing"}
        assert task.run_name == "test-run"
        assert task.scheduled_start_time == now

    def test_flow_run_task(self, client, cloud_api):
        # verify that create_flow_run was called
        task = StartFlowRun(
            project_name="Test Project",
            flow_name="Test Flow",
            parameters={"test": "ing"},
            run_name="test-run",
        )
        # verify that run returns the new flow run ID
        assert task.run() == "xyz890"
        # verify the GraphQL query was called with the correct arguments
        query_args = list(client.graphql.call_args_list[0][0][0]["query"].keys())[0]
        assert "Test Project" in query_args
        assert "Test Flow" in query_args

        # verify create_flow_run was called with the correct arguments
        client.create_flow_run.assert_called_once_with(
            flow_id="abc123",
            parameters={"test": "ing"},
            idempotency_key=None,
            context=None,
            run_name="test-run",
            scheduled_start_time=None,
        )

    def test_flow_run_task_with_flow_run_id(self, client, cloud_api):
        # verify that create_flow_run was called
        task = StartFlowRun(
            project_name="Test Project",
            flow_name="Test Flow",
            parameters={"test": "ing"},
        )

        # verify that run returns the new flow run ID
        with prefect.context(flow_run_id="test-id"):
            assert task.run() == "xyz890"

        # verify create_flow_run was called with the correct arguments
        client.create_flow_run.assert_called_once_with(
            flow_id="abc123",
            parameters={"test": "ing"},
            idempotency_key="test-id",
            context=None,
            run_name=None,
            scheduled_start_time=None,
        )

    def test_idempotency_key_uses_map_index_if_present(self, client, cloud_api):
        # verify that create_flow_run was called
        task = StartFlowRun(project_name="Test Project", flow_name="Test Flow")

        # verify that run returns the new flow run ID
        with prefect.context(flow_run_id="test-id", map_index=4):
            assert task.run() == "xyz890"

        # verify create_flow_run was called with the correct arguments
        client.create_flow_run.assert_called_once_with(
            flow_id="abc123",
            idempotency_key="test-id-4",
            parameters=None,
            context=None,
            run_name=None,
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

    def test_flow_run_task_with_flow_run_id(self, client, server_api):
        # verify that create_flow_run was called
        task = StartFlowRun(
            project_name="Test Project",
            flow_name="Test Flow",
            parameters={"test": "ing"},
        )

        # verify that run returns the new flow run ID
        with prefect.context(flow_run_id="test-id"):
            assert task.run() == "xyz890"

        # verify create_flow_run was called with the correct arguments
        client.create_flow_run.assert_called_once_with(
            flow_id="abc123",
            parameters={"test": "ing"},
            idempotency_key="test-id",
            context=None,
            run_name=None,
            scheduled_start_time=None,
        )
