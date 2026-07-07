"""
Module containing flows for interacting with Databricks
"""

import asyncio
import inspect
from logging import Logger
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from prefect import flow
from prefect.logging import get_run_logger
from prefect_databricks import DatabricksCredentials
from prefect_databricks.jobs import (
    jobs_run_now,
    jobs_runs_get,
    jobs_runs_get_output,
    jobs_runs_submit,
)
from prefect_databricks.models.jobs import (
    AccessControlRequest,
    GitSource,
    RunLifeCycleState,
    RunResultState,
    RunSubmitTaskSettings,
)

JobMetadata = Dict[str, Any]
NotebookOutput = Dict[str, Any]


class DatabricksJobTerminated(Exception):
    """Raised when Databricks jobs runs submit terminates"""


class DatabricksJobSkipped(Exception):
    """Raised when Databricks jobs runs submit skips"""


class DatabricksJobInternalError(Exception):
    """Raised when Databricks jobs runs submit encounters internal error"""


class DatabricksJobRunTimedOut(Exception):
    """
    Raised when Databricks jobs runs does not complete in the configured max
    wait seconds
    """


TERMINAL_STATUS_CODES = (
    RunLifeCycleState.terminated.value,
    RunLifeCycleState.skipped.value,
    RunLifeCycleState.internalerror.value,
)


