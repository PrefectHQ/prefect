from copy import deepcopy
from unittest.mock import Mock

import anyio
from prefect_gcp.workers.cloud_run import CloudRunWorker
from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    import pydantic.v1 as pydantic
else:
    import pydantic

import pytest
from googleapiclient.errors import HttpError
from prefect_gcp.cloud_run import CloudRunJob, CloudRunJobResult, Execution, Job
from prefect_gcp.credentials import GcpCredentials

from prefect.exceptions import InfrastructureNotFound
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_LOGGING_TO_API_ENABLED,
    PREFECT_PROFILES_PATH,
    temporary_settings,
)

executions_return_value = {
    "metadata": {"name": "test-name", "namespace": "test-namespace"},
    "spec": {"MySpec": "spec"},
    "status": {"logUri": "test-log-uri"},
}

jobs_return_value = {
    "metadata": {"name": "Test", "namespace": "test-namespace"},
    "spec": {"MySpec": "spec"},
    "status": {
        "conditions": [{"type": "Ready", "dog": "cat"}],
        "latestCreatedExecution": {"puppy": "kitty"},
    },
}


@pytest.fixture
def mock_client(monkeypatch, mock_credentials):
    m = Mock(name="MockClient")

    def mock_enter(m, *args, **kwargs):
        return m

    def mock_exit(m, *args, **kwargs):
        pass

    m.__enter__ = mock_enter
    m.__exit__ = mock_exit

    def get_mock_client(*args, **kwargs):
        return m

    monkeypatch.setattr(
        "prefect_gcp.cloud_run.CloudRunJob._get_client",
        get_mock_client,
    )

    return m


class MockExecution(Mock):
    call_count = 0

    def __init__(self, succeeded=False, *args, **kwargs):
        super().__init__()
        self.log_uri = "test_uri"
        self._succeeded = succeeded

    def is_running(self):
        MockExecution.call_count += 1

        if self.call_count > 2:
            return False
        return True

    def condition_after_completion(self):
        return {"message": "test"}

    def succeeded(self):
        return self._succeeded

    @classmethod
    def get(cls, *args, **kwargs):
        return cls()


def list_mock_calls(mock_client, assigned_calls=0):
    calls = []
    for call in mock_client.mock_calls:
        # mock `call.jobs().get()` results in two calls: `call.jobs()` and
        # `call.jobs().get()`, so we want to remove the first, smaller
        # call.
        if len(str(call).split(".")) > 2:
            calls.append(str(call))
    # assigning a return value to a call results in initial
    # mock calls which are not actually made
    actual_calls = calls[assigned_calls:]

    return actual_calls


