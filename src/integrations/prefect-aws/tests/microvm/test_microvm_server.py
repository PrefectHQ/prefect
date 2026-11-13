import http.client
import json
import os
import socket
import threading
import time
from collections.abc import Iterator
from unittest.mock import create_autospec
from uuid import UUID

import pytest
from prefect_aws.microvm import entrypoint
from prefect_aws.microvm import server as server_module
from prefect_aws.microvm.payload import InvalidRunHookPayload, RunHookRequest
from prefect_aws.microvm.server import LifecycleHookHandler, LifecycleHookServer
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
    port: int,
    method: str,
    path: str,
    body: bytes | None = None,
    timeout: float = 10,
) -> http.client.HTTPResponse:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
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


def wait_for_outcome(
    server: LifecycleHookServer, timeout: float = 10
) -> RunHookRequest | InvalidRunHookPayload:
    outcomes: list[RunHookRequest | InvalidRunHookPayload] = []
    waiter = threading.Thread(
        target=lambda: outcomes.append(server.wait_for_run_request()), daemon=True
    )
    waiter.start()
    waiter.join(timeout)
    assert outcomes, "No `/run` outcome was submitted."
    return outcomes[0]


def post_with_headers(
    port: int, headers: dict[str, str], body: bytes = b"", timeout: float = 10
) -> int:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    connection.putrequest("POST", "/run", skip_accept_encoding=True)
    for name, value in headers.items():
        connection.putheader(name, value)
    connection.endheaders(body)
    response = connection.getresponse()
    connection.close()
    return response.status


@pytest.mark.parametrize(
    "headers, problem",
    [
        ({"Content-Length": "-1"}, "negative"),
        ({}, "no Content-Length"),
        ({"Content-Length": "ten"}, "not an integer"),
    ],
)
def test_bad_content_length_is_rejected_unread(
    server: LifecycleHookServer, headers: dict[str, str], problem: str
):
    status = post_with_headers(port_of(server), headers, run_body(), timeout=5)

    assert status == 400
    rejection = wait_for_outcome(server)
    assert isinstance(rejection, InvalidRunHookPayload)
    assert problem in str(rejection)


@pytest.mark.parametrize(
    "env",
    [
        {TEST_ENV_VAR: "from-run-hook\x00"},
        {TEST_ENV_VAR: "from-run-hook\ud800"},
    ],
)
def test_unsettable_env_is_rejected_before_it_is_applied(
    server: LifecycleHookServer, env: dict[str, str]
):
    response = request(port_of(server), "POST", "/run", run_body(env=env))

    assert response.status == 400
    assert os.environ[TEST_ENV_VAR] == "before-run-hook"
    assert isinstance(wait_for_outcome(server), InvalidRunHookPayload)


def test_lone_surrogate_run_hook_payload_is_rejected(server: LifecycleHookServer):
    body = json.dumps({"microvmId": "microvm-abc", "runHookPayload": "\ud800"})

    response = request(port_of(server), "POST", "/run", body.encode())

    assert response.status == 400
    rejection = wait_for_outcome(server)
    assert isinstance(rejection, InvalidRunHookPayload)
    assert "not valid UTF-8" in str(rejection)


def test_unexpected_failure_after_claiming_the_run_still_hands_off_a_rejection(
    server: LifecycleHookServer, monkeypatch: pytest.MonkeyPatch
):
    def fail_to_parse(body: bytes) -> RunHookRequest:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(server_module, "parse_run_hook_request", fail_to_parse)

    response = request(port_of(server), "POST", "/run", run_body())

    assert response.status == 500
    rejection = wait_for_outcome(server)
    assert isinstance(rejection, InvalidRunHookPayload)
    assert "RuntimeError" in str(rejection)


def test_stop_serving_waits_for_a_request_in_progress(server: LifecycleHookServer):
    body = run_body()
    connection = socket.create_connection(("127.0.0.1", port_of(server)), timeout=10)
    connection.sendall(
        b"POST /run HTTP/1.0\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\n\r\n"
        + body[:5]
    )
    deadline = time.monotonic() + 10
    while server._active_handlers == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    stopper = threading.Thread(target=server.stop_serving)
    stopper.start()

    stopper.join(timeout=0.5)
    assert stopper.is_alive()

    connection.sendall(body[5:])
    stopper.join(timeout=10)
    assert not stopper.is_alive()
    assert isinstance(wait_for_outcome(server), RunHookRequest)
    connection.close()


