import pytest

pytest.importorskip("sodaspark")

try:
    from sodasql.scan.dialect import SPARK
except ImportError:
    pytest.skip("Intermittent issue with SPARK installation.", allow_module_level=True)
