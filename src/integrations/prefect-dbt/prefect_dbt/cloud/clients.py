"""Module containing clients for interacting with the dbt Cloud API"""

from typing import Any, Dict, List, Optional

from httpx import AsyncClient, Response
from sgqlc.endpoint.http import HTTPEndpoint
from typing_extensions import Literal

import prefect
from prefect_dbt.cloud.models import TriggerJobRunOptions


class DbtCloudAdministrativeClient:
    """
    Client for interacting with the dbt cloud Administrative API.

    Args:
        api_key: API key to authenticate with the dbt Cloud administrative API.
        account_id: ID of dbt Cloud account with which to interact.
        domain: Domain at which the dbt Cloud API is hosted.
    """

    def __init__(self, api_key: str, account_id: int, domain: str = "cloud.getdbt.com"):
        self._closed = False
        self._started = False

        self._admin_client = AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "user-agent": f"prefect-{prefect.__version__}",
                "x-dbt-partner-source": "prefect",
            },
            base_url=f"https://{domain}/api/v2/accounts/{account_id}",
        )

    async def call_endpoint(
        self,
        http_method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """
        Call an endpoint in the dbt Cloud API.

        Args:
            path: The partial path for the request (e.g. /projects/). Will be appended
                onto the base URL as determined by the client configuration.
            http_method: HTTP method to call on the endpoint.
            params: Query parameters to include in the request.
            json: JSON serializable body to send in the request.

        Returns:
            The response from the dbt Cloud administrative API.
        """
        response = await self._admin_client.request(
            method=http_method, url=path, params=params, json=json
        )

        response.raise_for_status()

        return response

    async def get_job(
        self,
        job_id: int,
        order_by: Optional[str] = None,
    ) -> Response:
        """
        Return job details for a job on an account.

        Args:
            job_id: Numeric ID of the job.
            order_by: Field to order the result by. Use - to indicate reverse order.

        Returns:
            The response from the dbt Cloud administrative API.
        """  # noqa
        params = {"order_by": order_by} if order_by else None
        return await self.call_endpoint(
            path=f"/jobs/{job_id}/", http_method="GET", params=params
        )

    async def trigger_job_run(
        self, job_id: int, options: Optional[TriggerJobRunOptions] = None
    ) -> Response:
        """
        Sends a request to the [trigger job run endpoint](https://docs.getdbt.com/dbt-cloud/api-v2#tag/Jobs/operation/triggerRun)
        to initiate a job run.

        Args:
            job_id: The ID of the job to trigger.
            options: An optional TriggerJobRunOptions instance to specify overrides for the triggered job run.

        Returns:
            The response from the dbt Cloud administrative API.
        """  # noqa
        if options is None:
            options = TriggerJobRunOptions()

        return await self.call_endpoint(
            path=f"/jobs/{job_id}/run/",
            http_method="POST",
            json=options.model_dump(exclude_none=True),
        )

    async def get_run(
        self,
        run_id: int,
        include_related: Optional[
            List[Literal["trigger", "job", "debug_logs", "run_steps"]]
        ] = None,
    ) -> Response:
        """
        Sends a request to the [get run endpoint](https://docs.getdbt.com/dbt-cloud/api-v2#tag/Runs/operation/getRunById)
        to get details about a job run.

        Args:
            run_id: The ID of the run to get details for.
            include_related: List of related fields to pull with the run.
                Valid values are "trigger", "job", "debug_logs", and "run_steps".
                If "debug_logs" is not provided in a request, then the included debug
                logs will be truncated to the last 1,000 lines of the debug log output file.

        Returns:
            The response from the dbt Cloud administrative API.
        """  # noqa
        params = {"include_related": include_related} if include_related else None
        return await self.call_endpoint(
            path=f"/runs/{run_id}/", http_method="GET", params=params
        )

    async def list_run_artifacts(
        self, run_id: int, step: Optional[int] = None
    ) -> Response:
        """
        Sends a request to the [list run artifacts endpoint](https://docs.getdbt.com/dbt-cloud/api-v2#tag/Runs/operation/listArtifactsByRunId)
        to fetch a list of paths of artifacts generated for a completed run.

        Args:
            run_id: The ID of the run to list run artifacts for.
            step: The index of the step in the run to query for artifacts. The
                first step in the run has the index 1. If the step parameter is
                omitted, then this method will return the artifacts compiled
                for the last step in the run.

        Returns:
            The response from the dbt Cloud administrative API.
        """  # noqa
        params = {"step": step} if step else None
        return await self.call_endpoint(
            path=f"/runs/{run_id}/artifacts/", http_method="GET", params=params
        )

    async def get_run_artifact(
        self, run_id: int, path: str, step: Optional[int] = None
    ) -> Response:
        """
        Sends a request to the [get run artifact endpoint](https://docs.getdbt.com/dbt-cloud/api-v2#tag/Runs/operation/getArtifactsByRunId)
        to fetch an artifact generated for a completed run.

        Args:
            run_id: The ID of the run to list run artifacts for.
            path: The relative path to the run artifact (e.g. manifest.json, catalog.json,
                run_results.json)
            step: The index of the step in the run to query for artifacts. The
                first step in the run has the index 1. If the step parameter is
                omitted, then this method will return the artifacts compiled
                for the last step in the run.

        Returns:
            The response from the dbt Cloud administrative API.
        """  # noqa
        params = {"step": step} if step else None
        return await self.call_endpoint(
            path=f"/runs/{run_id}/artifacts/{path}", http_method="GET", params=params
        )

    async def __aenter__(self):
        if self._closed:
            raise RuntimeError(
                "The client cannot be started again after it has been closed."
            )
        if self._started:
            raise RuntimeError("The client cannot be started more than once.")

        self._started = True

        return self

    async def __aexit__(self, *exc):
        self._closed = True
        await self._admin_client.__aexit__()


class DbtCloudMetadataClient:
    """
    Client for interacting with the dbt cloud Administrative API.

    Args:
        api_key: API key to authenticate with the dbt Cloud administrative API.
        domain: Domain at which the dbt Cloud API is hosted.
    """

    def __init__(self, api_key: str, domain: str = "metadata.cloud.getdbt.com"):
        self._http_endpoint = HTTPEndpoint(
            base_headers={
                "Authorization": f"Bearer {api_key}",
                "user-agent": f"prefect-{prefect.__version__}",
                "x-dbt-partner-source": "prefect",
                "content-type": "application/json",
            },
            url=f"https://{domain}/graphql",
        )

    def query(
        self,
        query: str,
        variables: Optional[Dict] = None,
        operation_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run a GraphQL query against the dbt Cloud metadata API.

        Args:
            query: The GraphQL query to run.
            variables: The values of any variables defined in the GraphQL query.
            operation_name: The name of the operation to run if multiple operations
                are defined in the provided query.

        Returns:
            The result of the GraphQL query.
        """
        return self._http_endpoint(
            query=query, variables=variables, operation_name=operation_name
        )
