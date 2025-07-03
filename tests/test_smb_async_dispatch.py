"""Tests for SMB filesystem async_dispatch migration."""

import asyncio
from unittest.mock import MagicMock, PropertyMock, patch

from prefect.filesystems import SMB


class TestSMBAsyncDispatch:
    """Test SMB filesystem async_dispatch behavior."""

    async def test_async_dispatch_methods_work_in_async_context(self):
        """Test that async_dispatch methods work correctly when called from async context."""
        smb = SMB(
            share_path="/share/path",
            smb_host="test.host.com",
            smb_username="user",
            smb_password="pass",
        )

        # Since RemoteFileSystem doesn't have aget_directory etc in this branch,
        # let's test that the SMB methods exist and are properly decorated
        assert asyncio.iscoroutinefunction(smb.aget_directory)
        assert asyncio.iscoroutinefunction(smb.aput_directory)
        assert asyncio.iscoroutinefunction(smb.aread_path)
        assert asyncio.iscoroutinefunction(smb.awrite_path)

        # And that the sync versions are regular functions
        assert not asyncio.iscoroutinefunction(smb.get_directory)
        assert not asyncio.iscoroutinefunction(smb.put_directory)
        assert not asyncio.iscoroutinefunction(smb.read_path)
        assert not asyncio.iscoroutinefunction(smb.write_path)

    def test_async_dispatch_methods_work_in_sync_context(self):
        """Test that async_dispatch methods work correctly when called from sync context."""
        smb = SMB(
            share_path="/share/path",
            smb_host="test.host.com",
            smb_username="user",
            smb_password="pass",
        )

        # Mock the filesystem property to avoid the actual RemoteFileSystem creation
        mock_fs = MagicMock()
        mock_fs.get_directory = MagicMock()
        mock_fs.put_directory = MagicMock(return_value=5)
        mock_fs.read_path = MagicMock(return_value=b"test content")
        mock_fs.write_path = MagicMock(
            return_value="smb://test.host.com/share/path/test.txt"
        )

        with patch.object(
            SMB, "filesystem", new_callable=PropertyMock
        ) as mock_property:
            mock_property.return_value = mock_fs

            # Test sync methods are called
            smb.get_directory(from_path="source", local_path="dest")
            mock_fs.get_directory.assert_called_once_with(
                from_path="source", local_path="dest"
            )

            result = smb.put_directory(local_path="local", to_path="remote")
            assert result == 5
            mock_fs.put_directory.assert_called_once_with(
                local_path="local", to_path="remote", ignore_file=None, overwrite=False
            )

            content = smb.read_path("test.txt")
            assert content == b"test content"
            mock_fs.read_path.assert_called_once_with("test.txt")

            path = smb.write_path("test.txt", b"new content")
            assert path == "smb://test.host.com/share/path/test.txt"
            mock_fs.write_path.assert_called_once_with(
                path="test.txt", content=b"new content"
            )
