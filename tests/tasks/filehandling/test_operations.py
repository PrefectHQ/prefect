from pathlib import Path
from unittest.mock import patch
import sys

from prefect.tasks.filehandling.operations import Move


class TestMove:
    def test_initialization(self):
        source_path = "/a/path/file.pdf"
        target_path = "/some/path/archive/file-2021.pdf"
        m = Move(source_path=source_path, target_path=target_path)

        assert m.source_path == source_path
        assert m.target_path == target_path

    @patch.object(Move, "_check_path_exists")
    @patch.object(Move, "_check_path_is_set")
    @patch("prefect.tasks.filehandling.operations.move")
    def test_return_value(self, mock_move, mock_target, mock_source):
        source_path = Path("/tmp/folder/myfile.txt")
        target_path = Path("/tmp/folder/archive")

        new_path = target_path.joinpath(source_path.name)
        mock_move.return_value = new_path
        m = Move(source_path=source_path, target_path=target_path)
        assert m.run() == new_path

        if sys.version_info >= (3, 9):
            mock_move.assert_called_with(source_path, target_path)
        else:
            mock_move.assert_called_with(str(source_path), str(target_path))

        mock_move.return_value = str(new_path)
        assert isinstance(m.run(), Path)
