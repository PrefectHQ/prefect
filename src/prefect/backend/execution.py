import copy
import subprocess
import sys
import pendulum
import os
import time
from contextlib import contextmanager
from typing import Any, Type, Optional

import prefect
from prefect import Flow
from prefect.backend.flow_run import FlowRunView
from prefect.run_configs import RunConfig
from prefect.utilities.logging import get_logger
from prefect.utilities.graphql import with_args


logger = get_logger("backend.execution")


def execute_flow_run_in_subprocess(
    flow_run_id: str, run_token: str = None
) -> FlowRunView:
    """
    Execute a flow run in a subprocess.

    See `execute_flow_run` for more details.

    Intended for executing a flow run without an agent.

    Args:
        - flow_run_id: The flow run to execute
        - run_token: The authentication token to provide to the flow run for
            communicating with the Prefect Cloud API. If not set, it will be inferred
            from the current config.

    Returns:
        FlowRunView: The final flow run object
    """
    flow_run = FlowRunView.from_flow_run_id(flow_run_id)

    # Set up the environment
    env = generate_flow_run_environ(
        flow_run_id=flow_run_id,
        flow_id=flow_run.flow_id,
        run_token=run_token,
        run_config=flow_run.run_config,
    )

    while not flow_run.state.is_finished():

        logger.debug("Checking for flow run scheduled start time...")
        flow_run_start = get_flow_run_scheduled_start_time(flow_run_id)
        if flow_run_start:
            interval = flow_run_start.diff(abs=False).in_seconds() * -1
            message = f"Flow run scheduled to run {flow_run_start.diff_for_humans()}; "
            if interval > 0:
                logger.info(message + "sleeping before trying to run flow...")
                time.sleep(interval)
            else:  # is scheduled in the past
                logger.debug(message + "trying to run flow now...")
        else:
            logger.debug("No scheduled time found; trying to run flow now...")

        logger.debug("Checking for retried task runs...")
        next_task_start = get_next_task_run_start_time(flow_run_id)
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

        logger.info("Creating subprocess to execute flow run...")
        # Creating a subprocess allows us to pass environment variables and ensure the
        # flow run loads a correct Prefect config. This CLI command calls out to
        # `execute_flow_run`
        result = subprocess.run(
            [sys.executable, "-m", "prefect", "execute", "flow-run"], env=env
        )
        logger.debug("Exited flow run subprocess.")

        try:
            result.check_returncode()
        except subprocess.CalledProcessError as exc:
            # Wrap this error to provide a clearer one
            raise RuntimeError("The flow run process failed.") from exc

        flow_run = flow_run.get_latest()

    return flow_run


