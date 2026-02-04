"""
Tests for FileCollector single file collection.

This module tests the FileCollector class's ability to collect single files
by pattern. Tests cover:
- Collecting existing single files
- Handling non-existent files (warning, no error)
- Directory traversal protection
- CollectionResult dataclass behavior
"""

from __future__ import annotations

import platform

import pytest
from prefect._experimental.bundles.file_collector import (
    CollectionResult,
    FileCollector,
)

from prefect._experimental.bundles.path_resolver import PathValidationError


class TestCollectionResult:
    """Tests for CollectionResult dataclass."""

    def test_create_empty_result(self):
        """Test creating an empty CollectionResult."""
        result = CollectionResult()
        assert result.files == []
        assert result.warnings == []
        assert result.total_size == 0
        assert result.patterns_matched == {}

    def test_create_with_files(self, tmp_path):
        """Test creating a CollectionResult with files."""
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"
        file1.touch()
        file2.touch()

        result = CollectionResult(
            files=[file1, file2],
            warnings=[],
            total_size=0,
            patterns_matched={"a.txt": [file1], "b.txt": [file2]},
        )
        assert len(result.files) == 2
        assert file1 in result.files
        assert file2 in result.files

    def test_create_with_warnings(self):
        """Test creating a CollectionResult with warnings."""
        result = CollectionResult(
            files=[],
            warnings=["Pattern 'missing.txt' matched no files"],
            total_size=0,
            patterns_matched={"missing.txt": []},
        )
        assert len(result.warnings) == 1
        assert "missing.txt" in result.warnings[0]

    def test_total_size_tracking(self, tmp_path):
        """Test that total_size is tracked correctly."""
        file = tmp_path / "data.txt"
        file.write_text("12345")  # 5 bytes

        result = CollectionResult(
            files=[file],
            warnings=[],
            total_size=5,
            patterns_matched={"data.txt": [file]},
        )
        assert result.total_size == 5

    def test_patterns_matched_tracking(self, tmp_path):
        """Test patterns_matched tracks which files each pattern matched."""
        file = tmp_path / "config.yaml"
        file.touch()

        result = CollectionResult(
            files=[file],
            warnings=[],
            total_size=0,
            patterns_matched={"config.yaml": [file]},
        )
        assert "config.yaml" in result.patterns_matched
        assert result.patterns_matched["config.yaml"] == [file]


