from collections import OrderedDict


class GQLResult(OrderedDict):
    """
    An ordered dict that also supports attribute ("dot") access
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


def format_graphql_result(graphql_result):
    """
    Given a graphql_result formatted as a dictionary, returns an object
    that also supports "dot" access:

    graphql_result['data']['child']
    graphql_result.data.child
    """
    if not isinstance(graphql_result, dict):
        return graphql_result
    for key, value in list(graphql_result.items()):
        if isinstance(value, dict):
            graphql_result[key] = format_graphql_result(value)
        elif isinstance(value, list):
            graphql_result[key] = [format_graphql_result(v) for v in value]
    return GQLResult(graphql_result)