@flow(
    name="Submit jobs runs and wait for completion",
    description=(
        "Triggers a Databricks jobs runs and waits for the triggered runs to complete."
    ),
)
async def jobs_runs_submit_and_wait_for_completion(
    databricks_credentials: DatabricksCredentials,
    tasks: Optional[List[RunSubmitTaskSettings]] = None,
    run_name: Optional[str] = None,
    max_wait_seconds: int = 900,
    poll_frequency_seconds: int = 10,
    git_source: Optional[GitSource] = None,
    timeout_seconds: Optional[int] = None,
    idempotency_token: Optional[str] = None,
    access_control_list: Optional[List[AccessControlRequest]] = None,
    return_metadata: bool = False,
    job_submission_handler: Optional[Callable] = None,
    **jobs_runs_submit_kwargs: Dict[str, Any],
) -> Union[NotebookOutput, Tuple[NotebookOutput, JobMetadata], None]:
    """
    Flow that triggers a job run and waits for the triggered run to complete.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        tasks:
            A list of task specifications (`RunSubmitTaskSettings`) to run. Each
            task defines its key, the cluster it runs on, and the work to do
            (a notebook, JAR, Python, SQL, or dbt task).
        run_name: An optional name for the run. Defaults to `Untitled`.
        git_source:
            An optional remote Git repository (`GitSource`) containing the
            notebooks used by the run's notebook tasks. This functionality is in
            Public Preview.
        timeout_seconds:
            An optional timeout, in seconds, applied to the run. The default is
            no timeout.
        idempotency_token:
            An optional token (at most 64 characters) guaranteeing the
            idempotency of the request. If a run with the token already exists,
            the existing run's ID is returned instead of creating a new run. See
            the Databricks docs on job idempotency for details.
        access_control_list:
            A list of permissions (`AccessControlRequest`) to set on the run.
        max_wait_seconds:
            The maximum number of seconds to wait for the entire flow to
            complete.
        poll_frequency_seconds:
            The number of seconds to wait between checks for run completion.
        return_metadata:
            If True, return a tuple of the notebook output and the run metadata.
            By default, only the notebook output is returned.
        job_submission_handler:
            An optional callable to intercept job submission.
        **jobs_runs_submit_kwargs:
            Additional keyword arguments to pass to `jobs_runs_submit`.

    Returns:
        Either a dict or a tuple (depends on `return_metadata`) comprised of
        * task_notebook_outputs: dictionary of task keys to its corresponding notebook output;
          this is the only object returned by default from this method
        * jobs_runs_metadata: dictionary containing IDs of the jobs runs tasks; this is only
          returned if `return_metadata=True`.

    Examples:
        Submit jobs runs and wait.
        ```python
        from prefect import flow
        from prefect_databricks import DatabricksCredentials
        from prefect_databricks.flows import jobs_runs_submit_and_wait_for_completion
        from prefect_databricks.models.jobs import (
            AutoScale,
            AwsAttributes,
            JobTaskSettings,
            NotebookTask,
            NewCluster,
        )

        @flow
        async def jobs_runs_submit_and_wait_for_completion_flow(notebook_path, **base_parameters):
            databricks_credentials = await DatabricksCredentials.load("BLOCK_NAME")

            # specify new cluster settings
            aws_attributes = AwsAttributes(
                availability="SPOT",
                zone_id="us-west-2a",
                ebs_volume_type="GENERAL_PURPOSE_SSD",
                ebs_volume_count=3,
                ebs_volume_size=100,
            )
            auto_scale = AutoScale(min_workers=1, max_workers=2)
            new_cluster = NewCluster(
                aws_attributes=aws_attributes,
                autoscale=auto_scale,
                node_type_id="m4.large",
                spark_version="10.4.x-scala2.12",
                spark_conf={"spark.speculation": True},
            )

            # specify notebook to use and parameters to pass
            notebook_task = NotebookTask(
                notebook_path=notebook_path,
                base_parameters=base_parameters,
            )

            # compile job task settings
            job_task_settings = JobTaskSettings(
                new_cluster=new_cluster,
                notebook_task=notebook_task,
                task_key="prefect-task"
            )

            multi_task_runs = await jobs_runs_submit_and_wait_for_completion(
                databricks_credentials=databricks_credentials,
                run_name="prefect-job",
                tasks=[job_task_settings]
            )

            return multi_task_runs
        ```
    """  # noqa
    logger = get_run_logger()

    # submit the jobs runs
    multi_task_jobs_runs_future = jobs_runs_submit.submit(
        databricks_credentials=databricks_credentials,
        tasks=tasks,
        run_name=run_name,
        git_source=git_source,
        timeout_seconds=timeout_seconds,
        idempotency_token=idempotency_token,
        access_control_list=access_control_list,
        **jobs_runs_submit_kwargs,
    )
    multi_task_jobs_runs = multi_task_jobs_runs_future.result()
    if job_submission_handler:
        result = job_submission_handler(multi_task_jobs_runs)
        if inspect.isawaitable(result):
            await result
    multi_task_jobs_runs_id = multi_task_jobs_runs["run_id"]

    # wait for all the jobs runs to complete in a separate flow
    # for a cleaner radar interface
    jobs_runs_state, jobs_runs_metadata = await jobs_runs_wait_for_completion(
        multi_task_jobs_runs_id=multi_task_jobs_runs_id,
        databricks_credentials=databricks_credentials,
        run_name=run_name,
        max_wait_seconds=max_wait_seconds,
        poll_frequency_seconds=poll_frequency_seconds,
    )

    # fetch the state results
    jobs_runs_life_cycle_state = jobs_runs_state["life_cycle_state"]
    jobs_runs_state_message = jobs_runs_state["state_message"]

    # return results or raise error
    if jobs_runs_life_cycle_state == RunLifeCycleState.terminated.value:
        jobs_runs_result_state = jobs_runs_state.get("result_state", None)
        if jobs_runs_result_state == RunResultState.success.value:
            task_notebook_outputs = {}
            for task in jobs_runs_metadata["tasks"]:
                task_key = task["task_key"]
                task_run_id = task["run_id"]
                task_run_output_future = jobs_runs_get_output.submit(
                    run_id=task_run_id,
                    databricks_credentials=databricks_credentials,
                )
                task_run_output = task_run_output_future.result()
                task_run_notebook_output = task_run_output.get("notebook_output", {})
                task_notebook_outputs[task_key] = task_run_notebook_output
            logger.info(
                "Databricks Jobs Runs Submit (%s ID %s) completed successfully!",
                run_name,
                multi_task_jobs_runs_id,
            )
            if return_metadata:
                return task_notebook_outputs, jobs_runs_metadata
            return task_notebook_outputs
        else:
            raise DatabricksJobTerminated(
                f"Databricks Jobs Runs Submit "
                f"({run_name} ID {multi_task_jobs_runs_id}) "
                f"terminated with result state, {jobs_runs_result_state}: "
                f"{jobs_runs_state_message}"
            )
    elif jobs_runs_life_cycle_state == RunLifeCycleState.skipped.value:
        raise DatabricksJobSkipped(
            f"Databricks Jobs Runs Submit ({run_name} ID "
            f"{multi_task_jobs_runs_id}) was skipped: {jobs_runs_state_message}.",
        )
    elif jobs_runs_life_cycle_state == RunLifeCycleState.internalerror.value:
        raise DatabricksJobInternalError(
            f"Databricks Jobs Runs Submit ({run_name} ID "
            f"{multi_task_jobs_runs_id}) "
            f"encountered an internal error: {jobs_runs_state_message}.",
        )


