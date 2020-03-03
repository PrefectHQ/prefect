import datetime
import json
import os
import re
import uuid
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional, Union
from urllib.parse import urljoin

import pendulum
import toml
from slugify import slugify

import prefect
from prefect.utilities.exceptions import AuthorizationError, ClientError
from prefect.utilities.graphql import (
    EnumValue,
    GraphQLResult,
    compress,
    parse_graphql,
    with_args,
)

if TYPE_CHECKING:
    from prefect.core import Flow
    import requests
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
        ("name", str),
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
        - api_server (str, optional): the URL to send all GraphQL requests
            to; if not provided, will be pulled from `cloud.graphql` config var
        - api_token (str, optional): a Prefect Cloud API token, taken from
            `config.cloud.auth_token` if not provided. If this token is USER-scoped, it may
            be used to log in to any tenant that the user is a member of. In that case,
            ephemeral JWTs will be loaded as necessary. Otherwise, the API token itself
            will be used as authorization.
    """

    def __init__(self, api_server: str = None, api_token: str = None):
        self._access_token = None
        self._refresh_token = None
        self._access_token_expires_at = pendulum.now()
        self._active_tenant_id = None

        # store api server
        self.api_server = api_server or prefect.context.config.cloud.get("graphql")

        # store api token
        self._api_token = api_token or prefect.context.config.cloud.get(
            "auth_token", None
        )

        # if no api token was passed, attempt to load state from local storage
        if not self._api_token:
            settings = self._load_local_settings()
            self._api_token = settings.get("api_token")

            if self._api_token:
                self._active_tenant_id = settings.get("active_tenant_id")
            if self._active_tenant_id:
                try:
                    self.login_to_tenant(tenant_id=self._active_tenant_id)
                except AuthorizationError:
                    # if an authorization error is raised, then the token is invalid and should
                    # be cleared
                    self.logout_from_tenant()

    # -------------------------------------------------------------------------
    # Utilities

    def get(
        self,
        path: str,
        server: str = None,
        headers: dict = None,
        params: Dict[str, JSONLike] = None,
        token: str = None,
    ) -> dict:
        """
        Convenience function for calling the Prefect API with token auth and GET request

        Args:
            - path (str): the path of the API url. For example, to GET
                http://prefect-server/v1/auth/login, path would be 'auth/login'.
            - server (str, optional): the server to send the GET request to;
                defaults to `self.api_server`
            - headers (dict, optional): Headers to pass with the request
            - params (dict): GET parameters
            - token (str): an auth token. If not supplied, the `client.access_token` is used.

        Returns:
            - dict: Dictionary representation of the request made
        """
        response = self._request(
            method="GET",
            path=path,
            params=params,
            server=server,
            headers=headers,
            token=token,
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
        token: str = None,
    ) -> dict:
        """
        Convenience function for calling the Prefect API with token auth and POST request

        Args:
            - path (str): the path of the API url. For example, to POST
                http://prefect-server/v1/auth/login, path would be 'auth/login'.
            - server (str, optional): the server to send the POST request to;
                defaults to `self.api_server`
            - headers(dict): headers to pass with the request
            - params (dict): POST parameters
            - token (str): an auth token. If not supplied, the `client.access_token` is used.

        Returns:
            - dict: Dictionary representation of the request made
        """
        response = self._request(
            method="POST",
            path=path,
            params=params,
            server=server,
            headers=headers,
            token=token,
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
        token: str = None,
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
            - token (str): an auth token. If not supplied, the `client.access_token` is used.

        Returns:
            - dict: Data returned from the GraphQL query

        Raises:
            - ClientError if there are errors raised by the GraphQL mutation
        """
        result = self.post(
            path="",
            server=self.api_server,
            headers=headers,
            params=dict(query=parse_graphql(query), variables=json.dumps(variables)),
            token=token,
        )

        if raise_on_error and "errors" in result:
            if "UNAUTHENTICATED" in str(result["errors"]):
                raise AuthorizationError(result["errors"])
            elif "Malformed Authorization header" in str(result["errors"]):
                raise AuthorizationError(result["errors"])
            raise ClientError(result["errors"])
        else:
            return GraphQLResult(result)  # type: ignore

    def _request(
        self,
        method: str,
        path: str,
        params: Dict[str, JSONLike] = None,
        server: str = None,
        headers: dict = None,
        token: str = None,
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
            - token (str): an auth token. If not supplied, the `client.access_token` is used.

        Returns:
            - requests.models.Response: The response returned from the request

        Raises:
            - ClientError: if the client token is not in the context (due to not being logged in)
            - ValueError: if a method is specified outside of the accepted GET, POST, DELETE
            - requests.HTTPError: if a status code is returned that is not `200` or `401`
        """
        if server is None:
            server = self.api_server
        assert isinstance(server, str)  # mypy assert

        if token is None:
            token = self.get_auth_token()

        # 'import requests' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import requests

        url = urljoin(server, path.lstrip("/")).rstrip("/")

        params = params or {}

        headers = headers or {}
        if token:
            headers["Authorization"] = "Bearer {}".format(token)
        headers["X-PREFECT-CORE-VERSION"] = str(prefect.__version__)

        session = requests.Session()
        retries = requests.packages.urllib3.util.retry.Retry(
            total=6,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            method_whitelist=["DELETE", "GET", "POST"],
        )
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retries))
        if method == "GET":
            response = session.get(url, headers=headers, params=params, timeout=30)
        elif method == "POST":
            response = session.post(url, headers=headers, json=params, timeout=30)
        elif method == "DELETE":
            response = session.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError("Invalid method: {}".format(method))

        # Check if request returned a successful status
        response.raise_for_status()

        return response

    # -------------------------------------------------------------------------
    # Auth
    # -------------------------------------------------------------------------

    @property
    def _local_settings_path(self) -> Path:
        """
        Returns the local settings directory corresponding to the current API servers
        """
        path = "{home}/client/{server}".format(
            home=prefect.context.config.home_dir,
            server=slugify(self.api_server, regex_pattern=r"[^-\.a-z0-9]+"),
        )
        return Path(os.path.expanduser(path)) / "settings.toml"

    def _save_local_settings(self, settings: dict) -> None:
        """
        Writes settings to local storage
        """
        self._local_settings_path.parent.mkdir(exist_ok=True, parents=True)
        with self._local_settings_path.open("w+") as f:
            toml.dump(settings, f)

    def _load_local_settings(self) -> dict:
        """
        Loads settings from local storage
        """
        if self._local_settings_path.exists():
            with self._local_settings_path.open("r") as f:
                return toml.load(f)  # type: ignore
        return {}

    def save_api_token(self) -> None:
        """
        Saves the API token in local storage.
        """
        settings = self._load_local_settings()
        settings["api_token"] = self._api_token
        self._save_local_settings(settings)

    def get_auth_token(self) -> str:
        """
        Returns an auth token:
            - if no explicit access token is stored, returns the api token
            - if there is an access token:
                - if there's a refresh token and the access token expires in the next 30 seconds,
                  then we refresh the access token and store the result
                - return the access token

        Returns:
            - str: the access token
        """
        if not self._access_token:
            return self._api_token

        expiration = self._access_token_expires_at or pendulum.now()
        if self._refresh_token and pendulum.now().add(seconds=30) > expiration:
            self._refresh_access_token()

        return self._access_token

    def get_available_tenants(self) -> List[Dict]:
        """
        Returns a list of available tenants.

        NOTE: this should only be called by users who have provided a USER-scoped API token.

        Returns:
            - List[Dict]: a list of dictionaries containing the id, slug, and name of
            available tenants
        """
        result = self.graphql(
            {"query": {"tenant(order_by: {slug: asc})": {"id", "slug", "name"}}},
            # use the API token to see all available tenants
            token=self._api_token,
        )  # type: ignore
        return result.data.tenant  # type: ignore

    def login_to_tenant(self, tenant_slug: str = None, tenant_id: str = None) -> bool:
        """
        Log in to a specific tenant

        NOTE: this should only be called by users who have provided a USER-scoped API token.

        Args:
            - tenant_slug (str): the tenant's slug
            - tenant_id (str): the tenant's id

        Returns:
            - bool: True if the login was successful

        Raises:
            - ValueError: if at least one of `tenant_slug` or `tenant_id` isn't provided
            - ValueError: if the `tenant_id` is not a valid UUID
            - ValueError: if no matching tenants are found

        """

        if tenant_slug is None and tenant_id is None:
            raise ValueError(
                "At least one of `tenant_slug` or `tenant_id` must be provided."
            )
        elif tenant_id:
            try:
                uuid.UUID(tenant_id)
            except ValueError:
                raise ValueError("The `tenant_id` must be a valid UUID.")

        tenant = self.graphql(
            {
                "query($slug: String, $id: uuid)": {
                    "tenant(where: {slug: { _eq: $slug }, id: { _eq: $id } })": {"id"}
                }
            },
            variables=dict(slug=tenant_slug, id=tenant_id),
            # use the API token to query the tenant
            token=self._api_token,
        )  # type: ignore
        if not tenant.data.tenant:  # type: ignore
            raise ValueError("No matching tenants found.")

        tenant_id = tenant.data.tenant[0].id  # type: ignore

        payload = self.graphql(
            {
                "mutation($input: switchTenantInput!)": {
                    "switchTenant(input: $input)": {
                        "accessToken",
                        "expiresAt",
                        "refreshToken",
                    }
                }
            },
            variables=dict(input=dict(tenantId=tenant_id)),
            # Use the API token to switch tenants
            token=self._api_token,
        )  # type: ignore
        self._access_token = payload.data.switchTenant.accessToken  # type: ignore
        self._access_token_expires_at = pendulum.parse(
            payload.data.switchTenant.expiresAt  # type: ignore
        )  # type: ignore
        self._refresh_token = payload.data.switchTenant.refreshToken  # type: ignore
        self._active_tenant_id = tenant_id

        # save the tenant setting
        settings = self._load_local_settings()
        settings["active_tenant_id"] = self._active_tenant_id
        self._save_local_settings(settings)

        return True

    def logout_from_tenant(self) -> None:
        self._access_token = None
        self._refresh_token = None
        self._active_tenant_id = None

        # remove the tenant setting
        settings = self._load_local_settings()
        settings["active_tenant_id"] = None
        self._save_local_settings(settings)

    def _refresh_access_token(self) -> bool:
        """
        Refresh the client's JWT access token.

        NOTE: this should only be called by users who have provided a USER-scoped API token.

        Returns:
            - bool: True if the refresh succeeds
        """
        payload = self.graphql(
            {
                "mutation($input: refreshTokenInput!)": {
                    "refreshToken(input: $input)": {
                        "accessToken",
                        "expiresAt",
                        "refreshToken",
                    }
                }
            },
            variables=dict(input=dict(accessToken=self._access_token)),
            # pass the refresh token as the auth header
            token=self._refresh_token,
        )  # type: ignore
        self._access_token = payload.data.refreshToken.accessToken  # type: ignore
        self._access_token_expires_at = pendulum.parse(
            payload.data.refreshToken.expiresAt  # type: ignore
        )  # type: ignore
        self._refresh_token = payload.data.refreshToken.refreshToken  # type: ignore

        return True

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def deploy(
        self,
        flow: "Flow",
        project_name: str,
        build: bool = True,
        set_schedule_active: bool = True,
        version_group_id: str = None,
        compressed: bool = True,
    ) -> str:
        """
        *Note*: This function will be deprecated soon and should be replaced with `client.register`

        Push a new flow to Prefect Cloud

        Args:
            - flow (Flow): a flow to register
            - project_name (str): the project that should contain this flow.
            - build (bool, optional): if `True`, the flow's environment is built
                prior to serialization; defaults to `True`
            - set_schedule_active (bool, optional): if `False`, will set the
                schedule to inactive in the database to prevent auto-scheduling runs (if the Flow has a schedule).
                Defaults to `True`. This can be changed later.
            - version_group_id (str, optional): the UUID version group ID to use for versioning this Flow
                in Cloud; if not provided, the version group ID associated with this Flow's project and name
                will be used.
            - compressed (bool, optional): if `True`, the serialized flow will be; defaults to `True`
                compressed

        Returns:
            - str: the ID of the newly-registered flow

        Raises:
            - ClientError: if the register failed
        """
        warnings.warn(
            "client.deploy() will be deprecated in an upcoming release. Please use client.register()",
            UserWarning,
        )

        return self.register(
            flow=flow,
            project_name=project_name,
            build=build,
            set_schedule_active=set_schedule_active,
            version_group_id=version_group_id,
            compressed=compressed,
        )

    def register(
        self,
        flow: "Flow",
        project_name: str,
        build: bool = True,
        set_schedule_active: bool = True,
        version_group_id: str = None,
        compressed: bool = True,
        no_url: bool = False,
    ) -> str:
        """
        Push a new flow to Prefect Cloud

        Args:
            - flow (Flow): a flow to register
            - project_name (str): the project that should contain this flow.
            - build (bool, optional): if `True`, the flow's environment is built
                prior to serialization; defaults to `True`
            - set_schedule_active (bool, optional): if `False`, will set the
                schedule to inactive in the database to prevent auto-scheduling runs (if the Flow has a schedule).
                Defaults to `True`. This can be changed later.
            - version_group_id (str, optional): the UUID version group ID to use for versioning this Flow
                in Cloud; if not provided, the version group ID associated with this Flow's project and name
                will be used.
            - compressed (bool, optional): if `True`, the serialized flow will be; defaults to `True`
                compressed
            - no_url (bool, optional): if `True`, the stdout from this function will not contain the
                URL link to the newly-registered flow in the Cloud UI

        Returns:
            - str: the ID of the newly-registered flow

        Raises:
            - ClientError: if the register failed
        """
        required_parameters = {p for p in flow.parameters() if p.required}
        if flow.schedule is not None and required_parameters:
            raise ClientError(
                "Flows with required parameters can not be scheduled automatically."
            )
        if any(e.key for e in flow.edges) and flow.result_handler is None:
            warnings.warn(
                "No result handler was specified on your Flow. Cloud features such as input caching and resuming task runs from failure may not work properly.",
                UserWarning,
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
                'Project {} not found. Run `client.create_project("{}")` to create it.'.format(
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
                    versionGroupId=version_group_id,
                )
            ),
        )  # type: Any

        flow_id = (
            res.data.createFlowFromCompressedString.id
            if compressed
            else res.data.createFlow.id
        )

        if not no_url:
            # Generate direct link to Cloud flow
            tenant_slug = self.get_default_tenant_slug()

            url = (
                re.sub("api-", "", prefect.config.cloud.api)
                if re.search("api-", prefect.config.cloud.api)
                else re.sub("api", "cloud", prefect.config.cloud.api)
            )

            flow_url = "/".join([url.rstrip("/"), tenant_slug, "flow", flow_id])

            print("Flow: {}".format(flow_url))

        return flow_id

    def get_default_tenant_slug(self) -> str:
        """
        Get the default tenant slug for the currently authenticated user

        Returns:
            - str: the slug of the current default tenant for this user
        """
        res = self.graphql(
            query={"query": {"user": {"default_membership": {"tenant": "slug"}}}}
        )

        user = res.get("data").user[0]
        return user.default_membership.tenant.slug

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
        flow_id: str = None,
        context: dict = None,
        parameters: dict = None,
        scheduled_start_time: datetime.datetime = None,
        idempotency_key: str = None,
        run_name: str = None,
        version_group_id: str = None,
    ) -> str:
        """
        Create a new flow run for the given flow id.  If `start_time` is not provided, the flow run will be scheduled to start immediately.
        If both `flow_id` and `version_group_id` are provided, only the `flow_id` will be used.

        Args:
            - flow_id (str, optional): the id of the Flow you wish to schedule
            - context (dict, optional): the run context
            - parameters (dict, optional): a dictionary of parameter values to pass to the flow run
            - scheduled_start_time (datetime, optional): the time to schedule the execution for; if not provided, defaults to now
            - idempotency_key (str, optional): an idempotency key; if provided, this run will be cached for 24
                hours. Any subsequent attempts to create a run with the same idempotency key
                will return the ID of the originally created run (no new run will be created after the first).
                An error will be raised if parameters or context are provided and don't match the original.
                Each subsequent request will reset the TTL for 24 hours.
            - run_name (str, optional): The name assigned to this flow run
            - version_group_id (str, optional): if provided, the unique unarchived flow within this version group will be scheduled
                to run.  This input can be used as a stable API for running flows which are regularly updated.

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
        if not flow_id and not version_group_id:
            raise ValueError("One of flow_id or version_group_id must be provided")

        inputs = (
            dict(flowId=flow_id) if flow_id else dict(versionGroupId=version_group_id)  # type: ignore
        )
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
        if run_name is not None:
            inputs.update(flowRunName=run_name)  # type: ignore
        res = self.graphql(create_mutation, variables=dict(input=inputs))
        return res.data.createFlowRun.flow_run.id  # type: ignore

    def get_flow_run_info(self, flow_run_id: str) -> FlowRunInfoResult:
        """
        Retrieves version and current state information for the given flow run.

        Args:
            - flow_run_id (str): the id of the flow run to get information for

        Returns:
            - GraphQLResult: an object representing information about the flow run

        Raises:
            - ClientError: if the GraphQL mutation is bad for any reason
        """
        query = {
            "query": {
                with_args("flow_run_by_pk", {"id": flow_run_id}): {
                    "id": True,
                    "name": True,
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
        self.graphql(mutation, raise_on_error=True)

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
        self.graphql(mutation, raise_on_error=True)

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
            "mutation($input: setFlowRunStatesInput!)": {
                "setFlowRunStates(input: $input)": {"states": {"id"}}
            }
        }

        serialized_state = state.serialize()

        result = self.graphql(
            mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            state=serialized_state,
                            flowRunId=flow_run_id,
                            version=version,
                        )
                    ]
                )
            ),
        )  # type: Any

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
    ) -> "prefect.engine.state.State":
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

        Returns:
            - State: the state the current task run should be considered in
        """
        mutation = {
            "mutation($input: setTaskRunStatesInput!)": {
                "setTaskRunStates(input: $input)": {
                    "states": {"id", "status", "message"}
                }
            }
        }

        serialized_state = state.serialize()

        result = self.graphql(
            mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            state=serialized_state,
                            taskRunId=task_run_id,
                            version=version,
                        )
                    ]
                )
            ),
        )  # type: Any
        state_payload = result.data.setTaskRunStates.states[0]
        if state_payload.status == "QUEUED":
            # If appropriate, the state attribute of the Queued state can be
            # set by the caller of this method
            return prefect.engine.state.Queued(
                message=state_payload.get("message"),
                start_time=pendulum.now("UTC").add(
                    seconds=prefect.context.config.cloud.queue_interval
                ),
            )
        return state

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

    def get_task_tag_limit(self, tag: str) -> Optional[int]:
        """
        Retrieve the current task tag concurrency limit for a given tag.

        Args:
            - tag (str): the tag to update

        Raises:
            - ClientError: if the GraphQL query fails
        """
        query = {
            "query": {
                with_args("task_tag_limit", {"where": {"tag": {"_eq": tag}}}): {
                    "limit": True
                }
            }
        }

        result = self.graphql(query)  # type: Any
        if result.data.task_tag_limit:
            return result.data.task_tag_limit[0].limit
        else:
            return None

    def update_task_tag_limit(self, tag: str, limit: int) -> None:
        """
        Update the task tag concurrency limit for a given tag; requires tenant admin permissions.

        Args:
            - tag (str): the tag to update
            - limit (int): the concurrency limit to enforce on the tag; should be a value >= 0

        Raises:
            - ClientError: if the GraphQL mutation is bad for any reason
            - ValueError: if the tag limit-setting was unsuccessful, or if a bad limit was provided
        """
        if limit < 0:
            raise ValueError("Concurrency limits must be >= 0")

        mutation = {
            "mutation($input: updateTaskTagLimitInput!)": {
                "updateTaskTagLimit(input: $input)": {"id"}
            }
        }

        result = self.graphql(
            mutation, variables=dict(input=dict(tag=tag, limit=limit))
        )  # type: Any

        if not result.data.updateTaskTagLimit.id:
            raise ValueError("Updating the task tag concurrency limit failed.")

    def delete_task_tag_limit(self, limit_id: str) -> None:
        """
        Deletes a given task tag concurrency limit; requires tenant admin permissions.

        Args:
            - limit_id (str): the ID of the tag to delete

        Raises:
            - ClientError: if the GraphQL mutation is bad for any reason
            - ValueError: if the tag deletion was unsuccessful, or if a bad tag ID was provided
        """
        mutation = {
            "mutation($input: deleteTaskTagLimitInput!)": {
                "deleteTaskTagLimit(input: $input)": {"success"}
            }
        }

        result = self.graphql(
            mutation, variables=dict(input=dict(limitId=limit_id))
        )  # type: Any

        if not result.data.deleteTaskTagLimit.success:
            raise ValueError("Deleting the task tag concurrency limit failed.")

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
        Uploads a log to Cloud.

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
        warnings.warn(
            "DEPRECATED: Client.write_run_log is deprecated, use Client.write_run_logs instead",
            UserWarning,
        )
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

    def write_run_logs(self, logs: List[Dict]) -> None:
        """
        Uploads a collection of logs to Cloud.

        Args:
            - logs (List[Dict]): a list of log entries to add

        Raises:
            - ValueError: if uploading the logs fail
        """
        mutation = {
            "mutation($input: writeRunLogsInput!)": {
                "writeRunLogs(input: $input)": {"success"}
            }
        }

        result = self.graphql(
            mutation, variables=dict(input=dict(logs=logs))
        )  # type: Any

        if not result.data.writeRunLogs.success:
            raise ValueError("Writing logs failed.")