class TestJob:
    @pytest.mark.parametrize(
        "ready_condition,expected_value",
        [({"status": "True"}, True), ({"status": "False"}, False), ({}, False)],
    )
    def test_is_ready(self, ready_condition, expected_value):
        job = Job(
            metadata={},
            spec={},
            status={},
            name="test",
            ready_condition=ready_condition,
            execution_status={},
        )
        assert job.is_ready() == expected_value

    @pytest.mark.parametrize(
        "status,expected_value",
        [
            ({}, {}),
            ({"conditions": []}, {}),
            ({"conditions": [{"type": "Dog", "val": "value"}]}, {}),
            (
                {"conditions": [{"type": "Ready", "val": "value"}]},
                {"type": "Ready", "val": "value"},
            ),
            (
                {
                    "conditions": [
                        {"type": "Dog", "val": "value"},
                        {"type": "Ready", "val": "value"},
                    ]
                },
                {"type": "Ready", "val": "value"},
            ),
        ],
    )
    def test_get_ready_condition(self, status, expected_value):
        assert Job._get_ready_condition({"status": status}) == expected_value

    @pytest.mark.parametrize(
        "status,expected_value",
        [
            ({}, {}),
            ({"latestCreatedExecution": {}}, {}),
            ({"latestCreatedExecution": {"some": "val"}}, {"some": "val"}),
        ],
    )
    def test_get_execution_status(self, status, expected_value):
        assert Job._get_execution_status({"status": status}) == expected_value

    @pytest.mark.parametrize(
        "execution_status,expected_value",
        [
            ({}, True),  # Has no execution
            (
                {"completionTimestamp": None},
                True,
            ),  # Has an execution with no completion timestamp
            (
                {"completionTimestamp": "Exists"},
                False,
            ),  # Has an execution and it has a completion timestamp
        ],
    )
    def test_has_execution_in_progress(self, execution_status, expected_value):
        job = Job(
            metadata={},
            spec={},
            status={},
            name="test",
            ready_condition={},
            execution_status=execution_status,
        )
        assert job.has_execution_in_progress() == expected_value

    def test_get_calls_correct_methods(self, mock_client):
        """Desired behavior: should call jobs().get().execute() with correct
        job name and namespace
        """
        mock_client.jobs().get().execute.return_value = jobs_return_value
        Job.get(client=mock_client, namespace="my-project-id", job_name="my-job-name")
        desired_calls = [
            "call.jobs().get()",  # Used to setup mock return
            "call.jobs().get(name='namespaces/my-project-id/jobs/my-job-name')",
            "call.jobs().get().execute()",
        ]
        actual_calls = list_mock_calls(mock_client=mock_client)
        assert actual_calls == desired_calls

    def test_return_value_for_get(self, mock_client):
        """Desired behavior: should return a Job object populated with values from
        `jobs_return_value` test object
        """
        mock_client.jobs().get().execute.return_value = jobs_return_value
        res = Job.get(
            client=mock_client, namespace="my-project-id", job_name="my-job-name"
        )

        assert res.name == jobs_return_value["metadata"]["name"]
        assert res.metadata == jobs_return_value["metadata"]
        assert res.spec == jobs_return_value["spec"]
        assert res.status == jobs_return_value["status"]
        assert res.ready_condition == jobs_return_value["status"]["conditions"][0]
        assert (
            res.execution_status
            == jobs_return_value["status"]["latestCreatedExecution"]
        )

    def test_delete_job(self, mock_client):
        """
        Desired behavior: should call jobs().delete().execute() with correct
        job name and namespace
        """
        Job.delete(
            client=mock_client, namespace="my-project-id", job_name="my-job-name"
        )
        desired_calls = [
            "call.jobs().delete(name='namespaces/my-project-id/jobs/my-job-name')",
            "call.jobs().delete().execute()",
        ]
        actual_calls = list_mock_calls(mock_client=mock_client)
        assert actual_calls == desired_calls

    def test_run_job(self, mock_client):
        """
        Desired behavior: should call jobs().run().execute() with correct
        job name and namespace
        """
        Job.run(client=mock_client, namespace="my-project-id", job_name="my-job-name")
        desired_calls = [
            "call.jobs().run(name='namespaces/my-project-id/jobs/my-job-name')",
            "call.jobs().run().execute()",
        ]
        actual_calls = list_mock_calls(mock_client=mock_client)
        assert actual_calls == desired_calls

    def test_create_job(self, mock_client):
        """
        Desired behavior: should call jobs().create().execute() with correct
        namespace and body
        """
        Job.create(client=mock_client, namespace="my-project-id", body={"dog": "cat"})
        desired_calls_v1 = [
            "call.jobs().create(parent='namespaces/my-project-id', body={'dog': 'cat'})",  # noqa
            "call.jobs().create().execute()",
        ]
        # ordering is non-deterministic
        desired_calls_v2 = [
            "call.jobs().create(body={'dog': 'cat'}, parent='namespaces/my-project-id')",  # noqa
            "call.jobs().create().execute()",
        ]
        actual_calls = list_mock_calls(mock_client=mock_client)
        try:
            assert actual_calls == desired_calls_v1
        except AssertionError:
            assert actual_calls == desired_calls_v2


