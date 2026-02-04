"""
Path resolution and validation utilities for bundles.

This module provides functions for validating user-provided paths
before resolution and collection. All validation is performed on
the path strings without filesystem access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class PathValidationError(Exception):
    """
    Represents a single path validation error.

    This exception is raised when a path fails validation. It can also
    be collected in a PathValidationResult for batch validation.

    Attributes:
        input_path: The original user-provided path string.
        resolved_path: The resolved path, if resolution was attempted.
        error_type: Type of error (empty, whitespace, null_byte, absolute,
                   duplicate, traversal, symlink_loop, broken_symlink, not_found).
        message: Human-readable error message.
        suggestion: Optional suggestion for fixing the error.
    """

    def __init__(
        self,
        input_path: str,
        resolved_path: str | None,
        error_type: str,
        message: str,
        suggestion: str | None = None,
    ) -> None:
        self.input_path = input_path
        self.resolved_path = resolved_path
        self.error_type = error_type
        self.message = message
        self.suggestion = suggestion
        super().__init__(message)


@dataclass
class PathValidationResult:
    """
    Result of batch path validation.

    Collects all validation errors before failing, allowing users
    to see all problems at once rather than fixing one at a time.

    Attributes:
        valid_paths: List of successfully validated paths.
        errors: List of validation errors encountered.
    """

    valid_paths: list[Path] = field(default_factory=list)
    errors: list[PathValidationError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Return True if any validation errors were collected."""
        return len(self.errors) > 0

    def raise_if_errors(self) -> None:
        """
        Raise PathResolutionError if any errors were collected.

        Raises:
            PathResolutionError: If self.errors is non-empty.
        """
        if self.errors:
            raise PathResolutionError(self.errors)


class PathResolutionError(Exception):
    """
    Exception raised when path validation fails.

    Contains all collected validation errors, formatted for clear
    error reporting.

    Attributes:
        errors: List of PathValidationError instances.
    """

    def __init__(self, errors: list[PathValidationError]) -> None:
        self.errors = errors
        message = self._format_message()
        super().__init__(message)

    def _format_message(self) -> str:
        """Format all errors into a single exception message."""
        count = len(self.errors)
        plural = "" if count == 1 else "s"
        lines = [f"{count} path validation error{plural}:"]

        for error in self.errors:
            lines.append(f"  - {error.input_path!r}: {error.message}")

        return "\n".join(lines)


def validate_path_input(path: str) -> None:
    """
    Validate a user-provided path string before resolution.

    Performs basic input validation without filesystem access:
    - Rejects empty strings
    - Rejects whitespace-only strings
    - Rejects strings containing null bytes
    - Rejects absolute paths

    Args:
        path: User-provided path string to validate.

    Raises:
        PathValidationError: If the path fails validation.
    """
    # Check for empty string
    if not path:
        raise PathValidationError(
            input_path=path,
            resolved_path=None,
            error_type="empty",
            message="Path cannot be empty",
        )

    # Check for whitespace-only
    if path.isspace():
        raise PathValidationError(
            input_path=path,
            resolved_path=None,
            error_type="whitespace",
            message="Path cannot be whitespace only",
        )

    # Check for null bytes
    if "\x00" in path:
        raise PathValidationError(
            input_path=path,
            resolved_path=None,
            error_type="null_byte",
            message="Path cannot contain null bytes",
        )

    # Check for absolute paths
    # Handle both Unix and Windows absolute paths
    path_obj = Path(path)

    # On Unix, Path("C:\\path").is_absolute() returns False
    # We need to also check Windows-style paths explicitly
    is_absolute = path_obj.is_absolute()

    # Also check for Windows drive letters on any platform
    # A path like "C:\path" or "C:/path" is absolute
    if not is_absolute and len(path) >= 2:
        # Check for drive letter pattern (e.g., "C:" or "D:")
        if path[1] == ":" and path[0].isalpha():
            is_absolute = True

    if is_absolute:
        raise PathValidationError(
            input_path=path,
            resolved_path=None,
            error_type="absolute",
            message=f"Absolute paths not allowed: {path!r}",
            suggestion="Use relative path from flow file directory",
        )


def check_for_duplicates(paths: list[str]) -> list[str]:
    """
    Check for duplicate paths in a list.

    Normalizes paths for comparison by:
    - Converting backslashes to forward slashes
    - Stripping trailing slashes

    Does NOT normalize path components (like ../), so paths that
    would resolve to the same file but have different string
    representations are NOT detected as duplicates.

    Args:
        paths: List of path strings to check.

    Returns:
        List of duplicate path strings (second occurrence and beyond).
        Returns the original path strings, not normalized versions.
    """
    seen: set[str] = set()
    duplicates: list[str] = []

    for path in paths:
        # Normalize for comparison only
        normalized = path.replace("\\", "/").rstrip("/")

        if normalized in seen:
            duplicates.append(path)
        else:
            seen.add(normalized)

    return duplicates


def normalize_path_separator(path: str) -> str:
    """
    Normalize path separators to forward slashes.

    Converts Windows-style backslashes to POSIX-style forward slashes
    for cross-platform storage and comparison. Paths are stored in
    POSIX format for portability.

    Args:
        path: Path string to normalize.

    Returns:
        Path string with all backslashes converted to forward slashes.
    """
    return path.replace("\\", "/")
