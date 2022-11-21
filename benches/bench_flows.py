"""
TODO: Add benches for higher number of tasks; blocked by engine deadlocks in CI.
"""
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from prefect import flow, task


def noop_function():
    pass


def bench_flow_decorator(benchmark: BenchmarkFixture):
    benchmark(flow, noop_function)


@pytest.mark.parametrize("options", [{}, {"timeout_seconds": 10}])
def bench_flow_call(benchmark: BenchmarkFixture, options):
    noop_flow = flow(**options)(noop_function)
    benchmark(noop_flow)


@pytest.mark.parametrize("num_tasks", [10, 50])
def bench_flow_with_submitted_tasks(benchmark: BenchmarkFixture, num_tasks: int):
    test_task = task(noop_function)

    @flow
    def benchmark_flow():
        for _ in range(num_tasks):
            test_task.submit()

    benchmark(benchmark_flow)


@pytest.mark.parametrize("num_tasks", [10, 50])
def bench_flow_with_called_tasks(benchmark: BenchmarkFixture, num_tasks: int):
    test_task = task(noop_function)

    @flow
    def benchmark_flow():
        for _ in range(num_tasks):
            test_task()

    benchmark(benchmark_flow)