class TestExecution:
    def test_succeeded_responds_true(self):
        """Desired behavior: `succeeded()` should return true if execution.status
        contains a list element that is a dict with a key "type" and a value of
        "Completed" and a key "status" and a value of "True"
        """
        execution = Execution(
            name="Test",
            namespace="test-namespace",
            metadata={},
            spec={},
            status={"conditions": [{"type": "Completed", "status": "True"}]},
            log_uri="",
        )
        assert execution.succeeded()

    @pytest.mark.parametrize(
        "conditions",
        [
            [],
            [{"type": "Dog", "status": "True"}],
            [{"type": "Completed", "status": "False"}],
            [{"type": "Completed", "status": "Dog"}],
        ],
    )
    def test_succeeded_responds_false(self, conditions):
        """Desired behavior: `succeeded()` should return False if execution.status
        lacks a list element that is a dict with a key "type" and a value of
        "Completed" and a key "status" and a value of "True".

        This could be a situation where there is no element containing the key, or
        the element with the key has a status that is not "True".
        """
        execution = Execution(
            name="Test",
            namespace="test-namespace",
            metadata={},
            spec={},
            status={"conditions": conditions},
            log_uri="",
        )
        assert not execution.succeeded()

    @pytest.mark.parametrize(
        "status,expected_value", [({}, True), ({"completionTime": "xyz"}, False)]
    )
    def test_is_running(self, status, expected_value):
        """Desired behavior: `is_running()` should return True if there if
        execution.status lack a key "completionTime", otherwise return False
        """
        execution = Execution(
            name="Test",
            namespace="test-namespace",
            metadata={},
            spec={},
            status=status,
            log_uri="",
        )
        assert execution.is_running() == expected_value

    @pytest.mark.parametrize(
        "conditions, expected_value",
        [
            ([], None),
            ([{"type": "Dog", "status": "True"}], None),
            (
                [{"type": "Completed", "status": "False"}],
                {"type": "Completed", "status": "False"},
            ),
            (
                [
                    {"type": "Dog", "status": "True"},
                    {"type": "Completed", "status": "False"},
                ],
                {"type": "Completed", "status": "False"},
            ),
        ],
    )
    def test_condition_after_completion_returns_correct_condition(
        self, conditions, expected_value
    ):
        """Desired behavior: `condition_after_completion()`
        should return the list element from execution.status that contains a dict
        with a key "type" and a value of "Completed" if it exists, else None
        """
        execution = Execution(
            name="Test",
            namespace="test-namespace",
            metadata={},
            spec={},
            status={"conditions": conditions},
            log_uri="",
        )
        assert execution.condition_after_completion() == expected_value

    def test_return_value_for_get(self, mock_client):
        """Desired behavior: should return an Execution object populated with values from
        `executions_return_value` test object
        """
        mock_client.executions().get().execute.return_value = executions_return_value
        res = Execution.get(
            client=mock_client,
            namespace="my-project-id",
            execution_name="test-execution-name",
        )

        assert res.name == executions_return_value["metadata"]["name"]
        assert res.namespace == executions_return_value["metadata"]["namespace"]
        assert res.metadata == executions_return_value["metadata"]
        assert res.spec == executions_return_value["spec"]
        assert res.status == executions_return_value["status"]
        assert res.log_uri == executions_return_value["status"]["logUri"]

    def test_get_calls_correct_methods(self, mock_client):
        """
        Desired behavior: should call executions().get().execute() with correct
        job name and namespace
        """
        mock_client.executions().get().execute.return_value = executions_return_value
        Execution.get(
            client=mock_client,
            namespace="my-project-id",
            execution_name="my-execution-name",
        )
        desired_calls = [
            "call.executions().get()",  # Used to setup mock return
            "call.executions().get(name='namespaces/my-project-id/executions/my-execution-name')",  # noqa
            "call.executions().get().execute()",
        ]
        actual_calls = list_mock_calls(mock_client=mock_client)
        assert actual_calls == desired_calls


@pytest.fixture
def cloud_run_job(service_account_info):
    return CloudRunJob(
        image="gcr.io//not-a/real-image",
        region="middle-earth2",
        credentials=GcpCredentials(service_account_info=service_account_info),
    )


def remove_server_url_from_env(env):
    """
    For convenience since the testing database URL is non-deterministic.
    """
    return [
        env_var
        for env_var in env
        if env_var["name"]
        not in [
            "PREFECT_API_DATABASE_CONNECTION_URL",
            "PREFECT_ORION_DATABASE_CONNECTION_URL",
            "PREFECT_SERVER_DATABASE_CONNECTION_URL",
        ]
    ]


