import time
from typing import Dict, List, Literal, Optional

# noinspection PyProtectedMember
from googleapiclient.discovery import Resource
from pydantic import VERSION as PYDANTIC_VERSION

from prefect.infrastructure.base import InfrastructureResult

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import BaseModel
else:
    from pydantic import BaseModel


class JobV2(BaseModel):
    """
    JobV2 is a data model for a job that will be run on Cloud Run with the V2 API.
    """

    name: str
    uid: str
    generation: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    createTime: str
    updateTime: str
    deleteTime: Optional[str]
    expireTime: Optional[str]
    creator: Optional[str]
    lastModifier: Optional[str]
    client: Optional[str]
    clientVersion: Optional[str]
    launchStage: Literal[
        "ALPHA",
        "BETA",
        "GA",
        "DEPRECATED",
        "EARLY_ACCESS",
        "PRELAUNCH",
        "UNIMPLEMENTED",
        "LAUNCH_TAG_UNSPECIFIED",
    ]
    binaryAuthorization: Dict
    template: Dict
    observedGeneration: Optional[str]
    terminalCondition: Dict
    conditions: List[Dict]
    executionCount: int
    latestCreatedExecution: Dict
    reconciling: bool
    satisfiesPzs: bool
    etag: str

    def is_ready(self) -> bool:
        """
        Check if the job is ready to run.

        Returns:
            Whether the job is ready to run.
        """
        ready_condition = self.get_ready_condition()

        if self._is_missing_container(ready_condition=ready_condition):
            raise Exception(f"{ready_condition.get('message')}")

        return ready_condition.get("state") == "CONDITION_SUCCEEDED"

    def get_ready_condition(self) -> Dict:
        """
        Get the ready condition for the job.

        Returns:
            The ready condition for the job.
        """
        if self.terminalCondition.get("type") == "Ready":
            return self.terminalCondition

        return {}

    @classmethod
    def get(
        cls,
        cr_client: Resource,
        project: str,
        location: str,
        job_name: str,
    ):
        """
        Get a job from Cloud Run with the V2 API.

        Args:
            cr_client: The base client needed for interacting with GCP
                Cloud Run V2 API.
            project: The GCP project ID.
            location: The GCP region.
            job_name: The name of the job to get.
        """
        # noinspection PyUnresolvedReferences
        request = cr_client.jobs().get(
            name=f"projects/{project}/locations/{location}/jobs/{job_name}",
        )

        response = request.execute()

        return cls(
            name=response["name"],
            uid=response["uid"],
            generation=response["generation"],
            labels=response.get("labels", {}),
            annotations=response.get("annotations", {}),
            createTime=response["createTime"],
            updateTime=response["updateTime"],
            deleteTime=response.get("deleteTime"),
            expireTime=response.get("expireTime"),
            creator=response.get("creator"),
            lastModifier=response.get("lastModifier"),
            client=response.get("client"),
            clientVersion=response.get("clientVersion"),
            launchStage=response.get("launchStage", "GA"),
            binaryAuthorization=response.get("binaryAuthorization", {}),
            template=response.get("template"),
            observedGeneration=response.get("observedGeneration"),
            terminalCondition=response.get("terminalCondition", {}),
            conditions=response.get("conditions", []),
            executionCount=response.get("executionCount", 0),
            latestCreatedExecution=response["latestCreatedExecution"],
            reconciling=response.get("reconciling", False),
            satisfiesPzs=response.get("satisfiesPzs", False),
            etag=response["etag"],
        )

    @staticmethod
    def create(
        cr_client: Resource,
        project: str,
        location: str,
        job_id: str,
        body: Dict,
    ) -> Dict:
        """
        Create a job on Cloud Run with the V2 API.

        Args:
            cr_client: The base client needed for interacting with GCP
                Cloud Run V2 API.
            project: The GCP project ID.
            location: The GCP region.
            job_id: The ID of the job to create.
            body: The job body.

        Returns:
            The response from the Cloud Run V2 API.
        """
        # noinspection PyUnresolvedReferences
        request = cr_client.jobs().create(
            parent=f"projects/{project}/locations/{location}",
            jobId=job_id,
            body=body,
        )

        response = request.execute()

        return response

    @staticmethod
    def delete(
        cr_client: Resource,
        project: str,
        location: str,
        job_name: str,
    ) -> Dict:
        """
        Delete a job on Cloud Run with the V2 API.

        Args:
            cr_client (Resource): The base client needed for interacting with GCP
                Cloud Run V2 API.
            project: The GCP project ID.
            location: The GCP region.
            job_name: The name of the job to delete.

        Returns:
            Dict: The response from the Cloud Run V2 API.
        """
        # noinspection PyUnresolvedReferences
        list_executions_request = (
            cr_client.jobs()
            .executions()
            .list(
                parent=f"projects/{project}/locations/{location}/jobs/{job_name}",
            )
        )
        list_executions_response = list_executions_request.execute()

        for execution_to_delete in list_executions_response.get("executions", []):
            # noinspection PyUnresolvedReferences
            delete_execution_request = (
                cr_client.jobs()
                .executions()
                .delete(
                    name=execution_to_delete["name"],
                )
            )
            delete_execution_request.execute()

            # Sleep 3 seconds so that the execution is deleted before deleting the job
            time.sleep(3)

        # noinspection PyUnresolvedReferences
        request = cr_client.jobs().delete(
            name=f"projects/{project}/locations/{location}/jobs/{job_name}",
        )

        response = request.execute()

        return response

    @staticmethod
    def run(
        cr_client: Resource,
        project: str,
        location: str,
        job_name: str,
    ):
        """
        Run a job on Cloud Run with the V2 API.

        Args:
            cr_client: The base client needed for interacting with GCP
                Cloud Run V2 API.
            project: The GCP project ID.
            location: The GCP region.
            job_name: The name of the job to run.
        """
        # noinspection PyUnresolvedReferences
        request = cr_client.jobs().run(
            name=f"projects/{project}/locations/{location}/jobs/{job_name}",
        )

        response = request.execute()

        return response

    @staticmethod
    def _is_missing_container(ready_condition: Dict) -> bool:
        """
        Check if the job is missing a container.

        Args:
            ready_condition: The ready condition for the job.

        Returns:
            Whether the job is missing a container.
        """
        if (
            ready_condition.get("state") == "CONTAINER_FAILED"
            and ready_condition.get("reason") == "ContainerMissing"
        ):
            return True

        return False


