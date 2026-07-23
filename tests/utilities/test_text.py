import pytest

from prefect.utilities.text import fuzzy_match_string, truncated_to


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


@pytest.mark.parametrize("value", [None, ""])
def test_truncated_to_empty_values(value):
    assert truncated_to(10, value) == ""


def test_truncated_to_returns_value_when_within_length():
    assert truncated_to(10, "short") == "short"


def test_truncated_to_truncates_long_value():
    result = truncated_to(10, "x" * 100)
    assert result == "xxxxx...90 additional characters...xxxxx"
    assert len(result) < 100


def test_truncated_to_keeps_original_when_truncation_would_be_longer():
    # The placeholder text can be longer than the tiny amount trimmed, in which
    # case the original value is returned unchanged.
    value = "x" * 25
    assert truncated_to(20, value) == value
