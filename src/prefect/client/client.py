# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import datetime
import json
import os
from typing import TYPE_CHECKING, Optional, Union

import prefect
from prefect.client.result_handlers import ResultHandler
from prefect.utilities.graphql import (
    EnumValue,
    parse_graphql,
    with_args,
    GraphQLResult,
    as_nested_dict,
)

if TYPE_CHECKING:
    import requests
    from prefect.core import Flow


BuiltIn = Union[bool, dict, list, str, set, tuple]


class AuthorizationError(Exception):
    pass


class Client:
    """
    Client for communication with Prefect Cloud

    If the arguments aren't specified the client initialization first checks the prefect
    configuration and if the server is not set there it checks the current context. The
    token will only be present in the current context.

    Args:
        - api_server (str, optional): the URL to send all basic POST requests
            to; if not provided, will be pulled from `cloud.api` config var
        - graphql_server (str, optional): the URL to send all GraphQL requests
            to; if not provided, will be pulled from `cloud.graphql` config var
    """

    def __init__(self, api_server: str = None, graphql_server: str = None) -> None:
        if not api_server:
            api_server = prefect.config.cloud.get("api", None)
            if not api_server:
                raise ValueError("Could not determine API server.")
        self.api_server = api_server

        if not graphql_server:
            graphql_server = prefect.config.cloud.get("graphql") or self.api_server
        self.graphql_server = graphql_server

        token = prefect.config.cloud.get("auth_token", None)

        if token is None:
            token_path = os.path.expanduser("~/.prefect/.credentials/auth_token")
            if os.path.exists(token_path):
                with open(token_path, "r") as f:
                    token = f.read()

        self.token = token

    # -------------------------------------------------------------------------
    # Utilities

    def post(self, path: str, server: str = None, **params: BuiltIn) -> dict:
        """
        Convenience function for calling the Prefect API with token auth and POST request

        Args:
            - path (str): the path of the API url. For example, to POST
                http://prefect-server/v1/auth/login, path would be 'auth/login'.
            - server (str, optional): the server to send the POST request to;
                defaults to `self.api_server`
            - params (dict): POST parameters

        Returns:
            - dict: Dictionary representation of the request made
        """
        response = self._request(method="POST", path=path, params=params, server=server)
        if response.text:
            return response.json()
        else:
            return {}

    def graphql(self, query: str, **variables: Union[bool, dict, str]) -> dict:
        """
        Convenience function for running queries against the Prefect GraphQL API

        Args:
            - query (str): A string representation of a graphql query to be executed
            - **variables (kwarg): Variables to be filled into a query with the key being
                equivalent to the variables that are accepted by the query

        Returns:
            - dict: Data returned from the GraphQL query

        Raises:
            - ValueError if there are errors raised in the graphql query
        """
        result = self.post(
            path="",
            query=query,
            variables=json.dumps(variables),
            server=self.graphql_server,
        )

        if "errors" in result:
            raise ValueError(result["errors"])
        else:
            return as_nested_dict(result, GraphQLResult).data  # type: ignore

    def _request(
        self, method: str, path: str, params: dict = None, server: str = None
    ) -> "requests.models.Response":
        """
        Runs any specified request (GET, POST, DELETE) against the server

        Args:
            - method (str): The type of request to be made (GET, POST, DELETE)
            - path (str): Path of the API URL
            - params (dict, optional): Parameters used for the request
            - server (str, optional): The server to make requests against, base API
                server is used if not specified

        Returns:
            - requests.models.Response: The response returned from the request

        Raises:
            - ValueError if the client token is not in the context (due to not being logged in)
            - ValueError if a method is specified outside of the accepted GET, POST, DELETE
            - requests.HTTPError if a status code is returned that is not `200` or `401`
        """
        # lazy import for performance
        import requests

        if server is None:
            server = self.api_server
        assert isinstance(server, str)  # mypy assert

        if self.token is None:
            raise ValueError("Call Client.login() to set the client token.")

        url = os.path.join(server, path.lstrip("/")).rstrip("/")

        params = params or {}

        # write this as a function to allow reuse in next try/except block
        def request_fn() -> "requests.models.Response":
            headers = {"Authorization": "Bearer {}".format(self.token)}
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=params)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError("Invalid method: {}".format(method))

            # Check if request returned a successful status
            response.raise_for_status()

            return response

        # If a 401 status code is returned, refresh the login token
        try:
            return request_fn()
        except requests.HTTPError as err:
            if err.response.status_code == 401:
                self.refresh_token()
                return request_fn()
            raise

    # -------------------------------------------------------------------------
    # Auth
    # -------------------------------------------------------------------------

    def login(
        self,
        email: str,
        password: str,
        account_slug: str = None,
        account_id: str = None,
    ) -> None:
        """
        Login to the server in order to gain access

        Args:
            - email (str): User's email on the platform
            - password (str): User's password on the platform
            - account_slug (str, optional): Slug that is unique to the user
            - account_id (str, optional): Specific Account ID for this user to use

        Raises:
            - ValueError if unable to login to the server (request does not return `200`)
        """

        # lazy import for performance
        import requests

        url = os.path.join(self.api_server, "login_email")
        response = requests.post(
            url,
            auth=(email, password),
            json=dict(account_id=account_id, account_slug=account_slug),
        )

        # Load the current auth token if able to login
        if not response.ok:
            raise ValueError("Could not log in.")
        self.token = response.json().get("token")
        if self.token:
            creds_path = os.path.expanduser("~/.prefect/.credentials")
            if not os.path.exists(creds_path):
                os.makedirs(creds_path)
            with open(os.path.join(creds_path, "auth_token"), "w+") as f:
                f.write(self.token)

    def logout(self) -> None:
        """
        Logs out by clearing all tokens, including deleting `~/.prefect/credentials/auth_token`
        """
        token_path = os.path.expanduser("~/.prefect/.credentials/auth_token")
        if os.path.exists(token_path):
            os.remove(token_path)
        del self.token

    def refresh_token(self) -> None:
        """
        Refresh the auth token for this user on the server. It is only valid for fifteen minutes.
        """
        # lazy import for performance
        import requests

        url = os.path.join(self.api_server, "refresh_token")
        response = requests.post(
            url, headers={"Authorization": "Bearer {}".format(self.token)}
        )
        self.token = response.json().get("token")

    def deploy(
        self, flow: "Flow", project_id: str, set_schedule_active: bool = False
    ) -> GraphQLResult:
        """
        Push a new Flow to the database.

        Args:
            - flow (Flow): the prefect Flow to insert into the database
            - project_id (str): the project ID to associate this Flow with (note
                that this can be changed later)
            - set_schedule_active (bool, optional): if `True`, will set the
                schedule to active in the database and begin scheduling runs (if the Flow has a schedule).
                Defaults to `False`

        Returns:
            - GraphQLResult: information about the newly created flow (e.g., its "id")
        """
        create_mutation = {
            "mutation($input: createFlowInput!)": {
                "createFlow(input: $input)": {"flow": {"id"}}
            }
        }
        schedule_mutation = {
            "mutation($input: setFlowScheduleIsActiveInput!)": {
                "setFlowScheduleIsActive(input: $input)": {"flow": {"id"}}
            }
        }
        res = self.graphql(
            parse_graphql(create_mutation),
            input=dict(
                projectId=project_id, serializedFlow=json.dumps(flow.serialize())
            ),
        )
        if set_schedule_active:
            scheduled_res = self.graphql(
                parse_graphql(schedule_mutation),
                input=dict(
                    flowId=res.createFlow.flow.id, isActive=True  # type: ignore
                ),
            )
        return res.createFlow.flow  # type: ignore

    def get_flow_run_info(
        self, flow_run_id: str, result_handler: ResultHandler = None
    ) -> GraphQLResult:
        """
        Retrieves version and current state information for the given flow run.

        Args:
            - flow_run_id (str): the id of the flow run to get information for
            - result_handler (ResultHandler, optional): the handler to use for
                retrieving and storing state results during execution

        Returns:
            - GraphQLResult: a `DotDict` with `"version"` and `"state"` keys
                representing the version and most recent state for this flow run

        Raises:
            - ValueError: if the GraphQL query is bad for any reason
        """
        query = {
            "query": {
                with_args("flow_run_by_pk", {"id": flow_run_id}): {
                    "parameters": True,
                    "version": True,
                    "current_state": {"serialized_state"},
                }
            }
        }
        result = self.graphql(parse_graphql(query)).flow_run_by_pk  # type: ignore
        if result is None:
            raise ValueError('Flow run id "{}" not found.'.format(flow_run_id))
        serialized_state = result.current_state.serialized_state
        state = prefect.engine.state.State.deserialize(serialized_state, result_handler)
        result.state = state
        return result

    def set_flow_run_state(
        self,
        flow_run_id: str,
        version: int,
        state: "prefect.engine.state.State",
        result_handler: ResultHandler = None,
    ) -> GraphQLResult:
        """
        Sets new state for a flow run in the database.

        Args:
            - flow_run_id (str): the id of the flow run to set state for
            - version (int): the current version of the flow run state
            - state (State): the new state for this flow run
            - result_handler (ResultHandler, optional): the handler to use for
                retrieving and storing state results during execution

        Returns:
            - GraphQLResult: a `DotDict` with a single `"version"` key for the
                new flow run version

        Raises:
            - ValueError: if the GraphQL query is bad for any reason
        """
        mutation = {
            "mutation($state: String!)": {
                with_args(
                    "setFlowRunState",
                    {
                        "input": {
                            "flowRunId": flow_run_id,
                            "version": version,
                            "state": EnumValue("$state"),
                        }
                    },
                ): {"flow_run": {"version"}}
            }
        }

        serialized_state = state.serialize(result_handler=result_handler)

        return self.graphql(  # type: ignore
            parse_graphql(mutation), state=json.dumps(serialized_state)
        ).setFlowRunState.flow_run

    def get_task_run_info(
        self,
        flow_run_id: str,
        task_id: str,
        map_index: Optional[int],
        result_handler: ResultHandler = None,
    ) -> GraphQLResult:
        """
        Retrieves version and current state information for the given task run. If this task run is not present in the database (which could
        occur if the `map_index` is non-zero), it will be created with a `Pending` state.

        Args:
            - flow_run_id (str): the id of the flow run that this task run lives in
            - task_id (str): the task id for this task run
            - map_index (int, optional): the mapping index for this task run; if
                `None`, it is assumed this task is _not_ mapped
            - result_handler (ResultHandler, optional): the handler to use for
                retrieving and storing state results during execution

        Returns:
            - GraphQLResult: a `DotDict` with `"version"`, `"state"` and `"id"` keys
                representing the version and most recent state for this task run

        Raises:
            - ValueError: if the GraphQL query is bad for any reason
        """
        mutation = {
            "mutation": {
                with_args(
                    "getOrCreateTaskRun",
                    {
                        "input": {
                            "flowRunId": flow_run_id,
                            "taskId": task_id,
                            "mapIndex": map_index,
                        }
                    },
                ): {
                    "task_run": {
                        "id": True,
                        "version": True,
                        "current_state": {"serialized_state"},
                    }
                }
            }
        }
        result = self.graphql(  # type: ignore
            parse_graphql(mutation)
        ).getOrCreateTaskRun.task_run

        serialized_state = result.current_state.serialized_state
        state = prefect.engine.state.State.deserialize(
            serialized_state, result_handler=result_handler
        )
        result.state = state
        return result

    def set_task_run_state(
        self,
        task_run_id: str,
        version: int,
        state: "prefect.engine.state.State",
        cache_for: datetime.timedelta = None,
        result_handler: ResultHandler = None,
    ) -> GraphQLResult:
        """
        Sets new state for a task run in the database.

        Args:
            - task_run_id (str): the id of the task run to set state for
            - version (int): the current version of the task run state
            - state (State): the new state for this task run
            - cache_for (timedelta, optional): how long to store the result of this task for, using the
                serializer set in config; if not provided, no caching occurs
            - result_handler (ResultHandler, optional): the handler to use for
                retrieving and storing state results during execution

        Returns:
            - GraphQLResult: a `DotDict` with a single `"version"` key for the
                new task run version

        Raises:
            - ValueError: if the GraphQL query is bad for any reason
        """
        mutation = {
            "mutation($state: String!)": {
                with_args(
                    "setTaskRunState",
                    {
                        "input": {
                            "taskRunId": task_run_id,
                            "version": version,
                            "state": EnumValue("$state"),
                        }
                    },
                ): {"task_run": {"version"}}
            }
        }

        serialized_state = state.serialize(result_handler=result_handler)

        return self.graphql(  # type: ignore
            parse_graphql(mutation), state=json.dumps(serialized_state)
        ).setTaskRunState.task_run
