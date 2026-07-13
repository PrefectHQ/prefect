import ast
import asyncio
import logging
import os
from datetime import datetime

from openlineage.client.uuid import generate_static_uuid

from prefect import client
from prefect.client.orchestration import get_client
from prefect.events.clients import get_events_subscriber
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.events.schemas.events import Event
from prefect_openlineage.adapter import PrefectOpenLineageAdapter

JOB_NAMESPACE: str = os.environ.get("OPENLINEAGE_NAMESPACE", "default")

logger: logging.Logger = logging.getLogger(__name__)


class PrefectOpenLineageListener:
    def __init__(
        self,
        client: client = None,
        adapter: PrefectOpenLineageAdapter = None,
    ):
        self.client = client or get_client()
        self.ol_adapter = adapter or PrefectOpenLineageAdapter()

    def build_run_id(
        self, execution_time: datetime, run_name: str, namespace: str
    ) -> str:
        return str(
            generate_static_uuid(
                instant=execution_time,
                data=f"{namespace}.{run_name}".encode("utf-8"),
            )
        )

    async def get_deployment_and_flow_info(self, flow_run_id: str) -> tuple:
        flow_run = await self.client.read_flow_run(flow_run_id)
        deployment = await self.client.read_deployment(flow_run.deployment_id)
        flow_id = flow_run.flow_id
        flow = await self.client.read_flow(flow_id)
        flow_name = flow.name
        try:
            ns = deployment.job_variables["env"]["OPENLINEAGE_NAMESPACE"]
        except KeyError:
            ns = JOB_NAMESPACE
            logger.info(
                "OPENLINEAGE_NAMESPACE deployment variable not found. Using OPENLINEAGE_NAMESPACE env variable."
            )
            if JOB_NAMESPACE == "default":
                logger.info(
                    "OPENLINEAGE_NAMESPACE env variable not set. Namespace will be 'default.'"
                )
        return (
            str(deployment.id),
            flow_run.start_time,
            deployment.created.isoformat(),
            deployment.updated.isoformat(),
            deployment.name,
            ns,
            flow_name,
        )

    async def get_prefect_version(self) -> str | None:
        try:
            response = await self.client._client.get("/admin/version")
            version = response.json()
            return version
        except TypeError:
            logger.info(
                "Cannot get the Prefect version. Did you set the PREFECT_API_URL?"
            )

    async def get_flow_ns(self, flow_run_id: str) -> str:
        """
        Looks for OPENLINEAGE_NAMESPACE job env variable in deployment.
        """
        flow_run = await self.client.read_flow_run(flow_run_id)
        deployment = await self.client.read_deployment(flow_run.deployment_id)
        try:
            ns = deployment.job_variables["env"]["OPENLINEAGE_NAMESPACE"]
        except KeyError:
            ns = JOB_NAMESPACE
            logger.info(
                "OPENLINEAGE_NAMESPACE deployment variable not found. Using OPENLINEAGE_NAMESPACE env variable."
            )
            if JOB_NAMESPACE == "default":
                logger.info(
                    "OPENLINEAGE_NAMESPACE env variable not found. Namespace will be 'default.'"
                )
        return ns

    async def get_job_ns(self, task_run_id: str) -> str:
        """
        Looks for OPENLINEAGE_NAMESPACE job env variable in parent deployment.
        """
        task_run = await self.client.read_task_run(task_run_id)
        return await self.get_flow_ns(task_run.flow_run_id)

    async def get_flow_run_start_time(self, flow_run_id: str) -> datetime:
        flow_run = await self.client.read_flow_run(flow_run_id)
        flow_run_start_time = flow_run.start_time
        return flow_run_start_time

    async def get_artifacts_by_task_run(self, run_id: str) -> list[dict]:
        payload = {"artifacts": {"task_run_id": {"any_": [run_id]}}}
        response = await self.client._client.post("/artifacts/filter", json=payload)
        if response.status_code == 200:
            dataset_info = []
            artifacts = response.json()
            for artifact in artifacts:
                if "ol-dataset" in artifact["description"]:
                    dataset_type = artifact["description"].split("_")[-1].lower()
                    data_list = ast.literal_eval(artifact["data"])
                    uri = data_list[0]["database_uri"].lower()
                    table = data_list[0]["table"].lower()
                    dataset_info.append(
                        {"uri": uri, "table": table, "dataset_type": dataset_type}
                    )
            return dataset_info
        else:
            logging.info("No datasets found for task run.")
            return []

    async def get_parent_runs(
        self, payload: dict, prefect_task_run_id: str
    ) -> list[dict]:
        try:
            parent_runs = []
            task_parents = payload["task_run"]["task_inputs"]["__parents__"]
            for parent in task_parents:
                task_run_id: str | None = (
                    parent["id"] if parent["input_type"] == "task_run" else None
                )
                if task_run_id:
                    parent_namespace: dict = await self.get_job_ns(task_run_id)
                    parent_run = await self.client.read_task_run(task_run_id)
                    parent_name = parent_run.name.split("-")[0]
                    parent_run_id = self.build_run_id(
                        parent_run.start_time, parent_name, parent_namespace
                    )
                    parent_runs.append(
                        {
                            "name": parent_name,
                            "namespace": parent_namespace,
                            "id": parent_run_id,
                        }
                    )
            return parent_runs
        except KeyError:
            logger.info("No task parents found for %s", prefect_task_run_id)
            return []

    async def collect_and_process_flow_runs(
        self, prefect_version: str, event: Event, event_state: str
    ) -> None:
        for res in event.related:
            if res["prefect.resource.role"] == "flow":
                flow_run_name = event.resource.name
                flow_name = res["prefect.resource.name"]

            if flow_run_name:
                prefect_flow_run_id = event.resource.id.split(".")[-1]
                event_time: datetime = datetime.fromisoformat(
                    event.resource["prefect.state-timestamp"]
                )
                deployment_and_flow_info = await self.get_deployment_and_flow_info(
                    prefect_flow_run_id
                )
                deployment_id = deployment_and_flow_info[0]
                start_time: datetime = deployment_and_flow_info[1]
                deployment_created = deployment_and_flow_info[2]
                deployment_updated = deployment_and_flow_info[3]
                deployment_name = deployment_and_flow_info[4]
                flow_namespace = deployment_and_flow_info[5]
                try:
                    ol_flow_run_id: str = self.build_run_id(
                        start_time, flow_name, flow_namespace
                    )
                except AttributeError:
                    logger.info(
                        "No Prefect run found for %s. OpenLineage event will not be emitted.",
                        prefect_flow_run_id,
                    )
                    continue

                self.ol_adapter.create_and_emit_flow_event(
                    runId=ol_flow_run_id,
                    eventType=event_state,
                    eventTime=event_time,
                    flowName=flow_name,
                    flowNamespace=flow_namespace,
                    prefectVersion=prefect_version,
                    deploymentId=deployment_id,
                    deploymentCreated=deployment_created,
                    deploymentUpdated=deployment_updated,
                    deploymentName=deployment_name,
                )

    async def collect_and_process_task_runs(
        self, prefect_version: str, event: Event, event_state: str
    ) -> None:
        task_name = event.resource.name.split("-")[0]
        event_time = datetime.fromisoformat(event.resource["prefect.state-timestamp"])
        expected_start_time = event.payload["task_run"]["expected_start_time"]
        prefect_task_run_id = event.resource.id.split(".")[-1]
        task_run = await self.client.read_task_run(prefect_task_run_id)

        if task_run:
            namespace = await self.get_job_ns(prefect_task_run_id)
            try:
                ol_task_run_id: str = self.build_run_id(
                    task_run.start_time, task_name, namespace
                )
            except AttributeError:
                logger.info("No Prefect run found for %s.", prefect_task_run_id)

            # Get datasets from Prefect Artifacts
            datasets = await self.get_artifacts_by_task_run(prefect_task_run_id)
            input_datasets = [
                dataset for dataset in datasets if dataset["dataset_type"] == "input"
            ]
            output_datasets = [
                dataset for dataset in datasets if dataset["dataset_type"] == "output"
            ]

            # Get job dependencies (Prefect "parents") info for JobDependenciesRunFacet
            parent_runs = await self.get_parent_runs(event.payload, prefect_task_run_id)

            # Get flow run info for ParentRunFacet
            for res in event.related:
                if res["prefect.resource.role"] == "flow-run":
                    flow_run_id = res["prefect.resource.id"].split(".")[-1]
                    deployment_and_flow_info = await self.get_deployment_and_flow_info(
                        flow_run_id
                    )
                    deployment_id = deployment_and_flow_info[0]
                    deployment_created = deployment_and_flow_info[2]
                    deployment_updated = deployment_and_flow_info[3]
                    deployment_name = deployment_and_flow_info[4]
                    flow_name = deployment_and_flow_info[6]
                    flow_start_time = deployment_and_flow_info[1]
                    try:
                        ol_flow_run_id: str = self.build_run_id(
                            flow_start_time, flow_name, namespace
                        )
                    except AttributeError:
                        logger.info(
                            "No Prefect run found for %s. ParentRunFacet will not be included.",
                            flow_run_id,
                        )
                        continue

            self.ol_adapter.create_and_emit_task_event(
                runId=ol_task_run_id,
                eventType=event_state,
                eventTime=event_time,
                expectedEventTime=expected_start_time,
                flowRunId=ol_flow_run_id,
                flowName=flow_name,
                taskName=task_name,
                namespace=namespace,
                jobDeps=parent_runs,
                prefectVersion=prefect_version,
                deploymentId=deployment_id,
                deploymentCreated=deployment_created,
                deploymentUpdated=deployment_updated,
                deploymentName=deployment_name,
                inputDatasets=input_datasets,
                outputDatasets=output_datasets,
            )
        else:
            logger.info(
                "No Prefect run found for %s, will not attempt to create OpenLineage event.",
                prefect_task_run_id,
            )

    async def collect_and_process_runs(self) -> None:
        try:
            os.environ.get("PREFECT_API_URL")
        except TypeError:
            logger.warn("PREFECT_API_URL not set. Prefect events will not be received.")
            return

        filter_criteria = EventFilter(
            event=EventNameFilter(
                prefix=[
                    "prefect.task-run.",
                    "prefect.flow-run.",
                    "prefect.asset.materialization.",
                ]
            )
        )

        async with get_events_subscriber(filter=filter_criteria) as subscriber:
            async with self.client:
                prefect_version = await self.get_prefect_version()

                async for event in subscriber:
                    entity_type = event.event.split(".")[1]
                    prefect_state = event.event.split(".")[-1]

                    if prefect_state in ["Running", "Completed", "Failed"]:
                        match prefect_state:
                            case "Running":
                                event_state = "START"
                            case "Completed":
                                event_state = "COMPLETE"
                            case "Failed":
                                event_state = "FAILED"

                        if entity_type == "flow-run":
                            await self.collect_and_process_flow_runs(
                                prefect_version, event, event_state
                            )

                        if entity_type == "task-run":
                            await self.collect_and_process_task_runs(
                                prefect_version, event, event_state
                            )


async def main():
    await PrefectOpenLineageListener().collect_and_process_runs()


asyncio.run(main())
