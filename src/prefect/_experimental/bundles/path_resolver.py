"""
Path resolution and validation utilities for bundles.

This module provides functions for validating user-provided paths
before resolution and collection. Includes input validation (no filesystem
access) and symlink resolution with security checks.
"""

from __future__ import annotations

import errno
from dataclasses import dataclass, field
from pathlib import Path

# Maximum depth for symlink chain traversal.
# Provides defense-in-depth alongside OS-level ELOOP protection.
MAX_SYMLINK_DEPTH = 10


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


def resolve_secure_path(user_path: str, base_dir: Path) -> Path:
    """
    Resolve a user-provided path securely relative to base directory.

    Validates the input path, normalizes path separators, resolves the path,
    and verifies that the resolved path is within the base directory.
    This prevents directory traversal attacks (e.g., ../../../etc/passwd).

    Args:
        user_path: User-provided path string (must be relative)
        base_dir: Base directory (e.g., flow file's parent directory)

    Returns:
        Resolved, validated Path

    Raises:
        PathValidationError: If path fails validation. Error types:
            - empty: Empty path string
            - whitespace: Whitespace-only path
            - null_byte: Path contains null bytes
            - absolute: Absolute path provided
            - not_found: Path does not exist
            - traversal: Path resolves outside base directory
            - os_error: OS-level error accessing path
    """
    # 1. Run input validation first (rejects empty, whitespace, null bytes, absolute)
    validate_path_input(user_path)

    # 2. Normalize separators for cross-platform (\ -> /)
    normalized = normalize_path_separator(user_path)

    # 3. Construct target path relative to base directory
    target = base_dir / normalized

    # 4. Resolve the base directory (must be resolved for comparison)
    resolved_base = base_dir.resolve()

    # 5. Resolve target path WITHOUT existence check first (to detect traversal)
    # This normalizes .. and . components without requiring the path to exist
    resolved = target.resolve(strict=False)

    # 6. Security check BEFORE existence check: resolved path must be within base directory
    # This ensures traversal attempts are caught even if the target doesn't exist
    if not resolved.is_relative_to(resolved_base):
        raise PathValidationError(
            input_path=user_path,
            resolved_path=str(resolved),
            error_type="traversal",
            message=f"Path traversal detected: {user_path!r} resolves outside base directory",
            suggestion="Use paths within the flow file's directory",
        )

    # 7. Now check existence
    if not resolved.exists():
        raise PathValidationError(
            input_path=user_path,
            resolved_path=str(resolved),
            error_type="not_found",
            message=f"Path does not exist: {user_path!r}",
            suggestion="Check that the file or directory exists",
        )

    return resolved


def resolve_with_symlink_check(
    path: Path,
    base_dir: Path,
    max_depth: int = MAX_SYMLINK_DEPTH,
) -> Path:
    """
    Resolve path with explicit symlink chain depth limit.

    This provides defense-in-depth alongside OS-level ELOOP protection.
    Symlinks are followed, but the final resolved path must be within base_dir.

    Args:
        path: Path to resolve (may contain symlinks)
        base_dir: Base directory for containment check
        max_depth: Maximum symlink chain depth (default: 10)

    Returns:
        Resolved path (symlinks followed)

    Raises:
        PathValidationError: If symlink chain too deep, broken, or escapes base dir
    """
    resolved_base = base_dir.resolve()
    current = path
    depth = 0
    seen_paths: set[Path] = set()

    # Manual symlink chain traversal for depth limiting
    while current.is_symlink():
        # Circular reference check
        if current in seen_paths:
            raise PathValidationError(
                input_path=str(path),
                resolved_path=str(current),
                error_type="symlink_loop",
                message="Circular symlink detected",
                suggestion="Check for circular symlinks in your project",
            )
        seen_paths.add(current)

        # Depth check
        if depth >= max_depth:
            raise PathValidationError(
                input_path=str(path),
                resolved_path=str(current),
                error_type="symlink_loop",
                message=f"Symlink chain exceeded {max_depth} levels",
                suggestion="Check for circular symlinks in your project",
            )

        # Read symlink target
        try:
            target = current.readlink()
        except OSError as e:
            raise PathValidationError(
                input_path=str(path),
                resolved_path=str(current),
                error_type="broken_symlink",
                message=f"Cannot read symlink: {e}",
                suggestion="Check that the symlink target exists",
            )

        # Resolve relative symlinks relative to symlink's parent
        if not target.is_absolute():
            target = current.parent / target

        current = target
        depth += 1

    # Final resolution with existence check
    try:
        resolved = current.resolve(strict=True)
    except FileNotFoundError:
        raise PathValidationError(
            input_path=str(path),
            resolved_path=str(current),
            error_type="broken_symlink",
            message="Symlink target does not exist",
            suggestion="Check that the symlink points to an existing file",
        )
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise PathValidationError(
                input_path=str(path),
                resolved_path=None,
                error_type="symlink_loop",
                message="Circular symlink detected by OS",
                suggestion="Check for circular symlinks in your project",
            )
        raise

    # Containment check on final resolved path
    if not resolved.is_relative_to(resolved_base):
        raise PathValidationError(
            input_path=str(path),
            resolved_path=str(resolved),
            error_type="traversal",
            message="Symlink resolves outside base directory",
            suggestion="Symlinks must point to files within the flow file's directory",
        )

    return resolved


