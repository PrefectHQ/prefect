import pytest
from atlassian.bitbucket import Bitbucket, Cloud
from prefect_bitbucket.credentials import BitBucketCredentials, ClientType

from prefect.blocks.core import Block


@pytest.mark.parametrize("token", [None, "token_value"])
def test_bitbucket_credentials(token):
    """Test credentials is Block type."""
    credentials_block = BitBucketCredentials(token=token)
    assert isinstance(credentials_block, Block)


def ensure_valid_bitbucket_username_passes():
    """Ensure invalid char username raises."""
    try:
        BitBucketCredentials(token="token", username="validusername")
    except Exception as exc:
        assert False, f"Valid username raised an exception {exc}"


def test_bitbucket_username_invalid_char():
    """Ensure invalid char username raises."""
    with pytest.raises(ValueError):
        BitBucketCredentials(token="token", username="invalid!username")


def test_bitbucket_username_over_max_length():
    """Ensure username of greater than max allowed length raises."""
    with pytest.raises(ValueError):
        BitBucketCredentials(
            token="token", username="usernamethatisoverthirtycharacters"
        )


@pytest.mark.parametrize(
    "client_type",
    ["local", "LOCAL", "cloud", "Cloud", ClientType.LOCAL, ClientType.CLOUD],
)
def test_bitbucket_get_client(client_type):
    bitbucket_credentials = BitBucketCredentials(
        url="my-url", username="my-username", password="my-password"
    )
    client = bitbucket_credentials.get_client(client_type=client_type)
    if not isinstance(client_type, str):
        client_type = client_type.value

    if client_type.lower() == "local":
        assert isinstance(client, Bitbucket)
    else:
        assert isinstance(client, Cloud)
