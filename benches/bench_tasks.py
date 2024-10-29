from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

from prefect import flow, task


def noop_function():
    pass


def bench_task_decorator(benchmark: "BenchmarkFixture"):
    benchmark(task, noop_function)


def bench_task_call(benchmark: "BenchmarkFixture"):
    noop_task = task(noop_function)

    @flow
    def benchmark_flow():
        benchmark(noop_task)

    benchmark_flow()


def bench_task_submit(benchmark: "BenchmarkFixture"):
    noop_task = task(noop_function)

    # The benchmark occurs within the flow to measure _submission_ time without
    # measuring any other part of orchestration / collection of results

    @flow
    def benchmark_flow():
        benchmark(noop_task.submit)

    benchmark_flow()
