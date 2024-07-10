import subprocess
import sys

import pytest


@pytest.mark.benchmark
def bench_import_prefect():
    subprocess.check_call([sys.executable, "-c", "import prefect"])
