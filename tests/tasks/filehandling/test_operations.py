from pathlib import Path
from unittest.mock import patch

import pytest

from prefect.tasks.filehandling.operations import Move


class TestMove:
    def test_initialization(self):
        source_path = "/a/path/file.pdf"
        target_path = "/some/path/archive"
        filename = "file-2021.pdf"
        m = Move(
            source_path=source_path, target_path=target_path, target_filename=filename
        )

        assert m.source_path == source_path
        assert m.target_path == target_path
        assert m.target_filename == filename
        assert not m.create_target_if_not_exists

    def test_source_path_not_found(self):
        source_path = "/tmp/folder/myfile.txt"
        with pytest.raises(ValueError) as exc_info:
            Move(source_path=source_path).run()

        assert f"Source path ({source_path}) not found!" in exc_info.value.args[0]

    @patch.object(Move, "_check_target_path")
    @patch.object(Path, "is_file", return_value=True)
    @patch.object(Path, "exists", return_value=True)
    @patch.object(Path, "rename")
    def test_target_filename(
        self, mock_rename, mock_exists, mock_is_file, mock_target_path
    ):
        target_path = Path("/tmp/folder/archive")
        # source = single file
        source_path = Path("/tmp/folder/myfile.txt")

        # Single file without new file name
        m = Move(source_path=source_path, target_path=target_path)
        assert m.run() == target_path.joinpath(source_path.name)

        # Single file with new file name
        assert m.run(target_filename="myfile-1234.txt") == target_path.joinpath(
            "myfile-1234.txt"
        )

        # source = directory
        mock_is_file.return_value = False
        source_path = Path("/tmp/folder")
        # ignore target_filename
        assert (
            m.run(source_path=source_path, target_filename="myfile-1234.txt")
            == target_path
        )
        # directory gets moved into new path
        assert m.run(source_path=source_path) == target_path
