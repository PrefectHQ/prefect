"""
Zip archive extractor for file bundles.

This module provides the ZipExtractor class for extracting files from a
sidecar zip archive to the working directory before flow execution.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


class ZipExtractor:
    """
    Extracts files from a zip archive to the working directory.

    Handles:
    - Relative path preservation
    - File overwrite with warning
    - File/directory type mismatch errors
    - Parent directory creation

    Usage:
        extractor = ZipExtractor(Path("/path/to/files.zip"))
        extractor.extract()  # Extracts to cwd
        extractor.cleanup()  # Deletes the zip file
    """

    def __init__(self, zip_path: Path | str) -> None:
        """
        Initialize extractor with path to zip file.

        Args:
            zip_path: Path to the zip file to extract.
        """
        self.zip_path = Path(zip_path)
        self._extracted = False

    def _check_type_mismatch(self, member: str, target_dir: Path) -> None:
        """Check if extraction would cause file/dir type mismatch."""
        dest_path = target_dir / member
        if not dest_path.exists():
            return

        is_member_dir = member.endswith("/")
        is_dest_dir = dest_path.is_dir()

        if is_dest_dir and not is_member_dir:
            raise RuntimeError(
                f"Cannot extract file '{member}': destination exists as directory"
            )
        if not is_dest_dir and is_member_dir:
            raise RuntimeError(
                f"Cannot extract directory '{member}': destination exists as file"
            )

    def extract(self, target_dir: Path | None = None) -> list[Path]:
        """
        Extract all files to target directory.

        Args:
            target_dir: Directory to extract to (defaults to cwd).

        Returns:
            List of extracted file paths.

        Raises:
            RuntimeError: If file/directory type mismatch.
            zipfile.BadZipFile: If zip is corrupted.
            FileNotFoundError: If zip_path doesn't exist.
        """
        target_dir = target_dir or Path.cwd()
        extracted_paths: list[Path] = []

        with zipfile.ZipFile(self.zip_path, "r") as zf:
            # Pre-check for type mismatches
            for member in zf.namelist():
                self._check_type_mismatch(member, target_dir)

            # Log overwrites before extraction
            for member in zf.namelist():
                dest_path = target_dir / member
                if dest_path.exists() and dest_path.is_file():
                    logger.warning(f"Overwriting existing file: {member}")

            # Extract all
            zf.extractall(target_dir)

            # Build extracted paths list
            for member in zf.namelist():
                if not member.endswith("/"):  # Skip directories
                    extracted_paths.append(target_dir / member)

        self._extracted = True
        return extracted_paths

    def cleanup(self) -> None:
        """
        Delete the zip file after successful extraction.

        Only deletes if extraction was successful.
        Logs warning if deletion fails.
        """
        if not self._extracted:
            logger.warning(
                f"Skipping zip cleanup - extraction not completed: {self.zip_path}"
            )
            return

        try:
            self.zip_path.unlink(missing_ok=True)
            logger.debug(f"Deleted zip file: {self.zip_path}")
        except OSError as e:
            logger.warning(f"Failed to delete zip file {self.zip_path}: {e}")
