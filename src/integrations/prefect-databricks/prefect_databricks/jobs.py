"""
This is a module containing tasks for interacting with:
Databricks jobs
"""

# This module was auto-generated using prefect-collection-generator so
# manually editing this file is not recommended. If this module
# is outdated, rerun scripts/generate.py.

# OpenAPI spec: jobs-2.1-aws.yaml
# Updated at: 2022-12-10T01:04:37.047265

from typing import Any, Dict, List, Optional

from prefect import task
from prefect_databricks import DatabricksCredentials
from prefect_databricks.models import jobs as models  # noqa
from prefect_databricks.rest import HTTPMethod, _unpack_contents, execute_endpoint


@task
async def jobs_runs_export(
    run_id: int,
    databricks_credentials: "DatabricksCredentials",
    views_to_export: Optional["models.ViewsToExport"] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Export and retrieve the job run task.

    Args:
        run_id:
            The canonical identifier for the run. This field is required.
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        views_to_export:
            Which views to export (CODE, DASHBOARDS, or ALL). Defaults to CODE.

    Returns:
        Upon success, a dict of the response containing the key `views`
        (`List["models.ViewItem"]`).

    Note:
        Calls the `/2.0/jobs/runs/export` API endpoint. Possible responses are
        200 (run was exported successfully), 400 (the request was malformed;
        see the JSON response for error details), 401 (the request was
        unauthorized), and 500 (the request was not handled correctly due to a
        server error).
    """  # noqa
    endpoint = "/2.0/jobs/runs/export"  # noqa

    responses = {
        200: "Run was exported successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    params = {
        "run_id": run_id,
        "views_to_export": views_to_export,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.GET,
        params=params,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_create(
    databricks_credentials: "DatabricksCredentials",
    name: str = "Untitled",
    tags: Dict = None,
    tasks: Optional[List["models.JobTaskSettings"]] = None,
    job_clusters: Optional[List["models.JobCluster"]] = None,
    email_notifications: "models.JobEmailNotifications" = None,
    webhook_notifications: "models.WebhookNotifications" = None,
    timeout_seconds: Optional[int] = None,
    schedule: "models.CronSchedule" = None,
    max_concurrent_runs: Optional[int] = None,
    git_source: "models.GitSource" = None,
    format: Optional[str] = None,
    access_control_list: Optional[List["models.AccessControlRequest"]] = None,
    parameters: Optional[List["models.JobParameter"]] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Create a new job.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        name: An optional name for the job.
        tags:
            A map of string key-value tags associated with the job, up to a
            maximum of 25. These are forwarded to jobs clusters as cluster tags.
        tasks:
            A list of task specifications (`JobTaskSettings`) to execute. Each
            task defines its key, the cluster it runs on, and the work to do
            (a notebook, JAR, Python, SQL, or dbt task).
        job_clusters:
            A list of shared job-cluster specifications (`JobCluster`) that tasks
            can reuse. Libraries must be declared per task, not on a shared
            cluster.
        email_notifications:
            Email addresses (`JobEmailNotifications`) to notify when runs of the
            job start, succeed, or fail.
        webhook_notifications:
            System notification IDs (`WebhookNotifications`) to call when runs of
            the job start, succeed, or fail, up to three destinations per event.
        timeout_seconds:
            An optional timeout, in seconds, applied to each run of the job. The
            default is no timeout.
        schedule:
            An optional periodic schedule (`CronSchedule`) expressed with Quartz
            cron syntax. By default the job runs only when triggered manually or
            through the API.
        max_concurrent_runs:
            The maximum number of concurrent runs allowed. Defaults to 1 and
            cannot exceed 1000; set to 0 to skip all new runs.
        git_source:
            An optional remote Git repository (`GitSource`) containing the
            notebooks used by the job's notebook tasks. This functionality is in
            Public Preview.
        format:
            The format of the job. Ignored in create, update, and reset calls;
            always `MULTI_TASK` on the Jobs API 2.1.
        access_control_list:
            A list of permissions (`AccessControlRequest`) to set on the job.
        parameters:
            Job-level parameter definitions (`JobParameter`).

    Returns:
        Upon success, a dict of the response containing the key `job_id`
        (`int`).

    Note:
        Calls the `/2.1/jobs/create` API endpoint. Possible responses are
        200 (job was created successfully), 400 (the request was malformed;
        see the JSON response for error details), 401 (the request was
        unauthorized), and 500 (the request was not handled correctly due to a
        server error).
    """  # noqa
    endpoint = "/2.1/jobs/create"  # noqa

    responses = {
        200: "Job was created successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    json_payload = {
        "name": name,
        "tags": tags,
        "tasks": tasks,
        "job_clusters": job_clusters,
        "email_notifications": email_notifications,
        "webhook_notifications": webhook_notifications,
        "timeout_seconds": timeout_seconds,
        "schedule": schedule,
        "max_concurrent_runs": max_concurrent_runs,
        "git_source": git_source,
        "format": format,
        "access_control_list": access_control_list,
        "parameters": parameters,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.POST,
        json=json_payload,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_delete(
    databricks_credentials: "DatabricksCredentials",
    job_id: Optional[int] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Deletes a job.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        job_id:
            The canonical identifier of the job to delete. This field is required,
            e.g. `11223344`.

    Returns:
        Upon success, an empty dict.

    Note:
        Calls the `/2.1/jobs/delete` API endpoint. Possible responses are
        200 (job was deleted successfully), 400 (the request was malformed;
        see the JSON response for error details), 401 (the request was
        unauthorized), and 500 (the request was not handled correctly due to a
        server error).
    """  # noqa
    endpoint = "/2.1/jobs/delete"  # noqa

    responses = {
        200: "Job was deleted successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    json_payload = {
        "job_id": job_id,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.POST,
        json=json_payload,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_get(
    job_id: int,
    databricks_credentials: "DatabricksCredentials",
) -> Dict[str, Any]:  # pragma: no cover
    """
    Retrieves the details for a single job.

    Args:
        job_id:
            The canonical identifier of the job to retrieve information about. This
            field is required.
        databricks_credentials:
            Credentials to use for authentication with Databricks.

    Returns:
        Upon success, a dict of the response containing the keys `job_id`
        (`int`), `creator_user_name` (`str`), `run_as_user_name` (`str`),
        `settings` (`"models.JobSettings"`), and `created_time` (`int`).

    Note:
        Calls the `/2.1/jobs/get` API endpoint. Possible responses are
        200 (job was retrieved successfully), 400 (the request was malformed;
        see the JSON response for error details), 401 (the request was
        unauthorized), and 500 (the request was not handled correctly due to a
        server error).
    """  # noqa
    endpoint = "/2.1/jobs/get"  # noqa

    responses = {
        200: "Job was retrieved successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    params = {
        "job_id": job_id,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.GET,
        params=params,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_list(
    databricks_credentials: "DatabricksCredentials",
    limit: int = 20,
    offset: int = 0,
    name: Optional[str] = None,
    expand_tasks: bool = False,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Retrieves a list of jobs.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        limit:
            The number of jobs to return. This value must be greater than 0 and less
            or equal to 25. The default value is 20.
        offset:
            The offset of the first job to return, relative to the most recently
            created job.
        name:
            A filter on the list based on the exact (case insensitive) job name.
        expand_tasks:
            Whether to include task and cluster details in the response.

    Returns:
        Upon success, a dict of the response containing the keys `jobs`
        (`List["models.Job"]`) and `has_more` (`bool`).

    Note:
        Calls the `/2.1/jobs/list` API endpoint. Possible responses are
        200 (list of jobs was retrieved successfully), 400 (the request was
        malformed; see the JSON response for error details), 401 (the request
        was unauthorized), and 500 (the request was not handled correctly due
        to a server error).
    """  # noqa
    endpoint = "/2.1/jobs/list"  # noqa

    responses = {
        200: "List of jobs was retrieved successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    params = {
        "limit": limit,
        "offset": offset,
        "name": name,
        "expand_tasks": expand_tasks,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.GET,
        params=params,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_reset(
    databricks_credentials: "DatabricksCredentials",
    job_id: Optional[int] = None,
    new_settings: "models.JobSettings" = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Overwrites all the settings for a specific job. Use the Update endpoint to
    update job settings partially.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        job_id: The canonical identifier of the job to reset. Required.
        new_settings:
            The complete new settings (`JobSettings`) for the job. These
            entirely replace the job's existing settings: changes to
            `timeout_seconds` apply to active runs, while changes to other
            fields apply only to future runs.

    Returns:
        Upon success, an empty dict.

    Note:
        Calls the `/2.1/jobs/reset` API endpoint. Possible responses are
        200 (job was overwritten successfully), 400 (the request was malformed;
        see the JSON response for error details), 401 (the request was
        unauthorized), and 500 (the request was not handled correctly due to a
        server error).
    """  # noqa
    endpoint = "/2.1/jobs/reset"  # noqa

    responses = {
        200: "Job was overwritten successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    json_payload = {
        "job_id": job_id,
        "new_settings": new_settings,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.POST,
        json=json_payload,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_run_now(
    databricks_credentials: "DatabricksCredentials",
    job_id: Optional[int] = None,
    idempotency_token: Optional[str] = None,
    jar_params: Optional[List[str]] = None,
    notebook_params: Optional[Dict] = None,
    python_params: Optional[List[str]] = None,
    spark_submit_params: Optional[List[str]] = None,
    python_named_params: Optional[Dict] = None,
    pipeline_params: Optional[str] = None,
    sql_params: Optional[Dict] = None,
    dbt_commands: Optional[List] = None,
    job_parameters: Optional[Dict] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Run a job and return the `run_id` of the triggered run.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        job_id: The ID of the job to run.
        idempotency_token:
            An optional token (at most 64 characters) guaranteeing the
            idempotency of the request. If a run with the token already exists,
            the existing run's ID is returned instead of creating a new run. See
            the Databricks docs on job idempotency for details.
        jar_params:
            A list of command-line parameters for Spark JAR tasks, used to invoke
            the main class. Cannot be combined with `notebook_params`, and its
            JSON representation cannot exceed 10,000 bytes.
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
        job_parameters:
            A map of job-level parameter overrides for the run.

    Returns:
        Upon success, a dict of the response containing the keys `run_id`
        (`int`) and `number_in_job` (`int`).

    Note:
        Calls the `/2.1/jobs/run-now` API endpoint. Possible responses are
        200 (run was started successfully), 400 (the request was malformed;
        see the JSON response for error details), 401 (the request was
        unauthorized), and 500 (the request was not handled correctly due to a
        server error).
    """  # noqa
    endpoint = "/2.1/jobs/run-now"  # noqa

    responses = {
        200: "Run was started successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    json_payload = {
        "job_id": job_id,
        "idempotency_token": idempotency_token,
        "jar_params": jar_params,
        "notebook_params": notebook_params,
        "python_params": python_params,
        "spark_submit_params": spark_submit_params,
        "python_named_params": python_named_params,
        "pipeline_params": pipeline_params,
        "sql_params": sql_params,
        "dbt_commands": dbt_commands,
        "job_parameters": job_parameters,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.POST,
        json=json_payload,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_runs_cancel(
    databricks_credentials: "DatabricksCredentials",
    run_id: Optional[int] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Cancels a job run. The run is canceled asynchronously, so it may still be
    running when this request completes.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        run_id:
            This field is required, e.g. `455644833`.

    Returns:
        Upon success, an empty dict.

    Note:
        Calls the `/2.1/jobs/runs/cancel` API endpoint. Possible responses are
        200 (run was cancelled successfully), 400 (the request was malformed;
        see the JSON response for error details), 401 (the request was
        unauthorized), and 500 (the request was not handled correctly due to a
        server error).
    """  # noqa
    endpoint = "/2.1/jobs/runs/cancel"  # noqa

    responses = {
        200: "Run was cancelled successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    json_payload = {
        "run_id": run_id,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.POST,
        json=json_payload,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_runs_cancel_all(
    databricks_credentials: "DatabricksCredentials",
    job_id: Optional[int] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Cancels all active runs of a job. The runs are canceled asynchronously, so it
    doesn't prevent new runs from being started.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        job_id:
            The canonical identifier of the job to cancel all runs of. This field is
            required, e.g. `11223344`.

    Returns:
        Upon success, an empty dict.

    Note:
        Calls the `/2.1/jobs/runs/cancel-all` API endpoint. Possible responses
        are 200 (all runs were cancelled successfully), 400 (the request was
        malformed; see the JSON response for error details), 401 (the request
        was unauthorized), and 500 (the request was not handled correctly due
        to a server error).
    """  # noqa
    endpoint = "/2.1/jobs/runs/cancel-all"  # noqa

    responses = {
        200: "All runs were cancelled successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    json_payload = {
        "job_id": job_id,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.POST,
        json=json_payload,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_runs_delete(
    databricks_credentials: "DatabricksCredentials",
    run_id: Optional[int] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Deletes a non-active run. Returns an error if the run is active.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        run_id:
            The canonical identifier of the run for which to retrieve the metadata,
            e.g. `455644833`.

    Returns:
        Upon success, an empty dict.

    Note:
        Calls the `/2.1/jobs/runs/delete` API endpoint. Possible responses are
        200 (run was deleted successfully), 400 (the request was malformed;
        see the JSON response for error details), 401 (the request was
        unauthorized), and 500 (the request was not handled correctly due to a
        server error).
    """  # noqa
    endpoint = "/2.1/jobs/runs/delete"  # noqa

    responses = {
        200: "Run was deleted successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    json_payload = {
        "run_id": run_id,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.POST,
        json=json_payload,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_runs_get(
    run_id: int,
    databricks_credentials: "DatabricksCredentials",
    include_history: Optional[bool] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Retrieve the metadata of a run.

    Args:
        run_id:
            The canonical identifier of the run for which to retrieve the metadata.
            This field is required.
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        include_history:
            Whether to include the repair history in the response.

    Returns:
        Upon success, a dict describing the run, including its identifiers
        (`job_id`, `run_id`), `state`, `tasks`, cluster spec and instance,
        scheduling and timing fields, and — when requested — its
        `repair_history`.

    Note:
        Calls the `/2.1/jobs/runs/get` API endpoint. Possible responses are
        200 (run was retrieved successfully), 400 (the request was malformed;
        see the JSON response for error details), 401 (the request was
        unauthorized), and 500 (the request was not handled correctly due to a
        server error).
    """  # noqa
    endpoint = "/2.1/jobs/runs/get"  # noqa

    responses = {
        200: "Run was retrieved successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    params = {
        "run_id": run_id,
        "include_history": include_history,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.GET,
        params=params,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_runs_get_output(
    run_id: int,
    databricks_credentials: "DatabricksCredentials",
) -> Dict[str, Any]:  # pragma: no cover
    """
    Retrieve the output and metadata of a single task run. When a notebook task
    returns a value through the dbutils.notebook.exit() call, you can use this
    endpoint to retrieve that value. Databricks restricts this API to return the
    first 5 MB of the output. To return a larger result, you can store job
    results in a cloud storage service. This endpoint validates that the run_id
    parameter is valid and returns an HTTP status code 400 if the run_id
    parameter is invalid. Runs are automatically removed after 60 days. If you
    to want to reference them beyond 60 days, you must save old run results
    before they expire. To export using the UI, see Export job run results. To
    export using the Jobs API, see Runs export.

    Args:
        run_id:
            The canonical identifier for the run. This field is required.
        databricks_credentials:
            Credentials to use for authentication with Databricks.

    Returns:
        Upon success, a dict of the response containing the keys
        `notebook_output` (`"models.NotebookOutput"`),
        `sql_output` (`"models.SqlOutput"`),
        `dbt_output` (`"models.DbtOutput"`), `logs` (`str`),
        `logs_truncated` (`bool`), `error` (`str`), `error_trace` (`str`), and
        `metadata` (`"models.Run"`).

    Note:
        Calls the `/2.1/jobs/runs/get-output` API endpoint. Possible responses
        are 200 (run output was retrieved successfully), 400 (a job run with
        multiple tasks was provided), 401 (the request was unauthorized), and
        500 (the request was not handled correctly due to a server error).
    """  # noqa
    endpoint = "/2.1/jobs/runs/get-output"  # noqa

    responses = {
        200: "Run output was retrieved successfully.",  # noqa
        400: "A job run with multiple tasks was provided.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    params = {
        "run_id": run_id,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.GET,
        params=params,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_runs_list(
    databricks_credentials: "DatabricksCredentials",
    active_only: bool = False,
    completed_only: bool = False,
    job_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 25,
    run_type: Optional[str] = None,
    expand_tasks: bool = False,
    start_time_from: Optional[int] = None,
    start_time_to: Optional[int] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    List runs in descending order by start time.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        active_only:
            If active_only is `true`, only active runs are included in the results;
            otherwise, lists both active and completed runs. An active
            run is a run in the `PENDING`, `RUNNING`, or `TERMINATING`.
            This field cannot be `true` when completed_only is `true`.
        completed_only:
            If completed_only is `true`, only completed runs are included in the
            results; otherwise, lists both active and completed runs.
            This field cannot be `true` when active_only is `true`.
        job_id:
            The job for which to list runs. If omitted, the Jobs service lists runs
            from all jobs.
        offset:
            The offset of the first run to return, relative to the most recent run.
        limit:
            The number of runs to return. This value must be greater than 0 and less
            than 25\. The default value is 25\. If a request specifies a
            limit of 0, the service instead uses the maximum limit.
        run_type:
            The type of runs to return. For a description of run types, see
            [Run](https://docs.databricks.com/dev-
            tools/api/latest/jobs.html
            operation/JobsRunsGet).
        expand_tasks:
            Whether to include task and cluster details in the response.
        start_time_from:
            Show runs that started _at or after_ this value. The value must be a UTC
            timestamp in milliseconds. Can be combined with
            _start_time_to_ to filter by a time range.
        start_time_to:
            Show runs that started _at or before_ this value. The value must be a
            UTC timestamp in milliseconds. Can be combined with
            _start_time_from_ to filter by a time range.

    Returns:
        Upon success, a dict of the response containing the keys `runs`
        (`List["models.Run"]`) and `has_more` (`bool`).

    Note:
        Calls the `/2.1/jobs/runs/list` API endpoint. Possible responses are
        200 (list of runs was retrieved successfully), 400 (the request was
        malformed; see the JSON response for error details), 401 (the request
        was unauthorized), and 500 (the request was not handled correctly due
        to a server error).
    """  # noqa
    endpoint = "/2.1/jobs/runs/list"  # noqa

    responses = {
        200: "List of runs was retrieved successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    params = {
        "active_only": active_only,
        "completed_only": completed_only,
        "job_id": job_id,
        "offset": offset,
        "limit": limit,
        "run_type": run_type,
        "expand_tasks": expand_tasks,
        "start_time_from": start_time_from,
        "start_time_to": start_time_to,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.GET,
        params=params,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_runs_repair(
    databricks_credentials: "DatabricksCredentials",
    run_id: Optional[int] = None,
    rerun_tasks: Optional[List[str]] = None,
    latest_repair_id: Optional[int] = None,
    rerun_all_failed_tasks: bool = False,
    jar_params: Optional[List[str]] = None,
    notebook_params: Optional[Dict] = None,
    python_params: Optional[List[str]] = None,
    spark_submit_params: Optional[List[str]] = None,
    python_named_params: Optional[Dict] = None,
    pipeline_params: Optional[str] = None,
    sql_params: Optional[Dict] = None,
    dbt_commands: Optional[List] = None,
    job_parameters: Optional[Dict] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Re-run one or more tasks. Tasks are re-run as part of the original job run, use
    the current job and task settings, and can be viewed in the history for the
    original job run.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        run_id:
            The job run ID of the run to repair. The run must not be in progress.
        rerun_tasks: The task keys of the task runs to repair.
        latest_repair_id:
            The ID of the latest repair. Not required when repairing a run for
            the first time, but must be provided on subsequent repair requests
            for the same run.
        rerun_all_failed_tasks:
            If true, repair all failed tasks. Only one of `rerun_tasks` or
            `rerun_all_failed_tasks` may be set.
        jar_params:
            A list of command-line parameters for Spark JAR tasks, used to invoke
            the main class. Cannot be combined with `notebook_params`, and its
            JSON representation cannot exceed 10,000 bytes.
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
        job_parameters:
            A map of job-level parameter overrides for the run.

    Returns:
        Upon success, a dict of the response containing the key `repair_id`
        (`int`).

    Note:
        Calls the `/2.1/jobs/runs/repair` API endpoint. Possible responses are
        200 (run repair was initiated), 400 (the request was malformed; see
        the JSON response for error details), 401 (the request was
        unauthorized), and 500 (the request was not handled correctly due to a
        server error).
    """  # noqa
    endpoint = "/2.1/jobs/runs/repair"  # noqa

    responses = {
        200: "Run repair was initiated.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    json_payload = {
        "run_id": run_id,
        "rerun_tasks": rerun_tasks,
        "latest_repair_id": latest_repair_id,
        "rerun_all_failed_tasks": rerun_all_failed_tasks,
        "jar_params": jar_params,
        "notebook_params": notebook_params,
        "python_params": python_params,
        "spark_submit_params": spark_submit_params,
        "python_named_params": python_named_params,
        "pipeline_params": pipeline_params,
        "sql_params": sql_params,
        "dbt_commands": dbt_commands,
        "job_parameters": job_parameters,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.POST,
        json=json_payload,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_runs_submit(
    databricks_credentials: "DatabricksCredentials",
    tasks: Optional[List["models.RunSubmitTaskSettings"]] = None,
    run_name: Optional[str] = None,
    webhook_notifications: "models.WebhookNotifications" = None,
    git_source: "models.GitSource" = None,
    timeout_seconds: Optional[int] = None,
    idempotency_token: Optional[str] = None,
    access_control_list: Optional[List["models.AccessControlRequest"]] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Submit a one-time run. This endpoint allows you to submit a workload directly
    without creating a job. Use the `jobs/runs/get` API to check the run state
    after the job is submitted.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        tasks:
            A list of task specifications (`RunSubmitTaskSettings`) to run. Each
            task defines its key, the cluster it runs on, and the work to do
            (a notebook, JAR, Python, SQL, or dbt task).
        run_name: An optional name for the run. Defaults to `Untitled`.
        webhook_notifications:
            System notification IDs (`WebhookNotifications`) to call when the run
            starts, succeeds, or fails, up to three destinations per event.
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

    Returns:
        Upon success, a dict of the response containing the key `run_id`
        (`int`).

    Note:
        Calls the `/2.1/jobs/runs/submit` API endpoint. Possible responses are
        200 (run was created and started successfully), 400 (the request was
        malformed; see the JSON response for error details), 401 (the request
        was unauthorized), and 500 (the request was not handled correctly due
        to a server error).
    """  # noqa
    endpoint = "/2.1/jobs/runs/submit"  # noqa

    responses = {
        200: "Run was created and started successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    json_payload = {
        "tasks": tasks,
        "run_name": run_name,
        "webhook_notifications": webhook_notifications,
        "git_source": git_source,
        "timeout_seconds": timeout_seconds,
        "idempotency_token": idempotency_token,
        "access_control_list": access_control_list,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.POST,
        json=json_payload,
    )

    contents = _unpack_contents(response, responses)
    return contents


@task
async def jobs_update(
    databricks_credentials: "DatabricksCredentials",
    job_id: Optional[int] = None,
    new_settings: "models.JobSettings" = None,
    fields_to_remove: Optional[List[str]] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Add, update, or remove specific settings of an existing job. Use the Reset
    endpoint to overwrite all job settings.

    Args:
        databricks_credentials:
            Credentials to use for authentication with Databricks.
        job_id: The canonical identifier of the job to update. Required.
        new_settings:
            The settings (`JobSettings`) to apply. Any top-level field provided
            is replaced entirely; partial updates of nested fields are not
            supported. Changes to `timeout_seconds` apply to active runs, while
            changes to other fields apply only to future runs.
        fields_to_remove:
            An optional list of top-level fields to remove from the job's
            settings. Removing nested fields is not supported.

    Returns:
        Upon success, an empty dict.

    Note:
        Calls the `/2.1/jobs/update` API endpoint. Possible responses are
        200 (job was updated successfully), 400 (the request was malformed;
        see the JSON response for error details), 401 (the request was
        unauthorized), and 500 (the request was not handled correctly due to a
        server error).
    """  # noqa
    endpoint = "/2.1/jobs/update"  # noqa

    responses = {
        200: "Job was updated successfully.",  # noqa
        400: "The request was malformed. See JSON response for error details.",  # noqa
        401: "The request was unauthorized.",  # noqa
        500: "The request was not handled correctly due to a server error.",  # noqa
    }

    json_payload = {
        "job_id": job_id,
        "new_settings": new_settings,
        "fields_to_remove": fields_to_remove,
    }

    response = await execute_endpoint.fn(
        endpoint,
        databricks_credentials,
        http_method=HTTPMethod.POST,
        json=json_payload,
    )

    contents = _unpack_contents(response, responses)
    return contents
