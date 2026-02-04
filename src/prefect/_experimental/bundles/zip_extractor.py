"""
Zip archive extractor for file bundles.

This module provides the ZipExtractor class for extracting files from a
sidecar zip archive to the working directory before flow execution.
"""

from __future__ import annotations

import logging
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
