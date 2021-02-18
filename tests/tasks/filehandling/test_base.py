from pathlib import Path
from unittest.mock import patch

import pytest

from prefect.tasks.filehandling.base import FileBase


class TestCompressionBase:
    def test_check_target_path_not_found(self):
        x = FileBase()
        target_dir = Path("/some/path")
        with pytest.raises(ValueError) as exc_info:
            x._check_target_path(target_dir, False)

        assert f"Target directory ({target_dir}) not found!" in exc_info.value.args[0]

    @patch.object(Path, "mkdir")
    def test_check_target_path_create_path(self, mock_mkdir, caplog):
        x = FileBase()
        target_dir = Path("/some/path")
        x._check_target_path(target_dir, True)

        assert f"Creating target directory: {target_dir}" in caplog.text
