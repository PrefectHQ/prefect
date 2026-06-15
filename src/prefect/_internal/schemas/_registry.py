from referencing import Registry


def non_fetching_registry() -> Registry:
    """An empty `referencing.Registry` that disables remote `$ref` fetching.

    Passing an explicit registry to jsonschema suppresses its default behavior of
    fetching `$ref` URLs over the network while validating an instance. With an
    empty registry, external references raise `referencing.exceptions.Unresolvable`
    without any network request, while in-document references (`#/$defs/...`) still
    resolve normally.
    """
    return Registry()
