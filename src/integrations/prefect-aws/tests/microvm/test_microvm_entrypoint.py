import http.client
import logging.config
import os
import signal
import socket
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import call, create_autospec
from uuid import uuid4

import pytest
from prefect_aws.microvm import entrypoint, supervisor
from prefect_aws.microvm.payload import (
    InvalidRunHookPayload,
    RunHookPayload,
    RunHookRequest,
)
from prefect_aws.microvm.server import LifecycleHookHandler, LifecycleHookServer
from prefect_aws.microvm.supervisor import report_crash, supervise_flow_run

from prefect.client.orchestration import SyncPrefectClient, get_client
from prefect.client.schemas.objects import FlowRun, State
from prefect.context import refresh_global_settings_context
from prefect.settings import get_current_settings
from prefect.states import Crashed, Running, StateType

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
    def run_flow(
        payload: RunHookPayload, restored_signal_mask: set[signal.Signals] | None = None
    ) -> int:
        return side_effect(payload)

    supervise = create_autospec(supervise_flow_run, side_effect=run_flow)
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


LOCALHOST_HOSTS_FILE = "127.0.0.1\tlocalhost\n::1\tlocalhost ip6-localhost\n"
FILES_FIRST_NSSWITCH_CONF = "passwd: files\nhosts: files dns\n"
NUMERIC_LOOKUP = call("127.0.0.1", None, type=socket.SOCK_STREAM)
LOCALHOST_LOOKUP = call("localhost", None, type=socket.SOCK_STREAM)


def use_name_service_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    hosts_file: str | bytes | None,
    nsswitch_conf: str | bytes | None,
) -> None:
    for attribute, name, content in [
        ("HOSTS_FILE_PATH", "hosts", hosts_file),
        ("NSSWITCH_CONF_PATH", "nsswitch.conf", nsswitch_conf),
    ]:
        path = tmp_path / name
        if isinstance(content, str):
            path.write_text(content)
        elif isinstance(content, bytes):
            path.write_bytes(content)
        monkeypatch.setattr(entrypoint, attribute, path)


def test_warm_name_lookup_looks_up_localhost_when_the_hosts_file_answers_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    use_name_service_files(
        monkeypatch, tmp_path, LOCALHOST_HOSTS_FILE, FILES_FIRST_NSSWITCH_CONF
    )
    getaddrinfo = patch_getaddrinfo(monkeypatch, return_value=[])

    entrypoint.warm_name_lookup()

    assert getaddrinfo.call_args_list == [NUMERIC_LOOKUP, LOCALHOST_LOOKUP]


@pytest.mark.parametrize(
    "hosts_file, nsswitch_conf",
    [
        ("127.0.0.1\tmicrovm\n", FILES_FIRST_NSSWITCH_CONF),
        ("# 127.0.0.1 localhost\n", FILES_FIRST_NSSWITCH_CONF),
        ("localhost\n", FILES_FIRST_NSSWITCH_CONF),
        (LOCALHOST_HOSTS_FILE, "hosts: dns files\n"),
        (LOCALHOST_HOSTS_FILE, "hosts: resolve [!UNAVAIL=return] files\n"),
        (LOCALHOST_HOSTS_FILE, "hosts:\n"),
        (LOCALHOST_HOSTS_FILE, "passwd: files\n"),
        (LOCALHOST_HOSTS_FILE, "# hosts: files dns\n"),
        (None, FILES_FIRST_NSSWITCH_CONF),
        (LOCALHOST_HOSTS_FILE, None),
        (LOCALHOST_HOSTS_FILE, b"hosts: files \xff\n"),
    ],
    ids=[
        "no-localhost-entry",
        "localhost-only-in-a-comment",
        "localhost-as-the-address",
        "dns-first",
        "resolve-first",
        "no-hosts-sources",
        "no-hosts-line",
        "hosts-line-commented-out",
        "no-hosts-file",
        "no-nsswitch-conf",
        "nsswitch-conf-not-utf-8",
    ],
)
def test_warm_name_lookup_skips_localhost_unless_the_hosts_file_answers_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    hosts_file: str | None,
    nsswitch_conf: str | bytes | None,
):
    use_name_service_files(monkeypatch, tmp_path, hosts_file, nsswitch_conf)
    getaddrinfo = patch_getaddrinfo(monkeypatch, return_value=[])

    entrypoint.warm_name_lookup()

    assert getaddrinfo.call_args_list == [NUMERIC_LOOKUP]


def test_warm_name_lookup_ignores_lookup_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    use_name_service_files(
        monkeypatch, tmp_path, LOCALHOST_HOSTS_FILE, FILES_FIRST_NSSWITCH_CONF
    )
    getaddrinfo = patch_getaddrinfo(
        monkeypatch, side_effect=socket.gaierror("no resolver")
    )

    entrypoint.warm_name_lookup()

    assert getaddrinfo.call_args_list == [NUMERIC_LOOKUP, LOCALHOST_LOOKUP]


