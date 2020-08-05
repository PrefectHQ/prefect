import pytest
from prefect.contrib.tasks.databricks import DatabricksRunSubmit


class TestDatabricksRunSubmit:
    def test_initialization(self):
        task = DatabricksRunSubmit()
        assert task.databricks_host is None
        assert task.databricks_retry_limit == 3
        assert task.databricks_retry_delay == 1

    def test_kwargs_passed(self):
        task = DatabricksRunSubmit(
            name="databricks-test-task",
            databricks_host="test.databricks.com",
            databricks_token="THIS_IS_A_TOKEN",
            notebook_task={"notebook_path": "/a/path"},
        )

        assert task.name == "databricks-test-task"
        assert task.json["run_name"] == "databricks-test-task"
        assert task.databricks_host == "test.databricks.com"
        assert task.json["notebook_task"]["notebook_path"] == "/a/path"

    def test_raises_if_invalid_host(self):
        task = DatabricksRunSubmit(
            name="databricks-test-task",
            databricks_host="test.example.com",
            notebook_task={"notebook_path": "/a/path"},
        )

        with pytest.raises(Exception, match="API requests to Databricks failed"):
            task.run()
