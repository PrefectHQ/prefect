import tempfile
from typing import List

from prefect.experimental.workers.base import BaseWorker
from prefect.orion.schemas.responses import WorkerFlowRunResponse
from prefect.utilities.processutils import run_process


class ProcessWorker(BaseWorker):
    type = "process"
    workflow_storage_scan_seconds = 5

    async def submit_scheduled_flow_runs(
        self, flow_run_response: List[WorkerFlowRunResponse]
    ):
        with tempfile.TemporaryDirectory(suffix="prefect") as working_dir:
            for entry in flow_run_response:
                self.logger.debug("Executing flow run %s", entry.flow_run.id)
                process = await run_process(
                    ["python", "-m", "prefect.engine", str(entry.flow_run.id)],
                    cwd=working_dir,
                )
                self.logger.debug(
                    "Flow run process exited with code %s", process.returncode
                )
