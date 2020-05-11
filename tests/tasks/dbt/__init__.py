from shutil import which
import pytest

if not which("dbt"):
    pytest.mark.skip("dbt not installed")
