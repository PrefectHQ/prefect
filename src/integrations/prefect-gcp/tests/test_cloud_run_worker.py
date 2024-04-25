import uuid
from unittest.mock import Mock

import anyio
from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    import pydantic.v1 as pydantic
else:
    import pydantic

import pytest
from googleapiclient.errors import HttpError
from jsonschema.exceptions import ValidationError
from prefect_gcp.credentials import GcpCredentials
from prefect_gcp.utilities import slugify_name
from prefect_gcp.workers.cloud_run import (
    CloudRunWorker,
    CloudRunWorkerJobConfiguration,
    CloudRunWorkerResult,
)

from prefect.client.schemas import FlowRun
from prefect.exceptions import InfrastructureNotFound
from prefect.server.schemas.actions import DeploymentCreate


@pytest.fixture(autouse=True)
def mock_credentials(gcp_credentials):
    yield


@pytest.fixture
def jobs_body():
    return {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "metadata": {
            "annotations": {
                # See: https://cloud.google.com/run/docs/troubleshooting#launch-stage-validation  # noqa
                "run.googleapis.com/launch-stage": "BETA",
            },
        },
        "spec": {  # JobSpec
            "template": {  # ExecutionTemplateSpec
                "spec": {  # ExecutionSpec
                    "template": {  # TaskTemplateSpec
                        "spec": {"containers": [{}]},  # TaskSpec
                    },
                },
            },
        },
    }


@pytest.fixture
def flow_run():
    return FlowRun(flow_id=uuid.uuid4(), name="my-flow-run-name")


@pytest.fixture
def cloud_run_worker_job_config(service_account_info, jobs_body):
    return CloudRunWorkerJobConfiguration(
        name="my-job-name",
        image="gcr.io//not-a/real-image",
        region="middle-earth2",
        job_body=jobs_body,
        credentials=GcpCredentials(service_account_info=service_account_info),
    )


@pytest.fixture
def cloud_run_worker_job_config_noncompliant_name(service_account_info, jobs_body):
    return CloudRunWorkerJobConfiguration(
        name="MY_JOB_NAME",
        image="gcr.io//not-a/real-image",
        region="middle-earth2",
        job_body=jobs_body,
        credentials=GcpCredentials(service_account_info=service_account_info),
    )


