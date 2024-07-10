import subprocess

import pytest


@pytest.mark.benchmark
def bench_import_prefect():
    subprocess.check_call(["python", "-c", "import prefect"])
