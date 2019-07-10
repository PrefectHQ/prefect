import base64
import datetime
import json
import os
import uuid
from unittest.mock import MagicMock, mock_open

import marshmallow
import pendulum
import pytest
import requests

import prefect
from prefect.client.client import Client, FlowRunInfoResult, TaskRunInfoResult
from prefect.engine.result import NoResult, Result, SafeResult
from prefect.engine.state import (
    Cached,
    Failed,
    Finished,
    Mapped,
    Paused,
    Pending,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    State,
    Success,
    TimedOut,
    TriggerFailed,
)
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.exceptions import AuthorizationError, ClientError
from prefect.utilities.graphql import GraphQLResult, decompress

#################################
##### Client Tests
#################################


def test_client_initializes_from_config():
    with set_temporary_config(
        {"cloud.graphql": "graphql_server", "cloud.auth_token": "token"}
    ):
        client = Client()
    assert client.graphql_server == "graphql_server"
    assert client.token == "token"


def test_client_initializes_and_prioritizes_kwargs():
    with set_temporary_config(
        {"cloud.graphql": "graphql_server", "cloud.auth_token": "token"}
    ):
        client = Client(graphql_server="my-graphql")
    assert client.graphql_server == "my-graphql"
    assert client.token == "token"


def test_client_token_initializes_from_file(monkeypatch):
    monkeypatch.setattr("os.path.exists", MagicMock(return_value=True))
    monkeypatch.setattr("builtins.open", mock_open(read_data="TOKEN"))
    with set_temporary_config({"cloud.auth_token": None}):
        client = Client()
    assert client.token == "TOKEN"


def test_client_token_priotizes_config_over_file(monkeypatch):
    monkeypatch.setattr("os.path.exists", MagicMock(return_value=True))
    monkeypatch.setattr("builtins.open", mock_open(read_data="file-token"))
    with set_temporary_config({"cloud.auth_token": "config-token"}):
        client = Client()
    assert client.token == "config-token"


def test_client_doesnt_write_to_file_if_token_provided_from_config(monkeypatch):
    monkeypatch.setattr("os.path.exists", MagicMock(return_value=True))
    mock_file = mock_open()
    monkeypatch.setattr("builtins.open", mock_file)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "token"}
    ):
        client = Client()
    assert not mock_file.called


@pytest.mark.parametrize("cloud", [True, False])
def test_client_doesnt_login_if_no_tokens_available(monkeypatch, cloud):
    post = MagicMock(
        return_value=MagicMock(
            ok=True, json=MagicMock(return_value=dict(token="secrettoken"))
        )
    )
    mock_file = mock_open()
    monkeypatch.setattr("builtins.open", mock_file)
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    config = {
        "cloud.graphql": "http://my-cloud.foo",
        "cloud.auth_token": None,
        "cloud.email": "test@example.com",
        "cloud.password": "1234",
    }

    if cloud:
        config.update(
            {
                "engine.flow_runner.default_class": "prefect.engine.cloud.CloudFlowRunner",
                "engine.task_runner.default_class": "prefect.engine.cloud.CloudTaskRunner",
            }
        )
    with set_temporary_config(config):
        client = Client()
    assert not post.called
    assert client.token is None


def test_client_logs_out_and_deletes_auth_token(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            ok=True, json=MagicMock(return_value=dict(token="secrettoken"))
        )
    )
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config({"cloud.graphql": "http://my-cloud.foo"}):
        client = Client()
    client.login("test@example.com", "1234")
    token_path = os.path.expanduser("~/.prefect/.credentials/auth_token")
    assert os.path.exists(token_path)
    with open(token_path, "r") as f:
        assert f.read() == "secrettoken"
    client.logout()
    assert not os.path.exists(token_path)


