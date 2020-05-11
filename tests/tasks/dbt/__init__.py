from shutil import which
import pytest

if not which("dbt"):
    pytest.skip("dbt not installed")
