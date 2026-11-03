import pytest

from prefect.utilities.names import generate_slug, obfuscate, obfuscate_string


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
    # default is not to reveal any characters
    assert obfuscate_string(s) == obfuscate_string(s, show_tail=False) == "*" * 8
    # show tail
    assert obfuscate_string(s, show_tail=True) == expected


@pytest.mark.parametrize(
    "s, expected",
    [
        (None, "********"),
        ("", "********"),
        ("a", "********"),
        ("abcdefghijklm", "*****klm"),
        (1, "********"),
        ({"x": "y"}, "********"),
    ],
)
def test_obfuscate(s, expected):
    # default is not to reveal any characters
    assert obfuscate(s) == obfuscate(s, show_tail=False) == "*" * 8
    # show tail
    assert obfuscate(s, show_tail=True) == expected


@pytest.mark.parametrize("n_words", [1, 0, -3, "x"])
def test_generate_slug_rejects_fewer_than_two_words(n_words):
    with pytest.raises(ValueError, match="must contain at least 2 words"):
        generate_slug(n_words)


def test_generate_slug_still_works():
    assert len(generate_slug(2).split("-")) == 2
