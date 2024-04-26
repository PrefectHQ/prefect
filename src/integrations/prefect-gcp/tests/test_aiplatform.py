from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest
from google.cloud.aiplatform_v1.types.accelerator_type import AcceleratorType
from google.cloud.aiplatform_v1.types.job_state import JobState
from prefect_gcp.aiplatform import (
    VertexAICustomTrainingJob,
    VertexAICustomTrainingJobResult,
)
from prefect_gcp.credentials import GcpCredentials
from prefect_gcp.workers.vertex import VertexAIWorker
from tenacity import RetryError

from prefect.exceptions import InfrastructureNotFound


class TestVertexAICustomTrainingJob:
    @pytest.fixture
    def vertex_ai_custom_training_job(self, gcp_credentials):
        return VertexAICustomTrainingJob(
            command=["echo", "hello!!"],
            region="us-east1",
            image="us-docker.pkg.dev/cloudrun/container/job:latest",
            gcp_credentials=gcp_credentials,
            labels={"prefect.io/flow-name": "hungry-hippo"},
        )

    # TODO: Improve test resiliency to changes in str output
    @patch("prefect_gcp.aiplatform.VertexAICustomTrainingJob._base_environment")
    def test_preview(
        self, mock_base_env, vertex_ai_custom_training_job: VertexAICustomTrainingJob
    ):
        mock_base_env.return_value = {"PREFECT_API_KEY": "secret"}
        actual_lines = vertex_ai_custom_training_job.preview().splitlines()

        expected_lines = """
            display_name: "container
            job_spec {
                worker_pool_specs {
                    container_spec {
                        image_uri: "us-docker.pkg.dev/cloudrun/container/job:latest"
                        command: "echo"
                        command: "hello!!"
                        env {
                          name: "PREFECT_API_KEY"
                          value: "secret"
                      }
                    }
                    machine_spec {
                        machine_type: "n1-standard-4"
                    }
                    replica_count: 1
                    disk_spec {
                        boot_disk_type: "pd-ssd"
                        boot_disk_size_gb: 100
                    }
                }
                scheduling {
                }
                service_account: "my_service_account_email"
            }
            labels {
                key: "prefect-io_flow-name"
                value: "hungry-hippo"
            }
        """.strip().splitlines()

        for actual_line, expected_line in zip(actual_lines, expected_lines):
            if '"container' in actual_line:
                actual_line = actual_line.split("-")[0]  # remove the unique hex
            assert actual_line.strip() == expected_line.strip()  # disregard whitespace

    @patch("prefect_gcp.aiplatform.VertexAICustomTrainingJob._base_environment")
    def test_environment_variables(self, mock_base_env, gcp_credentials):
        mock_base_env.return_value = {"PREFECT_API_KEY": "secret", "FOO": "INITIAL"}
        vertex_job = VertexAICustomTrainingJob(
            command=["echo", "hello!!"],
            region="us-east1",
            image="us-docker.pkg.dev/cloudrun/container/job:latest",
            gcp_credentials=gcp_credentials,
            env={"FOO": "BAR"},  # overrides
        )
        job_spec = vertex_job._build_job_spec()

        assert len(job_spec.worker_pool_specs) == 1

        env_list_in_container_spec = job_spec.worker_pool_specs[0].container_spec.env

        expected_env = VertexAICustomTrainingJob._base_environment().copy()
        expected_env.update({"FOO": "BAR", "PREFECT_API_KEY": "secret"})

        for item in env_list_in_container_spec:
            assert item.name in expected_env
            assert item.value == expected_env[item.name]

    def test_kill(
        self, vertex_ai_custom_training_job: VertexAICustomTrainingJob, caplog
    ):
        identifier = "projects/1234/locations/us-east1/customJobs/12345"
        vertex_ai_custom_training_job.kill(identifier)
        for record in caplog.records:
            if f"Requested to cancel {identifier}..." in record.msg:
                break
        else:
            raise AssertionError("identifier not in caplog")

    def raise_not_found(self, request):
        raise RuntimeError("Job does not exist")

    def test_kill_infrastructure_not_found(
        self, vertex_ai_custom_training_job: VertexAICustomTrainingJob
    ):
        identifier = "projects/1234/locations/us-east1/customJobs/12345"
        gcp_credentials = vertex_ai_custom_training_job.gcp_credentials
        job_service_client = gcp_credentials.job_service_client
        job_service_client.cancel_custom_job.side_effect = self.raise_not_found
        with pytest.raises(
            InfrastructureNotFound, match="Cannot stop Vertex AI job; the job name"
        ):
            vertex_ai_custom_training_job.kill(identifier)

    def raise_random_error(self, request):
        raise RuntimeError("Random error")

    def test_kill_infrastructure_error(
        self, vertex_ai_custom_training_job: VertexAICustomTrainingJob
    ):
        identifier = "projects/1234/locations/us-east1/customJobs/12345"
        gcp_credentials = vertex_ai_custom_training_job.gcp_credentials
        job_service_client = gcp_credentials.job_service_client
        job_service_client.cancel_custom_job.side_effect = self.raise_random_error
        with pytest.raises(RuntimeError, match="Random error"):
            vertex_ai_custom_training_job.kill(identifier)

    def test_run(self, vertex_ai_custom_training_job: VertexAICustomTrainingJob):
        actual = vertex_ai_custom_training_job.run()
        expected = VertexAICustomTrainingJobResult(
            identifier="mock_display_name", status_code=0
        )
        assert actual == expected

    def test_run_error(self, vertex_ai_custom_training_job: VertexAICustomTrainingJob):
        error = MagicMock(message="my error msg")
        failed_run_final = MagicMock(
            name="mock_name",
            state=JobState.JOB_STATE_FAILED,
            error=error,
            display_name="mock_display_name",
        )
        gcp_credentials = vertex_ai_custom_training_job.gcp_credentials
        gcp_credentials.job_service_client.get_custom_job.return_value = (
            failed_run_final
        )
        with pytest.raises(RuntimeError, match="my error msg"):
            vertex_ai_custom_training_job.run()

    def test_run_start_error(
        self, vertex_ai_custom_training_job: VertexAICustomTrainingJob
    ):
        gcp_credentials = vertex_ai_custom_training_job.gcp_credentials
        gcp_credentials.job_service_client.create_custom_job.side_effect = (
            RuntimeError()
        )

        with pytest.raises(RetryError):
            vertex_ai_custom_training_job.run()
        assert gcp_credentials.job_service_client.create_custom_job.call_count == 3

    def test_machine_spec(
        self, vertex_ai_custom_training_job: VertexAICustomTrainingJob
    ):
        vertex_ai_custom_training_job.accelerator_count = 1
        vertex_ai_custom_training_job.accelerator_type = "NVIDIA_TESLA_T4"

        job_spec = vertex_ai_custom_training_job._build_job_spec()

        assert job_spec.worker_pool_specs[0].machine_spec.accelerator_count == 1
        assert (
            job_spec.worker_pool_specs[0].machine_spec.accelerator_type
            == AcceleratorType.NVIDIA_TESLA_T4
        )