class ExecutionV2(BaseModel):
    """
    ExecutionV2 is a data model for an execution of a job that will be run on
        Cloud Run API v2.
    """

    name: str
    uid: str
    generation: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    createTime: str
    startTime: Optional[str]
    completionTime: Optional[str]
    deleteTime: Optional[str]
    expireTime: Optional[str]
    launchStage: Literal[
        "ALPHA",
        "BETA",
        "GA",
        "DEPRECATED",
        "EARLY_ACCESS",
        "PRELAUNCH",
        "UNIMPLEMENTED",
        "LAUNCH_TAGE_UNSPECIFIED",
    ]
    job: str
    parallelism: int
    taskCount: int
    template: Dict
    reconciling: bool
    conditions: List[Dict]
    observedGeneration: Optional[str]
    runningCount: Optional[int]
    succeededCount: Optional[int]
    failedCount: Optional[int]
    cancelledCount: Optional[int]
    retriedCount: Optional[int]
    logUri: str
    satisfiesPzs: bool
    etag: str

    def is_running(self) -> bool:
        """
        Return whether the execution is running.

        Returns:
            Whether the execution is running.
        """
        return self.completionTime is None

    def succeeded(self) -> bool:
        """
        Return whether the execution succeeded.

        Returns:
            Whether the execution succeeded.
        """
        return True if self.condition_after_completion() else False

    def condition_after_completion(self) -> Dict:
        """
        Return the condition after completion.

        Returns:
            The condition after completion.
        """
        if isinstance(self.conditions, List):
            for condition in self.conditions:
                if (
                    condition["state"] == "CONDITION_SUCCEEDED"
                    and condition["type"] == "Completed"
                ):
                    return condition

        return {}

    @classmethod
    def get(
        cls,
        cr_client: Resource,
        execution_id: str,
    ):
        """
        Get an execution from Cloud Run with the V2 API.

        Args:
            cr_client: The base client needed for interacting with GCP
                Cloud Run V2 API.
            execution_id: The name of the execution to get, in the form of
                projects/{project}/locations/{location}/jobs/{job}/executions
                    /{execution}
        """
        # noinspection PyUnresolvedReferences
        request = cr_client.jobs().executions().get(name=execution_id)

        response = request.execute()

        return cls(
            name=response["name"],
            uid=response["uid"],
            generation=response["generation"],
            labels=response.get("labels", {}),
            annotations=response.get("annotations", {}),
            createTime=response["createTime"],
            startTime=response.get("startTime"),
            completionTime=response.get("completionTime"),
            deleteTime=response.get("deleteTime"),
            expireTime=response.get("expireTime"),
            launchStage=response.get("launchStage", "GA"),
            job=response["job"],
            parallelism=response["parallelism"],
            taskCount=response["taskCount"],
            template=response["template"],
            reconciling=response.get("reconciling", False),
            conditions=response.get("conditions", []),
            observedGeneration=response.get("observedGeneration"),
            runningCount=response.get("runningCount"),
            succeededCount=response.get("succeededCount"),
            failedCount=response.get("failedCount"),
            cancelledCount=response.get("cancelledCount"),
            retriedCount=response.get("retriedCount"),
            logUri=response["logUri"],
            satisfiesPzs=response.get("satisfiesPzs", False),
            etag=response["etag"],
        )


class CloudRunJobV2Result(InfrastructureResult):
    """Result from a Cloud Run Job."""
