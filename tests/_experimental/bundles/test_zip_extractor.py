"""
Tests for ZipExtractor class.

ZipExtractor extracts files from a zip archive to the working directory,
preserving relative paths and handling overwrites with warnings.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest


class TestZipExtractorImports:
    """Tests for module imports."""

    def test_zip_extractor_importable(self) -> None:
        """ZipExtractor can be imported from module."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        assert ZipExtractor is not None


class TestZipExtractorInit:
    """Tests for ZipExtractor initialization."""

    def test_init_stores_zip_path(self, tmp_path: Path) -> None:
        """Constructor stores zip_path attribute."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = tmp_path / "test.zip"
        extractor = ZipExtractor(zip_path)
        assert extractor.zip_path == zip_path

    def test_init_accepts_path_object(self, tmp_path: Path) -> None:
        """Constructor accepts Path object."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = tmp_path / "test.zip"
        extractor = ZipExtractor(zip_path)
        assert isinstance(extractor.zip_path, Path)
        assert extractor.zip_path == zip_path

    def test_init_accepts_string_path(self, tmp_path: Path) -> None:
        """Constructor accepts string path and converts to Path."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = str(tmp_path / "test.zip")
        extractor = ZipExtractor(zip_path)
        assert isinstance(extractor.zip_path, Path)
        assert extractor.zip_path == Path(zip_path)

    def test_init_extracted_flag_false(self, tmp_path: Path) -> None:
        """_extracted flag is False initially."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = tmp_path / "test.zip"
        extractor = ZipExtractor(zip_path)
        assert extractor._extracted is False


