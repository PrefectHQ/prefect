"""
Tests for path resolution input validation.

This module tests the path validation functions in path_resolver.py.
All tests focus on input validation (no filesystem access).
"""

from __future__ import annotations

import platform

import pytest
from prefect._experimental.bundles.path_resolver import (
    PathResolutionError,
    PathValidationError,
    PathValidationResult,
    check_for_duplicates,
    normalize_path_separator,
    validate_path_input,
)


class TestPathValidationError:
    """Tests for PathValidationError dataclass."""

    def test_create_with_required_fields(self):
        """Test creating a PathValidationError with required fields."""
        error = PathValidationError(
            input_path="test.txt",
            resolved_path=None,
            error_type="empty",
            message="Path cannot be empty",
        )
        assert error.input_path == "test.txt"
        assert error.resolved_path is None
        assert error.error_type == "empty"
        assert error.message == "Path cannot be empty"
        assert error.suggestion is None

    def test_create_with_suggestion(self):
        """Test creating a PathValidationError with optional suggestion."""
        error = PathValidationError(
            input_path="/absolute/path",
            resolved_path="/absolute/path",
            error_type="absolute",
            message="Absolute paths not allowed",
            suggestion="Use relative path from flow file directory",
        )
        assert error.suggestion == "Use relative path from flow file directory"

    def test_all_error_types_are_valid(self):
        """Test that all documented error types can be used."""
        valid_error_types = [
            "empty",
            "whitespace",
            "null_byte",
            "absolute",
            "duplicate",
            "traversal",
            "symlink_loop",
            "broken_symlink",
            "not_found",
        ]
        for error_type in valid_error_types:
            error = PathValidationError(
                input_path="test",
                resolved_path=None,
                error_type=error_type,
                message=f"Error: {error_type}",
            )
            assert error.error_type == error_type


class TestPathValidationResult:
    """Tests for PathValidationResult dataclass."""

    def test_create_empty_result(self):
        """Test creating an empty validation result."""
        result = PathValidationResult()
        assert result.valid_paths == []
        assert result.errors == []
        assert result.has_errors is False

    def test_has_errors_with_errors(self):
        """Test has_errors property returns True when errors exist."""
        error = PathValidationError(
            input_path="",
            resolved_path=None,
            error_type="empty",
            message="Path cannot be empty",
        )
        result = PathValidationResult(errors=[error])
        assert result.has_errors is True

    def test_has_errors_without_errors(self):
        """Test has_errors property returns False when no errors."""
        result = PathValidationResult(valid_paths=[])
        assert result.has_errors is False

    def test_raise_if_errors_with_no_errors(self):
        """Test raise_if_errors does nothing when no errors."""
        result = PathValidationResult()
        result.raise_if_errors()  # Should not raise

    def test_raise_if_errors_with_errors(self):
        """Test raise_if_errors raises PathResolutionError when errors exist."""
        error = PathValidationError(
            input_path="",
            resolved_path=None,
            error_type="empty",
            message="Path cannot be empty",
        )
        result = PathValidationResult(errors=[error])
        with pytest.raises(PathResolutionError):
            result.raise_if_errors()


class TestPathResolutionError:
    """Tests for PathResolutionError exception."""

    def test_format_single_error(self):
        """Test exception message format with single error."""
        error = PathValidationError(
            input_path="",
            resolved_path=None,
            error_type="empty",
            message="Path cannot be empty",
        )
        exc = PathResolutionError([error])
        assert "1 path validation error" in str(exc)
        assert "Path cannot be empty" in str(exc)

    def test_format_multiple_errors(self):
        """Test exception message format with multiple errors."""
        errors = [
            PathValidationError(
                input_path="",
                resolved_path=None,
                error_type="empty",
                message="Path cannot be empty",
            ),
            PathValidationError(
                input_path="/abs/path",
                resolved_path=None,
                error_type="absolute",
                message="Absolute paths not allowed",
            ),
        ]
        exc = PathResolutionError(errors)
        assert "2 path validation error" in str(exc)
        assert "Path cannot be empty" in str(exc)
        assert "Absolute paths not allowed" in str(exc)

    def test_errors_accessible_on_exception(self):
        """Test that errors list is accessible on the exception."""
        error = PathValidationError(
            input_path="test",
            resolved_path=None,
            error_type="empty",
            message="Test error",
        )
        exc = PathResolutionError([error])
        assert exc.errors == [error]