def get_next_task_run_start_time(flow_run_id: str) -> Optional[pendulum.DateTime]:
    """
    Queries task runs associated with a flow run to get the earliest state start time.
    This time _may_ be in the past.

    Long retries are handled by exiting flow execution leaving the flow run in a
    'Running' state and attaching a start time to the task runs that need to be retried.
    This function checks for a long retry by querying for task runs that have a start
    time set. This allows us to wait until this run time is reached before starting
    flow run execution. If we starterd execution, the runner would just walk the DAG and
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

    task_runs = sorted(task_runs, key=lambda task_run: task_run.state_start_time)
    next_start_time = task_runs[0].state_start_time
    return pendulum.parse(next_start_time)


def get_flow_run_scheduled_start_time(flow_run_id: str) -> Optional[pendulum.DateTime]:
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
                with_args(
                    "flow_run",
                    {
                        "where": {
                            "state": {"_eq": "Scheduled"},
                            "id": {"_eq": flow_run_id},
                        }
                    },
                ): {
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
    states = sorted(flow_run.states, key=lambda state: state.created)
    state = states[0] if states else None

    # Return the most recently created state start time; default to the flow run
    # scheduled start time in case there are no state times
    start_time = (
        state.start_time
        if state and state.start_time
        else flow_run.scheduled_start_time
    )

    if not start_time:
        return None  # There is no scheduled start time in the states or on the run

    return pendulum.parse(start_time)


def generate_flow_run_environ(
    flow_run_id: str, flow_id: str, run_config: RunConfig, run_token: str = None
) -> dict:
    # TODO: Create a function to cast select config keys to env vars
    # TODO: Compare this local agent env to other agent envs to create general func
    # TODO: Use general func in all agents

    # 1. Local environment
    env = os.environ.copy()

    # 2. Logging config
    env.update({"PREFECT__LOGGING__LEVEL": prefect.config.logging.level})

    # 5. Values set on a LocalRun RunConfig (if present
    if run_config is not None and run_config.env is not None:
        env.update(run_config.env)

    # Required variables
    env.update(
        {
            "PREFECT__BACKEND": prefect.config.backend,
            "PREFECT__CLOUD__API": prefect.config.cloud.api,
            "PREFECT__CLOUD__AUTH_TOKEN": run_token or prefect.config.cloud.auth_token,
            "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run_id,
            "PREFECT__CONTEXT__FLOW_ID": flow_id,
            "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS": str(
                prefect.config.cloud.send_flow_run_logs
            ),
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }
    )

    # Filter out None values
    return {k: v for k, v in env.items() if v is not None}


def execute_flow_run(
    flow_run_id: str,
    flow: "Flow" = None,
    runner_cls: Type["prefect.engine.flow_runner.FlowRunner"] = None,
    **kwargs: Any,
) -> "FlowRunView":
    """ "
    The primary entry point for executing a flow run. The flow run will be run
    in-process using the given `runner_cls` which defaults to the `CloudFlowRunner`.

    This function assumes that the flow run's environment variables have been set
    already. See `execute_flow_run_in_subprocess` if you neeed the environment to be
    created.

    Args:
        - flow_run_id: The flow run id to execute; this run id must exist in the database
        - flow: A Flow object can be passed to execute a flow without loading t from
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
    if flow_run.flow.storage:
        logger.info("Loading secrets...")
        for secret in flow_run.flow.storage.secrets:
            with fail_flow_run_on_exception(
                flow_run_id=flow_run_id,
                message=f"Failed to load flow secret {secret!r}: {{exc}}",
            ):
                secrets[secret] = prefect.tasks.secrets.PrefectSecret(name=secret).run()

    # Load the flow from storage if not explicitly provided
    if not flow:
        logger.info(f"Loading flow from {flow_run.flow.storage}...")
        with prefect.context(secrets=secrets, loading_flow=True):
            with fail_flow_run_on_exception(
                flow_run_id=flow_run_id,
                message="Failed to load flow from storage: {exc}",
            ):
                flow = flow_run.flow.storage.get_flow(flow_run.flow.name)

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
        f"Beginning execution of flow run {flow_run.name!r} from {flow_run.flow.name!r} "
        f"with {runner_cls.__name__!r}"
    )
    with prefect.context(flow_run_id=flow_run_id):
        with fail_flow_run_on_exception(
            flow_run_id=flow_run_id,
            message="Failed to execute flow: {exc}",
        ):
            if flow_run.flow.run_config is not None:
                runner_cls(flow=flow).run(**run_kwargs)

            # Support for deprecated `flow.environment` use
            else:
                environment = flow.environment
                environment.setup(flow)
                environment.execute(flow)

    # Get the final state
    flow_run = flow_run.get_latest()
    logger.info(f"Run finished with final state {flow_run.state}")
    return flow_run


@contextmanager
def fail_flow_run_on_exception(
    flow_run_id: str,
    message: str = None,
) -> Any:
    """
    A utility context manager to set the state of the given flow run to 'Failed' if
    an exception occurs. A custom message can be provided for more details and will
    be attached to the state and added to the run logs. KeyboardInterrupts will set
    the flow run state to 'Cancelled' instead and will not use the message. All errors
    will be re-raised.

    Args:
        - flow_run_id: The flow run id to update the state of
        - message: The message to include in the state and logs. `{exc}` will be formatted
            with the exception details.
    """
    message = message or "Flow run failed with {exc}"
    client = prefect.Client()

    try:
        yield
    except Exception as exc:
        if not FlowRunView.from_flow_run_id(flow_run_id).state.is_finished():
            message = message.format(exc=exc.__repr__())
            client.set_flow_run_state(
                flow_run_id=flow_run_id, state=prefect.engine.state.Failed(message)
            )
            client.write_run_logs(
                [
                    dict(
                        flow_run_id=flow_run_id,  # type: ignore
                        name="prefect.backend.execution.execute_flow_run",
                        message=message,
                        level="ERROR",
                    )
                ]
            )
        logger.error(message, exc_info=True)
        raise