def test_main_warms_name_lookup_before_creating_the_hook_server(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    events: list[str] = []

    class RecordingHookServer(LifecycleHookServer):
        def __init__(self, server_address: tuple[str, int]) -> None:
            events.append("hook server created")
            super().__init__(server_address)

    monkeypatch.setattr(entrypoint, "LifecycleHookServer", RecordingHookServer)
    monkeypatch.setattr(
        entrypoint,
        "warm_name_lookup",
        create_autospec(
            entrypoint.warm_name_lookup,
            side_effect=lambda: events.append("name lookup warmed"),
        ),
    )
    patch_supervise(monkeypatch, lambda payload: 0)

    assert run_main(post_run_hook, hook_port, uuid4(), {}) == 0

    assert events == ["name lookup warmed", "hook server created"]


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


def blocked_signals() -> set[signal.Signals]:
    return signal.pthread_sigmask(signal.SIG_BLOCK, set())


def test_main_blocks_sigterm_from_run_and_hands_supervise_the_earlier_mask(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    assert signal.SIGTERM not in blocked_signals()
    sigterm_blocked_at_refresh: list[bool] = []
    monkeypatch.setattr(
        entrypoint,
        "refresh_global_settings_context",
        create_autospec(
            refresh_global_settings_context,
            side_effect=lambda: sigterm_blocked_at_refresh.append(
                signal.SIGTERM in blocked_signals()
            ),
        ),
    )
    sigterm_blocked_at_supervise: list[bool] = []

    def run_flow(
        payload: RunHookPayload, restored_signal_mask: set[signal.Signals] | None = None
    ) -> int:
        sigterm_blocked_at_supervise.append(signal.SIGTERM in blocked_signals())
        return 0

    supervise = create_autospec(supervise_flow_run, side_effect=run_flow)
    monkeypatch.setattr(entrypoint, "supervise_flow_run", supervise)
    signal_mask_before_main = blocked_signals()

    assert run_main(post_run_hook, hook_port, uuid4(), {}) == 0

    assert sigterm_blocked_at_refresh == [True]
    assert sigterm_blocked_at_supervise == [True]
    assert supervise.call_args.kwargs == {
        "restored_signal_mask": signal_mask_before_main
    }
    assert blocked_signals() == signal_mask_before_main


def test_main_unblocks_sigterm_when_the_settings_fail_to_load(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    register_unloadable_settings_env(monkeypatch)
    monkeypatch.setattr(entrypoint, "report_crash", create_autospec(report_crash))
    patch_supervise(monkeypatch, lambda payload: 0)
    signal_mask_before_main = blocked_signals()

    assert run_main(post_run_hook, hook_port, uuid4(), UNLOADABLE_SETTINGS_ENV) == 1

    assert blocked_signals() == signal_mask_before_main


def test_main_unblocks_sigterm_after_an_invalid_run_request(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    patch_supervise(monkeypatch, lambda payload: 0)
    signal_mask_before_main = blocked_signals()

    assert run_main(post_run_hook, hook_port, uuid4(), {}, 99) == 1

    assert blocked_signals() == signal_mask_before_main


def test_sigterm_during_a_slow_api_host_lookup_is_forwarded_to_the_child(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    main_thread_id = threading.main_thread().ident
    assert main_thread_id is not None
    sigterm_sent = threading.Event()

    def send_sigterm_then_finish() -> None:
        signal.pthread_kill(main_thread_id, signal.SIGTERM)
        sigterm_sent.set()
        time.sleep(0.2)

    def start_slow_lookup(api_url: str | None) -> threading.Thread:
        lookup = threading.Thread(target=send_sigterm_then_finish, daemon=True)
        lookup.start()
        return lookup

    monkeypatch.setattr(
        entrypoint,
        "start_api_host_lookup",
        create_autospec(
            entrypoint.start_api_host_lookup, side_effect=start_slow_lookup
        ),
    )
    # The child exits 0 on its own unless the SIGTERM reaches it.
    monkeypatch.setattr(supervisor, "execute_flow_run", lambda payload: time.sleep(5))
    report = create_autospec(report_crash)
    monkeypatch.setattr(supervisor, "report_crash", report)
    sigterms_handled_by_the_test: list[int] = []
    previous_sigterm_handler = signal.signal(
        signal.SIGTERM,
        lambda signum, frame: sigterms_handled_by_the_test.append(signum),
    )
    flow_run_id = uuid4()
    try:
        exit_code = run_main(post_run_hook, hook_port, flow_run_id, {})
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm_handler)

    assert sigterm_sent.is_set()
    assert sigterms_handled_by_the_test == []
    assert exit_code == 1
    report.assert_called_once_with(flow_run_id, "was killed by signal 15")


def register_env_for_run(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    # Registers each variable as unset, so that the value `/run` writes is undone
    # after the test.
    for name in names:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


def test_crash_report_fallback_uses_the_api_key_and_auth_string_from_run(
    monkeypatch: pytest.MonkeyPatch,
    post_run_hook: PostRunHook,
    hook_port: int,
    api_from_environment: str,
):
    register_unloadable_settings_env(monkeypatch)
    register_env_for_run(monkeypatch, "PREFECT_API_KEY", "PREFECT_API_AUTH_STRING")
    client_class = create_autospec(SyncPrefectClient)
    monkeypatch.setattr(supervisor, "SyncPrefectClient", client_class)
    propose = create_autospec(
        supervisor.propose_state_sync, return_value=Crashed(message="crashed")
    )
    monkeypatch.setattr(supervisor, "propose_state_sync", propose)
    patch_supervise(monkeypatch, lambda payload: 0)
    flow_run_id = uuid4()
    run_env = {
        **UNLOADABLE_SETTINGS_ENV,
        "PREFECT_API_KEY": "key-from-run",
        "PREFECT_API_AUTH_STRING": "admin:auth-from-run",
    }

    assert run_main(post_run_hook, hook_port, flow_run_id, run_env) == 1

    client_class.assert_called_once_with(
        api_from_environment,
        auth_string="admin:auth-from-run",
        api_key="key-from-run",
    )
    propose.assert_called_once()
    assert propose.call_args.kwargs["flow_run_id"] == flow_run_id


def test_crash_report_fallback_without_an_api_url_constructs_no_client(
    monkeypatch: pytest.MonkeyPatch,
    post_run_hook: PostRunHook,
    hook_port: int,
    caplog: pytest.LogCaptureFixture,
):
    register_unloadable_settings_env(monkeypatch)
    monkeypatch.delenv("PREFECT_API_URL")
    client_class = create_autospec(SyncPrefectClient)
    monkeypatch.setattr(supervisor, "SyncPrefectClient", client_class)
    supervise = patch_supervise(monkeypatch, lambda payload: 0)
    flow_run_id = uuid4()

    assert run_main(post_run_hook, hook_port, flow_run_id, UNLOADABLE_SETTINGS_ENV) == 1

    client_class.assert_not_called()
    supervise.assert_not_called()
    assert (
        f"Could not report flow run {flow_run_id} as crashed because "
        "PREFECT_API_URL is not set."
    ) in caplog.messages
    assert f"Could not report flow run {flow_run_id} as crashed." not in (
        caplog.messages
    )


def test_hook_threads_block_sigterm_and_the_main_thread_does_not_before_run(
    monkeypatch: pytest.MonkeyPatch, post_run_hook: PostRunHook, hook_port: int
):
    signals_blocked_in_ready_handler: list[set[signal.Signals]] = []
    original_do_get = LifecycleHookHandler.do_GET

    def record_mask_then_answer(handler: LifecycleHookHandler) -> None:
        signals_blocked_in_ready_handler.append(blocked_signals())
        original_do_get(handler)

    monkeypatch.setattr(LifecycleHookHandler, "do_GET", record_mask_then_answer)
    signals_blocked_in_main_waiting_for_run: list[set[signal.Signals]] = []
    original_wait = LifecycleHookServer.wait_for_run_request

    def record_mask_then_wait(
        server: LifecycleHookServer,
    ) -> RunHookRequest | InvalidRunHookPayload:
        signals_blocked_in_main_waiting_for_run.append(blocked_signals())
        return original_wait(server)

    monkeypatch.setattr(
        LifecycleHookServer, "wait_for_run_request", record_mask_then_wait
    )
    patch_supervise(monkeypatch, lambda payload: 0)

    # Posts `/run` only after `/ready` is answered, because `/run` stops the server.
    def get_ready_then_post_run() -> None:
        deadline = time.monotonic() + 5
        try:
            while time.monotonic() < deadline:
                connection = http.client.HTTPConnection(
                    "127.0.0.1", hook_port, timeout=1
                )
                try:
                    connection.request("GET", "/ready")
                    connection.getresponse().read()
                    return
                except OSError:
                    time.sleep(0.05)
                finally:
                    connection.close()
        finally:
            post_run_hook(hook_port, uuid4(), {})

    requester = threading.Thread(target=get_ready_then_post_run, daemon=True)
    requester.start()
    exit_code = entrypoint.main(port=hook_port)
    requester.join(timeout=10)

    assert exit_code == 0
    assert len(signals_blocked_in_ready_handler) == 1
    assert signal.SIGTERM in signals_blocked_in_ready_handler[0]
    assert len(signals_blocked_in_main_waiting_for_run) == 1
    assert signal.SIGTERM not in signals_blocked_in_main_waiting_for_run[0]
