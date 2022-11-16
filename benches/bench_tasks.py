from pytest_benchmark.fixture import BenchmarkFixture

from prefect import flow, task


def noop_function():
    pass


def bench_task_decorator(benchmark: BenchmarkFixture):
    benchmark(task, noop_function)


def bench_task_call(benchmark: BenchmarkFixture):
    noop_task = task(noop_function)

    @flow
    def test_flow():
        benchmark(noop_task)

    test_flow()


def bench_task_submit(benchmark: BenchmarkFixture):
    noop_task = task(noop_function)

    @flow
    def test_flow():
        benchmark(noop_task.submit)

    test_flow()
