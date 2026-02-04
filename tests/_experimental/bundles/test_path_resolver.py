"""
Tests for path resolution input validation and symlink handling.

This module tests the path validation functions in path_resolver.py.
Includes tests for input validation (no filesystem access) and
symlink resolution tests (uses tmp_path for filesystem operations).
"""

from __future__ import annotations

import platform

import pytest

from prefect._experimental.bundles.path_resolver import (
    MAX_SYMLINK_DEPTH,
    PathResolutionError,
    PathResolver,
    PathValidationError,
    PathValidationResult,
    check_for_duplicates,
    normalize_path_separator,
    resolve_paths,
    resolve_with_symlink_check,
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


# Skip symlink tests on Windows since symlink creation requires admin privileges
symlink_skip = pytest.mark.skipif(
    platform.system() == "Windows",
    reason="Symlink tests require admin privileges on Windows",
)


class TestMaxSymlinkDepth:
    """Tests for MAX_SYMLINK_DEPTH constant."""

    def test_max_symlink_depth_is_10(self):
        """Test that MAX_SYMLINK_DEPTH is set to 10."""
        assert MAX_SYMLINK_DEPTH == 10


@symlink_skip
class TestResolveWithSymlinkCheck:
    """Tests for resolve_with_symlink_check function."""

    def test_regular_file_no_symlink(self, tmp_path):
        """Test that regular file without symlink is resolved correctly."""
        # Setup: create a regular file
        file = tmp_path / "data" / "config.yaml"
        file.parent.mkdir(parents=True)
        file.write_text("config content")

        result = resolve_with_symlink_check(file, tmp_path)
        assert result == file.resolve()

    def test_symlink_within_base_dir(self, tmp_path):
        """Test symlink within base dir pointing to file within base dir is resolved."""
        # Setup: create target file and symlink
        target = tmp_path / "data" / "actual.txt"
        target.parent.mkdir(parents=True)
        target.write_text("actual content")

        link = tmp_path / "link.txt"
        link.symlink_to(target)

        result = resolve_with_symlink_check(link, tmp_path)
        assert result == target.resolve()

    def test_symlink_relative_target(self, tmp_path):
        """Test symlink with relative target path is resolved correctly."""
        # Setup: create target and symlink with relative path
        target = tmp_path / "data" / "file.txt"
        target.parent.mkdir(parents=True)
        target.write_text("content")

        link = tmp_path / "data" / "link.txt"
        # Use relative path for symlink target
        link.symlink_to("file.txt")

        result = resolve_with_symlink_check(link, tmp_path)
        assert result == target.resolve()

    def test_symlink_pointing_outside_base_dir_raises_traversal(self, tmp_path):
        """Test symlink pointing outside base dir raises PathValidationError."""
        # Setup: create base dir and outside target
        base_dir = tmp_path / "project"
        base_dir.mkdir()

        outside_target = tmp_path / "outside" / "secret.txt"
        outside_target.parent.mkdir(parents=True)
        outside_target.write_text("secret content")

        link = base_dir / "sneaky_link.txt"
        link.symlink_to(outside_target)

        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(link, base_dir)
        assert exc_info.value.error_type == "traversal"
        assert "outside" in exc_info.value.message.lower()

    def test_symlink_to_absolute_path_outside_raises_traversal(self, tmp_path):
        """Test symlink to absolute path outside base dir raises error."""
        # Setup: create link pointing to /etc/passwd equivalent
        base_dir = tmp_path / "project"
        base_dir.mkdir()

        outside_target = tmp_path / "outside.txt"
        outside_target.write_text("outside")

        link = base_dir / "link.txt"
        link.symlink_to(outside_target.resolve())  # Absolute path

        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(link, base_dir)
        assert exc_info.value.error_type == "traversal"

    def test_broken_symlink_raises_error(self, tmp_path):
        """Test broken symlink (target doesn't exist) raises PathValidationError."""
        link = tmp_path / "broken_link.txt"
        link.symlink_to(tmp_path / "nonexistent.txt")

        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(link, tmp_path)
        assert exc_info.value.error_type == "broken_symlink"
        assert "exist" in exc_info.value.message.lower()

    def test_symlink_chain_within_limit(self, tmp_path):
        """Test chain of symlinks within limit is resolved."""
        # Setup: create chain of 3 symlinks
        target = tmp_path / "actual.txt"
        target.write_text("content")

        link1 = tmp_path / "link1.txt"
        link1.symlink_to(target)

        link2 = tmp_path / "link2.txt"
        link2.symlink_to(link1)

        link3 = tmp_path / "link3.txt"
        link3.symlink_to(link2)

        result = resolve_with_symlink_check(link3, tmp_path)
        assert result == target.resolve()

    def test_symlink_chain_at_limit(self, tmp_path):
        """Test chain of exactly MAX_SYMLINK_DEPTH symlinks is resolved."""
        target = tmp_path / "actual.txt"
        target.write_text("content")

        prev = target
        for i in range(MAX_SYMLINK_DEPTH):
            link = tmp_path / f"link{i}.txt"
            link.symlink_to(prev)
            prev = link

        result = resolve_with_symlink_check(prev, tmp_path)
        assert result == target.resolve()

    def test_symlink_chain_over_limit_raises_error(self, tmp_path):
        """Test chain exceeding MAX_SYMLINK_DEPTH raises PathValidationError."""
        target = tmp_path / "actual.txt"
        target.write_text("content")

        prev = target
        # Create MAX_SYMLINK_DEPTH + 1 symlinks
        for i in range(MAX_SYMLINK_DEPTH + 1):
            link = tmp_path / f"link{i}.txt"
            link.symlink_to(prev)
            prev = link

        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(prev, tmp_path)
        assert exc_info.value.error_type == "symlink_loop"
        assert str(MAX_SYMLINK_DEPTH) in exc_info.value.message

    def test_circular_symlink_detected(self, tmp_path):
        """Test circular symlink (a -> b -> a) raises PathValidationError."""
        link_a = tmp_path / "a.txt"
        link_b = tmp_path / "b.txt"

        # Create circular reference: a -> b -> a
        link_b.symlink_to(link_a)
        link_a.symlink_to(link_b)

        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(link_a, tmp_path)
        assert exc_info.value.error_type == "symlink_loop"
        assert "circular" in exc_info.value.message.lower()

    def test_self_referential_symlink(self, tmp_path):
        """Test self-referential symlink (a -> a) raises PathValidationError."""
        # Note: Can't create self-ref directly, so we test via a 3-link chain
        link_a = tmp_path / "a.txt"
        link_b = tmp_path / "b.txt"
        link_c = tmp_path / "c.txt"

        # Create chain that loops: a -> b -> c -> a
        link_c.symlink_to(link_a)
        link_b.symlink_to(link_c)
        link_a.symlink_to(link_b)

        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(link_a, tmp_path)
        assert exc_info.value.error_type == "symlink_loop"

    def test_custom_max_depth(self, tmp_path):
        """Test custom max_depth parameter is respected."""
        target = tmp_path / "actual.txt"
        target.write_text("content")

        prev = target
        for i in range(5):
            link = tmp_path / f"link{i}.txt"
            link.symlink_to(prev)
            prev = link

        # With max_depth=3, chain of 5 should fail
        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(prev, tmp_path, max_depth=3)
        assert exc_info.value.error_type == "symlink_loop"

    def test_symlink_to_directory_within_base(self, tmp_path):
        """Test symlink to directory within base dir is resolved."""
        target_dir = tmp_path / "data"
        target_dir.mkdir()

        link = tmp_path / "data_link"
        link.symlink_to(target_dir)

        result = resolve_with_symlink_check(link, tmp_path)
        assert result == target_dir.resolve()

    def test_symlink_escape_via_parent_traversal(self, tmp_path):
        """Test symlink using .. to escape base dir raises error."""
        base_dir = tmp_path / "project" / "flows"
        base_dir.mkdir(parents=True)

        outside = tmp_path / "outside.txt"
        outside.write_text("outside content")

        # Create symlink using relative path with .. to escape
        link = base_dir / "sneaky.txt"
        link.symlink_to("../../outside.txt")

        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(link, base_dir)
        assert exc_info.value.error_type == "traversal"

    def test_suggestion_provided_for_traversal(self, tmp_path):
        """Test that traversal error includes suggestion."""
        base_dir = tmp_path / "project"
        base_dir.mkdir()

        outside = tmp_path / "outside.txt"
        outside.write_text("content")

        link = base_dir / "link.txt"
        link.symlink_to(outside)

        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(link, base_dir)
        assert exc_info.value.suggestion is not None
        assert "within" in exc_info.value.suggestion.lower()

    def test_suggestion_provided_for_broken_symlink(self, tmp_path):
        """Test that broken symlink error includes suggestion."""
        link = tmp_path / "broken.txt"
        link.symlink_to(tmp_path / "nonexistent.txt")

        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(link, tmp_path)
        assert exc_info.value.suggestion is not None
        assert "exist" in exc_info.value.suggestion.lower()

    def test_suggestion_provided_for_symlink_loop(self, tmp_path):
        """Test that symlink loop error includes suggestion."""
        link_a = tmp_path / "a.txt"
        link_b = tmp_path / "b.txt"
        link_b.symlink_to(link_a)
        link_a.symlink_to(link_b)

        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(link_a, tmp_path)
        assert exc_info.value.suggestion is not None
        assert "circular" in exc_info.value.suggestion.lower()

    def test_input_path_preserved_in_error(self, tmp_path):
        """Test that original input path is preserved in error."""
        base_dir = tmp_path / "project"
        base_dir.mkdir()

        outside = tmp_path / "outside.txt"
        outside.write_text("content")

        link = base_dir / "my_link.txt"
        link.symlink_to(outside)

        with pytest.raises(PathValidationError) as exc_info:
            resolve_with_symlink_check(link, base_dir)
        assert str(link) in exc_info.value.input_path


class TestResolveSecurePath:
    """Tests for resolve_secure_path function.

    These tests use real filesystem (tmp_path fixture) to verify
    path resolution and traversal protection.
    """

    def test_simple_relative_path(self, tmp_path):
        """Test resolving a simple relative path to an existing file."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create a test file
        test_file = tmp_path / "config.yaml"
        test_file.write_text("test content")

        # Resolve the path
        result = resolve_secure_path("config.yaml", tmp_path)

        # Should return the resolved path
        assert result == test_file.resolve()
        assert result.exists()

    def test_nested_directory_path(self, tmp_path):
        """Test resolving a path in a nested directory."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create nested structure
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        input_file = data_dir / "input.csv"
        input_file.write_text("col1,col2")

        # Resolve the path
        result = resolve_secure_path("data/input.csv", tmp_path)

        assert result == input_file.resolve()

    def test_dot_relative_path(self, tmp_path):
        """Test resolving a path starting with ./"""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create a test file
        test_file = tmp_path / "data" / "file.txt"
        test_file.parent.mkdir()
        test_file.write_text("content")

        # Resolve with ./ prefix
        result = resolve_secure_path("./data/file.txt", tmp_path)

        assert result == test_file.resolve()

    def test_traversal_single_level_rejected(self, tmp_path):
        """Test that ../config.yaml is rejected as traversal."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create a file outside the base directory
        sibling_dir = tmp_path.parent / "sibling"
        sibling_dir.mkdir(exist_ok=True)
        outside_file = sibling_dir / "config.yaml"
        outside_file.write_text("outside")

        with pytest.raises(PathValidationError) as exc_info:
            resolve_secure_path("../sibling/config.yaml", tmp_path)

        assert exc_info.value.error_type == "traversal"
        assert "traversal" in exc_info.value.message.lower()

    def test_traversal_nested_rejected(self, tmp_path):
        """Test that data/../../etc/passwd style traversal is rejected."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create directory structure
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        with pytest.raises(PathValidationError) as exc_info:
            # This attempts to go outside via nested traversal
            resolve_secure_path("data/../../etc/passwd", tmp_path)

        assert exc_info.value.error_type == "traversal"

    def test_traversal_with_existing_file_outside(self, tmp_path):
        """Test traversal is rejected even when target file exists."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create file outside base directory
        outside_dir = tmp_path.parent / "outside_test"
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "secret.txt"
        outside_file.write_text("secret data")

        # Try to access it via traversal
        with pytest.raises(PathValidationError) as exc_info:
            resolve_secure_path("../outside_test/secret.txt", tmp_path)

        assert exc_info.value.error_type == "traversal"

    def test_nonexistent_file_raises_not_found(self, tmp_path):
        """Test that non-existent file raises PathValidationError with not_found."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        with pytest.raises(PathValidationError) as exc_info:
            resolve_secure_path("nonexistent.txt", tmp_path)

        assert exc_info.value.error_type == "not_found"
        assert "exist" in exc_info.value.message.lower()

    def test_nonexistent_nested_path(self, tmp_path):
        """Test that path with non-existent parent directory raises not_found."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        with pytest.raises(PathValidationError) as exc_info:
            resolve_secure_path("missing/dir/file.txt", tmp_path)

        assert exc_info.value.error_type == "not_found"

    def test_cross_platform_backslash_path(self, tmp_path):
        """Test that Windows-style backslash paths are resolved correctly."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create nested structure
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        test_file = data_dir / "input.csv"
        test_file.write_text("content")

        # Use backslash path (Windows style)
        result = resolve_secure_path("data\\input.csv", tmp_path)

        assert result == test_file.resolve()

    def test_directory_resolution(self, tmp_path):
        """Test resolving a directory path."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create a subdirectory
        sub_dir = tmp_path / "subdir"
        sub_dir.mkdir()

        result = resolve_secure_path("subdir", tmp_path)

        assert result == sub_dir.resolve()
        assert result.is_dir()

    def test_dotfile_resolution(self, tmp_path):
        """Test resolving a dotfile path."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create a dotfile
        dotfile = tmp_path / ".gitignore"
        dotfile.write_text("*.pyc")

        result = resolve_secure_path(".gitignore", tmp_path)

        assert result == dotfile.resolve()

    def test_hidden_directory_resolution(self, tmp_path):
        """Test resolving a path in a hidden directory."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create hidden directory structure
        hidden_dir = tmp_path / ".config"
        hidden_dir.mkdir()
        config_file = hidden_dir / "settings.yaml"
        config_file.write_text("setting: value")

        result = resolve_secure_path(".config/settings.yaml", tmp_path)

        assert result == config_file.resolve()

    def test_traversal_that_returns_to_base(self, tmp_path):
        """Test path that goes up and back down stays in base."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create structure
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")

        # data/../file.txt goes up one then stays in base - this SHOULD work
        result = resolve_secure_path("data/../file.txt", tmp_path)
        assert result == test_file.resolve()

    def test_multiple_traversal_within_base(self, tmp_path):
        """Test multiple parent refs that stay within base directory."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create deep structure
        deep_dir = tmp_path / "a" / "b" / "c"
        deep_dir.mkdir(parents=True)
        target = tmp_path / "a" / "target.txt"
        target.write_text("content")

        # Go into c, then back up to a
        result = resolve_secure_path("a/b/c/../../target.txt", tmp_path)
        assert result == target.resolve()

    def test_input_validation_still_applied(self, tmp_path):
        """Test that input validation from Plan 01 is still applied."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Empty string should fail input validation
        with pytest.raises(PathValidationError) as exc_info:
            resolve_secure_path("", tmp_path)
        assert exc_info.value.error_type == "empty"

        # Null byte should fail input validation
        with pytest.raises(PathValidationError) as exc_info:
            resolve_secure_path("file\x00.txt", tmp_path)
        assert exc_info.value.error_type == "null_byte"

        # Absolute path should fail input validation
        with pytest.raises(PathValidationError) as exc_info:
            resolve_secure_path("/absolute/path", tmp_path)
        assert exc_info.value.error_type == "absolute"

    def test_resolved_path_contains_suggestion(self, tmp_path):
        """Test that traversal errors include helpful suggestion."""
        from prefect._experimental.bundles.path_resolver import resolve_secure_path

        # Create the parent structure to ensure file exists
        outside_dir = tmp_path.parent / "suggestions_test"
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "file.txt"
        outside_file.write_text("content")

        with pytest.raises(PathValidationError) as exc_info:
            resolve_secure_path("../suggestions_test/file.txt", tmp_path)

        assert exc_info.value.suggestion is not None
        assert (
            "flow" in exc_info.value.suggestion.lower()
            or "within" in exc_info.value.suggestion.lower()
        )


class TestPathResolver:
    """Tests for PathResolver class."""

    def test_resolve_caches_successful_resolution(self, tmp_path):
        """Successful resolutions are cached."""
        (tmp_path / "config.yaml").touch()
        resolver = PathResolver(tmp_path)

        # First resolution
        result1 = resolver.resolve("config.yaml")
        # Second resolution should use cache
        result2 = resolver.resolve("config.yaml")

        assert result1 == result2
        assert "config.yaml" in resolver._cache

    def test_resolve_caches_errors(self, tmp_path):
        """Failed resolutions are cached to avoid repeated filesystem access."""
        resolver = PathResolver(tmp_path)

        # First attempt fails
        with pytest.raises(PathValidationError) as exc1:
            resolver.resolve("nonexistent.txt")

        # Second attempt should raise same cached error
        with pytest.raises(PathValidationError) as exc2:
            resolver.resolve("nonexistent.txt")

        assert exc1.value.error_type == exc2.value.error_type

    def test_resolve_all_collects_all_errors(self, tmp_path):
        """resolve_all collects ALL errors, doesn't stop on first."""
        (tmp_path / "valid.txt").touch()
        resolver = PathResolver(tmp_path)

        result = resolver.resolve_all(
            [
                "valid.txt",  # Valid
                "",  # Error: empty
                "missing.txt",  # Error: not found
                "/absolute/path",  # Error: absolute
            ]
        )

        # Should have 1 valid path and 3 errors
        assert len(result.valid_paths) == 1
        assert len(result.errors) == 3
        assert result.has_errors

        # Check error types
        error_types = {e.error_type for e in result.errors}
        assert "empty" in error_types
        assert "not_found" in error_types
        assert "absolute" in error_types

    def test_resolve_all_detects_duplicates(self, tmp_path):
        """Duplicate paths are detected and reported."""
        (tmp_path / "config.yaml").touch()
        resolver = PathResolver(tmp_path)

        result = resolver.resolve_all(
            [
                "config.yaml",
                "config.yaml",  # Duplicate
            ]
        )

        assert len(result.errors) == 1
        assert result.errors[0].error_type == "duplicate"

    def test_clear_cache(self, tmp_path):
        """Cache can be cleared."""
        (tmp_path / "file.txt").touch()
        resolver = PathResolver(tmp_path)

        resolver.resolve("file.txt")
        assert len(resolver._cache) == 1

        resolver.clear_cache()
        assert len(resolver._cache) == 0


class TestResolvePaths:
    """Tests for resolve_paths convenience function."""

    def test_resolve_paths_raises_by_default(self, tmp_path):
        """resolve_paths raises PathResolutionError by default."""
        with pytest.raises(PathResolutionError) as exc_info:
            resolve_paths(["nonexistent.txt"], tmp_path)

        assert "path validation error" in str(exc_info.value).lower()

    def test_resolve_paths_no_raise_returns_errors(self, tmp_path):
        """resolve_paths with raise_on_errors=False returns errors."""
        result = resolve_paths(["nonexistent.txt"], tmp_path, raise_on_errors=False)

        assert result.has_errors
        assert len(result.errors) == 1

    def test_resolve_paths_success(self, tmp_path):
        """resolve_paths succeeds with valid paths."""
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()

        result = resolve_paths(["a.txt", "b.txt"], tmp_path)

        assert not result.has_errors
        assert len(result.valid_paths) == 2

    def test_resolve_paths_error_message_includes_all_errors(self, tmp_path):
        """PathResolutionError message includes all failed paths."""
        try:
            resolve_paths(["missing1.txt", "missing2.txt", ""], tmp_path)
            pytest.fail("Should have raised PathResolutionError")
        except PathResolutionError as e:
            error_str = str(e)
            assert "3" in error_str  # 3 errors
            assert "missing1.txt" in error_str or "not_found" in error_str
