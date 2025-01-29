from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient

if TYPE_CHECKING:
    from uuid import UUID

    from prefect._experimental.sla.objects import SlaMergeResponse, SlaTypes


class SlaClient(BaseClient):
    def apply_slas_for_deployment(
        self, deployment_id: "UUID", slas: "list[SlaTypes]"
    ) -> "SlaMergeResponse":
        """
        Applies service level agreements for a deployment. Performs matching by SLA name. If a SLA with the same name already exists, it will be updated. If a SLA with the same name does not exist, it will be created. Existing SLAs that are not in the list will be deleted.
        Args:
            deployment_id: The ID of the deployment to update SLAs for
            slas: List of SLAs to associate with the deployment
        Raises:
            httpx.RequestError: if the SLAs were not updated for any reason
        Returns:
            SlaMergeResponse: The response from the backend, containing the names of the created, updated, and deleted SLAs
        """
        resource_id = f"prefect.deployment.{deployment_id}"

        for sla in slas:
            sla.set_deployment_id(deployment_id)

        slas_spec_list = [
            sla.model_dump(mode="json", exclude_unset=True) for sla in slas
        ]

        response = self.request(
            "POST",
            f"/slas/apply-resource-slas/{resource_id}",
            json=slas_spec_list,
        )
        response.raise_for_status()

        response_json = response.json()

        from prefect._experimental.sla.objects import SlaMergeResponse

        return SlaMergeResponse(
            created=[sla.get("name") for sla in response_json.get("created")],
            updated=[sla.get("name") for sla in response_json.get("updated")],
            deleted=[sla.get("name") for sla in response_json.get("deleted")],
        )


class SlaAsyncClient(BaseAsyncClient):
    async def apply_slas_for_deployment(
        self, deployment_id: "UUID", slas: "list[SlaTypes]"
    ) -> "UUID":
        """
        Applies service level agreements for a deployment. Performs matching by SLA name. If a SLA with the same name already exists, it will be updated. If a SLA with the same name does not exist, it will be created. Existing SLAs that are not in the list will be deleted.
        Args:
            deployment_id: The ID of the deployment to update SLAs for
            slas: List of SLAs to associate with the deployment
        Raises:
            httpx.RequestError: if the SLAs were not updated for any reason
        Returns:
            SlaMergeResponse: The response from the backend, containing the names of the created, updated, and deleted SLAs
        """
        resource_id = f"prefect.deployment.{deployment_id}"

        for sla in slas:
            sla.set_deployment_id(deployment_id)

        slas_spec_list = [
            sla.model_dump(mode="json", exclude_unset=True) for sla in slas
        ]

        response = await self.request(
            "POST",
            f"/slas/apply-resource-slas/{resource_id}",
            json=slas_spec_list,
        )
        response.raise_for_status()

        response_json = response.json()

        from prefect._experimental.sla.objects import SlaMergeResponse

        return SlaMergeResponse(
            created=[sla.get("name") for sla in response_json.get("created")],
            updated=[sla.get("name") for sla in response_json.get("updated")],
            deleted=[sla.get("name") for sla in response_json.get("deleted")],
        )
