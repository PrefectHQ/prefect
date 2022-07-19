import pytest

from prefect.orion.utilities.names import obfuscate_string


@pytest.mark.parametrize(
    "s, expected",
    [
        ("", "********"),
        ("a", "********"),
        ("ab", "********"),
        ("abcdefghij", "********"),
        ("abcdefghijk", "*******k"),
        ("abcdefghijkl", "******kl"),
        ("abcdefghijklm", "*****klm"),
        ("abcdefghijklmn", "****klmn"),
        ("abcdefghijklmno", "****lmno"),
        ("ABCDEFGHIJKLmNO", "****LmNO"),
        ("              o", "****   o"),
    ],
)
def test_obfuscate_string(s, expected):
    assert obfuscate_string(s) == expected
