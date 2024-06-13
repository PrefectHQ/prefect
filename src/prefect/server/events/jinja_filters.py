import urllib.parse
from typing import Any, Mapping, Optional

from jinja2 import pass_context

from prefect.server.schemas.core import (
    Deployment,
    Flow,
    FlowRun,
    TaskRun,
    WorkPool,
    WorkQueue,
)
from prefect.server.schemas.responses import WorkQueueWithStatus
from prefect.server.utilities.schemas import ORMBaseModel
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.urls import url_for

model_to_kind = {
    Deployment: "prefect.deployment",
    Flow: "prefect.flow",
    FlowRun: "prefect.flow-run",
    TaskRun: "prefect.task-run",
    WorkQueue: "prefect.work-queue",
    WorkQueueWithStatus: "prefect.work-queue",
    WorkPool: "prefect.work-pool",
}


@pass_context
def ui_url(ctx: Mapping[str, Any], obj: Any) -> Optional[str]:
    """Return the UI URL for the given object."""
    return url_for(obj, url_type="ui")


@pass_context
def ui_resource_events_url(ctx: Mapping[str, Any], obj: Any) -> Optional[str]:
    """Given a Resource or Model, return a UI link to the events page
    filtered for that resource. If an unsupported object is provided,
    return `None`.

    Currently supports Automation, Resource, Deployment, Flow, FlowRun, TaskRun, and
    WorkQueue objects. Within a Resource, deployment, flow, flow-run, task-run,
    and work-queue are supported."""
    from prefect.server.events.schemas.automations import Automation
    from prefect.server.events.schemas.events import Resource

    url = None
    url_format = "events?resource={resource_id}"

    if isinstance(obj, Automation):
        url = url_format.format(resource_id=f"prefect.automation.{obj.id}")
    elif isinstance(obj, Resource):
        kind, _, id = obj.id.rpartition(".")
        url = url_format.format(resource_id=f"{kind}.{id}")
    elif isinstance(obj, ORMBaseModel):
        kind = model_to_kind.get(type(obj))  # type: ignore

        if kind:
            url = url_format.format(resource_id=f"{kind}.{obj.id}")
    if url:
        return urllib.parse.urljoin(PREFECT_UI_URL.value(), url)
    else:
        return None


all_filters = {"ui_url": ui_url, "ui_resource_events_url": ui_resource_events_url}
