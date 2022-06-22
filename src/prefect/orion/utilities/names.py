import coolname

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
