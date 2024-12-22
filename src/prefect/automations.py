from typing import TYPE_CHECKING, Optional, overload
from uuid import UUID

from pydantic import Field
from typing_extensions import Self

from prefect.client.orchestration import get_client
from prefect.events.actions import (
    CallWebhook,
    CancelFlowRun,
    ChangeFlowRunState,
    DeclareIncident,
    DoNothing,
    PauseAutomation,
    PauseDeployment,
    PauseWorkPool,
    PauseWorkQueue,
    ResumeAutomation,
    ResumeDeployment,
    ResumeWorkPool,
    ResumeWorkQueue,
    RunDeployment,
    SendNotification,
    SuspendFlowRun,
)
from prefect.events.schemas.automations import (
    AutomationCore,
    CompositeTrigger,
    CompoundTrigger,
    EventTrigger,
    MetricTrigger,
    MetricTriggerOperator,
    MetricTriggerQuery,
    Posture,
    PrefectMetric,
    ResourceSpecification,
    ResourceTrigger,
    SequenceTrigger,
    Trigger,
)
from prefect.exceptions import PrefectHTTPStatusError
from prefect.utilities.asyncutils import sync_compatible

__all__ = [
    "AutomationCore",
    "EventTrigger",
    "ResourceTrigger",
    "Posture",
    "Trigger",
    "ResourceSpecification",
    "MetricTriggerOperator",
    "MetricTrigger",
    "PrefectMetric",
    "CompositeTrigger",
    "SequenceTrigger",
    "CompoundTrigger",
    "MetricTriggerQuery",
    # action types
    "DoNothing",
    "RunDeployment",
    "PauseDeployment",
    "ResumeDeployment",
    "CancelFlowRun",
    "ChangeFlowRunState",
    "PauseWorkQueue",
    "ResumeWorkQueue",
    "SendNotification",
    "CallWebhook",
    "PauseAutomation",
    "ResumeAutomation",
    "SuspendFlowRun",
    "PauseWorkPool",
    "ResumeWorkPool",
    "DeclareIncident",
]


class Automation(AutomationCore):
    id: Optional[UUID] = Field(default=None, description="The ID of this automation")

    @sync_compatible
    async def create(self: Self) -> Self:
        """
        Create a new automation.

        auto_to_create = Automation(
            name="woodchonk",
            trigger=EventTrigger(
                expect={"animal.walked"},
                match={
                    "genus": "Marmota",
                    "species": "monax",
                },
                posture="Reactive",
                threshold=3,
                within=timedelta(seconds=10),
            ),
            actions=[CancelFlowRun()]
        )
        created_automation = auto_to_create.create()
        """
        async with get_client() as client:
            automation = AutomationCore(**self.model_dump(exclude={"id"}))
            self.id = await client.create_automation(automation=automation)
            return self

    @sync_compatible
    async def update(self: Self):
        """
        Updates an existing automation.
        auto = Automation.read(id=123)
        auto.name = "new name"
        auto.update()
        """
        assert self.id is not None
        async with get_client() as client:
            automation = AutomationCore(
                **self.model_dump(exclude={"id", "owner_resource"})
            )
            await client.update_automation(automation_id=self.id, automation=automation)

    @overload
    @classmethod
    async def read(cls, id: UUID, name: Optional[str] = ...) -> Self:
        ...

    @overload
    @classmethod
    async def read(cls, id: None = None, name: str = ...) -> Optional[Self]:
        ...

    @classmethod
    @sync_compatible
    async def read(
        cls, id: Optional[UUID] = None, name: Optional[str] = None
    ) -> Optional[Self]:
        """
        Read an automation by ID or name.
        automation = Automation.read(name="woodchonk")

        or

        automation = Automation.read(id=UUID("b3514963-02b1-47a5-93d1-6eeb131041cb"))
        """
        if id and name:
            raise ValueError("Only one of id or name can be provided")
        if not id and not name:
            raise ValueError("One of id or name must be provided")
        async with get_client() as client:
            if id:
                try:
                    automation = await client.read_automation(automation_id=id)
                except PrefectHTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        raise ValueError(f"Automation with ID {id!r} not found")
                    raise
                if automation is None:
                    raise ValueError(f"Automation with ID {id!r} not found")
                return cls(**automation.model_dump())
            else:
                if TYPE_CHECKING:
                    assert name is not None
                automation = await client.read_automations_by_name(name=name)
                if len(automation) > 0:
                    return cls(**automation[0].model_dump()) if automation else None
                else:
                    raise ValueError(f"Automation with name {name!r} not found")

    @sync_compatible
    async def delete(self: Self) -> bool:
        """
        auto = Automation.read(id = 123)
        auto.delete()
        """
        if self.id is None:
            raise ValueError("Can't delete an automation without an id")

        async with get_client() as client:
            try:
                await client.delete_automation(self.id)
                return True
            except PrefectHTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return False
                raise

    @sync_compatible
    async def disable(self: Self) -> bool:
        """
        Disable an automation.
        auto = Automation.read(id = 123)
        auto.disable()
        """
        if self.id is None:
            raise ValueError("Can't disable an automation without an id")

        async with get_client() as client:
            try:
                await client.pause_automation(self.id)
                return True
            except PrefectHTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return False
                raise

    @sync_compatible
    async def enable(self: Self) -> bool:
        """
        Enable an automation.
        auto = Automation.read(id = 123)
        auto.enable()
        """
        if self.id is None:
            raise ValueError("Can't enable an automation without an id")

        async with get_client() as client:
            try:
                await client.resume_automation(self.id)
                return True
            except PrefectHTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return False
                raise
