import pytest


from prefect.core.orion.client import Client, set_client, _CLIENT


@pytest.fixture
def user_client(client):
    user_client = Client(http_client=client)

    # Set the current client and reset it after the test exits
    token = set_client(user_client)
    try:
        yield
    finally:
        _CLIENT.reset(token)
