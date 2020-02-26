import ast
import functools
import logging
import os
import signal
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Generator, Iterable, Set, Union

import pendulum

from prefect import config
from prefect.client import Client
from prefect.engine.state import Failed, Submitted
from prefect.serialization import state
from prefect.utilities.context import context
from prefect.utilities.exceptions import AuthorizationError
from prefect.utilities.graphql import GraphQLResult, with_args

ascii_name = r"""
 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/
"""


@contextmanager
def exit_handler(agent: "Agent") -> Generator:
    exit_event = threading.Event()

    def _exit_handler(*args: Any, **kwargs: Any) -> None:
        agent.logger.info("Keyboard Interrupt received: Agent is shutting down.")
        exit_event.set()

    original = signal.getsignal(signal.SIGINT)
    try:
        signal.signal(signal.SIGINT, _exit_handler)
        yield exit_event
    except SystemExit:
        pass
    finally:
        signal.signal(signal.SIGINT, original)


class Agent:
    """
    Base class for Agents. Information on using the Prefect agents can be found at
    https://docs.prefect.io/cloud/agents/overview.html

    This Agent class is a standard point for executing Flows in Prefect Cloud. It is meant
    to have subclasses which inherit functionality from this class. The only piece that
    the subclasses should implement is the `deploy_flows` function, which specifies how to run a Flow on the given platform. It is built in this
    way to keep Prefect Cloud logic standard but allows for platform specific
    customizability.

    In order for this to operate `PREFECT__CLOUD__AGENT__AUTH_TOKEN` must be set as an
    environment variable or in your user configuration file.

    Args:
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - env_vars (dict, optional): a dictionary of environment variables and values that will be set
            on each flow run that this agent submits for execution
    """

    def __init__(
        self, name: str = None, labels: Iterable[str] = None, env_vars: dict = None
    ) -> None:
        self.name = name or config.cloud.agent.get("name", "agent")
        self.labels = list(
            labels or ast.literal_eval(config.cloud.agent.get("labels", "[]"))
        )
        self.env_vars = env_vars or dict()
        self.log_to_cloud = config.logging.log_to_cloud

        token = config.cloud.agent.get("auth_token")

        self.client = Client(api_token=token)
        self._verify_token(token)

        logger = logging.getLogger(self.name)
        logger.setLevel(config.cloud.agent.get("level"))
        if not any([isinstance(h, logging.StreamHandler) for h in logger.handlers]):
            ch = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(context.config.logging.format)
            formatter.converter = time.gmtime  # type: ignore
            ch.setFormatter(formatter)
            logger.addHandler(ch)

        self.logger = logger
        self.submitting_flow_runs = set()  # type: Set[str]

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
        result = self.client.graphql(query="query { authInfo { apiTokenScope } }")
        if (
            not result.data  # type: ignore
            or result.data.authInfo.apiTokenScope != "RUNNER"  # type: ignore
        ):
            raise AuthorizationError("Provided token does not have a RUNNER scope.")

    def start(self) -> None:
        """
        The main entrypoint to the agent. This function loops and constantly polls for
        new flow runs to deploy
        """
        try:
            with exit_handler(self) as exit_event:
                tenant_id = self.agent_connect()

                # Loop intervals for query sleep backoff
                loop_intervals = {
                    0: 0.25,
                    1: 0.5,
                    2: 1.0,
                    3: 2.0,
                    4: 4.0,
                    5: 8.0,
                    6: 10.0,
                }

                index = 0

                # the max workers default has changed in 3.5 and 3.8. For stable results the
                # default 3.8 behavior is elected here.
                max_workers = min(32, (os.cpu_count() or 1) + 4)

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    self.logger.debug("Max Workers: {}".format(max_workers))
                    while not exit_event.wait(timeout=loop_intervals[index]):
                        self.heartbeat()

                        if self.agent_process(executor, tenant_id):
                            index = 0
                        elif index < max(loop_intervals.keys()):
                            index += 1

                        self.logger.debug(
                            "Next query for flow runs in {} seconds".format(
                                loop_intervals[index]
                            )
                        )
        finally:
            self.on_shutdown()

    def on_shutdown(self) -> None:
        """
        Invoked when the event loop is exiting and the agent is shutting down. Intended
        as a hook for child classes to optionally implement.
        """

    def agent_connect(self) -> str:
        """
        Verify agent connection to Prefect Cloud by finding and returning a tenant id

        Returns:
            - str: The current tenant id
        """
        print(ascii_name)
        self.logger.info(
            "Starting {} with labels {}".format(type(self).__name__, self.labels)
        )
        self.logger.info(
            "Agent documentation can be found at https://docs.prefect.io/cloud/"
        )

        self.logger.debug("Querying for tenant ID")
        tenant_id = self.query_tenant_id()

        if not tenant_id:
            raise ConnectionError(
                "Tenant ID not found. Verify that you are using the proper API token."
            )

        self.logger.debug("Tenant ID: {} found".format(tenant_id))
        self.logger.info("Agent successfully connected to Prefect Cloud")
        self.logger.info("Waiting for flow runs...")

        return tenant_id

    def deploy_and_update_flow_run(self, flow_run: "GraphQLResult") -> None:
        """
        Deploy a flow run and update Cloud with the resulting deployment info.
        If any errors occur when submitting the flow run, capture the error and log to Cloud.

        Args:
            - flow_run (GraphQLResult): The specific flow run to deploy
        """
        # Deploy flow run and mark failed if any deployment error
        try:
            self.update_state(flow_run)
            deployment_info = self.deploy_flow(flow_run)
            if getattr(flow_run, "id", None):
                self.client.write_run_logs(
                    [
                        dict(
                            flowRunId=getattr(flow_run, "id"),  # type: ignore
                            name=self.name,
                            message="Submitted for execution: {}".format(
                                deployment_info
                            ),
                            level="INFO",
                        )
                    ]
                )
        except Exception as exc:
            ## if the state update failed, we don't want to follow up with another state update
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
                            flowRunId=getattr(flow_run, "id"),  # type: ignore
                            name=self.name,
                            message=str(exc),
                            level="ERROR",
                        )
                    ]
                )
            self.mark_failed(flow_run=flow_run, exc=exc)

    def on_flow_run_deploy_attempt(self, fut: "Future", flow_run_id: str) -> None:
        """
        Indicates that a flow run deployment has been deployed (sucessfully or otherwise).
        This is intended to be a future callback hook, called in the agent's main thread
        when the background thread has completed the deploy_and_update_flow_run() call, either
        successfully, in error, or cancelled. In all cases the agent should be open to
        attempting to deploy the flow run if the flow run id is still in the Cloud run queue.

        Args:
            - fut (Future): a callback requirement, the future which has completed or been cancelled.
            - flow_run_id (str): the id of the flow run that the future represents.
        """
        self.submitting_flow_runs.remove(flow_run_id)
        self.logger.debug("Completed flow run submission (id: {})".format(flow_run_id))

    def agent_process(self, executor: "ThreadPoolExecutor", tenant_id: str) -> bool:
        """
        Full process for finding flow runs, updating states, and deploying.

        Args:
            - executor (ThreadPoolExecutor): the interface to submit flow deployments in background threads
            - tenant_id (str): The tenant id to use in the query

        Returns:
            - bool: whether or not flow runs were found
        """
        flow_runs = None
        try:
            flow_runs = self.query_flow_runs(tenant_id=tenant_id)

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

    def query_tenant_id(self) -> Union[str, None]:
        """
        Query Prefect Cloud for the tenant id that corresponds to the agent's auth token

        Returns:
            - Union[str, None]: The current tenant id if found, None otherwise
        """
        query = {"query": {"tenant": {"id"}}}
        result = self.client.graphql(query)

        if result.data.tenant:  # type: ignore
            return result.data.tenant[0].id  # type: ignore

        return None

    def query_flow_runs(self, tenant_id: str) -> list:
        """
        Query Prefect Cloud for flow runs which need to be deployed and executed

        Args:
            - tenant_id (str): The tenant id to use in the query

        Returns:
            - list: A list of GraphQLResult flow run objects
        """
        self.logger.debug("Querying for flow runs")
        # keep a copy of what was curringly running before the query (future callbacks may be updating this set)
        currently_submitting_flow_runs = self.submitting_flow_runs.copy()

        # Get scheduled flow runs from queue
        mutation = {
            "mutation($input: getRunsInQueueInput!)": {
                "getRunsInQueue(input: $input)": {"flow_run_ids"}
            }
        }

        now = pendulum.now("UTC")
        result = self.client.graphql(
            mutation,
            variables={
                "input": {
                    "tenantId": tenant_id,
                    "before": now.isoformat(),
                    "labels": list(self.labels),
                }
            },
        )

        # we queried all of the available flow runs, however, some may have already been pulled
        # by this agent and are in the process of being submitted in the background. We do not
        # want to act on these "duplicate" flow runs until we've been assured that the background
        # thread has attempted to submit the work (successful or otherwise).
        flow_run_ids = set(result.data.getRunsInQueue.flow_run_ids)  # type: ignore

        if flow_run_ids:
            msg = "Found flow runs {}".format(result.data.getRunsInQueue.flow_run_ids)
        else:
            msg = "No flow runs found"

        already_submitting = flow_run_ids & currently_submitting_flow_runs
        target_flow_run_ids = flow_run_ids - already_submitting

        if already_submitting:
            msg += " ({} already submitting: {})".format(
                len(already_submitting), list(already_submitting)
            )

        self.logger.debug(msg)

        # Query metadata fow flow runs found in queue
        query = {
            "query": {
                with_args(
                    "flow_run",
                    {
                        # match flow runs in the flow_run_ids list
                        "where": {
                            "id": {"_in": list(target_flow_run_ids)},
                            "_or": [
                                # who are EITHER scheduled...
                                {"state": {"_eq": "Scheduled"}},
                                # OR running with task runs scheduled to start more than 3 seconds ago
                                {
                                    "state": {"_eq": "Running"},
                                    "task_runs": {
                                        "state_start_time": {
                                            "_lte": str(now.subtract(seconds=3))
                                        }
                                    },
                                },
                            ],
                        }
                    },
                ): {
                    "id": True,
                    "version": True,
                    "tenant_id": True,
                    "state": True,
                    "serialized_state": True,
                    "parameters": True,
                    "flow": {"id", "name", "environment", "storage", "version"},
                    with_args(
                        "task_runs",
                        {
                            "where": {
                                "state_start_time": {
                                    "_lte": str(now.subtract(seconds=3))
                                }
                            }
                        },
                    ): {"id", "version", "task_id", "serialized_state"},
                }
            }
        }

        if target_flow_run_ids:
            self.logger.debug("Querying flow run metadata")
            result = self.client.graphql(query)
            return result.data.flow_run  # type: ignore
        else:
            return []

    def update_state(self, flow_run: GraphQLResult) -> None:
        """
        After a flow run is grabbed this function sets the state to Submitted so it
        won't be picked up by any other processes

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object
        """
        self.logger.debug(
            "Updating states for flow run {}".format(flow_run.id)  # type: ignore
        )

        # Set flow run state to `Submitted` if it is currently `Scheduled`
        if state.StateSchema().load(flow_run.serialized_state).is_scheduled():

            self.logger.debug(
                "Flow run {} is in a Scheduled state, updating to Submitted".format(
                    flow_run.id  # type: ignore
                )
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
        for task_run in flow_run.task_runs:
            if state.StateSchema().load(task_run.serialized_state).is_scheduled():

                self.logger.debug(
                    "Task run {} is in a Scheduled state, updating to Submitted".format(
                        task_run.id  # type: ignore
                    )
                )
                self.client.set_task_run_state(
                    task_run_id=task_run.id,
                    version=task_run.version,
                    state=Submitted(
                        message="Submitted for execution.",
                        state=state.StateSchema().load(task_run.serialized_state),
                    ),
                )

    def mark_failed(self, flow_run: GraphQLResult, exc: Exception) -> None:
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
        self.logger.error("Error while deploying flow: {}".format(repr(exc)))

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Meant to be overridden by a platform specific deployment option

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
        Meant to be overridden by a platform specific heartbeat option
        """


if __name__ == "__main__":
    Agent().start()
