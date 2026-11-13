import http.client
import json
import signal
import socket
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import FrameType
from uuid import UUID

import pytest

import prefect.context
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import FlowRun, State
from prefect.settings import get_current_settings
from prefect.states import Pending

RUN_HOOK_POST_DEADLINE_SECONDS = 10


@flow
def microvm_supervisor_test_flow() -> None:
    pass


@pytest.fixture
def api_from_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[str]:
    """
    Point the settings that the entrypoint refreshes from the environment at the
    test harness, as `/run` does in a MicroVM, with no profile from this machine.
    """
    api_url = get_current_settings().api.url
    assert api_url is not None
    profiles = tmp_path / "profiles.toml"
    profiles.write_text('active = "microvm-test"\n\n[profiles.microvm-test]\n')
    monkeypatch.setenv("PREFECT_PROFILES_PATH", str(profiles))
    monkeypatch.setenv("PREFECT_API_URL", api_url)
    # Restores the global settings that `refresh_global_settings_context` replaces.
    monkeypatch.setattr(
        prefect.context,
        "GLOBAL_SETTINGS_CONTEXT",
        prefect.context.GLOBAL_SETTINGS_CONTEXT,
    )
    yield api_url


@pytest.fixture
def flow_run_in() -> Callable[[State], FlowRun]:
    def create(state: State) -> FlowRun:
        with get_client(sync_client=True) as client:
            flow_run = client.create_flow_run(
                microvm_supervisor_test_flow, state=Pending()
            )
            client.set_flow_run_state(flow_run.id, state, force=True)
            return client.read_flow_run(flow_run.id)

    return create


@pytest.fixture
def restore_signal_mask() -> Iterator[None]:
    """
    Fail a test that starts with SIGTERM blocked or changes this thread's signal
    mask, and restore the mask after it.
    """
    mask_before_test = signal.pthread_sigmask(signal.SIG_BLOCK, set())
    assert signal.SIGTERM not in mask_before_test
    try:
        yield
    finally:
        mask_after_test = signal.pthread_sigmask(signal.SIG_SETMASK, mask_before_test)
    assert mask_after_test == mask_before_test


@pytest.fixture
def hook_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def post_run_hook() -> Iterator[Callable[..., threading.Thread]]:
    """
    Return a function that posts a `/run` request for a flow run, with the given
    environment and payload version, once the hook server on a port is listening.

    A request that cannot be sent within `RUN_HOOK_POST_DEADLINE_SECONDS` fails
    the test.
    """
    test_finished = threading.Event()
    posters: list[threading.Thread] = []
    abandoned_post_errors: list[OSError | None] = []

    def fail_on_abandoned_post(signum: int, frame: FrameType | None) -> None:
        if not abandoned_post_errors:
            raise KeyboardInterrupt
        pytest.fail(
            f"Could not post the `/run` request within "
            f"{RUN_HOOK_POST_DEADLINE_SECONDS} seconds: {abandoned_post_errors[0]!r}"
        )

    def post_when_listening(
        port: int, flow_run_id: UUID, env: dict[str, str], version: int = 1
    ) -> threading.Thread:
        run_hook_payload = {"v": version, "flow_run_id": str(flow_run_id), "env": env}
        body = json.dumps(
            {"microvmId": "microvm-abc", "runHookPayload": json.dumps(run_hook_payload)}
        ).encode()

        def post() -> None:
            deadline = time.monotonic() + RUN_HOOK_POST_DEADLINE_SECONDS
            last_error: OSError | None = None
            while not test_finished.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    abandoned_post_errors.append(last_error)
                    # `main` waits for this request forever, so the failure is
                    # raised in the main thread. A real signal wakes a main
                    # thread blocked on a lock; `_thread.interrupt_main` does not.
                    main_thread_id = threading.main_thread().ident
                    assert main_thread_id is not None
                    signal.pthread_kill(main_thread_id, signal.SIGINT)
                    return
                connection = http.client.HTTPConnection(
                    "127.0.0.1", port, timeout=remaining
                )
                try:
                    connection.request("POST", "/run", body=body)
                    connection.getresponse().read()
                    return
                except OSError as exc:
                    last_error = exc
                    test_finished.wait(0.05)
                finally:
                    connection.close()

        thread = threading.Thread(target=post, daemon=True)
        posters.append(thread)
        thread.start()
        return thread

    previous_sigint_handler = signal.signal(signal.SIGINT, fail_on_abandoned_post)
    try:
        yield post_when_listening
    finally:
        test_finished.set()
        try:
            for poster in posters:
                poster.join(timeout=RUN_HOOK_POST_DEADLINE_SECONDS)
        finally:
            signal.signal(signal.SIGINT, previous_sigint_handler)
