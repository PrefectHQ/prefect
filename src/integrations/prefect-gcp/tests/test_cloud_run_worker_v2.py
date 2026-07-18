from unittest import mock
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError
from prefect_gcp.credentials import GcpCredentials
from prefect_gcp.models.cloud_run_v2 import ExecutionV2, SecretKeySelector
from prefect_gcp.utilities import slugify_name
from prefect_gcp.workers.cloud_run_v2 import (
    CloudRunWorkerJobV2Configuration,
    CloudRunWorkerV2,
    CloudRunWorkerV2Result,
)

from prefect.exceptions import InfrastructureNotFound
from prefect.logging.loggers import PrefectLogAdapter
from prefect.utilities.dockerutils import get_prefect_image_name


@pytest.fixture
def job_body():
    return {
        "client": "prefect",
        "launchStage": None,
        "template": {
            "template": {
                "maxRetries": None,
                "timeout": None,
                "vpcAccess": {
                    "connector": None,
                },
                "containers": [
                    {
                        "env": [],
                        "command": None,
                        "args": "-m prefect.engine",
                        "resources": {
                            "limits": {
                                "cpu": None,
                                "memory": None,
                            },
                        },
                    },
                ],
            }
        },
    }


@pytest.fixture
def cloud_run_worker_v2_job_config(service_account_info, job_body):
    return CloudRunWorkerJobV2Configuration(
        name="my-job-name",
        job_body=job_body,
        credentials=GcpCredentials(service_account_info=service_account_info),
        region="us-central1",
        timeout=604800,
        env={"ENV1": "VALUE1", "ENV2": "VALUE2"},
    )


@pytest.fixture
def cloud_run_worker_v2_job_config_noncompliant_name(service_account_info, job_body):
    return CloudRunWorkerJobV2Configuration(
        name="MY_JOB_NAME",
        job_body=job_body,
        credentials=GcpCredentials(service_account_info=service_account_info),
        region="us-central1",
        timeout=604800,
        env={"ENV1": "VALUE1", "ENV2": "VALUE2"},
    )


