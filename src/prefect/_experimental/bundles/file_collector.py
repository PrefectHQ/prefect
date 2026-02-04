"""
File collection utilities for bundles.

This module provides the FileCollector class for collecting files matching
user-provided patterns from a base directory. Handles single files, directory
patterns, and glob patterns with gitignore-style matching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

import pathspec
import pathspec.util

from prefect._experimental.bundles.path_resolver import (
    PathValidationError,
    normalize_path_separator,
    resolve_with_symlink_check,
    validate_path_input,
)

# Default exclusion patterns - common generated/cached directories and files
# that users typically don't want bundled. Uses gitignore-style patterns.
DEFAULT_EXCLUSIONS = [
    # Python
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.egg-info/",
    # Version control
    ".git/",
    ".hg/",
    ".svn/",
    # Package managers
    "node_modules/",
    ".venv/",
    "venv/",
    # IDEs
    ".idea/",
    ".vscode/",
    # OS files
    ".DS_Store",
    "Thumbs.db",
]


class PatternType(Enum):
    """Type of file pattern."""

    SINGLE_FILE = auto()
    DIRECTORY = auto()
    GLOB = auto()
    NEGATION = auto()


# Characters that indicate a glob pattern
GLOB_WILDCARDS = {"*", "?", "["}


def _is_glob_pattern(pattern: str) -> bool:
    """
    Check if a pattern contains glob wildcards.

    Patterns starting with '!' are negation patterns (handled separately),
    not glob patterns.

    Args:
        pattern: The pattern string to check.

    Returns:
        True if pattern contains glob wildcards, False otherwise.
    """
    # Negation patterns are not globs
    if pattern.startswith("!"):
        return False

    # Check for any glob wildcard character
    return any(char in pattern for char in GLOB_WILDCARDS)


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
        result = collector.collect(["config.yaml", "data/", "data/input.csv"])
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
        self._collected_files: set[Path] = set()  # Track for deduplication

    def collect(self, patterns: list[str]) -> CollectionResult:
        """
        Collect files matching the given patterns.

        Supports single file patterns, directory patterns, glob patterns, and
        negation patterns. Patterns are processed in order (gitignore-style):
        - Inclusion patterns add files to the collection
        - Negation patterns (starting with !) remove files from the current collection

        Pattern order matters: negation at position N only removes files that were
        already collected by patterns 1 to N-1. For example:
        - ["*.json", "!fixtures/*.json"] = all JSON except fixtures
        - ["!fixtures/*.json", "*.json"] = all JSON (negation had nothing to negate)

        Directory patterns collect all files recursively, excluding hidden files
        and common generated directories (see DEFAULT_EXCLUSIONS).

        Args:
            patterns: List of file patterns (e.g., ["config.yaml", "data/", "!*.test.py"])

        Returns:
            CollectionResult with collected files, warnings, and metadata.

        Raises:
            PathValidationError: If any pattern attempts directory traversal,
                               uses absolute paths, or contains invalid characters.
        """
        result = CollectionResult()
        self._collected_files = set()  # Reset deduplication tracking

        # Process patterns in order - order matters for negation
        for pattern in patterns:
            pattern_type = self._classify_pattern(pattern)

            if pattern_type == PatternType.NEGATION:
                # Negation: remove files from current collection
                excluded_files = self._process_negation(pattern)
                result.patterns_matched[pattern] = excluded_files

                # Remove excluded files from collection
                for file in excluded_files:
                    self._collected_files.discard(file)
                # No warning for negation patterns that exclude nothing
            else:
                # Inclusion pattern
                if pattern_type == PatternType.GLOB:
                    matched_files = self._collect_glob(pattern)
                elif pattern_type == PatternType.DIRECTORY:
                    matched_files = self._collect_directory(pattern)
                else:
                    matched_files = self._collect_single_file(pattern)

                result.patterns_matched[pattern] = matched_files

                if matched_files:
                    for file in matched_files:
                        # Deduplicate: only add if not already collected
                        if file not in self._collected_files:
                            self._collected_files.add(file)
                else:
                    # Pattern matched no files - add warning
                    result.warnings.append(f"Pattern '{pattern}' matched no files")

        # Build final file list with sizes
        for file in self._collected_files:
            result.files.append(file)
            result.total_size += file.stat().st_size

        return result

    def _process_negation(self, pattern: str) -> list[Path]:
        """
        Process a negation pattern and return files to exclude.

        Args:
            pattern: Negation pattern starting with '!' (e.g., "!*.test.py")

        Returns:
            List of files that match the negation pattern and should be excluded.
        """
        # Extract the inner pattern (without the leading !)
        inner_pattern = pattern[1:]

        # Compile the pattern using gitignore-style matching
        spec = pathspec.PathSpec.from_lines("gitwildmatch", [inner_pattern])

        # Find files in current collection that match the negation
        excluded: list[Path] = []
        for file in self._collected_files:
            rel_path = str(file.relative_to(self.base_dir))
            if spec.match_file(rel_path):
                excluded.append(file)

        return excluded

    def _classify_pattern(self, pattern: str) -> PatternType:
        """
        Classify a pattern to determine how to process it.

        Classification order:
        1. Negation patterns (starts with !)
        2. Glob patterns (contains *, ?, [ but not starting with !)
        3. Directory patterns (existing directory)
        4. Single file patterns (default)

        Args:
            pattern: The pattern string to classify.

        Returns:
            PatternType indicating how to process the pattern.
        """
        # Check for negation first
        if pattern.startswith("!"):
            return PatternType.NEGATION

        # Check for glob wildcards first (before checking filesystem)
        if _is_glob_pattern(pattern):
            return PatternType.GLOB

        # Normalize and check if it's a directory
        normalized = normalize_path_separator(pattern.rstrip("/"))
        target = self.base_dir / normalized

        if target.is_dir():
            return PatternType.DIRECTORY

        return PatternType.SINGLE_FILE

    def _collect_directory(self, pattern: str) -> list[Path]:
        """
        Collect all files from a directory recursively.

        Excludes hidden files (dotfiles), hidden directories, and files matching
        DEFAULT_EXCLUSIONS patterns.

        Args:
            pattern: Directory path pattern (e.g., "data/", "data")

        Returns:
            List of collected file paths within the directory.

        Raises:
            PathValidationError: If pattern fails validation.
        """
        # Validate input first
        normalized = normalize_path_separator(pattern.rstrip("/"))
        validate_path_input(normalized)

        dir_path = self.base_dir / normalized

        # Check if directory exists
        if not dir_path.is_dir():
            return []

        # Use pathspec.util.iter_tree_files for recursive file iteration
        collected: list[Path] = []
        try:
            for rel_path in pathspec.util.iter_tree_files(str(dir_path)):
                # rel_path is relative to dir_path
                file_path = dir_path / rel_path

                # Skip hidden files/directories (any path component starts with '.')
                path_parts = Path(rel_path).parts
                if any(part.startswith(".") for part in path_parts):
                    continue

                # Check against DEFAULT_EXCLUSIONS
                if self._matches_exclusion(rel_path):
                    continue

                # Validate the file (security check for symlinks)
                resolved = self._validate_file_path(file_path)
                if resolved is not None:
                    collected.append(resolved)
        except OSError:
            # Directory iteration failed - treat as empty
            return []

        return collected

    def _collect_glob(self, pattern: str) -> list[Path]:
        """
        Collect files matching a glob pattern.

        Uses pathspec library with gitwildmatch syntax for gitignore-compatible
        pattern matching. Excludes hidden files and DEFAULT_EXCLUSIONS.

        Args:
            pattern: Glob pattern (e.g., "*.json", "**/*.csv", "data/*.txt")

        Returns:
            List of collected file paths matching the pattern.
        """
        # Compile the pattern using gitignore-style matching
        spec = pathspec.PathSpec.from_lines("gitwildmatch", [pattern])

        collected: list[Path] = []
        try:
            # Iterate all files in base directory
            for rel_path in pathspec.util.iter_tree_files(str(self.base_dir)):
                # Skip hidden files/directories
                path_parts = Path(rel_path).parts
                if any(part.startswith(".") for part in path_parts):
                    continue

                # Check against DEFAULT_EXCLUSIONS
                if self._matches_exclusion(rel_path):
                    continue

                # Check if file matches the glob pattern
                if spec.match_file(rel_path):
                    file_path = self.base_dir / rel_path

                    # Validate the file (security check for symlinks)
                    resolved = self._validate_file_path(file_path)
                    if resolved is not None:
                        collected.append(resolved)
        except OSError:
            # Iteration failed - treat as no matches
            return []

        return collected

    def _matches_exclusion(self, rel_path: str) -> bool:
        """
        Check if a relative path matches any DEFAULT_EXCLUSIONS pattern.

        Args:
            rel_path: Path relative to the collected directory.

        Returns:
            True if the path should be excluded, False otherwise.
        """
        path_parts = Path(rel_path).parts
        filename = Path(rel_path).name

        for exclusion in DEFAULT_EXCLUSIONS:
            # Directory exclusion with glob (e.g., "*.egg-info/")
            if exclusion.endswith("/") and exclusion.startswith("*"):
                suffix = exclusion[1:-1]  # e.g., ".egg-info"
                for part in path_parts:
                    if part.endswith(suffix):
                        return True
            # Directory exclusion (e.g., "__pycache__/")
            elif exclusion.endswith("/"):
                dir_name = exclusion.rstrip("/")
                if dir_name in path_parts:
                    return True
            # Glob pattern for files (e.g., "*.pyc")
            elif exclusion.startswith("*"):
                suffix = exclusion[1:]  # e.g., ".pyc"
                if filename.endswith(suffix):
                    return True
            # Exact file match (e.g., ".DS_Store")
            elif filename == exclusion:
                return True

        return False

    def _validate_file_path(self, file_path: Path) -> Path | None:
        """
        Validate a file path, checking for symlinks and containment.

        Args:
            file_path: Absolute file path to validate.

        Returns:
            Resolved file path if valid, None if file doesn't exist or is broken symlink.

        Raises:
            PathValidationError: If path escapes base directory.
        """
        # Check for symlinks
        has_symlink = file_path.is_symlink()
        if not has_symlink:
            for parent in file_path.parents:
                if parent == self.base_dir:
                    break
                if parent.is_symlink():
                    has_symlink = True
                    break

        if has_symlink:
            try:
                return resolve_with_symlink_check(file_path, self.base_dir)
            except PathValidationError as e:
                if e.error_type in ("broken_symlink", "not_found"):
                    return None
                raise

        # Non-symlink: just resolve and verify containment
        resolved = file_path.resolve(strict=False)

        if not resolved.is_relative_to(self.base_dir):
            raise PathValidationError(
                input_path=str(file_path),
                resolved_path=str(resolved),
                error_type="traversal",
                message=f"Path escapes base directory: {file_path}",
                suggestion="Use paths within the flow file's directory",
            )

        if not resolved.exists():
            return None

        return resolved

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
    "DEFAULT_EXCLUSIONS",
    "FileCollector",
    "PatternType",
]
