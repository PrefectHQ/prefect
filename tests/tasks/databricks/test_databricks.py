import json
from typing import Any

import pytest
import responses
from requests import PreparedRequest

import prefect
from prefect.exceptions import PrefectException
from prefect.tasks.databricks import (
    DatabricksRunNow,
    DatabricksSubmitMultitaskRun,
    DatabricksSubmitRun,
    DatabricksGetJobID,
)
from prefect.tasks.databricks.databricks_hook import DatabricksHook
from prefect.tasks.databricks.models import (
    AccessControlRequest,
    AccessControlRequestForUser,
    AutoScale,
    AwsAttributes,
    AwsAvailability,
    CanManage,
    JobTaskSettings,
    Library,
    NewCluster,
    NotebookTask,
    PermissionLevel,
    SparkJarTask,
    TaskDependency,
)


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

    def _get_hook(self, *_):
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

    def _get_hook(self):
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
    return DatabricksGetJobIDTestOverride(
        mocked_response=databricks_list_api_response_success,
        databricks_conn_secret={
            "host": "https://cloud.databricks.com",
            "token": "databricks-token",
        },
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
        DatabricksGetJobID({})

    def test_initialization_passes_to_task_constructor(self):
        task = DatabricksGetJobID(
            databricks_conn_secret={"host": "host_name"},
            search_limit=1,
        )
        assert task.databricks_conn_secret == {"host": "host_name"}
        assert task.search_limit == 1

    def test_raises_cant_find_matching_job_name(self, get_jobid_task_template):
        with pytest.raises(ValueError, match="name"):
            get_jobid_task_template.run(job_name="none")

    def test_raises_on_duplicate_job_name(self, get_jobid_task_template):
        with pytest.raises(ValueError, match="duplicate"):
            get_jobid_task_template.run(job_name="duplicate")

    def test_find_matching_job_name(self, get_jobid_task_template):
        task_result = get_jobid_task_template.run(job_name="job_name")
        assert task_result == 76


@pytest.fixture
def flow_run_id():
    flow_run_id = "a1b2c3d4"
    prefect.context.flow_run_id = flow_run_id
    yield flow_run_id
    del prefect.context.flow_run_id


@pytest.fixture
def flow_run_name():
    flow_run_name = "angry_cat"
    prefect.context.flow_run_name = flow_run_name
    yield flow_run_name
    del prefect.context.flow_run_name


@pytest.fixture
def requests_mock():
    with responses.RequestsMock() as requests_mock:
        yield requests_mock


def body_entry_matcher(key: str, value: Any):
    def matcher(req: PreparedRequest):
        if req.body:
            body = req.body
            if isinstance(body, bytes):
                body = body.decode()
            body_json = json.loads(body)
            if body_json.get(key) == value:
                return True, f"Key ${key} in request body equals ${value}"
            elif body_json.get(key) is None:
                return False, f"Key ${key} not in request body"
            else:
                return False, f"Key ${key} in request body does not equal ${value}"
        else:
            return False, "No body in request"

    return matcher


@pytest.fixture
def match_run_sumbission_on_idempotency_token(requests_mock, flow_run_id):
    requests_mock.add(
        method=responses.POST,
        url="https://cloud.databricks.com/api/2.1/jobs/runs/submit",
        json={"run_id": "12345"},
        match=[body_entry_matcher("idempotency_token", flow_run_id)],
    )


@pytest.fixture
def match_run_sumbission_on_run_name(requests_mock, flow_run_name):
    requests_mock.add(
        method=responses.POST,
        url="https://cloud.databricks.com/api/2.1/jobs/runs/submit",
        json={"run_id": "12345"},
        match=[
            body_entry_matcher(
                "run_name", f"Job run created by Prefect flow run {flow_run_name}"
            )
        ],
    )


@pytest.fixture
def successful_run_submission(requests_mock):
    requests_mock.add(
        method=responses.POST,
        url="https://cloud.databricks.com/api/2.1/jobs/runs/submit",
        json={"run_id": "12345"},
    )


@pytest.fixture
def successful_run_completion(requests_mock):
    requests_mock.add(
        method=responses.GET,
        url="https://cloud.databricks.com/api/2.1/jobs/runs/get",
        match=[responses.matchers.json_params_matcher({"run_id": "12345"})],
        json={
            "run_page_url": "https://my-workspace.cloud.databricks.com/#job/11223344/run/123",
            "state": {
                "life_cycle_state": "TERMINATED",
                "result_state": "SUCCESS",
                "user_cancelled_or_timedout": False,
                "state_message": "",
            },
        },
    )


@pytest.fixture
def failed_run(requests_mock):
    requests_mock.add(
        method=responses.GET,
        url="https://cloud.databricks.com/api/2.1/jobs/runs/get",
        match=[responses.matchers.json_params_matcher({"run_id": "12345"})],
        json={
            "run_page_url": "https://my-workspace.cloud.databricks.com/#job/11223344/run/123",
            "state": {
                "life_cycle_state": "TERMINATED",
                "result_state": "FAILED",
                "user_cancelled_or_timedout": False,
                "state_message": "",
            },
        },
    )


class TestDatabricksSubmitMultitaskRun:
    databricks_conn_secret = {
        "host": "https://cloud.databricks.com",
        "token": "token",
    }
    test_databricks_task = JobTaskSettings(
        task_key="Match",
        description="Matches orders with user sessions",
        depends_on=[
            TaskDependency(task_key="Orders_Ingest"),
            TaskDependency(task_key="Sessionize"),
        ],
        new_cluster=NewCluster(
            spark_version="7.3.x-scala2.12",
            node_type_id="i3.xlarge",
            spark_conf={"spark.speculation": True},
            aws_attributes=AwsAttributes(
                availability=AwsAvailability.SPOT, zone_id="us-west-2a"
            ),
            autoscale=AutoScale(min_workers=2, max_workers=16),
        ),
        notebook_task=NotebookTask(
            notebook_path="/Users/user.name@databricks.com/Match",
            base_parameters={"name": "John Doe", "age": "35"},
        ),
        timeout_seconds=86400,
    )

    def test_requires_at_least_one_task(self, flow_run_name, flow_run_id):
        task = DatabricksSubmitMultitaskRun(
            databricks_conn_secret=self.databricks_conn_secret,
            tasks=[],
        )

        with pytest.raises(ValueError, match="at least one Databricks task"):
            task.run()

    def test_errors_on_incorrect_credential_format(self):
        task = DatabricksSubmitMultitaskRun(
            databricks_conn_secret="token",
            tasks=[self.test_databricks_task],
        )
        with pytest.raises(ValueError, match="must be supplied as a dictionary"):
            task.run()

    def test_default_idempotency_token(
        self,
        match_run_sumbission_on_idempotency_token,
        successful_run_completion,
    ):
        task = DatabricksSubmitMultitaskRun(
            databricks_conn_secret=self.databricks_conn_secret,
            tasks=[self.test_databricks_task],
            run_name="Test Run",
            access_control_list=[
                AccessControlRequestForUser(
                    user_name="jsmith@example.com",
                    permission_level=CanManage.CAN_MANAGE,
                )
            ],
        )

        # Will fail if expected idempotency token is not used
        assert task.run() == "12345"

    def test_default_run_name(
        self,
        match_run_sumbission_on_run_name,
        successful_run_completion,
    ):
        task = DatabricksSubmitMultitaskRun(
            databricks_conn_secret=self.databricks_conn_secret,
            tasks=[self.test_databricks_task],
            idempotency_token="1234",
        )

        # Will fail if expected run name is not used
        assert task.run() == "12345"

    def test_failed_run(
        self, failed_run, successful_run_submission, flow_run_id, flow_run_name
    ):
        with pytest.raises(
            PrefectException,
            match="DatabricksSubmitMultitaskRun failed with terminal state",
        ):
            DatabricksSubmitMultitaskRun(
                databricks_conn_secret=self.databricks_conn_secret,
                tasks=[self.test_databricks_task],
            ).run()

    def test_convert_dict_to_input_dataclasses(self):
        expected_result = {
            "tasks": [
                JobTaskSettings(
                    task_key="Sessionize",
                    description="Extracts session data from events",
                    existing_cluster_id="0923-164208-meows279",
                    spark_jar_task=SparkJarTask(
                        main_class_name="com.databricks.Sessionize",
                        parameters=["--data", "dbfs:/path/to/data.json"],
                    ),
                    libraries=[Library(jar="dbfs:/mnt/databricks/Sessionize.jar")],
                    timeout_seconds=86400,
                ),
                JobTaskSettings(
                    task_key="Orders_Ingest",
                    description="Ingests order data",
                    existing_cluster_id="0923-164208-meows279",
                    spark_jar_task=SparkJarTask(
                        main_class_name="com.databricks.OrdersIngest",
                        parameters=["--data", "dbfs:/path/to/order-data.json"],
                    ),
                    libraries=[Library(jar="dbfs:/mnt/databricks/OrderIngest.jar")],
                    timeout_seconds=86400,
                ),
                JobTaskSettings(
                    task_key="Match",
                    description="Matches orders with user sessions",
                    depends_on=[
                        TaskDependency(task_key="Orders_Ingest"),
                        TaskDependency(task_key="Sessionize"),
                    ],
                    new_cluster=NewCluster(
                        spark_version="7.3.x-scala2.12",
                        node_type_id="i3.xlarge",
                        spark_conf={"spark.speculation": True},
                        aws_attributes=AwsAttributes(
                            availability=AwsAvailability.SPOT, zone_id="us-west-2a"
                        ),
                        autoscale=AutoScale(min_workers=2, max_workers=16),
                    ),
                    notebook_task=NotebookTask(
                        notebook_path="/Users/user.name@databricks.com/Match",
                        base_parameters={"name": "John Doe", "age": "35"},
                    ),
                    timeout_seconds=86400,
                ),
            ],
            "run_name": "A multitask job run",
            "timeout_seconds": 86400,
            "idempotency_token": "8f018174-4792-40d5-bcbc-3e6a527352c8",
            "access_control_list": [
                AccessControlRequest(
                    __root__=AccessControlRequestForUser(
                        user_name="jsmith@example.com",
                        permission_level=PermissionLevel(__root__=CanManage.CAN_MANAGE),
                    )
                )
            ],
        }

        assert (
            DatabricksSubmitMultitaskRun.convert_dict_to_kwargs(
                {
                    "tasks": [
                        {
                            "task_key": "Sessionize",
                            "description": "Extracts session data from events",
                            "depends_on": [],
                            "existing_cluster_id": "0923-164208-meows279",
                            "spark_jar_task": {
                                "main_class_name": "com.databricks.Sessionize",
                                "parameters": ["--data", "dbfs:/path/to/data.json"],
                            },
                            "libraries": [
                                {"jar": "dbfs:/mnt/databricks/Sessionize.jar"}
                            ],
                            "timeout_seconds": 86400,
                        },
                        {
                            "task_key": "Orders_Ingest",
                            "description": "Ingests order data",
                            "depends_on": [],
                            "existing_cluster_id": "0923-164208-meows279",
                            "spark_jar_task": {
                                "main_class_name": "com.databricks.OrdersIngest",
                                "parameters": [
                                    "--data",
                                    "dbfs:/path/to/order-data.json",
                                ],
                            },
                            "libraries": [
                                {"jar": "dbfs:/mnt/databricks/OrderIngest.jar"}
                            ],
                            "timeout_seconds": 86400,
                        },
                        {
                            "task_key": "Match",
                            "description": "Matches orders with user sessions",
                            "depends_on": [
                                {"task_key": "Orders_Ingest"},
                                {"task_key": "Sessionize"},
                            ],
                            "new_cluster": {
                                "spark_version": "7.3.x-scala2.12",
                                "node_type_id": "i3.xlarge",
                                "spark_conf": {"spark.speculation": True},
                                "aws_attributes": {
                                    "availability": "SPOT",
                                    "zone_id": "us-west-2a",
                                },
                                "autoscale": {"min_workers": 2, "max_workers": 16},
                            },
                            "notebook_task": {
                                "notebook_path": "/Users/user.name@databricks.com/Match",
                                "base_parameters": {"name": "John Doe", "age": "35"},
                            },
                            "timeout_seconds": 86400,
                        },
                    ],
                    "run_name": "A multitask job run",
                    "timeout_seconds": 86400,
                    "idempotency_token": "8f018174-4792-40d5-bcbc-3e6a527352c8",
                    "access_control_list": [
                        {
                            "user_name": "jsmith@example.com",
                            "permission_level": "CAN_MANAGE",
                        }
                    ],
                }
            )
            == expected_result
        )

    def test_convert_dict_to_input_allow_extra(self):
        expected_result = {
            "tasks": [
                JobTaskSettings(
                    task_key="Match",
                    description="Matches orders with user sessions",
                    new_cluster=NewCluster(
                        spark_version="7.3.x-scala2.12",
                        node_type_id="i3.xlarge",
                        spark_conf={"spark.speculation": True},
                        aws_attributes=AwsAttributes(
                            availability=AwsAvailability.SPOT, zone_id="us-west-2a"
                        ),
                        autoscale=AutoScale(min_workers=2, max_workers=16),
                        amazing_new_feature=True,
                    ),
                    unsupported_argument="ignore_me",
                    another_unsupported_argument="ignore_me",
                ),
            ],
            "run_name": "A multitask job run",
            "timeout_seconds": 86400,
            "idempotency_token": "8f018174-4792-40d5-bcbc-3e6a527352c8",
        }

        assert (
            DatabricksSubmitMultitaskRun.convert_dict_to_kwargs(
                {
                    "tasks": [
                        {
                            "task_key": "Match",
                            "description": "Matches orders with user sessions",
                            "new_cluster": {
                                "spark_version": "7.3.x-scala2.12",
                                "node_type_id": "i3.xlarge",
                                "spark_conf": {"spark.speculation": True},
                                "aws_attributes": {
                                    "availability": "SPOT",
                                    "zone_id": "us-west-2a",
                                },
                                "autoscale": {"min_workers": 2, "max_workers": 16},
                                "amazing_new_feature": True,
                            },
                        },
                    ],
                    "run_name": "A multitask job run",
                    "timeout_seconds": 86400,
                    "idempotency_token": "8f018174-4792-40d5-bcbc-3e6a527352c8",
                }
            )
            == expected_result
        )
