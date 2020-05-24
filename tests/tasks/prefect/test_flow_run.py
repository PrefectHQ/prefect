import pytest
from unittest.mock import MagicMock

from prefect.tasks.prefect.flow_run import FlowRunTask


@pytest.fixture()
def client(monkeypatch):
    cloud_client = MagicMock(
        graphql=MagicMock(
            return_value=MagicMock(
                data=MagicMock(flow=[MagicMock(id="abc123"), MagicMock(id="def456")])
            )
        ),
        create_flow_run=MagicMock(return_value="xyz890"),
    )
    monkeypatch.setattr(
        "prefect.tasks.prefect.flow_run.Client", MagicMock(return_value=cloud_client),
    )
    yield cloud_client


class TestFlowRunTaskCloud:
    def test_initialization(self, cloud_api):
        # verify that the task is initialized as expected
        task = FlowRunTask(
            name="My Flow Run Task",
            checkpoint=False,
            project_name="Test Project",
            flow_name="Test Flow",
            parameters={"test": "ing"},
        )
        assert task.name == "My Flow Run Task"
        assert task.checkpoint is False
        assert task.project_name == "Test Project"
        assert task.flow_name == "Test Flow"
        assert task.parameters == {"test": "ing"}

    def test_flow_run_task(self, client, cloud_api):
        # verify that create_flow_run was called
        task = FlowRunTask(
            project_name="Test Project",
            flow_name="Test Flow",
            parameters={"test": "ing"},
        )
        # verify that run returns the new flow run ID
        assert task.run() == "xyz890"
        # verify the GraphQL query was called with the correct arguments
        query_args = list(client.graphql.call_args_list[0][0][0]["query"].keys())[0]
        assert "Test Project" in query_args
        assert "Test Flow" in query_args

        # verify create_flow_run was called with the correct arguments
        client.create_flow_run.assert_called_once_with(
            flow_id="abc123", parameters={"test": "ing"}
        )

    def test_flow_run_task_without_flow_name(self, cloud_api):
        # verify that a ValueError is raised without a flow name
        task = FlowRunTask(project_name="Test Project")
        with pytest.raises(ValueError, match="Must provide a flow name."):
            task.run()

    def test_flow_run_task_without_project_name(self, cloud_api):
        # verify that a ValueError is raised without a project name
        task = FlowRunTask(flow_name="Test Flow")
        with pytest.raises(ValueError, match="Must provide a project name."):
            task.run()

    def test_flow_run_task_with_no_matching_flow(self, client, cloud_api):
        # verify a ValueError is raised if the client returns no flows
        task = FlowRunTask(flow_name="Test Flow", project_name="Test Project")
        client.graphql = MagicMock(return_value=MagicMock(data=MagicMock(flow=[])))
        with pytest.raises(ValueError, match="Flow 'Test Flow' not found."):
            task.run()


class TestFlowRunTaskCoreServer:
    def test_initialization(self, server_api):
        # verify that the task is initialized as expected
        task = FlowRunTask(
            name="My Flow Run Task",
            checkpoint=False,
            flow_name="Test Flow",
            parameters={"test": "ing"},
        )
        assert task.name == "My Flow Run Task"
        assert task.checkpoint is False
        assert task.flow_name == "Test Flow"
        assert task.parameters == {"test": "ing"}

    def test_flow_run_task(self, client, server_api):
        # verify that create_flow_run was called
        task = FlowRunTask(flow_name="Test Flow", parameters={"test": "ing"},)
        # verify that run returns the new flow run ID
        assert task.run() == "xyz890"
        # verify the GraphQL query was called with the correct arguments
        query_args = list(client.graphql.call_args_list[0][0][0]["query"].keys())[0]
        assert "Test Flow" in query_args

        # verify create_flow_run was called with the correct arguments
        client.create_flow_run.assert_called_once_with(
            flow_id="abc123", parameters={"test": "ing"}
        )

    def test_flow_run_task_without_flow_name(self, server_api):
        # verify that a ValueError is raised without a flow name
        task = FlowRunTask()
        with pytest.raises(ValueError, match="Must provide a flow name."):
            task.run()

    def test_flow_run_task_with_no_matching_flow(self, client, server_api):
        # verify a ValueError is raised if the client returns no flows
        task = FlowRunTask(flow_name="Test Flow")
        client.graphql = MagicMock(return_value=MagicMock(data=MagicMock(flow=[])))
        with pytest.raises(ValueError, match="Flow 'Test Flow' not found."):
            task.run()
