import hashlib

import pytest

from prefect.utilities.hashing import file_hash, stable_hash


@pytest.mark.parametrize(
    "inputs,hash_algo,expected",
    [
        (
            ("hello",),
            None,
            "9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043",
        ),
        (
            ("goodbye",),
            None,
            "de2c0320cdff37271049dfa8cb835ffd54200216253a1dfbad75a1ae51bd30bb499e14e37fe993ba2ea57b863fc56304de94073d880c9c18eb0a469cde211d02",
        ),
        (
            (b"goodbye",),
            None,
            "de2c0320cdff37271049dfa8cb835ffd54200216253a1dfbad75a1ae51bd30bb499e14e37fe993ba2ea57b863fc56304de94073d880c9c18eb0a469cde211d02",
        ),
        (
            ("hello", "goodbye"),
            None,
            "be68ed8f7c48c3c78af4ab2a1c8ba497f469a55c171a6d81e9386f0f2245ed4c8bc85a2135ef8d839151dad1361522cdfbb25d0f252395c29b81a9445b52ca83",
        ),
        (
            ("hello", b"goodbye"),
            None,
            "be68ed8f7c48c3c78af4ab2a1c8ba497f469a55c171a6d81e9386f0f2245ed4c8bc85a2135ef8d839151dad1361522cdfbb25d0f252395c29b81a9445b52ca83",
        ),
        (
            ("goodbye", "hello"),
            None,
            "b779b909718f0c4d9b85f0a1a71bb58cec74e6deece4eadb522261e0cee267a7eb7f4d57327bc369c1774c0cf7d5185db0d5e3f04cc88aff78d1899249bd26d5",
        ),
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
        assert val == hashlib.sha512(b"0").hexdigest()
        # Check if the hash is stable
        assert (
            val
            == "31bca02094eb78126a517b206a88c73cfa9ec6f704c7030d18212cace820f025f00bf0ea68dbf3f3a5436ca63b53bf7bf80ad8d5de7d8359d0b7fed9dbc3ab99"
        )
