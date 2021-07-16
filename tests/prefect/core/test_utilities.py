import pytest

from prefect.core.utilities import file_hash


def test_file_hash_returns_hash():
    assert isinstance(file_hash(__file__), str)


def test_file_hash_raises_if_path_doesnt_exist():
    fake_path = "/root/foo/bar.txt"

    with pytest.raises(FileNotFoundError, match="/root/foo/bar.txt"):
        file_hash(path=fake_path)
