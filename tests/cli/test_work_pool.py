import pytest

from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_WORKERS
from prefect.testing.cli import invoke_and_assert


@pytest.fixture(autouse=True)
def auto_enable_workers(enable_workers):
    """
    Enable workers for testing
    """
    assert PREFECT_EXPERIMENTAL_ENABLE_WORKERS
    # Import to register worker CLI
    import prefect.experimental.cli.worker  # noqa


def test_create_work_pool():
    res = invoke_and_assert("work-pool create my-pool -t process --paused")
    assert res.exit_code == 0
    assert "Created work pool my-pool" in res.output
