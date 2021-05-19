import copy
import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Set,
    Any,
    Iterable,
    Type,
    cast,
)

import pendulum

import prefect
from prefect import Flow, Task
from prefect.backend.flow import FlowView
from prefect.backend.task_run import TaskRunView
from prefect.engine.state import State
from prefect.run_configs import RunConfig
from prefect.serialization.run_config import RunConfigSchema
from prefect.utilities.graphql import EnumValue, with_args
from prefect.utilities.logging import get_logger


logger = get_logger("backend.flow_run")


def watch_flow_run(
    flow_run_id: str,
    stream_logs: bool = True,
    output_fn: Callable[[int, str], None] = logger.log,
) -> "FlowRunView":
    """
    Watch execution of a flow run displaying state changes. This function will hang
    until the flow run enters a 'Finished' state.

    Args:
        flow_run_id: The flow run to watch
        stream_logs: If set, logs will be streamed from the flow run to here
        output_fn: A callable to use to display output. Must take a log level and
            message.

    Returns:
        FlowRunView: A view of the final state of the flow run

    """

    flow_run = FlowRunView.from_flow_run_id(flow_run_id)

    if flow_run.state.is_finished():
        output_fn(logging.INFO, "Your flow run is already finished!")
        return flow_run

    # The timestamp of the last displayed log so that we can scope each log query
    # to logs that have not been shown yet
    last_log_timestamp = None

    # A counter of states that have been displayed. Not a set so repeated states in the
    # backend are shown well.
    seen_states = 0

    # Some times (in seconds) to track displaying a warning about the flow not starting
    # on time
    total_time_elapsed = 0
    agent_warning_time_elapsed = 0
    agent_warning_initial_wait = 5
    agent_warning_repeat_interval = 30

    # We'll do a basic backoff for polling, not exposed as args because the user
    # probably should not need to tweak these.
    poll_min = poll_interval = 2
    poll_max = 10
    poll_factor = 1.5

    while not flow_run.state.is_finished():
        # Get the latest state
        flow_run = flow_run.get_latest()

        if (
            total_time_elapsed > agent_warning_initial_wait
            and agent_warning_time_elapsed > agent_warning_repeat_interval
            and not (flow_run.state.is_running() or flow_run.state.is_finished())
        ):
            agent_msg = check_for_compatible_agents(flow_run.labels)
            output_fn(
                logging.WARN,
                f"It has been {round(total_time_elapsed)} seconds and your flow run is "
                f"not started. {agent_msg}",
            )
            agent_warning_time_elapsed = 0

        # Create a shared message list so we can roll state changes and logs together
        # in the correct order
        messages = []

        # Add state change messages
        for state in flow_run.states[seen_states:]:
            messages.append(
                # Create some fake run logs
                FlowRunLog(
                    timestamp=state.timestamp,  # type: ignore
                    level=logging.INFO,
                    message=f"Entered state <{type(state).__name__}>: {state.message}",
                )
            )
            seen_states += 1

        if stream_logs:
            # Display logs if asked and the flow is running
            logs = flow_run.get_logs(start_time=last_log_timestamp)
            messages += logs
            if logs:
                # Set the last timestamp so the next query is scoped to logs we have
                # not seen yet
                last_log_timestamp = logs[-1].timestamp

        for timestamp, level, message in sorted(messages):
            level_name = logging.getLevelName(level)
            output_fn(
                level,
                f"{timestamp.in_tz(tz='local'):%H:%M:%S} | {level_name:<7} | {message}",
            )

        if not messages:
            # Delay the poll if there are no messages
            poll_interval = int(poll_interval * poll_factor)
        else:
            # Otherwise reset to the min poll time for a fast query
            poll_interval = poll_min

        poll_interval = min(poll_interval, poll_max)
        time.sleep(poll_interval)
        agent_warning_time_elapsed += poll_interval
        total_time_elapsed += poll_interval

    return flow_run


