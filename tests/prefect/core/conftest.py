import pytest


from prefect.core.client import Client, _current_client


@pytest.fixture
def user_client(client):
    user_client = Client(http_client=client)

    # This workaround is needed to set the `ContextVar` since fixtures / tests do not
    # share contexts in pytest: https://github.com/pytest-dev/pytest-asyncio/issues/127
    token = _current_client.set(user_client)
    try:
        yield
    finally:
        _current_client.reset(token)