class TestFileCollector:
    """Tests for FileCollector class."""

    def test_init_with_base_dir(self, tmp_path):
        """Test FileCollector initializes with base directory."""
        collector = FileCollector(tmp_path)
        assert collector.base_dir == tmp_path.resolve()

    def test_collect_single_existing_file(self, tmp_path):
        """Test collecting a single existing file."""
        # Setup: create a config file
        config = tmp_path / "config.yaml"
        config.write_text("key: value")

        # Collect the file
        collector = FileCollector(tmp_path)
        result = collector.collect(["config.yaml"])

        # Verify
        assert len(result.files) == 1
        assert result.files[0] == config.resolve()
        assert result.warnings == []
        assert "config.yaml" in result.patterns_matched
        assert result.patterns_matched["config.yaml"] == [config.resolve()]

    def test_collect_single_file_tracks_size(self, tmp_path):
        """Test that file size is tracked in total_size."""
        # Setup: create file with known content
        data_file = tmp_path / "data.txt"
        data_file.write_text("hello world")  # 11 bytes

        collector = FileCollector(tmp_path)
        result = collector.collect(["data.txt"])

        assert result.total_size == 11

    def test_collect_missing_file_adds_warning(self, tmp_path):
        """Test that missing file adds warning instead of raising."""
        collector = FileCollector(tmp_path)
        result = collector.collect(["nonexistent.txt"])

        # Should have warning, not raise
        assert len(result.files) == 0
        assert len(result.warnings) == 1
        assert "nonexistent.txt" in result.warnings[0]
        assert "matched no files" in result.warnings[0].lower()
        # Pattern should be tracked with empty match list
        assert result.patterns_matched["nonexistent.txt"] == []

    def test_collect_multiple_files(self, tmp_path):
        """Test collecting multiple single files."""
        # Setup: create multiple files
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"
        file1.write_text("aaa")
        file2.write_text("bbbbb")

        collector = FileCollector(tmp_path)
        result = collector.collect(["a.txt", "b.txt"])

        assert len(result.files) == 2
        assert file1.resolve() in result.files
        assert file2.resolve() in result.files
        assert result.total_size == 8  # 3 + 5

    def test_collect_mix_of_existing_and_missing(self, tmp_path):
        """Test collecting mix of existing and missing files."""
        # Setup: only create one file
        existing = tmp_path / "exists.txt"
        existing.write_text("content")

        collector = FileCollector(tmp_path)
        result = collector.collect(["exists.txt", "missing.txt"])

        # Should have one file and one warning
        assert len(result.files) == 1
        assert existing.resolve() in result.files
        assert len(result.warnings) == 1
        assert "missing.txt" in result.warnings[0]

    def test_collect_file_in_subdirectory(self, tmp_path):
        """Test collecting a file in a subdirectory."""
        # Setup: create nested file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        nested_file = data_dir / "input.csv"
        nested_file.write_text("col1,col2")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data/input.csv"])

        assert len(result.files) == 1
        assert result.files[0] == nested_file.resolve()

    def test_collect_traversal_raises_error(self, tmp_path):
        """Test that directory traversal raises PathValidationError."""
        collector = FileCollector(tmp_path)

        with pytest.raises(PathValidationError) as exc_info:
            collector.collect(["../escape.txt"])

        assert exc_info.value.error_type == "traversal"

    def test_collect_multiple_traversals_raises_on_first(self, tmp_path):
        """Test that traversal is caught even with valid files."""
        # Setup: create a valid file
        valid = tmp_path / "valid.txt"
        valid.touch()

        collector = FileCollector(tmp_path)

        # Traversal pattern first should raise immediately
        with pytest.raises(PathValidationError) as exc_info:
            collector.collect(["../escape.txt", "valid.txt"])

        assert exc_info.value.error_type == "traversal"

    def test_collect_absolute_path_raises_error(self, tmp_path):
        """Test that absolute paths raise PathValidationError."""
        collector = FileCollector(tmp_path)

        with pytest.raises(PathValidationError) as exc_info:
            collector.collect(["/etc/passwd"])

        assert exc_info.value.error_type == "absolute"

    def test_collect_empty_pattern_raises_error(self, tmp_path):
        """Test that empty pattern raises PathValidationError."""
        collector = FileCollector(tmp_path)

        with pytest.raises(PathValidationError) as exc_info:
            collector.collect([""])

        assert exc_info.value.error_type == "empty"

    def test_collect_dotfile(self, tmp_path):
        """Test collecting a dotfile."""
        dotfile = tmp_path / ".gitignore"
        dotfile.write_text("*.pyc")

        collector = FileCollector(tmp_path)
        result = collector.collect([".gitignore"])

        assert len(result.files) == 1
        assert result.files[0] == dotfile.resolve()

    def test_collect_file_with_backslash_path(self, tmp_path):
        """Test collecting file with Windows-style backslash path."""
        # Setup: create nested file
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        nested_file = data_dir / "file.txt"
        nested_file.write_text("content")

        collector = FileCollector(tmp_path)
        result = collector.collect(["data\\file.txt"])

        assert len(result.files) == 1
        assert result.files[0] == nested_file.resolve()

    def test_collect_empty_list(self, tmp_path):
        """Test collecting with empty pattern list."""
        collector = FileCollector(tmp_path)
        result = collector.collect([])

        assert result.files == []
        assert result.warnings == []
        assert result.total_size == 0
        assert result.patterns_matched == {}


# Skip symlink tests on Windows since symlink creation requires admin privileges
symlink_skip = pytest.mark.skipif(
    platform.system() == "Windows",
    reason="Symlink tests require admin privileges on Windows",
)


@symlink_skip
class TestFileCollectorSymlinks:
    """Tests for FileCollector symlink handling."""

    def test_collect_symlink_within_base_dir(self, tmp_path):
        """Test collecting a symlink that points within base dir."""
        # Setup: create target and symlink
        target = tmp_path / "actual.txt"
        target.write_text("content")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        collector = FileCollector(tmp_path)
        result = collector.collect(["link.txt"])

        # Should resolve to the target file
        assert len(result.files) == 1
        assert result.files[0] == target.resolve()

    def test_collect_symlink_escaping_base_dir_raises(self, tmp_path):
        """Test that symlink escaping base dir raises PathValidationError."""
        # Setup: create target outside base and symlink inside
        base_dir = tmp_path / "project"
        base_dir.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("secret")
        link = base_dir / "sneaky.txt"
        link.symlink_to(outside)

        collector = FileCollector(base_dir)

        with pytest.raises(PathValidationError) as exc_info:
            collector.collect(["sneaky.txt"])

        assert exc_info.value.error_type == "traversal"
