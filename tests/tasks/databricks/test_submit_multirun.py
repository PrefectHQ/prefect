import pydantic
import pytest

from prefect.exceptions import PrefectException
from prefect.tasks.databricks import DatabricksSubmitMultitaskRun
from prefect.tasks.databricks.models import (
    AccessControlRequestForGroup,
    AccessControlRequestForUser,
    AutoScale,
    AwsAttributes,
    AwsAvailability,
    CanManage,
    GitSource,
    JobTaskSettings,
    Library,
    NewCluster,
    NotebookTask,
    SparkJarTask,
    TaskDependency,
)
from tests.tasks.databricks.test_submit_run import (  # noqa
    failed_run,
    flow_run_id,
    flow_run_name,
    match_run_sumbission_on_idempotency_token,
    match_run_sumbission_on_run_name,
    requests_mock,
    successful_run_completion,
    successful_run_submission,
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

    def assert_job_is_converted_to_kwargs_correctly(self, job_json, typed_jobdef):
        converted = DatabricksSubmitMultitaskRun.convert_dict_to_kwargs(job_json)
        assert converted == typed_jobdef

    def test_convert_dict_to_input_dataclasses(self):
        self.assert_job_is_converted_to_kwargs_correctly(
            multi_task_job_json(), multi_task_job_def()
        )

    def test_convert_dict_to_input_dataclasses_with_gitsource(self):
        git_source_jobdef = multi_task_job_def()
        git_source_jobdef["git_source"] = prefect_git_source(git_branch="main")
        git_source_json = multi_task_job_json()
        git_source_json["git_source"] = {
            "git_url": "https://github.com/PrefectHQ/prefect/",
            "git_provider": "GitHub",
            "git_branch": "main",
        }
        self.assert_job_is_converted_to_kwargs_correctly(
            git_source_json, git_source_jobdef
        )

    def test_convert_dict_to_input_allow_extra(self):
        extra_params_jobdef = multi_task_job_def()
        last_task = extra_params_jobdef["tasks"][-1]
        last_task.new_cluster = last_task.new_cluster.copy(
            update={"amazing_new_feature": True}
        )
        last_task = last_task.copy(
            update={
                "unsupported_argument": "ignore_me",
                "another_unsupported_argument": "ignore_me",
            }
        )
        extra_params_source_json = multi_task_job_json()
        extra_params_source_json["tasks"][-1]["new_cluster"][
            "amazing_new_feature"
        ] = True
        self.assert_job_is_converted_to_kwargs_correctly(
            extra_params_source_json, extra_params_jobdef
        )


def prefect_git_source(**kwargs):
    return GitSource(
        git_url="https://github.com/PrefectHQ/prefect/", git_provider="GitHub", **kwargs
    )


def assert_git_source_conflicting_args(**kwargs):
    with pytest.raises(pydantic.ValidationError):
        prefect_git_source(**kwargs)


def test_gitsource_branch_or_tag_are_exclusive():
    assert_git_source_conflicting_args(git_branch="main", git_tag="v1.0")


def test_gitsource_branch_or_commit_are_exclusive():
    assert_git_source_conflicting_args(git_branch="main", git_commit="78ffc7055")


def test_gitsource_commit_or_tag_are_exclusive():
    assert_git_source_conflicting_args(git_tag="v1.0", git_commit="78ffc7055")


def multi_task_job_def():
    return {
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
            AccessControlRequestForUser(
                user_name="jsmith@example.com",
                permission_level=CanManage.CAN_MANAGE,
            ),
            AccessControlRequestForGroup(
                group_name="Admins", permission_level=CanManage.CAN_MANAGE
            ),
        ],
    }


def multi_task_job_json():
    return {
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
                "libraries": [{"jar": "dbfs:/mnt/databricks/Sessionize.jar"}],
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
                "libraries": [{"jar": "dbfs:/mnt/databricks/OrderIngest.jar"}],
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
            },
            {
                "group_name": "Admins",
                "permission_level": "CAN_MANAGE",
            },
        ],
    }
