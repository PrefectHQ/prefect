"""Cold-import benchmarks for Prefect modules.

Each benchmark measures the cost of importing a module into a fresh Python
interpreter.  To achieve true isolation the CI workflow invokes each
parametrized test in its own `pytest` process (see
`.github/workflows/codspeed-benchmarks.yaml`).  This avoids the need for
in-process `sys.modules` manipulation, which cannot fully undo the
side-effects of importing Prefect (background threads, Prometheus
collectors, logging handlers, Pydantic registries, etc.) and produced
non-deterministic instruction counts under CodSpeed.

The CI invocations also pass `-o 'filterwarnings='` to override the
warning filters in `pyproject.toml` that reference
`prefect._internal.compatibility.deprecated.PrefectDeprecationWarning`.
Without this, pytest resolves those filter classes at startup, which
triggers a prefect import before the benchmark runs.

For local one-off runs, invoke a single benchmark at a time::

    uv run pytest "benches/bench_import.py::bench_import_module[prefect]" \
        --codspeed -v -o 'filterwarnings='
"""

import importlib
from typing import TYPE_CHECKING

import pytest

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


@pytest.mark.benchmark(group="imports")
@pytest.mark.parametrize("module_name", IMPORT_MODULES, ids=IMPORT_MODULES)
def bench_import_module(benchmark: "BenchmarkFixture", module_name: str):
    benchmark.pedantic(
        importlib.import_module,
        args=(module_name,),
        rounds=1,
        warmup_rounds=0,
        iterations=1,
    )


@pytest.mark.benchmark(group="imports")
def bench_import_prefect_flow(benchmark: "BenchmarkFixture"):
    """Benchmark the public API form: from prefect import flow"""

    def import_prefect_flow():
        from prefect import flow  # noqa: F401

    benchmark.pedantic(
        import_prefect_flow,
        rounds=1,
        warmup_rounds=0,
        iterations=1,
    )
