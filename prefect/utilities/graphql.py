from collections import OrderedDict

class AttrDict(OrderedDict):

    def __getattribute__(self, key):
        if key in self:
            return self[key]
        else:
            return super().__getattribute__(key)


def format_graphql_response(graphql_response):
    """
    Given a graphql_response formatted as a dictionary, returns an object
    that also supports "dot" access:

    graphql_response['data']['child']
    graphql_response.data.child
    """
    if not isinstance(graphql_response, dict):
        return graphql_response
    for key, value in list(graphql_response.items()):
        if isinstance(value, dict):
            graphql_response[key] = format_graphql_response(value)
        elif isinstance(value, list):
            graphql_response[key] = [format_graphql_response(v) for v in value]
    return AttrDict(graphql_response)
