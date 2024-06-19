from __future__ import annotations

from typing import Optional

from googleapiclient.discovery import Resource
from pydantic import BaseModel
from slugify import slugify


def slugify_name(name: str, max_length: int = 30) -> Optional[str]:
    """
    Slugify text for use as a name.

    Keeps only alphanumeric characters and dashes, and caps the length
    of the slug at 30 chars.

    The 30 character length allows room to add a uuid for generating a unique
    name for the job while keeping the total length of a name below 63 characters,
    which is the limit for Cloud Run job names.

    Args:
        name: The name of the job

    Returns:
        The slugified job name or None if the slugified name is empty
    """
    slug = slugify(
        name,
        max_length=max_length,
        regex_pattern=r"[^a-zA-Z0-9-]+",
    )

    return slug if slug else None


"""
DEPRECATION WARNING:

This module is deprecated as of March 2024 and will not be available after September 2024.
It has been replaced by the Cloud Run and Cloud Run V2 workers, which offer enhanced functionality and better performance.

For upgrade instructions, see https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/.

Integrations with Google Cloud Run Job.

Examples:

    Run a job using Google Cloud Run Jobs:
    ```python
    CloudRunJob(
        image="gcr.io/my-project/my-image",
        region="us-east1",
        credentials=my_gcp_credentials
    ).run()
    ```

    Run a job that runs the command `echo hello world` using Google Cloud Run Jobs:
    ```python
    CloudRunJob(
        image="gcr.io/my-project/my-image",
        region="us-east1",
        credentials=my_gcp_credentials
        command=["echo", "hello world"]
    ).run()
    ```

"""  # noqa


class Job(BaseModel):
    """
    Utility class to call GCP `jobs` API and
    interact with the returned objects.
    """

    metadata: dict
    spec: dict
    status: dict
    name: str
    ready_condition: dict
    execution_status: dict

    def _is_missing_container(self):
        """
        Check if Job status is not ready because
        the specified container cannot be found.
        """
        if (
            self.ready_condition.get("status") == "False"
            and self.ready_condition.get("reason") == "ContainerMissing"
        ):
            return True
        return False

    def is_ready(self) -> bool:
        """Whether a job is finished registering and ready to be executed"""
        if self._is_missing_container():
            raise Exception(f"{self.ready_condition['message']}")
        return self.ready_condition.get("status") == "True"

    def has_execution_in_progress(self) -> bool:
        """See if job has a run in progress."""
        return (
            self.execution_status == {}
            or self.execution_status.get("completionTimestamp") is None
        )

    @staticmethod
    def _get_ready_condition(job: dict) -> dict:
        """Utility to access JSON field containing ready condition."""
        if job["status"].get("conditions"):
            for condition in job["status"]["conditions"]:
                if condition["type"] == "Ready":
                    return condition

        return {}

    @staticmethod
    def _get_execution_status(job: dict):
        """Utility to access JSON field containing execution status."""
        if job["status"].get("latestCreatedExecution"):
            return job["status"]["latestCreatedExecution"]

        return {}

    @classmethod
    def get(cls, client: Resource, namespace: str, job_name: str):
        """Make a get request to the GCP jobs API and return a Job instance."""
        request = client.jobs().get(name=f"namespaces/{namespace}/jobs/{job_name}")
        response = request.execute()

        return cls(
            metadata=response["metadata"],
            spec=response["spec"],
            status=response["status"],
            name=response["metadata"]["name"],
            ready_condition=cls._get_ready_condition(response),
            execution_status=cls._get_execution_status(response),
        )

    @staticmethod
    def create(client: Resource, namespace: str, body: dict):
        """Make a create request to the GCP jobs API."""
        request = client.jobs().create(parent=f"namespaces/{namespace}", body=body)
        response = request.execute()
        return response

    @staticmethod
    def delete(client: Resource, namespace: str, job_name: str):
        """Make a delete request to the GCP jobs API."""
        request = client.jobs().delete(name=f"namespaces/{namespace}/jobs/{job_name}")
        response = request.execute()
        return response

    @staticmethod
    def run(client: Resource, namespace: str, job_name: str):
        """Make a run request to the GCP jobs API."""
        request = client.jobs().run(name=f"namespaces/{namespace}/jobs/{job_name}")
        response = request.execute()
        return response


class Execution(BaseModel):
    """
    Utility class to call GCP `executions` API and
    interact with the returned objects.
    """

    name: str
    namespace: str
    metadata: dict
    spec: dict
    status: dict
    log_uri: str

    def is_running(self) -> bool:
        """Returns True if Execution is not completed."""
        return self.status.get("completionTime") is None

    def condition_after_completion(self):
        """Returns Execution condition if Execution has completed."""
        for condition in self.status["conditions"]:
            if condition["type"] == "Completed":
                return condition

    def succeeded(self):
        """Whether or not the Execution completed is a successful state."""
        completed_condition = self.condition_after_completion()
        if completed_condition and completed_condition["status"] == "True":
            return True

        return False

    @classmethod
    def get(cls, client: Resource, namespace: str, execution_name: str):
        """
        Make a get request to the GCP executions API
        and return an Execution instance.
        """
        request = client.executions().get(
            name=f"namespaces/{namespace}/executions/{execution_name}"
        )
        response = request.execute()

        return cls(
            name=response["metadata"]["name"],
            namespace=response["metadata"]["namespace"],
            metadata=response["metadata"],
            spec=response["spec"],
            status=response["status"],
            log_uri=response["status"]["logUri"],
        )