class TestCloudRunWorkerJobConfiguration:
    def test_job_name(self, cloud_run_worker_job_config):
        cloud_run_worker_job_config.job_body["metadata"]["name"] = "my-job-name"
        assert cloud_run_worker_job_config.job_name == "my-job-name"

    def test_job_name_is_slug(self, cloud_run_worker_job_config_noncompliant_name):
        cloud_run_worker_job_config_noncompliant_name._populate_name_if_not_present()
        assert cloud_run_worker_job_config_noncompliant_name.job_name[
            :-33
        ] == slugify_name("MY_JOB_NAME")

    def test_populate_envs(
        self,
        cloud_run_worker_job_config,
    ):
        container = cloud_run_worker_job_config.job_body["spec"]["template"]["spec"][
            "template"
        ]["spec"]["containers"][0]

        assert "env" not in container
        assert cloud_run_worker_job_config.env == {}
        cloud_run_worker_job_config.env = {"a": "b"}

        cloud_run_worker_job_config._populate_envs()

        assert "env" in container
        assert len(container["env"]) == 1
        assert container["env"][0]["name"] == "a"
        assert container["env"][0]["value"] == "b"

    def test_populate_image_if_not_present(self, cloud_run_worker_job_config):
        container = cloud_run_worker_job_config.job_body["spec"]["template"]["spec"][
            "template"
        ]["spec"]["containers"][0]

        assert "image" not in container

        cloud_run_worker_job_config._populate_image_if_not_present()

        # defaults to prefect image
        assert "image" in container
        assert container["image"].startswith("docker.io/prefecthq/prefect:")

    def test_populate_image_doesnt_overwrite(self, cloud_run_worker_job_config):
        image = "my-first-image"
        container = cloud_run_worker_job_config.job_body["spec"]["template"]["spec"][
            "template"
        ]["spec"]["containers"][0]
        container["image"] = image

        cloud_run_worker_job_config._populate_image_if_not_present()

        assert container["image"] == image

    def test_populate_name_if_not_present(self, cloud_run_worker_job_config):
        metadata = cloud_run_worker_job_config.job_body["metadata"]

        assert "name" not in metadata

        cloud_run_worker_job_config._populate_name_if_not_present()

        assert "name" in metadata
        assert metadata["name"][:-33] == cloud_run_worker_job_config.name

    def test_job_name_different_after_retry(self, cloud_run_worker_job_config):
        metadata = cloud_run_worker_job_config.job_body["metadata"]

        assert "name" not in metadata

        cloud_run_worker_job_config._populate_name_if_not_present()
        job_name_1 = metadata.pop("name")

        cloud_run_worker_job_config._populate_name_if_not_present()
        job_name_2 = metadata.pop("name")

        assert job_name_1[:-33] == job_name_2[:-33]
        assert job_name_1 != job_name_2

    def test_populate_or_format_command_doesnt_exist(self, cloud_run_worker_job_config):
        container = cloud_run_worker_job_config.job_body["spec"]["template"]["spec"][
            "template"
        ]["spec"]["containers"][0]

        assert "command" not in container

        cloud_run_worker_job_config._populate_or_format_command()

        assert "command" in container
        assert container["command"] == ["prefect", "flow-run", "execute"]

    def test_populate_or_format_command_already_exists(
        self, cloud_run_worker_job_config
    ):
        command = "my command and args"
        container = cloud_run_worker_job_config.job_body["spec"]["template"]["spec"][
            "template"
        ]["spec"]["containers"][0]
        container["command"] = command

        cloud_run_worker_job_config._populate_or_format_command()

        assert "command" in container
        assert container["command"] == command.split()

    def test_format_args_if_present(self, cloud_run_worker_job_config):
        args = "my args"
        container = cloud_run_worker_job_config.job_body["spec"]["template"]["spec"][
            "template"
        ]["spec"]["containers"][0]
        container["args"] = args

        cloud_run_worker_job_config._format_args_if_present()

        assert "args" in container
        assert container["args"] == args.split()

    def test_format_args_if_present_no_args(self, cloud_run_worker_job_config):
        container = cloud_run_worker_job_config.job_body["spec"]["template"]["spec"][
            "template"
        ]["spec"]["containers"][0]
        assert "args" not in container

        cloud_run_worker_job_config._format_args_if_present()

        assert "args" not in container

    def test_populate_name_doesnt_overwrite(
        self, cloud_run_worker_job_config, flow_run
    ):
        name = "my-name"
        metadata = cloud_run_worker_job_config.job_body["metadata"]
        metadata["name"] = name

        cloud_run_worker_job_config._populate_name_if_not_present()

        assert "name" in metadata
        assert metadata["name"] != flow_run.name
        assert metadata["name"] == name

    async def test_validates_against_an_empty_job_body(self):
        template = CloudRunWorker.get_default_base_job_template()
        template["job_configuration"]["job_body"] = {}
        template["job_configuration"]["region"] = "test-region1"

        with pytest.raises(pydantic.ValidationError) as excinfo:
            await CloudRunWorkerJobConfiguration.from_template_and_values(template, {})

        assert excinfo.value.errors() == [
            {
                "loc": ("job_body",),
                "msg": (
                    "Job is missing required attributes at the following paths: "
                    "/apiVersion, /kind, /metadata, /spec"
                ),
                "type": "value_error",
            }
        ]

    async def test_validates_for_a_job_body_missing_deeper_attributes(self):
        template = CloudRunWorker.get_default_base_job_template()
        template["job_configuration"]["job_body"] = {
            "apiVersion": "run.googleapis.com/v1",
            "kind": "Job",
            "metadata": {},
            "spec": {"template": {"spec": {"template": {"spec": {}}}}},
        }
        template["job_configuration"]["region"] = "test-region1"

        with pytest.raises(pydantic.ValidationError) as excinfo:
            await CloudRunWorkerJobConfiguration.from_template_and_values(template, {})

        assert excinfo.value.errors() == [
            {
                "loc": ("job_body",),
                "msg": (
                    "Job is missing required attributes at the following paths: "
                    "/metadata/annotations, "
                    "/spec/template/spec/template/spec/containers"
                ),
                "type": "value_error",
            }
        ]

    async def test_validates_for_a_job_with_incompatible_values(self):
        """We should give a human-friendly error when the user provides a custom Job
        manifest that is attempting to change required values."""
        template = CloudRunWorker.get_default_base_job_template()
        template["job_configuration"]["region"] = "test-region1"
        template["job_configuration"]["job_body"] = {
            "apiVersion": "v1",
            "kind": "NOTAJOB",
            "metadata": {
                "annotations": {
                    "run.googleapis.com/launch-stage": "NOTABETA",
                },
            },
            "spec": {  # JobSpec
                "template": {  # ExecutionTemplateSpec
                    "spec": {  # ExecutionSpec
                        "template": {  # TaskTemplateSpec
                            "spec": {"containers": [{}]},  # TaskSpec
                        },
                    },
                },
            },
        }

        with pytest.raises(pydantic.ValidationError) as excinfo:
            await CloudRunWorkerJobConfiguration.from_template_and_values(template, {})

        assert excinfo.value.errors() == [
            {
                "loc": ("job_body",),
                "msg": (
                    "Job has incompatible values for the following attributes: "
                    "/apiVersion must have value 'run.googleapis.com/v1', "
                    "/kind must have value 'Job', "
                    "/metadata/annotations/run.googleapis.com~1launch-stage "
                    "must have value 'BETA'"
                ),
                "type": "value_error",
            }
        ]


