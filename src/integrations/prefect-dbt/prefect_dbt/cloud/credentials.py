"""Module containing credentials for interacting with dbt Cloud"""

from typing import Union

from pydantic import Field, SecretStr
from typing_extensions import Literal

from prefect.blocks.abstract import CredentialsBlock
from prefect_dbt.cloud.clients import (
    DbtCloudAdministrativeClient,
    DbtCloudMetadataClient,
)


class DbtCloudCredentials(CredentialsBlock):
    """
    Credentials block for credential use across dbt Cloud tasks and flows.

    Attributes:
        api_key (SecretStr): API key to authenticate with the dbt Cloud
            administrative API. Refer to the [Authentication docs](
            https://docs.getdbt.com/dbt-cloud/api-v2#section/Authentication)
            for retrieving the API key.
        account_id (int): ID of dbt Cloud account with which to interact.
        domain (Optional[str]): Domain at which the dbt Cloud API is hosted.

    Examples:
        Load stored dbt Cloud credentials:
        ```python
        from prefect_dbt.cloud import DbtCloudCredentials

        dbt_cloud_credentials = DbtCloudCredentials.load("BLOCK_NAME")
        ```

        Use DbtCloudCredentials instance to trigger a job run:
        ```python
        from prefect_dbt.cloud import DbtCloudCredentials

        credentials = DbtCloudCredentials(api_key="my_api_key", account_id=123456789)

        async with dbt_cloud_credentials.get_administrative_client() as client:
            client.trigger_job_run(job_id=1)
        ```

        Load saved dbt Cloud credentials within a flow:
        ```python
        from prefect import flow

        from prefect_dbt.cloud import DbtCloudCredentials
        from prefect_dbt.cloud.jobs import trigger_dbt_cloud_job_run


        @flow
        def trigger_dbt_cloud_job_run_flow():
            credentials = DbtCloudCredentials.load("my-dbt-credentials")
            trigger_dbt_cloud_job_run(dbt_cloud_credentials=credentials, job_id=1)

        trigger_dbt_cloud_job_run_flow()
        ```
    """

    _block_type_name = "dbt Cloud Credentials"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5zE9lxfzBHjw3tnEup4wWL/9a001902ed43a84c6c96d23b24622e19/dbt-bit_tm.png?h=250"  # noqa
    _documentation_url = "https://docs.prefect.io/integrations/prefect-dbt"  # noqa

    api_key: SecretStr = Field(
        default=...,
        title="API Key",
        description="A dbt Cloud API key to use for authentication.",
    )
    account_id: int = Field(
        default=..., title="Account ID", description="The ID of your dbt Cloud account."
    )
    domain: str = Field(
        default="cloud.getdbt.com",
        description="The base domain of your dbt Cloud instance.",
    )

    def get_administrative_client(self) -> DbtCloudAdministrativeClient:
        """
        Returns a newly instantiated client for working with the dbt Cloud
        administrative API.

        Returns:
            An authenticated dbt Cloud administrative API client.
        """
        return DbtCloudAdministrativeClient(
            api_key=self.api_key.get_secret_value(),
            account_id=self.account_id,
            domain=self.domain,
        )

    def get_metadata_client(self) -> DbtCloudMetadataClient:
        """
        Returns a newly instantiated client for working with the dbt Cloud
        metadata API.

        Example:
            Sending queries via the returned metadata client:
            ```python
            from prefect_dbt import DbtCloudCredentials

            credentials_block = DbtCloudCredentials.load("test-account")
            metadata_client = credentials_block.get_metadata_client()
            query = \"\"\"
            {
                metrics(jobId: 123) {
                    uniqueId
                    name
                    packageName
                    tags
                    label
                    runId
                    description
                    type
                    sql
                    timestamp
                    timeGrains
                    dimensions
                    meta
                    resourceType
                    filters {
                        field
                        operator
                        value
                    }
                    model {
                        name
                    }
                }
            }
            \"\"\"
            metadata_client.query(query)
            # Result:
            # {
            #   "data": {
            #     "metrics": [
            #       {
            #         "uniqueId": "metric.tpch.total_revenue",
            #         "name": "total_revenue",
            #         "packageName": "tpch",
            #         "tags": [],
            #         "label": "Total Revenue ($)",
            #         "runId": 108952046,
            #         "description": "",
            #         "type": "sum",
            #         "sql": "net_item_sales_amount",
            #         "timestamp": "order_date",
            #         "timeGrains": ["day", "week", "month"],
            #         "dimensions": ["status_code", "priority_code"],
            #         "meta": {},
            #         "resourceType": "metric",
            #         "filters": [],
            #         "model": { "name": "fct_orders" }
            #       }
            #     ]
            #   }
            # }
            ```

        Returns:
            An authenticated dbt Cloud metadata API client.
        """
        return DbtCloudMetadataClient(
            api_key=self.api_key.get_secret_value(),
            domain=f"metadata.{self.domain}",
        )

    def get_client(
        self, client_type: Literal["administrative", "metadata"]
    ) -> Union[DbtCloudAdministrativeClient, DbtCloudMetadataClient]:
        """
        Returns a newly instantiated client for working with the dbt Cloud API.

        Args:
            client_type: Type of client to return. Accepts either 'administrative'
                or 'metadata'.

        Returns:
            The authenticated client of the requested type.
        """
        get_client_method = getattr(self, f"get_{client_type}_client", None)
        if get_client_method is None:
            raise ValueError(f"'{client_type}' is not a supported client type.")
        return get_client_method()
