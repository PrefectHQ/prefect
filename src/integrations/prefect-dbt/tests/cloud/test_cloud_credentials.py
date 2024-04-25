import pytest
from prefect_dbt import DbtCloudCredentials
from prefect_dbt.cloud.clients import (
    DbtCloudAdministrativeClient,
    DbtCloudMetadataClient,
)


@pytest.fixture
def dbt_cloud_credentials():
    return DbtCloudCredentials(api_key="my_api_key", account_id=123456789)


def test_get_administrative_client(dbt_cloud_credentials: DbtCloudCredentials):
    assert isinstance(
        dbt_cloud_credentials.get_administrative_client(), DbtCloudAdministrativeClient
    )


def test_get_metadata_client(dbt_cloud_credentials: DbtCloudCredentials):
    assert isinstance(
        dbt_cloud_credentials.get_metadata_client(), DbtCloudMetadataClient
    )


def test_get_client(dbt_cloud_credentials: DbtCloudCredentials):
    assert isinstance(
        dbt_cloud_credentials.get_client("administrative"), DbtCloudAdministrativeClient
    )
    assert isinstance(
        dbt_cloud_credentials.get_client("metadata"), DbtCloudMetadataClient
    )
    with pytest.raises(ValueError, match="'blorp' is not a supported client type"):
        dbt_cloud_credentials.get_client("blorp")
