"""
Utility functions for actually executing flow runs once they've been deployed to an
execution environment

These are not intended to be user-facing.
"""
import copy
import subprocess
import sys
import pendulum
import os
import time
from contextlib import contextmanager
from typing import Any, Type, Optional, cast, Dict

import prefect
from prefect import Flow
from prefect.backend.flow_run import FlowRunView
from prefect.run_configs import RunConfig
from prefect.utilities.logging import get_logger
from prefect.utilities.graphql import with_args
from prefect.configuration import to_environment_variables


logger = get_logger("backend.execution")


def execute_flow_run_in_subprocess(
    flow_run_id: str, run_api_key: str = None, include_local_env: bool = True
) -> FlowRunView:
    """
    Execute a flow run in a subprocess.

    See `execute_flow_run` for more details.

    Intended for executing a flow run without an agent.

    If an interrupt is received during execution, the flow run is marked as failed in
    contrast to an agent-based execution model where the flow run can be resubmitted by
    Lazarus.

    Args:
        - flow_run_id: The flow run to execute
        - run_api_key: The authentication key to provide to the flow run for
            communicating with the Prefect Cloud API. If not set, it will be inferred
            from the current config.
        - include_local_env: If `True`, the currently available environment variables
            will be passed through to the flow run. Defaults to `True` to match
            subprocess behavior.

    Returns:
        FlowRunView: The final flow run object
    """
    flow_run = FlowRunView.from_flow_run_id(flow_run_id)

    # Set up the environment
    env = generate_flow_run_environ(
        flow_run_id=flow_run_id,
        flow_id=flow_run.flow_id,
        run_api_key=run_api_key,
        run_config=flow_run.run_config,
        include_local_env=include_local_env,
    )

    if not flow_run.state.is_scheduled():
        raise RuntimeError(
            f"Flow run is already in state {flow_run.state!r}! Cannot execute flow run "
            "unless it is in a 'Scheduled' state"
        )

    while not flow_run.state.is_finished():

        _wait_for_flow_run_start_time(flow_run_id)

        try:
            # Creating a subprocess allows us to pass environment variables and ensure
            # the flow run loads a correct Prefect config. This CLI command calls out to
            # `execute_flow_run`
            logger.info("Creating subprocess to execute flow run...")
            result = subprocess.run(
                [sys.executable, "-m", "prefect", "execute", "flow-run"], env=env
            )
        except KeyboardInterrupt:
            _fail_flow_run(
                flow_run_id=flow_run_id,
                message="Flow run received an interrupt signal.",
            )
            raise  # Reraise interrupts
        except Exception as exc:
            message = "Flow run encountered unexpected exception during execution"
            _fail_flow_run(
                flow_run_id=flow_run_id,
                message=f"{message}: {exc!r}",
            )
            raise RuntimeError(message) from exc

        logger.debug("Exited flow run subprocess.")

        try:
            result.check_returncode()
        except subprocess.CalledProcessError as exc:
            # Wrap this error to provide a clearer one
            raise RuntimeError("The flow run process failed.") from exc

        # Wait half a second before getting the latest data to reduce the chance of
        # starting another subprocess that exits immediately
        time.sleep(0.5)
        flow_run = flow_run.get_latest()

    return flow_run


