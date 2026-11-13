import http.client
import logging.config
import os
import socket
import sys
import threading
import time
from collections.abc import Callable
from typing import Any
from unittest.mock import call, create_autospec
from uuid import uuid4

import pytest
from prefect_aws.microvm import entrypoint, supervisor
from prefect_aws.microvm.payload import RunHookPayload
from prefect_aws.microvm.server import LifecycleHookServer
from prefect_aws.microvm.supervisor import report_crash, supervise_flow_run

from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import FlowRun, State
from prefect.context import refresh_global_settings_context
from prefect.settings import get_current_settings
from prefect.states import Running, StateType

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="The MicroVM entrypoint forks."),
    pytest.mark.filterwarnings(
        "ignore:This process .* is multi-threaded:DeprecationWarning"
    ),
    pytest.mark.usefixtures("api_from_environment"),
]

PostRunHook = Callable[..., threading.Thread]
real_getaddrinfo = socket.getaddrinfo
UNLOADABLE_SETTINGS_ENV = {"PREFECT_API_REQUEST_TIMEOUT": "not-a-number"}


def run_main(post_run_hook: PostRunHook, port: int, *post_args: Any) -> int:
    poster = post_run_hook(port, *post_args)
    exit_code = entrypoint.main(port=port)
    poster.join(timeout=10)
    return exit_code


def patch_supervise(
    monkeypatch: pytest.MonkeyPatch, side_effect: Callable[[RunHookPayload], int]
) -> Any:
    supervise = create_autospec(supervise_flow_run, side_effect=side_effect)
    monkeypatch.setattr(entrypoint, "supervise_flow_run", supervise)
    return supervise


def patch_getaddrinfo(monkeypatch: pytest.MonkeyPatch, **autospec_kwargs: Any) -> Any:
    getaddrinfo = create_autospec(socket.getaddrinfo, **autospec_kwargs)
    monkeypatch.setattr(entrypoint.socket, "getaddrinfo", getaddrinfo)
    return getaddrinfo


def register_unloadable_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Registers the variable with a loadable value, so that the value `/run`
    # writes is undone after the test.
    monkeypatch.setenv(
        "PREFECT_API_REQUEST_TIMEOUT", str(get_current_settings().api.request_timeout)
    )


class SlowToCloseHookServer(LifecycleHookServer):
    """A hook server whose `server_close` takes long enough to lose a race with `main`."""

    closed = False

    def server_close(self) -> None:
        time.sleep(0.5)
        super().server_close()
        SlowToCloseHookServer.closed = True


@pytest.fixture
def slow_to_close_hook_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SlowToCloseHookServer, "closed", False)
    monkeypatch.setattr(entrypoint, "LifecycleHookServer", SlowToCloseHookServer)


def test_warm_name_lookup_resolves_localhost(monkeypatch: pytest.MonkeyPatch):
    getaddrinfo = patch_getaddrinfo(monkeypatch, return_value=[])

    entrypoint.warm_name_lookup()

    getaddrinfo.assert_called_once_with("localhost", None, type=socket.SOCK_STREAM)


def test_warm_name_lookup_ignores_a_lookup_error(monkeypatch: pytest.MonkeyPatch):
    getaddrinfo = patch_getaddrinfo(
        monkeypatch, side_effect=socket.gaierror("no resolver")
    )

    entrypoint.warm_name_lookup()

    getaddrinfo.assert_called_once()


