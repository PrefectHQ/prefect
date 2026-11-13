import http.client
import json
import socket
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from uuid import UUID

import pytest

import prefect.context
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import FlowRun, State
from prefect.settings import get_current_settings
from prefect.states import Pending


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
def hook_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def post_run_hook() -> Callable[..., threading.Thread]:
    """
    Return a function that posts a `/run` request for a flow run, with the given
    environment and payload version, once the hook server on a port is listening.
    """

    def post_when_listening(
        port: int, flow_run_id: UUID, env: dict[str, str], version: int = 1
    ) -> threading.Thread:
        run_hook_payload = {"v": version, "flow_run_id": str(flow_run_id), "env": env}
        body = json.dumps(
            {"microvmId": "microvm-abc", "runHookPayload": json.dumps(run_hook_payload)}
        ).encode()

        def post() -> None:
            for _ in range(100):
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                try:
                    connection.request("POST", "/run", body=body)
                    connection.getresponse().read()
                    return
                except ConnectionRefusedError:
                    threading.Event().wait(0.05)
                finally:
                    connection.close()

        thread = threading.Thread(target=post, daemon=True)
        thread.start()
        return thread

    return post_when_listening
