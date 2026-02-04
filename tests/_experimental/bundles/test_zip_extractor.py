"""
Tests for ZipExtractor class.

ZipExtractor extracts files from a zip archive to the working directory,
preserving relative paths and handling overwrites with warnings.
"""

from __future__ import annotations

from pathlib import Path


class TestZipExtractorImports:
    """Tests for module imports."""

    def test_zip_extractor_importable(self) -> None:
        """ZipExtractor can be imported from module."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        assert ZipExtractor is not None


class TestZipExtractorInit:
    """Tests for ZipExtractor initialization."""

    def test_init_stores_zip_path(self, tmp_path: Path) -> None:
        """Constructor stores zip_path attribute."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = tmp_path / "test.zip"
        extractor = ZipExtractor(zip_path)
        assert extractor.zip_path == zip_path

    def test_init_accepts_path_object(self, tmp_path: Path) -> None:
        """Constructor accepts Path object."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = tmp_path / "test.zip"
        extractor = ZipExtractor(zip_path)
        assert isinstance(extractor.zip_path, Path)
        assert extractor.zip_path == zip_path

    def test_init_accepts_string_path(self, tmp_path: Path) -> None:
        """Constructor accepts string path and converts to Path."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = str(tmp_path / "test.zip")
        extractor = ZipExtractor(zip_path)
        assert isinstance(extractor.zip_path, Path)
        assert extractor.zip_path == Path(zip_path)

    def test_init_extracted_flag_false(self, tmp_path: Path) -> None:
        """_extracted flag is False initially."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = tmp_path / "test.zip"
        extractor = ZipExtractor(zip_path)
        assert extractor._extracted is False