class PathResolver:
    """
    Path resolver with caching for efficient repeated resolution.

    Usage:
        resolver = PathResolver(base_dir=Path("/project/flows"))
        result = resolver.resolve_all(["config.yaml", "data/input.csv"])
        if result.has_errors:
            # Handle errors
        else:
            # Use result.valid_paths
    """

    def __init__(self, base_dir: Path):
        """
        Initialize resolver with base directory.

        Args:
            base_dir: Base directory for path resolution (typically flow file's parent)
        """
        self.base_dir = base_dir.resolve()
        self._cache: dict[str, Path] = {}
        self._error_cache: dict[str, PathValidationError] = {}

    def resolve(self, user_path: str) -> Path:
        """
        Resolve a single path with caching.

        Args:
            user_path: User-provided relative path

        Returns:
            Resolved Path

        Raises:
            PathValidationError: If validation fails
        """
        # Check error cache first
        if user_path in self._error_cache:
            raise self._error_cache[user_path]

        # Check success cache
        if user_path in self._cache:
            return self._cache[user_path]

        # Perform resolution
        try:
            resolved = self._do_resolve(user_path)
            self._cache[user_path] = resolved
            return resolved
        except PathValidationError as e:
            self._error_cache[user_path] = e
            raise

    def _do_resolve(self, user_path: str) -> Path:
        """Internal resolution logic."""
        # 1. Input validation
        validate_path_input(user_path)

        # 2. Normalize separators
        normalized = normalize_path_separator(user_path)

        # 3. Construct and resolve path
        target = self.base_dir / normalized

        # 4. Check if path involves symlinks and use appropriate resolver
        if target.is_symlink() or any(
            p.is_symlink() for p in target.parents if p != self.base_dir
        ):
            return resolve_with_symlink_check(target, self.base_dir)
        else:
            return resolve_secure_path(user_path, self.base_dir)

    def resolve_all(self, paths: list[str]) -> PathValidationResult:
        """
        Resolve multiple paths, collecting all errors.

        Per user requirements: Collect all errors before failing.
        Does NOT stop on first error.

        Args:
            paths: List of user-provided paths

        Returns:
            PathValidationResult with valid_paths and errors
        """
        result = PathValidationResult()

        # Check for duplicates first
        duplicates = check_for_duplicates(paths)
        for dup in duplicates:
            result.errors.append(
                PathValidationError(
                    input_path=dup,
                    resolved_path=None,
                    error_type="duplicate",
                    message=f"Duplicate path in input: {dup!r}",
                    suggestion="Remove duplicate paths from include_files",
                )
            )

        # Resolve each unique path
        seen: set[str] = set()
        for path in paths:
            normalized = normalize_path_separator(path)
            if normalized in seen:
                continue  # Skip duplicates (already reported)
            seen.add(normalized)

            try:
                resolved = self.resolve(path)
                result.valid_paths.append(resolved)
            except PathValidationError as e:
                result.errors.append(e)

        return result

    def clear_cache(self) -> None:
        """Clear resolution caches."""
        self._cache.clear()
        self._error_cache.clear()


def resolve_paths(
    paths: list[str],
    base_dir: Path,
    raise_on_errors: bool = True,
) -> PathValidationResult:
    """
    Resolve multiple paths relative to a base directory.

    This is the main entry point for path resolution. It:
    1. Validates all paths for security issues
    2. Checks for duplicates
    3. Resolves paths relative to base_dir
    4. Collects ALL errors before optionally raising

    Args:
        paths: List of user-provided paths (files, directories, patterns for Phase 2)
        base_dir: Base directory for resolution (flow file's parent directory)
        raise_on_errors: If True, raise PathResolutionError when any validation fails.
                        If False, return result with errors for inspection.

    Returns:
        PathValidationResult containing valid_paths and errors

    Raises:
        PathResolutionError: If raise_on_errors=True and any validation fails

    Example:
        # With raising (default)
        result = resolve_paths(["config.yaml", "data/"], flow_dir)

        # Without raising (for inspection)
        result = resolve_paths(["config.yaml", "missing.txt"], flow_dir, raise_on_errors=False)
        if result.has_errors:
            for error in result.errors:
                print(f"Warning: {error.message}")
    """
    resolver = PathResolver(base_dir)
    result = resolver.resolve_all(paths)

    if raise_on_errors and result.has_errors:
        result.raise_if_errors()

    return result


__all__ = [
    "PathValidationError",
    "PathValidationResult",
    "PathResolutionError",
    "PathResolver",
    "resolve_paths",
    "resolve_secure_path",
    "resolve_with_symlink_check",
    "validate_path_input",
    "check_for_duplicates",
    "normalize_path_separator",
    "MAX_SYMLINK_DEPTH",
]