def test_client_raises_if_login_fails(monkeypatch):
    post = MagicMock(return_value=MagicMock(ok=False))
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config({"cloud.graphql": "http://my-cloud.foo"}):
        client = Client()
    with pytest.raises(AuthorizationError):
        client.login("test@example.com", "1234")
    assert post.called
    assert post.call_args[0][0] == "http://my-cloud.foo/login_email"


def test_client_posts_raises_with_no_token(monkeypatch):
    post = MagicMock()
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": None}
    ):
        client = Client()
    with pytest.raises(AuthorizationError) as exc:
        result = client.post("/foo/bar")
    assert "Client.login" in str(exc.value)


def test_client_posts_to_graphql_server(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(success=True)))
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.post("/foo/bar")
    assert result == {"success": True}
    assert post.called
    assert post.call_args[0][0] == "http://my-cloud.foo/foo/bar"


def test_client_posts_retries_if_token_needs_refreshing(monkeypatch):
    error = requests.HTTPError()
    error.response = MagicMock(status_code=401)  # unauthorized
    post = MagicMock(
        return_value=MagicMock(
            raise_for_status=MagicMock(side_effect=error),
            json=MagicMock(return_value=dict(token="new-token")),
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    monkeypatch.setattr("requests.post", post)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    with pytest.raises(requests.HTTPError) as exc:
        result = client.post("/foo/bar")
    assert exc.value is error
    assert post.call_count == 3  # first call -> refresh token -> last call
    assert post.call_args[0][0] == "http://my-cloud.foo/foo/bar"
    assert client.token == "new-token"


def test_client_posts_graphql_to_graphql_server(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(success=True)))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.graphql("{projects{name}}")
    assert result.data == {"success": True}
    assert post.called
    assert post.call_args[0][0] == "http://my-cloud.foo"


def test_client_graphql_retries_if_token_needs_refreshing(monkeypatch):
    error = requests.HTTPError()
    error.response = MagicMock(status_code=401)  # unauthorized
    post = MagicMock(
        return_value=MagicMock(
            raise_for_status=MagicMock(side_effect=error),
            json=MagicMock(return_value=dict(token="new-token")),
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.post", post)
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    with pytest.raises(requests.HTTPError) as exc:
        result = client.graphql("{}")
    assert exc.value is error
    assert post.call_count == 3  # first call -> refresh token -> last call
    assert post.call_args[0][0] == "http://my-cloud.foo"
    assert client.token == "new-token"


## test actual mutation and query handling
def test_graphql_errors_get_raised(monkeypatch):
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data="42", errors="GraphQL issue!"))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    with pytest.raises(ClientError) as exc:
        res = client.graphql("query: {}")
    assert "GraphQL issue!" in str(exc.value)


@pytest.mark.parametrize("compressed", [True, False])
def test_client_deploy(monkeypatch, compressed):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "createFlowFromCompressedString": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "createFlow": {"id": "long-id"}}
        }
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    flow = prefect.Flow(name="test", storage=prefect.environments.storage.Memory())
    flow_id = client.deploy(
        flow, project_name="my-default-project", compressed=compressed
    )
    assert flow_id == "long-id"


@pytest.mark.parametrize("compressed", [True, False])
def test_client_deploy_builds_flow(monkeypatch, compressed):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "createFlowFromCompressedString": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "createFlow": {"id": "long-id"}}
        }
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    flow = prefect.Flow(name="test", storage=prefect.environments.storage.Memory())
    flow_id = client.deploy(
        flow, project_name="my-default-project", compressed=compressed
    )

    ## extract POST info
    if compressed:
        serialized_flow = decompress(
            json.loads(post.call_args[1]["json"]["variables"])["input"][
                "serializedFlow"
            ]
        )
    else:
        serialized_flow = json.loads(post.call_args[1]["json"]["variables"])["input"][
            "serializedFlow"
        ]
    assert serialized_flow["storage"] is not None


