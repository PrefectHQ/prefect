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
from typing import Any, Generator, Iterable, Set, Optional, cast, Type
from urllib.parse import urlparse

import pendulum
from tornado import web
from tornado.ioloop import IOLoop

from prefect import config
from prefect.client import Client
from prefect.engine.state import Failed, Submitted
from prefect.serialization import state
from prefect.serialization.run_config import RunConfigSchema
from prefect.run_configs import RunConfig, UniversalRun
from prefect.utilities.context import context
from prefect.utilities.exceptions import AuthorizationError
from prefect.utilities.graphql import GraphQLResult, with_args, EnumValue

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
        agent.logger.info("Keyboard Interrupt received: Agent is shutting down.")
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

    This Agent class is a standard point for executing Flows in Prefect Cloud. It is meant to
    have subclasses which inherit functionality from this class. The only piece that the
    subclasses should implement is the `deploy_flows` function, which specifies how to run a
    Flow on the given platform. It is built in this way to keep Prefect Cloud logic standard
    but allows for platform specific customizability.

    In order for this to operate `PREFECT__CLOUD__AGENT__AUTH_TOKEN` must be set as an
    environment variable or in your user configuration file.

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
        - max_polls (int, optional): maximum number of times the agent will poll Prefect Cloud
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
        no_cloud_logs: bool = False,
    ) -> None:
        # Load token and initialize client
        token = config.cloud.agent.get("auth_token")
        self.client = Client(api_server=config.cloud.api, api_token=token)

        self.agent_config_id = agent_config_id
        self.name = name or config.cloud.agent.get("name", "agent")
        self.labels = labels or list(config.cloud.agent.get("labels", []))
        self.env_vars = env_vars or config.cloud.agent.get("env_vars", dict())
        self.max_polls = max_polls
        self.log_to_cloud = False if no_cloud_logs else True
        self.heartbeat_period = 60  # exposed for testing

        self.agent_address = agent_address or config.cloud.agent.get(
            "agent_address", ""
        )

        self._api_server = None  # type: ignore
        self._api_server_loop: IOLoop = None
        self._api_server_thread: threading.Thread = None
        self._heartbeat_thread: threading.Thread = None
        self._agent_config: dict = None

        # Create the default logger
        self.logger = self._get_logger()

        self.submitting_flow_runs = set()  # type: Set[str]

        # Log configuration options
        self.logger.debug(f"Environment variables: {[*self.env_vars]}")
        self.logger.debug(f"Max polls: {self.max_polls}")
        self.logger.debug(f"Agent address: {self.agent_address}")
        self.logger.debug(f"Log to Cloud: {self.log_to_cloud}")
        self.logger.debug(f"Prefect backend: {config.backend}")

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

    def _verify_token(self, token: str) -> None:
        """
        Checks whether a token with a `RUNNER` scope was provided
        Args:
            - token (str): The provided agent token to verify
        Raises:
            - AuthorizationError: if token is empty or does not have a RUNNER role
        """
        if not token:
            raise AuthorizationError("No agent API token provided.")

        # Check if RUNNER role
        result = self.client.graphql(query="query { auth_info { api_token_scope } }")
        if (
            not result.data  # type: ignore
            or result.data.auth_info.api_token_scope != "RUNNER"  # type: ignore
        ):
            raise AuthorizationError("Provided token does not have a RUNNER scope.")

    def _register_agent(self) -> str:
        """
        Register this agent with a backend API and retrieve the ID

        Returns:
            - The agent ID as a string
        """
        agent_id = self.client.register_agent(
            agent_type=type(self).__name__,
            name=self.name,
            labels=self.labels,  # type: ignore
            agent_config_id=self.agent_config_id,
        )

        self.logger.debug(f"Agent ID: {agent_id}")

        if self.agent_config_id:
            self.agent_config = self._retrieve_agent_config()

        return agent_id

    def _retrieve_agent_config(self) -> dict:
        """
        Retrieve the configuration of an agent if an agent ID is provided

        Returns:
            - dict: a dictionary of agent configuration
        """
        agent_config = self.client.get_agent_config(self.agent_config_id)
        self.logger.debug(f"Loaded agent config {self.agent_config_id}: {agent_config}")
        return agent_config

    def _setup_api_connection(self) -> None:
        """
        Sets up the agent's connection to Cloud

        - Verifies token with Cloud
        - Gets an agent_id and attaches it to the headers
        - Runs a test query to check for a good setup
        """
        if config.backend == "cloud":
            self._verify_token(self.client.get_auth_token())

        # Register agent with backend API
        self.client.attach_headers({"X-PREFECT-AGENT-ID": self._register_agent()})

        self.logger.info(
            "Agent connecting to the Prefect API at {}".format(config.cloud.api)
        )

        try:
            self.client.graphql(query="query { hello }")
        except Exception as exc:
            self.logger.error(
                "There was an error connecting to {}".format(config.cloud.api)
            )
            self.logger.error(exc)

    def _enter_work_polling_loop(self) -> None:
        index = 0
        remaining_polls = math.inf if self.max_polls is None else self.max_polls

        # the max workers default has changed in 3.8. For stable results the
        # default 3.8 behavior is elected here.
        max_workers = min(32, (os.cpu_count() or 1) + 4)

        with exit_handler(self) as exit_event:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                self.logger.debug("Max Workers: {}".format(max_workers))
                while not exit_event.is_set() and remaining_polls:
                    # Reset the event in case it was set by poke handler.
                    AGENT_WAKE_EVENT.clear()

                    self.logger.info("Waiting for flow runs...")

                    if self.agent_process(executor):
                        index = 0
                    elif index < max(self._loop_intervals.keys()):
                        index += 1

                    remaining_polls -= 1

                    self.logger.debug(
                        "Next query for flow runs in {} seconds".format(
                            self._loop_intervals[index]
                        )
                    )

                    # Wait for loop interval timeout or agent to be poked by
                    # external process before querying for flow runs again.
                    AGENT_WAKE_EVENT.wait(timeout=self._loop_intervals[index])

    def _show_startup_display(self):
        print(ascii_name)
        self.logger.info(f"Starting {type(self).__name__} with labels {self.labels}")
        self.logger.info(
            "Agent documentation can be found at "
            "https://docs.prefect.io/orchestration/"
        )

    def start(self) -> None:
        """
        The main entrypoint to the agent process
        """

        try:
            self._setup_api_connection()

            # Call subclass hook
            self.on_startup()

            # Print some nice startup logs
            self._show_startup_display()

            # Start background tasks
            self._run_heartbeat_thread()
            self._run_agent_api_server()

            # Enter the main loop checking for new flows
            self._enter_work_polling_loop()

        finally:
            self.cleanup()

    def _run_agent_api_server(self):
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
                asyncio.get_event_loop()
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())

            self.logger.debug(
                f"Agent API server listening on port {self.agent_address}"
            )
            self._api_server = app.listen(port, address=hostname)  # type: ignore
            self._api_server_loop = IOLoop.current()
            self._api_server_loop.start()  # type: ignore

        self._api_server_thread = threading.Thread(
            name="api-server", target=run, daemon=True
        )
        self._api_server_thread.start()

    def _stop_agent_api_server(self):
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

    def cleanup(self) -> None:
        self.on_shutdown()
        self._stop_agent_api_server()
        self._stop_heartbeat_thread()

    def _run_heartbeat_thread(self) -> None:
        """
        Run a thread to send heartbeats to the backend API, should be called at `start`
        """

        def run() -> None:
            while True:
                try:
                    self.logger.debug("Running agent heartbeat...")
                    self.heartbeat()
                except Exception:
                    self.logger.error(
                        "Error in agent heartbeat, will try again in %.1f seconds",
                        self.heartbeat_period,
                        exc_info=True,
                    )
                else:
                    self.logger.debug(
                        "Sleeping heartbeat for %.1f seconds", self.heartbeat_period
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
            self.logger.debug("Stopping heartbeat thread")
            self._heartbeat_thread.join(timeout=1)

    def deploy_and_update_flow_run(self, flow_run: "GraphQLResult") -> None:
        """
        Deploy a flow run and update Cloud with the resulting deployment info.
        If any errors occur when submitting the flow run, capture the error and log to Cloud.

        Args:
            - flow_run (GraphQLResult): The specific flow run to deploy
        """
        # Deploy flow run and mark failed if any deployment error
        try:
            self._mark_flow_as_submitted(flow_run)
            deployment_info = self.deploy_flow(flow_run)
            if getattr(flow_run, "id", None):
                self.client.write_run_logs(
                    [
                        dict(
                            flow_run_id=getattr(flow_run, "id"),  # type: ignore
                            name=self.name,
                            message="Submitted for execution: {}".format(
                                deployment_info
                            ),
                            level="INFO",
                        )
                    ]
                )
        except Exception as exc:
            # if the state update failed, we don't want to follow up with another state update
            if "State update failed" in str(exc):
                self.logger.debug("Updating Flow Run state failed: {}".format(str(exc)))
                return
            self.logger.error(
                "Logging platform error for flow run {}".format(
                    getattr(flow_run, "id", "UNKNOWN")  # type: ignore
                )
            )
            if getattr(flow_run, "id", None):
                self.client.write_run_logs(
                    [
                        dict(
                            flow_run_id=getattr(flow_run, "id"),  # type: ignore
                            name=self.name,
                            message=str(exc),
                            level="ERROR",
                        )
                    ]
                )
            self._mark_flow_as_failed(flow_run=flow_run, exc=exc)

    def on_flow_run_deploy_attempt(self, fut: "Future", flow_run_id: str) -> None:
        """
        Indicates that a flow run deployment has been deployed (successfully or otherwise).
        This is intended to be a future callback hook, called in the agent's main thread
        when the background thread has completed the deploy_and_update_flow_run() call, either
        successfully, in error, or cancelled. In all cases the agent should be open to
        attempting to deploy the flow run if the flow run id is still in the Cloud run queue.

        Args:
            - fut (Future): a callback requirement, the future which has completed or been
                cancelled.
            - flow_run_id (str): the id of the flow run that the future represents.
        """
        self.submitting_flow_runs.remove(flow_run_id)
        self.logger.debug("Completed flow run submission (id: {})".format(flow_run_id))

    def agent_process(self, executor: "ThreadPoolExecutor") -> bool:
        """
        Full process for finding flow runs, updating states, and deploying.

        Args:
            - executor (ThreadPoolExecutor): the interface to submit flow deployments in
                background threads

        Returns:
            - bool: whether or not flow runs were found
        """
        flow_runs = None
        try:
            flow_runs = self.query_flow_runs()

            if flow_runs:
                self.logger.info(
                    "Found {} flow run(s) to submit for execution.".format(
                        len(flow_runs)
                    )
                )

            for flow_run in flow_runs:
                fut = executor.submit(self.deploy_and_update_flow_run, flow_run)
                self.submitting_flow_runs.add(flow_run.id)
                fut.add_done_callback(
                    functools.partial(
                        self.on_flow_run_deploy_attempt, flow_run_id=flow_run.id
                    )
                )

        except Exception as exc:
            self.logger.error(exc)

        return bool(flow_runs)

    def query_flow_runs(self) -> list:
        """
        Query Prefect Cloud for flow runs which need to be deployed and executed

        Returns:
            - list: A list of GraphQLResult flow run objects
        """
        self.logger.debug("Querying for flow runs")
        # keep a copy of what was curringly running before the query
        # (future callbacks may be updating this set)
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
                    "before": now.isoformat(),
                    "labels": list(self.labels),
                    "tenant_id": self.client.active_tenant_id,
                }
            },
        )

        # we queried all of the available flow runs, however, some may have already been pulled
        # by this agent and are in the process of being submitted in the background. We do not
        # want to act on these "duplicate" flow runs until we've been assured that the background
        # thread has attempted to submit the work (successful or otherwise).
        flow_run_ids = set(result.data.get_runs_in_queue.flow_run_ids)  # type: ignore

        if flow_run_ids:
            msg = "Found flow runs {}".format(
                result.data.get_runs_in_queue.flow_run_ids
            )
        else:
            msg = "No flow runs found"

        already_submitting = flow_run_ids & currently_submitting_flow_runs
        target_flow_run_ids = flow_run_ids - already_submitting

        if already_submitting:
            msg += " ({} already submitting: {})".format(
                len(already_submitting), list(already_submitting)
            )

        self.logger.debug(msg)

        if target_flow_run_ids:

            self.logger.debug("Querying flow run metadata")
            return self._get_flow_run_metadata(
                target_flow_run_ids, start_time=now.subtract(seconds=3)
            )

        else:
            return []

    def _get_flow_run_metadata(
        self, flow_run_ids: Iterable[str], start_time: pendulum.DateTime
    ) -> list:
        """
        Get metadata about a collection of flow run ids

        Args:
            flow_run_ids: Flow run ids to query (order will not be respected)
            start_time: Only

        Returns:
           List: Metadata per flow run sorted by scheduled start time (ascending)
        """
        query = {
            "query": {
                with_args(
                    "flow_run",
                    {
                        # match flow runs in the flow_run_ids list
                        "where": {
                            "id": {"_in": list(flow_run_ids)},
                            "_or": [
                                # who are EITHER scheduled...
                                {"state": {"_eq": "Scheduled"}},
                                # OR running with task runs scheduled to start more than 3
                                # seconds ago
                                {
                                    "state": {"_eq": "Running"},
                                    "task_runs": {
                                        "state_start_time": {
                                            "_lte": str(start_time)  # type: ignore
                                        }
                                    },
                                },
                            ],
                        },
                        "order_by": {"scheduled_start_time": EnumValue("asc")},
                    },
                ): {
                    "id": True,
                    "version": True,
                    "state": True,
                    "serialized_state": True,
                    "parameters": True,
                    "scheduled_start_time": True,
                    "run_config": True,
                    "flow": {
                        "id",
                        "name",
                        "environment",
                        "storage",
                        "version",
                        "core_version",
                    },
                    with_args(
                        "task_runs",
                        {
                            "where": {
                                "state_start_time": {
                                    "_lte": str(start_time)  # type: ignore
                                }
                            }
                        },
                    ): {"id", "version", "task_id", "serialized_state"},
                }
            }
        }
        result = self.client.graphql(query)
        return result.data.flow_run

    def _mark_flow_as_submitted(self, flow_run: GraphQLResult) -> None:
        """
        After a flow run is grabbed this function sets the state to Submitted so it
        won't be picked up by any other processes

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object
        """
        self.logger.debug(f"Updating states for flow run {flow_run.id}")

        # Set flow run state to `Submitted` if it is currently `Scheduled`
        if state.StateSchema().load(flow_run.serialized_state).is_scheduled():

            self.logger.debug(
                f"Flow run {flow_run.id} is in a Scheduled state, updating to Submitted"
            )
            self.client.set_flow_run_state(
                flow_run_id=flow_run.id,
                version=flow_run.version,
                state=Submitted(
                    message="Submitted for execution",
                    state=state.StateSchema().load(flow_run.serialized_state),
                ),
            )

        # Set task run states to `Submitted` if they are currently `Scheduled`
        task_runs_updated = 0
        for task_run in flow_run.task_runs:
            if state.StateSchema().load(task_run.serialized_state).is_scheduled():
                task_runs_updated += 1
                self.client.set_task_run_state(
                    task_run_id=task_run.id,
                    version=task_run.version,
                    state=Submitted(
                        message="Submitted for execution.",
                        state=state.StateSchema().load(task_run.serialized_state),
                    ),
                )
        if task_runs_updated:
            self.logger.debug(
                f"Updated {task_runs_updated} task runs from Scheduled state to "
                f"Submitted"
            )

    def _mark_flow_as_failed(self, flow_run: GraphQLResult, exc: Exception) -> None:
        """
        Mark a flow run as `Failed`

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object
            - exc (Exception): An exception that was raised to use as the `Failed`
                message
        """
        self.client.set_flow_run_state(
            flow_run_id=flow_run.id,
            version=flow_run.version,
            state=Failed(message=str(exc)),
        )
        self.logger.error("Error while deploying flow", exc_info=exc)

    def _get_run_config(
        self, flow_run: GraphQLResult, run_config_cls: Type[RunConfig]
    ) -> Optional[RunConfig]:
        """
        Get a run_config for the flow, if present.

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object
            - run_config_cls (Callable): The expected run-config class

        Returns:
            - RunConfig: The flow run's run-config. Returns None if an
                environment-based flow.
        """
        # If the flow is using a run_config, load it
        if getattr(flow_run, "run_config", None) is not None:
            run_config = RunConfigSchema().load(flow_run.run_config)
            if isinstance(run_config, UniversalRun):
                # Convert to agent-specific run-config
                return run_config_cls(labels=run_config.labels)
            elif not isinstance(run_config, run_config_cls):
                msg = (
                    "Flow run %s has a `run_config` of type `%s`, only `%s` is supported"
                    % (flow_run.id, type(run_config).__name__, run_config_cls.__name__)
                )
                self.logger.error(msg)
                raise TypeError(msg)
            return run_config
        elif getattr(flow_run.flow, "environment", None) is None:
            # No environment, use default run_config
            return run_config_cls()

        return None

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


if __name__ == "__main__":
    Agent().start()
