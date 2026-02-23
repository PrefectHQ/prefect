"""dbt Cloud executor for per-node orchestration.

This module provides:
- DbtCloudExecutor: Execute dbt nodes via dbt Cloud ephemeral jobs
"""

import json
import shlex
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

import prefect
from prefect.logging import get_logger
from prefect_dbt.cloud.credentials import DbtCloudCredentials
from prefect_dbt.cloud.runs import DbtCloudJobRunStatus
from prefect_dbt.core._executor import ExecutionResult
from prefect_dbt.core._manifest import DbtNode

logger = get_logger(__name__)


class DbtCloudExecutor:
    """Execute dbt nodes via dbt Cloud ephemeral jobs.

    Creates a temporary dbt Cloud job for each node (or wave) execution,
    triggers a run, polls for completion, extracts results from the run
    artifacts, and deletes the ephemeral job afterwards.

    Manifest Resolution:
        The orchestrator requires a `manifest.json` to parse the DAG.
        Call `resolve_manifest_path()` to download or generate the manifest
        and write it to a local temp file:

        1. If `defer_to_job_id` is set: downloads `manifest.json` from
           the job's most recent successful run via the dbt Cloud API.
        2. Otherwise: runs an ephemeral `dbt compile` job to generate the
           manifest, then deletes the ephemeral job.

    Args:
        credentials: DbtCloudCredentials block with API key and account ID.
        project_id: Numeric dbt Cloud project ID.
        environment_id: Numeric dbt Cloud environment ID.
        job_name_prefix: Prefix for ephemeral job names.
        timeout_seconds: Max seconds to wait for a run to complete.
        poll_frequency_seconds: Seconds between run status checks.
        threads: Override dbt `--threads` for all jobs (omitted if None).
        defer_to_job_id: Job ID to fetch `manifest.json` from. When set,
            `resolve_manifest_path()` downloads the manifest from this job's
            most recent successful run rather than generating it fresh.

    Example:

    ```python
    from prefect import flow
    from prefect_dbt import PrefectDbtOrchestrator
    from prefect_dbt.cloud import DbtCloudCredentials
    from prefect_dbt.cloud import DbtCloudExecutor

    @flow
    def run_dbt_cloud():
        executor = DbtCloudExecutor(
            credentials=DbtCloudCredentials.load("my-dbt-cloud"),
            project_id=12345,
            environment_id=67890,
            defer_to_job_id=111,  # fetch manifest from prod job
        )
        orchestrator = PrefectDbtOrchestrator(executor=executor)
        return orchestrator.run_build()
    ```
    """

    # Commands that accept the --full-refresh flag.
    _FULL_REFRESH_COMMANDS = frozenset({"run", "build", "seed"})

    def __init__(
        self,
        credentials: DbtCloudCredentials,
        project_id: int,
        environment_id: int,
        job_name_prefix: str = "prefect-orchestrator",
        timeout_seconds: int = 900,
        poll_frequency_seconds: int = 10,
        threads: int | None = None,
        defer_to_job_id: int | None = None,
    ):
        self._credentials = credentials
        self._project_id = project_id
        self._environment_id = environment_id
        self._job_name_prefix = job_name_prefix
        self._timeout_seconds = timeout_seconds
        self._poll_frequency_seconds = poll_frequency_seconds
        self._threads = threads
        self._defer_to_job_id = defer_to_job_id
        self._manifest_temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {credentials.api_key.get_secret_value()}",
                "user-agent": f"prefect-{prefect.__version__}",
                "x-dbt-partner-source": "prefect",
            },
            base_url=f"https://{credentials.domain}/api/v2/accounts/{credentials.account_id}",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_dbt_command(
        self,
        command: str,
        selectors: list[str],
        full_refresh: bool = False,
        indirect_selection: str | None = None,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
    ) -> str:
        """Build a dbt command string for a Cloud job step.

        Args:
            command: dbt sub-command (`"run"`, `"seed"`, `"build"`,
                `"test"`, `"snapshot"`, etc.)
            selectors: List of `--select` values.
            full_refresh: Whether to pass `--full-refresh`.
            indirect_selection: Optional `--indirect-selection` value (e.g.
                `"empty"` to suppress automatic test inclusion).
            target: Optional dbt target name (`--target`).
            extra_cli_args: Additional CLI arguments appended at the end.

        Returns:
            Complete dbt command string, e.g.
            `"dbt run --select path:models/staging/stg_users.sql"`.
        """
        parts = ["dbt", command]
        if self._threads is not None:
            parts.extend(["--threads", str(self._threads)])
        if full_refresh and command in self._FULL_REFRESH_COMMANDS:
            parts.append("--full-refresh")
        if indirect_selection is not None:
            parts.extend(["--indirect-selection", indirect_selection])
        if target is not None:
            parts.extend(["--target", target])
        if selectors:
            parts.extend(["--select"] + selectors)
        if extra_cli_args:
            parts.extend(extra_cli_args)
        return " ".join(shlex.quote(p) for p in parts)

    def _parse_run_results(
        self, run_results: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Parse dbt `run_results.json` into `ExecutionResult` artifacts.

        Args:
            run_results: Parsed `run_results.json` dict from the run artifact.

        Returns:
            Dict mapping `unique_id` to `{status, message, execution_time}`,
            or `None` if *run_results* is empty or missing.
        """
        if not run_results or "results" not in run_results:
            return None
        artifacts: dict[str, Any] = {}
        for result in run_results["results"]:
            uid = result.get("unique_id")
            if not uid:
                continue
            artifacts[uid] = {
                "status": str(result.get("status", "")),
                "message": result.get("message", ""),
                "execution_time": result.get("execution_time", 0.0),
            }
        return artifacts or None

    def _poll_run(self, run_id: int) -> DbtCloudJobRunStatus:
        """Poll a run until it reaches a terminal status.

        Args:
            run_id: dbt Cloud run ID to poll.

        Returns:
            Final `DbtCloudJobRunStatus`.

        Raises:
            TimeoutError: If the run does not complete within `timeout_seconds`.
        """
        start = time.monotonic()
        while True:
            resp = self._client.get(f"/runs/{run_id}/")
            resp.raise_for_status()
            status_code = resp.json()["data"].get("status")
            if DbtCloudJobRunStatus.is_terminal_status_code(status_code):
                return DbtCloudJobRunStatus(status_code)
            elapsed = time.monotonic() - start
            if elapsed >= self._timeout_seconds:
                break
            logger.debug(
                "Run %d status: %s. Polling again in %ds.",
                run_id,
                DbtCloudJobRunStatus(status_code).name
                if status_code is not None
                else "unknown",
                self._poll_frequency_seconds,
            )
            time.sleep(self._poll_frequency_seconds)
        raise TimeoutError(
            f"dbt Cloud run {run_id} did not complete within {self._timeout_seconds}s"
        )

    def _run_ephemeral_job(
        self,
        step: str,
        job_name: str,
    ) -> tuple[bool, dict[str, Any] | None, Exception | None]:
        """Create, trigger, poll, and clean up an ephemeral dbt Cloud job.

        The job is always deleted after completion or failure, even if an
        exception occurs during execution (cleanup errors are silently ignored
        to avoid masking the original error).

        Args:
            step: The dbt command to run (e.g.
                `"dbt run --select path:models/staging/stg_users.sql"`).
            job_name: Name for the ephemeral job (visible in the Cloud UI).

        Returns:
            Tuple of `(success, run_results_dict, error)`.

            - *success*: `True` if the run reached `SUCCESS` status.
            - *run_results_dict*: Parsed `run_results.json` or `None`.
            - *error*: Exception if a non-SUCCESS status or unexpected error
              occurred.
        """
        job_id: int | None = None
        try:
            create_resp = self._client.post(
                "/jobs/",
                json={
                    "project_id": self._project_id,
                    "environment_id": self._environment_id,
                    "name": job_name,
                    "execute_steps": [step],
                },
            )
            create_resp.raise_for_status()
            job_id = create_resp.json()["data"]["id"]
            logger.debug("Created ephemeral dbt Cloud job %d: %s", job_id, job_name)

            trigger_resp = self._client.post(f"/jobs/{job_id}/run/", json={})
            trigger_resp.raise_for_status()
            run_id: int = trigger_resp.json()["data"]["id"]
            logger.debug("Triggered run %d for job %d (%s)", run_id, job_id, step)

            final_status = self._poll_run(run_id)
            logger.debug("Run %d completed with status %s", run_id, final_status.name)

            run_results: dict[str, Any] | None = None
            try:
                artifact_resp = self._client.get(
                    f"/runs/{run_id}/artifacts/run_results.json"
                )
                artifact_resp.raise_for_status()
                run_results = artifact_resp.json()
            except Exception as artifact_err:
                logger.debug(
                    "Could not fetch run_results.json for run %d: %s",
                    run_id,
                    artifact_err,
                )

            success = final_status == DbtCloudJobRunStatus.SUCCESS
            error: Exception | None = None
            if not success:
                error = RuntimeError(
                    f"dbt Cloud run {run_id} finished with status {final_status.name}"
                )
            return success, run_results, error

        except Exception as exc:
            return False, None, exc

        finally:
            if job_id is not None:
                try:
                    self._client.delete(f"/jobs/{job_id}/").raise_for_status()
                    logger.debug("Deleted ephemeral dbt Cloud job %d", job_id)
                except Exception as del_err:
                    logger.warning(
                        "Failed to delete ephemeral job %d: %s", job_id, del_err
                    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_manifest_from_job(self, job_id: int) -> dict[str, Any]:
        """Fetch `manifest.json` from a job's most recent successful run.

        Uses the dbt Cloud endpoint::

            GET /accounts/{account_id}/jobs/{job_id}/artifacts/manifest.json

        Args:
            job_id: dbt Cloud job ID whose latest artifact to fetch.

        Returns:
            Parsed `manifest.json` as a dict.
        """
        resp = self._client.get(f"/jobs/{job_id}/artifacts/manifest.json")
        resp.raise_for_status()
        return resp.json()

    def generate_manifest(self) -> dict[str, Any]:
        """Generate a manifest by running an ephemeral dbt compile job.

        Creates a temporary job with `dbt compile`, triggers it, downloads
        `manifest.json` from the run artifacts, and then deletes the job.

        Returns:
            Parsed `manifest.json` as a dict.

        Raises:
            RuntimeError: If the compile job fails or the manifest artifact
                cannot be fetched.
        """
        job_name = f"{self._job_name_prefix}-compile-{int(time.time())}"
        job_id: int | None = None
        try:
            create_resp = self._client.post(
                "/jobs/",
                json={
                    "project_id": self._project_id,
                    "environment_id": self._environment_id,
                    "name": job_name,
                    "execute_steps": ["dbt compile"],
                },
            )
            create_resp.raise_for_status()
            job_id = create_resp.json()["data"]["id"]
            logger.debug("Created ephemeral compile job %d: %s", job_id, job_name)

            trigger_resp = self._client.post(f"/jobs/{job_id}/run/", json={})
            trigger_resp.raise_for_status()
            run_id: int = trigger_resp.json()["data"]["id"]
            logger.debug("Triggered compile run %d", run_id)

            final_status = self._poll_run(run_id)
            if final_status != DbtCloudJobRunStatus.SUCCESS:
                raise RuntimeError(
                    f"dbt compile job failed with status {final_status.name}. "
                    "Cannot generate manifest."
                )

            artifact_resp = self._client.get(f"/runs/{run_id}/artifacts/manifest.json")
            artifact_resp.raise_for_status()
            return artifact_resp.json()

        finally:
            if job_id is not None:
                try:
                    self._client.delete(f"/jobs/{job_id}/").raise_for_status()
                    logger.debug("Deleted ephemeral compile job %d", job_id)
                except Exception as del_err:
                    logger.warning(
                        "Failed to delete compile job %d: %s", job_id, del_err
                    )

    def resolve_manifest_path(self) -> Path:
        """Fetch or generate a manifest and write it to a temporary file.

        Called by `PrefectDbtOrchestrator` when no local `manifest_path`
        is provided.

        Strategy:

        - If `defer_to_job_id` is set, downloads `manifest.json` from
          that job's most recent successful run.
        - Otherwise, runs an ephemeral `dbt compile` job to generate it.

        Returns:
            Absolute `Path` to a local temp file containing `manifest.json`.
            The directory is owned by this executor instance and is cleaned up
            automatically when the executor is garbage collected.
        """
        if self._defer_to_job_id is not None:
            logger.info(
                "Fetching manifest.json from dbt Cloud job %d",
                self._defer_to_job_id,
            )
            manifest_data = self.fetch_manifest_from_job(self._defer_to_job_id)
        else:
            logger.info(
                "Generating manifest via ephemeral dbt compile job in environment %d",
                self._environment_id,
            )
            manifest_data = self.generate_manifest()

        # Use an isolated TemporaryDirectory tied to this executor so that:
        # 1. _resolve_target_path() gets a unique dbt target path per run.
        # 2. The directory is cleaned up automatically when the executor is
        #    garbage collected (no leaked /tmp/prefect_dbt_* directories).
        self._manifest_temp_dir = tempfile.TemporaryDirectory(prefix="prefect_dbt_")
        manifest_path = Path(self._manifest_temp_dir.name) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        logger.debug("Wrote manifest to %s", manifest_path)
        return manifest_path

    def execute_node(
        self,
        node: DbtNode,
        command: str,
        full_refresh: bool = False,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
    ) -> ExecutionResult:
        """Execute a single dbt node via an ephemeral dbt Cloud job.

        Creates a job with a single step (e.g.
        `"dbt run --select path:models/staging/stg_users.sql"`), triggers it,
        waits for completion, extracts results from `run_results.json`, and
        deletes the job.

        Args:
            node: The `DbtNode` to execute.
            command: dbt command (`"run"`, `"seed"`, `"snapshot"`, `"test"`).
            full_refresh: Whether to pass `--full-refresh` (ignored for
                commands that don't support it).
            target: Optional dbt target name (`--target`).
            extra_cli_args: Additional CLI arguments appended to the command.

        Returns:
            `ExecutionResult` with success/failure status and per-node artifacts.
        """
        step = self._build_dbt_command(
            command,
            selectors=[node.dbt_selector],
            full_refresh=full_refresh,
            target=target,
            extra_cli_args=extra_cli_args,
        )
        # Truncate node name to keep job names reasonable in the Cloud UI.
        safe_name = node.name[:40] if len(node.name) > 40 else node.name
        job_name = f"{self._job_name_prefix}-{command}-{safe_name}"

        success, run_results, error = self._run_ephemeral_job(step, job_name)
        artifacts = self._parse_run_results(run_results)

        # Union of requested node IDs and any IDs from run_results.json.
        result_ids = [node.unique_id]
        if artifacts:
            result_ids = list(dict.fromkeys(result_ids + list(artifacts)))

        return ExecutionResult(
            success=success,
            node_ids=result_ids,
            error=error,
            artifacts=artifacts,
        )

    def execute_wave(
        self,
        nodes: list[DbtNode],
        full_refresh: bool = False,
        indirect_selection: str | None = None,
        target: str | None = None,
        extra_cli_args: list[str] | None = None,
    ) -> ExecutionResult:
        """Execute a wave of dbt nodes via an ephemeral dbt Cloud job.

        Uses `dbt build --select sel1 sel2 ...` to execute all nodes in the
        wave in a single job step.

        Args:
            nodes: List of `DbtNode` objects to execute.
            full_refresh: Whether to pass `--full-refresh`.
            indirect_selection: Optional `--indirect-selection` value (e.g.
                `"empty"` to suppress automatic test inclusion).
            target: Optional dbt target name (`--target`).
            extra_cli_args: Additional CLI arguments appended to the command.

        Returns:
            `ExecutionResult` with success/failure status and per-node artifacts.

        Raises:
            ValueError: If *nodes* is empty.
        """
        if not nodes:
            raise ValueError("Cannot execute an empty wave")

        selectors = [node.dbt_selector for node in nodes]
        step = self._build_dbt_command(
            "build",
            selectors=selectors,
            full_refresh=full_refresh,
            indirect_selection=indirect_selection,
            target=target,
            extra_cli_args=extra_cli_args,
        )
        job_name = f"{self._job_name_prefix}-build-wave"

        success, run_results, error = self._run_ephemeral_job(step, job_name)
        artifacts = self._parse_run_results(run_results)

        node_ids = [node.unique_id for node in nodes]
        if artifacts:
            result_ids = list(dict.fromkeys(node_ids + list(artifacts)))
        else:
            result_ids = list(node_ids)

        return ExecutionResult(
            success=success,
            node_ids=result_ids,
            error=error,
            artifacts=artifacts,
        )
