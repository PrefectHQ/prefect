from collections.abc import Callable, Iterator
from pathlib import Path

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
        prefect.context, "GLOBAL_SETTINGS_CONTEXT", prefect.context.GLOBAL_SETTINGS_CONTEXT
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
