import cloudpickle
import os
import pytest
import random
import uuid

from requests.exceptions import HTTPError
from typing import Any, Dict, Optional

from prefect import context
from prefect import task, Flow
from prefect.storage.webhook import Webhook, _render_dict


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
    build_request_kwargs = {"url": "https://content.dropboxapi.com/2/files/upload"}
    get_flow_request_kwargs = {"url": "https://content.dropboxapi.com/2/files/download"}
    storage = Webhook(
        build_request_kwargs=build_request_kwargs,
        build_request_http_method="PATCH",
        get_flow_request_kwargs=get_flow_request_kwargs,
        get_flow_request_http_method="GET",
    )
    assert storage
    assert storage.logger
    assert storage.build_request_kwargs == build_request_kwargs
    assert storage.build_request_http_method == "PATCH"
    assert storage.get_flow_request_kwargs == get_flow_request_kwargs
    assert storage.get_flow_request_http_method == "GET"
    assert storage.secrets == []
    assert storage.stored_as_script is False


def test_all_valid_http_verb_combinations_work():
    possible_verbs = ["GET", "PATCH", "POST", "PUT"]
    for build_verb in possible_verbs:
        for get_verb in possible_verbs:
            storage = Webhook(
                build_request_kwargs={"url": "whatever"},
                build_request_http_method=build_verb,
                get_flow_request_kwargs={"url": "whatever"},
                get_flow_request_http_method=get_verb,
            )
            assert storage.build_request_http_method == build_verb
            assert storage.get_flow_request_http_method == get_verb


def test_webhook_fails_for_bad_build_request_http_method():
    with pytest.raises(RuntimeError, match="HTTP method 'PASTA' not recognized"):
        Webhook(
            build_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
            build_request_http_method="PASTA",
            get_flow_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
            get_flow_request_http_method="POST",
        )


def test_webhook_fails_for_bad_get_flow_request_http_method():
    with pytest.raises(RuntimeError, match="HTTP method 'BET' not recognized"):
        Webhook(
            build_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
            build_request_http_method="POST",
            get_flow_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
            get_flow_request_http_method="BET",
        )


def test_add_flow_and_contains_work_as_expected(sample_flow):
    webhook = Webhook(
        build_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        build_request_http_method="POST",
        get_flow_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_request_http_method="GET",
    )
    assert sample_flow.name not in webhook
    out = webhook.add_flow(sample_flow)
    assert isinstance(out, str)
    assert sample_flow.name in webhook
    assert str(uuid.uuid4()) not in webhook

    # should return False if input is not a string
    assert sample_flow not in webhook


def test_webhook_build_works_with_no_arguments(sample_flow):
    webhook = Webhook(
        build_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        build_request_http_method="POST",
        get_flow_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_request_http_method="GET",
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
    assert isinstance(res, Webhook)

    res = webhook.get_flow(sample_flow.name)
    assert isinstance(res, Flow)


def test_webhook_raises_warning_if_data_in_build_request_kwargs(sample_flow):
    webhook = Webhook(
        build_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files",
            "data": cloudpickle.dumps(sample_flow),
        },
        build_request_http_method="POST",
        get_flow_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_request_http_method="GET",
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
    assert isinstance(res, Webhook)


def test_webhook_raises_error_on_build_failure(sample_flow):
    webhook = Webhook(
        build_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        build_request_http_method="POST",
        get_flow_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_request_http_method="GET",
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
    webhook = Webhook(
        build_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        build_request_http_method="POST",
        get_flow_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_request_http_method="GET",
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
    webhook.build()

    with pytest.raises(HTTPError, match="test-error-message"):
        webhook.get_flow(sample_flow.name)


def test_render_dict_gets_env_variables(monkeypatch):
    some_cred = str(uuid.uuid4())
    another_secret = str(uuid.uuid4())
    monkeypatch.setenv("SOME_CRED", some_cred)
    webhook = Webhook(
        build_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files",
            "headers": {
                "X-Api-Key": "${SOME_CRED}",
                "X-Custom-Key": "${ANOTHER_SECRET}",
            },
        },
        build_request_http_method="POST",
        get_flow_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_request_http_method="GET",
    )

    # set a local secret
    context.setdefault("secrets", {})
    context.secrets["ANOTHER_SECRET"] = another_secret

    new_kwargs = _render_dict(webhook.build_request_kwargs)

    # _render_dict should not have side effects
    assert webhook.build_request_kwargs == {
        "url": "https://content.dropboxapi.com/2/files",
        "headers": {"X-Api-Key": "${SOME_CRED}", "X-Custom-Key": "${ANOTHER_SECRET}"},
    }

    # env variables and secrets should have been filled in
    assert new_kwargs["headers"]["X-Api-Key"] == some_cred
    assert new_kwargs["headers"]["X-Custom-Key"] == another_secret


def test_render_dict_raises_expected_exception_on_missing_env_var(monkeypatch):
    monkeypatch.delenv("SOME_CRED", raising=False)
    webhook = Webhook(
        build_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files",
            "headers": {"X-Api-Key": "Token ${SOME_CRED}"},
        },
        build_request_http_method="POST",
        get_flow_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_request_http_method="GET",
    )

    with pytest.raises(RuntimeError, match="SOME_CRED"):
        _render_dict(webhook.build_request_kwargs)


def test_render_dict_raises_expected_exception_on_missing_secret(monkeypatch):
    monkeypatch.delenv("ANOTHER_SECRET", raising=False)
    webhook = Webhook(
        build_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files?key=${ANOTHER_SECRET}"
        },
        build_request_http_method="POST",
        get_flow_request_kwargs={"url": "https://content.dropboxapi.com/2/files"},
        get_flow_request_http_method="GET",
    )

    with pytest.raises(
        RuntimeError, match="does not refer to an environment variable or"
    ):
        _render_dict(webhook.build_request_kwargs)


