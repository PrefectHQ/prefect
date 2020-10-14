import cloudpickle
import os
import string
import warnings

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional

from requests import Session
from requests.adapters import HTTPAdapter
from requests.models import Response
from requests.packages.urllib3.util.retry import Retry

from prefect.client import Secret
from prefect.environments.storage import Storage
from prefect.utilities.storage import extract_flow_from_file

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class _SecretMapping(Mapping):
    """
    Magic mapping. When `__getitem__()` is called
    to look for the value of a `key`, this mapping will
    try to resolve it from the environment and, if not found
    there, from `prefect` secrets.

    Raises:
        - RuntimeError if the key you're looking for isn't found
    """

    def __getitem__(self, key: str) -> str:
        out = os.getenv(key, None)  # type: ignore
        if out is None:
            try:
                out = Secret(key).get()
            except ValueError as exc:
                msg = (
                    "Template value '{}' does not refer to an "
                    "environment variable or Prefect secret."
                )
                raise RuntimeError(msg.format(key)) from exc
        return out  # type: ignore

    def __iter__(self) -> Iterator[Any]:
        return iter([])

    def __len__(self) -> int:
        return 0


_mapping = _SecretMapping()


def _render_dict(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace string elements in a dictionary with environment variables
    or Prefect secrets.

    This method will look through all string values (not keys) of a dictionary,
    recursively, for template string. When it encounters a string like
    `${abc}`, it will first try to replace it with the value of environment
    variable `abc`. If environment variable `abc` is not defined, it will try
    to replace it with `prefect` secret `abc`. If that is also not found,
    raises a `KeyError`.

    Args:
        - input_dict (Dict[str, Any]): A dictionary that may contain
            template strings.

    Returns:
        - A dictionary with template strings replaced by the literal values of
            environment variables or Prefect secrets

    Raises:
        - RuntimeError if any template value cannot be found in the environment
            or `prefect` secrets
    """
    output_dict = {}

    for key, value in input_dict.items():
        if isinstance(value, str):
            new_value = string.Template(value).substitute(_mapping)
            output_dict[key] = new_value
        elif isinstance(value, dict):
            output_dict[key] = _render_dict(value)  # type: ignore
        else:
            output_dict[key] = value

    return output_dict


class Webhook(Storage):
    """
    Webhook storage class. This class represents the Storage interface for
    Flows stored and retrieved with HTTP requests.

    This storage class takes in keyword arguments which describe how to
    create the requests. These arguments' values can contain template
    strings which will be filled in dynamically from environment variables
    or Prefect secrets.

     **Note**: Flows registered with this Storage option will automatically be
     labeled with `webhook-flow-storage`.

    Args:
        - build_request_kwargs (dict): Dictionary of keyword arguments to the
            function from `requests` used to store the flow. Do not supply
            `"data"` to this argument, as it will be overwritten with the
            flow's content when `.build()` is run.
        - build_request_http_method (str): HTTP method identifying the type of
            request to execute when storing the flow. For example, `"POST"` for
            `requests.post()`.
        - get_flow_request_kwargs (dict): Dictionary of keyword arguments to
            the function from `requests` used to retrieve the flow.
        - get_flow_request_http_method (str): HTTP method identifying the type
            of request to execute when storing the flow. For example, `"GET"`
            for `requests.post()`.
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

    Including Sensitive Data

    ------------------------

    It is common for requests used with this storage to need access to
    sensitive information.

    For example:

    - auth tokens passed in headers like `X-Api-Key` or `Authorization`
    - auth information passed in to URL as query parameters

    `Webhook` storage supports the inclusion of such sensitive information
    with templating. Any of the string values passed to
    `build_flow_request_kwargs` or `get_flow_request_kwargs` can include
    template strings like `${SOME_VARIABLE}`. When `.build()` or `.get_flow()`
    is run, such values will be replaced with the value of environment
    variables or, when no matching environment variable is found, Prefect
    Secrets.

    So, for example, to get an API key from an environment variable you
    can do the following

    ```python
    storage = Webhook(
        build_request_kwargs={
            "url": "some-service/upload",
            "headers" = {
                "Content-Type" = "application/octet-stream",
                "X-Api-Key": "${MY_COOL_ENV_VARIABLE}"
            }
        },
        build_request_http_method="POST",
    )
    ```

    You can also take advantage of this templating when only part
    of a string needs to be replaced.

    ```python
    storage = Webhook(
        get_flow_request_kwargs={
            "url": "some-service/download",
            "headers" = {
                "Accept" = "application/octet-stream",
                "Authorization": "Bearer ${MY_COOL_ENV_VARIABLE}"
            }
        },
        build_request_http_method="POST",
    )
    ```
    """

    def __init__(
        self,
        build_request_kwargs: Dict[str, Any],
        build_request_http_method: str,
        get_flow_request_kwargs: Dict[str, Any],
        get_flow_request_http_method: str,
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
            self.logger.critical(msg)
            raise RuntimeError(msg)

        if get_flow_request_http_method not in self._method_to_function.keys():
            msg = "HTTP method '{}' not recognized".format(get_flow_request_http_method)
            self.logger.critical(msg)
            raise RuntimeError(msg)

        self.stored_as_script = stored_as_script
        self.flow_script_path = flow_script_path

        self.build_request_kwargs = build_request_kwargs
        self.build_request_http_method = build_request_http_method

        self.get_flow_request_kwargs = get_flow_request_kwargs
        self.get_flow_request_http_method = get_flow_request_http_method

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

        get_flow_request_kwargs = _render_dict(self.get_flow_request_kwargs)

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
                # so that serialization and deserialization of flows doesnot fail
                if not self.flow_script_path:
                    msg = "flow_script_path must be provided if stored_as_script=True"
                    self.logger.critical(msg)
                    raise RuntimeError(msg)

                if not os.path.isfile(self.flow_script_path):
                    msg = "file '{}' passed to flow_script_path does not exist".format(
                        self.flow_script_path
                    )
                    self.logger.critical(msg)
                    raise RuntimeError(msg)

                with open(self.flow_script_path, "r") as f:
                    data = f.read().encode("utf-8")

            req_function = self._method_to_function[self.build_request_http_method]

            build_request_kwargs = _render_dict(self.build_request_kwargs)

            if "data" in build_request_kwargs.keys():
                msg = (
                    "'data' found in build_request_kwargs. This value is "
                    "overwritten with the flow content and should not "
                    "be set directly"
                )
                self.logger.warning(msg)
                warnings.warn(msg, RuntimeWarning, stacklevel=2)
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
