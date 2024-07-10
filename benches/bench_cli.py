import subprocess

import pytest


@pytest.mark.benchmark
def bench_prefect_help():
    subprocess.check_call(["prefect", "--help"])


@pytest.mark.benchmark
def bench_prefect_version():
    subprocess.check_call(["prefect", "version"])


@pytest.mark.benchmark
def bench_prefect_short_version():
    subprocess.check_call(["prefect", "--version"])


@pytest.mark.benchmark
def bench_prefect_profile_ls():
    subprocess.check_call(["prefect", "profile", "ls"])