class TestCloudRunJobContainerSettings:
    def test_captures_prefect_env(self, cloud_run_job):
        base_setting = {}
        with temporary_settings(
            updates={
                PREFECT_API_KEY: "Dog",
                PREFECT_API_URL: "Puppy",
                PREFECT_PROFILES_PATH: "Woof",
            },
            restore_defaults={PREFECT_LOGGING_TO_API_ENABLED},
        ):
            result = cloud_run_job._add_container_settings(base_setting)
            assert remove_server_url_from_env(result["env"]) == [
                {"name": "PREFECT_API_URL", "value": "Puppy"},
                {"name": "PREFECT_API_KEY", "value": "Dog"},
                {"name": "PREFECT_PROFILES_PATH", "value": "Woof"},
            ]

    def test_adds_job_env(self, cloud_run_job):
        base_setting = {}
        cloud_run_job.env = {"TestVar": "It's Working"}

        with temporary_settings(
            updates={
                PREFECT_API_KEY: "Dog",
                PREFECT_API_URL: "Puppy",
                PREFECT_PROFILES_PATH: "Woof",
            },
            restore_defaults={PREFECT_LOGGING_TO_API_ENABLED},
        ):
            result = cloud_run_job._add_container_settings(base_setting)
            assert remove_server_url_from_env(result["env"]) == [
                {"name": "PREFECT_API_URL", "value": "Puppy"},
                {"name": "PREFECT_API_KEY", "value": "Dog"},
                {"name": "PREFECT_PROFILES_PATH", "value": "Woof"},
                {"name": "TestVar", "value": "It's Working"},
            ]

    def test_job_env_overrides_base_env(self, cloud_run_job):
        base_setting = {}
        cloud_run_job.env = {
            "TestVar": "It's Working",
            "PREFECT_API_KEY": "Cat",
            "PREFECT_API_URL": "Kitty",
        }

        with temporary_settings(
            updates={
                PREFECT_API_KEY: "Dog",
                PREFECT_API_URL: "Puppy",
                PREFECT_PROFILES_PATH: "Woof",
            },
            restore_defaults={PREFECT_LOGGING_TO_API_ENABLED},
        ):
            result = cloud_run_job._add_container_settings(base_setting)
            assert remove_server_url_from_env(result["env"]) == [
                {"name": "PREFECT_API_URL", "value": "Kitty"},
                {"name": "PREFECT_API_KEY", "value": "Cat"},
                {"name": "PREFECT_PROFILES_PATH", "value": "Woof"},
                {"name": "TestVar", "value": "It's Working"},
            ]

    def test_command_overrides_default(self, cloud_run_job):
        cmd = ["echo", "howdy!"]
        cloud_run_job.command = cmd
        base_setting = {}
        result = cloud_run_job._add_container_settings(base_setting)
        assert result["command"] == cmd

    def test_resources_skipped_by_default(self, cloud_run_job):
        base_setting = {}
        result = cloud_run_job._add_container_settings(base_setting)
        assert result.get("resources") is None

    def test_resources_added_correctly(self, cloud_run_job):
        cpu = 1
        memory = 12
        memory_unit = "G"
        cloud_run_job.cpu = cpu
        cloud_run_job.memory = memory
        cloud_run_job.memory_unit = memory_unit
        base_setting = {}
        result = cloud_run_job._add_container_settings(base_setting)
        expected_cpu = "1000m"
        assert result["resources"] == {
            "limits": {"cpu": expected_cpu, "memory": str(memory) + memory_unit},
            "requests": {"cpu": expected_cpu, "memory": str(memory) + memory_unit},
        }

    def test_timeout_added_correctly(self, cloud_run_job):
        timeout = 10
        cloud_run_job.timeout = timeout
        result = cloud_run_job._jobs_body()
        assert result["spec"]["template"]["spec"]["template"]["spec"][
            "timeoutSeconds"
        ] == str(timeout)

    def test_max_retries_added_correctly(self, cloud_run_job):
        max_retries = 2
        cloud_run_job.max_retries = max_retries
        result = cloud_run_job._jobs_body()
        assert (
            result["spec"]["template"]["spec"]["template"]["spec"]["maxRetries"]
            == max_retries
        )

    def test_vpc_connector_name_added_correctly(self, cloud_run_job):
        cloud_run_job.vpc_connector_name = "vpc_name"
        result = cloud_run_job._jobs_body()
        assert (
            result["spec"]["template"]["metadata"]["annotations"][
                "run.googleapis.com/vpc-access-connector"
            ]
            == "vpc_name"
        )

    def test_memory_validation_succeeds(self, gcp_credentials):
        """Make sure that memory validation doesn't fail when valid params provided."""
        CloudRunJob(
            image="gcr.io//not-a/real-image",
            region="middle-earth2",
            credentials=gcp_credentials,
            cpu=1,
            memory=1,
            memory_unit="G",
        )

    def test_memory_validation_fails(self, gcp_credentials):
        """Make sure memory validation fails without both unit and memory"""
        with pytest.raises(pydantic.error_wrappers.ValidationError):
            CloudRunJob(
                image="gcr.io//not-a/real-image",
                region="middle-earth2",
                credentials=gcp_credentials,
                cpu=1,
                memory_unit="G",
            )
        with pytest.raises(pydantic.error_wrappers.ValidationError):
            CloudRunJob(
                image="gcr.io//not-a/real-image",
                region="middle-earth2",
                credentials=gcp_credentials,
                cpu=1,
                memory=1,
            )

    def test_args_skipped_by_default(self, cloud_run_job):
        base_setting = {}
        result = cloud_run_job._add_container_settings(base_setting)
        assert result.get("args") is None

    def test_args_added_correctly(self, cloud_run_job):
        args = ["a", "b"]
        cloud_run_job.args = args
        base_setting = {}
        result = cloud_run_job._add_container_settings(base_setting)
        assert result["args"] == args


