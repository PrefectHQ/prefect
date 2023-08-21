import subprocess

from pytest_benchmark.fixture import BenchmarkFixture


def bench_prefect_help(benchmark: BenchmarkFixture):
    benchmark.pedantic(subprocess.check_call, args=(["prefect", "--help"],), rounds=3)


def bench_prefect_version(benchmark: BenchmarkFixture):
    benchmark.pedantic(subprocess.check_call, args=(["prefect", "version"],), rounds=3)


def bench_prefect_short_version(benchmark: BenchmarkFixture):
    benchmark.pedantic(
        subprocess.check_call, args=(["prefect", "--version"],), rounds=3
    )


def bench_prefect_profile_ls(benchmark: BenchmarkFixture):
    benchmark.pedantic(
        subprocess.check_call, args=(["prefect", "profile", "ls"],), rounds=3
    )
