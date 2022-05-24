import datetime
import json
import random
import re
import time
import uuid
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, NamedTuple, Optional, Union
from urllib.parse import urljoin, urlparse

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
from prefect.exceptions import (
    AuthorizationError,
    ClientError,
    ObjectNotFoundError,
    VersionLockMismatchSignal,
)
from prefect.run_configs import RunConfig
from prefect.utilities.graphql import (
    EnumValue,
    GraphQLResult,
    compress,
    format_graphql_request_error,
    parse_graphql,
    with_args,
)
from prefect.utilities.logging import create_diagnostic_logger

if TYPE_CHECKING:
    import requests

    from prefect.core import Flow

JSONLike = Union[bool, dict, list, str, int, float, None]

# type definitions for GraphQL results


class TaskRunInfoResult(NamedTuple):
    # TODO: Deprecate this result in favor of `prefect.backend.TaskRun`
    id: str
    task_id: str
    task_slug: str
    version: int
    state: "prefect.engine.state.State"


class ProjectInfo(NamedTuple):
    id: str
    name: str


class FlowRunInfoResult(NamedTuple):
    # TODO: Deprecate this result in favor of `prefect.backend.FlowRun`
    id: str
    name: str
    flow_id: str
    project: ProjectInfo
    parameters: Dict[str, Any]
    context: Dict[str, Any]
    version: int
    scheduled_start_time: datetime.datetime
    state: "prefect.engine.state.State"
    task_runs: List[TaskRunInfoResult]


