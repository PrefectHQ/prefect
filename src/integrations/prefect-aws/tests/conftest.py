import sys

import pytest
from botocore import UNSIGNED
from botocore.client import Config
from prefect_aws import AwsCredentials
from prefect_aws.client_parameters import AwsClientParameters

from prefect.testing.utilities import prefect_test_harness


# added to eliminate warnings
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "is_public: mark test as using public S3 bucket or not"
    )
    config.addinivalue_line(
        "markers", "windows: tests that specifically test Windows-only behavior"
    )


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
):
    """Skip tests marked with @pytest.mark.windows on non-Windows platforms."""
    if sys.platform != "win32":
        for item in items:
            if item.get_closest_marker("windows"):
                item.add_marker(pytest.mark.skip(reason="Test only runs on Windows"))


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    with prefect_test_harness():
        yield


@pytest.fixture
async def aws_credentials():
    block = AwsCredentials(
        aws_access_key_id="access_key_id",
        aws_secret_access_key="secret_access_key",
        region_name="us-east-1",
    )
    await block.save("test-creds-block", overwrite=True)
    return block


@pytest.fixture
def aws_client_parameters_custom_endpoint():
    return AwsClientParameters(endpoint_url="http://custom.internal.endpoint.org")


@pytest.fixture
def aws_client_parameters_empty():
    return AwsClientParameters()


@pytest.fixture
def aws_client_parameters_public_bucket():
    return AwsClientParameters(config=Config(signature_version=UNSIGNED))
