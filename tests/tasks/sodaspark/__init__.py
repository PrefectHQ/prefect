import pytest

pytest.importorskip("sodaspark")

try:
    from sodasql.scan.dialect import SPARK
except ImportError:
    pytest.skip(reason="Issue with SPARK installation.", allow_module_level=True)