def test_get_client_uses_correct_endpoint(monkeypatch, mock_credentials, cloud_run_job):
    """Expected behavior: desired endpoint is called."""
    mock = Mock()
    monkeypatch.setattr("prefect_gcp.cloud_run.discovery.build", mock)
    cloud_run_job._get_client()
    desired_endpoint = f"https://{cloud_run_job.region}-run.googleapis.com"
    assert mock.call_args[1]["client_options"].api_endpoint == desired_endpoint


class TestCloudRunJobRun:
    job_ready = {
        "metadata": {"name": "Test", "namespace": "test-namespace"},
        "spec": {"MySpec": "spec"},
        "status": {
            "conditions": [{"type": "Ready", "status": "True"}],
            "latestCreatedExecution": {"puppy": "kitty"},
        },
    }
    execution_ready = {
        "metadata": {"name": "test-name", "namespace": "test-namespace"},
        "spec": {"MySpec": "spec"},
        "status": {"logUri": "test-log-uri"},
    }
    execution_complete_and_succeeded = {
        "metadata": {"name": "test-name", "namespace": "test-namespace"},
        "spec": {"MySpec": "spec"},
        "status": {
            "logUri": "test-log-uri",
            "completionTime": "Done!",
            "conditions": [{"type": "Completed", "status": "True"}],
        },
    }
    execution_not_found = {
        "metadata": {"name": "test-name", "namespace": "test-namespace"},
        "spec": {"MySpec": "spec"},
        "status": {
            "logUri": "test-log-uri",
            "completionTime": "Done!",
            "conditions": [
                {"type": "Completed", "status": "False", "message": "Not found"}
            ],
        },
    }
    execution_complete_and_failed = {
        "metadata": {"name": "test-name", "namespace": "test-namespace"},
        "spec": {"MySpec": "spec"},
        "status": {
            "logUri": "test-log-uri",
            "completionTime": "Done!",
            "conditions": [
                {"type": "Completed", "status": "False", "message": "test failure"}
            ],
        },
    }

    @pytest.mark.parametrize(
        "keep_job,expected_calls",
        [
            (
                True,
                [
                    "call.jobs().create",
                    "call.jobs().create().execute()",
                ],
            ),
            (
                False,
                [
                    "call.jobs().create",
                    "call.jobs().create().execute()",
                    "call.jobs().get",
                    "call.jobs().get().execute()",
                    "call.jobs().run",
                    "call.jobs().run().execute()",
                ],
            ),
        ],
    )
    def test_happy_path_api_calls_made_correctly(
        self, mock_client, cloud_run_job, keep_job, expected_calls
    ):
        """Expected behavior:
        Happy path:
        - A call to Job.create and execute
        - A call to Job.get and execute (check status)
        - A call to Job.run and execute (start the job when status is ready)
        - A call to Executions.get and execute (see the status of the Execution)
        - A call to Job.delete and execute if `keep_job` False, otherwise no call
        """
        cloud_run_job.keep_job = keep_job
        mock_client.jobs().get().execute.return_value = self.job_ready
        mock_client.jobs().run().execute.return_value = self.job_ready
        mock_client.executions().get().execute.return_value = (
            self.execution_complete_and_succeeded
        )
        cloud_run_job.run()
        calls = list_mock_calls(mock_client, 3)

        for call, expected_call in zip(calls, expected_calls):
            assert call.startswith(expected_call)

    def test_happy_path_result(self, mock_client, cloud_run_job):
        """Expected behavior: returns a CloudrunJobResult with status_code 0"""
        cloud_run_job.keep_job = True
        mock_client.jobs().get().execute.return_value = self.job_ready
        mock_client.jobs().run().execute.return_value = self.job_ready
        mock_client.executions().get().execute.return_value = (
            self.execution_complete_and_succeeded
        )
        res = cloud_run_job.run()
        assert isinstance(res, CloudRunJobResult)
        assert res.status_code == 0

    @pytest.mark.parametrize(
        "keep_job,expected_calls",
        [
            (
                True,
                [
                    "call.jobs().create",
                    "call.jobs().create().execute()",
                ],
            ),
            (
                False,
                [
                    "call.jobs().create",
                    "call.jobs().create().execute()",
                    "call.jobs().delete",
                    "call.jobs().delete().execute()",
                ],
            ),
        ],
    )
    def test_behavior_called_when_job_get_fails(
        self, monkeypatch, mock_client, cloud_run_job, keep_job, expected_calls
    ):
        """Expected behavior:
        When job create is called, but there is a subsequent exception on a get,
        there should be a delete call for that job if `keep_job` is False
        """
        cloud_run_job.keep_job = keep_job

        # Getting job will raise error
        def raise_exception(*args, **kwargs):
            raise Exception("This is an intentional exception")

        monkeypatch.setattr("prefect_gcp.cloud_run.Job.get", raise_exception)

        with pytest.raises(Exception):
            cloud_run_job.run()
        calls = list_mock_calls(mock_client, 0)

        for call, expected_call in zip(calls, expected_calls):
            assert call.startswith(expected_call)

    # Test that RuntimeError raised if something happens with execution
    @pytest.mark.parametrize(
        "keep_job,expected_calls",
        [
            (
                True,
                [
                    "call.jobs().create",
                    "call.jobs().create().execute()",
                    "call.jobs().get",
                    "call.jobs().get().execute()",
                    "call.jobs().run",
                    "call.jobs().run().execute()",
                ],
            ),
            (
                False,
                [
                    "call.jobs().create",
                    "call.jobs().create().execute()",
                    "call.jobs().get",
                    "call.jobs().get().execute()",
                    "call.jobs().run",
                    "call.jobs().run().execute()",
                    "call.jobs().delete",
                    "call.jobs().delete().execute()",
                ],
            ),
        ],
    )
    def test_behavior_called_when_execution_get_fails(
        self, monkeypatch, mock_client, cloud_run_job, keep_job, expected_calls
    ):
        """Expected behavior:
        Job creation is called successfully, the job is found when `get` is called,
        job `run` is called, but the execution fails, there should be a delete
        call for that job if `keep_job` is False, and an exception should be raised.
        """
        cloud_run_job.keep_job = keep_job
        mock_client.jobs().get().execute.return_value = self.job_ready
        mock_client.jobs().run().execute.return_value = self.job_ready

        # Getting execution will raise error
        def raise_exception(*args, **kwargs):
            raise Exception("This is an intentional exception")

        monkeypatch.setattr("prefect_gcp.cloud_run.Execution.get", raise_exception)

        with pytest.raises(Exception):
            cloud_run_job.run()
        calls = list_mock_calls(mock_client, 2)
        for call, expected_call in zip(calls, expected_calls):
            assert call.startswith(expected_call)

    async def test_kill(self, mock_client, cloud_run_job):
        mock_client.jobs().get().execute.return_value = self.job_ready
        mock_client.jobs().run().execute.return_value = self.job_ready
        mock_client.executions().get().execute.return_value = self.execution_not_found

        with anyio.fail_after(5):
            async with anyio.create_task_group() as tg:
                identifier = await tg.start(cloud_run_job.run)
                await cloud_run_job.kill(identifier)

        actual_calls = list_mock_calls(mock_client=mock_client)
        assert "call.jobs().delete().execute()" in actual_calls

    def failed_to_get(self):
        raise HttpError(Mock(reason="does not exist"), content=b"")

    async def test_kill_not_found(self, mock_client, cloud_run_job):
        mock_client.jobs().delete().execute.side_effect = self.failed_to_get
        with pytest.raises(
            InfrastructureNotFound, match="Cannot stop Cloud Run Job; the job name"
        ):
            await cloud_run_job.kill("non-existent")

    async def test_kill_grace_seconds(self, mock_client, cloud_run_job, caplog):
        mock_client.jobs().get().execute.return_value = self.job_ready
        mock_client.jobs().run().execute.return_value = self.job_ready
        mock_client.executions().get().execute.return_value = self.execution_not_found

        with anyio.fail_after(5):
            async with anyio.create_task_group() as tg:
                identifier = await tg.start(cloud_run_job.run)
                await cloud_run_job.kill(identifier, grace_seconds=42)

        for record in caplog.records:
            if "Kill grace period of 42s requested, but GCP does not" in record.msg:
                break
        else:
            raise AssertionError("Expected message not found.")


