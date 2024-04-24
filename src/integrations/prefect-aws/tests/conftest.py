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


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    with prefect_test_harness():
        yield


@pytest.fixture
def aws_credentials():
    block = AwsCredentials(
        aws_access_key_id="access_key_id",
        aws_secret_access_key="secret_access_key",
        region_name="us-east-1",
    )
    block.save("test-creds-block", overwrite=True)
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


@pytest.fixture(autouse=True)
def reset_object_registry():
    """
    Ensures each test has a clean object registry.
    """
    from prefect.context import PrefectObjectRegistry

    with PrefectObjectRegistry():
        yield
