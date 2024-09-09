import inspect
import ipaddress
import socket
import urllib.parse
from typing import TYPE_CHECKING, Any, Literal, Optional, Union
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel

from prefect import settings
from prefect.logging.loggers import get_logger

if TYPE_CHECKING:
    from prefect.blocks.core import Block
    from prefect.events.schemas.automations import Automation
    from prefect.events.schemas.events import ReceivedEvent, Resource
    from prefect.futures import PrefectFuture
    from prefect.variables import Variable

logger = get_logger("utilities.urls")

# The following objects are excluded from UI URL generation because we lack a
# directly-addressable URL:
#   worker
#   artifact
#   variable
#   saved-search
UI_URL_FORMATS = {
    "flow": "flows/flow/{obj_id}",
    "flow-run": "runs/flow-run/{obj_id}",
    "task-run": "runs/task-run/{obj_id}",
    "block": "blocks/block/{obj_id}",
    "block-document": "blocks/block/{obj_id}",
    "work-pool": "work-pools/work-pool/{obj_id}",
    "work-queue": "work-queues/work-queue/{obj_id}",
    "concurrency-limit": "concurrency-limits/concurrency-limit/{obj_id}",
    "deployment": "deployments/deployment/{obj_id}",
    "automation": "automations/automation/{obj_id}",
    "received-event": "events/event/{occurred}/{obj_id}",
}

# The following objects are excluded from API URL generation because we lack a
# directly-addressable URL:
#   worker
#   artifact
#   saved-search
#   received-event
API_URL_FORMATS = {
    "flow": "flows/{obj_id}",
    "flow-run": "flow_runs/{obj_id}",
    "task-run": "task_runs/{obj_id}",
    "variable": "variables/name/{obj_id}",
    "block": "blocks/{obj_id}",
    "work-pool": "work_pools/{obj_id}",
    "work-queue": "work_queues/{obj_id}",
    "concurrency-limit": "concurrency_limits/{obj_id}",
    "deployment": "deployments/{obj_id}",
    "automation": "automations/{obj_id}",
}

URLType = Literal["ui", "api"]
RUN_TYPES = {"flow-run", "task-run"}


def validate_restricted_url(url: str):
    """
    Validate that the provided URL is safe for outbound requests.  This prevents
    attacks like SSRF (Server Side Request Forgery), where an attacker can make
    requests to internal services (like the GCP metadata service, localhost addresses,
    or in-cluster Kubernetes services)

    Args:
        url: The URL to validate.

    Raises:
        ValueError: If the URL is a restricted URL.
    """

    try:
        parsed_url = urlparse(url)
    except ValueError:
        raise ValueError(f"{url!r} is not a valid URL.")

    if parsed_url.scheme not in ("http", "https"):
        raise ValueError(
            f"{url!r} is not a valid URL.  Only HTTP and HTTPS URLs are allowed."
        )

    hostname = parsed_url.hostname or ""

    # Remove IPv6 brackets if present
    if hostname.startswith("[") and hostname.endswith("]"):
        hostname = hostname[1:-1]

    if not hostname:
        raise ValueError(f"{url!r} is not a valid URL.")

    try:
        ip_address = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_address)
    except socket.gaierror:
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            raise ValueError(f"{url!r} is not a valid URL.  It could not be resolved.")

    if ip.is_private:
        raise ValueError(
            f"{url!r} is not a valid URL.  It resolves to the private address {ip}."
        )


def convert_class_to_name(obj: Any) -> str:
    """
    Convert CamelCase class name to dash-separated lowercase name
    """
    cls = obj if inspect.isclass(obj) else obj.__class__
    name = cls.__name__
    return "".join(["-" + i.lower() if i.isupper() else i for i in name]).lstrip("-")