class TestCloudRunWorkerJobV2Configuration:
    def test_project(self, cloud_run_worker_v2_job_config):
        assert cloud_run_worker_v2_job_config.project == "my_project"

    def test_job_name(self, cloud_run_worker_v2_job_config):
        assert cloud_run_worker_v2_job_config.job_name[:-8] == "my-job-name"

    def test_job_name_is_slug(self, cloud_run_worker_v2_job_config_noncompliant_name):
        assert cloud_run_worker_v2_job_config_noncompliant_name.job_name[
            :-8
        ] == slugify_name("MY_JOB_NAME")

    def test_job_name_different_after_retry(self, cloud_run_worker_v2_job_config):
        job_name_1 = cloud_run_worker_v2_job_config.job_name

        cloud_run_worker_v2_job_config._job_name = None

        job_name_2 = cloud_run_worker_v2_job_config.job_name

        assert job_name_1[:-8] == job_name_2[:-8]
        assert job_name_1 != job_name_2

    def test_job_name_preserves_long_base_name(self, service_account_info, job_body):
        long_name = "a" * 60
        config = CloudRunWorkerJobV2Configuration(
            name=long_name,
            job_body=job_body,
            credentials=GcpCredentials(service_account_info=service_account_info),
            region="us-central1",
            timeout=604800,
        )
        job_name = config.job_name
        assert len(job_name) <= 63
        base_part = job_name[:-8]  # 7 UUID + 1 hyphen
        assert len(base_part) == 55  # 63 - 1 - 7

    def test_populate_timeout(self, cloud_run_worker_v2_job_config):
        cloud_run_worker_v2_job_config._populate_timeout()

        assert (
            cloud_run_worker_v2_job_config.job_body["template"]["template"]["timeout"]
            == "604800s"
        )

    def test_populate_env(self, cloud_run_worker_v2_job_config):
        cloud_run_worker_v2_job_config._populate_env()

        assert cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"] == [
            {"name": "ENV1", "value": "VALUE1"},
            {"name": "ENV2", "value": "VALUE2"},
        ]

    def test_populate_env_with_secrets(self, cloud_run_worker_v2_job_config):
        cloud_run_worker_v2_job_config.env_from_secrets = {
            "SECRET_ENV1": SecretKeySelector(secret="SECRET1", version="latest")
        }
        cloud_run_worker_v2_job_config._populate_env()

        assert cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"] == [
            {"name": "ENV1", "value": "VALUE1"},
            {"name": "ENV2", "value": "VALUE2"},
            {
                "name": "SECRET_ENV1",
                "valueSource": {
                    "secretKeyRef": {"secret": "SECRET1", "version": "latest"}
                },
            },
        ]

    def test_populate_env_with_existing_envs(self, cloud_run_worker_v2_job_config):
        cloud_run_worker_v2_job_config.job_body["template"]["template"]["containers"][
            0
        ]["env"] = [{"name": "ENV0", "value": "VALUE0"}]
        cloud_run_worker_v2_job_config.env_from_secrets = {
            "SECRET_ENV1": SecretKeySelector(secret="SECRET1", version="latest")
        }
        cloud_run_worker_v2_job_config._populate_env()

        assert cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"] == [
            {"name": "ENV0", "value": "VALUE0"},
            {"name": "ENV1", "value": "VALUE1"},
            {"name": "ENV2", "value": "VALUE2"},
            {
                "name": "SECRET_ENV1",
                "valueSource": {
                    "secretKeyRef": {"secret": "SECRET1", "version": "latest"}
                },
            },
        ]

    def test_populate_image_if_not_present(self, cloud_run_worker_v2_job_config):
        cloud_run_worker_v2_job_config._populate_image_if_not_present()

        assert (
            cloud_run_worker_v2_job_config.job_body["template"]["template"][
                "containers"
            ][0]["image"]
            == f"docker.io/{get_prefect_image_name()}"
        )

    def test_populate_or_format_command(self, cloud_run_worker_v2_job_config):
        cloud_run_worker_v2_job_config._populate_or_format_command()

        assert cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["command"] == ["prefect", "flow-run", "execute"]

    def test_command_formats_correctly_for_logging(
        self, cloud_run_worker_v2_job_config
    ):
        """
        Regression test for command formatting in log messages.

        Previously, the code used `" ".join(configuration.command)` where
        `configuration.command` was a string. This caused each character to be
        joined with spaces, producing "p r e f e c t   f l o w - r u n   e x e c u t e"
        instead of "prefect flow-run execute".

        The fix uses the command list from job_body which is properly formatted.
        """
        cloud_run_worker_v2_job_config._populate_or_format_command()

        command_list = cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0].get("command", [])
        command_str = (
            " ".join(command_list) if command_list else "default container command"
        )

        assert command_str == "prefect flow-run execute"
        assert "p r e f e c t" not in command_str

    def test_format_args_if_present(self, cloud_run_worker_v2_job_config):
        cloud_run_worker_v2_job_config._format_args_if_present()

        assert cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["args"] == ["-m", "prefect.engine"]

    @pytest.mark.parametrize("vpc_access", [{"connector": None}, {}, None])
    def test_remove_vpc_access_if_connector_unset(
        self, cloud_run_worker_v2_job_config, vpc_access
    ):
        cloud_run_worker_v2_job_config.job_body["template"]["template"]["vpcAccess"] = (
            vpc_access
        )

        cloud_run_worker_v2_job_config._remove_vpc_access_if_unset()

        assert (
            "vpcAccess"
            not in cloud_run_worker_v2_job_config.job_body["template"]["template"]
        )

    def test_remove_vpc_access_originally_not_present(
        self, cloud_run_worker_v2_job_config
    ):
        cloud_run_worker_v2_job_config.job_body["template"]["template"].pop("vpcAccess")

        cloud_run_worker_v2_job_config._remove_vpc_access_if_unset()

        assert (
            "vpcAccess"
            not in cloud_run_worker_v2_job_config.job_body["template"]["template"]
        )

    def test_vpc_access_left_alone_if_connector_set(
        self, cloud_run_worker_v2_job_config
    ):
        cloud_run_worker_v2_job_config.job_body["template"]["template"]["vpcAccess"][
            "connector"
        ] = "projects/my_project/locations/us-central1/connectors/my-connector"

        cloud_run_worker_v2_job_config._remove_vpc_access_if_unset()

        assert cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "vpcAccess"
        ] == {
            "connector": "projects/my_project/locations/us-central1/connectors/my-connector"  # noqa E501
        }

    def test_vpc_access_left_alone_if_network_config_set(
        self, cloud_run_worker_v2_job_config
    ):
        cloud_run_worker_v2_job_config.job_body["template"]["template"]["vpcAccess"][
            "networkInterfaces"
        ] = [{"network": "projects/my_project/global/networks/my-network"}]

        cloud_run_worker_v2_job_config._remove_vpc_access_if_unset()

        assert cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "vpcAccess"
        ] == {
            "connector": None,
            "networkInterfaces": [
                {"network": "projects/my_project/global/networks/my-network"}
            ],
        }

    def test_configure_cloudsql_volumes_no_instances(
        self, cloud_run_worker_v2_job_config
    ):
        cloud_run_worker_v2_job_config.cloudsql_instances = []
        cloud_run_worker_v2_job_config._configure_cloudsql_volumes()

        template = cloud_run_worker_v2_job_config.job_body["template"]["template"]

        assert "volumes" not in template
        assert "volumeMounts" not in template["containers"][0]

    def test_configure_cloudsql_volumes_preserves_existing_volumes(
        self, cloud_run_worker_v2_job_config
    ):
        template = cloud_run_worker_v2_job_config.job_body["template"]["template"]
        template["volumes"] = [{"name": "existing-volume", "emptyDir": {}}]
        template["containers"][0]["volumeMounts"] = [
            {"name": "existing-volume", "mountPath": "/existing"}
        ]

        cloud_run_worker_v2_job_config.cloudsql_instances = ["project:region:instance1"]
        cloud_run_worker_v2_job_config._configure_cloudsql_volumes()

        assert len(template["volumes"]) == 2
        assert template["volumes"][0] == {"name": "existing-volume", "emptyDir": {}}
        assert template["volumes"][1] == {
            "name": "cloudsql",
            "cloudSqlInstance": {"instances": ["project:region:instance1"]},
        }

        assert len(template["containers"][0]["volumeMounts"]) == 2
        assert template["containers"][0]["volumeMounts"][0] == {
            "name": "existing-volume",
            "mountPath": "/existing",
        }
        assert template["containers"][0]["volumeMounts"][1] == {
            "name": "cloudsql",
            "mountPath": "/cloudsql",
        }

    def test_prepare_for_flow_run_configures_cloudsql(
        self, cloud_run_worker_v2_job_config
    ):
        cloud_run_worker_v2_job_config.cloudsql_instances = ["project:region:instance1"]

        class MockFlowRun:
            id = "test-id"
            name = "test-run"

            def model_dump(self, mode: str = "python") -> dict:
                return {"id": self.id, "name": self.name}

        cloud_run_worker_v2_job_config.prepare_for_flow_run(
            flow_run=MockFlowRun(), deployment=None, flow=None
        )

        template = cloud_run_worker_v2_job_config.job_body["template"]["template"]

        assert any(
            vol["name"] == "cloudsql"
            and vol["cloudSqlInstance"]["instances"] == ["project:region:instance1"]
            for vol in template["volumes"]
        )
        assert any(
            mount["name"] == "cloudsql" and mount["mountPath"] == "/cloudsql"
            for mount in template["containers"][0]["volumeMounts"]
        )

    def test_populate_env_with_prefect_api_key_secret(
        self, cloud_run_worker_v2_job_config
    ):
        cloud_run_worker_v2_job_config.prefect_api_key_secret = SecretKeySelector(
            secret="prefect-api-key", version="latest"
        )
        cloud_run_worker_v2_job_config._populate_env()

        env_vars = cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"]

        assert {"name": "ENV1", "value": "VALUE1"} in env_vars
        assert {"name": "ENV2", "value": "VALUE2"} in env_vars
        assert {
            "name": "PREFECT_API_KEY",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-api-key", "version": "latest"}
            },
        } in env_vars

    def test_populate_env_with_prefect_api_auth_string_secret(
        self, cloud_run_worker_v2_job_config
    ):
        cloud_run_worker_v2_job_config.prefect_api_auth_string_secret = (
            SecretKeySelector(secret="prefect-auth-string", version="latest")
        )
        cloud_run_worker_v2_job_config._populate_env()

        env_vars = cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"]

        assert {"name": "ENV1", "value": "VALUE1"} in env_vars
        assert {"name": "ENV2", "value": "VALUE2"} in env_vars
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-auth-string", "version": "latest"}
            },
        } in env_vars

    def test_populate_env_with_both_prefect_secrets(
        self, cloud_run_worker_v2_job_config
    ):
        cloud_run_worker_v2_job_config.prefect_api_key_secret = SecretKeySelector(
            secret="prefect-api-key", version="latest"
        )
        cloud_run_worker_v2_job_config.prefect_api_auth_string_secret = (
            SecretKeySelector(secret="prefect-auth-string", version="latest")
        )
        cloud_run_worker_v2_job_config._populate_env()

        env_vars = cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"]

        assert {"name": "ENV1", "value": "VALUE1"} in env_vars
        assert {"name": "ENV2", "value": "VALUE2"} in env_vars
        assert {
            "name": "PREFECT_API_KEY",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-api-key", "version": "latest"}
            },
        } in env_vars
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-auth-string", "version": "latest"}
            },
        } in env_vars

    def test_populate_env_with_all_secret_types(self, cloud_run_worker_v2_job_config):
        cloud_run_worker_v2_job_config.env_from_secrets = {
            "SECRET_ENV1": SecretKeySelector(secret="SECRET1", version="latest")
        }
        cloud_run_worker_v2_job_config.prefect_api_key_secret = SecretKeySelector(
            secret="prefect-api-key", version="latest"
        )
        cloud_run_worker_v2_job_config.prefect_api_auth_string_secret = (
            SecretKeySelector(secret="prefect-auth-string", version="latest")
        )
        cloud_run_worker_v2_job_config._populate_env()

        env_vars = cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"]

        assert {"name": "ENV1", "value": "VALUE1"} in env_vars
        assert {"name": "ENV2", "value": "VALUE2"} in env_vars
        assert {
            "name": "SECRET_ENV1",
            "valueSource": {"secretKeyRef": {"secret": "SECRET1", "version": "latest"}},
        } in env_vars
        assert {
            "name": "PREFECT_API_KEY",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-api-key", "version": "latest"}
            },
        } in env_vars
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-auth-string", "version": "latest"}
            },
        } in env_vars

    def test_prepare_for_flow_run_populates_labels(
        self, cloud_run_worker_v2_job_config
    ):
        class MockFlowRun:
            id = "test-id"
            name = "test-run"

            def model_dump(self, mode: str = "python") -> dict:
                return {"id": self.id, "name": self.name}

        cloud_run_worker_v2_job_config.prepare_for_flow_run(
            flow_run=MockFlowRun(), deployment=None, flow=None
        )

        labels = cloud_run_worker_v2_job_config.job_body["labels"]
        assert "prefect-io-flow-run-id" in labels
        assert labels["prefect-io-flow-run-id"] == "test-id"
        assert "prefect-io-flow-run-name" in labels
        assert labels["prefect-io-flow-run-name"] == "test-run"
        assert "prefect-io-version" in labels
        # Execution template also gets labels
        exec_labels = cloud_run_worker_v2_job_config.job_body["template"]["labels"]
        assert exec_labels == labels

    def test_populate_labels_preserves_existing(self, cloud_run_worker_v2_job_config):
        cloud_run_worker_v2_job_config.job_body["labels"] = {
            "my-custom-label": "my-value"
        }
        cloud_run_worker_v2_job_config.labels = {
            "prefect.io/flow-run-id": "abc-123",
        }

        cloud_run_worker_v2_job_config._populate_labels()

        labels = cloud_run_worker_v2_job_config.job_body["labels"]
        assert labels["my-custom-label"] == "my-value"
        assert labels["prefect-io-flow-run-id"] == "abc-123"

    def test_populate_labels_existing_take_precedence(
        self, cloud_run_worker_v2_job_config
    ):
        cloud_run_worker_v2_job_config.job_body["labels"] = {
            "prefect-io-flow-run-id": "override"
        }
        cloud_run_worker_v2_job_config.labels = {
            "prefect.io/flow-run-id": "from-prefect",
        }

        cloud_run_worker_v2_job_config._populate_labels()

        labels = cloud_run_worker_v2_job_config.job_body["labels"]
        assert labels["prefect-io-flow-run-id"] == "override"

    def test_populate_labels_replaces_stale_on_re_prepare(
        self, cloud_run_worker_v2_job_config
    ):
        """Labels from a previous prepare call should be replaced, not preserved."""
        cloud_run_worker_v2_job_config.job_body["labels"] = {
            "my-custom-label": "keep-me"
        }

        # First prepare
        cloud_run_worker_v2_job_config.labels = {
            "prefect.io/flow-run-id": "run-1",
        }
        cloud_run_worker_v2_job_config._populate_labels()
        assert (
            cloud_run_worker_v2_job_config.job_body["labels"]["prefect-io-flow-run-id"]
            == "run-1"
        )

        # Second prepare with new run
        cloud_run_worker_v2_job_config.labels = {
            "prefect.io/flow-run-id": "run-2",
        }
        cloud_run_worker_v2_job_config._populate_labels()

        labels = cloud_run_worker_v2_job_config.job_body["labels"]
        assert labels["prefect-io-flow-run-id"] == "run-2"
        assert labels["my-custom-label"] == "keep-me"

    def test_populate_labels_preserves_existing_exec_template_labels(
        self, cloud_run_worker_v2_job_config
    ):
        """Labels already on the execution template are not overwritten."""
        cloud_run_worker_v2_job_config.job_body.setdefault("template", {})["labels"] = {
            "exec-only-label": "keep-me"
        }
        cloud_run_worker_v2_job_config.labels = {
            "prefect.io/flow-run-id": "abc-123",
        }

        cloud_run_worker_v2_job_config._populate_labels()

        exec_labels = cloud_run_worker_v2_job_config.job_body["template"]["labels"]
        assert exec_labels["exec-only-label"] == "keep-me"
        assert exec_labels["prefect-io-flow-run-id"] == "abc-123"

    def test_exec_template_labels_capped_at_64(self, cloud_run_worker_v2_job_config):
        """Execution-template labels must not exceed the 64-label limit."""
        cloud_run_worker_v2_job_config.job_body.setdefault("template", {})["labels"] = {
            f"exec-{i}": "v" for i in range(60)
        }
        cloud_run_worker_v2_job_config.labels = {
            f"prefect.io/label-{i}": "v" for i in range(10)
        }

        cloud_run_worker_v2_job_config._populate_labels()

        exec_labels = cloud_run_worker_v2_job_config.job_body["template"]["labels"]
        assert len(exec_labels) <= 64
        # All 60 existing exec labels are preserved
        for i in range(60):
            assert f"exec-{i}" in exec_labels

    def test_exec_template_stale_labels_replaced_on_re_prepare(
        self, cloud_run_worker_v2_job_config
    ):
        """Stale Prefect labels on the exec template are replaced on re-prepare."""
        cloud_run_worker_v2_job_config.job_body.setdefault("template", {})["labels"] = {
            "exec-only": "keep"
        }

        cloud_run_worker_v2_job_config.labels = {
            "prefect.io/flow-run-id": "run-1",
        }
        cloud_run_worker_v2_job_config._populate_labels()

        cloud_run_worker_v2_job_config.labels = {
            "prefect.io/flow-run-id": "run-2",
        }
        cloud_run_worker_v2_job_config._populate_labels()

        exec_labels = cloud_run_worker_v2_job_config.job_body["template"]["labels"]
        assert exec_labels["prefect-io-flow-run-id"] == "run-2"
        assert exec_labels["exec-only"] == "keep"

    def test_user_exec_label_colliding_with_prefect_key_survives_re_prepare(
        self, cloud_run_worker_v2_job_config
    ):
        """A user-defined exec-template label whose key collides with a
        Prefect label must not be dropped on subsequent prepares."""
        # User has a custom exec-template label that happens to use
        # a key that Prefect also injects.
        cloud_run_worker_v2_job_config.job_body.setdefault("template", {})["labels"] = {
            "prefect-io-flow-run-id": "user-override"
        }

        # First prepare — user value should win on exec template
        cloud_run_worker_v2_job_config.labels = {
            "prefect.io/flow-run-id": "run-1",
        }
        cloud_run_worker_v2_job_config._populate_labels()
        exec_labels = cloud_run_worker_v2_job_config.job_body["template"]["labels"]
        assert exec_labels["prefect-io-flow-run-id"] == "user-override"

        # Second prepare — user value should still win
        cloud_run_worker_v2_job_config.labels = {
            "prefect.io/flow-run-id": "run-2",
        }
        cloud_run_worker_v2_job_config._populate_labels()
        exec_labels = cloud_run_worker_v2_job_config.job_body["template"]["labels"]
        assert exec_labels["prefect-io-flow-run-id"] == "user-override"