class TestValidatePathInput:
    """Tests for validate_path_input function."""

    def test_empty_string_rejected(self):
        """Test that empty string raises PathValidationError."""
        with pytest.raises(PathValidationError) as exc_info:
            validate_path_input("")
        assert exc_info.value.error_type == "empty"
        assert "empty" in exc_info.value.message.lower()

    def test_whitespace_only_rejected(self):
        """Test that whitespace-only string raises PathValidationError."""
        with pytest.raises(PathValidationError) as exc_info:
            validate_path_input("   ")
        assert exc_info.value.error_type == "whitespace"
        assert "whitespace" in exc_info.value.message.lower()

    def test_tabs_only_rejected(self):
        """Test that tabs-only string raises PathValidationError."""
        with pytest.raises(PathValidationError) as exc_info:
            validate_path_input("\t\t")
        assert exc_info.value.error_type == "whitespace"

    def test_newlines_only_rejected(self):
        """Test that newlines-only string raises PathValidationError."""
        with pytest.raises(PathValidationError) as exc_info:
            validate_path_input("\n\n")
        assert exc_info.value.error_type == "whitespace"

    def test_null_byte_rejected(self):
        """Test that path with null byte raises PathValidationError."""
        with pytest.raises(PathValidationError) as exc_info:
            validate_path_input("path\x00.txt")
        assert exc_info.value.error_type == "null_byte"
        assert "null" in exc_info.value.message.lower()

    def test_null_byte_at_start(self):
        """Test that null byte at start is rejected."""
        with pytest.raises(PathValidationError) as exc_info:
            validate_path_input("\x00path.txt")
        assert exc_info.value.error_type == "null_byte"

    def test_null_byte_at_end(self):
        """Test that null byte at end is rejected."""
        with pytest.raises(PathValidationError) as exc_info:
            validate_path_input("path.txt\x00")
        assert exc_info.value.error_type == "null_byte"

    def test_absolute_path_unix_rejected(self):
        """Test that absolute Unix path raises PathValidationError."""
        with pytest.raises(PathValidationError) as exc_info:
            validate_path_input("/absolute/path")
        assert exc_info.value.error_type == "absolute"
        assert "absolute" in exc_info.value.message.lower()
        assert exc_info.value.suggestion is not None
        assert "relative" in exc_info.value.suggestion.lower()

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only test")
    def test_absolute_path_windows_drive_rejected(self):
        """Test that Windows drive path raises PathValidationError."""
        with pytest.raises(PathValidationError) as exc_info:
            validate_path_input("C:\\Users\\path")
        assert exc_info.value.error_type == "absolute"

    def test_absolute_path_windows_drive_on_any_platform(self):
        """Test that Windows drive path is detected on any platform."""
        # Windows paths like C:\\ are considered absolute even on Unix
        with pytest.raises(PathValidationError) as exc_info:
            validate_path_input("C:\\absolute\\path")
        assert exc_info.value.error_type == "absolute"

    def test_valid_relative_path_accepted(self):
        """Test that valid relative path does not raise."""
        validate_path_input("config.yaml")  # Should not raise

    def test_valid_relative_path_with_dot(self):
        """Test that path starting with ./ does not raise."""
        validate_path_input("./config.yaml")  # Should not raise

    def test_valid_relative_path_with_subdirectory(self):
        """Test that path with subdirectory does not raise."""
        validate_path_input("data/file.txt")  # Should not raise

    def test_valid_path_with_backslashes(self):
        """Test that backslashes in path are allowed as input."""
        validate_path_input("data\\file.txt")  # Should not raise

    def test_valid_path_with_parent_reference(self):
        """Test that parent reference in relative path is allowed at input validation stage."""
        # Note: traversal detection happens during resolution, not input validation
        validate_path_input("../sibling/file.txt")  # Should not raise at input stage

    def test_valid_dotfile(self):
        """Test that dotfile paths are valid."""
        validate_path_input(".gitignore")  # Should not raise

    def test_valid_hidden_directory(self):
        """Test that hidden directory paths are valid."""
        validate_path_input(".config/settings.yaml")  # Should not raise


