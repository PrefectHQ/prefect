import textwrap
from typing import Any


def lowercase_first_letter(s: str) -> str:
    """
    Given a string, returns that string with a lowercase first letter
    """
    if s:
        return s[0].lower() + s[1:]
    return s


class GQLObject:
    """
    Helper object for building GraphQL queries.
    """

    def __init__(self, name: str = None, _arguments: str = None):
        self.__name = name or lowercase_first_letter(type(self).__name__)
        self.__arguments = _arguments

    def __call__(self, arguments: str) -> "GQLObject":
        return type(self)(name=self.__name, _arguments=arguments)

    def __repr__(self) -> str:
        return '<GQL: "{name}">'.format(self.__name)

    def __str__(self) -> str:
        if not self.__arguments:
            return self.__name
        else:
            return "{name}({arguments})".format(
                name=self.__name, arguments=self.__arguments
            )


def parse_graphql(document: Any) -> str:
    delimiter = "    "
    parsed = _parse_graphql_inner(document, delimiter=delimiter)
    parsed = parsed.replace(delimiter + "}", "}")
    parsed = textwrap.dedent(parsed).strip()
    return parsed


def _parse_graphql_inner(document: Any, delimiter: str) -> str:
    """
    Inner loop function of for `parse_graphql`.
    """
    if isinstance(document, (tuple, list, set)):
        return "\n".join(
            [_parse_graphql_inner(item, delimiter=delimiter) for item in document]
        )
    elif isinstance(document, dict):
        result = [
            "{key} {{\n{value}\n}}".format(
                key=_parse_graphql_inner(key, delimiter=delimiter),
                value=_parse_graphql_inner(value, delimiter=delimiter),
            )
            for key, value in document.items()
        ]
        return _parse_graphql_inner(result, delimiter=delimiter)
    elif isinstance(document, type) and issubclass(document, GQLObject):
        raise TypeError(
            'It looks like you included a `GQLObject` class ("{name}") '
            "in your document. Did you mean to use an instance of that type?".format(
                name=document.__name__
            )
        )
    else:
        return str(document).replace("\n", "\n" + delimiter)
