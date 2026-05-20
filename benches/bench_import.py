"""Cold-import benchmarks for Prefect modules.

Each benchmark measures the cost of a cold import starting from an empty
`sys.modules` with no `prefect*` entries.

**Why `benchmark.pedantic(setup=...)`?**

CodSpeed's simulation mode always executes at least one **warmup** round
(to prime the perf-trampoline cache on Python 3.12+) before the measured
round.  Critically, `setup` runs *outside* the callgrind instrumentation
markers, so each call — warmup and measured — starts with a clean
`sys.modules` while CodSpeed only counts instructions from
`importlib.import_module`.  Using `@pytest.mark.codspeed_benchmark`
without a `setup` would include the cleanup in the measurement or, worse,
measure a cached `sys.modules` hit after the warmup already performed the
cold import.

The CI workflow invokes each parametrized test in its own `pytest` process
and passes `-o 'filterwarnings='` to override the warning filters in
`pyproject.toml` that reference
`prefect._internal.compatibility.deprecated.PrefectDeprecationWarning`.
Without this, pytest resolves those filter classes at startup, which
triggers a prefect import before the benchmark runs.

For local one-off runs, invoke a single benchmark at a time::

    uv run pytest "benches/bench_import.py::bench_import_module[prefect]" \\
        --codspeed -v -o 'filterwarnings='
"""

import importlib
import sys
from typing import TYPE_CHECKING

import pytest
from prometheus_client import REGISTRY

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

IMPORT_MODULES = [
    # Each entry is the deepest leaf in its import chain so that a regression
    # in any parent module (e.g. prefect.server.schemas) is still caught
    # transitively.  The full 17-module list is exercised by the subprocess-
    # based smoke tests in tests/test_import_smoke.py.
    "prefect",
    "prefect.client.schemas.objects",
    "prefect.flows",
    "prefect.deployments",
    "prefect.events",
    "prefect.server.api.server",
    "prefect.task_runners",
]


def _reset_to_cold_state():
    """Restore the interpreter to a pre-import state for Prefect.

    Removes `prefect*` modules from `sys.modules`, unregisters any
    Prometheus collectors they created, and invalidates import caches.
    This runs inside `benchmark.pedantic(setup=...)` so it executes
    *outside* CodSpeed's callgrind markers — the benchmark only counts
    the instructions of the subsequent `importlib.import_module` call.
    """
    # Unregister prefect prometheus collectors so re-import can re-create them
    for collector, names in list(REGISTRY._collector_to_names.items()):
        if any(n.startswith("prefect") for n in names):
            REGISTRY.unregister(collector)

    for key in [k for k in sys.modules if k.startswith("prefect")]:
        del sys.modules[key]
    importlib.invalidate_caches()

    # Fail loudly if cleanup was incomplete
    leaked = [k for k in sys.modules if k.startswith("prefect")]
    assert not leaked, f"prefect modules still in sys.modules after reset: {leaked}"


@pytest.mark.benchmark(group="imports")
@pytest.mark.parametrize("module_name", IMPORT_MODULES, ids=IMPORT_MODULES)
def bench_import_module(benchmark: "BenchmarkFixture", module_name: str):
    def do_import():
        importlib.import_module(module_name)

    benchmark.pedantic(
        do_import,
        setup=_reset_to_cold_state,
        rounds=1,
        warmup_rounds=0,
        iterations=1,
    )


@pytest.mark.benchmark(group="imports")
def bench_import_prefect_flow(benchmark: "BenchmarkFixture"):
    """Benchmark the public API form: `from prefect import flow`."""

    def import_prefect_flow():
        from prefect import flow  # noqa: F401

    benchmark.pedantic(
        import_prefect_flow,
        setup=_reset_to_cold_state,
        rounds=1,
        warmup_rounds=0,
        iterations=1,
    )