@pytest.fixture
def default_base_job_template():
    return deepcopy(CloudRunWorker.get_default_base_job_template())


@pytest.fixture
async def credentials_block(service_account_info):
    credentials_block = GcpCredentials(
        service_account_info=service_account_info, project="my-project"
    )
    await credentials_block.save("test-for-publish", overwrite=True)
    return credentials_block


@pytest.fixture
def base_job_template_with_defaults(default_base_job_template, credentials_block):
    base_job_template_with_defaults = deepcopy(default_base_job_template)
    base_job_template_with_defaults["variables"]["properties"]["command"][
        "default"
    ] = "python my_script.py"
    base_job_template_with_defaults["variables"]["properties"]["env"]["default"] = {
        "VAR1": "value1",
        "VAR2": "value2",
    }
    base_job_template_with_defaults["variables"]["properties"]["labels"]["default"] = {
        "label1": "value1",
        "label2": "value2",
    }
    base_job_template_with_defaults["variables"]["properties"]["name"][
        "default"
    ] = "prefect-job"
    base_job_template_with_defaults["variables"]["properties"]["image"][
        "default"
    ] = "docker.io/my_image:latest"
    base_job_template_with_defaults["variables"]["properties"]["cpu"][
        "default"
    ] = "1000m"
    base_job_template_with_defaults["variables"]["properties"]["memory"][
        "default"
    ] = "512Mi"
    base_job_template_with_defaults["variables"]["properties"]["timeout"][
        "default"
    ] = 60
    base_job_template_with_defaults["variables"]["properties"]["vpc_connector_name"][
        "default"
    ] = "my-vpc-connector"
    base_job_template_with_defaults["variables"]["properties"]["keep_job"][
        "default"
    ] = True
    base_job_template_with_defaults["variables"]["properties"]["credentials"][
        "default"
    ] = {"$ref": {"block_document_id": str(credentials_block._block_document_id)}}
    base_job_template_with_defaults["variables"]["properties"]["region"][
        "default"
    ] = "us-central1"
    base_job_template_with_defaults["variables"]["properties"]["args"] = {
        "title": "Arguments",
        "type": "string",
        "description": "Arguments to be passed to your Cloud Run Job's entrypoint command.",  # noqa
        "default": ["--arg1", "value1", "--arg2", "value2"],
    }
    base_job_template_with_defaults["job_configuration"]["job_body"]["spec"][
        "template"
    ]["spec"]["template"]["spec"]["containers"][0]["args"] = "{{ args }}"

    return base_job_template_with_defaults


