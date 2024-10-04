import traceback

import pytest
import pytest_benchmark.plugin

from prefect.settings import Settings

_handle_saving = pytest_benchmark.session.BenchmarkSession.handle_saving


@pytest.hookimpl(hookwrapper=True)
def handle_saving(*args, **kwargs):
    """
    Patches pytest-benchmark's save handler to avoid raising exceptions on failure.
    An upstream bug causes failures to generate the benchmark JSON when tests fail.
    """
    try:
        return _handle_saving(*args, **kwargs)
    except Exception:
        print("Failed to save benchmark results:")
        traceback.print_exc()


pytest_benchmark.session.BenchmarkSession.handle_saving = handle_saving


@pytest.fixture(autouse=True)
def disable_test_mode(monkeypatch):
    monkeypatch.delenv("PREFECT_TEST_MODE", raising=False)
    monkeypatch.delenv("PREFECT_UNIT_TEST_MODE", raising=False)
    monkeypatch.setattr("prefect.settings.get_current_settings", lambda: Settings())
    yield