def execute_flow_run(
    flow_run_id: str,
    flow: "Flow" = None,
    runner_cls: Type["prefect.engine.flow_runner.FlowRunner"] = None,
    **kwargs: Any,
) -> "FlowRunView":
    """
    TODO: This is not used yet and will be hooked up to the CLI in the near future
          At that point, tests should be written and it should be fully compatible with
          the inline CLI functionality

    The primary entry point for executing a flow run. The flow run will be run
    in-process using the given `runner_cls` which defaults to the `CloudFlowRunner`.

    This function assumes that the flow run's environment variables have been set
    already. See `execute_flow_run_in_subprocess` if you neeed the environment to be
    created.

    Args:
        - flow_run_id: The flow run id to execute; this run id must exist in the database
        - flow: A Flow object can be passed to execute a flow without loading it from
            Storage. If `None`, the flow's Storage metadata will be pulled from the
            API and used to get a functional instance of the Flow and its tasks.
        - runner_cls: An optional `FlowRunner` to override the default `CloudFlowRunner`
        - **kwargs: Additional kwargs will be passed to the `FlowRunner.run` method

    Returns:
        A `FlowRunView` instance with information about the state of the flow run and its
        task runs
    """
    logger.debug(f"Querying for flow run {flow_run_id!r}")

    # Get the `FlowRunner` class type
    # TODO: Respect a config option for this class so it can be overridden by env var,
    #       create a separate config argument for flow runs executed with the backend
    runner_cls = runner_cls or prefect.engine.cloud.flow_runner.CloudFlowRunner

    # Get a `FlowRunView` object
    flow_run = FlowRunView.from_flow_run_id(
        flow_run_id=flow_run_id, load_static_tasks=False
    )

    logger.info(f"Constructing execution environment for flow run {flow_run_id!r}")

    # Populate global secrets
    secrets = prefect.context.get("secrets", {})
    flow_metadata = flow_run.get_flow_metadata()
    if flow_metadata.storage:
        logger.info("Loading secrets...")
        for secret in flow_metadata.storage.secrets:
            with _fail_flow_run_on_exception(
                flow_run_id=flow_run_id,
                message=f"Failed to load flow secret {secret!r}: {{exc}}",
            ):
                secrets[secret] = prefect.tasks.secrets.PrefectSecret(name=secret).run()

    # Load the flow from storage if not explicitly provided
    if not flow:
        logger.info(f"Loading flow from {flow_metadata.storage}...")
        with prefect.context(secrets=secrets, loading_flow=True):
            with _fail_flow_run_on_exception(
                flow_run_id=flow_run_id,
                message="Failed to load flow from storage: {exc}",
            ):
                flow = flow_metadata.storage.get_flow(flow_metadata.name)

    # Update the run context to include secrets with merging
    run_kwargs = copy.deepcopy(kwargs)
    run_kwargs["context"] = run_kwargs.get("context", {})
    run_kwargs["context"]["secrets"] = {
        # User provided secrets will override secrets we pulled from storage and the
        # current context
        **secrets,
        **run_kwargs["context"].get("secrets", {}),
    }
    # Update some default run kwargs with flow settings
    run_kwargs.setdefault("executor", flow.executor)

    # Execute the flow, this call will block until exit
    logger.info(
        f"Beginning execution of flow run {flow_run.name!r} from flow {flow_metadata.name!r} "
        f"with {runner_cls.__name__!r}"
    )
    with prefect.context(flow_run_id=flow_run_id):
        with _fail_flow_run_on_exception(
            flow_run_id=flow_run_id,
            message="Failed to execute flow: {exc}",
        ):
            runner_cls(flow=flow).run(**run_kwargs)

    # Get the final state
    flow_run = flow_run.get_latest()
    logger.info(f"Run finished with final state {flow_run.state}")
    return flow_run


