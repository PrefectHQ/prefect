import sys
from pathlib import Path, PosixPath, WindowsPath

import pytest

from prefect.utilities.filesystem import filter_files, relative_path_to_current_platform


def _path_set(*args: str):
    """
    Takes one or more paths and converts them to a set of paths in the
    current platform's format.
    """
    return {str(Path(p)) for p in args}


class TestFilterFiles:
    @pytest.fixture
    async def messy_dir(self, tmpdir):
        "Returns a full list of files and directories in a temp directory."
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
        all_files = {str(p.relative_to(tmpdir)) for p in path.rglob("*")}
        assert "README.md" in all_files  # ensure directory is populated
        return all_files

    async def test_default_includes_all_files_and_dirs(self, tmpdir, messy_dir):
        assert filter_files(root=tmpdir) == messy_dir

    async def test_filter_out_dirs(self, tmpdir, messy_dir):
        assert filter_files(root=tmpdir, include_dirs=False) == {
            p for p in messy_dir if not Path(tmpdir / p).is_dir()
        }

    async def test_simple_filetype_filter(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["*.py"])

        should_be_included = _path_set(
            "README.md", "venv", "venv/config.json", "utilities/README.md"
        )

        assert should_be_included.issubset(filtered)
        assert {f for f in filtered if f.endswith(".py")} == set()

    async def test_simple_filetype_filter_with_ignore_dirs(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["*.py"], include_dirs=False)

        should_be_included = _path_set(
            "README.md", "venv/config.json", "utilities/README.md"
        )

        should_be_excluded = _path_set(
            "venv", "utilities", "venv/__pycache__", "utilities/__pycache__"
        )

        assert should_be_included.issubset(filtered)
        assert should_be_excluded.isdisjoint(filtered)
        assert {f for f in filtered if f.endswith(".py")} == set()

    async def test_simple_filetype_filter_with_override(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["*.py", "!*__init__.py"])

        should_be_included = _path_set(
            "README.md", "venv", "venv/config.json", "utilities/README.md"
        )

        assert should_be_included.issubset(filtered)
        assert {f for f in filtered if f.endswith(".py")} == _path_set(
            "__init__.py",
            "utilities/__init__.py",
        )

    async def test_comments_and_empty_lines_are_ignored(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["*.py", "", "#!*__init__.py"])
        assert "README.md" in filtered
        assert {f for f in filtered if f.endswith(".py")} == set()

    async def test_override_order_matters(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["!*__init__.py", "*.py"])

        should_be_included = _path_set(
            "README.md", "venv/config.json", "utilities/README.md"
        )

        assert should_be_included.issubset(filtered)
        assert {f for f in filtered if f.endswith(".py")} == set()

    async def test_partial_directory_filter(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["utilities/*.md"])

        should_be_included = _path_set(
            "README.md", "utilities", "utilities/__init__.py"
        )

        assert should_be_included.issubset(filtered)
        assert "utilities/README.md" not in filtered

    @pytest.mark.parametrize("include_dirs", [True, False])
    async def test_full_directory_filter(self, tmpdir, messy_dir, include_dirs):
        tmpdir.ensure("utilities/venv")
        filtered = filter_files(
            tmpdir, ignore_patterns=["venv/**"], include_dirs=include_dirs
        )
        assert str(Path("utilities/venv")) in filtered
        expected = {"venv"} if include_dirs else set()
        assert {f for f in filtered if f.startswith("venv")} == expected

    @pytest.mark.parametrize("include_dirs", [True, False])
    async def test_alternate_directory_filter(self, tmpdir, messy_dir, include_dirs):
        filtered = filter_files(
            tmpdir, ignore_patterns=["__pycache__/"], include_dirs=include_dirs
        )
        assert "__init__.py" in filtered
        expected = (
            {str(Path("utilities/__pycache__")), str(Path("venv/__pycache__"))}
            if include_dirs
            else set()
        )
        assert {f for f in filtered if "pycache" in f} == expected


class TestPlatformSpecificRelpath:
    @pytest.mark.skipif(sys.platform == "win32", reason="This is a unix-specific test")
    @pytest.mark.parametrize(
        "path_str,expected",
        [
            ("mypath.py:my_flow", "mypath.py:my_flow"),
            (r"my\test\path.py:my_flow", "my/test/path.py:my_flow"),
            ("my\\test\\path.py:my_flow", "my/test/path.py:my_flow"),
            ("my/test/path.py:my_flow", "my/test/path.py:my_flow"),
        ],
    )
    def test_paths_on_unix(self, path_str, expected):
        new_path = relative_path_to_current_platform(path_str)

        assert isinstance(new_path, PosixPath)
        assert str(new_path) == expected

    @pytest.mark.skipif(
        sys.platform != "win32", reason="This is a windows-specific test"
    )
    @pytest.mark.parametrize(
        "path_str,expected",
        [
            ("mypath.py:my_flow", "mypath.py:my_flow"),
            (r"my\test\path.py:my_flow", "my\\test\\path.py:my_flow"),
            ("my\\test\\path.py:my_flow", "my\\test\\path.py:my_flow"),
            ("my/test/path.py:my_flow", "my\\test\\path.py:my_flow"),
        ],
    )
    def test_paths_on_windows(self, path_str, expected):
        new_path = relative_path_to_current_platform(path_str)

        assert isinstance(new_path, WindowsPath)
        assert str(new_path) == expected
