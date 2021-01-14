import pytest

pytest.skip("CI required extra SQL dependencies")
pytest.importorskip("pyodbc")