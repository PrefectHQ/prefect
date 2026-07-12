import logging
from datetime import datetime

from openlineage.client import OpenLineageClient
from openlineage.client.event_v2 import Dataset
from openlineage.client.facet import (
    JobTypeJobFacet,
    NominalTimeRunFacet,
    ParentRunFacet,
)
from openlineage.client.facet_v2 import job_dependencies_run, processing_engine_run
from openlineage.client.run import Job, Run, RunEvent, RunState

from prefect_openlineage.facets import PrefectDeploymentRunFacet

PRODUCER: str = (
    "https://github.com/prefectHQ/prefect/src/integrations/prefect-openlineage"
)

logger: logging.Logger = logging.getLogger(__name__)


class PrefectOpenLineageAdapter:
    def __init__(self, client: OpenLineageClient | None = None):
        self.client = client or OpenLineageClient()

    def create_and_emit_flow_event(
        self,
        runId: str,
        eventType: str,
        eventTime: datetime,
        flowName: str = None,
        flowNamespace: str = None,
        prefectVersion: str = None,
        deploymentId: str = None,
        deploymentCreated: str = None,
        deploymentUpdated: str = None,
        deploymentName: str = None,
    ) -> RunEvent:

        match eventType:
            case "START":
                eventType = RunState.START
            case "COMPLETE":
                eventType = RunState.COMPLETE
            case "FAILED":
                eventType = RunState.FAIL

        run_facets = {
            "prefectDeployment": PrefectDeploymentRunFacet(
                deployment_id=deploymentId,
                created=deploymentCreated,
                updated=deploymentUpdated,
                name=deploymentName,
            ),
            "processingEngine": processing_engine_run.ProcessingEngineRunFacet(
                version=prefectVersion, name="Prefect"
            ),
        }

        job_facets = {
            "jobType": JobTypeJobFacet(
                processingType="BATCH", integration="Prefect", jobType="FLOW"
            )
        }

        run_event = RunEvent(
            eventType=eventType,
            eventTime=eventTime.isoformat(),
            run=Run(runId, run_facets),
            job=Job(flowNamespace, flowName, job_facets),
            producer=PRODUCER,
        )

        try:
            self.client.emit(run_event)
            logger.info("Emitted OpenLineage event successfully.")
        except Exception:
            logger.exception("OpenLineage event not sent.")

    def create_and_emit_task_event(
        self,
        runId: str,
        eventType: str,
        eventTime: datetime,
        expectedEventTime: datetime = None,
        flowRunId: str = None,
        flowName: str = None,
        taskName: str = None,
        namespace: str = None,
        jobDeps: list = None,
        prefectVersion: str = None,
        deploymentId: str = None,
        deploymentCreated: str = None,
        deploymentUpdated: str = None,
        deploymentName: str = None,
        inputDatasets: list = [],
        outputDatasets: list = [],
    ) -> RunEvent:

        match eventType:
            case "START":
                eventType = RunState.START
            case "COMPLETE":
                eventType = RunState.COMPLETE
            case "FAILED":
                eventType = RunState.FAIL

        run_facets = {
            "nominalTime": NominalTimeRunFacet(nominalStartTime=expectedEventTime),
            "parentRun": ParentRunFacet(
                run={"runId": flowRunId}, job={"namespace": namespace, "name": flowName}
            ),
            "prefectDeployment": PrefectDeploymentRunFacet(
                deployment_id=deploymentId,
                created=deploymentCreated,
                updated=deploymentUpdated,
                name=deploymentName,
            ),
            "processingEngine": processing_engine_run.ProcessingEngineRunFacet(
                version=prefectVersion, name="Prefect"
            ),
        }
        if jobDeps:
            upstream_jobs = [
                job_dependencies_run.JobDependency(
                    job=job_dependencies_run.JobIdentifier(
                        namespace=dep["namespace"], name=dep["name"]
                    )
                )
                for dep in jobDeps
            ]
            run_facets["jobDependencies"] = (
                job_dependencies_run.JobDependenciesRunFacet(upstream=upstream_jobs)
            )

        job_facets = {
            "jobType": JobTypeJobFacet(
                processingType="BATCH", integration="Prefect", jobType="TASK"
            )
        }

        inputs = [
            Dataset(namespace=dataset["uri"], name=dataset["table"])
            for dataset in inputDatasets
        ]
        outputs = [
            Dataset(namespace=dataset["uri"], name=dataset["table"])
            for dataset in outputDatasets
        ]

        run_event = RunEvent(
            eventType=eventType,
            eventTime=eventTime.isoformat(),
            run=Run(runId, run_facets),
            job=Job(namespace, taskName, job_facets),
            producer=PRODUCER,
            inputs=inputs,
            outputs=outputs,
        )

        try:
            self.client.emit(run_event)
            logger.info("Emitted OpenLineage event successfully.")
        except Exception:
            logger.exception("OpenLineage event not sent.")