class TestCloudRunWorkerV2KillInfrastructure:
    """Tests for CloudRunWorkerV2.kill_infrastructure method."""

    async def test_kill_infrastructure_deletes_job(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        """Test that kill_infrastructure successfully deletes a Cloud Run V2 job."""
        job_name = "test-job-name"

        mock_client = MagicMock()
        mock_client.__enter__ = lambda self: mock_client
        mock_client.__exit__ = lambda self, *args: None

        with mock.patch.object(
            CloudRunWorkerV2, "_get_client", return_value=mock_client
        ):
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.delete"
            ) as mock_delete:
                async with CloudRunWorkerV2("my-work-pool") as worker:
                    await worker.kill_infrastructure(
                        infrastructure_pid=job_name,
                        configuration=cloud_run_worker_v2_job_config,
                        grace_seconds=30,
                    )

                mock_delete.assert_called_once_with(
                    cr_client=mock_client,
                    project=cloud_run_worker_v2_job_config.project,
                    location=cloud_run_worker_v2_job_config.region,
                    job_name=job_name,
                )

    async def test_kill_infrastructure_raises_not_found(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        """Test that kill_infrastructure raises InfrastructureNotFound for missing job."""
        job_name = "nonexistent-job"

        mock_client = MagicMock()
        mock_client.__enter__ = lambda self: mock_client
        mock_client.__exit__ = lambda self, *args: None

        # Create a proper mock response with status attribute
        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_http_error = HttpError(resp=mock_resp, content=b"Not found")

        with mock.patch.object(
            CloudRunWorkerV2, "_get_client", return_value=mock_client
        ):
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.delete",
                side_effect=mock_http_error,
            ):
                async with CloudRunWorkerV2("my-work-pool") as worker:
                    with pytest.raises(InfrastructureNotFound):
                        await worker.kill_infrastructure(
                            infrastructure_pid=job_name,
                            configuration=cloud_run_worker_v2_job_config,
                            grace_seconds=30,
                        )

    def test_watch_job_execution_raises_not_found_on_404(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        """Test that _watch_job_execution raises InfrastructureNotFound when execution is deleted."""
        mock_client = MagicMock()

        # Create a mock execution that is initially running
        mock_execution = MagicMock(spec=ExecutionV2)
        mock_execution.is_running.return_value = True
        mock_execution.name = "projects/test/locations/us-central1/jobs/test-job/executions/test-execution"

        # Create a 404 error for when we try to get the execution
        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_http_error = HttpError(resp=mock_resp, content=b"Execution not found")

        mock_logger = MagicMock(spec=PrefectLogAdapter)

        with mock.patch.object(ExecutionV2, "get", side_effect=mock_http_error):
            with pytest.raises(InfrastructureNotFound) as exc_info:
                CloudRunWorkerV2._watch_job_execution(
                    cr_client=mock_client,
                    configuration=cloud_run_worker_v2_job_config,
                    execution=mock_execution,
                    poll_interval=0,
                    logger=mock_logger,
                )

            assert "was deleted" in str(exc_info.value)

    def test_watch_job_execution_and_get_result_handles_deleted_execution(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        """Test that _watch_job_execution_and_get_result handles InfrastructureNotFound gracefully."""
        mock_client = MagicMock()

        # Create a mock execution
        mock_execution = MagicMock(spec=ExecutionV2)
        mock_execution.is_running.return_value = True
        mock_execution.name = "projects/test/locations/us-central1/jobs/test-job/executions/test-execution"

        # Create a mock logger
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        worker = CloudRunWorkerV2("my-work-pool")

        # Mock _watch_job_execution on the instance to raise InfrastructureNotFound
        with mock.patch.object(
            worker,
            "_watch_job_execution",
            side_effect=InfrastructureNotFound("Execution was deleted"),
        ):
            result = worker._watch_job_execution_and_get_result(
                cr_client=mock_client,
                configuration=cloud_run_worker_v2_job_config,
                execution=mock_execution,
                logger=mock_logger,
                poll_interval=0,
            )

            # Should return a result with status_code=-1, not raise an exception
            assert isinstance(result, CloudRunWorkerV2Result)
            assert result.status_code == -1

            # Should log an info message, not an error/critical
            mock_logger.info.assert_called_once()
            assert "was deleted" in mock_logger.info.call_args[0][0]

    def test_watch_job_execution_reraises_non_transient_errors(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        """Test that _watch_job_execution re-raises non-transient HTTP errors."""
        mock_client = MagicMock()

        mock_execution = MagicMock(spec=ExecutionV2)
        mock_execution.is_running.return_value = True
        mock_execution.name = "projects/test/locations/us-central1/jobs/test-job/executions/test-execution"

        # 400 is not transient, so it should bubble up immediately
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_http_error = HttpError(resp=mock_resp, content=b"Bad request")

        mock_logger = MagicMock(spec=PrefectLogAdapter)

        with mock.patch.object(ExecutionV2, "get", side_effect=mock_http_error):
            with pytest.raises(HttpError) as exc_info:
                CloudRunWorkerV2._watch_job_execution(
                    cr_client=mock_client,
                    configuration=cloud_run_worker_v2_job_config,
                    execution=mock_execution,
                    poll_interval=0,
                    logger=mock_logger,
                )

            assert exc_info.value.status_code == 400

    def test_watch_job_execution_retries_transient_error_then_succeeds(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        """Regression test: a transient 503 during polling should be retried, not crash the flow run."""
        mock_client = MagicMock()

        running_execution = MagicMock(spec=ExecutionV2)
        running_execution.is_running.return_value = True
        running_execution.name = "projects/test/locations/us-central1/jobs/test-job/executions/test-execution"

        completed_execution = MagicMock(spec=ExecutionV2)
        completed_execution.is_running.return_value = False
        completed_execution.name = running_execution.name

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        mock_logger = MagicMock(spec=PrefectLogAdapter)

        with (
            mock.patch.object(
                ExecutionV2, "get", side_effect=[transient_error, completed_execution]
            ),
            mock.patch("prefect_gcp.workers.cloud_run_v2.time.sleep"),
        ):
            result = CloudRunWorkerV2._watch_job_execution(
                cr_client=mock_client,
                configuration=cloud_run_worker_v2_job_config,
                execution=running_execution,
                poll_interval=0,
                logger=mock_logger,
            )

        assert result is completed_execution
        mock_logger.warning.assert_called_once()
        assert "503" in mock_logger.warning.call_args[0][1:].__repr__()


class TestCloudRunWorkerV2ExecutionPollRetries:
    def test_watch_job_execution_404_not_retried(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        """A 404 should immediately raise InfrastructureNotFound, not be retried."""
        mock_client = MagicMock()

        mock_execution = MagicMock(spec=ExecutionV2)
        mock_execution.is_running.return_value = True
        mock_execution.name = "projects/test/locations/us-central1/jobs/test-job/executions/test-execution"

        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_http_error = HttpError(resp=mock_resp, content=b"Execution not found")

        mock_logger = MagicMock(spec=PrefectLogAdapter)

        with mock.patch.object(
            ExecutionV2, "get", side_effect=mock_http_error
        ) as mock_get:
            with pytest.raises(InfrastructureNotFound):
                CloudRunWorkerV2._watch_job_execution(
                    cr_client=mock_client,
                    configuration=cloud_run_worker_v2_job_config,
                    execution=mock_execution,
                    poll_interval=0,
                    logger=mock_logger,
                )

            # 404 is not transient, so get should only be called once
            assert mock_get.call_count == 1


class TestCloudRunWorkerV2CreateJobRetries:
    def test_create_job_retries_on_transient_error_then_succeeds(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.create",
            side_effect=[transient_error, None],
        ) as mock_create:
            with mock.patch.object(worker, "_wait_for_job_creation"):
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.time.sleep"
                ) as mock_sleep:
                    worker._create_job_and_wait_for_registration(
                        configuration=cloud_run_worker_v2_job_config,
                        cr_client=mock_client,
                        logger=mock_logger,
                    )

        assert mock_create.call_count == 2
        mock_sleep.assert_called_once()
        mock_logger.warning.assert_called_once()

    def test_create_job_does_not_retry_on_non_transient_error(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 400
        non_transient_error = HttpError(resp=mock_resp, content=b"Bad request")

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.create",
            side_effect=non_transient_error,
        ) as mock_create:
            with mock.patch.object(worker, "_wait_for_job_creation"):
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.time.sleep"
                ) as mock_sleep:
                    with pytest.raises(HttpError):
                        worker._create_job_and_wait_for_registration(
                            configuration=cloud_run_worker_v2_job_config,
                            cr_client=mock_client,
                            logger=mock_logger,
                        )

        assert mock_create.call_count == 1
        mock_sleep.assert_not_called()

    def test_create_job_retries_until_max_attempts_then_raises(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.create",
            side_effect=[transient_error, transient_error, transient_error],
        ) as mock_create:
            with mock.patch.object(worker, "_wait_for_job_creation"):
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.time.sleep"
                ) as mock_sleep:
                    with pytest.raises(HttpError):
                        worker._create_job_and_wait_for_registration(
                            configuration=cloud_run_worker_v2_job_config,
                            cr_client=mock_client,
                            logger=mock_logger,
                        )

        assert mock_create.call_count == 3
        assert mock_sleep.call_count == 2


class TestCloudRunWorkerV2CreateJobRetriesFromEnv:
    def test_create_job_retries_use_custom_max_attempts_from_env(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        with mock.patch.dict(
            "os.environ",
            {
                "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_CREATE_JOB_MAX_ATTEMPTS": "5",
            },
        ):
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.create",
                side_effect=[transient_error] * 5,
            ) as mock_create:
                with mock.patch.object(worker, "_wait_for_job_creation"):
                    with mock.patch("prefect_gcp.workers.cloud_run_v2.time.sleep"):
                        with pytest.raises(HttpError):
                            worker._create_job_and_wait_for_registration(
                                configuration=cloud_run_worker_v2_job_config,
                                cr_client=mock_client,
                                logger=mock_logger,
                            )

        assert mock_create.call_count == 5

    def test_create_job_retries_use_custom_backoff_from_env(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        with mock.patch.dict(
            "os.environ",
            {
                "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_CREATE_JOB_INITIAL_DELAY_SECONDS": "2.5",
                "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_CREATE_JOB_MAX_DELAY_SECONDS": "20.0",
            },
        ):
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.create",
                side_effect=[transient_error, transient_error, transient_error],
            ):
                with mock.patch.object(worker, "_wait_for_job_creation"):
                    with mock.patch(
                        "prefect_gcp.workers.cloud_run_v2.time.sleep"
                    ) as mock_sleep:
                        with pytest.raises(HttpError):
                            worker._create_job_and_wait_for_registration(
                                configuration=cloud_run_worker_v2_job_config,
                                cr_client=mock_client,
                                logger=mock_logger,
                            )

        # wait_exponential_jitter: min(initial * 2 ** (n-1) + uniform(0, 1), max).
        # initial=2.5, max=20.0 -> attempt 1 in [2.5, 3.5], attempt 2 in [5.0, 6.0].
        sleeps = [call.args[0] for call in mock_sleep.call_args_list]
        assert len(sleeps) == 2
        assert 2.5 <= sleeps[0] <= 3.5
        assert 5.0 <= sleeps[1] <= 6.0


class TestCloudRunWorkerV2ReadinessPollRetries:
    """Transient HTTP errors during the _wait_for_job_creation readiness poll
    should be retried rather than crashing the flow run."""

    def _make_ready_job(self):
        job = MagicMock()
        job.is_ready.return_value = True
        return job

    def _make_not_ready_job(self):
        job = MagicMock()
        job.is_ready.return_value = False
        job.get_ready_condition.return_value = "waiting"
        return job

    def test_readiness_poll_retries_transient_error_then_succeeds(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        ready_job = self._make_ready_job()

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            side_effect=[transient_error, ready_job],
        ) as mock_get:
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.time.sleep"
            ) as mock_sleep:
                CloudRunWorkerV2._wait_for_job_creation(
                    cr_client=mock_client,
                    configuration=cloud_run_worker_v2_job_config,
                    logger=mock_logger,
                )

        assert mock_get.call_count == 2
        mock_sleep.assert_called_once()
        mock_logger.warning.assert_called_once()

    def test_readiness_poll_does_not_retry_non_transient_error(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 400
        non_transient_error = HttpError(resp=mock_resp, content=b"Bad request")

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            side_effect=non_transient_error,
        ) as mock_get:
            with mock.patch("prefect_gcp.workers.cloud_run_v2.time.sleep"):
                with pytest.raises(HttpError):
                    CloudRunWorkerV2._wait_for_job_creation(
                        cr_client=mock_client,
                        configuration=cloud_run_worker_v2_job_config,
                        logger=mock_logger,
                    )

        assert mock_get.call_count == 1

    def test_readiness_poll_retries_until_max_attempts_then_raises(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            side_effect=[transient_error, transient_error, transient_error],
        ) as mock_get:
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.time.sleep"
            ) as mock_sleep:
                with pytest.raises(HttpError):
                    CloudRunWorkerV2._wait_for_job_creation(
                        cr_client=mock_client,
                        configuration=cloud_run_worker_v2_job_config,
                        logger=mock_logger,
                    )

        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

    def test_readiness_poll_retries_transient_error_during_polling_loop(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        """A transient error in a later poll iteration is also retried."""
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        not_ready_job = self._make_not_ready_job()
        ready_job = self._make_ready_job()

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            side_effect=[not_ready_job, transient_error, ready_job],
        ) as mock_get:
            with mock.patch("prefect_gcp.workers.cloud_run_v2.time.sleep"):
                CloudRunWorkerV2._wait_for_job_creation(
                    cr_client=mock_client,
                    configuration=cloud_run_worker_v2_job_config,
                    logger=mock_logger,
                )

        assert mock_get.call_count == 3

    def test_readiness_poll_retries_429_and_500(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp_429 = MagicMock()
        mock_resp_429.status = 429
        error_429 = HttpError(resp=mock_resp_429, content=b"Too many requests")

        mock_resp_500 = MagicMock()
        mock_resp_500.status = 500
        error_500 = HttpError(resp=mock_resp_500, content=b"Internal server error")

        ready_job = self._make_ready_job()

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            side_effect=[error_429, error_500, ready_job],
        ) as mock_get:
            with mock.patch("prefect_gcp.workers.cloud_run_v2.time.sleep"):
                CloudRunWorkerV2._wait_for_job_creation(
                    cr_client=mock_client,
                    configuration=cloud_run_worker_v2_job_config,
                    logger=mock_logger,
                )

        assert mock_get.call_count == 3


