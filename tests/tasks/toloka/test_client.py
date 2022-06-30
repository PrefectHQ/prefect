import inspect
import re

import prefect
import pytest
import responses
from prefect.tasks.toloka.utils import (
    DEFAULT_TOLOKA_ENV,
    DEFAULT_TOLOKA_SECRET_NAME,
    with_toloka_client,
)
from toloka.client import TolokaClient


DEFAULT_TOKEN = "some-token"

OTHER_SECRET_NAME = "OTHER_SECRET"
OTHER_TOKEN = "some-other-token"
OTHER_ENV = "SANDBOX"


@pytest.fixture
def secrets_mock():
    secrets = {
        DEFAULT_TOLOKA_SECRET_NAME: DEFAULT_TOKEN,
        OTHER_SECRET_NAME: OTHER_TOKEN,
    }
    with prefect.context(secrets=secrets):
        yield


class TestWithTolokaClient:
    def test_signature(self, secrets_mock):
        @with_toloka_client
        def some_func(arg1, arg2, toloka_client):
            ...

        params = set(inspect.signature(some_func).parameters)
        assert {"arg1", "arg2", "secret_name", "env"} == params, params

    def test_new_toloka_client(self, secrets_mock):
        @with_toloka_client
        def some_func(expected_token, expected_env, toloka_client=None):
            assert expected_token == toloka_client.token
            assert TolokaClient.Environment[expected_env].value == toloka_client.url

        some_func(DEFAULT_TOKEN, DEFAULT_TOLOKA_ENV)
        some_func(OTHER_TOKEN, OTHER_ENV, secret_name=OTHER_SECRET_NAME, env=OTHER_ENV)


def test_add_headers(secrets_mock):
    @with_toloka_client
    def make_request(toloka_client):
        return toloka_client.get_pool("123")

    with responses.RequestsMock() as mocker:
        mocker.get(re.compile('.*'), body=b"...")

        with pytest.raises(Exception, match="Expecting value"):
            make_request()

        assert mocker.calls
        headers = mocker.calls[0].request.headers
        assert "prefect" == headers["X-Caller-Context"], headers