class Client:
    """
    Client for communication with Prefect Cloud

    If the arguments aren't specified the client initialization first checks the prefect
    configuration and if the server is not set there it checks the current context.

    Args:
        - api_server (str, optional): the URL to send all GraphQL requests to; if not
            provided, will be pulled from the current backend's `api` config
            variable
        - api_key (str, optional): a Prefect Cloud API key. If not provided, loaded
            from `config.cloud.api_key` or from the on disk cache from the
            `prefect auth` CLI
        - tenant_id (str, optional): the Prefect tenant to use. If not provided, loaded
            from `config.cloud.tenant_id` or the on disk cache from the
            `prefect auth` CLI
    """

    def __init__(
        self,
        api_server: str = None,
        api_key: str = None,
        tenant_id: str = None,
    ):
        self._attached_headers = {}  # type: Dict[str, str]
        self.logger = create_diagnostic_logger("Diagnostics")

        # Hard-code the auth filepath location
        self._auth_file = Path(prefect.context.config.home_dir).absolute() / "auth.toml"

        # Note the default is `cloud.api` which is `cloud.endpoint` or `server.endpoint`
        # depending on the value of the `backend` key
        # This must be set before `load_auth_from_disk()` can be called
        self.api_server = api_server or prefect.context.config.cloud.api

        # Load the API key
        cached_auth = self.load_auth_from_disk()
        self.api_key: Optional[str] = (
            api_key
            or prefect.context.config.cloud.get("api_key")
            or cached_auth.get("api_key")
        )

        # mypy struggles with this attribute type if not created here
        self._tenant_id: Optional[str] = None

        # Load the tenant id
        # This assignment is validated by the `Client.tenant_id` setter
        self.tenant_id: Optional[str] = (
            tenant_id  # type: ignore
            or prefect.context.config.cloud.get("tenant_id")
            or cached_auth.get("tenant_id")
        )

        # If not set at this point, when `Client.tenant_id` is accessed the default
        # tenant will be loaded and used for future requests.

    # API key authentication -----------------------------------------------------------

    def _get_auth_tenant(self) -> str:
        """
        Get the current tenant associated with the API key being used. If the client has
        a specific tenant id set, this will verify that the given tenant id is
        compatible with the API key because the tenant will be attached to the request.
        """
        if not prefect.config.backend == "cloud":

            raise ValueError(
                "Authentication is only supported for Prefect Cloud. "
                "Your backend is set to {prefect.config.backend!r}"
            )

        if not self.api_key:
            raise ValueError("You have not set an API key for authentication.")

        response = self.graphql({"query": {"auth_info": "tenant_id"}})
        tenant_id = response.get("data", {}).get("auth_info", {}).get("tenant_id", "")

        if tenant_id == "":
            raise ClientError(
                "Unexpected response from the API while querying for the default "
                f"tenant: {response}"
            )

        elif tenant_id is None:
            # If the backend returns a `None` value tenant id, it indicates that an API
            # token was passed in as an API key
            raise AuthorizationError(
                "An API token was used as an API key. There is no tenant associated "
                "with API tokens. Use an API key for authentication."
            )

        return tenant_id

    def _get_default_server_tenant(self) -> str:
        if prefect.config.backend == "server":
            response = self.graphql({"query": {"tenant": {"id"}}})
            tenants = response.get("data", {}).get("tenant", None)
            if tenants is None:
                raise ClientError(
                    f"Unexpected response from the API while querying for tenants: {response}"
                )

            if not tenants:  # The user has not created a tenant yet
                raise ClientError(
                    "Your Prefect Server instance has no tenants. "
                    "Create a tenant with `prefect server create-tenant`"
                )

            return tenants[0].id

        elif prefect.config.backend == "cloud":
            raise ValueError(
                "Default tenants are determined by authentication in Prefect Cloud. "
                "See `_get_auth_tenant` instead."
            )
        else:
            raise ValueError("Unknown backend {prefect.config.backend!r}")

    def load_auth_from_disk(self) -> Dict[str, str]:
        """
        Get the stashed `api_key` and `tenant_id` for the current `api_server` from the
        disk cache if it exists. If it does not, an empty dict is returned.

        WARNING: This will not mutate the `Client`, you must use the returned dict
                 to set `api_key` and `tenant_id`. This is
        """
        if not self._auth_file.exists():
            return {}

        return toml.loads(self._auth_file.read_text()).get(self._api_server_slug, {})

    def save_auth_to_disk(self) -> None:
        """
        Write the current auth information to the disk cache under a header for the
        current `api_server`
        """
        # Load the current contents of the entire file
        contents = (
            toml.loads(self._auth_file.read_text()) if self._auth_file.exists() else {}
        )

        # Update the data for this API server
        contents[self._api_server_slug] = {
            "api_key": self.api_key,
            "tenant_id": self._tenant_id,
        }

        # Update the file, including a comment blurb
        self._auth_file.parent.mkdir(parents=True, exist_ok=True)
        self._auth_file.write_text(
            "# This file is auto-generated and should not be manually edited\n"
            "# Update the Prefect config or use the CLI to login instead\n\n"
            + toml.dumps(contents)
        )

    @property
    def _api_server_slug(self) -> str:
        """
        A slugified version of the API server's network location, used for loading
        and saving settings for different API servers.

        This should only be relevant for the 'cloud' backend since the 'server' backend
        does not save authentication.

        This should remain stable or users will not be able to load credentials
        """
        # Parse the server to drop the protocol
        netloc = urlparse(self.api_server).netloc
        # Then return the slugified contents, falling back to the full server if it
        # could not be parsed into a net location
        return slugify(netloc or self.api_server, regex_pattern=r"[^-\.a-z0-9]+")

    @property
    def tenant_id(self) -> str:
        """
        Retrieve the current tenant id the client is interacting with.

        If it is has not been explicitly set, the default tenant id will be retrieved
        """
        if not self._tenant_id:
            if prefect.config.backend == "cloud":
                self._tenant_id = self._get_auth_tenant()
            elif prefect.config.backend == "server":
                self._tenant_id = self._get_default_server_tenant()
            else:
                raise ValueError(f"Unknown backend setting {prefect.config.backend!r}")

        if not self._tenant_id:
            raise ClientError(
                "A tenant could not be determined. Please use `prefect auth status` "
                "to get information about your authentication and file an issue."
            )

        return self._tenant_id

    @tenant_id.setter
    def tenant_id(self, tenant_id: Union[str, uuid.UUID, None]) -> None:
        if not tenant_id:
            self._tenant_id = None
            return

        if not isinstance(tenant_id, uuid.UUID):
            try:
                tenant_id = uuid.UUID(tenant_id)
            except ValueError as exc:
                raise ValueError(
                    f"The `tenant_id` must be a valid UUID. Got {tenant_id!r}."
                ) from exc

        self._tenant_id = str(tenant_id)

    # ----------------------------------------------------------------------------------

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
            raise ValueError(
                "To create a tenant with Prefect Cloud, please signup at "
                "https://cloud.prefect.io/"
            )

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
        api_key: str = None,
        retry_on_api_error: bool = True,
    ) -> dict:
        """
        Convenience function for calling the Prefect API with auth and GET request

        Args:
            - path (str): the path of the API url. For example, to GET
                http://prefect-server/v1/auth/login, path would be 'auth/login'.
            - server (str, optional): the server to send the GET request to;
                defaults to `self.api_server`
            - headers (dict, optional): Headers to pass with the request
            - params (dict): GET parameters
            - api_key (str): An api key for auth. Defaults to `client.api_key`.
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
            api_key=api_key,
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
        api_key: str = None,
        retry_on_api_error: bool = True,
    ) -> dict:
        """
        Convenience function for calling the Prefect API with auth and POST request

        Args:
            - path (str): the path of the API url. For example, to POST
                http://prefect-server/v1/auth/login, path would be 'auth/login'.
            - server (str, optional): the server to send the POST request to;
                defaults to `self.api_server`
            - headers(dict): headers to pass with the request
            - params (dict): POST parameters
            - api_key (str): An api key for auth. Defaults to `client.api_key`.
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
            api_key=api_key,
            retry_on_api_error=retry_on_api_error,
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
        variables: Mapping[str, JSONLike] = None,
        api_key: str = None,
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
            - api_key (str): An api key for auth. Defaults to `client.api_key`.
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
            api_key=api_key,
            retry_on_api_error=retry_on_api_error,
        )

        # TODO: It looks like this code is never reached because errors are raised
        #       in self._send_request by default
        if raise_on_error and "errors" in result:
            if "UNAUTHENTICATED" in str(result["errors"]):
                raise AuthorizationError(result["errors"])
            elif "Malformed Authorization header" in str(result["errors"]):
                raise AuthorizationError(result["errors"])
            elif (
                result["errors"][0].get("extensions", {}).get("code")
                == "VERSION_LOCKING_ERROR"
            ):
                raise VersionLockMismatchSignal(result["errors"])
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
        rate_limit_counter: int = 1,
    ) -> "requests.models.Response":
        import requests

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
            response = session.get(
                url,
                headers=headers,
                params=params,
                timeout=prefect.context.config.cloud.request_timeout,
            )
        elif method == "POST":
            response = session.post(
                url,
                headers=headers,
                json=params,
                timeout=prefect.context.config.cloud.request_timeout,
            )
        elif method == "DELETE":
            response = session.delete(
                url,
                headers=headers,
                timeout=prefect.context.config.cloud.request_timeout,
            )
        else:
            raise ValueError("Invalid method: {}".format(method))

        if prefect.context.config.cloud.get("diagnostics") is True:
            end_time = time.time()
            self.logger.debug(f"Response: {response.json()}")
            self.logger.debug(
                f"Request duration: {round(end_time - start_time, 4)} seconds"
            )

        # custom logic when encountering an API rate limit:
        # each time we encounter a rate limit, we sleep for
        # 3 minutes + random amount, where the random amount
        # is uniformly sampled from (0, 10 * 2 ** rate_limit_counter)
        # up to (0, 640), at which point an error is raised if the limit
        # is still being hit
        rate_limited = response.status_code == 429
        if rate_limited and rate_limit_counter <= 6:
            jitter = random.random() * 10 * (2**rate_limit_counter)
            naptime = 3 * 60 + jitter  # 180 second sleep + increasing jitter
            self.logger.debug(f"Rate limit encountered; sleeping for {naptime}s...")
            time.sleep(naptime)
            response = self._send_request(
                session=session,
                method=method,
                url=url,
                params=params,
                headers=headers,
                rate_limit_counter=rate_limit_counter + 1,
            )

        # Check if request returned a successful status
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            if response.status_code == 400 and params and "query" in params:
                # Create a custom-formatted err message for graphql errors which always
                # return a 400 status code and have "query" in the parameter dict
                try:
                    graphql_msg = format_graphql_request_error(response)
                except Exception:
                    # Fallback to a general message
                    graphql_msg = (
                        "This is likely caused by a poorly formatted GraphQL query or "
                        "mutation but the response could not be parsed for more details"
                    )
                raise ClientError(f"{exc}\n{graphql_msg}") from exc

            # Server-side and non-graphql errors will be raised without modification
            raise

        return response

    def _request(
        self,
        method: str,
        path: str,
        params: Dict[str, JSONLike] = None,
        server: str = None,
        headers: dict = None,
        api_key: str = None,
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
            - api_key (str): An api key for auth. Defaults to `client.api_key`.
            - retry_on_api_error (bool): whether the operation should be retried if the API returns
                an API_ERROR code

        Returns:
            - requests.models.Response: The response returned from the request

        Raises:
            - ClientError: on bad responses from the API
            - ValueError: if a method is specified outside of the accepted GET, POST, DELETE
            - requests.HTTPError: if a status code is returned that is not `200` or `401`
        """
        if server is None:
            server = self.api_server
        assert isinstance(server, str)  # mypy assert

        api_key = api_key or self.api_key

        # 'import requests' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import requests

        url = urljoin(server, path.lstrip("/")).rstrip("/")

        params = params or {}

        headers = headers or {}
        if api_key:
            headers["Authorization"] = "Bearer {}".format(api_key)

        if self.api_key and self._tenant_id:
            # Attach a tenant id to the headers if using an API key since it can be
            # used accross tenants. API tokens cannot and do not need this header.
            headers["X-PREFECT-TENANT-ID"] = self._tenant_id

        headers["X-PREFECT-CORE-VERSION"] = str(prefect.__version__)

        if self._attached_headers:
            headers.update(self._attached_headers)

        session = requests.Session()
        retry_total = 6
        retries = requests.packages.urllib3.util.retry.Retry(
            total=retry_total,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            # typeshed is out of date with urllib3 and missing `allowed_methods`
            allowed_methods=["DELETE", "GET", "POST"],  # type: ignore
        )
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retries))
        session.mount("http://", requests.adapters.HTTPAdapter(max_retries=retries))
        response = self._send_request(
            session=session, method=method, url=url, params=params, headers=headers
        )
        # parse the response
        try:
            json_resp = response.json()
        except JSONDecodeError as exc:
            if prefect.config.backend == "cloud" and "Authorization" not in headers:
                raise AuthorizationError(
                    "Malformed response received from Cloud - please ensure that you "
                    "are authenticated. See `prefect auth login --help`."
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

    def switch_tenant(self, tenant_slug: str = None, tenant_id: str = None) -> str:
        """
        Switch this client to the given tenant by slug or tenant id.

        The client tenant will be updated but will not be saved to disk without an
        explicit call.

        Args:
            - tenant_slug (str): the tenant's slug
            - tenant_id (str): the tenant's id

        Returns:
            - str: The id of the tenant

        Raises:
            - ValueError: if no matching tenants are found
            - ValueError: both slug and id are provided
            - AuthenticationError: if the key is not valid for the given tenant

        """

        # Validate the given tenant id -------------------------------------------------

        if tenant_slug and tenant_id:
            raise ValueError(
                "Received both `tenant_slug` and `tenant_id`; only one is allowed."
            )

        if tenant_slug:
            tenant = self.graphql(
                {
                    "query($slug: String)": {
                        "tenant(where: {slug: { _eq: $slug } })": {"id"}
                    }
                },
                variables=dict(slug=tenant_slug),
            )
            if not tenant.data.tenant:
                raise ValueError(f"No matching tenant found for slug {tenant_slug!r}.")

            tenant_id = tenant.data.tenant[0].id

        if not tenant_id:
            raise ValueError("A `tenant_id` or `tenant_slug` must be provided.")

        self.tenant_id = tenant_id
        self._get_auth_tenant()

        return self.tenant_id

    def get_available_tenants(self) -> List[Dict]:
        """
        Returns a list of available tenants.

        Returns:
            - List[Dict]: a list of dictionaries containing the id, slug, and name of
                available tenants
        """
        result = self.graphql(
            {"query": {"tenant(order_by: {slug: asc})": {"id", "slug", "name"}}},
            api_key=self.api_key,
        )
        return result.data.tenant  # type: ignore

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
        Register a new flow with Prefect Cloud.

        Args:
            - flow (Flow): a flow to register
            - project_name (str, optional): the project that should contain this flow.
            - build (bool, optional): if `True`, the flow's storage is built
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
            - ClientError: if the registration failed
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

        # verify that the serialized flow can be deserialized
        try:
            prefect.serialization.flow.FlowSchema().load(serialized_flow)
        except Exception as exc:
            raise ValueError(
                "Flow could not be deserialized successfully. Error was: {}".format(
                    repr(exc)
                )
            ) from exc

        # prepare for batched registration
        serialized_tasks = serialized_flow.pop("tasks")
        serialized_edges = serialized_flow.pop("edges")

        if compressed:
            serialized_flow = compress(serialized_flow)

        inputs = dict(
            project_id=(project[0].id if project else None),
            serialized_flow=serialized_flow,
            # we don't want to begin scheduling work until all tasks are registered
            set_schedule_active=False,
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

        # batch register tasks and edges separately
        task_mutation = {
            "mutation($input: register_tasks_input!)": {
                "register_tasks(input: $input)": {"success"}
            }
        }
        edge_mutation = {
            "mutation($input: register_edges_input!)": {
                "register_edges(input: $input)": {"success"}
            }
        }

        # tasks in batches of 500
        start = 0
        batch_size = 500
        stop = start + batch_size

        while start <= len(serialized_tasks):
            task_batch = serialized_tasks[start:stop]
            inputs = dict(
                flow_id=flow_id,
                serialized_tasks=task_batch,
            )
            self.graphql(
                task_mutation,
                variables=dict(input=inputs),
            )
            start = stop
            stop += batch_size

        # edges in batches of 500
        start = 0
        batch_size = 500
        stop = start + batch_size

        while start <= len(serialized_edges):
            edge_batch = serialized_edges[start:stop]
            inputs = dict(
                flow_id=flow_id,
                serialized_edges=edge_batch,
            )
            self.graphql(
                edge_mutation,
                variables=dict(input=inputs),
            )
            start = stop
            stop += batch_size

        # finally, if requested, we turn on the schedule
        if set_schedule_active:
            schedule_mutation = {
                "mutation($input: set_schedule_active_input!)": {
                    "set_schedule_active(input: $input)": {"success"}
                }
            }
            inputs = dict(flow_id=flow_id)
            self.graphql(
                schedule_mutation,
                variables=dict(input=inputs),
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
            if flow.run_config is not None:
                labels = sorted(flow.run_config.labels)
            else:
                labels = []
            msg = (
                f" {prefix}ID: {flow_id}\n"
                f" {prefix}Project: {project_name}\n"
                f" {prefix}Labels: {labels}"
            )
            print(msg)

        return flow_id

    def get_cloud_url(self, subdirectory: str, id: str) -> str:
        """
        Convenience method for creating Prefect Cloud URLs for a given subdirectory.

        Args:
            - subdirectory (str): the subdirectory to use (e.g., `"flow-run"`)
            - id (str): the ID of the page

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

        # Search for matching cloud API because we can't guarantee that the backend config is set
        using_cloud_api = ".prefect.io" in prefect.config.cloud.api
        tenant_slug = self.get_default_tenant_slug()

        # For various API versions parse out `api-` for direct UI link
        base_url = (
            (
                re.sub("api-", "", prefect.config.cloud.api)
                if re.search("api-", prefect.config.cloud.api)
                else re.sub("api", "cloud", prefect.config.cloud.api)
            )
            if using_cloud_api
            else prefect.config.server.ui.endpoint
        )

        return "/".join([base_url.rstrip("/"), tenant_slug, subdirectory, id])

    def get_default_tenant_slug(self) -> str:
        """
        Get the default tenant slug for the currently authenticated user

        Returns:
            - str: the slug of the current default tenant for this user
        """
        res = self.graphql({"query": {"tenant": {"id", "slug"}}})

        tenants = res["data"]["tenant"]
        for tenant in tenants:
            # Return the slug if it matches the current tenant id
            if tenant.id == self.tenant_id:
                return tenant.slug

        raise ValueError(
            f"Failed to find current tenant {self.tenant_id!r} in result {res}"
        )

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
                        tenant_id=self.tenant_id,
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

    def delete_project(self, project_name: str) -> bool:
        """
        Delete a project

        Args:
            - project_name (str): the project that should be created

        Returns:
            - bool: True if project is deleted else False
        Raises:
            - ValueError: if the project is None or doesn't exist
        """

        if project_name is None:
            raise TypeError("'project_name' is a required field for deleting a project")

        query_project = {
            "query": {
                with_args("project", {"where": {"name": {"_eq": project_name}}}): {
                    "id": True
                }
            }
        }

        project = self.graphql(query_project).data.project

        if not project:
            raise ValueError("Project {} not found.".format(project_name))

        project_mutation = {
            "mutation($input: delete_project_input!)": {
                "delete_project(input: $input)": {"success"}
            }
        }

        delete_project = self.graphql(
            project_mutation, variables=dict(input=dict(project_id=project[0].id))
        )

        return delete_project.data.delete_project.success

    def create_flow_run(
        self,
        flow_id: str = None,
        context: dict = None,
        parameters: dict = None,
        run_config: RunConfig = None,
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
            - run_config (RunConfig, optional): a run-config to use for this
                flow run, overriding any existing flow settings.
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

        inputs = {}  # type: Dict[str, Any]
        if flow_id:
            inputs["flow_id"] = flow_id
        else:
            inputs["version_group_id"] = version_group_id

        if parameters is not None:
            inputs["parameters"] = parameters
        if run_config is not None:
            inputs["run_config"] = run_config.serialize()
        if labels is not None:
            inputs["labels"] = labels
        if context is not None:
            inputs["context"] = context
        if idempotency_key is not None:
            inputs["idempotency_key"] = idempotency_key
        if scheduled_start_time is not None:
            inputs["scheduled_start_time"] = scheduled_start_time.isoformat()
        if run_name is not None:
            inputs["flow_run_name"] = run_name
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
        from prefect.engine.state import State

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
                    "flow": {"project": {"name": True, "id": True}},
                }
            }
        }
        result = self.graphql(query).data.flow_run_by_pk  # type: ignore
        if result is None:
            raise ClientError('Flow run ID not found: "{}"'.format(flow_run_id))

        task_runs = [
            TaskRunInfoResult(
                id=tr.id,
                version=tr.version,
                task_id=tr.task.id,
                task_slug=tr.task.slug,
                state=State.deserialize(tr.serialized_state)
                if tr.serialized_state
                else prefect.engine.state.Pending(),
            )
            for tr in result.task_runs
        ]

        state = (
            prefect.engine.state.State.deserialize(result.serialized_state)
            if result.serialized_state
            else prefect.engine.state.Pending()
        )

        return FlowRunInfoResult(
            id=result.id,
            name=result.name,
            flow_id=result.flow_id,
            version=result.version,
            task_runs=task_runs,
            state=state,
            scheduled_start_time=pendulum.parse(result.scheduled_start_time),  # type: ignore
            project=ProjectInfo(
                id=result.flow.project.id, name=result.flow.project.name
            ),
            parameters=(
                {} if result.parameters is None else result.parameters.to_dict()
            ),
            context=({} if result.context is None else result.context.to_dict()),
        )

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
        self.graphql(
            mutation,
            raise_on_error=True,
            headers={"X-PREFECT-HEARTBEAT-ID": flow_run_id},
        )

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

        if not flow_run:
            raise ObjectNotFoundError(f"Flow run {flow_run_id!r} not found.")

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
                    "get_or_create_task_run_info",
                    {
                        "input": {
                            "flow_run_id": flow_run_id,
                            "task_id": task_id,
                            "map_index": -1 if map_index is None else map_index,
                        }
                    },
                ): {
                    "id": True,
                    "version": True,
                    "serialized_state": True,
                }
            }
        }
        result = self.graphql(mutation)  # type: Any

        if result is None:
            raise ClientError("Failed to create task run.")

        task_run_info = result.data.get_or_create_task_run_info

        state = (
            prefect.engine.state.State.deserialize(task_run_info.serialized_state)
            if task_run_info.serialized_state
            else prefect.engine.state.Pending()
        )

        return TaskRunInfoResult(
            id=task_run_info.id,
            task_id=task_id,
            task_slug="",
            version=task_run_info.version,
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
                with_args("get_task_run_info", {"task_run_id": task_run_id}): {
                    "serialized_state": True,
                }
            }
        }

        task_run = self.graphql(query).data.get_task_run_info

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
                    tenant_id=self.tenant_id,
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
