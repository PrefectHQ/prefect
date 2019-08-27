import base64
import datetime
import json
import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional, Union

import pendulum
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

import prefect
from prefect.utilities.exceptions import AuthorizationError, ClientError
from prefect.utilities.graphql import (
    EnumValue,
    GraphQLResult,
    as_nested_dict,
    compress,
    parse_graphql,
    with_args,
)

if TYPE_CHECKING:
    from prefect.core import Flow
JSONLike = Union[bool, dict, list, str, int, float, None]

# type definitions for GraphQL results

TaskRunInfoResult = NamedTuple(
    "TaskRunInfoResult",
    [
        ("id", str),
        ("task_id", str),
        ("task_slug", str),
        ("version", int),
        ("state", "prefect.engine.state.State"),
    ],
)

FlowRunInfoResult = NamedTuple(
    "FlowRunInfoResult",
    [
        ("id", str),
        ("flow_id", str),
        ("parameters", Dict[str, Any]),
        ("context", Dict[str, Any]),
        ("version", int),
        ("scheduled_start_time", datetime.datetime),
        ("state", "prefect.engine.state.State"),
        ("task_runs", List[TaskRunInfoResult]),
    ],
)


class Client:
    """
    Client for communication with Prefect Cloud

    If the arguments aren't specified the client initialization first checks the prefect
    configuration and if the server is not set there it checks the current context. The
    token will only be present in the current context.

    Args:
        - graphql_server (str, optional): the URL to send all GraphQL requests
            to; if not provided, will be pulled from `cloud.graphql` config var
        - token (str, optional): a Prefect Cloud auth token for communication; if not
            provided, will be pulled from `cloud.auth_token` config var
    """

    def __init__(self, graphql_server: str = None, token: str = None):

        if not graphql_server:
            graphql_server = prefect.config.cloud.get("graphql")
        self.graphql_server = graphql_server

        token = token or prefect.config.cloud.get("auth_token", None)

        self.token_is_local = False
        if token is None:
            if os.path.exists(self.local_token_path):
                with open(self.local_token_path, "r") as f:
                    token = f.read() or None
                    self.token_is_local = True

        self.token = token

    @property
    def local_token_path(self) -> str:
        """
        Returns the local token path corresponding to the provided graphql_server
        """
        graphql_server = (self.graphql_server or "").replace("/", "_")
        return os.path.expanduser("~/.prefect/tokens/{}".format(graphql_server))

    # -------------------------------------------------------------------------
    # Utilities

    def get(
        self,
        path: str,
        server: str = None,
        headers: dict = None,
        params: Dict[str, JSONLike] = None,
    ) -> dict:
        """
        Convenience function for calling the Prefect API with token auth and GET request

        Args:
            - path (str): the path of the API url. For example, to GET
                http://prefect-server/v1/auth/login, path would be 'auth/login'.
            - server (str, optional): the server to send the GET request to;
                defaults to `self.graphql_server`
            - headers (dict, optional): Headers to pass with the request
            - params (dict): GET parameters

        Returns:
            - dict: Dictionary representation of the request made
        """
        response = self._request(
            method="GET", path=path, params=params, server=server, headers=headers
        )
        if response.text:
            return response.json()
        else:
            return {}

    def post(
        self,
        path: str,
        server: str = None,
        headers: dict = None,
        params: Dict[str, JSONLike] = None,
    ) -> dict:
        """
        Convenience function for calling the Prefect API with token auth and POST request

        Args:
            - path (str): the path of the API url. For example, to POST
                http://prefect-server/v1/auth/login, path would be 'auth/login'.
            - server (str, optional): the server to send the POST request to;
                defaults to `self.graphql_server`
            - headers(dict): headers to pass with the request
            - params (dict): POST parameters

        Returns:
            - dict: Dictionary representation of the request made
        """
        response = self._request(
            method="POST", path=path, params=params, server=server, headers=headers
        )
        if response.text:
            return response.json()
        else:
            return {}

    def graphql(
        self,
        query: Any,
        raise_on_error: bool = True,
        headers: Dict[str, str] = None,
        variables: Dict[str, JSONLike] = None,
    ) -> GraphQLResult:
        """
        Convenience function for running queries against the Prefect GraphQL API

        Args:
            - query (Any): A representation of a graphql query to be executed. It will be
                parsed by prefect.utilities.graphql.parse_graphql().
            - raise_on_error (bool): if True, a `ClientError` will be raised if the GraphQL
                returns any `errors`.
            - headers (dict): any additional headers that should be passed as part of the
                request
            - variables (dict): Variables to be filled into a query with the key being
                equivalent to the variables that are accepted by the query

        Returns:
            - dict: Data returned from the GraphQL query

        Raises:
            - ClientError if there are errors raised by the GraphQL mutation
        """
        result = self.post(
            path="",
            server=self.graphql_server,
            headers=headers,
            params=dict(query=parse_graphql(query), variables=json.dumps(variables)),
        )

        if raise_on_error and "errors" in result:
            raise ClientError(result["errors"])
        else:
            return as_nested_dict(result, GraphQLResult)  # type: ignore

    def _request(
        self,
        method: str,
        path: str,
        params: Dict[str, JSONLike] = None,
        server: str = None,
        headers: dict = None,
    ) -> "requests.models.Response":
        """
        Runs any specified request (GET, POST, DELETE) against the server

        Args:
            - method (str): The type of request to be made (GET, POST, DELETE)
            - path (str): Path of the API URL
            - params (dict, optional): Parameters used for the request
            - server (str, optional): The server to make requests against, base API
                server is used if not specified
            - headers (dict, optional): Headers to pass with the request

        Returns:
            - requests.models.Response: The response returned from the request

        Raises:
            - ClientError: if the client token is not in the context (due to not being logged in)
            - ValueError: if a method is specified outside of the accepted GET, POST, DELETE
            - requests.HTTPError: if a status code is returned that is not `200` or `401`
        """
        if server is None:
            server = self.graphql_server
        assert isinstance(server, str)  # mypy assert

        if self.token is None:
            raise AuthorizationError("No token found; call Client.login() to set one.")

        url = os.path.join(server, path.lstrip("/")).rstrip("/")

        params = params or {}

        headers = headers or {}
        headers.update({"Authorization": "Bearer {}".format(self.token)})
        session = requests.Session()
        retries = Retry(
            total=6,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            method_whitelist=["DELETE", "GET", "POST"],
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        if method == "GET":
            response = session.get(url, headers=headers, params=params)
        elif method == "POST":
            response = session.post(url, headers=headers, json=params)
        elif method == "DELETE":
            response = session.delete(url, headers=headers)
        else:
            raise ValueError("Invalid method: {}".format(method))

        # Check if request returned a successful status
        response.raise_for_status()

        return response

    # -------------------------------------------------------------------------
    # Auth
    # -------------------------------------------------------------------------

    def login(self, api_token: str) -> None:
        """
        Logs in to Prefect Cloud with an API token. The token is written to local storage
        so it persists across Prefect sessions.

        Args:
            - api_token (str): a Prefect Cloud API token

        Raises:
            - AuthorizationError if unable to login to the server (request does not return `200`)
        """
        if not os.path.exists(os.path.dirname(self.local_token_path)):
            os.makedirs(os.path.dirname(self.local_token_path))
        with open(self.local_token_path, "w+") as f:
            f.write(api_token)
        self.token = api_token
        self.token_is_local = True

    def logout(self) -> None:
        """
        Deletes the token from this client, and removes it from local storage.
        """
        self.token = None
        if self.token_is_local:
            if os.path.exists(self.local_token_path):
                os.remove(self.local_token_path)
            self.token_is_local = False

    def deploy(
        self,
        flow: "Flow",
        project_name: str,
        build: bool = True,
        set_schedule_active: bool = True,
        compressed: bool = True,
    ) -> str:
        """
        Push a new flow to Prefect Cloud

        Args:
            - flow (Flow): a flow to deploy
            - project_name (str): the project that should contain this flow.
            - build (bool, optional): if `True`, the flow's environment is built
                prior to serialization; defaults to `True`
            - set_schedule_active (bool, optional): if `False`, will set the
                schedule to inactive in the database to prevent auto-scheduling runs (if the Flow has a schedule).
                Defaults to `True`. This can be changed later.
            - compressed (bool, optional): if `True`, the serialized flow will be; defaults to `True`
                compressed

        Returns:
            - str: the ID of the newly-deployed flow

        Raises:
            - ClientError: if the deploy failed
        """
        required_parameters = {p for p in flow.parameters() if p.required}
        if flow.schedule is not None and required_parameters:
            raise ClientError(
                "Flows with required parameters can not be scheduled automatically."
            )
        if compressed:
            create_mutation = {
                "mutation($input: createFlowFromCompressedStringInput!)": {
                    "createFlowFromCompressedString(input: $input)": {"id"}
                }
            }
        else:
            create_mutation = {
                "mutation($input: createFlowInput!)": {
                    "createFlow(input: $input)": {"id"}
                }
            }

        query_project = {
            "query": {
                with_args("project", {"where": {"name": {"_eq": project_name}}}): {
                    "id": True
                }
            }
        }

        project = self.graphql(query_project).data.project  # type: ignore

        if not project:
            raise ValueError(
                "Project {} not found. Run `client.create_project({})` to create it.".format(
                    project_name, project_name
                )
            )

        serialized_flow = flow.serialize(build=build)  # type: Any

        # verify that the serialized flow can be deserialized
        try:
            prefect.serialization.flow.FlowSchema().load(serialized_flow)
        except Exception as exc:
            raise ValueError(
                "Flow could not be deserialized successfully. Error was: {}".format(
                    repr(exc)
                )
            )

        if compressed:
            serialized_flow = compress(serialized_flow)
        res = self.graphql(
            create_mutation,
            variables=dict(
                input=dict(
                    projectId=project[0].id,
                    serializedFlow=serialized_flow,
                    setScheduleActive=set_schedule_active,
                )
            ),
        )  # type: Any

        flow_id = (
            res.data.createFlowFromCompressedString.id
            if compressed
            else res.data.createFlow.id
        )
        return flow_id

    def create_project(self, project_name: str, project_description: str = None) -> str:
        """
        Create a new Project

        Args:
            - project_name (str): the project that should contain this flow
            - project_description (str, optional): the project description

        Returns:
            - str: the ID of the newly-created project

        Raises:
            - ClientError: if the project creation failed
        """
        project_mutation = {
            "mutation($input: createProjectInput!)": {
                "createProject(input: $input)": {"id"}
            }
        }

        res = self.graphql(
            project_mutation,
            variables=dict(
                input=dict(name=project_name, description=project_description)
            ),
        )  # type: Any

        return res.data.createProject.id

    def create_flow_run(
        self,
        flow_id: str,
        context: dict = None,
        parameters: dict = None,
        scheduled_start_time: datetime.datetime = None,
        idempotency_key: str = None,
    ) -> str:
        """
        Create a new flow run for the given flow id.  If `start_time` is not provided, the flow run will be scheduled to start immediately.

        Args:
            - flow_id (str): the id of the Flow you wish to schedule
            - context (dict, optional): the run context
            - parameters (dict, optional): a dictionary of parameter values to pass to the flow run
            - scheduled_start_time (datetime, optional): the time to schedule the execution for; if not provided, defaults to now
            - idempotency_key (str, optional): an idempotency key; if provided, this run will be cached for 24
                hours. Any subsequent attempts to create a run with the same idempotency key
                will return the ID of the originally created run (no new run will be created after the first).
                An error will be raised if parameters or context are provided and don't match the original.
                Each subsequent request will reset the TTL for 24 hours.

        Returns:
            - str: the ID of the newly-created flow run

        Raises:
            - ClientError: if the GraphQL query is bad for any reason
        """
        create_mutation = {
            "mutation($input: createFlowRunInput!)": {
                "createFlowRun(input: $input)": {"flow_run": "id"}
            }
        }
        inputs = dict(flowId=flow_id)
        if parameters is not None:
            inputs.update(parameters=parameters)  # type: ignore
        if context is not None:
            inputs.update(context=context)  # type: ignore
        if idempotency_key is not None:
            inputs.update(idempotencyKey=idempotency_key)  # type: ignore
        if scheduled_start_time is not None:
            inputs.update(
                scheduledStartTime=scheduled_start_time.isoformat()
            )  # type: ignore
        res = self.graphql(create_mutation, variables=dict(input=inputs))
        return res.data.createFlowRun.flow_run.id  # type: ignore

    def get_flow_run_info(self, flow_run_id: str) -> FlowRunInfoResult:
        """
        Retrieves version and current state information for the given flow run.

        Args:
            - flow_run_id (str): the id of the flow run to get information for

        Returns:
            - GraphQLResult: a `DotDict` representing information about the flow run

        Raises:
            - ClientError: if the GraphQL mutation is bad for any reason
        """
        query = {
            "query": {
                with_args("flow_run_by_pk", {"id": flow_run_id}): {
                    "id": True,
                    "flow_id": True,
                    "parameters": True,
                    "context": True,
                    "version": True,
                    "scheduled_start_time": True,
                    "serialized_state": True,
                    # load all task runs except dynamic task runs
                    with_args("task_runs", {"where": {"map_index": {"_eq": -1}}}): {
                        "id": True,
                        "task": {"id": True, "slug": True},
                        "version": True,
                        "serialized_state": True,
                    },
                }
            }
        }
        result = self.graphql(query).data.flow_run_by_pk  # type: ignore
        if result is None:
            raise ClientError('Flow run ID not found: "{}"'.format(flow_run_id))

        # convert scheduled_start_time from string to datetime
        result.scheduled_start_time = pendulum.parse(result.scheduled_start_time)

        # create "state" attribute from serialized_state
        result.state = prefect.engine.state.State.deserialize(
            result.pop("serialized_state")
        )

        # reformat task_runs
        task_runs = []
        for tr in result.task_runs:
            tr.state = prefect.engine.state.State.deserialize(
                tr.pop("serialized_state")
            )
            task_info = tr.pop("task")
            tr.task_id = task_info["id"]
            tr.task_slug = task_info["slug"]
            task_runs.append(TaskRunInfoResult(**tr))

        result.task_runs = task_runs
        result.context = (
            result.context.to_dict() if result.context is not None else None
        )
        result.parameters = (
            result.parameters.to_dict() if result.parameters is not None else None
        )
        return FlowRunInfoResult(**result)

    def update_flow_run_heartbeat(self, flow_run_id: str) -> None:
        """
        Convenience method for heartbeating a flow run.

        Does NOT raise an error if the update fails.

        Args:
            - flow_run_id (str): the flow run ID to heartbeat

        """
        mutation = {
            "mutation": {
                with_args(
                    "updateFlowRunHeartbeat", {"input": {"flowRunId": flow_run_id}}
                ): {"success"}
            }
        }
        self.graphql(mutation, raise_on_error=False)

    def update_task_run_heartbeat(self, task_run_id: str) -> None:
        """
        Convenience method for heartbeating a task run.

        Does NOT raise an error if the update fails.

        Args:
            - task_run_id (str): the task run ID to heartbeat

        """
        mutation = {
            "mutation": {
                with_args(
                    "updateTaskRunHeartbeat", {"input": {"taskRunId": task_run_id}}
                ): {"success"}
            }
        }
        self.graphql(mutation, raise_on_error=False)

    def set_flow_run_state(
        self, flow_run_id: str, version: int, state: "prefect.engine.state.State"
    ) -> None:
        """
        Sets new state for a flow run in the database.

        Args:
            - flow_run_id (str): the id of the flow run to set state for
            - version (int): the current version of the flow run state
            - state (State): the new state for this flow run

        Raises:
            - ClientError: if the GraphQL mutation is bad for any reason
        """
        mutation = {
            "mutation($state: JSON!)": {
                with_args(
                    "setFlowRunState",
                    {
                        "input": {
                            "flowRunId": flow_run_id,
                            "version": version,
                            "state": EnumValue("$state"),
                        }
                    },
                ): {"id"}
            }
        }

        serialized_state = state.serialize()

        self.graphql(mutation, variables=dict(state=serialized_state))  # type: Any

    def get_latest_cached_states(
        self, task_id: str, cache_key: Optional[str], created_after: datetime.datetime
    ) -> List["prefect.engine.state.State"]:
        """
        Pulls all Cached states for the given task that were created after the provided date.

        Args:
            - task_id (str): the task id for this task run
            - cache_key (Optional[str]): the cache key for this Task's cache; if `None`, the task id alone will be used
            - created_after (datetime.datetime): the earliest date the state should have been created at

        Returns:
            - List[State]: a list of Cached states created after the given date
        """
        where_clause = {
            "where": {
                "state": {"_eq": "Cached"},
                "_or": [
                    {"cache_key": {"_eq": cache_key}},
                    {"task_id": {"_eq": task_id}},
                ],
                "state_timestamp": {"_gte": created_after.isoformat()},
            },
            "order_by": {"state_timestamp": EnumValue("desc")},
        }
        query = {"query": {with_args("task_run", where_clause): "serialized_state"}}
        result = self.graphql(query)  # type: Any
        deserializer = prefect.engine.state.State.deserialize
        valid_states = [
            deserializer(res.serialized_state) for res in result.data.task_run
        ]
        return valid_states

    def get_task_run_info(
        self, flow_run_id: str, task_id: str, map_index: Optional[int] = None
    ) -> TaskRunInfoResult:
        """
        Retrieves version and current state information for the given task run.

        Args:
            - flow_run_id (str): the id of the flow run that this task run lives in
            - task_id (str): the task id for this task run
            - map_index (int, optional): the mapping index for this task run; if
                `None`, it is assumed this task is _not_ mapped

        Returns:
            - NamedTuple: a tuple containing `id, task_id, version, state`

        Raises:
            - ClientError: if the GraphQL mutation is bad for any reason
        """

        mutation = {
            "mutation": {
                with_args(
                    "getOrCreateTaskRun",
                    {
                        "input": {
                            "flowRunId": flow_run_id,
                            "taskId": task_id,
                            "mapIndex": -1 if map_index is None else map_index,
                        }
                    },
                ): {
                    "task_run": {
                        "id": True,
                        "version": True,
                        "serialized_state": True,
                        "task": {"slug": True},
                    }
                }
            }
        }
        result = self.graphql(mutation)  # type: Any
        task_run = result.data.getOrCreateTaskRun.task_run

        state = prefect.engine.state.State.deserialize(task_run.serialized_state)
        return TaskRunInfoResult(
            id=task_run.id,
            task_id=task_id,
            task_slug=task_run.task.slug,
            version=task_run.version,
            state=state,
        )

    def set_task_run_state(
        self,
        task_run_id: str,
        version: int,
        state: "prefect.engine.state.State",
        cache_for: datetime.timedelta = None,
    ) -> None:
        """
        Sets new state for a task run.

        Args:
            - task_run_id (str): the id of the task run to set state for
            - version (int): the current version of the task run state
            - state (State): the new state for this task run
            - cache_for (timedelta, optional): how long to store the result of this task for, using the
                serializer set in config; if not provided, no caching occurs

        Raises:
            - ClientError: if the GraphQL mutation is bad for any reason
        """
        mutation = {
            "mutation($state: JSON!)": {
                with_args(
                    "setTaskRunState",
                    {
                        "input": {
                            "taskRunId": task_run_id,
                            "version": version,
                            "state": EnumValue("$state"),
                        }
                    },
                ): {"id"}
            }
        }

        serialized_state = state.serialize()

        self.graphql(mutation, variables=dict(state=serialized_state))  # type: Any

    def set_secret(self, name: str, value: Any) -> None:
        """
        Set a secret with the given name and value.

        Args:
            - name (str): the name of the secret; used for retrieving the secret
                during task runs
            - value (Any): the value of the secret

        Raises:
            - ClientError: if the GraphQL mutation is bad for any reason
            - ValueError: if the secret-setting was unsuccessful
        """
        mutation = {
            "mutation($input: setSecretInput!)": {
                "setSecret(input: $input)": {"success"}
            }
        }

        result = self.graphql(
            mutation, variables=dict(input=dict(name=name, value=value))
        )  # type: Any

        if not result.data.setSecret.success:
            raise ValueError("Setting secret failed.")

    def write_run_log(
        self,
        flow_run_id: str,
        task_run_id: str = None,
        timestamp: datetime.datetime = None,
        name: str = None,
        message: str = None,
        level: str = None,
        info: Any = None,
    ) -> None:
        """
        Writes a log to Cloud

        Args:
            - flow_run_id (str): the flow run id
            - task_run_id (str, optional): the task run id
            - timestamp (datetime, optional): the timestamp; defaults to now
            - name (str, optional): the name of the logger
            - message (str, optional): the log message
            - level (str, optional): the log level as a string. Defaults to INFO, should be one of
                DEBUG, INFO, WARNING, ERROR, or CRITICAL.
            - info (Any, optional): a JSON payload of additional information

        Raises:
            - ValueError: if writing the log fails
        """
        mutation = {
            "mutation($input: writeRunLogInput!)": {
                "writeRunLog(input: $input)": {"success"}
            }
        }

        if timestamp is None:
            timestamp = pendulum.now("UTC")
        timestamp_str = pendulum.instance(timestamp).isoformat()
        result = self.graphql(
            mutation,
            variables=dict(
                input=dict(
                    flowRunId=flow_run_id,
                    taskRunId=task_run_id,
                    timestamp=timestamp_str,
                    name=name,
                    message=message,
                    level=level,
                    info=info,
                )
            ),
        )  # type: Any

        if not result.data.writeRunLog.success:
            raise ValueError("Writing log failed.")
