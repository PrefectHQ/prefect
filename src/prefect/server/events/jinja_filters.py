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
    """Return the UI URL for the given object.

    Supports Automation, Resource, Deployment, Flow, FlowRun, TaskRun, and
    WorkQueue objects. Within a Resource, deployment, flow, flow-run, task-run,
    and work-queue are supported. If the given object is of a different type or
    an unsupported Resource `None` is returned"""
    from prefect.server.events.schemas.automations import Automation
    from prefect.server.events.schemas.events import ReceivedEvent, Resource

    url = None

    url_formats = {
        "prefect.deployment": "deployments/deployment/{id}",
        "prefect.flow": "flows/flow/{id}",
        "prefect.flow-run": "flow-runs/flow-run/{id}",
        "prefect.task-run": "flow-runs/task-run/{id}",
        "prefect.work-queue": "work-queues/work-queue/{id}",
        "prefect.work-pool": "work-pools/work-pool/{name}",
    }

    if isinstance(obj, ReceivedEvent):
        url = "/events/event/{obj.occurred.strftime('%Y-%m-%d')}/{obj.id}"
    elif isinstance(obj, Automation):
        url = f"/automations/automation/{obj.id}"
    elif isinstance(obj, Resource):
        kind, _, id = obj.id.rpartition(".")
        url_format = url_formats.get(kind)
        if url_format:
            url = url_format.format(id=id)
    elif isinstance(obj, ORMBaseModel):
        url_format = url_formats.get(model_to_kind.get(type(obj)))  # type: ignore
        if url_format:
            url = url_format.format(id=obj.id, name=getattr(obj, "name", None))

    if url:
        return urllib.parse.urljoin(PREFECT_UI_URL.value(), url)
    else:
        return None


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