@pytest.mark.parametrize(
    "job_config",
    [
        "default",
        "custom",
    ],
)
async def test_generate_work_pool_base_job_template(
    job_config,
    base_job_template_with_defaults,
    credentials_block,
    default_base_job_template,
):
    job = CloudRunJob(
        image="docker.io/my_image:latest",
        region="us-central1",
        credentials=credentials_block,
    )
    expected_template = default_base_job_template
    expected_template["variables"]["properties"]["image"][
        "default"
    ] = "docker.io/my_image:latest"
    expected_template["variables"]["properties"]["region"]["default"] = "us-central1"
    expected_template["variables"]["properties"]["credentials"]["default"] = {
        "$ref": {"block_document_id": str(credentials_block._block_document_id)}
    }
    if job_config == "custom":
        expected_template = base_job_template_with_defaults
        job = CloudRunJob(
            command=["python", "my_script.py"],
            env={"VAR1": "value1", "VAR2": "value2"},
            labels={"label1": "value1", "label2": "value2"},
            name="prefect-job",
            image="docker.io/my_image:latest",
            cpu=1,
            memory=512,
            memory_unit="Mi",
            timeout=60,
            vpc_connector_name="my-vpc-connector",
            keep_job=True,
            credentials=credentials_block,
            region="us-central1",
            args=["--arg1", "value1", "--arg2", "value2"],
        )

    template = await job.generate_work_pool_base_job_template()

    assert template == expected_template
