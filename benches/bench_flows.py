"""
TODO: Add benches for higher number of tasks; blocked by engine deadlocks in CI.
"""

from typing import TYPE_CHECKING

import anyio
import pytest

from prefect import flow, task

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def noop_function():
    pass


async def anoop_function():
    pass


def bench_flow_decorator(benchmark: "BenchmarkFixture"):
    benchmark(flow, noop_function)


@pytest.mark.parametrize("options", [{}, {"timeout_seconds": 10}])
def bench_flow_call(benchmark: "BenchmarkFixture", options):
    noop_flow = flow(**options)(noop_function)
    benchmark(noop_flow)


# The benchmarks below this comment take too long to run with CodSpeed and are not included in the
# CodSpeed benchmarks. They are included in the local benchmarks. These benchmarks could be improved
# because we can only run the benchmarks with a large number of tasks once for each run which may
# not be enough to get a good reading.
# TODO: Find a way to measure these in CodSpeed.


@pytest.mark.parametrize("num_tasks", [10, 50, 100])
def bench_flow_with_submitted_tasks(benchmark: "BenchmarkFixture", num_tasks: int):
    test_task = task(noop_function)

    @flow
    def benchmark_flow():
        for _ in range(num_tasks):
            test_task.submit()

    benchmark(benchmark_flow)


@pytest.mark.parametrize("num_tasks", [10, 50, 100, 250])
def bench_flow_with_called_tasks(benchmark: "BenchmarkFixture", num_tasks: int):
    test_task = task(noop_function)

    @flow
    def benchmark_flow():
        for _ in range(num_tasks):
            test_task()

    if num_tasks > 100:
        benchmark.pedantic(benchmark_flow)
    else:
        benchmark(benchmark_flow)


@pytest.mark.parametrize("num_tasks", [10, 50, 100, 250])
def bench_async_flow_with_async_tasks(benchmark: "BenchmarkFixture", num_tasks: int):
    test_task = task(anoop_function)

    @flow
    async def benchmark_flow():
        async with anyio.create_task_group() as tg:
            for _ in range(num_tasks):
                tg.start_soon(test_task)

    if num_tasks > 100:
        benchmark.pedantic(anyio.run, (benchmark_flow,))
    else:
        benchmark(anyio.run, benchmark_flow)


@pytest.mark.parametrize("num_flows", [5, 10, 20])
def bench_flow_with_subflows(benchmark: "BenchmarkFixture", num_flows: int):
    test_flow = flow(noop_function)

    @flow
    def benchmark_flow():
        for _ in range(num_flows):
            test_flow()

    benchmark(benchmark_flow)


@pytest.mark.parametrize("num_flows", [5, 10, 20])
def bench_async_flow_with_sequential_subflows(
    benchmark: "BenchmarkFixture", num_flows: int
):
    test_flow = flow(anoop_function)

    @flow
    async def benchmark_flow():
        for _ in range(num_flows):
            await test_flow()

    benchmark(anyio.run, benchmark_flow)


@pytest.mark.parametrize("num_flows", [5, 10, 20])
def bench_async_flow_with_concurrent_subflows(
    benchmark: "BenchmarkFixture", num_flows: int
):
    test_flow = flow(anoop_function)

    @flow
    async def benchmark_flow():
        async with anyio.create_task_group() as tg:
            for _ in range(num_flows):
                tg.start_soon(test_flow)

    benchmark(anyio.run, benchmark_flow)
