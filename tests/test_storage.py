from pathlib import Path

import pytest

from prefect.storage import LocalFileSystem, RemoteFileSystem


class TestLocalFileSystem:
    async def test_read_write_roundtrip(self, tmp_path):
        fs = LocalFileSystem(basepath=str(tmp_path))
        await fs.write_path("test.txt", content=b"hello")
        assert await fs.read_path("test.txt") == b"hello"

    async def test_write_with_missing_directory_creates(self, tmp_path):
        fs = LocalFileSystem(basepath=str(tmp_path))
        await fs.write_path(Path("folder") / "test.txt", content=b"hello")
        assert (tmp_path / "folder").exists()
        assert (tmp_path / "folder" / "test.txt").read_text() == "hello"

    async def test_write_outside_of_basepath(self, tmp_path):
        fs = LocalFileSystem(basepath=str(tmp_path / "foo"))
        with pytest.raises(ValueError, match="..."):
            await fs.write_path(tmp_path / "bar" / "test.txt", content=b"hello")

    async def test_read_fails_for_directory(self, tmp_path):
        fs = LocalFileSystem(basepath=str(tmp_path))
        (tmp_path / "folder").mkdir()
        with pytest.raises(ValueError, match="not a file"):
            await fs.read_path(tmp_path / "folder")


class TestRemoteFileSystem:
    def test_must_contain_scheme(self):
        with pytest.raises(ValueError, match="must start with a scheme"):
            RemoteFileSystem(basepath="foo")

    def test_must_contain_net_location(self):
        with pytest.raises(
            ValueError, match="must include a location after the scheme"
        ):
            RemoteFileSystem(basepath="memory://")

    async def test_read_write_roundtrip(self):
        fs = RemoteFileSystem(basepath="memory://root")
        await fs.write_path("test.txt", content=b"hello")
        assert await fs.read_path("test.txt") == b"hello"

    async def test_write_with_missing_directory_succeeds(self):
        fs = RemoteFileSystem(basepath="memory://root/")
        await fs.write_path("memory://root/folder/test.txt", content=b"hello")
        assert await fs.read_path("folder/test.txt") == b"hello"

    async def test_write_outside_of_basepath_netloc(self):
        fs = RemoteFileSystem(basepath="memory://foo")
        with pytest.raises(ValueError, match="is outside of the base path"):
            await fs.write_path("memory://bar/test.txt", content=b"hello")

    async def test_write_outside_of_basepath_subpath(self):
        fs = RemoteFileSystem(basepath="memory://root/foo")
        with pytest.raises(ValueError, match="is outside of the base path"):
            await fs.write_path("memory://root/bar/test.txt", content=b"hello")

    async def test_write_to_different_scheme(self):
        fs = RemoteFileSystem(basepath="memory://foo")
        with pytest.raises(
            ValueError,
            match="with scheme 'file' must use the same scheme as the base path 'memory'",
        ):
            await fs.write_path("file://foo/test.txt", content=b"hello")

    async def test_read_fails_does_not_exist(self):
        fs = RemoteFileSystem(basepath="memory://root")
        with pytest.raises(FileNotFoundError):
            await fs.read_path("foo/bar")