def generate_flow_run_environ(
    flow_run_id: str,
    flow_id: str,
    run_config: RunConfig,
    run_api_key: str = None,
    include_local_env: bool = False,
) -> Dict[str, str]:
    """
    Utility to generate the environment variables required for a flow run

    Args:
        - flow_run_id: The id for the flow run that will be executed
        - flow_id: The id for the flow of the flow run that will be executed
        - run_config: The run config for the flow run, contributes environment variables
        - run_api_key: An optional API key to pass to the flow run for authenticating
            with the backend. If not set, it will be pulled from the Client
        - include_local_env: If `True`, the currently available environment variables
            will be passed through to the flow run. Defaults to `False` for security.

    Returns:
        - A dictionary of environment variables
    """
    # TODO: Generalize this and use it for all agents

    # Local environment
    env = cast(Dict[str, Optional[str]], os.environ.copy() if include_local_env else {})

    # Pass through config options that can be overriden by run config
    env.update(
        to_environment_variables(
            prefect.config,
            include={
                "logging.level",
                "logging.format",
                "logging.datefmt",
                "cloud.send_flow_run_logs",
            },
        )
    )

    # Update with run config environment
    if run_config is not None and run_config.env is not None:
        env.update(run_config.env)

    # Update with config options that cannot be overriden by the run config
    env.update(
        to_environment_variables(
            prefect.config,
            include={"backend", "cloud.api", "cloud.tenant_id"},
        )
    )

    # Pass authentication through
    client = prefect.Client()  # Instantiate a client to get the current API key
    env["PREFECT__CLOUD__API_KEY"] = run_api_key or client.api_key or ""
    # Backwards compat for auth tokens (only useful for containers)
    env["PREFECT__CLOUD__AUTH_TOKEN"] = run_api_key or client.api_key or ""

    # Add context information for the run
    env.update(
        {
            "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run_id,
            "PREFECT__CONTEXT__FLOW_ID": flow_id,
        }
    )

    # Update hardcoded execution variables
    env.update(
        {
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }
    )

    # Filter out `None` values
    return {k: v for k, v in env.items() if v is not None}


def _wait_for_flow_run_start_time(flow_run_id: str) -> None:
    """
    Utility that sleeps until the correct flow run start time using
    `_get_flow_run_scheduled_start_time` then `_get_next_task_run_start_time`

    See those two docstrings for details on why this is necessary.
    """
    logger.debug("Checking for flow run scheduled start time...")
    flow_run_start = _get_flow_run_scheduled_start_time(flow_run_id)
    if flow_run_start:
        interval = flow_run_start.diff(abs=False).in_seconds() * -1
        message = f"Flow run scheduled to run {flow_run_start.diff_for_humans()}; "
        if interval > 0:
            logger.info(message + "sleeping before trying to run flow...")
            time.sleep(interval)
        else:  # is scheduled in the past
            logger.debug(message + "moving to next check...")
    else:
        logger.debug("No scheduled time found; moving to next check...")

    logger.debug("Checking for retried task runs...")
    next_task_start = _get_next_task_run_start_time(flow_run_id)
    if next_task_start:
        interval = next_task_start.diff(abs=False).in_seconds() * -1
        message = f"Found task run scheduled {next_task_start.diff_for_humans()}; "
        if interval > 0:
            logger.info(message + "sleeping before trying to run flow...")
            # TODO: In the future we may want to set an upper limit if the backend
            #       may update the state of the flow for an earlier retry
            time.sleep(interval)
        else:  # is scheduled in the past
            logger.info(message + "trying to run flow now...")
    else:
        logger.debug("No scheduled task runs found; trying to run flow now...")


def _get_next_task_run_start_time(flow_run_id: str) -> Optional[pendulum.DateTime]:
    """
    Queries task runs associated with a flow run to get the earliest state start time.
    This time _may_ be in the past.

    Long retries are handled by exiting flow execution leaving the flow run in a
    'Running' state and attaching a start time to the task runs that need to be retried.
    This function checks for a long retry by querying for task runs that have a start
    time set. This allows us to wait until this run time is reached before starting
    flow run execution. If we started execution, the runner would just walk the DAG and
    exit since the task run is not ready to begin yet.

    Args:
        - flow_run_id: The flow run the task runs belong to

    Returns:
        None: If no scheduled task runs are found, otherwise
        pendulum.DateTime: The earliest scheduled task run start time.
    """
    client = prefect.Client()
    result = client.graphql(
        {
            "query": {
                with_args(
                    "task_run",
                    {
                        "where": {
                            "state_start_time": {"_is_null": False},
                            "flow_run_id": {"_eq": flow_run_id},
                            "flow_run": {
                                # Only include flow runs in a 'Running' state to reduce
                                # the scope of the query to retrying flow runs
                                "state": {"_eq": "Running"}
                            },
                        }
                    },
                ): {"state_start_time"}
            }
        }
    )
    task_runs = result.get("data", {}).get("task_run")
    if task_runs is None:
        raise ValueError(f"Unexpected result while querying for task runs: {result}")
    elif not task_runs:
        return None  # No scheduled task runs

    task_run = min(task_runs, key=lambda task_run: task_run.state_start_time)
    next_start_time = task_run.state_start_time
    return cast(pendulum.DateTime, pendulum.parse(next_start_time))


