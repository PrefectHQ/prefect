import webbrowser

from prefect.utilities.graphql import parse_graphql


def open_in_playground(query: str) -> None:
    """
    Open a graphql query in the Prefect GQL playground
    """
    from prefect import config
    url = "{}?query={}".format(config.cloud.get("graphql"), parse_graphql(query))
    webbrowser.open(url)
