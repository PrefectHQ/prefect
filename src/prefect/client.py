# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import os

import prefect
from prefect.utilities import json
from prefect.utilities.collections import to_dotdict


class AuthorizationError(Exception):
    pass


class Client:
    """
    Client for communication with Prefect Cloud

    If the arguments aren't specified the client initialization first checks the prefect
    configuration and if the server is not set there it checks the current context. The
    token will only be present in the current context.

    Args:
        - api_server (str, optional): Address for connection to the rest API
        - graphql_server (str, optional): Address for connection to the GraphQL rest API
        - token (str, optional): Authentication token server connection
    """

    def __init__(self, api_server=None, graphql_server=None, token=None):
        if api_server is None:
            api_server = prefect.config.server.get("api_server", None)

            # Check context
            if not api_server:
                api_server = prefect.context.get("api_server", None)
                if not api_server:
                    raise ValueError("Could not determine API server.")
        self._api_server = api_server

        if graphql_server is None:
            graphql_server = prefect.config.server.get("graphql_server", None)

            # Check context
            if not graphql_server:
                graphql_server = prefect.context.get("graphql_server", None)

                # Default to the API server
                if not graphql_server:
                    graphql_server = api_server
        self._graphql_server = graphql_server

        # Check context
        if token is None:
            token = prefect.context.get("token", None)
        self._token = token

        self.projects = Projects(client=self)
        self.flows = Flows(client=self)
        self.flow_runs = FlowRuns(client=self)
        self.task_runs = TaskRuns(client=self)

    # -------------------------------------------------------------------------
    # Utilities

    def _get(self, path, *, _json=True, _server=None, **params) -> dict:
        """
        Convenience function for calling the Prefect API with token auth and GET request

        Args:
            - path (str): the path of the API url. For example, to GET
                http://prefect-server/v1/auth/login, path would be 'auth/login'.
            - params (dict): GET parameters

        Returns:
            - dict: Dictionary representation of the request made
        """
        response = self._request(method="GET", path=path, params=params, server=_server)
        if _json:
            if response.text:
                response = response.json()
            else:
                response = {}
        return response

    def _post(self, path, *, _json=True, _server=None, **params) -> dict:
        """
        Convenience function for calling the Prefect API with token auth and POST request

        Args:
            - path (str): the path of the API url. For example, to POST
                http://prefect-server/v1/auth/login, path would be 'auth/login'.
            - params (dict): POST parameters

        Returns:
            - dict: Dictionary representation of the request made
        """
        response = self._request(
            method="POST", path=path, params=params, server=_server
        )
        if _json:
            if response.text:
                return response.json()
            else:
                response = {}
        else:
            return response

    def _delete(self, path, *, _server=None, _json=True) -> dict:
        """
        Convenience function for calling the Prefect API with token auth and DELETE request

        Args:
            - path (str): the path of the API url. For example, to DELETE
                http://prefect-server/v1/auth/login, path would be 'auth/login'

        Returns:
            - dict: Dictionary representation of the request made
        """
        response = self._request(method="DELETE", path=path, server=_server)
        if _json:
            if response.text:
                response = response.json()
            else:
                response = {}
        return response

    def graphql(self, query, **variables) -> dict:
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
        result = self._post(
            path="",
            query=query,
            variables=json.dumps(variables),
            _server=self._graphql_server,
        )

        if "errors" in result:
            raise ValueError(result["errors"])
        else:
            return to_dotdict(result).data

    def _request(self, method, path, params=None, server=None):
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
            server = self._api_server

        if self._token is None:
            raise ValueError("Call Client.login() to set the client token.")

        url = os.path.join(server, path.lstrip("/")).rstrip("/")

        params = params or {}

        # write this as a function to allow reuse in next try/except block
        def request_fn():
            headers = {"Authorization": "Bearer " + self._token}
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

    def login(self, email, password, account_slug=None, account_id=None) -> dict:
        """
        Login to the server in order to gain access

        Args:
            - email (str): User's email on the platform
            - password (str): User's password on the platform
            - account_slug (str, optional): Slug that is unique to the user
            - account_id (str, optional): Specific Account ID for this user to use

        Returns:
            - dict: Request with the list of accounts linked to this email/password combination
                Will not return anything if a single account is logged in to

        Raises:
            - ValueError if unable to login to the server (request does not return `200`)
        """

        # lazy import for performance
        import requests

        url = os.path.join(self._api_server, "login")
        response = requests.post(
            url,
            auth=(email, password),
            json=dict(account_id=account_id, account_slug=account_slug),
        )

        # Load the current auth token if able to login
        if not response.ok:
            raise ValueError("Could not log in.")
        self._token = response.json().get("token")

        # Functionality not yet ready
        # User must specify a single account to access
        # if not (account_id or account_slug):
        #     print("No account provided; returning available accounts.")
        #     # Will need to be a graphql query
        #     accounts = self._get("auth/accounts")
        #     return accounts

    def refresh_token(self) -> None:
        """
        Refresh the auth token for this user on the server. It is only valid for fifteen minutes.
        """
        # lazy import for performance
        import requests

        url = os.path.join(self._api_server, "auth/refresh")
        response = requests.post(
            url, headers={"Authorization": "Bearer " + self._token}
        )
        self._token = response.json().get("token")


