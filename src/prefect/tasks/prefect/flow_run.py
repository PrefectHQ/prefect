"""
Tasks for creating and inspecting Prefect flow runs


Example:
    ```python
    import prefect
    from prefect import task, Flow, Parameter
    from prefect.tasks.prefect.flow_run import (
        create_flow_run,
        get_task_run_result,
    )


    @task
    def create_some_data(length: int):
        return list(range(length))


    with Flow("child") as child_flow:
        data_size = Parameter("data_size", default=5)
        data = create_some_data(data_size)


    with Flow("parent") as parent_flow:
        child_run_id = create_flow_run(
            flow_name=child_flow.name, parameters=dict(data_size=10)
        )
        child_data = get_task_run_result(child_run_id, "create_some_data-1")

    if __name__ == "__main__":
        # Register the sub flow
        child_flow.register("default")

        # Run the parent flow locally
        flow_run = parent_flow.run()

        # Print the retrieved data
        print(flow_run.result[child_data].result)

    ```
"""

import datetime
import time
import pendulum
from typing import Any, Iterable, Optional, Union
from datetime import timedelta
from urllib.parse import urlparse

import prefect
from prefect import Client, Task, task
from prefect.artifacts import create_link
from prefect.backend.flow_run import FlowRunView, FlowView, watch_flow_run
from prefect.client import Client
from prefect.engine.signals import signal_from_state
from prefect.run_configs import RunConfig
from prefect.utilities.graphql import EnumValue, with_args
from prefect.utilities.tasks import defaults_from_attrs


@task
def create_flow_run(
    flow_id: str = None,
    flow_name: str = None,
    project_name: str = "",
    parameters: dict = None,
    context: dict = None,
    labels: Iterable[str] = None,
    run_name: str = None,
    run_config: Optional[RunConfig] = None,
    scheduled_start_time: Optional[Union[pendulum.DateTime, datetime.datetime]] = None,
) -> str:
    """
    Task to create a flow run in the Prefect backend.

    The flow to run must be registered and an agent must be available to deploy the
    flow run.

    Args:
        - flow_id: The flow or flow group uuid to lookup the flow to run
        - flow_name: The flow name to lookup the flow to run
        - project_name: The project name to lookup the flow to run. For use with
            `flow_name` if you have flows with the same name in multiple projects
        - parameters: An optional dictionary of parameters to pass to the flow run
        - context: An optional dictionary of context variables to pass to the flow run
        - labels: An optional iterable of labels to set on the flow run; if not
            provided, the default set of labels for the flow will be used
        - run_name: An optional name for the flow run; if not provided, the name will
            be generated as "{current_run_name}-{flow_name}"
        - run_config: An optional run config to use for the flow run; will override any
            existing run config settings
        - scheduled_start_time: An optional time in the future to schedule flow run
            execution for. If not provided, the flow run will be scheduled to start now

    Returns:
        str: The UUID of the created flow run
    """

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

    logger = prefect.context.logger
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

    # A run name for logging display; robust to 'run_name' being empty
    run_name_dsp = run_name or "<generated-name>"

    logger.info(f"Creating flow run {run_name_dsp!r} for flow {flow.name!r}...")

    client = Client()
    flow_run_id = client.create_flow_run(
        flow_id=flow.flow_id,
        parameters=parameters,
        context=context,
        labels=labels,
        run_name=run_name,
        run_config=run_config,
        scheduled_start_time=scheduled_start_time,
    )

    run_url = client.get_cloud_url("flow-run", flow_run_id)
    logger.info(f"Created flow run {run_name_dsp!r}: {run_url}")
    return flow_run_id


# Flow run results ---------------------------------------------------------------------


@task
def get_task_run_result(
    flow_run_id: str, task_slug: str, map_index: int = -1, poll_time: int = 5
) -> Any:
    """
    Task to get the result of a task from a flow run.

    Will wait for the flow run to finish entirely or dynamic task run results will not
    be properly populated.

    Results are loaded from the `Result` location of the task which may not be
    accessible from where this task is executed. You will need to ensure results can
    be accessed.

    Args:
        - flow_run_id: The flow run the task run belongs to
        - task_slug: The 'slug' of the task run you want to get the result of
        - map_index: If the task is mapped, the index you would like to access. By
            default, if given a mapped task, all of the child results will be loaded.
        - poll_time: The amount of time to wait while polling to check if the sub-flow
            has finished

    Returns:
        Any: The return value of the task
    """
    logger = prefect.context.logger

    if not task_slug:
        # Catch this explicitly because the user may user `task.slug` which is often
        # null
        raise ValueError("Required argument `task_slug` is empty")

    task_dsp = repr(task_slug) if map_index == -1 else f"'{task_slug}[{map_index}]'"

    if prefect.context.get("flow_run_id") == flow_run_id:
        # Since we are going to wait for flow run completion, if they pass this flow
        # run id, we will hang forever.
        raise ValueError(
            "Given `flow_run_id` is the same as the currently running flow. The "
            "`get_task_run_result` task cannot be used to retrieve results from the "
            "flow run it belongs to."
        )

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
    flow_run_id: str, stream_states: bool = True, stream_logs: bool = False
) -> "FlowRunView":
    """
    Task to wait for a flow run to finish executing, streaming state and log information

    Args:
        - flow_run_id: The flow run id to wait for
        - stream_states: Stream information about the flow run state changes
        - stream_logs: Stream flow run logs; if `stream_state` is `False` this will be
            ignored

    Returns:
        FlowRunView: A view of the flow run after completion
    """

    flow_run = FlowRunView.from_flow_run_id(flow_run_id)

    for log in watch_flow_run(
        flow_run_id, stream_states=stream_states, stream_logs=stream_logs
    ):
        message = f"Flow {flow_run.name!r}: {log.message}"
        prefect.context.logger.log(log.level, message)

    # Return the final view of the flow run
    return flow_run.get_latest()


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
        - poll_interval (timedelta): the time to wait between each check if the flow is finished.
                Has to be >= 3 seconds. Used only if `wait=True`. Defaults to 10 seconds.
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
        poll_interval: timedelta = timedelta(seconds=10),
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
        if poll_interval.total_seconds() < 3:
            raise ValueError(
                "`poll_interval` needs to be at least 3 seconds to avoid spamming the Prefect server. "
                f"(poll_interval == {poll_interval.total_seconds()} seconds)!"
            )
        self.poll_interval = poll_interval
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
            time.sleep(self.poll_interval.total_seconds())
            flow_run_state = client.get_flow_run_info(flow_run_id).state
            if flow_run_state.is_finished():
                exc = signal_from_state(flow_run_state)(
                    f"{flow_run_id} finished in state {flow_run_state}"
                )
                raise exc