@pytest.mark.parametrize("compressed", [True, False])
def test_client_deploy_optionally_avoids_building_flow(monkeypatch, compressed):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "createFlowFromCompressedString": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "createFlow": {"id": "long-id"}}
        }
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    flow = prefect.Flow(name="test")
    flow_id = client.deploy(
        flow, project_name="my-default-project", build=False, compressed=compressed
    )

    ## extract POST info
    if compressed:
        serialized_flow = decompress(
            json.loads(post.call_args[1]["json"]["variables"])["input"][
                "serializedFlow"
            ]
        )
    else:
        serialized_flow = json.loads(post.call_args[1]["json"]["variables"])["input"][
            "serializedFlow"
        ]
    assert serialized_flow["storage"] is None


def test_client_deploy_with_bad_proj_name(monkeypatch):
    response = {"data": {"project": []}}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    flow = prefect.Flow(name="test")
    with pytest.raises(ValueError) as exc:
        flow_id = client.deploy(flow, project_name="my-default-project")
    assert "not found" in str(exc.value)
    assert "client.create_project" in str(exc.value)


def test_get_flow_run_info(monkeypatch):
    response = """
{
    "flow_run_by_pk": {
        "version": 0,
        "parameters": {},
        "context": null,
        "scheduled_start_time": "2019-01-25T19:15:58.632412+00:00",
        "serialized_state": {
            "type": "Pending",
            "_result": {"type": "SafeResult", "value": "42", "result_handler": {"type": "JSONResultHandler"}},
            "message": null,
            "__version__": "0.3.3+309.gf1db024",
            "cached_inputs": null
        },
        "task_runs":[
            {
                "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                "task": {
                    "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                    "slug": "da344768-5f5d-4eaf-9bca-83815617f713"
                    },
                "version": 0,
                "serialized_state": {
                    "type": "Pending",
                    "result": null,
                    "message": null,
                    "__version__": "0.3.3+309.gf1db024",
                    "cached_inputs": null
                }
            }
        ]
    }
}
    """
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=json.loads(response)))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.get_flow_run_info(flow_run_id="74-salt")
    assert isinstance(result, FlowRunInfoResult)
    assert isinstance(result.scheduled_start_time, datetime.datetime)
    assert result.scheduled_start_time.minute == 15
    assert result.scheduled_start_time.year == 2019
    assert isinstance(result.state, Pending)
    assert result.state.result == "42"
    assert result.state.message is None
    assert result.version == 0
    assert isinstance(result.parameters, dict)
    assert result.context is None


def test_get_flow_run_info_with_nontrivial_payloads(monkeypatch):
    response = """
{
    "flow_run_by_pk": {
        "version": 0,
        "parameters": {"x": {"deep": {"nested": 5}}},
        "context": {"my_val": "test"},
        "scheduled_start_time": "2019-01-25T19:15:58.632412+00:00",
        "serialized_state": {
            "type": "Pending",
            "_result": {"type": "SafeResult", "value": "42", "result_handler": {"type": "JSONResultHandler"}},
            "message": null,
            "__version__": "0.3.3+309.gf1db024",
            "cached_inputs": null
        },
        "task_runs":[
            {
                "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                "task": {
                    "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                    "slug": "da344768-5f5d-4eaf-9bca-83815617f713"
                    },
                "version": 0,
                "serialized_state": {
                    "type": "Pending",
                    "result": null,
                    "message": null,
                    "__version__": "0.3.3+309.gf1db024",
                    "cached_inputs": null
                }
            }
        ]
    }
}
    """
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=json.loads(response)))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.get_flow_run_info(flow_run_id="74-salt")
    assert isinstance(result, FlowRunInfoResult)
    assert isinstance(result.scheduled_start_time, datetime.datetime)
    assert result.scheduled_start_time.minute == 15
    assert result.scheduled_start_time.year == 2019
    assert isinstance(result.state, Pending)
    assert result.state.result == "42"
    assert result.state.message is None
    assert result.version == 0
    assert isinstance(result.parameters, dict)
    assert result.parameters["x"]["deep"]["nested"] == 5
    # ensures all sub-dictionaries are actually dictionaries
    assert json.loads(json.dumps(result.parameters)) == result.parameters
    assert isinstance(result.context, dict)
    assert result.context["my_val"] == "test"


