import datetime
import json
import os
import tempfile
import uuid
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


def test_client_posts_to_api_server(patch_post):
    post = patch_post(dict(success=True))

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.post("/foo/bar")
    assert result == {"success": True}
    assert post.called
    assert post.call_args[0][0] == "http://my-cloud.foo/foo/bar"


def test_version_header(monkeypatch):
    get = MagicMock()
    session = MagicMock()
    session.return_value.get = get
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    client.get("/foo/bar")
    assert get.call_args[1]["headers"]["X-PREFECT-CORE-VERSION"] == str(
        prefect.__version__
    )


def test_version_header_cant_be_overridden(monkeypatch):
    get = MagicMock()
    session = MagicMock()
    session.return_value.get = get
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    client.get("/foo/bar", headers={"X-PREFECT-CORE-VERSION": "-1"})
    assert get.call_args[1]["headers"]["X-PREFECT-CORE-VERSION"] == str(
        prefect.__version__
    )


def test_client_attached_headers(monkeypatch, cloud_api):
    get = MagicMock()
    session = MagicMock()
    session.return_value.get = get
    monkeypatch.setattr("requests.Session", session)
    with set_temporary_config({"cloud.auth_token": "secret_token"}):
        client = Client()
        assert client._attached_headers == {}

        client.attach_headers({"1": "1"})
        assert client._attached_headers == {"1": "1"}

        client.attach_headers({"2": "2"})
        assert client._attached_headers == {"1": "1", "2": "2"}


def test_client_posts_graphql_to_api_server(patch_post):
    post = patch_post(dict(data=dict(success=True)))

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.graphql("{projects{name}}")
    assert result.data == {"success": True}
    assert post.called
    assert post.call_args[0][0] == "http://my-cloud.foo"


## test actual mutation and query handling
def test_graphql_errors_get_raised(patch_post):
    patch_post(dict(data="42", errors="GraphQL issue!"))

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    with pytest.raises(ClientError, match="GraphQL issue!"):
        client.graphql("query: {}")


