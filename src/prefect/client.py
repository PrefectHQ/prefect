# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import datetime
import os
from typing import Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    import requests

import prefect
from prefect.utilities import json
from prefect.utilities.collections import to_dotdict


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
        - token (str, optional): Authentication token server connection
    """

    def __init__(self, token: str = None) -> None:
        api_server = prefect.config.cloud.get("api_server", None)

        if not api_server:
            raise ValueError("Could not determine API server.")

        self.api_server = api_server

        graphql_server = prefect.config.cloud.get("graphql_server", None)

        # Default to the API server
        if not graphql_server:
            graphql_server = api_server

        self.graphql_server = graphql_server

        if token is None:
            token = prefect.config.cloud.get("auth_token", None)

            if token is None:
                if os.path.exists("~/.prefect/.credentials/auth_token"):
                    with open("~/.prefect/.credentials/auth_token", "r") as f:
                        token = f.read()

        self.token = token

        self.projects = Projects(client=self)
        self.flows = Flows(client=self)
        self.flow_runs = FlowRuns(client=self)
        self.task_runs = TaskRuns(client=self)

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
            return to_dotdict(result).data  # type: ignore

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
        email: str = None,
        password: str = None,
        account_slug: str = None,
        account_id: str = None,
    ) -> None:
        """
        Login to the server in order to gain access

        Args:
            - email (str): User's email on the platform; if not provided, pulled
                from config
            - password (str): User's password on the platform; if not provided,
                pulled from config
            - account_slug (str, optional): Slug that is unique to the user
            - account_id (str, optional): Specific Account ID for this user to use

        Raises:
            - ValueError if unable to login to the server (request does not return `200`)
        """

        # lazy import for performance
        import requests

        email = email or prefect.config.cloud.email
        password = password or prefect.config.cloud.password

        url = os.path.join(self.api_server, "login")
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
            if not os.path.exists("~/.prefect/.credentials"):
                os.makedirs("~/.prefect/.credentials")
            with open("~/.prefect/.credentials/auth_token", "w+") as f:
                f.write(self.token)

    def logout(self) -> None:
        """
        Logs out by clearing all tokens, including deleting `~/.prefect/credentials/auth_token`
        """
        os.remove("~/.prefect/.credentials/auth_token")
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


class ClientModule:

    _path = ""

    def __init__(self, client: Client, name: str = None) -> None:
        if name is None:
            name = type(self).__name__
        self._name = name
        self._client = client

    def __repr__(self) -> str:
        return "<Client Module: {name}>".format(name=self._name)

    def post(self, path: str, **data: BuiltIn) -> dict:
        path = path.lstrip("/")
        return self._client.post(os.path.join(self._path, path), **data)  # type: ignore

    def _graphql(self, query: str, **variables: BuiltIn) -> dict:
        return self._client.graphql(query=query, **variables)  # type: ignore


# -------------------------------------------------------------------------
# Projects


class Projects(ClientModule):
    def create(self, name: str) -> dict:
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
    def create(self, serialized_flow: dict) -> dict:
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

    def query(self, project_name: str, flow_name: str, flow_version: str) -> dict:
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
                    id
                }
            }
            """,
            name=flow_name,
            version=flow_version,
            project_name=project_name,
        )

    def delete(self, flow_id: str) -> dict:
        """
        Delete a flow on the server

        Args:
            - flow_id (str): The ID of a flow in the server

        Returns:
            - dict: Data returned from the GraphQL mutation
        """
        return self._graphql(
            """
            mutation($input: DeleteFlowInput!) {
                deleteFlow(input: $input) {
                    flowId
                }
            }
            """,
            input=dict(flowId=flow_id),
        )


# -------------------------------------------------------------------------
# FlowRuns


class FlowRuns(ClientModule):
    def create(
        self, flow_id: str, parameters: dict, start_time: datetime.datetime = None
    ) -> dict:
        """
        Create a flow run

        Args:
            - flow_id (str): A unique flow identifier
            - parameters (dict): Paramater dictionary to provide for the flow run
            - start_time (datetime, optional): An optional start time for the flow run

        Returns:
            - dict: Data returned from the GraphQL mutation
        """
        return self._graphql(
            """
            mutation($input: CreateFlowRunInput!) {
                createFlowRun(input: $input) {
                    flowRun {id}
                }
            }
            """,
            input=dict(flowId=flow_id, parameters=parameters, startTime=start_time),
        )

    def set_state(self, flow_run_id: str, state: "prefect.engine.state.State") -> dict:
        """
        Set a flow run state

        Args:
            - flow_run_id (str): A unique flow_run identifier
            - state (State): A prefect state object

        Returns:
            - dict: Data returned from the GraphQL query
        """
        state.result = None  # Temporary until we have cloud pickling
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

    def query(self, flow_run_id: str) -> dict:
        """
        Retrieve a flow's environment metadata

        Args:
            - flow_run_id (str): Unique identifier of a flow run this task run belongs to

        Returns:
            - dict: Data returned from the GraphQL query
        """
        return self._graphql(
            """
            query($flow_run_id: ID!) {
                flowRuns(where: {
                    id: $flow_run_id
                }) {
                    id,
                    parameters
                }
            }
            """,
            flow_run_id=flow_run_id,
        )


