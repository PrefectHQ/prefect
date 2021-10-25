from dataclasses import dataclass
from typing import List, Any

from prefect import Client
from prefect.utilities.graphql import with_args


@dataclass(frozen=True)
class TenantView:
    """
    A view of tenant data stored in the Prefect API.

    This object is designed to be an immutable view of the data stored in the Prefect
    backend API at the time it is created

    EXPERIMENTAL: This interface is experimental and subject to change

    Args:
        - tenant_id: The uuid of the tenant
        - name: The name of the tenant
        - slug: A machine compatible unique identifier for the tenant
    """

    tenant_id: str
    name: str
    slug: str

    @classmethod
    def _from_tenant_data(cls, tenant_data: dict) -> "TenantView":
        tenant_data = tenant_data.copy()
        tenant_id = tenant_data.pop("id")
        return cls(tenant_id=tenant_id, **tenant_data)

    @classmethod
    def _query_for_tenant(cls, where: dict, **kwargs: Any) -> dict:
        """
        Query for tenant data using `_query_for_tenants` but throw an exception if
        more than one matching tenant is found

        Args:
            - where: The `where` clause to use
            - **kwargs: Additional kwargs are passed to `_query_for_tenants`

        Returns:
            A dict of tenant data
        """
        tenants = cls._query_for_tenants(where=where, **kwargs)

        if len(tenants) > 1:
            raise ValueError(
                f"Found multiple ({len(tenants)}) tenants while querying for tenants "
                f"where {where}: {tenants}"
            )

        if not tenants:
            return {}

        tenant = tenants[0]
        return tenant

    @staticmethod
    def _query_for_tenants(
        where: dict,
        order_by: dict = None,
        error_on_empty: bool = True,
    ) -> List[dict]:
        """
        Query for tenant data necessary to initialize `TenantView` instances with
        `TenantView._from_tenant_data`.

        Args:
            - where (required): The Hasura `where` clause to filter by
            - order_by (optional): An optional Hasura `order_by` clause to order
                 results by
            - error_on_empty (optional): If `True` and no tenants are found, a
                `ValueError` will be raised

        Returns:
            A list of dicts of tenant information
        """
        client = Client()

        query_args = {"where": where}
        if order_by is not None:
            query_args["order_by"] = order_by

        tenant_query = {
            "query": {
                with_args("tenant", query_args): {
                    "id",
                    "slug",
                    "name",
                }
            }
        }

        result = client.graphql(tenant_query)
        tenants = result.get("data", {}).get("tenant", None)

        if tenants is None:
            raise ValueError(
                f"Received bad result while querying for tenants where {where}: "
                f"{result}"
            )

        if not tenants:  # Empty list
            if error_on_empty:
                raise ValueError(
                    f"No results found while querying for tenants where {where!r}"
                )
            return []

        # Return a list
        return tenants

    @classmethod
    def from_tenant_id(cls, tenant_id: str) -> "TenantView":
        """
        Get an instance of this class filled with information by querying for the given
        tenant id

        Args:
            - tenant_id: the tenant to lookup

        Returns:
            A populated `TenantView` instance
        """
        return cls._from_tenant_data(
            cls._query_for_tenant(where={"id": {"_eq": tenant_id}})
        )

    @classmethod
    def from_current_tenant(cls) -> "TenantView":
        """
        Get an instance of this class filled with information by querying for the
        tenant id set in the Prefect Client

        Returns:
            A populated `TenantView` instance
        """
        client = Client()
        return cls.from_tenant_id(client.tenant_id)
