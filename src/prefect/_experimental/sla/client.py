from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient

if TYPE_CHECKING:
    from uuid import UUID

    from prefect._experimental.sla.objects import SlaTypes


class SlaClient(BaseClient):
    def create_sla(self, sla: "SlaTypes") -> "UUID":
        """
        Creates a service level agreement.
        Args:
            sla: The SLA to create. Must have a deployment ID set.
        Raises:
            httpx.RequestError: if the SLA was not created for any reason
        Returns:
            the ID of the SLA in the backend
        """
        if not sla.owner_resource:
            raise ValueError(
                "Deployment ID is not set. Please set using `set_deployment_id`."
            )

        response = self.request(
            "POST",
            "/slas/",
            json=sla.model_dump(mode="json", exclude_unset=True),
        )
        response.raise_for_status()

        from uuid import UUID

        return UUID(response.json().get("id"))


class SlaAsyncClient(BaseAsyncClient):
    async def create_sla(self, sla: "SlaTypes") -> "UUID":
        """
        Creates a service level agreement.
        Args:
            sla: The SLA to create. Must have a deployment ID set.
        Raises:
            httpx.RequestError: if the SLA was not created for any reason
        Returns:
            the ID of the SLA in the backend
        """
        if not sla.owner_resource:
            raise ValueError(
                "Deployment ID is not set. Please set using `set_deployment_id`."
            )

        response = await self.request(
            "POST",
            "/slas/",
            json=sla.model_dump(mode="json", exclude_unset=True),
        )
        response.raise_for_status()

        from uuid import UUID

        return UUID(response.json().get("id"))
