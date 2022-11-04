import os
import sys
from pathlib import Path, PosixPath, WindowsPath
from tempfile import TemporaryDirectory
from typing import Tuple

import pytest

from prefect.utilities.filesystem import (
    filter_files,
    prefect_copytree,
    relative_path_to_current_platform,
)


def setup_test_directory(tmp_src: str, sub_dir: str = "puppy") -> Tuple[str, str]:
    """Add files and directories to a temporary directory. Returns a tuple with the
    expected parent-level contents and the expected child-level contents.
    """
    # add file to tmp_src
    f1_name = "dog.text"
    f1_path = Path(tmp_src) / f1_name
    f1 = open(f1_path, "w")
    f1.close()

    # add sub-directory to tmp_src
    sub_dir_path = Path(tmp_src) / sub_dir
    os.mkdir(sub_dir_path)

    # add file to sub-directory
    f2_name = "cat.txt"
    f2_path = sub_dir_path / f2_name
    f2 = open(f2_path, "w")
    f2.close()

    parent_contents = {f1_name, sub_dir}
    child_contents = {f2_name}

    assert set(os.listdir(tmp_src)) == parent_contents
    assert set(os.listdir(sub_dir_path)) == child_contents

    return parent_contents, child_contents


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
        assert "README.md" in filtered
        assert "venv" in filtered
        assert "venv/config.json" in filtered
        assert "utilities/README.md" in filtered
        assert {f for f in filtered if f.endswith(".py")} == set()

    async def test_simple_filetype_filter_with_ignore_dirs(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["*.py"], include_dirs=False)
        assert "README.md" in filtered
        assert "venv" not in filtered
        assert "venv/config.json" in filtered
        assert "utilities/README.md" in filtered
        assert {f for f in filtered if f.endswith(".py")} == set()

    async def test_simple_filetype_filter_with_override(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["*.py", "!*__init__.py"])
        assert "README.md" in filtered
        assert "venv" in filtered
        assert "venv/config.json" in filtered
        assert "utilities/README.md" in filtered
        assert {f for f in filtered if f.endswith(".py")} == {
            "__init__.py",
            "utilities/__init__.py",
        }

    async def test_comments_and_empty_lines_are_ignored(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["*.py", "", "#!*__init__.py"])
        assert "README.md" in filtered
        assert {f for f in filtered if f.endswith(".py")} == set()

    async def test_override_order_matters(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["!*__init__.py", "*.py"])
        assert "README.md" in filtered
        assert "venv/config.json" in filtered
        assert "utilities/README.md" in filtered
        assert {f for f in filtered if f.endswith(".py")} == set()

    async def test_partial_directory_filter(self, tmpdir, messy_dir):
        filtered = filter_files(tmpdir, ignore_patterns=["utilities/*.md"])
        assert "README.md" in filtered
        assert "utilities" in filtered
        assert "utilities/__init__.py" in filtered
        assert "utilities/README.md" not in filtered

    @pytest.mark.parametrize("include_dirs", [True, False])
    async def test_full_directory_filter(self, tmpdir, messy_dir, include_dirs):
        tmpdir.ensure("utilities/venv")
        filtered = filter_files(
            tmpdir, ignore_patterns=["venv/**"], include_dirs=include_dirs
        )
        assert "utilities/venv" in filtered
        expected = {"venv"} if include_dirs else set()
        assert {f for f in filtered if f.startswith("venv")} == expected

    @pytest.mark.parametrize("include_dirs", [True, False])
    async def test_alternate_directory_filter(self, tmpdir, messy_dir, include_dirs):
        filtered = filter_files(
            tmpdir, ignore_patterns=["__pycache__/"], include_dirs=include_dirs
        )
        assert "__init__.py" in filtered
        expected = (
            {"utilities/__pycache__", "venv/__pycache__"} if include_dirs else set()
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


class TestPrefectCopyTree:
    def test_dir_contents_copied_correctly(self):

        sub_dir_name = "puppy"

        with TemporaryDirectory() as tmp_src:
            parent_contents, child_contents = setup_test_directory(
                tmp_src, sub_dir_name
            )
            # move file contents to tmp_dst
            with TemporaryDirectory() as tmp_dst:

                prefect_copytree(src=tmp_src, dst=tmp_dst)
                assert set(os.listdir(tmp_dst)) == set(parent_contents)
                assert set(os.listdir(Path(tmp_dst) / sub_dir_name)) == child_contents

    async def test_dir_contents_copied_correctly_with_ignore_func(
        self,
    ):
        """Make sure that ignore file behaves properly."""

        sub_dir_name = "puppy"

        with TemporaryDirectory() as tmp_src:
            parent_contents, child_contents = setup_test_directory(
                tmp_src, sub_dir_name
            )

            # ignore .py files
            ignore_fpath = Path(tmp_src) / ".ignore"
            with open(ignore_fpath, "w") as f:
                f.write("*.py")

            # contents without .py files
            expected_contents = os.listdir(tmp_src)

            # add .py files
            with open(Path(tmp_src) / "dog.py", "w") as f:
                f.write("pass")

            with open(Path(tmp_src) / sub_dir_name / "cat.py", "w") as f:
                f.write("pass")

            def ignore_func(directory, files):
                ignore_patterns = ["*.py"]
                included_files = filter_files(directory, ignore_patterns)
                return_val = [f for f in files if f not in included_files]
                return return_val

            # move file contents to tmp_dst
            with TemporaryDirectory() as tmp_dst:
                prefect_copytree(src=tmp_src, dst=tmp_dst, ignore=ignore_func)

                assert set(os.listdir(tmp_dst)) == set(expected_contents)
                assert set(os.listdir(Path(tmp_dst) / sub_dir_name)) == child_contents