def _get_flow_run_scheduled_start_time(flow_run_id: str) -> Optional[pendulum.DateTime]:
    """
    Queries for the current scheduled start time of a flow

    Flow runs store a `scheduled_start_time` as their originally scheduled time to
    start. 'Scheduled' flow run states also store a `start_time` that supercedes the
    time on the flow run object itself. For example, if a flow run is scheduled for some
    time in the future and a user clicks the 'Start Now' button in the UI, we'll create
    a new 'Scheduled' state with an updated start time. This allows us to preserve
    start time history while making the state the source of truth.

    This function will always return the start time associated with the most recently
    created 'Scheduled' state, if available. If the most recent 'Scheduled' state has a
    null `start_time`, we will fall back to the flow run's `scheduled_start_time`.

    Args:
        - flow_run_id: The flow run of interest

    Returns:
        pendulum.DateTime: The most recent scheduled flow run start time

    Raises:
        - ValueError: On API error
        - ValueError: When zero or more than one flow runs are found

    """
    client = prefect.Client()
    result = client.graphql(
        {
            # We cannot query for states directly and must go through the `flow_run`
            # object
            "query": {
                with_args("flow_run", {"where": {"id": {"_eq": flow_run_id}}}): {
                    with_args("states", {"where": {"state": {"_eq": "Scheduled"}}}): {
                        "start_time",
                        "created",
                    },
                    "scheduled_start_time": True,
                }
            }
        }
    )
    flow_runs = result.get("data", {}).get("flow_run")
    if flow_runs is None:
        raise ValueError(
            f"Unexpected result while querying for flow run states: {result}"
        )
    elif len(flow_runs) > 1:
        raise ValueError(
            f"Found more than one flow run matching id {flow_run_id!r}: {result}"
        )
    elif not flow_runs:
        raise ValueError(f"No flow run exists with id {flow_run_id!r}.")

    # Get the one found flow run
    flow_run = flow_runs[0]

    # Get the most recently created state
    states = sorted(
        flow_run.states, key=lambda state: state.get("created", ""), reverse=True
    )
    state = states[0] if states else None

    # Return the most recently created state start time; default to the flow run
    # scheduled start time in case there are no state times
    start_time = (
        state.start_time
        if state and state.get("start_time")
        else flow_run.scheduled_start_time
    )

    if not start_time:
        return None  # There is no scheduled start time in the states or on the run

    return cast(pendulum.DateTime, pendulum.parse(start_time))


@contextmanager
def _fail_flow_run_on_exception(
    flow_run_id: str,
    message: str = None,
) -> Any:
    """
    A utility context manager to set the state of the given flow run to 'Failed' if
    an exception occurs. A custom message can be provided for more details and will
    be attached to the state and added to the run logs. All errors will be re-raised.



    Args:
        - flow_run_id: The flow run id to update the state of
        - message: The message to include in the state and logs. `{exc}` will be formatted
            with the exception details.

    """
    message = message or "Flow run failed with {exc}"

    try:
        yield
    except Exception as exc:
        message = message.format(exc=exc.__repr__())
        if not FlowRunView.from_flow_run_id(flow_run_id).state.is_finished():
            _fail_flow_run(flow_run_id, message=message)
        logger.error(message, exc_info=True)
        raise


def _fail_flow_run(flow_run_id: str, message: str) -> None:
    """
    Set a flow run to a 'Failed' state and write a a failure message log
    """
    client = prefect.Client()
    client.set_flow_run_state(
        flow_run_id=flow_run_id, state=prefect.engine.state.Failed(message)
    )
    client.write_run_logs(
        [
            dict(
                flow_run_id=flow_run_id,  # type: ignore
                name="prefect.backend.execution",
                message=message,
                level="ERROR",
            )
        ]
    )
