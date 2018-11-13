import textwrap
from typing import Iterable


def lowercase_first_letter(s: str) -> str:
    if s:
        return s[0].lower() + s[1:]
    return s


class GQLObject:
    def __init__(self, name: str = None, arguments=None):
        self.__arguments = arguments
        self.__name = name or lowercase_first_letter(type(self).__name__)

    def __call__(self, arguments: str) -> "GQLObject":
        return type(self)(name=self.__name, arguments=arguments)

    def __repr__(self) -> str:
        return f'<GQL: "{self.__name}">'

    def __str__(self) -> str:
        if not self.__arguments:
            return self.__name
        else:
            return f"{self.__name}({self.__arguments})"


def parse_graphql(document, first=True):
    delimiter = "    "
    if isinstance(document, (tuple, list, set)):
        parsed = f"\n".join([parse_graphql(item, first=False) for item in document])
    elif isinstance(document, dict):
        result = []
        for key, value in document.items():
            k = parse_graphql(key, first=False)
            v = parse_graphql(value, first=False)
            result.append(f"{k} {{\n{v}\n}}")
        parsed = parse_graphql(result, first=False)
    elif isinstance(document, type) and issubclass(document, GQLObject):
        raise TypeError(
            f'It looks like you included a `GQLObject` class ("{document.__name__}") '
            "in your document. Did you mean to use an instance of that type?"
        )
    else:
        parsed = str(document).replace("\n", f"\n{delimiter}")

    if first:
        parsed = parsed.replace(f"{delimiter}}}", "}")

    return parsed
