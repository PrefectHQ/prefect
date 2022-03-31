import functools
import logging
import math
import os
import signal
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Generator, Iterable, Optional, Set, Type, cast, Set, List
from urllib.parse import urlparse

import pendulum
from tornado import web
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer

from prefect import config
from prefect.client import Client
from prefect.engine.state import Failed, Submitted
from prefect.run_configs import RunConfig, UniversalRun
from prefect.serialization.state import StateSchema
from prefect.serialization.run_config import RunConfigSchema
from prefect.utilities.context import context
from prefect.utilities.graphql import GraphQLResult, with_args

ascii_name = r"""
 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/
"""
# Event to notify agent process to start looking for available flow runs.
AGENT_WAKE_EVENT = threading.Event()


@contextmanager
def exit_handler(agent: "Agent") -> Generator:
    exit_event = threading.Event()

    def _exit_handler(*args: Any, **kwargs: Any) -> None:
        agent.logger.info("Keyboard interrupt received! Shutting down...")
        exit_event.set()
        AGENT_WAKE_EVENT.set()

    original = signal.getsignal(signal.SIGINT)
    try:
        signal.signal(signal.SIGINT, _exit_handler)
        yield exit_event
    except SystemExit:
        pass
    finally:
        signal.signal(signal.SIGINT, original)


class HealthHandler(web.RequestHandler):
    """Respond to /api/health"""

    def get(self) -> None:
        # Empty json blob, may add more info later
        self.write({})


class PokeHandler(web.RequestHandler):
    """Respond to /api/poke

    The handler is expected to be called by user to notify agent of available
    flow runs waiting for execution.
    """

    def get(self) -> None:
        # Wake up agent that might be waiting for interval loop to complete.
        AGENT_WAKE_EVENT.set()


