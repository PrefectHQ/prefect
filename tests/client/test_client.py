import tempfile
import datetime
import json
import os
from unittest.mock import MagicMock, mock_open

import marshmallow
import pendulum
import pytest
import requests

import prefect
from prefect.client.client import Client, FlowRunInfoResult, TaskRunInfoResult
from prefect.engine.result import NoResult, Result, SafeResult
from prefect.engine.state import Pending
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


def test_client_token_path_depends_on_graphql_server():
    assert Client(graphql_server="a").local_token_path == os.path.expanduser(
        "~/.prefect/tokens/a"
    )

    assert Client(graphql_server="b").local_token_path == os.path.expanduser(
        "~/.prefect/tokens/b"
    )


def test_client_token_initializes_from_file(monkeypatch):

    with tempfile.NamedTemporaryFile() as f:
        f.write(b"TOKEN")
        f.seek(0)
        monkeypatch.setattr("prefect.client.Client.local_token_path", f.name)

        with set_temporary_config({"cloud.auth_token": None}):
            client = Client()
    assert client.token == "TOKEN"


def test_client_token_priotizes_config_over_file(monkeypatch):
    with tempfile.NamedTemporaryFile() as f:
        f.write(b"TOKEN")
        f.seek(0)
        monkeypatch.setattr("prefect.client.Client.local_token_path", f.name)

        with set_temporary_config({"cloud.auth_token": "CONFIG-TOKEN"}):
            client = Client()
    assert client.token == "CONFIG-TOKEN"


def test_login_writes_token(monkeypatch):
    with tempfile.NamedTemporaryFile() as f:
        monkeypatch.setattr("prefect.client.Client.local_token_path", f.name)

        client = Client()

        client.login(api_token="a")
        assert f.read() == b"a"

        f.seek(0)

        client.login(api_token="b")
        assert f.read() == b"b"


def test_login_creates_directories(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:

        f_path = os.path.join(tmp, "a", "b", "c")

        monkeypatch.setattr("prefect.client.Client.local_token_path", f_path)

        client = Client()

        client.login(api_token="a")

        with open(f_path) as f:
            assert f.read() == "a"


def test_logout_removes_token(monkeypatch):
    with tempfile.NamedTemporaryFile(delete=False) as f:
        monkeypatch.setattr("prefect.client.Client.local_token_path", f.name)

        client = Client()

        client.login(api_token="a")
        assert f.read() == b"a"

    client.logout()
    assert not os.path.exists(f.name)


def test_client_posts_raises_with_no_token(monkeypatch):
    post = MagicMock()
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": None}
    ):
        client = Client()
    with pytest.raises(AuthorizationError, match="Client.login"):
        result = client.post("/foo/bar")


def test_headers_are_passed_to_get(monkeypatch):
    get = MagicMock()
    session = MagicMock()
    session.return_value.get = get
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    client.get("/foo/bar", headers={"x": "y", "Authorization": "z"})
    assert get.called
    assert get.call_args[1]["headers"] == {
        "x": "y",
        "Authorization": "Bearer secret_token",
    }


def test_headers_are_passed_to_post(monkeypatch):
    post = MagicMock()
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    client.post("/foo/bar", headers={"x": "y", "Authorization": "z"})
    assert post.called
    assert post.call_args[1]["headers"] == {
        "x": "y",
        "Authorization": "Bearer secret_token",
    }


def test_headers_are_passed_to_graphql(monkeypatch):
    post = MagicMock()
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    client.graphql("query {}", headers={"x": "y", "Authorization": "z"})
    assert post.called
    assert post.call_args[1]["headers"] == {
        "x": "y",
        "Authorization": "Bearer secret_token",
    }


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
    with pytest.raises(ClientError, match="GraphQL issue!"):
        client.graphql("query: {}")


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


