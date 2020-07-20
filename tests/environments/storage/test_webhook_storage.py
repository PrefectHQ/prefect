import cloudpickle
import pytest
import random
import uuid

from requests.exceptions import HTTPError
from typing import Any, Dict, Optional

from prefect import task, Flow
from prefect.environments.storage import WebHook


@pytest.fixture
def sample_flow():
    @task
    def random_number():
        return random.randint(0, 100)

    with Flow("test-flow") as flow:
        random_number()

    return flow


class _MockResponse:
    """
    This class is a minimal mock of `requests.models.Response`.
    Other mocking functions created in the tests below use this
    to mock responses from services.
    """

    def __init__(
        self,
        status_code: int,
        json: Optional[Dict[str, Any]] = None,
        content: Optional[bytes] = None,
    ):
        self.status_code = status_code
        self.json_content = json or {}
        self.content = content

    def raise_for_status(self, *args, **kwargs) -> None:
        if (self.status_code // 100) != 2:
            raise HTTPError("test-error-message")
        else:
            RuntimeError("blegh")


def test_create_webhook_storage():
    build_kwargs = {"url": "https://content.dropboxapi.com/2/files/upload"}
    get_flow_kwargs = {"url": "https://content.dropboxapi.com/2/files/download"}
    storage = WebHook(
        build_kwargs=build_kwargs,
        build_http_method="PATCH",
        get_flow_kwargs=get_flow_kwargs,
        get_flow_http_method="GET",
    )
    assert storage
    assert storage.logger
    assert storage.build_kwargs == build_kwargs
    assert storage.build_http_method == "PATCH"
    assert storage.build_secret_config == {}
    assert storage.get_flow_kwargs == get_flow_kwargs
    assert storage.get_flow_http_method == "GET"
    assert storage.get_flow_secret_config == {}
    assert storage.secrets == []
    assert storage.default_labels == ["webhook-flow-storage"]


def test_all_valid_http_verb_combinations_work():
    possible_verbs = ["GET", "PATCH", "POST", "PUT"]
    for build_verb in possible_verbs:
        for get_verb in possible_verbs:
            storage = WebHook(
                build_kwargs={"url": "whatever"},
                build_http_method=build_verb,
                get_flow_kwargs={"url": "whatever"},
                get_flow_http_method=get_verb,
            )
            assert storage.build_http_method == build_verb
            assert storage.get_flow_http_method == get_verb


def test_webhook_fails_for_bad_build_http_method():
    with pytest.raises(RuntimeError, match="HTTP method 'PASTA' not recognized"):
        WebHook(
            build_kwargs={"url": "https://content.dropboxapi.com/2/files"},
            build_http_method="PASTA",
            get_flow_kwargs={"url": "https://content.dropboxapi.com/2/files"},
            get_flow_http_method="POST",
        )


def test_webhook_fails_for_bad_get_flow_http_method():
    with pytest.raises(RuntimeError, match="HTTP method 'BET' not recognized"):
        WebHook(
            build_kwargs={"url": "https://content.dropboxapi.com/2/files"},
            build_http_method="POST",
            get_flow_kwargs={"url": "https://content.dropboxapi.com/2/files"},
            get_flow_http_method="BET",
        )


def test_add_flow_and_contains_work_as_expected(sample_flow):
    webhook = WebHook(
        build_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        build_http_method="POST",
        get_flow_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_http_method="GET",
    )
    assert sample_flow.name not in webhook
    out = webhook.add_flow(sample_flow)
    assert isinstance(out, str)
    assert sample_flow.name in webhook
    assert str(uuid.uuid4()) not in webhook


def test_webhook_build_works_with_no_arguments(sample_flow):
    webhook = WebHook(
        build_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        build_http_method="POST",
        get_flow_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_http_method="GET",
    )

    def _mock_successful_get(*args, **kwargs):
        return _MockResponse(
            status_code=200, json={}, content=cloudpickle.dumps(sample_flow)
        )

    def _mock_successful_post(*args, **kwargs):
        return _MockResponse(status_code=200, json={"id": "abc"})

    webhook._method_to_function = {
        "GET": _mock_successful_get,
        "POST": _mock_successful_post,
    }
    webhook.add_flow(sample_flow)

    res = webhook.build()
    assert isinstance(res, WebHook)

    res = webhook.get_flow()
    assert isinstance(res, Flow)


def test_webhook_raises_warning_if_data_in_build_kwargs(sample_flow):
    webhook = WebHook(
        build_kwargs={
            "url": "https://content.dropboxapi.com/2/files",
            "data": cloudpickle.dumps(sample_flow),
        },
        build_http_method="POST",
        get_flow_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_http_method="GET",
    )

    def _mock_successful_get(*args, **kwargs):
        return _MockResponse(
            status_code=200, json={}, content=cloudpickle.dumps(sample_flow)
        )

    def _mock_successful_post(*args, **kwargs):
        return _MockResponse(status_code=200, json={"id": "abc"})

    webhook._method_to_function = {
        "GET": _mock_successful_get,
        "POST": _mock_successful_post,
    }
    webhook.add_flow(sample_flow)

    with pytest.warns(
        RuntimeWarning, match="flow content and should not be set directly"
    ):
        res = webhook.build()
    assert isinstance(res, WebHook)


def test_webhook_raises_error_on_build_failure(sample_flow):
    webhook = WebHook(
        build_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        build_http_method="POST",
        get_flow_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_http_method="GET",
    )

    def _mock_failed_post(*args, **kwargs):
        return _MockResponse(status_code=404, json={"id": "abc"})

    webhook._method_to_function = {
        "POST": _mock_failed_post,
    }
    webhook.add_flow(sample_flow)

    with pytest.raises(HTTPError, match="test-error-message"):
        webhook.build()


def test_webhook_raises_error_on_get_flow_failure(sample_flow):
    webhook = WebHook(
        build_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        build_http_method="POST",
        get_flow_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_http_method="GET",
    )

    def _mock_failed_get(*args, **kwargs):
        return _MockResponse(status_code=500, json={})

    def _mock_successful_post(*args, **kwargs):
        return _MockResponse(status_code=200, json={"id": "abc"})

    webhook._method_to_function = {
        "GET": _mock_failed_get,
        "POST": _mock_successful_post,
    }
    webhook.add_flow(sample_flow)
    res = webhook.build()

    with pytest.raises(HTTPError, match="test-error-message"):
        webhook.get_flow()
