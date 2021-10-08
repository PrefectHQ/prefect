import pytest

from prefect.tasks.databricks import DatabricksSubmitRun
from prefect.tasks.databricks import DatabricksRunNow
from prefect.tasks.databricks.databricks_hook import DatabricksHook


class DatabricksHookTestOverride(DatabricksHook):
    """
    Overrides `DatabricksHook` to avoid making actual API calls
    and return mocked responses instead

    Args:
        - mocked_response (dict): JSON response of API call
    """

    def __init__(self, mocked_response={}, **kwargs) -> None:
        self.mocked_response = mocked_response
        super().__init__(self, **kwargs)

    def _do_api_call(self, endpoint_info, json):
        return self.mocked_response


class DatabricksRunNowTestOverride(DatabricksRunNow):
    """
    Overrides `DatabricksRunNow` to allow mocked API responses
    to be returned using `DatabricksHookTestOverride`

    Args:
        - mocked_response (dict): JSON response of API call
    """

    def __init__(self, mocked_response, **kwargs) -> None:
        self.mocked_response = mocked_response
        super().__init__(**kwargs)

    def get_hook(self):
        return DatabricksHookTestOverride(self.mocked_response)


@pytest.fixture
def job_config():

    config = {
        "run_name": "Prefect Test",
        "new_cluster": {
            "spark_version": "6.6.x-scala2.11",
            "num_workers": 0,
            "node_type_id": "Standard_D3_v2",
        },
        "spark_python_task": {
            "python_file": f"dbfs:/FileStore/tables/runner.py",
            "parameters": [1],
        },
    }

    return config


@pytest.fixture
def notebook_job_config():

    config = {
        "job_id": 1,
        "notebook_params": {
            "dry-run": "true",
            "oldest-time-to-consider": "1457570074236",
        },
    }

    return config


@pytest.fixture
def notebook_job_config_full():

    config = {
        "job_id": 1,
        "notebook_params": {
            "dry-run": "true",
            "oldest-time-to-consider": "1457570074236",
        },
        "python_params": ["python-param1", "python-param2"],
        "spark_submit_params": ["spark-param1", "spark-param2"],
        "jar_params": ["jar-param1", "jar-param2"],
    }

    return config


@pytest.fixture
def databricks_api_response_success():

    response = {
        "run_id": "test-run-id",
        "run_page_url": "https://run_page_url",
        "state": {
            "life_cycle_state": "TERMINATED",
            "result_state": "SUCCESS",
            "state_message": "Completed",
        },
    }

    return response


@pytest.fixture
def task_template(databricks_api_response_success, notebook_job_config_full):

    return DatabricksRunNowTestOverride(
        mocked_response=databricks_api_response_success,
        databricks_conn_secret={
            "host": "https://cloud.databricks.com",
            "token": "databricks-token",
        },
        json=notebook_job_config_full,
    )


def test_raises_if_invalid_host_submitrun(job_config):

    # from prefect.tasks.secrets import PrefectSecret
    # conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
    # task = DatabricksSubmitRun(databricks_conn_secret=conn, json=job_config)

    with pytest.raises(AttributeError, match="object has no attribute"):
        task = DatabricksSubmitRun(
            databricks_conn_secret={"host": "", "token": ""}, json=job_config
        )
        task.run()


def test_raises_if_invalid_host_runnow(notebook_job_config):

    # from prefect.tasks.secrets import PrefectSecret
    # conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
    # task = DatabricksSubmitRun(databricks_conn_secret=conn, json=job_config)

    with pytest.raises(AttributeError, match="object has no attribute"):
        task = DatabricksRunNow(
            databricks_conn_secret={"host": "", "token": ""}, json=notebook_job_config
        )
        task.run()


def test_ensure_run_id_not_defined_within_class_arguments(job_config):
    assert not hasattr(job_config, "run_id")


class TestDatabricksRunNowAttributeOverrides:
    """Test various expected attribute override behavior with `DatabricksRunNow.run`"""

    def test_without_overrides(self, task_template):
        task_template.run()

        run_now_json = task_template.json
        assert run_now_json.get("job_id") == "1"
        assert run_now_json.get("notebook_params", {}).get("dry-run") == "true"
        assert (
            run_now_json.get("notebook_params", {}).get("oldest-time-to-consider")
            == "1457570074236"
        )
        assert run_now_json.get("python_params") == ["python-param1", "python-param2"]
        assert run_now_json.get("spark_submit_params") == [
            "spark-param1",
            "spark-param2",
        ]
        assert run_now_json.get("jar_params") == ["jar-param1", "jar-param2"]

    def test_with_job_id_override(self, task_template):
        task_template.run(job_id="42")
        assert task_template.json.get("job_id") == "42"

    def test_with_notebook_params_override(self, task_template):
        task_template.run(notebook_params={"dry-run": "false"})

        run_now_json = task_template.json
        assert run_now_json.get("notebook_params", {}).get("dry-run") == "false"
        assert (
            run_now_json.get("notebook_params", {}).get("oldest-time-to-consider")
            == "1457570074236"
        )

    def test_with_python_params_override(self, task_template):
        task_template.run(python_params=["python-param3"])
        assert task_template.json.get("python_params") == ["python-param3"]

    def test_with_spark_submit_params_override(self, task_template):
        task_template.run(spark_submit_params=["spark-param3"])
        assert task_template.json.get("spark_submit_params") == ["spark-param3"]

    def test_with_jar_params_override(self, task_template):
        task_template.run(jar_params=["jar-param3"])
        assert task_template.json.get("jar_params") == ["jar-param3"]

    def test_with_json_override(self, task_template):
        task_template.run(
            json={"job_id": "123"},
            notebook_params={"notebookparam1": "notebookvalue1"},
        )

        run_now_json = task_template.json
        assert len(run_now_json) == 2
        assert run_now_json.get("job_id") == "123"
        assert (
            run_now_json.get("notebook_params", {}).get("notebookparam1")
            == "notebookvalue1"
        )

    def test_ensure_run_id_not_defined_within_class_arguments(self, task_template):
        assert not hasattr(task_template, "run_id")
