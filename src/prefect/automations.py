from typing import TYPE_CHECKING, Optional, overload
from uuid import UUID

from pydantic import Field
from typing_extensions import Self

from prefect._internal.compatibility.async_dispatch import async_dispatch
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

    async def acreate(self: Self) -> Self:
        """
        Asynchronously create a new automation.

        Examples:

        ```python
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
        created_automation = await auto_to_create.acreate()
        ```
        """
        async with get_client() as client:
            automation = AutomationCore(**self.model_dump(exclude={"id"}))
            self.id = await client.create_automation(automation=automation)
            return self

    @async_dispatch(acreate)
    def create(self: Self) -> Self:
        """
        Create a new automation.

        Examples:

        ```python
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
        ```
        """
        with get_client(sync_client=True) as client:
            automation = AutomationCore(**self.model_dump(exclude={"id"}))
            self.id = client.create_automation(automation=automation)
            return self

    async def aupdate(self: Self) -> None:
        """
        Updates an existing automation.

        Examples:

        ```python
        auto = Automation.read(id=123)
        auto.name = "new name"
        auto.update()
        ```
        """
        assert self.id is not None
        async with get_client() as client:
            automation = AutomationCore(
                **self.model_dump(exclude={"id", "owner_resource"})
            )
            await client.update_automation(automation_id=self.id, automation=automation)

    @async_dispatch(aupdate)
    def update(self: Self):
        """
        Updates an existing automation.

        Examples:


        ```python
        auto = Automation.read(id=123)
        auto.name = "new name"
        auto.update()
        ```
        """
        assert self.id is not None
        with get_client(sync_client=True) as client:
            automation = AutomationCore(
                **self.model_dump(exclude={"id", "owner_resource"})
            )
            client.update_automation(automation_id=self.id, automation=automation)

    @overload
    @classmethod
    async def aread(cls, id: UUID, name: Optional[str] = ...) -> Self: ...

    @overload
    @classmethod
    async def aread(cls, id: None = None, name: str = ...) -> Self: ...

    @classmethod
    async def aread(cls, id: Optional[UUID] = None, name: Optional[str] = None) -> Self:
        """
        Asynchronously read an automation by ID or name.

        Examples:

        ```python
        automation = await Automation.aread(name="woodchonk")
        ```

        ```python
        automation = await Automation.aread(id=UUID("b3514963-02b1-47a5-93d1-6eeb131041cb"))
        ```
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
                    return cls(**automation[0].model_dump())
                raise ValueError(f"Automation with name {name!r} not found")

    @overload
    @classmethod
    async def read(cls, id: UUID, name: Optional[str] = ...) -> Self: ...

    @overload
    @classmethod
    async def read(cls, id: None = None, name: str = ...) -> Self: ...

    @classmethod
    @async_dispatch(aread)
    def read(cls, id: Optional[UUID] = None, name: Optional[str] = None) -> Self:
        """
        Read an automation by ID or name.

        Examples:

        ```python
        automation = Automation.read(name="woodchonk")
        ```

        ```python
        automation = Automation.read(id=UUID("b3514963-02b1-47a5-93d1-6eeb131041cb"))
        ```
        """
        if id and name:
            raise ValueError("Only one of id or name can be provided")
        if not id and not name:
            raise ValueError("One of id or name must be provided")
        with get_client(sync_client=True) as client:
            if id:
                try:
                    automation = client.read_automation(automation_id=id)
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
                automation = client.read_automations_by_name(name=name)
                if len(automation) > 0:
                    return cls(**automation[0].model_dump())
                raise ValueError(f"Automation with name {name!r} not found")

    async def adelete(self: Self) -> bool:
        """
        Asynchronously delete an automation.

        Examples:

        ```python
        auto = Automation.read(id = 123)
        await auto.adelete()
        ```
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

    @async_dispatch(adelete)
    def delete(self: Self) -> bool:
        """
        Delete an automation.

        Examples:

        ```python
        auto = Automation.read(id = 123)
        auto.delete()
        ```
        """
        if self.id is None:
            raise ValueError("Can't delete an automation without an id")

        with get_client(sync_client=True) as client:
            try:
                client.delete_automation(self.id)
                return True
            except PrefectHTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return False
                raise

    async def adisable(self: Self) -> bool:
        """
        Asynchronously disable an automation.

        Raises:
            ValueError: If the automation does not have an id
            PrefectHTTPStatusError: If the automation cannot be disabled

        Example:
        ```python
        auto = await Automation.aread(id = 123)
        await auto.adisable()
        ```
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

    @async_dispatch(adisable)
    def disable(self: Self) -> bool:
        """
        Disable an automation.


        Raises:
            ValueError: If the automation does not have an id
            PrefectHTTPStatusError: If the automation cannot be disabled

        Example:
        ```python
        auto = Automation.read(id = 123)
        auto.disable()
        ```
        """
        if self.id is None:
            raise ValueError("Can't disable an automation without an id")

        with get_client(sync_client=True) as client:
            try:
                client.pause_automation(self.id)
                return True
            except PrefectHTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return False
                raise

    async def aenable(self: Self) -> bool:
        """
        Asynchronously enable an automation.

        Raises:
            ValueError: If the automation does not have an id
            PrefectHTTPStatusError: If the automation cannot be enabled

        Example:
        ```python
        auto = await Automation.aread(id = 123)
        await auto.aenable()
        ```
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

    @async_dispatch(aenable)
    def enable(self: Self) -> bool:
        """
        Enable an automation.

        Raises:
            ValueError: If the automation does not have an id
            PrefectHTTPStatusError: If the automation cannot be enabled

        Example:
        ```python
        auto = Automation.read(id = 123)
        auto.enable()
        ```
        """
        if self.id is None:
            raise ValueError("Can't enable an automation without an id")

        with get_client(sync_client=True) as client:
            try:
                client.resume_automation(self.id)
                return True
            except PrefectHTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return False
                raise
