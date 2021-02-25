from pathlib import Path
import pytest
from prefect.tasks.filehandling.base import FileBase


class TestCompressionBase:
    def test_path_not_set(self):
        x = FileBase()
        source_path = None
        with pytest.raises(ValueError) as exc_info:
            x._check_path_is_set(source_path, "Source")

        assert "Source path is not set!" in exc_info.value.args[0]

    def test_path_exists(self):
        x = FileBase()
        source_path = Path("/tmp/folder/myfile.txt")
        with pytest.raises(ValueError) as exc_info:
            x._check_path_exists(source_path, "Source")

        assert f"Source path ({str(source_path)}) not found!" in exc_info.value.args[0]
