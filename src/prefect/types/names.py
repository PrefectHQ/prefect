from __future__ import annotations

import re
from functools import partial
from typing import Annotated, overload

from pydantic import AfterValidator, BeforeValidator, Field

LOWERCASE_LETTERS_NUMBERS_AND_DASHES_ONLY_REGEX = "^[a-z0-9-]*$"
LOWERCASE_LETTERS_NUMBERS_AND_UNDERSCORES_REGEX = "^[a-z0-9_]*$"
LOWERCASE_LETTERS_NUMBERS_AND_DASHES_OR_UNDERSCORES_REGEX = "^[a-z0-9-_]*$"


@overload
def raise_on_name_alphanumeric_dashes_only(
    value: str, field_name: str = ...
) -> str: ...


@overload
def raise_on_name_alphanumeric_dashes_only(
    value: None, field_name: str = ...
) -> None: ...


def raise_on_name_alphanumeric_dashes_only(
    value: str | None, field_name: str = "value"
) -> str | None:
    if value is not None and not bool(
        re.match(LOWERCASE_LETTERS_NUMBERS_AND_DASHES_ONLY_REGEX, value)
    ):
        raise ValueError(
            f"{field_name} must only contain lowercase letters, numbers, and dashes."
        )
    return value


@overload
def raise_on_name_alphanumeric_underscores_only(
    value: str, field_name: str = ...
) -> str: ...


@overload
def raise_on_name_alphanumeric_underscores_only(
    value: None, field_name: str = ...
) -> None: ...


def raise_on_name_alphanumeric_underscores_only(
    value: str | None, field_name: str = "value"
) -> str | None:
    if value is not None and not re.match(
        LOWERCASE_LETTERS_NUMBERS_AND_UNDERSCORES_REGEX, value
    ):
        raise ValueError(
            f"{field_name} must only contain lowercase letters, numbers, and"
            " underscores."
        )
    return value


def raise_on_name_alphanumeric_dashes_underscores_only(
    value: str, field_name: str = "value"
) -> str:
    if not re.match(LOWERCASE_LETTERS_NUMBERS_AND_DASHES_OR_UNDERSCORES_REGEX, value):
        raise ValueError(
            f"{field_name} must only contain lowercase letters, numbers, and"
            " dashes or underscores."
        )
    return value


BANNED_CHARACTERS = ["/", "%", "&", ">", "<"]

WITHOUT_BANNED_CHARACTERS = r"^[^" + "".join(BANNED_CHARACTERS) + "]+$"
Name = Annotated[str, Field(pattern=WITHOUT_BANNED_CHARACTERS)]

WITHOUT_BANNED_CHARACTERS_EMPTY_OK = r"^[^" + "".join(BANNED_CHARACTERS) + "]*$"
NameOrEmpty = Annotated[str, Field(pattern=WITHOUT_BANNED_CHARACTERS_EMPTY_OK)]


def non_emptyish(value: str) -> str:
    if not value.strip("' \""):
        raise ValueError("name cannot be an empty string")

    return value


NonEmptyishName = Annotated[
    str,
    Field(pattern=WITHOUT_BANNED_CHARACTERS),
    BeforeValidator(non_emptyish),
]


### specific names

BlockDocumentName = Annotated[
    Name,
    AfterValidator(
        partial(
            raise_on_name_alphanumeric_dashes_only, field_name="Block document name"
        )
    ),
]


BlockTypeSlug = Annotated[
    str,
    AfterValidator(
        partial(raise_on_name_alphanumeric_dashes_only, field_name="Block type slug")
    ),
]

ArtifactKey = Annotated[
    str,
    AfterValidator(
        partial(raise_on_name_alphanumeric_dashes_only, field_name="Artifact key")
    ),
]

MAX_VARIABLE_NAME_LENGTH = 255


VariableName = Annotated[
    str,
    AfterValidator(
        partial(
            raise_on_name_alphanumeric_dashes_underscores_only,
            field_name="Variable name",
        )
    ),
    Field(
        max_length=MAX_VARIABLE_NAME_LENGTH,
        description="The name of the variable",
        examples=["my_variable"],
    ),
]
