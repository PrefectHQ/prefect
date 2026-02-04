"""
End-to-end integration tests for include_files feature.

These tests verify the complete flow from @ecs(include_files=[...]) decorator
through bundle creation, upload, download, extraction, and flow execution.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest


class TestIncludeFilesIntegration:
    """End-to-end tests for include_files feature."""

    @pytest.fixture
    def project_dir(self, tmp_path: Path) -> Path:
        """Create a project directory with sample files."""
        # Create config file
        (tmp_path / "config.yaml").write_text("database: localhost\nport: 5432")

        # Create data directory with files
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "input.csv").write_text("id,name\n1,Alice\n2,Bob")
        (data_dir / "lookup.json").write_text('{"key": "value"}')

        # Create nested structure
        templates_dir = tmp_path / "templates" / "emails"
        templates_dir.mkdir(parents=True)
        (templates_dir / "welcome.html").write_text("<h1>Welcome!</h1>")

        return tmp_path

    @pytest.fixture
    def mock_flow_file(self, project_dir: Path) -> Path:
        """Create a mock flow file in the project directory."""
        flow_file = project_dir / "flows" / "my_flow.py"
        flow_file.parent.mkdir(exist_ok=True)
        flow_file.write_text("# Flow definition here")
        return flow_file

    def test_file_collector_and_zip_builder_integration(
        self, project_dir: Path
    ) -> None:
        """FileCollector output feeds correctly into ZipBuilder."""
        from prefect._experimental.bundles.file_collector import FileCollector
        from prefect._experimental.bundles.zip_builder import ZipBuilder

        # Collect files
        collector = FileCollector(project_dir)
        result = collector.collect(["config.yaml", "data/"])

        # Build zip
        builder = ZipBuilder(project_dir)
        zip_result = builder.build(result.files)

        try:
            # Verify zip contains expected files
            with zipfile.ZipFile(zip_result.zip_path) as zf:
                names = set(zf.namelist())
                assert "config.yaml" in names
                assert "data/input.csv" in names
                assert "data/lookup.json" in names

                # Verify content
                assert (
                    zf.read("config.yaml").decode() == "database: localhost\nport: 5432"
                )
                assert "Alice" in zf.read("data/input.csv").decode()
        finally:
            builder.cleanup()

    def test_zip_builder_extractor_roundtrip(
        self, project_dir: Path, tmp_path: Path
    ) -> None:
        """Files packaged by ZipBuilder extract correctly via ZipExtractor."""
        from prefect._experimental.bundles.file_collector import FileCollector
        from prefect._experimental.bundles.zip_builder import ZipBuilder
        from prefect._experimental.bundles.zip_extractor import ZipExtractor

        # Collect and build
        collector = FileCollector(project_dir)
        result = collector.collect(["config.yaml", "data/", "templates/"])

        builder = ZipBuilder(project_dir)
        zip_result = builder.build(result.files)

        # Extract to different directory (simulating remote execution)
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        extractor = ZipExtractor(zip_result.zip_path)
        extracted = extractor.extract(work_dir)

        try:
            # Verify extracted files
            assert (work_dir / "config.yaml").exists()
            assert (work_dir / "data" / "input.csv").exists()
            assert (work_dir / "data" / "lookup.json").exists()
            assert (work_dir / "templates" / "emails" / "welcome.html").exists()

            # Verify content matches
            assert (
                work_dir / "config.yaml"
            ).read_text() == "database: localhost\nport: 5432"
            assert "Alice" in (work_dir / "data" / "input.csv").read_text()
            assert (
                work_dir / "templates" / "emails" / "welcome.html"
            ).read_text() == "<h1>Welcome!</h1>"

            # Verify returned paths
            assert len(extracted) == 4
            assert all(p.exists() for p in extracted)
        finally:
            builder.cleanup()
