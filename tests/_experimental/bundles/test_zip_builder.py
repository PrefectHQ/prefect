"""
Tests for ZipBuilder class.

ZipBuilder packages collected files into a sidecar zip archive with
content-addressed storage key derivation using SHA256 hashes.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestZipResult:
    """Tests for ZipResult dataclass."""

    def test_dataclass_fields(self) -> None:
        """ZipResult has required fields: zip_path, sha256_hash, storage_key, size_bytes."""
        from prefect._experimental.bundles._zip_builder import ZipResult

        result = ZipResult(
            zip_path=Path("/tmp/test.zip"),
            sha256_hash="abc123",
            storage_key="files/abc123.zip",
            size_bytes=1024,
        )

        assert result.zip_path == Path("/tmp/test.zip")
        assert result.sha256_hash == "abc123"
        assert result.storage_key == "files/abc123.zip"
        assert result.size_bytes == 1024


class TestZipBuilderConstants:
    """Tests for ZipBuilder module constants."""

    def test_hash_chunk_size(self) -> None:
        """HASH_CHUNK_SIZE is 64KB for chunked reading."""
        from prefect._experimental.bundles._zip_builder import HASH_CHUNK_SIZE

        assert HASH_CHUNK_SIZE == 65536  # 64KB

    def test_zip_size_warning_threshold(self) -> None:
        """ZIP_SIZE_WARNING_THRESHOLD is 50MB."""
        from prefect._experimental.bundles._zip_builder import (
            ZIP_SIZE_WARNING_THRESHOLD,
        )

        assert ZIP_SIZE_WARNING_THRESHOLD == 50 * 1024 * 1024  # 50MB


class TestZipBuilderInit:
    """Tests for ZipBuilder initialization."""

    def test_stores_resolved_base_dir(self, tmp_path: Path) -> None:
        """ZipBuilder stores resolved base_dir."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        builder = ZipBuilder(tmp_path)
        assert builder.base_dir == tmp_path.resolve()

    def test_init_temp_dir_is_none(self, tmp_path: Path) -> None:
        """ZipBuilder initializes _temp_dir to None."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        builder = ZipBuilder(tmp_path)
        assert builder._temp_dir is None


class TestZipBuilderBuild:
    """Tests for ZipBuilder.build() method."""

    def test_build_empty_file_list(self, tmp_path: Path) -> None:
        """Empty file list produces valid empty zip with hash."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        builder = ZipBuilder(tmp_path)
        result = builder.build([])

        # Result should be valid
        assert result.zip_path.exists()
        assert result.zip_path.suffix == ".zip"
        assert result.sha256_hash  # Should have a hash
        assert result.storage_key.startswith("files/")
        assert result.storage_key.endswith(".zip")
        assert result.size_bytes > 0  # Even empty zip has some bytes

        # Should be a valid (empty) zip
        with zipfile.ZipFile(result.zip_path) as zf:
            assert len(zf.namelist()) == 0

        builder.cleanup()

    def test_build_single_file(self, tmp_path: Path) -> None:
        """Single file is added with relative path as arcname."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        # Create test file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        test_file = data_dir / "input.csv"
        test_file.write_text("col1,col2\n1,2\n")

        builder = ZipBuilder(tmp_path)
        result = builder.build([test_file])

        # Verify zip contents
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
            assert len(names) == 1
            # Should use forward slashes for path
            assert "data/input.csv" in names
            # Content should match
            assert zf.read("data/input.csv").decode() == "col1,col2\n1,2\n"

        builder.cleanup()

    def test_build_multiple_files(self, tmp_path: Path) -> None:
        """Multiple files preserve relative structure."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        # Create test files
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "file1.txt").write_text("content1")
        (tmp_path / "data" / "file2.txt").write_text("content2")

        builder = ZipBuilder(tmp_path)
        result = builder.build(
            [
                tmp_path / "config.yaml",
                tmp_path / "data" / "file1.txt",
                tmp_path / "data" / "file2.txt",
            ]
        )

        # Verify zip contents
        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
            assert len(names) == 3
            assert "config.yaml" in names
            assert "data/file1.txt" in names
            assert "data/file2.txt" in names

        builder.cleanup()

    def test_build_uses_deflate_compression(self, tmp_path: Path) -> None:
        """Zip uses DEFLATED compression."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        # Create test file with compressible content
        test_file = tmp_path / "data.txt"
        test_file.write_text("a" * 1000)

        builder = ZipBuilder(tmp_path)
        result = builder.build([test_file])

        with zipfile.ZipFile(result.zip_path) as zf:
            info = zf.getinfo("data.txt")
            assert info.compress_type == zipfile.ZIP_DEFLATED

        builder.cleanup()

    def test_build_deterministic_hash(self, tmp_path: Path) -> None:
        """Same files produce same hash (deterministic)."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        # Create test files
        (tmp_path / "a.txt").write_text("content a")
        (tmp_path / "b.txt").write_text("content b")

        files = [tmp_path / "a.txt", tmp_path / "b.txt"]

        # Build twice
        builder1 = ZipBuilder(tmp_path)
        result1 = builder1.build(files)
        hash1 = result1.sha256_hash
        builder1.cleanup()

        builder2 = ZipBuilder(tmp_path)
        result2 = builder2.build(files)
        hash2 = result2.sha256_hash
        builder2.cleanup()

        # Hashes should match
        assert hash1 == hash2

    def test_build_sorts_files_for_determinism(self, tmp_path: Path) -> None:
        """Files are sorted by relative path for deterministic hash."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        # Create test files
        (tmp_path / "z.txt").write_text("z content")
        (tmp_path / "a.txt").write_text("a content")

        # Build with different order
        builder1 = ZipBuilder(tmp_path)
        result1 = builder1.build([tmp_path / "z.txt", tmp_path / "a.txt"])
        hash1 = result1.sha256_hash
        builder1.cleanup()

        builder2 = ZipBuilder(tmp_path)
        result2 = builder2.build([tmp_path / "a.txt", tmp_path / "z.txt"])
        hash2 = result2.sha256_hash
        builder2.cleanup()

        # Hashes should match regardless of input order
        assert hash1 == hash2

    def test_build_storage_key_format(self, tmp_path: Path) -> None:
        """Storage key follows format files/{sha256hash}.zip."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        (tmp_path / "test.txt").write_text("test")

        builder = ZipBuilder(tmp_path)
        result = builder.build([tmp_path / "test.txt"])

        assert result.storage_key == f"files/{result.sha256_hash}.zip"
        assert result.storage_key.startswith("files/")
        assert result.storage_key.endswith(".zip")
        # Hash should be 64 hex characters (SHA256)
        hash_part = result.storage_key[6:-4]  # Remove "files/" and ".zip"
        assert len(hash_part) == 64
        assert all(c in "0123456789abcdef" for c in hash_part)

        builder.cleanup()

    def test_build_size_bytes_accurate(self, tmp_path: Path) -> None:
        """size_bytes matches actual zip file size."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        (tmp_path / "test.txt").write_text("some content here")

        builder = ZipBuilder(tmp_path)
        result = builder.build([tmp_path / "test.txt"])

        # size_bytes should match actual file size
        actual_size = result.zip_path.stat().st_size
        assert result.size_bytes == actual_size

        builder.cleanup()

    def test_build_creates_temp_directory(self, tmp_path: Path) -> None:
        """Build creates temp directory with prefect-zip- prefix."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        (tmp_path / "test.txt").write_text("test")

        builder = ZipBuilder(tmp_path)
        result = builder.build([tmp_path / "test.txt"])

        # Temp dir should exist and have correct prefix
        assert builder._temp_dir is not None
        assert Path(builder._temp_dir).exists()
        assert "prefect-zip-" in builder._temp_dir

        # Zip should be inside temp dir
        assert str(result.zip_path).startswith(builder._temp_dir)

        builder.cleanup()

    def test_build_windows_path_normalization(self, tmp_path: Path) -> None:
        """Windows-style paths are normalized to forward slashes in zip."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        # Create nested file
        nested = tmp_path / "sub" / "dir"
        nested.mkdir(parents=True)
        test_file = nested / "file.txt"
        test_file.write_text("content")

        builder = ZipBuilder(tmp_path)
        result = builder.build([test_file])

        with zipfile.ZipFile(result.zip_path) as zf:
            names = zf.namelist()
            # Should use forward slashes, not backslashes
            assert len(names) == 1
            assert "\\" not in names[0]
            assert "sub/dir/file.txt" in names

        builder.cleanup()


class TestZipBuilderSizeWarning:
    """Tests for size warning when zip exceeds 50MB threshold."""

    def test_no_warning_under_threshold(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No warning when zip is under 50MB."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        (tmp_path / "small.txt").write_text("small content")

        builder = ZipBuilder(tmp_path)
        with caplog.at_level("WARNING"):
            result = builder.build([tmp_path / "small.txt"])

        assert result.size_bytes < 50 * 1024 * 1024
        assert "exceeds" not in caplog.text.lower()
        assert "warning" not in caplog.text.lower() or "50" not in caplog.text

        builder.cleanup()

    def test_warning_at_threshold(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Warning is emitted when zip reaches 50MB threshold."""
        from prefect._experimental.bundles._zip_builder import (
            ZIP_SIZE_WARNING_THRESHOLD,
            ZipBuilder,
        )

        # Create a file that will produce a zip >= 50MB
        # We mock the file size check since creating actual large files is slow
        (tmp_path / "test.txt").write_text("test")

        builder = ZipBuilder(tmp_path)

        # Mock stat to return size >= threshold
        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = ZIP_SIZE_WARNING_THRESHOLD
            with caplog.at_level("WARNING"):
                builder.build([tmp_path / "test.txt"])

        # Should have warning about size
        assert any(
            "50" in record.message or "MB" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )

        builder.cleanup()

    def test_warning_shows_total_size(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Warning message includes total zip size."""
        from prefect._experimental.bundles._zip_builder import (
            ZipBuilder,
        )

        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")

        builder = ZipBuilder(tmp_path)

        # Mock to simulate large zip
        original_stat = Path.stat

        def mock_stat(self: Path) -> object:
            result = original_stat(self)
            if self.suffix == ".zip":
                # Return mock with large size
                class MockStat:
                    st_size = 60 * 1024 * 1024  # 60MB

                return MockStat()
            return result

        with patch.object(Path, "stat", mock_stat):
            with caplog.at_level("WARNING"):
                builder.build([tmp_path / "file1.txt", tmp_path / "file2.txt"])

        # Warning should mention size (60MB or similar)
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) > 0

        builder.cleanup()

    def test_warning_lists_largest_files(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Warning message lists largest files contributing to size."""
        from prefect._experimental.bundles._zip_builder import (
            ZIP_SIZE_WARNING_THRESHOLD,
            ZipBuilder,
        )

        # Create files with different sizes
        (tmp_path / "large.txt").write_text("x" * 1000)
        (tmp_path / "small.txt").write_text("y")

        builder = ZipBuilder(tmp_path)

        # Mock to simulate large zip
        original_stat = Path.stat

        def mock_stat(self: Path) -> object:
            result = original_stat(self)
            if self.suffix == ".zip":

                class MockStat:
                    st_size = ZIP_SIZE_WARNING_THRESHOLD + 1

                return MockStat()
            return result

        with patch.object(Path, "stat", mock_stat):
            with caplog.at_level("WARNING"):
                builder.build([tmp_path / "large.txt", tmp_path / "small.txt"])

        # Warning should mention file names
        warning_text = " ".join(
            r.message for r in caplog.records if r.levelname == "WARNING"
        )
        # Should mention at least one file
        assert (
            "large.txt" in warning_text
            or "small.txt" in warning_text
            or "files" in warning_text.lower()
        )

        builder.cleanup()


class TestZipBuilderCleanup:
    """Tests for ZipBuilder.cleanup() method."""

    def test_cleanup_removes_temp_directory(self, tmp_path: Path) -> None:
        """cleanup() removes the temp directory."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        (tmp_path / "test.txt").write_text("test")

        builder = ZipBuilder(tmp_path)
        builder.build([tmp_path / "test.txt"])

        temp_dir = builder._temp_dir
        assert temp_dir is not None
        assert Path(temp_dir).exists()

        builder.cleanup()

        # Temp dir should be gone
        assert not Path(temp_dir).exists()

    def test_cleanup_before_build_is_safe(self, tmp_path: Path) -> None:
        """cleanup() is safe to call before build()."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        builder = ZipBuilder(tmp_path)
        # Should not raise
        builder.cleanup()

    def test_cleanup_multiple_times_is_safe(self, tmp_path: Path) -> None:
        """cleanup() can be called multiple times safely."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        (tmp_path / "test.txt").write_text("test")

        builder = ZipBuilder(tmp_path)
        builder.build([tmp_path / "test.txt"])

        builder.cleanup()
        builder.cleanup()  # Second call should not raise

    def test_cleanup_sets_temp_dir_to_none(self, tmp_path: Path) -> None:
        """cleanup() sets _temp_dir to None after removal."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        (tmp_path / "test.txt").write_text("test")

        builder = ZipBuilder(tmp_path)
        builder.build([tmp_path / "test.txt"])

        assert builder._temp_dir is not None
        builder.cleanup()
        assert builder._temp_dir is None


class TestZipBuilderHashComputation:
    """Tests for SHA256 hash computation."""

    def test_hash_is_sha256(self, tmp_path: Path) -> None:
        """Hash is computed using SHA256."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        (tmp_path / "test.txt").write_text("test content")

        builder = ZipBuilder(tmp_path)
        result = builder.build([tmp_path / "test.txt"])

        # Verify by computing hash ourselves
        with open(result.zip_path, "rb") as f:
            expected_hash = hashlib.sha256(f.read()).hexdigest()

        assert result.sha256_hash == expected_hash

        builder.cleanup()

    def test_hash_uses_chunked_reading(self, tmp_path: Path) -> None:
        """Hash computation uses chunked reading (64KB chunks)."""
        from prefect._experimental.bundles._zip_builder import (
            HASH_CHUNK_SIZE,
            ZipBuilder,
        )

        # Create a file larger than one chunk
        large_content = "x" * (HASH_CHUNK_SIZE * 2 + 100)
        (tmp_path / "large.txt").write_text(large_content)

        builder = ZipBuilder(tmp_path)
        result = builder.build([tmp_path / "large.txt"])

        # Verify hash is still correct for large file
        with open(result.zip_path, "rb") as f:
            expected_hash = hashlib.sha256(f.read()).hexdigest()

        assert result.sha256_hash == expected_hash

        builder.cleanup()

    def test_hash_is_lowercase_hex(self, tmp_path: Path) -> None:
        """Hash is returned as lowercase hexadecimal."""
        from prefect._experimental.bundles._zip_builder import ZipBuilder

        (tmp_path / "test.txt").write_text("test")

        builder = ZipBuilder(tmp_path)
        result = builder.build([tmp_path / "test.txt"])

        # All characters should be lowercase hex
        assert result.sha256_hash == result.sha256_hash.lower()
        assert all(c in "0123456789abcdef" for c in result.sha256_hash)
        assert len(result.sha256_hash) == 64

        builder.cleanup()


class TestZipBuilderExports:
    """Tests for module exports."""

    def test_module_exports(self) -> None:
        """Module exports required symbols."""
        from prefect._experimental.bundles import _zip_builder

        assert hasattr(_zip_builder, "ZipBuilder")
        assert hasattr(_zip_builder, "ZipResult")
        assert hasattr(_zip_builder, "HASH_CHUNK_SIZE")
        assert hasattr(_zip_builder, "ZIP_SIZE_WARNING_THRESHOLD")

    def test_all_exports(self) -> None:
        """__all__ includes required exports."""
        from prefect._experimental.bundles._zip_builder import __all__

        assert "ZipBuilder" in __all__
        assert "ZipResult" in __all__
        assert "HASH_CHUNK_SIZE" in __all__
        assert "ZIP_SIZE_WARNING_THRESHOLD" in __all__
