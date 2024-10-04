import pytest

from prefect.utilities.text import fuzzy_match_string


@pytest.mark.parametrize(
    "word, possibilities, expected",
    [
        ("hello", ["hello", "world"], "hello"),
        ("Hello", ["hello", "world"], "hello"),
        ("colour", ["color", "flavour"], "color"),
        ("progam", ["program", "progress"], "program"),  # noqa
        ("pythn", ["python", "cython"], "python"),
        ("cat", ["dog", "pig", "cow"], None),
    ],
    ids=[
        "Exact match",
        "Case insensitive match",
        "Close match - British vs American spelling",
        "Missing character",
        "Multiple close matches",
        "No close matches within threshold",
    ],
)
def test_fuzzy_match_string(word, possibilities, expected):
    assert fuzzy_match_string(word, possibilities) == expected
