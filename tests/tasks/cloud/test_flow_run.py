import pytest
from unittest.mock import MagicMock

from prefect.tasks.cloud.flow_run import FlowRunTask


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
        "prefect.tasks.cloud.flow_run.Client", MagicMock(return_value=cloud_client),
    )
    yield cloud_client


class TestFlowRunTask:
    def test_initialization(self):
        # verify that the task is initialized as expected
        task = FlowRunTask(
            project_name="Test Project",
            flow_name="Test Flow",
            parameters={"test": "ing"},
        )
        assert task.project_name == "Test Project"
        assert task.flow_name == "Test Flow"
        assert task.parameters == {"test": "ing"}

    def test_flow_run_task(self, client):
        # verify that create_flow_run was called
        task = FlowRunTask(
            project_name="Test Project",
            flow_name="Test Flow",
            parameters={"test": "ing"},
        )
        # verify that run returns the new flow run ID
        assert task.run() == "xyz890"
        # verify the GraphQL query was called with the correct arguments
        client.graphql.assert_called_once_with(
            {
                "query": {
                    'flow(where: { name: { _eq: "Test Flow" }, project: { name: { _eq: "Test Project" } } }, order_by: { version: desc })': {
                        "id"
                    }
                }
            }
        )
        # verify create_flow_run was called with the correct arguments
        client.create_flow_run.assert_called_once_with(
            flow_id="abc123", parameters={"test": "ing"}
        )

    def test_flow_run_task_without_flow_name(self):
        # verify that a ValueError is raised without a flow name
        task = FlowRunTask(project_name="Test Project")
        with pytest.raises(ValueError, match="Must provide a flow name."):
            task.run()

    def test_flow_run_task_without_project_name(self):
        # verify that a ValueError is raised without a project name
        task = FlowRunTask(flow_name="Test Flow")
        with pytest.raises(ValueError, match="Must provide a project name."):
            task.run()

    def test_flow_run_task_with_no_matching_flow(self, client):
        # verify a ValueError is raised if the client returns no flows
        task = FlowRunTask(flow_name="Test Flow", project_name="Test Project")
        client.graphql = MagicMock(return_value=MagicMock(data=MagicMock(flow=[])))
        with pytest.raises(ValueError, match="No flow"):
            task.run()