def execute_flow_run(
    flow_run_id: str,
    flow: "Flow" = None,
    runner_cls: Type["prefect.engine.flow_runner.FlowRunner"] = None,
    **kwargs: Any,
) -> "FlowRunView":
    """ "
    The primary entry point for executing a flow run. The flow run will be run
    in-process using the given `runner_cls` which defaults to the `CloudFlowRunner`.

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


def check_for_compatible_agents(labels: Iterable[str], since_minutes: int = 1) -> str:
    """
    Checks for agents compatible with a set of labels returning a user-friendly message
    indicating the status, roughly one of the following cases
    - There is a healthy agent with matching labels
    - There are N healthy agents with matching labels
    - There is an unhealthy agent with matching labels but no healthy agents matching
    - There are N unhealthy agents with matching labels but no healthy agents matching
    - There are no healthy agents at all and no unhealthy agents with matching labels
    - There are healthy agents but no healthy or unhealthy agent has matching labels


    Args:
        - labels: A set of labels; typically associated with a flow run
        - since_minutes: The amount of time in minutes to allow an agent to be idle and
            considered active/healthy still

    Returns:
        A message string
    """
    client = prefect.Client()

    labels = set(labels)
    labels_blurb = f"labels {labels!r}" if labels else "empty labels"

    result = client.graphql(
        {"query": {"agents": {"last_queried", "labels", "name", "id"}}}
    )

    agents = result.get("data", {}).get("agents")
    if agents is None:
        raise ValueError(f"Recieved bad result while querying for agents: {result}")

    # Parse last query times
    for agent in agents:
        agent.last_queried = cast(
            Optional[pendulum.DateTime],
            pendulum.parse(agent.last_queried) if agent.last_queried else None,
        )

    # Drop agents that have not queried
    agents = [agent for agent in agents if agent.last_queried is not None]

    # Drop agents that have not sent a recent hearbeat
    since = pendulum.now().subtract(minutes=since_minutes)
    healthy_agents = [agent for agent in agents if agent.last_queried >= since]

    # Search for the flow run labels in running agents
    matching_healthy = []
    matching_unhealthy = []

    for agent in agents:
        empty_labels_match = not agent.labels and not labels
        if empty_labels_match or (labels and labels.issubset(agent.labels)):
            if agent in healthy_agents:
                matching_healthy.append(agent)
            else:
                matching_unhealthy.append(agent)

    if len(matching_healthy) == 1:
        # Display the single matching agent
        name_blurb = f" ({agent.name})" if agent.name else ""
        last_queried = (pendulum.now() - agent.last_queried).as_interval().in_words()
        return (
            f"Agent {agent.id}{name_blurb} has matching labels and last queried "
            f"{last_queried} ago. It should deploy your flow run."
        )

    if len(matching_healthy) > 1:
        # Display that there are multiple matching agents
        return (
            f"Found {len(matching_healthy)} healthy agents with matching labels. One "
            "of them should pick up your flow."
        )

    # We now know we have no matching healthy agents...

    if not healthy_agents and not matching_unhealthy:
        # Display that there are no matching agents all-time
        return (
            "There are no healthy agents in your tenant and it does not look like an "
            "agent with the required labels has been run recently. Start an agent with "
            f"{labels_blurb} to run your flow."
        )

    if len(matching_unhealthy) == 1:
        # Display that there is a single matching unhealthy agent
        name_blurb = f" ({agent.name})" if agent.name else ""
        last_queried = (pendulum.now() - agent.last_queried).as_interval().in_words()
        return (
            f"Agent {agent.id}{name_blurb} has matching labels and last queried "
            f"{last_queried} ago. Since it hasn't queried recently, it looks "
            f"unhealthy. Restart it or start a new agent with {labels_blurb} to deploy "
            f"your flow run."
        )

    if len(matching_unhealthy) > 1:
        # Display that there are multiple matching unhealthy agents
        return (
            f"Found {len(matching_unhealthy)} agents with matching labels but they "
            "have not queried recently and look unhealthy. Restart one of them or "
            f"start a new agent with {labels_blurb} deploy your flow run."
        )

    # No matching healthy or unhealthy agents
    return (
        f"You have {len(healthy_agents)} healthy agents in your tenant but do not have "
        f"an agent with {labels_blurb}. Start an agent with matching labels to deploy "
        "your flow run."
    )


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
                        name="prefect.backend.api.flow_run.execute_flow_run",
                        message=message,
                        level="ERROR",
                    )
                ]
            )
        logger.error(message, exc_info=True)
        raise


class FlowRunLog(NamedTuple):
    """
    Small wrapper for backend log objects
    """

    timestamp: pendulum.DateTime
    level: int
    message: str

    @classmethod
    def from_dict(cls, data: dict) -> "FlowRunLog":
        return cls(
            cast(pendulum.DateTime, pendulum.parse(data["timestamp"])),
            logging.getLevelName(data["level"]),  # actually gets level int from name
            data["message"],
        )


class _TimestampedState(State):
    """
    Small wrapper for flow run states to include a timestamp

    TODO: We will likely want to include timestamps directly on `State`. This extension
          is written as a subclass for compatibility with that future change
    """

    timestamp: pendulum.DateTime

    @classmethod
    def from_dict(cls, data: dict) -> "_TimestampedState":
        state = cls.deserialize(data["serialized_state"])
        state = cast(_TimestampedState, state)
        # Our 3.6 compatible version of pendulum does not have `fromisoformat` so we
        # parse and cast
        state.timestamp = cast(pendulum.DateTime, pendulum.parse(data["timestamp"]))
        return state


class FlowRunView:
    """
    A view of Flow Run data stored in the Prefect API.

    Provides lazy loading of Task Runs from the flow run.

    This object is designed to be an immutable view of the data stored in the Prefect
    backend API at the time it is created. However, each time a task run is retrieved
    the latest data for that task will be pulled since they are loaded lazily. Finished
    task runs will be cached in this object to reduce the amount of network IO.

    Args:
        - flow_run_id: The uuid of the flow run
        - name: The name of the flow run
        - flow_id: The uuid of the flow this run is associated with
        - state: The state of the flow run
        - labels: The labels assigned to this flow run
        - parameters: Parameter overrides for this flow run
        - context: Context overrides for this flow run
        - updated_at: When this flow run was last updated in the backend
        - run_config: The `RunConfig` this flow run was configured with
        - states: A sorted list of past states the flow run has been in
        - task_runs: An iterable of task run metadata to cache in this view

    Properties:
        - flow: Metadata for the flow this run is associated with; lazily retrived on
            first use

    """

    def __init__(
        self,
        flow_run_id: str,
        name: str,
        flow_id: str,
        labels: List[str],
        parameters: dict,
        context: dict,
        state: State,
        states: List[_TimestampedState],
        updated_at: pendulum.DateTime,
        run_config: "RunConfig",
        task_runs: Iterable["TaskRunView"] = None,
    ):
        self.flow_run_id = flow_run_id
        self.name = name
        self.flow_id = flow_id
        self.state = state
        self.labels = labels
        self.parameters = parameters
        self.context = context
        self.updated_at = updated_at
        self.states = states
        self.run_config = run_config

        # Cached value of all task run ids for this flow run, only cached if the flow
        # is done running
        self._task_run_ids: Optional[List[str]] = None

        # Cached value of flow metadata
        self._flow: Optional[FlowView] = None

        # Store a mapping of task run ids to task runs
        self._cached_task_runs: Dict[str, "TaskRunView"] = {}

        # Store a mapping of slugs to task run ids (mapped tasks share a slug)
        self._task_slug_to_task_run_ids: Mapping[str, Set[str]] = defaultdict(set)

        if task_runs is not None:
            for task_run in task_runs:
                self._cache_task_run_if_finished(task_run)

    def _cache_task_run_if_finished(self, task_run: "TaskRunView") -> None:
        """
        Add a task run to the cache if it is in a finished state

        Args:
            - task_run: The task run to add
        """
        if task_run.state.is_finished():
            self._cached_task_runs[task_run.task_run_id] = task_run
            self._task_slug_to_task_run_ids[task_run.task_slug].add(
                task_run.task_run_id
            )

    def get_latest(self, load_static_tasks: bool = False) -> "FlowRunView":
        """
        Get the a new copy of this object with the latest data from the API. Cached
        `TaskRunView` objects will be passed to the new object. Only finished tasks
        are cached so the cached data cannot be stale.

        This will not mutate the current object.

        Args:
            - load_static_tasks: Pre-populate the task runs with results from flow tasks
                that are unmapped. Defaults to `False` because it may be wasteful to
                query for task run data when cached tasks are already copied over
                from the old object.

        Returns:
            A new instance of FlowRunView
        """
        return self.from_flow_run_id(
            flow_run_id=self.flow_run_id,
            load_static_tasks=load_static_tasks,
            _cached_task_runs=self._cached_task_runs.values(),
        )

    def get_logs(
        self,
        start_time: pendulum.DateTime = None,
    ) -> List["FlowRunLog"]:
        """
        Get logs for this flow run from `start_time` to `self.updated_at` which is the
        last time that the flow run was updated in the backend before this object was
        created.

        Args:
            - start_time (optional): A time to start the log query at, useful for
                limiting the scope. If not provided, all logs up to `updated_at` are
                retrieved.

        Returns:
            A list of `FlowRunLog` objects sorted by timestamp
        """

        client = prefect.Client()

        logs_query = {
            with_args(
                "logs",
                {
                    "order_by": {EnumValue("timestamp"): EnumValue("asc")},
                    "where": {
                        "_and": [
                            {"timestamp": {"_lte": self.updated_at.isoformat()}},
                            (
                                {"timestamp": {"_gt": start_time.isoformat()}}
                                if start_time
                                else {}
                            ),
                        ]
                    },
                },
            ): {"timestamp": True, "message": True, "level": True}
        }

        result = client.graphql(
            {
                "query": {
                    with_args(
                        "flow_run",
                        {
                            "where": {"id": {"_eq": self.flow_run_id}},
                        },
                    ): logs_query
                }
            }
        )

        # Unpack the result
        logs = result.get("data", {}).get("flow_run", [{}])[0].get("logs", [])

        return [FlowRunLog.from_dict(log) for log in logs]

    @property
    def flow(self) -> "FlowView":
        """
        Flow metadata for the flow associated with this flow run. Lazily loaded at call
        time then cached for future calls.

        Returns:
            An instance of FlowView
        """
        if self._flow is None:
            self._flow = FlowView.from_flow_id(flow_id=self.flow_id)

        return self._flow

    @classmethod
    def _from_flow_run_data(
        cls, flow_run_data: dict, task_runs: Iterable["TaskRunView"] = None
    ) -> "FlowRunView":
        """
        Instantiate a `TaskRunView` from serialized data.

        This method deserializes objects into their Prefect types.

        Exists to maintain consistency in the design of backend "View" classes.

        Args:
            - flow_run_data: A dict of flow run data
            - task_runs: An optional iterable of task runs to pre-populate the cache with

        Returns:
            A populated `FlowRunView` instance
        """
        flow_run_data = flow_run_data.copy()  # Avoid mutating the input object

        flow_run_id = flow_run_data.pop("id")
        state = State.deserialize(flow_run_data.pop("serialized_state"))
        run_config = RunConfigSchema().load(flow_run_data.pop("run_config"))

        states_data = flow_run_data.pop("states", [])
        states = list(
            sorted(
                [_TimestampedState.from_dict(state_data) for state_data in states_data],
                key=lambda s: s.timestamp,
            )
        )
        updated_at = cast(
            pendulum.DateTime, pendulum.parse(flow_run_data.pop("updated"))
        )

        return cls(
            flow_run_id=flow_run_id,
            task_runs=task_runs,
            state=state,
            updated_at=updated_at,
            states=states,
            run_config=run_config,
            **flow_run_data,
        )

    @classmethod
    def from_flow_run_id(
        cls,
        flow_run_id: str,
        load_static_tasks: bool = True,
        _cached_task_runs: Iterable["TaskRunView"] = None,
    ) -> "FlowRunView":
        """
        Get an instance of this class filled with information by querying for the given
        flow run id

        Args:
            - flow_run_id: the flow run id to lookup
            - load_static_tasks: Pre-populate the task runs with results from flow tasks
                that are unmapped.
            - _cached_task_runs: Pre-populate the task runs with an existing iterable of
                task runs

        Returns:
            A populated `FlowRunView` instance
        """
        flow_run_data = cls._query_for_flow_run(where={"id": {"_eq": flow_run_id}})

        if load_static_tasks:
            task_run_data = TaskRunView._query_for_task_runs(
                where={
                    "map_index": {"_eq": -1},
                    "flow_run_id": {"_eq": flow_run_id},
                },
            )
            task_runs = [
                TaskRunView._from_task_run_data(data) for data in task_run_data
            ]

        else:
            task_runs = []

        # Combine with the provided `_cached_task_runs` iterable
        task_runs = task_runs + list(_cached_task_runs or [])

        return cls._from_flow_run_data(flow_run_data, task_runs=task_runs)

    @staticmethod
    def _query_for_flow_run(where: dict) -> dict:
        client = prefect.Client()

        flow_run_query = {
            "query": {
                with_args("flow_run", {"where": where}): {
                    "id": True,
                    "name": True,
                    "flow_id": True,
                    "serialized_state": True,
                    "states": {"timestamp", "serialized_state"},
                    "labels": True,
                    "parameters": True,
                    "context": True,
                    "updated": True,
                    "run_config": True,
                }
            }
        }

        result = client.graphql(flow_run_query)
        flow_runs = result.get("data", {}).get("flow_run", None)

        if flow_runs is None:
            raise ValueError(
                f"Received bad result while querying for flow runs where {where}: "
                f"{result}"
            )

        if not flow_runs:
            raise ValueError(
                f"No flow runs found while querying for flow runs where {where}"
            )

        if len(flow_runs) > 1:
            raise ValueError(
                f"Found multiple ({len(flow_runs)}) flow runs while querying for flow "
                f"runs where {where}: {flow_runs}"
            )

        return flow_runs[0]

    def get_task_run(
        self, task: Task = None, task_slug: str = None, task_run_id: str = None
    ) -> "TaskRunView":
        """
        Get information about a task run from this flow run. Lookup is available by one
        of the following arguments. If the task information is not available locally
        already, we will query the database for it. If multiple arguments are provided,
        we will validate that they are consistent with each other.

        All retrieved task runs that are finished will be cached to avoid re-querying in
        repeated calls

        Args:
            -  task: A `prefect.Task` object to use for the lookup. The slug will be
                pulled from the task to actually perform the query
            - task_slug: A task slug string to use for the lookup
            - task_run_id: A task run uuid to use for the lookup

        Returns:
            A cached or newly constructed TaskRunView instance
        """

        if task is not None:
            if not task.slug and not task_slug:
                raise ValueError(
                    f"Given task {task} does not have a `slug` set and cannot be "
                    "used for lookups; this generally occurs when the flow has not "
                    "been registered or serialized."
                )

            if task_slug is not None and task_slug != task.slug:
                raise ValueError(
                    "Both `task` and `task_slug` were provided but they contain "
                    "different slug values! "
                    f"`task.slug == {task.slug!r}` and `task_slug == {task_slug!r}`"
                )

            # If they've passed a task_slug that matches this task's slug we can
            # basically ignore the passed `task` object
            if not task_slug:
                task_slug = task.slug

        if task_run_id is not None:
            # Load from the cache if available or query for results
            result = (
                self._cached_task_runs[task_run_id]
                if task_run_id in self._cached_task_runs
                else TaskRunView.from_task_run_id(task_run_id)
            )

            if task_slug is not None and result.task_slug != task_slug:
                raise ValueError(
                    "Both `task_slug` and `task_run_id` were provided but the task "
                    "found using `task_run_id` has a different slug! "
                    f"`task_slug == {task_slug!r}` and "
                    f"`result.task_slug == {result.task_slug!r}`"
                )

            self._cache_task_run_if_finished(result)
            return result

        if task_slug is not None:

            if task_slug in self._task_slug_to_task_run_ids:
                task_run_ids = self._task_slug_to_task_run_ids[task_slug]

                # Check for the 'base' task, for unmapped tasks there should always
                # just be one run id but for mapped tasks there will be multiple
                for task_run_id in task_run_ids:
                    result = self._cached_task_runs[task_run_id]
                    if result.map_index == -1:
                        return result

                # We did not find the base mapped task in the cache so we'll
                # drop through to query for it

            result = TaskRunView.from_task_slug(
                task_slug=task_slug, flow_run_id=self.flow_run_id
            )
            self._cache_task_run_if_finished(result)
            return result

        raise ValueError(
            "One of `task_run_id`, `task`, or `task_slug` must be provided!"
        )

    def get_all_task_runs(self) -> List["TaskRunView"]:
        """
        Get all task runs for this flow run in a single query. Finished task run data
        is cached so future lookups do not query the backend.

        Returns:
            A list of TaskRunView objects
        """
        if len(self.task_run_ids) > 1000:
            raise ValueError(
                "Refusing to `get_all_task_runs` for a flow with more than 1000 tasks. "
                "Please load the tasks you are interested in individually."
            )

        # Run a single query instead of querying for each task run separately
        task_run_data = TaskRunView._query_for_task_runs(
            where={
                "flow_run_id": {"_eq": self.flow_run_id},
                "task_run_id": {"_not", {"_in": list(self._cached_task_runs.keys())}},
            }
        )
        task_runs = [TaskRunView._from_task_run_data(data) for data in task_run_data]
        # Add to cache
        for task_run in task_runs:
            self._cache_task_run_if_finished(task_run)

        return task_runs + list(self._cached_task_runs.values())

    @property
    def task_run_ids(self) -> List[str]:
        """
        Get all task run ids associated with this flow run. Lazily loaded at call time
        then cached for future calls.

        Returns:
            A list of string task run ids
        """
        # Return the cached value immediately if it exists
        if self._task_run_ids:
            return self._task_run_ids

        client = prefect.Client()

        task_query = {
            "query": {
                with_args(
                    "task_run",
                    {
                        "where": {
                            "flow_run_id": {"_eq": self.flow_run_id},
                        }
                    },
                ): {
                    "id": True,
                }
            }
        }
        result = client.graphql(task_query)
        task_runs = result.get("data", {}).get("task_run", None)

        if task_runs is None:
            logger.warning(
                f"Failed to load task run ids for flow run {self.flow_run_id}: "
                f"{result}"
            )

        task_run_ids = [task_run["id"] for task_run in task_runs]

        # If the flow run is done, we can safely cache this value
        if self.state.is_finished():
            self._task_run_ids = task_run_ids

        return task_run_ids

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}"
            "("
            + ", ".join(
                [
                    f"flow_run_id={self.flow_run_id!r}",
                    f"name={self.name!r}",
                    f"state={self.state!r}",
                    f"cached_task_runs={len(self._cached_task_runs)}",
                ]
            )
            + ")"
        )
