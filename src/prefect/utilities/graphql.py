import re
import textwrap
from typing import Any, Union
from prefect.utilities.collections import as_nested_dict


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
        if self.__arguments:
            arguments = parse_graphql_arguments(self.__arguments)
            return "{name}({arguments})".format(name=self.__name, arguments=arguments)
        return self.__name


def parse_graphql(document: Any) -> str:
    """
    Parses a document into a GraphQL-compliant query string.

    Documents can be a mix of `strings`, `dicts`, `lists` (or other sequences), and
    `GQLObjects`.

    The parser attempts to maintain the form of the Python objects in the resulting GQL query.

    For example:
    ```
    query = parse_graphql({
        'query': {
            'books(published: {gt: 1990})': {
                'title'
            },
            'authors': [
                'name',
                'books': {
                    'title'
                }]
            }
        }
    })
    ```
    results in:
    ```
    query {
        books(published: {gt: 1990}) {
            title
        }
        authors {
            name
            books {
                title
            }
        }
    }
    ```

    Args:
        - document (Any): A collection of Python objects complying with the general shape
            of a GraphQL query. Generally, this will consist of (at least) a dictionary, but
            also sequences and `GQLObjects`.

    Returns:
        - str: a GraphQL query compiled from the provided Python structures.

    Raises:
        - TypeError: if the user provided a `GQLObject` class, rather than an instance.
    """
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


def parse_graphql_arguments(arguments: Union[dict, str]) -> str:
    """
    Parses a dictionary of GraphQL arguments, returning a GraphQL-compliant string
    representation. If a string is passed, it is returned without modification.

    This parser makes a few adjustments to the dictionary's usual string representation:
        - `'` around keys are removed
        - spaces added around curly braces
        - leading and lagging braces are removed
        - `True` becomes `true`, `False` becomes `false`, and `None` becomes `null`
    """
    if isinstance(arguments, dict):
        parsed = as_nested_dict(arguments, dict)
        # remove quotes around keys
        parsed = str(parsed).replace("'", "")
        # strip leading and lagging braces
        parsed = parsed[1:-1]
        # add space before/after braces
        parsed = parsed.replace("{", "{ ").replace("}", " }")
        # replace True with true
        parsed = re.sub(r"\bTrue\b", "true", parsed)
        # replace False with false
        parsed = re.sub(r"\bFalse\b", "false", parsed)
        # replace None with null
        parsed = re.sub(r"\bNone\b", "null", parsed)
        return parsed
    return arguments