class TestCheckForDuplicates:
    """Tests for check_for_duplicates function."""

    def test_no_duplicates(self):
        """Test that unique paths return empty list."""
        paths = ["a.txt", "b.txt", "c.txt"]
        duplicates = check_for_duplicates(paths)
        assert duplicates == []

    def test_exact_duplicate(self):
        """Test that exact duplicate is detected."""
        paths = ["a.txt", "b.txt", "a.txt"]
        duplicates = check_for_duplicates(paths)
        assert duplicates == ["a.txt"]

    def test_multiple_duplicates(self):
        """Test that multiple duplicates are detected."""
        paths = ["a.txt", "b.txt", "a.txt", "b.txt", "c.txt"]
        duplicates = check_for_duplicates(paths)
        assert "a.txt" in duplicates
        assert "b.txt" in duplicates
        assert len(duplicates) == 2

    def test_triple_occurrence(self):
        """Test that third occurrence is also reported."""
        paths = ["a.txt", "a.txt", "a.txt"]
        duplicates = check_for_duplicates(paths)
        # Both second and third occurrences should be reported
        assert duplicates == ["a.txt", "a.txt"]

    def test_different_paths_not_normalized(self):
        """Test that paths with .. are NOT normalized (string comparison only)."""
        # data/../a.txt and a.txt are different strings
        paths = ["a.txt", "data/../a.txt"]
        duplicates = check_for_duplicates(paths)
        assert duplicates == []

    def test_backslash_normalized_for_comparison(self):
        """Test that backslashes are normalized to forward slashes for comparison."""
        paths = ["data/file.txt", "data\\file.txt"]
        duplicates = check_for_duplicates(paths)
        # These should be detected as duplicates
        assert "data\\file.txt" in duplicates

    def test_trailing_slash_normalized(self):
        """Test that trailing slashes are normalized for comparison."""
        paths = ["data/", "data"]
        duplicates = check_for_duplicates(paths)
        # These should be detected as duplicates
        assert len(duplicates) == 1

    def test_preserves_original_path_strings(self):
        """Test that original path strings are returned, not normalized versions."""
        paths = ["data/file.txt", "data\\file.txt"]
        duplicates = check_for_duplicates(paths)
        # Should return the original backslash version
        assert duplicates == ["data\\file.txt"]

    def test_empty_list(self):
        """Test that empty list returns empty list."""
        duplicates = check_for_duplicates([])
        assert duplicates == []

    def test_single_item(self):
        """Test that single item list returns empty list."""
        duplicates = check_for_duplicates(["a.txt"])
        assert duplicates == []

    def test_case_sensitive(self):
        """Test that comparison is case-sensitive."""
        paths = ["File.txt", "file.txt"]
        duplicates = check_for_duplicates(paths)
        # These are different paths (case matters on most filesystems)
        assert duplicates == []


class TestNormalizePathSeparator:
    """Tests for normalize_path_separator function."""

    def test_backslash_to_forward_slash(self):
        """Test that backslashes are converted to forward slashes."""
        assert normalize_path_separator("data\\file.txt") == "data/file.txt"

    def test_multiple_backslashes(self):
        """Test that multiple backslashes are converted."""
        assert (
            normalize_path_separator("path\\to\\deeply\\nested\\file.txt")
            == "path/to/deeply/nested/file.txt"
        )

    def test_forward_slashes_unchanged(self):
        """Test that forward slashes remain unchanged."""
        assert normalize_path_separator("data/file.txt") == "data/file.txt"

    def test_mixed_slashes(self):
        """Test that mixed slashes are normalized."""
        assert (
            normalize_path_separator("path\\to/mixed/file.txt")
            == "path/to/mixed/file.txt"
        )

    def test_no_slashes(self):
        """Test that path without slashes is unchanged."""
        assert normalize_path_separator("file.txt") == "file.txt"

    def test_empty_string(self):
        """Test that empty string returns empty string."""
        assert normalize_path_separator("") == ""

    def test_dot_path(self):
        """Test that dot path is handled."""
        assert normalize_path_separator(".\\config") == "./config"

    def test_double_dot_path(self):
        """Test that parent reference path is handled."""
        assert normalize_path_separator("..\\sibling") == "../sibling"

    def test_windows_style_path(self):
        """Test full Windows-style path conversion."""
        assert (
            normalize_path_separator("src\\prefect\\bundles\\__init__.py")
            == "src/prefect/bundles/__init__.py"
        )
