import datetime
import time
import warnings
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

import prefect
from prefect import Client, Flow, Task, task
from prefect.artifacts import create_link
from prefect.backend.flow_run import FlowRunLog, FlowRunView, FlowView, watch_flow_run
from prefect.client import Client
from prefect.engine.signals import FAIL, signal_from_state
from prefect.engine.state import State
from prefect.run_configs import RunConfig
from prefect.utilities.graphql import EnumValue, with_args
from prefect.utilities.tasks import defaults_from_attrs


# Flow run creation --------------------------------------------------------------------


@task
def create_flow_run(
    flow_id: str = None,
    flow_name: str = None,
    project_name: str = "",
    parameters: dict = None,
    context: dict = None,
    labels: Iterable[str] = None,
    run_name: str = None,
) -> str:
    if flow_id and flow_name:
        raise ValueError(
            "Received both `flow_id` and `flow_name`. Only one flow identifier "
            "can be passed."
        )
    if not flow_id and not flow_name:
        raise ValueError(
            "Both `flow_id` and `flow_name` are null. You must pass a flow "
            "identifier"
        )

    logger = prefect.context.logger.getChild("create_flow_run")

    logger.debug("Looking up flow metadata...")

    if flow_id:
        flow = FlowView.from_id(flow_id)

    if flow_name:
        flow = FlowView.from_flow_name(flow_name, project_name=project_name)

    # Generate a 'sub-flow' run name
    if not run_name:
        current_run = prefect.context.get("flow_run_name")
        if current_run:
            run_name = f"{current_run}-{flow.name}"

    logger.info(f"Creating flow run {run_name!r} for flow {flow.name!r}...")

    client = Client()
    flow_run_id = client.create_flow_run(
        flow_id=flow.flow_id,
        parameters=parameters,
        context=context,
        labels=labels or None,  # If labels is empty list pass `None` for defaults
        run_name=run_name,
    )

    run_url = client.get_cloud_url("flow-run", flow_run_id)
    logger.info(f"Created flow run {run_name!r} ({run_url})")
    return flow_run_id


# Flow run results ---------------------------------------------------------------------


@task
def get_flow_run_state(flow_run_id: str) -> "State":
    flow_run = FlowRunView.from_flow_run_id(flow_run_id)
    return flow_run.state


@task
def get_task_run_result(
    flow_run_id: str, task_slug: str, map_index: int = -1, poll_time: int = 5
):
    logger = prefect.context.logger.getChild("get_task_run_result")

    if not task_slug:
        raise ValueError("Required argument `task_slug` is empty")

    task_dsp = repr(task_slug) if map_index == -1 else f"'{task_slug}[{map_index}]'"

    # Get the parent flow run state
    flow_run = FlowRunView.from_flow_run_id(flow_run_id)

    # Wait for the flow run to be finished
    while not flow_run.state.is_finished():
        logger.debug(
            f"Waiting for flow run {flow_run_id} to finish before retreiving result "
            f"for task run {task_dsp}..."
        )
        time.sleep(poll_time)
        flow_run = flow_run.get_latest()

    # Get the task run
    logger.debug("Retrieving task run metadata...")
    task_run = flow_run.get_task_run(task_slug=task_slug, map_index=map_index)

    # Load the result from storage
    logger.debug(
        f"Loading task run result from {type(task_run.state._result).__name__}..."
    )
    return task_run.get_result()


@task
def wait_for_flow_run(
    flow_run_id: str, stream_state: bool = True, stream_logs: bool = False
) -> "FlowRunView":

    flow_run = FlowRunView.from_flow_run_id(flow_run_id)

    def log_with_flow_run_id(log: FlowRunLog):
        message = f"Flow {flow_run.name!r}: {log.message}"
        prefect.context.logger.log(log.level, message)

    output_fn = log_with_flow_run_id if stream_state else lambda *_, **__: None

    if not stream_state and stream_logs:
        warnings.warn("`stream_logs` will be ignored since `stream_state` is `False`")

    return watch_flow_run(flow_run_id, stream_logs=stream_logs, output_fn=output_fn)


# Legacy -------------------------------------------------------------------------------


