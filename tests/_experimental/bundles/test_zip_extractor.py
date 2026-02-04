"""
Tests for ZipExtractor class.

ZipExtractor extracts files from a zip archive to the working directory,
preserving relative paths and handling overwrites with warnings.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest


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


class TestZipExtractorExtract:
    """Tests for ZipExtractor.extract() method."""

    @pytest.fixture
    def create_test_zip(self, tmp_path: Path):
        """Factory fixture to create test zip files."""

        def _create(files: dict[str, str]) -> Path:
            """Create a zip with the given files. Keys are paths, values are content."""
            zip_path = tmp_path / "test.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                for path, content in files.items():
                    zf.writestr(path, content)
            return zip_path

        return _create

    def test_extract_single_file(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Single file is extracted to target directory."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"config.yaml": "key: value"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(target_dir)

        assert (target_dir / "config.yaml").exists()
        assert (target_dir / "config.yaml").read_text() == "key: value"

    def test_extract_preserves_relative_paths(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Nested directory structure is preserved (data/input.csv -> ./data/input.csv)."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"data/input.csv": "a,b,c"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(target_dir)

        assert (target_dir / "data" / "input.csv").exists()
        assert (target_dir / "data" / "input.csv").read_text() == "a,b,c"

    def test_extract_creates_parent_directories(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Creates parent directories as needed."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"deeply/nested/file.txt": "content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(target_dir)

        assert (target_dir / "deeply" / "nested" / "file.txt").exists()

    def test_extract_to_cwd_by_default(
        self, tmp_path: Path, create_test_zip: callable, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Uses cwd when no target specified."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"default.txt": "default content"})
        work_dir = tmp_path / "workdir"
        work_dir.mkdir()
        monkeypatch.chdir(work_dir)

        extractor = ZipExtractor(zip_path)
        extractor.extract()

        assert (work_dir / "default.txt").exists()
        assert (work_dir / "default.txt").read_text() == "default content"

    def test_extract_to_custom_target_dir(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Accepts custom target directory."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"custom.txt": "custom content"})
        custom_dir = tmp_path / "custom_output"
        custom_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        extractor.extract(custom_dir)

        assert (custom_dir / "custom.txt").exists()

    def test_extract_returns_list_of_paths(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Returns list of extracted file paths."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip(
            {"file1.txt": "content1", "dir/file2.txt": "content2"}
        )
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        result = extractor.extract(target_dir)

        assert isinstance(result, list)
        assert len(result) == 2
        assert target_dir / "file1.txt" in result
        assert target_dir / "dir" / "file2.txt" in result

    def test_extract_sets_extracted_flag(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Sets _extracted to True after successful extraction."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip({"file.txt": "content"})
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        assert extractor._extracted is False
        extractor.extract(target_dir)
        assert extractor._extracted is True

    def test_extract_multiple_files(
        self, tmp_path: Path, create_test_zip: callable
    ) -> None:
        """Multiple files are extracted correctly."""
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        zip_path = create_test_zip(
            {
                "root.txt": "root content",
                "dir1/file1.txt": "file1 content",
                "dir1/file2.txt": "file2 content",
                "dir2/nested/deep.txt": "deep content",
            }
        )
        target_dir = tmp_path / "output"
        target_dir.mkdir()

        extractor = ZipExtractor(zip_path)
        result = extractor.extract(target_dir)

        assert len(result) == 4
        assert (target_dir / "root.txt").read_text() == "root content"
        assert (target_dir / "dir1" / "file1.txt").read_text() == "file1 content"
        assert (target_dir / "dir1" / "file2.txt").read_text() == "file2 content"
        assert (
            target_dir / "dir2" / "nested" / "deep.txt"
        ).read_text() == "deep content"
