import re

from prefect.exceptions import InvalidNameError

BANNED_CHARACTERS = ["/", "%", "&", ">", "<"]
LOWERCASE_LETTERS_NUMBERS_AND_DASHES_ONLY_REGEX = "^[a-z0-9-]*$"
LOWERCASE_LETTERS_NUMBERS_AND_UNDERSCORES_REGEX = "^[a-z0-9_]*$"


def raise_on_name_with_banned_characters(name: str) -> None:
    """
    Raise an InvalidNameError if the given name contains any invalid
    characters.
    """
    if any(c in name for c in BANNED_CHARACTERS):
        raise InvalidNameError(
            f"Name {name!r} contains an invalid character. "
            f"Must not contain any of: {BANNED_CHARACTERS}."
        )


def raise_on_name_alphanumeric_dashes_only(value, field_name: str = "value"):
    if not bool(re.match(LOWERCASE_LETTERS_NUMBERS_AND_DASHES_ONLY_REGEX, value)):
        raise ValueError(
            f"{field_name} must only contain lowercase letters, numbers, and dashes."
        )
    return value


def raise_on_name_alphanumeric_underscores_only(value, field_name: str = "value"):
    if not bool(re.match(LOWERCASE_LETTERS_NUMBERS_AND_UNDERSCORES_REGEX, value)):
        raise ValueError(
            f"{field_name} must only contain lowercase letters, numbers, and"
            " underscores."
        )
    return value