# -------------------------------------------------------------------------
# TaskRuns


class TaskRuns(ClientModule):
    def set_state(self, task_run_id: str, state: "prefect.engine.state.State") -> dict:
        """
        Set a task run state

        Args:
            - task_run_id (str): A unique task run identifier
            - state (State): A prefect state object

        Returns:
            - dict: Data returned from the GraphQL query
        """
        state.result = None  # Temporary until we have cloud pickling
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

    def query(self, flow_run_id: str, task_id: str) -> dict:
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
    def run_flow(self, flow_run_id: str) -> dict:
        """
        Run a flow

        Args:
            - flow_run_id (str): The flow run to communicate to

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
            input=dict(flowRunId=flow_run_id),
        )


class Secret(json.Serializable):
    """
    A Secret is a serializable object used to represent a secret key & value.

    Args:
        - name (str): The name of the secret

    The value of the `Secret` is not set upon initialization and instead is set
    either in `prefect.context` or on the server, with behavior dependent on the value
    of the `use_local_secrets` flag in your Prefect configuration file.
    """

    _json_codec = json.ObjectAttributesCodec

    def __init__(self, name: str) -> None:
        self.name = name

    def get(self) -> Optional[str]:
        """
        Retrieve the secret value.

        If not found, returns `None`.

        Raises:
            - ValueError: if `use_local_secrets=False` and the Client fails to retrieve your secret
        """
        if prefect.config.cloud.use_local_secrets is True:
            secrets = prefect.context.get("_secrets", {})
            return secrets.get(self.name)
        else:
            client = Client()
            return client.graphql(  # type: ignore
                """
                query($key: String!) {
                    secret(key: $key) {
                        value
                    }
                }""",
                key=self.name,
            ).secret.value


# -------------------------------------------------------------------------
# States


class States(ClientModule):
    def set_flow_run_from_serialized_state(
        self, flow_run_id: str, version: int, state: "prefect.engine.state.State"
    ) -> dict:
        """
        Set a flow run state

        Args:
            - flow_run_id (str): A unique flow_run identifier
            - version (int): Previous flow run version
            - state (State): A serialized prefect state object

        Returns:
            - dict: Data returned from the GraphQL query
        """
        return self._graphql(
            """
            mutation($input: SetFlowRunFromSerializedStateInput!) {
                setFlowRunStateFromSerialized(input: $input) {
                    state {state}
                }
            }
            """,
            input=dict(
                flowRunId=flow_run_id,
                version=version,
                serializedState=json.dumps(state),
            ),
        )

    def query_flow_run_version(self, flow_run_id: str) -> dict:
        """
        Retrieve a flow run's version

        Args:
            - flow_run_id (str): Unique identifier of a flow run

        Returns:
            - dict: Data returned from the GraphQL query
        """
        return self._graphql(
            """
            query($flow_run_id: ID!) {
                flowRuns(where: {
                    id: $flow_run_id
                }) {
                    version
                }
            }
            """,
            flow_run_id=flow_run_id,
        )

    def set_task_run_from_serialized_state(
        self, task_run_id: str, version: int, state: "prefect.engine.state.State"
    ) -> dict:
        """
        Set a task run state

        Args:
            - task_run_id (str): A unique task_run identifier
            - version (int): Previous flow run version
            - state (State): A serialized prefect state object

        Returns:
            - dict: Data returned from the GraphQL query
        """
        return self._graphql(
            """
            mutation($input: SetTaskRunFromSerializedStateInput!) {
                setTaskRunStateFromSerialized(input: $input) {
                    state {state}
                }
            }
            """,
            input=dict(
                taskRunId=task_run_id,
                version=version,
                serializedState=json.dumps(state),
            ),
        )

    def query_task_run_id_and_version(
        self, flow_run_id: str, task_id: Optional[str]
    ) -> dict:
        """
        Retrieve a task run's id and version

        Args:
            - flow_run_id (str): Unique identifier of a flow run
            - task_id (str): ID of the task

        Returns:
            - dict: Data returned from the GraphQL query
        """
        return self._graphql(
            """
            query($flow_run_id: ID!, $task_id: ID!) {
                taskRuns(where: {
                    flow_run_id: $flow_run_id,
                    task_id: $task_id
                }) {
                    id,
                    version
                }
            }
            """,
            flow_run_id=flow_run_id,
            task_id=task_id or "",
        )
