# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import coolname

BLACKLIST = {
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

    # regenerate words if they include blacklisted words
    while BLACKLIST.intersection(words):
        words = coolname.generate(n_words)

    return "-".join(words)
