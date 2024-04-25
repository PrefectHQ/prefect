import json
import os
from pathlib import Path

import pytest
from google.cloud.aiplatform.gapic import JobServiceClient
from prefect_gcp import GcpCredentials
from prefect_gcp.credentials import ClientType

from prefect import flow, task
from prefect.blocks.core import Block


def _get_first_file_in_root():
    for path in os.listdir(os.path.expanduser("~")):
        if os.path.isfile(os.path.join(os.path.expanduser("~"), path)):
            return os.path.join("~", path)


SERVICE_ACCOUNT_FILES = [
    Path(__file__).parent.absolute() / "test_credentials.py",
]
SERVICE_ACCOUNT_FILES.append(str(SERVICE_ACCOUNT_FILES[0]))
SERVICE_ACCOUNT_FILES.append(_get_first_file_in_root())
SERVICE_ACCOUNT_FILES.append(os.path.expanduser(_get_first_file_in_root()))


@pytest.mark.parametrize("service_account_file", SERVICE_ACCOUNT_FILES)
def test_get_credentials_from_service_account_file(
    service_account_file, oauth2_credentials
):
    """Expected behavior:
    `service_account_file` is typed as a path, so we expect either input
    to be a PosixPath.

    In our conftest, we define a fixture `oauth2_credentials` that patches
    GCP's Credential methods to return its input.
    We expect our `get_credentials_from_service_account`
    method to call GCP's method with the path we pass in.
    """
    credentials = GcpCredentials(
        service_account_file=service_account_file, project="my-project"
    ).get_credentials_from_service_account()
    assert isinstance(credentials, Path)
    assert credentials == Path(service_account_file).expanduser()


def test_get_credentials_from_service_account_info(
    service_account_info, oauth2_credentials
):
    credentials = GcpCredentials(
        service_account_info=service_account_info, project="my-project"
    ).get_credentials_from_service_account()
    if isinstance(service_account_info, str):
        service_account_info = json.loads(service_account_info)
    for key, value in service_account_info.items():
        assert getattr(credentials, key) == value


def test_get_credentials_from_service_account_file_error(oauth2_credentials):
    with pytest.raises(ValueError):
        GcpCredentials(
            service_account_file="~/does_not/exist"
        ).get_credentials_from_service_account()


def test_able_to_load_credentials_from_json_string(service_account_info_json):
    gcp_credentials = GcpCredentials(service_account_info=service_account_info_json)
    assert gcp_credentials.service_account_info.get_secret_value() == {
        "project_id": "my_project",
        "token_uri": "my-token-uri",
        "client_email": "my-client-email",
        "private_key": "my-private-key",
    }


def test_raise_on_invalid_json_credentials():
    with pytest.raises(ValueError):
        GcpCredentials(service_account_info="not json")


def test_get_credentials_from_service_account_both_error(
    service_account_info, oauth2_credentials
):
    with pytest.raises(ValueError):
        GcpCredentials(
            service_account_file=SERVICE_ACCOUNT_FILES[0],
            service_account_info=service_account_info,
        ).get_credentials_from_service_account()


def test_block_initialization(service_account_info, oauth2_credentials):
    gcp_credentials = GcpCredentials(service_account_info=service_account_info)
    assert gcp_credentials.project == "my_project"


def test_block_initialization_project_specified(
    service_account_info, oauth2_credentials
):
    gcp_credentials = GcpCredentials(
        service_account_info=service_account_info, project="overrided_project"
    )
    assert gcp_credentials.project == "overrided_project"


def test_block_initialization_gcloud_cli(google_auth, oauth2_credentials):
    gcp_credentials = GcpCredentials()
    assert gcp_credentials.project == "my_project"


def test_block_initialization_metadata_server(
    google_auth_no_quota_project, oauth2_credentials
):
    gcp_credentials = GcpCredentials()
    assert gcp_credentials.project == "my_project"


@pytest.mark.parametrize("override_project", [None, "override_project"])
def test_get_cloud_storage_client(
    override_project, service_account_info, oauth2_credentials, storage_client
):
    @flow
    def test_flow():
        project = "test_project"
        credentials = GcpCredentials(
            service_account_info=service_account_info,
            project=project,
        )
        client = credentials.get_cloud_storage_client(project=override_project)
        if isinstance(service_account_info, str):
            expected = json.loads(service_account_info)
        else:
            expected = service_account_info
        for key, value in expected.items():
            assert getattr(client.credentials, key) == value

        if override_project is None:
            assert client.project == project
        else:
            assert client.project == override_project
        return True

    test_flow()


def test_get_job_service_client(service_account_info, oauth2_credentials):
    @flow
    def test_flow():
        project = "test_project"
        credentials = GcpCredentials(
            service_account_info=service_account_info,
            project=project,
        )
        client = credentials.get_job_service_client(client_options={})
        assert isinstance(client, JobServiceClient)

    test_flow()


class MockTargetConfigs(Block):
    credentials: GcpCredentials

    def get_configs(self):
        """
        Returns the dbt configs, likely used eventually for writing to profiles.yml.
        Returns:
            A configs JSON.
        """
        configs = self.credentials.dict()
        for key in Block().dict():
            configs.pop(key, None)
        for key in configs.copy():
            if key.startswith("_"):
                configs.pop(key)
            elif hasattr(configs[key], "get_secret_value"):
                configs[key] = configs[key].get_secret_value()
        return configs


class MockCliProfile(Block):
    target_configs: MockTargetConfigs

    def get_profile(self):
        profile = {
            "name": {
                "outputs": {"target": self.target_configs.get_configs()},
            },
        }
        return profile


def test_credentials_is_able_to_serialize_back(monkeypatch, service_account_info):
    @task
    def test_task(mock_cli_profile):
        return mock_cli_profile.get_profile()

    @flow
    def test_flow():
        gcp_credentials = GcpCredentials(
            service_account_info=service_account_info, project="my-project"
        )
        mock_target_configs = MockTargetConfigs(credentials=gcp_credentials)
        mock_cli_profile = MockCliProfile(target_configs=mock_target_configs)
        task_result = test_task(mock_cli_profile)
        return task_result

    expected = {
        "name": {
            "outputs": {
                "target": {
                    "project": "my-project",
                    "service_account_file": None,
                    "service_account_info": {
                        "project_id": "my_project",
                        "token_uri": "my-token-uri",
                        "client_email": "my-client-email",
                        "private_key": "my-private-key",
                    },
                }
            }
        }
    }
    assert test_flow() == expected


async def test_get_access_token_async(gcp_credentials):
    print(gcp_credentials.get_credentials_from_service_account().token)
    token = await gcp_credentials.get_access_token()
    assert token == "my-token"


def test_get_access_token_sync_compatible(gcp_credentials):
    token = gcp_credentials.get_access_token()
    assert token == "my-token"


@pytest.mark.parametrize("input_type", [None, str])
@pytest.mark.parametrize(
    "client_type",
    [
        ClientType.BIGQUERY,
        ClientType.CLOUD_STORAGE,
        ClientType.AIPLATFORM,
        ClientType.SECRET_MANAGER,
    ],
)
def test_get_client(gcp_credentials, input_type, client_type):
    if input_type is not None:
        client_type = input_type(client_type.value)
    assert gcp_credentials.get_client(client_type=client_type)


def test_get_client_error(gcp_credentials):
    with pytest.raises(ValueError, match="'cool' is not a valid ClientType"):
        assert gcp_credentials.get_client(client_type="cool")
