import subprocess
import sys

import pytest


@pytest.mark.benchmark
def bench_import_prefect():
    subprocess.check_call([sys.executable, "-c", "import prefect"])


@pytest.mark.benchmark
def bench_import_prefect_flow():
    subprocess.check_call([sys.executable, "-c", "from prefect import flow"])