@pytest.fixture
def default_base_job_template():
    return deepcopy(VertexAIWorker.get_default_base_job_template())


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
    base_job_template_with_defaults["variables"]["properties"]["credentials"][
        "default"
    ] = {"$ref": {"block_document_id": str(credentials_block._block_document_id)}}
    base_job_template_with_defaults["variables"]["properties"]["region"][
        "default"
    ] = "us-central1"
    base_job_template_with_defaults["variables"]["properties"]["machine_type"][
        "default"
    ] = "n1-standard-4"
    base_job_template_with_defaults["variables"]["properties"]["accelerator_count"][
        "default"
    ] = 1
    base_job_template_with_defaults["variables"]["properties"]["accelerator_type"][
        "default"
    ] = "NVIDIA_TESLA_T4"
    base_job_template_with_defaults["variables"]["properties"]["boot_disk_type"][
        "default"
    ] = "pd-ssd"
    base_job_template_with_defaults["variables"]["properties"]["boot_disk_size_gb"][
        "default"
    ] = 200
    base_job_template_with_defaults["variables"]["properties"][
        "maximum_run_time_hours"
    ]["default"] = 24
    base_job_template_with_defaults["variables"]["properties"]["network"][
        "default"
    ] = "my-network"
    base_job_template_with_defaults["variables"]["properties"]["reserved_ip_ranges"][
        "default"
    ] = ["172.31.0.0/16", "192.168.0.0./16"]
    base_job_template_with_defaults["variables"]["properties"]["service_account_name"][
        "default"
    ] = "my-service-account"
    base_job_template_with_defaults["variables"]["properties"][
        "job_watch_poll_interval"
    ]["default"] = 60
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
    job = VertexAICustomTrainingJob(
        image="docker.io/my_image:latest",
        region="us-central1",
        gcp_credentials=credentials_block,
    )
    expected_template = default_base_job_template
    default_base_job_template["variables"]["properties"]["image"][
        "default"
    ] = "docker.io/my_image:latest"
    default_base_job_template["variables"]["properties"]["region"][
        "default"
    ] = "us-central1"
    default_base_job_template["variables"]["properties"]["credentials"]["default"] = {
        "$ref": {"block_document_id": str(credentials_block._block_document_id)}
    }
    if job_config == "custom":
        expected_template = base_job_template_with_defaults
        job = VertexAICustomTrainingJob(
            command=["python", "my_script.py"],
            env={"VAR1": "value1", "VAR2": "value2"},
            labels={"label1": "value1", "label2": "value2"},
            name="prefect-job",
            image="docker.io/my_image:latest",
            gcp_credentials=credentials_block,
            region="us-central1",
            machine_type="n1-standard-4",
            accelerator_count=1,
            accelerator_type="NVIDIA_TESLA_T4",
            boot_disk_type="pd-ssd",
            boot_disk_size_gb=200,
            maximum_run_time=60 * 60 * 24,
            network="my-network",
            reserved_ip_ranges=["172.31.0.0/16", "192.168.0.0./16"],
            service_account="my-service-account",
            job_watch_poll_interval=60,
        )

    template = await job.generate_work_pool_base_job_template()

    assert template == expected_template
