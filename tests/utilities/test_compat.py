import os
from tempfile import TemporaryDirectory
from typing import Tuple

from anyio import Path

from prefect.utilities.compat import copytree
from prefect.utilities.filesystem import filter_files


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


class TestPrefectCopyTree:
    def test_dir_contents_copied_correctly(self):
        sub_dir_name = "puppy"

        with TemporaryDirectory() as tmp_src:
            parent_contents, child_contents = setup_test_directory(
                tmp_src, sub_dir_name
            )
            # move file contents to tmp_dst
            with TemporaryDirectory() as tmp_dst:

                copytree(src=tmp_src, dst=tmp_dst, dirs_exist_ok=True)
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
                copytree(
                    src=tmp_src, dst=tmp_dst, ignore=ignore_func, dirs_exist_ok=True
                )

                assert set(os.listdir(tmp_dst)) == set(expected_contents)
                assert set(os.listdir(Path(tmp_dst) / sub_dir_name)) == child_contents