def _update_and_log_state_changes(
    job_or_task_states: Dict[str, Any],
    job_or_task_metadata: Dict[str, Any],
    logger: Logger,
    run_type: str = "Task",
) -> Dict[str, Any]:
    """
    Stores the states of a job or task to its collection and logs the output
    if it changes.

    Args:
        job_or_task_states: The dictionary of job or task states.
        job_or_task_metadata: Metadata object containing run, url and state
        logger: Logger instance to log with.
        run_type: String indicating if is job or task, defaults to Task

    Returns
        A copy of the job_or_task_states dictionary with any state updates
    """

    run_id = job_or_task_metadata.get("run_id", "")
    run_page_url = job_or_task_metadata.get("run_page_url", "")
    state = job_or_task_metadata.get("state", {})

    string_run_id = str(run_id)

    job_or_task_states_copy = job_or_task_states.copy()

    if string_run_id not in job_or_task_states_copy:
        job_or_task_states_copy[string_run_id] = {}

    new_item = {}
    new_item["run_page_url"] = run_page_url
    new_item["run_id"] = run_id
    new_item["state"] = state

    life_cycle_state = state.get("life_cycle_state", "")
    state_message = state.get("state_message", "")
    result_state = state.get("result_state", "")

    if "state" in job_or_task_states_copy[string_run_id]:
        existing_state = job_or_task_states_copy[string_run_id]["state"]
        existing_life_cycle_state = existing_state.get("life_cycle_state", "")
        existing_state_message = existing_state.get("state_message", "")
        existing_result_state = existing_state.get("result_state", "")

        if (
            life_cycle_state == existing_life_cycle_state
            and state_message == existing_state_message
            and result_state == existing_result_state
        ):
            return job_or_task_states_copy

    logger.info(
        "%s Run '%s' states updated!\n"
        "Life cycle: '%s'\n"
        "Result: '%s'\n"
        "Message '%s'\n"
        "Url: %s\n",
        run_type,
        run_id,
        life_cycle_state,
        result_state,
        state_message,
        run_page_url,
    )

    job_or_task_states_copy[string_run_id] = new_item
    return job_or_task_states_copy