def test_get_flow_run_info_raises_informative_error(monkeypatch):
    response = """
    {
        "flow_run_by_pk": null
    }
    """
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=json.loads(response)))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    with pytest.raises(ClientError) as exc:
        result = client.get_flow_run_info(flow_run_id="74-salt")
    assert "not found" in str(exc.value)


def test_set_flow_run_state(monkeypatch):
    response = {"data": {"setFlowRunState": {"id": 1}}}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.set_flow_run_state(
        flow_run_id="74-salt", version=0, state=Pending()
    )
    assert result is None


def test_set_flow_run_state_with_error(monkeypatch):
    response = {
        "data": {"setFlowRunState": None},
        "errors": [{"message": "something went wrong"}],
    }
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    with pytest.raises(ClientError) as exc:
        client.set_flow_run_state(flow_run_id="74-salt", version=0, state=Pending())
    assert "something went wrong" in str(exc.value)


def test_get_task_run_info(monkeypatch):
    response = """
    {
        "getOrCreateTaskRun": {
            "task_run": {
                "id": "772bd9ee-40d7-479c-9839-4ab3a793cabd",
                "version": 0,
                "serialized_state": {
                    "type": "Pending",
                    "_result": {"type": "SafeResult", "value": "42", "result_handler": {"type": "JSONResultHandler"}},
                    "message": null,
                    "__version__": "0.3.3+310.gd19b9b7.dirty",
                    "cached_inputs": null
                },
                "task": {
                    "slug": "slug"
                }
            }
        }
    }
    """
    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=json.loads(response)))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.get_task_run_info(
        flow_run_id="74-salt", task_id="72-salt", map_index=None
    )
    assert isinstance(result, TaskRunInfoResult)
    assert isinstance(result.state, Pending)
    assert result.state.result == "42"
    assert result.state.message is None
    assert result.id == "772bd9ee-40d7-479c-9839-4ab3a793cabd"
    assert result.version == 0


def test_get_task_run_info_with_error(monkeypatch):
    response = {
        "data": {"getOrCreateTaskRun": None},
        "errors": [{"message": "something went wrong"}],
    }
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    with pytest.raises(ClientError) as exc:
        client.get_task_run_info(
            flow_run_id="74-salt", task_id="72-salt", map_index=None
        )

    assert "something went wrong" in str(exc.value)


def test_set_task_run_state(monkeypatch):
    response = {"data": {"setTaskRunState": None}}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))

    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.set_task_run_state(
        task_run_id="76-salt", version=0, state=Pending()
    )

    assert result is None


def test_set_task_run_state_serializes(monkeypatch):
    response = {"data": {"setTaskRunState": None}}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))

    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    res = SafeResult(lambda: None, result_handler=None)
    with pytest.raises(marshmallow.exceptions.ValidationError) as exc:
        result = client.set_task_run_state(
            task_run_id="76-salt", version=0, state=Pending(result=res)
        )


def test_set_task_run_state_with_error(monkeypatch):
    response = {
        "data": {"setTaskRunState": None},
        "errors": [{"message": "something went wrong"}],
    }
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))

    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    with pytest.raises(ClientError) as exc:
        client.set_task_run_state(task_run_id="76-salt", version=0, state=Pending())
    assert "something went wrong" in str(exc.value)


def test_write_log_successfully(monkeypatch):
    response = {"data": {"writeRunLog": {"success": True}}}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    assert client.write_run_log(flow_run_id="1") is None


def test_write_log_with_error(monkeypatch):
    response = {
        "data": {"writeRunLog": None},
        "errors": [{"message": "something went wrong"}],
    }
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    with pytest.raises(ClientError) as exc:
        client.write_run_log(flow_run_id="1")
    assert "something went wrong" in str(exc.value)
