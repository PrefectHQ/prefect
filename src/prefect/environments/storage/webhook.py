import cloudpickle
import os
import warnings

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from requests import Session
from requests.adapters import HTTPAdapter
from requests.models import Response
from requests.packages.urllib3.util.retry import Retry

from prefect.client import Secret
from prefect.environments.storage import Storage
from prefect.utilities.storage import extract_flow_from_file

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Webhook(Storage):
    """
    Webhook storage class. This class represents the Storage interface for
    Flows stored and retrieved with HTTP requests.

    This storage class takes in keyword arguments which describe how to
    create the requests, including information on how to fill in headers
    from environment variable or Prefect Cloud secrets.

     **Note**: Flows registered with this Storage option will automatically be
     labeled with `webhook-flow-storage`.

    Args:
        - build_request_kwargs (dict): Dictionary of keyword arguments to the
            function from `requests` used to store the flow. Do not supply
            `"data"` to this argument, as it will be overwritten with the
            flow's content when `.build()` is run.
        - build_request_http_method (str): HTTP method identifying the type of request
            to execute when storing the flow. For example, `"POST"` for
            `requests.post()`.
        - build_secret_config (dict): A dictionary describing how to set
            request headers from environment variables or Prefect Cloud
            secrets. See example for details on specifying this. This config
            applies to the request issued by `.build()`, and  will also be
            used for `.get_flow()` unless you explicitly set
            `get_flow_secret_config`.
        - get_flow_request_kwargs (dict): Dictionary of keyword arguments to the
            function from `requests` used to retrieve the flow.
        - get_flow_request_http_method (str): HTTP method identifying the type of
            request to execute when storing the flow. For example, `"GET"`
            for `requests.post()`.
        - get_flow_secret_config (dict): Similar to `build_secret_config`, but
            used for the request in `.get_flow()`. By default, the config
            passed to `build_secret_config` will be used for `.get_flow()`
            as well. Pass a value to this argument only if you want to use a
            different config for `.get_flow()` than the one used for
            `.build()`.
        - stored_as_script (bool, optional): boolean for specifying if the
            flow has been stored as a `.py` file. Defaults to `False`.
        - flow_script_path (str, optional): path to a local `.py` file that
            defines the flow. You must pass a value to this argument if
            `stored_as_script` is `True`. This script's content will be read
            into a string and attached to the request in `build()` as UTF-8
            encoded binary data. Similarly, `.get_flow()` expects that the
            script's contents will be returned as binary data. This path will
            not be sent to Prefect Cloud and is only needed when running
            `.build()`.
        - **kwargs (Any, optional): any additional `Storage` initialization
            options

    Passing sensitive data in headers
    ---------------------------------

    For services which require authentication, use `secret_config` to pass
    sensitive data like API keys without storing their values in this Storage
    object.

    This should be a dictionary whose keys are headers, and whose
    values indicate whether to retrieve real values from environment
    variables (`"type": "environment"`) or Prefect Cloud secrets
    (`"type": "secret"`).

    So, for example, to get an API key from an environment variable you
    can do the following

    ```python
    storage = Webhook(
        build_request_kwargs={
            "url": "some-service",
            "headers" = {
                "Content-Type" = "application/octet-stream"
            }
        },
        build_request_http_method="POST",
        ...
        ...
        build_secret_config={
            "X-Api-Key": {
                "name": "MY_COOL_ENV_VARIABLE",
                "type": "environment"
            }
        }
    )
    ```
    """

    def __init__(
        self,
        build_request_kwargs: Dict[str, Any],
        build_request_http_method: str,
        get_flow_request_kwargs: Dict[str, Any],
        get_flow_request_http_method: str,
        build_secret_config: Optional[Dict[str, Any]] = None,
        get_flow_secret_config: Optional[Dict[str, Any]] = None,
        stored_as_script: bool = False,
        flow_script_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.flows = dict()  # type: Dict[str, str]
        self._flows = dict()  # type: Dict[str, "Flow"]

        # set up logic for authenticating with Saturn back-end service
        retry_logic = HTTPAdapter(max_retries=Retry(total=3))
        self._session = Session()
        self._session.mount("http://", retry_logic)
        self._session.mount("https://", retry_logic)

        self._method_to_function = {
            "GET": self._session.get,
            "PATCH": self._session.patch,
            "POST": self._session.post,
            "PUT": self._session.put,
        }

        if build_request_http_method not in self._method_to_function.keys():
            msg = "HTTP method '{}' not recognized".format(build_request_http_method)
            self.logger.fatal(msg)
            raise RuntimeError(msg)

        if get_flow_request_http_method not in self._method_to_function.keys():
            msg = "HTTP method '{}' not recognized".format(get_flow_request_http_method)
            self.logger.fatal(msg)
            raise RuntimeError(msg)

        self.stored_as_script = stored_as_script
        self.flow_script_path = flow_script_path

        self.build_request_kwargs = build_request_kwargs
        self.build_request_http_method = build_request_http_method
        self.build_secret_config = build_secret_config or {}

        self.get_flow_request_kwargs = get_flow_request_kwargs
        self.get_flow_request_http_method = get_flow_request_http_method
        self.get_flow_secret_config = get_flow_secret_config or self.build_secret_config

        self._build_responses: Optional[Dict[str, Response]] = None

        super().__init__(stored_as_script=stored_as_script, **kwargs)

    @property
    def default_labels(self) -> List[str]:
        return ["webhook-flow-storage"]

    def get_flow(self, flow_location: str = "placeholder") -> "Flow":
        """
        Get the flow from storage. This method will call
        `cloudpickle.loads()` on the binary content of the flow, so it
        should only be called in an environment with all of the flow's
        dependencies.

        Args:
            - flow_location (str): This argument is included to comply with the
                interface used by other storage objects, but it has no meaning
                for `Webhook` storage, since `Webhook` only corresponds to a
                single flow. Ignore it.

        Raises:
            - requests.exceptions.HTTPError if getting the flow fails
        """
        self.logger.info("Retrieving flow")
        req_function = self._method_to_function[self.get_flow_request_http_method]

        get_flow_request_kwargs = deepcopy(self.get_flow_request_kwargs)
        get_flow_request_kwargs["headers"] = self._render_headers(
            headers=get_flow_request_kwargs.get("headers", {}),
            secret_config=self.get_flow_secret_config,
        )

        response = req_function(**get_flow_request_kwargs)  # type: ignore
        response.raise_for_status()

        if self.stored_as_script:
            flow_script_content = response.content.decode("utf-8")
            return extract_flow_from_file(file_contents=flow_script_content)  # type: ignore

        return cloudpickle.loads(response.content)

    def add_flow(self, flow: "Flow") -> str:
        """
        Method for adding a flow to a `Storage` object's in-memory
        storage. `.build()` will look here for flows.

        `Webhook` storage only supports a single flow per storage
        object, so this method will overwrite any existing flows
        stored in an instance.

        Args:
            - flow (Flow): a Prefect Flow to add

        Returns:
            - str: the name of the flow
        """
        self.flows = {flow.name: flow.name}
        self._flows = {flow.name: flow}
        return flow.name

    def build(self) -> "Webhook":
        """
        Build the Webhook storage object by issuing an HTTP request
        to store the flow.

        If `self.stored_as_script` is `True`, this method
        will read in the contents of `self.flow_script_path`, convert it to
        byes, and attach it to the request as `data`.

        The response from this request is stored in `._build_responses`,
        a dictionary keyed by flow name. If you are using a service where
        all the details necessary to fetch a flow cannot be known until you've
        stored it, you can do something like the following.

        ```python
        import cloudpickle
        import json
        import os
        import random
        import requests

        from prefect import task, Task, Flow
        from prefect.environments.storage import Webhook

        @task
        def random_number():
            return random.randint(0, 100)
        with Flow("test-flow") as flow:
            random_number()


        flow.storage = Webhook(
            build_request_kwargs={
                "url": "some-service/upload",
                "headers": {"Content-Type": "application/octet-stream"},
            },
            build_request_http_method="POST",
            get_flow_request_kwargs={
                "url": "some-service/download",
                "headers": {"Accept": "application/octet-stream"},
            },
            get_flow_request_http_method="GET",
        )

        flow.storage.add_flow(flow)
        res = flow.storage.build()

        # get the ID from the response
        flow_id = res._build_responses[flow.name].json()["id"]

        #  update storage
        flow.storage.get_flow_request_kwargs["url"] = f"{GET_ROUTE}/{flow_id}"
        ```

        Returns:
            - Storage: a Webhook storage object

        Raises:
            - requests.exceptions.HTTPError if pushing the flow fails
        """
        self.run_basic_healthchecks()
        self._build_responses = {}

        for flow_name, flow in self._flows.items():
            self.logger.info("Uploading flow '{}'".format(flow_name))

            data = cloudpickle.dumps(flow)
            if self.stored_as_script:

                # these checks are here in build() instead of the constructor
                # so that serialization and deserialization of flows does not fail
                if not self.flow_script_path:
                    msg = "flow_script_path must be provided if stored_as_script=True"
                    self.logger.fatal(msg)
                    raise RuntimeError(msg)

                if not os.path.isfile(self.flow_script_path):
                    msg = "file '{}' passed to flow_script_path does not exist".format(
                        self.flow_script_path
                    )
                    self.logger.fatal(msg)
                    raise RuntimeError(msg)

                with open(self.flow_script_path, "r") as f:
                    data = f.read().encode("utf-8")

            req_function = self._method_to_function[self.build_request_http_method]

            build_request_kwargs = deepcopy(self.build_request_kwargs)
            build_request_kwargs["headers"] = self._render_headers(
                headers=build_request_kwargs.get("headers", {}),
                secret_config=self.build_secret_config,
            )

            if "data" in build_request_kwargs.keys():
                msg = (
                    "'data' found in build_request_kwargs. This value is overwritten "
                    "with the flow content and should not be set directly"
                )
                self.logger.warning(msg)
                warnings.warn(msg, RuntimeWarning)
            build_request_kwargs["data"] = data

            response = req_function(**build_request_kwargs)  # type: ignore
            response.raise_for_status()

            self._build_responses[flow_name] = response
            self.logger.info("Successfully uploaded flow '{}'".format(flow_name))

        return self

    def __contains__(self, obj: Any) -> bool:
        """
        Method for determining whether an object is
        contained within this storage.
        """
        if not isinstance(obj, str):
            return False
        return obj in self.flows

    @staticmethod
    def _render_headers(
        headers: Dict[str, Any], secret_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Given a dictionary of headers, add additional headers with values
        resolved from environment variables or Prefect Cloud secrets.

        Args:
            - headers (dict): A dictionary of headers.
            - secret_config (dict): A secret config. See `help(Webhook)` for
                details on how this should be constructed.
        Raises:
            - KeyError if referencing an environment variable that does not exist
            - ValueError if referencing a Secret that does not exist
        """
        out_headers = deepcopy(headers)
        for header, details in secret_config.items():
            name = details["name"]
            if details["type"] == "environment":
                out_headers[header] = os.environ[name]
            elif details["type"] == "secret":
                out_headers[header] = Secret(name).get()
        return out_headers
