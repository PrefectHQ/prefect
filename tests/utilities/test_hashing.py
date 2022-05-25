import hashlib

import pytest

import prefect
from prefect.utilities.hashing import file_hash, stable_hash, to_qualified_name


@pytest.mark.parametrize(
    "inputs,hash_algo,expected",
    [
        (("hello",), None, "5d41402abc4b2a76b9719d911017c592"),
        (("goodbye",), None, "69faab6268350295550de7d587bc323d"),
        ((b"goodbye",), None, "69faab6268350295550de7d587bc323d"),
        (("hello", "goodbye"), None, "441add4718519b71e42d329a834d6d5e"),
        (("hello", b"goodbye"), None, "441add4718519b71e42d329a834d6d5e"),
        (("goodbye", "hello"), None, "c04d8ccb6b9368703e62be93358094f9"),
        (
            ("goodbye", "hello"),
            hashlib.sha256,
            "b0ea3cd336c7962e2be976c5ee262bb986df79ea32d1fda1872cf146d982a641",
        ),
        (
            ("hello", b"goodbye"),
            hashlib.sha256,
            "3e4dc8cb9fce3f3e0aea6905faf58fd5baba4981c4f043ae03f58ef6a331de2f",
        ),
    ],
)
def test_stable_hash(inputs, hash_algo, expected):
    if hash_algo is None:
        assert stable_hash(*inputs) == expected
    else:
        assert stable_hash(*inputs, hash_algo=hash_algo) == expected


def my_fn():
    pass


@pytest.mark.parametrize(
    "obj,expected",
    [
        (to_qualified_name, "prefect.utilities.hashing.to_qualified_name"),
        (prefect.tasks.Task, "prefect.tasks.Task"),
        (prefect.tasks.Task.__call__, "prefect.tasks.Task.__call__"),
        (lambda x: x + 1, "tests.utilities.test_hashing.<lambda>"),
        (my_fn, "tests.utilities.test_hashing.my_fn"),
    ],
)
def test_to_qualified_name(obj, expected):
    assert to_qualified_name(obj) == expected


class TestFileHash:
    def test_file_hash_returns_string(self):
        assert isinstance(file_hash(__file__), str)

    def test_file_hash_requires_path(self):
        with pytest.raises(TypeError, match="path"):
            file_hash()

    def test_file_hash_raises_if_path_doesnt_exist(self, tmp_path):
        fake_path = tmp_path.joinpath("foobar.txt")

        with pytest.raises(FileNotFoundError):
            file_hash(path=fake_path)

    def test_file_hash_hashes(self, tmp_path):
        with open(tmp_path.joinpath("test.py"), "w") as f:
            f.write("0")

        val = file_hash(tmp_path.joinpath("test.py"))
        assert val == hashlib.md5(b"0").hexdigest()
        # Check if the hash is stable
        assert val == "cfcd208495d565ef66e7dff9f98764da"
