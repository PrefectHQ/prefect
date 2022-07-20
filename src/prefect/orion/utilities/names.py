import coolname

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


def obfuscate_string(s: str) -> str:
    """
    Obfuscates a string by returning a new string of 8 characters. If the input
    string is longer than 10 characters, then up to 4 of its final characters
    will become final characters of the obfuscated string; all other characters
    are "*".

    "abc"      -> "********"
    "abcdefgh" -> "********"
    "abcdefghijk" -> "*******k"
    "abcdefghijklmnopqrs" -> "****pqrs"
    """
    result = OBFUSCATED_PREFIX + "*" * 4
    # take up to 4 characters, but only after the 10th character
    suffix = s[10:][-4:]
    if suffix:
        result = f"{result[:-len(suffix)]}{suffix}"
    return result
