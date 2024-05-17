import pytest
from azure.identity import DefaultAzureCredential
from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    pass
else:
    pass

from prefect_azure import AzureContainerInstanceCredentials


def test_azure_container_instance_credentials_no_args():
    credentials = AzureContainerInstanceCredentials()
    assert credentials.tenant_id is None
    assert credentials.client_id is None
    assert credentials.client_secret is None
    assert isinstance(credentials._create_credential(), DefaultAzureCredential)


def test_azure_container_instance_credentials_insufficient_args():
    with pytest.raises(ValueError, match="If any of `client_id`"):
        AzureContainerInstanceCredentials(tenant_id="tenant_id")


def test_azure_container_instance_credentials_random_kwargs():
    credentials = AzureContainerInstanceCredentials(
        credential_kwargs={"exclude_powershell_credential": True}
    )
    assert credentials.credential_kwargs == {"exclude_powershell_credential": True}