class Agent:
    """
    Base class for Agents. Information on using the Prefect agents can be found at
    https://docs.prefect.io/orchestration/agents/overview.html

    This Agent class is a standard point for executing Flows through the Prefect API. It is meant to
    have subclasses which inherit functionality from this class. The only piece that the
    subclasses should implement is the `deploy_flows` function, which specifies how to run a
    Flow on the given platform. It is built in this way to keep Prefect API logic standard
    but allows for platform specific customizability.

    Args:
        - agent_config_id (str, optional): An optional agent configuration ID that can be used to set
            configuration based on an agent from a backend API. If set, all configuration values will be
            pulled from backend agent configuration. If not set, any manual kwargs will be used.
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string
            identifiers used by Prefect Agents when polling for work
        - env_vars (dict, optional): a dictionary of environment variables and values that will
            be set on each flow run that this agent submits for execution
        - max_polls (int, optional): maximum number of times the agent will poll the Prefect API
            for flow runs; defaults to infinite
        - agent_address (str, optional): Address to serve internal api at. Currently this is
            just health checks for use by an orchestration layer. Leave blank for no api server
            (default).
        - no_cloud_logs (bool, optional): Disable logging to a Prefect backend for this agent
            and all deployed flow runs
    """

    # Loop intervals for query sleep backoff
    _loop_intervals = {
        0: 0.25,
        1: 0.5,
        2: 1.0,
        3: 2.0,
        4: 4.0,
        5: 8.0,
        6: 10.0,
    }

    def __init__(
        self,
        agent_config_id: str = None,
        name: str = None,
        labels: Iterable[str] = None,
        env_vars: dict = None,
        max_polls: int = None,
        agent_address: str = None,
        no_cloud_logs: bool = None,
    ) -> None:
        # Auth with an API key will be loaded from the config or disk by the Client
        self.client = Client(api_server=config.cloud.api)

        self.agent_config_id = agent_config_id
        self._agent_config: Optional[dict] = None

        self.name = name or config.cloud.agent.get("name", "agent")
        self.labels = labels or list(config.cloud.agent.get("labels", []))
        self.env_vars = env_vars or config.cloud.agent.get("env_vars", dict())
        self.max_polls = max_polls

        if no_cloud_logs is None:  # Load from config if unset
            self.log_to_cloud = config.cloud.send_flow_run_logs
        else:
            self.log_to_cloud = not no_cloud_logs

        self.heartbeat_period = 60  # exposed for testing
        self.agent_address = agent_address or config.cloud.agent.get("agent_address")

        # These track background task objects so we can tear them down on exit
        self._api_server: Optional[HTTPServer] = None
        self._api_server_loop: Optional[IOLoop] = None
        self._api_server_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None

        # Create the default logger
        self.logger = self._get_logger()

        # Store a set of flows that are being submitted to prevent duplicate submissions
        self.submitting_flow_runs: Set[str] = set()

        # Log configuration options
        self.logger.debug(f"Environment variables: {[*self.env_vars]}")
        self.logger.debug(f"Max polls: {self.max_polls}")
        self.logger.debug(f"Agent address: {self.agent_address}")
        self.logger.debug(f"Log to Cloud: {self.log_to_cloud}")
        self.logger.debug(f"Prefect backend: {config.backend}")

    @property
    def flow_run_api_key(self) -> Optional[str]:
        """
        Get the API key that the flow run should use to authenticate with Cloud.

        Currently just returns the key that the agent is using to query for flow runs
        """
        return self.client.api_key

    def start(self) -> None:
        """
        The main entrypoint to the agent process. Sets up the agent then continuously
        polls for work to submit.

        This is the only method that should need to be called externally.
        """

        try:
            self._setup_api_connection()

            # Call subclass hook
            self.on_startup()

            # Print some nice startup logs
            self._show_startup_display()

            # Start background tasks
            self._start_heartbeat_thread()
            if self.agent_address:
                self._start_agent_api_server()

            # Enter the main loop checking for new flows
            with exit_handler(self) as exit_event:
                self._enter_work_polling_loop(exit_event)

        finally:

            self.on_shutdown()
            self._stop_agent_api_server()
            self._stop_heartbeat_thread()

    # Subclass hooks -------------------------------------------------------------------
    # -- These are intended to be defined by specific agent types

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Invoked when a flow should be deployed for execution by this agent

        Must be implemented by a child class.

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object

        Returns:
            - str: Information about the deployment

        Raises:
            - ValueError: if deployment attempted on unsupported Storage type
        """
        raise NotImplementedError()

    def heartbeat(self) -> None:
        """
        Invoked by the heartbeat thread on a loop.

        A hook for child classes to implement.
        """
        pass

    def on_startup(self) -> None:
        """
        Invoked when the agent is starting up after verifying the connection to the API
        but before background tasks are created and work begins

        A hook for child classes to optionally implement.
        """
        pass

    def on_shutdown(self) -> None:
        """
        Invoked when the event loop is exiting and the agent is shutting down.

        A hook for child classes to optionally implement.
        """
        pass

    # Main work loop -------------------------------------------------------------------
    # We've now entered implementation details of the agent base. Subclasses should
    # not need to worry about how this works.

    def _enter_work_polling_loop(self, exit_event: threading.Event) -> None:
        """
        This method will loop until `exit_event` is set or `max_polls` is reached. The
        primary call is to `_submit_deploy_flow_run_jobs` which handles querying for
        and submitting ready flow runs. If there were flow runs to process, the loop
        will repeat immediately to attempt to pull all ready work quickly. If not, the
        loop will backoff with an increasing sleep.
        """
        backoff_index = 0
        remaining_polls = math.inf if self.max_polls is None else self.max_polls

        # the max workers default has changed in 3.8. For stable results the
        # default 3.8 behavior is elected here.
        max_workers = min(32, (os.cpu_count() or 1) + 4)
        self.logger.debug(
            f"Running thread pool with {max_workers} workers to handle flow deployment"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while not exit_event.is_set() and remaining_polls:
                # Reset the event in case it was set by poke handler.
                AGENT_WAKE_EVENT.clear()

                submitted_flow_runs = self._submit_deploy_flow_run_jobs(
                    executor=executor,
                )

                # Flow runs were found, so start the next iteration immediately
                if submitted_flow_runs:
                    backoff_index = 0
                # Otherwise, add to the index (unless we are at the max already)
                elif backoff_index < max(self._loop_intervals.keys()):
                    backoff_index += 1

                remaining_polls -= 1

                self.logger.debug(
                    "Sleeping flow run poller for {} seconds...".format(
                        self._loop_intervals[backoff_index]
                    )
                )

                # Wait for loop interval timeout or agent to be poked by
                # external process before querying for flow runs again.
                AGENT_WAKE_EVENT.wait(timeout=self._loop_intervals[backoff_index])

    def _submit_deploy_flow_run_jobs(self, executor: "ThreadPoolExecutor") -> list:
        """
        - Queries for ready flow runs
        - Submits calls of `_deploy_flow_run(flow_run)` to the executor
        - Tracks submitted runs to prevent double deployments

        Args:
            - executor (ThreadPoolExecutor): the interface to submit flow deployments in
                background threads

        Returns:
            - A list of submitted flow runs
        """
        # Query for ready runs -- allowing for intermittent failures by handling
        # exceptions
        try:
            flow_run_ids = self._get_ready_flow_runs()
        except Exception:
            self.logger.error("Failed to query for ready flow runs", exc_info=True)
            return []

        # Get the flow run metadata necessary for deployment in bulk; this also filters
        # flow runs that may have been submitted by another agent in the meantime
        try:
            flow_runs = self._get_flow_run_metadata(flow_run_ids)
        except Exception:
            self.logger.error("Failed to query for flow run metadata", exc_info=True)
            return []

        # Deploy each flow run in parallel with the executor
        for flow_run in flow_runs:
            self.logger.debug(f"Submitting flow run {flow_run.id} for deployment...")
            executor.submit(self._deploy_flow_run, flow_run).add_done_callback(
                functools.partial(
                    self._deploy_flow_run_completed_callback, flow_run_id=flow_run.id
                )
            )
            self.submitting_flow_runs.add(flow_run.id)

        return flow_runs

    def _deploy_flow_run(
        self,
        flow_run: "GraphQLResult",
    ) -> None:
        """
        Deploy a flow run and update Cloud with the resulting deployment info.
        If any errors occur when submitting the flow run, capture the error and log to
        Cloud.

        Args:
            - flow_run (GraphQLResult): The specific flow run to deploy
        """

        # Deploy flow run and mark failed if any deployment error
        try:
            # Wait for the flow run's start time. The agent pre-fetches runs that may
            # not need to start until up to 10 seconds later so we need to wait to
            # prevent the flow from starting early
            #
            # `state.start_time` is used instead of `flow_run.scheduled_start_time` for
            # execution; `scheduled_start_time` is only to record the originally scheduled
            # start time of the flow run
            #
            # There are two possible states the flow run could be in at this point
            # - Scheduled - in this case the flow run state will have a start time
            # - Running - in this case the flow run state will not have a start time so we default to now
            flow_run_state = StateSchema().load(flow_run.serialized_state)
            start_time = getattr(flow_run_state, "start_time", pendulum.now())
            delay_seconds = max(0, (start_time - pendulum.now()).total_seconds())
            if delay_seconds:
                self.logger.debug(
                    f"Waiting {delay_seconds}s to deploy flow run {flow_run.id} on "
                    "time..."
                )
                time.sleep(delay_seconds)

            self.logger.info(
                f"Deploying flow run {flow_run.id} to execution environment..."
            )

            self._mark_flow_as_submitted(flow_run)

            # Call the main deployment hook
            deployment_info = self.deploy_flow(flow_run)

            self.logger.info(f"Completed deployment of flow run {flow_run.id}")

            self._safe_write_run_log(
                flow_run,
                message="Submitted for execution: {}".format(deployment_info),
                level="INFO",
            )

        except Exception as exc:
            # On exception, we'll mark this flow as failed

            # if first failure was a state update error, we don't want to try another
            # state update
            if "State update failed" in str(exc):
                self.logger.debug("Updating Flow Run state failed: {}".format(str(exc)))
                return

            # This is to match existing past behavior, I cannot imagine we would reach
            # this point with a flow run that has no id
            if not getattr(flow_run, "id"):
                self.logger.error("Flow run is missing an id.", exc_info=True)
                return

            self.logger.error(
                f"Exception encountered while deploying flow run {flow_run.id}",
                exc_info=True,
            )

            self._safe_write_run_log(
                flow_run,
                message=str(exc),
                level="ERROR",
            )
            self._mark_flow_as_failed(flow_run=flow_run, message=str(exc))

            self.logger.error(f"Deployment of {flow_run.id} aborted!")

    def _deploy_flow_run_completed_callback(
        self, _: "Future", flow_run_id: str
    ) -> None:
        """
        Called on completion of `_deploy_flow_run` regardless of success.
        Clears the `flow_run_id` from the submitted flow runs cached. No matter what
        the result of the deployment job was, if the flow is in the ready queue from
        the backend API this agent should be open to trying to deploy it again.

        Args:
            - _ (Future): required for future callbacks but unused
            - flow_run_id (str): the id of the flow run that the future represents.
        """
        self.submitting_flow_runs.remove(flow_run_id)

    # Background jobs ------------------------------------------------------------------
    # - Agent API server
    # - Heartbeat thread

    def _start_agent_api_server(self) -> None:
        if not self.agent_address:
            raise ValueError("Cannot run agent API without setting `agent_address`")

        parsed = urlparse(self.agent_address)
        if not parsed.port:
            raise ValueError("Must specify port in agent address")
        port = cast(int, parsed.port)
        hostname = parsed.hostname or ""
        app = web.Application(
            [("/api/health", HealthHandler), ("/api/poke", PokeHandler)]
        )

        def run() -> None:
            # Ensure there's an active event loop in this thread
            import asyncio

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())

            self.logger.debug(
                f"Agent API server listening on port {self.agent_address}"
            )
            self._api_server = app.listen(port, address=hostname)
            self._api_server_loop = IOLoop.current()
            self._api_server_loop.start()  # type: ignore

        self._api_server_thread = threading.Thread(
            name="api-server", target=run, daemon=True
        )
        self._api_server_thread.start()

    def _stop_agent_api_server(self) -> None:
        if self._api_server is not None:
            self.logger.debug("Stopping agent API server")
            self._api_server.stop()

        if self._api_server_loop is not None:
            self.logger.debug("Stopping agent API server loop")

            def stop_server() -> None:
                try:
                    loop = cast(IOLoop, self._api_server_loop)
                    loop.stop()
                except Exception:
                    pass

            self._api_server_loop.add_callback(stop_server)

        if self._api_server_thread is not None:
            self.logger.debug("Joining agent API threads")
            # Give the server a small period to shutdown nicely, otherwise it
            # will terminate on exit anyway since it's a daemon thread.
            self._api_server_thread.join(timeout=1)

    def _start_heartbeat_thread(self) -> None:
        """
        Run a thread to send heartbeats to the backend API, should be called at `start`
        """

        def run() -> None:
            while True:
                try:
                    self.logger.debug("Sending agent heartbeat...")
                    self.heartbeat()
                except Exception:
                    self.logger.error(
                        "Error in agent heartbeat, will try again in %.1f seconds...",
                        self.heartbeat_period,
                        exc_info=True,
                    )
                else:
                    self.logger.debug(
                        "Heartbeat succesful! Sleeping for %.1f seconds...",
                        self.heartbeat_period,
                    )
                time.sleep(self.heartbeat_period)

        self._heartbeat_thread = threading.Thread(
            name="heartbeat", target=run, daemon=True
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat_thread(self) -> None:
        """
        Stop the heartbeat thread, should be called at `cleanup`
        """
        if self._heartbeat_thread is not None:
            self.logger.debug("Stopping heartbeat thread...")
            self._heartbeat_thread.join(timeout=1)

    # Backend API queries --------------------------------------------------------------

    def _get_ready_flow_runs(self, prefetch_seconds: int = 10) -> Set[str]:
        """
        Query the Prefect API for flow runs in the 'ready' queue. Results from here
        should be filtered by '_get_flow_run_metadata' to prevent duplicate submissions
        across agents.

        Args:
            - prefetch_seconds: The number of seconds in the future to fetch runs for.
                This reduces the chance of a flow starting late due to a polling loop
                backoff and should be set to the largest loop interval.
                `_deploy_flow_run` will wait until the true scheduled start time before
                deploying the flow.

        Returns:
            - set: A set of flow run ids that are ready
        """
        self.logger.debug("Querying for ready flow runs...")

        # keep a copy of what was submitted running before the query as the thread
        # pool might modify the set in the meantime
        currently_submitting_flow_runs = self.submitting_flow_runs.copy()

        # Get scheduled flow runs from queue
        mutation = {
            "mutation($input: get_runs_in_queue_input!)": {
                "get_runs_in_queue(input: $input)": {"flow_run_ids"}
            }
        }

        now = pendulum.now("UTC")
        result = self.client.graphql(
            mutation,
            variables={
                "input": {
                    "before": now.add(seconds=prefetch_seconds).isoformat(),
                    "labels": list(self.labels),
                    "tenant_id": self.client.tenant_id,
                }
            },
        )

        # we queried all of the available flow runs, however, some may have already been pulled
        # by this agent and are in the process of being submitted in the background. We do not
        # want to act on these "duplicate" flow runs until we've been assured that the background
        # thread has attempted to submit the work (successful or otherwise).
        flow_run_ids = set(result.data.get_runs_in_queue.flow_run_ids)  # type: ignore

        if flow_run_ids:
            msg = f"Found {len(flow_run_ids)} ready flow run(s): {flow_run_ids}"
        else:
            msg = "No ready flow runs found."

        already_submitting = flow_run_ids & currently_submitting_flow_runs
        target_flow_run_ids = flow_run_ids - already_submitting

        if already_submitting:
            msg += " ({} already being submitted: {})".format(
                len(already_submitting), list(already_submitting)
            )

        self.logger.debug(msg)
        return target_flow_run_ids

    def _get_flow_run_metadata(
        self,
        flow_run_ids: Iterable[str],
    ) -> List["GraphQLResult"]:
        """
        Get metadata about a collection of flow run ids that the agent is preparing
        to submit

        This function will filter the flow runs to a collection where:

        - The flow run is in a 'Scheduled' state. This prevents flow runs that have
          been submitted by another agent from being submitted again.

        - The flow run is in another state, but has task runs in a 'Running' state
          scheduled to start now. This is for retries in which the flow run is placed
          back into the ready queue but is not in a Scheduled state.

        Args:
            flow_run_ids: Flow run ids to query (order will not be respected)
            start_time: Only

        Returns:
           List: Metadata per flow run sorted by scheduled start time (ascending)
        """
        if not flow_run_ids:
            return []

        flow_run_ids = list(flow_run_ids)
        self.logger.debug(f"Retrieving metadata for {len(flow_run_ids)} flow run(s)...")

        # This buffer allows flow runs to retry immediately in their own deployment
        # without the agent creating a second deployment
        retry_start_time_buffer = pendulum.now("UTC").subtract(seconds=3).isoformat()

        where = {
            # Only get flow runs in the requested set
            "id": {"_in": flow_run_ids},
            # and filter by the additional criteria...
            "_or": [
                # This flow run has not been taken by another agent
                {"state": {"_eq": "Scheduled"}},
                # Or, this flow run has been set to retry and has not been immediately
                # retried in its own process
                {
                    "state": {"_eq": "Running"},
                    "task_runs": {
                        "state_start_time": {"_lte": retry_start_time_buffer}
                    },
                },
            ],
        }

        query = {
            "query": {
                with_args("flow_run", {"where": where}): {
                    "id": True,
                    "version": True,
                    "state": True,
                    "serialized_state": True,
                    "parameters": True,
                    "scheduled_start_time": True,
                    "run_config": True,
                    "name": True,
                    "flow": {
                        "id",
                        "name",
                        "environment",
                        "storage",
                        "version",
                        "core_version",
                    },
                    # Collect and return task run metadata as well so the state can be
                    # updated in `_mark_flow_as_submitted`
                    with_args(
                        "task_runs",
                        {
                            "where": {
                                "state_start_time": {"_lte": retry_start_time_buffer}
                            }
                        },
                    ): {"id", "version", "task_id", "serialized_state"},
                }
            }
        }
        result = self.client.graphql(query)
        return sorted(
            result.data.flow_run,
            key=lambda flow_run: flow_run.serialized_state.get(
                "start_time", pendulum.now("utc").isoformat()
            ),
        )

    def _mark_flow_as_submitted(self, flow_run: GraphQLResult) -> None:
        """
        After a flow run is grabbed this function sets the state to Submitted so it
        won't be picked up by any other processes

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object
        """
        # Set flow run state to `Submitted` if it is currently `Scheduled`
        if StateSchema().load(flow_run.serialized_state).is_scheduled():

            self.logger.debug(
                f"Updating flow run {flow_run.id} state from Scheduled -> Submitted..."
            )
            self.client.set_flow_run_state(
                flow_run_id=flow_run.id,
                version=flow_run.version,
                state=Submitted(
                    message="Submitted for execution",
                    state=StateSchema().load(flow_run.serialized_state),
                ),
            )

        # Set task run states to `Submitted` if they are currently `Scheduled`
        task_runs_updated = 0
        for task_run in flow_run.task_runs:
            if StateSchema().load(task_run.serialized_state).is_scheduled():
                task_runs_updated += 1
                self.client.set_task_run_state(
                    task_run_id=task_run.id,
                    version=task_run.version,
                    state=Submitted(
                        message="Submitted for execution.",
                        state=StateSchema().load(task_run.serialized_state),
                    ),
                )
        if task_runs_updated:
            self.logger.debug(
                f"Updated {task_runs_updated} task runs states for flow run "
                f"{flow_run.id} from  Scheduled -> Submitted"
            )

    def _mark_flow_as_failed(self, flow_run: GraphQLResult, message: str) -> None:
        """
        Mark a flow run as `Failed`

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object
            - exc (Exception): An exception that was raised to use as the `Failed`
                message
        """
        self.logger.error(
            f"Updating flow run {flow_run.id} state to Failed...",
        )
        self.client.set_flow_run_state(
            flow_run_id=flow_run.id,
            version=flow_run.version,
            state=Failed(message=message),
        )

    def _get_run_config(
        self, flow_run: GraphQLResult, run_config_cls: Type[RunConfig]
    ) -> RunConfig:
        """
        Get a run_config for the flow, if present. The returned run config is always of
        type `run_config_cls`

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object
            - run_config_cls (Callable): The expected run-config class

        Returns:
            - RunConfig: The flow run's run-config or an instance of `run_config_cls`
        """
        # If the flow is using a run_config, load it
        if getattr(flow_run, "run_config", None) is not None:
            run_config = RunConfigSchema().load(flow_run.run_config)
            if isinstance(run_config, UniversalRun):
                # Convert to agent-specific run-config
                return run_config_cls(env=run_config.env, labels=run_config.labels)
            elif not isinstance(run_config, run_config_cls):
                msg = (
                    "Flow run %s has a `run_config` of type `%s`, only `%s` is supported"
                    % (flow_run.id, type(run_config).__name__, run_config_cls.__name__)
                )
                self.logger.error(msg)
                raise TypeError(msg)
            return run_config

        # Otherwise, return the default run_config
        return run_config_cls()

    def _safe_write_run_log(
        self, flow_run: GraphQLResult, message: str, level: str
    ) -> None:
        """
        Write a log to the backend API for the given flow run. If the flow run object
        does not have an id, this is a no-op.

        Args:
            flow_run: The flow run object returned by a GQL query
            message: The log message
            level: The log level
        """
        if getattr(flow_run, "id", None):
            self.client.write_run_logs(
                [
                    dict(
                        flow_run_id=flow_run.id,
                        name=self.name,
                        message=message,
                        level=level,
                    )
                ]
            )

    # Backend API connection -----------------------------------------------------------

    def _register_agent(self) -> str:
        """
        Register this agent with a backend API and retrieve the ID

        Returns:
            - The agent ID as a string
        """

        config_id_blub = (
            f" with config {self.agent_config_id}" if self.agent_config_id else ""
        )
        self.logger.info(f"Registering agent{config_id_blub}...")

        agent_id = self.client.register_agent(
            agent_type=type(self).__name__,
            name=self.name,
            labels=self.labels,  # type: ignore
            agent_config_id=self.agent_config_id,
        )

        self.logger.info("Registration successful!")
        self.logger.debug(f"Assigned agent id: {agent_id}")

        if self.agent_config_id:
            self.agent_config = self._retrieve_agent_config()

        return agent_id

    def _retrieve_agent_config(self) -> dict:
        """
        Retrieve the configuration of an agent if an agent ID is provided

        Returns:
            - dict: a dictionary of agent configuration
        """
        if not self.agent_config_id:
            raise ValueError(
                "Cannot retrieve agent config without setting `agent_config_id`"
            )

        agent_config = self.client.get_agent_config(self.agent_config_id)
        self.logger.debug(f"Loaded agent config {self.agent_config_id}: {agent_config}")
        return agent_config

    def _setup_api_connection(self) -> None:
        """
        Sets up the agent's connection to Cloud

        - Gets an agent_id and attaches it to the headers
        - Runs a test query to check for a good setup

        Raises:
            RuntimeError: On failed test query
        """

        # Register agent with backend API
        self.client.attach_headers({"X-PREFECT-AGENT-ID": self._register_agent()})

        self.logger.debug(f"Sending test query to API at {config.cloud.api!r}...")

        try:
            self.client.graphql(query="query { hello }")
            self.logger.debug("Test query successful!")
        except Exception as exc:
            raise RuntimeError(
                f"Error while contacting API at {config.cloud.api}"
            ) from exc

    # Utilities ------------------------------------------------------------------------

    def _show_startup_display(self) -> None:
        print(ascii_name)
        self.logger.info(f"Starting {type(self).__name__} with labels {self.labels}")
        self.logger.info(
            "Agent documentation can be found at "
            "https://docs.prefect.io/orchestration/"
        )
        self.logger.info("Waiting for flow runs...")

    def _get_logger(self) -> logging.Logger:
        """
        Create an agent logger based on config options
        """

        logger = logging.getLogger(self.name)
        logger.setLevel(config.cloud.agent.get("level"))

        # Ensure it has a stream handler
        if not any(
            isinstance(handler, logging.StreamHandler) for handler in logger.handlers
        ):
            ch = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(context.config.logging.format)
            formatter.converter = time.gmtime  # type: ignore
            ch.setFormatter(formatter)
            logger.addHandler(ch)

        return logger


if __name__ == "__main__":
    Agent().start()
