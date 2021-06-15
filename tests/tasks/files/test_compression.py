import os
import zipfile
from pathlib import Path

import pytest

from prefect.tasks.files import Unzip, Zip


class TestUnzip:
    def test_initialization(self):
        uz = Unzip(zip_path="zip_path", extract_dir="extract_dir")
        assert uz.zip_path == "zip_path"
        assert uz.extract_dir == "extract_dir"

        uz = Unzip()
        assert uz.zip_path == ""
        assert uz.extract_dir == ""

    def test_zip_path_not_provided(self, tmpdir):
        uz = Unzip(extract_dir=str(tmpdir))
        with pytest.raises(ValueError, match="No `zip_path` provided"):
            uz.run()

    def test_zip_path_not_found(self, tmpdir):
        bad = str(tmpdir.join("bad.zip"))
        uz = Unzip(zip_path=bad, extract_dir=str(tmpdir))
        with pytest.raises(ValueError, match=f"`zip_path` {bad!r} not found"):
            uz.run()

    def test_run(self, tmpdir):
        zip_path = str(tmpdir.join("data.zip"))
        extract_dir = str(tmpdir.join("out"))

        with zipfile.ZipFile(zip_path, mode="w") as fil:
            fil.writestr("path/to/file", b"some data")
            fil.writestr("path/to/file2", b"some other data")

        uz = Unzip(zip_path, extract_dir)
        out = uz.run()
        assert out == Path(extract_dir)
        assert os.path.exists(os.path.join(extract_dir, "path", "to", "file"))
        assert os.path.exists(os.path.join(extract_dir, "path", "to", "file2"))


class TestZip:
    def test_initialization(self):
        z = Zip(source_path="source_path", zip_path="zip_path")
        assert z.source_path == "source_path"
        assert z.zip_path == "zip_path"

        z = Zip()
        assert z.source_path == ""
        assert z.zip_path == ""

    def test_compression_method(self):
        z = Zip()
        assert z.compression == zipfile.ZIP_DEFLATED

        z = Zip(compression_method="store")
        assert z.compression == zipfile.ZIP_STORED

        z = Zip(compression_method="bzip2")
        assert z.compression == zipfile.ZIP_BZIP2

        z = Zip(compression_method="lzma")
        assert z.compression == zipfile.ZIP_LZMA

        with pytest.raises(ValueError) as exc_info:
            Zip(compression_method="blabla")

        assert "Compression method blabla is not supported!" in exc_info.value.args[0]

    def test_source_path_not_defined(self):
        with pytest.raises(ValueError, match="No `source_path` provided"):
            Zip().run()

    def test_run(self, tmpdir):
        zip_path = str(tmpdir.join("myfile.zip"))
        source = tmpdir.join("source")
        source.join("file1").write_binary(b"test1", ensure=True)
        source.join("file2").write_binary(b"test2", ensure=True)
        source_path = str(source)

        Zip(source_path=source_path, zip_path=zip_path).run()

        assert os.path.exists(zip_path)

        out = tmpdir.join("out").mkdir()

        with zipfile.ZipFile(zip_path) as f:
            f.extractall(out)

        assert out.join("source").join("file1").exists()
        assert out.join("source").join("file2").exists()
