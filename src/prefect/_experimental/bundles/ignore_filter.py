"""
Ignore filtering utilities for bundles.

This module provides the IgnoreFilter class for filtering collected files
through cascading .prefectignore patterns. It supports gitignore-style
pattern syntax and cascades patterns from project root and flow directory.

Key features:
- Cascading .prefectignore loading (project root + flow directory)
- gitignore-compatible pattern matching via pathspec.GitIgnoreSpec
- Auto-exclusion of .prefectignore file itself
- Warnings for explicit includes that are excluded by ignore patterns
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pathspec

logger = logging.getLogger(__name__)

# Hardcoded patterns for sensitive files that should trigger warnings.
# These files are still collected (warning only, not blocked), but users
# are advised to add them to .prefectignore if they don't want them bundled.
SENSITIVE_PATTERNS = [
    ".env*",  # Environment files
    "*.pem",  # SSL certificates
    "*.key",  # Private keys
    "credentials.*",  # Credentials files
    "*_rsa",  # RSA keys
    "*.p12",  # PKCS12 certificates
    "secrets.*",  # Secrets files
]


@dataclass
class FilterResult:
    """
    Result of filtering files through .prefectignore patterns.

    Attributes:
        included_files: List of files that passed filtering.
        excluded_by_ignore: List of files excluded by .prefectignore patterns.
        explicitly_excluded: List of warning messages for user-explicit patterns
            that were excluded by .prefectignore.
    """

    included_files: list[Path] = field(default_factory=list)
    excluded_by_ignore: list[Path] = field(default_factory=list)
    explicitly_excluded: list[str] = field(default_factory=list)


def find_project_root(start_dir: Path) -> Path | None:
    """
    Find the nearest parent directory containing pyproject.toml.

    Walks up the directory tree from start_dir looking for a directory
    containing pyproject.toml, which indicates a Python project root.

    Args:
        start_dir: Directory to start searching from.

    Returns:
        Path to project root directory, or None if not found.
    """
    # Check start_dir and all parents
    for parent in [start_dir, *start_dir.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return None


def _read_ignore_file(path: Path) -> list[str]:
    """
    Read an ignore file, stripping comments and blank lines.

    Args:
        path: Path to the ignore file.

    Returns:
        List of pattern strings (no comments, no blanks).
    """
    lines = path.read_text().splitlines()
    return [line for line in lines if line.strip() and not line.startswith("#")]


def load_ignore_patterns(flow_dir: Path) -> list[str]:
    """
    Load patterns from cascading .prefectignore files.

    Load order (patterns combined via union):
    1. Project root .prefectignore (if found via pyproject.toml detection)
    2. Flow directory .prefectignore (if different from project root)

    Missing .prefectignore files emit debug log, not warning.

    Args:
        flow_dir: Flow file's directory (base for relative paths).

    Returns:
        Combined list of pattern strings from all .prefectignore files.
    """
    patterns: list[str] = []

    # 1. Find and load project root .prefectignore
    project_root = find_project_root(flow_dir)
    if project_root is not None:
        project_ignore = project_root / ".prefectignore"
        if project_ignore.exists():
            logger.debug(f"Loading .prefectignore from project root: {project_ignore}")
            patterns.extend(_read_ignore_file(project_ignore))
        else:
            logger.debug(f"No .prefectignore found at project root: {project_root}")
    else:
        logger.debug(f"No project root found for: {flow_dir}")

    # 2. Load flow directory .prefectignore (if different from project root)
    flow_ignore = flow_dir / ".prefectignore"
    if flow_ignore.exists():
        # Only load if different from project root's .prefectignore
        if project_root is None or flow_dir.resolve() != project_root.resolve():
            logger.debug(f"Loading .prefectignore from flow directory: {flow_ignore}")
            patterns.extend(_read_ignore_file(flow_ignore))
    else:
        logger.debug(f"No .prefectignore found in flow directory: {flow_dir}")

    return patterns


class IgnoreFilter:
    """
    Filters collected files through .prefectignore patterns.

    Loads patterns from cascading .prefectignore files (project root
    and flow directory) and provides filtering via gitignore-style
    pattern matching.

    Usage:
        filter = IgnoreFilter(Path("/project/flows"))
        result = filter.filter(collected_files)
        for file in result.included_files:
            print(file)

    The .prefectignore file itself is always auto-excluded from results.
    """

    def __init__(self, flow_dir: Path) -> None:
        """
        Initialize IgnoreFilter with flow directory.

        Args:
            flow_dir: Base directory for file collection (typically flow file's parent).
        """
        self.flow_dir = flow_dir.resolve()
        self._spec: pathspec.GitIgnoreSpec | None = None
        self._load_patterns()

    def _load_patterns(self) -> None:
        """Load patterns and compile into pathspec."""
        patterns = load_ignore_patterns(self.flow_dir)
        if patterns:
            self._spec = pathspec.GitIgnoreSpec.from_lines(patterns)

    def filter(
        self,
        files: list[Path],
        explicit_patterns: list[str] | None = None,
    ) -> FilterResult:
        """
        Filter files through .prefectignore patterns.

        Args:
            files: List of file paths to filter.
            explicit_patterns: Optional list of patterns that the user explicitly
                included. If a file matches both an explicit pattern AND is
                excluded by .prefectignore, a warning is added to explicitly_excluded.

        Returns:
            FilterResult with included_files, excluded_by_ignore, and
            explicitly_excluded warnings.
        """
        result = FilterResult()
        explicit_patterns = explicit_patterns or []

        for file in files:
            # Make path relative to flow_dir for pattern matching
            try:
                rel_path = str(file.relative_to(self.flow_dir))
            except ValueError:
                # File not under flow_dir - try with resolved paths
                try:
                    rel_path = str(file.resolve().relative_to(self.flow_dir))
                except ValueError:
                    # Can't make relative - just use name
                    rel_path = file.name

            # Auto-exclude .prefectignore files (hardcoded behavior)
            if rel_path.endswith(".prefectignore") or file.name == ".prefectignore":
                result.excluded_by_ignore.append(file)
                continue

            # Check against ignore spec
            excluded = False
            if self._spec is not None:
                if self._spec.match_file(rel_path):
                    excluded = True

            if excluded:
                result.excluded_by_ignore.append(file)

                # Check if this file was explicitly included by user
                for pattern in explicit_patterns:
                    # Check if the explicit pattern matches this file
                    if self._matches_explicit_pattern(rel_path, pattern):
                        result.explicitly_excluded.append(
                            f"File '{rel_path}' was explicitly included but is "
                            f"excluded by .prefectignore. Edit .prefectignore to include it."
                        )
                        break
            else:
                result.included_files.append(file)

        return result

    def _matches_explicit_pattern(self, rel_path: str, pattern: str) -> bool:
        """
        Check if a relative path matches an explicit pattern.

        Simple matching - checks if the pattern is the same as the
        relative path or if the path ends with the pattern.

        Args:
            rel_path: Relative file path (e.g., "data/input.csv")
            pattern: User-provided pattern (e.g., "input.csv" or "data/input.csv")

        Returns:
            True if the path matches the pattern.
        """
        # Exact match
        if rel_path == pattern:
            return True

        # Pattern is just the filename
        if rel_path.endswith(f"/{pattern}") or rel_path == pattern:
            return True

        # Pattern matches filename
        if Path(rel_path).name == pattern:
            return True

        return False


def check_sensitive_files(files: list[Path], base_dir: Path) -> list[str]:
    """
    Check if any files match sensitive patterns and return warnings.

    Sensitive files are still collected (warning only, not blocked), but
    users are advised to add them to .prefectignore if they don't want
    them bundled.

    Args:
        files: List of file paths to check.
        base_dir: Base directory for relative path calculation.

    Returns:
        List of warning strings for files matching sensitive patterns.
    """
    spec = pathspec.GitIgnoreSpec.from_lines(SENSITIVE_PATTERNS)
    warnings: list[str] = []

    for file in files:
        rel_path = str(file.relative_to(base_dir))
        if spec.match_file(rel_path):
            # Find which pattern matched
            for pattern in SENSITIVE_PATTERNS:
                single_spec = pathspec.GitIgnoreSpec.from_lines([pattern])
                if single_spec.match_file(rel_path):
                    warnings.append(
                        f"{rel_path} matches sensitive pattern {pattern}. "
                        "Consider adding to .prefectignore"
                    )
                    break

    return warnings


def emit_excluded_warning(
    excluded: list[Path], base_dir: Path, limit: int = 10
) -> None:
    """
    Emit a batched warning for files excluded by .prefectignore.

    The warning lists up to `limit` files, then shows "and N more" for
    any additional files.

    Args:
        excluded: List of excluded file paths.
        base_dir: Base directory for relative path calculation.
        limit: Maximum number of file names to show (default 10).
    """
    if not excluded:
        return

    count = len(excluded)
    names = [str(f.relative_to(base_dir)) for f in excluded[:limit]]

    if count <= limit:
        logger.warning(f"{count} files excluded by .prefectignore: {', '.join(names)}")
    else:
        logger.warning(
            f"{count} files excluded by .prefectignore: "
            f"{', '.join(names)}...and {count - limit} more"
        )


__all__ = [
    "FilterResult",
    "IgnoreFilter",
    "SENSITIVE_PATTERNS",
    "check_sensitive_files",
    "emit_excluded_warning",
    "find_project_root",
    "load_ignore_patterns",
]
