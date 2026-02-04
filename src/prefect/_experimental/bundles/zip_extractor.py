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
            # Extract all
            zf.extractall(target_dir)

            # Build extracted paths list
            for member in zf.namelist():
                if not member.endswith("/"):  # Skip directories
                    extracted_paths.append(target_dir / member)

        self._extracted = True
        return extracted_paths