@flow(
    name="Wait for completion of jobs runs",
    description="Waits for the jobs runs to finish running",
)
async def jobs_runs_wait_for_completion(
    multi_task_jobs_runs_id: int,
    databricks_credentials: DatabricksCredentials,
    run_name: Optional[str] = None,
    max_wait_seconds: int = 900,
    poll_frequency_seconds: int = 10,
):
    """
    Flow that triggers a job run and waits for the triggered run to complete.

    Args:
        run_name: The name of the jobs runs task.
        multi_task_jobs_runs_id: The ID of the jobs runs task to watch.
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        max_wait_seconds:
            Maximum number of seconds to wait for the entire flow to complete.
        poll_frequency_seconds: Number of seconds to wait in between checks for
            run completion.

    Returns:
        jobs_runs_state: A dict containing the jobs runs life cycle state and message.
        jobs_runs_metadata: A dict containing IDs of the jobs runs tasks.

    Examples:
        Waits for completion on jobs runs.
        ```python
        from prefect import flow
        from prefect_databricks import DatabricksCredentials
        from prefect_databricks.flows import jobs_runs_wait_for_completion

        @flow
        async def jobs_runs_wait_for_completion_flow():
            databricks_credentials = await DatabricksCredentials.load("BLOCK_NAME")
            return await jobs_runs_wait_for_completion(
                multi_task_jobs_runs_id=45429,
                databricks_credentials=databricks_credentials,
                run_name="my_run_name",
                max_wait_seconds=1800,  # 30 minutes
                poll_frequency_seconds=120,  # 2 minutes
            )
        ```
    """
    logger = get_run_logger()

    seconds_waited_for_run_completion = 0
    wait_for = []

    jobs_status = {}
    tasks_status = {}
    while seconds_waited_for_run_completion <= max_wait_seconds:
        jobs_runs_metadata_future = jobs_runs_get.submit(
            run_id=multi_task_jobs_runs_id,
            databricks_credentials=databricks_credentials,
            wait_for=wait_for,
        )
        wait_for = [jobs_runs_metadata_future]

        jobs_runs_metadata = jobs_runs_metadata_future.result()
        jobs_status = _update_and_log_state_changes(
            jobs_status, jobs_runs_metadata, logger, "Job"
        )
        jobs_runs_metadata_tasks = jobs_runs_metadata.get("tasks", [])
        for task_metadata in jobs_runs_metadata_tasks:
            tasks_status = _update_and_log_state_changes(
                tasks_status, task_metadata, logger, "Task"
            )

        jobs_runs_state = jobs_runs_metadata.get("state", {})
        jobs_runs_life_cycle_state = jobs_runs_state["life_cycle_state"]
        if jobs_runs_life_cycle_state in TERMINAL_STATUS_CODES:
            return jobs_runs_state, jobs_runs_metadata

        logger.info("Waiting for %s seconds.", poll_frequency_seconds)
        await asyncio.sleep(poll_frequency_seconds)
        seconds_waited_for_run_completion += poll_frequency_seconds

    raise DatabricksJobRunTimedOut(
        f"Max wait time of {max_wait_seconds} seconds exceeded while waiting "
        f"for job run ({run_name} ID {multi_task_jobs_runs_id})"
    )


