import subprocess

from pytest_benchmark.fixture import BenchmarkFixture


def bench_import_prefect(benchmark: BenchmarkFixture):
    benchmark(subprocess.check_call, args=(["python", "-c", "import prefect"],))
