"""
File collection utilities for bundles.

This module provides the FileCollector class for collecting files matching
user-provided patterns from a base directory. Handles single files, with
glob and directory patterns to be added in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from prefect._experimental.bundles.path_resolver import (
    PathValidationError,
    normalize_path_separator,
    resolve_with_symlink_check,
    validate_path_input,
)


@dataclass
class CollectionResult:
    """
    Result of file collection operation.

    Attributes:
        files: List of collected file paths (resolved, absolute).
        warnings: List of warning messages (e.g., zero-match patterns).
        total_size: Sum of all collected file sizes in bytes.
        patterns_matched: Mapping of pattern -> list of files that matched.
    """

    files: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_size: int = 0
    patterns_matched: dict[str, list[Path]] = field(default_factory=dict)


class FileCollector:
    """
    Collects files matching user patterns from a base directory.

    Usage:
        collector = FileCollector(Path("/project/flows"))
        result = collector.collect(["config.yaml", "data/input.csv"])
        for file in result.files:
            print(file)

    Security:
        - All paths are validated against directory traversal attacks
        - Symlinks are followed but must resolve within base directory
        - Absolute paths are rejected
    """

    def __init__(self, base_dir: Path) -> None:
        """
        Initialize FileCollector with a base directory.

        Args:
            base_dir: Base directory for file collection. All patterns
                     are resolved relative to this directory.
        """
        self.base_dir = base_dir.resolve()

    def collect(self, patterns: list[str]) -> CollectionResult:
        """
        Collect files matching the given patterns.

        Currently supports single file patterns only. Glob and directory
        patterns will be added in later phases.

        Args:
            patterns: List of file patterns (e.g., ["config.yaml", "data/input.csv"])

        Returns:
            CollectionResult with collected files, warnings, and metadata.

        Raises:
            PathValidationError: If any pattern attempts directory traversal,
                               uses absolute paths, or contains invalid characters.
        """
        result = CollectionResult()

        for pattern in patterns:
            matched_files = self._collect_single_file(pattern)
            result.patterns_matched[pattern] = matched_files

            if matched_files:
                for file in matched_files:
                    result.files.append(file)
                    result.total_size += file.stat().st_size
            else:
                # Pattern matched no files - add warning
                result.warnings.append(f"Pattern '{pattern}' matched no files")

        return result

    def _collect_single_file(self, pattern: str) -> list[Path]:
        """
        Collect a single file by its path pattern.

        Args:
            pattern: File path pattern (e.g., "config.yaml", "data/input.csv")

        Returns:
            List containing the resolved file path if it exists, empty list otherwise.

        Raises:
            PathValidationError: If pattern fails validation (traversal, absolute, etc.)
        """
        # Validate input (raises on empty, whitespace, null bytes, absolute paths)
        validate_path_input(pattern)

        # Normalize path separators for cross-platform compatibility
        normalized = normalize_path_separator(pattern)

        # Construct target path
        target = self.base_dir / normalized

        # Check if path is a symlink and use symlink-aware resolution
        # Also check parent paths for symlinks
        has_symlink = target.is_symlink()
        if not has_symlink:
            # Check if any parent is a symlink
            for parent in target.parents:
                if parent == self.base_dir:
                    break
                if parent.is_symlink():
                    has_symlink = True
                    break

        if has_symlink:
            # Use symlink-aware resolution which validates traversal
            try:
                resolved = resolve_with_symlink_check(target, self.base_dir)
                return [resolved]
            except PathValidationError as e:
                if e.error_type in ("broken_symlink", "not_found"):
                    # Treat broken symlink as missing file
                    return []
                raise

        # Non-symlink path: manually validate traversal
        resolved = target.resolve(strict=False)

        # Security check: resolved path must be within base directory
        if not resolved.is_relative_to(self.base_dir):
            raise PathValidationError(
                input_path=pattern,
                resolved_path=str(resolved),
                error_type="traversal",
                message=f"Path traversal detected: {pattern!r} resolves outside base directory",
                suggestion="Use paths within the flow file's directory",
            )

        # Check if file exists
        if not resolved.exists():
            return []

        # File exists and is within bounds
        return [resolved]


__all__ = [
    "CollectionResult",
    "FileCollector",
]
