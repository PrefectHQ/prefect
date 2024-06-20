import traceback

import pytest
import pytest_benchmark.plugin

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
