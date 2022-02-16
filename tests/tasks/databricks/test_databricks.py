import pytest

from prefect.tasks.databricks import DatabricksSubmitRun, DatabricksGetJobID
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


class DatabricksGetJobIDTestOverride(DatabricksGetJobID):
    """
    Overrides `DatabricksGetJobID` to allow mocked API responses
    to be returned using `DatabricksHookTestOverride`.

    Args:
        - mocked_response (dict): JSON response of API call.
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
def databricks_run_api_response_success():

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
def databricks_list_api_response_success():
    response = {
        "jobs": [
            {
                "job_id": 76,
                "settings": {
                    "name": "job_name",
                    "email_notifications": {},
                    "max_concurrent_runs": 1,
                    "format": "MULTI_TASK",
                },
                "created_time": 1643102107360,
                "creator_user_name": "user",
            },
            {
                "job_id": 99,
                "settings": {
                    "name": "duplicate",
                    "email_notifications": {},
                    "max_concurrent_runs": 1,
                    "format": "MULTI_TASK",
                },
                "created_time": 1643102107360,
                "creator_user_name": "user",
            },
            {
                "job_id": 100,
                "settings": {
                    "name": "duplicate",
                    "email_notifications": {},
                    "max_concurrent_runs": 1,
                    "format": "MULTI_TASK",
                },
                "created_time": 1643102107360,
                "creator_user_name": "user",
            },
        ],
        "has_more": False,
    }
    return response


@pytest.fixture
def run_now_task_template(
    databricks_run_api_response_success, notebook_job_config_full
):

    return DatabricksRunNowTestOverride(
        mocked_response=databricks_run_api_response_success,
        databricks_conn_secret={
            "host": "https://cloud.databricks.com",
            "token": "databricks-token",
        },
        json=notebook_job_config_full,
    )


@pytest.fixture
def get_jobid_task_template(databricks_list_api_response_success):
    def _task_template(job_name):
        return DatabricksGetJobIDTestOverride(
            mocked_response=databricks_list_api_response_success,
            databricks_conn_secret={
                "host": "https://cloud.databricks.com",
                "token": "databricks-token",
            },
            job_name=job_name,
        )

    return _task_template


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

    def test_without_overrides(self, run_now_task_template):
        run_now_task_template.run()

        run_now_json = run_now_task_template.json
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

    def test_with_job_id_override(self, run_now_task_template):
        run_now_task_template.run(job_id="42")
        assert run_now_task_template.json.get("job_id") == "42"

    def test_with_notebook_params_override(self, run_now_task_template):
        run_now_task_template.run(notebook_params={"dry-run": "false"})

        run_now_json = run_now_task_template.json
        assert run_now_json.get("notebook_params", {}).get("dry-run") == "false"
        assert (
            run_now_json.get("notebook_params", {}).get("oldest-time-to-consider")
            == "1457570074236"
        )

    def test_with_python_params_override(self, run_now_task_template):
        run_now_task_template.run(python_params=["python-param3"])
        assert run_now_task_template.json.get("python_params") == ["python-param3"]

    def test_with_spark_submit_params_override(self, run_now_task_template):
        run_now_task_template.run(spark_submit_params=["spark-param3"])
        assert run_now_task_template.json.get("spark_submit_params") == ["spark-param3"]

    def test_with_jar_params_override(self, run_now_task_template):
        run_now_task_template.run(jar_params=["jar-param3"])
        assert run_now_task_template.json.get("jar_params") == ["jar-param3"]

    def test_with_json_override(self, run_now_task_template):
        run_now_task_template.run(
            json={"job_id": "123"},
            notebook_params={"notebookparam1": "notebookvalue1"},
        )

        run_now_json = run_now_task_template.json
        assert len(run_now_json) == 2
        assert run_now_json.get("job_id") == "123"
        assert (
            run_now_json.get("notebook_params", {}).get("notebookparam1")
            == "notebookvalue1"
        )

    def test_ensure_run_id_not_defined_within_class_arguments(
        self, run_now_task_template
    ):
        assert not hasattr(run_now_task_template, "run_id")


class TestDatabricksGetJobID:
    def test_initialization(self):
        DatabricksGetJobID({}, "test")

    def test_initialization_passes_to_task_constructor(self):
        task = DatabricksGetJobID(
            job_name="test",
            databricks_conn_secret={"host": "host_name"},
            search_limit=1,
        )
        assert task.job_name == "test"
        assert task.databricks_conn_secret == {"host": "host_name"}
        assert task.search_limit == 1

    def test_raises_cant_find_matching_job_name(self, get_jobid_task_template):
        with pytest.raises(ValueError, match="name"):
            get_jobid_task_template(job_name="none").run()

    def test_raises_on_duplicate_job_name(self, get_jobid_task_template):
        with pytest.raises(ValueError, match="duplicate"):
            get_jobid_task_template(job_name="duplicate").run()

    def test_find_matching_job_name(self, get_jobid_task_template):
        task_result = get_jobid_task_template(job_name="job_name").run()
        assert task_result == 76