class TestCloudRunWorkerV2SubmitJobRetries:
    def test_submit_job_retries_on_transient_error_then_succeeds(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")
        successful_submission = {"metadata": {"name": "test-execution"}}

        with (
            mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.get",
                return_value=MagicMock(latestCreatedExecution={}),
            ),
            mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                side_effect=[transient_error, successful_submission],
            ) as mock_run,
        ):
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.ExecutionV2.get"
            ) as mock_get:
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.time.sleep"
                ) as mock_sleep:
                    result = worker._begin_job_execution(
                        cr_client=mock_client,
                        configuration=cloud_run_worker_v2_job_config,
                        logger=mock_logger,
                    )

        assert mock_run.call_count == 2
        mock_sleep.assert_called_once()
        mock_logger.warning.assert_called_once()
        assert result is mock_get.return_value

    def test_submit_job_does_not_retry_on_non_transient_error(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 400
        non_transient_error = HttpError(resp=mock_resp, content=b"Bad request")

        with (
            mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.get",
                return_value=MagicMock(latestCreatedExecution={}),
            ),
            mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                side_effect=non_transient_error,
            ) as mock_run,
        ):
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.time.sleep"
            ) as mock_sleep:
                with pytest.raises(HttpError):
                    worker._begin_job_execution(
                        cr_client=mock_client,
                        configuration=cloud_run_worker_v2_job_config,
                        logger=mock_logger,
                    )

        assert mock_run.call_count == 1
        mock_sleep.assert_not_called()

    def test_submit_job_retries_until_max_attempts_then_raises(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        with (
            mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.get",
                return_value=MagicMock(latestCreatedExecution={}),
            ),
            mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                side_effect=[transient_error, transient_error, transient_error],
            ) as mock_run,
        ):
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.time.sleep"
            ) as mock_sleep:
                with pytest.raises(HttpError):
                    worker._begin_job_execution(
                        cr_client=mock_client,
                        configuration=cloud_run_worker_v2_job_config,
                        logger=mock_logger,
                    )

        assert mock_run.call_count == 3
        assert mock_sleep.call_count == 2