class TestCloudRunWorkerValidConfiguration:
    @pytest.mark.parametrize("cpu", ["1", "100", "100m", "1500m"])
    def test_invalid_cpu_string(self, cpu):
        deployment = DeploymentCreate(
            name="my-deployment",
            flow_id=uuid.uuid4(),
            infra_overrides={"region": "test-region1", "cpu": cpu},
        )
        with pytest.raises(ValidationError) as excinfo:
            deployment.check_valid_configuration(
                CloudRunWorker.get_default_base_job_template()
            )

        assert excinfo.value.message == f"'{cpu}' does not match '^(\\\\d*000)m$'"

    @pytest.mark.parametrize("cpu", ["1000m", "2000m", "3000m"])
    def test_valid_cpu_string(self, cpu):
        deployment = DeploymentCreate(
            name="my-deployment",
            flow_id=uuid.uuid4(),
            infra_overrides={"region": "test-region1", "cpu": cpu},
        )
        deployment.check_valid_configuration(
            CloudRunWorker.get_default_base_job_template()
        )

    @pytest.mark.parametrize("memory", ["1", "100", "100Gigs"])
    def test_invalid_memory_string(self, memory):
        deployment = DeploymentCreate(
            name="my-deployment",
            flow_id=uuid.uuid4(),
            infra_overrides={"region": "test-region1", "memory": memory},
        )
        with pytest.raises(ValidationError) as excinfo:
            deployment.check_valid_configuration(
                CloudRunWorker.get_default_base_job_template()
            )
        assert (
            excinfo.value.message
            == f"'{memory}' does not match '^\\\\d+(?:G|Gi|M|Mi)$'"
        )

    @pytest.mark.parametrize("memory", ["512G", "512Gi", "512M", "512Mi"])
    def test_valid_memory_string(self, memory):
        deployment = DeploymentCreate(
            name="my-deployment",
            flow_id=uuid.uuid4(),
            infra_overrides={"region": "test-region1", "memory": memory},
        )
        deployment.check_valid_configuration(
            CloudRunWorker.get_default_base_job_template()
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
        "prefect_gcp.workers.cloud_run.CloudRunWorker._get_client",
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


class TestCloudRunWorker:
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
    async def test_happy_path_api_calls_made_correctly(
        self,
        mock_client,
        cloud_run_worker_job_config,
        keep_job,
        flow_run,
        expected_calls,
    ):
        """Expected behavior:
        Happy path:
        - A call to Job.create and execute
        - A call to Job.get and execute (check status)
        - A call to Job.run and execute (start the job when status is ready)
        - A call to Executions.get and execute (see the status of the Execution)
        - A call to Job.delete and execute if `keep_job` False, otherwise no call
        """
        async with CloudRunWorker("my-work-pool") as cloud_run_worker:
            cloud_run_worker_job_config.keep_job = keep_job
            cloud_run_worker_job_config.prepare_for_flow_run(flow_run, None, None)
            mock_client.jobs().get().execute.return_value = self.job_ready
            mock_client.jobs().run().execute.return_value = self.job_ready
            mock_client.executions().get().execute.return_value = (
                self.execution_complete_and_succeeded
            )
            await cloud_run_worker.run(flow_run, cloud_run_worker_job_config)
            calls = list_mock_calls(mock_client, 3)

            for call, expected_call in zip(calls, expected_calls):
                assert call.startswith(expected_call)

    async def test_happy_path_result(
        self, mock_client, cloud_run_worker_job_config, flow_run
    ):
        """Expected behavior: returns a CloudrunJobResult with status_code 0"""
        async with CloudRunWorker("my-work-pool") as cloud_run_worker:
            cloud_run_worker_job_config.keep_job = True
            cloud_run_worker_job_config.prepare_for_flow_run(flow_run, None, None)
            mock_client.jobs().get().execute.return_value = self.job_ready
            mock_client.jobs().run().execute.return_value = self.job_ready
            mock_client.executions().get().execute.return_value = (
                self.execution_complete_and_succeeded
            )
            res = await cloud_run_worker.run(flow_run, cloud_run_worker_job_config)
            assert isinstance(res, CloudRunWorkerResult)
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
    async def test_behavior_called_when_job_get_fails(
        self,
        monkeypatch,
        mock_client,
        cloud_run_worker_job_config,
        flow_run,
        keep_job,
        expected_calls,
    ):
        """Expected behavior:
        When job create is called, but there is a subsequent exception on a get,
        there should be a delete call for that job if `keep_job` is False
        """
        async with CloudRunWorker("my-work-pool") as cloud_run_worker:
            cloud_run_worker_job_config.keep_job = keep_job

            # Getting job will raise error
            def raise_exception(*args, **kwargs):
                raise Exception("This is an intentional exception")

            monkeypatch.setattr("prefect_gcp.cloud_run.Job.get", raise_exception)

            with pytest.raises(Exception):
                await cloud_run_worker.run(flow_run, cloud_run_worker_job_config)
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
    async def test_behavior_called_when_execution_get_fails(
        self,
        monkeypatch,
        mock_client,
        cloud_run_worker_job_config,
        flow_run,
        keep_job,
        expected_calls,
    ):
        """Expected behavior:
        Job creation is called successfully, the job is found when `get` is called,
        job `run` is called, but the execution fails, there should be a delete
        call for that job if `keep_job` is False, and an exception should be raised.
        """
        async with CloudRunWorker("my-work-pool") as cloud_run_worker:
            cloud_run_worker_job_config.keep_job = keep_job
            mock_client.jobs().get().execute.return_value = self.job_ready
            mock_client.jobs().run().execute.return_value = self.job_ready

            # Getting execution will raise error
            def raise_exception(*args, **kwargs):
                raise Exception("This is an intentional exception")

            monkeypatch.setattr("prefect_gcp.cloud_run.Execution.get", raise_exception)

            with pytest.raises(Exception):
                await cloud_run_worker.run(flow_run, cloud_run_worker_job_config)
            calls = list_mock_calls(mock_client, 2)
            for call, expected_call in zip(calls, expected_calls):
                assert call.startswith(expected_call)

    async def test_kill(self, mock_client, cloud_run_worker_job_config, flow_run):
        async with CloudRunWorker("my-work-pool") as cloud_run_worker:
            cloud_run_worker_job_config.prepare_for_flow_run(flow_run, None, None)

            mock_client.jobs().get().execute.return_value = self.job_ready
            mock_client.jobs().run().execute.return_value = self.job_ready
            mock_client.executions().get().execute.return_value = (
                self.execution_not_found
            )  # noqa

            with anyio.fail_after(5):
                async with anyio.create_task_group() as tg:
                    identifier = await tg.start(
                        cloud_run_worker.run, flow_run, cloud_run_worker_job_config
                    )
                    await cloud_run_worker.kill_infrastructure(
                        identifier, cloud_run_worker_job_config
                    )

            actual_calls = list_mock_calls(mock_client=mock_client)
            assert "call.jobs().delete().execute()" in actual_calls

    def failed_to_get(self):
        raise HttpError(Mock(reason="does not exist"), content=b"")

    async def test_kill_not_found(
        self, mock_client, cloud_run_worker_job_config, flow_run
    ):
        async with CloudRunWorker("my-work-pool") as cloud_run_worker:
            cloud_run_worker_job_config.prepare_for_flow_run(flow_run, None, None)

            mock_client.jobs().delete().execute.side_effect = self.failed_to_get
            with pytest.raises(
                InfrastructureNotFound, match="Cannot stop Cloud Run Job; the job name"
            ):
                await cloud_run_worker.kill_infrastructure(
                    "non-existent", cloud_run_worker_job_config
                )

    async def test_kill_grace_seconds(
        self, mock_client, cloud_run_worker_job_config, flow_run, caplog
    ):
        async with CloudRunWorker("my-work-pool") as cloud_run_worker:
            cloud_run_worker_job_config.prepare_for_flow_run(flow_run, None, None)

            mock_client.jobs().get().execute.return_value = self.job_ready
            mock_client.jobs().run().execute.return_value = self.job_ready
            mock_client.executions().get().execute.return_value = (
                self.execution_not_found
            )

            with anyio.fail_after(5):
                async with anyio.create_task_group() as tg:
                    identifier = await tg.start(
                        cloud_run_worker.run, flow_run, cloud_run_worker_job_config
                    )
                    await cloud_run_worker.kill_infrastructure(
                        identifier, cloud_run_worker_job_config, grace_seconds=42
                    )

            for record in caplog.records:
                if "Kill grace period of 42s requested, but GCP does not" in record.msg:
                    break
            else:
                raise AssertionError("Expected message not found.")
