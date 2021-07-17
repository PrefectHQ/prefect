import pytest
import hashlib

from prefect.core.utilities import file_hash


def test_file_hash_returns_string():
    assert isinstance(file_hash(__file__), str)


def test_file_hash_requires_path():
    with pytest.raises(TypeError, match="path"):
        file_hash()


def test_file_hash_raises_if_path_doesnt_exist():
    fake_path = "/root/foo/bar.txt"

    with pytest.raises(FileNotFoundError, match="/root/foo/bar.txt"):
        file_hash(path=fake_path)


def test_file_hash_hashes(tmpdir):
    with open(tmpdir / "test.py", "w") as f:
        f.write("0")

    val = file_hash(tmpdir / "test.py")
    assert val == hashlib.md5(b"0").hexdigest()
    # Check if the hash is stable
    assert val == "cfcd208495d565ef66e7dff9f98764da"