class TestCloudRunWorkerV2SubmitJobRetriesFromEnv:
    def test_submit_job_retries_use_custom_max_attempts_from_env(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        with mock.patch.dict(
            "os.environ",
            {
                "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_SUBMIT_JOB_MAX_ATTEMPTS": "5",
            },
        ):
            with (
                mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.JobV2.get",
                    return_value=MagicMock(latestCreatedExecution={}),
                ),
                mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                    side_effect=[transient_error] * 5,
                ) as mock_run,
            ):
                with mock.patch("prefect_gcp.workers.cloud_run_v2.time.sleep"):
                    with pytest.raises(HttpError):
                        worker._begin_job_execution(
                            cr_client=mock_client,
                            configuration=cloud_run_worker_v2_job_config,
                            logger=mock_logger,
                        )

        assert mock_run.call_count == 5

    def test_submit_job_retries_use_custom_backoff_from_env(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        with mock.patch.dict(
            "os.environ",
            {
                "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_SUBMIT_JOB_INITIAL_DELAY_SECONDS": "2.5",
                "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_SUBMIT_JOB_MAX_DELAY_SECONDS": "20.0",
            },
        ):
            with (
                mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.JobV2.get",
                    return_value=MagicMock(latestCreatedExecution={}),
                ),
                mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                    side_effect=[transient_error, transient_error, transient_error],
                ),
            ):
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.time.sleep"
                ) as mock_sleep:
                    with pytest.raises(HttpError):
                        worker._begin_job_execution(
                            cr_client=mock_client,
                            configuration=cloud_run_worker_v2_job_config,
                            logger=mock_logger,
                        )

        # wait_exponential_jitter: min(initial * 2 ** (n-1) + uniform(0, 1), max).
        # initial=2.5, max=20.0 -> attempt 1 in [2.5, 3.5], attempt 2 in [5.0, 6.0].
        sleeps = [call.args[0] for call in mock_sleep.call_args_list]
        assert len(sleeps) == 2
        assert 2.5 <= sleeps[0] <= 3.5
        assert 5.0 <= sleeps[1] <= 6.0