@flow(
    name="Submit existing job runs and wait for completion",
    description=(
        "Triggers a Databricks jobs runs and waits for the triggered runs to complete."
    ),
)
async def jobs_runs_submit_by_id_and_wait_for_completion(
    databricks_credentials: DatabricksCredentials,
    job_id: int,
    idempotency_token: Optional[str] = None,
    jar_params: Optional[List[str]] = None,
    max_wait_seconds: int = 900,
    poll_frequency_seconds: int = 10,
    notebook_params: Optional[Dict] = None,
    python_params: Optional[List[str]] = None,
    spark_submit_params: Optional[List[str]] = None,
    python_named_params: Optional[Dict] = None,
    pipeline_params: Optional[str] = None,
    sql_params: Optional[Dict] = None,
    dbt_commands: Optional[List] = None,
    job_submission_handler: Optional[Callable] = None,
    **jobs_runs_submit_kwargs: Dict[str, Any],
) -> Dict:
    """flow that triggers an existing job and waits for its completion

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        job_id: The ID of the Databricks job to run.
        idempotency_token:
            An optional token (at most 64 characters) guaranteeing the
            idempotency of the request. If a run with the token already exists,
            the existing run's ID is returned instead of creating a new run. See
            the Databricks docs on job idempotency for details.
        jar_params:
            A list of command-line parameters for Spark JAR tasks, used to invoke
            the main class. Cannot be combined with `notebook_params`, and its
            JSON representation cannot exceed 10,000 bytes.
        max_wait_seconds:
            The maximum number of seconds to wait for the entire flow to
            complete.
        poll_frequency_seconds:
            The number of seconds to wait between checks for run completion.
        notebook_params:
            A map of key-value parameters for notebook tasks, accessible through
            `dbutils.widgets.get`. Cannot be combined with `jar_params`, and its
            JSON representation cannot exceed 10,000 bytes.
        python_params:
            A list of command-line parameters for Python tasks. ASCII characters
            only; its JSON representation cannot exceed 10,000 bytes.
        spark_submit_params:
            A list of parameters passed to the `spark-submit` script. ASCII
            characters only; its JSON representation cannot exceed 10,000 bytes.
        python_named_params:
            A map of named parameters for Python wheel tasks.
        pipeline_params:
            Parameters for Delta Live Tables pipeline tasks, such as whether to
            trigger a full refresh.
        sql_params:
            A map of key-value parameters for SQL tasks. SQL alert tasks do not
            support custom parameters.
        dbt_commands:
            A list of dbt commands to run for dbt tasks, for example
            `["dbt deps", "dbt seed", "dbt run"]`.
        job_submission_handler:
            An optional callable to intercept job submission.

    Raises:
        DatabricksJobTerminated:
            Raised when the Databricks job run is terminated with a non-successful
            result state.
        DatabricksJobSkipped: Raised when the Databricks job run is skipped.
        DatabricksJobInternalError:
            Raised when the Databricks job run encounters an internal error.

    Returns:
        Dict: A dictionary containing information about the completed job run.

    Examples:
        ```python
        import asyncio

        from prefect import flow
        from prefect_databricks import DatabricksCredentials
        from prefect_databricks.flows import (
            jobs_runs_submit_by_id_and_wait_for_completion,
        )


        @flow
        async def submit_existing_job(block_name: str, job_id: int):
            databricks_credentials = await DatabricksCredentials.load(block_name)

            run = await jobs_runs_submit_by_id_and_wait_for_completion(
                databricks_credentials=databricks_credentials, job_id=job_id
            )

            return run


        asyncio.run(submit_existing_job(block_name="db-creds", job_id=1234))
        ```
    """
    logger = get_run_logger()

    # submit the jobs runs

    jobs_runs_future = jobs_run_now.submit(
        databricks_credentials=databricks_credentials,
        job_id=job_id,
        idempotency_token=idempotency_token,
        jar_params=jar_params,
        notebook_params=notebook_params,
        python_params=python_params,
        spark_submit_params=spark_submit_params,
        python_named_params=python_named_params,
        pipeline_params=pipeline_params,
        sql_params=sql_params,
        dbt_commands=dbt_commands,
        **jobs_runs_submit_kwargs,
    )

    jobs_runs = jobs_runs_future.result()

    if job_submission_handler:
        result = job_submission_handler(jobs_runs)
        if inspect.isawaitable(result):
            await result
    job_run_id = jobs_runs["run_id"]

    # wait for all the jobs runs to complete in a separate flow
    # for a cleaner radar interface
    jobs_runs_state, jobs_runs_metadata = await jobs_runs_wait_for_completion(
        multi_task_jobs_runs_id=job_run_id,
        databricks_credentials=databricks_credentials,
        max_wait_seconds=max_wait_seconds,
        poll_frequency_seconds=poll_frequency_seconds,
    )

    # fetch the state results
    jobs_runs_life_cycle_state = jobs_runs_state["life_cycle_state"]
    jobs_runs_state_message = jobs_runs_state["state_message"]

    # return results or raise error
    if jobs_runs_life_cycle_state == RunLifeCycleState.terminated.value:
        jobs_runs_result_state = jobs_runs_state.get("result_state", None)
        if jobs_runs_result_state == RunResultState.success.value:
            task_notebook_outputs = {}
            for task in jobs_runs_metadata["tasks"]:
                task_key = task["task_key"]
                task_run_id = task["run_id"]
                task_run_output_future = jobs_runs_get_output.submit(
                    run_id=task_run_id,
                    databricks_credentials=databricks_credentials,
                )
                task_run_output = task_run_output_future.result()
                task_run_notebook_output = task_run_output.get("notebook_output", {})
                task_notebook_outputs[task_key] = task_run_notebook_output
            logger.info(
                f"Databricks Jobs Runs Submit {job_id} completed successfully!",
            )
            return task_notebook_outputs
        else:
            raise DatabricksJobTerminated(
                f"Databricks Jobs Runs Submit ID {job_id} "
                f"terminated with result state, {jobs_runs_result_state}: "
                f"{jobs_runs_state_message}"
            )
    elif jobs_runs_life_cycle_state == RunLifeCycleState.skipped.value:
        raise DatabricksJobSkipped(
            f"Databricks Jobs Runs Submit ID "
            f"{job_id} was skipped: {jobs_runs_state_message}.",
        )
    elif jobs_runs_life_cycle_state == RunLifeCycleState.internalerror.value:
        raise DatabricksJobInternalError(
            f"Databricks Jobs Runs Submit ID "
            f"{job_id} "
            f"encountered an internal error: {jobs_runs_state_message}.",
        )