def test_a_stalled_run_request_times_out_and_hands_off_a_rejection(
    server: LifecycleHookServer, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(LifecycleHookHandler, "timeout", 0.2)
    body = run_body()
    connection = socket.create_connection(("127.0.0.1", port_of(server)), timeout=10)
    connection.sendall(
        b"POST /run HTTP/1.0\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\n\r\n"
        + body[:5]
    )

    rejection = wait_for_outcome(server)

    connection.close()
    assert isinstance(rejection, InvalidRunHookPayload)
    assert "TimeoutError" in str(rejection)
    assert os.environ[TEST_ENV_VAR] == "before-run-hook"


def test_hook_request_timeout_is_shorter_than_the_stop_serving_wait():
    assert (
        0 < LifecycleHookHandler.timeout < server_module.HANDLER_FINISH_TIMEOUT_SECONDS
    )


def test_other_hooks_return_200(server: LifecycleHookServer):
    response = request(
        port_of(server), "POST", "/aws/lambda-microvms/runtime/v1/suspend"
    )

    assert response.status == 200


def test_binding_the_wildcard_address_skips_the_reverse_dns_lookup(
    monkeypatch: pytest.MonkeyPatch,
):
    def fail_getfqdn(name: str = "") -> str:
        raise AssertionError(f"socket.getfqdn({name!r}) was called")

    monkeypatch.setattr(socket, "getfqdn", fail_getfqdn)

    hook_server = LifecycleHookServer(("0.0.0.0", 0))
    try:
        assert hook_server.server_name == "0.0.0.0"
        assert hook_server.server_port == hook_server.server_address[1]
        assert hook_server.server_port != 0
    finally:
        hook_server.server_close()


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
    port = free_port()
    hook_request_outcomes_during_run: list[str] = []

    def run_flow(payload: object) -> int:
        try:
            request(port, "GET", "/ready", timeout=1)
        except ConnectionRefusedError:
            hook_request_outcomes_during_run.append("refused")
        except TimeoutError:
            hook_request_outcomes_during_run.append("timed out")
        else:
            hook_request_outcomes_during_run.append("answered")
        return 0

    supervise = create_autospec(supervise_flow_run, side_effect=run_flow)
    monkeypatch.setattr(entrypoint, "supervise_flow_run", supervise)
    poster = post_when_listening(port, run_body())

    exit_code = entrypoint.main(port=port)

    poster.join(timeout=10)
    assert exit_code == 0
    supervise.assert_called_once()
    (payload,) = supervise.call_args.args
    assert payload.flow_run_id == FLOW_RUN_ID
    assert supervise.call_args.kwargs == {}
    # The server closed its listening socket before the flow run started.
    assert hook_request_outcomes_during_run == ["refused"]


def test_flow_code_can_bind_the_hook_port(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(TEST_ENV_VAR, "before-run-hook")
    port = free_port()
    bind_errors: list[OSError] = []

    def run_flow(payload: object) -> int:
        try:
            with socket.create_server(("0.0.0.0", port)):
                pass
        except OSError as exc:
            bind_errors.append(exc)
        return 0

    supervise = create_autospec(supervise_flow_run, side_effect=run_flow)
    monkeypatch.setattr(entrypoint, "supervise_flow_run", supervise)
    poster = post_when_listening(port, run_body())

    exit_code = entrypoint.main(port=port)

    poster.join(timeout=10)
    assert exit_code == 0
    supervise.assert_called_once()
    assert bind_errors == []


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


# Long enough that a stop which waits out the poll interval cannot pass the
# timing assertions, however slow the machine.
LONG_POLL_INTERVAL_SECONDS = 30


def serve_with_a_long_poll_interval(hook_server: LifecycleHookServer) -> None:
    hook_server.serve_forever(poll_interval=LONG_POLL_INTERVAL_SECONDS)


def test_stop_serving_does_not_wait_out_the_poll_interval():
    stop_times: list[float] = []
    for _ in range(5):
        hook_server = LifecycleHookServer(("127.0.0.1", 0))
        serving = threading.Thread(
            target=serve_with_a_long_poll_interval, args=(hook_server,), daemon=True
        )
        serving.start()
        # Lets the loop enter its first `select`, so the stop has to wake it.
        assert request(port_of(hook_server), "GET", "/ready").status == 200

        started = time.monotonic()
        hook_server.stop_serving()
        stop_times.append(time.monotonic() - started)

        serving.join(timeout=10)
        assert not serving.is_alive()
        hook_server.server_close()

    assert max(stop_times) < 5, stop_times


def test_stop_serving_wakes_the_loop_through_the_loopback_address(
    monkeypatch: pytest.MonkeyPatch,
):
    hook_server = LifecycleHookServer(("0.0.0.0", 0))
    serving = threading.Thread(target=hook_server.serve_forever, daemon=True)
    serving.start()
    connect = create_autospec(
        socket.create_connection, side_effect=socket.create_connection
    )
    monkeypatch.setattr(server_module.socket, "create_connection", connect)

    hook_server.stop_serving()

    serving.join(timeout=10)
    hook_server.server_close()
    assert connect.call_args_list[0].args[0] == ("127.0.0.1", port_of(hook_server))


def test_stop_serving_still_stops_when_the_wake_connection_fails(
    server: LifecycleHookServer, monkeypatch: pytest.MonkeyPatch
):
    connect = create_autospec(
        socket.create_connection, side_effect=ConnectionRefusedError()
    )
    monkeypatch.setattr(server_module.socket, "create_connection", connect)
    waker_errors: list[threading.ExceptHookArgs] = []
    monkeypatch.setattr(threading, "excepthook", waker_errors.append)

    started = time.monotonic()
    server.stop_serving()
    stop_time = time.monotonic() - started

    connect.assert_called()
    assert waker_errors == []
    # Without a wake, the loop notices the shutdown at its next 0.5 s poll.
    assert stop_time < 5


class LateShutdownServer(LifecycleHookServer):
    def shutdown(self) -> None:
        time.sleep(0.1)
        super().shutdown()


def test_stop_serving_wakes_the_loop_again_after_an_early_wake():
    hook_server = LateShutdownServer(("127.0.0.1", 0))
    serving = threading.Thread(
        target=serve_with_a_long_poll_interval, args=(hook_server,), daemon=True
    )
    serving.start()

    started = time.monotonic()
    hook_server.stop_serving()
    stop_time = time.monotonic() - started

    serving.join(timeout=10)
    hook_server.server_close()
    # A lost wake would leave the loop waiting out its poll interval.
    assert stop_time < 5, stop_time