class TestCloudRunWorkerV2SubmitJobRecovery:
    """
    Recovery from non-idempotent transient errors on jobs.run.

    `jobs.run` may return a transient 5xx *after* the server already accepted
    the submission and created an execution. A blind retry would leak a second
    execution. The worker reconciles by snapshotting the parent job's
    `latestCreatedExecution` and adopting any new execution that appears.
    """

    @staticmethod
    def _job_with_execution(execution_name):
        job = MagicMock()
        job.latestCreatedExecution = (
            {"name": execution_name} if execution_name is not None else {}
        )
        return job

    def test_adopts_new_execution_when_latest_created_advances(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        baseline_name = "projects/p/locations/l/jobs/j/executions/exec-baseline"
        new_name = "projects/p/locations/l/jobs/j/executions/exec-new"

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            side_effect=[
                self._job_with_execution(baseline_name),
                self._job_with_execution(new_name),
            ],
        ) as mock_job_get:
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                side_effect=transient_error,
            ) as mock_run:
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.ExecutionV2.get"
                ) as mock_exec_get:
                    with mock.patch(
                        "prefect_gcp.workers.cloud_run_v2.time.sleep"
                    ) as mock_sleep:
                        result = worker._begin_job_execution(
                            cr_client=mock_client,
                            configuration=cloud_run_worker_v2_job_config,
                            logger=mock_logger,
                        )

        assert mock_run.call_count == 1
        assert mock_job_get.call_count == 2
        mock_sleep.assert_not_called()
        mock_exec_get.assert_called_once()
        assert mock_exec_get.call_args.kwargs["execution_id"] == new_name
        assert result is mock_exec_get.return_value

        warning_messages = [call.args[0] for call in mock_logger.warning.call_args_list]
        assert any("duplicate run" in msg for msg in warning_messages)

    def test_retries_normally_when_latest_created_unchanged(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")
        successful_submission = {"metadata": {"name": "test-execution"}}

        baseline_name = "projects/p/locations/l/jobs/j/executions/exec-baseline"

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            return_value=self._job_with_execution(baseline_name),
        ) as mock_job_get:
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                side_effect=[transient_error, successful_submission],
            ) as mock_run:
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.ExecutionV2.get"
                ) as mock_exec_get:
                    with mock.patch(
                        "prefect_gcp.workers.cloud_run_v2.time.sleep"
                    ) as mock_sleep:
                        result = worker._begin_job_execution(
                            cr_client=mock_client,
                            configuration=cloud_run_worker_v2_job_config,
                            logger=mock_logger,
                        )

        assert mock_run.call_count == 2
        assert mock_job_get.call_count == 2
        mock_sleep.assert_called_once()
        mock_exec_get.assert_called_once()
        assert mock_exec_get.call_args.kwargs["execution_id"] == "test-execution"
        assert result is mock_exec_get.return_value

        warning_messages = [call.args[0] for call in mock_logger.warning.call_args_list]
        assert not any("duplicate run" in msg for msg in warning_messages)

    @mock.patch.dict(
        "os.environ",
        {
            "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_API_READ_RETRY_MAX_ATTEMPTS": "1"
        },
    )
    def test_falls_back_when_baseline_lookup_raises(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        # API_READ_RETRY_MAX_ATTEMPTS=1 caps every _read_with_retry call (the
        # baseline snapshot and the post-submit fetch alike) to a single attempt.
        # Only the baseline read is made to fail here: one 503 makes it give up
        # and fall back to None, then submission retries. The post-submit fetch
        # never fails in this test, so the shared cap is observable only on the
        # baseline lookup.
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")
        lookup_error = HttpError(resp=mock_resp, content=b"Service unavailable")
        successful_submission = {"metadata": {"name": "test-execution"}}

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            side_effect=[lookup_error, self._job_with_execution(None)],
        ):
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                side_effect=[transient_error, successful_submission],
            ) as mock_run:
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.ExecutionV2.get"
                ) as mock_exec_get:
                    with mock.patch("prefect_gcp.workers.cloud_run_v2.time.sleep"):
                        result = worker._begin_job_execution(
                            cr_client=mock_client,
                            configuration=cloud_run_worker_v2_job_config,
                            logger=mock_logger,
                        )

        assert mock_run.call_count == 2
        assert mock_exec_get.call_args.kwargs["execution_id"] == "test-execution"
        assert result is mock_exec_get.return_value
        mock_logger.debug.assert_called()
        warning_messages = [call.args[0] for call in mock_logger.warning.call_args_list]
        assert not any("duplicate run" in msg for msg in warning_messages)

    @mock.patch.dict(
        "os.environ",
        {
            "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_API_READ_RETRY_MAX_ATTEMPTS": "2"
        },
    )
    def test_fails_fast_after_recovery_lookup_retries_exhausted(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        # The recovery lookup now retries transient errors. When it still cannot
        # read the job after exhausting its attempts, the worker fails fast on the
        # original submission error instead of risking a duplicate run.
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")
        lookup_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        baseline_name = "projects/p/locations/l/jobs/j/executions/exec-baseline"

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            side_effect=[
                self._job_with_execution(baseline_name),
                lookup_error,
                lookup_error,
            ],
        ) as mock_job_get:
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                side_effect=transient_error,
            ) as mock_run:
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.ExecutionV2.get"
                ) as mock_exec_get:
                    with mock.patch(
                        "prefect_gcp.workers.cloud_run_v2.time.sleep"
                    ) as mock_sleep:
                        with pytest.raises(HttpError) as exc_info:
                            worker._begin_job_execution(
                                cr_client=mock_client,
                                configuration=cloud_run_worker_v2_job_config,
                                logger=mock_logger,
                            )

        assert exc_info.value is transient_error
        assert mock_run.call_count == 1
        # baseline lookup (1) + recovery lookup retried to exhaustion (2)
        assert mock_job_get.call_count == 3
        mock_sleep.assert_called()
        mock_exec_get.assert_not_called()
        warning_messages = [call.args[0] for call in mock_logger.warning.call_args_list]
        assert any("Failing fast" in msg for msg in warning_messages)
        assert not any(
            "Using the existing execution" in msg for msg in warning_messages
        )

    def test_adopts_when_baseline_is_none_and_execution_appears(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        first_name = "projects/p/locations/l/jobs/j/executions/exec-first"

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            side_effect=[
                self._job_with_execution(None),
                self._job_with_execution(first_name),
            ],
        ):
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                side_effect=transient_error,
            ) as mock_run:
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.ExecutionV2.get"
                ) as mock_exec_get:
                    with mock.patch("prefect_gcp.workers.cloud_run_v2.time.sleep"):
                        result = worker._begin_job_execution(
                            cr_client=mock_client,
                            configuration=cloud_run_worker_v2_job_config,
                            logger=mock_logger,
                        )

        assert mock_run.call_count == 1
        assert mock_exec_get.call_args.kwargs["execution_id"] == first_name
        assert result is mock_exec_get.return_value
        warning_messages = [call.args[0] for call in mock_logger.warning.call_args_list]
        assert any("duplicate run" in msg for msg in warning_messages)

    @mock.patch.dict(
        "os.environ",
        {
            "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_API_READ_RETRY_MAX_ATTEMPTS": "2"
        },
    )
    def test_baseline_lookup_retries_transient_then_succeeds(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        # The baseline snapshot read now retries a transient error before giving up.
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")
        successful_submission = {"metadata": {"name": "test-execution"}}

        baseline_name = "projects/p/locations/l/jobs/j/executions/exec-baseline"

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            side_effect=[transient_error, self._job_with_execution(baseline_name)],
        ) as mock_job_get:
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                return_value=successful_submission,
            ) as mock_run:
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.ExecutionV2.get"
                ) as mock_exec_get:
                    with mock.patch("prefect_gcp.workers.cloud_run_v2.time.sleep"):
                        result = worker._begin_job_execution(
                            cr_client=mock_client,
                            configuration=cloud_run_worker_v2_job_config,
                            logger=mock_logger,
                        )

        # baseline get retried once (transient) before returning the job
        assert mock_job_get.call_count == 2
        assert mock_run.call_count == 1
        assert result is mock_exec_get.return_value

    @mock.patch.dict(
        "os.environ",
        {
            "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_API_READ_RETRY_MAX_ATTEMPTS": "2"
        },
    )
    def test_post_submit_fetch_retries_transient_then_succeeds(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        # A transient 503 on the post-submission ExecutionV2.get must not crash a
        # submission that already succeeded; the fetch retries instead.
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")
        successful_submission = {"metadata": {"name": "test-execution"}}
        execution = MagicMock(spec=ExecutionV2)

        baseline_name = "projects/p/locations/l/jobs/j/executions/exec-baseline"

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            return_value=self._job_with_execution(baseline_name),
        ):
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                return_value=successful_submission,
            ):
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.ExecutionV2.get",
                    side_effect=[transient_error, execution],
                ) as mock_exec_get:
                    with mock.patch("prefect_gcp.workers.cloud_run_v2.time.sleep"):
                        result = worker._begin_job_execution(
                            cr_client=mock_client,
                            configuration=cloud_run_worker_v2_job_config,
                            logger=mock_logger,
                        )

        # the post-submit fetch retried the transient error instead of crashing
        assert mock_exec_get.call_count == 2
        assert result is execution

    @mock.patch.dict(
        "os.environ",
        {
            "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_API_READ_RETRY_MAX_ATTEMPTS": "2"
        },
    )
    def test_adopts_after_recovery_lookup_retries_transient(
        self, cloud_run_worker_v2_job_config, mock_credentials
    ):
        # The recovery lookup retries a transient error, then succeeds and sees a
        # new execution already started server-side; the worker adopts it instead
        # of retrying the submission, avoiding a duplicate run.
        worker = CloudRunWorkerV2("my-work-pool")
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=PrefectLogAdapter)

        mock_resp = MagicMock()
        mock_resp.status = 503
        transient_error = HttpError(resp=mock_resp, content=b"Service unavailable")
        lookup_error = HttpError(resp=mock_resp, content=b"Service unavailable")

        baseline_name = "projects/p/locations/l/jobs/j/executions/exec-baseline"
        new_name = "projects/p/locations/l/jobs/j/executions/exec-new"

        with mock.patch(
            "prefect_gcp.workers.cloud_run_v2.JobV2.get",
            side_effect=[
                self._job_with_execution(baseline_name),
                lookup_error,
                self._job_with_execution(new_name),
            ],
        ) as mock_job_get:
            with mock.patch(
                "prefect_gcp.workers.cloud_run_v2.JobV2.run",
                side_effect=transient_error,
            ) as mock_run:
                with mock.patch(
                    "prefect_gcp.workers.cloud_run_v2.ExecutionV2.get"
                ) as mock_exec_get:
                    with mock.patch(
                        "prefect_gcp.workers.cloud_run_v2.time.sleep"
                    ) as mock_sleep:
                        result = worker._begin_job_execution(
                            cr_client=mock_client,
                            configuration=cloud_run_worker_v2_job_config,
                            logger=mock_logger,
                        )

        assert mock_run.call_count == 1
        # baseline snapshot (1) + recovery lookup retried once (2)
        assert mock_job_get.call_count == 3
        mock_sleep.assert_called()
        mock_exec_get.assert_called_once()
        assert mock_exec_get.call_args.kwargs["execution_id"] == new_name
        assert result is mock_exec_get.return_value
        warning_messages = [call.args[0] for call in mock_logger.warning.call_args_list]
        assert any("duplicate run" in msg for msg in warning_messages)


