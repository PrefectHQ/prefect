import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prefect.tasks.filehandling.compression import Unzip, Zip


class TestUnzip:
    def test_initialization(self):
        zip = "/a/path/file.zip"
        target_dir = "/some/path"
        uz = Unzip(target_path=target_dir, source=zip)

        assert uz.source == zip
        assert uz.target_path == target_dir

    def test_source_file_not_found(self):
        zip = Path("/a/path/file.zip")
        target_dir = "/some/path"
        uz = Unzip(zip, target_dir)
        with pytest.raises(ValueError) as exc_info:
            uz.run()

        assert f"Source path ({str(zip)}) not found!" in exc_info.value.args[0]

    @patch.object(Path, "exists")
    def test_source_file_is_not_a_zip_file(self, mock_is_file):
        zip = Path("/a/path/file.rar")
        target_dir = "/some/path"
        mock_is_file.return_value = True
        uz = Unzip(zip, target_dir)
        with pytest.raises(TypeError) as exc_info:
            uz.run()

        assert f"Source file ({str(zip)}) is not a zip file" in exc_info.value.args[0]

    @patch.object(zipfile, "is_zipfile", return_value=True)
    @patch.object(Unzip, "_check_path_exists")
    @patch("prefect.tasks.filehandling.compression.ZipFile", return_value=MagicMock())
    def test_target_path(self, mock_zipfile, mock_check_target_path, mock_is_zipfile):
        zip = "/a/path/file.rar"
        target_dir = "/some/path"

        uz = Unzip(zip, target_dir)
        assert uz.run() == Path(target_dir)
        assert uz.run(target_path=None) == Path.cwd()


class TestZip:
    def test_initialization(self):
        zip = "/a/path/file.zip"
        target_dir = "/some/path"
        z = Zip(target_path=target_dir, source=zip)

        assert z.source == zip
        assert z.target_path == target_dir
        assert z.compression == zipfile.ZIP_DEFLATED

    def test_source_path_not_defined(self):
        with pytest.raises(ValueError) as exc_info:
            Zip().run()

        assert "Source path is not set!" in exc_info.value.args[0]

    @patch.object(Path, "is_file", return_value=True)
    @patch.object(Zip, "_check_path_is_set")
    @patch(
        "prefect.tasks.filehandling.compression.ZipFile",
        return_value=MagicMock(),
        autospec=True,
    )
    def test_zip_file_name(self, mock_zipfile, mock_target_path, mock_exists, caplog):
        target = Path("/some/path/myfile.zip")

        # Single source file
        source = Path("/a/path/file.txt")
        Zip(source=source, target_path=target).run()

        assert f"Adding {source.name} to {target}" in caplog.text

        # # List of source files
        source = ["/a/nother/object.pdf", Path("/a/path/file.txt"), "/some/other/dir"]
        Zip(source=source, target_path=target).run()

        assert f"Adding {Path(source[0]).name} to {target}" in caplog.text
        assert f"Adding {Path(source[2]).name} to {target}" in caplog.text