class TestZipExtractorExtract:
    """Tests for ZipExtractor.extract() method."""

    @pytest.fixture
    def create_test_zip(self, tmp_path: Path):
        """Factory fixture to create test zip files."""

        def _create(files: dict[str, str]) -> Path:
            """Create a zip with the given files. Keys are paths, values are content."""
            zip_path = tmp_path / "test.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for path, content in files.items():
                    zf.writestr(path, content)
            return zip_path

        return _create

    def test_extract_single_file(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Single file is extracted to target directory."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"config.yaml": "key: value"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(target_dir)

        assert (target_dir / "config.yaml").exists()
        assert (target_dir / "config.yaml").read_text() == "key: value"

    def test_extract_preserves_relative_paths(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Nested directory structure is preserved (data/input.csv -> ./data/input.csv)."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"data/input.csv": "a,b,c"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(target_dir)

        assert (target_dir / "data" / "input.csv").exists()
        assert (target_dir / "data" / "input.csv").read_text() == "a,b,c"

    def test_extract_creates_parent_directories(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Creates parent directories as needed."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"deeply/nested/file.txt": "content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(target_dir)

        assert (target_dir / "deeply" / "nested" / "file.txt").exists()

    def test_extract_to_cwd_by_default(
        self, tmp_path: Path, create_test_zip: callable, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Uses cwd when no target specified."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"default.txt": "default content"})
        work_dir = tmp_path / "workdir"
        work_dir.mkdir()
        monkeypatch.chdir(work_dir)

        extractor = ZipExtractor(zip_path)
        extractor.extract()

        assert (work_dir / "default.txt").exists()
        assert (work_dir / "default.txt").read_text() == "default content"

    def test_extract_to_custom_target_dir(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Accepts custom target directory."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"custom.txt": "custom content"})
        custom_dir = tmp_path / "custom_output"
        custom_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(custom_dir)

        assert (custom_dir / "custom.txt").exists()

    def test_extract_returns_list_of_paths(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Returns list of extracted file paths."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip(
            {"file1.txt": "content1", "dir/file2.txt": "content2"}
        )
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        result = extractor.extract(target_dir)

        assert isinstance(result, list)
        assert len(result) == 2
        assert target_dir / "file1.txt" in result
        assert target_dir / "dir" / "file2.txt" in result

    def test_extract_sets_extracted_flag(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Sets _extracted to True after successful extraction."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"file.txt": "content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        assert extractor._extracted is False
        extractor.extract(target_dir)
        assert extractor._extracted is True

    def test_extract_multiple_files(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Multiple files are extracted correctly."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip(
            {
                "root.txt": "root content",
                "dir1/file1.txt": "file1 content",
                "dir1/file2.txt": "file2 content",
                "dir2/nested/deep.txt": "deep content",
            }
        )
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        result = extractor.extract(target_dir)

        assert len(result) == 4
        assert (target_dir / "root.txt").read_text() == "root content"
        assert (target_dir / "dir1" / "file1.txt").read_text() == "file1 content"
        assert (target_dir / "dir1" / "file2.txt").read_text() == "file2 content"
        assert (
            target_dir / "dir2" / "nested" / "deep.txt"
        ).read_text() == "deep content"


class TestZipExtractorOverwrite:
    """Tests for overwrite behavior with warnings."""

    @pytest.fixture
    def create_test_zip(self, tmp_path: Path):
        """Factory fixture to create test zip files."""

        def _create(files: dict[str, str]) -> Path:
            """Create a zip with the given files. Keys are paths, values are content."""
            zip_path = tmp_path / "test.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for path, content in files.items():
                    zf.writestr(path, content)
            return zip_path

        return _create

    def test_extract_overwrites_existing_file(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Existing file is overwritten by extraction."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"config.yaml": "new content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        # Create existing file with different content
        existing_file = target_dir / "config.yaml"
        existing_file.write_text("old content")

        extractor = ZipExtractor(zip_path)
        extractor.extract(target_dir)

        assert existing_file.read_text() == "new content"

    def test_extract_logs_warning_on_overwrite(
        self,
        tmp_path: Path,
        create_test_zip: callable,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warning is logged when overwriting existing file."""
        import logging

        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"config.yaml": "new content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        # Create existing file
        existing_file = target_dir / "config.yaml"
        existing_file.write_text("old content")

        extractor = ZipExtractor(zip_path)
        with caplog.at_level(logging.WARNING):
            extractor.extract(target_dir)

        assert "Overwriting existing file: config.yaml" in caplog.text

    def test_extract_overwrites_multiple_files(
        self,
        tmp_path: Path,
        create_test_zip: callable,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Multiple existing files are overwritten with warnings."""
        import logging

        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"file1.txt": "new1", "dir/file2.txt": "new2"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()
        (target_dir / "dir").mkdir()

        # Create existing files
        (target_dir / "file1.txt").write_text("old1")
        (target_dir / "dir" / "file2.txt").write_text("old2")

        extractor = ZipExtractor(zip_path)
        with caplog.at_level(logging.WARNING):
            extractor.extract(target_dir)

        # Verify files overwritten
        assert (target_dir / "file1.txt").read_text() == "new1"
        assert (target_dir / "dir" / "file2.txt").read_text() == "new2"

        # Verify warnings logged
        assert "Overwriting existing file: file1.txt" in caplog.text
        assert "Overwriting existing file: dir/file2.txt" in caplog.text

    def test_extract_no_warning_for_new_files(
        self,
        tmp_path: Path,
        create_test_zip: callable,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """No warning when file doesn't exist."""
        import logging

        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"newfile.txt": "content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        with caplog.at_level(logging.WARNING):
            extractor.extract(target_dir)

        assert "Overwriting" not in caplog.text


class TestZipExtractorTypeMismatch:
    """Tests for file/directory type mismatch detection."""

    @pytest.fixture
    def create_test_zip(self, tmp_path: Path):
        """Factory fixture to create test zip files."""

        def _create(files: dict[str, str]) -> Path:
            """Create a zip with the given files. Keys are paths, values are content."""
            zip_path = tmp_path / "test.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for path, content in files.items():
                    zf.writestr(path, content)
            return zip_path

        return _create

    def test_extract_fails_file_over_directory(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Error when file in zip would overwrite existing directory."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        # Create zip with a file named "data"
        zip_path = create_test_zip({"data": "file content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        # Create existing directory with same name
        (target_dir / "data").mkdir()

        extractor = ZipExtractor(zip_path)
        with pytest.raises(RuntimeError) as exc_info:
            extractor.extract(target_dir)

        assert "data" in str(exc_info.value)
        assert "directory" in str(exc_info.value).lower()

    def test_extract_fails_directory_over_file(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Error when directory in zip would overwrite existing file."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        # Create zip with a directory entry and file inside
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Explicitly add directory entry
            zf.writestr("config/", "")
            zf.writestr("config/settings.yaml", "key: value")

        target_dir = tmp_path / "output"
        target_dir.mkdir()

        # Create existing file with same name as directory
        (target_dir / "config").write_text("i am a file")

        extractor = ZipExtractor(zip_path)
        with pytest.raises(RuntimeError) as exc_info:
            extractor.extract(target_dir)

        assert "config" in str(exc_info.value)
        assert "file" in str(exc_info.value).lower()

    def test_extract_error_message_includes_path(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Error message includes the problematic path."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        # Create zip with a file named "conflicting_name"
        zip_path = create_test_zip({"conflicting_name": "content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        # Create existing directory with same name
        (target_dir / "conflicting_name").mkdir()

        extractor = ZipExtractor(zip_path)
        with pytest.raises(RuntimeError) as exc_info:
            extractor.extract(target_dir)

        assert "conflicting_name" in str(exc_info.value)

    def test_extract_type_mismatch_before_any_extraction(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """No files are extracted when type mismatch is detected."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        # Create zip with multiple files, one will conflict
        zip_path = create_test_zip(
            {"goodfile.txt": "good content", "badname": "bad content"}
        )
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        # Create existing directory that conflicts with "badname" file
        (target_dir / "badname").mkdir()

        extractor = ZipExtractor(zip_path)
        with pytest.raises(RuntimeError):
            extractor.extract(target_dir)

        # Verify no files were extracted
        assert not (target_dir / "goodfile.txt").exists()
        assert extractor._extracted is False


class TestZipExtractorCleanup:
    """Tests for cleanup() method behavior."""

    @pytest.fixture
    def create_test_zip(self, tmp_path: Path):
        """Factory fixture to create test zip files."""

        def _create(files: dict[str, str]) -> Path:
            """Create a zip with the given files. Keys are paths, values are content."""
            zip_path = tmp_path / "test.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for path, content in files.items():
                    zf.writestr(path, content)
            return zip_path

        return _create

    def test_cleanup_deletes_zip_file(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Zip file is deleted after cleanup."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"file.txt": "content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(target_dir)
        assert zip_path.exists()

        extractor.cleanup()
        assert not zip_path.exists()

    def test_cleanup_only_after_successful_extract(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Cleanup skips deletion if extraction not completed."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"file.txt": "content"})

        extractor = ZipExtractor(zip_path)
        # Don't call extract
        extractor.cleanup()

        # Zip should still exist
        assert zip_path.exists()

    def test_cleanup_logs_warning_if_not_extracted(
        self,
        tmp_path: Path,
        create_test_zip: callable,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warning is logged when cleanup called before extract."""
        import logging

        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"file.txt": "content"})

        extractor = ZipExtractor(zip_path)
        with caplog.at_level(logging.WARNING):
            extractor.cleanup()

        assert "extraction not completed" in caplog.text.lower()

    def test_cleanup_logs_warning_on_delete_failure(
        self,
        tmp_path: Path,
        create_test_zip: callable,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warning is logged if deletion fails (doesn't raise)."""
        import logging
        from unittest.mock import patch

        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"file.txt": "content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(target_dir)

        # Mock unlink to raise OSError
        with (
            patch.object(zip_path, "unlink", side_effect=OSError("Permission denied")),
            caplog.at_level(logging.WARNING),
        ):
            # Should not raise
            extractor.cleanup()

        assert "Failed to delete" in caplog.text

    def test_cleanup_safe_to_call_multiple_times(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Multiple cleanup calls don't raise."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"file.txt": "content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(target_dir)

        # Call cleanup multiple times - should not raise
        extractor.cleanup()
        extractor.cleanup()
        extractor.cleanup()

    def test_cleanup_handles_missing_file(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """No error if zip file was already deleted."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"file.txt": "content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(target_dir)

        # Delete file manually before cleanup
        zip_path.unlink()

        # Should not raise
        extractor.cleanup()
