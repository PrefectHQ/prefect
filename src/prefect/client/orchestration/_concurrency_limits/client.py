from __future__ import annotations

from typing import TYPE_CHECKING, Any

from httpx import HTTPStatusError, RequestError

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
from prefect.exceptions import ObjectNotFound

if TYPE_CHECKING:
    from uuid import UUID

    from httpx import Response

    from prefect.client.schemas.actions import (
        GlobalConcurrencyLimitCreate,
        GlobalConcurrencyLimitUpdate,
    )
    from prefect.client.schemas.objects import ConcurrencyLimit
    from prefect.client.schemas.responses import GlobalConcurrencyLimitResponse


class ConcurrencyLimitClient(BaseClient):
    def create_concurrency_limit(
        self,
        tag: str,
        concurrency_limit: int,
    ) -> "UUID":
        """
        Create a tag concurrency limit in the Prefect API. These limits govern concurrently
        running tasks.

        Args:
            tag: a tag the concurrency limit is applied to
            concurrency_limit: the maximum number of concurrent task runs for a given tag

        Raises:
            httpx.RequestError: if the concurrency limit was not created for any reason

        Returns:
            the ID of the concurrency limit in the backend
        """
        from prefect.client.schemas.actions import ConcurrencyLimitCreate

        concurrency_limit_create = ConcurrencyLimitCreate(
            tag=tag,
            concurrency_limit=concurrency_limit,
        )
        response = self.request(
            "POST",
            "/concurrency_limits/",
            json=concurrency_limit_create.model_dump(mode="json"),
        )

        concurrency_limit_id = response.json().get("id")

        if not concurrency_limit_id:
            raise RequestError(f"Malformed response: {response}")
        from uuid import UUID

        return UUID(concurrency_limit_id)

    def read_concurrency_limit_by_tag(
        self,
        tag: str,
    ) -> "ConcurrencyLimit":
        """
        Read the concurrency limit set on a specific tag.

        Args:
            tag: a tag the concurrency limit is applied to

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: if the concurrency limit was not created for any reason

        Returns:
            the concurrency limit set on a specific tag
        """
        try:
            response = self.request(
                "GET",
                "/concurrency_limits/tag/{tag}",
                path_params={"tag": tag},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

        concurrency_limit_id = response.json().get("id")

        if not concurrency_limit_id:
            raise RequestError(f"Malformed response: {response}")
        from prefect.client.schemas.objects import ConcurrencyLimit

        return ConcurrencyLimit.model_validate(response.json())

    def read_concurrency_limits(
        self,
        limit: int,
        offset: int,
    ) -> list["ConcurrencyLimit"]:
        """
        Lists concurrency limits set on task run tags.

        Args:
            limit: the maximum number of concurrency limits returned
            offset: the concurrency limit query offset

        Returns:
            a list of concurrency limits
        """

        body = {
            "limit": limit,
            "offset": offset,
        }

        response = self.request("POST", "/concurrency_limits/filter", json=body)
        from prefect.client.schemas.objects import ConcurrencyLimit

        return ConcurrencyLimit.model_validate_list(response.json())

    def reset_concurrency_limit_by_tag(
        self,
        tag: str,
        slot_override: list["UUID | str"] | None = None,
    ) -> None:
        """
        Resets the concurrency limit slots set on a specific tag.

        Args:
            tag: a tag the concurrency limit is applied to
            slot_override: a list of task run IDs that are currently using a
                concurrency slot, please check that any task run IDs included in
                `slot_override` are currently running, otherwise those concurrency
                slots will never be released.

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        """
        if slot_override is not None:
            slot_override = [str(slot) for slot in slot_override]

        try:
            self.request(
                "POST",
                "/concurrency_limits/tag/{tag}/reset",
                path_params={"tag": tag},
                json=dict(slot_override=slot_override),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def delete_concurrency_limit_by_tag(
        self,
        tag: str,
    ) -> None:
        """
        Delete the concurrency limit set on a specific tag.

        Args:
            tag: a tag the concurrency limit is applied to

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        """
        try:
            self.request(
                "DELETE",
                "/concurrency_limits/tag/{tag}",
                path_params={"tag": tag},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def increment_v1_concurrency_slots(
        self,
        names: list[str],
        task_run_id: "UUID",
    ) -> "Response":
        """
        Increment concurrency limit slots for the specified limits.

        Args:
            names (List[str]): A list of limit names for which to increment limits.
            task_run_id (UUID): The task run ID incrementing the limits.
        """
        data: dict[str, Any] = {
            "names": names,
            "task_run_id": str(task_run_id),
        }

        return self.request(
            "POST",
            "/concurrency_limits/increment",
            json=data,
        )

    def decrement_v1_concurrency_slots(
        self,
        names: list[str],
        task_run_id: "UUID",
        occupancy_seconds: float,
    ) -> "Response":
        """
        Decrement concurrency limit slots for the specified limits.

        Args:
            names: A list of limit names to decrement.
            task_run_id: The task run ID that incremented the limits.
            occupancy_seconds (float): The duration in seconds that the limits
                were held.

        Returns:
            "Response": The HTTP response from the server.
        """
        data: dict[str, Any] = {
            "names": names,
            "task_run_id": str(task_run_id),
            "occupancy_seconds": occupancy_seconds,
        }

        return self.request(
            "POST",
            "/concurrency_limits/decrement",
            json=data,
        )

    def increment_concurrency_slots(
        self,
        names: list[str],
        slots: int,
        mode: str,
        create_if_missing: bool | None = None,
    ) -> "Response":
        return self.request(
            "POST",
            "/v2/concurrency_limits/increment",
            json={
                "names": names,
                "slots": slots,
                "mode": mode,
                "create_if_missing": create_if_missing if create_if_missing else False,
            },
        )

    def release_concurrency_slots(
        self, names: list[str], slots: int, occupancy_seconds: float
    ) -> "Response":
        """
        Release concurrency slots for the specified limits.

        Args:
            names: A list of limit names for which to release slots.
            slots: The number of concurrency slots to release.
            occupancy_seconds (float): The duration in seconds that the slots
                were occupied.

        Returns:
            "Response": The HTTP response from the server.
        """

        return self.request(
            "POST",
            "/v2/concurrency_limits/decrement",
            json={
                "names": names,
                "slots": slots,
                "occupancy_seconds": occupancy_seconds,
            },
        )

    def create_global_concurrency_limit(
        self, concurrency_limit: "GlobalConcurrencyLimitCreate"
    ) -> "UUID":
        response = self.request(
            "POST",
            "/v2/concurrency_limits/",
            json=concurrency_limit.model_dump(mode="json", exclude_unset=True),
        )
        from uuid import UUID

        return UUID(response.json()["id"])

    def update_global_concurrency_limit(
        self, name: str, concurrency_limit: "GlobalConcurrencyLimitUpdate"
    ) -> "Response":
        try:
            response = self.request(
                "PATCH",
                "/v2/concurrency_limits/{id_or_name}",
                path_params={"id_or_name": name},
                json=concurrency_limit.model_dump(mode="json", exclude_unset=True),
            )
            return response
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def delete_global_concurrency_limit_by_name(self, name: str) -> "Response":
        try:
            response = self.request(
                "DELETE",
                "/v2/concurrency_limits/{id_or_name}",
                path_params={"id_or_name": name},
            )
            return response
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def read_global_concurrency_limit_by_name(
        self, name: str
    ) -> "GlobalConcurrencyLimitResponse":
        try:
            response = self.request(
                "GET",
                "/v2/concurrency_limits/{id_or_name}",
                path_params={"id_or_name": name},
            )
            from prefect.client.schemas.responses import GlobalConcurrencyLimitResponse

            return GlobalConcurrencyLimitResponse.model_validate(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    def upsert_global_concurrency_limit_by_name(self, name: str, limit: int) -> None:
        """Creates a global concurrency limit with the given name and limit if one does not already exist.

        If one does already exist matching the name then update it's limit if it is different.

        Note: This is not done atomically.
        """
        from prefect.client.schemas.actions import (
            GlobalConcurrencyLimitCreate,
            GlobalConcurrencyLimitUpdate,
        )

        try:
            existing_limit = self.read_global_concurrency_limit_by_name(name)
        except ObjectNotFound:
            existing_limit = None

        if not existing_limit:
            self.create_global_concurrency_limit(
                GlobalConcurrencyLimitCreate(
                    name=name,
                    limit=limit,
                )
            )
        elif existing_limit.limit != limit:
            self.update_global_concurrency_limit(
                name, GlobalConcurrencyLimitUpdate(limit=limit)
            )

    def read_global_concurrency_limits(
        self, limit: int = 10, offset: int = 0
    ) -> list["GlobalConcurrencyLimitResponse"]:
        response = self.request(
            "POST",
            "/v2/concurrency_limits/filter",
            json={
                "limit": limit,
                "offset": offset,
            },
        )

        from prefect.client.schemas.responses import GlobalConcurrencyLimitResponse

        return GlobalConcurrencyLimitResponse.model_validate_list(response.json())


class ConcurrencyLimitAsyncClient(BaseAsyncClient):
    async def create_concurrency_limit(
        self,
        tag: str,
        concurrency_limit: int,
    ) -> "UUID":
        """
        Create a tag concurrency limit in the Prefect API. These limits govern concurrently
        running tasks.

        Args:
            tag: a tag the concurrency limit is applied to
            concurrency_limit: the maximum number of concurrent task runs for a given tag

        Raises:
            httpx.RequestError: if the concurrency limit was not created for any reason

        Returns:
            the ID of the concurrency limit in the backend
        """
        from prefect.client.schemas.actions import ConcurrencyLimitCreate

        concurrency_limit_create = ConcurrencyLimitCreate(
            tag=tag,
            concurrency_limit=concurrency_limit,
        )
        response = await self.request(
            "POST",
            "/concurrency_limits/",
            json=concurrency_limit_create.model_dump(mode="json"),
        )

        concurrency_limit_id = response.json().get("id")

        if not concurrency_limit_id:
            raise RequestError(f"Malformed response: {response}")
        from uuid import UUID

        return UUID(concurrency_limit_id)

    async def read_concurrency_limit_by_tag(
        self,
        tag: str,
    ) -> "ConcurrencyLimit":
        """
        Read the concurrency limit set on a specific tag.

        Args:
            tag: a tag the concurrency limit is applied to

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: if the concurrency limit was not created for any reason

        Returns:
            the concurrency limit set on a specific tag
        """
        try:
            response = await self.request(
                "GET",
                "/concurrency_limits/tag/{tag}",
                path_params={"tag": tag},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

        concurrency_limit_id = response.json().get("id")

        if not concurrency_limit_id:
            raise RequestError(f"Malformed response: {response}")
        from prefect.client.schemas.objects import ConcurrencyLimit

        return ConcurrencyLimit.model_validate(response.json())

    async def read_concurrency_limits(
        self,
        limit: int,
        offset: int,
    ) -> list["ConcurrencyLimit"]:
        """
        Lists concurrency limits set on task run tags.

        Args:
            limit: the maximum number of concurrency limits returned
            offset: the concurrency limit query offset

        Returns:
            a list of concurrency limits
        """

        body = {
            "limit": limit,
            "offset": offset,
        }

        response = await self.request("POST", "/concurrency_limits/filter", json=body)
        from prefect.client.schemas.objects import ConcurrencyLimit

        return ConcurrencyLimit.model_validate_list(response.json())

    async def reset_concurrency_limit_by_tag(
        self,
        tag: str,
        slot_override: list["UUID | str"] | None = None,
    ) -> None:
        """
        Resets the concurrency limit slots set on a specific tag.

        Args:
            tag: a tag the concurrency limit is applied to
            slot_override: a list of task run IDs that are currently using a
                concurrency slot, please check that any task run IDs included in
                `slot_override` are currently running, otherwise those concurrency
                slots will never be released.

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        """
        if slot_override is not None:
            slot_override = [str(slot) for slot in slot_override]

        try:
            await self.request(
                "POST",
                "/concurrency_limits/tag/{tag}/reset",
                path_params={"tag": tag},
                json=dict(slot_override=slot_override),
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def delete_concurrency_limit_by_tag(
        self,
        tag: str,
    ) -> None:
        """
        Delete the concurrency limit set on a specific tag.

        Args:
            tag: a tag the concurrency limit is applied to

        Raises:
            ObjectNotFound: If request returns 404
            httpx.RequestError: If request fails

        """
        try:
            await self.request(
                "DELETE",
                "/concurrency_limits/tag/{tag}",
                path_params={"tag": tag},
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def increment_v1_concurrency_slots(
        self,
        names: list[str],
        task_run_id: "UUID",
    ) -> "Response":
        """
        Increment concurrency limit slots for the specified limits.

        Args:
            names: A list of limit names for which to increment limits.
            task_run_id: The task run ID incrementing the limits.
        """
        data: dict[str, Any] = {
            "names": names,
            "task_run_id": str(task_run_id),
        }

        return await self.request(
            "POST",
            "/concurrency_limits/increment",
            json=data,
        )

    async def decrement_v1_concurrency_slots(
        self,
        names: list[str],
        task_run_id: "UUID",
        occupancy_seconds: float,
    ) -> "Response":
        """
        Decrement concurrency limit slots for the specified limits.

        Args:
            names: A list of limit names to decrement.
            task_run_id: The task run ID that incremented the limits.
            occupancy_seconds (float): The duration in seconds that the limits
                were held.

        Returns:
            "Response": The HTTP response from the server.
        """
        data: dict[str, Any] = {
            "names": names,
            "task_run_id": str(task_run_id),
            "occupancy_seconds": occupancy_seconds,
        }

        return await self.request(
            "POST",
            "/concurrency_limits/decrement",
            json=data,
        )

    async def increment_concurrency_slots(
        self,
        names: list[str],
        slots: int,
        mode: str,
        create_if_missing: bool | None = None,
    ) -> "Response":
        return await self.request(
            "POST",
            "/v2/concurrency_limits/increment",
            json={
                "names": names,
                "slots": slots,
                "mode": mode,
                "create_if_missing": create_if_missing if create_if_missing else False,
            },
        )

    async def release_concurrency_slots(
        self, names: list[str], slots: int, occupancy_seconds: float
    ) -> "Response":
        """
        Release concurrency slots for the specified limits.

        Args:
            names: A list of limit names for which to release slots.
            slots: The number of concurrency slots to release.
            occupancy_seconds (float): The duration in seconds that the slots
                were occupied.

        Returns:
            "Response": The HTTP response from the server.
        """

        return await self.request(
            "POST",
            "/v2/concurrency_limits/decrement",
            json={
                "names": names,
                "slots": slots,
                "occupancy_seconds": occupancy_seconds,
            },
        )

    async def create_global_concurrency_limit(
        self, concurrency_limit: "GlobalConcurrencyLimitCreate"
    ) -> "UUID":
        response = await self.request(
            "POST",
            "/v2/concurrency_limits/",
            json=concurrency_limit.model_dump(mode="json", exclude_unset=True),
        )
        from uuid import UUID

        return UUID(response.json()["id"])

    async def update_global_concurrency_limit(
        self, name: str, concurrency_limit: "GlobalConcurrencyLimitUpdate"
    ) -> "Response":
        try:
            response = await self.request(
                "PATCH",
                "/v2/concurrency_limits/{id_or_name}",
                path_params={"id_or_name": name},
                json=concurrency_limit.model_dump(mode="json", exclude_unset=True),
            )
            return response
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def delete_global_concurrency_limit_by_name(self, name: str) -> "Response":
        try:
            response = await self.request(
                "DELETE",
                "/v2/concurrency_limits/{id_or_name}",
                path_params={"id_or_name": name},
            )
            return response
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def read_global_concurrency_limit_by_name(
        self, name: str
    ) -> "GlobalConcurrencyLimitResponse":
        try:
            response = await self.request(
                "GET",
                "/v2/concurrency_limits/{id_or_name}",
                path_params={"id_or_name": name},
            )
            from prefect.client.schemas.responses import GlobalConcurrencyLimitResponse

            return GlobalConcurrencyLimitResponse.model_validate(response.json())
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ObjectNotFound(http_exc=e) from e
            else:
                raise

    async def upsert_global_concurrency_limit_by_name(
        self, name: str, limit: int
    ) -> None:
        """Creates a global concurrency limit with the given name and limit if one does not already exist.

        If one does already exist matching the name then update it's limit if it is different.

        Note: This is not done atomically.
        """
        from prefect.client.schemas.actions import (
            GlobalConcurrencyLimitCreate,
            GlobalConcurrencyLimitUpdate,
        )

        try:
            existing_limit = await self.read_global_concurrency_limit_by_name(name)
        except ObjectNotFound:
            existing_limit = None

        if not existing_limit:
            await self.create_global_concurrency_limit(
                GlobalConcurrencyLimitCreate(
                    name=name,
                    limit=limit,
                )
            )
        elif existing_limit.limit != limit:
            await self.update_global_concurrency_limit(
                name, GlobalConcurrencyLimitUpdate(limit=limit)
            )

    async def read_global_concurrency_limits(
        self, limit: int = 10, offset: int = 0
    ) -> list["GlobalConcurrencyLimitResponse"]:
        response = await self.request(
            "POST",
            "/v2/concurrency_limits/filter",
            json={
                "limit": limit,
                "offset": offset,
            },
        )

        from prefect.client.schemas.responses import GlobalConcurrencyLimitResponse

        return GlobalConcurrencyLimitResponse.model_validate_list(response.json())
