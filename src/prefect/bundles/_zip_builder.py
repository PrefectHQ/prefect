"""
Zip archive builder for file bundles.

This module provides the ZipBuilder class for packaging collected files into a
sidecar zip archive with content-addressed storage key derivation using SHA256
hashes.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Size of chunks for reading files when computing hash (64KB)
HASH_CHUNK_SIZE = 65536

# Warning threshold for zip file size (50MB)
ZIP_SIZE_WARNING_THRESHOLD = 50 * 1024 * 1024


@dataclass
class ZipResult:
    """
    Result of building a zip archive.

    Attributes:
        zip_path: Path to the temporary zip file.
        sha256_hash: Lowercase hex digest of the zip content.
        storage_key: Content-addressed storage key in format "files/{hash}.zip".
        size_bytes: Size of the zip file in bytes.
    """

    zip_path: Path
    sha256_hash: str
    storage_key: str
    size_bytes: int


class ZipBuilder:
    """
    Builds zip archives from collected files with content-addressed naming.

    Files are added to the zip with their relative paths preserved, using
    forward slashes regardless of platform. The resulting zip uses SHA256
    content hashing for deduplication across deployments.

    Usage:
        builder = ZipBuilder(Path("/project"))
        result = builder.build([
            Path("/project/data/input.csv"),
            Path("/project/config.yaml"),
        ])
        # Upload result.zip_path using result.storage_key
        builder.cleanup()

    The caller is responsible for calling cleanup() when done with the zip file.
    """

    def __init__(self, base_dir: Path) -> None:
        """
        Initialize ZipBuilder with a base directory.

        Args:
            base_dir: Base directory for computing relative paths.
                     All files must be within this directory.
        """
        self.base_dir = base_dir.resolve()
        self._temp_dir: str | None = None

    def build(self, files: list[Path]) -> ZipResult:
        """
        Build a zip archive from the given files.

        Files are sorted by relative path before adding to ensure deterministic
        hash computation regardless of input order.

        Args:
            files: List of absolute file paths to include in the zip.
                  All files must be within base_dir.

        Returns:
            ZipResult containing path to zip, hash, storage key, and size.
        """
        # Sort files by relative path for deterministic hash
        sorted_files = sorted(files, key=lambda f: str(f.relative_to(self.base_dir)))

        # Create temp directory for zip file
        self._temp_dir = tempfile.mkdtemp(prefix="prefect-zip-")
        zip_path = Path(self._temp_dir) / "files.zip"

        # Build the zip with DEFLATED compression
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted_files:
                # Compute relative path with forward slashes
                rel_path = file_path.relative_to(self.base_dir)
                arcname = str(rel_path).replace("\\", "/")
                zf.write(file_path, arcname)

        # Compute SHA256 hash using chunked reading
        sha256_hash = self._compute_hash(zip_path)

        # Get file size
        size_bytes = zip_path.stat().st_size

        # Emit warning if zip exceeds threshold
        if size_bytes >= ZIP_SIZE_WARNING_THRESHOLD:
            self._emit_size_warning(zip_path, sorted_files, size_bytes)

        # Build storage key
        storage_key = f"files/{sha256_hash}.zip"

        return ZipResult(
            zip_path=zip_path,
            sha256_hash=sha256_hash,
            storage_key=storage_key,
            size_bytes=size_bytes,
        )

    def _compute_hash(self, zip_path: Path) -> str:
        """
        Compute SHA256 hash of a file using chunked reading.

        Args:
            zip_path: Path to the file to hash.

        Returns:
            Lowercase hex digest of the SHA256 hash.
        """
        hasher = hashlib.sha256()
        with open(zip_path, "rb") as f:
            while True:
                chunk = f.read(HASH_CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    def _emit_size_warning(
        self, zip_path: Path, files: list[Path], size_bytes: int
    ) -> None:
        """
        Emit a warning about large zip file size.

        Args:
            zip_path: Path to the zip file.
            files: List of files included in the zip.
            size_bytes: Size of the zip file in bytes.
        """
        size_mb = size_bytes / (1024 * 1024)

        # Get file sizes and sort by size descending
        file_sizes = [(f, f.stat().st_size) for f in files]
        file_sizes.sort(key=lambda x: x[1], reverse=True)

        # Format largest files (up to 5)
        largest = file_sizes[:5]
        file_info = ", ".join(
            f"{f.name} ({s / (1024 * 1024):.1f} MB)" for f, s in largest
        )

        logger.warning(
            f"Zip file is large: {size_mb:.1f} MB exceeds "
            f"{ZIP_SIZE_WARNING_THRESHOLD / (1024 * 1024):.0f} MB threshold. "
            f"Largest files: {file_info}"
        )

    def cleanup(self) -> None:
        """
        Remove the temporary directory and zip file.

        Safe to call multiple times or before build().
        """
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None


__all__ = [
    "HASH_CHUNK_SIZE",
    "ZIP_SIZE_WARNING_THRESHOLD",
    "ZipBuilder",
    "ZipResult",
]