def url_for(
    obj: Union[
        "PrefectFuture",
        "Block",
        "Variable",
        "Automation",
        "Resource",
        "ReceivedEvent",
        BaseModel,
        str,
    ],
    obj_id: Optional[Union[str, UUID]] = None,
    url_type: URLType = "ui",
    default_base_url: Optional[str] = None,
) -> Optional[str]:
    """
    Returns the URL for a Prefect object.

    Pass in a supported object directly or provide an object name and ID.

    Args:
        obj (Union[PrefectFuture, Block, Variable, Automation, Resource, ReceivedEvent, BaseModel, str]):
            A Prefect object to get the URL for, or its URL name and ID.
        obj_id (Union[str, UUID], optional):
            The UUID of the object.
        url_type (Literal["ui", "api"], optional):
            Whether to return the URL for the UI (default) or API.
        default_base_url (str, optional):
            The default base URL to use if no URL is configured.

    Returns:
        Optional[str]: The URL for the given object or None if the object is not supported.

    Examples:
        url_for(my_flow_run)
        url_for(obj=my_flow_run)
        url_for("flow-run", obj_id="123e4567-e89b-12d3-a456-426614174000")
    """
    from prefect.blocks.core import Block
    from prefect.events.schemas.automations import Automation
    from prefect.events.schemas.events import ReceivedEvent, Resource
    from prefect.futures import PrefectFuture

    if isinstance(obj, PrefectFuture):
        name = "task-run"
    elif isinstance(obj, Block):
        name = "block"
    elif isinstance(obj, Automation):
        name = "automation"
    elif isinstance(obj, ReceivedEvent):
        name = "received-event"
    elif isinstance(obj, Resource):
        if obj.id.startswith("prefect."):
            name = obj.id.split(".")[1]
        else:
            logger.debug(f"No URL known for resource with ID: {obj.id}")
            return None
    elif isinstance(obj, str):
        name = obj
    else:
        name = convert_class_to_name(obj)

    # Can't do an isinstance check here because the client build
    # doesn't have access to that server schema.
    if name == "work-queue-with-status":
        name = "work-queue"

    if url_type != "ui" and url_type != "api":
        raise ValueError(f"Invalid URL type: {url_type}. Use 'ui' or 'api'.")

    if url_type == "ui" and name not in UI_URL_FORMATS:
        logger.debug("No UI URL known for this object: %s", name)
        return None
    elif url_type == "api" and name not in API_URL_FORMATS:
        logger.debug("No API URL known for this object: %s", name)
        return None

    if isinstance(obj, str) and not obj_id:
        raise ValueError(
            "If passing an object name, you must also provide an object ID."
        )

    base_url = (
        settings.PREFECT_UI_URL.value()
        if url_type == "ui"
        else settings.PREFECT_API_URL.value()
    )
    base_url = base_url or default_base_url

    if not base_url:
        logger.debug(
            f"No URL found for the Prefect {'UI' if url_type == 'ui' else 'API'}, "
            f"and no default base path provided."
        )
        return None

    if not obj_id:
        # We treat PrefectFuture as if it was the underlying task run,
        # so we need to check the object type here instead of name.
        if isinstance(obj, PrefectFuture):
            obj_id = getattr(obj, "task_run_id", None)
        elif name == "block":
            # Blocks are client-side objects whose API representation is a
            # BlockDocument.
            obj_id = obj._block_document_id
        elif name in ("variable", "work-pool"):
            obj_id = obj.name
        elif isinstance(obj, Resource):
            obj_id = obj.id.rpartition(".")[2]
        else:
            obj_id = getattr(obj, "id", None)
        if not obj_id:
            logger.debug(
                "An ID is required to build a URL, but object did not have one: %s", obj
            )
            return ""

    url_format = (
        UI_URL_FORMATS.get(name) if url_type == "ui" else API_URL_FORMATS.get(name)
    )

    if isinstance(obj, ReceivedEvent):
        url = url_format.format(
            occurred=obj.occurred.strftime("%Y-%m-%d"), obj_id=obj_id
        )
    else:
        url = url_format.format(obj_id=obj_id)

    if not base_url.endswith("/"):
        base_url += "/"
    return urllib.parse.urljoin(base_url, url)
