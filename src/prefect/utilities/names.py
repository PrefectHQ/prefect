from typing import Any

import coolname  # type: ignore # the version after coolname 2.2.0 should have stubs.

OBFUSCATED_PREFIX = "****"

IGNORE_LIST = {
    "sexy",
    "demonic",
    "kickass",
    "heretic",
    "godlike",
    "booby",
    "chubby",
    "gay",
    "sloppy",
    "funky",
    "juicy",
    "beaver",
    "curvy",
    "fat",
    "flashy",
    "flat",
    "thick",
    "nippy",
}


def generate_slug(n_words: int) -> str:
    """
    Generates a random slug.

    Args:
        - n_words (int): the number of words in the slug
    """
    words = coolname.generate(n_words)

    # regenerate words if they include ignored words
    while IGNORE_LIST.intersection(words):
        words = coolname.generate(n_words)

    return "-".join(words)


def obfuscate(s: Any, show_tail: bool = False) -> str:
    """
    Obfuscates any data type's string representation. See `obfuscate_string`.
    """
    if s is None:
        return OBFUSCATED_PREFIX + "*" * 4

    return obfuscate_string(str(s), show_tail=show_tail)


def obfuscate_string(s: str, show_tail: bool = False) -> str:
    """
    Obfuscates a string by returning a new string of 8 characters. If the input
    string is longer than 10 characters and show_tail is True, then up to 4 of
    its final characters will become final characters of the obfuscated string;
    all other characters are "*".

    "abc"      -> "********"
    "abcdefgh" -> "********"
    "abcdefghijk" -> "*******k"
    "abcdefghijklmnopqrs" -> "****pqrs"
    """
    result = OBFUSCATED_PREFIX + "*" * 4
    # take up to 4 characters, but only after the 10th character
    suffix = s[10:][-4:]
    if suffix and show_tail:
        result = f"{result[: -len(suffix)]}{suffix}"
    return result
