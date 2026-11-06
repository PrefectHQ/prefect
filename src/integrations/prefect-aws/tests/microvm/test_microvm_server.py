import http.client
import json
import os
import socket
import threading
from collections.abc import Iterator
from unittest.mock import create_autospec
from uuid import UUID

import pytest
from prefect_aws.microvm import entrypoint
from prefect_aws.microvm.payload import InvalidRunHookPayload, RunHookRequest
from prefect_aws.microvm.server import LifecycleHookServer
from prefect_aws.microvm.supervisor import supervise_flow_run

FLOW_RUN_ID = UUID("0b6f3c8e-2d6a-4c1e-8f3b-7a9d5e4c2b10")
TEST_ENV_VAR = "PREFECT_AWS_MICROVM_TEST_VALUE"


def run_body(**payload_overrides: object) -> bytes:
    payload: dict[str, object] = {
        "v": 1,
        "flow_run_id": str(FLOW_RUN_ID),
        "env": {TEST_ENV_VAR: "from-run-hook"},
        "entrypoint": None,
        "working_dir": None,
    }
    payload.update(payload_overrides)
    return json.dumps(
        {"microvmId": "microvm-abc", "runHookPayload": json.dumps(payload)}
    ).encode()


def request(
    port: int, method: str, path: str, body: bytes | None = None
) -> http.client.HTTPResponse:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request(method, path, body=body)
    response = connection.getresponse()
    response.read()
    connection.close()
    return response


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[LifecycleHookServer]:
    # Registers the variable with monkeypatch so the value `/run` writes is undone.
    monkeypatch.setenv(TEST_ENV_VAR, "before-run-hook")
    hook_server = LifecycleHookServer(("127.0.0.1", 0))
    thread = threading.Thread(target=hook_server.serve_forever, daemon=True)
    thread.start()
    yield hook_server
    hook_server.shutdown()
    hook_server.server_close()


def port_of(server: LifecycleHookServer) -> int:
    return server.server_address[1]


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("path", ["/ready", "/aws/lambda-microvms/runtime/v1/ready"])
def test_ready_returns_200(server: LifecycleHookServer, method: str, path: str):
    assert request(port_of(server), method, path).status == 200


@pytest.mark.parametrize("path", ["/run", "/aws/lambda-microvms/runtime/v1/run"])
def test_run_applies_env_returns_200_and_hands_off_the_request(
    server: LifecycleHookServer, path: str
):
    response = request(port_of(server), "POST", path, run_body())

    assert response.status == 200
    assert os.environ[TEST_ENV_VAR] == "from-run-hook"
    run_request = server.wait_for_run_request()
    assert isinstance(run_request, RunHookRequest)
    assert run_request.microvm_id == "microvm-abc"
    assert run_request.payload.flow_run_id == FLOW_RUN_ID


def test_second_run_is_refused(server: LifecycleHookServer):
    assert request(port_of(server), "POST", "/run", run_body()).status == 200
    second = request(
        port_of(server),
        "POST",
        "/run",
        run_body(env={TEST_ENV_VAR: "from-second-run-hook"}),
    )

    assert second.status == 409
    assert os.environ[TEST_ENV_VAR] == "from-run-hook"


def test_invalid_run_returns_400_and_hands_off_the_error(server: LifecycleHookServer):
    response = request(port_of(server), "POST", "/run", run_body(v=2))

    assert response.status == 400
    assert os.environ[TEST_ENV_VAR] == "before-run-hook"
    rejection = server.wait_for_run_request()
    assert isinstance(rejection, InvalidRunHookPayload)
    assert "version 2" in str(rejection)


def test_oversized_request_body_is_rejected_unread(server: LifecycleHookServer):
    connection = http.client.HTTPConnection("127.0.0.1", port_of(server), timeout=10)
    connection.putrequest("POST", "/run")
    connection.putheader("Content-Length", str(2 * 1024 * 1024))
    connection.endheaders()
    response = connection.getresponse()
    connection.close()

    assert response.status == 400
    assert isinstance(server.wait_for_run_request(), InvalidRunHookPayload)


def test_other_hooks_return_200(server: LifecycleHookServer):
    response = request(
        port_of(server), "POST", "/aws/lambda-microvms/runtime/v1/suspend"
    )

    assert response.status == 200


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def post_when_listening(port: int, body: bytes) -> threading.Thread:
    def post() -> None:
        for _ in range(100):
            try:
                request(port, "POST", "/run", body)
                return
            except ConnectionRefusedError:
                threading.Event().wait(0.05)

    thread = threading.Thread(target=post, daemon=True)
    thread.start()
    return thread


def test_main_supervises_the_flow_run_from_the_run_request(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(TEST_ENV_VAR, "before-run-hook")
    supervise = create_autospec(supervise_flow_run, return_value=0)
    monkeypatch.setattr(entrypoint, "supervise_flow_run", supervise)
    port = free_port()
    poster = post_when_listening(port, run_body())

    exit_code = entrypoint.main(port=port)

    poster.join(timeout=10)
    assert exit_code == 0
    supervise.assert_called_once()
    (payload,) = supervise.call_args.args
    assert payload.flow_run_id == FLOW_RUN_ID


def test_main_exits_1_without_running_anything_on_an_invalid_payload(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(TEST_ENV_VAR, "before-run-hook")
    supervise = create_autospec(supervise_flow_run, return_value=0)
    monkeypatch.setattr(entrypoint, "supervise_flow_run", supervise)
    port = free_port()
    poster = post_when_listening(port, run_body(v=99))

    exit_code = entrypoint.main(port=port)

    poster.join(timeout=10)
    assert exit_code == 1
    supervise.assert_not_called()
