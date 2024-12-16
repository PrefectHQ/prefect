from importlib import import_module

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas.events import (
        Event,
        ReceivedEvent,
        Resource,
        RelatedResource,
        ResourceSpecification,
    )
    from .schemas.automations import (
        Automation,
        AutomationCore,
        Posture,
        TriggerTypes,
        Trigger,
        ResourceTrigger,
        EventTrigger,
        MetricTrigger,
        MetricTriggerOperator,
        MetricTriggerQuery,
        CompositeTrigger,
        CompoundTrigger,
        SequenceTrigger,
    )
    from .schemas.deployment_triggers import (
        DeploymentTriggerTypes,
        DeploymentEventTrigger,
        DeploymentMetricTrigger,
        DeploymentCompoundTrigger,
        DeploymentSequenceTrigger,
    )
    from .actions import (
        ActionTypes,
        Action,
        DoNothing,
        RunDeployment,
        PauseDeployment,
        ResumeDeployment,
        ChangeFlowRunState,
        CancelFlowRun,
        SuspendFlowRun,
        CallWebhook,
        SendNotification,
        PauseWorkPool,
        ResumeWorkPool,
        PauseWorkQueue,
        ResumeWorkQueue,
        PauseAutomation,
        ResumeAutomation,
        DeclareIncident,
    )
    from .clients import get_events_client, get_events_subscriber
    from .utilities import emit_event

__all__ = [
    "Event",
    "ReceivedEvent",
    "Resource",
    "RelatedResource",
    "ResourceSpecification",
    "Automation",
    "AutomationCore",
    "Posture",
    "TriggerTypes",
    "Trigger",
    "ResourceTrigger",
    "EventTrigger",
    "MetricTrigger",
    "MetricTriggerOperator",
    "MetricTriggerQuery",
    "CompositeTrigger",
    "CompoundTrigger",
    "SequenceTrigger",
    "DeploymentTriggerTypes",
    "DeploymentEventTrigger",
    "DeploymentMetricTrigger",
    "DeploymentCompoundTrigger",
    "DeploymentSequenceTrigger",
    "ActionTypes",
    "Action",
    "DoNothing",
    "RunDeployment",
    "PauseDeployment",
    "ResumeDeployment",
    "ChangeFlowRunState",
    "CancelFlowRun",
    "SuspendFlowRun",
    "CallWebhook",
    "SendNotification",
    "PauseWorkPool",
    "ResumeWorkPool",
    "PauseWorkQueue",
    "ResumeWorkQueue",
    "PauseAutomation",
    "ResumeAutomation",
    "DeclareIncident",
    "emit_event",
    "get_events_client",
    "get_events_subscriber",
]
_public_api: dict[str, tuple[str, str]] = {
    "Event": (__spec__.parent, ".schemas.events"),
    "ReceivedEvent": (__spec__.parent, ".schemas.events"),
    "Resource": (__spec__.parent, ".schemas.events"),
    "RelatedResource": (__spec__.parent, ".schemas.events"),
    "ResourceSpecification": (__spec__.parent, ".schemas.events"),
    "Automation": (__spec__.parent, ".schemas.automations"),
    "AutomationCore": (__spec__.parent, ".schemas.automations"),
    "Posture": (__spec__.parent, ".schemas.automations"),
    "TriggerTypes": (__spec__.parent, ".schemas.automations"),
    "Trigger": (__spec__.parent, ".schemas.automations"),
    "ResourceTrigger": (__spec__.parent, ".schemas.automations"),
    "EventTrigger": (__spec__.parent, ".schemas.automations"),
    "MetricTrigger": (__spec__.parent, ".schemas.automations"),
    "MetricTriggerOperator": (__spec__.parent, ".schemas.automations"),
    "MetricTriggerQuery": (__spec__.parent, ".schemas.automations"),
    "CompositeTrigger": (__spec__.parent, ".schemas.automations"),
    "CompoundTrigger": (__spec__.parent, ".schemas.automations"),
    "SequenceTrigger": (__spec__.parent, ".schemas.automations"),
    "DeploymentTriggerTypes": (__spec__.parent, ".schemas.deployment_triggers"),
    "DeploymentEventTrigger": (__spec__.parent, ".schemas.deployment_triggers"),
    "DeploymentMetricTrigger": (__spec__.parent, ".schemas.deployment_triggers"),
    "DeploymentCompoundTrigger": (__spec__.parent, ".schemas.deployment_triggers"),
    "DeploymentSequenceTrigger": (__spec__.parent, ".schemas.deployment_triggers"),
    "ActionTypes": (__spec__.parent, ".actions"),
    "Action": (__spec__.parent, ".actions"),
    "DoNothing": (__spec__.parent, ".actions"),
    "RunDeployment": (__spec__.parent, ".actions"),
    "PauseDeployment": (__spec__.parent, ".actions"),
    "ResumeDeployment": (__spec__.parent, ".actions"),
    "ChangeFlowRunState": (__spec__.parent, ".actions"),
    "CancelFlowRun": (__spec__.parent, ".actions"),
    "SuspendFlowRun": (__spec__.parent, ".actions"),
    "CallWebhook": (__spec__.parent, ".actions"),
    "SendNotification": (__spec__.parent, ".actions"),
    "PauseWorkPool": (__spec__.parent, ".actions"),
    "ResumeWorkPool": (__spec__.parent, ".actions"),
    "PauseWorkQueue": (__spec__.parent, ".actions"),
    "ResumeWorkQueue": (__spec__.parent, ".actions"),
    "PauseAutomation": (__spec__.parent, ".actions"),
    "ResumeAutomation": (__spec__.parent, ".actions"),
    "DeclareIncident": (__spec__.parent, ".actions"),
    "emit_event": (__spec__.parent, ".utilities"),
    "get_events_client": (__spec__.parent, ".clients"),
    "get_events_subscriber": (__spec__.parent, ".clients"),
}


def __getattr__(attr_name: str) -> object:
    try:
        dynamic_attr = _public_api.get(attr_name)
        if dynamic_attr is None:
            return import_module(f".{attr_name}", package=__name__)

        package, module_name = dynamic_attr

        if module_name == "__module__":
            return import_module(f".{attr_name}", package=package)
        else:
            module = import_module(module_name, package=package)
            return getattr(module, attr_name)
    except ModuleNotFoundError as ex:
        if TYPE_CHECKING:
            assert ex.name is not None
        module, _, attribute = ex.name.rpartition(".")
        raise AttributeError(f"module {module} has no attribute {attribute}") from ex
