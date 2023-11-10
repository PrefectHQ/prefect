import pytest

import prefect
import prefect.cli.server
from prefect.testing.utilities import AsyncMock

# All tests that invoke invoke_and_assert() can end up running our CLI command
# coroutines off the main thread. If the CLI command calls
# forward_signal_handler(), which prefect.cli.server.start does, the test run
# will fail because only the main thread can attach signal handlers.
pytestmark = pytest.mark.flaky(max_runs=2)


@pytest.fixture
def mock_run_process(monkeypatch: pytest.MonkeyPatch):
    def mark_as_started(*args, task_status, **kwargs):
        task_status.started()

    mock = AsyncMock(side_effect=mark_as_started)
    monkeypatch.setattr(prefect.cli.server, "run_process", mock)
    yield mock