class TestCloudRunReadRetryEradication:
    def test_all_cloud_run_reads_go_through_retry_helper(self):
        """Guard against the copy-paste mistake of a bare JobV2.get / ExecutionV2.get.

        Every prior retry gap was a literal `JobV2.get(` / `ExecutionV2.get(`
        that skipped the shared helper. This lints against that specific
        regression by asserting every such call in the worker module is lexically
        under a `_read_with_retry` call. It does not defend against indirect
        calls (getattr, symbol aliasing); it catches the common forgotten-wrap
        mistake.
        """
        import ast
        import pathlib

        from prefect_gcp.workers import cloud_run_v2

        tree = ast.parse(pathlib.Path(cloud_run_v2.__file__).read_text())
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }

        def is_read_call(node):
            return (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"JobV2", "ExecutionV2"}
            )

        def under_read_helper(node):
            current = parents.get(node)
            while current is not None:
                func = getattr(current, "func", None)
                if isinstance(current, ast.Call) and (
                    (isinstance(func, ast.Name) and func.id == "_read_with_retry")
                    or (
                        isinstance(func, ast.Attribute)
                        and func.attr == "_read_with_retry"
                    )
                ):
                    return True
                current = parents.get(current)
            return False

        offenders = [
            node.lineno
            for node in ast.walk(tree)
            if is_read_call(node) and not under_read_helper(node)
        ]
        assert not offenders, (
            "JobV2.get / ExecutionV2.get must be wrapped in _read_with_retry; "
            f"bare reads found at lines {offenders}"
        )