def test_client_register_raises_if_required_param_isnt_scheduled(
    patch_post, monkeypatch, tmpdir
):
    response = {
        "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
    }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    a = prefect.schedules.clocks.DatesClock(
        [pendulum.now("UTC").add(seconds=0.1)], parameter_defaults=dict(x=1)
    )
    b = prefect.schedules.clocks.DatesClock(
        [pendulum.now("UTC").add(seconds=0.25)], parameter_defaults=dict(y=2)
    )

    x = prefect.Parameter("x", required=True)

    flow = prefect.Flow(
        "test", schedule=prefect.schedules.Schedule(clocks=[a, b]), tasks=[x]
    )
    flow.storage = prefect.environments.storage.Local(tmpdir)
    flow.result = flow.storage.result

    with pytest.raises(
        ClientError,
        match="Flows with required parameters can not be scheduled automatically",
    ):
        flow_id = client.register(
            flow,
            project_name="my-default-project",
            compressed=False,
            version_group_id=str(uuid.uuid4()),
        )


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_doesnt_raise_for_scheduled_params(
    patch_post, compressed, monkeypatch, tmpdir
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    a = prefect.schedules.clocks.DatesClock(
        [pendulum.now("UTC").add(seconds=0.1)], parameter_defaults=dict(x=1)
    )
    b = prefect.schedules.clocks.DatesClock(
        [pendulum.now("UTC").add(seconds=0.25)], parameter_defaults=dict(x=2, y=5)
    )

    x = prefect.Parameter("x", required=True)
    y = prefect.Parameter("y", default=1)

    flow = prefect.Flow(
        "test", schedule=prefect.schedules.Schedule(clocks=[a, b]), tasks=[x, y]
    )
    flow.storage = prefect.environments.storage.Local(tmpdir)
    flow.result = flow.storage.result

    flow_id = client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        version_group_id=str(uuid.uuid4()),
    )
    assert flow_id == "long-id"


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register(patch_post, compressed, monkeypatch, tmpdir):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    flow = prefect.Flow(name="test", storage=prefect.environments.storage.Local(tmpdir))
    flow.result = flow.storage.result

    flow_id = client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        version_group_id=str(uuid.uuid4()),
    )
    assert flow_id == "long-id"


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_raises_for_keyed_flows_with_no_result(
    patch_post, compressed, monkeypatch, tmpdir
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    @prefect.task
    def a(x):
        pass

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    with prefect.Flow(
        name="test", storage=prefect.environments.storage.Local(tmpdir)
    ) as flow:
        a(prefect.Task())

    flow.result = None

    with pytest.warns(UserWarning, match="result handler"):
        flow_id = client.register(
            flow,
            project_name="my-default-project",
            compressed=compressed,
            version_group_id=str(uuid.uuid4()),
        )


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_doesnt_raise_if_no_keyed_edges(
    patch_post, compressed, monkeypatch, tmpdir
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    flow = prefect.Flow(name="test", storage=prefect.environments.storage.Local(tmpdir))
    flow.result = None

    flow_id = client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        version_group_id=str(uuid.uuid4()),
    )
    assert flow_id == "long-id"


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_builds_flow(patch_post, compressed, monkeypatch, tmpdir):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    post = patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    flow = prefect.Flow(name="test", storage=prefect.environments.storage.Local(tmpdir))
    flow.result = flow.storage.result

    flow_id = client.register(
        flow, project_name="my-default-project", compressed=compressed
    )

    ## extract POST info
    if compressed:
        serialized_flow = decompress(
            json.loads(post.call_args[1]["json"]["variables"])["input"][
                "serialized_flow"
            ]
        )
    else:
        serialized_flow = json.loads(post.call_args[1]["json"]["variables"])["input"][
            "serialized_flow"
        ]
    assert serialized_flow["storage"] is not None


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_optionally_avoids_building_flow(
    patch_post, compressed, monkeypatch
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    post = patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    flow = prefect.Flow(name="test")
    flow.result = prefect.engine.result.Result()

    flow_id = client.register(
        flow, project_name="my-default-project", build=False, compressed=compressed
    )

    ## extract POST info
    if compressed:
        serialized_flow = decompress(
            json.loads(post.call_args[1]["json"]["variables"])["input"][
                "serialized_flow"
            ]
        )
    else:
        serialized_flow = json.loads(post.call_args[1]["json"]["variables"])["input"][
            "serialized_flow"
        ]
    assert serialized_flow["storage"] is None


def test_client_register_with_bad_proj_name(patch_post, monkeypatch, cloud_api):
    patch_post({"data": {"project": []}})

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config({"cloud.auth_token": "secret_token"}):
        client = Client()
    flow = prefect.Flow(name="test")
    flow.result = prefect.engine.result.Result()

    with pytest.raises(ValueError) as exc:
        flow_id = client.register(flow, project_name="my-default-project")
    assert "not found" in str(exc.value)
    assert "client.create_project" in str(exc.value)


def test_client_register_with_flow_that_cant_be_deserialized(patch_post, monkeypatch):
    patch_post({"data": {"project": [{"id": "proj-id"}]}})

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    task = prefect.Task()
    # we add a max_retries value to the task without a corresponding retry_delay; this will fail at deserialization
    task.max_retries = 3
    flow = prefect.Flow(name="test", tasks=[task])
    flow.result = prefect.engine.result.Result()

    with pytest.raises(
        ValueError,
        match=(
            "(Flow could not be deserialized).*"
            "(`retry_delay` must be provided if max_retries > 0)"
        ),
    ) as exc:
        client.register(flow, project_name="my-default-project", build=False)


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_flow_id_output(
    patch_post, compressed, monkeypatch, capsys, cloud_api, tmpdir
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    flow = prefect.Flow(name="test", storage=prefect.environments.storage.Local(tmpdir))
    flow.result = flow.storage.result

    flow_id = client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        version_group_id=str(uuid.uuid4()),
    )
    assert flow_id == "long-id"

    captured = capsys.readouterr()
    assert "Flow: https://cloud.prefect.io/tslug/flow/long-id\n" in captured.out


@pytest.mark.parametrize("compressed", [True, False])
def test_client_register_flow_id_no_output(
    patch_post, compressed, monkeypatch, capsys, tmpdir
):
    if compressed:
        response = {
            "data": {
                "project": [{"id": "proj-id"}],
                "create_flow_from_compressed_string": {"id": "long-id"},
            }
        }
    else:
        response = {
            "data": {"project": [{"id": "proj-id"}], "create_flow": {"id": "long-id"}}
        }
    patch_post(response)

    monkeypatch.setattr(
        "prefect.client.Client.get_default_tenant_slug", MagicMock(return_value="tslug")
    )

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    flow = prefect.Flow(name="test", storage=prefect.environments.storage.Local(tmpdir))
    flow.result = flow.storage.result

    flow_id = client.register(
        flow,
        project_name="my-default-project",
        compressed=compressed,
        version_group_id=str(uuid.uuid4()),
        no_url=True,
    )
    assert flow_id == "long-id"

    captured = capsys.readouterr()
    assert captured.out == "Result check: OK\n"


def test_get_flow_run_info(patch_post):
    response = {
        "flow_run_by_pk": {
            "id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "flow_id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "name": "flow-run-name",
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
    post = patch_post(dict(data=response))

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
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


def test_get_flow_run_info_with_nontrivial_payloads(patch_post):
    response = {
        "flow_run_by_pk": {
            "id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "flow_id": "da344768-5f5d-4eaf-9bca-83815617f713",
            "name": "flow-run-name",
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
    post = patch_post(dict(data=response))

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
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


def test_get_flow_run_info_raises_informative_error(patch_post):
    post = patch_post(dict(data={"flow_run_by_pk": None}))
    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    with pytest.raises(ClientError, match="not found"):
        client.get_flow_run_info(flow_run_id="74-salt")


def test_set_flow_run_state(patch_post):
    response = {"data": {"set_flow_run_state": {"id": 1}}}
    post = patch_post(response)

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.set_flow_run_state(
        flow_run_id="74-salt", version=0, state=Pending()
    )
    assert result is None


def test_set_flow_run_state_with_error(patch_post):
    response = {
        "data": {"set_flow_run_state": None},
        "errors": [{"message": "something went wrong"}],
    }
    post = patch_post(response)

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    with pytest.raises(ClientError, match="something went wrong"):
        client.set_flow_run_state(flow_run_id="74-salt", version=0, state=Pending())


def test_get_task_run_info(patch_posts):
    mutation_resp = {
        "get_or_create_task_run": {"id": "772bd9ee-40d7-479c-9839-4ab3a793cabd",}
    }
    query_resp = {
        "task_run_by_pk": {
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

    post = patch_posts([dict(data=mutation_resp), dict(data=query_resp)])
    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
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


def test_get_task_run_info_with_error(patch_post):
    response = {
        "data": {"get_or_create_task_run": None},
        "errors": [{"message": "something went wrong"}],
    }
    post = patch_post(response)

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    with pytest.raises(ClientError, match="something went wrong"):
        client.get_task_run_info(
            flow_run_id="74-salt", task_id="72-salt", map_index=None
        )


def test_set_task_run_state(patch_post):
    response = {"data": {"set_task_run_states": {"states": [{"status": "SUCCESS"}]}}}
    post = patch_post(response)
    state = Pending()

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.set_task_run_state(task_run_id="76-salt", version=0, state=state)

    assert result is state


def test_set_task_run_state_responds_to_status(patch_post):
    response = {"data": {"set_task_run_states": {"states": [{"status": "QUEUED"}]}}}
    post = patch_post(response)
    state = Pending()

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
    result = client.set_task_run_state(task_run_id="76-salt", version=0, state=state)

    assert result.is_queued()
    assert result.state is None  # caller should set this


def test_set_task_run_state_responds_to_config_when_queued(patch_post):
    response = {
        "data": {
            "set_task_run_states": {
                "states": [{"status": "QUEUED", "message": "hol up"}]
            }
        }
    }
    post = patch_post(response)
    state = Pending()

    with set_temporary_config(
        {
            "cloud.api": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "cloud.queue_interval": 750,
        }
    ):
        client = Client()
        result = client.set_task_run_state(
            task_run_id="76-salt", version=0, state=state
        )

    assert result.is_queued()
    assert result.state is None  # caller should set this
    assert result.message == "hol up"
    assert result.start_time >= pendulum.now("UTC").add(seconds=749)


def test_set_task_run_state_serializes(patch_post):
    response = {"data": {"set_task_run_states": {"states": [{"status": "SUCCESS"}]}}}
    post = patch_post(response)

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    res = SafeResult(lambda: None, result_handler=None)
    with pytest.raises(marshmallow.exceptions.ValidationError):
        client.set_task_run_state(
            task_run_id="76-salt", version=0, state=Pending(result=res)
        )


def test_set_task_run_state_with_error(patch_post):
    response = {
        "data": {"set_task_run_states": None},
        "errors": [{"message": "something went wrong"}],
    }
    post = patch_post(response)

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    with pytest.raises(ClientError, match="something went wrong"):
        client.set_task_run_state(task_run_id="76-salt", version=0, state=Pending())


def test_create_flow_run_requires_flow_id_or_version_group_id():
    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    with pytest.raises(
        ValueError, match="flow_id or version_group_id must be provided"
    ):
        client.create_flow_run()


@pytest.mark.parametrize("kwargs", [dict(flow_id="blah"), dict(version_group_id="cat")])
def test_create_flow_run_with_input(patch_post, kwargs):
    response = {
        "data": {"create_flow_run": {"id": "FOO"}},
    }
    post = patch_post(response)

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

    assert client.create_flow_run(**kwargs) == "FOO"


def test_get_default_tenant_slug_as_user(patch_post):
    response = {
        "data": {"user": [{"default_membership": {"tenant": {"slug": "tslug"}}}]}
    }

    patch_post(response)

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
        slug = client.get_default_tenant_slug()

        assert slug == "tslug"


def test_get_default_tenant_slug_not_as_user(patch_post):
    response = {"data": {"tenant": [{"slug": "tslug"}]}}

    patch_post(response)

    with set_temporary_config(
        {"cloud.api": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        client = Client()
        slug = client.get_default_tenant_slug(as_user=False)

        assert slug == "tslug"


def test_get_cloud_url_as_user(patch_post, cloud_api):
    response = {
        "data": {"user": [{"default_membership": {"tenant": {"slug": "tslug"}}}]}
    }

    patch_post(response)

    with set_temporary_config(
        {"cloud.api": "http://api.prefect.io", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

        url = client.get_cloud_url(subdirectory="flow", id="id")
        assert url == "http://cloud.prefect.io/tslug/flow/id"

        url = client.get_cloud_url(subdirectory="flow-run", id="id2")
        assert url == "http://cloud.prefect.io/tslug/flow-run/id2"


def test_get_cloud_url_not_as_user(patch_post, cloud_api):
    response = {"data": {"tenant": [{"slug": "tslug"}]}}

    patch_post(response)

    with set_temporary_config(
        {"cloud.api": "http://api.prefect.io", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

        url = client.get_cloud_url(subdirectory="flow", id="id", as_user=False)
        assert url == "http://cloud.prefect.io/tslug/flow/id"

        url = client.get_cloud_url(subdirectory="flow-run", id="id2", as_user=False)
        assert url == "http://cloud.prefect.io/tslug/flow-run/id2"


def test_get_cloud_url_different_regex(patch_post, cloud_api):
    response = {
        "data": {"user": [{"default_membership": {"tenant": {"slug": "tslug"}}}]}
    }

    patch_post(response)

    with set_temporary_config(
        {"cloud.api": "http://api-hello.prefect.io", "cloud.auth_token": "secret_token"}
    ):
        client = Client()

        url = client.get_cloud_url(subdirectory="flow", id="id")
        assert url == "http://hello.prefect.io/tslug/flow/id"

        url = client.get_cloud_url(subdirectory="flow-run", id="id2")
        assert url == "http://hello.prefect.io/tslug/flow-run/id2"


def test_register_agent(patch_post, cloud_api):
    response = {"data": {"register_agent": {"id": "ID"}}}

    patch_post(response)

    with set_temporary_config({"cloud.auth_token": "secret_token"}):
        client = Client()

        agent_id = client.register_agent(
            agent_type="type", name="name", labels=["1", "2"]
        )
        assert agent_id == "ID"


def test_register_agent_raises_error(patch_post, cloud_api):
    response = {"data": {"register_agent": {"id": None}}}

    patch_post(response)

    with set_temporary_config({"cloud.auth_token": "secret_token"}):
        client = Client()

        with pytest.raises(ValueError):
            agent_id = client.register_agent(
                agent_type="type", name="name", labels=["1", "2"]
            )