class ClientModule:

    _path = ""

    def __init__(self, client, name=None):
        if name is None:
            name = type(self).__name__
        self._name = name
        self._client = client

    def __repr__(self):
        return "<Client Module: {name}>".format(name=self._name)

    def _get(self, path, **params):
        path = path.lstrip("/")
        return self._client._get(os.path.join(self._path, path), **params)

    def _post(self, path, **data):
        path = path.lstrip("/")
        return self._client._post(os.path.join(self._path, path), **data)

    def _delete(self, path, **params):
        path = path.lstrip("/")
        return self._client._delete(os.path.join(self._path, path), **params)

    def _graphql(self, query, **variables):
        return self._client.graphql(query=query, **variables)


# -------------------------------------------------------------------------
# Projects


class Projects(ClientModule):
    def create(self, name) -> dict:
        """
        Create a new project for this account

        Args:
            - name (str): The name for this new project

        Returns:
            - dict: Data returned from the GraphQL query
        """
        return self._graphql(
            """
            mutation($input: CreateProjectInput!) {
                createProject(input: $input) {
                    project {id}
                }
            }
            """,
            input=dict(name=name),
        )


# -------------------------------------------------------------------------
# Flows


class Flows(ClientModule):
    def create(self, serialized_flow) -> dict:
        """
        Create a new flow on the server

        Args:
            - serialized_flow (dict): A json serialized version of a flow

        Returns:
            - dict: Data returned from the GraphQL mutation
        """
        return self._graphql(
            """
            mutation($input: CreateFlowInput!) {
                createFlow(input: $input) {
                    flow {id}
                }
            }
            """,
            input=dict(serializedFlow=json.dumps(serialized_flow)),
        )

    def query_environment_metadata(self, project_name, flow_name, flow_version) -> dict:
        """
        Retrieve a flow's environment metadata

        Args:
            - project_name (str): Name of the project that the flow belongs to
            - flow_name (str): Name of the flow
            - flow_version (str): Version of the flow

        Returns:
            - dict: Data returned from the GraphQL query
        """
        return self._graphql(
            """
            query($name: String!, $project_name: String!, $version: String!) {
                flows(where: {
                    name: $name,
                    version: $version,
                    project: {
                        name: $project_name
                    }
                }) {
                    id,
                    environment
                }
            }
            """,
            name=flow_name,
            version=flow_version,
            project_name=project_name,
        )


# -------------------------------------------------------------------------
# FlowRuns


class FlowRuns(ClientModule):
    def create(self, flow_id, parameters) -> dict:
        """
        Create a flow run

        Args:
            - flow_id (str): A unique flow identifier
            - parameters (dict): Paramaters set on a flow

        Returns:
            - dict: Data returned from the GraphQL mutation
        """
        return self._graphql(
            """
            mutation($input: CreateFlowRunInput!) {
                createFlowRun(input: $input) {
                    flow_run {id}
                }
            }
            """,
            input=dict(flowId=flow_id, parameters=json.dumps(parameters)),
        )

    def set_state(self, flow_run_id, state) -> dict:
        """
        Set a flow run state

        Args:
            - flow_run_id (str): A unique flow_run identifier
            - state (State): A prefect state object

        Returns:
            - dict: Data returned from the GraphQL query
        """
        return self._graphql(
            """
            mutation($input: SetFlowRunStateInput!) {
                setFlowRunState(input: $input) {
                    flow_state {state}
                }
            }
            """,
            input=dict(flowRunId=flow_run_id, state=json.dumps(state)),
        )


# -------------------------------------------------------------------------
# TaskRuns


class TaskRuns(ClientModule):
    def set_state(self, task_run_id, state) -> dict:
        """
        Set a task run state

        Args:
            - task_run_id (str): A unique task run identifier
            - state (State): A prefect state object

        Returns:
            - dict: Data returned from the GraphQL query
        """
        return self._graphql(
            """
            mutation($input: SetTaskRunStateInput!) {
                setTaskRunState(input: $input) {
                    task_state {state}
                }
            }
            """,
            input=dict(taskRunId=task_run_id, state=json.dumps(state)),
        )

    def query(self, flow_run_id, task_id) -> dict:
        """
        Retrieve a flow's environment metadata

        Args:
            - flow_run_id (str): Unique identifier of a flow run this task run belongs to
            - task_id (str): Unique identifier of this task

        Returns:
            - dict: Data returned from the GraphQL query
        """
        return self._graphql(
            """
            query($flow_run_id: ID!, $task_id: ID!) {
                taskRuns(where: {
                    flow_run_id: $flow_run_id,
                    task_id: $task_id,
                }) {
                    id
                }
            }
            """,
            flow_run_id=flow_run_id,
            task_id=task_id,
        )


# -------------------------------------------------------------------------
# Execution


class RunFlow(ClientModule):
    def run_flow(self, image_name, image_tag, flow_id, flow_run_id=None) -> dict:
        """
        Run a flow

        Args:
            - image_name (str): The image container name the flow is in
            - image_tag (str): The tag of the flow's image
            - flow_id (str): The ID of the flow to be run
            - flow_run_id (str, optional): The flow run to communicate to

        Returns:
            - dict: Data returned from the GraphQL query
        """
        return self._graphql(
            """
            mutation($input: RunFlowInput!) {
                runFlow(input: $input) {
                    status
                }
            }
            """,
            input=dict(
                imageName=image_name,
                imageTag=image_tag,
                flowId=flow_id,
                flowRunId=flow_run_id,
            ),
        )
