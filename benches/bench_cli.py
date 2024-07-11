import subprocess

# It's hard to get a good reading on these in CodSpeed because they run in another process and
# CodSpeed currently doesn't include system calls in the benchmark time.
# TODO: Find a way to measure these in CodSpeed


def bench_prefect_help(benchmark):
    benchmark(subprocess.check_call, ["prefect", "--help"])


def bench_prefect_version(benchmark):
    benchmark(subprocess.check_call, ["prefect", "version"])


def bench_prefect_short_version(benchmark):
    benchmark(subprocess.check_call, ["prefect", "--version"])


def bench_prefect_profile_ls(benchmark):
    benchmark(subprocess.check_call, ["prefect", "profile", "ls"])