def test_client_deploy_with_flow_that_cant_be_deserialized(monkeypatch):
    response = {"data": {"project": [{"id": "proj-id"}]}}
    post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    task = prefect.Task()
    # we add a max_retries value to the task without a corresponding retry_delay; this will fail at deserialization
    task.max_retries = 3
    flow = prefect.Flow(name="test", tasks=[task])

    with pytest.raises(
        ValueError,
        match=(
            "(Flow could not be deserialized).*"
            "(`retry_delay` must be provided if max_retries > 0)"
        ),
    ) as exc:
        client.deploy(flow, project_name="my-default-project", build=False)


def test_get_flow_run_info(monkeypatch):
    response = {
        "flow_run_by_pk": {
            "id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "flow_id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "version": 0,
            "parameters": {},
            "context": None,
            "scheduled_start_time": "2019-01-25T19:15:58.632412+00:00",
            "serialized_state": {
                "type": "Pending",
                "_result": {
                    "type": "SafeResult",
                    "value": "42",
                    "result_handler": {"type": "JSONResultHandler"},
                },
                "message": None,
                "__version__": "0.3.3+309.gf1db024",
                "cached_inputs": None,
            },
            "task_runs": [
                {
                    "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                    "task": {
                        "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                        "slug": "da344768-5f5d-4eaf-9bca-83815617f713",
                    },
                    "version": 0,
                    "serialized_state": {
                        "type": "Pending",
                        "result": None,
                        "message": None,
                        "__version__": "0.3.3+309.gf1db024",
                        "cached_inputs": None,
                    },
                }
            ],
        }
    }

    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=response)))
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
    response = {
        "flow_run_by_pk": {
            "id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "flow_id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "version": 0,
            "parameters": {"x": {"deep": {"nested": 5}}},
            "context": {"my_val": "test"},
            "scheduled_start_time": "2019-01-25T19:15:58.632412+00:00",
            "serialized_state": {
                "type": "Pending",
                "_result": {
                    "type": "SafeResult",
                    "value": "42",
                    "result_handler": {"type": "JSONResultHandler"},
                },
                "message": None,
                "__version__": "0.3.3+309.gf1db024",
                "cached_inputs": None,
            },
            "task_runs": [
                {
                    "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                    "task": {
                        "id": "da344768-5f5d-4eaf-9bca-83815617f713",
                        "slug": "da344768-5f5d-4eaf-9bca-83815617f713",
                    },
                    "version": 0,
                    "serialized_state": {
                        "type": "Pending",
                        "result": None,
                        "message": None,
                        "__version__": "0.3.3+309.gf1db024",
                        "cached_inputs": None,
                    },
                }
            ],
        }
    }

    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=response)))
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
    response = {"flow_run_by_pk": None}
    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=response)))
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    with pytest.raises(ClientError, match="not found"):
        client.get_flow_run_info(flow_run_id="74-salt")


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
    with pytest.raises(ClientError, match="something went wrong"):
        client.set_flow_run_state(flow_run_id="74-salt", version=0, state=Pending())


def test_get_task_run_info(monkeypatch):
    response = {
        "getOrCreateTaskRun": {
            "task_run": {
                "id": "772bd9ee-40d7-479c-9839-4ab3a793cabd",
                "version": 0,
                "serialized_state": {
                    "type": "Pending",
                    "_result": {
                        "type": "SafeResult",
                        "value": "42",
                        "result_handler": {"type": "JSONResultHandler"},
                    },
                    "message": None,
                    "__version__": "0.3.3+310.gd19b9b7.dirty",
                    "cached_inputs": None,
                },
                "task": {"slug": "slug"},
            }
        }
    }

    post = MagicMock(
        return_value=MagicMock(json=MagicMock(return_value=dict(data=response)))
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

    with pytest.raises(ClientError, match="something went wrong"):
        client.get_task_run_info(
            flow_run_id="74-salt", task_id="72-salt", map_index=None
        )


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
    with pytest.raises(marshmallow.exceptions.ValidationError):
        client.set_task_run_state(
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

    with pytest.raises(ClientError, match="something went wrong"):
        client.set_task_run_state(task_run_id="76-salt", version=0, state=Pending())


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

    with pytest.raises(ClientError, match="something went wrong"):
        client.write_run_log(flow_run_id="1")
