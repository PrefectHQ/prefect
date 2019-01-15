import json
import re
import textwrap
import uuid
from collections.abc import KeysView, ValuesView
from typing import Any, Union

from prefect.utilities.collections import DotDict, as_nested_dict


def lowercase_first_letter(s: str) -> str:
    """
    Given a string, returns that string with a lowercase first letter
    """
    if s:
        return s[0].lower() + s[1:]
    return s


class GraphQLResult(DotDict):
    __protect_critical_keys__ = False

    def __repr__(self) -> str:
        try:
            return json.dumps(as_nested_dict(self, dict), indent=4)
        except TypeError:
            return repr(self.to_dict())


class EnumValue:
    """
    When parsing GraphQL arguments, strings can be wrapped in this class to be rendered
    as enum values, without quotation marks.

    Args:
        - value (str): the value that should be represented as an enum value

    """

    def __init__(self, value: str):
        self.value = value

    def __str__(self) -> str:
        return self.value


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
        return '<GQL: "{name}">'.format(name=self.__name)

    def __str__(self) -> str:
        if self.__arguments:
            return with_args(self.__name, self.__arguments)
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

    For convenience, if a dictionary key is True, it is ignored and the key alone is used as
    a field name

    ```python
    {'query':{
        'books': {
            'id': True,
            'name': True,
            'author': {
                'id',
                'name',
            }
        }
    }}
    ```

    is equivalent to:

    ```python
    {'query':{
        'books': [
            'id',
            'name',
            {'author': {
                'id',
                'name',
            }}
        ]
    }}
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
    if isinstance(document, (tuple, list, set, KeysView, ValuesView)):
        return "\n".join(
            [_parse_graphql_inner(item, delimiter=delimiter) for item in document]
        )
    elif isinstance(document, (dict, DotDict)):
        result = []
        for key, value in document.items():
            if value is True:
                result.append(key)
            else:
                result.append(
                    "{key} {{\n{value}\n}}".format(
                        key=key, value=_parse_graphql_inner(value, delimiter=delimiter)
                    )
                )

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


def parse_graphql_arguments(arguments: Any) -> str:
    """
    Parses a dictionary of GraphQL arguments, returning a GraphQL-compliant string
    representation. If a string is passed, it is returned without modification.

    This parser makes a few adjustments to the dictionary's usual string representation:
        - `'` around keys are removed
        - spaces added around curly braces
        - leading and lagging braces are removed
        - `True` becomes `true`, `False` becomes `false`, and `None` becomes `null`

    Args:
        - arguments (Any): an object (usually a dictionary) representing the GraphQL arguments

    Returns:
        - str: a string representing the parsed GraphQL arguments
    """
    parsed = _parse_arguments_inner(arguments)
    # remove '{ ' and ' }' from front and end of parsed dict
    if isinstance(arguments, (dict, DotDict)):
        parsed = parsed[2:-2]
    # remove '"' and '"' from front and end of parsed str
    elif isinstance(arguments, str):
        parsed = parsed[1:-1]
    return parsed


def _parse_arguments_inner(arguments: Any) -> str:
    if isinstance(arguments, (dict, DotDict)):
        # empty dicts are valid GQL arguments
        if len(arguments) == 0:
            return "{}"

        formatted = []
        for key, value in arguments.items():
            formatted.append(
                "{key}: {value}".format(key=key, value=_parse_arguments_inner(value))
            )
        return "{ " + ", ".join(formatted) + " }"
    elif isinstance(arguments, (list, tuple, set, KeysView, ValuesView)):
        return "[" + ", ".join([_parse_arguments_inner(a) for a in arguments]) + "]"
    elif isinstance(arguments, str):
        return json.dumps(arguments)
    elif arguments is True:
        return "true"
    elif arguments is False:
        return "false"
    elif arguments is None:
        return "null"
    elif isinstance(arguments, uuid.UUID):
        return _parse_arguments_inner(str(arguments))
    return str(arguments)


def with_args(field: Any, arguments: Any) -> str:
    """
    Given Python objects representing a field name and arguments, formats them as a single
    GraphQL compatible string.

    Example:

    ```
    query = parse_graphql({
        'query': {
            with_args("task", {"where": {"id": 3}}): {
                "id"
            }
        }
    })

    assert query == '''
        query {
            task(where: {id: 3}) {
                id
            }
        }
        '''
    ```

    Args:
        - field (Any): the GraphQL field that will be supplied with arguments
        - arguments (Any): the arguments to be parsed and  supplied to the field

    Returns:
        - str: the parsed field and arguments
    """
    parsed_field = parse_graphql(field)
    parsed_arguments = parse_graphql_arguments(arguments)
    return "{field}({arguments})".format(field=parsed_field, arguments=parsed_arguments)
