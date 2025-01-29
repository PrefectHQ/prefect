from __future__ import annotations

from typing import TYPE_CHECKING

from httpx import HTTPStatusError

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
from prefect.exceptions import ObjectNotFound

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.events.schemas.automations import Automation, AutomationCore


class AutomationClient(BaseClient):
    def create_automation(self, automation: "AutomationCore") -> "UUID":
        """Creates an automation in Prefect Cloud."""
        response = self.request(
            "POST",
            "/automations/",
            json=automation.model_dump(mode="json"),
        )
        from uuid import UUID

        return UUID(response.json()["id"])

    def update_automation(
        self, automation_id: "UUID", automation: "AutomationCore"
    ) -> None:
        """Updates an automation in Prefect Cloud."""
        response = self.request(
            "PUT",
            "/automations/{id}",
            path_params={"id": automation_id},
            json=automation.model_dump(mode="json", exclude_unset=True),
        )
        response.raise_for_status()

    def read_automations(self) -> list["Automation"]:
        response = self.request("POST", "/automations/filter")
        response.raise_for_status()
        from prefect.events.schemas.automations import Automation

        return Automation.model_validate_list(response.json())

    def find_automation(self, id_or_name: "str | UUID") -> "Automation | None":
        from uuid import UUID

        if isinstance(id_or_name, str):
            name = id_or_name
            try:
                id = UUID(id_or_name)
            except ValueError:
                id = None
        else:
            id = id_or_name
            name = str(id)

        if id:
            try:
                automation = self.read_automation(id)
                return automation
            except HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise ObjectNotFound(http_exc=e) from e

        automations = self.read_automations()

        # Look for it by an exact name
        for automation in automations:
            if automation.name == name:
                return automation

        # Look for it by a case-insensitive name
        for automation in automations:
            if automation.name.lower() == name.lower():
                return automation

        return None

    def read_automation(self, automation_id: "UUID | str") -> "Automation | None":
        response = self.request(
            "GET", "/automations/{id}", path_params={"id": automation_id}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        from prefect.events.schemas.automations import Automation

        return Automation.model_validate(response.json())

    def read_automations_by_name(self, name: str) -> list["Automation"]:
        """
        Query the Prefect API for an automation by name. Only automations matching the provided name will be returned.

        Args:
            name: the name of the automation to query

        Returns:
            a list of Automation model representations of the automations
        """
        from prefect.client.schemas.sorting import AutomationSort
        from prefect.events.filters import (
            AutomationFilter,
            AutomationFilterName,
        )

        automation_filter = AutomationFilter(name=AutomationFilterName(any_=[name]))

        response = self.request(
            "POST",
            "/automations/filter",
            json={
                "sort": AutomationSort.UPDATED_DESC,
                "automations": automation_filter.model_dump(mode="json")
                if automation_filter
                else None,
            },
        )

        response.raise_for_status()
        from prefect.events.schemas.automations import Automation

        return Automation.model_validate_list(response.json())

    def pause_automation(self, automation_id: "UUID") -> None:
        response = self.request(
            "PATCH",
            "/automations/{id}",
            path_params={"id": automation_id},
            json={"enabled": False},
        )
        response.raise_for_status()

    def resume_automation(self, automation_id: "UUID") -> None:
        response = self.request(
            "PATCH",
            "/automations/{id}",
            path_params={"id": automation_id},
            json={"enabled": True},
        )
        response.raise_for_status()

    def delete_automation(self, automation_id: "UUID") -> None:
        response = self.request(
            "DELETE",
            "/automations/{id}",
            path_params={"id": automation_id},
        )
        if response.status_code == 404:
            return

        response.raise_for_status()

    def read_resource_related_automations(self, resource_id: str) -> list["Automation"]:
        response = self.request(
            "GET",
            "/automations/related-to/{resource_id}",
            path_params={"resource_id": resource_id},
        )
        response.raise_for_status()
        from prefect.events.schemas.automations import Automation

        return Automation.model_validate_list(response.json())

    def delete_resource_owned_automations(self, resource_id: str) -> None:
        self.request(
            "DELETE",
            "/automations/owned-by/{resource_id}",
            path_params={"resource_id": resource_id},
        )


class AutomationAsyncClient(BaseAsyncClient):
    async def create_automation(self, automation: "AutomationCore") -> "UUID":
        """Creates an automation in Prefect Cloud."""
        response = await self.request(
            "POST",
            "/automations/",
            json=automation.model_dump(mode="json"),
        )
        from uuid import UUID

        return UUID(response.json()["id"])

    async def update_automation(
        self, automation_id: "UUID", automation: "AutomationCore"
    ) -> None:
        """Updates an automation in Prefect Cloud."""
        response = await self.request(
            "PUT",
            "/automations/{id}",
            path_params={"id": automation_id},
            json=automation.model_dump(mode="json", exclude_unset=True),
        )
        response.raise_for_status()

    async def read_automations(self) -> list["Automation"]:
        response = await self.request("POST", "/automations/filter")
        response.raise_for_status()
        from prefect.events.schemas.automations import Automation

        return Automation.model_validate_list(response.json())

    async def find_automation(self, id_or_name: "str | UUID") -> "Automation | None":
        from uuid import UUID

        if isinstance(id_or_name, str):
            name = id_or_name
            try:
                id = UUID(id_or_name)
            except ValueError:
                id = None
        else:
            id = id_or_name
            name = str(id)

        if id:
            try:
                automation = await self.read_automation(id)
                return automation
            except HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise ObjectNotFound(http_exc=e) from e

        automations = await self.read_automations()

        # Look for it by an exact name
        for automation in automations:
            if automation.name == name:
                return automation

        # Look for it by a case-insensitive name
        for automation in automations:
            if automation.name.lower() == name.lower():
                return automation

        return None

    async def read_automation(self, automation_id: "UUID | str") -> "Automation | None":
        response = await self.request(
            "GET", "/automations/{id}", path_params={"id": automation_id}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        from prefect.events.schemas.automations import Automation

        return Automation.model_validate(response.json())

    async def read_automations_by_name(self, name: str) -> list["Automation"]:
        """
        Query the Prefect API for an automation by name. Only automations matching the provided name will be returned.

        Args:
            name: the name of the automation to query

        Returns:
            a list of Automation model representations of the automations
        """
        from prefect.client.schemas.sorting import AutomationSort
        from prefect.events.filters import (
            AutomationFilter,
            AutomationFilterName,
        )

        automation_filter = AutomationFilter(name=AutomationFilterName(any_=[name]))

        response = await self.request(
            "POST",
            "/automations/filter",
            json={
                "sort": AutomationSort.UPDATED_DESC,
                "automations": automation_filter.model_dump(mode="json")
                if automation_filter
                else None,
            },
        )

        response.raise_for_status()
        from prefect.events.schemas.automations import Automation

        return Automation.model_validate_list(response.json())

    async def pause_automation(self, automation_id: "UUID") -> None:
        response = await self.request(
            "PATCH",
            "/automations/{id}",
            path_params={"id": automation_id},
            json={"enabled": False},
        )
        response.raise_for_status()

    async def resume_automation(self, automation_id: "UUID") -> None:
        response = await self.request(
            "PATCH",
            "/automations/{id}",
            path_params={"id": automation_id},
            json={"enabled": True},
        )
        response.raise_for_status()

    async def delete_automation(self, automation_id: "UUID") -> None:
        response = await self.request(
            "DELETE",
            "/automations/{id}",
            path_params={"id": automation_id},
        )
        if response.status_code == 404:
            return

        response.raise_for_status()

    async def read_resource_related_automations(
        self, resource_id: str
    ) -> list["Automation"]:
        response = await self.request(
            "GET",
            "/automations/related-to/{resource_id}",
            path_params={"resource_id": resource_id},
        )
        response.raise_for_status()
        from prefect.events.schemas.automations import Automation

        return Automation.model_validate_list(response.json())

    async def delete_resource_owned_automations(self, resource_id: str) -> None:
        await self.request(
            "DELETE",
            "/automations/owned-by/{resource_id}",
            path_params={"resource_id": resource_id},
        )