def test_templating_works_with_env_variable_top_level(monkeypatch):
    monkeypatch.setenv("JAVA_HOME", "abc")
    x = {"a": "coffee_place: ${JAVA_HOME}"}
    out = _render_dict(x)
    assert out == {"a": "coffee_place: abc"}
    assert x == {"a": "coffee_place: ${JAVA_HOME}"}


def test_templating_works_with_env_variable_recursively(monkeypatch):
    monkeypatch.setenv("USER", "leia")
    x = {"a": {"b": {"c": "Bearer: ${USER}"}}}
    out = _render_dict(x)
    assert out == {"a": {"b": {"c": "Bearer: leia"}}}
    assert x == {"a": {"b": {"c": "Bearer: ${USER}"}}}


def templating_works_if_nothing_to_template():
    x = {"thing": 4, "stuff": [5, 6, 7], "big": {"if": True}}
    out = _render_dict(x)
    assert out == x
    assert x == {"thing": 4, "stuff": [5, 6, 7], "big": {"if": True}}


def templating_works_with_embedded_json_strings():
    x = {"headers": {"dropbox-args": '{"USER"}'}}
    out = _render_dict(x)
    assert out == x


def test_webhook_works_with_file_storage(sample_flow, tmpdir):

    script_file = os.path.join(tmpdir, "{}.py".format(str(uuid.uuid4())))
    script_contents = """from prefect import Flow\nf=Flow('test-flow')"""
    with open(script_file, "w") as f:
        f.write(script_contents)

    webhook = Webhook(
        build_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files",
            "headers": {"Content-Type": "application/octet-stream"},
        },
        build_request_http_method="POST",
        get_flow_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files",
            "headers": {"Accept": "application/octet-stream"},
        },
        get_flow_request_http_method="GET",
        stored_as_script=True,
        flow_script_path=script_file,
    )

    def _mock_successful_get(*args, **kwargs):
        file_contents = """from prefect import Flow\nf=Flow('test-flow')"""
        return _MockResponse(
            status_code=200, json={}, content=file_contents.encode("utf-8")
        )

    def _mock_successful_post(*args, **kwargs):
        return _MockResponse(status_code=200, json={"id": "abc"})

    webhook._method_to_function = {
        "GET": _mock_successful_get,
        "POST": _mock_successful_post,
    }
    webhook.add_flow(sample_flow)

    res = webhook.build()
    assert isinstance(res, Webhook)

    res = webhook.get_flow(sample_flow.name)
    assert isinstance(res, Flow)
    assert res.name == "test-flow"


def test_webhook_throws_informative_error_if_flow_script_path_not_set(sample_flow):

    webhook = Webhook(
        build_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files",
            "headers": {"Content-Type": "application/octet-stream"},
        },
        build_request_http_method="POST",
        get_flow_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files",
            "headers": {"Accept": "application/octet-stream"},
        },
        get_flow_request_http_method="GET",
        stored_as_script=True,
    )

    webhook.add_flow(sample_flow)

    error_msg = "flow_script_path must be provided if stored_as_script=True"
    with pytest.raises(RuntimeError, match=error_msg):
        res = webhook.build()
        assert isinstance(res, Webhook)


def test_webhook_throws_informative_error_if_flow_script_file_does_not_exist(
    sample_flow,
):

    nonexistent_file = "{}.py".format(str(uuid.uuid4()))
    webhook = Webhook(
        build_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files",
            "headers": {"Content-Type": "application/octet-stream"},
        },
        build_request_http_method="POST",
        get_flow_request_kwargs={
            "url": "https://content.dropboxapi.com/2/files",
            "headers": {"Accept": "application/octet-stream"},
        },
        get_flow_request_http_method="GET",
        stored_as_script=True,
        flow_script_path=nonexistent_file,
    )

    webhook.add_flow(sample_flow)

    error_msg = "passed to flow_script_path does not exist"
    with pytest.raises(RuntimeError, match=error_msg):
        res = webhook.build()
        assert isinstance(res, Webhook)
