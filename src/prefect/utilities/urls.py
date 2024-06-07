import inspect
from typing import Any, Literal, Optional, Union
from uuid import UUID

from prefect import settings
from prefect._internal.schemas.bases import ObjectBaseModel
from prefect.futures import PrefectFuture
from prefect.logging.loggers import get_logger

logger = get_logger("utilities.urls")

# Whitelisted set of object names
WHITELISTED_OBJECT_NAMES = {
    "block",
    "work-pool",
    "work-queue",
    "concurrency-limit",
    "deployment",
    "flow-run",
    "flow",
    "saved-search",
    "task-run",
    "worker",
    "artifact",
    "variable",
}

URLType = Literal["ui", "api"]
RUN_TYPES = {"flow-run", "task-run"}


def convert_class_to_name(obj: Any) -> str:
    # Convert CamelCase class name to dash-separated lowercase name
    cls = obj if inspect.isclass(obj) else obj.__class__
    name = cls.__name__
    return "".join(["-" + i.lower() if i.isupper() else i for i in name]).lstrip("-")


def url_for(
    obj: Union[
        ObjectBaseModel,
        PrefectFuture,
        str,
    ],
    obj_id: Optional[Union[str, UUID]] = None,
    url_type: URLType = "ui",
    default_base_path: Optional[str] = None,
) -> str:
    """
    Returns the URL for a Prefect object.

    Pass in a supported object directly or provide an object name and ID.

    Args:
        obj (Union[ObjectBaseModel, PrefectFuture, str]):
            A Prefect object to get the URL for, or its URL name and ID.
        obj_id (Union[str, UUID], optional):
            The UUID of the object.
        url_type (Literal["ui", "api"], optional):
            Whether to return the URL for the UI (default) or API.
        default_base_path (str, optional):
            The default base path to use if no URL is found.

    Returns:
        str: The URL for the given object.

    Examples:
        url_for(my_flow_run)
        url_for(obj=my_flow_run)
        url_for("flow-run", obj_id="123e4567-e89b-12d3-a456-426614174000")
    """
    if isinstance(obj, PrefectFuture):
        name = "task-run"
    elif isinstance(obj, str):
        name = obj
    else:
        name = convert_class_to_name(obj)

    if name not in WHITELISTED_OBJECT_NAMES:
        logger.error("This object is not supported: %s", name)
        return ""

    if isinstance(obj, str) and not obj_id:
        raise ValueError(
            "If passing an object name, you must also provide an object ID."
        )

    url = (
        settings.PREFECT_UI_URL.value()
        if url_type == "ui"
        else settings.PREFECT_API_URL.value()
    )
    url = url or default_base_path

    if not url:
        logger.warning(
            f"No URL found for the Prefect {'UI' if url_type == 'ui' else 'API'}, "
            f"and no default base path provided."
        )
        return ""

    if not obj_id:
        obj_id = getattr(obj, "id", None) or getattr(obj, "task_run_id", None)

    if not obj_id:
        logger.error("No ID attribute found on the object: %s", obj)
        return ""

    if name in RUN_TYPES:
        return f"{url}/runs/{name}/{obj_id}"
    else:
        return f"{url}/{name}s/{name}/{obj_id}"
