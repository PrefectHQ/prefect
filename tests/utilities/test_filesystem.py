from pathlib import Path

import pytest

from prefect.utilities.filesystem import filter_files


class TestFilterFiles:
    @pytest.fixture
    async def messy_dir(self, tmpdir):
        "Returns a full list of files to check against"
        # some top-level files
        tmpdir.ensure("README.md")
        tmpdir.ensure("config.json")
        tmpdir.ensure("setup.py")
        tmpdir.ensure(".env")
        tmpdir.ensure("__init__.py")

        # a venv directory
        tmpdir.mkdir("venv")
        tmpdir.ensure("venv/setup.py")
        tmpdir.ensure("venv/.env")
        tmpdir.ensure("venv/config.json")
        tmpdir.ensure("venv/.secret")
        tmpdir.mkdir("venv/__pycache__")
        tmpdir.ensure("venv/__pycache__/file.pyc")

        # a utilities directory
        tmpdir.mkdir("utilities")
        tmpdir.mkdir("utilities/__pycache__")
        tmpdir.ensure("utilities/__pycache__/hel28.pyc")
        tmpdir.ensure("utilities/README.md")
        tmpdir.ensure("utilities/__init__.py")
        tmpdir.ensure("utilities/helpers.py")

        path = Path(tmpdir)
        all_files = {
            str(p.relative_to(tmpdir)) for p in path.rglob("*") if not p.is_dir()
        }
        assert "README.md" in all_files  # ensure directory is populated
        return all_files

    async def test_default_includes_all_files(self, tmpdir, messy_dir):
        assert filter_files(root=tmpdir) == messy_dir

    async def test_simple_filetype_filter(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["*.py"])
        assert "README.md" in filtered
        assert "venv/config.json" in filtered
        assert "utilities/README.md" in filtered
        assert {f for f in filtered if f.endswith(".py")} == set()

    async def test_simple_filetype_filter_with_override(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["*.py", "!*__init__.py"])
        assert "README.md" in filtered
        assert "venv/config.json" in filtered
        assert "utilities/README.md" in filtered
        assert {f for f in filtered if f.endswith(".py")} == {
            "__init__.py",
            "utilities/__init__.py",
        }

    async def test_override_order_matters(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["!*__init__.py", "*.py"])
        assert "README.md" in filtered
        assert "venv/config.json" in filtered
        assert "utilities/README.md" in filtered
        assert {f for f in filtered if f.endswith(".py")} == set()

    async def test_partial_directory_filter(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["utilities/*.md"])
        assert "README.md" in filtered
        assert "utilities/__init__.py" in filtered
        assert "utilities/README.md" not in filtered

    async def test_full_directory_filter(self, tmpdir, messy_dir):
        tmpdir.ensure("utilities/venv")
        filtered = filter_files(tmpdir, ignore_patterns=["venv/**"])
        assert "utilities/venv" in filtered
        assert {f for f in filtered if f.startswith("venv")} == set()

    async def test_alternate_directory_filter(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["__pycache__/"])
        assert "__init__.py" in filtered
        assert {f for f in filtered if "pycache" in f} == set()
