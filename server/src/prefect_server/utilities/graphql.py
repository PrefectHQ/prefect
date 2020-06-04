# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import json
import textwrap
from typing import Any, Dict, Union

import ariadne
from box import Box

import prefect_server
from prefect.utilities.graphql import parse_graphql
from prefect_server.utilities.http import httpx_client

# define common objects for binding resolvers
query = ariadne.QueryType()
mutation = ariadne.MutationType()


class GraphQLClient:
    def __init__(self, url, headers=None):
        self.url = url
        self.headers = headers or {}
        self.logger = prefect_server.utilities.logging.get_logger(type(self).__name__)

    async def execute(
        self,
        query: Union[str, Dict[str, Any]],
        variables: Dict[str, Any] = None,
        headers: dict = None,
        raise_on_error: bool = True,
        as_box=True,
    ) -> dict:
        """
        Args:
            - query (Union[str, dict]): either a GraphQL query string or objects that are compatible
                with prefect.utilities.graphql.parse_graphql().
            - variables (dict): GraphQL variables
            - headers (dict): Headers to include with the GraphQL request
            - raise_on_error (bool): if True, a `ValueError` is raised whenever the GraphQL
                result contains an `errors` field.
            - as_box (bool): if True, a `box.Box` object is returned, which behaves like a dict
                but allows "dot" access in addition to key access.

        Returns:
            - dict: a dictionary of GraphQL info. If `as_box` is True, it will be a Box (dict subclass)

        Raises:
            - GraphQLSyntaxError: if the provided query is not a valid GraphQL query
            - ValueError: if `raise_on_error=True` and there are any errors during execution.
        """
        if not isinstance(query, str):
            query = parse_graphql(query)

        # validate query
        if prefect_server.config.debug:
            ariadne.gql(query)

        # timeout of 30 seconds
        response = await httpx_client.post(
            self.url,
            json=dict(query=query, variables=variables or {}),
            headers=headers or self.headers,
            timeout=30,
        )
        try:
            result = response.json()
        except json.decoder.JSONDecodeError as exc:
            self.logger.error(
                "JSON Decode Error on {}".format(response.content.decode())
            )
            self.logger.error(exc)
            raise exc

        if raise_on_error and "errors" in result:
            if prefect_server.config.debug:
                self.log_query_debug_info(
                    query=query,
                    variables=variables or {},
                    errors=result["errors"],
                    headers=headers or self.headers,
                )
            raise ValueError(result["errors"])

        # convert to box
        if as_box:
            result = Box(result)

        return result

    def log_query_debug_info(
        self, query: str, variables: dict, errors: str = None, headers: dict = None
    ) -> None:
        """
        Creates a nicely-formatted representation of a query, variables, and any errors.
        """

        debug_info = textwrap.dedent(
            """
            GraphQL Query:

                ### --- Query ------------------------------

            {query}


                ### --- Variables ------------------------------

            {variables}


                ### --- Errors ------------------------------

            {errors}


                ### --- Headers ------------------------------

            {headers}
            """
        ).format(
            query=textwrap.indent(
                query if len(query.splitlines()) < 100 else "<skipped due to length>",
                "        ",
            ),
            variables=textwrap.indent(
                json.dumps(variables or {}, sort_keys=True, indent=2)
                if len(variables or {}) < 100
                else "<skipped due to length>",
                "        ",
            ),
            errors=textwrap.indent(
                json.dumps(errors or "", sort_keys=True, indent=2), "        "
            ),
            headers=textwrap.indent(
                json.dumps(headers or {}, sort_keys=True, indent=2), "        "
            ),
        )
        self.logger.debug(debug_info)
