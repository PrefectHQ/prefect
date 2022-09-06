import os
from pathlib import Path

import pytest

import prefect
from prefect.filesystems import GitHub, LocalFileSystem, RemoteFileSystem
from prefect.testing.utilities import AsyncMock

TEST_PROJECTS_DIR = prefect.__root_path__ / "tests" / "test-projects"


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

    async def test_resolve_path(self, tmp_path):
        fs = LocalFileSystem(basepath=str(tmp_path))

        assert fs._resolve_path(tmp_path) == tmp_path
        assert fs._resolve_path(tmp_path / "subdirectory") == tmp_path / "subdirectory"
        assert fs._resolve_path("subdirectory") == tmp_path / "subdirectory"


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

    async def test_resolve_path(self):
        base = "memory://root"
        fs = RemoteFileSystem(basepath=base)

        assert fs._resolve_path(base) == base + "/"
        assert fs._resolve_path(f"{base}/subdir") == f"{base}/subdir"
        assert fs._resolve_path("subdirectory") == f"{base}/subdirectory"

    async def test_put_directory_flat(self):
        fs = RemoteFileSystem(basepath="memory://flat")
        await fs.put_directory(
            os.path.join(TEST_PROJECTS_DIR, "flat-project"),
            ignore_file=os.path.join(
                TEST_PROJECTS_DIR, "flat-project", ".prefectignore"
            ),
        )
        copied_files = set(fs.filesystem.glob("/flat/**"))

        assert copied_files == {
            "/flat/explicit_relative.py",
            "/flat/implicit_relative.py",
            "/flat/shared_libs.py",
        }

    async def test_put_directory_tree(self):
        fs = RemoteFileSystem(basepath="memory://tree")
        await fs.put_directory(
            os.path.join(TEST_PROJECTS_DIR, "tree-project"),
            ignore_file=os.path.join(
                TEST_PROJECTS_DIR, "tree-project", ".prefectignore"
            ),
        )
        copied_files = set(fs.filesystem.glob("/tree/**"))

        assert copied_files == {
            "/tree/imports",
            "/tree/imports/explicit_relative.py",
            "/tree/imports/implicit_relative.py",
            "/tree/shared_libs",
            "/tree/shared_libs/bar.py",
            "/tree/shared_libs/foo.py",
        }


class TestGitHub:
    async def test_subprocess_errors_are_surfaced(self):
        g = GitHub(repository="incorrect-url-scheme")
        with pytest.raises(
            OSError, match="fatal: repository 'incorrect-url-scheme' does not exist"
        ):
            await g.get_directory()

    async def test_repository_default(self, monkeypatch):
        class p:
            returncode = 0

        mock = AsyncMock(return_value=p())
        monkeypatch.setattr(prefect.filesystems, "run_process", mock)
        g = GitHub(repository="prefect")
        await g.get_directory()

        assert mock.await_count == 1
        assert f"git clone prefect" in mock.await_args[0][0]

    async def test_reference_default(self, monkeypatch):
        class p:
            returncode = 0

        mock = AsyncMock(return_value=p())
        monkeypatch.setattr(prefect.filesystems, "run_process", mock)
        g = GitHub(repository="prefect", reference="2.0.0")
        await g.get_directory()

        assert mock.await_count == 1
        assert f"git clone prefect -b 2.0.0 --depth 1" in mock.await_args[0][0]
