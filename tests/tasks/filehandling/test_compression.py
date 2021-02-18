import os
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prefect.tasks.filehandling.compression import Unzip, Zip


class TestUnzip:
    def test_initialization(self):
        zip = "/a/path/file.zip"
        target_dir = "/some/path"
        password = "p4s5"
        uz = Unzip(
            zip_password=password, target_directory=target_dir, zip_file_path=zip
        )

        assert uz.zip_file_path == zip
        assert uz.target_directory == target_dir
        assert uz.zip_password == password
        assert not uz.remove_after_unzip
        assert not uz.create_target_if_not_exists

    def test_source_file_not_found(self):
        zip = Path("/a/path/file.zip")
        target_dir = "/some/path"
        uz = Unzip(zip, target_dir)
        with pytest.raises(ValueError) as exc_info:
            uz.run()

        assert f"Source file ({str(zip)}) not found!" in exc_info.value.args[0]

    @patch.object(Path, "is_file")
    def test_source_file_is_not_a_zip_file(self, mock_is_file):
        zip = Path("/a/path/file.rar")
        target_dir = "/some/path"
        mock_is_file.return_value = True
        uz = Unzip(zip, target_dir)
        with pytest.raises(TypeError) as exc_info:
            uz.run()

        assert f"Source file ({str(zip)}) is not a zip file" in exc_info.value.args[0]

    @patch.object(Path, "is_file", return_value=True)
    @patch.object(Path, "mkdir")
    @patch.object(zipfile, "is_zipfile", return_value=True)
    @patch.object(Unzip, "_check_target_path")
    @patch("prefect.tasks.filehandling.compression.ZipFile", return_value=MagicMock())
    def test_target_path(
        self,
        mock_zipfile,
        mock_check_target_path,
        mock_is_zipfile,
        mock_mkdir,
        mock_is_file,
    ):
        zip = "/a/path/file.rar"
        target_dir = "/some/path"

        uz = Unzip(zip, target_dir)
        assert uz.run() == Path(target_dir)
        assert uz.run(use_filename_as_target_dir=True) == Path(target_dir).joinpath(
            Path(zip).stem
        )

    @patch.object(Path, "is_file", return_value=True)
    @patch.object(Path, "mkdir")
    @patch.object(zipfile, "is_zipfile", return_value=True)
    @patch.object(Unzip, "_check_target_path")
    @patch("prefect.tasks.filehandling.compression.ZipFile", return_value=MagicMock())
    @patch.object(os, "remove")
    def test_remove_zip(
        self,
        mock_remove,
        mock_zipfile,
        mock_check_target_path,
        mock_is_zipfile,
        mock_mkdir,
        mock_is_file,
        caplog,
    ):
        zip = Path("/a/path/file.rar")
        target_dir = "/some/path"
        uz = Unzip(zip, target_dir)
        uz.run(remove_after_unzip=True)
        assert f"Removing {str(zip)} after extraction." in caplog.text


class TestZip:
    def test_initialization(self):
        zip = "/a/path/file.zip"
        target_dir = "/some/path"
        z = Zip(target_directory=target_dir, source_path=zip)

        assert z.source_path == zip
        assert z.target_directory == target_dir
        assert not z.create_target_if_not_exists

    def test_source_path_not_defined(self):
        with pytest.raises(ValueError) as exc_info:
            Zip().run()

        assert "Source path is not defined." in exc_info.value.args[0]

    @patch.object(Path, "is_file", return_value=True)
    @patch.object(Zip, "_check_target_path")
    @patch(
        "prefect.tasks.filehandling.compression.ZipFile",
        return_value=MagicMock(),
        autospec=True,
    )
    def test_zip_file_name(self, mock_zipfile, mock_target_path, mock_is_file):
        # Single source
        source = "/a/path/file.txt"
        target = Path("/some/path")

        z = Zip(source_path=source, target_directory=target)
        assert z.run() == target.joinpath("file.zip")

        # Multi source, first file
        source = ["/a/nother/object.pdf", Path("/a/path/file.txt"), "/some/other/dir"]

        z = Zip(source_path=source, target_directory=target)
        assert z.run() == target.joinpath("object.zip")

        # Multi source, first dir
        source = ["/some/other/dir", "/a/nother/object.pdf", Path("/a/path/file.txt")]

        mock_is_file.return_value = False
        z = Zip(source_path=source, target_directory=target)
        assert z.run() == target.joinpath("dir.zip")

        # Given name without extension
        assert z.run(zip_file_name="MyTestFile") == target.joinpath("MyTestFile.zip")

        # Given name with extension
        assert z.run(zip_file_name="MyTestFile.zip") == target.joinpath(
            "MyTestFile.zip"
        )
