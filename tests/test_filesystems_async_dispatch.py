"""Tests for the RemoteFileSystem and SMB async_dispatch migration."""

import inspect

from prefect.filesystems import RemoteFileSystem


class TestRemoteFileSystemAsyncDispatch:
    """Tests for the RemoteFileSystem async_dispatch migration."""

    def test_has_async_methods(self):
        """Verify RemoteFileSystem has async method variants."""
        assert hasattr(RemoteFileSystem, "aget_directory")
        assert hasattr(RemoteFileSystem, "aput_directory")
        assert hasattr(RemoteFileSystem, "aread_path")
        assert hasattr(RemoteFileSystem, "awrite_path")

    def test_has_aio_attributes(self):
        """Verify .aio backward compatibility attributes exist."""
        assert hasattr(RemoteFileSystem.get_directory, "aio")
        assert hasattr(RemoteFileSystem.put_directory, "aio")
        assert hasattr(RemoteFileSystem.read_path, "aio")
        assert hasattr(RemoteFileSystem.write_path, "aio")

    def test_sync_read_write_works(self):
        """Test sync read/write with memory filesystem."""
        fs = RemoteFileSystem(basepath="memory://test-sync/")
        fs.write_path("test.txt", b"hello sync")
        content = fs.read_path("test.txt")
        assert content == b"hello sync"

    async def test_async_read_write_works(self):
        """Test async read/write with memory filesystem."""
        fs = RemoteFileSystem(basepath="memory://test-async/")
        await fs.write_path("test.txt", b"hello async")
        content = await fs.read_path("test.txt")
        assert content == b"hello async"

    async def test_explicit_async_methods_work(self):
        """Test explicit async methods (aread_path, awrite_path)."""
        fs = RemoteFileSystem(basepath="memory://test-explicit/")
        await fs.awrite_path("test.txt", b"hello explicit")
        content = await fs.aread_path("test.txt")
        assert content == b"hello explicit"

    async def test_dispatch_returns_coroutine_in_async_context(self):
        """Test that sync methods return coroutine in async context."""
        fs = RemoteFileSystem(basepath="memory://test-dispatch/")

        result = fs.write_path("test.txt", b"dispatch test")
        assert inspect.iscoroutine(result)
        await result

        result = fs.read_path("test.txt")
        assert inspect.iscoroutine(result)
        content = await result
        assert content == b"dispatch test"

    def test_sync_get_directory_works(self, tmp_path):
        """Test sync get_directory with memory filesystem."""
        fs = RemoteFileSystem(basepath="memory://test-get-dir/")
        fs.write_path("subdir/test.txt", b"hello")

        local_dir = tmp_path / "local"
        local_dir.mkdir()

        fs.get_directory(
            from_path="memory://test-get-dir/subdir/", local_path=str(local_dir)
        )
        assert (local_dir / "test.txt").read_bytes() == b"hello"

    async def test_async_get_directory_works(self, tmp_path):
        """Test async get_directory with memory filesystem."""
        fs = RemoteFileSystem(basepath="memory://test-aget-dir/")
        await fs.write_path("subdir/test.txt", b"hello async")

        local_dir = tmp_path / "local"
        local_dir.mkdir()

        await fs.get_directory(
            from_path="memory://test-aget-dir/subdir/", local_path=str(local_dir)
        )
        assert (local_dir / "test.txt").read_bytes() == b"hello async"

    def test_sync_put_directory_works(self, tmp_path):
        """Test sync put_directory with memory filesystem."""
        fs = RemoteFileSystem(basepath="memory://test-put-dir/")

        local_dir = tmp_path / "local"
        local_dir.mkdir()
        (local_dir / "test.txt").write_bytes(b"hello put")

        count = fs.put_directory(local_path=str(local_dir), to_path="uploaded/")
        assert count == 1

        content = fs.read_path("uploaded/test.txt")
        assert content == b"hello put"

    async def test_async_put_directory_works(self, tmp_path):
        """Test async put_directory with memory filesystem."""
        fs = RemoteFileSystem(basepath="memory://test-aput-dir/")

        local_dir = tmp_path / "local"
        local_dir.mkdir()
        (local_dir / "test.txt").write_bytes(b"hello aput")

        count = await fs.put_directory(local_path=str(local_dir), to_path="uploaded/")
        assert count == 1

        content = await fs.read_path("uploaded/test.txt")
        assert content == b"hello aput"
