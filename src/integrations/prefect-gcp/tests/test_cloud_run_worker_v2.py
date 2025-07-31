import pytest
from prefect_gcp.credentials import GcpCredentials
from prefect_gcp.models.cloud_run_v2 import SecretKeySelector
from prefect_gcp.utilities import slugify_name
from prefect_gcp.workers.cloud_run_v2 import CloudRunWorkerJobV2Configuration

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
        timeout=86400,
        env={"ENV1": "VALUE1", "ENV2": "VALUE2"},
    )


@pytest.fixture
def cloud_run_worker_v2_job_config_noncompliant_name(service_account_info, job_body):
    return CloudRunWorkerJobV2Configuration(
        name="MY_JOB_NAME",
        job_body=job_body,
        credentials=GcpCredentials(service_account_info=service_account_info),
        region="us-central1",
        timeout=86400,
        env={"ENV1": "VALUE1", "ENV2": "VALUE2"},
    )


class TestCloudRunWorkerJobV2Configuration:
    def test_project(self, cloud_run_worker_v2_job_config):
        assert cloud_run_worker_v2_job_config.project == "my_project"

    def test_job_name(self, cloud_run_worker_v2_job_config):
        assert cloud_run_worker_v2_job_config.job_name[:-33] == "my-job-name"

    def test_job_name_is_slug(self, cloud_run_worker_v2_job_config_noncompliant_name):
        assert cloud_run_worker_v2_job_config_noncompliant_name.job_name[
            :-33
        ] == slugify_name("MY_JOB_NAME")

    def test_job_name_different_after_retry(self, cloud_run_worker_v2_job_config):
        job_name_1 = cloud_run_worker_v2_job_config.job_name

        cloud_run_worker_v2_job_config._job_name = None

        job_name_2 = cloud_run_worker_v2_job_config.job_name

        assert job_name_1[:-33] == job_name_2[:-33]
        assert job_name_1 != job_name_2

    def test_populate_timeout(self, cloud_run_worker_v2_job_config):
        cloud_run_worker_v2_job_config._populate_timeout()

        assert (
            cloud_run_worker_v2_job_config.job_body["template"]["template"]["timeout"]
            == "86400s"
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
