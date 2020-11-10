import datetime
import json
import os
import re
import time
import uuid
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional, Union
from urllib.parse import urljoin

# if simplejson is installed, `requests` defaults to using it instead of json
# this allows the client to gracefully handle either json or simplejson
try:
    from simplejson.errors import JSONDecodeError
except ImportError:
    from json.decoder import JSONDecodeError

import pendulum
import toml
from slugify import slugify

import prefect
from prefect.utilities.exceptions import (
    AuthorizationError,
    ClientError,
    VersionLockError,
)
from prefect.utilities.graphql import (
    EnumValue,
    GraphQLResult,
    compress,
    parse_graphql,
    with_args,
)
from prefect.utilities.logging import create_diagnostic_logger

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
        self._attached_headers = {}  # type: Dict[str, str]
        self.logger = create_diagnostic_logger("Diagnostics")

        # store api server
        self.api_server = api_server or prefect.context.config.cloud.get("graphql")

        self._api_token = api_token or prefect.context.config.cloud.get(
            "auth_token", None
        )

        # Initialize the tenant and api token if not yet set
        if not self._api_token and prefect.config.backend == "cloud":
            self._init_tenant()

    def create_tenant(self, name: str, slug: str = None) -> str:
        """
        Creates a new tenant.

        Note this route only works when run against Prefect Server.

        Args:
            - name (str): the name of the tenant to create
            - slug (str, optional): the slug of the tenant to create; defaults to name

        Returns:
            - str: the ID of the newly created tenant, or the ID of the currently active tenant

        Raises:
            - ValueError: if run against Prefect Cloud
        """
        if prefect.config.backend != "server":
            msg = "To create a tenant with Prefect Cloud, please signup at https://cloud.prefect.io/"
            raise ValueError(msg)

        if slug is None:
            slug = slugify(name)

        tenant_info = self.graphql(
            {
                "mutation($input: create_tenant_input!)": {
                    "create_tenant(input: $input)": {"id"}
                }
            },
            variables=dict(input=dict(name=name, slug=slug)),
        )
        return tenant_info.data.create_tenant.id

    # -------------------------------------------------------------------------
    # Utilities

    def get(
        self,
        path: str,
        server: str = None,
        headers: dict = None,
        params: Dict[str, JSONLike] = None,
        token: str = None,
        retry_on_api_error: bool = True,
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
            - retry_on_api_error (bool): whether the operation should be retried if the API returns
                an API_ERROR code

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
            retry_on_api_error=retry_on_api_error,
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
        retry_on_api_error: bool = True,
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
            - retry_on_api_error (bool): whether the operation should be retried if the API returns
                an API_ERROR code

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
            retry_on_api_error=retry_on_api_error,
        )
        if response.text:
            return response.json()
        else:
            return {}

    @property
    def active_tenant_id(self) -> Optional[str]:
        """
        Return the tenant to contact the server.
        If your tenant has not been set yet it will be initialized.
        """
        if self._active_tenant_id is None:
            self._init_tenant()
        return self._active_tenant_id

    def _init_tenant(self) -> None:
        """
        Init the tenant to contact the server.

        If your backend is set to cloud the tenant will be read from: $HOME/.prefect/settings.toml.

        For the server backend it will try to retrieve the default tenant. If the server is
        protected with auth like BasicAuth do not forget to `attach_headers` before any call.
        """
        if prefect.config.backend == "cloud":
            # if no api token was passed, attempt to load state from local storage
            settings = self._load_local_settings()

            if not self._api_token:
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
        else:
            tenant_info = self.graphql({"query": {"tenant": {"id"}}})
            if tenant_info.data.tenant:
                self._active_tenant_id = tenant_info.data.tenant[0].id

    def graphql(
        self,
        query: Any,
        raise_on_error: bool = True,
        headers: Dict[str, str] = None,
        variables: Dict[str, JSONLike] = None,
        token: str = None,
        retry_on_api_error: bool = True,
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
            - retry_on_api_error (bool): whether the operation should be retried if the API returns
                an API_ERROR code

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
            retry_on_api_error=retry_on_api_error,
        )

        if raise_on_error and "errors" in result:
            if "UNAUTHENTICATED" in str(result["errors"]):
                raise AuthorizationError(result["errors"])
            elif "Malformed Authorization header" in str(result["errors"]):
                raise AuthorizationError(result["errors"])
            elif (
                result["errors"][0].get("extensions", {}).get("code")
                == "VERSION_LOCKING_ERROR"
            ):
                raise VersionLockError(result["errors"])
            raise ClientError(result["errors"])
        else:
            return GraphQLResult(result)  # type: ignore

    def _send_request(
        self,
        session: "requests.Session",
        method: str,
        url: str,
        params: Dict[str, JSONLike] = None,
        headers: dict = None,
    ) -> "requests.models.Response":
        if prefect.context.config.cloud.get("diagnostics") is True:
            self.logger.debug(f"Preparing request to {url}")
            clean_headers = {
                head: re.sub("Bearer .*", "Bearer XXXX", val)
                for head, val in headers.items()  # type: ignore
            }
            self.logger.debug(f"Headers: {clean_headers}")
            self.logger.debug(f"Request: {params}")
            start_time = time.time()

        if method == "GET":
            response = session.get(url, headers=headers, params=params, timeout=30)
        elif method == "POST":
            response = session.post(url, headers=headers, json=params, timeout=30)
        elif method == "DELETE":
            response = session.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError("Invalid method: {}".format(method))

        if prefect.context.config.cloud.get("diagnostics") is True:
            end_time = time.time()
            self.logger.debug(f"Response: {response.json()}")
            self.logger.debug(
                f"Request duration: {round(end_time - start_time, 4)} seconds"
            )

        # Check if request returned a successful status
        if response.status_code == 400:
            msg = (
                f"400 Client Error: Bad Request for url: {url}\n\n"
                f"This is likely caused by a poorly formatted GraphQL query or mutation."
            )
            try:
                msg += f" GraphQL sent:\n\n{parse_graphql(params)}"
            except Exception:
                # failed to format, raise below
                pass
            finally:
                raise ClientError(msg)
        response.raise_for_status()
        return response

    def _request(
        self,
        method: str,
        path: str,
        params: Dict[str, JSONLike] = None,
        server: str = None,
        headers: dict = None,
        token: str = None,
        retry_on_api_error: bool = True,
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
            - retry_on_api_error (bool): whether the operation should be retried if the API returns
                an API_ERROR code

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

        if self._attached_headers:
            headers.update(self._attached_headers)

        session = requests.Session()
        retry_total = 6 if prefect.config.backend == "cloud" else 1
        retries = requests.packages.urllib3.util.retry.Retry(
            total=retry_total,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            method_whitelist=["DELETE", "GET", "POST"],
        )
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retries))
        response = self._send_request(
            session=session, method=method, url=url, params=params, headers=headers
        )

        # parse the response
        try:
            json_resp = response.json()
        except JSONDecodeError as exc:
            if prefect.config.backend == "cloud" and "Authorization" not in headers:
                raise ClientError(
                    "Malformed response received from Cloud - please ensure that you "
                    "have an API token properly configured."
                ) from exc
            else:
                raise ClientError("Malformed response received from API.") from exc

        # check if there was an API_ERROR code in the response
        if "API_ERROR" in str(json_resp.get("errors")) and retry_on_api_error:
            success, retry_count = False, 0
            # retry up to six times
            while success is False and retry_count < 6:
                response = self._send_request(
                    session=session,
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                )
                if "API_ERROR" in str(response.json().get("errors")):
                    retry_count += 1
                    time.sleep(0.25 * (2 ** (retry_count - 1)))
                else:
                    success = True

        return response

    def attach_headers(self, headers: dict) -> None:
        """
        Set headers to be attached to this Client

        Args:
            - headers (dict): A dictionary of headers to attach to this client. These headers
                get added on to the existing dictionary of headers.
        """
        self._attached_headers.update(headers)

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
            return self._api_token  # type: ignore

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
            except ValueError as exc:
                raise ValueError("The `tenant_id` must be a valid UUID.") from exc

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

        if prefect.config.backend == "cloud":
            payload = self.graphql(
                {
                    "mutation($input: switch_tenant_input!)": {
                        "switch_tenant(input: $input)": {
                            "access_token",
                            "expires_at",
                            "refresh_token",
                        }
                    }
                },
                variables=dict(input=dict(tenant_id=tenant_id)),
                # Use the API token to switch tenants
                token=self._api_token,
            )  # type: ignore
            self._access_token = payload.data.switch_tenant.access_token  # type: ignore
            self._access_token_expires_at = pendulum.parse(  # type: ignore
                payload.data.switch_tenant.expires_at  # type: ignore
            )  # type: ignore
            self._refresh_token = payload.data.switch_tenant.refresh_token  # type: ignore

        self._active_tenant_id = tenant_id  # type: ignore

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
                "mutation($input: refresh_token_input!)": {
                    "refresh_token(input: $input)": {
                        "access_token",
                        "expires_at",
                        "refresh_token",
                    }
                }
            },
            variables=dict(input=dict(access_token=self._access_token)),
            # pass the refresh token as the auth header
            token=self._refresh_token,
        )  # type: ignore
        self._access_token = payload.data.refresh_token.access_token  # type: ignore
        self._access_token_expires_at = pendulum.parse(  # type: ignore
            payload.data.refresh_token.expires_at  # type: ignore
        )  # type: ignore
        self._refresh_token = payload.data.refresh_token.refresh_token  # type: ignore

        return True

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def register(
        self,
        flow: "Flow",
        project_name: str = None,
        build: bool = True,
        set_schedule_active: bool = True,
        version_group_id: str = None,
        compressed: bool = True,
        no_url: bool = False,
        idempotency_key: str = None,
    ) -> str:
        """
        Push a new flow to Prefect Cloud

        Args:
            - flow (Flow): a flow to register
            - project_name (str, optional): the project that should contain this flow.
            - build (bool, optional): if `True`, the flow's environment is built
                prior to serialization; defaults to `True`
            - set_schedule_active (bool, optional): if `False`, will set the schedule to
                inactive in the database to prevent auto-scheduling runs (if the Flow has a
                schedule).  Defaults to `True`. This can be changed later.
            - version_group_id (str, optional): the UUID version group ID to use for versioning
                this Flow in Cloud; if not provided, the version group ID associated with this
                Flow's project and name will be used.
            - compressed (bool, optional): if `True`, the serialized flow will be; defaults to
                `True` compressed
            - no_url (bool, optional): if `True`, the stdout from this function will not
                contain the URL link to the newly-registered flow in the Cloud UI
            - idempotency_key (optional, str): a key that, if matching the most recent
                registration call for this flow group, will prevent the creation of
                another flow version and return the existing flow id instead.

        Returns:
            - str: the ID of the newly-registered flow

        Raises:
            - ClientError: if the register failed
        """
        required_parameters = {p for p in flow.parameters() if p.required}
        if flow.schedule is not None and required_parameters:
            required_names = {p.name for p in required_parameters}
            if not all(
                [
                    required_names <= set(c.parameter_defaults.keys())
                    for c in flow.schedule.clocks
                ]
            ):
                raise ClientError(
                    "Flows with required parameters can not be scheduled automatically."
                )
        if any(e.key for e in flow.edges) and flow.result is None:
            warnings.warn(
                "No result handler was specified on your Flow. Cloud features such as "
                "input caching and resuming task runs from failure may not work properly.",
                stacklevel=2,
            )
        if compressed:
            create_mutation = {
                "mutation($input: create_flow_from_compressed_string_input!)": {
                    "create_flow_from_compressed_string(input: $input)": {"id"}
                }
            }
        else:
            create_mutation = {
                "mutation($input: create_flow_input!)": {
                    "create_flow(input: $input)": {"id"}
                }
            }

        project = None

        if project_name is None:
            raise TypeError(
                "'project_name' is a required field when registering a flow."
            )

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
                "Project {} not found. Run `prefect create project '{}'` to create it.".format(
                    project_name, project_name
                )
            )

        serialized_flow = flow.serialize(build=build)  # type: Any

        # Set Docker storage image in environment metadata if provided
        if isinstance(flow.storage, prefect.environments.storage.Docker):
            flow.environment.metadata["image"] = flow.storage.name
            serialized_flow = flow.serialize(build=False)

        # If no image ever set, default metadata to all_extras image on current version
        if not flow.environment.metadata.get("image"):
            version = prefect.__version__.split("+")[0]
            flow.environment.metadata[
                "image"
            ] = f"prefecthq/prefect:all_extras-{version}"
            serialized_flow = flow.serialize(build=False)

        # verify that the serialized flow can be deserialized
        try:
            prefect.serialization.flow.FlowSchema().load(serialized_flow)
        except Exception as exc:
            raise ValueError(
                "Flow could not be deserialized successfully. Error was: {}".format(
                    repr(exc)
                )
            ) from exc

        if compressed:
            serialized_flow = compress(serialized_flow)

        inputs = dict(
            project_id=(project[0].id if project else None),
            serialized_flow=serialized_flow,
            set_schedule_active=set_schedule_active,
            version_group_id=version_group_id,
        )
        # Add newly added inputs only when set for backwards compatibility
        if idempotency_key is not None:
            inputs.update(idempotency_key=idempotency_key)

        res = self.graphql(
            create_mutation,
            variables=dict(input=inputs),
            retry_on_api_error=False,
        )  # type: Any

        flow_id = (
            res.data.create_flow_from_compressed_string.id
            if compressed
            else res.data.create_flow.id
        )

        if not no_url:
            # Query for flow group id
            res = self.graphql(
                {
                    "query": {
                        with_args("flow_by_pk", {"id": flow_id}): {"flow_group_id": ...}
                    }
                }
            )
            flow_group_id = res.get("data").flow_by_pk.flow_group_id

            # Generate direct link to Cloud flow
            flow_url = self.get_cloud_url("flow", flow_group_id)

            prefix = "└── "

            print("Flow URL: {}".format(flow_url))

            # Extra information to improve visibility
            msg = (
                f" {prefix}ID: {flow_id}\n"
                f" {prefix}Project: {project_name}\n"
                f" {prefix}Labels: {list(flow.environment.labels)}"
            )
            print(msg)

        return flow_id

    def get_cloud_url(self, subdirectory: str, id: str, as_user: bool = True) -> str:
        """
        Convenience method for creating Prefect Cloud URLs for a given subdirectory.

        Args:
            - subdirectory (str): the subdirectory to use (e.g., `"flow-run"`)
            - id (str): the ID of the page
            - as_user (bool, optional): whether this query is being made from a USER scoped token;
                defaults to `True`. Only used internally for queries made from RUNNERs

        Returns:
            - str: the URL corresponding to the appropriate base URL, tenant slug, subdirectory
                and ID

        Example:

        ```python
        from prefect import Client

        client = Client()
        client.get_cloud_url("flow-run", "424242-ca-94611-111-55")
        # returns "https://cloud.prefect.io/my-tenant-slug/flow-run/424242-ca-94611-111-55"
        ```
        """
        # Generate direct link to UI
        if prefect.config.backend == "cloud":
            tenant_slug = self.get_default_tenant_slug(as_user=as_user)
        else:
            tenant_slug = ""

        base_url = (
            re.sub("api-", "", prefect.config.cloud.api)
            if re.search("api-", prefect.config.cloud.api)
            else re.sub("api", "cloud", prefect.config.cloud.api)
        )

        full_url = prefect.config.cloud.api
        if tenant_slug:
            full_url = "/".join([base_url.rstrip("/"), tenant_slug, subdirectory, id])
        elif prefect.config.backend == "server":
            full_url = "/".join([prefect.config.server.ui.endpoint, subdirectory, id])

        return full_url

    def get_default_tenant_slug(self, as_user: bool = True) -> str:
        """
        Get the default tenant slug for the currently authenticated user

        Args:
            - as_user (bool, optional): whether this query is being made from a USER scoped token;
                defaults to `True`. Only used internally for queries made from RUNNERs

        Returns:
            - str: the slug of the current default tenant for this user
        """
        if as_user:
            query = {
                "query": {"user": {"default_membership": {"tenant": "slug"}}}
            }  # type: dict
        else:
            query = {"query": {"tenant": {"slug"}}}

        res = self.graphql(query)

        if as_user:
            user = res.get("data").user[0]
            slug = user.default_membership.tenant.slug
        else:
            slug = res.get("data").tenant[0].slug
        return slug

    def create_project(self, project_name: str, project_description: str = None) -> str:
        """
        Create a new project if a project with the name provided does not already exist

        Args:
            - project_name (str): the project that should be created
            - project_description (str, optional): the project description

        Returns:
            - str: the ID of the newly-created or pre-existing project

        Raises:
            - ClientError: if the project creation failed
        """
        project_mutation = {
            "mutation($input: create_project_input!)": {
                "create_project(input: $input)": {"id"}
            }
        }

        try:
            res = self.graphql(
                project_mutation,
                variables=dict(
                    input=dict(
                        name=project_name,
                        description=project_description,
                        tenant_id=self.active_tenant_id,
                    )
                ),
            )  # type: Any
        except ClientError as exc:
            if "'Uniqueness violation.'" in str(exc):
                project_query = {
                    "query": {
                        with_args(
                            "project", {"where": {"name": {"_eq": project_name}}}
                        ): {"id": True}
                    }
                }
                res = self.graphql(project_query)
                return res.data.project[0].id
            raise

        return res.data.create_project.id

    def create_flow_run(
        self,
        flow_id: str = None,
        context: dict = None,
        parameters: dict = None,
        labels: List[str] = None,
        scheduled_start_time: datetime.datetime = None,
        idempotency_key: str = None,
        run_name: str = None,
        version_group_id: str = None,
    ) -> str:
        """
        Create a new flow run for the given flow id.  If `start_time` is not provided, the flow
        run will be scheduled to start immediately.  If both `flow_id` and `version_group_id`
        are provided, only the `flow_id` will be used.

        Args:
            - flow_id (str, optional): the id of the Flow you wish to schedule
            - context (dict, optional): the run context
            - parameters (dict, optional): a dictionary of parameter values to pass to the flow run
            - labels (List[str], optional): a list of labels to apply to the flow run
            - scheduled_start_time (datetime, optional): the time to schedule the execution
                for; if not provided, defaults to now
            - idempotency_key (str, optional): an idempotency key; if provided, this run will
                be cached for 24 hours. Any subsequent attempts to create a run with the same
                idempotency key will return the ID of the originally created run (no new run
                will be created after the first).  An error will be raised if parameters or
                context are provided and don't match the original.  Each subsequent request
                will reset the TTL for 24 hours.
            - run_name (str, optional): The name assigned to this flow run
            - version_group_id (str, optional): if provided, the unique unarchived flow within
                this version group will be scheduled to run.  This input can be used as a
                stable API for running flows which are regularly updated.

        Returns:
            - str: the ID of the newly-created flow run

        Raises:
            - ClientError: if the GraphQL query is bad for any reason
        """
        create_mutation = {
            "mutation($input: create_flow_run_input!)": {
                "create_flow_run(input: $input)": {"id": True}
            }
        }
        if not flow_id and not version_group_id:
            raise ValueError("One of flow_id or version_group_id must be provided")

        if flow_id:
            inputs = dict(flow_id=flow_id)
        else:
            inputs = dict(version_group_id=version_group_id)  # type: ignore
        if parameters is not None:
            inputs.update(parameters=parameters)  # type: ignore
        if labels is not None:
            inputs.update(labels=labels)  # type: ignore
        if context is not None:
            inputs.update(context=context)  # type: ignore
        if idempotency_key is not None:
            inputs.update(idempotency_key=idempotency_key)  # type: ignore
        if scheduled_start_time is not None:
            inputs.update(
                scheduled_start_time=scheduled_start_time.isoformat()
            )  # type: ignore
        if run_name is not None:
            inputs.update(flow_run_name=run_name)  # type: ignore
        res = self.graphql(create_mutation, variables=dict(input=inputs))
        return res.data.create_flow_run.id  # type: ignore

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
                    "update_flow_run_heartbeat", {"input": {"flow_run_id": flow_run_id}}
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
                    "update_task_run_heartbeat", {"input": {"task_run_id": task_run_id}}
                ): {"success"}
            }
        }
        self.graphql(mutation, raise_on_error=True)

    def set_flow_run_name(self, flow_run_id: str, name: str) -> bool:
        """
        Set the name of a flow run.

        Args:
            - flow_run_id (str): the id of a flow run
            - name (str): a name for this flow run

        Returns:
            - bool: whether or not the flow run name was updated
        """
        mutation = {
            "mutation($input: set_flow_run_name_input!)": {
                "set_flow_run_name(input: $input)": {
                    "success": True,
                }
            }
        }

        result = self.graphql(
            mutation, variables=dict(input=dict(flow_run_id=flow_run_id, name=name))
        )

        return result.data.set_flow_run_name.success

    def get_flow_run_state(self, flow_run_id: str) -> "prefect.engine.state.State":
        """
        Retrieves the current state for a flow run.

        Args:
            - flow_run_id (str): the id for this flow run

        Returns:
            - State: a Prefect State object
        """
        query = {
            "query": {
                with_args("flow_run_by_pk", {"id": flow_run_id}): {
                    "serialized_state": True,
                }
            }
        }

        flow_run = self.graphql(query).data.flow_run_by_pk

        return prefect.engine.state.State.deserialize(flow_run.serialized_state)

    def set_flow_run_state(
        self,
        flow_run_id: str,
        state: "prefect.engine.state.State",
        version: int = None,
    ) -> "prefect.engine.state.State":
        """
        Sets new state for a flow run in the database.

        Args:
            - flow_run_id (str): the id of the flow run to set state for
            - state (State): the new state for this flow run
            - version (int, optional): the current version of the flow run state. This is optional
                but it can be supplied to enforce version-locking.

        Returns:
            - State: the state the current flow run should be considered in

        Raises:
            - ClientError: if the GraphQL mutation is bad for any reason
        """
        mutation = {
            "mutation($input: set_flow_run_states_input!)": {
                "set_flow_run_states(input: $input)": {
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
                            flow_run_id=flow_run_id,
                            version=version,
                        )
                    ]
                )
            ),
        )  # type: Any

        state_payload = result.data.set_flow_run_states.states[0]
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

    def get_latest_cached_states(
        self, task_id: str, cache_key: Optional[str], created_after: datetime.datetime
    ) -> List["prefect.engine.state.State"]:
        """
        Pulls all Cached states for the given task that were created after the provided date.

        Args:
            - task_id (str): the task id for this task run
            - cache_key (Optional[str]): the cache key for this Task's cache; if `None`, the
                task id alone will be used
            - created_after (datetime.datetime): the earliest date the state should have been
                created at

        Returns:
            - List[State]: a list of Cached states created after the given date
        """
        args = {
            "where": {
                "state": {"_eq": "Cached"},
                "state_timestamp": {"_gte": created_after.isoformat()},
            },
            "order_by": {"state_timestamp": EnumValue("desc")},
            "limit": 100,
        }  # type: Dict[str, Any]

        # if a cache key was provided, match it against all tasks
        if cache_key is not None:
            args["where"].update({"cache_key": {"_eq": cache_key}})
        # otherwise match against only this task, across all cache keys
        else:
            args["where"].update({"task_id": {"_eq": task_id}})

        query = {"query": {with_args("task_run", args): "serialized_state"}}
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
                    "get_or_create_task_run",
                    {
                        "input": {
                            "flow_run_id": flow_run_id,
                            "task_id": task_id,
                            "map_index": -1 if map_index is None else map_index,
                        }
                    },
                ): {
                    "id": True,
                }
            }
        }
        result = self.graphql(mutation)  # type: Any

        if result is None:
            raise ClientError("Failed to create task run.")

        task_run_id = result.data.get_or_create_task_run.id

        query = {
            "query": {
                with_args("task_run_by_pk", {"id": task_run_id}): {
                    "version": True,
                    "serialized_state": True,
                    "task": {"slug": True},
                }
            }
        }
        task_run = self.graphql(query).data.task_run_by_pk  # type: ignore

        if task_run is None:
            raise ClientError('Task run ID not found: "{}"'.format(task_run_id))

        state = prefect.engine.state.State.deserialize(task_run.serialized_state)
        return TaskRunInfoResult(
            id=task_run_id,
            task_id=task_id,
            task_slug=task_run.task.slug,
            version=task_run.version,
            state=state,
        )

    def set_task_run_name(self, task_run_id: str, name: str) -> bool:
        """
        Set the name of a task run

        Args:
            - task_run_id (str): the id of a task run
            - name (str): a name for this task run

        Returns:
            - bool: whether or not the task run name was updated
        """
        mutation = {
            "mutation($input: set_task_run_name_input!)": {
                "set_task_run_name(input: $input)": {
                    "success": True,
                }
            }
        }

        result = self.graphql(
            mutation, variables=dict(input=dict(task_run_id=task_run_id, name=name))
        )

        return result.data.set_task_run_name.success

    def cancel_flow_run(self, flow_run_id: str) -> bool:
        """
        Cancel the flow run by id

        Args:
            - flow_run_id (str): the id of the flow run

        Returns:
            - bool: whether or not the flow run was canceled
        """
        mutation = {
            "mutation($input: cancel_flow_run_input!)": {
                "cancel_flow_run(input: $input)": {
                    "state": True,
                }
            }
        }
        result = self.graphql(
            mutation, variables=dict(input=dict(flow_run_id=flow_run_id))
        )
        return result.data.cancel_flow_run.state

    def get_task_run_state(self, task_run_id: str) -> "prefect.engine.state.State":
        """
        Retrieves the current state for a task run.

        Args:
            - task_run_id (str): the id for this task run

        Returns:
            - State: a Prefect State object
        """
        query = {
            "query": {
                with_args("task_run_by_pk", {"id": task_run_id}): {
                    "serialized_state": True,
                }
            }
        }

        task_run = self.graphql(query).data.task_run_by_pk

        return prefect.engine.state.State.deserialize(task_run.serialized_state)

    def set_task_run_state(
        self,
        task_run_id: str,
        state: "prefect.engine.state.State",
        version: int = None,
        cache_for: datetime.timedelta = None,
    ) -> "prefect.engine.state.State":
        """
        Sets new state for a task run.

        Args:
            - task_run_id (str): the id of the task run to set state for
            - state (State): the new state for this task run
            - version (int, optional): the current version of the task run state. This is optional
                but it can be supplied to enforce version-locking.
            - cache_for (timedelta, optional): how long to store the result of this task for,
                using the serializer set in config; if not provided, no caching occurs

        Raises:
            - ClientError: if the GraphQL mutation is bad for any reason

        Returns:
            - State: the state the current task run should be considered in
        """
        mutation = {
            "mutation($input: set_task_run_states_input!)": {
                "set_task_run_states(input: $input)": {
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
                            task_run_id=task_run_id,
                            version=version,
                        )
                    ]
                )
            ),
        )  # type: Any
        state_payload = result.data.set_task_run_states.states[0]
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
            "mutation($input: set_secret_input!)": {
                "set_secret(input: $input)": {"success"}
            }
        }

        result = self.graphql(
            mutation, variables=dict(input=dict(name=name, value=value))
        )  # type: Any

        if not result.data.set_secret.success:
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
            "mutation($input: update_task_tag_limit_input!)": {
                "update_task_tag_limit(input: $input)": {"id"}
            }
        }

        result = self.graphql(
            mutation, variables=dict(input=dict(tag=tag, limit=limit))
        )  # type: Any

        if not result.data.update_task_tag_limit.id:
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
            "mutation($input: delete_task_tag_limit_input!)": {
                "delete_task_tag_limit(input: $input)": {"success"}
            }
        }

        result = self.graphql(
            mutation, variables=dict(input=dict(limit_id=limit_id))
        )  # type: Any

        if not result.data.delete_task_tag_limit.success:
            raise ValueError("Deleting the task tag concurrency limit failed.")

    def write_run_logs(self, logs: List[Dict]) -> None:
        """
        Uploads a collection of logs to Cloud.

        Args:
            - logs (List[Dict]): a list of log entries to add

        Raises:
            - ValueError: if uploading the logs fail
        """
        mutation = {
            "mutation($input: write_run_logs_input!)": {
                "write_run_logs(input: $input)": {"success"}
            }
        }

        result = self.graphql(
            mutation, variables=dict(input=dict(logs=logs))
        )  # type: Any

        if not result.data.write_run_logs.success:
            raise ValueError("Writing logs failed.")

    def register_agent(
        self,
        agent_type: str,
        name: str = None,
        labels: List[str] = None,
        agent_config_id: str = None,
    ) -> str:
        """
        Register an agent with a backend API

        Args:
            - agent_type (str): The type of agent being registered
            - name: (str, optional): The name of the agent being registered
            - labels (List[str], optional): A list of any present labels on the agent
                being registered
            - agent_config_id (str, optional): The ID of an agent configuration to register with

        Returns:
            - The agent ID as a string
        """
        mutation = {
            "mutation($input: register_agent_input!)": {
                "register_agent(input: $input)": {"id"}
            }
        }

        result = self.graphql(
            mutation,
            variables=dict(
                input=dict(
                    type=agent_type,
                    name=name,
                    labels=labels or [],
                    tenant_id=self.active_tenant_id,
                    agent_config_id=agent_config_id,
                )
            ),
        )

        if not result.data.register_agent.id:
            raise ValueError("Error registering agent")

        return result.data.register_agent.id

    def get_agent_config(self, agent_config_id: str) -> dict:
        """
        Get agent config settings

        Args:
            - agent_config_id (str): The ID of an agent configuration to retrieve

        Returns:
            - dict: the agent configuration's `settings`
        """
        query = {
            "query": {
                with_args(
                    "agent_config", {"where": {"id": {"_eq": agent_config_id}}}
                ): {"settings": True}
            }
        }

        result = self.graphql(query)  # type: Any
        return result.data.agent_config[0].settings

    def create_task_run_artifact(
        self, task_run_id: str, kind: str, data: dict, tenant_id: str = None
    ) -> str:
        """
        Create an artifact that corresponds to a specific task run

        Args:
            - task_run_id (str): the task run id
            - kind (str): the artifact kind
            - data (dict): the artifact data
            - tenant_id (str, optional): the tenant id that this artifact belongs to. Defaults
                to the tenant ID linked to the task run

        Returns:
            - str: the task run artifact ID
        """
        mutation = {
            "mutation($input: create_task_run_artifact_input!)": {
                "create_task_run_artifact(input: $input)": {"id"}
            }
        }

        result = self.graphql(
            mutation,
            variables=dict(
                input=dict(
                    task_run_id=task_run_id, kind=kind, data=data, tenant_id=tenant_id
                )
            ),
        )

        artifact_id = result.data.create_task_run_artifact.id
        if not artifact_id:
            raise ValueError("Error creating task run artifact")

        return artifact_id

    def update_task_run_artifact(self, task_run_artifact_id: str, data: dict) -> None:
        """
        Update an artifact that corresponds to a specific task run

        Args:
            - task_run_artifact_id (str): the task run artifact id
            - data (dict): the artifact data
        """
        if task_run_artifact_id is None:
            raise ValueError(
                "The ID of an existing task run artifact must be provided."
            )

        mutation = {
            "mutation($input: update_task_run_artifact_input!)": {
                "update_task_run_artifact(input: $input)": {"success"}
            }
        }

        self.graphql(
            mutation,
            variables=dict(
                input=dict(task_run_artifact_id=task_run_artifact_id, data=data)
            ),
        )

    def delete_task_run_artifact(self, task_run_artifact_id: str) -> None:
        """
        Delete an artifact that corresponds to a specific task run

        Args:
            - task_run_artifact_id (str): the task run artifact id
        """
        if task_run_artifact_id is None:
            raise ValueError(
                "The ID of an existing task run artifact must be provided."
            )

        mutation = {
            "mutation($input: delete_task_run_artifact_input!)": {
                "delete_task_run_artifact(input: $input)": {"success"}
            }
        }

        self.graphql(
            mutation,
            variables=dict(input=dict(task_run_artifact_id=task_run_artifact_id)),
        )