def test_hook_server_answers_ready_while_the_name_lookup_warm_up_is_blocked(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    release_warm_up = threading.Event()

    def block_for_localhost(host: Any, *args: Any, **kwargs: Any) -> Any:
        if host == "localhost":
            release_warm_up.wait()
            return []
        return real_getaddrinfo(host, *args, **kwargs)

    patch_getaddrinfo(monkeypatch, side_effect=block_for_localhost)
    patch_supervise(monkeypatch, lambda payload: 0)
    ready_answers_while_blocked: list[int] = []

    # Posts `/run` only after `/ready` is answered, because `/run` stops the server.
    def probe_ready_then_post_run() -> None:
        deadline = time.monotonic() + 5
        try:
            while time.monotonic() < deadline:
                connection = http.client.HTTPConnection(
                    "127.0.0.1", hook_port, timeout=1
                )
                try:
                    connection.request("GET", "/ready")
                    status = connection.getresponse().status
                except OSError:
                    time.sleep(0.05)
                    continue
                finally:
                    connection.close()
                if not release_warm_up.is_set():
                    ready_answers_while_blocked.append(status)
                return
        finally:
            release_warm_up.set()
            post_run_hook(hook_port, uuid4(), {})

    prober = threading.Thread(target=probe_ready_then_post_run, daemon=True)
    prober.start()
    try:
        exit_code = entrypoint.main(port=hook_port)
    finally:
        release_warm_up.set()
    prober.join(timeout=10)

    assert exit_code == 0
    assert ready_answers_while_blocked == [200]


def test_main_forks_only_after_the_name_lookup_warm_up_has_finished(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    release_warm_up = threading.Event()
    warm_up_finished = threading.Event()

    def slow_warm_up() -> None:
        release_warm_up.wait()
        warm_up_finished.set()

    def start_release_timer(api_url: str | None) -> None:
        release_timer = threading.Timer(0.2, release_warm_up.set)
        release_timer.daemon = True
        release_timer.start()

    monkeypatch.setattr(
        entrypoint,
        "warm_name_lookup",
        create_autospec(entrypoint.warm_name_lookup, side_effect=slow_warm_up),
    )
    # The 0.2 second wait starts at `/run`, so that only the join before the
    # fork can account for it.
    monkeypatch.setattr(
        entrypoint,
        "start_api_host_lookup",
        create_autospec(
            entrypoint.start_api_host_lookup, side_effect=start_release_timer
        ),
    )
    warm_up_finished_at_supervise: list[bool] = []

    def run_flow(payload: RunHookPayload) -> int:
        warm_up_finished_at_supervise.append(warm_up_finished.is_set())
        return 0

    patch_supervise(monkeypatch, run_flow)
    try:
        exit_code = run_main(post_run_hook, hook_port, uuid4(), {})
    finally:
        release_warm_up.set()

    assert exit_code == 0
    assert warm_up_finished_at_supervise == [True]


def test_main_runs_the_flow_run_when_localhost_does_not_resolve(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    def fail_for_localhost(host: Any, *args: Any, **kwargs: Any) -> Any:
        if host == "localhost":
            raise socket.gaierror("no resolver")
        return real_getaddrinfo(host, *args, **kwargs)

    getaddrinfo = patch_getaddrinfo(monkeypatch, side_effect=fail_for_localhost)
    supervise = patch_supervise(monkeypatch, lambda payload: 0)

    assert run_main(post_run_hook, hook_port, uuid4(), {}) == 0

    assert call("localhost", None, type=socket.SOCK_STREAM) in (
        getaddrinfo.call_args_list
    )
    supervise.assert_called_once()


@pytest.mark.parametrize(
    "api_url, host, port",
    [
        ("https://api.example.com/api", "api.example.com", 443),
        ("http://api.example.com/api", "api.example.com", 80),
        ("http://127.0.0.1:4200/api", "127.0.0.1", 4200),
    ],
)
def test_api_host_lookup_resolves_the_host_and_port_of_the_url(
    monkeypatch: pytest.MonkeyPatch, api_url: str, host: str, port: int
):
    getaddrinfo = patch_getaddrinfo(monkeypatch, return_value=[])

    lookup = entrypoint.start_api_host_lookup(api_url)

    assert lookup is not None
    lookup.join(timeout=5)
    assert not lookup.is_alive()
    assert lookup.daemon
    getaddrinfo.assert_called_once_with(host, port, type=socket.SOCK_STREAM)


@pytest.mark.parametrize(
    "api_url",
    [
        None,
        "",
        "ftp://api.example.com/api",
        "http:///api",
        "api.example.com/api",
        "http://api.example.com:99999/api",
        "http://[::1/api",
    ],
    ids=["none", "empty", "ftp", "no-hostname", "no-scheme", "bad-port", "bad-ipv6"],
)
def test_api_host_lookup_is_not_started_for_an_unusable_url(
    monkeypatch: pytest.MonkeyPatch, api_url: str | None
):
    getaddrinfo = patch_getaddrinfo(monkeypatch, return_value=[])

    assert entrypoint.start_api_host_lookup(api_url) is None

    getaddrinfo.assert_not_called()


def test_api_host_lookup_error_stays_in_the_lookup_thread(
    monkeypatch: pytest.MonkeyPatch,
):
    getaddrinfo = patch_getaddrinfo(
        monkeypatch, side_effect=socket.gaierror("no resolver")
    )
    uncaught_thread_errors: list[threading.ExceptHookArgs] = []
    monkeypatch.setattr(threading, "excepthook", uncaught_thread_errors.append)

    lookup = entrypoint.start_api_host_lookup("https://api.example.com/api")

    assert lookup is not None
    lookup.join(timeout=5)
    getaddrinfo.assert_called_once()
    assert uncaught_thread_errors == []


def test_api_host_lookup_of_an_over_long_label_stays_in_the_lookup_thread(
    monkeypatch: pytest.MonkeyPatch,
):
    # The hostname fails IDNA encoding inside `getaddrinfo`, before any query.
    getaddrinfo = patch_getaddrinfo(monkeypatch, side_effect=real_getaddrinfo)
    uncaught_thread_errors: list[threading.ExceptHookArgs] = []
    monkeypatch.setattr(threading, "excepthook", uncaught_thread_errors.append)

    lookup = entrypoint.start_api_host_lookup(f"https://{'a' * 64}.example.com/api")

    assert lookup is not None
    lookup.join(timeout=5)
    getaddrinfo.assert_called_once()
    assert uncaught_thread_errors == []


def test_main_looks_up_the_api_host_from_the_run_environment(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    api_url = "http://api.example.com:4200/api"
    # Registered so that the value `/run` writes is undone after the test.
    monkeypatch.setenv("PREFECT_API_URL", "")
    monkeypatch.setattr(
        entrypoint,
        "refresh_global_settings_context",
        create_autospec(refresh_global_settings_context),
    )
    start_lookup = create_autospec(entrypoint.start_api_host_lookup, return_value=None)
    monkeypatch.setattr(entrypoint, "start_api_host_lookup", start_lookup)
    patch_supervise(monkeypatch, lambda payload: 0)

    assert (
        run_main(post_run_hook, hook_port, uuid4(), {"PREFECT_API_URL": api_url}) == 0
    )

    start_lookup.assert_called_once_with(api_url)


def test_main_forks_only_after_a_slow_api_host_lookup_has_finished(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    release_lookup = threading.Event()
    slow_lookup = threading.Thread(target=release_lookup.wait, daemon=True)
    release_timer = threading.Timer(0.2, release_lookup.set)
    release_timer.daemon = True

    def start_slow_lookup(api_url: str | None) -> threading.Thread:
        slow_lookup.start()
        release_timer.start()
        return slow_lookup

    monkeypatch.setattr(
        entrypoint,
        "start_api_host_lookup",
        create_autospec(
            entrypoint.start_api_host_lookup, side_effect=start_slow_lookup
        ),
    )
    lookup_alive_at_supervise: list[bool] = []

    def run_flow(payload: RunHookPayload) -> int:
        lookup_alive_at_supervise.append(slow_lookup.is_alive())
        return 0

    patch_supervise(monkeypatch, run_flow)
    try:
        exit_code = run_main(post_run_hook, hook_port, uuid4(), {})
    finally:
        release_lookup.set()

    assert exit_code == 0
    assert lookup_alive_at_supervise == [False]


def test_main_refreshes_settings_before_the_fork_and_leaves_logging_to_the_child(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    events: list[str] = []
    monkeypatch.setattr(
        entrypoint,
        "refresh_global_settings_context",
        create_autospec(
            refresh_global_settings_context,
            side_effect=lambda: events.append("settings refreshed"),
        ),
    )
    monkeypatch.setattr(
        logging.config,
        "dictConfig",
        create_autospec(
            logging.config.dictConfig,
            side_effect=lambda config: events.append("logging configured"),
        ),
    )

    def run_flow(payload: RunHookPayload) -> int:
        events.append("flow run forked")
        return 0

    patch_supervise(monkeypatch, run_flow)

    assert run_main(post_run_hook, hook_port, uuid4(), {}) == 0

    assert events == ["settings refreshed", "flow run forked"]


def test_child_sets_up_logging_first_and_without_refreshing_settings(
    monkeypatch: pytest.MonkeyPatch,
):
    calls_read, calls_write = os.pipe()

    def report_call(name: str) -> Callable[..., None]:
        def record(*args: Any, **kwargs: Any) -> None:
            os.write(calls_write, f"{name} {args} {kwargs}\n".encode())

        return record

    monkeypatch.setattr(
        supervisor,
        "refresh_global_settings_context",
        report_call("refresh_global_settings_context"),
    )
    monkeypatch.setattr(supervisor, "setup_logging", report_call("setup_logging"))
    monkeypatch.setattr(
        supervisor,
        "_make_preferred_oom_victim",
        report_call("_make_preferred_oom_victim"),
    )
    monkeypatch.setattr(supervisor, "execute_flow_run", lambda payload: None)
    try:
        exit_code = supervisor.supervise_flow_run(
            RunHookPayload(v=1, flow_run_id=uuid4())
        )
    finally:
        os.close(calls_write)
    with os.fdopen(calls_read) as calls:
        child_calls = calls.read().splitlines()

    assert exit_code == 0
    assert child_calls == [
        "setup_logging () {'incremental': False}",
        "_make_preferred_oom_victim () {}",
    ]


@pytest.mark.usefixtures("slow_to_close_hook_server")
def test_hook_server_is_closed_before_the_flow_run_is_forked(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    closed_at_fork: list[bool] = []

    def run_flow(payload: RunHookPayload) -> int:
        closed_at_fork.append(SlowToCloseHookServer.closed)
        return 0

    patch_supervise(monkeypatch, run_flow)

    assert run_main(post_run_hook, hook_port, uuid4(), {}) == 0

    assert closed_at_fork == [True]


@pytest.mark.usefixtures("slow_to_close_hook_server")
def test_settings_failure_moves_the_flow_run_to_crashed(
    monkeypatch: pytest.MonkeyPatch,
    post_run_hook: PostRunHook,
    hook_port: int,
    flow_run_in: Callable[[State], FlowRun],
):
    flow_run = flow_run_in(Running())
    register_unloadable_settings_env(monkeypatch)
    supervise = patch_supervise(monkeypatch, lambda payload: 0)

    exit_code = run_main(post_run_hook, hook_port, flow_run.id, UNLOADABLE_SETTINGS_ENV)

    assert exit_code == 1
    assert SlowToCloseHookServer.closed
    supervise.assert_not_called()
    with get_client(sync_client=True) as client:
        state = client.read_flow_run(flow_run.id).state
    assert state is not None
    assert state.type == StateType.CRASHED
    assert state.message == "Flow run process could not load its settings."


def test_settings_failure_exits_1_when_the_crash_report_fails(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    register_unloadable_settings_env(monkeypatch)
    report = create_autospec(report_crash, side_effect=RuntimeError("no API"))
    monkeypatch.setattr(entrypoint, "report_crash", report)
    supervise = patch_supervise(monkeypatch, lambda payload: 0)
    flow_run_id = uuid4()

    assert run_main(post_run_hook, hook_port, flow_run_id, UNLOADABLE_SETTINGS_ENV) == 1

    report.assert_called_once_with(flow_run_id, "could not load its settings")
    supervise.assert_not_called()


def test_invalid_run_request_exits_1_without_a_lookup_or_a_settings_refresh(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    refresh = create_autospec(refresh_global_settings_context)
    start_lookup = create_autospec(entrypoint.start_api_host_lookup)
    monkeypatch.setattr(entrypoint, "refresh_global_settings_context", refresh)
    monkeypatch.setattr(entrypoint, "start_api_host_lookup", start_lookup)
    supervise = patch_supervise(monkeypatch, lambda payload: 0)

    assert run_main(post_run_hook, hook_port, uuid4(), {}, 99) == 1

    start_lookup.assert_not_called()
    refresh.assert_not_called()
    supervise.assert_not_called()