class StartFlowRun(Task):
    """
    Task used to kick off a flow run using Prefect Core's server or Prefect Cloud.  If multiple
    versions of the flow are found, this task will kick off the most recent unarchived version.

    Args:
        - flow_name (str, optional): the name of the flow to schedule; this value may also be
            provided at run time
        - project_name (str, optional): if running with Cloud as a backend, this is the project
            in which the flow is located; this value may also be provided at runtime. If
            running with Prefect Core's server as the backend, this should not be provided.
        - parameters (dict, optional): the parameters to pass to the flow run being scheduled;
            this value may also be provided at run time
        - run_config (RunConfig, optional): a run-config to use for this flow
            run, overriding any existing flow settings.
        - wait (bool, optional): whether to wait the triggered flow run's state; if True, this
            task will wait until the flow run is complete, and then reflect the corresponding
            state as the state of this task.  Defaults to `False`.
        - new_flow_context (dict, optional): the optional run context for the new flow run
        - run_name (str, optional): name to be set for the flow run
        - scheduled_start_time (datetime, optional): the time to schedule the execution
            for; if not provided, defaults to now
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        flow_name: str = None,
        project_name: str = None,
        parameters: dict = None,
        run_config: RunConfig = None,
        wait: bool = False,
        new_flow_context: dict = None,
        run_name: str = None,
        scheduled_start_time: datetime.datetime = None,
        **kwargs: Any,
    ):
        self.flow_name = flow_name
        self.project_name = project_name
        # Check that users haven't passed tasks to `parameters`
        if parameters is not None:
            for v in parameters.values():
                if isinstance(v, Task):
                    raise TypeError(
                        "An instance of `Task` was passed to the `StartFlowRun` constructor via the "
                        "`parameters` kwarg. You'll want to pass these parameters when calling the "
                        "task instead. For example:\n\n"
                        "  start_flow_run = StartFlowRun(...)  # static (non-Task) args go here\n"
                        "  res = start_flow_run(parameters=...)  # dynamic (Task) args go here\n\n"
                        "see https://docs.prefect.io/core/concepts/flows.html#apis for more info."
                    )
        self.parameters = parameters
        self.run_config = run_config
        self.new_flow_context = new_flow_context
        self.run_name = run_name
        self.wait = wait
        self.scheduled_start_time = scheduled_start_time
        if flow_name:
            kwargs.setdefault("name", f"Flow {flow_name}")
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "flow_name",
        "project_name",
        "parameters",
        "run_config",
        "new_flow_context",
        "run_name",
        "scheduled_start_time",
    )
    def run(
        self,
        flow_name: str = None,
        project_name: str = None,
        parameters: dict = None,
        run_config: RunConfig = None,
        new_flow_context: dict = None,
        run_name: str = None,
        idempotency_key: str = None,
        scheduled_start_time: datetime.datetime = None,
    ) -> str:
        """
        Run method for the task; responsible for scheduling the specified flow run.

        Args:
            - flow_name (str, optional): the name of the flow to schedule; if not provided,
                this method will use the flow name provided at initialization
            - project_name (str, optional): the Cloud project in which the flow is located; if
                not provided, this method will use the project provided at initialization. If
                running with Prefect Core's server as the backend, this should not be provided.
            - parameters (dict, optional): the parameters to pass to the flow run being
                scheduled; if not provided, this method will use the parameters provided at
                initialization
            - run_config (RunConfig, optional): a run-config to use for this flow
                run, overriding any existing flow settings.
            - new_flow_context (dict, optional): the optional run context for the new flow run
            - run_name (str, optional): name to be set for the flow run
            - idempotency_key (str, optional): a unique idempotency key for scheduling the
                flow run. Duplicate flow runs with the same idempotency key will only create
                a single flow run. This is useful for ensuring that only one run is created
                if this task is retried. If not provided, defaults to the active `task_run_id`.
            - scheduled_start_time (datetime, optional): the time to schedule the execution
                for; if not provided, defaults to now

        Returns:
            - str: the ID of the newly-scheduled flow run

        Raises:
            - ValueError: if flow was not provided, cannot be found, or if a project name was
                not provided while using Cloud as a backend

        Example:
            ```python
            from prefect.tasks.prefect.flow_run import StartFlowRun

            kickoff_task = StartFlowRun(project_name="Hello, World!", flow_name="My Cloud Flow")
            ```

        """

        # verify that flow and project names were passed where necessary
        if flow_name is None:
            raise ValueError("Must provide a flow name.")
        if project_name is None:
            raise ValueError("Must provide a project name.")

        where_clause = {
            "name": {"_eq": flow_name},
            "archived": {"_eq": False},
            "project": {"name": {"_eq": project_name}},
        }

        # find the flow ID to schedule
        query = {
            "query": {
                with_args(
                    "flow",
                    {
                        "where": where_clause,
                        "order_by": {"version": EnumValue("desc")},
                        "limit": 1,
                    },
                ): {"id"}
            }
        }

        client = Client()
        flow = client.graphql(query).data.flow

        # verify that a flow has been returned
        if not flow:
            raise ValueError("Flow '{}' not found.".format(flow_name))

        # grab the ID for the most recent version
        flow_id = flow[0].id

        if idempotency_key is None:
            idempotency_key = prefect.context.get("task_run_id", None)

        # providing an idempotency key ensures that retries for this task
        # will not create additional flow runs
        flow_run_id = client.create_flow_run(
            flow_id=flow_id,
            parameters=parameters,
            run_config=run_config,
            idempotency_key=idempotency_key,
            context=new_flow_context,
            run_name=run_name,
            scheduled_start_time=scheduled_start_time,
        )

        self.logger.debug(f"Flow Run {flow_run_id} created.")

        self.logger.debug(f"Creating link artifact for Flow Run {flow_run_id}.")
        run_link = client.get_cloud_url("flow-run", flow_run_id, as_user=False)
        create_link(urlparse(run_link).path)
        self.logger.info(f"Flow Run: {run_link}")

        if not self.wait:
            return flow_run_id

        while True:
            time.sleep(10)
            flow_run_state = client.get_flow_run_info(flow_run_id).state
            if flow_run_state.is_finished():
                exc = signal_from_state(flow_run_state)(
                    f"{flow_run_id} finished in state {flow_run_state}"
                )
                raise exc


class FlowRunTask(StartFlowRun):
    def __new__(cls, *args, **kwargs):  # type: ignore
        warnings.warn(
            "`FlowRunTask` has been renamed to `prefect.tasks.prefect.StartFlowRun`,"
            "please update your code accordingly",
            stacklevel=2,
        )
        return super().__new__(cls)
